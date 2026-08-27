# Operations runbook

This runbook defines provider-neutral operational checks. Provider-specific AWS commands remain in `PRODUCTION_RUNBOOK.md`; any hard-coded release SHA in historical documents must be revalidated before use.

## Routine health checks

1. Confirm the deployed image digests and `/api/v1/version` release identity.
2. Check frontend `/healthz`, API `/health`, and API `/ready`.
3. Verify PostgreSQL availability, current Alembic head, connection pool pressure, storage, and backup age.
4. Verify Redis availability, memory/evictions, latency, and authentication/TLS.
5. Verify fresh generic-worker, pipeline-worker, and scheduler heartbeats.
6. Review queue depth, failed/dead-letter jobs, pipeline/export failures, and schedule lag.
7. Check persistent storage capacity and malware-scanner health.
8. Check SMTP acceptance, bounce/complaint signals, and delivery failures when email is enabled.
9. Review authentication/authorization anomalies and audit-event ingestion.

## Release

Follow `docs/deployment/PRODUCTION_DEPLOYMENT.md`. Record the immutable SHA, image digests, Alembic head, infrastructure plan/application identifier, smoke results, and rollback task/image references. Never deploy from a dirty working tree or mutable image tag.

## Service restart

Restart only the affected service with the same immutable image/configuration. Confirm leases and long-running work before restarting a worker. Keep exactly one logical scheduler role. Verify readiness and heartbeat recovery afterward.

## Failed pipeline or export

Capture the tenant-safe resource/job/run ID, correlation ID, state, attempt count, lease owner, error code, and worker version. Check dependencies and storage before retrying through supported APIs. Do not edit job or run rows manually and do not expose payloads in tickets.

## Security incident

Restrict traffic, freeze deployments, preserve logs/audit data, revoke affected sessions/credentials, rotate secrets using an approved overlap plan, and restore only from verified recovery points. Do not delete evidence. Follow `SECURITY.md` for reporting.

## Backups and restore

See `docs/deployment/BACKUP_AND_RESTORE.md`. Restore drills must use isolated resources and report counts/metadata rather than raw customer data.
