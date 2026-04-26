# Lark Bridge

The built-in `lark` bridge adapter accepts Lark/Feishu events through the Lark websocket client, normalizes accepted events, and submits bridge-triggered YA Claw runs. Agents reply or act from the workspace with `lark-cli`.

## Embedded Deployment

Use embedded dispatch for current Lark bridge deployments:

```env
YA_CLAW_BRIDGE_DISPATCH_MODE=embedded
YA_CLAW_BRIDGE_ENABLED_ADAPTERS=lark
YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx
YA_CLAW_BRIDGE_LARK_APP_SECRET=replace-with-app-secret
YA_CLAW_BRIDGE_LARK_DEFAULT_PROFILE=default
YA_CLAW_BRIDGE_LARK_EVENT_TYPES=im.chat.member.bot.added_v1,im.chat.member.user.added_v1,im.message.receive_v1,drive.notice.comment_add_v1
YA_CLAW_BRIDGE_LARK_REPLY_IDENTITY=bot
YA_CLAW_BRIDGE_LARK_DOMAIN=https://open.feishu.cn
```

`BridgeSupervisor` starts `LarkBridgeAdapter` with the HTTP server. The adapter requires `YA_CLAW_BRIDGE_LARK_APP_ID` and `YA_CLAW_BRIDGE_LARK_APP_SECRET`, creates a Lark websocket client with `auto_reconnect=True`, registers every event type in `YA_CLAW_BRIDGE_LARK_EVENT_TYPES`, and passes normalized events to `BridgeController`.

## Lark App Requirements

Configure the Lark/Feishu app for websocket event delivery and subscribe to the event types enabled in YA Claw. The default allowlist is:

- `im.chat.member.bot.added_v1`
- `im.chat.member.user.added_v1`
- `im.message.receive_v1`
- `drive.notice.comment_add_v1`

Grant the app permissions needed for the selected event subscriptions and for replies/actions performed by `lark-cli` from the agent workspace.

## Conversation Mapping

Lark events become `BridgeInboundMessage` records:

| Event shape                  | Conversation key                                                                    |
| ---------------------------- | ----------------------------------------------------------------------------------- |
| `im.message.receive_v1`      | message `chat_id`                                                                   |
| Generic chat event           | `chat_id` or `open_chat_id` from the event payload                                  |
| Drive event                  | `drive/{file_token}` or another stable Drive token as the fallback conversation key |
| Other accepted generic event | `event/{event_type}/{event_id}`                                                     |

The database maps `(adapter, tenant_key, external_chat_id)` to a YA Claw session. `tenant_key` comes from the Lark event header and falls back to `default`.

## Event and Message Dedupe

YA Claw dedupes inbound bridge traffic before creating runs:

1. `(adapter, tenant_key, event_id)`
2. `(adapter, tenant_key, external_message_id)`

Duplicate events return the existing session/run identifiers when available. Failed event processing records the error on the bridge event row.

## Profile Selection

Lark-triggered conversations use this profile resolution:

1. `YA_CLAW_BRIDGE_LARK_DEFAULT_PROFILE` when set
2. `YA_CLAW_DEFAULT_PROFILE`
3. `default`

Seed the selected profile at startup for deploys that rely on bundled profile configuration:

```env
YA_CLAW_PROFILE_SEED_FILE=/etc/ya-claw/profiles.yaml
YA_CLAW_AUTO_SEED_PROFILES=true
```

## Workspace Reply Credentials

Agents reply from the workspace with `lark-cli`. YA Claw builds workspace reply credentials from the service process environment in this order:

1. `LARK_APP_ID` and `LARK_APP_SECRET`
2. `YA_CLAW_BRIDGE_LARK_APP_ID` and `YA_CLAW_BRIDGE_LARK_APP_SECRET`

Use explicit `LARK_*` variables when the workspace should use a separate Lark identity:

```env
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=replace-with-app-secret
```

For Docker shell shapes, `DefaultEnvironmentFactory` passes these values into `DockerEnvironmentFactory`; `ReusableSandboxEnvironment` then creates the workspace container with Docker SDK `containers.run(environment=...)`. The variables become container-level environment values available to `lark-cli`.

Reusable workspace containers keep the environment from container creation time. After changing Lark credentials, remove the workspace container and its cache so YA Claw creates a container with the new environment:

```bash
docker rm -f ya-claw-workspace-<fingerprint>
rm -f /var/lib/ya-claw/data/docker-workspace-containers/workspace.json
```

The official Docker workspace image includes `lark-cli` and copies Lark-related skills into `/workspace/.agents/skills/` at container startup.

## Agent Reply Contract

The bridge-created run prompt includes the source message ID and an idempotency key. The recommended reply shape is:

```bash
lark-cli im +messages-reply \
  --message-id <message_id> \
  --as bot \
  --text '<reply>' \
  --idempotency-key bridge-lark-<event_id>
```

Set `YA_CLAW_BRIDGE_LARK_REPLY_IDENTITY=bot` for the default bot reply identity. Use app permissions and workspace credentials that match the reply identity and action surface.

## Manual Mode Status

`YA_CLAW_BRIDGE_DISPATCH_MODE=manual` starts the HTTP server and leaves `BridgeSupervisor` outside the server lifespan. Current CLI bridge commands print requested actions as placeholders for the separated worker model:

```bash
uv run --package ya-claw ya-claw bridge ls
uv run --package ya-claw ya-claw bridge run lark
uv run --package ya-claw ya-claw bridge serve lark
```

Use embedded mode for active Lark websocket ingestion in current deployments.

## References

- Bridge overview: [`overview.md`](overview.md)
- Bridge operations: [`operations.md`](operations.md)
- Environment settings: [`../environment.md`](../environment.md)
