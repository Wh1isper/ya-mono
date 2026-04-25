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

ensure_group_for_gid() {
  local target_gid="$1"
  if getent group "${target_gid}" >/dev/null; then
    return 0
  fi

  local group_name="ya-claw-g${target_gid}"
  local suffix=1
  while getent group "${group_name}" >/dev/null; do
    group_name="ya-claw-g${target_gid}-${suffix}"
    suffix=$((suffix + 1))
  done

  groupadd --gid "${target_gid}" "${group_name}"
}

ensure_user_for_uid() {
  local target_uid="$1"
  local target_gid="$2"
  local target_home="$3"
  if getent passwd "${target_uid}" >/dev/null; then
    return 0
  fi

  local user_name="ya-claw-u${target_uid}"
  local suffix=1
  while getent passwd "${user_name}" >/dev/null; do
    user_name="ya-claw-u${target_uid}-${suffix}"
    suffix=$((suffix + 1))
  done

  useradd \
    --uid "${target_uid}" \
    --gid "${target_gid}" \
    --home-dir "${target_home}" \
    --create-home \
    --shell /bin/bash \
    "${user_name}"
}

if [[ "${EUID}" -eq 0 && -n "${YA_CLAW_RUN_UID:-}" ]]; then
  target_uid="${YA_CLAW_RUN_UID}"
  target_gid="${YA_CLAW_RUN_GID:-${YA_CLAW_RUN_UID}}"
  target_home="/home/ya-claw"

  validate_numeric_id YA_CLAW_RUN_UID "${target_uid}"
  validate_numeric_id YA_CLAW_RUN_GID "${target_gid}"
  ensure_group_for_gid "${target_gid}"
  ensure_user_for_uid "${target_uid}" "${target_gid}" "${target_home}"

  mkdir -p "${target_home}"
  chown "${target_uid}:${target_gid}" "${target_home}"

  export HOME="${target_home}"
  export YA_CLAW_RUN_UID="${target_uid}"
  export YA_CLAW_RUN_GID="${target_gid}"

  exec gosu "${target_uid}:${target_gid}" "$@"
fi

exec "$@"
