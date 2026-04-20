from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ya_claw.runtime_state import InMemoryRuntimeState


class HealthStatus(BaseModel):
    status: str
    database: str
    runtime_state: str


class HealthController:
    async def read(self, db_engine: AsyncEngine | None, runtime_state: InMemoryRuntimeState | None) -> HealthStatus:
        database_status = "unavailable"
        runtime_state_status = "unavailable"

        if isinstance(db_engine, AsyncEngine):
            try:
                async with db_engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                database_status = "ok"
            except Exception:
                database_status = "error"

        if isinstance(runtime_state, InMemoryRuntimeState):
            runtime_state_status = "ok"

        overall_status = "ok"
        if database_status != "ok" or runtime_state_status != "ok":
            overall_status = "degraded"

        return HealthStatus(
            status=overall_status,
            database=database_status,
            runtime_state=runtime_state_status,
        )
