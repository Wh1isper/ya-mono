# ya-mono

> Yet Another Agents

[![Release](https://img.shields.io/github/v/release/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/wh1isper/ya-mono/main.yml?branch=main)](https://github.com/wh1isper/ya-mono/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/wh1isper/ya-mono/branch/main/graph/badge.svg)](https://codecov.io/gh/wh1isper/ya-mono)
[![License](https://img.shields.io/github/license/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/blob/main/LICENSE)

## Packages

- [`packages/ya-agent-sdk`](packages/ya-agent-sdk) — Python SDK for building AI agents with Pydantic AI
- [`packages/yaacli`](packages/yaacli) — TUI reference implementation built on top of `ya-agent-sdk`

## Repository Layout

- [`packages/`](packages/) — publishable workspace members
- [`skills/`](skills/) — canonical skill sources and reference material
- [`examples/`](examples/) — runnable SDK examples
- [`scripts/`](scripts/) — repository automation scripts
- [`.github/`](.github/) — CI and release workflows

## Primary Skill Source

- [`skills/agent-builder/`](skills/agent-builder) — source of truth for the `agent-builder` skill bundled into YAACLI

## Quick Start

```bash
git clone git@github.com:YOUR_NAME/ya-mono.git
cd ya-mono
uv sync --all-packages
```

Run checks:

```bash
make check
make test
```

Run the CLI:

```bash
make cli
```

## Package Guides

- [ya-agent-sdk README](packages/ya-agent-sdk/README.md)
- [yaacli README](packages/yaacli/README.md)
- [agent-builder skill](skills/agent-builder/SKILL.md)
- [Contributing Guide](CONTRIBUTING.md)

## Workspace Commands

| Command          | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `make install`   | Sync the workspace and install pre-commit hooks                  |
| `make lint`      | Run pre-commit hooks across the repository                       |
| `make check`     | Run lock validation, lint, pyright, and deptry for both packages |
| `make test`      | Run SDK and CLI tests                                            |
| `make build`     | Build the `ya-agent-sdk` distribution                            |
| `make build-all` | Build distributions for all workspace packages                   |

## License

BSD 3-Clause License. See [LICENSE](LICENSE).
