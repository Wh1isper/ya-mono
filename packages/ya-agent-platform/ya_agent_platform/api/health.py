from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str
    postgres: str
    redis: str


@router.get("/healthz", response_model=HealthStatus)
async def healthz(request: Request) -> HealthStatus:
    postgres = "unavailable"
    redis = "unavailable"

    db_engine = getattr(request.app.state, "db_engine", None)
    if db_engine is not None:
        try:
            async with db_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            postgres = "ok"
        except Exception:
            postgres = "error"

    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis = "ok"
        except Exception:
            redis = "error"

    status = "degraded" if "error" in {postgres, redis} else "ok"
    return HealthStatus(status=status, postgres=postgres, redis=redis)
