#!/usr/bin/env sh
set -eu

if [ "${YA_CLAW_AUTO_MIGRATE:-true}" = "true" ]; then
  ya-claw db upgrade
fi

exec ya-claw serve --no-migrate "$@"
