"""YAACLI CLI - TUI for AI agents."""

from __future__ import annotations

import importlib.metadata
import logging


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

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
