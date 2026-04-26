# Profiles

Profiles define reusable agent runtime behavior. They live in the database and can be seeded from YAML.

## Default Profile

`YA_CLAW_DEFAULT_PROFILE` defaults to `default`. Set it only when a deployment uses another profile name as the request fallback.

```env
YA_CLAW_DEFAULT_PROFILE=default
```

## Seed Profiles on Startup

Production baseline:

```env
YA_CLAW_PROFILE_SEED_FILE=/etc/ya-claw/profiles.yaml
YA_CLAW_AUTO_SEED_PROFILES=true
```

Seeded profiles use create/update semantics. Every startup refreshes matching database profiles from the YAML file, including subagent configuration. Database profiles absent from the YAML file remain available.

Manual seed:

```bash
uv run --package ya-claw ya-claw profiles seed --file /etc/ya-claw/profiles.yaml
```

API seed:

```bash
curl -X POST \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  http://127.0.0.1:9042/api/v1/profiles/seed
```

## Profile Contents

Profiles can define:

- model
- system prompt
- model settings and config presets
- built-in tool groups
- subagents
- tool approval policy
- MCP server definitions
- enabled and disabled MCP namespaces
- workspace backend hint

Important built-in toolsets:

- `session`: read-only current-session inspection tools
- `schedule`: agent-owned schedule management tools

## Test Run

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"profile_name":"default","input_parts":[{"type":"text","text":"Inspect this workspace and report the current directory."}]}' \
  http://127.0.0.1:9042/api/v1/sessions
```

Then inspect sessions:

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  http://127.0.0.1:9042/api/v1/sessions
```
