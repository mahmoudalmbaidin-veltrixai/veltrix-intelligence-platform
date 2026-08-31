#!/bin/sh
set -eu

# Railway volumes are mounted as root and cannot be shared across services.
# The demo therefore runs the existing API and worker entry points in one
# container, then drops every long-running process to the image's vip user.
storage_roots="
${DASHBOARD_ARTIFACT_ROOT:-/data/vip-artifacts}
${DASHBOARD_EMAIL_OUTBOX_ROOT:-/data/vip-email-outbox}
${PIPELINE_ARTIFACT_ROOT:-/data/vip-pipeline-artifacts}
${FILE_STORAGE_ROOT:-/data/vip-files}
"

for root in $storage_roots; do
  mkdir -p "$root"
done

run_process() {
  if [ "$(id -u)" -eq 0 ]; then
    exec_user="vip"
    for root in $storage_roots; do
      chown -R "$exec_user:$exec_user" "$root"
    done
    su-exec "$exec_user" "$@" &
  else
    "$@" &
  fi
  started_pid=$!
}

stop_processes() {
  trap - EXIT INT TERM HUP
  for pid in ${api_pid:-} ${job_worker_pid:-} ${pipeline_worker_pid:-}; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  for pid in ${api_pid:-} ${job_worker_pid:-} ${pipeline_worker_pid:-}; do
    wait "$pid" 2>/dev/null || true
  done
}

trap stop_processes EXIT INT TERM HUP

run_process python -m vip_api.jobs.worker
job_worker_pid=$started_pid
run_process python -m vip_api.pipelines.worker
pipeline_worker_pid=$started_pid
run_process uvicorn vip_api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log
api_pid=$started_pid

# These are all required demo processes. If any one exits, stop the group so
# Railway restarts a coherent service instead of serving a partially working UI.
set +e
wait -n "$api_pid" "$job_worker_pid" "$pipeline_worker_pid"
child_status=$?
set -e
if [ "$child_status" -eq 0 ]; then
  child_status=1
fi
stop_processes
exit "$child_status"
