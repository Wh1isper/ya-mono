#!/usr/bin/env sh
set -eu

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

echo "== healthz =="
curl -fsS "$BASE_URL/healthz" | python -m json.tool

echo "== profiles =="
request GET /api/v1/profiles | python -m json.tool

create_payload=$(python - <<'PY'
import json
print(json.dumps({
    'profile_name': 'default',
    'project_id': 'e2e-smoke',
    'metadata': {'source': 'e2e-smoke'},
    'input_parts': [{'type': 'text', 'text': 'hello from e2e smoke'}],
}))
PY
)

echo "== create session =="
create_response=$(request POST /api/v1/sessions "$create_payload")
printf '%s\n' "$create_response" | python -m json.tool

session_id=$(printf '%s' "$create_response" | extract_json "data['session']['id']")
run_id=$(printf '%s' "$create_response" | python -c "import json,sys; data=json.load(sys.stdin); run=data.get('run') or {}; print(run.get('id',''))")

if [ -n "$run_id" ]; then
  echo "== run detail =="
  request GET "/api/v1/runs/$run_id?include_message=true" | python -m json.tool
fi

echo "== session detail =="
request GET "/api/v1/sessions/$session_id?include_message=true" | python -m json.tool

echo "E2E smoke passed for session $session_id"
