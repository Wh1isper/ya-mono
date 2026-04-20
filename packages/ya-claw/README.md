# YA Claw

Workspace-native single-node agent runtime for the `ya-mono` workspace.

## Scope

YA Claw packages a durable runtime shell around `ya-agent-sdk` with:

- registered workspaces resolved through `WorkspaceProvider`
- reusable agent profiles
- resumable sessions and runs
- PostgreSQL-backed relational state
- Redis-backed live events and coordination
- a bundled web shell for local and self-hosted use

## Current Direction

The current delivery target is a single-node runtime with one API service, one PostgreSQL, one Redis, and a local filesystem data root.

## Layout

```text
packages/ya-claw/
├── README.md
├── infra/
│   ├── dev.env
│   └── docker-compose.dev.yml
├── pyproject.toml
├── spec/
├── start.sh
├── tests/
└── ya_claw/
    ├── alembic/
    ├── api/
    ├── app.py
    ├── cli.py
    ├── config.py
    ├── db/
    └── redis.py
```

## Quick Start

From the workspace root:

```bash
uv sync --all-packages
make claw-infra-up
set -a && source packages/ya-claw/infra/dev.env && set +a
uv run --package ya-claw ya-claw serve --reload
```

The development server listens on `http://127.0.0.1:9042` by default.

## Database and Redis Commands

```bash
uv run --package ya-claw ya-claw migrate
uv run --package ya-claw ya-claw db current
uv run --package ya-claw ya-claw db history
uv run --package ya-claw ya-claw db migrate "add session tables"
```

## Web Shell

Run the web shell from the repository root:

```bash
make web-dev
```

## Development Infrastructure

```bash
make claw-infra-up
make claw-infra-status
make claw-infra-down
```

Default development URLs live in `packages/ya-claw/infra/dev.env`.

## Docker

Build from the repository root:

```bash
docker build -f Dockerfile.ya-claw -t ya-claw:dev .
```

## Initial API Surface

- `GET /healthz` — service health probe with PostgreSQL and Redis component status
- `GET /api/v1/claw/info` — runtime metadata and active surfaces
- `GET /api/v1/claw/topology` — high-level component topology for the UI and tooling

## Spec Set

- [`spec/README.md`](spec/README.md)
- [`spec/000-product-overview.md`](spec/000-product-overview.md)
- [`spec/001-system-architecture.md`](spec/001-system-architecture.md)
- [`spec/002-workspace-provider.md`](spec/002-workspace-provider.md)
- [`spec/003-session-and-runtime.md`](spec/003-session-and-runtime.md)
- [`spec/004-storage-and-streaming.md`](spec/004-storage-and-streaming.md)
- [`spec/005-http-api-and-web-ui.md`](spec/005-http-api-and-web-ui.md)
