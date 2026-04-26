from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.controller.schedule import ScheduleController
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.notifications import NotificationHub
from ya_claw.runtime_state import InMemoryRuntimeState


class ScheduleDispatcher:
    def __init__(
        self,
        *,
        settings: ClawSettings,
        session_factory: async_sessionmaker[AsyncSession],
        runtime_state: InMemoryRuntimeState,
        run_dispatcher: RunDispatcher,
        notification_hub: NotificationHub | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._runtime_state = runtime_state
        self._run_dispatcher = run_dispatcher
        self._notification_hub = notification_hub
        self._controller = ScheduleController()
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def startup(self) -> None:
        if not self._settings.schedule_dispatch_enabled:
            logger.info("Schedule dispatcher disabled")
            return
        if self._task is not None:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_loop(), name="ya-claw-schedule-dispatcher")
        logger.info("Schedule dispatcher started")

    async def shutdown(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        logger.info("Schedule dispatcher stopped")

    async def dispatch_once(self) -> int:
        async with self._session_factory() as db_session:
            pending = await self._controller.dispatch_pending(
                db_session,
                self._settings,
                self._runtime_state,
                self._run_dispatcher,
                limit=self._settings.schedule_max_due_per_tick,
            )
            due = await self._controller.dispatch_due(
                db_session,
                self._settings,
                self._runtime_state,
                self._run_dispatcher,
                limit=self._settings.schedule_max_due_per_tick,
            )
        for fire in [*pending, *due]:
            await self._publish_fire(fire.model_dump(mode="json"))
        return len(pending) + len(due)

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                count = await self.dispatch_once()
                if count:
                    logger.info("Schedule dispatcher processed fires count={}", count)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Schedule dispatcher tick failed error={}", exc)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=max(self._settings.schedule_tick_seconds, 1),
                )
            except TimeoutError:
                continue

    async def _publish_fire(self, payload: dict[str, object]) -> None:
        if self._notification_hub is None:
            return
        await self._notification_hub.publish("schedule.fire.updated", payload)


async def maybe_call(value: Callable[[], Awaitable[None]] | None) -> None:
    if value is not None:
        await value()
