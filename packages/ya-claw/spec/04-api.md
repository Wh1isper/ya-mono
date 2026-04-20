# 04 - API

YA Claw exposes one local HTTP API under `/api/v1`.

The API should stay resource-oriented and small enough to match the single-node runtime shape.

## Resource Groups

```mermaid
flowchart TB
    ROOT[/api/v1]
    ROOT --> CLAW[/claw]
    ROOT --> WORKSPACES[/workspaces]
    ROOT --> PROFILES[/profiles]
    ROOT --> SESSIONS[/sessions]
    ROOT --> RUNS[/runs]
    ROOT --> ARTIFACTS[/artifacts]
    ROOT --> EVENTS[/events]
```

## Top-level Endpoints

| Method | Path                    | Purpose             |
| ------ | ----------------------- | ------------------- |
| `GET`  | `/healthz`              | service health      |
| `GET`  | `/api/v1/claw/info`     | runtime metadata    |
| `GET`  | `/api/v1/claw/topology` | high-level topology |

## Workspaces

| Method  | Path                                        | Purpose                    |
| ------- | ------------------------------------------- | -------------------------- |
| `POST`  | `/api/v1/workspaces`                        | create workspace           |
| `GET`   | `/api/v1/workspaces`                        | list workspaces            |
| `GET`   | `/api/v1/workspaces/{workspace_id}`         | inspect workspace          |
| `POST`  | `/api/v1/workspaces/{workspace_id}/resolve` | preview binding resolution |
| `PATCH` | `/api/v1/workspaces/{workspace_id}`         | update workspace           |

## Profiles

| Method  | Path                            | Purpose         |
| ------- | ------------------------------- | --------------- |
| `POST`  | `/api/v1/profiles`              | create profile  |
| `GET`   | `/api/v1/profiles`              | list profiles   |
| `GET`   | `/api/v1/profiles/{profile_id}` | inspect profile |
| `PATCH` | `/api/v1/profiles/{profile_id}` | update profile  |

## Sessions

| Method | Path                                    | Purpose               |
| ------ | --------------------------------------- | --------------------- |
| `POST` | `/api/v1/sessions`                      | create root session   |
| `GET`  | `/api/v1/sessions`                      | list sessions         |
| `GET`  | `/api/v1/sessions/{session_id}`         | inspect session       |
| `POST` | `/api/v1/sessions/{session_id}/fork`    | fork session lineage  |
| `POST` | `/api/v1/sessions/{session_id}/compact` | compact session state |

## Runs

| Method | Path                           | Purpose     |
| ------ | ------------------------------ | ----------- |
| `POST` | `/api/v1/runs`                 | start run   |
| `GET`  | `/api/v1/runs/{run_id}`        | inspect run |
| `POST` | `/api/v1/runs/{run_id}/cancel` | cancel run  |

## Artifacts

| Method | Path                                       | Purpose                 |
| ------ | ------------------------------------------ | ----------------------- |
| `GET`  | `/api/v1/artifacts/{artifact_id}`          | fetch artifact metadata |
| `GET`  | `/api/v1/artifacts/{artifact_id}/download` | download artifact       |

## Events

| Method | Path                                   | Purpose                 |
| ------ | -------------------------------------- | ----------------------- |
| `GET`  | `/api/v1/events/runs/{run_id}`         | stream run events       |
| `GET`  | `/api/v1/events/sessions/{session_id}` | stream session timeline |

## Request Model

A run request should carry:

- session creation or continuation intent
- selected profile
- selected workspace and optional project
- input payload parts
- optional transport override

## API Style

- `GET` for pure reads
- `POST` or `PATCH` for mutations
- SSE for browser-native live delivery

## Error Envelope

Suggested error shape:

```json
{
  "error": {
    "code": "workspace_resolution_failed",
    "message": "WorkspaceProvider could not resolve the workspace.",
    "details": {}
  }
}
```

## Authentication

The single-node baseline can start from one shared bearer token model or trusted local deployment mode.

Authentication should stay orthogonal to workspace, session, and run structure.
