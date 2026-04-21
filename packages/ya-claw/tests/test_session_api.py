from __future__ import annotations

import asyncio
import json
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
        "YA_CLAW_WORKSPACE_ROOT",
    ):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("YA_CLAW_API_TOKEN", "test-token")
    monkeypatch.setenv("YA_CLAW_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("YA_CLAW_WORKSPACE_ROOT", str(tmp_path / "workspace"))

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


def test_session_endpoints_return_run_info() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        create_session_response = client.post(
            "/api/v1/sessions",
            headers=_auth_headers(),
            json={"profile_name": "general", "project_id": "repo-a", "metadata": {"source": "api"}},
        )
        assert create_session_response.status_code == 201
        session_payload = create_session_response.json()

        create_run_response = client.post(
            "/api/v1/runs",
            headers=_auth_headers(),
            json={
                "session_id": session_payload["id"],
                "profile_name": "general",
                "project_id": "repo-a",
                "input_text": "hello from api",
                "metadata": {"source": "api"},
            },
        )
        assert create_run_response.status_code == 201
        run_payload = create_run_response.json()

        list_sessions_response = client.get("/api/v1/sessions", headers=_auth_headers())
        assert list_sessions_response.status_code == 200
        sessions_payload = list_sessions_response.json()

        session_detail_response = client.get(f"/api/v1/sessions/{session_payload['id']}", headers=_auth_headers())
        assert session_detail_response.status_code == 200
        detail_payload = session_detail_response.json()

        session_runs_response = client.get(f"/api/v1/sessions/{session_payload['id']}/runs", headers=_auth_headers())
        assert session_runs_response.status_code == 200
        runs_payload = session_runs_response.json()

        run_detail_response = client.get(f"/api/v1/runs/{run_payload['id']}", headers=_auth_headers())
        assert run_detail_response.status_code == 200

        cancel_run_response = client.post(f"/api/v1/runs/{run_payload['id']}/cancel", headers=_auth_headers())
        assert cancel_run_response.status_code == 200

    assert len(sessions_payload) == 1
    assert sessions_payload[0]["id"] == session_payload["id"]
    assert sessions_payload[0]["run_count"] == 1
    assert sessions_payload[0]["active_run_ids"] == [run_payload["id"]]
    assert sessions_payload[0]["latest_run"]["id"] == run_payload["id"]
    assert detail_payload["recent_runs"][0]["id"] == run_payload["id"]
    assert runs_payload[0]["id"] == run_payload["id"]
    assert run_detail_response.json()["input_text"] == "hello from api"
    assert cancel_run_response.json()["status"] == "cancelled"


def test_session_blob_endpoints_read_committed_files(tmp_path: Path) -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        create_session_response = client.post("/api/v1/sessions", headers=_auth_headers(), json={})
        session_id = create_session_response.json()["id"]

        settings = get_settings()
        session_dir = settings.session_store_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "state.json").write_text(json.dumps({"state": "ready"}), encoding="utf-8")
        (session_dir / "message.json").write_text(json.dumps({"messages": []}), encoding="utf-8")

        state_response = client.get(f"/api/v1/sessions/{session_id}/state", headers=_auth_headers())
        message_response = client.get(f"/api/v1/sessions/{session_id}/message", headers=_auth_headers())

    assert state_response.status_code == 200
    assert state_response.json() == {"state": "ready"}
    assert message_response.status_code == 200
    assert message_response.json() == {"messages": []}


def test_session_blob_endpoints_require_session_row() -> None:
    _create_schema()

    settings = get_settings()
    session_dir = settings.session_store_dir / "orphan-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "state.json").write_text(json.dumps({"state": "ready"}), encoding="utf-8")

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/sessions/orphan-session/state", headers=_auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Session 'orphan-session' was not found."}
