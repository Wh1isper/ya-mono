from __future__ import annotations

import asyncio
import json

from ya_claw.notifications import create_notification_hub


async def test_notification_hub_replays_events_after_last_event_id() -> None:
    hub = create_notification_hub()
    await hub.publish("session.created", {"session_id": "session-a"})
    await hub.publish("run.created", {"run_id": "run-a"})

    stream = hub.stream(last_event_id="1")
    event = await asyncio.wait_for(anext(stream), timeout=1)
    await hub.aclose()

    assert event["id"] == "2"
    assert event["event"] == "run.created"
    assert json.loads(event["data"])["payload"] == {"run_id": "run-a"}


async def test_notification_hub_tails_live_events_and_closes() -> None:
    hub = create_notification_hub()
    stream = hub.stream()
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)

    await hub.publish("profile.updated", {"profile_name": "general"})
    event = await asyncio.wait_for(pending, timeout=1)
    await hub.aclose()

    assert event["id"] == "1"
    assert event["event"] == "profile.updated"
    assert json.loads(event["data"])["payload"] == {"profile_name": "general"}
