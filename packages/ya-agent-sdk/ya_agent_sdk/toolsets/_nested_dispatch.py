"""Shared native dispatch for nested tool calls."""

from __future__ import annotations

from dataclasses import replace

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.tool_manager import ToolManager
from pydantic_ai.toolsets import ToolsetTool

from ya_agent_sdk.context import AgentContext


async def prepare_nested_tool(
    manager: ToolManager[AgentContext],
    ctx: RunContext[AgentContext],
    tool: ToolsetTool[AgentContext],
) -> ToolsetTool[AgentContext]:
    """Apply the active capability's preparation policy to one hidden tool."""
    capability = manager.root_capability
    if capability is None:
        return tool
    definitions = await capability.prepare_tools(ctx, [tool.tool_def])
    prepared = next((item for item in definitions if item.name == tool.tool_def.name), None)
    if prepared is None:
        raise ModelRetry(f"Tool {tool.tool_def.name!r} is not available in this agent context")
    return replace(tool, tool_def=prepared)
