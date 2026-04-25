from __future__ import annotations

import asyncio
import contextlib
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from y_agent_environment import Environment, ResourceFactory, ResourceRegistryState
from ya_agent_sdk.environment import LocalShell, SandboxEnvironment, VirtualLocalFileOperator, VirtualMount
from ya_agent_sdk.environment.sandbox import DockerShell

_DOCKER_SANDBOX_METADATA_KEY = "sandbox"
_DOCKER_SANDBOX_PROVIDER = "docker"
_DOCKER_SANDBOX_NAME_PREFIX = "ya-claw-session"


@dataclass(slots=True)
class ProjectMount:
    project_id: str
    description: str | None
    host_path: Path
    virtual_path: Path
    readable: bool = True
    writable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkspaceBinding:
    project_id: str
    host_path: Path
    virtual_path: Path
    cwd: Path
    readable_paths: list[Path]
    writable_paths: list[Path]
    project_mounts: list[ProjectMount] = field(default_factory=list)
    environment_overrides: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    backend_hint: str | None = None

    def __post_init__(self) -> None:
        if not self.project_mounts:
            self.project_mounts = [
                ProjectMount(
                    project_id=self.project_id,
                    description=None,
                    host_path=self.host_path,
                    virtual_path=self.virtual_path,
                )
            ]


class WorkspaceProvider(ABC):
    @abstractmethod
    def resolve(self, project_id: str, metadata: dict[str, Any] | None = None) -> WorkspaceBinding:
        raise NotImplementedError


class MappedLocalEnvironment(Environment):
    def __init__(
        self,
        *,
        mounts: list[VirtualMount],
        host_cwd: Path,
        shell_timeout: float = 30.0,
        tmp_base_dir: Path | None = None,
        enable_tmp_dir: bool = True,
        resource_state: ResourceRegistryState | None = None,
        resource_factories: dict[str, ResourceFactory] | None = None,
        include_os_env: bool = True,
    ) -> None:
        super().__init__(resource_state=resource_state, resource_factories=resource_factories)
        self._mounts = mounts
        self._host_cwd = host_cwd
        self._shell_timeout = shell_timeout
        self._tmp_base_dir = tmp_base_dir
        self._enable_tmp_dir = enable_tmp_dir
        self._include_os_env = include_os_env
        self._tmp_dir_obj: tempfile.TemporaryDirectory[str] | None = None

    async def _setup(self) -> None:
        tmp_dir_path: Path | None = None
        if self._enable_tmp_dir:
            self._tmp_dir_obj = tempfile.TemporaryDirectory(
                prefix="ya_claw_workspace_",
                dir=str(self._tmp_base_dir) if self._tmp_base_dir else None,
            )
            tmp_dir_path = Path(self._tmp_dir_obj.name)

        self._file_operator = VirtualLocalFileOperator(
            mounts=self._mounts,
            default_virtual_path=self._mounts[0].virtual_path,
            tmp_dir=tmp_dir_path,
        )
        allowed_paths = [mount.host_path.resolve() for mount in self._mounts]
        if tmp_dir_path is not None:
            allowed_paths.append(tmp_dir_path.resolve())
        self._shell = LocalShell(
            default_cwd=self._host_cwd,
            allowed_paths=allowed_paths,
            default_timeout=self._shell_timeout,
            include_os_env=self._include_os_env,
        )

    async def _teardown(self) -> None:
        if self._tmp_dir_obj is not None:
            self._tmp_dir_obj.cleanup()
            self._tmp_dir_obj = None


