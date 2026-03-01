"""Tests for SandboxEnvironment, DockerShell, and VirtualLocalFileOperator.

DockerShell tests require Docker to be installed.
Tests are marked with pytest.mark.docker to allow skipping when Docker is unavailable.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from y_agent_environment import FileOperationError, PathNotAllowedError

from ya_agent_sdk.environment.local import VirtualLocalFileOperator, VirtualMount

# Skip Docker-dependent tests if docker is not installed
docker = pytest.importorskip("docker")

from ya_agent_sdk.environment.sandbox import DockerShell, SandboxEnvironment  # noqa: E402

# --- VirtualMount Tests ---


def test_virtual_mount_requires_absolute_virtual_path() -> None:
    """Should reject relative virtual_path."""
    with pytest.raises(ValueError, match="virtual_path must be absolute"):
        VirtualMount(Path("/tmp"), Path("workspace"))  # noqa: S108


def test_virtual_mount_frozen() -> None:
    """Should be immutable."""
    mount = VirtualMount(Path("/tmp"), Path("/workspace"))  # noqa: S108
    with pytest.raises(AttributeError):
        mount.host_path = Path("/other")  # type: ignore[misc]


# --- VirtualLocalFileOperator Tests ---


def test_virtual_file_operator_init(tmp_path: Path) -> None:
    """Should initialize with mounts list."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )
    assert op._mounts[0].host_path == tmp_path
    assert op._mounts[0].virtual_path == Path("/workspace")
    assert op._default_path == Path("/workspace")


def test_virtual_file_operator_requires_at_least_one_mount() -> None:
    """Should reject empty mounts list."""
    with pytest.raises(ValueError, match="At least one mount is required"):
        VirtualLocalFileOperator(mounts=[])


def test_virtual_file_operator_custom_default_path(tmp_path: Path) -> None:
    """Should allow custom default_virtual_path."""
    op = VirtualLocalFileOperator(
        mounts=[
            VirtualMount(tmp_path / "a", Path("/workspace/a")),
            VirtualMount(tmp_path / "b", Path("/workspace/b")),
        ],
        default_virtual_path=Path("/workspace/b"),
    )
    assert op._default_path == Path("/workspace/b")


async def test_virtual_file_operator_read_write(tmp_path: Path) -> None:
    """Should read/write files using virtual paths mapped to host."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    # Write using relative path
    await op.write_file("test.txt", "hello world")
    assert (tmp_path / "test.txt").read_text() == "hello world"

    # Read back using relative path
    content = await op.read_file("test.txt")
    assert content == "hello world"


async def test_virtual_file_operator_absolute_virtual_paths(tmp_path: Path) -> None:
    """Should handle absolute virtual paths correctly."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    # Write using absolute virtual path
    await op.write_file("/workspace/abs_test.txt", "absolute")
    assert (tmp_path / "abs_test.txt").read_text() == "absolute"

    # Read using absolute virtual path
    content = await op.read_file("/workspace/abs_test.txt")
    assert content == "absolute"


async def test_virtual_file_operator_nested_paths(tmp_path: Path) -> None:
    """Should handle nested directory paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    await op.mkdir("subdir", parents=True)
    await op.write_file("subdir/nested.txt", "nested content")
    assert (tmp_path / "subdir" / "nested.txt").read_text() == "nested content"

    content = await op.read_file("subdir/nested.txt")
    assert content == "nested content"


async def test_virtual_file_operator_path_not_allowed(tmp_path: Path) -> None:
    """Should reject paths outside virtual mounts."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    with pytest.raises(PathNotAllowedError):
        await op.read_file("/etc/passwd")


async def test_virtual_file_operator_exists(tmp_path: Path) -> None:
    """Should check existence through virtual paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    assert not await op.exists("nope.txt")

    (tmp_path / "exists.txt").write_text("yes")
    assert await op.exists("exists.txt")
    assert await op.is_file("exists.txt")


async def test_virtual_file_operator_list_dir(tmp_path: Path) -> None:
    """Should list directory contents through virtual paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "subdir").mkdir()

    entries = await op.list_dir(".")
    assert "a.txt" in entries
    assert "b.txt" in entries
    assert "subdir" in entries


async def test_virtual_file_operator_glob(tmp_path: Path) -> None:
    """Should glob against host filesystem, return relative paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    (tmp_path / "file1.py").write_text("x")
    (tmp_path / "file2.py").write_text("y")
    (tmp_path / "file3.txt").write_text("z")

    results = await op.glob("*.py")
    assert len(results) == 2
    names = {Path(r).name for r in results}
    assert names == {"file1.py", "file2.py"}


async def test_virtual_file_operator_stat(tmp_path: Path) -> None:
    """Should return stat for virtual path."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    (tmp_path / "stat_test.txt").write_text("content")
    stat = await op.stat("stat_test.txt")
    assert stat["is_file"] is True
    assert stat["size"] == 7


