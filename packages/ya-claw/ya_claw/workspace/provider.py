from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
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
_DOCKER_WORKSPACE_NAME_PREFIX = "ya-claw-workspace"
_DOCKER_CONTAINER_CACHE_SCHEMA_VERSION = 1
_DOCKER_CONTAINER_LOCKS: dict[str, asyncio.Lock] = {}
_DEFAULT_VIRTUAL_WORKSPACE_PATH = Path("/workspace")
_DEFAULT_CONTAINER_CACHE_FILE = "workspace.json"


@dataclass(slots=True)
class WorkspaceBinding:
    host_path: Path
    virtual_path: Path
    cwd: Path
    readable_paths: list[Path]
    writable_paths: list[Path]
    environment_overrides: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    backend_hint: str | None = None


class WorkspaceProvider(ABC):
    @abstractmethod
    def resolve(self, metadata: dict[str, Any] | None = None) -> WorkspaceBinding:
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
        environment_overrides: dict[str, str] | None = None,
    ) -> None:
        super().__init__(resource_state=resource_state, resource_factories=resource_factories)
        self._mounts = mounts
        self._host_cwd = host_cwd
        self._shell_timeout = shell_timeout
        self._tmp_base_dir = tmp_base_dir
        self._enable_tmp_dir = enable_tmp_dir
        self._include_os_env = include_os_env
        self._environment_overrides = dict(environment_overrides or {})
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
        self._shell = WorkspaceLocalShell(
            default_cwd=self._host_cwd,
            allowed_paths=allowed_paths,
            default_timeout=self._shell_timeout,
            include_os_env=self._include_os_env,
            environment_overrides=self._environment_overrides,
        )

    async def _teardown(self) -> None:
        if self._tmp_dir_obj is not None:
            self._tmp_dir_obj.cleanup()
            self._tmp_dir_obj = None


