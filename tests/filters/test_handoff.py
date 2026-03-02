"""Tests for ya_agent_sdk.filters.handoff module."""

from pathlib import Path
from unittest.mock import MagicMock

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.events import HandoffCompleteEvent, HandoffStartEvent
from ya_agent_sdk.filters.handoff import _build_handoff_messages, process_handoff_message


async def test_process_handoff_no_handoff_message(tmp_path: Path) -> None:
    """Should return unchanged history when no handoff message is set."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Hello")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            assert result == history
            assert len(request.parts) == 1


async def test_process_handoff_with_handoff_message(tmp_path: Path) -> None:
    """Should build virtual tool call messages with handoff summary."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            ctx.handoff_message = "Previous context summary here"

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Continue task")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            # Should return 3 messages: system+user, tool call, tool return+handoff-complete
            assert len(result) == 3

            # First message: system prompt placeholder (no user prompt since user_prompts is None)
            first_msg = result[0]
            assert isinstance(first_msg, ModelRequest)
            assert any(isinstance(p, SystemPromptPart) for p in first_msg.parts)

            # Second message: virtual handoff tool call
            second_msg = result[1]
            assert isinstance(second_msg, ModelResponse)
            assert len(second_msg.parts) == 1
            assert isinstance(second_msg.parts[0], ToolCallPart)
            assert second_msg.parts[0].tool_name == "handoff"

            # Third message: tool return with summary + handoff-complete
            third_msg = result[2]
            assert isinstance(third_msg, ModelRequest)
            tool_return_parts = [p for p in third_msg.parts if isinstance(p, ToolReturnPart)]
            assert len(tool_return_parts) == 1
            assert tool_return_parts[0].tool_name == "handoff"
            assert "Previous context summary here" in tool_return_parts[0].content
            # handoff-complete marker
            user_parts = [p for p in third_msg.parts if isinstance(p, UserPromptPart)]
            assert len(user_parts) == 1
            assert "handoff-complete" in user_parts[0].content

            # Tool call IDs should match
            assert second_msg.parts[0].tool_call_id == tool_return_parts[0].tool_call_id

            # Handoff message should be cleared
            assert ctx.handoff_message is None


async def test_process_handoff_with_user_prompts(tmp_path: Path) -> None:
    """Should include original user_prompts in first request."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            ctx.handoff_message = "Summary"
            ctx.user_prompts = "Build me a web app with React"

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Continue")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            assert len(result) == 3

            # First message should contain system prompt + original user prompt
            first_msg = result[0]
            assert isinstance(first_msg, ModelRequest)
            assert any(isinstance(p, SystemPromptPart) for p in first_msg.parts)
            user_parts = [p for p in first_msg.parts if isinstance(p, UserPromptPart)]
            assert len(user_parts) == 1
            assert user_parts[0].content == "Build me a web app with React"


async def test_process_handoff_with_steering_messages(tmp_path: Path) -> None:
    """Should include steering messages in tool return request and clear them after."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            ctx.handoff_message = "Summary"
            ctx.user_prompts = "Original task"
            ctx.steering_messages = ["Focus on tests", "Skip docs"]

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Continue")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            assert len(result) == 3

            # Third message should contain tool return, steering, and handoff-complete
            third_msg = result[2]
            assert isinstance(third_msg, ModelRequest)
            user_parts = [p for p in third_msg.parts if isinstance(p, UserPromptPart)]
            # 2 steering + handoff-complete
            assert len(user_parts) == 3
            assert "[User Steering] Focus on tests" in user_parts[0].content
            assert "[User Steering] Skip docs" in user_parts[1].content
            assert "handoff-complete" in user_parts[2].content

            # Steering messages should be cleared
            assert ctx.steering_messages == []


async def test_process_handoff_without_user_prompts(tmp_path: Path) -> None:
    """Should still produce valid messages even without user_prompts."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            ctx.handoff_message = "Summary"
            # user_prompts is None by default

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Continue")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            assert len(result) == 3

            # First message: only system prompt (no user prompt)
            first_msg = result[0]
            user_parts = [p for p in first_msg.parts if isinstance(p, UserPromptPart)]
            assert len(user_parts) == 0


async def test_process_handoff_empty_history(tmp_path: Path) -> None:
    """Should still produce compacted messages even with empty history."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            ctx.handoff_message = "Summary"

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            result = await process_handoff_message(mock_ctx, [])

            # Should produce compacted messages regardless of empty input
            assert len(result) == 3
            assert ctx.handoff_message is None