async def test_virtual_file_operator_move_copy(tmp_path: Path) -> None:
    """Should move and copy files through virtual paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    await op.write_file("original.txt", "data")

    # Copy
    await op.copy("original.txt", "copied.txt")
    assert (tmp_path / "copied.txt").read_text() == "data"

    # Move
    await op.move("copied.txt", "moved.txt")
    assert not (tmp_path / "copied.txt").exists()
    assert (tmp_path / "moved.txt").read_text() == "data"


async def test_virtual_file_operator_delete(tmp_path: Path) -> None:
    """Should delete files through virtual paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    (tmp_path / "to_delete.txt").write_text("bye")
    assert await op.exists("to_delete.txt")

    await op.delete("to_delete.txt")
    assert not await op.exists("to_delete.txt")


async def test_virtual_file_operator_file_not_found(tmp_path: Path) -> None:
    """Should raise FileOperationError for missing files."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    with pytest.raises(FileOperationError, match="file not found"):
        await op.read_file("nonexistent.txt")


async def test_virtual_file_operator_context_instructions(tmp_path: Path) -> None:
    """Should generate instructions with virtual paths."""
    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
    )

    # Create some files so tree has content
    (tmp_path / "test.py").write_text("pass")

    instructions = await op.get_context_instructions()
    assert instructions is not None
    assert "/workspace" in instructions
    # Should NOT contain host path
    assert str(tmp_path) not in instructions


# --- Multi-mount Tests ---


async def test_virtual_file_operator_multi_mount(tmp_path: Path) -> None:
    """Should route operations to correct mount based on longest prefix."""
    host_a = tmp_path / "project"
    host_b = tmp_path / "config"
    host_a.mkdir()
    host_b.mkdir()

    op = VirtualLocalFileOperator(
        mounts=[
            VirtualMount(host_a, Path("/workspace/project")),
            VirtualMount(host_b, Path("/workspace/config")),
        ],
        default_virtual_path=Path("/workspace/project"),
    )

    # Write to project mount (relative resolves against default)
    await op.write_file("main.py", "print('hello')")
    assert (host_a / "main.py").read_text() == "print('hello')"
    assert not (host_b / "main.py").exists()

    # Write to config mount (absolute path)
    await op.write_file("/workspace/config/settings.json", '{"key": "val"}')
    assert (host_b / "settings.json").read_text() == '{"key": "val"}'
    assert not (host_a / "settings.json").exists()

    # Read back from both mounts
    assert await op.read_file("main.py") == "print('hello')"
    assert await op.read_file("/workspace/config/settings.json") == '{"key": "val"}'


async def test_virtual_file_operator_multi_mount_path_isolation(tmp_path: Path) -> None:
    """Should reject paths outside all mounts."""
    host_a = tmp_path / "a"
    host_a.mkdir()

    op = VirtualLocalFileOperator(
        mounts=[VirtualMount(host_a, Path("/workspace/a"))],
        default_virtual_path=Path("/workspace/a"),
    )

    with pytest.raises(PathNotAllowedError):
        await op.read_file("/workspace/b/secret.txt")


async def test_virtual_file_operator_multi_mount_context_instructions(tmp_path: Path) -> None:
    """Should generate file trees for each mount."""
    host_a = tmp_path / "project"
    host_b = tmp_path / "config"
    host_a.mkdir()
    host_b.mkdir()
    (host_a / "main.py").write_text("pass")
    (host_b / "settings.json").write_text("{}")

    op = VirtualLocalFileOperator(
        mounts=[
            VirtualMount(host_a, Path("/workspace/project")),
            VirtualMount(host_b, Path("/workspace/config")),
        ],
    )

    instructions = await op.get_context_instructions()
    assert instructions is not None
    assert "/workspace/project" in instructions
    assert "/workspace/config" in instructions
    assert "main.py" in instructions
    assert "settings.json" in instructions
    # Should NOT contain host paths
    assert str(host_a) not in instructions
    assert str(host_b) not in instructions


async def test_virtual_file_operator_multi_mount_longest_prefix(tmp_path: Path) -> None:
    """Should match longest virtual prefix for nested mounts."""
    host_root = tmp_path / "root"
    host_nested = tmp_path / "nested"
    host_root.mkdir()
    host_nested.mkdir()

    op = VirtualLocalFileOperator(
        mounts=[
            VirtualMount(host_root, Path("/workspace")),
            VirtualMount(host_nested, Path("/workspace/special")),
        ],
    )

    # /workspace/special/file.txt should go to host_nested, not host_root/special/
    await op.write_file("/workspace/special/file.txt", "nested mount")
    assert (host_nested / "file.txt").read_text() == "nested mount"
    assert not (host_root / "special").exists()

    # /workspace/other.txt should go to host_root
    await op.write_file("/workspace/other.txt", "root mount")
    assert (host_root / "other.txt").read_text() == "root mount"


async def test_virtual_file_operator_multi_mount_glob(tmp_path: Path) -> None:
    """Should glob within the default mount for relative patterns."""
    host_a = tmp_path / "a"
    host_b = tmp_path / "b"
    host_a.mkdir()
    host_b.mkdir()
    (host_a / "file1.py").write_text("a")
    (host_b / "file2.py").write_text("b")

    op = VirtualLocalFileOperator(
        mounts=[
            VirtualMount(host_a, Path("/workspace/a")),
            VirtualMount(host_b, Path("/workspace/b")),
        ],
        default_virtual_path=Path("/workspace/a"),
    )

    # Relative glob searches default mount
    results = await op.glob("*.py")
    assert len(results) == 1
    assert "file1.py" in results[0]


# --- DockerShell Tests ---


def test_docker_shell_initialization() -> None:
    """Should initialize with container_id and container_workdir."""

    shell = DockerShell(
        container_id="test123",
        container_workdir="/app",
        default_timeout=60.0,
    )
    assert shell._container_id == "test123"
    assert shell._container_workdir == "/app"
    assert shell._default_timeout == 60.0


async def test_docker_shell_execute_empty_command() -> None:
    """Should raise error for empty command."""
    from y_agent_environment import ShellExecutionError

    shell = DockerShell(container_id="test123")
    with pytest.raises(ShellExecutionError):
        await shell.execute("")


async def test_docker_shell_execute_success() -> None:
    """Should execute command and return results."""
    shell = DockerShell(container_id="test123")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(
        exit_code=0,
        output=(b"hello\n", b""),
    )

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    shell._client = mock_client

    code, stdout, stderr = await shell.execute("echo hello")

    assert code == 0
    assert stdout == "hello\n"
    assert stderr == ""
    mock_container.exec_run.assert_called_once()


async def test_docker_shell_execute_with_cwd() -> None:
    """Should pass workdir to docker exec."""
    shell = DockerShell(container_id="test123", container_workdir="/workspace")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(
        exit_code=0,
        output=(b"", b""),
    )

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    shell._client = mock_client

    await shell.execute("ls", cwd="subdir")

    mock_container.exec_run.assert_called_once()
    call_kwargs = mock_container.exec_run.call_args[1]
    assert call_kwargs["workdir"] == "/workspace/subdir"


async def test_docker_shell_execute_with_absolute_cwd() -> None:
    """Should use absolute cwd as-is."""
    shell = DockerShell(container_id="test123", container_workdir="/workspace")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(
        exit_code=0,
        output=(b"", b""),
    )

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    shell._client = mock_client

    await shell.execute("ls", cwd="/tmp")  # noqa: S108

    call_kwargs = mock_container.exec_run.call_args[1]
    assert call_kwargs["workdir"] == "/tmp"  # noqa: S108


async def test_docker_shell_execute_with_env() -> None:
    """Should pass environment variables."""
    shell = DockerShell(container_id="test123")

    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(
        exit_code=0,
        output=(b"", b""),
    )

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    shell._client = mock_client

    await shell.execute("env", env={"FOO": "bar"})

    call_kwargs = mock_container.exec_run.call_args[1]
    assert call_kwargs["environment"] == {"FOO": "bar"}


async def test_docker_shell_get_context_instructions() -> None:
    """Should return docker-specific instructions."""
    shell = DockerShell(
        container_id="abc123",
        container_workdir="/workspace",
        default_timeout=30.0,
    )
    instructions = await shell.get_context_instructions()

    assert instructions is not None
    assert "docker-exec" in instructions
    assert "abc123" in instructions
    assert "/workspace" in instructions


# --- SandboxEnvironment Tests ---


def test_sandbox_environment_requires_mounts() -> None:
    """Should raise ValueError if mounts is empty."""
    with pytest.raises(ValueError, match="At least one mount is required"):
        SandboxEnvironment(mounts=[], image="python:3.11")


def test_sandbox_environment_requires_shell_or_docker() -> None:
    """Should raise ValueError if no shell backend can be determined."""
    with pytest.raises(ValueError, match="Either shell, container_id, or image must be provided"):
        SandboxEnvironment(mounts=[VirtualMount(Path("/tmp"), Path("/workspace"))])  # noqa: S108


def test_sandbox_environment_initialization_with_container_id(tmp_path: Path) -> None:
    """Should initialize with existing container_id."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/app"))],
        container_id="existing123",
        cleanup_on_exit=False,
    )
    assert env._container_id == "existing123"
    assert env._work_dir == "/app"
    assert env._cleanup_on_exit is False


