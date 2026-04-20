# ya-mono

> Yet Another Agents

[![Release](https://img.shields.io/github/v/release/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/wh1isper/ya-mono/main.yml?branch=main)](https://github.com/wh1isper/ya-mono/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/wh1isper/ya-mono/graph/badge.svg?token=UOM3ONfEb4)](https://codecov.io/gh/wh1isper/ya-mono)
[![License](https://img.shields.io/github/license/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/blob/main/LICENSE)

## Packages

- [`packages/ya-agent-sdk`](packages/ya-agent-sdk) — Python SDK for building AI agents with Pydantic AI
- [`packages/yaacli`](packages/yaacli) — TUI reference implementation built on top of `ya-agent-sdk`
- [`packages/ya-claw`](packages/ya-claw) — workspace-native single-node runtime with `WorkspaceProvider`, PostgreSQL, and Redis
- [`packages/ya-agent-platform`](packages/ya-agent-platform) — reserved package name with TBD scope

## Apps

- [`apps/ya-claw-web`](apps/ya-claw-web) — Vite + React web shell for YA Claw

## Repository Layout

- [`packages/`](packages/) — publishable workspace members
- [`apps/`](apps/) — frontend applications and user-facing shells
- [`skills/`](skills/) — canonical skill sources and reference material
- [`examples/`](examples/) — runnable SDK examples
- [`scripts/`](scripts/) — repository automation scripts
- [`.github/`](.github/) — CI and release workflows

## Primary Skill Source

- [`skills/agent-builder/`](skills/agent-builder/) — source of truth for the `agent-builder` skill bundled into YAACLI

## Installation

Prerequisites:

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- `make`
- Node.js with `corepack` available for the web app

Clone the repository and install the workspace environment:

```bash
git clone https://github.com/wh1isper/ya-mono.git
cd ya-mono
make install
```

Install the bundled `agent-builder` skill into `~/.agents/skills`:

```bash
make install-skills
```

## Getting Started

### SDK and CLI

Recommended starting points:

- Read [`skills/agent-builder/SKILL.md`](skills/agent-builder/SKILL.md) for the main agent-building workflow
- Read [`skills/agent-builder/README.md`](skills/agent-builder/README.md) for the skill file map
- Run examples from [`examples/`](examples/) for end-to-end usage patterns

### YA Claw

Read the runtime design docs:

- [`packages/ya-claw/spec/README.md`](packages/ya-claw/spec/README.md)
- [`packages/ya-claw/spec/000-product-overview.md`](packages/ya-claw/spec/000-product-overview.md)
- [`packages/ya-claw/spec/002-workspace-provider.md`](packages/ya-claw/spec/002-workspace-provider.md)

Run the local development infrastructure:

```bash
make claw-infra-up
```

Run the backend:

```bash
make run-claw
```

Run the web shell:

```bash
make web-dev
```

Build the images:

```bash
make docker-build-claw
make docker-build-platform
```

## Dockerfiles

- `Dockerfile.ya-claw` — YA Claw image build
- `Dockerfile.ya-agent-platform` — YA Agent Platform image build

## Development

Run repository checks:

```bash
make lint
make check
make test
```

## Package Guides

- [ya-agent-sdk README](packages/ya-agent-sdk/README.md)
- [yaacli README](packages/yaacli/README.md)
- [ya-claw README](packages/ya-claw/README.md)
- [ya-agent-platform README](packages/ya-agent-platform/README.md)
- [agent-builder skill](skills/agent-builder/SKILL.md)
- [Contributing Guide](CONTRIBUTING.md)

## Workspace Commands

| Command                      | Description                                                         |
| ---------------------------- | ------------------------------------------------------------------- |
| `make install`               | Install Python dependencies, web dependencies, and pre-commit hooks |
| `make install-skills`        | Install the `agent-builder` skill bundle into `~/.agents/skills`    |
| `make lint`                  | Check lock consistency and run pre-commit hooks                     |
| `make check`                 | Run lock validation, lint, pyright, deptry, and web checks          |
| `make test`                  | Run SDK, CLI, and YA Claw tests                                     |
| `make run-claw`              | Run the YA Claw backend                                             |
| `make claw-infra-up`         | Start YA Claw PostgreSQL and Redis                                  |
| `make claw-infra-down`       | Stop YA Claw PostgreSQL and Redis                                   |
| `make web-dev`               | Run the YA Claw web app                                             |
| `make build-claw`            | Build the `ya-claw` distribution                                    |
| `make build-platform`        | Build the reserved `ya-agent-platform` package                      |
| `make build-all`             | Build distributions for all workspace packages                      |
| `make docker-build-claw`     | Build the YA Claw Docker image                                      |
| `make docker-build-platform` | Build the YA Agent Platform Docker image                            |

## License

BSD 3-Clause License. See [LICENSE](LICENSE).
