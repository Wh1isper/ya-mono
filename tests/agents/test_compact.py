from pathlib import Path

from pydantic_ai.messages import (
    BinaryContent,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
    VideoUrl,
)

from ya_agent_sdk.agents.compact import (
    _COMPACT_STRIP_KEYS,
    _INCOMPATIBLE_BETAS,
    _MAX_TOOL_RETURN_CHARS,
    _is_media_content,
    _media_to_placeholder,
    _strip_incompatible_settings,
    _trim_history_for_compact,
    _truncate_str,
)
from ya_agent_sdk.agents.main import create_agent
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.filters.auto_load_files import process_auto_load_files

# =============================================================================
# _truncate_str tests
# =============================================================================


def test_truncate_str_short_content() -> None:
    """Short content should not be truncated."""
    content = "short content"
    assert _truncate_str(content) == content


def test_truncate_str_at_boundary() -> None:
    """Content exactly at max_chars should not be truncated."""
    content = "x" * _MAX_TOOL_RETURN_CHARS
    assert _truncate_str(content) == content


def test_truncate_str_long_content() -> None:
    """Long content should be truncated with head + marker + tail."""
    content = "H" * 300 + "M" * 400 + "T" * 300
    result = _truncate_str(content)

    assert len(result) < len(content)
    assert result.startswith("H" * 200)
    assert result.endswith("T" * 200)
    assert "[... 600 chars truncated ...]" in result


# =============================================================================
# _is_media_content tests
# =============================================================================


def test_is_media_content_image_url() -> None:
    assert _is_media_content(ImageUrl(url="https://example.com/image.png")) is True


def test_is_media_content_video_url() -> None:
    assert _is_media_content(VideoUrl(url="https://example.com/video.mp4")) is True


def test_is_media_content_binary_image() -> None:
    assert _is_media_content(BinaryContent(data=b"fake", media_type="image/png")) is True


def test_is_media_content_binary_video() -> None:
    assert _is_media_content(BinaryContent(data=b"fake", media_type="video/mp4")) is True


def test_is_media_content_string() -> None:
    assert _is_media_content("hello") is False


def test_is_media_content_binary_text() -> None:
    assert _is_media_content(BinaryContent(data=b"fake", media_type="application/pdf")) is False


# =============================================================================
# _media_to_placeholder tests
# =============================================================================


def test_media_to_placeholder_image_url() -> None:
    assert _media_to_placeholder(ImageUrl(url="https://example.com/img.png")) == "[image: https://example.com/img.png]"


def test_media_to_placeholder_video_url() -> None:
    assert _media_to_placeholder(VideoUrl(url="https://example.com/v.mp4")) == "[video: https://example.com/v.mp4]"


def test_media_to_placeholder_binary() -> None:
    assert (
        _media_to_placeholder(BinaryContent(data=b"x", media_type="image/png")) == "[image/png binary content removed]"
    )


# =============================================================================
# _trim_history_for_compact tests
# =============================================================================


def test_trim_truncates_large_tool_returns() -> None:
    """Large ToolReturnPart content should be truncated."""
    large_content = "a" * 1000
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="view", content=large_content, tool_call_id="call_1"),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    assert len(trimmed) == 1
    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, ToolReturnPart)
    assert isinstance(part.content, str)
    assert len(part.content) < len(large_content)
    assert "[... " in part.content


def test_trim_preserves_small_tool_returns() -> None:
    """Small ToolReturnPart content should not be modified."""
    small_content = "OK"
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="shell", content=small_content, tool_call_id="call_1"),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    part = trimmed[0]
    assert isinstance(part, ModelRequest)
    assert part.parts[0].content == small_content  # type: ignore[union-attr]


def test_trim_replaces_image_content_in_user_prompt() -> None:
    """Image content in UserPromptPart should be replaced with placeholder."""
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "Describe this image",
                        ImageUrl(url="https://example.com/image.png"),
                    ]
                ),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    assert isinstance(part.content, list)
    assert len(part.content) == 2
    assert part.content[0] == "Describe this image"
    assert part.content[1] == "[image: https://example.com/image.png]"


def test_trim_replaces_video_content_in_user_prompt() -> None:
    """Video content in UserPromptPart should be replaced with placeholder."""
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "Describe this video",
                        VideoUrl(url="https://example.com/video.mp4"),
                    ]
                ),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    assert isinstance(part.content, list)
    assert len(part.content) == 2
    assert part.content[0] == "Describe this video"
    assert part.content[1] == "[video: https://example.com/video.mp4]"


def test_trim_replaces_binary_image_in_user_prompt() -> None:
    """BinaryContent images in UserPromptPart should be replaced with placeholder."""
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "Analyze this",
                        BinaryContent(data=b"fake-image-data", media_type="image/png"),
                    ]
                ),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    assert isinstance(part.content, list)
    assert len(part.content) == 2
    assert part.content[0] == "Analyze this"
    assert part.content[1] == "[image/png binary content removed]"


