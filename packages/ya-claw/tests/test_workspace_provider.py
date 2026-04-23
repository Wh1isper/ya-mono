from __future__ import annotations

from pathlib import Path

from ya_agent_sdk.environment import SandboxEnvironment, VirtualLocalFileOperator
from ya_claw.workspace import (
    DockerEnvironmentFactory,
    DockerWorkspaceProvider,
    LocalEnvironmentFactory,
    LocalWorkspaceProvider,
    MappedLocalEnvironment,
    ReusableSandboxEnvironment,
    build_session_sandbox_container_ref,
)


def test_local_workspace_provider_resolves_virtual_workspace(tmp_path: Path) -> None:
    provider = LocalWorkspaceProvider(tmp_path / "workspace-root")

    binding = provider.resolve("repo-a", metadata={"source": "api"})

    assert binding.project_id == "repo-a"
    assert binding.host_path.exists()
    assert binding.virtual_path == Path("/workspace") / "repo-a"
    assert binding.cwd == binding.virtual_path
    assert binding.metadata["provider"] == "local"
    assert binding.metadata["shell_backend"] == "local"
    assert binding.backend_hint == "local"


async def test_local_environment_factory_uses_virtual_fs_and_local_shell(tmp_path: Path) -> None:
    provider = LocalWorkspaceProvider(tmp_path / "workspace-root")
    binding = provider.resolve("repo-a")
    factory = LocalEnvironmentFactory()
    environment = factory.build(binding)
    assert isinstance(environment, MappedLocalEnvironment)

    async with environment as env:
        assert isinstance(env.file_operator, VirtualLocalFileOperator)
        assert env.shell is not None
        await env.file_operator.write_file("notes.txt", "hello")
        content = await env.file_operator.read_file("notes.txt")
        exit_code, stdout, stderr = await env.shell.execute("pwd && ls", cwd=str(binding.host_path))

    assert content == "hello"
    assert exit_code == 0
    assert stderr == ""
    assert "notes.txt" in stdout


def test_docker_workspace_provider_builds_declarative_binding(tmp_path: Path) -> None:
    provider = DockerWorkspaceProvider(tmp_path / "workspace-root", image="python:3.11")

    binding = provider.resolve("repo-a", metadata={"session_id": "session-1"})

    assert binding.project_id == "repo-a"
    assert binding.virtual_path == Path("/workspace") / "repo-a"
    assert binding.metadata["provider"] == "docker"
    assert binding.metadata["docker_image"] == "python:3.11"
    assert binding.metadata["sandbox"]["container_ref"] == build_session_sandbox_container_ref("session-1")
    assert binding.backend_hint == "docker"


def test_docker_environment_factory_builds_sandbox_environment(tmp_path: Path) -> None:
    provider = DockerWorkspaceProvider(tmp_path / "workspace-root", image="python:3.11")
    binding = provider.resolve("repo-a", metadata={"session_id": "session-1"})
    factory = DockerEnvironmentFactory(image="python:3.11")

    environment = factory.build(binding)

    assert isinstance(environment, SandboxEnvironment)
    assert isinstance(environment, ReusableSandboxEnvironment)
    assert environment.container_ref == build_session_sandbox_container_ref("session-1")


def test_docker_environment_factory_prefers_container_id_and_keeps_stable_ref(tmp_path: Path) -> None:
    provider = DockerWorkspaceProvider(tmp_path / "workspace-root", image="python:3.11")
    binding = provider.resolve(
        "repo-a",
        metadata={
            "session_id": "session-1",
            "sandbox": {
                "container_id": "container-123",
                "container_ref": build_session_sandbox_container_ref("session-1"),
            },
        },
    )
    factory = DockerEnvironmentFactory(image="python:3.11")

    environment = factory.build(binding)

    assert isinstance(environment, ReusableSandboxEnvironment)
    assert environment.container_id == "container-123"
    assert environment.container_ref == build_session_sandbox_container_ref("session-1")
