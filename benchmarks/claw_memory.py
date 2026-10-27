"""Offline YA Claw allocation probes (run from the repository root).

uv run --all-packages python benchmarks/claw_memory.py events
uv run --all-packages python benchmarks/claw_memory.py events --baseline-ref 050c847
uv run --all-packages python benchmarks/claw_memory.py history
uv run --all-packages python benchmarks/claw_memory.py checkpoint
uv run --all-packages python benchmarks/claw_memory.py checkpoint --baseline-ref 050c847

The optional baseline reads only the named modules from git, without changing the
checkout or dependencies. History compares the actual native/Foundation streaming
path with and without the old eager-deepcopy boundary (an ablation, not an old SDK).
All measurements exclude imports and input construction. Checkpoints use disposable
normal run-store artifacts; no event journal, paging, provider, or live data is used.
"""

# Assertions validate probe semantics; baseline execution loads trusted local git code.
# ruff: noqa: S101, S102, S603, S607
from __future__ import annotations

import argparse
import asyncio
import gc
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def historical_module(ref: str, path: str, name: str) -> ModuleType:
    source = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True)
    module = ModuleType(name)
    sys.modules[name] = module  # dataclasses resolve postponed annotations here
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def start() -> float:
    gc.collect()
    tracemalloc.start()
    return time.perf_counter()


def report(case: str, started: float, **fields) -> None:
    elapsed = time.perf_counter() - started
    gc.collect()
    retained, peak = tracemalloc.get_traced_memory()
    print(
        json.dumps({
            "case": case,
            "seconds": round(elapsed, 4),
            "retained_mib": round(retained / 2**20, 4),
            "peak_mib": round(peak / 2**20, 4),
            **fields,
        }),
        flush=True,
    )


async def events(ref: str | None) -> None:
    from ya_claw.runtime_state import create_runtime_state

    if ref:
        replay = historical_module(
            ref, "packages/ya-agent-stream-protocol/ya_agent_stream_protocol/agui/replay.py", "baseline_replay"
        )
        # Import before defining ActiveRunHandle so its default_factory uses the
        # historical buffer too, rather than mixing old state with new compaction.
        with patch("ya_agent_stream_protocol.agui.AguiReplayBuffer", replay.AguiReplayBuffer):
            runtime = historical_module(ref, "packages/ya-claw/ya_claw/runtime_state.py", "baseline_runtime")
        create_runtime_state = runtime.create_runtime_state
    started = start()
    state = create_runtime_state()
    handle = state.register_run("session", "run")
    for index in range(20_000):
        await state.append_run_event(
            "run",
            {
                "type": "TEXT_MESSAGE_CHUNK",
                "messageId": "text",
                "delta": f"{index:08d}" + "x" * 56,
            },
        )
    report(
        "events",
        started,
        ref=ref,
        raw_events=len(handle.events),
        fragments=sum(map(len, handle.replay._chunk_fragments.values())),
    )
    snapshot = handle.replay.snapshot()
    assert len(snapshot[0]["delta"]) == 20_000 * 64
    report("events_snapshot", started, ref=ref)
    del handle, snapshot
    state.clear_run("run")
    await state.aclose()
    report("events_cleaned", started, ref=ref)
    tracemalloc.stop()


def make_history():
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart

    messages = [ModelRequest(parts=[UserPromptPart("Read the dataset.")])]
    for index in range(80):
        call_id = f"call_{index}"
        messages.extend([
            ModelResponse(parts=[ToolCallPart("query", {"page": index}, tool_call_id=call_id)]),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        "query",
                        {
                            "rows": [
                                {"id": f"{index}-{row}", "value": f"{index:04d}{row:04d}" + "x" * 248}
                                for row in range(250)
                            ],
                        },
                        tool_call_id=call_id,
                    )
                ]
            ),
        ])
    messages.append(ModelResponse(parts=[TextPart("Dataset received.")]))
    return messages


