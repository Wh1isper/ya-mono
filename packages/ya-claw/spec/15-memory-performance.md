# Memory Ownership and Performance

This report records the October 27, 2026 Pydantic AI upgrade and memory work. The
optimization removes duplicate active-run representations and eager history copies
while preserving complete canonical history and replay. Runtime events remain in
memory; there is no paging file or raw-event journal.

## Dependency and Native Infrastructure Cutover

The workspace moves from Pydantic AI 2.40.0 to 2.61.0, including matching slim and
graph packages. On October 27, 2026 at 04:24 UTC, all three official PyPI JSON
endpoints still reported 2.61.0; the 2.62.0 version endpoint returned HTTP 404.
GitHub had published v2.62.0, but it was not yet installable from PyPI at this check.

The upgrade adopts these native contracts:

- `ToolReturnPart(outcome="retried")` and `RetryFeedbackPart` replace production
  use of `RetryPromptPart`, including retry budgets, recovery, AGUI, and CLI display.
- `ModelMessagesTypeAdapter` reads old `retry-prompt` saved messages through its
  native legacy adapter. There is no dependency-version rollback layer.
- Node classes come from public Pydantic AI exports. The thin streaming driver
  delegates lifecycle ordering and recovery to `_run_node_with_hooks` and graph
  advancement to `_advance_graph`, replacing the copied lifecycle implementation.
  Those two private calls remain covered by native contract tests.
- Nested Tool Proxy and CodeAct execution use `ToolManager.handle_call` for native
  validation, approval, deferred resolution, and retry outcomes, replacing the
  duplicate deferred protocol.
- Native request views require explicit canonical-history commits. Request-only
  media projection stays separate from persistent history.

The separate `pydantic-ai-harness` compaction and CodeMode features were evaluated.
They do not currently replace YA's exact applied-input ledger, `run_program`, and
host-owned execution persistence. The Responses WebSocket transport also remains:
Pydantic AI realtime is a different protocol, not an equivalent replacement.

## Root Causes and Implemented Changes

| Source                        | Previous ownership                                                           | Implemented ownership                                                                                     |
| ----------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Active SSE events             | Every raw delta retained until run cleanup, plus compact replay              | Ring of at most 512 events and 512 KiB serialized payloads; complete compact replay remains authoritative |
| Replay strings                | One Python string per chunk, plus joined snapshot copies                     | Geometric fragment merging; snapshots share immutable joined text                                         |
| Slow/new SSE subscriptions    | Raw list offsets into the full event history                                 | Monotonic IDs, atomic snapshot/cutover, explicit reset on expired cursor, bounded delivery batches        |
| Browser live history          | Raw deltas truncated to the last 1,000 events                                | Complete coalesced replay, snapshot replacement, ID deduplication and retry cursor                        |
| Browser checkpoint/live merge | Could append the same run's full live prefix after its checkpoint            | Run-scoped replacement in Chat, Debug and Agency; incomplete live state yields to durable terminal state  |
| Foundation history hooks      | Deep-copy the entire history before even checking for a no-op                | Trusted SDK processors share untouched nodes and replace changed nodes; unknown mutators retain isolation |
| Compaction/handoff            | Copy before deciding whether reduction is needed                             | Copy only after the reduction guard passes                                                                |
| SDK stream output             | Unbounded producer queue                                                     | Queue of 128 events with awaited publication and cancellation-safe backpressure                           |
| Restore                       | Load native state and full replay together; retain raw JSON after conversion | Load replay only for legacy reconstruction; release source JSON after native construction                 |
| State checkpoint              | Duplicate exported context keys and a complete serialized JSON string        | One `context_state` field; incremental JSON encoding through normal atomic file replacement               |
| Session locks                 | Registry retained every historical session ID                                | Weak registry while callers own locks; shutdown clears remaining registries                               |

The SSE snapshot is a transport frame (`claw.replay_snapshot`), not a persisted AGUI
event. Its SSE ID is the atomic replay cutover; later events have greater IDs. A slow
subscriber that falls behind receives another complete snapshot. Oversized events
remain in canonical replay even if they cannot fit in the raw ring. See
[Storage and Streaming](03-storage-and-streaming.md) for the protocol contract.

