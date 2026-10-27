"""Hook-aware driver for agent runs whose nodes are streamed manually."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai.run import AgentRun
from pydantic_graph import End


async def drive_streamed_run(
    run: AgentRun[Any, Any],
    process_node: Callable[[Any, AgentRun[Any, Any]], Awaitable[None]],
) -> None:
    """Stream SDK node events inside the native node lifecycle.

    Pydantic AI owns hook ordering, error recovery, cancellation and pending-input
    draining. Its public ``next()`` cannot accept our node-stream consumer; keep
    that integration in this adapter, using the same lifecycle entry point as
    native ``Agent.run(event_stream_handler=...)``.
    """

    async def stream_step(node: Any) -> Any:
        await process_node(node, run)
        return await run._advance_graph(node)  # pyright: ignore[reportPrivateUsage]

    node = run.next_node
    while not isinstance(node, End):
        node = await run._run_node_with_hooks(node, stream_step)  # pyright: ignore[reportPrivateUsage]
