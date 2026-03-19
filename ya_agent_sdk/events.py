"""Custom agent events for sideband streaming.

This module defines custom events that agents can emit via the sideband
stream channel (agent_stream_queues) to communicate status and results
to consumers without interrupting the main agent flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai import DeferredToolResults
    from pydantic_ai.messages import UserContent


@dataclass
class AgentEvent:
    """Base class for custom agent events (sideband channel).

    Attributes:
        event_id: Unique identifier to correlate related events (e.g., start/complete pairs).
        timestamp: When the event was created.
    """

    event_id: str
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# Compact Events
# =============================================================================


@dataclass
class CompactStartEvent(AgentEvent):
    """Emitted when context compaction starts.

    Attributes:
        message_count: Number of messages before compaction.
    """

    message_count: int = 0


@dataclass
class CompactCompleteEvent(AgentEvent):
    """Emitted when context compaction completes successfully.

    Attributes:
        summary_markdown: The compacted summary in markdown format.
        original_message_count: Number of messages before compaction.
        compacted_message_count: Number of messages after compaction.
    """

    summary_markdown: str = ""
    original_message_count: int = 0
    compacted_message_count: int = 0


@dataclass
class CompactFailedEvent(AgentEvent):
    """Emitted when context compaction fails.

    Attributes:
        error: Error message describing the failure.
        message_count: Number of messages that were attempted to compact.
    """

    error: str = ""
    message_count: int = 0


# =============================================================================
# Handoff Events
# =============================================================================


@dataclass
class HandoffStartEvent(AgentEvent):
    """Emitted when context handoff starts.

    Attributes:
        message_count: Number of messages before handoff.
    """

    message_count: int = 0


@dataclass
class HandoffCompleteEvent(AgentEvent):
    """Emitted when context handoff completes successfully.

    Attributes:
        handoff_content: The actual handoff content/summary being passed to next context.
        original_message_count: Number of messages before handoff.
    """

    handoff_content: str = ""
    original_message_count: int = 0


@dataclass
class HandoffFailedEvent(AgentEvent):
    """Emitted when context handoff fails.

    Attributes:
        error: Error message describing the failure.
        message_count: Number of messages at failure time.
    """

    error: str = ""
    message_count: int = 0


# =============================================================================
# Subagent Lifecycle Events
# =============================================================================


@dataclass
class SubagentStartEvent(AgentEvent):
    """Emitted when a subagent starts execution.

    This event is emitted by the delegate tool when a subagent begins processing.
    Consumers can use this to display a progress indicator for the subagent.

    Attributes:
        agent_id: Unique identifier for this subagent instance (e.g., "explorer-a7b9").
        agent_name: Human-readable subagent name (e.g., "explorer").
        prompt_preview: First N characters of the prompt sent to subagent.
    """

    agent_id: str = ""
    agent_name: str = ""
    prompt_preview: str = ""


@dataclass
class SubagentCompleteEvent(AgentEvent):
    """Emitted when a subagent completes execution.

    This event is emitted by the delegate tool when a subagent finishes,
    regardless of success or failure. Consumers can use this to update
    the progress indicator to show completion status.

    Attributes:
        agent_id: Unique identifier for this subagent instance.
        agent_name: Human-readable subagent name.
        success: Whether the subagent completed successfully.
        request_count: Number of LLM requests the subagent made during execution.
        result_preview: First N characters of the subagent's output.
        error: Error message if success is False.
        duration_seconds: How long the subagent ran.
    """

    agent_id: str = ""
    agent_name: str = ""
    success: bool = True
    request_count: int = 0
    result_preview: str = ""
    error: str = ""
    duration_seconds: float = 0.0


# =============================================================================
# Message Bus Events
# =============================================================================


@dataclass
class BusMessageInfo:
    """Info about a single bus message.

    Attributes:
        content: Original message content (before template rendering).
            Can be str for text or Sequence[UserContent] for multimodal.
        rendered_content: Rendered message content (template already applied).
            Can be str for text or Sequence[UserContent] for multimodal.
        source: Who sent the message (e.g., "user", agent_id).
        target: Who should receive the message (agent_id, or None for broadcast).
        content_text: Text-only representation of the content for display/logging.
    """

    content: str | Sequence[UserContent]
    rendered_content: str | Sequence[UserContent]
    source: str
    target: str | None = None
    content_text: str = ""


@dataclass
class MessageReceivedEvent(AgentEvent):
    """Emitted when bus messages are received and injected into conversation.

    This event is emitted by the bus_message filter when pending messages
    are consumed and injected. Consumers can use this to display
    incoming messages in the UI.

    Attributes:
        messages: List of received message info.
    """

    messages: list[BusMessageInfo] = field(default_factory=list)


# =============================================================================
# Agent Lifecycle Events
# =============================================================================


@dataclass
class AgentExecutionStartEvent(AgentEvent):
    """Emitted when agent execution begins (before first node).

    This event marks the start of an agent run. Use it for:
    - Initializing progress indicators
    - Starting execution timers
    - Logging agent invocations

    Attributes:
        user_prompt: The user prompt passed to the agent (str or multimodal content).
        deferred_tool_results: Results from deferred tool calls, if any.
        message_history_count: Number of messages in provided history.
    """

    user_prompt: str | Sequence[UserContent] | None = None
    deferred_tool_results: DeferredToolResults | None = None
    message_history_count: int = 0


@dataclass
class AgentExecutionCompleteEvent(AgentEvent):
    """Emitted when agent execution completes successfully.

    This event marks successful completion of an agent run. Use it for:
    - Finalizing progress indicators
    - Recording execution metrics
    - Logging completion status

    Attributes:
        total_loops: Total number of model request loops executed.
        total_duration_seconds: Total execution time.
        final_message_count: Number of messages after execution.
    """

    total_loops: int = 0
    total_duration_seconds: float = 0.0
    final_message_count: int = 0


@dataclass
class AgentExecutionFailedEvent(AgentEvent):
    """Emitted when agent execution fails with an error.

    This event is emitted when an exception occurs during agent execution.
    Use it for error tracking and user notification.

    Attributes:
        error: Error message describing the failure.
        error_type: Type name of the exception (e.g., "UsageLimitExceeded").
        total_loops: Number of loops completed before failure.
        total_duration_seconds: Time elapsed before failure.
    """

    error: str = ""
    error_type: str = ""
    total_loops: int = 0
    total_duration_seconds: float = 0.0


# =============================================================================
# Model Request Events
# =============================================================================


@dataclass
class ModelRequestStartEvent(AgentEvent):
    """Emitted when agent starts a model request (thinking phase).

    A model request sends the current conversation to the LLM and waits for a response.
    This marks the beginning of a "loop" - one model request plus optional tool executions.

    Use this event for:
    - Displaying "Thinking..." status in UI
    - Tracking loop iterations (e.g., "Loop 3/10")
    - Implementing client-side loop limits

    Attributes:
        loop_index: Zero-based loop iteration number.
        message_count: Number of messages in history at request start.
    """

    loop_index: int = 0
    message_count: int = 0


@dataclass
class ModelRequestCompleteEvent(AgentEvent):
    """Emitted when a model request completes (response received).

    This marks the end of the thinking phase. If the model requested tool calls,
    a ToolCallsStartEvent will follow.

    Attributes:
        loop_index: Current loop iteration number.
        duration_seconds: Time spent waiting for model response.
    """

    loop_index: int = 0
    duration_seconds: float = 0.0


# =============================================================================
# Tool Calls Events
# =============================================================================


@dataclass
class ToolCallsStartEvent(AgentEvent):
    """Emitted when agent starts executing tool calls.

    This marks the transition from thinking to tool execution phase.
    Tool calls are executed based on the model's response.

    Use this event for:
    - Displaying "Running tools..." status in UI
    - Tracking tool execution phases

    Attributes:
        loop_index: Current loop iteration number.
    """

    loop_index: int = 0


@dataclass
class ToolCallsCompleteEvent(AgentEvent):
    """Emitted when tool calls execution completes.

    After this event, the agent will either:
    - Start another model request (ModelRequestStartEvent)
    - Complete execution (AgentExecutionCompleteEvent)

    Attributes:
        loop_index: Current loop iteration number.
        duration_seconds: Time spent executing tools.
    """

    loop_index: int = 0
    duration_seconds: float = 0.0


# =============================================================================
# Tool Search Events
# =============================================================================


class NamespaceStatus(StrEnum):
    """Initialization status of a namespace (toolset) in ToolSearchToolSet."""

    connected = "connected"
    """Namespace initialized successfully and is available for use."""

    skipped = "skipped"
    """Namespace failed to initialize but was optional, so it was skipped."""

    error = "error"
    """Namespace was connected but encountered a runtime error (e.g., disconnected)."""


@dataclass
class ToolSearchInitEvent(AgentEvent):
    """Emitted on first get_tools() call to report namespace initialization status.

    This event is emitted by ToolSearchToolSet after all wrapped toolsets have
    been initialized (via __aenter__). It reports which namespaces connected
    successfully and which were skipped due to initialization failure (when
    configured as optional via optional_namespaces).

    Consumers can use this to display MCP server connection status in the UI.

    Attributes:
        namespace_status: Mapping of namespace ID to initialization status.
            Namespaces that failed and were required do not appear here
            because they raise during __aenter__.
    """

    namespace_status: dict[str, NamespaceStatus] = field(default_factory=dict)


# =============================================================================
# File Change Events
# =============================================================================


class FileChangeAction(StrEnum):
    """Type of file system change."""

    created = "created"
    """A new file was created."""

    modified = "modified"
    """An existing file was modified."""

    moved = "moved"
    """A file or directory was moved/renamed."""

    copied = "copied"
    """A file was copied."""


@dataclass
class TextReplacement:
    """A single text replacement within a file.

    Attributes:
        old_string: Original text that was replaced (empty for new file creation).
        new_string: Replacement text.
    """

    old_string: str = ""
    new_string: str = ""


@dataclass
class FileChange:
    """A single file change entry.

    Attributes:
        path: File path that changed (relative to working directory).
        action: Type of change.
        destination: Target path for move/copy operations.
        replacements: Structured text replacements for edit operations.
    """

    path: str = ""
    action: FileChangeAction = FileChangeAction.modified
    destination: str | None = None
    replacements: list[TextReplacement] = field(default_factory=list)


@dataclass
class FileChangeEvent(AgentEvent):
    """Emitted when files are created, modified, moved, or copied.

    One event per tool call, may contain multiple file changes
    (e.g., multi_edit edits one file, move/copy handle multiple pairs).

    Only emitted on successful operations. Failed operations (file not found,
    text not matched, etc.) do not produce events.

    Attributes:
        changes: List of file changes in this operation.
        tool_name: Which tool triggered the changes (e.g., "edit", "write", "move").
    """

    changes: list[FileChange] = field(default_factory=list)
    tool_name: str = ""


# =============================================================================
# Task Events
# =============================================================================


@dataclass
class TaskInfo:
    """Snapshot of a single task for event transport.

    Attributes:
        id: Task identifier.
        subject: Task title.
        description: Task description.
        status: Current status ("pending", "in_progress", "completed").
        active_form: Present progressive form shown during in_progress.
        owner: Task owner/assignee.
        blocked_by: Task IDs that block this task.
        blocks: Task IDs that this task blocks.
    """

    id: str = ""
    subject: str = ""
    description: str = ""
    status: str = "pending"
    active_form: str | None = None
    owner: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)


@dataclass
class TaskEvent(AgentEvent):
    """Emitted when task state changes (create, update, list).

    Contains a full snapshot of all tasks for stateless rendering.
    Consumers can render the complete task board from this event
    without tracking incremental changes.

    Attributes:
        tasks: Full list of all tasks in current state.
    """

    tasks: list[TaskInfo] = field(default_factory=list)


# =============================================================================
# Memory Events
# =============================================================================


@dataclass
class MemoryEvent(AgentEvent):
    """Emitted when memory state changes (set, delete).

    Contains a full snapshot of all memory entries for stateless rendering.
    Consumers can render the complete memory view from this event
    without tracking incremental changes.

    Attributes:
        entries: Full dict of all memory entries (key -> value).
    """

    entries: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Type Aliases
# =============================================================================

# Union of all lifecycle events for type hints
LifecycleEvent = (
    AgentExecutionStartEvent
    | AgentExecutionCompleteEvent
    | AgentExecutionFailedEvent
    | ModelRequestStartEvent
    | ModelRequestCompleteEvent
    | ToolCallsStartEvent
    | ToolCallsCompleteEvent
)
