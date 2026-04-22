from __future__ import annotations

import asyncio

from ya_claw.runtime_state import ActiveRunHandle, InMemoryRuntimeState, create_runtime_state


async def _collect_events(state: InMemoryRuntimeState, run_id: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    async for event in state.stream_run_events(run_id):
        events.append(event)
    return events


async def test_stream_run_events_closes_after_terminal_event() -> None:
    state = create_runtime_state()
    state.register_run("session-1", "run-1")

    consumer = asyncio.create_task(_collect_events(state, "run-1"))
    await asyncio.sleep(0)
    await state.append_run_event("run-1", {"type": "run.created"})
    await state.append_run_event("run-1", {"type": "run.cancelled"}, terminal=True)

    events = await asyncio.wait_for(consumer, timeout=1)

    assert [event["event"] for event in events] == ["run.created", "run.cancelled"]
    handle = state.get_run_handle("run-1")
    assert isinstance(handle, ActiveRunHandle)
    assert handle.closed is True


async def test_stream_run_events_replays_from_last_event_id() -> None:
    state = create_runtime_state()
    state.register_run("session-1", "run-1")
    await state.append_run_event("run-1", {"type": "run.created"})
    await state.append_run_event("run-1", {"type": "run.started"})
    await state.append_run_event("run-1", {"type": "run.completed"}, terminal=True)

    events: list[dict[str, str]] = []
    async for event in state.stream_run_events("run-1", last_event_id="1"):
        events.append(event)

    assert [event["event"] for event in events] == ["run.started", "run.completed"]


async def test_runtime_state_aclose_releases_waiting_subscribers() -> None:
    state = create_runtime_state()
    state.register_run("session-1", "run-1")

    consumer = asyncio.create_task(_collect_events(state, "run-1"))
    await asyncio.sleep(0.05)
    assert state.subscribers == 1

    await state.aclose()
    events = await asyncio.wait_for(consumer, timeout=1)

    assert events == []
    assert state.subscribers == 0
