from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncEngine

from ya_claw.api.health import router as health_router
from ya_claw.api.runs import router as runs_router
from ya_claw.api.sessions import router as sessions_router
from ya_claw.config import ClawSettings, get_settings
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.runtime_state import InMemoryRuntimeState, create_runtime_state


class ClawApplication:
    reserved_frontend_paths = ("api", "docs", "redoc", "openapi.json", "healthz")
    auth_exempt_paths = frozenset({"/healthz"})

    def __init__(self, settings: ClawSettings):
        self.settings = settings

    def create(self) -> FastAPI:
        self.settings.require_api_token()

        app = FastAPI(
            title=self.settings.app_name,
            version="0.1.0",
            description="Workspace-native single-node agent runtime with in-process state and SQLite-first storage.",
            lifespan=self.lifespan,
        )
        app.state.settings = self.settings
        app.state.db_engine = None
        app.state.db_session_factory = None
        app.state.runtime_state = None

        self.register_api_token_middleware(app)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.include_router(health_router)
        app.include_router(sessions_router, prefix="/api/v1")
        app.include_router(runs_router, prefix="/api/v1")

        frontend_registered = self.register_frontend(app)
        if not frontend_registered:
            self.register_index(app)

        return app

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        self.settings.ensure_runtime_directories()

        app.state.db_engine = create_engine(
            self.settings.resolved_database_url,
            echo=self.settings.database_echo,
            pool_size=self.settings.database_pool_size,
            max_overflow=self.settings.database_max_overflow,
            pool_recycle=self.settings.database_pool_recycle_seconds,
        )
        app.state.db_session_factory = create_session_factory(app.state.db_engine)
        app.state.runtime_state = create_runtime_state()

        try:
            yield
        finally:
            db_engine = app.state.db_engine
            runtime_state = app.state.runtime_state

            app.state.db_session_factory = None

            if isinstance(runtime_state, InMemoryRuntimeState):
                await runtime_state.aclose()

            if isinstance(db_engine, AsyncEngine):
                await db_engine.dispose()

    def register_api_token_middleware(self, app: FastAPI) -> None:
        expected_token = self.settings.require_api_token()

        @app.middleware("http")
        async def require_api_token(
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            if request.method == "OPTIONS" or request.url.path in self.auth_exempt_paths:
                return await call_next(request)

            authorization_header = request.headers.get("Authorization")
            provided_token = self.resolve_bearer_token(authorization_header)
            if not isinstance(provided_token, str) or not compare_digest(provided_token, expected_token):
                return JSONResponse(
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                    content={"detail": "Bearer token required."},
                )

            return await call_next(request)

    def resolve_bearer_token(self, authorization_header: str | None) -> str | None:
        if authorization_header is None:
            return None

        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer":
            return None

        normalized_token = token.strip()
        return normalized_token or None

    def register_frontend(self, app: FastAPI) -> bool:
        web_dist_dir = self.settings.web_dist_dir
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
            if normalized_path in self.reserved_frontend_paths or any(
                normalized_path.startswith(f"{prefix}/") for prefix in self.reserved_frontend_paths if "/" not in prefix
            ):
                raise HTTPException(status_code=404, detail="Route not found.")

            return FileResponse(self.resolve_frontend_target(web_dist_dir, normalized_path))

        return True

    def resolve_frontend_target(self, web_dist_dir: Path, requested_path: str) -> Path:
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

    def register_index(self, app: FastAPI) -> None:
        @app.get("/")
        async def index() -> dict[str, object]:
            return {
                "name": self.settings.app_name,
                "environment": self.settings.environment,
                "docs_url": "/docs",
                "spec_path": "packages/ya-claw/spec",
                "surfaces": ["sessions", "runs", "schedules", "bridges"],
            }


def create_app() -> FastAPI:
    settings = get_settings()
    return ClawApplication(settings).create()
