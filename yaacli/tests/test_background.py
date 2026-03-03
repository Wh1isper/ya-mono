"""Tests for background task manager and background delegate tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext
from yaacli.background import BACKGROUND_MANAGER_KEY, BackgroundTaskManager
from yaacli.environment import TUIEnvironment
from yaacli.toolsets.background import BackgroundDelegateTool

from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.toolsets.core.base import BaseTool

# =============================================================================
# BackgroundTaskManager Tests
# =============================================================================


@pytest.mark.asyncio
async def test_manager_register_task() -> None:
    """Registering a task should track it in active_tasks."""
    manager = BackgroundTaskManager()

    async def noop() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(noop())
    manager.register_task("test-agent", task)

    assert "test-agent" in manager.active_tasks
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_manager_task_auto_removed_on_completion() -> None:
    """Task should be auto-removed from active_tasks when it completes."""
    manager = BackgroundTaskManager()

    async def quick() -> None:
        pass

    task = asyncio.create_task(quick())
    manager.register_task("test-agent", task)
    await task
    # Allow done callback to fire
    await asyncio.sleep(0)

    assert "test-agent" not in manager.active_tasks


@pytest.mark.asyncio
async def test_manager_completion_callback() -> None:
    """notify_completion should invoke the registered callback."""
    manager = BackgroundTaskManager()
    callback_calls: list[str] = []

    def callback(agent_id: str) -> None:
        callback_calls.append(agent_id)

    manager.set_completion_callback(callback)
    manager.notify_completion("test-agent-1")
    manager.notify_completion("test-agent-2")

    assert callback_calls == ["test-agent-1", "test-agent-2"]

    # Clear callback
    manager.set_completion_callback(None)
    manager.notify_completion("test-agent-3")
    assert len(callback_calls) == 2  # No new calls


@pytest.mark.asyncio
async def test_manager_has_active_tasks() -> None:
    """has_active_tasks should reflect running tasks."""
    manager = BackgroundTaskManager()
    assert not manager.has_active_tasks

    async def sleeper() -> None:
        await asyncio.sleep(100)

    task = asyncio.create_task(sleeper())
    manager.register_task("test-agent", task)
    assert manager.has_active_tasks

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)  # Allow done callback
    assert not manager.has_active_tasks


@pytest.mark.asyncio
async def test_manager_close_cancels_tasks() -> None:
    """close() should cancel all registered tasks."""
    manager = BackgroundTaskManager()

    async def sleeper() -> None:
        await asyncio.sleep(100)

    task1 = asyncio.create_task(sleeper())
    task2 = asyncio.create_task(sleeper())
    manager.register_task("agent-1", task1)
    manager.register_task("agent-2", task2)

    assert len(manager.active_tasks) == 2

    await manager.close()

    assert task1.cancelled()
    assert task2.cancelled()
    assert len(manager.active_tasks) == 0


def test_manager_get_context_instruction_empty() -> None:
    """get_context_instruction should return None with no tasks."""
    manager = BackgroundTaskManager()
    assert manager.get_context_instruction() is None


@pytest.mark.asyncio
async def test_manager_get_context_instruction_with_tasks() -> None:
    """get_context_instruction should return XML with running tasks."""
    manager = BackgroundTaskManager()

    async def sleeper() -> None:
        await asyncio.sleep(100)

    task = asyncio.create_task(sleeper())
    manager.register_task("explorer-bg-a1b2", task)

    result = manager.get_context_instruction()
    assert result is not None
    assert "explorer-bg-a1b2" in result
    assert "background-tasks" in result

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_manager_set_core_toolset_and_get_delegate() -> None:
    """set_core_toolset should enable get_delegate_tool."""
    manager = BackgroundTaskManager()
    assert manager.get_delegate_tool() is None
    assert not manager.has_delegate_tool

    # Mock a toolset with a delegate tool
    mock_tool = MagicMock(spec=BaseTool)
    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_tool

    manager.set_core_toolset(mock_toolset)
    assert manager.has_delegate_tool
    assert manager.get_delegate_tool() is mock_tool


def test_manager_get_delegate_tool_not_found() -> None:
    """get_delegate_tool should return None if delegate tool doesn't exist."""
    manager = BackgroundTaskManager()

    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.side_effect = Exception("not found")

    manager.set_core_toolset(mock_toolset)
    assert manager.get_delegate_tool() is None


# =============================================================================
# BackgroundDelegateTool Tests
# =============================================================================


def _make_run_ctx(
    *,
    manager: BackgroundTaskManager | None = None,
    agent_id: str = "main",
) -> RunContext[AgentContext]:
    """Create a mock RunContext with optional BackgroundTaskManager."""
    mock_resources = MagicMock()
    if manager is not None:
        mock_resources.get.return_value = manager
    else:
        mock_resources.get.return_value = None

    mock_ctx = MagicMock()
    mock_ctx.resources = mock_resources
    mock_ctx.agent_id = agent_id

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_ctx
    return run_ctx


