"""Error-aware retry recovery for streamed agent runs.

This module contains durable message-history healing steps used by
``stream_agent(..., resume_on_error=True)`` before the next retry attempt.
The recovery runs after tool-call closure and before the resume prompt is
added, so the next model request and any persisted recoverable history share
the repaired messages.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from pydantic_ai.messages import (
    BaseToolCallPart,
    BaseToolReturnPart,
    BinaryContent,
    FilePart,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    ToolReturnPart,
    UploadedFile,
    UserContent,
    UserPromptPart,
    VideoUrl,
)

from ya_agent_sdk._logger import get_logger
from ya_agent_sdk.agents.models.utils import is_retryable_model_stream_exception
from ya_agent_sdk.context import AgentContext, StreamRecoveryPolicy
from ya_agent_sdk.filters.cold_start import _trim_tool_returns

logger = get_logger(__name__)

DEFAULT_STREAM_RESUME_PROMPT = (
    "The previous streaming model request failed before the agent finished. "
    "Continue the task from the available conversation history. Avoid repeating completed work."
)

_INCOMPLETE_TOOL_RESULT = (
    "The previous agent attempt ended before this tool produced a terminal result. "
    "Completion and side-effect status are unknown; verify current state before continuing."
)

_MEDIA_REMOVED_REMINDER = (
    "<system-reminder>Media content was removed during retry recovery because the previous "
    "request exceeded the model context limit. If the media is still needed, ask the user "
    "to attach it again or inspect it with a focused tool call.</system-reminder>"
)

_RESPONSE_MEDIA_REMOVED_TEXT = (
    "<system-reminder>Assistant media content was removed during retry recovery because the "
    "previous request exceeded the model context limit.</system-reminder>"
)

_CONTEXT_OVERFLOW_PATTERNS = (
    "context_length_exceeded",
    "maximum context length",
    "max context length",
    "context window",
    "context limit",
    "context too long",
    "prompt is too long",
    "prompt too long",
    "too many tokens",
    "token count exceeds maximum",
    "exceeds maximum token",
    "exceed the maximum number of tokens",
    "input is too long",
    "input too long",
    "reduce the length of the messages",
    "reduce the size of your message",
    "messages resulted in",
    "requested tokens",
)


@dataclass(frozen=True)
class RetryRecoveryResult:
    """Result of retry message recovery."""

    history: list[ModelMessage]
    changed: bool = False
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StreamRetryDecision:
    """One recovery decision from the shared stream retry budgets."""

    recoverable: bool
    budget: str
    failures_in_budget: int
    max_attempts: int


@dataclass(slots=True)
class StreamRetryController:
    """Track independent execution and transient transport retry budgets."""

    policy: StreamRecoveryPolicy
    non_transport_failures: int = 0
    transport_failures: int = 0

    def record_failure(
        self,
        exc: BaseException,
        *,
        failed_during_model_request: bool,
        successful_model_request: bool,
    ) -> StreamRetryDecision:
        if successful_model_request:
            self.transport_failures = 0

        if failed_during_model_request and is_retryable_model_stream_exception(exc):
            self.transport_failures += 1
            failures = self.transport_failures
            max_attempts = self.policy.transport_max_attempts
            budget = "transport"
        else:
            self.non_transport_failures += 1
            failures = self.non_transport_failures
            max_attempts = self.policy.max_attempts
            budget = "execution"

        return StreamRetryDecision(
            recoverable=self.policy.enabled and failures + 1 <= max_attempts,
            budget=budget,
            failures_in_budget=failures,
            max_attempts=max_attempts,
        )


def extract_resume_history(run: Any | None, fallback_history: Sequence[ModelMessage] | None) -> list[ModelMessage]:
    """Extract the latest available messages from a failed run."""
    if run is not None:
        try:
            messages = list(run.all_messages())
        except Exception:
            logger.debug("Failed to extract run messages for stream resume", exc_info=True)
        else:
            if messages:
                return messages
    return list(fallback_history or [])


def _unreturned_tool_calls(
    history: Sequence[ModelMessage],
) -> tuple[dict[str, str], set[str]]:
    ordinary_calls: dict[str, str] = {}
    native_calls: set[str] = set()
    for message in history:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, NativeToolCallPart):
                    native_calls.add(part.tool_call_id)
                elif isinstance(part, NativeToolReturnPart):
                    native_calls.discard(part.tool_call_id)
                elif isinstance(part, BaseToolCallPart):
                    ordinary_calls[part.tool_call_id] = part.tool_name
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, BaseToolReturnPart):
                    ordinary_calls.pop(part.tool_call_id, None)
    return ordinary_calls, native_calls


def history_has_unreturned_tool_calls(history: Sequence[ModelMessage]) -> bool:
    """Return whether history contains ordinary or native calls without results."""
    ordinary_calls, native_calls = _unreturned_tool_calls(history)
    return bool(ordinary_calls or native_calls)


def close_unreturned_tool_calls(history: Sequence[ModelMessage]) -> list[ModelMessage]:
    """Close incomplete calls with a bounded status independent of exception details."""
    ordinary_calls, native_calls = _unreturned_tool_calls(history)
    if not ordinary_calls and not native_calls:
        return list(history)

    normalized_history: list[ModelMessage] = []
    for message in history:
        if not isinstance(message, ModelResponse) or not native_calls:
            normalized_history.append(message)
            continue
        parts = [
            part
            for part in message.parts
            if not (isinstance(part, NativeToolCallPart) and part.tool_call_id in native_calls)
        ]
        if parts:
            normalized_history.append(replace(message, parts=parts))

    if ordinary_calls:
        normalized_history.append(
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name=tool_name,
                        tool_call_id=tool_call_id,
                        content=_INCOMPLETE_TOOL_RESULT,
                        outcome="failed",
                    )
                    for tool_call_id, tool_name in ordinary_calls.items()
                ]
            )
        )
    return normalized_history


def recover_retry_message_history(
    exc: BaseException,
    history: Sequence[ModelMessage],
    ctx: AgentContext,
) -> RetryRecoveryResult:
    """Apply built-in retry recovery policies to message history.

    Args:
        exc: Exception raised by the previous attempt.
        history: Recovered message history from the previous attempt.
        ctx: Active agent context.

    Returns:
        Recovered history plus change metadata.
    """
    recovered = list(history)
    if not recovered:
        return RetryRecoveryResult(history=recovered)

    error_text = _exception_text(exc)
    reasons: list[str] = []
    changed = False

    if _is_context_overflow_error(error_text):
        recovered, overflow_changed = heal_context_overflow_history(recovered, ctx)
        if overflow_changed:
            changed = True
            reasons.append("context_overflow")

    if changed:
        logger.info("Retry recovery changed message history reasons=%s", ",".join(reasons))

    return RetryRecoveryResult(history=recovered, changed=changed, reasons=tuple(reasons))


def heal_context_overflow_history(
    history: Sequence[ModelMessage], ctx: AgentContext
) -> tuple[list[ModelMessage], bool]:
    """Trim large tool returns and remove image/video media for overflow retries."""
    recovered = list(history)
    changed = False

    trimmed_count = _trim_tool_returns(recovered)
    if trimmed_count:
        changed = True
        logger.info("Retry recovery trimmed %d tool return parts after context overflow", trimmed_count)

    media_recovered, media_changed = _strip_image_video_media(recovered)
    if media_changed:
        changed = True
        logger.info("Retry recovery removed image/video media after context overflow")

    return media_recovered, changed


def _strip_image_video_media(history: Sequence[ModelMessage]) -> tuple[list[ModelMessage], bool]:
    recovered: list[ModelMessage] = []
    changed = False

    for message in history:
        if isinstance(message, ModelRequest):
            new_message, message_changed = _strip_media_from_request(message)
            recovered.append(new_message)
            changed = changed or message_changed
            continue

        if isinstance(message, ModelResponse):
            new_message, message_changed = _strip_media_from_response(message)
            recovered.append(new_message)
            changed = changed or message_changed
            continue

        recovered.append(message)

    return recovered, changed


def _strip_media_from_request(message: ModelRequest) -> tuple[ModelRequest, bool]:
    new_parts: list[ModelRequestPart] = []
    changed = False

    for part in message.parts:
        if isinstance(part, UserPromptPart):
            if isinstance(part.content, str):
                new_parts.append(part)
                continue
            new_content, content_changed = _replace_media_content(part.content)
            new_parts.append(replace(part, content=_coerce_user_prompt_content(new_content)))
            changed = changed or content_changed
            continue

        if isinstance(part, ToolReturnPart | NativeToolReturnPart):
            new_content, content_changed = _replace_media_content(part.content)
            new_parts.append(replace(part, content=new_content))
            changed = changed or content_changed
            continue

        new_parts.append(part)

    if changed:
        return replace(message, parts=new_parts), True
    return message, False


def _strip_media_from_response(message: ModelResponse) -> tuple[ModelResponse, bool]:
    new_parts: list[ModelResponsePart] = []
    changed = False

    for part in message.parts:
        if isinstance(part, FilePart) and _is_image_or_video_content(part.content):
            new_parts.append(TextPart(content=_RESPONSE_MEDIA_REMOVED_TEXT))
            changed = True
            continue
        new_parts.append(part)

    if not changed:
        return message, False

    return replace(message, parts=new_parts), True


def _replace_media_content(content: object) -> tuple[object, bool]:
    if _is_image_or_video_content(content):
        return _MEDIA_REMOVED_REMINDER, True

    if isinstance(content, list):
        changed = False
        new_list_items: list[object] = []
        for item in content:
            new_item, item_changed = _replace_media_content(item)
            new_list_items.append(new_item)
            changed = changed or item_changed
        return new_list_items, changed

    if isinstance(content, tuple):
        changed = False
        new_tuple_items: list[object] = []
        for item in content:
            new_item, item_changed = _replace_media_content(item)
            new_tuple_items.append(new_item)
            changed = changed or item_changed
        return tuple(new_tuple_items), changed

    if isinstance(content, dict):
        changed = False
        new_dict_items: dict[object, object] = {}
        for key, value in content.items():
            new_value, value_changed = _replace_media_content(value)
            new_dict_items[key] = new_value
            changed = changed or value_changed
        return new_dict_items, changed

    return content, False


def _coerce_user_prompt_content(content: object) -> str | Sequence[UserContent]:
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(content, (bytes, bytearray)):
        return list(content)  # type: ignore[list-item]
    return [content]  # type: ignore[list-item]


def _is_image_or_video_content(content: object) -> bool:
    if isinstance(content, ImageUrl | VideoUrl):
        return True
    if isinstance(content, UploadedFile) and isinstance(content.media_type, str):
        return content.media_type.startswith(("image/", "video/"))
    return isinstance(content, BinaryContent) and content.media_type.startswith(("image/", "video/"))


def _is_context_overflow_error(error_text: str) -> bool:
    lowered = error_text.lower()
    if not any(pattern in lowered for pattern in _CONTEXT_OVERFLOW_PATTERNS):
        return False
    token_or_context = (
        "token" in lowered or "context" in lowered or "prompt" in lowered or "message" in lowered or "input" in lowered
    )
    return token_or_context


def _exception_text(exc: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    _collect_exception_text(exc, parts, seen)
    return "\n".join(parts)


def _collect_exception_text(exc: BaseException, parts: list[str], seen: set[int]) -> None:
    if id(exc) in seen:
        return
    seen.add(id(exc))

    parts.append(type(exc).__name__)
    try:
        parts.append(str(exc))
    except Exception:
        parts.append(repr(exc))

    body = getattr(exc, "body", None)
    if body is not None:
        parts.append(_safe_json_text(body))

    args = getattr(exc, "args", None)
    if args:
        parts.append(_safe_json_text(args))

    if exc.__cause__ is not None:
        _collect_exception_text(exc.__cause__, parts, seen)
    if exc.__context__ is not None:
        _collect_exception_text(exc.__context__, parts, seen)


def _safe_json_text(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return repr(value)
