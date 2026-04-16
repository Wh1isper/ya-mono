"""Browser use specific test fixtures."""

import contextlib
import time
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture(scope="session")
def test_server(docker_client, docker_network):
    """Start Nginx container to serve test HTML files."""
    fixtures_path = Path(__file__).parent / "test_fixtures"

    if not fixtures_path.exists():
        pytest.skip("test_fixtures directory not found")

    container_name = f"test-server-{uuid4().hex}"
    container = None

    try:
        container = docker_client.containers.run(
            "nginx:alpine",
            detach=True,
            name=container_name,
            network=docker_network,
            volumes={
                str(fixtures_path.absolute()): {
                    "bind": "/usr/share/nginx/html/test_fixtures",
                    "mode": "ro",
                }
            },
            remove=True,
        )

        # Wait for nginx to be ready
        max_retries = 10
        for _ in range(max_retries):
            try:
                exit_code, _ = container.exec_run("wget -q -O- http://localhost/test_fixtures/basic.html")
                if exit_code == 0:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            if container:
                container.stop()
            pytest.fail("Nginx container failed to start")

        yield f"http://{container_name}"

    finally:
        if container:
            with contextlib.suppress(Exception):
                container.stop()


@pytest.fixture(scope="session")
def cdp_url(chrome_cdp_url, test_server):
    """CDP URL with test server dependency.

    This ensures the test server is started before browser tests run,
    so the browser can access test fixtures via the Docker network.
    """
    # test_server is used to ensure nginx container starts first
    _ = test_server
    return chrome_cdp_url
