"""Workspace isolation strategy abstraction.

This module provides the WorkspaceStrategy ABC for creating isolated
workspace directories. Strategies define the mechanism (git worktree,
file copy, etc.) while Environment.fork() handles the lifecycle.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from pathlib import Path


class WorkspaceStrategy(ABC):
    """Strategy for creating an isolated workspace directory.

    Implementations define how to create a temporary, isolated copy of
    a working directory. The lifecycle is managed via async context manager:
    workspace is created on enter, cleaned up on exit.

    Example::

        strategy = GitWorktreeStrategy()
        if strategy.is_available(Path("/my/repo")):
            async with strategy.create(Path("/my/repo")) as ws_path:
                # ws_path is an isolated copy of /my/repo
                ...
            # Cleanup happens automatically
    """

    @abstractmethod
    def is_available(self, working_dir: Path) -> bool:
        """Check if this strategy can create a workspace for the given directory.

        Args:
            working_dir: The directory to create an isolated copy of.

        Returns:
            True if this strategy can handle the given directory.
        """
        ...

    @abstractmethod
    def create(self, working_dir: Path) -> AbstractAsyncContextManager[Path]:
        """Create an isolated workspace directory.

        Returns an async context manager that yields the path to the
        isolated workspace. Cleanup happens when the context exits.

        Args:
            working_dir: The source directory to isolate from.

        Yields:
            Path to the new isolated workspace directory.
        """
        ...
