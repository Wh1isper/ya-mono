# 002 Bridge Contract

## Goal

A bridge converts an external system into normalized platform events.
Every channel-specific adapter speaks the same platform contract.

## Design Goals

- one inbound event envelope across all IM systems
- one outbound delivery envelope across all IM systems
- idempotent processing
- easy local development for bridge authors
- secure bridge authentication with future cloud deployment in mind

## Bridge Roles

| Role            | Responsibility                                                 |
| --------------- | -------------------------------------------------------------- |
| Ingress Adapter | parse webhooks or polling events from an external system       |
| Egress Adapter  | send platform replies and updates back to that external system |
| Bridge Registry | stores bridge metadata, secrets, and routing bindings          |
| Platform Core   | validates, routes, persists, and executes the event            |

## Inbound Envelope

```json
{
  "event_id": "evt_01HR8V4Z7H6M7P9H2PK9J0Z6AA",
  "bridge_kind": "discord",
  "bridge_instance_id": "bridge_discord_prod",
  "workspace_id": "ws_main",
  "channel_id": "discord_channel_123",
  "thread_id": "discord_thread_456",
  "external_message_id": "msg_789",
  "actor": {
    "external_user_id": "user_123",
    "display_name": "alice",
    "is_bot": false
  },
  "message": {
    "type": "text",
    "text": "deploy the latest staging build",
    "attachments": []
  },
  "occurred_at": "2026-04-16T11:00:00Z",
  "metadata": {
    "raw_event_type": "message.create"
  }
}
```

## Outbound Envelope

```json
{
  "delivery_id": "dlv_01HR8V6VFS4M0CSK72A1E4R7JX",
  "bridge_instance_id": "bridge_discord_prod",
  "workspace_id": "ws_main",
  "channel_id": "discord_channel_123",
  "thread_id": "discord_thread_456",
  "message": {
    "type": "text",
    "text": "staging build queued",
    "attachments": []
  },
  "reply_to_external_message_id": "msg_789",
  "metadata": {
    "session_id": "sess_abc"
  }
}
```

## Delivery Semantics

### Inbound

- `event_id` is globally unique per bridge event
- the platform stores processed event ids for deduplication
- bridge retries are safe when the same envelope is resent

### Outbound

- the platform issues one delivery record per outbound send attempt
- the bridge returns send status plus the external message id
- delivery retry policy lives in the platform core

## Bridge Authentication

Phase 1 supports shared secret authentication per bridge instance.
Phase 2 can add signed requests, rotated credentials, and short-lived tokens.

## Transport Shape

Phase 1 bridge transport uses HTTP JSON.
Later phases can add queue-based transports for high-volume adapters.

## Proposed Endpoints

| Endpoint                                             | Direction          | Purpose                              |
| ---------------------------------------------------- | ------------------ | ------------------------------------ |
| `POST /api/v1/bridges/events`                        | bridge -> platform | deliver normalized inbound event     |
| `POST /api/v1/bridges/deliveries/{delivery_id}/ack`  | bridge -> platform | acknowledge outbound delivery result |
| `GET /api/v1/bridges/instances/{bridge_instance_id}` | bridge -> platform | fetch bridge configuration snapshot  |

## Open Questions

1. streaming replies through bridges as edits versus appended messages
2. attachment upload flow and object storage handoff
3. channel membership sync and permissions caching
