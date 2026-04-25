# 04 - API

YA Claw exposes one local HTTP API under `/api/v1`.

The API has two layers:

- **session API** for the common high-level workflow
- **run API** for explicit low-level orchestration

## API Principle

The API accepts durable execution intent first.
Run creation writes a queued run record before active execution begins.

## Resource Groups

```mermaid
flowchart TB
    ROOT[/api/v1]
    ROOT --> SESSIONS[/sessions]
    ROOT --> RUNS[/runs]
    ROOT --> EVENTS[/events via nested session and run routes]
    ROOT --> PROFILES[/profiles and seed operations later]
```

## Top-level Endpoints

| Method | Path       | Purpose                              |
| ------ | ---------- | ------------------------------------ |
| `GET`  | `/healthz` | service, storage, and runtime health |

## Sessions

| Method | Path                                      | Purpose                                         |
| ------ | ----------------------------------------- | ----------------------------------------------- |
| `POST` | `/api/v1/sessions`                        | create a session with optional first queued run |
| `GET`  | `/api/v1/sessions`                        | list sessions                                   |
| `GET`  | `/api/v1/sessions/{session_id}`           | inspect session and committed state             |
| `POST` | `/api/v1/sessions/{session_id}/runs`      | create a new queued run under the session       |
| `POST` | `/api/v1/sessions/{session_id}/steer`     | steer the active run through the session        |
| `POST` | `/api/v1/sessions/{session_id}/interrupt` | interrupt the active run through the session    |
| `POST` | `/api/v1/sessions/{session_id}/cancel`    | cancel the active run through the session       |
| `POST` | `/api/v1/sessions/{session_id}/fork`      | fork a new session lineage                      |
| `GET`  | `/api/v1/sessions/{session_id}/events`    | replay and tail session events                  |

## Runs

| Method | Path                              | Purpose                         |
| ------ | --------------------------------- | ------------------------------- |
| `POST` | `/api/v1/runs`                    | create a queued run directly    |
| `GET`  | `/api/v1/runs/{run_id}`           | inspect run and committed state |
| `POST` | `/api/v1/runs/{run_id}/steer`     | steer a specific active run     |
| `POST` | `/api/v1/runs/{run_id}/interrupt` | interrupt a specific active run |
| `POST` | `/api/v1/runs/{run_id}/cancel`    | cancel a specific active run    |
| `GET`  | `/api/v1/runs/{run_id}/events`    | replay and tail run events      |

## Request Model

Run creation and steering use structured input parts.

### Shared Input Field

```json
{
  "input_parts": [{ "type": "text", "text": "hello" }]
}
```

Supported part types:

- `text`
- `url`
- `file`
- `binary`
- `mode`
- `command`

### Session Create Request

Suggested fields:

- `profile_name`
- `project_id`
- `metadata`
- `input_parts`
- `dispatch_mode`
- `trigger_type`

### Session Continue Request

Suggested fields:

- `restore_from_run_id`
- `input_parts`
- `metadata`
- `dispatch_mode`
- `trigger_type`

### Run Create Request

Suggested fields:

- `session_id`
- `restore_from_run_id`
- `profile_name`
- `project_id`
- `input_parts`
- `metadata`
- `dispatch_mode`
- `trigger_type`

## Creation Semantics

JSON run-creating endpoints should:

1. write the durable run record with `status=queued`
2. update session pointers such as `head_run_id`
3. notify the in-process supervisor when execution is available
4. return the queued run record immediately

Foreground streaming creation uses dedicated SSE endpoints:

- `POST /api/v1/sessions:stream`
- `POST /api/v1/sessions/{session_id}/runs:stream`
- `POST /api/v1/runs:stream`

## Run Summary Shape

Suggested run summary fields:

- `id`
- `session_id`
- `sequence_no`
- `restore_from_run_id`
- `status`
- `trigger_type`
- `profile_name`
- `project_id`
- `input_preview`
- `output_summary`
- `error_message`
- `termination_reason`
- `created_at`
- `started_at`
- `finished_at`
- `committed_at`

### Status Semantics in API

- `queued` means accepted and durable, waiting to be claimed
- `running` means claimed by the supervisor and currently executing
- `completed`, `failed`, and `cancelled` are terminal states

## GET Response Shape

Session and run GET endpoints should return the structured record plus committed blobs.

### Session GET

`GET /api/v1/sessions/{session_id}?include_message=true`

```json
{
  "session": {
    "id": "session_123",
    "head_run_id": "run_3",
    "head_success_run_id": "run_2",
    "active_run_id": "run_3",
    "recent_runs": []
  },
  "state": {},
  "message": []
}
```

### Run GET

`GET /api/v1/runs/{run_id}?include_message=true`

```json
{
  "run": {
    "id": "run_2",
    "session_id": "session_123",
    "restore_from_run_id": "run_1",
    "input_parts": [],
    "has_state": true,
    "has_message": true
  },
  "state": {},
  "message": []
}
```

## Control Endpoints

Control endpoints stay flat and explicit.

Recommended shape:

- `POST /sessions/{session_id}/steer`
- `POST /sessions/{session_id}/interrupt`
- `POST /sessions/{session_id}/cancel`
- `POST /runs/{run_id}/steer`
- `POST /runs/{run_id}/interrupt`
- `POST /runs/{run_id}/cancel`

Session control routes to `active_run_id`.
Run control routes to the addressed run.

## Event Streaming

Event streaming uses SSE.

### Replay Contract

- each event has a monotonic SSE ID
- reconnect uses `Last-Event-ID`
- the server replays buffered events after that cursor
- the server then tails live events

### Transport Principle

The single-node baseline keeps the event buffer in memory.
Queued-run creation and active execution are separate concerns.
SSE reflects active or recently buffered execution, not the act of durable creation itself.

## Future Profile API

YA Claw should eventually expose profile management and seed sync APIs.
The profile records remain durable database state even when seeded from YAML.

## Authentication

The single-node baseline uses one shared bearer token configured through `YA_CLAW_API_TOKEN`.
Every HTTP route except `/healthz` sends `Authorization: Bearer <token>`.
