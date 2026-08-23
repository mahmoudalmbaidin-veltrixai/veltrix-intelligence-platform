#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 3 ]] || {
  echo "usage: rollback.sh CLUSTER SERVICE=TASK_DEFINITION [SERVICE=TASK_DEFINITION ...]" >&2
  exit 64
}

cluster="$1"
shift

services=()
for mapping in "$@"; do
  service="${mapping%%=*}"
  task_definition="${mapping#*=}"
  [[ -n "$service" && -n "$task_definition" && "$service" != "$task_definition" ]]
  aws ecs update-service \
    --cluster "$cluster" \
    --service "$service" \
    --task-definition "$task_definition" \
    --force-new-deployment >/dev/null
  services+=("$service")
done

aws ecs wait services-stable --cluster "$cluster" --services "${services[@]}"
echo "Application services rolled back. No Alembic downgrade was executed."

