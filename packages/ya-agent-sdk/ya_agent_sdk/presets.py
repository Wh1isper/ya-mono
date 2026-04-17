"""ModelSettings presets for different providers and thinking levels.

This module provides pre-configured ModelSettings for common use cases across
different model providers (Anthropic, OpenAI, Gemini). Each provider has presets
for different "thinking levels" (reasoning intensity).

Naming Convention:
- `{provider}_{level}` - e.g., `anthropic_high`, `openai_medium`
- `{provider}_{api}_{level}` - for providers with multiple APIs, e.g., `openai_responses_high`

Thinking Levels:
- `high`: Maximum reasoning depth, higher latency
- `medium`: Balanced reasoning (default)
- `low`: Minimal reasoning, lower latency

Adaptive Thinking (Anthropic Opus 4.6 / Sonnet 4.6):
- Uses `thinking.type: "adaptive"` instead of fixed budget_tokens
- Claude dynamically determines when and how much to think
- Effort parameter (`anthropic_effort`) guides thinking depth
- Automatically enables interleaved thinking (no beta header needed)
- Presets: `anthropic_adaptive_{level}` where level is the effort level

Usage::

    from ya_agent_sdk.subagents.presets import get_model_settings, ModelSettingsPreset

    # Get preset by name
    settings = get_model_settings("anthropic_high")

    # Or use enum
    settings = get_model_settings(ModelSettingsPreset.ANTHROPIC_HIGH)

    # Use with Agent
    agent = Agent(model="anthropic:claude-sonnet-4", model_settings=settings)
"""

from __future__ import annotations

import copy
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from ya_agent_sdk.context import ModelCapability

if TYPE_CHECKING:
    from pydantic_ai import ModelSettings

# =============================================================================
# Constants
# =============================================================================

K_TOKENS = 1024

# Anthropic beta headers for extended context
ANTHROPIC_1M_BETA = "context-1m-2025-08-07"
ANTHROPIC_INTERLEAVED_BETA = "interleaved-thinking-2025-05-14"
ANTHROPIC_CONTEXT_MANAGEMENT_BETA = "context-management-2025-06-27"


def build_anthropic_betas(
    *,
    use_1m_context: bool = False,
    use_interleaved_thinking: bool = False,
    use_context_management: bool = False,
) -> dict[str, str]:
    """Build list of Anthropic beta headers for extended context."""
    betas = []
    if use_1m_context:
        betas.append(ANTHROPIC_1M_BETA)
    if use_interleaved_thinking:
        betas.append(ANTHROPIC_INTERLEAVED_BETA)
    if use_context_management:
        betas.append(ANTHROPIC_CONTEXT_MANAGEMENT_BETA)

    if not betas:
        return {}
    return {
        "anthropic-beta": ",".join(betas),
    }


def build_context_management(
    *,
    clear_tool_uses: bool = False,
    tool_use_trigger_tokens: int = 100_000,
    tool_use_keep: int = 3,
    tool_use_clear_at_least: int | None = 20_000,
    tool_use_clear_inputs: bool = False,
    tool_use_exclude_tools: list[str] | None = None,
    clear_thinking: bool = True,
    thinking_keep_turns: int | Literal["all"] = "all",
) -> dict[str, Any]:
    """Build context_management config for Anthropic API.

    Creates a context management configuration that controls server-side clearing
    of tool results and thinking blocks from conversation history.

    Args:
        clear_tool_uses: Enable clearing old tool results.
        tool_use_trigger_tokens: Input token threshold to trigger clearing.
        tool_use_keep: Number of recent tool use/result pairs to keep.
        tool_use_clear_at_least: Minimum tokens to clear (None to disable).
        tool_use_clear_inputs: Also clear tool call parameters (not just results).
        tool_use_exclude_tools: Tool names that should never be cleared.
        clear_thinking: Enable clearing old thinking blocks.
        thinking_keep_turns: Number of recent assistant turns with thinking to keep,
            or "all" to keep all thinking blocks.

    Returns:
        Dict suitable for the ``context_management`` field in Anthropic API requests.

    Example::

        cm = build_context_management(tool_use_trigger_tokens=50_000, thinking_keep_turns=3)
    """
    edits: list[dict[str, Any]] = []

    # Thinking clearing must come first per Anthropic docs
    if clear_thinking:
        thinking_edit: dict[str, Any] = {"type": "clear_thinking_20251015"}
        if thinking_keep_turns == "all":
            thinking_edit["keep"] = "all"
        else:
            thinking_edit["keep"] = {"type": "thinking_turns", "value": thinking_keep_turns}
        edits.append(thinking_edit)

    if clear_tool_uses:
        tool_edit: dict[str, Any] = {
            "type": "clear_tool_uses_20250919",
            "trigger": {"type": "input_tokens", "value": tool_use_trigger_tokens},
            "keep": {"type": "tool_uses", "value": tool_use_keep},
        }
        if tool_use_clear_at_least is not None:
            tool_edit["clear_at_least"] = {"type": "input_tokens", "value": tool_use_clear_at_least}
        if tool_use_exclude_tools:
            tool_edit["exclude_tools"] = tool_use_exclude_tools
        if tool_use_clear_inputs:
            tool_edit["clear_tool_inputs"] = True
        edits.append(tool_edit)

    return {"edits": edits}


