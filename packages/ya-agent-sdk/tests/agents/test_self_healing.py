"""Request-local repair contracts, including stream and capability boundaries."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import copy, deepcopy

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import (
    BinaryContent,
    CompactionPart,
    FilePart,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    RetryFeedbackPart,
    RetryInfo,
    TextContent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestContext, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.wrapper import WrapperModel
from ya_agent_sdk.agents.models.self_healing import (
    DEFAULT_MODEL_RECOVERY_RULES,
    ModelRecoveryRule,
    SelfHealingModel,
    strip_thinking_parts,
)
from ya_agent_sdk.capabilities import RuntimeFoundationCapability, SelfHealingModelCapability
from ya_agent_sdk.capabilities.defaults import build_default_capability_catalog
from ya_agent_sdk.context import AgentContext

PARAMETERS = ModelRequestParameters()
ITEM_ERROR = "Invalid 'input[2].id': 'foreign-id'. Expected an ID that begins with 'msg'."


class RejectOnce(WrapperModel):
    def __init__(self, error: Exception, *, always: bool = False) -> None:
        super().__init__(TestModel(custom_output_text="done"))
        self.error = error
        self.always = always
        self.seen: list[list[ModelMessage]] = []

    def observe(self, messages: list[ModelMessage]) -> None:
        self.seen.append(deepcopy(messages))
        if self.always or len(self.seen) == 1:
            raise self.error

    async def request(self, messages, model_settings, model_request_parameters):
        self.observe(messages)
        return ModelResponse(parts=[TextPart("done")])

    @asynccontextmanager
    async def request_stream(
        self, messages, model_settings, model_request_parameters, run_context=None
    ) -> AsyncIterator[StreamedResponse]:
        self.observe(messages)
        async with super().request_stream(messages, model_settings, model_request_parameters, run_context) as stream:
            yield stream


def history() -> list[ModelMessage]:
    return [
        ModelResponse(parts=[ThinkingPart("secret", signature="sig"), TextPart("answer", id="foreign-id")]),
        ModelRequest(parts=[UserPromptPart("continue")]),
    ]


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        "messages.2.content.0.thinking.thinking: Field required",
        "thinking and redacted_thinking blocks cannot be modified",
        "Invalid signature in `thinking` block",
        {"error": [{"upstream_code": "invalid_encrypted_content"}]},
        "Encrypted content could not be verified",
        "Encrypted content could not be decrypted",
        "5008 item not found",
        "5005 rs_123 not found",
        "reasoning item not found",
    ],
)
async def test_reasoning_rules_replay_private_copy(body, streaming: bool) -> None:
    original = history()
    snapshot = deepcopy(original)
    provider = RejectOnce(ModelHTTPError(400, "test", body=body))
    model = SelfHealingModel(provider)
    if streaming:
        async with model.request_stream(original, None, PARAMETERS) as stream:
            async for _ in stream:
                pass
    else:
        await model.request(original, None, PARAMETERS)
    assert len(provider.seen) == 2
    assert provider.seen[1][0].parts == [TextPart("answer", id="foreign-id")]
    assert original == snapshot


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        {"error": {"message": ITEM_ERROR}},
        {"errors": [{"message": ITEM_ERROR.replace("'", '"')}]},
        {
            "message": "[gateway/model] Invalid request: " + json.dumps({"error": {"message": ITEM_ERROR}}),
            "type": "upstream_error",
        },
    ],
)
async def test_structured_provider_error_preserves_message_quotes(body, streaming: bool) -> None:
    original = history()
    snapshot = deepcopy(original)
    provider = RejectOnce(ModelHTTPError(400, "test", body=body))
    model = SelfHealingModel(provider)
    if streaming:
        async with model.request_stream(original, None, PARAMETERS) as stream:
            async for _ in stream:
                pass
    else:
        await model.request(original, None, PARAMETERS)
    assert len(provider.seen) == 2
    assert provider.seen[1][0].parts == [TextPart("answer")]
    assert original == snapshot


@pytest.mark.parametrize("outcome", ["success", "retried", "failed", "denied", "interrupted"])
async def test_item_repair_preserves_all_tool_identities(outcome) -> None:
    original = [
        ModelResponse(
            parts=[
                ThinkingPart("reasoning", signature="sig"),
                CompactionPart("opaque"),
                TextPart("answer", id="msg_1", provider_name="openai"),
                ToolCallPart("lookup", {}, tool_call_id="call_1|fc_1", id="fc_1", provider_details={"x": 1}),
                NativeToolCallPart("search", {}, tool_call_id="native-1", id="native", provider_name="openai"),
                NativeToolReturnPart("search", "result", tool_call_id="native-1", provider_name="openai"),
                FilePart(BinaryContent(b"output", media_type="image/png"), id="file", provider_name="openai"),
            ],
            provider_name="openai",
            provider_url="https://example.test",
            provider_response_id="resp_1",
            provider_details={"x": 1},
        ),
        ModelRequest(
            parts=[
                ToolReturnPart("lookup", "result", tool_call_id="call_1|fc_1", outcome=outcome),
                RetryFeedbackPart(content="Please reconsider the answer.", retry=RetryInfo(cause="model_retry")),
            ]
        ),
    ]
    snapshot = deepcopy(original)
    provider = RejectOnce(ModelHTTPError(400, "test", body=ITEM_ERROR))
    await SelfHealingModel(provider).request(original, None, PARAMETERS)
    response = provider.seen[1][0]
    assert isinstance(response, ModelResponse)
    assert (
        response.provider_name
        is response.provider_url
        is response.provider_response_id
        is response.provider_details
        is None
    )
    assert not any(isinstance(part, ThinkingPart | CompactionPart) for part in response.parts)
    assert response.parts[1].tool_call_id == "call_1|fc_1"
    assert response.parts[2].tool_call_id == response.parts[3].tool_call_id == "native-1"
    assert provider.seen[1][1] == original[1]
    for part in response.parts:
        assert part.provider_name is None
        assert part.provider_details is None
        if not isinstance(part, NativeToolReturnPart):
            assert part.id is None
    assert original == snapshot


@pytest.mark.parametrize(
    "status,body",
    [
        (413, "large"),
        (400, "message size exceeds limit"),
        (400, "message size exceeded"),
        (400, "message size is greater than limit"),
        (400, "request entity too large"),
        (400, "payload too large"),
        (400, "request payload size exceeds limit"),
    ],
)
async def test_oversized_media_repair(status: int, body: str) -> None:
    image = BinaryContent(b"image", media_type="image/png")
    video = BinaryContent(b"video", media_type="video/mp4")
    audio = BinaryContent(b"audio", media_type="audio/wav")
    url = ImageUrl("https://example.test/image.png")
    original = [
        ModelRequest(
            parts=[
                UserPromptPart(["keep", image, video, audio, url, TextContent("annotated", metadata={"custom": 1})]),
                ToolReturnPart("view", image, tool_call_id="call_1"),
                ToolReturnPart("view", ["keep", video, audio], tool_call_id="call_2"),
                NativeToolReturnPart("native", [image], tool_call_id="native-1"),
            ],
            metadata={"custom": "retained"},
        )
    ]
    snapshot = deepcopy(original)
    provider = RejectOnce(ModelHTTPError(status, "test", body=body))
    await SelfHealingModel(provider).request(original, None, PARAMETERS)
    request = provider.seen[1][0]
    content = request.parts[0].content
    assert content[0] == "keep"
    assert isinstance(content[1], TextContent) and "image was removed" in content[1].content
    assert isinstance(content[2], TextContent) and "video was removed" in content[2].content
    assert content[1].metadata == {"display": False, "source_id": "self_healing_model"}
    assert content[3:] == original[0].parts[0].content[3:]
    assert "image was removed" in request.parts[1].content
    assert "video was removed" in request.parts[2].content[1]
    assert request.parts[3] == original[0].parts[3]
    assert request.metadata == original[0].metadata
    assert original == snapshot


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("mode", ["unmatched", "wrong_exception", "no_change", "empty_rules", "second_failure"])
async def test_replay_requires_match_and_change_and_is_bounded(mode: str, streaming: bool) -> None:
    error = ModelHTTPError(400, "test", body="Invalid signature in thinking block")
    if mode == "unmatched":
        error = ModelHTTPError(400, "test", body="Invalid input: please fix your schema")
    if mode == "wrong_exception":
        error = RuntimeError("Invalid signature in thinking block")
    original = [] if mode == "no_change" else history()
    provider = RejectOnce(error, always=True)
    model = SelfHealingModel(provider, rules=[] if mode == "empty_rules" else None)
    with pytest.raises(type(error)):
        if streaming:
            async with model.request_stream(original, None, PARAMETERS):
                pass
        else:
            await model.request(original, None, PARAMETERS)
    assert len(provider.seen) == (2 if mode == "second_failure" else 1)


async def test_stream_consumer_failure_is_not_replayed() -> None:
    provider = RejectOnce(ModelHTTPError(400, "test", body="Invalid signature in thinking block"))
    provider.seen.append([])  # Establish the first stream successfully.
    model = SelfHealingModel(provider)
    with pytest.raises(ModelAPIError):
        async with model.request_stream(history(), None, PARAMETERS) as stream:
            async for _ in stream:
                raise ModelAPIError("test", "Invalid signature in thinking block")
    assert len(provider.seen) == 2


@pytest.mark.parametrize("clone", [copy, deepcopy])
@pytest.mark.parametrize("rules", [None, [], [ModelRecoveryRule("custom", lambda _: True, strip_thinking_parts)]])
def test_model_copy_preserves_rules(clone, rules) -> None:
    model = SelfHealingModel(TestModel(), rules=rules)
    assert clone(model)._rules == (DEFAULT_MODEL_RECOVERY_RULES if rules is None else tuple(rules))


async def test_capability_wraps_late_effective_model_without_stacking() -> None:
    provider = RejectOnce(ModelHTTPError(400, "test", body="Invalid signature in thinking block"))

    class SelectModel(AbstractCapability[AgentContext]):
        async def before_model_request(self, ctx: RunContext[AgentContext], request: ModelRequestContext):
            request.model = provider
            return request

    agent = Agent(TestModel(), capabilities=[SelfHealingModelCapability(), SelectModel()])
    result = await agent.run("continue", deps=AgentContext(), message_history=history())
    assert result.output == "done"
    assert len(provider.seen) == 2
    assert isinstance(result.all_messages()[0].parts[0], ThinkingPart)

    wrapped = WrapperModel(SelfHealingModel(TestModel(), rules=[]))
    request = ModelRequestContext(
        model=wrapped, messages=history(), model_settings=None, model_request_parameters=PARAMETERS
    )
    updated = await SelfHealingModelCapability().before_model_request(None, request)
    assert updated is request
    assert updated.model is wrapped


def test_foundation_and_catalog_include_self_healing() -> None:
    assert any(isinstance(item, SelfHealingModelCapability) for item in RuntimeFoundationCapability().capabilities)
    catalog = build_default_capability_catalog()
    assert SelfHealingModelCapability in catalog.custom_capability_types
    assert "ToolIdCompatibilityCapability" not in catalog
