# Monitoring

## Required signals

| Area | Minimum signals |
| --- | --- |
| Frontend | health check, 4xx/5xx, latency, CSP violations where collected |
| API | readiness, request rate/latency/errors, process restarts, dependency failures |
| PostgreSQL | CPU, storage, connections, locks, slow queries, backup/PITR age |
| Redis | availability, memory, evictions, latency, connection errors |
| Workers | replica count, heartbeat age, queue depth, retries, dead letters, lease recovery |
| Scheduler | singleton count, heartbeat age, due-item lag, dispatch errors |
| Storage | capacity, latency, mount availability, backup age, integrity errors |
| Email | accepted/rejected sends, bounce/complaint rate, provider errors |
| Security | login failures/lockouts, authorization denials, audit gaps, secret-access anomalies |

The API metrics endpoint must be protected with `METRICS_BEARER_TOKEN` and should not be exposed directly to the public internet. Centralized logs must redact cookies, authorization headers, connector secrets, reset/invitation tokens, signed download URLs, and customer payloads.

## Alerting principles

- Alert on user impact and breached operating thresholds, not every transient retry.
- Treat missing worker/scheduler heartbeats, database/Redis unavailability, storage exhaustion, failed backups, tenant-isolation signals, and malware-scanner failure as actionable.
- Route alerts to an owned on-call channel and document escalation outside Git when it contains personal contact details.

The AWS implementation defines CloudWatch log groups, dashboards/alarms, and service-count checks. Validate thresholds against the actual workload before production.
