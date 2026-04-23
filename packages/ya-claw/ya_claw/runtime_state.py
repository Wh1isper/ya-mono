from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from ya_claw.agui_adapter import AguiReplayBuffer


@dataclass(slots=True)
class BufferedEvent:
    id: str
    payload: dict[str, Any]
    terminal: bool = False


@dataclass(slots=True)
class ActiveRunHandle:
    run_id: str
    session_id: str
    dispatch_mode: str = "async"
    steering_inputs: list[list[dict[str, Any]]] = field(default_factory=list)
    events: list[BufferedEvent] = field(default_factory=list)
    replay: AguiReplayBuffer = field(default_factory=AguiReplayBuffer)
    next_event_id: int = 1
    closed: bool = False
    termination_requested: str | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


@dataclass(slots=True)
class InMemoryRuntimeState:
    run_handles: dict[str, ActiveRunHandle] = field(default_factory=dict)
    session_latest_run_ids: dict[str, str] = field(default_factory=dict)
    background_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    subscribers: int = 0

    def register_run(self, session_id: str, run_id: str, *, dispatch_mode: str = "async") -> ActiveRunHandle:
        handle = ActiveRunHandle(run_id=run_id, session_id=session_id, dispatch_mode=dispatch_mode)
        self.run_handles[run_id] = handle
        self.session_latest_run_ids[session_id] = run_id
        return handle

    def get_run_handle(self, run_id: str) -> ActiveRunHandle | None:
        return self.run_handles.get(run_id)

    def get_session_run_handle(self, session_id: str) -> ActiveRunHandle | None:
        run_id = self.session_latest_run_ids.get(session_id)
        if run_id is None:
            return None
        return self.get_run_handle(run_id)

    def get_replay_events(self, run_id: str) -> list[dict[str, Any]]:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            raise KeyError(run_id)
        return handle.replay.snapshot()

    def register_background_task(self, run_id: str, task: asyncio.Task[None]) -> None:
        self.background_tasks[run_id] = task

    def get_background_task(self, run_id: str) -> asyncio.Task[None] | None:
        return self.background_tasks.get(run_id)

    def clear_background_task(self, run_id: str) -> None:
        self.background_tasks.pop(run_id, None)

    async def append_run_event(
        self,
        run_id: str,
        payload: dict[str, Any],
        *,
        terminal: bool = False,
        replay: bool = True,
    ) -> BufferedEvent:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            raise KeyError(run_id)

        if replay:
            handle.replay.append(payload)

        event = BufferedEvent(id=str(handle.next_event_id), payload=payload, terminal=terminal)
        handle.next_event_id += 1
        handle.events.append(event)
        if terminal:
            handle.closed = True

        async with handle.condition:
            handle.condition.notify_all()

        return event

    async def record_steering(self, run_id: str, input_parts: list[dict[str, Any]]) -> None:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            raise KeyError(run_id)
        handle.steering_inputs.append(list(input_parts))

    def consume_steering_inputs(self, run_id: str) -> list[list[dict[str, Any]]]:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            return []
        pending = list(handle.steering_inputs)
        handle.steering_inputs.clear()
        return pending

    def get_termination_requested(self, run_id: str) -> str | None:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            return None
        return handle.termination_requested

    async def request_stop(self, run_id: str, termination_reason: str) -> None:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            raise KeyError(run_id)
        handle.termination_requested = termination_reason
        async with handle.condition:
            handle.condition.notify_all()

    async def close_run(self, run_id: str) -> None:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            return
        handle.closed = True
        async with handle.condition:
            handle.condition.notify_all()

    async def stream_run_events(self, run_id: str, last_event_id: str | None = None) -> AsyncIterator[dict[str, str]]:
        handle = self.get_run_handle(run_id)
        if not isinstance(handle, ActiveRunHandle):
            raise KeyError(run_id)

        cursor = _resolve_cursor(last_event_id)
        self.subscribers += 1
        try:
            while True:
                async with handle.condition:
                    while cursor >= len(handle.events) and not handle.closed:
                        await handle.condition.wait()
                    pending_events = list(handle.events[cursor:])
                    handle_closed = handle.closed

                for event in pending_events:
                    cursor += 1
                    yield {
                        "id": event.id,
                        "event": str(event.payload.get("type", "message")),
                        "data": json.dumps(event.payload, ensure_ascii=False),
                    }
                    if event.terminal:
                        return

                if handle_closed:
                    return
        finally:
            self.subscribers = max(self.subscribers - 1, 0)

    async def stream_session_events(
        self,
        session_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        handle = self.get_session_run_handle(session_id)
        if not isinstance(handle, ActiveRunHandle):
            raise KeyError(session_id)
        async for event in self.stream_run_events(handle.run_id, last_event_id=last_event_id):
            yield event

    async def aclose(self) -> None:
        background_tasks = list(self.background_tasks.values())
        for task in background_tasks:
            if not task.done():
                task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        for handle in self.run_handles.values():
            handle.closed = True
            async with handle.condition:
                handle.condition.notify_all()
        self.run_handles.clear()
        self.session_latest_run_ids.clear()
        self.background_tasks.clear()
        self.subscribers = 0


def _resolve_cursor(last_event_id: str | None) -> int:
    if last_event_id is None:
        return 0
    try:
        return max(int(last_event_id), 0)
    except ValueError:
        return 0


def create_runtime_state() -> InMemoryRuntimeState:
    return InMemoryRuntimeState()
