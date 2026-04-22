from __future__ import annotations

from typing import Any, cast

from y_agent_environment import Environment
from ya_agent_sdk.agents.main import AgentRuntime, create_agent
from ya_agent_sdk.context import ModelConfig, ResumableState
from ya_agent_sdk.toolsets.core.base import BaseTool
from ya_agent_sdk.toolsets.core.document import tools as document_tools
from ya_agent_sdk.toolsets.core.filesystem import tools as filesystem_tools
from ya_agent_sdk.toolsets.core.multimodal import tools as multimodal_tools
from ya_agent_sdk.toolsets.core.shell import tools as shell_tools
from ya_agent_sdk.toolsets.core.web import tools as web_tools

from ya_claw.config import ClawSettings
from ya_claw.context import ClawAgentContext, ClawWorkspaceBindingSnapshot
from ya_claw.execution.profile import ResolvedProfile
from ya_claw.workspace import WorkspaceBinding, extract_session_sandbox_metadata

_DEFAULT_SYSTEM_PROMPT = """
You are the YA Claw execution agent.
Work inside the provided workspace, use filesystem and shell tools carefully,
and leave the workspace in a useful committed state for the next run.
Prefer concise, action-oriented execution.
""".strip()

_TOOL_REGISTRY: dict[str, list[type[BaseTool]]] = {
    "filesystem": list(filesystem_tools),
    "shell": list(shell_tools),
    "web": list(web_tools),
    "multimodal": list(multimodal_tools),
    "document": list(document_tools),
}
_TOOLSET_ALIASES: dict[str, list[str]] = {
    "core": ["filesystem", "shell"],
}


class ClawRuntimeBuilder:
    def __init__(self, *, settings: ClawSettings) -> None:
        self._settings = settings

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
            tools=self._resolve_tools(profile.toolsets),
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

    def _resolve_tools(self, toolset_names: list[str]) -> list[type[BaseTool]]:
        resolved: list[type[BaseTool]] = []
        seen: set[str] = set()
        for name in toolset_names:
            expanded_names = _TOOLSET_ALIASES.get(name, [name])
            for expanded_name in expanded_names:
                for tool in _TOOL_REGISTRY.get(expanded_name, []):
                    tool_name = getattr(tool, "name", tool.__name__)
                    if tool_name in seen:
                        continue
                    seen.add(tool_name)
                    resolved.append(tool)
        return resolved

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
        prompt_lines.append(f"Profile: {profile.name}")
        if isinstance(project_id, str) and project_id.strip() != "":
            prompt_lines.append(f"Project ID: {project_id}")
        return "\n".join(prompt_lines)
