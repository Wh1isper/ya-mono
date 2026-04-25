from __future__ import annotations

import json
from pathlib import Path

import pytest
from ya_agent_sdk.agents.main import stream_agent
from ya_agent_sdk.environment import SandboxEnvironment, VirtualMount
from ya_agent_sdk.toolsets.skills.toolset import SkillToolset
from ya_agent_sdk.toolsets.tool_proxy.toolset import ToolProxyToolset
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


def test_runtime_builder_resolves_core_builtin_toolset(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
    )
    builder = ClawRuntimeBuilder(settings=settings)

    resolved_tool_names = [getattr(tool, "name", tool.__name__) for tool in builder._resolve_builtin_tools(["core"])]

    assert "view" in resolved_tool_names
    assert "shell_exec" in resolved_tool_names
    assert "spawn_delegate" in resolved_tool_names
    assert "list_session_turns" in resolved_tool_names
    assert "get_run_trace" in resolved_tool_names


def test_runtime_builder_resolves_runtime_mcp_toolsets_with_profile_filters(tmp_path: Path) -> None:
    settings = ClawSettings(
        api_token="test-token",  # noqa: S106
        data_dir=tmp_path / "runtime-data",
        workspace_root=tmp_path / "workspace",
    )
    builder = ClawRuntimeBuilder(settings=settings)
    host_path = tmp_path / "workspace" / "repo-a"
    project_mcp_file = host_path / ".ya-claw" / "mcp.json"
    project_mcp_file.parent.mkdir(parents=True, exist_ok=True)
    project_mcp_file.write_text(
        json.dumps({
            "servers": {
                "github": {
                    "transport": "stdio",
                    "command": "npx",
                },
                "context7": {
                    "transport": "streamable_http",
                    "url": "https://mcp.context7.com/mcp",
                    "description": "Library docs",
                    "required": False,
                },
            }
        }),
        encoding="utf-8",
    )
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
    profile = ResolvedProfile(
        name="default",
        model="test",
        model_settings=None,
        model_config=None,
        enabled_mcps=["context7", "github"],
        disabled_mcps=["github"],
        need_user_approve_mcps=["context7"],
    )

    toolsets = builder._resolve_runtime_toolsets(profile=profile, binding=binding)

    assert len(toolsets) == 2
    assert isinstance(toolsets[0], SkillToolset)
    assert isinstance(toolsets[1], ToolProxyToolset)
    assert [toolset.tool_prefix for toolset in toolsets[1]._toolsets] == ["context7"]
    assert toolsets[1]._optional_namespaces == {"context7"}


async def test_runtime_builder_streams_with_pydantic_ai_test_model_and_exports_state(tmp_path: Path) -> None:
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
        builtin_toolsets=[],
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

    seen_events: list[object] = []
    async with runtime:
        async with stream_agent(runtime, "say hello") as streamer:
            async for event in streamer:
                seen_events.append(event)
        assert streamer.run is not None
        assert streamer.run.result is not None
        result_output = streamer.run.result.output
        exported_state = runtime.ctx.export_state()

    assert result_output == "success (no tool calls)"
    assert seen_events
    assert runtime.ctx.session_id == "session-1"
    assert runtime.ctx.claw_run_id == "run-1"
    assert runtime.ctx.workspace_binding is not None
    assert runtime.ctx.workspace_binding.cwd == "/workspace/repo-a"
    assert exported_state is not None
