"""Tests for background task manager and spawn delegate tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext
from yaacli.background import BACKGROUND_MANAGER_KEY, BackgroundTaskManager
from yaacli.environment import TUIEnvironment
from yaacli.toolsets.background import SpawnDelegateTool

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
# SpawnDelegateTool Tests
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
    """SpawnDelegateTool should be unavailable without BackgroundTaskManager."""
    tool = SpawnDelegateTool()
    ctx = _make_run_ctx(manager=None)
    assert not tool.is_available(ctx)


def test_tool_not_available_without_delegate() -> None:
    """SpawnDelegateTool should be unavailable if delegate tool doesn't exist."""
    manager = BackgroundTaskManager()
    # No core_toolset set -> no delegate tool
    tool = SpawnDelegateTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")
    assert not tool.is_available(ctx)


def test_tool_not_available_for_subagent() -> None:
    """SpawnDelegateTool should be unavailable for subagents."""
    manager = BackgroundTaskManager()

    mock_delegate = MagicMock(spec=BaseTool)
    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    tool = SpawnDelegateTool()
    # Using a subagent id instead of "main"
    ctx = _make_run_ctx(manager=manager, agent_id="explorer-1234")
    assert not tool.is_available(ctx)


def test_tool_available_with_delegate() -> None:
    """SpawnDelegateTool should be available when delegate tool exists and agent is main."""
    manager = BackgroundTaskManager()

    mock_delegate = MagicMock(spec=BaseTool)
    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    tool = SpawnDelegateTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")
    assert tool.is_available(ctx)


@pytest.mark.asyncio
async def test_tool_call_launches_background_task() -> None:
    """Calling SpawnDelegateTool should launch a background task."""
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

    tool = SpawnDelegateTool()
    result = await tool.call(run_ctx, subagent_name="explorer", prompt="Find stuff")

    # Should return immediately with a status message
    assert "Spawned delegate" in result
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
    """Calling SpawnDelegateTool without manager should return error."""
    tool = SpawnDelegateTool()
    ctx = _make_run_ctx(manager=None)
    result = await tool.call(ctx, subagent_name="explorer", prompt="Find stuff")
    assert "Error" in result


@pytest.mark.asyncio
async def test_tool_call_no_delegate() -> None:
    """Calling SpawnDelegateTool without delegate tool should return error."""
    manager = BackgroundTaskManager()
    tool = SpawnDelegateTool()
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


# =============================================================================
# SteerSubagentTool Tests
# =============================================================================


def test_steer_not_available_without_manager() -> None:
    """SteerSubagentTool should be unavailable without BackgroundTaskManager."""
    from yaacli.toolsets.background import SteerSubagentTool

    tool = SteerSubagentTool()
    ctx = _make_run_ctx(manager=None)
    assert not tool.is_available(ctx)


def test_steer_not_available_without_active_tasks() -> None:
    """SteerSubagentTool should be unavailable when no background tasks are running."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()
    tool = SteerSubagentTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")
    assert not tool.is_available(ctx)


def test_steer_not_available_for_subagent() -> None:
    """SteerSubagentTool should be unavailable for subagents."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()
    tool = SteerSubagentTool()
    ctx = _make_run_ctx(manager=manager, agent_id="explorer-1234")
    assert not tool.is_available(ctx)


@pytest.mark.asyncio
async def test_steer_available_with_active_tasks() -> None:
    """SteerSubagentTool should be available when background tasks are running."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()

    async def sleeper() -> None:
        await asyncio.sleep(100)

    task = asyncio.create_task(sleeper())
    manager.register_task("searcher-bg-a1b2", task)

    tool = SteerSubagentTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")
    assert tool.is_available(ctx)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_steer_sends_bus_message() -> None:
    """Steering a running subagent should send a targeted BusMessage."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()

    async def sleeper() -> None:
        await asyncio.sleep(100)

    task = asyncio.create_task(sleeper())
    manager.register_task("searcher-bg-a1b2", task)

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.agent_id = "main"
    mock_deps.send_message = MagicMock()

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SteerSubagentTool()
    result = await tool.call(run_ctx, agent_id="searcher-bg-a1b2", message="also check docs folder")

    assert "Steering message sent" in result
    assert "searcher-bg-a1b2" in result

    # Verify BusMessage was sent with correct target
    mock_deps.send_message.assert_called_once()
    sent_msg = mock_deps.send_message.call_args[0][0]
    assert sent_msg.target == "searcher-bg-a1b2"
    assert sent_msg.source == "main"
    assert sent_msg.content == "also check docs folder"

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_steer_finished_agent_suggests_resume() -> None:
    """Steering a finished subagent should suggest spawn_delegate resume."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()

    # Create and immediately complete a task
    async def quick() -> None:
        pass

    task = asyncio.create_task(quick())
    manager.register_task("searcher-bg-a1b2", task)
    await task
    await asyncio.sleep(0)  # Allow done callback to fire

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.agent_id = "main"
    mock_deps.agent_registry = {}

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SteerSubagentTool()
    result = await tool.call(run_ctx, agent_id="searcher-bg-a1b2", message="dig deeper")

    assert "already completed" in result
    assert "spawn_delegate" in result
    assert "agent_id" in result
    assert "searcher-bg-a1b2" in result
    assert "delegate" in result


@pytest.mark.asyncio
async def test_steer_unknown_agent_suggests_resume() -> None:
    """Steering an unknown agent_id should suggest resume."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.agent_id = "main"
    mock_deps.agent_registry = {}

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SteerSubagentTool()
    result = await tool.call(run_ctx, agent_id="nonexistent-bg-0000", message="hello")

    assert "already completed" in result
    assert "spawn_delegate" in result