class WorkspaceLocalShell(LocalShell):
    def __init__(
        self,
        *,
        environment_overrides: dict[str, str],
        default_cwd: Path | None = None,
        allowed_paths: list[Path] | None = None,
        default_timeout: float = 30.0,
        include_os_env: bool = True,
    ) -> None:
        super().__init__(
            default_cwd=default_cwd,
            allowed_paths=allowed_paths,
            default_timeout=default_timeout,
            include_os_env=include_os_env,
        )
        self._environment_overrides = dict(environment_overrides)

    def _build_effective_env(self, env: dict[str, str] | None) -> dict[str, str] | None:
        merged_env = {**self._environment_overrides, **dict(env or {})}
        if not merged_env:
            return super()._build_effective_env(env)
        return super()._build_effective_env(merged_env)


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
        workspace_environment: dict[str, str] | None = None,
        shell_timeout: float = 30.0,
        cleanup_on_exit: bool = False,
        container_cache_path: Path | None = None,
    ) -> None:
        super().__init__(
            mounts=mounts,
            work_dir=work_dir,
            container_id=preferred_container_id,
            image=image,
            cleanup_on_exit=cleanup_on_exit,
            shell_timeout=shell_timeout,
        )
        self._container_ref = container_ref
        self._workspace_uid = workspace_uid
        self._workspace_gid = workspace_gid
        self._workspace_environment = dict(workspace_environment or {})
        self._container_cache_path = container_cache_path.expanduser() if container_cache_path is not None else None

    @property
    def container_ref(self) -> str:
        return self._container_ref

    @property
    def container_cache_path(self) -> Path | None:
        return self._container_cache_path

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
            lock_key = str(self._container_cache_path or self._container_ref)
            lock = _DOCKER_CONTAINER_LOCKS.setdefault(lock_key, asyncio.Lock())
            async with lock:
                await self._ensure_container()

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

    async def _ensure_container(self) -> None:
        cached_container_id = self._container_id or await self._read_cached_container_id()
        if cached_container_id is not None:
            self._container_id = cached_container_id
            try:
                await self._verify_container()
                await self._write_cached_container_id(cached_container_id)
                return
            except RuntimeError:
                await self._clear_cached_container_id(cached_container_id)
                await self._remove_container(cached_container_id)
                self._container_id = None

        discovered_container_id = await self._resolve_container_id_from_ref()
        if discovered_container_id is not None:
            self._container_id = discovered_container_id
            try:
                await self._verify_container()
                await self._write_cached_container_id(discovered_container_id)
                return
            except RuntimeError:
                await self._clear_cached_container_id(discovered_container_id)
                await self._remove_container(discovered_container_id)
                self._container_id = None

        self._container_id = await self._create_container()
        self._created_container = True
        await self._write_cached_container_id(self._container_id)

    async def _teardown(self) -> None:
        if self._cleanup_on_exit and self._created_container and self._container_id is not None:
            await self._clear_cached_container_id(self._container_id)
            await self._stop_container()

        if self._tmp_dir_obj is not None:
            self._tmp_dir_obj.cleanup()
            self._tmp_dir_obj = None

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
        workspace_environment = dict(self._workspace_environment)

        def _run_container() -> str:
            try:
                volumes = {str(m.host_path.resolve()): {"bind": str(m.virtual_path), "mode": "rw"} for m in mounts}
                if tmp_dir is not None:
                    volumes[str(tmp_dir)] = {"bind": str(tmp_dir), "mode": "rw"}
                environment = {**workspace_environment, "YA_CLAW_WORKSPACE_STARTUP_DIR": work_dir}
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

    async def _verify_container(self) -> None:
        container_id = self._container_id
        if container_id is None:
            raise RuntimeError("Container ID is not set")

        def _check_and_start_container() -> None:
            try:
                container = self.client.containers.get(container_id)
                container.reload()
                status = _normalize_optional_str(getattr(container, "status", None))
                if status == "running":
                    _raise_for_unhealthy_container(container_id, container)
                    return
                if status in ("exited", "created", "paused"):
                    container.start()
                    container.reload()
                    next_status = _normalize_optional_str(getattr(container, "status", None))
                    if next_status != "running":
                        raise RuntimeError(f"Container {container_id} failed to start (status: {next_status})")
                    _raise_for_unhealthy_container(container_id, container)
                    return
                raise RuntimeError(f"Container {container_id} is in unrecoverable state: {status}")
            except RuntimeError:
                raise
            except Exception as exc:
                if exc.__class__.__name__ == "NotFound":
                    raise RuntimeError(f"Container not found: {container_id}") from exc
                raise RuntimeError(f"Failed to verify/start container: {exc}") from exc

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _check_and_start_container)

    async def _resolve_container_id_from_ref(self) -> str | None:
        container_ref = self._container_ref

        def _resolve() -> str | None:
            try:
                container = self.client.containers.get(container_ref)
                return _normalize_optional_str(getattr(container, "id", None))
            except Exception:
                return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _resolve)

    async def _read_cached_container_id(self) -> str | None:
        cache_path = self._container_cache_path
        if cache_path is None:
            return None

        def _read() -> str | None:
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                return None
            if not isinstance(payload, dict):
                return None
            if payload.get("schema_version") != _DOCKER_CONTAINER_CACHE_SCHEMA_VERSION:
                return None
            if payload.get("container_ref") != self._container_ref:
                return None
            if payload.get("image") != self._image:
                return None
            return _normalize_optional_str(payload.get("container_id"))

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _read)

    async def _write_cached_container_id(self, container_id: str) -> None:
        cache_path = self._container_cache_path
        if cache_path is None:
            return
        payload = {
            "schema_version": _DOCKER_CONTAINER_CACHE_SCHEMA_VERSION,
            "container_ref": self._container_ref,
            "container_id": container_id,
            "image": self._image,
            "work_dir": self._work_dir,
        }

        def _write() -> None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write)

    async def _clear_cached_container_id(self, container_id: str | None = None) -> None:
        cache_path = self._container_cache_path
        if cache_path is None:
            return

        def _clear() -> None:
            cached_container_id: str | None = None
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    cached_container_id = _normalize_optional_str(payload.get("container_id"))
            except Exception:
                cached_container_id = None
            if container_id is not None and cached_container_id not in (None, container_id):
                return
            with contextlib.suppress(FileNotFoundError):
                cache_path.unlink()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _clear)

    async def _remove_container(self, container_id: str) -> None:
        def _remove() -> None:
            try:
                container = self.client.containers.get(container_id)
                with contextlib.suppress(Exception):
                    container.stop(timeout=10)
                with contextlib.suppress(Exception):
                    container.remove(force=True)
            except Exception:
                return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _remove)


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
        workspace_environment: dict[str, str] | None = None,
    ) -> None:
        self._shell_timeout = shell_timeout
        self._tmp_base_dir = tmp_base_dir
        self._workspace_environment = dict(workspace_environment or {})

    def build(self, binding: WorkspaceBinding) -> Environment:
        return MappedLocalEnvironment(
            mounts=_virtual_mounts_from_binding(binding),
            host_cwd=binding.host_path,
            shell_timeout=self._shell_timeout,
            tmp_base_dir=self._tmp_base_dir,
            environment_overrides={**self._workspace_environment, **binding.environment_overrides},
        )


