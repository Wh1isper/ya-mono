# 008 HTTP API

## API Families

| Family          | Prefix                   | Audience                                          |
| --------------- | ------------------------ | ------------------------------------------------- |
| Ops             | `/healthz`, `/readyz`    | probes and operators                              |
| Auth            | `/api/v1/auth`           | browser clients and service clients               |
| Platform Admin  | `/api/v1/platform-admin` | platform operators                                |
| Tenant Admin    | `/api/v1/admin`          | tenant owners, tenant admins, workspace operators |
| Chat            | `/api/v1/chat`           | Web UI, API clients, bridge orchestrators         |
| Runtime Control | `/api/v1/runtime`        | operators and internal clients                    |
| Bridges         | `/api/v1/bridges`        | bridge adapters                                   |

All APIs are JSON over HTTP except live event streams, which use SSE in the first implementation.

## Auth Endpoints

| Method | Path                  | Purpose                                     |
| ------ | --------------------- | ------------------------------------------- |
| `POST` | `/api/v1/auth/login`  | human login for browser or development mode |
| `POST` | `/api/v1/auth/logout` | revoke browser session or token             |
| `GET`  | `/api/v1/auth/me`     | resolve current actor and scopes            |
| `POST` | `/api/v1/auth/tokens` | mint scoped service token or session token  |

OIDC browser flows can sit beside these endpoints through redirect-based routes.

## Platform Admin Endpoints

| Method | Path                                                 | Purpose                         |
| ------ | ---------------------------------------------------- | ------------------------------- |
| `GET`  | `/api/v1/platform-admin/tenants`                     | list tenants                    |
| `POST` | `/api/v1/platform-admin/tenants`                     | create tenant                   |
| `GET`  | `/api/v1/platform-admin/tenants/{tenant_id}`         | inspect tenant                  |
| `POST` | `/api/v1/platform-admin/tenants/{tenant_id}/suspend` | suspend tenant                  |
| `GET`  | `/api/v1/platform-admin/runtime-pools`               | list runtime pools              |
| `POST` | `/api/v1/platform-admin/runtime-pools`               | register or update runtime pool |
| `GET`  | `/api/v1/platform-admin/audit`                       | global audit search             |

## Tenant Admin Endpoints

| Method | Path                                  | Purpose                             |
| ------ | ------------------------------------- | ----------------------------------- |
| `GET`  | `/api/v1/admin/tenant`                | get current tenant summary          |
| `GET`  | `/api/v1/admin/members`               | list members and service principals |
| `POST` | `/api/v1/admin/members`               | invite or create member             |
| `GET`  | `/api/v1/admin/workspaces`            | list workspaces                     |
| `POST` | `/api/v1/admin/workspaces`            | create workspace                    |
| `GET`  | `/api/v1/admin/agent-profiles`        | list agent profiles                 |
| `POST` | `/api/v1/admin/agent-profiles`        | create agent profile                |
| `GET`  | `/api/v1/admin/environment-profiles`  | list environment profiles           |
| `POST` | `/api/v1/admin/environment-profiles`  | create environment profile          |
| `GET`  | `/api/v1/admin/bridges/installations` | list bridge installations           |
| `POST` | `/api/v1/admin/bridges/installations` | create bridge installation          |
| `GET`  | `/api/v1/admin/policies`              | list effective policies             |
| `POST` | `/api/v1/admin/secrets`               | register or rotate secret reference |

## Chat Endpoints

| Method | Path                                                    | Purpose                                 |
| ------ | ------------------------------------------------------- | --------------------------------------- |
| `GET`  | `/api/v1/chat/workspaces`                               | list workspaces available to the actor  |
| `GET`  | `/api/v1/chat/conversations`                            | list conversations                      |
| `POST` | `/api/v1/chat/conversations`                            | create a new conversation               |
| `GET`  | `/api/v1/chat/conversations/{conversation_id}`          | fetch conversation summary              |
| `POST` | `/api/v1/chat/conversations/{conversation_id}/sessions` | enqueue a new session in a conversation |
| `POST` | `/api/v1/chat/conversations/{conversation_id}/fork`     | fork from a prior session               |
| `GET`  | `/api/v1/chat/sessions/{session_id}`                    | fetch session summary                   |
| `GET`  | `/api/v1/chat/sessions/{session_id}/events`             | live or replay event stream             |
| `POST` | `/api/v1/chat/sessions/{session_id}/approve`            | submit approval payload                 |
| `POST` | `/api/v1/chat/sessions/{session_id}/artifacts`          | upload files for future turns           |

## Runtime Control Endpoints

| Method | Path                                              | Purpose                                |
| ------ | ------------------------------------------------- | -------------------------------------- |
| `POST` | `/api/v1/runtime/sessions/{session_id}/interrupt` | cancel a running session               |
| `POST` | `/api/v1/runtime/sessions/{session_id}/steer`     | inject guidance into a running session |
| `GET`  | `/api/v1/runtime/sessions/{session_id}/status`    | read scheduler and worker state        |
| `POST` | `/api/v1/runtime/sessions/{session_id}/retry`     | retry a retryable failed session       |

## Bridge Endpoints

| Method | Path                                                               | Purpose                         |
| ------ | ------------------------------------------------------------------ | ------------------------------- |
| `POST` | `/api/v1/bridges/events`                                           | ingest normalized inbound event |
| `POST` | `/api/v1/bridges/deliveries/{delivery_id}/ack`                     | acknowledge outbound attempt    |
| `GET`  | `/api/v1/bridges/installations/{bridge_installation_id}`           | fetch installation snapshot     |
| `POST` | `/api/v1/bridges/installations/{bridge_installation_id}/heartbeat` | report bridge liveness          |

## Session Create Request

```json
{
  "workspace_id": "ws_support",
  "agent_profile_id": "support-agent",
  "environment_profile_id": "shared-sandbox",
  "input": [
    {"type": "text", "text": "summarize the last three incidents"}
  ],
  "metadata": {
    "surface": "web_chat"
  }
}
```

The server resolves omitted fields from conversation and workspace defaults.

## Session Create Response

```json
{
  "conversation_id": "conv_123",
  "session_id": "sess_456",
  "status": "queued",
  "stream_url": "/api/v1/chat/sessions/sess_456/events"
}
```

## API Rules

1. every write endpoint records audit metadata
2. every cross-network retriable write accepts `Idempotency-Key`
3. list endpoints are paginated and tenant-scoped
4. event streaming endpoints support resumable SSE semantics
5. actor identity resolves tenant and workspace scope before handler logic

## Versioning

- external APIs live under `/api/v1`
- envelope shapes stay additive where possible
- breaking schema changes land behind `/api/v2`
