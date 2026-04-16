# YA Agent Platform

Cloud-ready agent platform package for the `ya-mono` workspace.

## Scope

This package initializes the backend service for a complete agent platform:

- management API for platform and workspace administration
- chat-facing API for first-party Chat UI
- bridge-facing API surface for IM connectors
- runtime integration points for `ya-agent-sdk`
- specification documents that define the target architecture before full implementation

## Current Layout

```text
packages/ya-agent-platform/
├── pyproject.toml
├── README.md
├── spec/
├── tests/
└── ya_agent_platform/
    ├── api/
    ├── app.py
    ├── cli.py
    └── config.py
```

## Quick Start

From the workspace root:

```bash
uv sync --all-packages
uv run --package ya-agent-platform ya-agent-platform serve --reload
```

The development server listens on `http://127.0.0.1:9042` by default.

## Combined Docker Image

The repository root `Dockerfile` builds a single production image that contains:

- the `ya-agent-platform` backend
- the bundled `ya-agent-platform-web` frontend
- FastAPI static serving for the built web assets

Build locally from the repository root:

```bash
docker build -t ya-agent-platform:dev .
```

Run locally:

```bash
docker run --rm -p 9042:9042 ya-agent-platform:dev
```

The container serves the combined application on `http://127.0.0.1:9042`.

## Container Publishing

GitHub Actions publishes this image to GHCR with these tags:

- `dev` on every push to `main`
- `<release-tag>` on every published release
- `latest` on every published release

## Initial API Surface

- `GET /healthz` — service health probe
- `GET /api/v1/platform/info` — platform metadata and enabled surfaces
- `GET /api/v1/platform/topology` — high-level component topology for the UI and tooling

## Specification Set

- [`spec/README.md`](spec/README.md)
- [`spec/000-platform-overview.md`](spec/000-platform-overview.md)
- [`spec/001-system-architecture.md`](spec/001-system-architecture.md)
- [`spec/002-bridge-contract.md`](spec/002-bridge-contract.md)
- [`spec/003-http-api.md`](spec/003-http-api.md)

## Next Build Phase

1. add persistence and identity models
2. add runtime orchestration and worker execution
3. add bridge registry and delivery guarantees
4. connect the web app to live platform endpoints
