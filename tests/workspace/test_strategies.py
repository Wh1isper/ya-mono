"""Tests for workspace isolation strategies."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ya_agent_sdk.workspace import GitWorktreeStrategy, WorkspaceStrategy, auto_detect_strategy

# =============================================================================
# WorkspaceStrategy ABC
# =============================================================================


def test_workspace_strategy_is_abstract() -> None:
    """WorkspaceStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        WorkspaceStrategy()  # type: ignore[abstract]


# =============================================================================
# GitWorktreeStrategy
# =============================================================================


def _init_git_repo(path: Path) -> None:
    """Create a git repo with an initial commit at the given path."""
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


def test_git_worktree_is_available_in_repo(tmp_path: Path) -> None:
    """GitWorktreeStrategy.is_available returns True inside a git repo."""
    _init_git_repo(tmp_path)
    strategy = GitWorktreeStrategy()
    assert strategy.is_available(tmp_path) is True


def test_git_worktree_not_available_outside_repo(tmp_path: Path) -> None:
    """GitWorktreeStrategy.is_available returns False outside a git repo."""
    strategy = GitWorktreeStrategy()
    assert strategy.is_available(tmp_path) is False


@pytest.mark.anyio
async def test_git_worktree_create(tmp_path: Path) -> None:
    """GitWorktreeStrategy.create produces a valid worktree."""
    _init_git_repo(tmp_path)
    strategy = GitWorktreeStrategy()

    async with strategy.create(tmp_path) as ws_path:
        assert ws_path.exists()
        assert ws_path != tmp_path
        # The README from the initial commit should exist
        assert (ws_path / "README.md").exists()
        assert (ws_path / "README.md").read_text() == "hello"
        # Should be listed as a worktree
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert str(ws_path) in result.stdout

    # After exit, worktree should be cleaned up
    assert not ws_path.exists()


@pytest.mark.anyio
async def test_git_worktree_isolation(tmp_path: Path) -> None:
    """Files created in worktree do not appear in the main repo."""
    _init_git_repo(tmp_path)
    strategy = GitWorktreeStrategy()

    async with strategy.create(tmp_path) as ws_path:
        (ws_path / "new_file.txt").write_text("isolated")
        assert (ws_path / "new_file.txt").exists()

    # Main repo should not have the file
    assert not (tmp_path / "new_file.txt").exists()


@pytest.mark.anyio
async def test_git_worktree_fails_outside_repo(tmp_path: Path) -> None:
    """GitWorktreeStrategy.create raises RuntimeError outside a git repo."""
    strategy = GitWorktreeStrategy()
    with pytest.raises(RuntimeError, match="Not a git repository"):
        async with strategy.create(tmp_path):
            pass  # pragma: no cover


# =============================================================================
# auto_detect_strategy
# =============================================================================


def test_auto_detect_returns_none_for_none() -> None:
    """auto_detect_strategy returns None when working_dir is None."""
    assert auto_detect_strategy(None) is None


def test_auto_detect_returns_git_in_repo(tmp_path: Path) -> None:
    """auto_detect_strategy returns GitWorktreeStrategy inside a git repo."""
    _init_git_repo(tmp_path)
    strategy = auto_detect_strategy(tmp_path)
    assert isinstance(strategy, GitWorktreeStrategy)


def test_auto_detect_returns_none_outside_repo(tmp_path: Path) -> None:
    """auto_detect_strategy returns None outside a git repo."""
    strategy = auto_detect_strategy(tmp_path)
    assert strategy is None
