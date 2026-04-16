"""Tests for FileChangeEvent emission from filesystem tools."""

from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import MagicMock

from pydantic_ai import RunContext
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.environment.local import LocalEnvironment
from ya_agent_sdk.events import FileChangeAction, FileChangeEvent, TextReplacement
from ya_agent_sdk.toolsets.core.filesystem._types import EditItem
from ya_agent_sdk.toolsets.core.filesystem.edit import EditTool, MultiEditTool
from ya_agent_sdk.toolsets.core.filesystem.move_copy import CopyTool, MoveTool
from ya_agent_sdk.toolsets.core.filesystem.write import WriteTool


async def _collect_events(ctx: AgentContext) -> list[FileChangeEvent]:
    """Drain all FileChangeEvents from the agent's stream queue."""
    queue = ctx.agent_stream_queues[ctx.agent_id]
    events: list[FileChangeEvent] = []
    while not queue.empty():
        event = await queue.get()
        if isinstance(event, FileChangeEvent):
            events.append(event)
    return events


async def _make_ctx(stack: AsyncExitStack, tmp_path: Path) -> tuple[AgentContext, MagicMock]:
    """Create an AgentContext with stream queue enabled and a mock RunContext."""
    env = await stack.enter_async_context(
        LocalEnvironment(allowed_paths=[tmp_path], default_path=tmp_path, tmp_base_dir=tmp_path)
    )
    ctx = await stack.enter_async_context(AgentContext(env=env))
    ctx._stream_queue_enabled = True

    mock_run_ctx = MagicMock(spec=RunContext)
    mock_run_ctx.deps = ctx
    return ctx, mock_run_ctx


# =============================================================================
# EditTool events
# =============================================================================


async def test_edit_create_emits_created_event(tmp_path: Path) -> None:
    """EditTool should emit FileChangeEvent with 'created' action for new files."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = EditTool()

        await tool.call(run_ctx, file_path="new.txt", old_string="", new_string="hello world")

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.tool_name == "edit"
        assert len(event.changes) == 1

        change = event.changes[0]
        assert change.path == "new.txt"
        assert change.action == FileChangeAction.created
        assert len(change.replacements) == 1
        assert change.replacements[0].old_string == ""
        assert change.replacements[0].new_string == "hello world"


async def test_edit_modify_emits_modified_event(tmp_path: Path) -> None:
    """EditTool should emit FileChangeEvent with 'modified' action and structured replacement."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = EditTool()

        (tmp_path / "test.txt").write_text("Hello World")
        await tool.call(run_ctx, file_path="test.txt", old_string="World", new_string="Universe")

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.tool_name == "edit"

        change = event.changes[0]
        assert change.path == "test.txt"
        assert change.action == FileChangeAction.modified
        assert change.replacements == [TextReplacement(old_string="World", new_string="Universe")]


async def test_edit_replace_all_emits_event(tmp_path: Path) -> None:
    """EditTool with replace_all should emit a single event with the replacement."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = EditTool()

        (tmp_path / "test.txt").write_text("foo bar foo baz foo")
        await tool.call(run_ctx, file_path="test.txt", old_string="foo", new_string="qux", replace_all=True)

        events = await _collect_events(ctx)
        assert len(events) == 1
        assert events[0].changes[0].replacements[0] == TextReplacement(old_string="foo", new_string="qux")


async def test_edit_error_does_not_emit_event(tmp_path: Path) -> None:
    """EditTool should not emit events on failure (file not found, text not matched)."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = EditTool()

        # File not found
        await tool.call(run_ctx, file_path="nonexistent.txt", old_string="foo", new_string="bar")
        assert await _collect_events(ctx) == []

        # Text not found
        (tmp_path / "test.txt").write_text("Hello World")
        await tool.call(run_ctx, file_path="test.txt", old_string="missing", new_string="bar")
        assert await _collect_events(ctx) == []

        # File already exists (create mode)
        await tool.call(run_ctx, file_path="test.txt", old_string="", new_string="new content")
        assert await _collect_events(ctx) == []


# =============================================================================
# MultiEditTool events
# =============================================================================


async def test_multi_edit_modify_emits_event_with_all_replacements(tmp_path: Path) -> None:
    """MultiEditTool should emit one event with all replacements listed."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MultiEditTool()

        (tmp_path / "test.txt").write_text("aaa bbb ccc")
        edits = [
            EditItem(old_string="aaa", new_string="xxx"),
            EditItem(old_string="bbb", new_string="yyy"),
            EditItem(old_string="ccc", new_string="zzz"),
        ]
        await tool.call(run_ctx, file_path="test.txt", edits=edits)

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.tool_name == "multi_edit"

        change = event.changes[0]
        assert change.path == "test.txt"
        assert change.action == FileChangeAction.modified
        assert len(change.replacements) == 3
        assert change.replacements[0] == TextReplacement(old_string="aaa", new_string="xxx")
        assert change.replacements[1] == TextReplacement(old_string="bbb", new_string="yyy")
        assert change.replacements[2] == TextReplacement(old_string="ccc", new_string="zzz")


async def test_multi_edit_create_emits_created_event(tmp_path: Path) -> None:
    """MultiEditTool with empty old_string first edit should emit 'created' action."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MultiEditTool()

        edits = [
            EditItem(old_string="", new_string="Hello World"),
            EditItem(old_string="World", new_string="Universe"),
        ]
        await tool.call(run_ctx, file_path="new.txt", edits=edits)

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.changes[0].action == FileChangeAction.created
        assert len(event.changes[0].replacements) == 2


