"""Shared message builders for compact and handoff filters.

Provides reusable building blocks for constructing compacted message histories.
Both compact and handoff flows produce messages with the same structural elements
(original-request, user-steering, context-restored), and this module centralizes
those patterns to avoid duplication.
"""

from collections.abc import Sequence

from pydantic_ai import UserContent
from pydantic_ai.messages import ModelMessage, UserPromptPart

# =============================================================================
# Keep Tag Constants
# =============================================================================

KEEP_TAG_KEY = "keep"
"""Metadata key used to mark messages that should survive trimming across compaction cycles."""

KEEP_COMPACT = "compact"
"""Keep tag value for messages produced by compact."""

KEEP_HANDOFF = "handoff"
"""Keep tag value for messages produced by handoff."""


# =============================================================================
# Shared Message Part Builders
# =============================================================================


def build_original_request_parts(
    original_prompt: str | Sequence[UserContent] | None,
) -> list[UserPromptPart]:
    """Build labeled original-request parts.

    Wraps the user's initial prompt with an XML label so the model
    knows this is the original request from the start of the conversation.

    Args:
        original_prompt: The initial user prompt. None to skip.

    Returns:
        List of UserPromptPart (empty if original_prompt is None).
    """
    if original_prompt is None:
        return []
    return [
        UserPromptPart(
            content="<original-request>Below is the user's original request from the start of the conversation:</original-request>"
        ),
        UserPromptPart(content=original_prompt),
    ]


def build_steering_parts(
    steering_messages: list[str] | None,
) -> list[UserPromptPart]:
    """Build user-steering parts.

    Wraps steering messages (sent by the user during the previous work session)
    with an XML label and individual message prefixes.

    Args:
        steering_messages: List of steering message strings. None or empty to skip.

    Returns:
        List of UserPromptPart (empty if no steering messages).
    """
    if not steering_messages:
        return []
    parts: list[UserPromptPart] = [
        UserPromptPart(
            content="<user-steering>Below are messages the user sent during your previous work session:</user-steering>"
        ),
    ]
    for steering in steering_messages:
        parts.append(UserPromptPart(content=f"[User Steering] {steering}"))
    return parts


def build_context_restored_part() -> UserPromptPart:
    """Build context-restored marker part.

    This marker tells the model that the context was compacted and provides
    instructions on how to synthesize the summary, original request, and
    steering messages to resume work.

    Returns:
        A single UserPromptPart with the context-restored marker.
    """
    return UserPromptPart(
        content=(
            "<context-restored>"
            "Context was compacted from a long conversation. "
            "The summary above is the most authoritative source for current state. "
            "Synthesize the summary, original request, and any user steering messages to resume work. "
            "Do NOT repeat questions, confirmations, or actions documented in the summary. "
            "If the summary records a user decision, respect it without re-asking."
            "</context-restored>"
        )
    )


def has_keep_tag(message: ModelMessage) -> bool:
    """Check if a message has a keep tag in its metadata.

    Messages tagged with keep metadata should be preserved during trimming
    to avoid losing prior session summaries across compaction cycles.

    Args:
        message: A ModelMessage (ModelRequest or ModelResponse).

    Returns:
        True if the message has a keep tag.
    """
    return bool(message.metadata and KEEP_TAG_KEY in message.metadata)
