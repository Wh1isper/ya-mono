# Environment Configuration

YA Claw loads settings from process environment and `.env` files. `YA_CLAW_*` variables configure the service. Provider keys and tool credentials can share the same env file because YA Claw startup exports non-`YA_CLAW_` entries into the process environment.

## Required Settings

| Variable                             | Purpose                                                                    |
| ------------------------------------ | -------------------------------------------------------------------------- |
| `YA_CLAW_API_TOKEN`                  | Shared bearer token for all HTTP routes except `/healthz`                  |
| `YA_CLAW_DATA_DIR`                   | Persistent runtime data root for run store and runtime records             |
| `YA_CLAW_WORKSPACE_DIR`              | Persistent workspace directory exposed to agent environments               |
| `YA_CLAW_WORKSPACE_PROVIDER_BACKEND` | Workspace backend: `docker` or `local`                                     |
| `YA_CLAW_DEFAULT_PROFILE`            | Profile name used when requests omit `profile_name`; defaults to `default` |

## Core Service Settings

| Variable                  | Default                                  | Purpose                                                             |
| ------------------------- | ---------------------------------------- | ------------------------------------------------------------------- |
| `YA_CLAW_ENVIRONMENT`     | `development`                            | Runtime environment label                                           |
| `YA_CLAW_HOST`            | `127.0.0.1`; Docker image sets `0.0.0.0` | HTTP bind host                                                      |
| `YA_CLAW_PORT`            | `9042`                                   | HTTP bind port                                                      |
| `YA_CLAW_PUBLIC_BASE_URL` | `http://127.0.0.1:9042`                  | Public base URL used by integrations                                |
| `YA_CLAW_INSTANCE_ID`     | generated host/pid/id                    | Runtime instance identity for run ownership and heartbeat           |
| `YA_CLAW_AUTO_MIGRATE`    | `true`                                   | Run database migrations on startup                                  |
| `YA_CLAW_WEB_DIST_DIR`    | unset                                    | Web shell dist directory; Docker image uses `/srv/ya-claw/web-dist` |
| `YA_CLAW_ALLOW_ORIGINS`   | local dev origins                        | CORS origins parsed by pydantic-settings                            |

## Storage Settings

| Variable                                | Default                                   | Purpose                                |
| --------------------------------------- | ----------------------------------------- | -------------------------------------- |
| `YA_CLAW_DATA_DIR`                      | `~/.ya-claw/data`                         | Runtime data directory                 |
| `YA_CLAW_WORKSPACE_DIR`                 | `~/.ya-claw/data/workspace`               | Agent workspace directory              |
| `YA_CLAW_DATABASE_URL`                  | SQLite under `~/.ya-claw/ya_claw.sqlite3` | SQLAlchemy database URL                |
| `YA_CLAW_DATABASE_ECHO`                 | `false`                                   | SQL logging                            |
| `YA_CLAW_DATABASE_POOL_SIZE`            | `5`                                       | PostgreSQL pool size                   |
| `YA_CLAW_DATABASE_MAX_OVERFLOW`         | `10`                                      | PostgreSQL pool overflow               |
| `YA_CLAW_DATABASE_POOL_RECYCLE_SECONDS` | `3600`                                    | PostgreSQL connection recycle interval |

## Profile and Execution Settings

| Variable                     | Purpose                                                                       |
| ---------------------------- | ----------------------------------------------------------------------------- |
| `YA_CLAW_DEFAULT_PROFILE`    | Default profile name; defaults to `default`                                   |
| `YA_CLAW_PROFILE_SEED_FILE`  | YAML seed file path, commonly `packages/ya-claw/profiles.yaml` in development |
| `YA_CLAW_AUTO_SEED_PROFILES` | Upsert seeded profiles on startup                                             |

## Workspace Provider Settings

