"""Immutable model-request helpers shared by foundation capabilities."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import TypeVar

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest
from pydantic_ai.models import ModelRequestContext

DepsT = TypeVar("DepsT")
HistoryProcessor = Callable[
    [RunContext[DepsT], list[ModelMessage]],
    list[ModelMessage] | Awaitable[list[ModelMessage]],
]


def copy_request_context(
    request_context: ModelRequestContext,
    *,
    messages: list[ModelMessage] | None = None,
) -> ModelRequestContext:
    """Clone a request envelope while preserving upstream read-only metadata."""
    cloned = copy.copy(request_context)
    cloned.messages = messages if messages is not None else copy.deepcopy(list(request_context.messages))
    return cloned


async def apply_history_processor(
    processor: HistoryProcessor[DepsT],
    ctx: RunContext[DepsT],
    request_context: ModelRequestContext,
    *,
    persist: bool = True,
    copy_on_write: bool = False,
) -> ModelRequestContext:
    """Apply a transformer, isolating legacy mutators and committing canonical changes.

    SDK-owned copy-on-write processors share unchanged messages and replace every
    modified node. Unknown processors retain a detached input tree.
    """
    messages = list(request_context.messages)
    if not copy_on_write:
        messages = copy.deepcopy(messages)
    processed = processor(ctx, messages)
    if inspect.isawaitable(processed):
        processed = await processed
    if len(processed) == len(request_context.messages) and all(
        new is old for new, old in zip(processed, request_context.messages, strict=True)
    ):
        return request_context
    if processed == request_context.messages:
        return request_context
    if persist:
        ctx.messages[:] = processed
    return copy_request_context(request_context, messages=processed)


async def apply_context_snapshot(
    processor: HistoryProcessor[DepsT],
    ctx: RunContext[DepsT],
    request_context: ModelRequestContext,
    *,
    snapshot_key: str,
) -> ModelRequestContext:
    """Commit one snapshot per canonical request, including across retry/restore.

    Request metadata, not rendered text, records ownership. Replaying an unanswered
    request must retain its original snapshot rather than prepend another one.
    Lifecycle reducers create new requests, so their continuations get fresh context.
    """
    messages = request_context.messages
    if not messages or not isinstance(messages[-1], ModelRequest):
        return request_context
    last_request = messages[-1]
    if (last_request.metadata or {}).get(snapshot_key):
        return request_context

    # Earlier before-model hooks may have replaced history without updating ctx.messages.
    # Usage and pressure reminders must describe the retained, post-lifecycle history.
    projected = await apply_history_processor(
        processor, replace(ctx, messages=messages), request_context, persist=False, copy_on_write=True
    )
    if projected is request_context:
        return request_context
    updated_request = projected.messages[-1]
    if not isinstance(updated_request, ModelRequest):
        raise TypeError("Context snapshot processor must preserve the final ModelRequest")
    projected.messages[-1] = replace(updated_request, metadata={**(updated_request.metadata or {}), snapshot_key: True})
    ctx.messages[:] = projected.messages
    return projected
