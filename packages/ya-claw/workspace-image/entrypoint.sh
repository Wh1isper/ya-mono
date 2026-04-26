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

ensure_lark_cli_config() {
  local app_id="${LARK_APP_ID:-${LARKSUITE_CLI_APP_ID:-}}"
  local app_secret="${LARK_APP_SECRET:-${LARKSUITE_CLI_APP_SECRET:-}}"

  if [[ -z "${app_id}" || -z "${app_secret}" ]]; then
    return 0
  fi

  export YA_CLAW_LARK_CLI_APP_ID="${app_id}"
  export YA_CLAW_LARK_CLI_APP_SECRET="${app_secret}"
  export YA_CLAW_LARK_CLI_BRAND="${LARKSUITE_CLI_BRAND:-feishu}"
  export YA_CLAW_LARK_CLI_DEFAULT_AS="${LARKSUITE_CLI_DEFAULT_AS:-bot}"
  export YA_CLAW_LARK_CLI_STRICT_MODE="${LARKSUITE_CLI_STRICT_MODE:-bot}"
  export YA_CLAW_LARK_CLI_PROFILE="${YA_CLAW_LARK_CLI_PROFILE:-ya-claw-bridge}"
  unset LARKSUITE_CLI_APP_ID
  unset LARKSUITE_CLI_APP_SECRET
  unset LARKSUITE_CLI_USER_ACCESS_TOKEN
  unset LARKSUITE_CLI_TENANT_ACCESS_TOKEN

  python3 <<'PY'
import json
import os
import tempfile
from pathlib import Path

app_id = os.environ["YA_CLAW_LARK_CLI_APP_ID"].strip()
app_secret = os.environ["YA_CLAW_LARK_CLI_APP_SECRET"].strip()
brand = os.environ.get("YA_CLAW_LARK_CLI_BRAND", "feishu").strip() or "feishu"
default_as = os.environ.get("YA_CLAW_LARK_CLI_DEFAULT_AS", "bot").strip() or "bot"
strict_mode = os.environ.get("YA_CLAW_LARK_CLI_STRICT_MODE", "bot").strip() or "bot"
profile = os.environ.get("YA_CLAW_LARK_CLI_PROFILE", "ya-claw-bridge").strip() or "ya-claw-bridge"
home = Path(os.environ.get("HOME") or "/home/claw")
config_dir = Path(os.environ.get("LARKSUITE_CLI_CONFIG_DIR") or home / ".lark-cli")
config_path = config_dir / "config.json"
config_dir.mkdir(parents=True, exist_ok=True)

existing: dict[str, object]
try:
    existing_raw = json.loads(config_path.read_text(encoding="utf-8"))
    existing = existing_raw if isinstance(existing_raw, dict) else {}
except FileNotFoundError:
    existing = {}
except json.JSONDecodeError:
    existing = {}

apps_raw = existing.get("apps")
apps = apps_raw if isinstance(apps_raw, list) else []
managed_app = {
    "name": profile,
    "appId": app_id,
    "appSecret": app_secret,
    "brand": brand,
    "defaultAs": default_as,
    "strictMode": strict_mode,
    "users": [],
}
updated = False
for index, item in enumerate(apps):
    if isinstance(item, dict) and item.get("name") == profile:
        apps[index] = managed_app
        updated = True
        break
if not updated:
    apps.append(managed_app)

existing["currentApp"] = profile
existing["apps"] = apps
fd, tmp_name = tempfile.mkstemp(prefix="config.", suffix=".json", dir=str(config_dir))
try:
    with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
        json.dump(existing, tmp_file, ensure_ascii=False, indent=2)
        tmp_file.write("\n")
    os.chmod(tmp_name, 0o600)
    os.replace(tmp_name, config_path)
finally:
    if os.path.exists(tmp_name):
        os.unlink(tmp_name)
PY
}

copy_bundled_skills() {
  local bundled_skills_root="/opt/ya-claw/skills"
  local startup_dir="${YA_CLAW_WORKSPACE_STARTUP_DIR:-${PWD}}"
  local agents_root="${startup_dir}/.agents"
  local skills_root="${agents_root}/skills"
  local ready_file="${agents_root}/.bundled-skills-ready"
  local ready_tmp="${agents_root}/.bundled-skills-ready.tmp.$$"

  mkdir -p "${agents_root}"
  rm -f "${ready_file}" "${ready_tmp}"

  if [[ -d "${bundled_skills_root}" ]]; then
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
  fi

  printf 'ready\n' > "${ready_tmp}"
  mv "${ready_tmp}" "${ready_file}"
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
    export HOME="${HOME:-/home/claw}"
    ensure_lark_cli_config
    copy_bundled_skills
    exit 0
  fi
  ensure_lark_cli_config
  copy_bundled_skills
fi

run_as_workspace_user "$@"
