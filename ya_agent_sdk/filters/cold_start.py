"""Cold start trim filter for message history.

When resuming a session after a long gap (e.g., > 1 hour), the provider's KV
cache is likely expired and the full message history must be re-encoded from
scratch.  Truncating large tool return content before sending reduces input
token cost significantly, since the model already analyzed these results in
previous turns and its own reasoning is preserved in ModelResponse parts.

This filter is cheap (pure string truncation, zero LLM calls) and should run
before the compact filter so that the reduced token count may even prevent
compact from triggering.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolReturnPart,
)

from ya_agent_sdk._logger import get_logger
from ya_agent_sdk.context import AgentContext

logger = get_logger(__name__)

# Maximum characters to keep in a single tool return content
_MAX_TOOL_RETURN_CHARS = 500
# Characters to keep from the beginning and end when truncating
_TOOL_RETURN_KEEP_HEAD = 200
_TOOL_RETURN_KEEP_TAIL = 200


def _truncate_tool_content(content: str) -> str:
    """Truncate a string, keeping head and tail portions."""
    if len(content) <= _MAX_TOOL_RETURN_CHARS:
        return content

    head = content[:_TOOL_RETURN_KEEP_HEAD]
    tail = content[-_TOOL_RETURN_KEEP_TAIL:]
    truncated_count = len(content) - _TOOL_RETURN_KEEP_HEAD - _TOOL_RETURN_KEEP_TAIL
    return f"{head}\n[... {truncated_count} chars truncated ...]\n{tail}"


def _get_last_response_timestamp(message_history: list[ModelMessage]) -> datetime | None:
    """Get the timestamp of the last ModelResponse in the history."""
    for msg in reversed(message_history):
        if isinstance(msg, ModelResponse):
            return msg.timestamp
    return None


def _get_idle_seconds(message_history: list[ModelMessage]) -> float | None:
    """Return seconds since the last model response, or None if unavailable."""
    last_ts = _get_last_response_timestamp(message_history)
    if last_ts is None:
        return None
    now = datetime.now() if last_ts.tzinfo is None else datetime.now(tz=last_ts.tzinfo)
    return (now - last_ts).total_seconds()


def _trim_tool_returns(message_history: list[ModelMessage]) -> int:
    """Truncate large ToolReturnPart content in-place. Returns count of trimmed parts."""
    trimmed_count = 0
    for idx, message in enumerate(message_history):
        if not isinstance(message, ModelRequest):
            continue

        new_parts = list(message.parts)
        parts_modified = False
        for i, part in enumerate(new_parts):
            if not isinstance(part, ToolReturnPart):
                continue
            content_str = part.model_response_str()
            if len(content_str) > _MAX_TOOL_RETURN_CHARS:
                new_parts[i] = replace(part, content=_truncate_tool_content(content_str))
                parts_modified = True
                trimmed_count += 1

        if parts_modified:
            message_history[idx] = replace(message, parts=new_parts)

    return trimmed_count


def cold_start_trim(
    ctx: RunContext[AgentContext],
    message_history: list[ModelMessage],
) -> list[ModelMessage]:
    """Trim tool results when KV cache is likely expired.

    When the gap between the last model response and now exceeds the
    configured threshold (``cold_start_trim_seconds``), truncate all
    ``ToolReturnPart`` content in the history to save input token cost
    on the cold re-encoding.

    After the first model response in the new session the gap naturally
    becomes very small, so this filter only fires on the first request
    after a cold start -- no extra bookkeeping needed.

    Args:
        ctx: Runtime context containing AgentContext.
        message_history: Current message history to potentially trim.

    Returns:
        The (possibly mutated) message history with large tool results truncated.
    """
    if not message_history:
        return message_history

    threshold = ctx.deps.model_cfg.cold_start_trim_seconds
    if not threshold or threshold <= 0:
        return message_history

    idle = _get_idle_seconds(message_history)
    if idle is None or idle < threshold:
        return message_history

    logger.info(
        "Cold start detected (gap=%.0fs > threshold=%ds), trimming tool results",
        idle,
        threshold,
    )

    trimmed_count = _trim_tool_returns(message_history)
    if trimmed_count > 0:
        logger.info("Trimmed %d tool return parts for cold start", trimmed_count)

    return message_history
