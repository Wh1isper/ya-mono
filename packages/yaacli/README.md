# YAACLI CLI

TUI reference implementation for [ya-agent-sdk](https://github.com/wh1isper/ya-mono/tree/main/packages/ya-agent-sdk).

## Usage

Run with uvx:

```bash
uvx yaacli
```

Install with uv:

```bash
uv tool install yaacli
yaacli
```

Update with uv:

```bash
uv tool upgrade yaacli
```

Install with pip:

```bash
pip install yaacli
yaacli
```

Run as a module:

```bash
python -m yaacli
```

## Development

This package lives in the [`ya-mono`](https://github.com/wh1isper/ya-mono) workspace.

```bash
git clone git@github.com:YOUR_NAME/ya-mono.git
cd ya-mono
uv sync --all-packages
```

Run CLI tests from the workspace root:

```bash
make test-cli
```

## License

BSD 3-Clause License. See the [repository license](https://github.com/wh1isper/ya-mono/blob/main/LICENSE).
