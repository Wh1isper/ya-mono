"""Regression contracts for the native streamed node lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic_ai import ModelRequestNode
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_graph import End
from ya_agent_sdk.agents.main import create_agent, stream_agent
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.environment.local import LocalEnvironment


@dataclass
class _NodeLifecycle(AbstractCapability[AgentContext]):
    trace: list[str] = field(default_factory=list)
    inside_wrapper: bool = False
    recover: bool = False
    enqueue_at_end: bool = False

    async def wrap_node_run(self, ctx, *, node, handler):
        self.inside_wrapper = True
        try:
            result = await handler(node)
            if isinstance(result, End) and self.enqueue_at_end:
                self.enqueue_at_end = False
                ctx.enqueue("late steering", priority="when_idle")
            return result
        finally:
            self.inside_wrapper = False

    async def before_node_run(self, ctx, *, node):
        assert self.inside_wrapper
        if isinstance(node, ModelRequestNode):
            self.trace.append("before")
        return node

    async def on_node_run_error(self, ctx, *, node, error):
        assert self.inside_wrapper
        self.trace.append("error")
        if not self.recover:
            raise error
        self.recover = False
        return ModelRequestNode(request=ModelRequest(parts=[UserPromptPart("recover")]))

    async def after_node_run(self, ctx, *, node, result):
        assert self.inside_wrapper
        if isinstance(node, ModelRequestNode):
            self.trace.append("after")
        return result


@pytest.mark.parametrize("recover,late", [(False, False), (True, False), (False, True)])
async def test_streamed_driver_delegates_complete_native_lifecycle(tmp_path: Path, recover: bool, late: bool) -> None:
    capability = _NodeLifecycle(recover=recover, enqueue_at_end=late)
    calls: list[list[ModelMessage]] = []

    async def stream_function(messages: list[ModelMessage], _info: AgentInfo):
        assert capability.inside_wrapper
        capability.trace.append("stream")
        calls.append(list(messages))
        if recover and len(calls) == 1:
            raise RuntimeError("recover inside native node lifecycle")
        yield "answer"

    runtime = create_agent(
        FunctionModel(stream_function=stream_function),
        env=LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path),
        capabilities=[capability],
    )
    async with stream_agent(runtime, "start", resume_on_error=False) as streamer:
        async for _event in streamer:
            pass
        streamer.raise_if_exception()

    assert capability.inside_wrapper is False
    if recover:
        assert capability.trace == ["before", "stream", "error", "after", "before", "stream", "after"]
    elif late:
        assert capability.trace == ["before", "stream", "after"] * 2
        assert any(
            isinstance(message, ModelRequest)
            and any(isinstance(part, UserPromptPart) and part.content == "late steering" for part in message.parts)
            for message in calls[-1]
        )
    else:
        assert capability.trace == ["before", "stream", "after"]
