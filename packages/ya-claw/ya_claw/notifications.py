from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

_DEFAULT_NOTIFICATION_BUFFER_SIZE = 1000


class NotificationEvent(BaseModel):
    id: str
    type: str
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class NotificationHub:
    max_events: int = _DEFAULT_NOTIFICATION_BUFFER_SIZE
    events: list[NotificationEvent] = field(default_factory=list)
    next_event_id: int = 1
    subscribers: int = 0
    closed: bool = False
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> NotificationEvent:
        event = NotificationEvent(
            id=str(self.next_event_id),
            type=event_type,
            created_at=datetime.now(UTC),
            payload=dict(payload or {}),
        )
        self.next_event_id += 1
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

        async with self.condition:
            self.condition.notify_all()

        return event

    async def stream(self, last_event_id: str | None = None) -> AsyncIterator[dict[str, str]]:
        cursor_id = _resolve_event_id(last_event_id)
        self.subscribers += 1
        try:
            while True:
                async with self.condition:
                    while not self.closed and not self._has_events_after(cursor_id):
                        await self.condition.wait()
                    if self.closed and not self._has_events_after(cursor_id):
                        return
                    pending_events = [event for event in self.events if int(event.id) > cursor_id]

                for event in pending_events:
                    cursor_id = int(event.id)
                    yield {
                        "id": event.id,
                        "event": event.type,
                        "data": json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
                    }
        finally:
            self.subscribers = max(self.subscribers - 1, 0)

    async def aclose(self) -> None:
        self.closed = True
        async with self.condition:
            self.condition.notify_all()

    def _has_events_after(self, cursor_id: int) -> bool:
        return any(int(event.id) > cursor_id for event in self.events)


def create_notification_hub() -> NotificationHub:
    return NotificationHub()


def _resolve_event_id(last_event_id: str | None) -> int:
    if last_event_id is None:
        return 0
    try:
        return max(int(last_event_id), 0)
    except ValueError:
        return 0
