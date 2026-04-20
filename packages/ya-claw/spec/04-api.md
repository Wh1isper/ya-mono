# 04 - API

YA Claw exposes one local HTTP API under `/api/v1`.

The API should stay small enough to match the single-node runtime shape.

## Resource Groups

```mermaid
flowchart TB
    ROOT[/api/v1]
    ROOT --> CLAW[/claw]
    ROOT --> SESSIONS[/sessions]
    ROOT --> RUNS[/runs]
    ROOT --> EVENTS[/events]
    ROOT --> SCHEDULES[/schedules]
    ROOT --> BRIDGES[/bridges]
    ROOT --> ARTIFACTS[/artifacts]
```

## Top-level Endpoints

| Method | Path                    | Purpose                              |
| ------ | ----------------------- | ------------------------------------ |
| `GET`  | `/healthz`              | service, storage, and runtime health |
| `GET`  | `/api/v1/claw/info`     | runtime metadata                     |
| `GET`  | `/api/v1/claw/topology` | high-level topology                  |

## Sessions

| Method | Path                                    | Purpose                               |
| ------ | --------------------------------------- | ------------------------------------- |
| `POST` | `/api/v1/sessions`                      | create root session                   |
| `GET`  | `/api/v1/sessions`                      | list sessions                         |
| `GET`  | `/api/v1/sessions/{session_id}`         | inspect session                       |
| `GET`  | `/api/v1/sessions/{session_id}/state`   | read committed session state snapshot |
| `GET`  | `/api/v1/sessions/{session_id}/message` | read committed compacted message view |
| `POST` | `/api/v1/sessions/{session_id}/fork`    | fork session lineage                  |
| `POST` | `/api/v1/sessions/{session_id}/compact` | compact session state                 |

## Runs

| Method | Path                           | Purpose            |
| ------ | ------------------------------ | ------------------ |
| `POST` | `/api/v1/runs`                 | start run          |
| `GET`  | `/api/v1/runs/{run_id}`        | inspect run        |
| `POST` | `/api/v1/runs/{run_id}/cancel` | cancel run or task |

### Run Scheduling Model

- foreground runs execute within the single-node process
- background work stays attached to the same runtime and surfaces through run status and events
- task coordination stays in process memory
- schedule dispatch and bridge ingress both create runs through the same execution path

## Schedules

| Method  | Path                                      | Purpose                       |
| ------- | ----------------------------------------- | ----------------------------- |
| `POST`  | `/api/v1/schedules`                       | create session schedule       |
| `GET`   | `/api/v1/schedules`                       | list schedules                |
| `GET`   | `/api/v1/schedules/{schedule_id}`         | inspect schedule              |
| `PATCH` | `/api/v1/schedules/{schedule_id}`         | update schedule               |
| `POST`  | `/api/v1/schedules/{schedule_id}/enable`  | enable schedule               |
| `POST`  | `/api/v1/schedules/{schedule_id}/disable` | disable schedule              |
| `POST`  | `/api/v1/schedules/{schedule_id}/trigger` | trigger schedule immediately  |
| `GET`   | `/api/v1/schedules/{schedule_id}/runs`    | list runs created by schedule |

## Bridges

| Method | Path                                       | Purpose                         |
| ------ | ------------------------------------------ | ------------------------------- |
| `GET`  | `/api/v1/bridges`                          | list bridge endpoints           |
| `GET`  | `/api/v1/bridges/{bridge_id}`              | inspect bridge endpoint         |
| `POST` | `/api/v1/bridges/{bridge_id}/dispatch`     | ingest channel event or message |
| `GET`  | `/api/v1/bridges/{bridge_id}/events`       | stream bridge runtime events    |
| `POST` | `/api/v1/bridges/{bridge_id}/task-relay`   | submit async bridge work        |
| `POST` | `/api/v1/bridges/{bridge_id}/stream-relay` | start foreground bridge relay   |

### Bridge Request Model

A bridge dispatch request should carry:

- bridge endpoint identity
- source platform event payload
- target relay mode
- session routing policy
- opaque `project_id` or project-selection metadata
- optional reply target metadata

## Artifacts

| Method | Path                                       | Purpose                 |
| ------ | ------------------------------------------ | ----------------------- |
| `GET`  | `/api/v1/artifacts/{artifact_id}`          | fetch artifact metadata |
| `GET`  | `/api/v1/artifacts/{artifact_id}/download` | download artifact       |

## Events

| Method | Path                                   | Purpose                                |
| ------ | -------------------------------------- | -------------------------------------- |
| `GET`  | `/api/v1/events/runs/{run_id}`         | stream live run events                 |
| `GET`  | `/api/v1/events/sessions/{session_id}` | stream session timeline                |
| `GET`  | `/api/v1/events/agui/{session_id}`     | stream AGUI-aligned session event flow |

## Request Model

A run request should carry:

- session creation or continuation intent
- selected profile when profiles are runtime-managed
- opaque `project_id`
- input payload parts
- request metadata for project resolution and delivery
- optional transport override

### Request Design Principle

YA Claw consumes `project_id` and metadata.
YA Claw does not need project CRUD endpoints.

## API Style

- `GET` for pure reads
- `POST` or `PATCH` for mutations
- SSE for browser-native live delivery, AGUI-aligned session events, and bridge stream relay

## Error Envelope

Suggested error shape:

```json
{
  "error": {
    "code": "project_resolution_failed",
    "message": "The runtime could not resolve the requested execution scope.",
    "details": {}
  }
}
```

## Authentication

The single-node baseline can start from one shared bearer token model or trusted local deployment mode.

Authentication should stay orthogonal to session, run, schedule, and bridge structure.
