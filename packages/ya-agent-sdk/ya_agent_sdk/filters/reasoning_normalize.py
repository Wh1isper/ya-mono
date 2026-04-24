"""Normalize reasoning parts for the active model provider."""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart

from ya_agent_sdk._logger import logger
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.context.agent import ModelCapability, ModelConfig

# Empty content satisfies DeepSeek reasoning validation while keeping the
# synthesized part semantically inert.
_SYNTHETIC_REASONING = ""


def normalize_reasoning_for_model(
    ctx: RunContext[AgentContext],
    history: list[ModelMessage],
) -> list[ModelMessage]:
    """Ensure historical assistant messages match the active model's reasoning policy.

    Models with ``reasoning_required`` need every historical ``ModelResponse`` to
    contain a ``ThinkingPart``. When a response lacks one, this filter inserts an
    empty provider-tagged ``ThinkingPart`` at the head of the response.

    Models with ``reasoning_foreign_incompatible`` accept only same-provider
    ``ThinkingPart`` entries, so foreign-provider thinking entries are removed
    before any required placeholder is synthesized.
    """
    if not history:
        return history

    model_cfg = ctx.deps.model_cfg
    if not isinstance(model_cfg, ModelConfig):
        return history

    requires, strict_provider = _reasoning_policy(model_cfg)
    if not (requires or strict_provider):
        return history

    current_provider = _provider_tag(ctx)
    synthesized = 0
    dropped = 0

    for msg in history:
        if not isinstance(msg, ModelResponse):
            continue

        if strict_provider:
            dropped += _drop_foreign_thinking(msg, current_provider)

        if requires and _missing_thinking(msg):
            _prepend_synthetic_thinking(msg, current_provider)
            synthesized += 1

    if synthesized or dropped:
        logger.debug(
            "Reasoning normalize: synthesized=%d dropped=%d (provider=%s)",
            synthesized,
            dropped,
            current_provider,
        )

    return history


def _reasoning_policy(model_cfg: ModelConfig) -> tuple[bool, bool]:
    """Return reasoning-required and strict-provider flags for a model config."""
    caps = model_cfg.capabilities
    return (
        ModelCapability.reasoning_required in caps,
        ModelCapability.reasoning_foreign_incompatible in caps,
    )


def _drop_foreign_thinking(msg: ModelResponse, current_provider: str) -> int:
    """Drop ThinkingPart entries whose provider differs from the active provider."""
    original_count = len(msg.parts)
    msg.parts = [
        part
        for part in msg.parts
        if not isinstance(part, ThinkingPart) or (part.provider_name or "") == current_provider
    ]
    return original_count - len(msg.parts)


def _missing_thinking(msg: ModelResponse) -> bool:
    """Return whether a response lacks a ThinkingPart."""
    return not any(isinstance(part, ThinkingPart) for part in msg.parts)


def _prepend_synthetic_thinking(msg: ModelResponse, current_provider: str) -> None:
    """Prepend an empty provider-tagged ThinkingPart to a response."""
    msg.parts = [
        ThinkingPart(content=_SYNTHETIC_REASONING, provider_name=current_provider),
        *msg.parts,
    ]


def _provider_tag(ctx: RunContext[AgentContext]) -> str:
    """Return the best-effort provider tag for ``ThinkingPart.provider_name``."""
    model = ctx.model
    return getattr(model, "system", None) or getattr(model, "model_name", None) or "unknown"
