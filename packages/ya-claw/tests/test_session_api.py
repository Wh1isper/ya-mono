from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from ya_claw.app import create_app
from ya_claw.config import get_settings
from ya_claw.db.engine import create_engine, create_session_factory
from ya_claw.orm.base import Base
from ya_claw.orm.tables import RunRecord, SessionRecord


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


def _mark_run_completed(session_id: str, run_id: str) -> None:
    async def _run() -> None:
        settings = get_settings()
        for _ in range(5):
            engine = create_engine(settings.resolved_database_url)
            session_factory = create_session_factory(engine)
            now = datetime.now(UTC)
            try:
                async with session_factory() as db_session:
                    session_record = await db_session.get(SessionRecord, session_id)
                    run_record = await db_session.get(RunRecord, run_id)
                    assert isinstance(session_record, SessionRecord)
                    assert isinstance(run_record, RunRecord)
                    run_record.status = "completed"
                    run_record.started_at = now - timedelta(seconds=2)
                    run_record.finished_at = now - timedelta(seconds=1)
                    run_record.committed_at = now
                    session_record.active_run_id = None
                    session_record.head_success_run_id = run_id
                    await db_session.commit()
                    return
            except OperationalError:
                await asyncio.sleep(0.1)
            finally:
                await engine.dispose()
        raise AssertionError("failed to mark run completed due to persistent database lock")

    asyncio.run(_run())


def test_session_and_run_endpoints_support_rerun_controls_and_events() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        create_session_response = client.post(
            "/api/v1/sessions",
            headers=_auth_headers(),
            json={
                "profile_name": "general",
                "project_id": "repo-a",
                "metadata": {"source": "api"},
                "input_parts": [{"type": "text", "text": "hello from api"}],
            },
        )
        assert create_session_response.status_code == 201
        session_payload = create_session_response.json()["session"]
        first_run_payload = create_session_response.json()["run"]
        assert isinstance(first_run_payload, dict)
        assert session_payload["status"] == "queued"

        session_steer_response = client.post(
            f"/api/v1/sessions/{session_payload['id']}/steer",
            headers=_auth_headers(),
            json={"input_parts": [{"type": "text", "text": "focus on tests"}]},
        )
        assert session_steer_response.status_code == 409

        steer_response = client.post(
            f"/api/v1/runs/{first_run_payload['id']}/steer",
            headers=_auth_headers(),
            json={"input_parts": [{"type": "text", "text": "focus on tests"}]},
        )
        assert steer_response.status_code == 200

        interrupt_response = client.post(
            f"/api/v1/runs/{first_run_payload['id']}/interrupt",
            headers=_auth_headers(),
        )
        assert interrupt_response.status_code == 200
        assert interrupt_response.json()["termination_reason"] == "interrupt"

        rerun_response = client.post(
            f"/api/v1/sessions/{session_payload['id']}/runs",
            headers=_auth_headers(),
            json={
                "restore_from_run_id": first_run_payload["id"],
                "input_parts": [{"type": "text", "text": "retry after interrupt"}],
            },
        )
        assert rerun_response.status_code == 201
        rerun_payload = rerun_response.json()

        list_sessions_response = client.get("/api/v1/sessions", headers=_auth_headers())
        assert list_sessions_response.status_code == 200
        sessions_payload = list_sessions_response.json()

        session_detail_response = client.get(
            f"/api/v1/sessions/{session_payload['id']}?include_message=true",
            headers=_auth_headers(),
        )
        assert session_detail_response.status_code == 200
        detail_payload = session_detail_response.json()

        run_detail_response = client.get(
            f"/api/v1/runs/{rerun_payload['id']}?include_message=true",
            headers=_auth_headers(),
        )
        assert run_detail_response.status_code == 200

        run_events_response = client.get(f"/api/v1/runs/{first_run_payload['id']}/events", headers=_auth_headers())
        assert run_events_response.status_code == 200

    assert len(sessions_payload) == 1
    assert sessions_payload[0]["id"] == session_payload["id"]
    assert sessions_payload[0]["run_count"] == 2
    assert sessions_payload[0]["head_run_id"] == rerun_payload["id"]
    assert sessions_payload[0]["latest_run"]["id"] == rerun_payload["id"]
    assert detail_payload["session"]["runs"][0]["id"] == rerun_payload["id"]
    assert detail_payload["session"]["runs_limit"] == 20
    assert detail_payload["session"]["runs_has_more"] is False
    assert detail_payload["session"]["runs"][0]["message"] is None
    assert run_detail_response.json()["session"]["id"] == session_payload["id"]
    assert run_detail_response.json()["run"]["input_preview"] == "retry after interrupt"
    assert run_detail_response.json()["state"] is None
    assert run_detail_response.json()["message"] is None or isinstance(run_detail_response.json()["message"], list)
    assert "ya_claw.run_queued" in run_events_response.text
    assert "ya_claw.run_interrupted" in run_events_response.text


