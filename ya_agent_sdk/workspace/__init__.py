"""Workspace isolation strategies.

This module provides the WorkspaceStrategy abstraction and built-in
implementations for creating isolated workspaces. Used by
Environment.fork() to create independent working directories for
subagent execution.

Strategies:
    - GitWorktreeStrategy: Fast, space-efficient isolation via git worktree.
      Changes can be merged back via git. Used by auto_detect_strategy.

Example::

    from ya_agent_sdk.workspace import GitWorktreeStrategy, auto_detect_strategy

    # Explicit strategy
    strategy = GitWorktreeStrategy()
    async with strategy.create(Path("/my/repo")) as ws:
        ...

    # Auto-detect (returns GitWorktreeStrategy or None)
    strategy = auto_detect_strategy(Path("/my/project"))
    if strategy:
        async with strategy.create(Path("/my/project")) as ws:
            ...
"""

from pathlib import Path

from ya_agent_sdk.workspace.base import WorkspaceStrategy
from ya_agent_sdk.workspace.git_worktree import GitWorktreeStrategy


def auto_detect_strategy(working_dir: Path | None) -> WorkspaceStrategy | None:
    """Auto-detect the best workspace strategy for a directory.

    Returns GitWorktreeStrategy if the directory is inside a git repository,
    otherwise None. Only GitWorktreeStrategy is used for auto-detection because
    copied workspaces cannot merge changes back to the parent.

    Args:
        working_dir: The directory to evaluate. Returns None if None.

    Returns:
        GitWorktreeStrategy if in a git repo, None otherwise.
    """
    if working_dir is None:
        return None
    git = GitWorktreeStrategy()
    if git.is_available(working_dir):
        return git
    return None


__all__ = [
    "GitWorktreeStrategy",
    "WorkspaceStrategy",
    "auto_detect_strategy",
]
