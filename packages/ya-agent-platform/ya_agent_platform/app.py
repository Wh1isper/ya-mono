from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ya_agent_platform.api.health import router as health_router
from ya_agent_platform.api.platform import router as platform_router
from ya_agent_platform.config import PlatformSettings, get_settings
from ya_agent_platform.db.engine import create_engine
from ya_agent_platform.redis import create_redis_client

_RESERVED_FRONTEND_PATHS = ("api", "docs", "redoc", "openapi.json", "healthz")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    app.state.db_engine = None
    app.state.redis = None

    if settings.database_url:
        app.state.db_engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle=settings.database_pool_recycle_seconds,
        )

    if settings.redis_url:
        app.state.redis = create_redis_client(settings.redis_url)

    try:
        yield
    finally:
        redis_client = app.state.redis
        if redis_client is not None:
            await redis_client.aclose()

        db_engine = app.state.db_engine
        if db_engine is not None:
            await db_engine.dispose()


def _resolve_frontend_target(web_dist_dir: Path, requested_path: str) -> Path:
    relative_path = requested_path.strip("/")
    if relative_path == "":
        return web_dist_dir / "index.html"

    candidate = (web_dist_dir / relative_path).resolve()
    web_root = web_dist_dir.resolve()

    try:
        candidate.relative_to(web_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Invalid frontend asset path.") from exc

    if candidate.is_file():
        return candidate

    return web_dist_dir / "index.html"


def _register_frontend(app: FastAPI, settings: PlatformSettings) -> bool:
    web_dist_dir = settings.web_dist_dir
    if web_dist_dir is None:
        return False

    index_file = web_dist_dir / "index.html"
    if not web_dist_dir.exists() or not index_file.exists():
        return False

    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_route(full_path: str) -> FileResponse:
        normalized_path = full_path.strip("/")
        if normalized_path in _RESERVED_FRONTEND_PATHS or any(
            normalized_path.startswith(f"{prefix}/") for prefix in _RESERVED_FRONTEND_PATHS if "/" not in prefix
        ):
            raise HTTPException(status_code=404, detail="Route not found.")

        return FileResponse(_resolve_frontend_target(web_dist_dir, normalized_path))

    return True


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Cloud-ready agent platform backend built on top of ya-agent-sdk.",
        lifespan=_lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(platform_router)

    frontend_registered = _register_frontend(app, settings)

    if not frontend_registered:

        @app.get("/")
        async def index() -> dict[str, object]:
            return {
                "name": settings.app_name,
                "environment": settings.environment,
                "docs_url": "/docs",
                "spec_path": "packages/ya-agent-platform/spec",
                "surfaces": {
                    "admin": settings.admin_mount_path,
                    "chat": settings.chat_mount_path,
                    "bridges": settings.bridge_mount_path,
                },
            }

    return app
