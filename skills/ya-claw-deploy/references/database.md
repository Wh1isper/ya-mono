# Database

YA Claw uses SQLite by default and supports PostgreSQL through `YA_CLAW_DATABASE_URL`.

## SQLite

Default SQLite path:

```text
~/.ya-claw/ya_claw.sqlite3
```

The path is derived from the parent of `YA_CLAW_DATA_DIR`. With:

```env
YA_CLAW_DATA_DIR=/var/lib/ya-claw/data
```

The SQLite file is:

```text
/var/lib/ya-claw/ya_claw.sqlite3
```

For single-node deployments, SQLite keeps operations simple. Back up both the SQLite file and the runtime data directory.

## PostgreSQL

Set:

```env
YA_CLAW_DATABASE_URL=postgresql+psycopg://ya_claw:ya_claw@postgres:5432/ya_claw
```

Pool settings:

```env
YA_CLAW_DATABASE_POOL_SIZE=5
YA_CLAW_DATABASE_MAX_OVERFLOW=10
YA_CLAW_DATABASE_POOL_RECYCLE_SECONDS=3600
```

`YA_CLAW_DATA_DIR` is still required because run continuity blobs live in the local run store.

## Migrations

The `ya-claw start` command runs migrations when `YA_CLAW_AUTO_MIGRATE=true`.

Manual commands:

```bash
uv run --package ya-claw ya-claw db upgrade
uv run --package ya-claw ya-claw db current
uv run --package ya-claw ya-claw db history
```

## Backup

SQLite backup baseline:

```bash
systemctl stop ya-claw
sqlite3 /var/lib/ya-claw/ya_claw.sqlite3 ".backup '/backup/ya_claw.sqlite3'"
rsync -a /var/lib/ya-claw/data/ /backup/data/
systemctl start ya-claw
```

PostgreSQL backup baseline:

```bash
pg_dump "$YA_CLAW_DATABASE_URL" > ya_claw.sql
rsync -a /var/lib/ya-claw/data/ /backup/data/
```

The data directory contains `run-store/{run_id}/state.json` and `run-store/{run_id}/message.json`, so database-only backups capture metadata and data-dir backups capture committed continuity blobs.

## Restore

SQLite restore baseline:

```bash
systemctl stop ya-claw
cp /backup/ya_claw.sqlite3 /var/lib/ya-claw/ya_claw.sqlite3
rsync -a --delete /backup/data/ /var/lib/ya-claw/data/
chown -R ya-claw:ya-claw /var/lib/ya-claw
systemctl start ya-claw
```

PostgreSQL restore baseline:

```bash
psql "$YA_CLAW_DATABASE_URL" < ya_claw.sql
rsync -a --delete /backup/data/ /var/lib/ya-claw/data/
```
