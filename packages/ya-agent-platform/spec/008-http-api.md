# 008 HTTP API

## API Families

| Family          | Prefix                | Audience                                       |
| --------------- | --------------------- | ---------------------------------------------- |
| Ops             | `/healthz`, `/readyz` | probes and operators                           |
| Auth            | `/api/v1/auth`        | browser clients and service clients            |
| Admin           | `/api/v1/admin`       | admins and scoped users with management grants |
| Chat            | `/api/v1/chat`        | Web UI, API clients, bridge orchestrators      |
| Runtime Control | `/api/v1/runtime`     | operators and internal clients                 |
| Bridges         | `/api/v1/bridges`     | bridge adapters                                |

All APIs are JSON over HTTP except live event streams, which use SSE in the first implementation.

## Auth Endpoints

| Method | Path                  | Purpose                                     |
| ------ | --------------------- | ------------------------------------------- |
| `POST` | `/api/v1/auth/login`  | human login for browser or development mode |
| `POST` | `/api/v1/auth/logout` | revoke browser session or token             |
| `GET`  | `/api/v1/auth/me`     | resolve current actor, grants, and scopes   |
| `POST` | `/api/v1/auth/tokens` | mint scoped service token or session token  |

OIDC browser flows can sit beside these endpoints through redirect-based routes.

## Admin Endpoints

| Method | Path                                        | Purpose                                                                                              |
| ------ | ------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/v1/admin/tenants`                     | list tenants                                                                                         |
| `POST` | `/api/v1/admin/tenants`                     | create tenant                                                                                        |
| `GET`  | `/api/v1/admin/tenants/{tenant_id}`         | inspect tenant                                                                                       |
| `POST` | `/api/v1/admin/tenants/{tenant_id}/suspend` | suspend tenant                                                                                       |
| `GET`  | `/api/v1/admin/cost-centers`                | list cost centers                                                                                    |
| `POST` | `/api/v1/admin/cost-centers`                | create cost center                                                                                   |
| `GET`  | `/api/v1/admin/users`                       | list users and grants                                                                                |
| `POST` | `/api/v1/admin/users/{user_id}/grants`      | create or update scoped grants                                                                       |
| `GET`  | `/api/v1/admin/agent-profiles`              | list agent profiles                                                                                  |
| `POST` | `/api/v1/admin/agent-profiles`              | create agent profile                                                                                 |
| `GET`  | `/api/v1/admin/environment-profiles`        | list environment profiles                                                                            |
| `POST` | `/api/v1/admin/environment-profiles`        | create environment profile                                                                           |
| `GET`  | `/api/v1/admin/bridges/installations`       | list bridge installations                                                                            |
| `POST` | `/api/v1/admin/bridges/installations`       | create bridge installation                                                                           |
| `GET`  | `/api/v1/admin/workspace-provider`          | inspect provider registry, selected provider key, bootstrap config summary, capabilities, and health |
| `GET`  | `/api/v1/admin/runtime-pools`               | list runtime pools                                                                                   |
| `GET`  | `/api/v1/admin/audit`                       | search audit records                                                                                 |
| `GET`  | `/api/v1/admin/usage`                       | query usage by tenant, profile, or cost center                                                       |

## Chat Endpoints

| Method | Path                                                    | Purpose                                 |
| ------ | ------------------------------------------------------- | --------------------------------------- |
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
  "agent_profile_id": "support-agent",
  "environment_profile_id": "shared-sandbox",
  "cost_center_id": "cc_support_ops",
  "project_ids": ["repo-a", "repo-b"],
  "workspace_provider_input": {
    "container_id": "devbox-1"
  },
  "input": [
    {"type": "text", "text": "summarize the last three incidents"}
  ],
  "metadata": {
    "surface": "web_chat"
  }
}
```

The server resolves omitted fields from conversation and tenant defaults.
The provided `cost_center_id` must pass scoped-grant and policy checks.
The provided `project_ids` and `workspace_provider_input` must pass provider-policy checks.
The calling business layer is responsible for deciding why this conversation should run against those `project_ids`.

## Session Create Response

```json
{
  "conversation_id": "conv_123",
  "session_id": "sess_456",
  "status": "queued",
  "effective_cost_center_id": "cc_support_ops",
  "project_binding_id": "pb_01J...",
  "stream_url": "/api/v1/chat/sessions/sess_456/events"
}
```

## API Rules

1. every write endpoint records audit metadata
2. every cross-network retriable write accepts `Idempotency-Key`
3. list endpoints are paginated and scope-aware
4. event streaming endpoints support resumable SSE semantics
5. actor identity resolves role, grants, tenant scope, and effective cost center before handler logic
6. project context enters execution through `project_ids` and the configured `WorkspaceProvider`
7. provider implementations are code-registered, provider selection is deployment-level, and registry state is exposed through read-only admin inspection

## Versioning

- external APIs live under `/api/v1`
- envelope shapes stay additive where possible
- breaking schema changes land behind `/api/v2`
