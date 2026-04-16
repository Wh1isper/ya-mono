"""Tests for subagent_wrapper functionality."""

from contextlib import asynccontextmanager
from typing import Any

import pytest
from ya_agent_sdk.context import AgentContext, SubagentWrapper
from ya_agent_sdk.environment.local import LocalEnvironment


@pytest.fixture
async def env() -> LocalEnvironment:
    """Create a test environment."""
    async with LocalEnvironment() as environment:
        yield environment


def test_subagent_wrapper_type_alias() -> None:
    """SubagentWrapper should be a Callable type alias."""
    assert SubagentWrapper is not None

    @asynccontextmanager
    async def my_wrapper(agent_name: str, agent_id: str, metadata: dict[str, Any]):
        yield

    wrapper: SubagentWrapper = my_wrapper
    assert callable(wrapper)


async def test_context_without_subagent_wrapper(env: LocalEnvironment) -> None:
    """Context without subagent_wrapper should have it as None."""
    async with AgentContext(env=env) as ctx:
        assert ctx.subagent_wrapper is None


async def test_context_with_subagent_wrapper(env: LocalEnvironment) -> None:
    """Context with subagent_wrapper should store it correctly."""
    call_log: list[dict[str, Any]] = []

    @asynccontextmanager
    async def my_wrapper(agent_name: str, agent_id: str, metadata: dict[str, Any]):
        call_log.append({"agent_name": agent_name, "agent_id": agent_id, "metadata": metadata})
        yield

    async with AgentContext(env=env, subagent_wrapper=my_wrapper) as ctx:
        assert ctx.subagent_wrapper is my_wrapper

        # Test it works as a context manager
        wrapper_metadata = ctx.get_wrapper_metadata()
        async with ctx.subagent_wrapper("debugger", "debugger-abc1", wrapper_metadata):
            pass

        assert len(call_log) == 1
        assert call_log[0]["agent_name"] == "debugger"
        assert call_log[0]["agent_id"] == "debugger-abc1"
        assert call_log[0]["metadata"]["run_id"] == ctx.run_id


async def test_subagent_wrapper_inherited_by_subagent_context(env: LocalEnvironment) -> None:
    """Subagent context should inherit subagent_wrapper via model_copy."""

    @asynccontextmanager
    async def my_wrapper(agent_name: str, agent_id: str, metadata: dict[str, Any]):
        yield

    async with AgentContext(env=env, subagent_wrapper=my_wrapper) as ctx:
        async with ctx.create_subagent_context("child", agent_id="child-001") as sub_ctx:
            # subagent_wrapper should be inherited
            assert sub_ctx.subagent_wrapper is my_wrapper


async def test_subagent_wrapper_not_serialized(env: LocalEnvironment) -> None:
    """subagent_wrapper should be excluded from serialization."""

    @asynccontextmanager
    async def my_wrapper(agent_name: str, agent_id: str, metadata: dict[str, Any]):
        yield

    async with AgentContext(env=env, subagent_wrapper=my_wrapper) as ctx:
        state = ctx.export_state()
        # The wrapper should not appear in the serialized state
        state_dict = state.model_dump()
        assert "subagent_wrapper" not in state_dict