| Variable                                                | Purpose                                                                   |
| ------------------------------------------------------- | ------------------------------------------------------------------------- |
| `YA_CLAW_WORKSPACE_PROVIDER_BACKEND`                    | `docker` for Docker shell execution, `local` for local shell execution    |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_IMAGE`               | Workspace image, default `ghcr.io/wh1isper/ya-claw-workspace:latest`      |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOST_WORKSPACE_DIR`  | Docker daemon-visible workspace path for service Docker + Docker shell    |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_UID`                 | UID inside auto-started workspace containers                              |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_GID`                 | GID inside auto-started workspace containers                              |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXEC_USER`           | Docker exec user; default `auto` resolves to workspace UID:GID            |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOME`                | Default HOME for Docker exec commands, default `/home/claw`               |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_CONTAINER_CACHE_DIR` | Stable workspace container ID cache directory                             |
| `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXTRA_MOUNTS`        | Comma-separated Docker extra mounts using host_path:container_path[:mode] |
| `YA_CLAW_WORKSPACE_ENV_VARS`                            | Comma-separated process env names forwarded into workspace environments   |

## Bridge Settings

| Variable                              | Purpose                                                                       |
| ------------------------------------- | ----------------------------------------------------------------------------- |
| `YA_CLAW_BRIDGE_DISPATCH_MODE`        | `embedded` or `manual`; default `embedded`                                    |
| `YA_CLAW_BRIDGE_ENABLED_ADAPTERS`     | Comma-separated adapter list, currently `lark`                                |
| `YA_CLAW_BRIDGE_LARK_ENABLED`         | Compatibility switch that also enables the Lark adapter                       |
| `YA_CLAW_BRIDGE_LARK_APP_ID`          | Lark/Feishu app ID for bridge websocket ingress                               |
| `YA_CLAW_BRIDGE_LARK_APP_SECRET`      | Lark/Feishu app secret for bridge websocket ingress                           |
| `YA_CLAW_BRIDGE_LARK_DEFAULT_PROFILE` | Profile used for Lark-triggered runs; falls back to `YA_CLAW_DEFAULT_PROFILE` |
| `YA_CLAW_BRIDGE_LARK_EVENT_TYPES`     | Accepted Lark event allowlist                                                 |
| `YA_CLAW_BRIDGE_LARK_REPLY_IDENTITY`  | `bot` or `user`                                                               |
| `YA_CLAW_BRIDGE_LARK_DOMAIN`          | Lark/Feishu OpenAPI domain                                                    |
| `LARK_APP_ID`                         | Workspace `lark-cli` app ID; overrides bridge-derived workspace value         |
| `LARK_APP_SECRET`                     | Workspace `lark-cli` app secret; overrides bridge-derived workspace value     |

For Docker shell shapes, YA Claw passes workspace environment values to the reusable workspace container at container creation time. Built-in `LARK_APP_ID` and `LARK_APP_SECRET` aliases come from explicit process env values or the Lark bridge app settings. Additional values are forwarded by listing process env names in `YA_CLAW_WORKSPACE_ENV_VARS`. Docker shell commands use `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXEC_USER=auto` by default, which resolves to workspace UID:GID, and receive `HOME` from `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOME` with default `/home/claw`. Additional host directories are mounted by listing `host_path:container_path[:mode]` entries in `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXTRA_MOUNTS`; supported modes are `rw` and `ro`.

```env
MY_TOOL_API_KEY=replace-with-tool-key
MY_TOOL_ENDPOINT=https://tool.example.com
YA_CLAW_WORKSPACE_ENV_VARS=MY_TOOL_API_KEY,MY_TOOL_ENDPOINT
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXEC_USER=auto
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOME=/home/claw
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_EXTRA_MOUNTS=/srv/ya-claw/home:/home/claw:rw,/srv/ya-claw/cache:/cache:ro
```

Recreate the workspace container after changing values passed to Docker container creation.

See [`bridge/overview.md`](bridge/overview.md), [`bridge/lark.md`](bridge/lark.md), and [`bridge/operations.md`](bridge/operations.md) for deployment shape and operations details.

## Production Env Baseline

Use this as the baseline and edit secrets, public URL, profile path, storage paths, and provider credentials:

```env
YA_CLAW_ENVIRONMENT=production
YA_CLAW_HOST=0.0.0.0
YA_CLAW_PORT=9042
YA_CLAW_PUBLIC_BASE_URL=https://claw.example.com
YA_CLAW_API_TOKEN=replace-with-a-long-random-token
YA_CLAW_AUTO_MIGRATE=true
YA_CLAW_DATA_DIR=/var/lib/ya-claw/data
YA_CLAW_WORKSPACE_DIR=/var/lib/ya-claw/workspace
YA_CLAW_WORKSPACE_PROVIDER_BACKEND=docker
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOST_WORKSPACE_DIR=/srv/ya-claw/workspace
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_IMAGE=ghcr.io/wh1isper/ya-claw-workspace:latest
YA_CLAW_PROFILE_SEED_FILE=/etc/ya-claw/profiles.yaml
YA_CLAW_AUTO_SEED_PROFILES=true
YA_CLAW_BRIDGE_DISPATCH_MODE=embedded
YA_CLAW_BRIDGE_ENABLED_ADAPTERS=lark
YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx
YA_CLAW_BRIDGE_LARK_APP_SECRET=replace-with-app-secret
YA_CLAW_BRIDGE_LARK_DEFAULT_PROFILE=default
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=replace-with-workspace-lark-secret
MY_TOOL_API_KEY=replace-with-tool-key
YA_CLAW_WORKSPACE_ENV_VARS=MY_TOOL_API_KEY
GATEWAY_API_KEY=replace-with-provider-key
GATEWAY_BASE_URL=https://gateway.example.com
```
