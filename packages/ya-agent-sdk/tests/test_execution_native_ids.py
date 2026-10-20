"""Native IDs survive suspension, JSON checkpoints, host decisions and healing."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter
from pydantic_ai import ApprovalRequired, CallDeferred, DeferredToolRequests, RunContext
from pydantic_ai.capabilities import Capability
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessagesTypeAdapter,
    PartEndEvent,
    PartStartEvent,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import DeltaThinkingPart, DeltaToolCall, FunctionModel
from ya_agent_sdk.agents.main import create_agent
from ya_agent_sdk.capabilities import SelfHealingModelCapability
from ya_agent_sdk.context import AgentContext, ResumableState
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.execution import AgentExecutionHarness, AgentSegmentRequest, AgentSegmentStatus
from ya_agent_sdk.interactions import DeferredApprovalResolution, DeferredCallResolution, DeferredInteractionResolver


@pytest.mark.parametrize("tool_call_id", ["call_native_123", "call_123|fc_123", "ya-persisted-legacy-id"])
@pytest.mark.parametrize("decision", ["approved", "denied", "external"])
async def test_checkpoint_continuation_preserves_native_ids_and_executes_once(
    tmp_path: Path, tool_call_id: str, decision: str
) -> None:
    effects: list[str] = []
    model_attempts = 0
    events = []
    metadata = {"reviewer": "test", "reason": "side effect"}

    async def guarded_effect(ctx: RunContext[AgentContext], value: str) -> str:
        if decision == "external":
            raise CallDeferred(metadata=metadata)
        if not ctx.tool_call_approved:
            raise ApprovalRequired(metadata=metadata)
        effects.append(value)
        return value

    async def model_stream(messages, _info):
        nonlocal model_attempts
        results = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
        if not results:
            yield {0: DeltaThinkingPart(content="plan", signature="provider-signature")}
            yield {1: DeltaToolCall(name="guarded_effect", json_args='{"value":"original"}', tool_call_id=tool_call_id)}
            return
        model_attempts += 1
        assert results[-1].tool_call_id == tool_call_id
        if model_attempts == 1:
            raise ModelHTTPError(400, "test", body="Invalid signature in thinking block")
        assert not any(isinstance(part, ThinkingPart) for message in messages for part in message.parts)
        yield "finished"

    def runtime(state=None):
        return create_agent(
            FunctionModel(stream_function=model_stream),
            env=LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path),
            capabilities=[Capability(tools=[guarded_effect]), SelfHealingModelCapability()],
            output_type=[str, DeferredToolRequests],
            state=state,
        )

    async def collect(event):
        events.append(event.event)

    harness = AgentExecutionHarness()
    suspended = await harness.execute_segment(runtime(), AgentSegmentRequest(user_prompt="do it"), event_sink=collect)
    assert suspended.status is AgentSegmentStatus.suspended
    assert effects == []
    requests = suspended.deferred_requests
    assert requests is not None
    assert [part.tool_call_id for part in requests.calls + requests.approvals] == [tool_call_id]
    assert requests.metadata == {tool_call_id: metadata}
    assert not any(
        isinstance(part, ToolReturnPart) for message in suspended.checkpoint.messages for part in message.parts
    )

    # Simulate a host store round trip and a newly constructed runtime.
    messages = ModelMessagesTypeAdapter.validate_json(
        ModelMessagesTypeAdapter.dump_json(list(suspended.checkpoint.messages))
    )
    state = ResumableState.model_validate_json(suspended.checkpoint.state.model_dump_json())
    requests = TypeAdapter(DeferredToolRequests).validate_json(TypeAdapter(DeferredToolRequests).dump_json(requests))
    resolution = (
        DeferredCallResolution(tool_call_id=tool_call_id, result="external result")
        if decision == "external"
        else DeferredApprovalResolution(
            tool_call_id=tool_call_id,
            approved=decision == "approved",
            override_args={"value": "override"} if decision == "approved" else None,
        )
    )
    results = DeferredInteractionResolver().resolve(requests, [resolution])
    assert set(results.calls) | set(results.approvals) == {tool_call_id}
    completed = await harness.execute_segment(
        runtime(state), AgentSegmentRequest(message_history=messages, deferred_tool_results=results), event_sink=collect
    )
    assert completed.status is AgentSegmentStatus.completed
    assert completed.output == "finished"
    assert effects == (["override"] if decision == "approved" else [])
    assert model_attempts == 2  # A provider retry never reruns the approved tool.
    tool_parts = [
        part
        for message in completed.checkpoint.messages
        for part in message.parts
        if isinstance(part, ToolCallPart | ToolReturnPart)
    ]
    assert all(part.tool_call_id == tool_call_id for part in tool_parts)
    assert sum(isinstance(part, ToolReturnPart) for part in tool_parts) == 1
    assert any(isinstance(part, ThinkingPart) for message in completed.checkpoint.messages for part in message.parts)
    event_parts = [
        event.part
        for event in events
        if isinstance(event, FunctionToolCallEvent | FunctionToolResultEvent | PartStartEvent | PartEndEvent)
        and isinstance(event.part, ToolCallPart | ToolReturnPart)
    ]
    assert event_parts
    assert all(part.tool_call_id == tool_call_id for part in event_parts)
