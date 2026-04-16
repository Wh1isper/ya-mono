# ya-mono

> Yet Another Agents

[![Release](https://img.shields.io/github/v/release/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/wh1isper/ya-mono/main.yml?branch=main)](https://github.com/wh1isper/ya-mono/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/wh1isper/ya-mono/graph/badge.svg?token=UOM3ONfEb4)](https://codecov.io/gh/wh1isper/ya-mono)
[![License](https://img.shields.io/github/license/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/blob/main/LICENSE)

## Packages

- [`packages/ya-agent-sdk`](packages/ya-agent-sdk) — Python SDK for building AI agents with Pydantic AI
- [`packages/yaacli`](packages/yaacli) — TUI reference implementation built on top of `ya-agent-sdk`
- [`packages/ya-agent-platform`](packages/ya-agent-platform) — cloud-ready backend package for platform APIs, orchestration, and bridge integration

## Apps

- [`apps/ya-agent-platform-web`](apps/ya-agent-platform-web) — Vite + React web shell for management and chat surfaces

## Repository Layout

- [`packages/`](packages/) — publishable workspace members
- [`apps/`](apps/) — frontend applications and user-facing shells
- [`skills/`](skills/) — canonical skill sources and reference material
- [`examples/`](examples/) — runnable SDK examples
- [`scripts/`](scripts/) — repository automation scripts
- [`.github/`](.github/) — CI and release workflows

## Primary Skill Source

- [`skills/agent-builder/`](skills/agent-builder) — source of truth for the `agent-builder` skill bundled into YAACLI

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

A practical flow for agent setup is:

1. Run `make install`.
2. Run `make install-skills`.
3. Tell your agent to read `skills/agent-builder/SKILL.md` in this repository, or read the installed copy under `~/.agents/skills/agent-builder/SKILL.md`.
4. Start from `examples/general.py`, `examples/deepresearch.py`, or `examples/browser_use.py` depending on the workflow.

When you want to run the local CLI with the latest bundled skills, use:

```bash
make cli
```

### YA Agent Platform

Run the backend:

```bash
make run-platform
```

Run the web shell:

```bash
make web-dev
```

Build and run the combined Docker image:

```bash
make docker-build-platform
make docker-run-platform
```

Published platform image tags:

- `ghcr.io/wh1isper/ya-agent-platform:dev` on every update to `main`
- `ghcr.io/wh1isper/ya-agent-platform:<release-tag>` on each published release
- `ghcr.io/wh1isper/ya-agent-platform:latest` on each published release

Read the initial architecture docs here:

- [`packages/ya-agent-platform/spec/README.md`](packages/ya-agent-platform/spec/README.md)
- [`packages/ya-agent-platform/spec/000-platform-overview.md`](packages/ya-agent-platform/spec/000-platform-overview.md)
- [`packages/ya-agent-platform/spec/001-system-architecture.md`](packages/ya-agent-platform/spec/001-system-architecture.md)
- [`packages/ya-agent-platform/spec/002-bridge-contract.md`](packages/ya-agent-platform/spec/002-bridge-contract.md)
- [`packages/ya-agent-platform/spec/003-http-api.md`](packages/ya-agent-platform/spec/003-http-api.md)

## Development

Run repository checks:

```bash
make lint
make check
make test
```

Run package-specific targets:

```bash
make test-platform
make build-platform
```

## Package Guides

- [ya-agent-sdk README](packages/ya-agent-sdk/README.md)
- [yaacli README](packages/yaacli/README.md)
- [ya-agent-platform README](packages/ya-agent-platform/README.md)
- [agent-builder skill](skills/agent-builder/SKILL.md)
- [Contributing Guide](CONTRIBUTING.md)

## Workspace Commands

| Command                      | Description                                                            |
| ---------------------------- | ---------------------------------------------------------------------- |
| `make install`               | Install Python dependencies, web dependencies, and pre-commit hooks    |
| `make install-skills`        | Install the `agent-builder` skill bundle into `~/.agents/skills`       |
| `make lint`                  | Check lock consistency and run pre-commit hooks                        |
| `make check`                 | Run lock validation, lint, pyright, and deptry for all Python packages |
| `make test`                  | Run SDK, CLI, and platform tests                                       |
| `make test-sdk`              | Run SDK tests only                                                     |
| `make test-cli`              | Run CLI tests only                                                     |
| `make test-platform`         | Run YA Agent Platform tests only                                       |
| `make cli`                   | Sync skill assets and launch `yaacli`                                  |
| `make run-platform`          | Run the YA Agent Platform backend                                      |
| `make web-install`           | Install web dependencies for `apps/ya-agent-platform-web`              |
| `make web-dev`               | Run the YA Agent Platform web app                                      |
| `make docker-build-platform` | Build the combined YA Agent Platform Docker image                      |
| `make docker-run-platform`   | Run the combined YA Agent Platform Docker image                        |
| `make build`                 | Build the `ya-agent-sdk` distribution                                  |
| `make build-platform`        | Build the `ya-agent-platform` distribution                             |
| `make build-all`             | Build distributions for all workspace packages                         |
| `make clean-build`           | Remove build artifacts                                                 |
| `make publish`               | Publish built distributions in `dist/` to PyPI                         |
| `make build-and-publish`     | Build and publish distributions                                        |
| `make help`                  | Print available make targets                                           |

## License

BSD 3-Clause License. See [LICENSE](LICENSE).
