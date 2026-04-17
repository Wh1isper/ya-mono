# YA Agent Platform

Cloud-ready agent platform package for the `ya-mono` workspace.

## Scope

This package initializes the backend service for a complete agent platform:

- multi-tenant control plane for tenants, cost centers, profiles, bridges, policies, and secrets
- a single configurable `WorkspaceProvider` that maps `project_ids` into agent environments
- chat-facing API for the first-party Web UI and programmatic clients
- role-aware administration for admins and scoped users
- bridge-facing API surface for IM connectors and future channel adapters
- runtime orchestration built on `ya-agent-sdk` with environment-aware scheduling
- persistence scaffold with PostgreSQL, Redis, packaged Alembic migrations, and startup auto-migration
- specification documents that define the target architecture before full implementation

## Current Layout

```text
packages/ya-agent-platform/
├── README.md
├── infra/
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
set -a && source packages/ya-agent-platform/infra/dev.env && set +a
uv run --package ya-agent-platform ya-agent-platform serve --reload
```

The development server listens on `http://127.0.0.1:9042` by default.

## Database and Redis Commands

Use the package CLI directly:

```bash
uv run --package ya-agent-platform ya-agent-platform migrate
uv run --package ya-agent-platform ya-agent-platform db current
uv run --package ya-agent-platform ya-agent-platform db history
uv run --package ya-agent-platform ya-agent-platform db migrate "add workspace provider tables"
```

Use the workspace Makefile wrappers:

```bash
make platform-db-upgrade
make platform-db-current
make platform-db-history
make platform-db-migrate MSG="add workspace provider tables"
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

Default development URLs live in `packages/ya-agent-platform/infra/dev.env`.

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

The spec is organized around a multi-tenant, cloud-ready platform model with simple admin/user roles, first-class cost centers, and one configurable `WorkspaceProvider`.

Primary documents:

- [`spec/README.md`](spec/README.md)
- [`spec/000-platform-overview.md`](spec/000-platform-overview.md)
- [`spec/001-product-model.md`](spec/001-product-model.md)
- [`spec/002-multi-tenancy-and-identity.md`](spec/002-multi-tenancy-and-identity.md)
- [`spec/003-control-plane.md`](spec/003-control-plane.md)
- [`spec/004-runtime-and-environments.md`](spec/004-runtime-and-environments.md)
- [`spec/005-session-and-execution-model.md`](spec/005-session-and-execution-model.md)
- [`spec/006-events-streaming-and-notifications.md`](spec/006-events-streaming-and-notifications.md)
- [`spec/007-bridge-protocol.md`](spec/007-bridge-protocol.md)
- [`spec/008-http-api.md`](spec/008-http-api.md)
- [`spec/009-web-ui.md`](spec/009-web-ui.md)
- [`spec/010-deployment-topology.md`](spec/010-deployment-topology.md)
- [`spec/011-data-model.md`](spec/011-data-model.md)

## Next Build Phase

1. add multi-tenant persistence models, cost centers, and auth context
2. add `WorkspaceProvider` integration and provider-aware runtime resolution
3. add control-plane CRUD for tenants, agent profiles, environment profiles, bridges, and grants
4. add runtime scheduling, session orchestration, and durable replay storage
5. connect the Web UI to live chat, admin, usage, and audit endpoints
