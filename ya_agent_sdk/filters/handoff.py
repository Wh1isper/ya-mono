"""Handoff message history processor.

This module provides a history processor that injects handoff summaries
into the message history when a context reset occurs.

Uses a virtual tool call pattern so the model understands handoff as a tool
operation result, avoiding confusion when users mention "handoff" in conversation.

Note:
    This processor must be used together with `ya_agent_sdk.toolsets.context.handoff.HandoffTool`.
    See HandoffTool for usage example.
"""

from collections.abc import Sequence
from uuid import uuid4

from pydantic_ai import UserContent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.tools import RunContext

from ya_agent_sdk._logger import get_logger
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.events import (
    HandoffCompleteEvent,
    HandoffFailedEvent,
    HandoffStartEvent,
)

logger = get_logger(__name__)


def _build_handoff_messages(
    summary: str,
    original_prompt: str | Sequence[UserContent] | None = None,
    steering_messages: list[str] | None = None,
    tool_call_id: str = "handoff-ack",
) -> list[ModelMessage]:
    """Build compacted message history after handoff.

    Uses a virtual tool call pattern:
    1. Request with system prompt + original user prompt
    2. Response with virtual summarize tool call
    3. Request with summarize tool return (summary) + steering + summary-complete marker

    This structure makes it clear to the model that the summary is a tool
    result, not the model's own output, avoiding confusion when users mention "handoff".

    Args:
        summary: The handoff summary content.
        original_prompt: The initial user prompt from the session.
        steering_messages: Additional steering messages from user during execution.
        tool_call_id: Tool call ID for the virtual handoff call.

    Returns:
        List of ModelMessage representing the compacted history.
    """
    # Message 1: system + labeled original user prompt
    # Placeholder will be replaced by create_system_prompt_filter downstream
    request_parts: list[SystemPromptPart | UserPromptPart] = [
        SystemPromptPart(content="Placeholder system prompt"),
    ]
    if original_prompt is not None:
        request_parts.append(
            UserPromptPart(
                content="<original-request>Below is the user's original request from the start of the conversation:</original-request>"
            )
        )
        request_parts.append(UserPromptPart(content=original_prompt))

    # Message 2: virtual handoff tool call
    tool_call = ToolCallPart(
        tool_name="summarize",
        args={"content": "[summary injected as tool return]"},
        tool_call_id=tool_call_id,
    )

    # Message 3: summarize tool return + steering + summary-complete
    final_parts: list[ToolReturnPart | UserPromptPart] = [
        ToolReturnPart(
            tool_name="summarize",
            content=summary,
            tool_call_id=tool_call_id,
        ),
    ]

    if steering_messages:
        final_parts.append(
            UserPromptPart(
                content="<user-steering>Below are messages the user sent during your previous work session:</user-steering>"
            )
        )
        for steering in steering_messages:
            final_parts.append(UserPromptPart(content=f"[User Steering] {steering}"))

    final_parts.append(
        UserPromptPart(
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
    )

    return [
        ModelRequest(parts=request_parts),
        ModelResponse(parts=[tool_call]),
        ModelRequest(parts=final_parts),
    ]


async def process_handoff_message(
    ctx: RunContext[AgentContext],
    message_history: list[ModelMessage],
) -> list[ModelMessage]:
    """Inject handoff summary into message history after context reset.

    This is a pydantic-ai history_processor that can be passed to Agent's
    history_processors parameter. When a handoff occurs, the previous context
    is cleared but a summary message is preserved in ctx.deps.handoff_message.

    Uses a virtual tool call pattern:
    1. Request with system prompt + original user prompt
    2. Response with virtual summarize tool call
    3. Request with summarize tool return (summary) + steering + summary-complete marker

    This ensures the model understands the summary as a tool result,
    and downstream filters like auto_load_files can append to the last request.

    Note: Subagents created via enter_subagent() have handoff_message cleared,
    so they won't be affected by the main agent's handoff state.

    Args:
        ctx: Runtime context containing AgentContext with handoff_message.
        message_history: Current message history to process.

    Returns:
        Processed message history with handoff summary injected, or unchanged
        history if no handoff is pending.

    Example:
        agent = Agent(
            'openai:gpt-4',
            deps_type=AgentContext,
            history_processors=[process_handoff_message],
        )
    """
    agent_ctx = ctx.deps

    # Reset force flag at the start of each filter pipeline pass
    agent_ctx.force_inject_instructions = False

    if not agent_ctx.handoff_message:
        return message_history

    # Generate event_id to correlate start/complete events
    event_id = uuid4().hex[:8]
    original_message_count = len(message_history)

    try:
        # Emit start event
        await agent_ctx.emit_event(HandoffStartEvent(event_id=event_id, message_count=original_message_count))

        handoff_content = agent_ctx.handoff_message

        # Virtual tool call ID for the handoff acknowledgment
        virtual_tool_call_id = f"handoff-ack-{event_id}"

        # Build compacted messages using virtual tool call pattern
        result = _build_handoff_messages(
            handoff_content,
            agent_ctx.user_prompts,
            agent_ctx.steering_messages or None,
            tool_call_id=virtual_tool_call_id,
        )

        if agent_ctx.steering_messages:
            logger.debug("Including %d steering messages in handoff", len(agent_ctx.steering_messages))

        # Clear handoff state
        agent_ctx.handoff_message = None
        # Clear steering_messages after successful handoff (content is now in summary)
        agent_ctx.steering_messages.clear()

        # Force downstream filters to inject instructions despite ToolReturnPart
        agent_ctx.force_inject_instructions = True

        # Emit complete event with the actual handoff content
        await agent_ctx.emit_event(
            HandoffCompleteEvent(
                event_id=event_id,
                handoff_content=handoff_content,
                original_message_count=original_message_count,
            )
        )

        return result

    except Exception as e:
        # Emit failed event so consumers know handoff did not succeed
        await agent_ctx.emit_event(
            HandoffFailedEvent(event_id=event_id, error=str(e), message_count=original_message_count)
        )
        # On error, return original history
        return message_history