def test_tool_not_available_without_manager() -> None:
    """BackgroundDelegateTool should be unavailable without BackgroundTaskManager."""
    tool = BackgroundDelegateTool()
    ctx = _make_run_ctx(manager=None)
    assert not tool.is_available(ctx)


def test_tool_not_available_without_delegate() -> None:
    """BackgroundDelegateTool should be unavailable if delegate tool doesn't exist."""
    manager = BackgroundTaskManager()
    # No core_toolset set -> no delegate tool
    tool = BackgroundDelegateTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")
    assert not tool.is_available(ctx)


def test_tool_not_available_for_subagent() -> None:
    """BackgroundDelegateTool should be unavailable for subagents."""
    manager = BackgroundTaskManager()

    mock_delegate = MagicMock(spec=BaseTool)
    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    tool = BackgroundDelegateTool()
    # Using a subagent id instead of "main"
    ctx = _make_run_ctx(manager=manager, agent_id="explorer-1234")
    assert not tool.is_available(ctx)


def test_tool_available_with_delegate() -> None:
    """BackgroundDelegateTool should be available when delegate tool exists and agent is main."""
    manager = BackgroundTaskManager()

    mock_delegate = MagicMock(spec=BaseTool)
    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    tool = BackgroundDelegateTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")
    assert tool.is_available(ctx)


@pytest.mark.asyncio
async def test_tool_call_launches_background_task() -> None:
    """Calling BackgroundDelegateTool should launch a background task."""
    manager = BackgroundTaskManager()

    # Create a mock delegate tool that returns a result
    mock_delegate = AsyncMock(spec=BaseTool)
    mock_delegate.call = AsyncMock(return_value="Subagent result")

    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    # Create mock context
    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.subagent_history = {}
    mock_deps.agent_id = "main"
    mock_deps.send_message = MagicMock()

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = BackgroundDelegateTool()
    result = await tool.call(run_ctx, subagent_name="explorer", prompt="Find stuff")

    # Should return immediately with a status message
    assert "Background task started" in result
    assert "explorer" in result

    # A background task should be registered
    assert len(manager.active_tasks) == 1

    # Wait for the background task to complete
    tasks = list(manager.active_tasks.values())
    await asyncio.gather(*tasks, return_exceptions=True)
    await asyncio.sleep(0)  # Allow done callbacks to fire

    # Completion callback should have been called (via notify_completion)
    # We don't have a callback set, but the task should complete
    assert not manager.has_active_tasks

    # Message should be sent to bus
    mock_deps.send_message.assert_called_once()
    sent_msg = mock_deps.send_message.call_args[0][0]
    assert sent_msg.target == "main"


@pytest.mark.asyncio
async def test_tool_call_no_manager() -> None:
    """Calling BackgroundDelegateTool without manager should return error."""
    tool = BackgroundDelegateTool()
    ctx = _make_run_ctx(manager=None)
    result = await tool.call(ctx, subagent_name="explorer", prompt="Find stuff")
    assert "Error" in result


@pytest.mark.asyncio
async def test_tool_call_no_delegate() -> None:
    """Calling BackgroundDelegateTool without delegate tool should return error."""
    manager = BackgroundTaskManager()
    tool = BackgroundDelegateTool()
    ctx = _make_run_ctx(manager=manager)
    result = await tool.call(ctx, subagent_name="explorer", prompt="Find stuff")
    assert "Error" in result


# =============================================================================
# TUIEnvironment Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_env_background_manager_registered(tmp_path: Path) -> None:
    """BackgroundTaskManager should be registered as a resource."""
    async with TUIEnvironment(default_path=tmp_path) as env:
        manager = env.resources.get_typed(BACKGROUND_MANAGER_KEY, BackgroundTaskManager)
        assert isinstance(manager, BackgroundTaskManager)


@pytest.mark.asyncio
async def test_env_background_manager_property(tmp_path: Path) -> None:
    """background_manager property should return the BackgroundTaskManager."""
    async with TUIEnvironment(default_path=tmp_path) as env:
        manager = env.background_manager
        assert isinstance(manager, BackgroundTaskManager)
        # Same instance from resources
        assert manager is env.resources.get_typed(BACKGROUND_MANAGER_KEY, BackgroundTaskManager)


def test_env_background_manager_not_available_before_enter(tmp_path: Path) -> None:
    """background_manager should raise before entering."""
    env = TUIEnvironment(default_path=tmp_path)
    with pytest.raises(RuntimeError, match="not entered"):
        _ = env.background_manager


@pytest.mark.asyncio
async def test_env_background_tasks_cleaned_on_exit(tmp_path: Path) -> None:
    """Background tasks should be cancelled when environment exits."""

    async def sleeper() -> None:
        await asyncio.sleep(100)

    task_ref: asyncio.Task[None] | None = None

    async with TUIEnvironment(default_path=tmp_path) as env:
        manager = env.background_manager
        task_ref = asyncio.create_task(sleeper())
        manager.register_task("test-bg", task_ref)
        assert len(manager.active_tasks) == 1

    # After exit, task should be cancelled (manager.close() called by resource registry)
    assert task_ref is not None
    assert task_ref.cancelled() or task_ref.done()
