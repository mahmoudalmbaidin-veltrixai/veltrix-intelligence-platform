#!/usr/bin/env bash
set -euo pipefail

readonly CERTIFIED_SHA="4e97591845a93037d6e54b0237bcb3208d1b2696"

usage() {
  echo "usage: deploy.sh ENV CLUSTER SUBNET_IDS_CSV SECURITY_GROUP DB_IDENTIFIER API_IMAGE WEB_IMAGE APP_URL API_URL" >&2
  exit 64
}

[[ $# -eq 9 ]] || usage

readonly environment="$1"
readonly cluster="$2"
readonly subnet_ids_csv="$3"
readonly security_group="$4"
readonly db_identifier="$5"
readonly api_image="$6"
readonly web_image="$7"
readonly app_url="$8"
readonly api_url="$9"

[[ "${RELEASE_SHA:-}" == "$CERTIFIED_SHA" ]] || {
  echo "Refusing deployment: RELEASE_SHA must equal certified SHA $CERTIFIED_SHA" >&2
  exit 65
}

[[ "$api_image" == *@sha256:* && "$web_image" == *@sha256:* ]] || {
  echo "Refusing deployment: API and web images must use immutable digest references" >&2
  exit 65
}

command -v aws >/dev/null
command -v jq >/dev/null

register_family() {
  local family="$1"
  local container="$2"
  local image="$3"
  local source_file target_file
  source_file="$(mktemp)"
  target_file="$(mktemp)"

  aws ecs describe-task-definition \
    --task-definition "$family" \
    --query taskDefinition > "$source_file"

  jq --arg container "$container" --arg image "$image" '
    del(
      .taskDefinitionArn,
      .revision,
      .status,
      .requiresAttributes,
      .compatibilities,
      .registeredAt,
      .registeredBy
    )
    | .containerDefinitions |= map(
        if .name == $container then .image = $image else . end
      )
  ' "$source_file" > "$target_file"

  aws ecs register-task-definition \
    --cli-input-json "file://$target_file" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text

  rm -f "$source_file" "$target_file"
}

snapshot_id=""
if [[ "$environment" == "production" ]]; then
  snapshot_id="${db_identifier}-predeploy-$(date -u +%Y%m%d%H%M%S)"
  aws rds create-db-snapshot \
    --db-instance-identifier "$db_identifier" \
    --db-snapshot-identifier "$snapshot_id" >/dev/null
  aws rds wait db-snapshot-available --db-snapshot-identifier "$snapshot_id"
fi

migration_task="$(register_family "${cluster}-migration" migration "$api_image")"

IFS=',' read -r -a subnets <<< "$subnet_ids_csv"
subnet_json="$(printf '%s\n' "${subnets[@]}" | jq -R . | jq -sc .)"
network_json="$(jq -nc \
  --argjson subnets "$subnet_json" \
  --arg sg "$security_group" \
  '{awsvpcConfiguration:{subnets:$subnets,securityGroups:[$sg],assignPublicIp:"DISABLED"}}')"

migration_run="$(aws ecs run-task \
  --cluster "$cluster" \
  --task-definition "$migration_task" \
  --launch-type FARGATE \
  --network-configuration "$network_json" \
  --started-by "vip-release-${CERTIFIED_SHA:0:12}" \
  --query 'tasks[0].taskArn' \
  --output text)"

[[ -n "$migration_run" && "$migration_run" != "None" ]] || {
  echo "Migration task failed to start" >&2
  exit 1
}

aws ecs wait tasks-stopped --cluster "$cluster" --tasks "$migration_run"
# JMESPath backticks are literals for the AWS CLI.
# shellcheck disable=SC2016
migration_exit="$(aws ecs describe-tasks \
  --cluster "$cluster" \
  --tasks "$migration_run" \
  --query 'tasks[0].containers[?name==`migration`].exitCode | [0]' \
  --output text)"

[[ "$migration_exit" == "0" ]] || {
  aws ecs describe-tasks --cluster "$cluster" --tasks "$migration_run" >&2
  echo "Migration failed; services were not changed" >&2
  exit 1
}

declare -A task_definitions
declare -A previous_task_definitions
for service in dashboard-worker pipeline-worker api web scheduler; do
  previous_task_definitions[$service]="$(aws ecs describe-services \
    --cluster "$cluster" \
    --services "$service" \
    --query 'services[0].taskDefinition' \
    --output text)"
  [[ "${previous_task_definitions[$service]}" == arn:* ]] || {
    echo "Unable to capture previous task definition for $service" >&2
    exit 1
  }
done

task_definitions[api]="$(register_family "${cluster}-api" api "$api_image")"
task_definitions[web]="$(register_family "${cluster}-web" web "$web_image")"
task_definitions[dashboard-worker]="$(register_family "${cluster}-dashboard-worker" dashboard-worker "$api_image")"
task_definitions[pipeline-worker]="$(register_family "${cluster}-pipeline-worker" pipeline-worker "$api_image")"
task_definitions[scheduler]="$(register_family "${cluster}-scheduler" scheduler "$api_image")"

deployment_started=false
rollback_previous() {
  local failed_status=$?
  trap - ERR
  if [[ "$deployment_started" == true ]]; then
    echo "Deployment failed; restoring all previous ECS task definitions" >&2
    for rollback_service in dashboard-worker pipeline-worker api web scheduler; do
      aws ecs update-service \
        --cluster "$cluster" \
        --service "$rollback_service" \
        --task-definition "${previous_task_definitions[$rollback_service]}" \
        --force-new-deployment >/dev/null || true
    done
    aws ecs wait services-stable \
      --cluster "$cluster" \
      --services api web dashboard-worker pipeline-worker scheduler || true
  fi
  exit "$failed_status"
}
trap rollback_previous ERR

for service in dashboard-worker pipeline-worker api web scheduler; do
  deployment_started=true
  aws ecs update-service \
    --cluster "$cluster" \
    --service "$service" \
    --task-definition "${task_definitions[$service]}" \
    --force-new-deployment >/dev/null
done

aws ecs wait services-stable \
  --cluster "$cluster" \
  --services api web dashboard-worker pipeline-worker scheduler

"$(dirname "$0")/smoke.sh" "$environment" "$app_url" "$api_url"
trap - ERR

jq -n \
  --arg environment "$environment" \
  --arg release_sha "$CERTIFIED_SHA" \
  --arg api_image "$api_image" \
  --arg web_image "$web_image" \
  --arg migration_task "$migration_run" \
  --arg snapshot "$snapshot_id" \
  --arg deployed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{environment:$environment,release_sha:$release_sha,api_image:$api_image,web_image:$web_image,migration_task:$migration_task,predeploy_snapshot:$snapshot,deployed_at:$deployed_at}' \
  > deployment-manifest.json
