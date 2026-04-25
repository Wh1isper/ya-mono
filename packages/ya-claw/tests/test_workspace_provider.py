from __future__ import annotations

from pathlib import Path

from ya_agent_sdk.environment import SandboxEnvironment, VirtualLocalFileOperator, VirtualMount
from ya_claw.workspace import (
    DockerEnvironmentFactory,
    DockerWorkspaceProvider,
    LocalEnvironmentFactory,
    LocalWorkspaceProvider,
    MappedLocalEnvironment,
    ReusableSandboxEnvironment,
    build_session_sandbox_container_ref,
    build_session_sandbox_metadata,
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


def test_local_workspace_provider_resolves_multiple_project_mounts(tmp_path: Path) -> None:
    provider = LocalWorkspaceProvider(tmp_path / "workspace-root")

    binding = provider.resolve(
        "repo-a",
        metadata={
            "projects": [
                {"project_id": "repo-a", "description": "primary repo"},
                {"project_id": "repo-b", "description": "reference repo"},
            ]
        },
    )

    assert binding.project_id == "repo-a"
    assert [mount.project_id for mount in binding.project_mounts] == ["repo-a", "repo-b"]
    assert [mount.virtual_path for mount in binding.project_mounts] == [
        Path("/workspace") / "repo-a",
        Path("/workspace") / "repo-b",
    ]
    assert binding.project_mounts[0].description == "primary repo"
    assert binding.project_mounts[1].description == "reference repo"
    assert binding.readable_paths == [Path("/workspace") / "repo-a", Path("/workspace") / "repo-b"]
    assert binding.writable_paths == [Path("/workspace") / "repo-a", Path("/workspace") / "repo-b"]


async def test_local_environment_factory_mounts_multiple_projects_for_fileops_and_shell(tmp_path: Path) -> None:
    provider = LocalWorkspaceProvider(tmp_path / "workspace-root")
    binding = provider.resolve(
        "repo-a",
        metadata={
            "projects": [
                {"project_id": "repo-a", "description": "primary repo"},
                {"project_id": "repo-b", "description": "reference repo"},
            ]
        },
    )
    factory = LocalEnvironmentFactory()
    environment = factory.build(binding)

    async with environment as env:
        assert isinstance(env.file_operator, VirtualLocalFileOperator)
        assert env.shell is not None
        await env.file_operator.write_file("notes.txt", "repo-a")
        await env.file_operator.write_file("/workspace/repo-b/notes.txt", "repo-b")
        repo_a_content = await env.file_operator.read_file("notes.txt")
        repo_b_content = await env.file_operator.read_file("/workspace/repo-b/notes.txt")
        exit_code, stdout, stderr = await env.shell.execute(
            'printf \'%s|%s\' "$(cat notes.txt)" "$(cat ../repo-b/notes.txt)"'
        )

    assert repo_a_content == "repo-a"
    assert repo_b_content == "repo-b"
    assert exit_code == 0
    assert stderr == ""
    assert stdout == "repo-a|repo-b"


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
    factory = DockerEnvironmentFactory(image="python:3.11", workspace_uid=1234, workspace_gid=2345)

    environment = factory.build(binding)

    assert isinstance(environment, SandboxEnvironment)
    assert isinstance(environment, ReusableSandboxEnvironment)
    assert environment.container_ref == build_session_sandbox_container_ref("session-1")
    assert binding.metadata["workspace_uid"] == 1234
    assert binding.metadata["workspace_gid"] == 2345


async def test_reusable_sandbox_environment_passes_workspace_identity_to_docker(tmp_path: Path) -> None:
    captured_run_kwargs: dict[str, object] = {}

    class FakeContainer:
        id = "container-123"

    class FakeContainers:
        def run(self, **kwargs: object) -> FakeContainer:
            captured_run_kwargs.update(kwargs)
            return FakeContainer()

    class FakeDockerClient:
        containers = FakeContainers()

    environment = ReusableSandboxEnvironment(
        mounts=[VirtualMount(host_path=tmp_path / "repo-a", virtual_path=Path("/workspace/repo-a"))],
        work_dir="/workspace/repo-a",
        image="python:3.11",
        container_ref="session-container",
        workspace_uid=1234,
        workspace_gid=2345,
    )
    environment._client = FakeDockerClient()

    container_id = await environment._create_container()

    assert container_id == "container-123"
    assert captured_run_kwargs["name"] == "session-container"
    assert captured_run_kwargs["working_dir"] == "/workspace/repo-a"
    assert captured_run_kwargs["environment"] == {
        "YA_CLAW_WORKSPACE_STARTUP_DIR": "/workspace/repo-a",
        "YA_CLAW_WORKSPACE_UID": "1234",
        "YA_CLAW_HOST_UID": "1234",
        "YA_CLAW_WORKSPACE_GID": "2345",
        "YA_CLAW_HOST_GID": "2345",
    }


def test_session_sandbox_metadata_preserves_workspace_identity(tmp_path: Path) -> None:
    provider = DockerWorkspaceProvider(tmp_path / "workspace-root", image="python:3.11")
    binding = provider.resolve("repo-a", metadata={"session_id": "session-1"})
    factory = DockerEnvironmentFactory(image="python:3.11", workspace_uid=0, workspace_gid=0)
    environment = factory.build(binding)
    environment._container_id = "container-123"

    metadata = build_session_sandbox_metadata(binding=binding, environment=environment)

    assert metadata is not None
    assert metadata["workspace_uid"] == 0
    assert metadata["workspace_gid"] == 0


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
