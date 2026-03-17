"""Tests for yaacli output guards."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.exceptions import ModelRetry
from yaacli.events import LoopCompleteEvent, LoopCompleteReason, LoopIterationEvent
from yaacli.guards import LOOP_COMPLETE_MARKER, loop_guard
from yaacli.session import TUIContext


def _make_ctx(deps: TUIContext) -> MagicMock:
    """Create a mock RunContext with the given deps."""
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


@pytest.fixture
def tui_ctx() -> TUIContext:
    """Create a minimal TUIContext for testing (not entered)."""
    ctx = TUIContext.model_construct()
    ctx.loop_task = None
    ctx.loop_iteration = 0
    ctx.loop_max_iterations = 10
    ctx._stream_queue_enabled = False
    return ctx


@pytest.mark.asyncio
async def test_loop_guard_passthrough_when_inactive(tui_ctx: TUIContext) -> None:
    """Guard should pass through output when loop is not active."""
    ctx = _make_ctx(tui_ctx)
    result = await loop_guard(ctx, "Hello world")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_loop_guard_passthrough_deferred_tool_requests(tui_ctx: TUIContext) -> None:
    """Guard should pass through DeferredToolRequests even when loop is active."""
    tui_ctx.loop_task = "fix tests"
    ctx = _make_ctx(tui_ctx)

    mock_deferred = MagicMock()  # Simulate DeferredToolRequests (not a str)
    result = await loop_guard(ctx, mock_deferred)
    assert result is mock_deferred


@pytest.mark.asyncio
async def test_loop_guard_verified_complete(tui_ctx: TUIContext) -> None:
    """Guard should pass through and reset when output contains LOOP_COMPLETE_MARKER."""
    tui_ctx.loop_task = "fix tests"
    tui_ctx.loop_iteration = 3
    ctx = _make_ctx(tui_ctx)

    with patch.object(TUIContext, "emit_event", new_callable=AsyncMock) as mock_emit:
        output = f"All done. {LOOP_COMPLETE_MARKER}"
        result = await loop_guard(ctx, output)

        assert result == output
        assert tui_ctx.loop_task is None
        assert tui_ctx.loop_iteration == 0

        # Check event was emitted
        mock_emit.assert_called_once()
        event = mock_emit.call_args[0][0]
        assert isinstance(event, LoopCompleteEvent)
        assert event.reason == LoopCompleteReason.verified
        assert event.iteration == 3


@pytest.mark.asyncio
async def test_loop_guard_continues_iteration(tui_ctx: TUIContext) -> None:
    """Guard should raise ModelRetry to continue when task not verified."""
    tui_ctx.loop_task = "fix tests"
    tui_ctx.loop_iteration = 0
    tui_ctx.loop_max_iterations = 10
    ctx = _make_ctx(tui_ctx)

    with patch.object(TUIContext, "emit_event", new_callable=AsyncMock) as mock_emit:
        with pytest.raises(ModelRetry, match="loop-check"):
            await loop_guard(ctx, "I think it's done")

        assert tui_ctx.loop_iteration == 1

        # Check iteration event was emitted
        mock_emit.assert_called_once()
        event = mock_emit.call_args[0][0]
        assert isinstance(event, LoopIterationEvent)
        assert event.iteration == 1
        assert event.max_iterations == 10


@pytest.mark.asyncio
async def test_loop_guard_max_iterations_reached(tui_ctx: TUIContext) -> None:
    """Guard should stop and pass through when max iterations exceeded."""
    tui_ctx.loop_task = "fix tests"
    tui_ctx.loop_iteration = 10  # Already at max
    tui_ctx.loop_max_iterations = 10
    ctx = _make_ctx(tui_ctx)

    with patch.object(TUIContext, "emit_event", new_callable=AsyncMock) as mock_emit:
        result = await loop_guard(ctx, "Still working...")

        assert result == "Still working..."
        assert tui_ctx.loop_task is None
        assert tui_ctx.loop_iteration == 0

        # Check event was emitted
        mock_emit.assert_called_once()
        event = mock_emit.call_args[0][0]
        assert isinstance(event, LoopCompleteEvent)
        assert event.reason == LoopCompleteReason.max_iterations


@pytest.mark.asyncio
async def test_loop_guard_multiple_iterations(tui_ctx: TUIContext) -> None:
    """Guard should increment iteration each time it retries."""
    tui_ctx.loop_task = "fix tests"
    tui_ctx.loop_iteration = 0
    tui_ctx.loop_max_iterations = 3
    ctx = _make_ctx(tui_ctx)

    with patch.object(TUIContext, "emit_event", new_callable=AsyncMock) as mock_emit:
        # Iteration 1
        with pytest.raises(ModelRetry):
            await loop_guard(ctx, "working...")
        assert tui_ctx.loop_iteration == 1

        # Iteration 2
        with pytest.raises(ModelRetry):
            await loop_guard(ctx, "still working...")
        assert tui_ctx.loop_iteration == 2

        # Iteration 3
        with pytest.raises(ModelRetry):
            await loop_guard(ctx, "almost done...")
        assert tui_ctx.loop_iteration == 3

        # Iteration 4 - exceeds max, should pass through
        result = await loop_guard(ctx, "giving up...")
        assert result == "giving up..."
        assert tui_ctx.loop_task is None

        # 3 iteration events + 1 complete event = 4 calls
        assert mock_emit.call_count == 4


def test_tui_context_loop_active_property() -> None:
    """TUIContext.loop_active property should reflect loop_task state."""
    ctx = TUIContext.model_construct()
    ctx.loop_task = None
    assert ctx.loop_active is False

    ctx.loop_task = "some task"
    assert ctx.loop_active is True


def test_tui_context_reset_loop() -> None:
    """TUIContext.reset_loop should clear all loop state."""
    ctx = TUIContext.model_construct()
    ctx.loop_task = "some task"
    ctx.loop_iteration = 5

    ctx.reset_loop()

    assert ctx.loop_task is None
    assert ctx.loop_iteration == 0
