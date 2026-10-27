"""History transformations share untouched payloads and isolate changed nodes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models import ModelRequestContext, ModelRequestParameters
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from ya_agent_sdk.capabilities.foundation._request import apply_history_processor
from ya_agent_sdk.capabilities.foundation.history import (
    ColdStartCapability,
    ContextCompactionCapability,
    HandoffCapability,
    ReasoningCompatibilityCapability,
    ToolArgumentRepairCapability,
)
from ya_agent_sdk.capabilities.foundation.request import MediaCompatibilityCapability, RuntimeContextCapability


@pytest.mark.parametrize(
    "capability",
    [
        ColdStartCapability,
        ContextCompactionCapability,
        HandoffCapability,
        ReasoningCompatibilityCapability,
        ToolArgumentRepairCapability,
        MediaCompatibilityCapability,
    ],
)
async def test_noop_capability_shares_large_tool_payload(agent_context, capability):
    payload = {"rows": [{"value": str(i)} for i in range(100)]}
    tool_id = "provider-call-original"
    messages = [
        ModelRequest(parts=[ToolReturnPart("query", payload, tool_call_id=tool_id)]),
        ModelResponse(parts=[TextPart("done")]),
        ModelRequest(parts=[UserPromptPart("next")]),
    ]
    model = TestModel()
    ctx = RunContext(deps=agent_context, model=model, usage=RunUsage(), messages=list(messages))
    request = ModelRequestContext(
        model=model, messages=messages, model_settings={}, model_request_parameters=ModelRequestParameters()
    )
    projected = await capability().before_model_request(ctx, request)
    assert projected is request
    assert projected.messages[0] is messages[0]
    assert messages[0].parts[0].content is payload


async def test_runtime_snapshot_copies_only_last_request(agent_context, monkeypatch):
    monkeypatch.setattr(type(agent_context), "get_context_instructions", AsyncMock(return_value="runtime snapshot"))
    older = ModelRequest(parts=[ToolReturnPart("query", {"large": list(range(100))}, tool_call_id="id")])
    last = ModelRequest(parts=[UserPromptPart("next")])
    model = TestModel()
    ctx = RunContext(deps=agent_context, model=model, usage=RunUsage(), messages=[older, last])
    request = ModelRequestContext(
        model=model, messages=[older, last], model_settings={}, model_request_parameters=ModelRequestParameters()
    )
    projected = await RuntimeContextCapability().before_model_request(ctx, request)
    assert projected.messages[0] is older
    assert projected.messages[-1] is not last
    assert len(last.parts) == 1
    assert last.metadata is None
    assert ctx.messages == projected.messages


async def test_unknown_mutating_processor_keeps_detached_input(agent_context):
    original = ModelResponse(parts=[ToolCallPart("query", {"nested": ["original"]})])
    model = TestModel()
    ctx = RunContext(deps=agent_context, model=model, usage=RunUsage(), messages=[original])
    request = ModelRequestContext(
        model=model, messages=[original], model_settings={}, model_request_parameters=ModelRequestParameters()
    )

    def mutate(_ctx, messages):
        messages[0].parts[0].args["nested"].append("changed")
        return messages

    projected = await apply_history_processor(mutate, ctx, request, persist=False)
    assert original.parts[0].args == {"nested": ["original"]}
    assert projected.messages[0].parts[0].args == {"nested": ["original", "changed"]}
