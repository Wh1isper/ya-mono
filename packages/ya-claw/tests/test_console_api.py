from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ya_claw.app import create_app
from ya_claw.config import get_settings
from ya_claw.db.engine import create_engine
from ya_claw.notifications import NotificationHub
from ya_claw.orm.base import Base


@pytest.fixture(autouse=True)
def clear_claw_settings(monkeypatch, tmp_path: Path) -> None:
    for env_name in (
        "YA_CLAW_API_TOKEN",
        "YA_CLAW_DATABASE_URL",
        "YA_CLAW_DATA_DIR",
        "YA_CLAW_WEB_DIST_DIR",
        "YA_CLAW_WORKSPACE_DIR",
        "YA_CLAW_PROFILE_SEED_FILE",
        "YA_CLAW_AUTO_SEED_PROFILES",
        "YA_CLAW_EXECUTION_MODEL",
    ):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("YA_CLAW_API_TOKEN", "test-token")
    monkeypatch.setenv("YA_CLAW_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("YA_CLAW_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("YA_CLAW_PROFILE_SEED_FILE", str(tmp_path / "profiles.yaml"))
    monkeypatch.setenv("YA_CLAW_AUTO_SEED_PROFILES", "false")

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


def _notification_hub(client: TestClient) -> NotificationHub:
    notification_hub = client.app.state.notification_hub
    assert isinstance(notification_hub, NotificationHub)
    return notification_hub


def test_claw_info_reports_console_capabilities() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/claw/info", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "YA Claw"
    assert payload["auth"] == "bearer"
    assert payload["features"]["session_events"] is True
    assert payload["features"]["run_events"] is True
    assert payload["features"]["notifications"] is True
    assert "notifications" in payload["surfaces"]


def test_console_notifications_endpoint_is_present_in_openapi() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/claw/notifications" in response.json()["paths"]


def test_console_notifications_capture_session_run_and_profile_events() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        session_response = client.post(
            "/api/v1/sessions",
            headers=_auth_headers(),
            json={
                "profile_name": "general",
                "input_parts": [{"type": "text", "text": "hello"}],
            },
        )
        assert session_response.status_code == 201
        session_payload = session_response.json()["session"]
        run_payload = session_response.json()["run"]

        profile_response = client.put(
            "/api/v1/profiles/general",
            headers=_auth_headers(),
            json={
                "model": "gateway@openai-responses:gpt-5.4",
                "builtin_toolsets": ["core"],
                "enabled": True,
            },
        )
        assert profile_response.status_code == 200

        events = _notification_hub(client).events
        event_types = [event.type for event in events]
        assert event_types[:3] == ["session.created", "run.created", "profile.created"]
        assert events[0].payload["session_id"] == session_payload["id"]
        assert events[1].payload["run_id"] == run_payload["id"]
        assert events[2].payload["profile_name"] == "general"


def test_profile_delete_emits_console_notification() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        put_response = client.put(
            "/api/v1/profiles/custom",
            headers=_auth_headers(),
            json={
                "model": "gateway@openai-responses:gpt-5.4",
                "enabled": True,
            },
        )
        assert put_response.status_code == 200

        delete_response = client.delete("/api/v1/profiles/custom", headers=_auth_headers())
        assert delete_response.status_code == 204

        events = _notification_hub(client).events

    assert events[-1].type == "profile.deleted"
    assert events[-1].payload["profile_name"] == "custom"
