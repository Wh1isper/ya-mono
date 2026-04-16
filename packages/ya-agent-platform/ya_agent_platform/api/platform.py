from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ya_agent_platform.config import get_settings

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


class PlatformInfo(BaseModel):
    name: str
    environment: str
    public_base_url: str
    surfaces: list[str]
    bridge_model: str
    runtime_model: str


class PlatformTopology(BaseModel):
    nodes: list[str]
    edges: list[str]


@router.get("/info", response_model=PlatformInfo)
async def platform_info() -> PlatformInfo:
    settings = get_settings()
    return PlatformInfo(
        name=settings.app_name,
        environment=settings.environment,
        public_base_url=settings.public_base_url,
        surfaces=["management-api", "chat-api", "bridge-api", "chat-ui"],
        bridge_model="bridge adapters connect external IM systems to normalized platform events",
        runtime_model="agent sessions run through ya-agent-sdk based runtimes and workers",
    )


@router.get("/topology", response_model=PlatformTopology)
async def platform_topology() -> PlatformTopology:
    return PlatformTopology(
        nodes=[
            "chat-ui",
            "management-api",
            "chat-api",
            "bridge-api",
            "runtime-control",
            "runtime-workers",
            "postgres",
            "redis-or-message-bus",
        ],
        edges=[
            "chat-ui -> management-api",
            "chat-ui -> chat-api",
            "bridge adapters -> bridge-api",
            "management-api -> runtime-control",
            "chat-api -> runtime-control",
            "runtime-control -> runtime-workers",
            "runtime-control -> postgres",
            "runtime-control -> redis-or-message-bus",
        ],
    )
