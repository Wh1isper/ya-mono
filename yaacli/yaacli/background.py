"""Background task manager for CLI.

BackgroundTaskManager is a BaseResource that manages background subagent
tasks. It tracks asyncio tasks, provides callback-based completion notification,
and holds a reference to the core toolset for accessing the delegate tool.

Design:
- Callback-based: No polling. TUI registers a callback that's invoked on completion.
- Event-driven: Background tool calls notify_completion() when done.
- Race-free: TUI callback checks state atomically before scheduling agent turn.

Example:
    # Register with environment
    env.resources.set(BACKGROUND_MANAGER_KEY, BackgroundTaskManager())

    # Set core toolset and completion callback after runtime is entered
    manager.set_core_toolset(runtime.core_toolset)
    manager.set_completion_callback(on_background_complete)

    # Access from tool
    manager = ctx.deps.resources.get_typed(BACKGROUND_MANAGER_KEY, BackgroundTaskManager)
    delegate = manager.get_delegate_tool()
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from y_agent_environment import BaseResource

from yaacli.logging import get_logger

if TYPE_CHECKING:
    from ya_agent_sdk.toolsets.core.base import BaseTool, Toolset

logger = get_logger(__name__)

BACKGROUND_MANAGER_KEY = "background_task_manager"


class BackgroundTaskManager(BaseResource):
    """Manages background subagent tasks as a CLI resource.

    This resource tracks asyncio tasks spawned by SpawnDelegateTool,
    provides callback-based completion notification, and holds a reference
    to the core toolset for accessing the delegate tool.

    Lifecycle:
    - Created and registered during TUIEnvironment._setup()
    - core_toolset and completion_callback set after runtime entered (TUIApp.__aenter__)
    - Tasks registered by SpawnDelegateTool during agent execution
    - notify_completion() called when tasks complete
    - All tasks cancelled on close() (TUIEnvironment._teardown)
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._core_toolset: Toolset[Any] | None = None
        self._completion_callback: Callable[[str], None] | None = None

    def set_core_toolset(self, toolset: Toolset[Any] | None) -> None:
        """Set the core toolset reference for delegate tool access.

        Called by TUIApp after the runtime is entered.

        Args:
            toolset: The core Toolset from AgentRuntime.
        """
        self._core_toolset = toolset

    def set_completion_callback(self, callback: Callable[[str], None] | None) -> None:
        """Set callback to invoke when a background task completes.

        The callback receives the agent_id of the completed task.
        Called from the asyncio event loop, so it's safe to schedule tasks.

        Args:
            callback: Function to call on task completion, or None to clear.
        """
        self._completion_callback = callback

    def notify_completion(self, agent_id: str) -> None:
        """Notify that a background task has completed.

        Called by SpawnDelegateTool when a task finishes (success or failure).
        This invokes the registered callback if one exists.

        Args:
            agent_id: The ID of the completed background agent.
        """
        logger.debug("Background task completed: %s", agent_id)
        if self._completion_callback:
            try:
                self._completion_callback(agent_id)
            except Exception:
                logger.exception("Error in completion callback for %s", agent_id)

    def get_delegate_tool(self) -> BaseTool | None:
        """Get the delegate tool instance from the core toolset.

        Returns:
            The delegate BaseTool instance, or None if not available.
        """
        if self._core_toolset is None:
            return None
        try:
            return self._core_toolset._get_tool_instance("delegate")
        except Exception:
            return None

    @property
    def has_delegate_tool(self) -> bool:
        """Check if the delegate tool is available."""
        return self.get_delegate_tool() is not None

    @property
    def has_active_tasks(self) -> bool:
        """Check if there are any active (non-completed) background tasks."""
        return any(not t.done() for t in self._tasks.values())

    @property
    def active_tasks(self) -> dict[str, asyncio.Task[Any]]:
        """Active background tasks, keyed by agent_id (copy)."""
        return dict(self._tasks)

    def register_task(self, agent_id: str, task: asyncio.Task[Any]) -> None:
        """Register a background task for tracking.

        The task is auto-removed from the registry when it completes.

        Args:
            agent_id: Unique identifier for the background subagent.
            task: The asyncio.Task running the subagent.
        """
        self._tasks[agent_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(agent_id, None))
        logger.debug("Registered background task: %s", agent_id)

    async def close(self) -> None:
        """Cancel all background tasks and clean up."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug("Cancelled %d background tasks", len(tasks))
        self._tasks.clear()
        self._core_toolset = None
        self._completion_callback = None

    def get_context_instruction(self) -> str | None:
        """Return context instruction about active background tasks.

        Returns XML describing running background tasks, or None if none active.
        """
        running = [(aid, t) for aid, t in self._tasks.items() if not t.done()]
        if not running:
            return None

        lines = ["<background-tasks>"]
        for agent_id, _ in running:
            lines.append(f'  <task agent-id="{agent_id}" status="running"/>')
        lines.append("</background-tasks>")
        return "\n".join(lines)

    async def wait_for_all(self, timeout: float | None = None) -> None:
        """Wait for all background tasks to complete.

        Args:
            timeout: Maximum seconds to wait. None for no timeout.
        """
        tasks = list(self._tasks.values())
        if not tasks:
            return
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