class DockerEnvironmentFactory(EnvironmentFactory):
    def __init__(
        self,
        *,
        image: str,
        workspace_uid: int | None = None,
        workspace_gid: int | None = None,
        workspace_environment: dict[str, str] | None = None,
        shell_timeout: float = 30.0,
        cleanup_on_exit: bool = False,
        container_cache_dir: Path | None = None,
    ) -> None:
        self._image = image
        self._workspace_uid = workspace_uid
        self._workspace_gid = workspace_gid
        self._workspace_environment = dict(workspace_environment or {})
        self._shell_timeout = shell_timeout
        self._cleanup_on_exit = cleanup_on_exit
        self._container_cache_dir = container_cache_dir.expanduser() if container_cache_dir is not None else None

    def build(self, binding: WorkspaceBinding) -> Environment:
        sandbox_metadata = extract_workspace_sandbox_metadata(binding.metadata) or {}
        preferred_container_id = _normalize_optional_str(sandbox_metadata.get("container_id"))
        container_ref = _normalize_optional_str(sandbox_metadata.get("container_ref")) or build_workspace_container_ref(
            image=self._image,
            workspace_dir=binding.host_path,
        )
        mounts = _virtual_mounts_from_binding(binding)
        workspace_environment = {**self._workspace_environment, **binding.environment_overrides}
        if isinstance(self._workspace_uid, int):
            binding.metadata["workspace_uid"] = self._workspace_uid
        if isinstance(self._workspace_gid, int):
            binding.metadata["workspace_gid"] = self._workspace_gid
        binding.metadata[_DOCKER_SANDBOX_METADATA_KEY] = {
            **sandbox_metadata,
            "provider": _DOCKER_SANDBOX_PROVIDER,
            "container_ref": container_ref,
            "image": self._image,
        }
        return ReusableSandboxEnvironment(
            mounts=mounts,
            work_dir=str(binding.cwd),
            image=self._image,
            container_ref=container_ref,
            preferred_container_id=preferred_container_id,
            workspace_uid=self._workspace_uid,
            workspace_gid=self._workspace_gid,
            workspace_environment=workspace_environment,
            cleanup_on_exit=self._cleanup_on_exit,
            shell_timeout=self._shell_timeout,
            container_cache_path=_build_container_cache_path(self._container_cache_dir),
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
        workspace_environment: dict[str, str] | None = None,
        docker_container_cache_dir: Path | None = None,
    ) -> None:
        self._local_factory = LocalEnvironmentFactory(
            shell_timeout=shell_timeout,
            tmp_base_dir=tmp_base_dir,
            workspace_environment=workspace_environment,
        )
        self._docker_factory = DockerEnvironmentFactory(
            image=docker_image,
            workspace_uid=workspace_uid,
            workspace_gid=workspace_gid,
            workspace_environment=workspace_environment,
            shell_timeout=shell_timeout,
            cleanup_on_exit=cleanup_on_exit,
            container_cache_dir=docker_container_cache_dir,
        )

    def build(self, binding: WorkspaceBinding) -> Environment:
        backend = (binding.backend_hint or "local").strip().lower()
        if backend == "docker":
            return self._docker_factory.build(binding)
        return self._local_factory.build(binding)


class LocalWorkspaceProvider(WorkspaceProvider):
    def __init__(
        self,
        workspace_dir: Path,
        *,
        virtual_workspace_path: Path = _DEFAULT_VIRTUAL_WORKSPACE_PATH,
    ) -> None:
        self._workspace_dir = workspace_dir.expanduser().resolve()
        self._virtual_workspace_path = virtual_workspace_path

    def resolve(self, metadata: dict[str, Any] | None = None) -> WorkspaceBinding:
        return _build_workspace_binding(
            workspace_dir=self._workspace_dir,
            virtual_workspace_path=self._virtual_workspace_path,
            metadata=dict(metadata or {}),
            provider="local",
            backend_hint="local",
            extra_metadata={
                "shell_backend": "local",
                "file_operator": "virtual-local",
                "host_cwd": str(self._workspace_dir),
            },
        )