def test_sandbox_environment_initialization_with_image(tmp_path: Path) -> None:
    """Should initialize with image for new container."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        image="python:3.11",
        cleanup_on_exit=True,
    )
    assert env._image == "python:3.11"
    assert env._cleanup_on_exit is True


def test_sandbox_environment_initialization_with_custom_shell(tmp_path: Path) -> None:
    """Should initialize with custom shell backend."""
    mock_shell = MagicMock(spec=["execute", "get_context_instructions", "close"])
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        shell=mock_shell,
    )
    assert env._custom_shell is mock_shell


def test_sandbox_environment_custom_work_dir(tmp_path: Path) -> None:
    """Should use custom work_dir when provided."""
    env = SandboxEnvironment(
        mounts=[
            VirtualMount(tmp_path / "a", Path("/workspace/a")),
            VirtualMount(tmp_path / "b", Path("/workspace/b")),
        ],
        work_dir="/workspace/b",
        image="python:3.11",
    )
    assert env._work_dir == "/workspace/b"


def test_sandbox_environment_default_work_dir(tmp_path: Path) -> None:
    """Should default work_dir to first mount's virtual_path."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/myworkspace"))],
        image="python:3.11",
    )
    assert env._work_dir == "/myworkspace"


async def test_sandbox_environment_properties_before_enter(tmp_path: Path) -> None:
    """Should raise error when accessing properties before entering context."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="test123",
    )
    with pytest.raises(RuntimeError, match="Environment not entered"):
        _ = env.file_operator
    with pytest.raises(RuntimeError, match="Environment not entered"):
        _ = env.shell


async def test_sandbox_environment_enter_with_existing_container(tmp_path: Path) -> None:
    """Should verify container and create operators on enter."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="existing123",
        cleanup_on_exit=False,
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        assert env.file_operator is not None
        assert env.shell is not None
        # File operator should use virtual path
        assert env._file_operator._default_path == Path("/workspace")
        assert env._shell._container_id == "existing123"
        assert env._shell._container_workdir == "/workspace"

    # Verify container was not stopped (cleanup_on_exit=False)
    assert mock_container.stop.call_count == 0


