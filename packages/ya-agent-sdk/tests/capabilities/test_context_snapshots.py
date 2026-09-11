"""Canonical context survives native cleanup and request-only projections.

Provider mapping is exercised offline: request methods only map and capture payloads.
"""

from __future__ import annotations

import copy
import io
import json
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import pytest
from PIL import Image
from pydantic_ai import RunContext, capture_run_messages
from pydantic_ai.capabilities import AbstractCapability, CombinedCapability, ReinjectSystemPrompt
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestContext, ModelRequestParameters
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RequestUsage, RunUsage
from ya_agent_sdk.agents.main import create_agent
from ya_agent_sdk.capabilities import RuntimeFoundationCapability
from ya_agent_sdk.capabilities.foundation.history import (
    ColdStartCapability,
    ContextCompactionCapability,
    HandoffCapability,
)
from ya_agent_sdk.capabilities.foundation.request import EnvironmentContextCapability, RuntimeContextCapability
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.presets import get_model_cfg


@dataclass
class PingCapability(AbstractCapability[AgentContext]):
    holder: dict[str, Any]
    enqueue: bool

    def get_toolset(self):
        toolset = FunctionToolset()

        @toolset.tool_plain
        def ping() -> str:
            """Return a fixed tool result, optionally accompanied by native input."""
            if self.enqueue:
                self.holder["run"].enqueue("New user guidance")
            return "pong"

        return toolset


class CaptureOpenAI(OpenAIResponsesModel):
    captures: list[dict[str, Any]]
    request_messages: list[list[ModelMessage]]

    async def request(self, messages, model_settings, model_request_parameters):
        instructions, inputs = await self._map_messages(messages, model_settings or {}, model_request_parameters)
        self.captures.append({"system": str(instructions), "input": copy.deepcopy(inputs)})
        self.request_messages.append(copy.deepcopy(messages))
        return _response(len(self.captures))


class CaptureAnthropic(AnthropicModel):
    captures: list[dict[str, Any]]
    request_messages: list[list[ModelMessage]]

    async def request(self, messages, model_settings, model_request_parameters):
        system, inputs = await self._map_message(messages, model_request_parameters, model_settings or {})
        # The Anthropic SDK serializes binary image streams later; compare their
        # bytes rather than BytesIO object identity in these offline wire captures.
        captured_inputs = json.loads(json.dumps(inputs, default=lambda value: value.getvalue().hex()))
        self.captures.append({"system": system, "input": captured_inputs})
        self.request_messages.append(copy.deepcopy(messages))
        return _response(len(self.captures))


def _response(number: int) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart("ping", {}, tool_call_id=f"call_{number}")] if number < 3 else [TextPart("done")],
        usage=RequestUsage(input_tokens=100 * number, output_tokens=10),
    )


def _contexts(messages: list[ModelMessage], tag: str) -> list[str]:
    return [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str) and tag in part.content
    ]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("scenario", ["ordinary", "consecutive", "inspection", "media", "enqueue"])
async def test_context_prefix_survives_provider_projection(agent_context, provider, scenario) -> None:
    if provider == "openai":
        model = CaptureOpenAI("gpt-5", provider=OpenAIProvider(api_key="offline-test"))
    else:
        model = CaptureAnthropic("claude-sonnet-4-5", provider=AnthropicProvider(api_key="offline-test"))
    model.captures = []
    model.request_messages = []
    holder: dict[str, Any] = {}
    runtime = create_agent(
        model,
        env=agent_context.env,
        model_cfg=get_model_cfg("gpt5_350k"),
        system_prompt="REAL SYSTEM",
        capabilities=[RuntimeFoundationCapability(), PingCapability(holder, scenario == "enqueue")],
    )
    if scenario == "inspection":
        runtime.ctx.files_to_inspect = ["example.py"]
    history = [ModelRequest(parts=[UserPromptPart("Earlier pending input")])] if scenario == "consecutive" else []
    source_history = copy.deepcopy(history)
    prompt: Any = "Start task"
    image = None
    if scenario == "media":
        buffer = io.BytesIO()
        Image.new("RGB", (100, 5000), "white").save(buffer, format="PNG")
        image = BinaryContent(buffer.getvalue(), media_type="image/png")
        prompt = ["Inspect this image", image]

    try:
        async with runtime:
            async with runtime.agent.iter(prompt, deps=runtime.ctx, message_history=history) as run:
                holder["run"] = run
                async for _ in run:
                    pass
            assert run.result is not None
            # Round-trip the actual canonical history, not the model's request-only view.
            canonical = ModelMessagesTypeAdapter.validate_json(run.result.all_messages_json())
    finally:
        await model.client.close()

    assert history == source_history
    assert len(model.captures) == 3
    snapshots = [_contexts(messages, "<runtime-context>") for messages in model.request_messages]
    assert [len(items) for items in snapshots] == [1, 2, 3]
    assert _contexts(canonical, "<runtime-context>") == snapshots[-1]
    assert "<total-tokens>110</total-tokens>" in snapshots[1][-1]
    for previous, current in pairwise(snapshots):
        assert current[: len(previous)] == previous
    environment = _contexts(canonical, "<environment")
    assert environment
    assert _contexts(model.request_messages[-1], "<environment") == environment
    assert all(
        "REAL SYSTEM" in str(item["system"])
        if provider == "anthropic"
        else {"role": "system", "content": "REAL SYSTEM"} in item["input"]
        for item in model.captures
    )
    assert all("<system>REAL SYSTEM</system>" not in json.dumps(item["input"]) for item in model.captures)
    assert all(item["system"] == model.captures[0]["system"] for item in model.captures)

    # One-shot reminders intentionally disappear. All other cases keep the full
    # prior provider input, even when canonical requests were merged or images split.
    if scenario != "inspection":
        for previous, current in pairwise(model.captures):
            assert current["input"][: len(previous["input"])] == previous["input"]
    else:
        assert "<files-to-inspect" in json.dumps(model.captures[0]["input"])
        assert "<files-to-inspect" not in json.dumps(model.captures[1]["input"])
        assert not _contexts(canonical, "<files-to-inspect")
        assert runtime.ctx.files_to_inspect == []
    if image is not None:

        def images(messages):
            return [
                item
                for message in messages
                if isinstance(message, ModelRequest)
                for part in message.parts
                if isinstance(part, UserPromptPart) and not isinstance(part.content, str)
                for item in part.content
                if isinstance(item, BinaryContent)
            ]

        assert [(item.data, item.media_type) for item in images(canonical)] == [(image.data, image.media_type)]
        assert len(images(model.request_messages[0])) == 2


