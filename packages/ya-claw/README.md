# YA Claw

Workspace-native single-node agent runtime and web service for the `ya-mono` workspace.

## Scope

YA Claw packages a durable runtime shell around `ya-agent-sdk` with:

- registered workspaces resolved through `WorkspaceProvider`
- reusable agent profiles
- resumable sessions and runs
- in-process active state and async task coordination
- session schedules for timed execution
- SQLite-first durable state with optional PostgreSQL
- local filesystem session continuity and exported state
- a bundled web shell for local and self-hosted use
- bridge adapters that connect IM channels to the YA Claw service

## Current Direction

The target single-node shape runs as one web service.
The runtime keeps active session state, live delivery, async tasks, schedule dispatch, and bridge coordination inside one runtime process.
SQLite is the default durable store.
PostgreSQL remains an optional storage backend for deployments that prefer an external relational database.

## Layout

Key areas in this package:

- `.env.example` — runtime environment example
- `spec/` — architecture and runtime design documents
- `tests/` — runtime tests
- `ya_claw/api/` — HTTP API surface
- `ya_claw/bridge/` — IM bridge adapters and relay logic
- `ya_claw/app.py` and `ya_claw/cli.py` — application entrypoints
- `ya_claw/config.py` — runtime configuration

## Runtime Shape

The runtime shape is:

- one YA Claw web service
- one in-process runtime state manager
- one session scheduler
- one bridge subsystem for external channels
- one shared bearer token for HTTP access
- one SQLite database by default
- optional PostgreSQL
- one runtime data directory for sensitive session continuity
- one workspace root for project data
- one bundled web shell

## Quick Start

From the workspace root, start the default runtime flow:

```bash
uv sync --all-packages
cp packages/ya-claw/.env.example packages/ya-claw/.env
uv run --package ya-claw ya-claw serve --reload
```

Set `YA_CLAW_API_TOKEN` before starting the service.
The development server listens on `http://127.0.0.1:9042` by default.
YA Claw loads `YA_CLAW_*` settings from `packages/ya-claw/.env` and the process environment.
Use [`packages/ya-agent-sdk/.env.example`](../ya-agent-sdk/.env.example) for SDK and tool environment variables.

Default local paths:

- SQLite database: `~/.ya-claw/ya_claw.sqlite3`
- runtime data root: `~/.ya-claw/data`
- workspace root: `~/.ya-claw/workspace`

## External Database

Set `YA_CLAW_DATABASE_URL` in `packages/ya-claw/.env` when you want an external PostgreSQL database.
The default SQLite file stays at `~/.ya-claw/ya_claw.sqlite3`.

## Database Commands

```bash
uv run --package ya-claw ya-claw db upgrade
uv run --package ya-claw ya-claw db current
uv run --package ya-claw ya-claw db history
uv run --package ya-claw ya-claw db revision "add session tables"
```

## Bridge Commands

The CLI owns a top-level bridge command group.

```bash
uv run --package ya-claw ya-claw bridge ls
uv run --package ya-claw ya-claw bridge run lark
uv run --package ya-claw ya-claw bridge serve lark
```

### Bridge Relay Modes

- `task relay` — a bridge submits work to YA Claw as an async session flow and delivers agent output back through the channel adapter or channel CLI
- `stream relay` — a bridge opens a foreground run, consumes SSE from the YA Claw service, and streams channel-ready output directly

## Web Shell

Run the web shell from the repository root:

```bash
make web-dev
```

## Docker

Build from the repository root:

```bash
docker build -f Dockerfile.ya-claw -t ya-claw:dev .
```

## Initial API Surface

Every HTTP route except `/healthz` expects `Authorization: Bearer <YA_CLAW_API_TOKEN>`.

- `GET /healthz` — service health probe with storage and runtime component status
- `GET /api/v1/schedules` — session schedule inspection surface
- `POST /api/v1/bridges/{bridge_id}/dispatch` — bridge ingress surface

## Spec Set

- [`spec/README.md`](spec/README.md)
- [`spec/00-overview.md`](spec/00-overview.md)
- [`spec/01-configuration-and-workspace-provider.md`](spec/01-configuration-and-workspace-provider.md)
- [`spec/02-execution-and-session.md`](spec/02-execution-and-session.md)
- [`spec/03-storage-and-streaming.md`](spec/03-storage-and-streaming.md)
- [`spec/04-api.md`](spec/04-api.md)
- [`spec/05-web-ui-and-operations.md`](spec/05-web-ui-and-operations.md)