async def test_process_handoff_last_message_has_user_prompt(tmp_path: Path) -> None:
    """Last message should have UserPromptPart for auto_load_files compatibility."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            ctx.handoff_message = "Summary"

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Hello")])
            result = await process_handoff_message(mock_ctx, [request])

            # Last message must have UserPromptPart so auto_load_files filter can inject
            last_msg = result[-1]
            assert isinstance(last_msg, ModelRequest)
            assert any(isinstance(p, UserPromptPart) for p in last_msg.parts)


async def test_process_handoff_emits_events(tmp_path: Path) -> None:
    """Should emit HandoffStartEvent and HandoffCompleteEvent with handoff content."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            # Enable streaming to capture events
            ctx._stream_queue_enabled = True

            ctx.handoff_message = "Test handoff content"

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Continue")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            # Verify result: 3 messages
            assert len(result) == 3

            # Collect events from queue
            events = []
            while not ctx.agent_stream_queues[ctx.agent_id].empty():
                events.append(await ctx.agent_stream_queues[ctx.agent_id].get())

            # Should have start and complete events
            assert len(events) == 2

            start_event = events[0]
            assert isinstance(start_event, HandoffStartEvent)
            assert start_event.message_count == 1

            complete_event = events[1]
            assert isinstance(complete_event, HandoffCompleteEvent)
            assert complete_event.handoff_content == "Test handoff content"
            assert complete_event.original_message_count == 1
            # Event IDs should match
            assert start_event.event_id == complete_event.event_id


async def test_process_handoff_no_events_when_streaming_disabled(tmp_path: Path) -> None:
    """Should not emit events when streaming is disabled."""
    async with LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    ) as env:
        async with AgentContext(env=env) as ctx:
            # Streaming is disabled by default
            assert ctx._stream_queue_enabled is False

            ctx.handoff_message = "Test content"

            mock_ctx = MagicMock()
            mock_ctx.deps = ctx

            request = ModelRequest(parts=[UserPromptPart(content="Continue")])
            history = [request]

            result = await process_handoff_message(mock_ctx, history)

            # Should return 3 messages
            assert len(result) == 3

            # Queue should be empty since streaming is disabled
            assert ctx.agent_stream_queues[ctx._agent_id].empty()


def test_build_handoff_messages_basic() -> None:
    """Should build 3-message virtual tool call structure."""
    result = _build_handoff_messages("Test summary", tool_call_id="test-id")

    assert len(result) == 3

    # First: request with system prompt
    assert isinstance(result[0], ModelRequest)
    assert any(isinstance(p, SystemPromptPart) for p in result[0].parts)

    # Second: response with tool call
    assert isinstance(result[1], ModelResponse)
    assert isinstance(result[1].parts[0], ToolCallPart)
    assert result[1].parts[0].tool_name == "handoff"
    assert result[1].parts[0].tool_call_id == "test-id"

    # Third: request with tool return + handoff-complete
    assert isinstance(result[2], ModelRequest)
    tool_returns = [p for p in result[2].parts if isinstance(p, ToolReturnPart)]
    assert len(tool_returns) == 1
    assert tool_returns[0].content == "Test summary"
    assert tool_returns[0].tool_call_id == "test-id"
    assert any(isinstance(p, UserPromptPart) and "handoff-complete" in p.content for p in result[2].parts)


def test_build_handoff_messages_with_prompt_and_steering() -> None:
    """Should include original prompt in first request and steering in last request."""
    result = _build_handoff_messages(
        "Summary",
        original_prompt="Build a CLI tool",
        steering_messages=["Use click library"],
    )

    # Original prompt in first message
    first_msg = result[0]
    assert isinstance(first_msg, ModelRequest)
    user_parts = [p for p in first_msg.parts if isinstance(p, UserPromptPart)]
    assert len(user_parts) == 1
    assert user_parts[0].content == "Build a CLI tool"

    # Steering in last message
    third_msg = result[2]
    assert isinstance(third_msg, ModelRequest)
    user_parts = [p for p in third_msg.parts if isinstance(p, UserPromptPart)]
    assert len(user_parts) == 2  # steering + handoff-complete
    assert "[User Steering] Use click library" in user_parts[0].content
