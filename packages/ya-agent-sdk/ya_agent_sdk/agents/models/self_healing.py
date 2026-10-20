# Copyright 2026 Converge AI
# SPDX-License-Identifier: Apache-2.0
# Adapted from agent-foundation e36d0518c51a1d89eef20715de4f3b187040d885.
# Modified for YA: copy-on-repair request isolation and native prompt metadata.
"""Narrowly matched, request-local provider-history self-healing."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import (
    BaseToolCallPart,
    BinaryContent,
    CompactionPart,
    FilePart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NativeToolReturnPart,
    TextContent,
    TextPart,
    ThinkingPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext

HistoryRepair = Callable[[list[ModelMessage]], int]
ErrorMatcher = Callable[[Exception], bool]


@dataclass(frozen=True, slots=True)
class ModelRecoveryRule:
    """One provider-error matcher and replay-safe history repair."""

    name: str
    matches: ErrorMatcher
    repair: HistoryRepair


class SelfHealingModel(WrapperModel):
    """Replay one rejected request after repairing a private history copy.

    Published events, canonical history, and deferred tool identities remain
    unchanged. A second failure propagates; stream bodies are never replayed.
    """

    def __init__(self, wrapped: Model, *, rules: Sequence[ModelRecoveryRule] | None = None) -> None:
        super().__init__(wrapped)
        self._rules = DEFAULT_MODEL_RECOVERY_RULES if rules is None else tuple(rules)

    def __copy__(self) -> SelfHealingModel:
        return SelfHealingModel(self.wrapped, rules=self._rules)

    def __deepcopy__(self, memo: dict[int, Any]) -> SelfHealingModel:
        return SelfHealingModel(deepcopy(self.wrapped, memo), rules=self._rules)

    def _repair(self, error: Exception, messages: list[ModelMessage]) -> list[ModelMessage] | None:
        for rule in self._rules:
            if rule.matches(error):
                repaired = deepcopy(messages)
                return repaired if rule.repair(repaired) > 0 else None
        return None

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        try:
            return await super().request(messages, model_settings, model_request_parameters)
        except Exception as error:
            repaired = self._repair(error, messages)
            if repaired is None:
                raise
        return await super().request(repaired, model_settings, model_request_parameters)

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[object] | None = None,
    ) -> AsyncGenerator[StreamedResponse]:
        async with AsyncExitStack() as stack:
            try:
                stream = await stack.enter_async_context(
                    super().request_stream(messages, model_settings, model_request_parameters, run_context)
                )
            except Exception as error:
                repaired = self._repair(error, messages)
                if repaired is None:
                    raise
                stream = await stack.enter_async_context(
                    super().request_stream(repaired, model_settings, model_request_parameters, run_context)
                )
            yield stream


def strip_thinking_parts(history: list[ModelMessage]) -> int:
    """Remove provider-bound reasoning parts while preserving other content."""
    removed = 0
    for message in history:
        if not isinstance(message, ModelResponse):
            continue
        kept = [part for part in message.parts if not isinstance(part, ThinkingPart)]
        removed += len(message.parts) - len(kept)
        message.parts = kept
    return removed


def strip_provider_native_state(history: list[ModelMessage]) -> int:
    """Remove provider-bound IDs and metadata, preserving tool_call_id."""
    changed = strip_thinking_parts(history)
    for message in history:
        if not isinstance(message, ModelResponse):
            continue
        response_values = (
            message.provider_name,
            message.provider_url,
            message.provider_details,
            message.provider_response_id,
        )
        changed += sum(value is not None for value in response_values)
        message.provider_name = None
        message.provider_url = None
        message.provider_details = None
        message.provider_response_id = None

        portable_parts = []
        for part in message.parts:
            if isinstance(part, CompactionPart):
                changed += 1
                continue
            if isinstance(part, TextPart | BaseToolCallPart | FilePart):
                changed += sum(value is not None for value in (part.id, part.provider_name, part.provider_details))
                part.id = None
                part.provider_name = None
                part.provider_details = None
            elif isinstance(part, NativeToolReturnPart):
                changed += sum(value is not None for value in (part.provider_name, part.provider_details))
                part.provider_name = None
                part.provider_details = None
            portable_parts.append(part)
        message.parts = portable_parts
    return changed


def _error_text(error: ModelAPIError) -> str:
    values = [error.message or ""]
    if isinstance(error, ModelHTTPError):
        values.extend((str(error.status_code), str(error.body or "")))
    return " ".join(values).lower()


def _body_contains(value: object, *, key: str, expected: str) -> bool:
    if isinstance(value, dict):
        if value.get(key) == expected:
            return True
        return any(_body_contains(item, key=key, expected=expected) for item in value.values())
    if isinstance(value, list):
        return any(_body_contains(item, key=key, expected=expected) for item in value)
    return False


_INVALID_ENCRYPTED_PATTERN = re.compile(r"['\"]upstream_code['\"]\s*:\s*['\"]invalid_encrypted_content['\"]")
_INVALID_PROVIDER_ITEM_ID_PATTERN = re.compile(
    r"invalid\s+['\"]input\[\d+\]\.id['\"]:\s*['\"][^'\"]+['\"]\.\s*"
    r"expected an id that begins with\s+['\"`][a-z][a-z0-9_-]*['\"`]"
)
_ANTHROPIC_INCOMPLETE_THINKING_PATTERN = re.compile(
    r"messages\.\d+\.content\.\d+\.thinking\.thinking:\s*field required\b"
)


def _has_invalid_encrypted_content(error: ModelAPIError) -> bool:
    if isinstance(error, ModelHTTPError) and _body_contains(
        error.body, key="upstream_code", expected="invalid_encrypted_content"
    ):
        return True
    return _INVALID_ENCRYPTED_PATTERN.search(_error_text(error)) is not None


def _is_invalid_provider_item_id(error: Exception) -> bool:
    return isinstance(error, ModelAPIError) and _INVALID_PROVIDER_ITEM_ID_PATTERN.search(_error_text(error)) is not None


def _is_anthropic_incomplete_thinking(error: Exception) -> bool:
    return (
        isinstance(error, ModelAPIError)
        and _ANTHROPIC_INCOMPLETE_THINKING_PATTERN.search(_error_text(error)) is not None
    )


def _is_anthropic_modified_thinking(error: Exception) -> bool:
    if not isinstance(error, ModelAPIError):
        return False
    text = _error_text(error)
    modified_block = (
        "thinking" in text
        and "redacted_thinking" in text
        and ("cannot be modified" in text or "must remain as they were" in text)
    )
    thinking_block = any(
        marker in text
        for marker in ("thinking block", "`thinking` block", "redacted_thinking block", "`redacted_thinking` block")
    )
    invalid_signature = thinking_block and "invalid" in text and "signature" in text
    return modified_block or invalid_signature


def _is_stale_reasoning(error: Exception) -> bool:
    if not isinstance(error, ModelAPIError):
        return False
    text = _error_text(error)
    if _has_invalid_encrypted_content(error):
        return True
    if "could not be verified" in text or "could not be decrypted" in text:
        return True
    expected_reasoning_id = any(
        marker in text
        for marker in (
            "expected an id that begins with 'rs",
            'expected an id that begins with "rs',
            "expected an id that begins with `rs",
        )
    )
    invalid_input_id = ("invalid 'input[" in text and "].id'" in text) or (
        'invalid "input[' in text and '].id"' in text
    )
    if invalid_input_id and expected_reasoning_id:
        return True
    co_markers = ("rs_", "item", "not found")
    if any(code in text for code in ("5008", "5005")) and any(marker in text for marker in co_markers):
        return True
    return "reasoning" in text and any(marker in text for marker in co_markers)


_OVERSIZED_PAYLOAD_MARKERS = (
    "message size exceeds",
    "message size exceeded",
    "message size is greater than",
    "request entity too large",
    "payload too large",
    "request payload size exceeds",
)
_OVERSIZED_IMAGE_REMINDER = (
    "<system-reminder>An image was removed because the request exceeded the "
    "provider's size limit. View it again if you still need it.</system-reminder>"
)
_OVERSIZED_VIDEO_REMINDER = (
    "<system-reminder>A video was removed because the request exceeded the "
    "provider's size limit. Read or view it again if you still need it.</system-reminder>"
)


def _is_oversized_payload(error: Exception) -> bool:
    if not isinstance(error, ModelAPIError):
        return False
    if isinstance(error, ModelHTTPError) and error.status_code == 413:
        return True
    return any(marker in _error_text(error) for marker in _OVERSIZED_PAYLOAD_MARKERS)


def _oversized_media_reminder(item: BinaryContent, *, user_prompt: bool) -> TextContent | str:
    text = _OVERSIZED_IMAGE_REMINDER if item.is_image else _OVERSIZED_VIDEO_REMINDER
    return (
        TextContent(content=text, metadata={"display": False, "source_id": "self_healing_model"})
        if user_prompt
        else text
    )


def _drop_inline_media(history: list[ModelMessage]) -> int:
    removed = 0
    for message in history:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart) or type(part) is ToolReturnPart:
                    removed += _drop_part_media(cast(UserPromptPart | ToolReturnPart, part))
    return removed


def _drop_part_media(part: UserPromptPart | ToolReturnPart) -> int:
    content = part.content
    user_prompt = isinstance(part, UserPromptPart)
    if isinstance(content, BinaryContent):
        if content.media_type.startswith(("image/", "video/")):
            reminder = _oversized_media_reminder(content, user_prompt=user_prompt)
            if isinstance(part, UserPromptPart):
                part.content = [reminder]
            else:
                part.content = reminder
            return 1
        return 0
    if isinstance(content, str) or not isinstance(content, Sequence):
        return 0
    items = list(content)
    removed = 0
    for index, item in enumerate(items):
        if isinstance(item, BinaryContent) and item.media_type.startswith(("image/", "video/")):
            items[index] = _oversized_media_reminder(item, user_prompt=user_prompt)
            removed += 1
    if removed:
        part.content = items
    return removed


DEFAULT_MODEL_RECOVERY_RULES: tuple[ModelRecoveryRule, ...] = (
    ModelRecoveryRule("oversized_payload", _is_oversized_payload, _drop_inline_media),
    ModelRecoveryRule("invalid_provider_item_id", _is_invalid_provider_item_id, strip_provider_native_state),
    ModelRecoveryRule("anthropic_incomplete_thinking", _is_anthropic_incomplete_thinking, strip_thinking_parts),
    ModelRecoveryRule("anthropic_modified_thinking", _is_anthropic_modified_thinking, strip_thinking_parts),
    ModelRecoveryRule("stale_reasoning", _is_stale_reasoning, strip_thinking_parts),
)

__all__ = ["ModelRecoveryRule", "SelfHealingModel"]
