"""Immutable model-request helpers shared by foundation capabilities."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any, TypeVar

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
    cloned.messages = messages if messages is not None else copy.deepcopy(request_context.messages)
    return cloned


async def apply_history_processor(
    processor: HistoryProcessor[DepsT],
    ctx: RunContext[DepsT],
    request_context: ModelRequestContext,
) -> ModelRequestContext:
    """Apply a legacy algorithm copy-on-write at the canonical request boundary."""
    messages = copy.deepcopy(request_context.messages)
    processed = processor(ctx, messages)
    if inspect.isawaitable(processed):
        processed = await processed
    if processed == request_context.messages:
        return request_context
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
    projected = await apply_history_processor(processor, replace(ctx, messages=messages), request_context)
    if projected is request_context:
        return request_context
    updated_request = projected.messages[-1]
    if not isinstance(updated_request, ModelRequest):
        raise TypeError("Context snapshot processor must preserve the final ModelRequest")
    updated_request.metadata = {**(updated_request.metadata or {}), snapshot_key: True}
    return projected


async def project_history(
    processor: HistoryProcessor[DepsT],
    ctx: RunContext[DepsT],
    request_context: ModelRequestContext,
    handler: Callable[[ModelRequestContext], Awaitable[Any]],
) -> Any:
    """Apply a processor to a request-only copy and invoke the next handler."""
    projected = await apply_history_processor(processor, ctx, request_context)
    return await handler(projected)
