from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from ya_claw.controller.health import HealthController, HealthStatus
from ya_claw.runtime_state import InMemoryRuntimeState

router = APIRouter(tags=["health"])
controller = HealthController()


@router.get("/healthz", response_model=HealthStatus)
async def healthz(request: Request) -> HealthStatus:
    db_engine = request.app.state.db_engine
    runtime_state = request.app.state.runtime_state

    typed_db_engine: AsyncEngine | None = None
    typed_runtime_state: InMemoryRuntimeState | None = None

    if isinstance(db_engine, AsyncEngine):
        typed_db_engine = db_engine
    if isinstance(runtime_state, InMemoryRuntimeState):
        typed_runtime_state = runtime_state

    return await controller.read(db_engine=typed_db_engine, runtime_state=typed_runtime_state)
