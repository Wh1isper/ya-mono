#!/usr/bin/env sh
set -eu

: "${YA_CLAW_SMOKE_VERBOSE_JSON:=0}"

resolve_settings() {
  uv run --package ya-claw python - <<'PY'
from ya_claw.config import get_settings

settings = get_settings()
values = {
    'YA_CLAW_PUBLIC_BASE_URL': settings.public_base_url,
    'YA_CLAW_API_TOKEN': settings.api_token_value or '',
    'YA_CLAW_DEFAULT_PROFILE': settings.default_profile,
}
for key, value in values.items():
    print(f'{key}={value}')
PY
}

while IFS='=' read -r key value; do
  case "$key" in
    YA_CLAW_PUBLIC_BASE_URL) BASE_URL=${YA_CLAW_PUBLIC_BASE_URL:-$value} ;;
    YA_CLAW_API_TOKEN) API_TOKEN=${YA_CLAW_API_TOKEN:-$value} ;;
    YA_CLAW_DEFAULT_PROFILE) DEFAULT_PROFILE=${YA_CLAW_DEFAULT_PROFILE:-$value} ;;
  esac
done <<EOF
$(resolve_settings)
EOF

: "${BASE_URL:=http://127.0.0.1:9042}"
: "${API_TOKEN:=}"
: "${DEFAULT_PROFILE:=default}"

if [ -z "$API_TOKEN" ]; then
  echo "YA Claw API token is required." >&2
  exit 1
fi

request() {
  method=$1
  path=$2
  data=${3:-}
  if [ -n "$data" ]; then
    curl -fsS -X "$method" \
      -H "Authorization: Bearer $API_TOKEN" \
      -H "Content-Type: application/json" \
      "$BASE_URL$path" \
      -d "$data"
  else
    curl -fsS -X "$method" \
      -H "Authorization: Bearer $API_TOKEN" \
      "$BASE_URL$path"
  fi
}

json_get() {
  path=$1
  python -c '
import json
import sys

def path_get(value, path):
    if path in ("", "."):
        return value
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value

value = path_get(json.load(sys.stdin), sys.argv[1])
if isinstance(value, str):
    print(value)
elif value is None:
    print("")
else:
    print(json.dumps(value))
' "$path"
}

json_check() {
  check=$1
  shift
  python -c '
import json
import sys
from collections.abc import Mapping

data = json.load(sys.stdin)
check = sys.argv[1]
args = sys.argv[2:]


def path_get(value, path):
    if path in ("", "."):
        return value
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)

try:
    if check == "eq":
        path, expected = args
        value = path_get(data, path)
        if str(value) != expected:
            fail(f"Expected {path}={expected!r}, got {value!r}.")
    elif check == "in":
        path, *expected_values = args
        value = path_get(data, path)
        if str(value) not in expected_values:
            fail(f"Expected {path} in {expected_values!r}, got {value!r}.")
    elif check == "is-true":
        path = args[0]
        value = path_get(data, path)
        if value is not True:
            fail(f"Expected {path} to be true, got {value!r}.")
    elif check == "is-none":
        path = args[0]
        value = path_get(data, path)
        if value is not None:
            fail(f"Expected {path} to be null, got {value!r}.")
    elif check == "truthy-string":
        path = args[0]
        value = path_get(data, path)
        if not isinstance(value, str) or value.strip() == "":
            fail(f"Expected {path} to be a non-empty string, got {value!r}.")
    elif check == "is-list":
        path = args[0]
        value = path_get(data, path)
        if not isinstance(value, list):
            fail(f"Expected {path} to be a list, got {type(value).__name__}.")
    elif check == "len-min":
        path, minimum = args
        value = path_get(data, path)
        if not hasattr(value, "__len__") or len(value) < int(minimum):
            fail(f"Expected {path} length >= {minimum}, got {len(value) if hasattr(value, '__len__') else 'unknown'}.")
    elif check == "contains-name":
        path, expected_name = args
        value = path_get(data, path)
        if not isinstance(value, list) or not any(isinstance(item, Mapping) and item.get("name") == expected_name for item in value):
            fail(f"Expected {path} to contain an object named {expected_name!r}.")
    else:
        fail(f"Unknown JSON check: {check}.")
except (KeyError, IndexError, TypeError, ValueError) as exc:
    fail(f"JSON check {check} failed: {exc}")
' "$check" "$@"
}

