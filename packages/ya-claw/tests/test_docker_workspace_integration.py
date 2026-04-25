from __future__ import annotations

import contextlib
from pathlib import Path
from uuid import uuid4

import pytest
from ya_claw.workspace import DockerEnvironmentFactory, DockerWorkspaceProvider


@pytest.fixture(scope="session")
def docker_client():
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        pytest.skip("Docker is not available")


async def test_docker_environment_executes_shell_inside_virtual_workspace(
    tmp_path: Path,
    docker_client,
) -> None:
    image = "python:3.11"
    try:
        docker_client.images.get(image)
    except Exception:
        pytest.skip(f"Docker image {image} is not available locally")

    session_id = f"session-{uuid4().hex[:8]}"
    provider = DockerWorkspaceProvider(tmp_path / "workspace-root", image=image)
    binding = provider.resolve("repo-a", metadata={"session_id": session_id})
    factory = DockerEnvironmentFactory(image=image, cleanup_on_exit=True)
    environment = factory.build(binding)

    try:
        async with environment as env:
            await env.file_operator.write_file("input.txt", "docker-ok")
            exit_code, stdout, stderr = await env.shell.execute(
                "pwd && python - <<'PY'\nfrom pathlib import Path\nPath('output.txt').write_text(Path('input.txt').read_text() + '-shell')\nprint(Path.cwd())\nPY"
            )
            output = await env.file_operator.read_file("output.txt")

        assert exit_code == 0
        assert stderr == ""
        assert str(binding.cwd) in stdout
        assert output == "docker-ok-shell"
    finally:
        container_ref = binding.metadata.get("sandbox", {}).get("container_ref")
        if isinstance(container_ref, str):
            with contextlib.suppress(Exception):
                container = docker_client.containers.get(container_ref)
                container.remove(force=True)