These changes use ownership strategies examined in `agent-foundation` commits
`8c4110f` and `f8fed4f`: private event ownership, bounded raw transport retention,
complete compact snapshots, releasing consumed references, and lazy history copies.
Claw retains its existing run/condition architecture instead of adopting that
project's additional hub, epoch, and lineage layers.

## Reproducible Measurements

Run from the repository root after `uv sync --all-packages`:

```bash
uv run --all-packages python benchmarks/claw_memory.py events --baseline-ref 050c847
uv run --all-packages python benchmarks/claw_memory.py events
uv run --all-packages python benchmarks/claw_memory.py history
uv run --all-packages python benchmarks/claw_memory.py checkpoint --baseline-ref 050c847
uv run --all-packages python benchmarks/claw_memory.py checkpoint
```

Use only trusted local Git revisions for `--baseline-ref`: the benchmark executes
the selected historical modules without changing the checkout or dependencies.

Environment: Linux, Python 3.13.7, Pydantic AI 2.61.0. Measurements use `tracemalloc`
after imports. History/checkpoint input construction is outside the measured region;
event creation is included. Numbers describe Python allocations in these paths,
not whole-service RSS. History and checkpoint values are medians of three runs;
event values are one bounded run, corroborating the earlier investigation.

| Workload / metric                                        |   Baseline | Optimized | Reduction |
| -------------------------------------------------------- | ---------: | --------: | --------: |
| 20,000 unique 64-character deltas: retained active state |  7.781 MiB | 1.426 MiB |     81.7% |
| Same stream with a complete snapshot retained            |  9.002 MiB | 1.426 MiB |     84.2% |
| Native SDK/Foundation turn: additional allocation peak   |  5.703 MiB | 0.476 MiB |     91.7% |
| Same turn: elapsed time with tracing                     |    1.621 s |   0.513 s |     68.4% |
| 7,111,954-byte checkpoint: additional write peak         | 13.695 MiB | 0.166 MiB |     98.8% |

### What Each Measurement Exercises

**Events:** the actual `InMemoryRuntimeState.append_run_event` and replay buffer,
with 1,280,000 characters of complete text. The historical modules come from
`050c847`; both versions run with the same installed dependencies. Raw events fall
from 20,000 to 512 and replay fragments from 20,000 to 5. After cleanup, traced
retained allocations return to approximately 0.001 MiB.

**History:** a real `create_agent` / `stream_agent` / native graph run with the full
`RuntimeFoundationCapability`, offline `TestModel`, and an empty environment. Input
contains 80 tool results, each with 250 distinct structured rows and 256-character
values. The probe verifies all 20,000 rows remain after the run. The baseline is an
ablation restoring eager deep-copy at the Foundation boundary on the same upgraded
runtime; it isolates this ownership change rather than comparing different native
versions. These values were rerun after integrating the native tool-ID and
request-local self-healing changes from main (`122f41c`). Normal requests share
history; matched provider-error repair retains its separate deep-copy boundary.
No compaction or provider call is involved.

**Checkpoint:** actual old/new `RunStore.write_state`, preserving the same encoded
artifact size and atomic replacement. Incremental encoding costs more CPU: median
traced write time rises from 0.156 s to 0.518 s. Event byte accounting and ownership
copying similarly raise the traced 20,000-event ingestion time from 0.269 s to
1.245 s. These are explicit memory/CPU tradeoffs.

**Native restoration:** the benchmark also checks the preserved JSON-to-native
message path. Its peak is approximately 26 MiB for this fixture in both versions;
this decoder cost has not been reduced. The production improvement is avoiding the
additional replay read and releasing raw restore blobs promptly. Binary-content
restoration continues through native `validate_json` rather than `validate_python`.

Separate fresh-process import measurements found that upgrading alone lowered bare
Pydantic AI import RSS from 98.25 to 71.21 MiB, but full Claw app import moved only
from 194.28 to 192.28 MiB. Service imports remain a substantial fixed floor. A narrow
20-run offline SDK lifetime probe retained 0.027 MiB after collection and found no
material leak in that specific workload.

## Follow-up: Historical Retention Query

