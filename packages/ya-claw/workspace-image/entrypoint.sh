#!/usr/bin/env bash
set -euo pipefail

copy_bundled_skills() {
  local bundled_skills_root="/opt/ya-claw/skills"
  local startup_dir="${YA_CLAW_WORKSPACE_STARTUP_DIR:-${PWD}}"
  local skills_root="${startup_dir}/.agents/skills"

  if [[ ! -d "${bundled_skills_root}" ]]; then
    return 0
  fi

  mkdir -p "${skills_root}"

  shopt -s nullglob dotglob
  local bundled_skill_dir
  for bundled_skill_dir in "${bundled_skills_root}"/*; do
    if [[ ! -d "${bundled_skill_dir}" ]]; then
      continue
    fi

    local skill_name
    skill_name="$(basename "${bundled_skill_dir}")"
    mkdir -p "${skills_root}/${skill_name}"
    cp -R "${bundled_skill_dir}/." "${skills_root}/${skill_name}/"
  done
}

copy_bundled_skills

exec "$@"
