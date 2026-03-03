"""Background delegate tool for TUI environment.

This tool launches subagent tasks in the background without blocking
the main agent. Results are delivered via message bus when complete.

Example:
    from ya_agent_sdk.toolsets.core.base import Toolset
    from yaacli.toolsets.background import BackgroundDelegateTool

    toolset = Toolset(tools=[..., BackgroundDelegateTool])
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.context.bus import BusMessage
from ya_agent_sdk.toolsets.core.base import BaseTool
from ya_agent_sdk.toolsets.core.subagent.factory import generate_unique_id
from yaacli.background import BACKGROUND_MANAGER_KEY, BackgroundTaskManager
from yaacli.logging import get_logger

logger = get_logger(__name__)


class BackgroundDelegateTool(BaseTool):
    """Launch a subagent in the background without blocking.

    This tool wraps the SDK's `delegate` tool and runs it as an asyncio task.
    The main agent continues immediately while the subagent works.
    Results are delivered via message bus when the subagent completes.
    """

    name = "background_delegate"
    description = "Launch a subagent in the background (non-blocking). Result delivered via message bus."

    def is_available(self, ctx: RunContext[AgentContext]) -> bool:
        """Available only for main agent with BackgroundTaskManager and delegate tool.

        Restricted to main agent because:
        - Results are sent to target=deps.agent_id via message bus
        - Subagents unsubscribe from bus when they exit
        - Messages sent to a subagent's agent_id would become unreachable
        """
        # Only available for main agent to avoid unreachable messages
        if ctx.deps.agent_id != "main":
            return False
        manager = self._get_manager(ctx)
        return manager is not None and manager.has_delegate_tool

    async def get_instruction(self, ctx: RunContext[AgentContext]) -> str | None:
        """Generate instruction for background delegate."""
        manager = self._get_manager(ctx)
        if manager is None:
            return None

        # Get active background tasks info
        task_info = manager.get_context_instruction()

        lines = [
            "<background-delegate-tool>",
            "Same subagent names as the `delegate` tool.",
            "Use this for long-running tasks where you don't need immediate results.",
            "The subagent runs in the background and its result is delivered via message bus.",
            "You can continue working on other tasks while the background subagent runs.",
        ]
        if task_info:
            lines.append("")
            lines.append(task_info)
        lines.append("</background-delegate-tool>")
        return "\n".join(lines)

    async def call(
        self,
        ctx: RunContext[AgentContext],
        subagent_name: Annotated[str, Field(description="Name of the subagent to delegate to")],
        prompt: Annotated[str, Field(description="The prompt to send to the subagent")],
    ) -> str:
        """Launch a subagent in the background."""
        manager = self._get_manager(ctx)
        if manager is None:
            return "Error: BackgroundTaskManager not available"

        delegate = manager.get_delegate_tool()
        if delegate is None:
            return "Error: delegate tool not available"

        deps = ctx.deps

        # Generate a unique agent_id for tracking
        short_id = generate_unique_id(deps.subagent_history)
        agent_id = f"{subagent_name}-bg-{short_id}"

        async def _run_background() -> None:
            """Background coroutine that runs the subagent and posts result to bus."""
            try:
                result = await delegate.call(
                    ctx,
                    subagent_name=subagent_name,
                    prompt=prompt,
                    agent_id=agent_id,
                )
                # Post result to message bus for the main agent
                deps.send_message(
                    BusMessage(
                        content=result,
                        source=agent_id,
                        target=deps.agent_id,
                    )
                )
                logger.info("Background subagent '%s' (%s) completed", subagent_name, agent_id)
            except Exception as e:
                logger.warning("Background subagent '%s' (%s) failed: %s", subagent_name, agent_id, e)
                deps.send_message(
                    BusMessage(
                        content=f"Background subagent '{subagent_name}' (id: {agent_id}) failed: {e}",
                        source=agent_id,
                        target=deps.agent_id,
                    )
                )
            finally:
                # Notify completion so TUI can trigger a new agent turn if idle
                manager.notify_completion(agent_id)

        task = asyncio.create_task(_run_background())
        manager.register_task(agent_id, task)

        return (
            f"Background task started: {subagent_name} (id: {agent_id}). "
            "Result will be delivered via message bus when complete. "
            "You can continue with other work."
        )

    def _get_manager(self, ctx: RunContext[AgentContext]) -> BackgroundTaskManager | None:
        """Get BackgroundTaskManager from resources."""
        if ctx.deps.resources is None:
            return None
        resource = ctx.deps.resources.get(BACKGROUND_MANAGER_KEY)
        if isinstance(resource, BackgroundTaskManager):
            return resource
        return None


background_tools: list[type[BaseTool]] = [BackgroundDelegateTool]
