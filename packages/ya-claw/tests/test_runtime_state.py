from __future__ import annotations

import asyncio

import pytest
from ya_claw.runtime_state import HitlWaitAborted, InMemoryRuntimeState, create_runtime_state


async def _collect_events(state: InMemoryRuntimeState, run_id: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    async for event in state.stream_run_events(run_id, last_event_id="0"):
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
    assert state.get_run_handle("run-1") is None


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


async def test_runtime_state_prunes_terminal_stream_run_after_consumer_finishes() -> None:
    state = create_runtime_state()
    state.register_run("session-1", "run-1")
    await state.append_run_event("run-1", {"type": "run.created"})
    await state.append_run_event("run-1", {"type": "run.completed"}, terminal=True)

    events: list[dict[str, str]] = []
    async for event in state.stream_run_events("run-1", last_event_id="0"):
        events.append(event)

    assert [event["event"] for event in events] == ["run.created", "run.completed"]
    assert state.get_run_handle("run-1") is None
    assert state.session_latest_run_ids == {}


async def test_runtime_state_scheduled_cleanup_clears_unconsumed_closed_run() -> None:
    state = create_runtime_state()
    state.register_run("session-1", "run-1")
    await state.append_run_event("run-1", {"type": "run.completed"}, terminal=True)

    state.schedule_run_cleanup("run-1", delay_seconds=0)
    await asyncio.sleep(0.05)

    assert state.get_run_handle("run-1") is None
    assert state.cleanup_tasks == {}


async def test_runtime_state_hitl_waits_until_all_interactions_resolve() -> None:
    from datetime import UTC, datetime

    from ya_claw.controller.models import ActiveInteraction

    state = create_runtime_state()
    state.register_run("session-1", "run-1")
    interactions = [
        ActiveInteraction(
            interaction_id="hitl-1",
            run_id="run-1",
            session_id="session-1",
            tool_call_id="tool-1",
            tool_name="shell_exec",
            title="Approve shell",
            sequence_no=1,
            total_count=2,
            created_at=datetime.now(UTC),
        ),
        ActiveInteraction(
            interaction_id="hitl-2",
            run_id="run-1",
            session_id="session-1",
            tool_call_id="tool-2",
            tool_name="file_write",
            title="Approve write",
            sequence_no=2,
            total_count=2,
            created_at=datetime.now(UTC),
        ),
    ]
    state.set_hitl_pending("run-1", "session-1", interactions)

    waiter = asyncio.create_task(state.wait_hitl_batch("run-1"))
    await asyncio.sleep(0)
    assert not waiter.done()

    resolved, current, remaining = await state.resolve_hitl_interaction("run-1", "hitl-1", approved=True)
    assert resolved.status == "approved"
    assert current is not None
    assert current.interaction_id == "hitl-2"
    assert remaining == 1
    assert not waiter.done()

    await state.resolve_hitl_interaction("run-1", "hitl-2", approved=False, reason="no")
    results = await asyncio.wait_for(waiter, timeout=1)

    assert [item.tool_call_id for item in results] == ["tool-1", "tool-2"]
    assert results[0].approved is True
    assert results[1].approved is False
    assert results[1].reason == "no"


async def test_runtime_state_stop_aborts_pending_hitl_wait() -> None:
    from ya_claw.controller.models import ActiveInteraction

    state = create_runtime_state()
    state.register_run("session-1", "run-1")
    state.set_hitl_pending(
        "run-1",
        "session-1",
        [
            ActiveInteraction(
                interaction_id="hitl-1",
                run_id="run-1",
                session_id="session-1",
                tool_call_id="tool-1",
                title="Approve",
            )
        ],
    )
    waiter = asyncio.create_task(state.wait_hitl_batch("run-1"))
    await asyncio.sleep(0)

    await state.request_stop("run-1", "cancel")

    with pytest.raises(HitlWaitAborted, match="cancel"):
        await asyncio.wait_for(waiter, timeout=1)


async def test_session_locks_keep_identity_while_held_or_waiting() -> None:
    import gc

    state = create_runtime_state()
    entered = asyncio.Event()

    async def waiter() -> None:
        async with state.session_lock("s"):
            entered.set()

    async with state.session_lock("s"):
        lock = state.session_lock("s")
        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        gc.collect()
        assert state.session_lock("s") is lock
        assert not entered.is_set()
        del lock
    await task
    gc.collect()
    assert entered.is_set()
    assert len(state.session_locks) == 0
    for i in range(1000):
        state.session_lock(str(i))
    assert len(state.session_locks) == 0
    await state.aclose()


async def test_bounded_ring_resets_expired_cursor_and_preserves_complete_text() -> None:
    import json

    state = create_runtime_state()
    handle = state.register_run("s", "r")
    handle.max_live_events = 2
    for delta in "ABCD":
        await state.append_run_event("r", {"type": "TEXT_MESSAGE_CHUNK", "messageId": "m", "delta": delta})
    assert len(handle.events) == 2
    stream = state.stream_run_events("r", last_event_id="1")
    snapshot = await anext(stream)
    assert snapshot["event"] == "claw.replay_snapshot"
    assert snapshot["id"] == "4"
    assert json.loads(snapshot["data"])["events"][0]["delta"] == "ABCD"
    await state.append_run_event("r", {"type": "TEXT_MESSAGE_CHUNK", "messageId": "m", "delta": "E"})
    event = await anext(stream)
    assert event["id"] == "5"
    assert json.loads(event["data"])["delta"] == "E"
    assert all(e["type"] != "claw.replay_snapshot" for e in state.get_replay_events("r"))
    await stream.aclose()
    await state.aclose()


async def test_slow_subscriber_resets_again_after_snapshot_cutover() -> None:
    import json

    state = create_runtime_state()
    handle = state.register_run("s", "r")
    handle.max_live_events = 2
    await state.append_run_event("r", {"type": "TEXT_MESSAGE_CHUNK", "messageId": "m", "delta": "A"})
    stream = state.stream_run_events("r")
    first = await anext(stream)
    assert first["id"] == "1"
    for delta in "BCD":
        await state.append_run_event("r", {"type": "TEXT_MESSAGE_CHUNK", "messageId": "m", "delta": delta})
    second = await anext(stream)
    assert second["id"] == "4"
    assert json.loads(second["data"])["events"][0]["delta"] == "ABCD"
    assert json.loads(first["data"])["events"][0]["delta"] == "A"
    await state.append_run_event("r", {"type": "RUN_FINISHED"}, terminal=True)
    terminal = await anext(stream)
    assert terminal["event"] == "RUN_FINISHED"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    await state.aclose()


async def test_oversized_terminal_snapshot_closes_and_keeps_payload_isolated() -> None:
    import json

    state = create_runtime_state()
    handle = state.register_run("s", "r")
    handle.max_live_bytes = 1
    payload = {"type": "CUSTOM", "value": {"nested": ["original"]}}
    returned = await state.append_run_event("r", payload)
    payload["value"]["nested"].append("caller mutation")
    returned.payload["value"]["nested"].append("return mutation")
    await state.append_run_event("r", {"type": "RUN_FINISHED"}, terminal=True)
    assert not handle.events
    assert handle.event_bytes == 0
    events = [event async for event in state.stream_run_events("r")]
    assert len(events) == 1
    snapshot = json.loads(events[0]["data"])
    assert snapshot["closed"] is True
    assert snapshot["events"][0]["value"]["nested"] == ["original"]
    assert state.get_run_handle("r") is None


async def test_future_cursor_resets_without_waiting_for_another_event() -> None:
    import json

    state = create_runtime_state()
    state.register_run("s", "r")
    stream = state.stream_run_events("r", last_event_id="99")
    snapshot = await asyncio.wait_for(anext(stream), timeout=1)
    assert snapshot["id"] == "0"
    assert json.loads(snapshot["data"])["reason"] == "cursor_invalid"
    await stream.aclose()
    await state.aclose()


async def test_independent_subscribers_survive_ring_eviction_and_registry_cleanup() -> None:
    import json

    state = create_runtime_state()
    handle = state.register_run("s", "r")
    handle.max_live_events = 2
    slow = state.stream_run_events("r")
    fast = state.stream_run_events("r")
    await anext(slow)
    await anext(fast)
    for delta in "ABCD":
        await state.append_run_event("r", {"type": "TEXT_MESSAGE_CHUNK", "messageId": "m", "delta": delta})
        event = await anext(fast)
        assert json.loads(event["data"])["delta"] == delta
    await state.append_run_event("r", {"type": "RUN_FINISHED"}, terminal=True)
    assert (await anext(fast))["event"] == "RUN_FINISHED"
    with pytest.raises(StopAsyncIteration):
        await anext(fast)
    assert state.get_run_handle("r") is None
    snapshot = json.loads((await anext(slow))["data"])
    assert snapshot["events"][0]["delta"] == "ABCD"
    assert snapshot["closed"] is True
    with pytest.raises(StopAsyncIteration):
        await anext(slow)
    assert state.subscribers == 0
    await state.aclose()


async def test_replay_read_cannot_mutate_private_event_payloads() -> None:
    state = create_runtime_state()
    state.register_run("s", "r")
    await state.append_run_event("r", {"type": "CUSTOM", "value": {"items": ["original"]}})
    snapshot = state.get_replay_events("r")
    snapshot[0]["value"]["items"].append("reader")
    assert state.get_replay_events("r")[0]["value"] == {"items": ["original"]}
    await state.aclose()
