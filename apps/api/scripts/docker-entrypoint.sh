#!/bin/sh
set -eu

if [ "${SKIP_PLATFORM_BOOTSTRAP:-false}" != "true" ]; then
  alembic upgrade head
  python -m vip_api.cli seed-governance
  python -m vip_api.cli seed-connection-types
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "${APP_ENV:-development}" = "development" ]; then
  exec uvicorn vip_api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload --no-access-log
fi

exec uvicorn vip_api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log