async def test_sandbox_environment_enter_creates_new_container(tmp_path: Path) -> None:
    """Should create container when entering with image."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        image="python:3.11",
        cleanup_on_exit=True,
    )

    mock_container = MagicMock()
    mock_container.id = "new123"

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        assert env._container_id == "new123"
        assert env._created_container is True

    # Verify container was stopped and removed (cleanup_on_exit=True)
    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()


async def test_sandbox_environment_file_operator_uses_virtual_paths(tmp_path: Path) -> None:
    """Should configure file operator with virtual paths mapped to host_dir."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="test123",
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        # Write a file using file operator (relative path)
        await env.file_operator.write_file("test.txt", "hello")
        # Actual file should be on host
        assert (tmp_path / "test.txt").read_text() == "hello"

        # Read back using absolute virtual path
        content = await env.file_operator.read_file("/workspace/test.txt")
        assert content == "hello"


async def test_sandbox_environment_multi_mount(tmp_path: Path) -> None:
    """Should support multiple mounts."""
    host_a = tmp_path / "project"
    host_b = tmp_path / "config"
    host_a.mkdir()
    host_b.mkdir()

    env = SandboxEnvironment(
        mounts=[
            VirtualMount(host_a, Path("/workspace/project")),
            VirtualMount(host_b, Path("/workspace/config")),
        ],
        work_dir="/workspace/project",
        container_id="test123",
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        # Write to project mount (default, relative path)
        await env.file_operator.write_file("main.py", "code")
        assert (host_a / "main.py").read_text() == "code"

        # Write to config mount (absolute path)
        await env.file_operator.write_file("/workspace/config/app.json", "{}")
        assert (host_b / "app.json").read_text() == "{}"


async def test_sandbox_environment_tmp_dir_enabled(tmp_path: Path) -> None:
    """Should create tmp directory when enabled."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="test123",
        enable_tmp_dir=True,
        tmp_base_dir=tmp_path,
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        assert env.tmp_dir is not None
        assert env.tmp_dir.exists()
        tmp_dir = env.tmp_dir

    # Tmp dir should be cleaned up after exit
    assert not tmp_dir.exists()


async def test_sandbox_environment_tmp_dir_disabled(tmp_path: Path) -> None:
    """Should not create tmp directory when disabled."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="test123",
        enable_tmp_dir=False,
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        assert env.tmp_dir is None


async def test_sandbox_environment_get_context_instructions(tmp_path: Path) -> None:
    """Should return instructions with virtual paths, no mount-mapping."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="test123",
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        instructions = await env.get_context_instructions()

        assert instructions is not None
        assert "/workspace" in instructions
        # Should NOT have mount-mapping (paths are symmetric now)
        assert "mount-mapping" not in instructions
        # Should NOT expose host path
        assert str(tmp_path) not in instructions


async def test_sandbox_environment_cross_session_sharing(tmp_path: Path) -> None:
    """Should support cross-session container sharing with cleanup_on_exit=False."""
    mount = VirtualMount(tmp_path, Path("/workspace"))

    # First session
    env1 = SandboxEnvironment(
        mounts=[mount],
        container_id="shared123",
        cleanup_on_exit=False,
    )

    mock_container = MagicMock()
    mock_container.status = "running"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env1._client = mock_client

    async with env1:
        await env1.file_operator.write_file("session1.txt", "from session 1")

    assert mock_container.stop.call_count == 0

    # Second session
    env2 = SandboxEnvironment(
        mounts=[mount],
        container_id="shared123",
        cleanup_on_exit=False,
    )
    env2._client = mock_client

    async with env2:
        content = await env2.file_operator.read_file("session1.txt")
        assert content == "from session 1"


async def test_sandbox_environment_with_custom_shell(tmp_path: Path) -> None:
    """Should use custom shell backend when provided."""
    mock_shell = MagicMock()
    mock_shell.execute = MagicMock(return_value=(0, "output", ""))
    mock_shell.get_context_instructions = MagicMock(return_value="custom shell")
    mock_shell.close = MagicMock()

    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        shell=mock_shell,
    )

    async with env:
        assert env.shell is mock_shell
        await env.file_operator.write_file("test.txt", "custom shell test")
        assert (tmp_path / "test.txt").read_text() == "custom shell test"
        assert env._created_container is False


async def test_sandbox_environment_create_container_mounts_tmp_dir(tmp_path: Path) -> None:
    """Should mount tmp_dir into Docker container when creating a new one."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        image="python:3.11",
        enable_tmp_dir=True,
        tmp_base_dir=tmp_path,
    )

    mock_container = MagicMock()
    mock_container.id = "new123"

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        # Verify containers.run was called with tmp_dir in volumes
        call_kwargs = mock_client.containers.run.call_args[1]
        volumes = call_kwargs["volumes"]
        # Should have 2 volumes: the mount + tmp_dir
        assert len(volumes) == 2
        # tmp_dir should be mounted at the same path inside container
        assert env.tmp_dir is not None
        assert str(env.tmp_dir) in volumes


async def test_sandbox_environment_auto_start_stopped_container(tmp_path: Path) -> None:
    """Should auto-start a stopped container instead of raising error."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="stopped123",
        cleanup_on_exit=False,
    )

    mock_container = MagicMock()
    # Simulate: first reload returns "exited", after start() returns "running"
    mock_container.status = "exited"

    def _reload_side_effect() -> None:
        # After start() is called, status changes to running
        if mock_container.start.called:
            mock_container.status = "running"

    mock_container.reload.side_effect = _reload_side_effect

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    async with env:
        # Should have auto-started the container
        mock_container.start.assert_called_once()
        assert env.file_operator is not None
        assert env.shell is not None


async def test_sandbox_environment_unrecoverable_container_state(tmp_path: Path) -> None:
    """Should raise error for containers in unrecoverable state."""
    env = SandboxEnvironment(
        mounts=[VirtualMount(tmp_path, Path("/workspace"))],
        container_id="dead123",
        cleanup_on_exit=False,
    )

    mock_container = MagicMock()
    mock_container.status = "removing"

    mock_client = MagicMock()
    mock_client.containers.get.return_value = mock_container
    env._client = mock_client

    with pytest.raises(RuntimeError, match="unrecoverable state"):
        async with env:
            pass
