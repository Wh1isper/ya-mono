## Repository Overview

`ya-mono` is a workspace-first monorepo managed with `uv`.

Workspace members:

- `packages/ya-agent-sdk` — SDK for building AI agents with Pydantic AI
- `packages/yaacli` — TUI reference implementation built on top of the SDK
- `packages/ya-claw` — workspace-native single-node runtime web service with `WorkspaceProvider`, in-process runtime state, schedules, bridges, and SQLite-first storage
- `packages/ya-agent-platform` — WIP stateless agent service with TBD scope

Shared repository areas:

- `apps/` — frontend applications and user-facing shells
- `skills/` — canonical skill sources and reference material
- `examples/` — runnable SDK examples
- `scripts/` — repository automation scripts
- `.github/` — CI and release workflows
- `Dockerfile.ya-claw` — YA Claw image build
- `Dockerfile.ya-agent-platform` — YA Agent Platform image build
- `.dockerignore` — Docker build context rules

## Primary Package Focus

Most architecture work in this repository targets `packages/ya-agent-sdk` and `packages/ya-claw`.

- **Language**: Python 3.11+
- **Package Manager**: uv
- **Build System**: hatchling
- **Frontend Stack**: Vite + React + TypeScript

## Runtime Direction

- YA Claw is the active runtime product in this repository
- the current delivery target is a single-node runtime
- `WorkspaceProvider` is the core extension boundary
- active session state, live events, async task coordination, schedules, and bridge coordination stay in process
- SQLite is the default durable store
- PostgreSQL is an optional durable store for deployments that prefer an external database
- local filesystem stores exported state and artifacts
- `ya-agent-platform` is a WIP stateless agent service with TBD scope

## Development Workflow

After changing code, run:

1. `make lint`
2. `make check`
3. `make test`

Useful commands:

| Command                      | Description                               |
| ---------------------------- | ----------------------------------------- |
| `make run-claw`              | Run the YA Claw backend                   |
| `make web-dev`               | Run the YA Claw web app                   |
| `make build-claw`            | Build the `ya-claw` package               |
| `make build-platform`        | Build the WIP `ya-agent-platform` package |
| `make docker-build-claw`     | Build the YA Claw Docker image            |
| `make docker-build-platform` | Build the YA Agent Platform Docker image  |

## Environment Configuration

Environment variables are loaded via `pydantic-settings` from the process environment or `.env` files.

- YA Agent SDK example env file: `packages/ya-agent-sdk/.env.example`
- YAACLI example env file: `packages/yaacli/.env.example`
- YA Claw example env file: `packages/ya-claw/.env.example`
- Example runtime env file: `examples/.env.example`
- YAACLI runtime env prefix: `YAACLI_`
- YA Agent SDK runtime env prefix: `YA_AGENT_`
- YA Claw runtime env prefix: `YA_CLAW_`

Keep `packages/ya-agent-sdk/.env.example`, `packages/yaacli/.env.example`, `packages/ya-claw/.env.example`, and `examples/.env.example` updated when environment variables change.

## Notes For Repository Changes

When editing workspace metadata, keep these files aligned:

- `pyproject.toml`
- `packages/ya-agent-sdk/pyproject.toml`
- `packages/yaacli/pyproject.toml`
- `packages/ya-claw/pyproject.toml`
- `packages/ya-agent-platform/pyproject.toml`
- `pnpm-workspace.yaml`
- `Makefile`
- `.github/workflows/*.yml`
- `Dockerfile.ya-claw`
- `Dockerfile.ya-agent-platform`
- `.dockerignore`
- `README.md` and package READMEs
- `packages/ya-claw/spec/*`
- `skills/agent-builder/*`
- `scripts/sync-skills.sh`
