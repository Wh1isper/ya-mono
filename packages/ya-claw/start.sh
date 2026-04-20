#!/usr/bin/env sh
set -eu

if [ "${YA_CLAW_AUTO_MIGRATE:-true}" = "true" ]; then
  ya-claw migrate
fi

exec ya-claw serve --no-migrate "$@"
