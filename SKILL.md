---
name: ya-mono
summary: Workspace entry point for the Yet Another Agents monorepo.
---

# ya-mono Workspace

This repository is a `uv` workspace with two packages:

- `packages/ya-agent-sdk` — SDK for building AI agents with Pydantic AI
- `packages/yaacli` — TUI reference implementation built on top of the SDK

## Key Entry Points

- SDK guide: [`packages/ya-agent-sdk/README.md`](packages/ya-agent-sdk/README.md)
- SDK skill: [`packages/ya-agent-sdk/SKILL.md`](packages/ya-agent-sdk/SKILL.md)
- CLI guide: [`packages/yaacli/README.md`](packages/yaacli/README.md)
- Shared docs: [`docs/`](docs/)
- Shared examples: [`examples/`](examples/)

## Development

```bash
uv sync --all-packages
make check
make test
```

## Recommendation

Use `packages/ya-agent-sdk/SKILL.md` when the task is about building agents or understanding the SDK architecture.
