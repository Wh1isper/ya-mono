from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.controller.heartbeat import HeartbeatController
from ya_claw.execution.dispatcher import RunDispatcher
from ya_claw.notifications import NotificationHub
from ya_claw.runtime_state import InMemoryRuntimeState


class HeartbeatDispatcher:
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
        self._controller = HeartbeatController()
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def startup(self) -> None:
        if not self._settings.heartbeat_enabled:
            logger.info("Heartbeat dispatcher disabled")
            return
        if self._task is not None:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_loop(), name="ya-claw-heartbeat-dispatcher")
        logger.info("Heartbeat dispatcher started")

    async def shutdown(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        logger.info("Heartbeat dispatcher stopped")

    async def dispatch_once(self) -> int:
        async with self._session_factory() as db_session:
            fire = await self._controller.dispatch_due(
                db_session,
                self._settings,
                self._runtime_state,
                self._run_dispatcher,
            )
        if fire is None:
            return 0
        if self._notification_hub is not None:
            await self._notification_hub.publish("heartbeat.fire.updated", fire.model_dump(mode="json"))
        return 1

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                count = await self.dispatch_once()
                if count:
                    logger.info("Heartbeat dispatcher processed fires count={}", count)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Heartbeat dispatcher tick failed error={}", exc)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=max(min(self._settings.heartbeat_interval_seconds, 60), 1),
                )
            except TimeoutError:
                continue