def with_context_management(
    settings: dict[str, Any],
    context_management: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Add Anthropic context management to existing model settings.

    Creates a new settings dict (deep copy) with the context management beta header
    and ``extra_body`` containing the ``context_management`` configuration.

    Args:
        settings: Existing Anthropic model settings dict (e.g., from a preset).
        context_management: Pre-built context_management config from
            :func:`build_context_management`, or None to build one from kwargs.
        **kwargs: Passed to :func:`build_context_management` when
            ``context_management`` is None.

    Returns:
        New settings dict with context management enabled.

    Example::

        # Default context management on any preset
        settings = with_context_management(ANTHROPIC_HIGH)

        # Customize parameters
        settings = with_context_management(
            ANTHROPIC_DEFAULT,
            tool_use_trigger_tokens=50_000,
            thinking_keep_turns="all",
        )

        # Use pre-built config
        cm = build_context_management(clear_thinking=False)
        settings = with_context_management(ANTHROPIC_MEDIUM, context_management=cm)
    """
    new_settings = copy.deepcopy(settings)

    if context_management is None:
        context_management = build_context_management(**kwargs)

    # Merge beta header
    existing_beta = new_settings.get("extra_headers", {}).get("anthropic-beta", "")
    betas = [b.strip() for b in existing_beta.split(",") if b.strip()]
    if ANTHROPIC_CONTEXT_MANAGEMENT_BETA not in betas:
        betas.append(ANTHROPIC_CONTEXT_MANAGEMENT_BETA)
    new_settings.setdefault("extra_headers", {})["anthropic-beta"] = ",".join(betas)

    # Merge extra_body
    existing_body = new_settings.get("extra_body") or {}
    if not isinstance(existing_body, dict):
        existing_body = {}
    existing_body["context_management"] = context_management
    new_settings["extra_body"] = existing_body

    return new_settings


# =============================================================================
# Preset Enum
# =============================================================================


class ModelSettingsPreset(StrEnum):
    """Available ModelSettings presets."""

    # Anthropic standard presets (no beta headers)
    ANTHROPIC_DEFAULT = "anthropic_default"
    ANTHROPIC_HIGH = "anthropic_high"
    ANTHROPIC_MEDIUM = "anthropic_medium"
    ANTHROPIC_LOW = "anthropic_low"
    ANTHROPIC_OFF = "anthropic_off"

    # Anthropic adaptive thinking presets (for Opus 4.6 / Sonnet 4.6)
    ANTHROPIC_ADAPTIVE_DEFAULT = "anthropic_adaptive_default"
    ANTHROPIC_ADAPTIVE_HIGH = "anthropic_adaptive_high"
    ANTHROPIC_ADAPTIVE_MEDIUM = "anthropic_adaptive_medium"
    ANTHROPIC_ADAPTIVE_LOW = "anthropic_adaptive_low"

    # Anthropic adaptive + 1M context presets
    ANTHROPIC_ADAPTIVE_1M_DEFAULT = "anthropic_adaptive_1m_default"
    ANTHROPIC_ADAPTIVE_1M_HIGH = "anthropic_adaptive_1m_high"
    ANTHROPIC_ADAPTIVE_1M_MEDIUM = "anthropic_adaptive_1m_medium"
    ANTHROPIC_ADAPTIVE_1M_LOW = "anthropic_adaptive_1m_low"

    # Anthropic adaptive + context management presets
    ANTHROPIC_ADAPTIVE_CM_DEFAULT = "anthropic_adaptive_cm_default"
    ANTHROPIC_ADAPTIVE_CM_HIGH = "anthropic_adaptive_cm_high"
    ANTHROPIC_ADAPTIVE_CM_MEDIUM = "anthropic_adaptive_cm_medium"
    ANTHROPIC_ADAPTIVE_CM_LOW = "anthropic_adaptive_cm_low"

    # Anthropic adaptive + 1M context + context management presets
    ANTHROPIC_ADAPTIVE_1M_CM_DEFAULT = "anthropic_adaptive_1m_cm_default"
    ANTHROPIC_ADAPTIVE_1M_CM_HIGH = "anthropic_adaptive_1m_cm_high"
    ANTHROPIC_ADAPTIVE_1M_CM_MEDIUM = "anthropic_adaptive_1m_cm_medium"
    ANTHROPIC_ADAPTIVE_1M_CM_LOW = "anthropic_adaptive_1m_cm_low"

    # Anthropic interleaved thinking presets (with beta headers)
    ANTHROPIC_DEFAULT_INTERLEAVED_THINKING = "anthropic_default_interleaved_thinking"
    ANTHROPIC_HIGH_INTERLEAVED_THINKING = "anthropic_high_interleaved_thinking"
    ANTHROPIC_MEDIUM_INTERLEAVED_THINKING = "anthropic_medium_interleaved_thinking"
    ANTHROPIC_LOW_INTERLEAVED_THINKING = "anthropic_low_interleaved_thinking"
    ANTHROPIC_OFF_INTERLEAVED_THINKING = "anthropic_off_interleaved_thinking"

    # Anthropic 1M context presets (with beta headers for extended context)
    ANTHROPIC_1M_DEFAULT = "anthropic_1m_default"
    ANTHROPIC_1M_HIGH = "anthropic_1m_high"
    ANTHROPIC_1M_MEDIUM = "anthropic_1m_medium"
    ANTHROPIC_1M_LOW = "anthropic_1m_low"
    ANTHROPIC_1M_OFF = "anthropic_1m_off"

    # Anthropic 1M context + interleaved thinking presets (with beta headers)
    ANTHROPIC_1M_DEFAULT_INTERLEAVED_THINKING = "anthropic_1m_default_interleaved_thinking"
    ANTHROPIC_1M_HIGH_INTERLEAVED_THINKING = "anthropic_1m_high_interleaved_thinking"
    ANTHROPIC_1M_MEDIUM_INTERLEAVED_THINKING = "anthropic_1m_medium_interleaved_thinking"
    ANTHROPIC_1M_LOW_INTERLEAVED_THINKING = "anthropic_1m_low_interleaved_thinking"
    ANTHROPIC_1M_OFF_INTERLEAVED_THINKING = "anthropic_1m_off_interleaved_thinking"

    # Anthropic context management presets (server-side tool result and thinking block clearing)
    ANTHROPIC_CM_DEFAULT = "anthropic_cm_default"
    ANTHROPIC_CM_HIGH = "anthropic_cm_high"
    ANTHROPIC_CM_MEDIUM = "anthropic_cm_medium"
    ANTHROPIC_CM_LOW = "anthropic_cm_low"
    ANTHROPIC_CM_OFF = "anthropic_cm_off"

    # Anthropic 1M context + context management presets
    ANTHROPIC_1M_CM_DEFAULT = "anthropic_1m_cm_default"
    ANTHROPIC_1M_CM_HIGH = "anthropic_1m_cm_high"
    ANTHROPIC_1M_CM_MEDIUM = "anthropic_1m_cm_medium"
    ANTHROPIC_1M_CM_LOW = "anthropic_1m_cm_low"
    ANTHROPIC_1M_CM_OFF = "anthropic_1m_cm_off"

    # Anthropic context management + interleaved thinking presets
    ANTHROPIC_CM_DEFAULT_INTERLEAVED_THINKING = "anthropic_cm_default_interleaved_thinking"
    ANTHROPIC_CM_HIGH_INTERLEAVED_THINKING = "anthropic_cm_high_interleaved_thinking"
    ANTHROPIC_CM_MEDIUM_INTERLEAVED_THINKING = "anthropic_cm_medium_interleaved_thinking"
    ANTHROPIC_CM_LOW_INTERLEAVED_THINKING = "anthropic_cm_low_interleaved_thinking"
    ANTHROPIC_CM_OFF_INTERLEAVED_THINKING = "anthropic_cm_off_interleaved_thinking"

    # Anthropic 1M context + context management + interleaved thinking presets
    ANTHROPIC_1M_CM_DEFAULT_INTERLEAVED_THINKING = "anthropic_1m_cm_default_interleaved_thinking"
    ANTHROPIC_1M_CM_HIGH_INTERLEAVED_THINKING = "anthropic_1m_cm_high_interleaved_thinking"
    ANTHROPIC_1M_CM_MEDIUM_INTERLEAVED_THINKING = "anthropic_1m_cm_medium_interleaved_thinking"
    ANTHROPIC_1M_CM_LOW_INTERLEAVED_THINKING = "anthropic_1m_cm_low_interleaved_thinking"
    ANTHROPIC_1M_CM_OFF_INTERLEAVED_THINKING = "anthropic_1m_cm_off_interleaved_thinking"

    # OpenAI Chat Completions presets (GPT-4, etc.)
    OPENAI_DEFAULT = "openai_default"
    OPENAI_HIGH = "openai_high"
    OPENAI_MEDIUM = "openai_medium"
    OPENAI_LOW = "openai_low"

    # OpenAI Responses API presets (o1, o3 reasoning models)
    OPENAI_RESPONSES_DEFAULT = "openai_responses_default"
    OPENAI_RESPONSES_HIGH = "openai_responses_high"
    OPENAI_RESPONSES_MEDIUM = "openai_responses_medium"
    OPENAI_RESPONSES_LOW = "openai_responses_low"

    # Gemini thinking_budget presets (for Gemini 2.5)
    GEMINI_THINKING_BUDGET_DEFAULT = "gemini_thinking_budget_default"
    GEMINI_THINKING_BUDGET_HIGH = "gemini_thinking_budget_high"
    GEMINI_THINKING_BUDGET_MEDIUM = "gemini_thinking_budget_medium"
    GEMINI_THINKING_BUDGET_LOW = "gemini_thinking_budget_low"

    # Gemini thinking_level presets (for Gemini 3)
    GEMINI_THINKING_LEVEL_DEFAULT = "gemini_thinking_level_default"
    GEMINI_THINKING_LEVEL_HIGH = "gemini_thinking_level_high"
    GEMINI_THINKING_LEVEL_MEDIUM = "gemini_thinking_level_medium"
    GEMINI_THINKING_LEVEL_LOW = "gemini_thinking_level_low"
    GEMINI_THINKING_LEVEL_MINIMAL = "gemini_thinking_level_minimal"


# =============================================================================
# Anthropic Presets
# =============================================================================


def _anthropic_settings(
    thinking_budget: int,
    max_tokens: int = 21 * K_TOKENS,
    *,
    use_1m_context: bool = False,
    use_interleaved_thinking: bool = False,
    use_context_management: bool = False,
    context_management: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create Anthropic model settings with thinking enabled.

    Args:
        thinking_budget: Token budget for thinking (higher = more reasoning).
        max_tokens: Maximum output tokens.
        use_1m_context: Whether to include 1M context beta headers.
        use_interleaved_thinking: Whether to include interleaved thinking beta headers.
        use_context_management: Whether to include context management beta headers.
        context_management: Context management config to include via extra_body.
            If None and use_context_management is True, uses build_context_management() defaults.

    Returns:
        Dict suitable for AnthropicModelSettings.
    """
    settings: dict[str, Any] = {
        "max_tokens": max_tokens,
        "anthropic_thinking": {
            "type": "enabled",
            "budget_tokens": thinking_budget,
        },
        "anthropic_cache_instructions": True,
        "anthropic_cache_response": True,
        "anthropic_cache_messages": True,
    }
    extra_headers = build_anthropic_betas(
        use_1m_context=use_1m_context,
        use_interleaved_thinking=use_interleaved_thinking,
        use_context_management=use_context_management,
    )
    if extra_headers:
        settings["extra_headers"] = extra_headers
    if use_context_management:
        cm = context_management if context_management is not None else build_context_management()
        settings["extra_body"] = {"context_management": cm}
    return settings


def _anthropic_adaptive_settings(
    effort: Literal["low", "medium", "high", "max"] = "high",
    max_tokens: int = 32 * K_TOKENS,
    *,
    use_1m_context: bool = False,
    use_context_management: bool = False,
    context_management: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create Anthropic model settings with adaptive thinking.

    Adaptive thinking lets Claude dynamically determine when and how much to use
    extended thinking. It automatically enables interleaved thinking (no beta
    header needed). Supported on Opus 4.6 and Sonnet 4.6.

    Args:
        effort: Effort level guiding how much thinking Claude does.
            'high' (default) always thinks deeply, 'medium' uses moderate thinking,
            'low' minimizes thinking, 'max' is unconstrained (Opus 4.6 only).
        max_tokens: Maximum output tokens (includes thinking + response).
        use_1m_context: Whether to include 1M context beta headers.
        use_context_management: Whether to include context management beta headers.
        context_management: Context management config to include via extra_body.
            If None and use_context_management is True, uses build_context_management() defaults.

    Returns:
        Dict suitable for AnthropicModelSettings.
    """
    settings: dict[str, Any] = {
        "max_tokens": max_tokens,
        "anthropic_thinking": {
            "type": "adaptive",
            "display": "summarized",
        },
        "anthropic_effort": effort,
        "anthropic_cache_instructions": True,
        "anthropic_cache_response": True,
        "anthropic_cache_messages": True,
    }
    # Adaptive thinking does NOT need interleaved thinking beta (it's automatic)
    extra_headers = build_anthropic_betas(
        use_1m_context=use_1m_context,
        use_context_management=use_context_management,
    )
    if extra_headers:
        settings["extra_headers"] = extra_headers
    if use_context_management:
        cm = context_management if context_management is not None else build_context_management()
        settings["extra_body"] = {"context_management": cm}
    return settings


def _anthropic_off_settings(
    *,
    use_1m_context: bool = False,
    use_interleaved_thinking: bool = False,
    use_context_management: bool = False,
    context_management: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create Anthropic model settings with thinking disabled.

    Args:
        use_1m_context: Whether to include 1M context beta headers.
        use_interleaved_thinking: Whether to include interleaved thinking beta headers.
        use_context_management: Whether to include context management beta headers.
        context_management: Context management config to include via extra_body.
            If None and use_context_management is True, uses build_context_management() defaults.

    Returns:
        Dict suitable for AnthropicModelSettings.
    """
    settings: dict[str, Any] = {
        "anthropic_thinking": {
            "type": "disabled",
        },
        "anthropic_cache_instructions": True,
        "anthropic_cache_response": True,
        "anthropic_cache_messages": True,
    }
    extra_headers = build_anthropic_betas(
        use_1m_context=use_1m_context,
        use_interleaved_thinking=use_interleaved_thinking,
        use_context_management=use_context_management,
    )
    if extra_headers:
        settings["extra_headers"] = extra_headers
    if use_context_management:
        cm = context_management if context_management is not None else build_context_management(clear_thinking=False)
        settings["extra_body"] = {"context_management": cm}
    return settings


# -----------------------------------------------------------------------------
# Standard Anthropic presets (no beta headers)
# -----------------------------------------------------------------------------

ANTHROPIC_DEFAULT: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
)
"""Anthropic default: Same as medium, 16K thinking budget."""

ANTHROPIC_HIGH: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
)
"""Anthropic high thinking: 21K thinking budget, max reasoning depth."""