async def history() -> None:
    from pydantic_ai.messages import ToolReturnPart
    from pydantic_ai.models.test import TestModel
    from ya_agent_environment import Environment
    from ya_agent_sdk.agents.main import create_agent, stream_agent
    from ya_agent_sdk.capabilities import RuntimeFoundationCapability
    from ya_agent_sdk.capabilities.foundation import _request

    class EmptyEnvironment(Environment):
        async def _setup(self):
            pass

        async def _teardown(self, *args):
            pass

    original = _request.apply_history_processor

    async def eager_copy(processor, ctx, request_context, **kwargs):
        kwargs["copy_on_write"] = False
        return await original(processor, ctx, request_context, **kwargs)

    async def turn(messages):
        runtime = create_agent(
            TestModel(call_tools=[], custom_output_text="done"),
            env=EmptyEnvironment(),
            capabilities=[RuntimeFoundationCapability()],
            system_prompt="Use the existing dataset.",
        )
        async with stream_agent(runtime, "Continue.", message_history=messages) as streamer:
            async for _ in streamer:
                pass
            streamer.raise_if_exception()
            assert streamer.run.result.output == "done"
            # Verify the representative tool payload survives the actual native
            # graph and all Foundation hooks, not just a standalone helper.
            result = streamer.run.result.all_messages()
            assert sum(
                len(part.content["rows"])
                for message in result
                for part in message.parts
                if isinstance(part, ToolReturnPart) and isinstance(part.content, dict) and "rows" in part.content
            ) == (20_000 if messages else 0)
        return len(result)

    await turn([])  # warm native schemas/templates outside the measurement
    for strategy in ("eager_deepcopy", "copy_on_write"):
        for repeat in range(3):
            messages = make_history()
            with (
                patch(
                    "ya_agent_sdk.capabilities.foundation.history.apply_history_processor",
                    eager_copy if strategy == "eager_deepcopy" else original,
                ),
                patch(
                    "ya_agent_sdk.capabilities.foundation._request.apply_history_processor",
                    eager_copy if strategy == "eager_deepcopy" else original,
                ),
            ):
                started = start()
                count = await turn(messages)
                report("foundation_native_stream", started, strategy=strategy, repeat=repeat, messages=count)
                tracemalloc.stop()


def checkpoint(ref: str | None) -> None:
    from pydantic_ai.messages import ModelMessagesTypeAdapter
    from ya_claw.config import ClawSettings
    from ya_claw.execution.store import RunStore

    if ref:
        RunStore = historical_module(ref, "packages/ya-claw/ya_claw/execution/store.py", "baseline_store").RunStore
    history = make_history()
    payload = {"message_history": ModelMessagesTypeAdapter.dump_python(history, mode="json"), "context_state": {}}
    for repeat in range(3):
        with TemporaryDirectory(prefix="claw-memory-") as directory:
            store = RunStore(ClawSettings(data_dir=Path(directory)))
            started = start()
            path = store.write_state("run", payload)
            report("checkpoint_write", started, ref=ref, repeat=repeat, artifact_bytes=path.stat().st_size)
            tracemalloc.stop()
            # Decode through the same JSON path as the coordinator to preserve
            # binary restoration semantics. Release the raw JSON after transfer.
            started = start()
            restored = store.read_state("run")
            native = ModelMessagesTypeAdapter.validate_json(json.dumps(restored["message_history"]).encode())
            del restored
            assert len(native) == len(history)
            report("checkpoint_native_restore", started, ref=ref, repeat=repeat, messages=len(native))
            tracemalloc.stop()
            del native


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["events", "history", "checkpoint"])
    parser.add_argument("--baseline-ref")
    args = parser.parse_args()
    if args.mode == "history" and args.baseline_ref:
        parser.error("history uses an eager-copy ablation, not --baseline-ref")
    print(
        json.dumps({
            "python": platform.python_version(),
            "pydantic_ai": importlib.metadata.version("pydantic-ai-slim"),
            "mode": args.mode,
            "baseline_ref": args.baseline_ref,
        })
    )
    if args.mode == "events":
        asyncio.run(events(args.baseline_ref))
    elif args.mode == "history":
        asyncio.run(history())
    else:
        checkpoint(args.baseline_ref)
