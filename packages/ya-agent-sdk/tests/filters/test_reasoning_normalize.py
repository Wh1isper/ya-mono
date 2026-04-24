"""Tests for ya_agent_sdk.filters.reasoning_normalize module."""

from unittest.mock import MagicMock

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    UserPromptPart,
)
from ya_agent_sdk.agents.compact import _trim_history_for_compact
from ya_agent_sdk.context import ModelCapability, ModelConfig
from ya_agent_sdk.filters.reasoning_normalize import normalize_reasoning_for_model


def _ctx(*capabilities: ModelCapability, provider: str = "deepseek") -> MagicMock:
    ctx = MagicMock()
    ctx.deps.model_cfg = ModelConfig(capabilities=set(capabilities))
    ctx.model.system = provider
    ctx.model.model_name = f"{provider}:test-model"
    return ctx


def test_no_op_for_non_reasoning_model() -> None:
    """Should return history as-is when the active model has no reasoning capability flags."""
    history: list[ModelMessage] = [
        ModelResponse(parts=[TextPart(content="Hello")]),
    ]

    result = normalize_reasoning_for_model(_ctx(provider="openai"), history)

    assert result is history
    assert history[0].parts == [TextPart(content="Hello")]  # type: ignore[union-attr]


def test_synthesize_thinking_part_when_required() -> None:
    """Should synthesize ThinkingPart for every response missing reasoning content."""
    history: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="Hi")]),
        ModelResponse(parts=[TextPart(content="Hello")]),
        ModelResponse(parts=[ToolCallPart(tool_name="view", args={"file_path": "a.py"}, tool_call_id="call_1")]),
    ]

    normalize_reasoning_for_model(_ctx(ModelCapability.reasoning_required), history)

    for msg in history:
        if isinstance(msg, ModelResponse):
            assert isinstance(msg.parts[0], ThinkingPart)
            assert msg.parts[0].content == ""
            assert msg.parts[0].provider_name == "deepseek"


def test_keep_existing_thinking_part() -> None:
    """Should keep existing ThinkingPart without inserting another one."""
    existing = ThinkingPart(content="existing reasoning", provider_name="deepseek")
    history: list[ModelMessage] = [
        ModelResponse(parts=[existing, TextPart(content="Hello")]),
    ]

    normalize_reasoning_for_model(_ctx(ModelCapability.reasoning_required), history)

    response = history[0]
    assert isinstance(response, ModelResponse)
    assert response.parts == [existing, TextPart(content="Hello")]
    assert sum(isinstance(part, ThinkingPart) for part in response.parts) == 1


def test_drop_foreign_thinking_when_strict() -> None:
    """Should remove ThinkingPart entries whose provider tag differs from the active provider."""
    own = ThinkingPart(content="own reasoning", provider_name="deepseek")
    foreign = ThinkingPart(content="foreign reasoning", provider_name="anthropic")
    history: list[ModelMessage] = [
        ModelResponse(parts=[foreign, own, TextPart(content="Hello")]),
    ]

    normalize_reasoning_for_model(
        _ctx(ModelCapability.reasoning_foreign_incompatible, provider="deepseek"),
        history,
    )

    response = history[0]
    assert isinstance(response, ModelResponse)
    assert response.parts == [own, TextPart(content="Hello")]


def test_preserves_order_of_other_parts() -> None:
    """Should insert synthesized ThinkingPart before existing response parts."""
    text = TextPart(content="I will call a tool.")
    tool_call = ToolCallPart(tool_name="view", args={"file_path": "a.py"}, tool_call_id="call_1")
    history: list[ModelMessage] = [
        ModelResponse(parts=[text, tool_call]),
    ]

    normalize_reasoning_for_model(_ctx(ModelCapability.reasoning_required), history)

    response = history[0]
    assert isinstance(response, ModelResponse)
    assert isinstance(response.parts[0], ThinkingPart)
    assert response.parts[1:] == [text, tool_call]


def test_compact_filter_does_not_re_strip() -> None:
    """Should preserve synthesized ThinkingPart during compact pre-trimming."""
    history: list[ModelMessage] = [
        ModelResponse(parts=[TextPart(content="Hello")]),
    ]
    normalize_reasoning_for_model(_ctx(ModelCapability.reasoning_required), history)

    trimmed = _trim_history_for_compact(history)

    response = trimmed[0]
    assert isinstance(response, ModelResponse)
    assert isinstance(response.parts[0], ThinkingPart)
    assert response.parts[0].content == ""
    assert response.parts[0].provider_name == "deepseek"
    assert response.parts[1] == TextPart(content="Hello")
