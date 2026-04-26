# YA Claw

Workspace-native single-node agent runtime and web service for the `ya-mono` workspace.

## Scope

YA Claw packages a durable runtime shell around `ya-agent-sdk` with:

- one persistent workspace resolved through `WorkspaceProvider`
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
- one persistent workspace directory
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
Set `YA_CLAW_PROFILE_SEED_FILE` plus `YA_CLAW_AUTO_SEED_PROFILES=true` when you want packaged profiles to seed into the database on startup. Seeded profiles use create/update semantics: every startup refreshes matching database profiles from the YAML file, including subagent configuration, while profiles absent from the YAML file remain in the database.
Runs auto-dispatch through the built-in coordinator and resolve model/runtime behavior from AgentProfile rows. The default profile name is `default`.

Profile, MCP, and coordinator settings:

- `YA_CLAW_PROFILE_SEED_FILE=packages/ya-claw/profiles.yaml`
- `YA_CLAW_AUTO_SEED_PROFILES=true`
- `YA_CLAW_DEFAULT_PROFILE=default`
- `YA_CLAW_WORKSPACE_PROVIDER_BACKEND=local|docker`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_IMAGE=ghcr.io/wh1isper/ya-claw-workspace:latest`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOST_WORKSPACE_DIR=/srv/ya-claw/workspace`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_UID=<service process UID>`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_GID=<service process GID>`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXEC_USER=auto`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOME=/home/claw`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_CONTAINER_CACHE_DIR=~/.ya-claw/data/docker-workspace-containers`
- `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXTRA_MOUNTS=/srv/ya-claw/home:/home/claw:rw,/srv/ya-claw/cache:/cache:ro`
- `YA_CLAW_WORKSPACE_ENV_VARS=MY_TOOL_API_KEY,MY_TOOL_ENDPOINT`
- `YA_CLAW_BRIDGE_DISPATCH_MODE=embedded|manual`
- `YA_CLAW_BRIDGE_ENABLED_ADAPTERS=lark`
- `YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx`
- `YA_CLAW_BRIDGE_LARK_APP_SECRET=...`
- `YA_CLAW_BRIDGE_LARK_DEFAULT_PROFILE=default`
- `YA_CLAW_BRIDGE_LARK_EVENT_TYPES=im.chat.member.bot.added_v1,im.chat.member.user.added_v1,im.message.receive_v1,drive.notice.comment_add_v1`
- `YA_CLAW_BRIDGE_LARK_REPLY_IDENTITY=bot`
- `LARKSUITE_CLI_APP_ID=cli_xxx`
- `LARKSUITE_CLI_APP_SECRET=...`
- `LARKSUITE_CLI_BRAND=feishu`
- `LARKSUITE_CLI_DEFAULT_AS=bot`
- `LARKSUITE_CLI_STRICT_MODE=bot`
- `LARK_APP_ID=cli_xxx`
- `LARK_APP_SECRET=...`

Profiles store model, prompt, model context config, builtin tool groups, subagents, approval policy, MCP server definitions, and MCP namespace filters. YA Claw accepts profile MCP servers with `streamable_http` transport. Every YA Claw agent runtime receives the profile MCP configuration through `ToolProxyToolset`, and each profile can narrow that surface with `enabled_mcps` and `disabled_mcps`.

Session and run requests use the shared workspace configured by `YA_CLAW_WORKSPACE_DIR`. YA Claw maps that host directory to `/workspace` for file operations and shell execution. Workspace guidance loads from `/workspace/AGENTS.md`, and workspace skills are discovered from `/workspace/.agents/skills/`.

Workspace environments receive official `lark-cli` credential variables (`LARKSUITE_CLI_APP_ID`, `LARKSUITE_CLI_APP_SECRET`, `LARKSUITE_CLI_BRAND`, `LARKSUITE_CLI_DEFAULT_AS`, `LARKSUITE_CLI_STRICT_MODE`) from explicit process environment values or from the configured Lark bridge app settings. YA Claw also injects legacy `LARK_APP_ID` and `LARK_APP_SECRET` aliases for compatibility with other tooling. `YA_CLAW_WORKSPACE_ENV_VARS` forwards additional comma-separated process environment variable names into workspace environments. For Docker workspaces, forwarded values are passed at reusable workspace container creation time.

The default Docker workspace image is `ghcr.io/wh1isper/ya-claw-workspace:latest`. It is based on Debian stable and includes Python, Node.js, Debian Chromium, the `agent-browser` CLI, and an `agent-browser` discovery skill copied into mounted workspaces at container start. Auto-started workspace containers receive `YA_CLAW_WORKSPACE_UID`, `YA_CLAW_WORKSPACE_GID`, `YA_CLAW_HOST_UID`, and `YA_CLAW_HOST_GID`; the default values come from the YA Claw service process UID/GID and can be overridden with `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_UID` and `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_GID`. Docker exec uses `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXEC_USER=auto` by default, which resolves to the configured workspace UID:GID, and sets `HOME` from `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOME` with default `/home/claw`. `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXTRA_MOUNTS` adds comma-separated `host_path:container_path[:mode]` mounts to Docker workspace containers, with `rw` and `ro` modes. Docker workspace containers reuse one stable container for the configured workspace, cache the container ID under `~/.ya-claw/data/docker-workspace-containers`, check running and Docker health status before each reuse, start stopped containers, and refresh the cache after container recreation. Use `agent-browser skills get core` inside a workspace session for the version-matched browser automation workflow.

Profiles can be managed through:

- REST API: `/api/v1/profiles`
- Seed API: `POST /api/v1/profiles/seed`
- CLI: `ya-claw profiles seed`

Default local paths:

- SQLite database: `~/.ya-claw/ya_claw.sqlite3`
- runtime data root: `~/.ya-claw/data`
- workspace directory: `~/.ya-claw/data/workspace`

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

### Bridge Dispatch

Bridge dispatch controls whether the YA Claw HTTP server starts bridge adapters:

- `embedded` starts enabled adapters inside the YA Claw server lifespan under `BridgeSupervisor`.
- `manual` starts the YA Claw HTTP server without starting `BridgeSupervisor`.

Bridge adapters submit inbound events through the same session/run controller path used by HTTP requests, so bridge ingress behaves as a self-request inside the service process. The Lark bridge reads `YA_CLAW_BRIDGE_LARK_EVENT_TYPES` as a comma-separated event allowlist. The default allowlist covers bot-added-to-chat, user-added-to-chat, message receive, and Drive comment notification events. Message receive events map each `tenant_key + chat_id` pair to one YA Claw session. Other Lark events use `chat_id` when present and fall back to a stable event or Drive conversation key. Every accepted inbound event creates a queued bridge-triggered run, and the agent replies or acts from the workspace with `lark-cli`.

## Web Shell

Run the web shell from the repository root:

```bash
make web-dev
```

## Docker

Build the YA Claw service image from the repository root:

```bash
docker build -f Dockerfile.ya-claw -t ya-claw:dev .
```

Build the official workspace image locally:

```bash
docker build -f Dockerfile.ya-claw-workspace -t ya-claw-workspace:dev .
```

Build the workspace image with a default UID/GID baked in:

```bash
docker build \
  --build-arg WORKSPACE_UID=1000 \
  --build-arg WORKSPACE_GID=1000 \
  -f Dockerfile.ya-claw-workspace \
  -t ya-claw-workspace:dev .
