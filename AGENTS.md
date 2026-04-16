## Repository Overview

`ya-mono` is a workspace-first monorepo managed with `uv`.

Workspace members:

- `packages/ya-agent-sdk` — SDK for building AI agents with Pydantic AI
- `packages/yaacli` — TUI reference implementation built on top of the SDK

Shared repository areas:

- `docs/` — shared documentation referenced by the SDK package and skill bundle
- `examples/` — runnable examples for the SDK
- `scripts/` — repository automation scripts
- `.github/` — CI and release workflows

## Primary Package Focus

Most architecture work in this repository targets `packages/ya-agent-sdk`.

- **Language**: Python 3.11+
- **Package Manager**: uv
- **Build System**: hatchling

## SDK Package Structure

```text
packages/ya-agent-sdk/
├── pyproject.toml
├── README.md
├── SKILL.md
├── tests/
│   ├── agents/
│   ├── environment/
│   ├── filters/
│   ├── sandbox/
│   ├── subagents/
│   └── toolsets/
└── ya_agent_sdk/
    ├── agents/
    ├── context/
    ├── environment/
    ├── filters/
    ├── sandbox/
    ├── stream/
    ├── subagents/
    ├── toolsets/
    ├── _config.py
    ├── _logger.py
    ├── events.py
    ├── media.py
    ├── presets.py
    ├── usage.py
    └── utils.py
```

## CLI Package Structure

```text
packages/yaacli/
├── pyproject.toml
├── README.md
├── LICENSE
├── tests/
├── spec/
└── yaacli/
    ├── background.py
    ├── browser.py
    ├── cli.py
    ├── config.py
    ├── display.py
    ├── environment.py
    ├── events.py
    ├── guards.py
    ├── hooks.py
    ├── logging.py
    ├── mcp.py
    ├── runtime.py
    ├── session.py
    └── usage.py
```

## Key SDK Features

- Environment-based architecture via `Environment`
- Resumable sessions with `AgentContext` state export and restore
- Hierarchical agents and markdown-configured subagents
- Skills system with hot reload and progressive loading
- Human-in-the-loop approval workflows
- Extensible toolset architecture with hooks
- Resumable resources for long-lived browser or external sessions
- Browser automation through sandbox integration
- Streaming support with lifecycle and event hooks

## Development Workflow

After changing code, run:

1. `make lint`
2. `make check`
3. `make test`

Useful commands:

| Command          | Description                                          |
| ---------------- | ---------------------------------------------------- |
| `make install`   | Sync the full workspace and install pre-commit hooks |
| `make lint`      | Run pre-commit linters                               |
| `make check`     | Lock validation, lint, pyright, deptry               |
| `make test`      | Run SDK and CLI tests                                |
| `make test-sdk`  | Run SDK tests only                                   |
| `make test-cli`  | Run CLI tests only                                   |
| `make build`     | Build the `ya-agent-sdk` package                     |
| `make build-all` | Build both workspace packages                        |
| `make cli`       | Sync skill assets and launch the CLI                 |

## Code Style

- Formatter: `ruff` with line length `120`
- Type checking: `pyright` in standard mode
- Target Python: `3.11`
- Imports stay at module top level except `TYPE_CHECKING` blocks for cycle avoidance
- Tests use standalone functions such as `def test_xxx()`

## Environment Configuration

Environment variables are loaded via `pydantic-settings` from the process environment or `.env` files.

- Repository example env file: `.env.example`
- Example runtime env file: `examples/.env.example`

Keep `.env.example` updated when environment variables change.

## Documentation Map

Shared docs live in `docs/`.

- `docs/context.md`
- `docs/streaming.md`
- `docs/events.md`
- `docs/tool-search.md`
- `docs/toolset.md`
- `docs/subagent.md`
- `docs/message-bus.md`
- `docs/skills.md`
- `docs/environment.md`
- `docs/resumable-resources.md`
- `docs/model.md`
- `docs/logging.md`

## Prompt Design

Prompt documents follow a single-layer XML style.

Rules:

- Use one clear top-level tag per logical block
- Prefer stable semantic tag names such as `<identity>` and `<tool_usage>`
- Keep each block focused on one concern
- Use Markdown lists inside tags instead of deeply nested XML
- Use tags for meaning and structure

## Notes For Repository Changes

When editing workspace metadata, keep these files aligned:

- `pyproject.toml`
- `packages/ya-agent-sdk/pyproject.toml`
- `packages/yaacli/pyproject.toml`
- `Makefile`
- `.github/workflows/*.yml`
- `README.md` and package READMEs
