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
cp packages/yaacli/.env.example packages/yaacli/.env
```

YAACLI loads `.env` from `packages/yaacli/.env` and the current working directory.
Provider API keys can live in that `.env` file or in `~/.yaacli/config.toml` under `[env]`.
SDK and tool variables such as `YA_AGENT_*`, `YA_AGENT_BROWSER_USE_*`, and search API keys can also live in that same `.env` file because YAACLI loads it into the process environment at startup.
Use [`packages/ya-agent-sdk/.env.example`](../ya-agent-sdk/.env.example) as the reference list for SDK and tool variables.

Run CLI tests from the workspace root:

```bash
make test-cli
```

## Clipboard Image Paste

YAACLI reads clipboard images through Pillow first on macOS and Windows.
macOS also reads Finder-copied image files through Cocoa pasteboard APIs via `pyobjc-framework-Cocoa`.
Linux image paste still relies on `wl-paste` on Wayland or `xclip` on X11.

## License

BSD 3-Clause License. See the [repository license](https://github.com/wh1isper/ya-mono/blob/main/LICENSE).