def test_trim_replaces_all_media_in_list_with_placeholders() -> None:
    """When all content items are media, each should be replaced with placeholder."""
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        ImageUrl(url="https://example.com/image.png"),
                    ]
                ),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    assert isinstance(part.content, list)
    assert part.content[0] == "[image: https://example.com/image.png]"


def test_trim_handles_singleton_media_content() -> None:
    """Direct media content (not in a list) should be replaced with placeholder."""
    # This is technically a type violation (content should be str | Sequence[UserContent])
    # but we handle it defensively
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                UserPromptPart(content=ImageUrl(url="https://example.com/image.png")),  # type: ignore[arg-type]
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    assert part.content == "[image: https://example.com/image.png]"


def test_trim_preserves_string_user_prompts() -> None:
    """String UserPromptPart content should not be modified."""
    history: list[ModelMessage] = [
        ModelRequest(
            parts=[
                UserPromptPart(content="Hello, how are you?"),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    request = trimmed[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    assert part.content == "Hello, how are you?"


def test_trim_preserves_model_responses() -> None:
    """ModelResponse messages should be kept as-is."""
    history: list[ModelMessage] = [
        ModelResponse(parts=[TextPart(content="I can help with that.")]),
    ]

    trimmed = _trim_history_for_compact(history)

    assert len(trimmed) == 1
    response = trimmed[0]
    assert isinstance(response, ModelResponse)
    assert response.parts[0].content == "I can help with that."  # type: ignore[union-attr]


def test_trim_handles_mixed_messages() -> None:
    """Should handle a realistic mixed message history."""
    history: list[ModelMessage] = [
        # User sends text
        ModelRequest(
            parts=[
                UserPromptPart(content="Read this file"),
            ]
        ),
        # Assistant responds with tool call
        ModelResponse(parts=[TextPart(content="Reading file...")]),
        # Tool return with large content
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="view", content="x" * 2000, tool_call_id="call_1"),
            ]
        ),
        # User sends image + text
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        "What about this?",
                        ImageUrl(url="https://example.com/screenshot.png"),
                    ]
                ),
            ]
        ),
    ]

    trimmed = _trim_history_for_compact(history)

    assert len(trimmed) == 4

    # First message: preserved
    req0 = trimmed[0]
    assert isinstance(req0, ModelRequest)
    assert isinstance(req0.parts[0], UserPromptPart)
    assert req0.parts[0].content == "Read this file"

    # Second message: ModelResponse preserved
    assert isinstance(trimmed[1], ModelResponse)

    # Third message: tool return truncated
    req2 = trimmed[2]
    assert isinstance(req2, ModelRequest)
    part2 = req2.parts[0]
    assert isinstance(part2, ToolReturnPart)
    assert isinstance(part2.content, str)
    assert len(part2.content) < 2000
    assert "[... " in part2.content

    # Fourth message: image replaced with placeholder, text kept
    req3 = trimmed[3]
    assert isinstance(req3, ModelRequest)
    part3 = req3.parts[0]
    assert isinstance(part3, UserPromptPart)
    assert isinstance(part3.content, list)
    assert len(part3.content) == 2
    assert part3.content[0] == "What about this?"
    assert part3.content[1] == "[image: https://example.com/screenshot.png]"


# =============================================================================
# Integration tests
# =============================================================================


async def test_create_agent_runs_auto_load_files_after_compact(tmp_path: Path) -> None:
    env = LocalEnvironment(
        allowed_paths=[tmp_path],
        default_path=tmp_path,
        tmp_base_dir=tmp_path,
    )

    async with create_agent(
        model="test",
        env=env,
    ) as runtime:
        processors = runtime.agent.history_processors
        auto_load_indexes = [i for i, processor in enumerate(processors) if processor is process_auto_load_files]

        assert len(auto_load_indexes) == 2
        assert auto_load_indexes[-1] > auto_load_indexes[0]


# =============================================================================
# _strip_incompatible_settings tests
# =============================================================================


def test_strip_incompatible_settings_no_incompatible_keys() -> None:
    """Settings without incompatible keys should be preserved."""
    settings = {"max_tokens": 4096, "temperature": 0.5}
    result = _strip_incompatible_settings(settings)
    assert result == {"max_tokens": 4096, "temperature": 0.5}


def test_strip_incompatible_settings_removes_cache_keys() -> None:
    """Anthropic cache keys should be stripped, other keys preserved."""
    settings = {
        "max_tokens": 4096,
        "anthropic_cache_instructions": True,
        "anthropic_cache_messages": True,
        "anthropic_cache_tool_definitions": "5m",
    }
    result = _strip_incompatible_settings(settings)
    assert result == {"max_tokens": 4096}
    # Original should not be modified
    assert "anthropic_cache_instructions" in settings