class DockerWorkspaceProvider(WorkspaceProvider):
    def __init__(
        self,
        workspace_dir: Path,
        *,
        image: str,
        virtual_workspace_path: Path = _DEFAULT_VIRTUAL_WORKSPACE_PATH,
    ) -> None:
        self._workspace_dir = workspace_dir.expanduser().resolve()
        self._image = image
        self._virtual_workspace_path = virtual_workspace_path

    def resolve(self, metadata: dict[str, Any] | None = None) -> WorkspaceBinding:
        resolved_metadata = dict(metadata or {})
        sandbox_metadata = extract_workspace_sandbox_metadata(resolved_metadata) or {}
        container_ref = _normalize_optional_str(sandbox_metadata.get("container_ref")) or build_workspace_container_ref(
            image=self._image,
            workspace_dir=self._workspace_dir,
        )
        sandbox_metadata = {
            **sandbox_metadata,
            "provider": _DOCKER_SANDBOX_PROVIDER,
            "container_ref": container_ref,
            "image": _normalize_optional_str(sandbox_metadata.get("image")) or self._image,
        }
        resolved_metadata[_DOCKER_SANDBOX_METADATA_KEY] = sandbox_metadata
        return _build_workspace_binding(
            workspace_dir=self._workspace_dir,
            virtual_workspace_path=self._virtual_workspace_path,
            metadata=resolved_metadata,
            provider="docker",
            backend_hint="docker",
            extra_metadata={
                "shell_backend": "docker",
                "file_operator": "virtual-local",
                "docker_image": self._image,
                "host_mount": str(self._workspace_dir),
                "container_mount": str(self._virtual_workspace_path),
            },
        )


def _build_workspace_binding(
    *,
    workspace_dir: Path,
    virtual_workspace_path: Path,
    metadata: dict[str, Any],
    provider: str,
    backend_hint: str,
    extra_metadata: dict[str, Any],
) -> WorkspaceBinding:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return WorkspaceBinding(
        host_path=workspace_dir,
        virtual_path=virtual_workspace_path,
        cwd=virtual_workspace_path,
        readable_paths=[virtual_workspace_path],
        writable_paths=[virtual_workspace_path],
        metadata={
            **metadata,
            "provider": provider,
            **extra_metadata,
        },
        backend_hint=backend_hint,
    )


def _virtual_mounts_from_binding(binding: WorkspaceBinding) -> list[VirtualMount]:
    return [VirtualMount(host_path=binding.host_path, virtual_path=binding.virtual_path)]


def build_workspace_container_ref(*, image: str, workspace_dir: Path) -> str:
    fingerprint_source = f"{workspace_dir.expanduser().resolve()}|{image}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:12]
    return f"{_DOCKER_WORKSPACE_NAME_PREFIX}-{fingerprint}"


def extract_workspace_sandbox_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    raw_sandbox = metadata.get(_DOCKER_SANDBOX_METADATA_KEY)
    if not isinstance(raw_sandbox, dict):
        return None
    return dict(raw_sandbox)


def build_workspace_sandbox_metadata(*, binding: WorkspaceBinding, environment: Environment) -> dict[str, Any] | None:
    if not isinstance(environment, SandboxEnvironment):
        return None
    backend = (binding.backend_hint or binding.metadata.get("provider") or "").strip().lower()
    if backend != "docker":
        return None

    existing = extract_workspace_sandbox_metadata(binding.metadata) or {}
    container_ref = _normalize_optional_str(existing.get("container_ref"))
    if container_ref is None and isinstance(environment, ReusableSandboxEnvironment):
        container_ref = environment.container_ref

    return {
        "provider": _DOCKER_SANDBOX_PROVIDER,
        "container_ref": container_ref or environment.container_id,
        "container_id": environment.container_id,
        "image": _normalize_optional_str(existing.get("image"))
        or _normalize_optional_str(binding.metadata.get("docker_image")),
        "workspace_uid": _first_optional_int(existing.get("workspace_uid"), binding.metadata.get("workspace_uid")),
        "workspace_gid": _first_optional_int(existing.get("workspace_gid"), binding.metadata.get("workspace_gid")),
        "host_mount": str(binding.host_path),
        "container_mount": str(binding.virtual_path),
        "cwd": str(binding.cwd),
    }


def remove_workspace_sandbox_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(metadata or {})
    normalized.pop(_DOCKER_SANDBOX_METADATA_KEY, None)
    return normalized


def _raise_for_unhealthy_container(container_id: str, container: Any) -> None:
    state = getattr(container, "attrs", {}).get("State")
    if not isinstance(state, dict):
        return
    health = state.get("Health")
    if not isinstance(health, dict):
        return
    health_status = _normalize_optional_str(health.get("Status"))
    if health_status in (None, "healthy", "starting"):
        return
    raise RuntimeError(f"Container {container_id} is unhealthy (health: {health_status})")


def _build_container_cache_path(cache_dir: Path | None) -> Path | None:
    if cache_dir is None:
        return None
    return cache_dir / _DEFAULT_CONTAINER_CACHE_FILE


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
