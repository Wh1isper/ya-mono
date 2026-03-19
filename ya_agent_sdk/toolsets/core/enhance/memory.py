"""Memory management tool for persistent key-value storage.

This tool allows the agent to store, update, and delete memory entries
that persist across conversation turns. Memory entries are automatically
injected into runtime instructions on every user prompt.
"""

from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.events import MemoryEvent
from ya_agent_sdk.toolsets.base import Instruction
from ya_agent_sdk.toolsets.core.base import BaseTool

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class MemoryUpdateTool(BaseTool):
    """Tool for storing, updating, or deleting memory entries."""

    name = "memory_update"
    description = (
        "Update or delete a memory entry. "
        "Memory persists across turns and is always visible in context. "
        "Omit value to delete the entry."
    )
    auto_inherit = True

    async def get_instruction(self, ctx: RunContext[AgentContext]) -> Instruction | None:
        """Get instruction for this tool."""
        instruction_file = _PROMPTS_DIR / "memory.md"
        if instruction_file.exists():
            return Instruction(group="memory", content=instruction_file.read_text())
        return None

    async def call(
        self,
        ctx: RunContext[AgentContext],
        key: Annotated[str, Field(description="Unique key for the memory entry.")],
        value: Annotated[
            str | None,
            Field(description="Content to store. Omit or set to null to delete the entry."),
        ] = None,
    ) -> str:
        if value is None:
            if ctx.deps.memory_manager.delete(key):
                await ctx.deps.emit_event(self._build_memory_event(ctx))
                return f"Memory entry '{key}' deleted."
            return f"Memory entry '{key}' not found."

        ctx.deps.memory_manager.set(key, value)
        await ctx.deps.emit_event(self._build_memory_event(ctx))
        return f"Memory entry '{key}' stored."

    @staticmethod
    def _build_memory_event(ctx: RunContext[AgentContext]) -> MemoryEvent:
        """Build a MemoryEvent with full snapshot of all entries."""
        return MemoryEvent(
            event_id=f"memory-{ctx.deps.run_id[:8]}",
            entries=dict(ctx.deps.memory_manager.entries),
        )