ANTHROPIC_MEDIUM: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
)
"""Anthropic medium thinking: 16K thinking budget, balanced reasoning."""

ANTHROPIC_LOW: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
)
"""Anthropic low thinking: 4K thinking budget, minimal reasoning overhead."""

ANTHROPIC_OFF: dict[str, Any] = _anthropic_off_settings()
"""Anthropic off: Thinking disabled, caching enabled."""

# -----------------------------------------------------------------------------
# Anthropic adaptive thinking presets (for Opus 4.6 / Sonnet 4.6)
# Adaptive thinking automatically enables interleaved thinking.
# -----------------------------------------------------------------------------

ANTHROPIC_ADAPTIVE_DEFAULT: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
)
"""Anthropic adaptive default: High effort (API default), Claude always thinks deeply."""

ANTHROPIC_ADAPTIVE_HIGH: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
)
"""Anthropic adaptive high: High effort, Claude always thinks deeply."""

ANTHROPIC_ADAPTIVE_MEDIUM: dict[str, Any] = _anthropic_adaptive_settings(
    effort="medium",
    max_tokens=21 * K_TOKENS,
)
"""Anthropic adaptive medium: Moderate thinking, may skip for simple queries."""

ANTHROPIC_ADAPTIVE_LOW: dict[str, Any] = _anthropic_adaptive_settings(
    effort="low",
    max_tokens=16 * K_TOKENS,
)
"""Anthropic adaptive low: Minimal thinking, skips for simple tasks."""

# -----------------------------------------------------------------------------
# Anthropic adaptive + 1M context presets
# -----------------------------------------------------------------------------

ANTHROPIC_ADAPTIVE_1M_DEFAULT: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic adaptive 1M default: High effort with 1M context beta."""

ANTHROPIC_ADAPTIVE_1M_HIGH: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic adaptive 1M high: High effort with 1M context beta."""

