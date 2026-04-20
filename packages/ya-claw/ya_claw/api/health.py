from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str
    database: str
    runtime_state: str


@router.get("/healthz", response_model=HealthStatus)
async def healthz(request: Request) -> HealthStatus:
    database = "unavailable"
    runtime_state = "unavailable"

    db_engine = getattr(request.app.state, "db_engine", None)
    if db_engine is not None:
        try:
            async with db_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            database = "ok"
        except Exception:
            database = "error"

    runtime_manager = getattr(request.app.state, "runtime_state", None)
    if runtime_manager is not None:
        runtime_state = "ok"

    status = "ok" if database == "ok" and runtime_state == "ok" else "degraded"
    return HealthStatus(status=status, database=database, runtime_state=runtime_state)