json_summary() {
  summary=$1
  python -c '
import json
import sys

data = json.load(sys.stdin)
summary = sys.argv[1]

if summary == "profile":
    output = {
        "name": data["name"],
        "model": data["model"],
        "enabled": data["enabled"],
        "toolsets": data.get("toolsets", []),
        "subagent_count": len(data.get("subagents", [])),
    }
elif summary == "session-create":
    output = {
        "session_id": data["session"]["id"],
        "profile_name": data["session"].get("profile_name"),
        "status": data["session"]["status"],
        "run_count": data["session"]["run_count"],
        "has_run": data.get("run") is not None,
    }
elif summary == "run":
    output = {
        "run_id": data["id"],
        "session_id": data["session_id"],
        "status": data["status"],
        "profile_name": data.get("profile_name"),
        "sequence_no": data["sequence_no"],
        "input_part_types": [part["type"] for part in data.get("input_parts") or []],
        "termination_reason": data.get("termination_reason"),
        "has_message": data.get("has_message"),
    }
elif summary == "run-get":
    output = {
        "session_id": data["session"]["id"],
        "run_id": data["run"]["id"],
        "status": data["run"]["status"],
        "has_state": data["run"].get("has_state"),
        "has_message": data["run"].get("has_message"),
        "message_event_count": len(data.get("message") or []),
    }
elif summary == "trace":
    output = {
        "run_id": data["run_id"],
        "session_id": data["session_id"],
        "item_count": data["item_count"],
        "truncated": data["truncated"],
    }
elif summary == "session-detail":
    output = {
        "session_id": data["session"]["id"],
        "status": data["session"]["status"],
        "runs_limit": data["session"]["runs_limit"],
        "run_count": data["session"]["run_count"],
        "latest_run_id": (data["session"].get("latest_run") or {}).get("id"),
        "returned_run_ids": [run["id"] for run in data["session"].get("runs", [])],
        "session_message_event_count": len(data.get("message") or []),
    }
elif summary == "turns":
    output = {
        "session_id": data["session_id"],
        "limit": data["limit"],
        "turn_count": len(data.get("turns", [])),
        "has_more": data["has_more"],
    }
else:
    raise SystemExit(f"Unknown JSON summary: {summary}")

print(json.dumps(output, indent=2))
' "$summary"
}

print_json() {
  python -m json.tool
}

print_verbose_json() {
  if [ "$YA_CLAW_SMOKE_VERBOSE_JSON" = "1" ]; then
    print_json
  else
    python -c 'import sys; sys.stdin.read()'
  fi
}

wait_for_run_dispatch() {
  run_id=$1
  RUN_DETAIL=""
  attempt=0
  while [ "$attempt" -lt 30 ]; do
    RUN_DETAIL=$(request GET "/api/v1/runs/$run_id?include_state=false&include_message=true")
    status=$(printf '%s' "$RUN_DETAIL" | json_get "run.status")
    echo "status=$status"
    if [ "$status" != "queued" ]; then
      break
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
}

echo "== healthz =="
health_response=$(curl -fsS "$BASE_URL/healthz")
printf '%s\n' "$health_response" | print_json
printf '%s' "$health_response" | json_check eq status ok
printf '%s' "$health_response" | json_check eq database ok
printf '%s' "$health_response" | json_check eq runtime_state ok

echo "== claw info =="
info_response=$(request GET /api/v1/claw/info)
printf '%s\n' "$info_response" | print_json
printf '%s' "$info_response" | json_check eq auth bearer
printf '%s' "$info_response" | json_check in workspace_provider_backend local docker
printf '%s' "$info_response" | json_check is-true features.profiles

echo "== profiles =="
profiles_response=$(request GET /api/v1/profiles)
printf '%s\n' "$profiles_response" | print_json
printf '%s' "$profiles_response" | json_check len-min . 1
printf '%s' "$profiles_response" | json_check contains-name . "$DEFAULT_PROFILE"

echo "== default profile detail =="
profile_response=$(request GET "/api/v1/profiles/$DEFAULT_PROFILE")
printf '%s\n' "$profile_response" | json_summary profile
printf '%s' "$profile_response" | json_check eq name "$DEFAULT_PROFILE"
printf '%s' "$profile_response" | json_check is-true enabled
printf '%s' "$profile_response" | json_check truthy-string model

session_payload=$(DEFAULT_PROFILE="$DEFAULT_PROFILE" python - <<'PY'
import json
import os
print(json.dumps({
    'profile_name': os.environ['DEFAULT_PROFILE'],
    'metadata': {'source': 'e2e-smoke', 'case': 'empty-session'},
    'dispatch_mode': 'stream',
}))
PY
)