ANTHROPIC_ADAPTIVE_1M_MEDIUM: dict[str, Any] = _anthropic_adaptive_settings(
    effort="medium",
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic adaptive 1M medium: Moderate thinking with 1M context beta."""

ANTHROPIC_ADAPTIVE_1M_LOW: dict[str, Any] = _anthropic_adaptive_settings(
    effort="low",
    max_tokens=16 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic adaptive 1M low: Minimal thinking with 1M context beta."""

# -----------------------------------------------------------------------------
# Anthropic adaptive + context management presets
# -----------------------------------------------------------------------------

ANTHROPIC_ADAPTIVE_CM_DEFAULT: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic adaptive CM default: High effort with context management."""

ANTHROPIC_ADAPTIVE_CM_HIGH: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic adaptive CM high: High effort with context management."""

ANTHROPIC_ADAPTIVE_CM_MEDIUM: dict[str, Any] = _anthropic_adaptive_settings(
    effort="medium",
    max_tokens=21 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic adaptive CM medium: Moderate thinking with context management."""

ANTHROPIC_ADAPTIVE_CM_LOW: dict[str, Any] = _anthropic_adaptive_settings(
    effort="low",
    max_tokens=16 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic adaptive CM low: Minimal thinking with context management."""

# -----------------------------------------------------------------------------
# Anthropic adaptive + 1M context + context management presets
# -----------------------------------------------------------------------------

ANTHROPIC_ADAPTIVE_1M_CM_DEFAULT: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic adaptive 1M CM default: High effort with 1M context + context management."""

ANTHROPIC_ADAPTIVE_1M_CM_HIGH: dict[str, Any] = _anthropic_adaptive_settings(
    effort="high",
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic adaptive 1M CM high: High effort with 1M context + context management."""

ANTHROPIC_ADAPTIVE_1M_CM_MEDIUM: dict[str, Any] = _anthropic_adaptive_settings(
    effort="medium",
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic adaptive 1M CM medium: Moderate thinking with 1M context + context management."""

ANTHROPIC_ADAPTIVE_1M_CM_LOW: dict[str, Any] = _anthropic_adaptive_settings(
    effort="low",
    max_tokens=16 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic adaptive 1M CM low: Minimal thinking with 1M context + context management."""

# -----------------------------------------------------------------------------
# Anthropic interleaved thinking presets (with beta headers)
# -----------------------------------------------------------------------------

ANTHROPIC_DEFAULT_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_interleaved_thinking=True,
)
"""Anthropic interleaved default: Same as medium with interleaved thinking."""

ANTHROPIC_HIGH_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_interleaved_thinking=True,
)
"""Anthropic interleaved high: 21K thinking budget with interleaved thinking."""

ANTHROPIC_MEDIUM_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_interleaved_thinking=True,
)
"""Anthropic interleaved medium: 16K thinking budget with interleaved thinking."""

ANTHROPIC_LOW_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_interleaved_thinking=True,
)
"""Anthropic interleaved low: 4K thinking budget with interleaved thinking."""

ANTHROPIC_OFF_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_off_settings(
    use_interleaved_thinking=True,
)
"""Anthropic interleaved off: Thinking disabled with interleaved thinking."""

# -----------------------------------------------------------------------------
# Anthropic 1M context presets (with beta headers for extended context)
# -----------------------------------------------------------------------------

ANTHROPIC_1M_DEFAULT: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic 1M default: Same as medium, 16K thinking budget, with 1M context beta."""

ANTHROPIC_1M_HIGH: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic 1M high thinking: 21K thinking budget, max reasoning depth, with 1M context beta."""

ANTHROPIC_1M_MEDIUM: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic 1M medium thinking: 16K thinking budget, balanced reasoning, with 1M context beta."""

ANTHROPIC_1M_LOW: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_1m_context=True,
)
"""Anthropic 1M low thinking: 4K thinking budget, minimal reasoning overhead, with 1M context beta."""

ANTHROPIC_1M_OFF: dict[str, Any] = _anthropic_off_settings(use_1m_context=True)
"""Anthropic 1M off: Thinking disabled, with 1M context beta and caching enabled."""

# -----------------------------------------------------------------------------
# Anthropic 1M context + interleaved thinking presets (with beta headers)
# -----------------------------------------------------------------------------

ANTHROPIC_1M_DEFAULT_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
)
"""Anthropic 1M interleaved default: 16K thinking budget with 1M + interleaved thinking."""

ANTHROPIC_1M_HIGH_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
)
"""Anthropic 1M interleaved high: 21K thinking budget with 1M + interleaved thinking."""

ANTHROPIC_1M_MEDIUM_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
)
"""Anthropic 1M interleaved medium: 16K thinking budget with 1M + interleaved thinking."""

ANTHROPIC_1M_LOW_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
)
"""Anthropic 1M interleaved low: 4K thinking budget with 1M + interleaved thinking."""

ANTHROPIC_1M_OFF_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_off_settings(
    use_1m_context=True,
    use_interleaved_thinking=True,
)
"""Anthropic 1M interleaved off: Thinking disabled with 1M + interleaved thinking."""

# -----------------------------------------------------------------------------
# Anthropic context management presets (server-side tool result / thinking clearing)
# -----------------------------------------------------------------------------

ANTHROPIC_CM_DEFAULT: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic CM default: Same as medium, 16K thinking budget, with context management."""

ANTHROPIC_CM_HIGH: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic CM high: 21K thinking budget, max reasoning depth, with context management."""

ANTHROPIC_CM_MEDIUM: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic CM medium: 16K thinking budget, balanced reasoning, with context management."""

ANTHROPIC_CM_LOW: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_context_management=True,
)
"""Anthropic CM low: 4K thinking budget, minimal reasoning overhead, with context management."""

ANTHROPIC_CM_OFF: dict[str, Any] = _anthropic_off_settings(use_context_management=True)
"""Anthropic CM off: Thinking disabled, with context management (tool result clearing only)."""

# -----------------------------------------------------------------------------
# Anthropic 1M context + context management presets
# -----------------------------------------------------------------------------

ANTHROPIC_1M_CM_DEFAULT: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic 1M CM default: 16K thinking budget, with 1M context + context management."""

ANTHROPIC_1M_CM_HIGH: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic 1M CM high: 21K thinking budget, with 1M context + context management."""

ANTHROPIC_1M_CM_MEDIUM: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic 1M CM medium: 16K thinking budget, with 1M context + context management."""

ANTHROPIC_1M_CM_LOW: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic 1M CM low: 4K thinking budget, with 1M context + context management."""

ANTHROPIC_1M_CM_OFF: dict[str, Any] = _anthropic_off_settings(
    use_1m_context=True,
    use_context_management=True,
)
"""Anthropic 1M CM off: Thinking disabled, with 1M context + context management."""

# -----------------------------------------------------------------------------
# Anthropic context management + interleaved thinking presets
# -----------------------------------------------------------------------------

ANTHROPIC_CM_DEFAULT_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic CM interleaved default: 16K thinking budget with context management + interleaved thinking."""

ANTHROPIC_CM_HIGH_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic CM interleaved high: 21K thinking budget with context management + interleaved thinking."""

ANTHROPIC_CM_MEDIUM_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic CM interleaved medium: 16K thinking budget with context management + interleaved thinking."""

ANTHROPIC_CM_LOW_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic CM interleaved low: 4K thinking budget with context management + interleaved thinking."""

