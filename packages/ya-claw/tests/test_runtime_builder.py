from __future__ import annotations

from pathlib import Path

import pytest
from ya_agent_sdk.environment import SandboxEnvironment, VirtualMount
from ya_claw.config import ClawSettings
from ya_claw.execution.profile import ResolvedProfile
from ya_claw.execution.runtime import ClawRuntimeBuilder
from ya_claw.workspace import MappedLocalEnvironment, WorkspaceBinding


def test_runtime_builder_propagates_container_id_from_workspace_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GATEWAY_API_KEY", "test-gateway-key")
    monkeypatch.setenv("GATEWAY_BASE_URL", "https://gateway.example.test")
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
        execution_model="gateway@openai-responses:gpt-5.4",
    )
    builder = ClawRuntimeBuilder(settings=settings)
    host_path = tmp_path / "workspace" / "repo-a"
    host_path.mkdir(parents=True, exist_ok=True)
    binding = WorkspaceBinding(
        project_id="repo-a",
        host_path=host_path,
        virtual_path=Path("/workspace/repo-a"),
        cwd=Path("/workspace/repo-a"),
        readable_paths=[Path("/workspace/repo-a")],
        writable_paths=[Path("/workspace/repo-a")],
        metadata={
            "provider": "docker",
            "sandbox": {
                "container_id": "container-xyz",
                "container_ref": "ya-claw-session-session-1",
            },
        },
        backend_hint="docker",
    )
    environment = SandboxEnvironment(
        mounts=[VirtualMount(host_path=host_path, virtual_path=Path("/workspace/repo-a"))],
        work_dir="/workspace/repo-a",
        container_id="container-xyz",
    )
    profile = ResolvedProfile(
        name="default",
        model="gateway@openai-responses:gpt-5.4",
        model_settings=None,
        model_config=None,
        workspace_backend_hint="docker",
    )

    runtime = builder.build(
        profile=profile,
        binding=binding,
        environment=environment,
        restore_state=None,
        session_id="session-1",
        run_id="run-1",
        project_id="repo-a",
        restore_from_run_id=None,
        dispatch_mode="async",
        source_kind="api",
        source_metadata={},
        claw_metadata={},
    )

    assert runtime.ctx.container_id == "container-xyz"
    assert runtime.ctx.workspace_binding is not None
    assert runtime.ctx.workspace_binding.metadata["sandbox"]["container_id"] == "container-xyz"


def test_runtime_builder_resolves_core_toolset(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
    )
    builder = ClawRuntimeBuilder(settings=settings)

    resolved_tool_names = [getattr(tool, "name", tool.__name__) for tool in builder._resolve_tools(["core"])]

    assert "view" in resolved_tool_names
    assert "shell_exec" in resolved_tool_names


async def test_runtime_builder_runs_with_pydantic_ai_test_model(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
    )
    builder = ClawRuntimeBuilder(settings=settings)
    host_path = tmp_path / "workspace" / "repo-a"
    host_path.mkdir(parents=True, exist_ok=True)
    binding = WorkspaceBinding(
        project_id="repo-a",
        host_path=host_path,
        virtual_path=Path("/workspace/repo-a"),
        cwd=Path("/workspace/repo-a"),
        readable_paths=[Path("/workspace/repo-a")],
        writable_paths=[Path("/workspace/repo-a")],
        metadata={},
        backend_hint="local",
    )
    environment = MappedLocalEnvironment(
        mounts=[VirtualMount(host_path=host_path, virtual_path=Path("/workspace/repo-a"))],
        host_cwd=host_path,
    )
    profile = ResolvedProfile(
        name="default",
        model="test",
        model_settings=None,
        model_config=None,
        toolsets=[],
        workspace_backend_hint="local",
    )

    runtime = builder.build(
        profile=profile,
        binding=binding,
        environment=environment,
        restore_state=None,
        session_id="session-1",
        run_id="run-1",
        project_id="repo-a",
        restore_from_run_id=None,
        dispatch_mode="async",
        source_kind="api",
        source_metadata={},
        claw_metadata={},
    )

    async with runtime:
        result = await runtime.agent.run("say hello", deps=runtime.ctx)

    assert result.output == "success (no tool calls)"
