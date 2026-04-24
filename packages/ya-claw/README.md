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
make run-claw
```

Set `YA_CLAW_API_TOKEN` before starting the service.
The development server listens on `http://127.0.0.1:9042` by default.
YA Claw loads `YA_CLAW_*` settings from `packages/ya-claw/.env` and the process environment.
YA Claw startup also exports provider variables such as `GATEWAY_API_KEY` and `GATEWAY_BASE_URL` from `packages/ya-claw/.env` into the process environment.
Use [`packages/ya-agent-sdk/.env.example`](../ya-agent-sdk/.env.example) for shared SDK and tool environment variables when you want the same keys outside YA Claw startup.
Set `YA_CLAW_PROFILE_SEED_FILE` plus `YA_CLAW_AUTO_SEED_PROFILES=true` when you want packaged profiles to seed into the database on startup.
Set `YA_CLAW_EXECUTION_MODEL` when you want runs to auto-dispatch through the built-in coordinator.
Without that setting, created runs stay queued until another execution path picks them up.

Profile, MCP, and coordinator settings:

- `YA_CLAW_PROFILE_SEED_FILE=packages/ya-claw/profiles.yaml`
- `YA_CLAW_AUTO_SEED_PROFILES=true`
- `YA_CLAW_DEFAULT_PROFILE=default`
- `YA_CLAW_MCP_CONFIG_FILE=~/.ya-claw/mcp.json`
- `YA_CLAW_PROJECT_MCP_CONFIG_PATH=.ya-claw/mcp.json`
- `YA_CLAW_WORKSPACE_PROVIDER_BACKEND=local|docker`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_IMAGE=python:3.11`
- `YA_CLAW_EXECUTION_CONTEXT_WINDOW=200000`

Profiles store model, prompt, builtin tool groups, subagents, approval policy, and MCP namespace filters. Runtime-wide MCP server definitions load from `~/.ya-claw/mcp.json` with per-workspace override at `.ya-claw/mcp.json`. Every YA Claw agent runtime receives the active MCP configuration through `ToolProxyToolset`, and each profile can narrow that surface with `enabled_mcps` and `disabled_mcps`.

Session and run requests accept `project_id` for a single workspace and `projects` for multi-project workspaces. Each project entry carries `project_id` plus optional `description`; YA Claw maps every project to a host directory under `YA_CLAW_WORKSPACE_ROOT` and exposes it at `/workspace/{project_id}` for file operations and shell execution. Project skills are discovered from each mounted project's `.agents/skills/` directory.

Profiles can be managed through:

- REST API: `/api/v1/profiles`
- Seed API: `POST /api/v1/profiles/seed`
- CLI: `ya-claw profiles seed`

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
- `POST /api/v1/sessions` — create a session with optional first run
- `GET /api/v1/sessions` — list sessions
- `GET /api/v1/sessions/{session_id}` — inspect a session plus paginated runs and optional compacted message replay lists
- `POST /api/v1/sessions/{session_id}/runs` — create a run under a session
- `POST /api/v1/sessions/{session_id}/steer` — steer the active run through the session surface
- `POST /api/v1/sessions/{session_id}/interrupt` — interrupt the active run through the session surface
- `POST /api/v1/sessions/{session_id}/cancel` — cancel the active run through the session surface
- `POST /api/v1/runs` — create a run directly through the low-level surface
- `GET /api/v1/runs/{run_id}` — inspect a run plus session summary, committed state, and optional compacted message replay list
- `POST /api/v1/runs/{run_id}/steer` — steer a specific active run
- `POST /api/v1/runs/{run_id}/interrupt` — interrupt a specific active run
- `POST /api/v1/runs/{run_id}/cancel` — cancel a specific active run

## Spec Set

- [`spec/README.md`](spec/README.md)
- [`spec/00-overview.md`](spec/00-overview.md)
- [`spec/01-configuration-and-workspace-provider.md`](spec/01-configuration-and-workspace-provider.md)
- [`spec/02-execution-and-session.md`](spec/02-execution-and-session.md)
- [`spec/03-storage-and-streaming.md`](spec/03-storage-and-streaming.md)
- [`spec/04-api.md`](spec/04-api.md)
- [`spec/05-web-ui-and-operations.md`](spec/05-web-ui-and-operations.md)