ANTHROPIC_CM_OFF_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_off_settings(
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic CM interleaved off: Thinking disabled with context management + interleaved thinking."""

# -----------------------------------------------------------------------------
# Anthropic 1M context + context management + interleaved thinking presets
# -----------------------------------------------------------------------------

ANTHROPIC_1M_CM_DEFAULT_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic 1M CM interleaved default: 16K thinking budget with 1M + context management + interleaved thinking."""

ANTHROPIC_1M_CM_HIGH_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=21 * K_TOKENS,
    max_tokens=32 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic 1M CM interleaved high: 21K thinking budget with 1M + context management + interleaved thinking."""

ANTHROPIC_1M_CM_MEDIUM_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic 1M CM interleaved medium: 16K thinking budget with 1M + context management + interleaved thinking."""

ANTHROPIC_1M_CM_LOW_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    use_1m_context=True,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic 1M CM interleaved low: 4K thinking budget with 1M + context management + interleaved thinking."""

ANTHROPIC_1M_CM_OFF_INTERLEAVED_THINKING: dict[str, Any] = _anthropic_off_settings(
    use_1m_context=True,
    use_interleaved_thinking=True,
    use_context_management=True,
)
"""Anthropic 1M CM interleaved off: Thinking disabled with 1M + context management + interleaved thinking."""


# =============================================================================
# OpenAI Chat Completions Presets
# =============================================================================


def _openai_chat_settings(
    reasoning_effort: Literal["low", "medium", "high"] | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Create OpenAI Chat Completions settings.

    Note: reasoning_effort is supported for o1/o3 models via Chat Completions API.
    For non-reasoning models (GPT-4, etc.), reasoning_effort is ignored.

    Args:
        reasoning_effort: Reasoning intensity for o1/o3 models ('low', 'medium', 'high').
        max_tokens: Maximum output tokens (None for model default).

    Returns:
        Dict suitable for OpenAIChatModelSettings.
    """
    settings: dict[str, Any] = {}
    if reasoning_effort is not None:
        settings["openai_reasoning_effort"] = reasoning_effort
    if max_tokens is not None:
        settings["max_tokens"] = max_tokens
    return settings


OPENAI_DEFAULT: dict[str, Any] = _openai_chat_settings(
    reasoning_effort="medium",
    max_tokens=8 * K_TOKENS,
)
"""OpenAI Chat default: Same as medium, balanced reasoning and max_tokens."""

OPENAI_HIGH: dict[str, Any] = _openai_chat_settings(
    reasoning_effort="high",
    max_tokens=16 * K_TOKENS,
)
"""OpenAI Chat high: Maximum reasoning effort, higher max_tokens."""

OPENAI_MEDIUM: dict[str, Any] = _openai_chat_settings(
    reasoning_effort="medium",
    max_tokens=8 * K_TOKENS,
)
"""OpenAI Chat medium: Balanced reasoning effort and max_tokens."""

OPENAI_LOW: dict[str, Any] = _openai_chat_settings(
    reasoning_effort="low",
    max_tokens=4 * K_TOKENS,
)
"""OpenAI Chat low: Minimal reasoning, lower max_tokens for faster responses."""


# =============================================================================
# OpenAI Responses API Presets (o1, o3 reasoning models)
# =============================================================================


def _openai_responses_settings(
    reasoning_effort: Literal["low", "medium", "high"],
    reasoning_summary: Literal["detailed", "concise", "auto"] = "auto",
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Create OpenAI Responses API settings for reasoning models.

    Args:
        reasoning_effort: Reasoning intensity ('low', 'medium', 'high').
        reasoning_summary: Summary level of reasoning process.
        max_tokens: Maximum output tokens (None for model default).

    Returns:
        Dict suitable for OpenAIResponsesModelSettings.
    """
    settings: dict[str, Any] = {
        "openai_store": False,
        "openai_reasoning_effort": reasoning_effort,
        "openai_reasoning_summary": reasoning_summary,
    }
    if max_tokens is not None:
        settings["max_output_tokens"] = max_tokens
    return settings


OPENAI_RESPONSES_DEFAULT: dict[str, Any] = _openai_responses_settings(
    reasoning_effort="medium",
    reasoning_summary="auto",
    max_tokens=16 * K_TOKENS,
)
"""OpenAI Responses default: Same as medium, balanced reasoning effort."""

OPENAI_RESPONSES_HIGH: dict[str, Any] = _openai_responses_settings(
    reasoning_effort="high",
    reasoning_summary="detailed",
    max_tokens=32 * K_TOKENS,
)
"""OpenAI Responses high: Maximum reasoning effort with detailed summary."""

OPENAI_RESPONSES_MEDIUM: dict[str, Any] = _openai_responses_settings(
    reasoning_effort="medium",
    reasoning_summary="auto",
    max_tokens=16 * K_TOKENS,
)
"""OpenAI Responses medium: Balanced reasoning effort."""

OPENAI_RESPONSES_LOW: dict[str, Any] = _openai_responses_settings(
    reasoning_effort="low",
    reasoning_summary="concise",
    max_tokens=8 * K_TOKENS,
)
"""OpenAI Responses low: Minimal reasoning, faster responses."""


# =============================================================================
# Gemini thinking_budget Presets (for Gemini 2.5)
# =============================================================================


def _gemini_thinking_budget_settings(
    thinking_budget: int,
    max_tokens: int | None = None,
    include_thoughts: bool = False,
) -> dict[str, Any]:
    """Create Gemini model settings with thinking_budget only (for Gemini 2.5).

    Args:
        thinking_budget: Token budget for thinking.
        max_tokens: Maximum output tokens.
        include_thoughts: Whether to include thinking in response.

    Returns:
        Dict suitable for GoogleModelSettings.
    """
    settings: dict[str, Any] = {
        "google_thinking_config": {
            "thinking_budget": thinking_budget,
            "include_thoughts": include_thoughts,
        },
    }
    if max_tokens is not None:
        settings["max_tokens"] = max_tokens
    return settings


GEMINI_THINKING_BUDGET_DEFAULT: dict[str, Any] = _gemini_thinking_budget_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=16 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 2.5 default: 16K thinking budget, balanced reasoning."""

GEMINI_THINKING_BUDGET_HIGH: dict[str, Any] = _gemini_thinking_budget_settings(
    thinking_budget=32 * K_TOKENS,
    max_tokens=21 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 2.5 high: 32K thinking budget, maximum reasoning depth."""

GEMINI_THINKING_BUDGET_MEDIUM: dict[str, Any] = _gemini_thinking_budget_settings(
    thinking_budget=16 * K_TOKENS,
    max_tokens=16 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 2.5 medium: 16K thinking budget, balanced reasoning."""

GEMINI_THINKING_BUDGET_LOW: dict[str, Any] = _gemini_thinking_budget_settings(
    thinking_budget=4 * K_TOKENS,
    max_tokens=8 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 2.5 low: 4K thinking budget, minimal reasoning overhead."""


# =============================================================================
# Gemini thinking_level Presets (for Gemini 3)
# =============================================================================


def _gemini_thinking_level_settings(
    thinking_level: Literal["HIGH", "MEDIUM", "LOW", "MINIMAL"],
    max_tokens: int | None = None,
    include_thoughts: bool = False,
) -> dict[str, Any]:
    """Create Gemini model settings with thinking_level only (for Gemini 3).

    Args:
        thinking_level: Thinking level ('HIGH', 'MEDIUM', 'LOW', 'MINIMAL').
        max_tokens: Maximum output tokens.
        include_thoughts: Whether to include thinking in response.

    Returns:
        Dict suitable for GoogleModelSettings.
    """
    settings: dict[str, Any] = {
        "google_thinking_config": {
            "thinking_level": thinking_level,
            "include_thoughts": include_thoughts,
        },
    }
    if max_tokens is not None:
        settings["max_tokens"] = max_tokens
    return settings


GEMINI_THINKING_LEVEL_DEFAULT: dict[str, Any] = _gemini_thinking_level_settings(
    thinking_level="LOW",
    max_tokens=16 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 3 default: MEDIUM thinking level, balanced reasoning."""

GEMINI_THINKING_LEVEL_HIGH: dict[str, Any] = _gemini_thinking_level_settings(
    thinking_level="HIGH",
    max_tokens=21 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 3 high: HIGH thinking level, maximum reasoning depth."""

GEMINI_THINKING_LEVEL_MEDIUM: dict[str, Any] = _gemini_thinking_level_settings(
    thinking_level="MEDIUM",
    max_tokens=16 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 3 medium: MEDIUM thinking level, balanced reasoning."""

GEMINI_THINKING_LEVEL_LOW: dict[str, Any] = _gemini_thinking_level_settings(
    thinking_level="LOW",
    max_tokens=8 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 3 low: LOW thinking level, minimal reasoning overhead."""

GEMINI_THINKING_LEVEL_MINIMAL: dict[str, Any] = _gemini_thinking_level_settings(
    thinking_level="MINIMAL",
    max_tokens=4 * K_TOKENS,
    include_thoughts=False,
)
"""Gemini 3 minimal: MINIMAL thinking level (Flash only, may still think for complex tasks)."""


# =============================================================================
# Preset Registry
# =============================================================================

_PRESET_REGISTRY: dict[str, dict[str, Any]] = {
    # Anthropic standard (no beta headers)
    ModelSettingsPreset.ANTHROPIC_DEFAULT.value: ANTHROPIC_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_HIGH.value: ANTHROPIC_HIGH,
    ModelSettingsPreset.ANTHROPIC_MEDIUM.value: ANTHROPIC_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_LOW.value: ANTHROPIC_LOW,
    ModelSettingsPreset.ANTHROPIC_OFF.value: ANTHROPIC_OFF,
    # Anthropic adaptive thinking (Opus 4.6 / Sonnet 4.6)
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_DEFAULT.value: ANTHROPIC_ADAPTIVE_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_HIGH.value: ANTHROPIC_ADAPTIVE_HIGH,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_MEDIUM.value: ANTHROPIC_ADAPTIVE_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_LOW.value: ANTHROPIC_ADAPTIVE_LOW,
    # Anthropic adaptive + 1M context
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_DEFAULT.value: ANTHROPIC_ADAPTIVE_1M_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_HIGH.value: ANTHROPIC_ADAPTIVE_1M_HIGH,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_MEDIUM.value: ANTHROPIC_ADAPTIVE_1M_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_LOW.value: ANTHROPIC_ADAPTIVE_1M_LOW,
    # Anthropic adaptive + context management
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_CM_DEFAULT.value: ANTHROPIC_ADAPTIVE_CM_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_CM_HIGH.value: ANTHROPIC_ADAPTIVE_CM_HIGH,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_CM_MEDIUM.value: ANTHROPIC_ADAPTIVE_CM_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_CM_LOW.value: ANTHROPIC_ADAPTIVE_CM_LOW,
    # Anthropic adaptive + 1M context + context management
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_CM_DEFAULT.value: ANTHROPIC_ADAPTIVE_1M_CM_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_CM_HIGH.value: ANTHROPIC_ADAPTIVE_1M_CM_HIGH,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_CM_MEDIUM.value: ANTHROPIC_ADAPTIVE_1M_CM_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_CM_LOW.value: ANTHROPIC_ADAPTIVE_1M_CM_LOW,
    # Anthropic interleaved thinking (with beta headers)
    ModelSettingsPreset.ANTHROPIC_DEFAULT_INTERLEAVED_THINKING.value: ANTHROPIC_DEFAULT_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_HIGH_INTERLEAVED_THINKING.value: ANTHROPIC_HIGH_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_MEDIUM_INTERLEAVED_THINKING.value: ANTHROPIC_MEDIUM_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_LOW_INTERLEAVED_THINKING.value: ANTHROPIC_LOW_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_OFF_INTERLEAVED_THINKING.value: ANTHROPIC_OFF_INTERLEAVED_THINKING,
    # Anthropic 1M context (with beta headers)
    ModelSettingsPreset.ANTHROPIC_1M_DEFAULT.value: ANTHROPIC_1M_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_1M_HIGH.value: ANTHROPIC_1M_HIGH,
    ModelSettingsPreset.ANTHROPIC_1M_MEDIUM.value: ANTHROPIC_1M_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_1M_LOW.value: ANTHROPIC_1M_LOW,
    ModelSettingsPreset.ANTHROPIC_1M_OFF.value: ANTHROPIC_1M_OFF,
    # Anthropic 1M context + interleaved thinking (with beta headers)
    ModelSettingsPreset.ANTHROPIC_1M_DEFAULT_INTERLEAVED_THINKING.value: ANTHROPIC_1M_DEFAULT_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_HIGH_INTERLEAVED_THINKING.value: ANTHROPIC_1M_HIGH_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_MEDIUM_INTERLEAVED_THINKING.value: ANTHROPIC_1M_MEDIUM_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_LOW_INTERLEAVED_THINKING.value: ANTHROPIC_1M_LOW_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_OFF_INTERLEAVED_THINKING.value: ANTHROPIC_1M_OFF_INTERLEAVED_THINKING,
    # Anthropic context management
    ModelSettingsPreset.ANTHROPIC_CM_DEFAULT.value: ANTHROPIC_CM_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_CM_HIGH.value: ANTHROPIC_CM_HIGH,
    ModelSettingsPreset.ANTHROPIC_CM_MEDIUM.value: ANTHROPIC_CM_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_CM_LOW.value: ANTHROPIC_CM_LOW,
    ModelSettingsPreset.ANTHROPIC_CM_OFF.value: ANTHROPIC_CM_OFF,
    # Anthropic 1M context + context management
    ModelSettingsPreset.ANTHROPIC_1M_CM_DEFAULT.value: ANTHROPIC_1M_CM_DEFAULT,
    ModelSettingsPreset.ANTHROPIC_1M_CM_HIGH.value: ANTHROPIC_1M_CM_HIGH,
    ModelSettingsPreset.ANTHROPIC_1M_CM_MEDIUM.value: ANTHROPIC_1M_CM_MEDIUM,
    ModelSettingsPreset.ANTHROPIC_1M_CM_LOW.value: ANTHROPIC_1M_CM_LOW,
    ModelSettingsPreset.ANTHROPIC_1M_CM_OFF.value: ANTHROPIC_1M_CM_OFF,
    # Anthropic context management + interleaved thinking
    ModelSettingsPreset.ANTHROPIC_CM_DEFAULT_INTERLEAVED_THINKING.value: ANTHROPIC_CM_DEFAULT_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_CM_HIGH_INTERLEAVED_THINKING.value: ANTHROPIC_CM_HIGH_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_CM_MEDIUM_INTERLEAVED_THINKING.value: ANTHROPIC_CM_MEDIUM_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_CM_LOW_INTERLEAVED_THINKING.value: ANTHROPIC_CM_LOW_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_CM_OFF_INTERLEAVED_THINKING.value: ANTHROPIC_CM_OFF_INTERLEAVED_THINKING,
    # Anthropic 1M context + context management + interleaved thinking
    ModelSettingsPreset.ANTHROPIC_1M_CM_DEFAULT_INTERLEAVED_THINKING.value: ANTHROPIC_1M_CM_DEFAULT_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_CM_HIGH_INTERLEAVED_THINKING.value: ANTHROPIC_1M_CM_HIGH_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_CM_MEDIUM_INTERLEAVED_THINKING.value: ANTHROPIC_1M_CM_MEDIUM_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_CM_LOW_INTERLEAVED_THINKING.value: ANTHROPIC_1M_CM_LOW_INTERLEAVED_THINKING,
    ModelSettingsPreset.ANTHROPIC_1M_CM_OFF_INTERLEAVED_THINKING.value: ANTHROPIC_1M_CM_OFF_INTERLEAVED_THINKING,
    # OpenAI Chat
    ModelSettingsPreset.OPENAI_DEFAULT.value: OPENAI_DEFAULT,
    ModelSettingsPreset.OPENAI_HIGH.value: OPENAI_HIGH,
    ModelSettingsPreset.OPENAI_MEDIUM.value: OPENAI_MEDIUM,
    ModelSettingsPreset.OPENAI_LOW.value: OPENAI_LOW,
    # OpenAI Responses
    ModelSettingsPreset.OPENAI_RESPONSES_DEFAULT.value: OPENAI_RESPONSES_DEFAULT,
    ModelSettingsPreset.OPENAI_RESPONSES_HIGH.value: OPENAI_RESPONSES_HIGH,
    ModelSettingsPreset.OPENAI_RESPONSES_MEDIUM.value: OPENAI_RESPONSES_MEDIUM,
    ModelSettingsPreset.OPENAI_RESPONSES_LOW.value: OPENAI_RESPONSES_LOW,
    # Gemini thinking_budget (for Gemini 2.5)
    ModelSettingsPreset.GEMINI_THINKING_BUDGET_DEFAULT.value: GEMINI_THINKING_BUDGET_DEFAULT,
    ModelSettingsPreset.GEMINI_THINKING_BUDGET_HIGH.value: GEMINI_THINKING_BUDGET_HIGH,
    ModelSettingsPreset.GEMINI_THINKING_BUDGET_MEDIUM.value: GEMINI_THINKING_BUDGET_MEDIUM,
    ModelSettingsPreset.GEMINI_THINKING_BUDGET_LOW.value: GEMINI_THINKING_BUDGET_LOW,
    # Gemini thinking_level (for Gemini 3)
    ModelSettingsPreset.GEMINI_THINKING_LEVEL_DEFAULT.value: GEMINI_THINKING_LEVEL_DEFAULT,
    ModelSettingsPreset.GEMINI_THINKING_LEVEL_HIGH.value: GEMINI_THINKING_LEVEL_HIGH,
    ModelSettingsPreset.GEMINI_THINKING_LEVEL_MEDIUM.value: GEMINI_THINKING_LEVEL_MEDIUM,
    ModelSettingsPreset.GEMINI_THINKING_LEVEL_LOW.value: GEMINI_THINKING_LEVEL_LOW,
    ModelSettingsPreset.GEMINI_THINKING_LEVEL_MINIMAL.value: GEMINI_THINKING_LEVEL_MINIMAL,
}

# Short aliases for convenience
_PRESET_ALIASES: dict[str, str] = {
    # Provider defaults (default preset)
    "anthropic": ModelSettingsPreset.ANTHROPIC_DEFAULT.value,
    "anthropic_adaptive": ModelSettingsPreset.ANTHROPIC_ADAPTIVE_DEFAULT.value,
    "anthropic_adaptive_1m": ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_DEFAULT.value,
    "anthropic_adaptive_cm": ModelSettingsPreset.ANTHROPIC_ADAPTIVE_CM_DEFAULT.value,
    "anthropic_adaptive_1m_cm": ModelSettingsPreset.ANTHROPIC_ADAPTIVE_1M_CM_DEFAULT.value,
    "anthropic_interleaved": ModelSettingsPreset.ANTHROPIC_DEFAULT_INTERLEAVED_THINKING.value,
    "anthropic_1m": ModelSettingsPreset.ANTHROPIC_1M_DEFAULT.value,
    "anthropic_1m_interleaved": ModelSettingsPreset.ANTHROPIC_1M_DEFAULT_INTERLEAVED_THINKING.value,
    "anthropic_cm": ModelSettingsPreset.ANTHROPIC_CM_DEFAULT.value,
    "anthropic_1m_cm": ModelSettingsPreset.ANTHROPIC_1M_CM_DEFAULT.value,
    "anthropic_cm_interleaved": ModelSettingsPreset.ANTHROPIC_CM_DEFAULT_INTERLEAVED_THINKING.value,
    "anthropic_1m_cm_interleaved": ModelSettingsPreset.ANTHROPIC_1M_CM_DEFAULT_INTERLEAVED_THINKING.value,
    "openai": ModelSettingsPreset.OPENAI_DEFAULT.value,
    "openai_responses": ModelSettingsPreset.OPENAI_RESPONSES_DEFAULT.value,
    "gemini_2.5": ModelSettingsPreset.GEMINI_THINKING_BUDGET_DEFAULT.value,
    "gemini_3": ModelSettingsPreset.GEMINI_THINKING_LEVEL_DEFAULT.value,
    "gemini": ModelSettingsPreset.GEMINI_THINKING_LEVEL_DEFAULT.value,  # Default to Gemini 3
    # Generic level aliases (default to anthropic)
    "high": ModelSettingsPreset.ANTHROPIC_HIGH.value,
    "medium": ModelSettingsPreset.ANTHROPIC_MEDIUM.value,
    "low": ModelSettingsPreset.ANTHROPIC_LOW.value,
}


# =============================================================================
# Public API
# =============================================================================


def get_model_settings(preset: str | ModelSettingsPreset) -> dict[str, Any]:
    """Get ModelSettings by preset name.

    Args:
        preset: Preset name (string) or ModelSettingsPreset enum.

    Returns:
        ModelSettings dict for the specified preset.

    Raises:
        ValueError: If preset name is not found.

    Example::

        # By string name
        settings = get_model_settings("anthropic_high")

        # By enum
        settings = get_model_settings(ModelSettingsPreset.GEMINI_MEDIUM)

        # By alias
        settings = get_model_settings("anthropic")  # -> anthropic_medium
    """
    name = preset.value if isinstance(preset, ModelSettingsPreset) else preset

    # Check aliases first
    if name in _PRESET_ALIASES:
        name = _PRESET_ALIASES[name]

    if name not in _PRESET_REGISTRY:
        available = list(_PRESET_REGISTRY.keys()) + list(_PRESET_ALIASES.keys())
        msg = f"Unknown preset: {preset!r}. Available: {sorted(available)}"
        raise ValueError(msg)

    return _PRESET_REGISTRY[name]


def resolve_model_settings(
    preset_or_dict: ModelSettings | str | dict[str, Any] | ModelSettingsPreset | None,
) -> dict[str, Any] | None:
    """Resolve a preset name or dict to ModelSettings.

    This is the main entry point for resolving model settings from various formats:
    - None -> None (use model defaults)
    - str -> lookup preset by name
    - ModelSettingsPreset -> lookup preset by enum
    - dict -> return as-is (assumed to be valid ModelSettings)
    - ModelSettings -> convert to dict using model_dump()

    Args:
        preset_or_dict: Preset name, enum, dict, ModelSettings, or None.

    Returns:
        ModelSettings dict or None.

    Example::

        # From YAML config
        config_value = "anthropic_high"
        settings = resolve_model_settings(config_value)

        # From dict in YAML
        config_value = {"temperature": 0.5, "max_tokens": 4096}
        settings = resolve_model_settings(config_value)
    """
    if preset_or_dict is None:
        return None
    if isinstance(preset_or_dict, str):
        return get_model_settings(preset_or_dict)
    if isinstance(preset_or_dict, ModelSettingsPreset):
        return get_model_settings(preset_or_dict)
    # ModelSettings is a TypedDict (subclass of dict), return as-is
    return dict(preset_or_dict)


def list_presets() -> list[str]:
    """List all available preset names.

    Returns:
        List of preset names (including aliases).
    """
    return sorted(set(_PRESET_REGISTRY.keys()) | set(_PRESET_ALIASES.keys()))


# =============================================================================
# ModelConfig Presets
# =============================================================================

# Special value indicating inheritance from parent
INHERIT = "inherit"


class ModelConfigPreset(StrEnum):
    """Available ModelConfig presets for context management."""

    # Anthropic models
    CLAUDE_200K = "claude_200k"
    CLAUDE_1M = "claude_1m"

    # OpenAI models (GPT-5 series with 270k context)
    GPT5_270K = "gpt5_270k"

    # Gemini models
    GEMINI_200K = "gemini_200k"
    GEMINI_1M = "gemini_1m"


# ModelConfig preset registry
_MODEL_CFG_REGISTRY: dict[str, dict[str, Any]] = {
    # Anthropic Claude models (vision, no video support)
    ModelConfigPreset.CLAUDE_200K.value: {
        "context_window": 200_000,
        "max_images": 20,
        "max_videos": 0,  # Claude doesn't support video
        "support_gif": True,
        "split_large_images": True,
        "image_split_max_height": 4096,
        "image_split_overlap": 50,
        "capabilities": {ModelCapability.vision, ModelCapability.document_understanding},
    },
    ModelConfigPreset.CLAUDE_1M.value: {
        "context_window": 1_000_000,
        "max_images": 20,
        "max_videos": 0,  # Claude doesn't support video
        "support_gif": True,
        "split_large_images": True,
        "image_split_max_height": 4096,
        "image_split_overlap": 50,
        "capabilities": {ModelCapability.vision, ModelCapability.document_understanding},
    },
    # OpenAI GPT-5 series (vision, no video support)
    ModelConfigPreset.GPT5_270K.value: {
        "context_window": 270_000,
        "max_images": 20,
        "max_videos": 0,  # GPT doesn't support video
        "support_gif": False,
        "split_large_images": True,
        "image_split_max_height": 4096,
        "image_split_overlap": 50,
        "capabilities": {ModelCapability.vision},
    },
    # Gemini models (vision + video support)
    ModelConfigPreset.GEMINI_200K.value: {
        "context_window": 200_000,
        "max_images": 20,
        "max_videos": 1,  # Gemini supports video
        "support_gif": True,
        "split_large_images": True,
        "image_split_max_height": 4096,
        "image_split_overlap": 50,
        "capabilities": {
            ModelCapability.vision,
            ModelCapability.video_understanding,
            ModelCapability.audio_understanding,
            ModelCapability.document_understanding,
        },
    },
    ModelConfigPreset.GEMINI_1M.value: {
        "context_window": 1_000_000,
        "max_images": 20,
        "max_videos": 1,  # Gemini supports video
        "support_gif": True,
        "split_large_images": True,
        "image_split_max_height": 4096,
        "image_split_overlap": 50,
        "capabilities": {
            ModelCapability.vision,
            ModelCapability.video_understanding,
            ModelCapability.audio_understanding,
            ModelCapability.document_understanding,
        },
    },
}

# ModelConfig aliases
_MODEL_CFG_ALIASES: dict[str, str] = {
    "claude": ModelConfigPreset.CLAUDE_1M.value,
    "anthropic": ModelConfigPreset.CLAUDE_1M.value,
    "gpt5": ModelConfigPreset.GPT5_270K.value,
    "openai": ModelConfigPreset.GPT5_270K.value,
    "gemini": ModelConfigPreset.GEMINI_200K.value,
}


def get_model_cfg(preset: str | ModelConfigPreset) -> dict[str, Any]:
    """Get ModelConfig by preset name.

    Args:
        preset: Preset name (string) or ModelConfigPreset enum.

    Returns:
        Dict suitable for ModelConfig constructor.

    Raises:
        ValueError: If preset name is not found.

    Example::

        # By string name
        cfg = get_model_cfg("claude_200k")

        # By enum
        cfg = get_model_cfg(ModelConfigPreset.GEMINI_1M)

        # By alias
        cfg = get_model_cfg("claude")  # -> claude_1m
    """
    name = preset.value if isinstance(preset, ModelConfigPreset) else preset

    # Check aliases first
    if name in _MODEL_CFG_ALIASES:
        name = _MODEL_CFG_ALIASES[name]

    if name not in _MODEL_CFG_REGISTRY:
        available = list(_MODEL_CFG_REGISTRY.keys()) + list(_MODEL_CFG_ALIASES.keys())
        msg = f"Unknown ModelConfig preset: {preset!r}. Available: {sorted(available)}"
        raise ValueError(msg)

    return _MODEL_CFG_REGISTRY[name].copy()


def resolve_model_cfg(
    preset_or_dict: str | dict[str, Any] | ModelConfigPreset | None,
) -> dict[str, Any] | None:
    """Resolve a preset name or dict to ModelConfig dict.

    This is the main entry point for resolving ModelConfig from various formats:
    - None -> None (inherit from parent)
    - "inherit" -> None (explicit inherit)
    - str -> lookup preset by name
    - ModelConfigPreset -> lookup preset by enum
    - dict -> return as-is (assumed to be valid ModelConfig kwargs)

    Args:
        preset_or_dict: Preset name, enum, dict, or None.

    Returns:
        Dict suitable for ModelConfig constructor, or None for inherit.

    Example::

        # Inherit from parent (default)
        cfg = resolve_model_cfg(None)  # -> None
        cfg = resolve_model_cfg("inherit")  # -> None

        # From preset name
        cfg = resolve_model_cfg("claude_200k")

        # From dict
        cfg = resolve_model_cfg({"context_window": 100000, "max_images": 10})
    """
    if preset_or_dict is None:
        return None
    if isinstance(preset_or_dict, str):
        if preset_or_dict == INHERIT:
            return None
        return get_model_cfg(preset_or_dict)
    if isinstance(preset_or_dict, ModelConfigPreset):
        return get_model_cfg(preset_or_dict)
    # dict - return as-is
    return dict(preset_or_dict)


def list_model_cfg_presets() -> list[str]:
    """List all available ModelConfig preset names.

    Returns:
        List of preset names (including aliases).
    """
    return sorted(set(_MODEL_CFG_REGISTRY.keys()) | set(_MODEL_CFG_ALIASES.keys()))
