#!/usr/bin/env sh
set -eu

if [ "${YA_PLATFORM_AUTO_MIGRATE:-true}" = "true" ] && [ -n "${YA_PLATFORM_DATABASE_URL:-}" ]; then
  ya-agent-platform migrate
fi

exec ya-agent-platform serve --no-migrate "$@"
