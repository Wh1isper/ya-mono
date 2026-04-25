from __future__ import annotations

import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ya_claw.config import ClawSettings
from ya_claw.orm.tables import RuntimeInstanceRecord

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RuntimeInstanceManager:
    def __init__(
        self,
        *,
        settings: ClawSettings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory

    @property
    def instance_id(self) -> str:
        return self._settings.instance_id

    async def register(self, metadata: dict[str, Any] | None = None) -> bool:
        now = _utc_now()
        try:
            async with self._session_factory() as db_session:
                record = await db_session.get(RuntimeInstanceRecord, self.instance_id)
                if not isinstance(record, RuntimeInstanceRecord):
                    record = RuntimeInstanceRecord(
                        id=self.instance_id,
                        hostname=socket.gethostname(),
                        process_id=os.getpid(),
                        status="active",
                        instance_metadata=dict(metadata or {}),
                        started_at=now,
                        heartbeat_at=now,
                    )
                    db_session.add(record)
                else:
                    record.hostname = socket.gethostname()
                    record.process_id = os.getpid()
                    record.status = "active"
                    record.instance_metadata = dict(metadata or record.instance_metadata or {})
                    record.heartbeat_at = now
                    record.stopped_at = None
                await db_session.commit()
                return True
        except SQLAlchemyError:
            logger.warning("Runtime instance table is unavailable; skipping instance registration.")
            return False

    async def heartbeat(self) -> bool:
        now = _utc_now()
        try:
            async with self._session_factory() as db_session:
                record = await db_session.get(RuntimeInstanceRecord, self.instance_id)
                if isinstance(record, RuntimeInstanceRecord):
                    record.status = "active"
                    record.heartbeat_at = now
                    record.stopped_at = None
                    await db_session.commit()
                    return True
        except SQLAlchemyError:
            logger.warning("Runtime instance table is unavailable; skipping instance heartbeat.")
            return False
        return await self.register()

    async def mark_stopped(self) -> bool:
        now = _utc_now()
        try:
            async with self._session_factory() as db_session:
                record = await db_session.get(RuntimeInstanceRecord, self.instance_id)
                if isinstance(record, RuntimeInstanceRecord):
                    record.status = "stopped"
                    record.heartbeat_at = now
                    record.stopped_at = now
                    await db_session.commit()
                    return True
        except SQLAlchemyError:
            logger.warning("Runtime instance table is unavailable; skipping instance stop marker.")
            return False
        return False
