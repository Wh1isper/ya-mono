"""Tests for LocalEnvironment.fork() workspace isolation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.workspace import GitWorktreeStrategy


def _init_git_repo(path: Path) -> None:
    """Create a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    (path / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


@pytest.mark.anyio
async def test_fork_with_git_worktree_strategy(tmp_path: Path) -> None:
    """LocalEnvironment.fork() works with GitWorktreeStrategy."""
    _init_git_repo(tmp_path)

    async with LocalEnvironment(default_path=tmp_path, fork_strategy=GitWorktreeStrategy()) as env:
        async with env.fork() as forked:
            # Forked env should have its own file_operator
            assert forked.file_operator is not None
            assert forked.shell is not None

            content = await forked.file_operator.read_file("README.md")
            assert content == "hello"

            # Write in forked env should not affect parent
            await forked.file_operator.write_file("new.txt", "isolated")
            assert await forked.file_operator.exists("new.txt")

        # Parent should not have the new file
        assert not await env.file_operator.exists("new.txt")


@pytest.mark.anyio
async def test_fork_auto_detect_git(tmp_path: Path) -> None:
    """LocalEnvironment.fork() auto-detects GitWorktreeStrategy in git repos."""
    _init_git_repo(tmp_path)

    async with LocalEnvironment(default_path=tmp_path) as env:
        # No explicit strategy -- should auto-detect git
        async with env.fork() as forked:
            content = await forked.file_operator.read_file("README.md")
            assert content == "hello"


@pytest.mark.anyio
async def test_fork_auto_detect_no_git_raises(tmp_path: Path) -> None:
    """LocalEnvironment.fork() raises NotImplementedError outside git repos."""
    (tmp_path / "file.txt").write_text("content")

    async with LocalEnvironment(default_path=tmp_path) as env:
        with pytest.raises(NotImplementedError, match="Cannot fork"):
            async with env.fork():
                pass  # pragma: no cover


@pytest.mark.anyio
async def test_fork_no_default_path_raises() -> None:
    """LocalEnvironment.fork() raises when no default_path and no strategy."""
    async with LocalEnvironment(enable_tmp_dir=False) as env:
        with pytest.raises(NotImplementedError, match="Cannot fork"):
            async with env.fork():
                pass  # pragma: no cover


@pytest.mark.anyio
async def test_fork_cleanup_on_exit(tmp_path: Path) -> None:
    """Forked environment is fully cleaned up after context exit."""
    _init_git_repo(tmp_path)

    forked_path: Path | None = None

    async with LocalEnvironment(default_path=tmp_path, fork_strategy=GitWorktreeStrategy()) as env:
        async with env.fork() as forked:
            assert forked.file_operator is not None
            forked_path = forked.file_operator._default_path

        # After exit, the workspace dir should be gone
        assert forked_path is not None
        assert not forked_path.exists()


@pytest.mark.anyio
async def test_fork_independent_shell(tmp_path: Path) -> None:
    """Forked environment has an independent shell with its own cwd."""
    _init_git_repo(tmp_path)
    (tmp_path / "marker.txt").write_text("parent")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add marker"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )

    async with LocalEnvironment(default_path=tmp_path, fork_strategy=GitWorktreeStrategy()) as env:
        async with env.fork() as forked:
            # Shell should work in the forked workspace
            rc, stdout, _ = await forked.shell.execute("cat marker.txt")
            assert rc == 0
            assert stdout.strip() == "parent"

            # Create a file via shell in forked env
            await forked.shell.execute("echo 'forked' > shell_file.txt")
            assert await forked.file_operator.exists("shell_file.txt")

        # Parent should not have the shell-created file
        assert not (tmp_path / "shell_file.txt").exists()