```

Run the YA Claw service image under a specific UID/GID:

```bash
docker run \
  -e YA_CLAW_RUN_UID=1000 \
  -e YA_CLAW_RUN_GID=1000 \
  -e YA_CLAW_API_TOKEN=replace-with-a-long-random-token \
  ya-claw:dev
```

## Initial API Surface

Every HTTP route except `/healthz` expects `Authorization: Bearer <YA_CLAW_API_TOKEN>`.

- `GET /healthz` — service health probe with storage and runtime component status
- `POST /api/v1/sessions` — create a session with optional first queued run and return JSON
- `POST /api/v1/sessions:stream` — create a session with a first run and stream foreground SSE events
- `GET /api/v1/sessions` — list sessions
- `GET /api/v1/sessions/{session_id}` — inspect a session plus paginated runs, top-level committed state, and optional compacted message replay lists
- `POST /api/v1/sessions/{session_id}/runs` — create a run under a session and return JSON
- `POST /api/v1/sessions/{session_id}/runs:stream` — create a run under a session and stream foreground SSE events
- `POST /api/v1/sessions/{session_id}/steer` — steer the active run through the session surface
- `POST /api/v1/sessions/{session_id}/interrupt` — interrupt the active run through the session surface
- `POST /api/v1/sessions/{session_id}/cancel` — cancel the active run through the session surface
- `POST /api/v1/runs` — create a run directly through the low-level surface and return JSON
- `POST /api/v1/runs:stream` — create a run directly and stream foreground SSE events
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