def test_strip_incompatible_settings_removes_thinking_keys() -> None:
    """Thinking-related keys should be stripped (incompatible with ToolOutput)."""
    settings = {
        "max_tokens": 4096,
        "thinking": "high",
        "anthropic_thinking": {"type": "enabled", "budget_tokens": 10000},
        "anthropic_effort": "high",
    }
    result = _strip_incompatible_settings(settings)
    assert result == {"max_tokens": 4096}


def test_strip_incompatible_settings_strips_interleaved_beta() -> None:
    """Interleaved thinking beta header should be stripped from extra_headers."""
    settings = {
        "max_tokens": 4096,
        "extra_headers": {
            "anthropic-beta": "context-1m-2025-08-07,interleaved-thinking-2025-05-14",
        },
    }
    result = _strip_incompatible_settings(settings)
    assert result == {
        "max_tokens": 4096,
        "extra_headers": {"anthropic-beta": "context-1m-2025-08-07"},
    }


def test_strip_incompatible_settings_removes_empty_beta_header() -> None:
    """If only incompatible betas exist, the entire header should be removed."""
    settings = {
        "max_tokens": 4096,
        "extra_headers": {
            "anthropic-beta": "interleaved-thinking-2025-05-14",
        },
    }
    result = _strip_incompatible_settings(settings)
    assert result == {"max_tokens": 4096}


def test_strip_incompatible_settings_preserves_non_beta_headers() -> None:
    """Non-beta extra headers should be preserved even when beta is removed."""
    settings = {
        "max_tokens": 4096,
        "extra_headers": {
            "anthropic-beta": "interleaved-thinking-2025-05-14",
            "x-custom": "value",
        },
    }
    result = _strip_incompatible_settings(settings)
    assert result == {
        "max_tokens": 4096,
        "extra_headers": {"x-custom": "value"},
    }


def test_strip_incompatible_settings_full_preset() -> None:
    """Should handle a full Anthropic preset with all settings."""
    settings = {
        "max_tokens": 32768,
        "thinking": "high",
        "anthropic_thinking": {"type": "adaptive"},
        "anthropic_effort": "high",
        "anthropic_cache_instructions": True,
        "anthropic_cache_messages": True,
        "extra_headers": {
            "anthropic-beta": "context-1m-2025-08-07,interleaved-thinking-2025-05-14,context-management-2025-06-27",
        },
        "extra_body": {
            "context_management": {
                "edits": [
                    {"type": "clear_thinking_20251015", "keep": "all"},
                    {"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 100000}},
                ]
            }
        },
    }
    result = _strip_incompatible_settings(settings)
    assert result == {
        "max_tokens": 32768,
        "extra_headers": {"anthropic-beta": "context-1m-2025-08-07,context-management-2025-06-27"},
        "extra_body": {
            "context_management": {
                "edits": [
                    {"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 100000}},
                ]
            }
        },
    }


def test_strip_incompatible_settings_removes_clear_thinking_from_context_management() -> None:
    """clear_thinking edit should be removed from context_management."""
    settings = {
        "max_tokens": 4096,
        "extra_body": {
            "context_management": {
                "edits": [
                    {"type": "clear_thinking_20251015", "keep": {"type": "thinking_turns", "value": 3}},
                ]
            }
        },
    }
    result = _strip_incompatible_settings(settings)
    # Only clear_thinking edit -> context_management and extra_body removed entirely
    assert result == {"max_tokens": 4096}
    assert "extra_body" not in result


def test_strip_incompatible_settings_preserves_tool_use_clearing() -> None:
    """clear_tool_uses edit should be preserved when clear_thinking is stripped."""
    settings = {
        "max_tokens": 4096,
        "extra_body": {
            "context_management": {
                "edits": [
                    {"type": "clear_thinking_20251015", "keep": "all"},
                    {"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 50000}},
                ]
            }
        },
    }
    result = _strip_incompatible_settings(settings)
    assert result == {
        "max_tokens": 4096,
        "extra_body": {
            "context_management": {
                "edits": [
                    {"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 50000}},
                ]
            }
        },
    }


def test_strip_incompatible_settings_known_keys() -> None:
    """All expected keys should be in _COMPACT_STRIP_KEYS."""
    assert "anthropic_cache_tool_definitions" in _COMPACT_STRIP_KEYS
    assert "anthropic_cache_instructions" in _COMPACT_STRIP_KEYS
    assert "anthropic_cache_messages" in _COMPACT_STRIP_KEYS
    assert "thinking" in _COMPACT_STRIP_KEYS
    assert "anthropic_thinking" in _COMPACT_STRIP_KEYS
    assert "anthropic_effort" in _COMPACT_STRIP_KEYS


def test_strip_incompatible_settings_known_betas() -> None:
    """All expected betas should be in _INCOMPATIBLE_BETAS."""
    assert "interleaved-thinking-2025-05-14" in _INCOMPATIBLE_BETAS
