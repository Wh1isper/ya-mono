#!/usr/bin/env sh
set -eu

if [ "${YA_CLAW_AUTO_MIGRATE:-true}" = "true" ] && [ -n "${YA_CLAW_DATABASE_URL:-}" ]; then
  ya-claw migrate
fi

exec ya-claw serve --no-migrate "$@"