Read-only inspection of a fresh deployment on October 27, 2026 found a 4.95 GiB
Python-process RSS high-water mark and approximately 1.41 GiB current RSS. The
retention dispatcher started at 05:51:34 UTC with a 300-second startup delay and
completed its first sweep at 05:56:53 without deleting artifacts. The only subsequent
active run started at 06:00:03 with no restore source and a roughly 300 KiB replay.

`SessionPruneController._load_runs()` selected every column of every historical run.
The 12,734 rows contained 801,572,780 characters of serialized input and 899,332,744
characters of metadata. A separate read-only process decoded one row at a time and
summed unique reachable Python-object sizes within each payload: those two columns
accounted for 3,167,083,882 bytes (2.95 GiB), before ORM objects, driver result buffers,
and allocator overhead. No conversation content was printed or copied. This is a
strong causal candidate for the observed startup peak; the original peak itself was
not sampled with an attached profiler.

Retention selection now loads only session IDs/head pointers and run IDs, session
IDs, sequence numbers, restore links, statuses, and creation timestamps. Payload
columns are excluded at SQL execution, before JSON decoding. Existing recent-run,
head, active-run, direct-restore protection, ordering, cutoff, and batch semantics
are unchanged. This needs no schema, retention-policy, or deployment-setting change.
Memory scales with the small index records rather than all historical conversation
content. The index itself still grows with record count.

### Process-level Reproduction

```bash
uv run --all-packages python benchmarks/claw_prune_memory.py --baseline-ref 1a0b1a7e --rows 10000
uv run --all-packages python benchmarks/claw_prune_memory.py --rows 10000
```

The Linux probe seeds disposable SQLite data in a separate process, then executes
the actual retention selector in a fresh process. Each of 10,000 runs has a distinct
65,536-character ASCII input and metadata value (1,250 MiB total payload). Both
versions select the same 100 IDs. No deletion, live data, provider, or event paging
is involved. These are single-run observations on Python 3.13.7:

| Process metric                          |     Baseline | Narrow projection |
| --------------------------------------- | -----------: | ----------------: |
| RSS before query                        |   195.27 MiB |        193.06 MiB |
| Peak RSS                                | 1,464.71 MiB |        219.48 MiB |
| Peak increase over pre-query RSS        | 1,269.44 MiB |         26.41 MiB |
| RSS after session close and explicit GC |   768.85 MiB |        203.52 MiB |
| RSS after engine disposal               |   726.10 MiB |        200.69 MiB |
| Selector elapsed time                   |      3.879 s |           0.493 s |

The additional peak falls by 97.9%. Elevated baseline RSS survives collection after
all run records leave scope, reproducing retained process memory without establishing
an application-object leak. The fix avoids these allocations rather than adding
forced GC, allocator trimming, or disk paging to production. A smaller 2,000-row
probe also drops peak RSS from 453.36 to 202.18 MiB. Deployment-level improvement
must be measured after this follow-up is deployed; these are isolated path results.

A regression verifies that the emitted SQL and loaded ORM attributes exclude input,
metadata, and output payloads while returning unchanged candidates. Existing pruning
tests cover protected heads, active work, restore sources, generated sessions, failed
cleanup, and retries.

## Validation and Remaining Memory Sources

Regression coverage includes old saved retry messages, native lifecycle recovery,
Tool Proxy/CodeAct approval and deferral, history ownership and caller isolation,
full-queue cancellation, replay immutability, expired/future cursors, slow and
concurrent subscribers, FastAPI lifespan GET/POST SSE routes, real fetch-event-source
retry headers, failed/removed live handles, and checkpoint/live UI replacement.

Full canonical history and complete replay still scale with actual conversation
content. The live ring's byte budget measures serialized payloads, not total Python
object overhead. The main output queue bounds event count, not individual payload
size. Existing sideband queues and unrestricted concurrent active runs remain
separate capacity concerns.

Foreground shell execution still collects complete output before SDK preview
bounding. Changing that requires a deliberate output-retention contract; silently
truncating it would lose output previously available to callers. Background shell
buffers already have bounded retention. These shell semantics are unchanged here.

Production-provider traffic, Docker subprocess workloads, and full-service concurrent
RSS were not benchmarked. The measured reductions directly target long active
streams, repeated history processing, and checkpoint serialization, rather than
claiming a fixed percentage reduction for every deployment.
