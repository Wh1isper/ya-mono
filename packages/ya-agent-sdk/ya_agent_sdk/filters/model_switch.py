"""Compatibility exports for historical model-switch reasoning handling."""

from ya_agent_sdk.filters.reasoning_normalize import normalize_reasoning_for_model

handle_model_switch = normalize_reasoning_for_model

__all__ = ["handle_model_switch", "normalize_reasoning_for_model"]
