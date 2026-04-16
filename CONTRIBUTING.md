# Contributing to `ya-mono`

Contributions are welcome.

## Report Bugs

Open an issue at https://github.com/wh1isper/ya-mono/issues and include:

- operating system and version
- local setup details that affect reproduction
- clear reproduction steps

## Choose Work

Open issues tagged `bug`, `enhancement`, or `help wanted` are good starting points.

## Local Setup

1. Fork `ya-mono` on GitHub.
2. Clone your fork.

```bash
cd <directory>
git clone git@github.com:YOUR_NAME/ya-mono.git
cd ya-mono
```

3. Install the workspace environment and pre-commit hooks.

```bash
make install
```

4. Install the bundled `agent-builder` skill when your changes touch skill packaging or local CLI workflows.

```bash
make install-skills
```

5. Create a branch.

```bash
git checkout -b name-of-your-change
```

## Development Workflow

Run the full validation flow after code changes:

```bash
make lint
make check
make test
```

Useful targets during development:

| Command          | Description                            |
| ---------------- | -------------------------------------- |
| `make test-sdk`  | Run SDK tests only                     |
| `make test-cli`  | Run CLI tests only                     |
| `make test-fix`  | Run tests with inline snapshot updates |
| `make cli`       | Sync skill assets and launch the CLI   |
| `make build`     | Build the `ya-agent-sdk` package       |
| `make build-all` | Build both workspace packages          |
| `make help`      | Print available make targets           |

Package locations:

- SDK: `packages/ya-agent-sdk`
- CLI: `packages/yaacli`
- Skill source: `skills/agent-builder`

## Keep References Aligned

Update related repository references when behavior, packaging, or workspace metadata changes:

- `README.md`
- `packages/ya-agent-sdk/README.md`
- `packages/yaacli/README.md`
- `skills/agent-builder/*`
- `scripts/sync-skills.sh`
- `pyproject.toml`
- `packages/ya-agent-sdk/pyproject.toml`
- `packages/yaacli/pyproject.toml`
- `Makefile`
- `.github/workflows/*.yml`

## Pull Request Guidelines

1. Include tests for behavior changes.
2. Update documentation and skill references for user-facing changes.
3. Keep workspace metadata and release-related files aligned.
4. Describe the motivation and validation steps in the pull request.