def test_session_detail_can_include_message_and_paginate_runs() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        create_session_response = client.post("/api/v1/sessions", headers=_auth_headers(), json={})
        assert create_session_response.status_code == 201
        session_id = create_session_response.json()["session"]["id"]

        first_run_response = client.post(
            "/api/v1/runs",
            headers=_auth_headers(),
            json={
                "session_id": session_id,
                "input_parts": [{"type": "text", "text": "hello-1"}],
            },
        )
        assert first_run_response.status_code == 201
        first_run_id = first_run_response.json()["id"]

        second_run_response = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            headers=_auth_headers(),
            json={
                "input_parts": [{"type": "text", "text": "hello-2"}],
            },
        )
        assert second_run_response.status_code == 201
        second_run_id = second_run_response.json()["id"]

    _mark_run_completed(session_id, first_run_id)
    _mark_run_completed(session_id, second_run_id)

    settings = get_settings()
    first_run_dir = settings.run_store_dir / first_run_id
    second_run_dir = settings.run_store_dir / second_run_id
    first_run_dir.mkdir(parents=True, exist_ok=True)
    second_run_dir.mkdir(parents=True, exist_ok=True)
    (first_run_dir / "message.json").write_text(
        json.dumps([{"type": "message", "content": "first"}]),
        encoding="utf-8",
    )
    (second_run_dir / "message.json").write_text(
        json.dumps([{"type": "message", "content": "second"}]),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        session_response = client.get(
            f"/api/v1/sessions/{session_id}?runs_limit=1&include_message=true",
            headers=_auth_headers(),
        )
        page_2_response = client.get(
            f"/api/v1/sessions/{session_id}?runs_limit=1&before_sequence_no=2&include_message=true",
            headers=_auth_headers(),
        )

    assert session_response.status_code == 200
    assert session_response.json()["session"]["runs"][0]["id"] == second_run_id
    assert session_response.json()["session"]["runs"][0]["message"] == [{"type": "message", "content": "second"}]
    assert session_response.json()["session"]["runs_has_more"] is True
    assert session_response.json()["session"]["runs_next_before_sequence_no"] == 2

    assert page_2_response.status_code == 200
    assert page_2_response.json()["session"]["runs"][0]["id"] == first_run_id
    assert page_2_response.json()["session"]["runs"][0]["message"] == [{"type": "message", "content": "first"}]
    assert page_2_response.json()["session"]["runs_has_more"] is False


def test_run_get_rejects_non_array_message_blob() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        create_session_response = client.post("/api/v1/sessions", headers=_auth_headers(), json={})
        assert create_session_response.status_code == 201
        session_id = create_session_response.json()["session"]["id"]

        create_run_response = client.post(
            "/api/v1/runs",
            headers=_auth_headers(),
            json={
                "session_id": session_id,
                "input_parts": [{"type": "text", "text": "hello"}],
            },
        )
        assert create_run_response.status_code == 201
        run_id = create_run_response.json()["id"]

    _mark_run_completed(session_id, run_id)

    settings = get_settings()
    run_dir = settings.run_store_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "message.json").write_text(json.dumps({"events": []}), encoding="utf-8")

    with TestClient(create_app()) as client:
        run_response = client.get(
            f"/api/v1/runs/{run_id}?include_message=true",
            headers=_auth_headers(),
        )

    assert run_response.status_code == 500
    assert "top-level JSON array" in run_response.json()["detail"]


def test_run_get_exposes_session_state_and_message() -> None:
    _create_schema()

    with TestClient(create_app()) as client:
        create_session_response = client.post("/api/v1/sessions", headers=_auth_headers(), json={})
        assert create_session_response.status_code == 201
        session_id = create_session_response.json()["session"]["id"]

        create_run_response = client.post(
            "/api/v1/runs",
            headers=_auth_headers(),
            json={
                "session_id": session_id,
                "input_parts": [{"type": "text", "text": "hello"}],
            },
        )
        assert create_run_response.status_code == 201
        run_id = create_run_response.json()["id"]

    _mark_run_completed(session_id, run_id)

    settings = get_settings()
    run_dir = settings.run_store_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text(json.dumps({"state": "ready"}), encoding="utf-8")
    (run_dir / "message.json").write_text(json.dumps([]), encoding="utf-8")

    with TestClient(create_app()) as client:
        run_response = client.get(
            f"/api/v1/runs/{run_id}?include_message=true",
            headers=_auth_headers(),
        )

    assert run_response.status_code == 200
    assert run_response.json()["session"]["id"] == session_id
    assert run_response.json()["state"] == {"state": "ready"}
    assert run_response.json()["message"] == []
    assert run_response.json()["run"]["has_state"] is True
    assert run_response.json()["run"]["has_message"] is True
