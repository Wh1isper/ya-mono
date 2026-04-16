from pathlib import Path

from fastapi.testclient import TestClient
from ya_agent_platform.app import create_app
from ya_agent_platform.config import get_settings

client = TestClient(create_app())


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_platform_info() -> None:
    response = client.get("/api/v1/platform/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "YA Agent Platform"
    assert "chat-ui" in payload["surfaces"]


def test_index_without_frontend_bundle() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "YA Agent Platform"


def test_serves_frontend_bundle(monkeypatch, tmp_path: Path) -> None:
    web_dist_dir = tmp_path / "web-dist"
    web_dist_dir.mkdir()
    (web_dist_dir / "index.html").write_text("<html><body>platform shell</body></html>", encoding="utf-8")
    assets_dir = web_dist_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "app.js").write_text("console.log('ready')", encoding="utf-8")

    monkeypatch.setenv("YA_PLATFORM_WEB_DIST_DIR", str(web_dist_dir))
    get_settings.cache_clear()

    app = create_app()
    app_client = TestClient(app)

    root_response = app_client.get("/")
    asset_response = app_client.get("/assets/app.js")
    spa_response = app_client.get("/chat")

    assert root_response.status_code == 200
    assert "platform shell" in root_response.text
    assert asset_response.status_code == 200
    assert "console.log('ready')" in asset_response.text
    assert spa_response.status_code == 200
    assert "platform shell" in spa_response.text

    get_settings.cache_clear()
