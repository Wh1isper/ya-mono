"""Tests for subagent workspace isolation."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.subagents.config import IsolationMode, SubagentConfig, parse_subagent_markdown
from ya_agent_sdk.toolsets.core.subagent.factory import create_subagent_call_func
from ya_agent_sdk.toolsets.core.subagent.isolation import resolve_env

# =============================================================================
# resolve_env tests
# =============================================================================


@pytest.mark.anyio
async def test_resolve_env_passthrough_when_not_isolated() -> None:
    """resolve_env yields the same env when isolated=False."""
    env = MagicMock()
    async with resolve_env(env, isolated=False) as result:
        assert result is env


@pytest.mark.anyio
async def test_resolve_env_passthrough_when_env_is_none() -> None:
    """resolve_env yields None when env is None, even if isolated=True."""
    async with resolve_env(None, isolated=True) as result:
        assert result is None


@pytest.mark.anyio
async def test_resolve_env_forks_when_isolated() -> None:
    """resolve_env calls env.fork() when isolated=True."""
    forked_env = MagicMock()

    env = MagicMock()
    fork_cm = AsyncMock()
    fork_cm.__aenter__ = AsyncMock(return_value=forked_env)
    fork_cm.__aexit__ = AsyncMock(return_value=None)
    env.fork.return_value = fork_cm

    async with resolve_env(env, isolated=True) as result:
        assert result is forked_env

    env.fork.assert_called_once()


@pytest.mark.anyio
async def test_resolve_env_fallback_when_fork_not_supported() -> None:
    """resolve_env falls back to original env when fork is not supported."""
    from ya_agent_sdk.toolsets.core.subagent.isolation import _fork_unsupported_types

    env = MagicMock()
    env_type = type(env)
    env.fork.side_effect = NotImplementedError("no fork support")

    # Clean cache for this test
    _fork_unsupported_types.discard(env_type)

    async with resolve_env(env, isolated=True) as result:
        assert result is env

    # Type should now be cached
    assert env_type in _fork_unsupported_types

    # Clean up
    _fork_unsupported_types.discard(env_type)


@pytest.mark.anyio
async def test_resolve_env_skips_fork_for_cached_type() -> None:
    """resolve_env skips fork entirely for cached unsupported types."""
    from ya_agent_sdk.toolsets.core.subagent.isolation import _fork_unsupported_types

    env = MagicMock()
    env_type = type(env)

    # Pre-populate cache
    _fork_unsupported_types.add(env_type)

    async with resolve_env(env, isolated=True) as result:
        assert result is env

    # fork() should never have been called
    env.fork.assert_not_called()

    # Clean up
    _fork_unsupported_types.discard(env_type)


# =============================================================================
# create_subagent_call_func signature tests
# =============================================================================


def test_call_func_never_mode_has_no_isolated_param() -> None:
    """NEVER mode: generated call_func does not have 'isolated' parameter."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test")
    call_func = create_subagent_call_func(agent, isolation=IsolationMode.NEVER)

    sig = inspect.signature(call_func)
    assert "isolated" not in sig.parameters
    assert "prompt" in sig.parameters
    assert "agent_id" in sig.parameters


def test_call_func_always_mode_has_no_isolated_param() -> None:
    """ALWAYS mode: generated call_func does not have 'isolated' parameter."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test")
    call_func = create_subagent_call_func(agent, isolation=IsolationMode.ALWAYS)

    sig = inspect.signature(call_func)
    assert "isolated" not in sig.parameters


def test_call_func_optional_mode_has_isolated_param() -> None:
    """OPTIONAL mode: generated call_func has 'isolated' parameter with default False."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test")
    call_func = create_subagent_call_func(agent, isolation=IsolationMode.OPTIONAL)

    sig = inspect.signature(call_func)
    assert "isolated" in sig.parameters
    param = sig.parameters["isolated"]
    assert param.default is False


