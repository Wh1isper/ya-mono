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

## Installation

Prerequisites:

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- `make`

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

Use the repository skill source directly or install the bundled skill and point your agent at it.

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

## Development

Run repository checks:

```bash
make lint
make check
make test
```

Run the CLI locally:

```bash
make cli
```

## Package Guides

- [ya-agent-sdk README](packages/ya-agent-sdk/README.md)
- [yaacli README](packages/yaacli/README.md)
- [agent-builder skill](skills/agent-builder/SKILL.md)
- [Contributing Guide](CONTRIBUTING.md)

## Workspace Commands

| Command                  | Description                                                      |
| ------------------------ | ---------------------------------------------------------------- |
| `make install`           | Install the workspace environment and pre-commit hooks           |
| `make install-skills`    | Install the `agent-builder` skill bundle into `~/.agents/skills` |
| `make lint`              | Check lock consistency and run pre-commit hooks                  |
| `make cli`               | Sync skill assets and launch `yaacli`                            |
| `make check`             | Run lock validation, lint, pyright, and deptry for both packages |
| `make test`              | Run SDK and CLI tests                                            |
| `make test-sdk`          | Run SDK tests only                                               |
| `make test-cli`          | Run CLI tests only                                               |
| `make test-fix`          | Run tests with inline snapshot updates                           |
| `make build`             | Build the `ya-agent-sdk` distribution                            |
| `make build-all`         | Build distributions for all workspace packages                   |
| `make clean-build`       | Remove build artifacts                                           |
| `make publish`           | Publish built distributions in `dist/` to PyPI                   |
| `make build-and-publish` | Build and publish distributions                                  |
| `make help`              | Print available make targets                                     |

## License

BSD 3-Clause License. See [LICENSE](LICENSE).
