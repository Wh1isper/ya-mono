#!/usr/bin/env bash
set -euo pipefail

validate_numeric_id() {
  local name="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^[0-9]+$ ]]; then
    echo "${name} must be a numeric ID." >&2
    exit 1
  fi
}

resolve_workspace_identity() {
  YA_CLAW_WORKSPACE_UID="${YA_CLAW_WORKSPACE_UID:-$(id -u)}"
  YA_CLAW_WORKSPACE_GID="${YA_CLAW_WORKSPACE_GID:-$(id -g)}"

  validate_numeric_id YA_CLAW_WORKSPACE_UID "${YA_CLAW_WORKSPACE_UID}"
  validate_numeric_id YA_CLAW_WORKSPACE_GID "${YA_CLAW_WORKSPACE_GID}"

  export YA_CLAW_WORKSPACE_UID
  export YA_CLAW_WORKSPACE_GID
  export YA_CLAW_HOST_UID="${YA_CLAW_HOST_UID:-${YA_CLAW_WORKSPACE_UID}}"
  export YA_CLAW_HOST_GID="${YA_CLAW_HOST_GID:-${YA_CLAW_WORKSPACE_GID}}"
}

ensure_group_for_gid() {
  local target_gid="$1"
  if getent group "${target_gid}" >/dev/null; then
    return 0
  fi

  local group_name="claw-g${target_gid}"
  local suffix=1
  while getent group "${group_name}" >/dev/null; do
    group_name="claw-g${target_gid}-${suffix}"
    suffix=$((suffix + 1))
  done

  groupadd --gid "${target_gid}" "${group_name}"
}

ensure_user_for_uid() {
  local target_uid="$1"
  local target_gid="$2"
  if getent passwd "${target_uid}" >/dev/null; then
    return 0
  fi

  local user_name="claw-u${target_uid}"
  local suffix=1
  while getent passwd "${user_name}" >/dev/null; do
    user_name="claw-u${target_uid}-${suffix}"
    suffix=$((suffix + 1))
  done

  useradd \
    --uid "${target_uid}" \
    --gid "${target_gid}" \
    --home-dir /home/claw \
    --create-home \
    --shell /bin/bash \
    "${user_name}"
}

ensure_workspace_user() {
  if [[ "${EUID}" -ne 0 ]]; then
    return 0
  fi

  ensure_group_for_gid "${YA_CLAW_WORKSPACE_GID}"
  ensure_user_for_uid "${YA_CLAW_WORKSPACE_UID}" "${YA_CLAW_WORKSPACE_GID}"

  mkdir -p /home/claw
  chown "${YA_CLAW_WORKSPACE_UID}:${YA_CLAW_WORKSPACE_GID}" /home/claw
}

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

run_as_workspace_user() {
  if [[ "${EUID}" -eq 0 ]]; then
    export HOME=/home/claw
    export USER="$(id -un "${YA_CLAW_WORKSPACE_UID}" 2>/dev/null || printf 'claw')"
    exec gosu "${YA_CLAW_WORKSPACE_UID}:${YA_CLAW_WORKSPACE_GID}" "$@"
  fi

  exec "$@"
}

resolve_workspace_identity
ensure_workspace_user

if [[ "${EUID}" -eq 0 ]]; then
  export HOME=/home/claw
  export USER="$(id -un "${YA_CLAW_WORKSPACE_UID}" 2>/dev/null || printf 'claw')"
  gosu "${YA_CLAW_WORKSPACE_UID}:${YA_CLAW_WORKSPACE_GID}" "$0" --copy-bundled-skills
else
  if [[ "${1:-}" == "--copy-bundled-skills" ]]; then
    copy_bundled_skills
    exit 0
  fi
  copy_bundled_skills
fi

run_as_workspace_user "$@"
