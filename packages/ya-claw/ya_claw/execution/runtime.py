from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from y_agent_environment import Environment
from ya_agent_sdk.agents.main import AgentRuntime, create_agent
from ya_agent_sdk.context import ModelConfig, ResumableState
from ya_agent_sdk.mcp import build_mcp_servers, extract_mcp_descriptions, extract_optional_mcps, filter_mcp_config
from ya_agent_sdk.toolsets.core.base import BaseTool
from ya_agent_sdk.toolsets.core.document import tools as document_tools
from ya_agent_sdk.toolsets.core.filesystem import tools as filesystem_tools
from ya_agent_sdk.toolsets.core.multimodal import tools as multimodal_tools
from ya_agent_sdk.toolsets.core.shell import tools as shell_tools
from ya_agent_sdk.toolsets.core.web import tools as web_tools
from ya_agent_sdk.toolsets.skills.toolset import SHARED_SKILLS_DIR_NAME, SkillToolset
from ya_agent_sdk.toolsets.tool_proxy.toolset import ToolProxyToolset
from ya_agent_sdk.toolsets.tool_search import create_best_strategy

from ya_claw.config import ClawSettings
from ya_claw.context import ClawAgentContext, ClawWorkspaceBindingSnapshot
from ya_claw.execution.profile import ResolvedProfile
from ya_claw.mcp import ClawMCPConfigResolver
from ya_claw.toolsets.background import SpawnDelegateTool, SteerSubagentTool
from ya_claw.workspace import WorkspaceBinding, extract_session_sandbox_metadata

if TYPE_CHECKING:
    from pydantic_ai.toolsets import AbstractToolset

_DEFAULT_SYSTEM_PROMPT = """
You are the YA Claw execution agent.
Work inside the provided workspace, use filesystem and shell tools carefully,
and leave the workspace in a useful committed state for the next run.
Prefer concise, action-oriented execution.
""".strip()

_BUILTIN_TOOL_REGISTRY: dict[str, list[type[BaseTool]]] = {
    "filesystem": list(filesystem_tools),
    "shell": list(shell_tools),
    "web": list(web_tools),
    "multimodal": list(multimodal_tools),
    "document": list(document_tools),
    "background": [SpawnDelegateTool, SteerSubagentTool],
}
_BUILTIN_TOOLSET_ALIASES: dict[str, list[str]] = {
    "core": ["filesystem", "shell", "background"],
}


