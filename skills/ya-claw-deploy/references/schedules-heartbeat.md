# Schedules and Heartbeat Deployment

YA Claw has two timer surfaces:

- schedules are cron jobs managed through the API, web console, or the agent `schedule` toolset
- heartbeat is a runtime-owned operational timer controlled by environment settings

## Default Heartbeat Configuration

| Setting                              | Default                                    | Purpose                                                         |
| ------------------------------------ | ------------------------------------------ | --------------------------------------------------------------- |
| `YA_CLAW_HEARTBEAT_ENABLED`          | `false`                                    | Enables the heartbeat dispatcher                                |
| `YA_CLAW_HEARTBEAT_INTERVAL_SECONDS` | `300`                                      | Seconds between heartbeat fires                                 |
| `YA_CLAW_HEARTBEAT_PROFILE`          | unset                                      | Uses `YA_CLAW_DEFAULT_PROFILE`, which defaults to `default`     |
| `YA_CLAW_HEARTBEAT_PROMPT`           | `Run heartbeat according to HEARTBEAT.md.` | Prompt submitted for heartbeat runs                             |
| `YA_CLAW_HEARTBEAT_ON_ACTIVE`        | `skip`                                     | Active-run policy used by heartbeat dispatcher                  |
| `HEARTBEAT.md` path                  | `<workspace>/HEARTBEAT.md`                 | Runtime-owned heartbeat guidance loaded only for heartbeat runs |

Heartbeat is disabled by default. When enabled, each fire creates an isolated session and a queued run with `trigger_type=heartbeat`. The runtime loads regular workspace guidance from `AGENTS.md` and heartbeat guidance from `HEARTBEAT.md`.

## Enable Heartbeat

```env
YA_CLAW_HEARTBEAT_ENABLED=true
YA_CLAW_HEARTBEAT_INTERVAL_SECONDS=300
YA_CLAW_HEARTBEAT_PROFILE=default
YA_CLAW_HEARTBEAT_PROMPT=Run heartbeat according to HEARTBEAT.md.
YA_CLAW_HEARTBEAT_ON_ACTIVE=skip
```

Create the heartbeat guidance file in the configured workspace:

```bash
cat > /var/lib/ya-claw/workspace/HEARTBEAT.md <<'EOF'
# Heartbeat

Check runtime health, workspace cleanliness, and recent failed runs.
Write a short operational note when an issue needs attention.
EOF
```

For Docker workspace provider deployments, create `HEARTBEAT.md` in `YA_CLAW_WORKSPACE_DIR` from the service point of view and confirm the Docker daemon-visible path maps to the same workspace through `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOST_WORKSPACE_DIR`.

## Schedule Dispatcher Defaults

| Setting                             | Default | Purpose                                       |
| ----------------------------------- | ------- | --------------------------------------------- |
| `YA_CLAW_SCHEDULE_DISPATCH_ENABLED` | `true`  | Enables cron schedule dispatch                |
| `YA_CLAW_SCHEDULE_TICK_SECONDS`     | `5`     | Dispatcher scan interval                      |
| `YA_CLAW_SCHEDULE_MAX_DUE_PER_TICK` | `20`    | Maximum due schedule fires processed per scan |

Schedules use five-field cron expressions plus timezone. Manual trigger is available through the web console and `POST /api/v1/schedules/{schedule_id}:trigger`.

## Agent Schedule Toolset

Profiles can include the built-in `schedule` toolset, or include `core`, which expands to the default operational tools including `schedule`.

Agent-facing schedule tools accept:

- plain text `prompt`
- five-field `cron`
- `timezone`
- `enabled`
- `continue_current_session`
- `start_from_current_session`
- `steer_when_running`

The runtime maps these simple fields to the durable schedule record. Agent-created schedules inherit the current run profile and are scoped to the current session.

## Web Console Operations

The web console provides:

- Schedules page for cron job list, create, edit, delete, enable, pause, manual trigger, and recent fires
- Heartbeat page for effective config, `HEARTBEAT.md` presence, next fire, last fire, fire history, and manual trigger

## API Checks

```bash
curl -H "Authorization: Bearer $YA_CLAW_API_TOKEN" \
  http://127.0.0.1:9042/api/v1/heartbeat/config

curl -H "Authorization: Bearer $YA_CLAW_API_TOKEN" \
  http://127.0.0.1:9042/api/v1/heartbeat/status

curl -H "Authorization: Bearer $YA_CLAW_API_TOKEN" \
  http://127.0.0.1:9042/api/v1/schedules
```

Manual heartbeat trigger:

```bash
curl -X POST -H "Authorization: Bearer $YA_CLAW_API_TOKEN" \
  http://127.0.0.1:9042/api/v1/heartbeat:trigger
```

Create a cron schedule:

```bash
curl -X POST \
  -H "Authorization: Bearer $YA_CLAW_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:9042/api/v1/schedules \
  -d '{
    "name": "Daily workspace review",
    "prompt": "Review the workspace and report follow-up actions.",
    "cron": "0 9 * * *",
    "timezone": "UTC",
    "enabled": true,
    "continue_current_session": false,
    "start_from_current_session": false,
    "steer_when_running": false,
    "owner_kind": "user"
  }'
```

## Operational Checks

- `/healthz` should report service health.
- `/api/v1/heartbeat/config` should show `guidance_file.exists=true` after `HEARTBEAT.md` is created.
- `/api/v1/heartbeat/fires` should show heartbeat fire records after dispatcher or manual trigger runs.
- `/api/v1/schedules` should show cron schedules and `next_fire_at` values.
- run history should show `trigger_type=heartbeat` or `trigger_type=schedule` for timer-created runs.

## Backup and Restore

Timer state is stored in the relational database:

- `schedules`
- `schedule_fires`
- `heartbeat_fires`

Heartbeat instructions are stored in the workspace file `HEARTBEAT.md`. Include both database backup and workspace backup in production backup procedures.
