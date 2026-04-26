from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ya_claw.app import create_app
from ya_claw.config import get_settings
from ya_claw.db.engine import create_engine
from ya_claw.orm.base import Base


@pytest.fixture(autouse=True)
def clear_claw_settings(monkeypatch, tmp_path: Path) -> None:
    for env_name in (
        "YA_CLAW_API_TOKEN",
        "YA_CLAW_DATABASE_URL",
        "YA_CLAW_DATA_DIR",
        "YA_CLAW_WEB_DIST_DIR",
        "YA_CLAW_WORKSPACE_DIR",
        "YA_CLAW_EXECUTION_MODEL",
    ):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("YA_CLAW_API_TOKEN", "test-token")
    monkeypatch.setenv("YA_CLAW_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("YA_CLAW_WORKSPACE_DIR", str(tmp_path / "workspace"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _create_schema() -> None:
    async def _run() -> None:
        settings = get_settings()
        engine = create_engine(settings.resolved_database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_json_create_routes_ignore_stream_dispatch_mode_for_response_type() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        session_response = client.post(
            "/api/v1/sessions",
            headers=_auth_headers(),
            json={
                "input_parts": [{"type": "text", "text": "hello"}],
                "dispatch_mode": "stream",
            },
        )
        run_response = client.post(
            "/api/v1/runs",
            headers=_auth_headers(),
            json={
                "input_parts": [{"type": "text", "text": "hello"}],
                "dispatch_mode": "stream",
            },
        )

    assert session_response.status_code == 201
    assert session_response.headers["content-type"].startswith("application/json")
    assert session_response.json()["run"]["status"] == "queued"
    assert run_response.status_code == 201
    assert run_response.headers["content-type"].startswith("application/json")
    assert run_response.json()["status"] == "queued"


def test_stream_routes_are_present_in_openapi() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/sessions:stream" in paths
    assert "/api/v1/sessions/{session_id}/runs:stream" in paths
    assert "/api/v1/runs:stream" in paths