class ReusableSandboxEnvironment(SandboxEnvironment):
    def __init__(
        self,
        *,
        mounts: list[VirtualMount],
        work_dir: str,
        image: str,
        container_ref: str,
        preferred_container_id: str | None = None,
        workspace_uid: int | None = None,
        workspace_gid: int | None = None,
        shell_timeout: float = 30.0,
        cleanup_on_exit: bool = False,
    ) -> None:
        super().__init__(
            mounts=mounts,
            work_dir=work_dir,
            container_id=preferred_container_id or container_ref,
            image=image,
            cleanup_on_exit=cleanup_on_exit,
            shell_timeout=shell_timeout,
        )
        self._container_ref = container_ref
        self._workspace_uid = workspace_uid
        self._workspace_gid = workspace_gid

    @property
    def container_ref(self) -> str:
        return self._container_ref

    async def _setup(self) -> None:
        tmp_dir_path: Path | None = None
        if self._enable_tmp_dir:
            self._tmp_dir_obj = tempfile.TemporaryDirectory(
                prefix="ya_agent_sandbox_",
                dir=str(self._tmp_base_dir) if self._tmp_base_dir else None,
            )
            tmp_dir_path = Path(self._tmp_dir_obj.name)

        for mount in self._mounts:
            mount.host_path.resolve().mkdir(parents=True, exist_ok=True)

        if self._custom_shell is None:
            if self._container_id is None:
                self._container_id = await self._create_container()
                self._created_container = True
            else:
                try:
                    await self._verify_container()
                except RuntimeError as exc:
                    if "Container not found" not in str(exc):
                        raise
                    self._container_id = await self._create_container()
                    self._created_container = True

        self._file_operator = VirtualLocalFileOperator(
            mounts=self._mounts,
            default_virtual_path=Path(self._work_dir),
            tmp_dir=tmp_dir_path,
        )

        if self._custom_shell is not None:
            self._shell = self._custom_shell
        else:
            if self._container_id is None:
                raise RuntimeError("container_id must be set when no custom shell is provided")
            self._shell = DockerShell(
                container_id=self._container_id,
                container_workdir=self._work_dir,
                default_timeout=self._shell_timeout,
            )

    async def _create_container(self) -> str:
        if self._image is None:
            raise ValueError("Image must be provided to create a new container")

        image = self._image
        work_dir = self._work_dir
        mounts = self._mounts
        tmp_dir = self.tmp_dir
        container_ref = self._container_ref
        workspace_uid = self._workspace_uid
        workspace_gid = self._workspace_gid

        def _run_container() -> str:
            try:
                volumes = {str(m.host_path.resolve()): {"bind": str(m.virtual_path), "mode": "rw"} for m in mounts}
                if tmp_dir is not None:
                    volumes[str(tmp_dir)] = {"bind": str(tmp_dir), "mode": "rw"}
                environment = {"YA_CLAW_WORKSPACE_STARTUP_DIR": work_dir}
                if isinstance(workspace_uid, int):
                    environment["YA_CLAW_WORKSPACE_UID"] = str(workspace_uid)
                    environment["YA_CLAW_HOST_UID"] = str(workspace_uid)
                if isinstance(workspace_gid, int):
                    environment["YA_CLAW_WORKSPACE_GID"] = str(workspace_gid)
                    environment["YA_CLAW_HOST_GID"] = str(workspace_gid)
                container = self.client.containers.run(
                    image=image,
                    volumes=volumes,
                    working_dir=work_dir,
                    environment=environment,
                    detach=True,
                    stdin_open=True,
                    tty=True,
                    name=container_ref,
                )
                container_id = container.id
                if container_id is None:
                    raise RuntimeError("Container was created but has no ID")
                return container_id
            except Exception as exc:
                raise RuntimeError(f"Failed to start reusable container '{container_ref}': {exc}") from exc

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run_container)


class EnvironmentFactory(ABC):
    @abstractmethod
    def build(self, binding: WorkspaceBinding) -> Environment:
        raise NotImplementedError


class LocalEnvironmentFactory(EnvironmentFactory):
    def __init__(
        self,
        *,
        shell_timeout: float = 30.0,
        tmp_base_dir: Path | None = None,
    ) -> None:
        self._shell_timeout = shell_timeout
        self._tmp_base_dir = tmp_base_dir

    def build(self, binding: WorkspaceBinding) -> Environment:
        mounts = _virtual_mounts_from_binding(binding)
        primary_mount = binding.project_mounts[0]
        return MappedLocalEnvironment(
            mounts=mounts,
            host_cwd=primary_mount.host_path,
            shell_timeout=self._shell_timeout,
            tmp_base_dir=self._tmp_base_dir,
        )


