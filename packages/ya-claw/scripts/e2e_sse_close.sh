#!/usr/bin/env sh
set -eu

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

resolve_settings() {
  uv run python - <<'PY'
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

extract_json() {
  python -c "import json,sys; data=json.load(sys.stdin); print(eval(sys.argv[1], {'data': data}))" "$1"
}

create_payload=$(python - <<'PY'
import json
print(json.dumps({
    'profile_name': 'default',
    'project_id': 'e2e-sse-close',
    'input_parts': [{'type': 'text', 'text': 'verify sse closes'}],
}))
PY
)

create_response=$(request POST /api/v1/runs "$create_payload")
run_id=$(printf '%s' "$create_response" | extract_json "data['id']")
echo "run_id=$run_id"

SSE_OUT="$TMP_DIR/events.txt"
curl -fsS -N \
  -H "Authorization: Bearer $API_TOKEN" \
  "$BASE_URL/api/v1/runs/$run_id/events" > "$SSE_OUT" &
SSE_PID=$!

sleep 1
request POST "/api/v1/runs/$run_id/cancel" | python -m json.tool

wait "$SSE_PID"

echo "== SSE tail =="
tail -n 6 "$SSE_OUT"

python - "$SSE_OUT" <<'PY'
import json
from pathlib import Path
import sys

content = Path(sys.argv[1]).read_text(encoding='utf-8')
events = []
for line in content.splitlines():
    if not line.startswith('data: '):
        continue
    events.append(json.loads(line[6:]))

assert any(event.get('type') == 'CUSTOM' and event.get('name') == 'ya_claw.run_queued' for event in events), events
assert any(
    (event.get('type') == 'CUSTOM' and event.get('name') == 'ya_claw.run_cancelled')
    or event.get('type') == 'RUN_FINISHED'
    for event in events
), events
print('SSE close assertion passed')
PY
