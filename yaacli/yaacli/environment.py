"""TUI Environment for yaacli.

TUIEnvironment extends LocalEnvironment with BackgroundTaskManager
for managing background async tasks. Shell background process management
is handled by the Shell ABC from y-agent-environment directly.

Example:
    async with TUIEnvironment(default_path=Path.cwd()) as env:
        # Background shell processes via Shell ABC
        process_id = await env.shell.start("npm run dev")
        for pid, proc in env.shell.active_background_processes.items():
            print(f"{pid}: {proc.command}")
"""

from __future__ import annotations

from pathlib import Path

from y_agent_environment import ResourceFactory, ResourceRegistryState

from ya_agent_sdk.environment.local import LocalEnvironment
from yaacli.background import BACKGROUND_MANAGER_KEY, BackgroundTaskManager


class TUIEnvironment(LocalEnvironment):
    """Extended environment for TUI with background task management.

    Background process management is provided by Shell ABC directly
    (start/drain_output/wait_process/kill_process). BackgroundTaskManager
    handles non-process async tasks and is registered as a resource.
    """

    def __init__(
        self,
        allowed_paths: list[Path] | None = None,
        default_path: Path | None = None,
        shell_timeout: float = 30.0,
        tmp_base_dir: Path | None = None,
        enable_tmp_dir: bool = True,
        resource_state: ResourceRegistryState | None = None,
        resource_factories: dict[str, ResourceFactory] | None = None,
        include_os_env: bool = True,
    ) -> None:
        super().__init__(
            allowed_paths=allowed_paths,
            default_path=default_path,
            shell_timeout=shell_timeout,
            tmp_base_dir=tmp_base_dir,
            enable_tmp_dir=enable_tmp_dir,
            resource_state=resource_state,
            resource_factories=resource_factories,
            include_os_env=include_os_env,
        )
        self._background_manager: BackgroundTaskManager | None = None

    async def _setup(self) -> None:
        await super()._setup()
        self._background_manager = BackgroundTaskManager()
        self.resources.set(BACKGROUND_MANAGER_KEY, self._background_manager)

    async def _teardown(self) -> None:
        self._background_manager = None
        await super()._teardown()

    @property
    def background_manager(self) -> BackgroundTaskManager:
        """Get the BackgroundTaskManager resource."""
        if self._background_manager is None:
            raise RuntimeError("TUIEnvironment not entered. Use 'async with TUIEnvironment() as env:'")
        return self._background_manager
