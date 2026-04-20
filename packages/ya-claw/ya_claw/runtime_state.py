from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class InMemoryRuntimeState:
    active_runs: set[str] = field(default_factory=set)
    background_tasks: set[str] = field(default_factory=set)
    subscribers: int = 0

    async def aclose(self) -> None:
        self.active_runs.clear()
        self.background_tasks.clear()
        self.subscribers = 0


def create_runtime_state() -> InMemoryRuntimeState:
    return InMemoryRuntimeState()
