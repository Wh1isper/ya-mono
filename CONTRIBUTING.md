# Contributing to `ya-mono`

Contributions are welcome.

## Report Bugs

Report bugs at https://github.com/wh1isper/ya-mono/issues

Include:

- operating system and version
- local setup details that affect reproduction
- clear reproduction steps

## Implement Changes

Open issues tagged `bug`, `enhancement`, or `help wanted` are good starting points.

## Update References

Repository reference material lives in `skills/agent-builder/`, package READMEs, and in-code docstrings.

## Local Setup

1. Fork `ya-mono` on GitHub.
2. Clone your fork.

```bash
cd <directory>
git clone git@github.com:YOUR_NAME/ya-mono.git
cd ya-mono
```

3. Sync the full workspace.

```bash
uv sync --all-packages
```

4. Install pre-commit hooks.

```bash
uv run pre-commit install
```

5. Create a branch.

```bash
git checkout -b name-of-your-change
```

## Validation

Run the repository checks before opening a pull request.

```bash
make check
make test
```

Package locations:

- SDK: `packages/ya-agent-sdk`
- CLI: `packages/yaacli`
- Skill source: `skills/agent-builder`

## Pull Request Guidelines

1. Include tests for behavior changes.
2. Update `skills/agent-builder/` and package READMEs when behavior or references change.
3. Keep package metadata and workspace references aligned.
