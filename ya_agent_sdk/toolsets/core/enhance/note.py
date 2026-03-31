"""Note tool for persistent key-value storage.

This tool allows the agent to store, update, and delete note entries
that persist across conversation turns. Note entries are automatically
injected into runtime instructions on every user prompt.
"""

from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.events import NoteEvent
from ya_agent_sdk.toolsets.base import Instruction
from ya_agent_sdk.toolsets.core.base import BaseTool

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class NoteTool(BaseTool):
    """Tool for storing, updating, or deleting note entries."""

    name = "note"
    description = (
        "Update or delete a note entry. "
        "Notes persist across turns and are always visible in context. "
        "Omit value to delete the entry."
    )
    auto_inherit = True

    async def get_instruction(self, ctx: RunContext[AgentContext]) -> Instruction | None:
        """Get instruction for this tool."""
        instruction_file = _PROMPTS_DIR / "note.md"
        if instruction_file.exists():
            return Instruction(group="note", content=instruction_file.read_text())
        return None

    async def call(
        self,
        ctx: RunContext[AgentContext],
        key: Annotated[str, Field(description="Unique key for the note entry.")],
        value: Annotated[
            str | None,
            Field(description="Content to store. Omit or set to null to delete the entry."),
        ] = None,
    ) -> str:
        if value is None:
            if ctx.deps.note_manager.delete(key):
                await ctx.deps.emit_event(self._build_note_event(ctx))
                return f"Note entry '{key}' deleted."
            return f"Note entry '{key}' not found."

        ctx.deps.note_manager.set(key, value)
        await ctx.deps.emit_event(self._build_note_event(ctx))
        return f"Note entry '{key}' stored."

    @staticmethod
    def _build_note_event(ctx: RunContext[AgentContext]) -> NoteEvent:
        """Build a NoteEvent with full snapshot of all entries."""
        return NoteEvent(
            event_id=f"note-{ctx.deps.run_id[:8]}",
            entries=dict(ctx.deps.note_manager.entries),
        )
