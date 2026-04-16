---
name: agent-builder
description: Build AI agents using ya-agent-sdk with Pydantic AI. Covers agent creation via create_agent(), toolset configuration, session persistence with ResumableState, subagent hierarchies, and browser automation. Use when creating agent applications, configuring custom tools, managing multi-turn sessions, setting up hierarchical agents, or implementing HITL approval flows.
---

# Building Agents with ya-agent-sdk

Build production-ready AI agents with Pydantic AI.

## Quick Start

```python
from ya_agent_sdk.agents import create_agent

async with create_agent("openai:gpt-4o") as runtime:
    result = await runtime.agent.run("Hello", deps=runtime.ctx)
    print(result.output)
```

## Installation

```bash
pip install ya-agent-sdk[all]
```

## References

| Topic | Link |
| --- | --- |
| Context and sessions | https://github.com/wh1isper/ya-mono/tree/main/docs/context.md |
| Streaming and hooks | https://github.com/wh1isper/ya-mono/tree/main/docs/streaming.md |
| Events | https://github.com/wh1isper/ya-mono/tree/main/docs/events.md |
| Toolsets | https://github.com/wh1isper/ya-mono/tree/main/docs/toolset.md |
| Tool search | https://github.com/wh1isper/ya-mono/tree/main/docs/tool-search.md |
| Subagents | https://github.com/wh1isper/ya-mono/tree/main/docs/subagent.md |
| Environment | https://github.com/wh1isper/ya-mono/tree/main/docs/environment.md |
| Resumable resources | https://github.com/wh1isper/ya-mono/tree/main/docs/resumable-resources.md |
| Skills | https://github.com/wh1isper/ya-mono/tree/main/docs/skills.md |
| Message bus | https://github.com/wh1isper/ya-mono/tree/main/docs/message-bus.md |
| Model configuration | https://github.com/wh1isper/ya-mono/tree/main/docs/model.md |
| Logging | https://github.com/wh1isper/ya-mono/tree/main/docs/logging.md |

## Task Guide

### Create a Basic Agent

```python
from ya_agent_sdk.agents import create_agent

async with create_agent("anthropic:claude-sonnet-4") as runtime:
    result = await runtime.agent.run("Summarize this project", deps=runtime.ctx)
    print(result.output)
```

### Add Tools

```python
from ya_agent_sdk.agents import create_agent
from ya_agent_sdk.toolsets.core.filesystem import tools as fs_tools
from ya_agent_sdk.toolsets.core.shell import tools as shell_tools

async with create_agent(
    model="anthropic:claude-sonnet-4",
    system_prompt="You are a coding assistant.",
    tools=[*fs_tools, *shell_tools],
) as runtime:
    result = await runtime.agent.run("List the repository files", deps=runtime.ctx)
    print(result.output)
```

### Persist Sessions

```python
state = runtime.ctx.export_state()

restored_runtime = create_agent("openai:gpt-4o", state=state)
```

### Configure HITL

```python
async with create_agent(
    model="anthropic:claude-sonnet-4",
    tools=[*fs_tools, *shell_tools],
    need_user_approve_tools=["shell", "edit"],
) as runtime:
    ...
```

### Use Subagents

```python
from ya_agent_sdk.subagents import SubagentConfig

config = SubagentConfig(
    name="researcher",
    description="Research specialist for web searches",
    system_prompt="You are a research specialist.",
    tools=["search_with_tavily", "visit_webpage"],
)
```

### Browser Automation

See the browser example:

- https://github.com/wh1isper/ya-mono/tree/main/examples/browser_use.py

## Example Programs

- https://github.com/wh1isper/ya-mono/tree/main/examples/general.py
- https://github.com/wh1isper/ya-mono/tree/main/examples/deepresearch.py
- https://github.com/wh1isper/ya-mono/tree/main/examples/browser_use.py

## Workspace Context

This skill is sourced from `packages/ya-agent-sdk` in the `ya-mono` workspace and copied into the CLI skill bundle via `scripts/sync-skills.sh`.
