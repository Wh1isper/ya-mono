# Ya Agent SDK

> Yet Another Agent SDK

[![Release](https://img.shields.io/github/v/release/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/wh1isper/ya-mono/main.yml?branch=main)](https://github.com/wh1isper/ya-mono/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/wh1isper/ya-mono/branch/main/graph/badge.svg)](https://codecov.io/gh/wh1isper/ya-mono)
[![Commit activity](https://img.shields.io/github/commit-activity/m/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/commits/main)
[![License](https://img.shields.io/github/license/wh1isper/ya-mono)](https://github.com/wh1isper/ya-mono/blob/main/LICENSE)

Yet Another Agent SDK for building AI agents with [Pydantic AI](https://ai.pydantic.dev/).

## Key Features

- Environment-based architecture for file operations, shell access, and resources
- Fully typed SDK validated with pyright
- Resumable sessions with state export and restore
- Hierarchical agents with subagent delegation
- Tool search for large tool libraries
- Skills system with hot reload and progressive loading
- Human-in-the-loop approval workflows
- Event system and streaming support
- Message bus for agent coordination and user steering
- Browser automation with Docker sandbox support

## Installation

```bash
pip install ya-agent-sdk[all]
uv add ya-agent-sdk[all]
```

Selective extras:

```bash
pip install ya-agent-sdk[docker]
pip install ya-agent-sdk[web]
pip install ya-agent-sdk[document]
pip install ya-agent-sdk[s3]
pip install ya-agent-sdk[tool-search]
```

## Quick Start

```python
from ya_agent_sdk.agents import create_agent, stream_agent

runtime = create_agent("openai:gpt-4o")

async with stream_agent(runtime, "Hello") as streamer:
    async for event in streamer:
        print(event)
```

## Repository Context

This package lives in the [`ya-mono`](https://github.com/wh1isper/ya-mono) workspace.

- CLI package: [`packages/yaacli`](https://github.com/wh1isper/ya-mono/tree/main/packages/yaacli)
- Examples: [`examples/`](https://github.com/wh1isper/ya-mono/tree/main/examples)
- Skill source: [`skills/agent-builder/`](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder)
- agent-builder skill: [`skills/agent-builder/SKILL.md`](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/SKILL.md)

## Examples

| Example | Description |
| --- | --- |
| [`general.py`](https://github.com/wh1isper/ya-mono/tree/main/examples/general.py) | Production pattern with streaming, HITL approval, and session persistence |
| [`deepresearch.py`](https://github.com/wh1isper/ya-mono/tree/main/examples/deepresearch.py) | Autonomous research agent with web search and content extraction |
| [`browser_use.py`](https://github.com/wh1isper/ya-mono/tree/main/examples/browser_use.py) | Browser automation with Docker-based headless Chrome sandbox |

## Reference Files

- [AgentContext & Sessions](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/context.md)
- [Streaming & Hooks](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/streaming.md)
- [Events](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/events.md)
- [Toolset Architecture](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/toolset.md)
- [Tool Search](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/tool-search.md)
- [Subagent System](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/subagent.md)
- [Skills System](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/skills.md)
- [Message Bus](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/message-bus.md)
- [Media Upload](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/media.md)
- [Custom Environments](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/environment.md)
- [Resumable Resources](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/resumable-resources.md)
- [Model Configuration](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/model.md)
- [Logging Configuration](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/logging.md)
- [Tool Proxy](https://github.com/wh1isper/ya-mono/tree/main/skills/agent-builder/tool-proxy.md)

## Development

```bash
git clone git@github.com:YOUR_NAME/ya-mono.git
cd ya-mono
uv sync --all-packages
```

Workspace commands live at the repository root. See the [contributing guide](https://github.com/wh1isper/ya-mono/tree/main/CONTRIBUTING.md).
