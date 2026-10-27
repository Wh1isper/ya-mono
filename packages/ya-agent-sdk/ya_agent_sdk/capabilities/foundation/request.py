"""Canonical context snapshots and request-only media/file projections."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability, CapabilityOrdering, ReinjectSystemPrompt
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models import ModelRequestContext

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.filters.capability import filter_by_capability
from ya_agent_sdk.filters.environment_instructions import create_environment_instructions_filter
from ya_agent_sdk.filters.file_inspection import build_file_inspection_prompt
from ya_agent_sdk.filters.image import (
    compress_large_images,
    drop_extra_images,
    drop_extra_videos,
    drop_gif_images,
    split_large_images,
)
from ya_agent_sdk.filters.runtime_instructions import inject_runtime_instructions

from ._request import apply_context_snapshot, apply_history_processor, copy_request_context
from .history import ColdStartCapability, ContextCompactionCapability, HandoffCapability

ModelHandler = Callable[[ModelRequestContext], Awaitable[Any]]


async def _project_media(
    ctx: RunContext[AgentContext],
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    processors = (
        split_large_images,
        compress_large_images,
        drop_extra_images,
        drop_gif_images,
        drop_extra_videos,
        filter_by_capability,
    )
    # These processors assign content on request parts; nested media transforms
    # construct replacement containers/content. Share response trees and large tool
    # payloads rather than deepcopying the entire conversation before every request.
    current = [
        replace(
            message,
            parts=[
                replace(part) if isinstance(part, (UserPromptPart, ToolReturnPart)) else part for part in message.parts
            ],
        )
        if isinstance(message, ModelRequest)
        else message
        for message in messages
    ]
    for processor in processors:
        result = processor(ctx, current)
        current = await result if inspect.isawaitable(result) else result
    return current


@dataclass(kw_only=True)
class MediaCompatibilityCapability(AbstractCapability[AgentContext]):
    """Project media into the active provider's request envelope only."""

    id: str | None = "media_compatibility"

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(
            wrapped_by=(
                HandoffCapability,
                ContextCompactionCapability,
                ColdStartCapability,
                ReinjectSystemPrompt,
                EnvironmentContextCapability,
                RuntimeContextCapability,
            ),
            wraps=(FileInspectionCapability,),
        )

    async def before_model_request(
        self,
        ctx: RunContext[AgentContext],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        return await apply_history_processor(_project_media, ctx, request_context, persist=False, copy_on_write=True)


@dataclass(kw_only=True)
class FileInspectionCapability(AbstractCapability[AgentContext]):
    """Inject a one-shot file-inspection reminder and commit after success."""

    id: str | None = "file_inspection"

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(
            wrapped_by=(
                HandoffCapability,
                ContextCompactionCapability,
                ColdStartCapability,
                ReinjectSystemPrompt,
                EnvironmentContextCapability,
                RuntimeContextCapability,
            )
        )

    async def before_model_request(
        self,
        ctx: RunContext[AgentContext],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        pending = tuple(ctx.deps.files_to_inspect)
        if not pending:
            return request_context

        messages = list(request_context.messages)
        last_request = next(
            (message for message in reversed(messages) if isinstance(message, ModelRequest)),
            None,
        )
        if last_request is None:
            return request_context

        messages[messages.index(last_request)] = replace(
            last_request,
            parts=[
                *last_request.parts,
                UserPromptPart(content=build_file_inspection_prompt(list(pending))),
            ],
        )
        return copy_request_context(request_context, messages=messages)

    async def wrap_model_request(
        self,
        ctx: RunContext[AgentContext],
        *,
        request_context: ModelRequestContext,
        handler: ModelHandler,
    ) -> Any:
        pending = tuple(ctx.deps.files_to_inspect)
        response = await handler(request_context)
        remaining = list(ctx.deps.files_to_inspect)
        for path in pending:
            with suppress(ValueError):
                remaining.remove(path)
        ctx.deps.files_to_inspect = remaining
        return response


@dataclass(kw_only=True)
class EnvironmentContextCapability(AbstractCapability[AgentContext]):
    """Persist current Environment instructions as a canonical request snapshot."""

    id: str | None = "environment_context"

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(
            wrapped_by=(HandoffCapability, ContextCompactionCapability, ColdStartCapability, ReinjectSystemPrompt),
            wraps=(RuntimeContextCapability,),
        )

    async def before_model_request(
        self,
        ctx: RunContext[AgentContext],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        env = ctx.deps.env
        if env is None:
            return request_context
        processor = create_environment_instructions_filter(env)
        return await apply_context_snapshot(processor, ctx, request_context, snapshot_key="ya:environment_context")


@dataclass(kw_only=True)
class RuntimeContextCapability(AbstractCapability[AgentContext]):
    """Persist fresh runtime/session context as a canonical request snapshot."""

    id: str | None = "runtime_context"

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(
            wrapped_by=(HandoffCapability, ContextCompactionCapability, ColdStartCapability, ReinjectSystemPrompt),
        )

    async def before_model_request(
        self,
        ctx: RunContext[AgentContext],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        return await apply_context_snapshot(
            inject_runtime_instructions, ctx, request_context, snapshot_key="ya:runtime_context"
        )
