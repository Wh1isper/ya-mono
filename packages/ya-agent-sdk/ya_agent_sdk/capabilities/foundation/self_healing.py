# Copyright 2026 Converge AI
# SPDX-License-Identifier: Apache-2.0
# Adapted from agent-foundation e36d0518c51a1d89eef20715de4f3b187040d885.
# Modified for YA's explicit runtime foundation and capability catalog.
"""Install self-healing around the effective request model."""

from __future__ import annotations

from collections.abc import Sequence
from copy import copy
from dataclasses import dataclass

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability, CapabilityOrdering
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.models.wrapper import WrapperModel

from ya_agent_sdk.agents.models.self_healing import DEFAULT_MODEL_RECOVERY_RULES, ModelRecoveryRule, SelfHealingModel
from ya_agent_sdk.context import AgentContext


@dataclass(init=False)
class SelfHealingModelCapability(AbstractCapability[AgentContext]):
    """Wrap the final effective model, once, for request-local repair."""

    id = "self_healing_model"

    def __init__(self, rules: Sequence[ModelRecoveryRule] | None = None) -> None:
        self.rules = DEFAULT_MODEL_RECOVERY_RULES if rules is None else tuple(rules)

    @classmethod
    def from_spec(cls) -> SelfHealingModelCapability:
        """Portable specs use the defaults; callable rules are Python-only."""
        return cls()

    def get_ordering(self) -> CapabilityOrdering:
        return CapabilityOrdering(position="innermost")

    async def before_model_request(
        self, ctx: RunContext[AgentContext], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        model = request_context.model
        while isinstance(model, WrapperModel):
            if isinstance(model, SelfHealingModel):
                return request_context
            model = model.wrapped
        updated = copy(request_context)
        updated.model = SelfHealingModel(request_context.model, rules=self.rules)
        return updated
