from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ya_claw.app import create_app
from ya_claw.config import get_settings


@pytest.fixture(autouse=True)
def clear_claw_settings(monkeypatch, tmp_path: Path) -> None:
    for env_name in ("YA_CLAW_DATABASE_URL", "YA_CLAW_WEB_DIST_DIR"):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("YA_CLAW_DATA_DIR", str(tmp_path / "runtime-data"))

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_healthz() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "runtime_state": "ok"}


def test_claw_info() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/claw/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "YA Claw"
    assert "web-shell" in payload["surfaces"]


def test_index_without_frontend_bundle() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "YA Claw"


def test_serves_frontend_bundle(monkeypatch, tmp_path: Path) -> None:
    web_dist_dir = tmp_path / "web-dist"
    web_dist_dir.mkdir()
    (web_dist_dir / "index.html").write_text("<html><body>claw shell</body></html>", encoding="utf-8")
    assets_dir = web_dist_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "app.js").write_text("console.log('ready')", encoding="utf-8")

    monkeypatch.setenv("YA_CLAW_WEB_DIST_DIR", str(web_dist_dir))
    get_settings.cache_clear()

    with TestClient(create_app()) as app_client:
        root_response = app_client.get("/")
        asset_response = app_client.get("/assets/app.js")
        spa_response = app_client.get("/sessions")

    assert root_response.status_code == 200
    assert "claw shell" in root_response.text
    assert asset_response.status_code == 200
    assert "console.log('ready')" in asset_response.text
    assert spa_response.status_code == 200
    assert "claw shell" in spa_response.text

    get_settings.cache_clear()
