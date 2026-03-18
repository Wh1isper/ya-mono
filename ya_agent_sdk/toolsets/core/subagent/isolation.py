"""Workspace isolation helpers for subagent execution.

Provides the resolve_env async context manager that transparently
handles environment forking when isolated execution is requested.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from y_agent_environment import Environment

from ya_agent_sdk._logger import get_logger

logger = get_logger(__name__)

# Cache environment types that are known to not support fork().
# Prevents repeated NotImplementedError + warning on every subagent call.
_fork_unsupported_types: set[type] = set()


@asynccontextmanager
async def resolve_env(
    env: Environment | None,
    isolated: bool,
) -> AsyncIterator[Environment | None]:
    """Resolve environment for subagent execution.

    When isolated=True, forks the environment to create an independent
    workspace. If the environment does not support forking, falls back
    to the original environment gracefully:

    - First call: attempts fork, caches the failure, logs a warning.
    - Subsequent calls: skips fork silently for the same environment type.

    This design ensures custom Environment subclasses that don't implement
    fork() work without noise or performance overhead.

    Args:
        env: The parent environment (may be None).
        isolated: Whether to create an isolated workspace.

    Yields:
        The effective environment (forked or original).
    """
    if not isolated or env is None:
        yield env
        return

    env_type = type(env)

    # Fast path: skip fork for known-unsupported environment types
    if env_type in _fork_unsupported_types:
        yield env
        return

    try:
        async with env.fork() as forked:
            logger.info("Forked environment for isolated subagent execution")
            yield forked
    except NotImplementedError:
        _fork_unsupported_types.add(env_type)
        logger.warning(
            "%s does not support fork() -- subagents will share the parent environment. "
            "Implement fork() on your Environment subclass to enable workspace isolation.",
            env_type.__name__,
        )
        yield env
