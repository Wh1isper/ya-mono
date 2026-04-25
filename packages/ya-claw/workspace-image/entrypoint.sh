#!/usr/bin/env bash
set -euo pipefail

install_agent_browser_skill() {
  local bundled_skill_root="/opt/ya-claw/skills/agent-browser"

  if [[ ! -d "${bundled_skill_root}" ]]; then
    return 0
  fi

  shopt -s nullglob
  local workspace_dir
  for workspace_dir in /workspace/*; do
    if [[ ! -d "${workspace_dir}" ]]; then
      continue
    fi

    local skills_root="${workspace_dir}/.agents/skills"
    if [[ -e "${skills_root}/agent-browser/SKILL.md" ]]; then
      continue
    fi

    mkdir -p "${skills_root}"
    cp -R "${bundled_skill_root}" "${skills_root}/agent-browser"
  done
}

install_agent_browser_skill

exec "$@"