def test_call_func_default_is_always_mode() -> None:
    """Default isolation mode is ALWAYS."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test")
    call_func = create_subagent_call_func(agent)

    sig = inspect.signature(call_func)
    assert "isolated" not in sig.parameters


# =============================================================================
# SubagentConfig isolation field tests
# =============================================================================


def test_config_isolation_default_is_always() -> None:
    """SubagentConfig.isolation defaults to ALWAYS."""
    config = SubagentConfig(
        name="test",
        description="test",
        system_prompt="test",
    )
    assert config.isolation == IsolationMode.ALWAYS


def test_config_isolation_from_frontmatter() -> None:
    """SubagentConfig parses isolation from YAML frontmatter."""
    config = parse_subagent_markdown("""---
name: executor
description: Execute tasks
isolation: optional
---
You are an executor.
""")
    assert config.isolation == IsolationMode.OPTIONAL


def test_config_isolation_always_from_frontmatter() -> None:
    """SubagentConfig parses isolation: always from frontmatter."""
    config = parse_subagent_markdown("""---
name: worker
description: Isolated worker
isolation: always
---
You work in isolation.
""")
    assert config.isolation == IsolationMode.ALWAYS


def test_config_isolation_missing_defaults_to_always() -> None:
    """SubagentConfig defaults to ALWAYS when isolation is not in frontmatter."""
    config = parse_subagent_markdown("""---
name: reader
description: Read code
---
You read code.
""")
    assert config.isolation == IsolationMode.ALWAYS


# =============================================================================
# Integration: fork is called for ALWAYS mode
# =============================================================================


@pytest.mark.anyio
async def test_always_mode_calls_resolve_env_with_true() -> None:
    """ALWAYS mode calls _execute_subagent with should_isolate=True."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test_agent")
    call_func = create_subagent_call_func(agent, isolation=IsolationMode.ALWAYS)

    with patch("ya_agent_sdk.toolsets.core.subagent.factory._execute_subagent") as mock_execute:
        mock_execute.return_value = "<id>test</id>\n<response>ok</response>\n"

        mock_self = MagicMock()
        mock_ctx = MagicMock()

        await call_func(mock_self, mock_ctx, "do something")

        mock_execute.assert_called_once()
        # should_isolate is the last positional arg
        call_args = mock_execute.call_args
        assert call_args[0][-1] is True  # should_isolate


@pytest.mark.anyio
async def test_never_mode_calls_resolve_env_with_false() -> None:
    """NEVER mode calls _execute_subagent with should_isolate=False."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test_agent")
    call_func = create_subagent_call_func(agent, isolation=IsolationMode.NEVER)

    with patch("ya_agent_sdk.toolsets.core.subagent.factory._execute_subagent") as mock_execute:
        mock_execute.return_value = "<id>test</id>\n<response>ok</response>\n"

        mock_self = MagicMock()
        mock_ctx = MagicMock()

        await call_func(mock_self, mock_ctx, "do something")

        call_args = mock_execute.call_args
        assert call_args[0][-1] is False  # should_isolate


@pytest.mark.anyio
async def test_optional_mode_passes_isolated_flag() -> None:
    """OPTIONAL mode passes the isolated flag from the tool call."""
    agent: Agent[AgentContext, str] = Agent("test", deps_type=AgentContext, name="test_agent")
    call_func = create_subagent_call_func(agent, isolation=IsolationMode.OPTIONAL)

    with patch("ya_agent_sdk.toolsets.core.subagent.factory._execute_subagent") as mock_execute:
        mock_execute.return_value = "<id>test</id>\n<response>ok</response>\n"

        mock_self = MagicMock()
        mock_ctx = MagicMock()

        # Call with isolated=True
        await call_func(mock_self, mock_ctx, "do something", isolated=True)
        call_args = mock_execute.call_args
        assert call_args[0][-1] is True

        mock_execute.reset_mock()

        # Call with isolated=False (default)
        await call_func(mock_self, mock_ctx, "do something")
        call_args = mock_execute.call_args
        assert call_args[0][-1] is False