class DockerEnvironmentFactory(EnvironmentFactory):
    def __init__(
        self,
        *,
        image: str,
        workspace_uid: int | None = None,
        workspace_gid: int | None = None,
        shell_timeout: float = 30.0,
        cleanup_on_exit: bool = False,
    ) -> None:
        self._image = image
        self._workspace_uid = workspace_uid
        self._workspace_gid = workspace_gid
        self._shell_timeout = shell_timeout
        self._cleanup_on_exit = cleanup_on_exit

    def build(self, binding: WorkspaceBinding) -> Environment:
        sandbox_metadata = extract_session_sandbox_metadata(binding.metadata)
        preferred_container_id = _normalize_optional_str(
            sandbox_metadata.get("container_id") if isinstance(sandbox_metadata, dict) else None
        )
        container_ref = _normalize_optional_str(
            sandbox_metadata.get("container_ref") if isinstance(sandbox_metadata, dict) else None
        )
        if container_ref is None:
            session_id = _normalize_optional_str(binding.metadata.get("session_id"))
            if session_id is not None:
                container_ref = build_session_sandbox_container_ref(session_id)

        mounts = _virtual_mounts_from_binding(binding)
        if isinstance(self._workspace_uid, int):
            binding.metadata["workspace_uid"] = self._workspace_uid
        if isinstance(self._workspace_gid, int):
            binding.metadata["workspace_gid"] = self._workspace_gid

        if container_ref is not None:
            return ReusableSandboxEnvironment(
                mounts=mounts,
                work_dir=str(binding.cwd),
                image=self._image,
                container_ref=container_ref,
                preferred_container_id=preferred_container_id,
                workspace_uid=self._workspace_uid,
                workspace_gid=self._workspace_gid,
                cleanup_on_exit=self._cleanup_on_exit,
                shell_timeout=self._shell_timeout,
            )

        return SandboxEnvironment(
            mounts=mounts,
            work_dir=str(binding.cwd),
            image=self._image,
            cleanup_on_exit=self._cleanup_on_exit,
            shell_timeout=self._shell_timeout,
        )


class DefaultEnvironmentFactory(EnvironmentFactory):
    def __init__(
        self,
        *,
        docker_image: str,
        workspace_uid: int | None = None,
        workspace_gid: int | None = None,
        shell_timeout: float = 30.0,
        tmp_base_dir: Path | None = None,
        cleanup_on_exit: bool = False,
    ) -> None:
        self._local_factory = LocalEnvironmentFactory(shell_timeout=shell_timeout, tmp_base_dir=tmp_base_dir)
        self._docker_factory = DockerEnvironmentFactory(
            image=docker_image,
            workspace_uid=workspace_uid,
            workspace_gid=workspace_gid,
            shell_timeout=shell_timeout,
            cleanup_on_exit=cleanup_on_exit,
        )

    def build(self, binding: WorkspaceBinding) -> Environment:
        backend = (binding.backend_hint or "local").strip().lower()
        if backend == "docker":
            return self._docker_factory.build(binding)
        return self._local_factory.build(binding)


class LocalWorkspaceProvider(WorkspaceProvider):
    def __init__(
        self,
        workspace_root: Path,
        *,
        virtual_workspace_root: Path = Path("/workspace"),
    ) -> None:
        self._workspace_root = workspace_root.expanduser().resolve()
        self._virtual_workspace_root = virtual_workspace_root

    def resolve(self, project_id: str, metadata: dict[str, Any] | None = None) -> WorkspaceBinding:
        resolved_metadata = dict(metadata or {})
        host_path = (self._workspace_root / project_id).resolve()
        return _build_workspace_binding(
            workspace_root=self._workspace_root,
            virtual_workspace_root=self._virtual_workspace_root,
            project_id=project_id,
            metadata=resolved_metadata,
            provider="local",
            backend_hint="local",
            extra_metadata={
                "shell_backend": "local",
                "file_operator": "virtual-local",
                "host_cwd": str(host_path),
            },
        )


