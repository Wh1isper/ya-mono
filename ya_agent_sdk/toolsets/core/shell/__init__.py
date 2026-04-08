"""Shell-related tools.

Tools for executing shell commands and managing background processes.
"""

from ya_agent_sdk.toolsets.core.base import BaseTool
from ya_agent_sdk.toolsets.core.shell.shell import (
    ShellInputTool,
    ShellKillTool,
    ShellSignalTool,
    ShellStatusTool,
    ShellTool,
    ShellWaitTool,
)

tools: list[type[BaseTool]] = [
    ShellTool,
    ShellWaitTool,
    ShellKillTool,
    ShellStatusTool,
    ShellInputTool,
    ShellSignalTool,
]

__all__ = [
    "ShellInputTool",
    "ShellKillTool",
    "ShellSignalTool",
    "ShellStatusTool",
    "ShellTool",
    "ShellWaitTool",
    "tools",
]
