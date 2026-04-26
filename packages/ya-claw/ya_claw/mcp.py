from __future__ import annotations

from typing import Any

from ya_agent_sdk.mcp import MCPConfig, MCPServerConfig

_ALLOWED_PROFILE_MCP_TRANSPORTS = {"streamable_http"}


def build_profile_mcp_config(mcp_servers: dict[str, Any] | None) -> MCPConfig | None:
    if not isinstance(mcp_servers, dict) or not mcp_servers:
        return None

    servers: dict[str, MCPServerConfig] = {}
    for raw_name, raw_config in mcp_servers.items():
        name = str(raw_name).strip()
        if name == "" or not isinstance(raw_config, dict):
            continue
        config = MCPServerConfig.model_validate(raw_config)
        if config.transport not in _ALLOWED_PROFILE_MCP_TRANSPORTS:
            raise ValueError(f"Profile MCP server '{name}' uses unsupported transport: {config.transport}")
        if not isinstance(config.url, str) or config.url.strip() == "":
            raise ValueError(f"Profile MCP server '{name}' requires a URL.")
        servers[name] = config.model_copy(update={"url": config.url.strip()}, deep=True)

    if not servers:
        return None
    return MCPConfig(servers=servers)


def normalize_profile_mcp_servers(mcp_servers: dict[str, Any] | None) -> dict[str, Any]:
    config = build_profile_mcp_config(mcp_servers)
    if config is None:
        return {}
    return config.model_dump(mode="json", exclude_none=True)["servers"]