async def test_multi_edit_error_does_not_emit_event(tmp_path: Path) -> None:
    """MultiEditTool should not emit events on failure."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MultiEditTool()

        # File not found
        edits = [EditItem(old_string="foo", new_string="bar")]
        await tool.call(run_ctx, file_path="nonexistent.txt", edits=edits)
        assert await _collect_events(ctx) == []


# =============================================================================
# WriteTool events
# =============================================================================


async def test_write_create_emits_created_event(tmp_path: Path) -> None:
    """WriteTool should emit 'created' when writing a new file."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = WriteTool()

        await tool.call(run_ctx, file_path="new.txt", content="hello")

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.tool_name == "write"
        assert event.changes[0].path == "new.txt"
        assert event.changes[0].action == FileChangeAction.created
        assert event.changes[0].replacements == []


async def test_write_overwrite_emits_modified_event(tmp_path: Path) -> None:
    """WriteTool should emit 'modified' when overwriting an existing file."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = WriteTool()

        (tmp_path / "test.txt").write_text("old content")
        await tool.call(run_ctx, file_path="test.txt", content="new content")

        events = await _collect_events(ctx)
        assert len(events) == 1
        assert events[0].changes[0].action == FileChangeAction.modified


async def test_write_append_emits_modified_event(tmp_path: Path) -> None:
    """WriteTool in append mode should emit 'modified'."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = WriteTool()

        (tmp_path / "test.txt").write_text("start ")
        await tool.call(run_ctx, file_path="test.txt", content="end", mode="a")

        events = await _collect_events(ctx)
        assert len(events) == 1
        assert events[0].changes[0].action == FileChangeAction.modified


async def test_write_invalid_mode_does_not_emit_event(tmp_path: Path) -> None:
    """WriteTool should not emit events on invalid mode error."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = WriteTool()

        await tool.call(run_ctx, file_path="test.txt", content="content", mode="x")
        assert await _collect_events(ctx) == []


# =============================================================================
# MoveTool events
# =============================================================================


async def test_move_emits_moved_event(tmp_path: Path) -> None:
    """MoveTool should emit FileChangeEvent with 'moved' action."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MoveTool()

        (tmp_path / "src.txt").write_text("content")
        await tool.call(run_ctx, pairs=[{"src": "src.txt", "dst": "dst.txt"}])

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.tool_name == "move"
        assert len(event.changes) == 1

        change = event.changes[0]
        assert change.path == "src.txt"
        assert change.action == FileChangeAction.moved
        assert change.destination == "dst.txt"
        assert change.replacements == []


async def test_move_batch_emits_single_event(tmp_path: Path) -> None:
    """MoveTool batch operation should emit one event with multiple changes."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MoveTool()

        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        await tool.call(
            run_ctx,
            pairs=[
                {"src": "a.txt", "dst": "a2.txt"},
                {"src": "b.txt", "dst": "b2.txt"},
            ],
        )

        events = await _collect_events(ctx)
        assert len(events) == 1
        assert len(events[0].changes) == 2
        assert events[0].changes[0].path == "a.txt"
        assert events[0].changes[0].destination == "a2.txt"
        assert events[0].changes[1].path == "b.txt"
        assert events[0].changes[1].destination == "b2.txt"


async def test_move_failure_does_not_emit_event(tmp_path: Path) -> None:
    """MoveTool should not emit events when all operations fail."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MoveTool()

        await tool.call(run_ctx, pairs=[{"src": "nonexistent.txt", "dst": "dst.txt"}])
        assert await _collect_events(ctx) == []


async def test_move_partial_success_emits_only_successful(tmp_path: Path) -> None:
    """MoveTool should only include successful moves in the event."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = MoveTool()

        (tmp_path / "exists.txt").write_text("content")
        await tool.call(
            run_ctx,
            pairs=[
                {"src": "exists.txt", "dst": "moved.txt"},
                {"src": "nonexistent.txt", "dst": "fail.txt"},
            ],
        )

        events = await _collect_events(ctx)
        assert len(events) == 1
        assert len(events[0].changes) == 1
        assert events[0].changes[0].path == "exists.txt"


# =============================================================================
# CopyTool events
# =============================================================================


async def test_copy_emits_copied_event(tmp_path: Path) -> None:
    """CopyTool should emit FileChangeEvent with 'copied' action."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = CopyTool()

        (tmp_path / "src.txt").write_text("content")
        await tool.call(run_ctx, pairs=[{"src": "src.txt", "dst": "copy.txt"}])

        events = await _collect_events(ctx)
        assert len(events) == 1
        event = events[0]
        assert event.tool_name == "copy"

        change = event.changes[0]
        assert change.path == "src.txt"
        assert change.action == FileChangeAction.copied
        assert change.destination == "copy.txt"
        assert change.replacements == []


async def test_copy_batch_emits_single_event(tmp_path: Path) -> None:
    """CopyTool batch operation should emit one event with multiple changes."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = CopyTool()

        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        await tool.call(
            run_ctx,
            pairs=[
                {"src": "a.txt", "dst": "a_copy.txt"},
                {"src": "b.txt", "dst": "b_copy.txt"},
            ],
        )

        events = await _collect_events(ctx)
        assert len(events) == 1
        assert len(events[0].changes) == 2


async def test_copy_failure_does_not_emit_event(tmp_path: Path) -> None:
    """CopyTool should not emit events when all operations fail."""
    async with AsyncExitStack() as stack:
        ctx, run_ctx = await _make_ctx(stack, tmp_path)
        tool = CopyTool()

        await tool.call(run_ctx, pairs=[{"src": "nonexistent.txt", "dst": "copy.txt"}])
        assert await _collect_events(ctx) == []
