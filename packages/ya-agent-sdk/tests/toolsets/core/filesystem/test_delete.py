"""Tests for ya_agent_sdk.toolsets.core.filesystem.delete module."""

from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import MagicMock

from pydantic_ai import RunContext
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.toolsets.core.filesystem.delete import DeleteTool


async def _make_run_ctx(stack: AsyncExitStack, tmp_path: Path) -> MagicMock:
    env = await stack.enter_async_context(
        LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path)
    )
    ctx = await stack.enter_async_context(AgentContext(env=env))
    mock_run_ctx = MagicMock(spec=RunContext)
    mock_run_ctx.deps = ctx
    return mock_run_ctx


async def test_delete_tool_attributes(agent_context: AgentContext) -> None:
    """Should have correct name, description, and instructions."""
    assert DeleteTool.name == "delete"
    assert "Delete" in DeleteTool.description
    tool = DeleteTool()
    mock_run_ctx = MagicMock(spec=RunContext)
    mock_run_ctx.deps = agent_context
    instruction = await tool.get_instruction(mock_run_ctx)
    assert instruction is not None


async def test_delete_file(tmp_path: Path) -> None:
    """Should delete a file."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        (tmp_path / "test.txt").write_text("content")

        result = await tool.call(run_ctx, paths=["test.txt"])
        assert result == [{"path": "test.txt", "success": True, "message": "Deleted test.txt"}]
        assert not (tmp_path / "test.txt").exists()


async def test_delete_empty_directory(tmp_path: Path) -> None:
    """Should delete an empty directory without recursive mode."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        (tmp_path / "empty").mkdir()

        result = await tool.call(run_ctx, paths=["empty"])
        assert result[0]["success"] is True
        assert not (tmp_path / "empty").exists()


async def test_delete_non_empty_directory_requires_recursive(tmp_path: Path) -> None:
    """Should require recursive mode for non-empty directories."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "file.txt").write_text("content")

        result = await tool.call(run_ctx, paths=["dir"])
        assert result[0]["success"] is False
        assert "recursive=True" in result[0]["message"]
        assert (tmp_path / "dir" / "file.txt").exists()


async def test_delete_directory_recursive(tmp_path: Path) -> None:
    """Should delete a non-empty directory with recursive mode."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        (tmp_path / "dir" / "nested").mkdir(parents=True)
        (tmp_path / "dir" / "nested" / "file.txt").write_text("content")
        (tmp_path / "dir" / "root.txt").write_text("root")

        result = await tool.call(run_ctx, paths=["dir"], recursive=True)
        assert result[0]["success"] is True
        assert not (tmp_path / "dir").exists()


async def test_delete_missing_path_without_force(tmp_path: Path) -> None:
    """Should fail for missing paths when force is disabled."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        result = await tool.call(run_ctx, paths=["missing.txt"])
        assert result[0]["success"] is False
        assert "not found" in result[0]["message"]


async def test_delete_missing_path_with_force(tmp_path: Path) -> None:
    """Should succeed for missing paths when force is enabled."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        result = await tool.call(run_ctx, paths=["missing.txt"], force=True)
        assert result[0]["success"] is True
        assert "ignored" in result[0]["message"]


async def test_delete_recursive_force_matches_rm_rf_cleanup(tmp_path: Path) -> None:
    """Should support rm -rf style cleanup."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        (tmp_path / "build" / "cache").mkdir(parents=True)
        (tmp_path / "build" / "cache" / "artifact.bin").write_text("data")

        result = await tool.call(run_ctx, paths=["build", "already-gone"], recursive=True, force=True)
        assert len(result) == 2
        assert all(item["success"] for item in result)
        assert not (tmp_path / "build").exists()


async def test_delete_multiple_paths_partial_success(tmp_path: Path) -> None:
    """Should process batch deletes independently."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        (tmp_path / "exists.txt").write_text("content")

        result = await tool.call(run_ctx, paths=["exists.txt", "missing.txt"])
        assert result[0]["success"] is True
        assert result[1]["success"] is False
        assert not (tmp_path / "exists.txt").exists()


async def test_delete_protected_workspace_anchor(tmp_path: Path) -> None:
    """Should refuse workspace anchor paths."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        result = await tool.call(run_ctx, paths=["."], recursive=True, force=True)
        assert result[0]["success"] is False
        assert "protected path" in result[0]["message"]
        assert tmp_path.exists()


async def test_delete_protected_absolute_workspace_root(tmp_path: Path) -> None:
    """Should refuse the absolute workspace root path."""
    async with AsyncExitStack() as stack:
        run_ctx = await _make_run_ctx(stack, tmp_path)
        tool = DeleteTool()

        result = await tool.call(run_ctx, paths=[str(tmp_path)], recursive=True, force=True)
        assert result[0]["success"] is False
        assert "protected path" in result[0]["message"]
        assert tmp_path.exists()


async def test_delete_tool_unavailable_without_file_operator(agent_context: AgentContext) -> None:
    """Should be unavailable when file_operator is absent."""
    tool = DeleteTool()
    mock_run_ctx = MagicMock(spec=RunContext)
    mock_run_ctx.deps = agent_context.model_copy(update={"env": None})
    assert tool.is_available(mock_run_ctx) is False
