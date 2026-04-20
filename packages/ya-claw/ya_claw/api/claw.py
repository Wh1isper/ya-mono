from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ya_claw.config import get_settings

router = APIRouter(prefix="/api/v1/claw", tags=["claw"])


class ClawInfo(BaseModel):
    name: str
    environment: str
    public_base_url: str
    surfaces: list[str]
    provider_model: str
    storage_model: str


class ClawTopology(BaseModel):
    nodes: list[str]
    edges: list[str]


@router.get("/info", response_model=ClawInfo)
async def claw_info() -> ClawInfo:
    settings = get_settings()
    return ClawInfo(
        name=settings.app_name,
        environment=settings.environment,
        public_base_url=settings.public_base_url,
        surfaces=["workspaces", "profiles", "sessions", "runs", "artifacts", "events", "web-shell"],
        provider_model="one configured WorkspaceProvider resolves local workspace bindings for runtime execution",
        storage_model="PostgreSQL stores durable state, Redis carries live events, and the local filesystem stores artifacts",
    )


@router.get("/topology", response_model=ClawTopology)
async def claw_topology() -> ClawTopology:
    return ClawTopology(
        nodes=["web-shell", "claw-api", "workspace-provider", "runtime-coordinator", "postgres", "redis"],
        edges=[
            "web-shell -> claw-api",
            "claw-api -> workspace-provider",
            "claw-api -> runtime-coordinator",
            "runtime-coordinator -> postgres",
            "runtime-coordinator -> redis",
        ],
    )
