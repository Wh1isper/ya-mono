"""Tool proxy toolset for fixed two-tool dynamic invocation.

Provides ToolProxyToolset, a wrapper over multiple AbstractToolsets that
exposes exactly two fixed tools: ``search_tools`` for discovery and
``call_tool`` for invocation. The tool list never changes, maximizing
prompt cache hit rates.

Toolsets with ``id`` are treated as namespaces (atomic loading);
toolsets without ``id`` provide loose tools (individual loading).
State is stored in AgentContext for automatic session restore.

Usage::

    from ya_agent_sdk.toolsets.tool_proxy import ToolProxyToolset

    proxy_toolset = ToolProxyToolset(
        toolsets=[arxiv_toolset, github_toolset, misc_toolset],
        namespace_descriptions={"arxiv": "Search academic papers"},
    )
"""

from ya_agent_sdk.toolsets.tool_proxy.toolset import ToolProxyToolset

__all__ = [
    "ToolProxyToolset",
]
