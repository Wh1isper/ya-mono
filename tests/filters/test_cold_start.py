"""Tests for ya_agent_sdk.filters.cold_start module."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from ya_agent_sdk.context import AgentContext, ModelConfig
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.filters.cold_start import (
    _MAX_TOOL_RETURN_CHARS,
    _truncate_tool_content,
    cold_start_trim,
)


def _make_ctx_mock(ctx: AgentContext) -> MagicMock:
    mock = MagicMock()
    mock.deps = ctx
    return mock


def _make_history(
    *,
    tool_content: str = "short",
    response_timestamp: datetime | None = None,
) -> list:
    """Build a minimal message history with one tool call/return pair."""
    if response_timestamp is None:
        response_timestamp = datetime.now(tz=UTC)

    return [
        ModelRequest(parts=[UserPromptPart(content="do something")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="shell", args='{"command":"ls"}', tool_call_id="c1")],
            model_name="test-model",
            timestamp=response_timestamp,
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="shell", content=tool_content, tool_call_id="c1")],
        ),
        ModelResponse(
            parts=[TextPart(content="done")],
            model_name="test-model",
            timestamp=response_timestamp,
        ),
    ]


# ---------------------------------------------------------------------------
# _truncate_tool_content
# ---------------------------------------------------------------------------


def test_truncate_short_content() -> None:
    """Short content should be returned unchanged."""
    short = "x" * _MAX_TOOL_RETURN_CHARS
    assert _truncate_tool_content(short) == short


def test_truncate_long_content() -> None:
    """Long content should be truncated with head + marker + tail."""
    long = "A" * 1000
    result = _truncate_tool_content(long)
    assert len(result) < len(long)
    assert "truncated" in result
    assert result.startswith("A" * 200)
    assert result.endswith("A" * 200)


# ---------------------------------------------------------------------------
# cold_start_trim -- no trimming cases
# ---------------------------------------------------------------------------


async def test_no_trim_empty_history(tmp_path: Path) -> None:
    """Empty history should pass through unchanged."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=3600)) as ctx:
            result = cold_start_trim(_make_ctx_mock(ctx), [])
            assert result == []


async def test_no_trim_disabled(tmp_path: Path) -> None:
    """When cold_start_trim_seconds=0, no trimming should happen."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=0)) as ctx:
            big_content = "B" * 2000
            history = _make_history(
                tool_content=big_content,
                response_timestamp=datetime.now(tz=UTC) - timedelta(hours=2),
            )
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            # Content should be unchanged
            tool_return = result[2].parts[0]
            assert tool_return.content == big_content


async def test_no_trim_warm_cache(tmp_path: Path) -> None:
    """When gap is within threshold, no trimming should happen."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=3600)) as ctx:
            big_content = "C" * 2000
            # Response was 5 minutes ago -- well within 1-hour threshold
            history = _make_history(
                tool_content=big_content,
                response_timestamp=datetime.now(tz=UTC) - timedelta(minutes=5),
            )
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            tool_return = result[2].parts[0]
            assert tool_return.content == big_content


# ---------------------------------------------------------------------------
# cold_start_trim -- trimming cases
# ---------------------------------------------------------------------------


async def test_trim_cold_start(tmp_path: Path) -> None:
    """When gap exceeds threshold, large tool results should be truncated."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=3600)) as ctx:
            big_content = "D" * 2000
            # Response was 2 hours ago -- exceeds 1-hour threshold
            history = _make_history(
                tool_content=big_content,
                response_timestamp=datetime.now(tz=UTC) - timedelta(hours=2),
            )
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            tool_return = result[2].parts[0]
            assert len(tool_return.content) < len(big_content)
            assert "truncated" in tool_return.content


async def test_trim_preserves_small_tool_results(tmp_path: Path) -> None:
    """Small tool results should not be truncated even on cold start."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=3600)) as ctx:
            small_content = "E" * 100
            history = _make_history(
                tool_content=small_content,
                response_timestamp=datetime.now(tz=UTC) - timedelta(hours=2),
            )
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            tool_return = result[2].parts[0]
            assert tool_return.content == small_content


async def test_trim_preserves_non_tool_parts(tmp_path: Path) -> None:
    """User prompts and model text responses should never be modified."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=3600)) as ctx:
            history = _make_history(
                tool_content="F" * 2000,
                response_timestamp=datetime.now(tz=UTC) - timedelta(hours=2),
            )
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            # User prompt untouched
            assert result[0].parts[0].content == "do something"
            # Model text response untouched
            assert result[3].parts[0].content == "done"


async def test_trim_multiple_tool_returns(tmp_path: Path) -> None:
    """All large tool returns in the history should be trimmed."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=60)) as ctx:
            old_ts = datetime.now(tz=UTC) - timedelta(minutes=5)
            history = [
                ModelRequest(parts=[UserPromptPart(content="step 1")]),
                ModelResponse(
                    parts=[ToolCallPart(tool_name="view", args="{}", tool_call_id="c1")],
                    model_name="m",
                    timestamp=old_ts,
                ),
                ModelRequest(
                    parts=[ToolReturnPart(tool_name="view", content="G" * 1000, tool_call_id="c1")],
                ),
                ModelResponse(
                    parts=[ToolCallPart(tool_name="grep", args="{}", tool_call_id="c2")],
                    model_name="m",
                    timestamp=old_ts,
                ),
                ModelRequest(
                    parts=[ToolReturnPart(tool_name="grep", content="H" * 800, tool_call_id="c2")],
                ),
                ModelResponse(
                    parts=[TextPart(content="analysis")],
                    model_name="m",
                    timestamp=old_ts,
                ),
            ]
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            # Both large tool returns should be trimmed
            assert "truncated" in result[2].parts[0].content
            assert "truncated" in result[4].parts[0].content


async def test_trim_naive_timestamp(tmp_path: Path) -> None:
    """Should handle naive (timezone-unaware) timestamps correctly."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=3600)) as ctx:
            big_content = "I" * 2000
            # Naive timestamp (no tzinfo), 2 hours ago
            naive_ts = datetime.now() - timedelta(hours=2)
            history = _make_history(tool_content=big_content, response_timestamp=naive_ts)
            result = cold_start_trim(_make_ctx_mock(ctx), history)
            tool_return = result[2].parts[0]
            assert "truncated" in tool_return.content


async def test_trim_preserves_messages_after_last_model_response(tmp_path: Path) -> None:
    """Pending tool results after the last model response should stay intact."""
    async with LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path) as env:
        async with AgentContext(env=env, model_cfg=ModelConfig(cold_start_trim_seconds=60)) as ctx:
            old_ts = datetime.now(tz=UTC) - timedelta(minutes=5)
            old_content = "J" * 1200
            pending_content = "K" * 1200
            history = [
                ModelRequest(parts=[UserPromptPart(content="step 1")]),
                ModelResponse(
                    parts=[ToolCallPart(tool_name="view", args="{}", tool_call_id="c1")],
                    model_name="m",
                    timestamp=old_ts,
                ),
                ModelRequest(
                    parts=[ToolReturnPart(tool_name="view", content=old_content, tool_call_id="c1")],
                ),
                ModelResponse(
                    parts=[ToolCallPart(tool_name="grep", args="{}", tool_call_id="c2")],
                    model_name="m",
                    timestamp=old_ts,
                ),
                ModelRequest(
                    parts=[ToolReturnPart(tool_name="grep", content=pending_content, tool_call_id="c2")],
                ),
            ]

            result = cold_start_trim(_make_ctx_mock(ctx), history)

            assert "truncated" in result[2].parts[0].content
            assert result[4].parts[0].content == pending_content
