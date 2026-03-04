"""Background delegate tool for TUI environment.

This tool launches subagent tasks in the background without blocking
the main agent. Results are delivered via message bus when complete.

SteerSubagentTool allows the main agent to send steering guidance to
running background subagents via the shared message bus.

Example:
    from ya_agent_sdk.toolsets.core.base import Toolset
    from yaacli.toolsets.background import SpawnDelegateTool, SteerSubagentTool

    toolset = Toolset(tools=[..., SpawnDelegateTool, SteerSubagentTool])
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


class SpawnDelegateTool(BaseTool):
    """Launch a subagent in the background without blocking.

    This tool wraps the SDK's `delegate` tool and runs it as an asyncio task.
    The main agent continues immediately while the subagent works.
    Results are delivered via message bus when the subagent completes.

    Supports resume via agent_id parameter: pass the agent_id of a previously
    completed background subagent to continue its conversation in the background.
    """

    name = "spawn_delegate"
    description = "Spawn a subagent in the background (non-blocking). Result delivered via message bus."

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
        """Generate instruction for spawn delegate."""
        manager = self._get_manager(ctx)
        if manager is None:
            return None

        # Get active background tasks info
        task_info = manager.get_context_instruction()

        lines = [
            "Same subagent names as the `delegate` tool.",
            "Use this for long-running tasks where you don't need immediate results.",
            "The subagent runs in the background and its result is delivered via message bus.",
            "You can continue working on other tasks while the background subagent runs.",
        ]
        if task_info:
            lines.append("")
            lines.append(task_info)
        return "\n".join(lines)

    async def call(
        self,
        ctx: RunContext[AgentContext],
        subagent_name: Annotated[str, Field(description="Name of the subagent to delegate to")],
        prompt: Annotated[str, Field(description="The prompt to send to the subagent")],
        agent_id: Annotated[
            str | None, Field(description="Optional agent ID to resume a previous background subagent")
        ] = None,
    ) -> str:
        """Launch a subagent in the background."""
        manager = self._get_manager(ctx)
        if manager is None:
            return "Error: BackgroundTaskManager not available"

        delegate = manager.get_delegate_tool()
        if delegate is None:
            return "Error: delegate tool not available"

        deps = ctx.deps

        # Use provided agent_id for resume, or generate a new one
        if not agent_id:
            short_id = generate_unique_id(deps.subagent_history)
            agent_id = f"{subagent_name}-bg-{short_id}"

        effective_agent_id = agent_id

        async def _run_background() -> None:
            """Background coroutine that runs the subagent and posts result to bus."""
            try:
                result = await delegate.call(
                    ctx,
                    subagent_name=subagent_name,
                    prompt=prompt,
                    agent_id=effective_agent_id,
                )
                # Post result to message bus for the main agent
                deps.send_message(
                    BusMessage(
                        content=result,
                        source=effective_agent_id,
                        target=deps.agent_id,
                    )
                )
                logger.info("Spawned delegate '%s' (%s) completed", subagent_name, effective_agent_id)
            except Exception as e:
                logger.warning("Spawned delegate '%s' (%s) failed: %s", subagent_name, effective_agent_id, e)
                deps.send_message(
                    BusMessage(
                        content=f"Spawned delegate '{subagent_name}' (id: {effective_agent_id}) failed: {e}",
                        source=effective_agent_id,
                        target=deps.agent_id,
                    )
                )
            finally:
                # Notify completion so TUI can trigger a new agent turn if idle
                manager.notify_completion(effective_agent_id)

        task = asyncio.create_task(_run_background())
        manager.register_task(effective_agent_id, task)

        is_resume = effective_agent_id in deps.subagent_history
        action = "Resumed" if is_resume else "Spawned"
        return (
            f"{action} delegate: {subagent_name} (id: {effective_agent_id}). "
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


class SteerSubagentTool(BaseTool):
    """Send steering guidance to a running background subagent.

    Injects a message into the subagent's execution via the shared message bus.
    The subagent will receive it on its next LLM call via inject_bus_messages filter.

    If the target subagent has already completed, suggests using spawn_delegate
    with agent_id to resume the conversation instead.
    """

    name = "steer_subagent"
    description = "Send additional guidance to a running background subagent."

    def is_available(self, ctx: RunContext[AgentContext]) -> bool:
        """Available only for main agent with active background tasks."""
        if ctx.deps.agent_id != "main":
            return False
        manager = self._get_manager(ctx)
        return manager is not None and manager.has_active_tasks

    async def get_instruction(self, ctx: RunContext[AgentContext]) -> str | None:
        """Only show instruction when there are active background tasks."""
        manager = self._get_manager(ctx)
        if manager is None or not manager.has_active_tasks:
            return None
        return (
            "Send additional guidance to a running background subagent.\n"
            "The message is injected into the subagent's context on its next LLM call.\n"
            "Use this to redirect, refine, or add constraints to an in-progress task."
        )

    async def call(
        self,
        ctx: RunContext[AgentContext],
        agent_id: Annotated[str, Field(description="ID of the background subagent (e.g., 'searcher-bg-a7b9')")],
        message: Annotated[str, Field(description="Steering guidance to send")],
    ) -> str:
        """Send steering message to a running background subagent."""
        manager = self._get_manager(ctx)
        if manager is None:
            return "Error: BackgroundTaskManager not available"

        # Verify the target agent is actually running
        if agent_id not in manager.active_tasks or manager.active_tasks[agent_id].done():
            return self._suggest_resume(ctx, agent_id, message, manager)

        # Send targeted message via shared bus
        ctx.deps.send_message(
            BusMessage(
                content=message,
                source=ctx.deps.agent_id,  # "main"
                target=agent_id,
            )
        )

        return f"Steering message sent to {agent_id}. It will be injected on the subagent's next LLM call."

    def _suggest_resume(
        self,
        ctx: RunContext[AgentContext],
        agent_id: str,
        message: str,
        manager: BackgroundTaskManager,
    ) -> str:
        """Build error message suggesting resume for finished agents."""
        # Look up agent_name from registry for the delegate call
        agent_info = ctx.deps.agent_registry.get(agent_id)
        agent_name = agent_info.agent_name if agent_info else agent_id.split("-bg-")[0]

        # Check if there are other active tasks to mention
        active = [aid for aid, t in manager.active_tasks.items() if not t.done()]
        active_hint = f" Active tasks: {', '.join(active)}" if active else ""

        # Truncate message for the suggestion if too long
        prompt_preview = message[:80] + "..." if len(message) > 80 else message

        return (
            f"'{agent_id}' has already completed and cannot be steered.{active_hint}\n"
            f"To continue its conversation in the background, use spawn_delegate with agent_id to resume:\n"
            f'  spawn_delegate(subagent_name="{agent_name}", prompt="{prompt_preview}", agent_id="{agent_id}")\n'
            f"Or use blocking delegate for synchronous resume:\n"
            f'  delegate(subagent_name="{agent_name}", prompt="{prompt_preview}", agent_id="{agent_id}")'
        )

    def _get_manager(self, ctx: RunContext[AgentContext]) -> BackgroundTaskManager | None:
        """Get BackgroundTaskManager from resources."""
        if ctx.deps.resources is None:
            return None
        resource = ctx.deps.resources.get(BACKGROUND_MANAGER_KEY)
        if isinstance(resource, BackgroundTaskManager):
            return resource
        return None


background_tools: list[type[BaseTool]] = [SpawnDelegateTool, SteerSubagentTool]