class ClawRuntimeBuilder:
    def __init__(
        self,
        *,
        settings: ClawSettings,
        mcp_config_resolver: ClawMCPConfigResolver | None = None,
    ) -> None:
        self._settings = settings
        self._mcp_config_resolver = mcp_config_resolver or ClawMCPConfigResolver(settings=settings)

    def build(
        self,
        *,
        profile: ResolvedProfile,
        binding: WorkspaceBinding,
        environment: Environment,
        restore_state: ResumableState | None,
        session_id: str,
        run_id: str,
        project_id: str | None,
        restore_from_run_id: str | None,
        dispatch_mode: str,
        source_kind: str | None,
        source_metadata: dict[str, Any] | None,
        claw_metadata: dict[str, Any] | None,
    ) -> AgentRuntime[ClawAgentContext, Any, Environment]:
        sandbox_metadata = extract_session_sandbox_metadata(binding.metadata) or {}
        extra_context_kwargs = {
            "session_id": session_id,
            "claw_run_id": run_id,
            "profile_name": profile.name,
            "project_id": project_id,
            "restore_from_run_id": restore_from_run_id,
            "dispatch_mode": dispatch_mode,
            "container_id": sandbox_metadata.get("container_id") if isinstance(sandbox_metadata, dict) else None,
            "workspace_binding": ClawWorkspaceBindingSnapshot.from_binding(binding),
            "source_kind": source_kind,
            "source_metadata": dict(source_metadata or {}),
            "claw_metadata": dict(claw_metadata or {}),
        }
        return create_agent(
            model=profile.model,
            model_settings=cast(Any, profile.model_settings),
            context_type=ClawAgentContext,
            model_cfg=self._build_model_config(profile),
            env=environment,
            extra_context_kwargs=extra_context_kwargs,
            state=restore_state,
            need_user_approve_tools=profile.need_user_approve_tools,
            need_user_approve_mcps=profile.need_user_approve_mcps,
            tools=self._resolve_builtin_tools(profile.builtin_toolsets),
            toolsets=self._resolve_runtime_toolsets(profile=profile, binding=binding) or None,
            subagent_configs=profile.subagent_configs,
            include_builtin_subagents=profile.include_builtin_subagents,
            unified_subagents=profile.unified_subagents,
            system_prompt=self._build_system_prompt(profile=profile, binding=binding, project_id=project_id),
        )

    def _build_model_config(self, profile: ResolvedProfile) -> ModelConfig:
        payload = dict(profile.model_config or {})
        if payload.get("context_window") is None and self._settings.execution_context_window > 0:
            payload["context_window"] = self._settings.execution_context_window
        return ModelConfig.model_validate(payload)

    def _resolve_builtin_tools(self, toolset_names: list[str]) -> list[type[BaseTool]]:
        resolved: list[type[BaseTool]] = []
        seen: set[str] = set()
        for name in toolset_names:
            expanded_names = _BUILTIN_TOOLSET_ALIASES.get(name, [name])
            for expanded_name in expanded_names:
                for tool in _BUILTIN_TOOL_REGISTRY.get(expanded_name, []):
                    tool_name = getattr(tool, "name", tool.__name__)
                    if tool_name in seen:
                        continue
                    seen.add(tool_name)
                    resolved.append(tool)
        return resolved

    def _resolve_runtime_toolsets(
        self,
        *,
        profile: ResolvedProfile,
        binding: WorkspaceBinding,
    ) -> list[AbstractToolset[Any]]:
        toolsets: list[AbstractToolset[Any]] = [
            SkillToolset(toolset_id="skills", extra_dir_names=[SHARED_SKILLS_DIR_NAME]),
        ]
        loaded_config = self._mcp_config_resolver.load_for_workspace(binding.host_path)
        if loaded_config is None:
            return toolsets

        filtered_config = filter_mcp_config(
            loaded_config.config,
            enabled_mcps=profile.enabled_mcps,
            disabled_mcps=profile.disabled_mcps,
        )
        if not filtered_config.servers:
            return toolsets

        mcp_servers = build_mcp_servers(filtered_config, need_approval_mcps=profile.need_user_approve_mcps)
        if not mcp_servers:
            return toolsets

        mcp_descriptions = extract_mcp_descriptions(filtered_config)
        optional_mcps = extract_optional_mcps(filtered_config)
        toolsets.append(
            ToolProxyToolset(
                toolsets=mcp_servers,
                namespace_descriptions=mcp_descriptions if mcp_descriptions else None,
                search_strategy=create_best_strategy(),
                optional_namespaces=optional_mcps if optional_mcps else None,
            )
        )
        return toolsets

    def _build_system_prompt(
        self,
        *,
        profile: ResolvedProfile,
        binding: WorkspaceBinding,
        project_id: str | None,
    ) -> str:
        prompt_lines = [profile.system_prompt or _DEFAULT_SYSTEM_PROMPT]
        prompt_lines.append(f"Workspace virtual root: {binding.virtual_path}")
        prompt_lines.append(f"Default working directory: {binding.cwd}")
        prompt_lines.append(f"Readable paths: {', '.join(str(path) for path in binding.readable_paths)}")
        prompt_lines.append(f"Writable paths: {', '.join(str(path) for path in binding.writable_paths)}")
        prompt_lines.append("Mounted projects:")
        for mount in binding.project_mounts:
            description = f" -- {mount.description}" if isinstance(mount.description, str) and mount.description else ""
            prompt_lines.append(f"- {mount.project_id}: {mount.virtual_path}{description}")
        prompt_lines.append("Project skills are discovered from each mounted project's .agents/skills/ directory.")
        prompt_lines.append(f"Profile: {profile.name}")
        if isinstance(project_id, str) and project_id.strip() != "":
            prompt_lines.append(f"Project ID: {project_id}")
        return "\n".join(prompt_lines)