class DockerWorkspaceProvider(WorkspaceProvider):
    def __init__(
        self,
        workspace_root: Path,
        *,
        image: str,
        virtual_workspace_root: Path = Path("/workspace"),
    ) -> None:
        self._workspace_root = workspace_root.expanduser().resolve()
        self._image = image
        self._virtual_workspace_root = virtual_workspace_root

    def resolve(self, project_id: str, metadata: dict[str, Any] | None = None) -> WorkspaceBinding:
        resolved_metadata = dict(metadata or {})
        host_path = (self._workspace_root / project_id).resolve()
        virtual_path = self._virtual_workspace_root / project_id
        session_id = _normalize_optional_str(resolved_metadata.get("session_id"))
        sandbox_metadata = extract_session_sandbox_metadata(resolved_metadata) or {}
        if session_id is not None:
            sandbox_metadata = {
                **sandbox_metadata,
                "provider": _DOCKER_SANDBOX_PROVIDER,
                "container_ref": _normalize_optional_str(sandbox_metadata.get("container_ref"))
                or build_session_sandbox_container_ref(session_id),
                "image": _normalize_optional_str(sandbox_metadata.get("image")) or self._image,
                "project_id": project_id,
            }
        if sandbox_metadata:
            resolved_metadata[_DOCKER_SANDBOX_METADATA_KEY] = sandbox_metadata
        return _build_workspace_binding(
            workspace_root=self._workspace_root,
            virtual_workspace_root=self._virtual_workspace_root,
            project_id=project_id,
            metadata=resolved_metadata,
            provider="docker",
            backend_hint="docker",
            extra_metadata={
                "shell_backend": "docker",
                "file_operator": "virtual-local",
                "docker_image": self._image,
                "host_mount": str(host_path),
                "container_mount": str(virtual_path),
            },
        )


def _extract_project_specs(
    *,
    project_id: str,
    metadata: dict[str, Any],
) -> list[dict[str, str | None]]:
    specs: list[dict[str, str | None]] = []
    indexes: dict[str, int] = {}

    def add_spec(raw_project_id: Any, raw_description: Any = None) -> None:
        if not isinstance(raw_project_id, str):
            return
        normalized_project_id = raw_project_id.strip()
        if normalized_project_id == "":
            return
        description = raw_description.strip() if isinstance(raw_description, str) else None
        existing_index = indexes.get(normalized_project_id)
        if isinstance(existing_index, int):
            if specs[existing_index].get("description") is None and description:
                specs[existing_index]["description"] = description
            return
        indexes[normalized_project_id] = len(specs)
        specs.append({
            "project_id": normalized_project_id,
            "description": description or None,
        })

    add_spec(project_id)
    raw_projects = metadata.get("projects")
    if isinstance(raw_projects, list):
        for raw_project in raw_projects:
            if isinstance(raw_project, dict):
                add_spec(raw_project.get("project_id"), raw_project.get("description"))
    return specs


def _build_workspace_binding(
    *,
    workspace_root: Path,
    virtual_workspace_root: Path,
    project_id: str,
    metadata: dict[str, Any],
    provider: str,
    backend_hint: str,
    extra_metadata: dict[str, Any],
) -> WorkspaceBinding:
    project_specs = _extract_project_specs(project_id=project_id, metadata=metadata)
    project_mounts: list[ProjectMount] = []
    for spec in project_specs:
        current_project_id = str(spec["project_id"])
        host_path = (workspace_root / current_project_id).resolve()
        host_path.mkdir(parents=True, exist_ok=True)
        virtual_path = virtual_workspace_root / current_project_id
        project_mounts.append(
            ProjectMount(
                project_id=current_project_id,
                description=spec.get("description"),
                host_path=host_path,
                virtual_path=virtual_path,
                metadata={"provider": provider},
            )
        )

    primary_mount = project_mounts[0]
    readable_paths = [mount.virtual_path for mount in project_mounts if mount.readable]
    writable_paths = [mount.virtual_path for mount in project_mounts if mount.writable]
    return WorkspaceBinding(
        project_id=primary_mount.project_id,
        host_path=primary_mount.host_path,
        virtual_path=primary_mount.virtual_path,
        cwd=primary_mount.virtual_path,
        readable_paths=readable_paths,
        writable_paths=writable_paths,
        project_mounts=project_mounts,
        metadata={
            **metadata,
            "provider": provider,
            "projects": [
                {
                    "project_id": mount.project_id,
                    "description": mount.description,
                    "host_path": str(mount.host_path),
                    "virtual_path": str(mount.virtual_path),
                }
                for mount in project_mounts
            ],
            **extra_metadata,
        },
        backend_hint=backend_hint,
    )


