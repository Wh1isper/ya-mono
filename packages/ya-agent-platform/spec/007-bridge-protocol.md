# 007 Bridge Protocol

## Purpose

A bridge adapter connects an external channel to YA Agent Platform through one normalized contract.

The adapter is channel-aware.
The platform core is tenant-aware.
The conversation model stays shared.

## Bridge Design Principles

- adapters stay stateless wherever possible
- normalized inbound envelopes make routing deterministic
- outbound delivery is durable and retryable
- bridge credentials are installation-scoped
- one installation belongs to one tenant
- route resolution can supply default `project_ids` for a session run

## Bridge Installation Model

A bridge installation stores:

- `tenant_id`
- `bridge_kind` such as `discord`, `slack`, `telegram`, `wecom`, `email`
- auth material reference
- route rules
- optional default `project_ids`
- optional provider-default input
- mention and thread behavior
- outbound delivery policy
- health metadata and last heartbeat

## Inbound Envelope

```json
{
  "event_id": "bevt_01J...",
  "event_type": "message.created",
  "bridge_kind": "discord",
  "bridge_installation_id": "bridge_discord_acme_prod",
  "tenant_id": "tenant_acme",
  "route": {
    "channel_id": "discord_channel_123",
    "thread_id": "discord_thread_456",
    "conversation_key": "discord:123:456"
  },
  "actor": {
    "external_user_id": "u_789",
    "display_name": "alice",
    "is_bot": false
  },
  "message": {
    "type": "text",
    "text": "summarize the latest incident",
    "attachments": []
  },
  "metadata": {
    "raw_event_type": "MESSAGE_CREATE"
  },
  "occurred_at": "2026-04-17T03:10:00Z"
}
```

## Routing Rules

Bridge routing resolves in this order:

1. explicit route override on the installation
2. route mapping based on channel or thread rules
3. installation default `project_ids` or provider-default input
4. tenant default route policy

The result selects:

- tenant
- target conversation or conversation creation policy
- default `project_ids` when the bridge route defines project context
- default agent and environment profiles if configured

## Outbound Delivery Envelope

```json
{
  "delivery_id": "dlv_01J...",
  "bridge_installation_id": "bridge_discord_acme_prod",
  "tenant_id": "tenant_acme",
  "session_id": "sess_456",
  "route": {
    "channel_id": "discord_channel_123",
    "thread_id": "discord_thread_456"
  },
  "message": {
    "mode": "final",
    "type": "text",
    "text": "Here is the incident summary...",
    "attachments": []
  },
  "reply_to_external_message_id": "msg_789",
  "metadata": {
    "conversation_id": "conv_123"
  }
}
```

### Delivery modes

| Mode            | Meaning                                         |
| --------------- | ----------------------------------------------- |
| `stream_append` | adapter can send incremental appended chunks    |
| `stream_edit`   | adapter can edit a single in-flight message     |
| `final`         | adapter sends one final message                 |
| `signal`        | adapter sends typing, seen, or auxiliary signal |

Each installation declares which delivery modes it supports.

## Bridge Authentication

### Inbound auth

Supported mechanisms:

- bearer installation token
- HMAC signed webhook
- provider-native signature verification with installation metadata

### Outbound auth

Outbound worker credentials come from the bridge installation secret projection.

The platform core never requires channel credentials to be embedded in session data.

## Idempotency And Retries

### Inbound

- `event_id` is installation-scoped unique
- the platform stores processed event ids for deduplication
- adapters can safely retry inbound submits

### Outbound

- every outbound attempt gets a `delivery_attempt_id`
- the logical `delivery_id` remains stable across retries
- adapters acknowledge success or terminal failure through the ack API
- retry policy belongs to the platform installation config

## Attachment Handling

Inbound attachments can be:

- passed as URLs when safe and policy allows
- ingested into object storage and attached as artifacts
- promoted into the session input as provider-visible file references

Outbound attachments are produced from committed artifacts or signed object-store URLs.

## Required Bridge Endpoints

| Endpoint                                                                | Direction          | Purpose                             |
| ----------------------------------------------------------------------- | ------------------ | ----------------------------------- |
| `POST /api/v1/bridges/events`                                           | bridge -> platform | submit normalized inbound envelope  |
| `POST /api/v1/bridges/deliveries/{delivery_id}/ack`                     | bridge -> platform | acknowledge outbound attempt result |
| `GET /api/v1/bridges/installations/{bridge_installation_id}`            | bridge -> platform | fetch installation config snapshot  |
| `POST /api/v1/bridges/installations/{bridge_installation_id}/heartbeat` | bridge -> platform | report adapter liveness and version |

## Product Rule

Bridge adapters translate channel behavior.
They do not own conversation state, identity policy, provider resolution, or retry policy.
Those belong to the platform.
