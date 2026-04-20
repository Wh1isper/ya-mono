## Repository Overview

`ya-mono` is a workspace-first monorepo managed with `uv`.

Workspace members:

- `packages/ya-agent-sdk` — SDK for building AI agents with Pydantic AI
- `packages/yaacli` — TUI reference implementation built on top of the SDK
- `packages/ya-claw` — workspace-native single-node runtime with `WorkspaceProvider`, PostgreSQL, and Redis
- `packages/ya-agent-platform` — reserved package name with TBD scope

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

## YA Claw Package Structure

```text
packages/ya-claw/
├── pyproject.toml
├── README.md
├── infra/
├── spec/
├── tests/
└── ya_claw/
    ├── api/
    ├── app.py
    ├── cli.py
    ├── config.py
    └── __main__.py
```

## Reserved Package Structure

```text
packages/ya-agent-platform/
├── pyproject.toml
├── README.md
└── ya_agent_platform/
    └── __init__.py
```

## Web App Structure

```text
apps/ya-claw-web/
├── package.json
├── README.md
├── index.html
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   └── styles.css
└── vite.config.ts
```

## Runtime Direction

- YA Claw is the active runtime product in this repository
- the current delivery target is a single-node runtime
- `WorkspaceProvider` is the core extension boundary
- PostgreSQL stores durable relational state
- Redis handles live events and coordination
- local filesystem stores exported state and artifacts
- `ya-agent-platform` stays reserved with TBD scope

## Development Workflow

After changing code, run:

1. `make lint`
2. `make check`
3. `make test`

Useful commands:

| Command                      | Description                                    |
| ---------------------------- | ---------------------------------------------- |
| `make run-claw`              | Run the YA Claw backend                        |
| `make claw-infra-up`         | Start YA Claw PostgreSQL and Redis             |
| `make claw-infra-down`       | Stop YA Claw PostgreSQL and Redis              |
| `make web-dev`               | Run the YA Claw web app                        |
| `make build-claw`            | Build the `ya-claw` package                    |
| `make build-platform`        | Build the reserved `ya-agent-platform` package |
| `make docker-build-claw`     | Build the YA Claw Docker image                 |
| `make docker-build-platform` | Build the YA Agent Platform Docker image       |

## Environment Configuration

Environment variables are loaded via `pydantic-settings` from the process environment or `.env` files.

- Repository example env file: `.env.example`
- Example runtime env file: `examples/.env.example`
- YA Claw runtime env prefix: `YA_CLAW_`

Keep `.env.example` updated when environment variables change.

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
