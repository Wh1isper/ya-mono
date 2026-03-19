"""Memory management for agent sessions.

This module provides a simple key-value memory store that persists
across turns and sessions. Memory entries are injected into runtime
instructions so the agent always has access to stored context.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryManager(BaseModel):
    """Manager for session-persistent memory entries.

    Provides a simple key-value store that the agent can read/write.
    Entries are injected into runtime instructions on every user prompt,
    giving the agent persistent recall across turns.

    MemoryManager is shared between parent and subagent contexts (shallow copy),
    providing a unified memory view across the agent hierarchy.

    Example:
        manager = MemoryManager()
        manager.set("language", "User prefers Chinese communication")
        manager.set("os", "macOS")
        manager.delete("os")
        entries = manager.list_all()
    """

    entries: dict[str, str] = Field(default_factory=dict)
    """All memory entries keyed by entry key."""

    def set(self, key: str, value: str) -> None:
        """Set or update a memory entry.

        Args:
            key: Unique key for the memory entry.
            value: Content to store.
        """
        self.entries[key] = value

    def get(self, key: str) -> str | None:
        """Get a memory entry by key.

        Args:
            key: The key to look up.

        Returns:
            The stored value if found, None otherwise.
        """
        return self.entries.get(key)

    def delete(self, key: str) -> bool:
        """Delete a memory entry by key.

        Args:
            key: The key to delete.

        Returns:
            True if the entry was deleted, False if not found.
        """
        if key in self.entries:
            del self.entries[key]
            return True
        return False

    def list_all(self) -> list[tuple[str, str]]:
        """Get all entries sorted by key.

        Returns:
            List of (key, value) tuples sorted by key.
        """
        return sorted(self.entries.items())

    def export_memory(self) -> dict[str, str]:
        """Export entries for serialization.

        Returns:
            Dict of key-value pairs.
        """
        return dict(self.entries)

    @classmethod
    def from_exported(cls, data: dict[str, Any]) -> MemoryManager:
        """Restore MemoryManager from exported data.

        Args:
            data: Exported memory data from export_memory().

        Returns:
            Restored MemoryManager instance.
        """
        return cls(entries={str(k): str(v) for k, v in data.items()})