async def test_snapshot_is_copy_on_write_and_reads_retained_history(agent_context) -> None:
    model = TestModel()
    stale = [ModelResponse(parts=[TextPart("discarded")], usage=RequestUsage(input_tokens=99999))]
    retained = [ModelRequest(parts=[UserPromptPart("restored")], metadata={"keep": "handoff"})]
    source = copy.deepcopy(retained)
    ctx = RunContext(deps=agent_context, model=model, usage=RunUsage(), messages=stale)
    request = ModelRequestContext(
        model=model, messages=retained, model_settings={}, model_request_parameters=ModelRequestParameters()
    )
    request.model_id = "test-id"
    request.streaming = True

    updated = await RuntimeContextCapability().before_model_request(ctx, request)
    assert updated is not request
    assert retained == source
    assert ctx.messages == stale
    assert updated.model_id == "test-id"
    assert updated.streaming is True
    assert "<token-usage>" not in _contexts(updated.messages, "<runtime-context>")[0]
    assert updated.messages[-1].metadata == {"keep": "handoff", "ya:runtime_context": True}
    repeated = await RuntimeContextCapability().before_model_request(ctx, updated)
    assert repeated is updated


async def test_failed_request_snapshot_survives_native_resume_without_duplication(agent_context) -> None:
    class FailingModel(TestModel):
        async def request(self, messages, model_settings, model_request_parameters):
            raise RuntimeError("offline request failure")

    capabilities = [RuntimeFoundationCapability()]
    async with create_agent(FailingModel(), env=agent_context.env, capabilities=capabilities) as runtime:
        with capture_run_messages() as messages, pytest.raises(RuntimeError, match="offline request failure"):
            await runtime.agent.run("Continue", deps=runtime.ctx)
    before = ModelMessagesTypeAdapter.validate_json(ModelMessagesTypeAdapter.dump_json(messages))
    assert len(_contexts(before, "<runtime-context>")) == 1
    assert len(_contexts(before, "<environment")) == 1

    async with create_agent(
        TestModel(custom_output_text="ok", call_tools=[]), env=agent_context.env, capabilities=capabilities
    ) as runtime:
        result = await runtime.agent.run(message_history=before, deps=runtime.ctx)
    assert _contexts(result.all_messages(), "<runtime-context>") == _contexts(before, "<runtime-context>")
    assert _contexts(result.all_messages(), "<environment") == _contexts(before, "<environment")


@pytest.mark.parametrize("snapshot", [EnvironmentContextCapability, RuntimeContextCapability])
@pytest.mark.parametrize(
    "predecessor", [HandoffCapability, ContextCompactionCapability, ColdStartCapability, ReinjectSystemPrompt]
)
def test_snapshot_ordering_with_optional_lifecycle_capabilities(snapshot, predecessor) -> None:
    # Reversed caller order must not put context ahead of a standalone reducer or reinjection.
    combined = CombinedCapability([snapshot(), predecessor()])
    assert [type(cap) for cap in combined.capabilities] == [predecessor, snapshot]