def _virtual_mounts_from_binding(binding: WorkspaceBinding) -> list[VirtualMount]:
    return [
        VirtualMount(host_path=mount.host_path, virtual_path=mount.virtual_path)
        for mount in binding.project_mounts
        if mount.readable or mount.writable
    ]


def build_session_sandbox_container_ref(session_id: str) -> str:
    return f"{_DOCKER_SANDBOX_NAME_PREFIX}-{session_id}"


def extract_session_sandbox_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    raw_sandbox = metadata.get(_DOCKER_SANDBOX_METADATA_KEY)
    if not isinstance(raw_sandbox, dict):
        return None
    return dict(raw_sandbox)


def build_session_sandbox_metadata(*, binding: WorkspaceBinding, environment: Environment) -> dict[str, Any] | None:
    if not isinstance(environment, SandboxEnvironment):
        return None
    backend = (binding.backend_hint or binding.metadata.get("provider") or "").strip().lower()
    if backend != "docker":
        return None

    existing = extract_session_sandbox_metadata(binding.metadata) or {}
    container_ref = _normalize_optional_str(existing.get("container_ref"))
    if container_ref is None and isinstance(environment, ReusableSandboxEnvironment):
        container_ref = environment.container_ref

    return {
        "provider": _DOCKER_SANDBOX_PROVIDER,
        "container_ref": container_ref or environment.container_id,
        "container_id": environment.container_id,
        "image": _normalize_optional_str(existing.get("image"))
        or _normalize_optional_str(binding.metadata.get("docker_image")),
        "project_id": binding.project_id,
        "workspace_uid": _first_optional_int(existing.get("workspace_uid"), binding.metadata.get("workspace_uid")),
        "workspace_gid": _first_optional_int(existing.get("workspace_gid"), binding.metadata.get("workspace_gid")),
        "projects": [
            {
                "project_id": mount.project_id,
                "description": mount.description,
                "host_mount": str(mount.host_path),
                "container_mount": str(mount.virtual_path),
            }
            for mount in binding.project_mounts
        ],
        "host_mount": str(binding.host_path),
        "container_mount": str(binding.virtual_path),
        "cwd": str(binding.cwd),
    }


async def cleanup_session_sandbox(metadata: dict[str, Any] | None) -> bool:
    sandbox = extract_session_sandbox_metadata(metadata)
    if sandbox is None:
        return False

    container_ref = _normalize_optional_str(sandbox.get("container_ref")) or _normalize_optional_str(
        sandbox.get("container_id")
    )
    if container_ref is None:
        return False

    def _cleanup() -> bool:
        try:
            import docker
        except Exception:
            return False

        client = docker.from_env()
        try:
            container = client.containers.get(container_ref)
            with contextlib.suppress(Exception):
                container.stop(timeout=10)
            with contextlib.suppress(Exception):
                container.remove(force=True)
            return True
        except Exception:
            return False
        finally:
            with contextlib.suppress(Exception):
                client.close()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _cleanup)


def remove_session_sandbox_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(metadata or {})
    normalized.pop(_DOCKER_SANDBOX_METADATA_KEY, None)
    return normalized


def _normalize_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _first_optional_int(*values: Any) -> int | None:
    for value in values:
        normalized_value = _normalize_optional_int(value)
        if normalized_value is not None:
            return normalized_value
    return None


def _normalize_optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None
