"""YAACLI CLI - TUI for AI agents."""

from __future__ import annotations

import importlib.metadata
import logging
from types import TracebackType


def _configure_logging() -> None:
    """Configure logging to suppress noisy third-party logs.

    Suppresses:
    - asyncio ERROR logs during async generator cleanup (pydantic-ai/mcp issue)
    - MCP INFO logs (ListToolsRequest, etc.)
    """
    # Configure root logger first to prevent MCP's basicConfig from taking effect
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(levelname)s: %(message)s",
        )

    # Suppress asyncio async generator cleanup errors
    # These occur during shutdown and are harmless but noisy
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    # Suppress mcp INFO logs
    logging.getLogger("mcp").setLevel(logging.WARNING)


_configure_logging()


def _patch_pydantic_ai_contextvar() -> None:
    """Patch pydantic-ai's set_current_run_context to suppress ContextVar cleanup errors.

    When pydantic-ai creates async tasks for streaming model requests, the
    ContextVar token from ``_CURRENT_RUN_CONTEXT.set()`` may belong to a
    different ``contextvars.Context`` copy than the one active during
    ``_CURRENT_RUN_CONTEXT.reset(token)`` in the finally block.  This raises
    ``ValueError: ... was created in a different Context`` which is benign --
    the model response has already been received -- but propagates through
    ``on_model_request_error`` (default: re-raise) and can terminate the
    agent run.

    This patch replaces ``set_current_run_context`` in ``_agent_graph`` with a
    version that catches the ValueError in the finally block, preventing the
    error from propagating at all.
    """
    from collections.abc import Iterator
    from contextlib import contextmanager, suppress

    try:
        import pydantic_ai._agent_graph as _agent_graph
        from pydantic_ai._run_context import _CURRENT_RUN_CONTEXT
    except ImportError:
        return

    @contextmanager
    def _safe_set_current_run_context(run_context: object) -> Iterator[None]:
        token = _CURRENT_RUN_CONTEXT.set(run_context)  # type: ignore[arg-type]
        try:
            yield
        finally:
            with suppress(ValueError):
                # Benign: token was created in a different contextvars.Context
                # copy (e.g. asyncio.create_task without explicit context=).
                # The ContextVar will naturally be cleaned up when the Context
                # object is garbage collected.
                _CURRENT_RUN_CONTEXT.reset(token)

    _agent_graph.set_current_run_context = _safe_set_current_run_context  # type: ignore[assignment]


_patch_pydantic_ai_contextvar()


def _patch_sniffio_asyncio_detection() -> None:
    """Force sniffio to always detect 'asyncio' in the yaacli process.

    sniffio detects the current async library in this order:
      1. thread_local.name  (threading.local, per-thread)
      2. current_async_library_cvar  (ContextVar, per-context)
      3. asyncio.current_task()  (fallback)

    Previous approach (ContextVar only) failed in cancel+resend scenarios:
    when a user cancels a running agent and immediately sends a new message,
    prompt_toolkit's input thread schedules the key handler via
    call_soon_threadsafe, which creates a context copy from the input
    thread's context.  Through task cancellation and recreation cycles,
    the ContextVar value can be lost in certain context branches, causing
    AsyncLibraryNotFoundError from httpcore/anyio.

    Setting thread_local.name is the most robust approach because:
    - It is checked FIRST by sniffio (highest priority)
    - It is not affected by ContextVar propagation across task contexts
    - The asyncio event loop runs single-threaded, so all event loop
      code (including model requests) sees the thread_local value
    - yaacli exclusively uses asyncio, so this is always correct
    """
    try:
        from sniffio._impl import thread_local
    except ImportError:
        return

    thread_local.name = "asyncio"


_patch_sniffio_asyncio_detection()


def _patch_anyio_cancel_scope_null_task() -> None:
    """Patch anyio CancelScope to tolerate asyncio.current_task() returning None.

    After Ctrl+C cancellation, httpx stream cleanup (`response.aclose()`) uses
    anyio's `AsyncShieldCancellation` (a CancelScope) to shield the connection
    close from further cancellation.  `CancelScope.__enter__` unconditionally
    calls `asyncio.current_task()` and uses the result as a key in a
    `WeakKeyDictionary`.  When cleanup runs in a context where the asyncio task
    has already been torn down (e.g. async-generator finalization triggered by
    GC after cancellation), `current_task()` returns None, causing:

        TypeError: cannot create weak reference to 'NoneType' object

    This patch wraps `__enter__` and `__exit__` so that when `current_task()`
    is None the scope degrades to a no-op.  This is safe because:
    - There is no task to shield; cancellation management is meaningless.
    - The code inside the scope (closing the TCP connection) is a best-effort
      cleanup that should not raise.
    """
    import asyncio

    try:
        from anyio._backends._asyncio import CancelScope
    except ImportError:
        return

    _original_enter = CancelScope.__enter__
    _original_exit = CancelScope.__exit__

    _NOOP_ATTR = "_yaacli_noop"

    def _safe_enter(self: CancelScope) -> CancelScope:
        if asyncio.current_task() is None:
            # No active task -- degrade to a no-op context manager.
            self._active = True
            object.__setattr__(self, _NOOP_ATTR, True)
            return self
        object.__setattr__(self, _NOOP_ATTR, False)
        return _original_enter(self)

    def _safe_exit(
        self: CancelScope,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if getattr(self, _NOOP_ATTR, False):
            self._active = False
            return False  # Do not suppress exceptions
        return _original_exit(self, exc_type, exc_val, exc_tb)

    CancelScope.__enter__ = _safe_enter  # type: ignore[assignment]
    CancelScope.__exit__ = _safe_exit  # type: ignore[assignment]


_patch_anyio_cancel_scope_null_task()

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