echo "== create empty session =="
session_response=$(request POST /api/v1/sessions "$session_payload")
printf '%s\n' "$session_response" | json_summary session-create
session_id=$(printf '%s' "$session_response" | json_get "session.id")
printf '%s' "$session_response" | json_check is-none run
printf '%s' "$session_response" | json_check eq session.status idle
printf '%s' "$session_response" | json_check eq session.profile_name "$DEFAULT_PROFILE"

run_payload=$(DEFAULT_PROFILE="$DEFAULT_PROFILE" python - <<'PY'
import json
import os
print(json.dumps({
    'metadata': {'source': 'e2e-smoke', 'case': 'session-run'},
    'input_parts': [
        {'type': 'mode', 'mode': 'smoke'},
        {'type': 'text', 'text': f'hello from e2e smoke using {os.environ["DEFAULT_PROFILE"]}'},
    ],
}))
PY
)

echo "== create session run =="
run_response=$(request POST "/api/v1/sessions/$session_id/runs" "$run_payload")
printf '%s\n' "$run_response" | json_summary run
run_id=$(printf '%s' "$run_response" | json_get "id")
printf '%s' "$run_response" | json_check eq session_id "$session_id"
printf '%s' "$run_response" | json_check eq status queued
printf '%s' "$run_response" | json_check eq input_parts.0.type mode
printf '%s' "$run_response" | json_check eq input_parts.1.type text

echo "== wait for run dispatch =="
wait_for_run_dispatch "$run_id"
printf '%s\n' "$RUN_DETAIL" | json_summary run-get
printf '%s\n' "$RUN_DETAIL" | print_verbose_json
status=$(printf '%s' "$RUN_DETAIL" | json_get "run.status")
if [ "$status" = "queued" ]; then
  echo "Run stayed queued after dispatch wait." >&2
  exit 1
fi
if [ "$status" = "failed" ]; then
  echo "Run failed during smoke dispatch." >&2
  exit 1
fi

case "$status" in
  running)
    echo "== cancel running smoke run =="
    cancel_response=$(request POST "/api/v1/runs/$run_id/cancel")
    printf '%s\n' "$cancel_response" | json_summary run
    cancel_status=$(printf '%s' "$cancel_response" | json_get "status")
    case "$cancel_status" in
      cancelled|completed)
        ;;
      *)
        echo "Unexpected cancel response status: $cancel_status" >&2
        exit 1
        ;;
    esac
    ;;
  completed|cancelled)
    echo "run reached terminal status=$status"
    ;;
  *)
    echo "Unexpected run status: $status" >&2
    exit 1
    ;;
esac

echo "== run detail =="
run_detail_response=$(request GET "/api/v1/runs/$run_id?include_state=false&include_message=true")
printf '%s\n' "$run_detail_response" | json_summary run-get
printf '%s\n' "$run_detail_response" | print_verbose_json
printf '%s' "$run_detail_response" | json_check eq session.id "$session_id"
printf '%s' "$run_detail_response" | json_check eq run.id "$run_id"
printf '%s' "$run_detail_response" | json_check eq run.input_parts.0.type mode
printf '%s' "$run_detail_response" | json_check is-none state

echo "== run trace =="
trace_response=$(request GET "/api/v1/runs/$run_id/trace?max_item_chars=256&max_total_chars=512")
printf '%s\n' "$trace_response" | json_summary trace
printf '%s\n' "$trace_response" | print_verbose_json
printf '%s' "$trace_response" | json_check eq run_id "$run_id"
printf '%s' "$trace_response" | json_check eq session_id "$session_id"
printf '%s' "$trace_response" | json_check is-list trace

echo "== session detail with replay inputs =="
session_detail_response=$(request GET "/api/v1/sessions/$session_id?include_message=true&include_input_parts=true&runs_limit=1")
printf '%s\n' "$session_detail_response" | json_summary session-detail
printf '%s\n' "$session_detail_response" | print_verbose_json
printf '%s' "$session_detail_response" | json_check eq session.id "$session_id"
printf '%s' "$session_detail_response" | json_check eq session.runs_limit 1
printf '%s' "$session_detail_response" | json_check eq session.runs.0.id "$run_id"
printf '%s' "$session_detail_response" | json_check eq session.runs.0.input_parts.0.type mode
printf '%s' "$session_detail_response" | json_check eq session.latest_run.id "$run_id"

echo "== session turns =="
turns_response=$(request GET "/api/v1/sessions/$session_id/turns?limit=5")
printf '%s\n' "$turns_response" | json_summary turns
printf '%s\n' "$turns_response" | print_verbose_json
printf '%s' "$turns_response" | json_check eq session_id "$session_id"
printf '%s' "$turns_response" | json_check eq limit 5
printf '%s' "$turns_response" | json_check is-list turns

echo "E2E smoke passed for session $session_id run $run_id"
