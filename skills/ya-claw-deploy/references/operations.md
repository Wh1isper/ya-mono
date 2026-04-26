# Operations

Use these checks for production deployment verification, upgrades, backup, restore, and troubleshooting.

## Health Checks

Unauthenticated service health:

```bash
curl http://127.0.0.1:9042/healthz
```

Authenticated service info:

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  http://127.0.0.1:9042/api/v1/claw/info
```

The info endpoint reports service capabilities, storage model, workspace provider backend, and auth mode.

## Runtime Logs

Docker compose:

```bash
docker compose logs -f ya-claw
```

systemd:

```bash
journalctl -u ya-claw -f
```

Look for:

- database migration status
- seeded profile names
- execution supervisor startup
- runtime instance registration
- bridge supervisor startup when embedded bridge is enabled
- workspace container creation or reuse errors

## Bridge Checks

For embedded bridges, use the bridge-specific operations guide: [`bridge/operations.md`](bridge/operations.md).

Check service logs for bridge supervisor startup, adapter task creation, inbound dedupe results, conversation IDs, session IDs, and run IDs.

For Lark deployments, verify service ingress credentials and workspace reply credentials:

```env
YA_CLAW_BRIDGE_DISPATCH_MODE=embedded
YA_CLAW_BRIDGE_ENABLED_ADAPTERS=lark
YA_CLAW_BRIDGE_LARK_APP_ID=cli_xxx
YA_CLAW_BRIDGE_LARK_APP_SECRET=replace-with-app-secret
```

## Workspace Checks

For Docker shell shapes:

```bash
docker ps --filter 'name=ya-claw-workspace'
docker logs ya-claw-workspace-<fingerprint>
docker exec -it ya-claw-workspace-<fingerprint> pwd
docker exec -it ya-claw-workspace-<fingerprint> ls -la /workspace
docker exec -it ya-claw-workspace-<fingerprint> agent-browser --help
docker exec -it ya-claw-workspace-<fingerprint> lark-cli --version
```

For service local + local shell:

```bash
sudo -u ya-claw sh -lc 'cd /var/lib/ya-claw/workspace && pwd && ls -la'
```

Remove a stale workspace container and cache after changing the workspace image or mount contract:

```bash
docker rm -f ya-claw-workspace-<fingerprint>
rm -f /var/lib/ya-claw/data/docker-workspace-containers/workspace.json
```

## API Smoke Test

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"profile_name":"default","input_parts":[{"type":"text","text":"Run a deployment smoke test from the workspace."}]}' \
  http://127.0.0.1:9042/api/v1/sessions
```

Then list sessions:

```bash
curl -sS \
  -H "Authorization: Bearer ${YA_CLAW_API_TOKEN}" \
  http://127.0.0.1:9042/api/v1/sessions
```

## Upgrade

Docker compose baseline:

```bash
docker compose pull
docker compose up -d
curl http://127.0.0.1:9042/healthz
```

Local image baseline:

```bash
git pull
make docker-build-claw
make docker-build-claw-workspace
docker compose up -d --build
```

The `ya-claw start` command applies migrations when `YA_CLAW_AUTO_MIGRATE=true`.

## Backup

Back up both database and run store. For SQLite compose deployments with a runtime volume mounted at `/var/lib/ya-claw`:

```bash
docker compose stop ya-claw
docker run --rm \
  -v ya-claw-runtime:/var/lib/ya-claw \
  -v "$PWD/backups:/backup" \
  alpine sh -lc 'cp /var/lib/ya-claw/ya_claw.sqlite3 /backup/ya_claw.sqlite3 && tar -czf /backup/data.tgz -C /var/lib/ya-claw data workspace'
docker compose start ya-claw
```

For PostgreSQL, combine `pg_dump` with a data/workspace archive.

## Troubleshooting

### Missing API Token

Startup fails when `YA_CLAW_API_TOKEN` is empty. Generate a long token and restart.

### Run Execution Stays Pending

Check service logs, profile model configuration, model provider credentials, and runtime supervisor startup messages.

### Workspace Container Startup Fails

Check Docker access from the service container or service user:

```bash
docker ps
```

For compose, confirm `/var/run/docker.sock` is mounted. For systemd, confirm the service user has Docker access.

For service Docker + Docker shell, confirm `YA_CLAW_WORKSPACE_PROVIDER_DOCKER_HOST_WORKSPACE_DIR` points to a Docker daemon-visible host path and that the service has the same workspace content mounted at `YA_CLAW_WORKSPACE_DIR`.

### Permission Errors in Workspace

Align service and workspace IDs for Docker shell shapes:

```env
YA_CLAW_RUN_UID=1000
YA_CLAW_RUN_GID=1000
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_UID=1000
YA_CLAW_WORKSPACE_PROVIDER_DOCKER_GID=1000
```

Then repair ownership on mounted paths.

### Profile Missing

Enable seed or seed manually:

```env
YA_CLAW_PROFILE_SEED_FILE=/etc/ya-claw/profiles.yaml
YA_CLAW_AUTO_SEED_PROFILES=true
```

```bash
uv run --package ya-claw ya-claw profiles seed --seed-file /etc/ya-claw/profiles.yaml
```
