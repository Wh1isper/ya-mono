"""Environment abstractions for file operations and shell execution.

This module provides Protocol-based interfaces and implementations for
environment operations, allowing different backends (local, remote, S3, SSH, etc.)
to be used interchangeably.
"""

from ya_agent_sdk.environment.local import (
    LocalEnvironment,
    LocalFileOperator,
    LocalShell,
    VirtualLocalFileOperator,
    VirtualMount,
)

# Sandbox environment is optional (requires docker package)
try:
    from ya_agent_sdk.environment.sandbox import (  # noqa: F401
        DockerShell,
        SandboxEnvironment,
    )

    _DOCKER_AVAILABLE = True
except ModuleNotFoundError:
    _DOCKER_AVAILABLE = False

__all__ = [
    "LocalEnvironment",
    "LocalFileOperator",
    "LocalShell",
    "VirtualLocalFileOperator",
    "VirtualMount",
]

# Add Sandbox exports if available
if _DOCKER_AVAILABLE:
    __all__.extend(["DockerShell", "SandboxEnvironment"])
