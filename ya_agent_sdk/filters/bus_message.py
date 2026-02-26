"""Bus message injection filter.

This filter injects pending bus messages into the conversation
at the start of each LLM request, enabling real-time communication
between user and agents, or between agents.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from html import escape

from pydantic_ai import RunContext, UserContent
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.context.bus import BusMessage, content_as_text
from ya_agent_sdk.events import BusMessageInfo, MessageReceivedEvent


def _build_user_prompt_part(msg: BusMessage, rendered: str | Sequence[UserContent]) -> UserPromptPart:
    """Build a UserPromptPart from a bus message and its rendered content.

    For str content: wraps in XML-style bus-message tags as a single string.
    For multimodal content: creates a sequence with text header, content items, and text footer.

    Args:
        msg: The original bus message.
        rendered: The rendered content (str or multimodal sequence).

    Returns:
        A UserPromptPart ready for injection into the conversation.
    """
    header = f'<bus-message source="{escape(msg.source)}">'
    footer = "</bus-message>"

    if isinstance(rendered, str):
        return UserPromptPart(content=f"{header}\n{rendered}\n{footer}")

    # Multimodal: build a sequence with text bookends
    parts: list[UserContent] = [header]
    parts.extend(rendered)
    parts.append(footer)
    return UserPromptPart(content=parts)


async def inject_bus_messages(
    ctx: RunContext[AgentContext],
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Inject pending bus messages into the conversation.

    This filter consumes pending messages from the message bus
    and injects them as user prompt parts into the last ModelRequest.

    Supports both text (str) and multimodal (Sequence[UserContent]) content.
    Text messages are wrapped in XML tags; multimodal messages are injected
    as UserPromptPart with a mixed sequence of text headers and media parts.

    Idempotency:
        Uses ctx.deps.consume_messages() which tracks consumed message IDs.
        Even if this filter runs multiple times (e.g., on LLM retry),
        each message is only injected once.

    Injection:
        Messages are rendered using their template and appended
        to the last ModelRequest's parts list.

    Filter Order:
        This filter should run BEFORE inject_runtime_instructions
        to ensure messages are visible before runtime context.

    Args:
        ctx: Run context containing AgentContext.
        messages: Current message history.

    Returns:
        Modified message history with injected bus messages.
    """
    if not messages or not isinstance(messages[-1], ModelRequest):
        return messages

    # Consume messages idempotently (each message only returned once)
    pending = ctx.deps.consume_messages()

    if not pending:
        return messages

    # Pre-render messages once for both injection and event
    rendered_messages = [(msg, msg.render()) for msg in pending]

    # Accumulate user steering messages for compact (text representation only)
    for msg, rendered in rendered_messages:
        if msg.source == "user":
            if isinstance(rendered, str):
                ctx.deps.steering_messages.append(rendered)
            else:
                # For multimodal content, accumulate the text representation
                text = content_as_text(rendered)
                if text:
                    ctx.deps.steering_messages.append(text)

    # Build UserPromptParts for each message
    parts = [_build_user_prompt_part(msg, rendered) for msg, rendered in rendered_messages]

    # Emit single event with all messages
    event = MessageReceivedEvent(
        event_id=f"bus-recv-{uuid.uuid4().hex[:8]}",
        messages=[
            BusMessageInfo(
                content=msg.content,
                rendered_content=rendered,
                source=msg.source,
                target=msg.target,
                content_text=msg.content_text(),
            )
            for msg, rendered in rendered_messages
        ],
    )
    await ctx.deps.emit_event(event)

    # Inject into last message's parts
    messages[-1].parts = [*messages[-1].parts, *parts]

    return messages
