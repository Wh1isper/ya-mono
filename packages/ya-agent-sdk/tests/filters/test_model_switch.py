"""Compatibility tests for ya_agent_sdk.filters.model_switch module."""

from ya_agent_sdk.filters.model_switch import handle_model_switch
from ya_agent_sdk.filters.reasoning_normalize import normalize_reasoning_for_model


def test_handle_model_switch_reexports_reasoning_normalize() -> None:
    """Historical import path should point to reasoning normalization."""
    assert handle_model_switch is normalize_reasoning_for_model
