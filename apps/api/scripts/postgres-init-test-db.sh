#!/bin/sh
set -eu

# This database is isolated for integration tests that validate downgrade/upgrade behavior.
if ! psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align \
    --command "SELECT 1 FROM pg_database WHERE datname = 'vip_test'" | grep -q 1; then
  createdb --username "$POSTGRES_USER" --owner "$POSTGRES_USER" vip_test
fi
