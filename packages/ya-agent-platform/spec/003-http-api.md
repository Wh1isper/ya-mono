# 003 HTTP API

## API Families

| Family     | Prefix             | Audience                        |
| ---------- | ------------------ | ------------------------------- |
| Ops        | `/healthz`         | probes and platform operators   |
| Platform   | `/api/v1/platform` | first-party web app and tooling |
| Management | `/api/v1/admin`    | operators and automation        |
| Chat       | `/api/v1/chat`     | Chat UI                         |
| Bridges    | `/api/v1/bridges`  | IM bridge adapters              |

## Phase 1 Endpoints

### Ops

| Method | Path       | Purpose              |
| ------ | ---------- | -------------------- |
| `GET`  | `/healthz` | basic liveness probe |

### Platform

| Method | Path                        | Purpose                                 |
| ------ | --------------------------- | --------------------------------------- |
| `GET`  | `/`                         | backend index and mounted surface hints |
| `GET`  | `/api/v1/platform/info`     | platform metadata for the web shell     |
| `GET`  | `/api/v1/platform/topology` | component topology for operator UX      |

## Planned Management Endpoints

| Method | Path                             | Purpose                  |
| ------ | -------------------------------- | ------------------------ |
| `GET`  | `/api/v1/admin/workspaces`       | list workspaces          |
| `POST` | `/api/v1/admin/workspaces`       | create workspace         |
| `GET`  | `/api/v1/admin/agent-profiles`   | list agent profiles      |
| `POST` | `/api/v1/admin/bridge-instances` | register bridge instance |

## Planned Chat Endpoints

| Method | Path                                          | Purpose               |
| ------ | --------------------------------------------- | --------------------- |
| `POST` | `/api/v1/chat/sessions`                       | create a session      |
| `GET`  | `/api/v1/chat/sessions/{session_id}`          | fetch session summary |
| `POST` | `/api/v1/chat/sessions/{session_id}/messages` | append user input     |
| `GET`  | `/api/v1/chat/sessions/{session_id}/stream`   | stream runtime events |

## Planned Bridge Endpoints

| Method | Path                                             | Purpose                         |
| ------ | ------------------------------------------------ | ------------------------------- |
| `POST` | `/api/v1/bridges/events`                         | ingest normalized inbound event |
| `POST` | `/api/v1/bridges/deliveries/{delivery_id}/ack`   | acknowledge delivery result     |
| `GET`  | `/api/v1/bridges/instances/{bridge_instance_id}` | bridge bootstrap config         |

## Example: Platform Info Response

```json
{
  "name": "YA Agent Platform",
  "environment": "development",
  "public_base_url": "http://127.0.0.1:9042",
  "surfaces": [
    "management-api",
    "chat-api",
    "bridge-api",
    "chat-ui"
  ],
  "bridge_model": "bridge adapters connect external IM systems to normalized platform events",
  "runtime_model": "agent sessions run through ya-agent-sdk based runtimes and workers"
}
```

## Authentication Roadmap

1. local development: trusted local mode or static admin token
2. multi-user admin: session auth or OIDC
3. bridges: per-instance secret with rotation support
4. workspace APIs: scoped service tokens

## API Style

- JSON over HTTP for request-response flows
- SSE for runtime streaming in the first iteration
- explicit versioning under `/api/v1`
- stable normalized event schemas for surfaces and bridges
