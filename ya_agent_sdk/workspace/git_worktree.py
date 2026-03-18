"""Git worktree workspace strategy.

Creates isolated workspaces using ``git worktree add --detach``.
The worktree is removed automatically when the context manager exits.
"""

import asyncio
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from ya_agent_sdk._logger import get_logger
from ya_agent_sdk.workspace.base import WorkspaceStrategy

logger = get_logger(__name__)


def _get_git_root(working_dir: Path) -> Path | None:
    """Get the git repository root for the given directory.

    Returns None if the directory is not inside a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=str(working_dir),
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


async def _run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a git command asynchronously.

    Args:
        args: Git subcommand and arguments (without leading "git").
        cwd: Working directory for the command.

    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    return (
        process.returncode or 0,
        stdout_bytes.decode("utf-8", errors="replace").strip(),
        stderr_bytes.decode("utf-8", errors="replace").strip(),
    )


class GitWorktreeStrategy(WorkspaceStrategy):
    """Create isolated workspaces using git worktree.

    Uses ``git worktree add <path> --detach`` to create a worktree
    that shares the git object store with the main repository but has
    its own working directory. The worktree is removed on cleanup.

    This is the preferred strategy for git repositories as it is fast
    (no file copying) and space-efficient (shared object store).

    Example::

        strategy = GitWorktreeStrategy()
        async with strategy.create(Path("/my/repo")) as ws:
            # ws is a detached worktree at the same commit
            ...
    """

    def __init__(self, *, tmp_prefix: str = "ya_ws_git_") -> None:
        """Initialize GitWorktreeStrategy.

        Args:
            tmp_prefix: Prefix for temporary worktree directories.
        """
        self._tmp_prefix = tmp_prefix

    def is_available(self, working_dir: Path) -> bool:
        """Check if working_dir is inside a git repository with commits."""
        return _get_git_root(working_dir) is not None

    @asynccontextmanager
    async def create(self, working_dir: Path) -> AsyncIterator[Path]:
        """Create an isolated git worktree.

        Creates a detached worktree at the current HEAD commit.
        The worktree is forcefully removed when the context exits.

        Args:
            working_dir: Directory inside the git repository.

        Yields:
            Path to the worktree directory.

        Raises:
            RuntimeError: If git worktree creation fails.
        """
        git_root = _get_git_root(working_dir)
        if git_root is None:
            raise RuntimeError(f"Not a git repository: {working_dir}")

        ws_dir = Path(tempfile.mkdtemp(prefix=self._tmp_prefix))

        try:
            # Remove the empty tmpdir first -- git worktree add requires a non-existent path
            ws_dir.rmdir()

            rc, _stdout, stderr = await _run_git(
                ["worktree", "add", str(ws_dir), "--detach"],
                cwd=git_root,
            )
            if rc != 0:
                raise RuntimeError(f"git worktree add failed (rc={rc}): {stderr}")

            logger.info("Created git worktree: %s", ws_dir)
            yield ws_dir

        finally:
            # Clean up worktree
            rc, _, stderr = await _run_git(
                ["worktree", "remove", "--force", str(ws_dir)],
                cwd=git_root,
            )
            if rc != 0:
                logger.warning("git worktree remove failed (rc=%d): %s -- falling back to rmtree", rc, stderr)
                shutil.rmtree(ws_dir, ignore_errors=True)
            else:
                logger.info("Removed git worktree: %s", ws_dir)
