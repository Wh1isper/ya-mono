# Bridge Operations

Use these checks when enabling embedded bridges, verifying Lark ingress, or troubleshooting bridge-triggered runs.

## Startup Checks

Health endpoint:

```bash
curl http://127.0.0.1:9042/healthz
```

Authenticated service info:

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  http://127.0.0.1:9042/api/v1/claw/info
```

Expected embedded bridge settings:

```env
YA_CLAW_BRIDGE_DISPATCH_MODE=embedded
YA_CLAW_BRIDGE_ENABLED_ADAPTERS=lark
YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx
YA_CLAW_BRIDGE_LARK_APP_SECRET=replace-with-app-secret
```

Inspect service logs for `BridgeSupervisor` startup, adapter task creation, Lark websocket connection messages, inbound event handling, dedupe results, conversation IDs, session IDs, and run IDs.

## Lark Credential Checks

The service process needs Lark bridge ingress credentials:

```env
YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx
YA_CLAW_BRIDGE_LARK_APP_SECRET=replace-with-app-secret
```

The workspace needs `lark-cli` reply credentials. YA Claw injects `LARK_APP_ID` and `LARK_APP_SECRET` into workspace environments from explicit process env values or from the Lark bridge settings.

For Docker shell shapes, these values are passed when the reusable workspace container is created. Check the workspace container:

```bash
docker exec -it ya-claw-workspace-<fingerprint> lark-cli --version
docker exec -it ya-claw-workspace-<fingerprint> sh -lc 'test -n "$LARK_APP_ID" && test -n "$LARK_APP_SECRET"'
```

After credential changes, recreate the reusable workspace container so Docker receives the new environment:

```bash
docker rm -f ya-claw-workspace-<fingerprint>
rm -f /var/lib/ya-claw/data/docker-workspace-containers/workspace.json
```

## Event Subscription Checks

Confirm the Lark/Feishu app subscribes to the event types configured in YA Claw:

```env
YA_CLAW_BRIDGE_LARK_EVENT_TYPES=im.chat.member.bot.added_v1,im.chat.member.user.added_v1,im.message.receive_v1,drive.notice.comment_add_v1
```

Align the Lark app subscription list with the YA Claw allowlist so each intended event type reaches the adapter handler.

## Profile Checks

Bridge-created sessions require a valid profile:

```env
YA_CLAW_BRIDGE_LARK_DEFAULT_PROFILE=default
YA_CLAW_PROFILE_SEED_FILE=/etc/ya-claw/profiles.yaml
YA_CLAW_AUTO_SEED_PROFILES=true
```

Check startup logs for seeded profile names. Use the profiles command when seeding manually:

```bash
uv run --package ya-claw ya-claw profiles seed --seed-file /etc/ya-claw/profiles.yaml
```

## Event Dedupe Checks

Bridge dedupe uses these keys:

1. `(adapter, tenant_key, event_id)`
2. `(adapter, tenant_key, external_message_id)`

Repeated Lark delivery should reuse the existing bridge event result. Inspect logs and database rows for `duplicate`, `submitted`, `queued`, and `failed` statuses.

## Conversation Checks

Lark message events map chat conversations to YA Claw sessions by `(adapter, tenant_key, chat_id)`. Drive and generic events use stable fallback keys for payloads that carry Drive tokens or event IDs.

A new chat creates one bridge conversation row and one YA Claw session. Later events with the same conversation key create runs under the same session.

## Troubleshooting

### Bridge Supervisor Startup

Confirm embedded dispatch and enabled adapters:

```env
YA_CLAW_BRIDGE_DISPATCH_MODE=embedded
YA_CLAW_BRIDGE_ENABLED_ADAPTERS=lark
```

Restart the service and inspect logs for bridge lifecycle messages.

### Lark Adapter Fails on Startup

Set both Lark bridge credentials:

```env
YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx
YA_CLAW_BRIDGE_LARK_APP_SECRET=replace-with-app-secret
```

Confirm outbound network access from the YA Claw service to the configured Lark domain:

```env
YA_CLAW_BRIDGE_LARK_DOMAIN=https://open.feishu.cn
```

### Events Arrive but Runs Fail

Check profile configuration, model provider credentials, execution supervisor startup, and workspace provider health. Bridge ingestion creates the run; normal run execution handles model calls and tools.

### Agent Reply Fails

Check `lark-cli` availability and credentials in the workspace container or local workspace environment. Confirm the Lark app has reply permissions for the chat/message type and that the agent uses the message ID and idempotency key provided in the bridge prompt.

### Manual Command Status

The current manual bridge CLI commands are placeholders for separated worker flows. Embedded dispatch is the active Lark websocket ingestion path.

## References

- Bridge overview: [`overview.md`](overview.md)
- Lark bridge: [`lark.md`](lark.md)
- General operations: [`../operations.md`](../operations.md)
