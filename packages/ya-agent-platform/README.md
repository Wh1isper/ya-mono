# YA Agent Platform

Cloud-ready agent platform package for the `ya-mono` workspace.

## Scope

This package initializes the backend service for a complete agent platform:

- management API for platform and workspace administration
- chat-facing API for first-party Chat UI
- bridge-facing API surface for IM connectors
- runtime integration points for `ya-agent-sdk`
- persistence scaffold with PostgreSQL, Redis, packaged Alembic migrations, and startup auto-migration
- specification documents that define the target architecture before full implementation

## Current Layout

```text
packages/ya-agent-platform/
├── README.md
├── dev/
│   ├── dev.env
│   └── docker-compose.dev.yml
├── pyproject.toml
├── spec/
├── start.sh
├── tests/
└── ya_agent_platform/
    ├── alembic/
    ├── alembic.ini
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
make platform-infra-up
set -a && source packages/ya-agent-platform/dev/dev.env && set +a
uv run --package ya-agent-platform ya-agent-platform serve --reload
```

The development server listens on `http://127.0.0.1:9042` by default.

## Database and Redis Commands

Use the package CLI directly:

```bash
uv run --package ya-agent-platform ya-agent-platform migrate
uv run --package ya-agent-platform ya-agent-platform db current
uv run --package ya-agent-platform ya-agent-platform db history
uv run --package ya-agent-platform ya-agent-platform db migrate "add workspace tables"
```

Use the workspace Makefile wrappers:

```bash
make platform-db-upgrade
make platform-db-current
make platform-db-history
make platform-db-migrate MSG="add workspace tables"
```

## Auto Migration

`YA_PLATFORM_AUTO_MIGRATE=true` is the default behavior.

- `ya-agent-platform serve` applies migrations before boot when `YA_PLATFORM_DATABASE_URL` is configured
- `ya-agent-platform migrate` runs migrations separately
- `start.sh` applies migrations before starting the server in container environments

## Development Infrastructure

The dev compose file starts PostgreSQL and Redis:

```bash
make platform-infra-up
make platform-infra-status
make platform-infra-down
```

Default development URLs live in `packages/ya-agent-platform/dev/dev.env`.

## Combined Docker Image

The repository root `Dockerfile` builds a single production image that contains:

- the `ya-agent-platform` backend
- the bundled `ya-agent-platform-web` frontend
- FastAPI static serving for the built web assets
- startup auto-migration support through `packages/ya-agent-platform/start.sh`

Build locally from the repository root:

```bash
docker build -t ya-agent-platform:dev .
```

Run locally:

```bash
docker run --rm -p 9042:9042 ya-agent-platform:dev
```

The container serves the combined application on `http://127.0.0.1:9042`.

## Initial API Surface

- `GET /healthz` — service health probe with postgres and redis component status
- `GET /api/v1/platform/info` — platform metadata and enabled surfaces
- `GET /api/v1/platform/topology` — high-level component topology for the UI and tooling

## Specification Set

- [`spec/README.md`](spec/README.md)
- [`spec/000-platform-overview.md`](spec/000-platform-overview.md)
- [`spec/001-system-architecture.md`](spec/001-system-architecture.md)
- [`spec/002-bridge-contract.md`](spec/002-bridge-contract.md)
- [`spec/003-http-api.md`](spec/003-http-api.md)

## Next Build Phase

1. add persistence models and first migrations
2. add runtime orchestration and worker execution
3. add bridge registry and delivery guarantees
4. connect the web app to live platform endpoints