@pytest.mark.asyncio
async def test_steer_uses_agent_registry_for_name() -> None:
    """Resume suggestion should look up agent_name from agent_registry."""
    from yaacli.toolsets.background import SteerSubagentTool

    from ya_agent_sdk.context.agent import AgentInfo

    manager = BackgroundTaskManager()

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.agent_id = "main"
    mock_deps.agent_registry = {
        "searcher-bg-a1b2": AgentInfo(agent_id="searcher-bg-a1b2", agent_name="searcher", parent_agent_id="main"),
    }

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SteerSubagentTool()
    result = await tool.call(run_ctx, agent_id="searcher-bg-a1b2", message="check more")

    assert 'subagent_name="searcher"' in result


@pytest.mark.asyncio
async def test_steer_shows_active_tasks_hint() -> None:
    """Resume suggestion should mention other active tasks if any."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()

    async def sleeper() -> None:
        await asyncio.sleep(100)

    active_task = asyncio.create_task(sleeper())
    manager.register_task("debugger-bg-c3d1", active_task)

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.agent_id = "main"
    mock_deps.agent_registry = {}

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SteerSubagentTool()
    # Try to steer a non-existent agent while another is active
    result = await tool.call(run_ctx, agent_id="searcher-bg-a1b2", message="hello")

    assert "Active tasks: debugger-bg-c3d1" in result

    active_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active_task


# =============================================================================
# SpawnDelegateTool Resume Tests
# =============================================================================


@pytest.mark.asyncio
async def test_spawn_delegate_with_agent_id_resume() -> None:
    """SpawnDelegateTool should pass agent_id through for resume."""
    manager = BackgroundTaskManager()

    mock_delegate = AsyncMock(spec=BaseTool)
    mock_delegate.call = AsyncMock(return_value="Resumed result")

    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.subagent_history = {"searcher-bg-a1b2": []}  # Existing history
    mock_deps.agent_id = "main"
    mock_deps.send_message = MagicMock()

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SpawnDelegateTool()
    result = await tool.call(run_ctx, subagent_name="searcher", prompt="dig deeper", agent_id="searcher-bg-a1b2")

    # Should indicate resume
    assert "Resumed" in result
    assert "searcher-bg-a1b2" in result

    # Wait for background task
    tasks = list(manager.active_tasks.values())
    await asyncio.gather(*tasks, return_exceptions=True)
    await asyncio.sleep(0)

    # Delegate should have been called with the provided agent_id
    mock_delegate.call.assert_called_once()
    call_kwargs = mock_delegate.call.call_args
    assert call_kwargs[1]["agent_id"] == "searcher-bg-a1b2"


@pytest.mark.asyncio
async def test_spawn_delegate_without_agent_id_generates_new() -> None:
    """SpawnDelegateTool without agent_id should generate a new one."""
    manager = BackgroundTaskManager()

    mock_delegate = AsyncMock(spec=BaseTool)
    mock_delegate.call = AsyncMock(return_value="New result")

    mock_toolset = MagicMock()
    mock_toolset._get_tool_instance.return_value = mock_delegate
    manager.set_core_toolset(mock_toolset)

    mock_deps = MagicMock()
    mock_deps.resources = MagicMock()
    mock_deps.resources.get.return_value = manager
    mock_deps.subagent_history = {}
    mock_deps.agent_id = "main"
    mock_deps.send_message = MagicMock()

    run_ctx = MagicMock(spec=RunContext)
    run_ctx.deps = mock_deps

    tool = SpawnDelegateTool()
    result = await tool.call(run_ctx, subagent_name="explorer", prompt="Find stuff")

    # Should indicate spawned (not resumed)
    assert "Spawned" in result
    assert "explorer" in result

    # Wait for background task
    tasks = list(manager.active_tasks.values())
    await asyncio.gather(*tasks, return_exceptions=True)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_steer_instruction_only_with_active_tasks() -> None:
    """get_instruction should return None when no active tasks."""
    from yaacli.toolsets.background import SteerSubagentTool

    manager = BackgroundTaskManager()
    tool = SteerSubagentTool()
    ctx = _make_run_ctx(manager=manager, agent_id="main")

    instruction = await tool.get_instruction(ctx)
    assert instruction is None

    # Add an active task
    async def sleeper() -> None:
        await asyncio.sleep(100)

    task = asyncio.create_task(sleeper())
    manager.register_task("searcher-bg-a1b2", task)

    instruction = await tool.get_instruction(ctx)
    assert instruction is not None
    assert "Send additional guidance" in instruction

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
