# VIP V1 Rollback and Recovery Runbook

Frozen release: `4e97591845a93037d6e54b0237bcb3208d1b2696`  
Expected Alembic head: `20260808_0025`

Use an approved operator role and change/incident record. Capture current and prior image digests, ECS task-definition ARNs, database checkpoint, Alembic head, symptoms, timestamps, and decision owner before mutation. Never paste secrets into commands, logs, tickets, or chat.

## Principles

- Application rollback changes ECS task definitions/images; it does not automatically change the database.
- Prefer a forward fix with a newly certified release when the database has changed.
- **Do not automatically run `alembic downgrade`.** Use it only when the exact migration has a reviewed, data-safe, rehearsed downgrade and an approved checkpoint exists.
- Never restore over the source RDS/EFS resource. Restore to new resources, validate in isolation, then cut over.
- If a fix requires application source change, stop: create a new RC/SHA and recertify.
- Keep the singleton scheduler at one logical instance throughout rollback.

## Decision matrix

| Condition | Action |
| --- | --- |
| Migration task fails before service update | Do not update services. Preserve logs/checkpoint, diagnose, and retry only after approval. No application rollback is needed. |
| New tasks fail but schema remains backward-compatible | Restore all prior task definitions/digests; keep current schema; run health/version/smoke. |
| New schema is not safe for prior application | Disable mutation/traffic, restore pre-deploy RDS snapshot to a new private instance, validate an isolated recovery deployment, then approved cutover. |
| Bad data written after deployment | Freeze writes; incident commander chooses forward repair or point-in-time restore based on data-loss window. Never improvise SQL cleanup. |
| Redis loss/corruption | Restore snapshot or create a new encrypted group, update secret, redeploy all consumers, reconcile PostgreSQL-backed queues. |
| EFS loss/corruption | Stop mutations, restore backup to a new filesystem/access point, validate metadata/artifact consistency, update task definitions, then cut over. |
| Secret compromise | Restrict traffic, rotate the affected secret using its supported procedure, redeploy consumers, verify, revoke old version, preserve evidence. Connector key compromise requires a new certified re-encryption capability/incident plan. |

## 1. Stabilize and preserve evidence

1. Declare incident/change owner and stop concurrent deployment workflows.
2. If continued writes risk damage, change ALB listeners to an approved fixed 503 maintenance response before reducing API desired count. Do not expose a partially writable stack.
3. For security incidents, apply the approved emergency WAF restriction, preserve CloudTrail/WAF/ALB/application logs, and revoke affected sessions/credentials through supported procedures.
4. Record:

   - current/prior ECS task-definition ARNs and image digests for API, web, dashboard worker, pipeline worker, scheduler;
   - deployment manifest and release SHA returned by `/api/v1/version`;
   - current Alembic head and migration task ARN/exit/log stream;
   - RDS snapshot/PITR time and EFS recovery point;
   - active alarms, request/error timestamps, safe correlation IDs, queue/lease state.

## 2. Application service rollback

Use the exact prior task definitions recorded in the last successful deployment manifest/ECS history:

```bash
infra/aws/scripts/rollback.sh vip-<environment> \
  api=vip-<environment>-api:PREVIOUS \
  web=vip-<environment>-web:PREVIOUS \
  dashboard-worker=vip-<environment>-dashboard-worker:PREVIOUS \
  pipeline-worker=vip-<environment>-pipeline-worker:PREVIOUS \
  scheduler=vip-<environment>-scheduler:PREVIOUS
```

The script updates services and waits for stability; it executes no Alembic downgrade. Roll back the full compatible service set, not an arbitrary API/worker mixture. Confirm scheduler desired/running count stays exactly 1 and scheduling remains disabled elsewhere.

After stability:

- verify web `/healthz`, API `/health`, API `/ready`, and `/api/v1/version`;
- verify each running task uses the intended prior digest;
- verify worker/scheduler heartbeats and queues;
- run `infra/aws/scripts/smoke.sh` and the risk-relevant authenticated smoke flows;
- monitor 5xx, latency, RDS, Redis, EFS, worker failures, and duplicate scheduled execution.

If the prior application cannot safely operate with the current schema, keep traffic disabled and proceed to database recovery.

## 3. Database migration/data recovery

### Failed migration before promotion

The deployment script updates no service when the migration task exits non-zero. Preserve the failed task/logs and pre-deploy snapshot. Do not edit `alembic_version` manually and do not let API replicas retry migration. Determine whether the failure is environmental (network, secret, capacity) or an application migration defect. An application defect requires a new certified RC.

### Forward-fix default

For a successfully applied migration, keep schema at `20260808_0025` and deploy a compatible newly certified fix. This preserves post-migration writes and avoids unreviewed reverse transformations.

### Point-in-time/snapshot restore

Use when schema incompatibility or bad data makes forward operation unsafe:

1. Select the pre-deploy snapshot or approved PITR timestamp and calculate expected data-loss window.
2. Restore to a **new** private RDS identifier/security group; preserve source DB unchanged/read-only where practical.
3. Create a temporary recovery runtime secret pointing only to the restored DB.
4. Start an isolated migration/current-head verification task with no public listener. Do not mutate beyond the approved compatibility command.
5. Start isolated API/workers against restored RDS and non-production/recovery Redis/EFS as appropriate.
6. Verify Alembic head, non-sensitive entity counts, tenant isolation, critical workflows, audit continuity, and file/DB metadata consistency.
7. Obtain incident/change approval, update runtime secret/task definitions, and cut over services.
8. Run full health/version/smoke and monitor. Retain old DB until the approved rollback window ends.

Record recovery point, requested/actual restore time, achieved RPO/RTO, row/entity counts without customer payloads, checks, approvers, cutover, and cleanup.

## 4. EFS recovery

1. Stop API/workers that can write affected paths or place the system in maintenance.
2. Restore the selected AWS Backup recovery point to a new EFS filesystem.
3. Create a new access point with the expected UID/GID and private mount targets/security group.
4. Mount it only to an isolated diagnostic task and verify expected tenant-scoped keys under:

   - `/data/vip-files`
   - `/data/vip-pipeline-artifacts`
   - `/data/vip-artifacts`

5. Compare database metadata to file presence/size/checksum where available without opening/logging customer contents.
6. Update task definitions to the new filesystem/access point, deploy a compatible full service set, and run upload/pipeline/PDF/PNG durability smoke.
7. Keep the prior filesystem read-only until approval; never overwrite it during restore.

## 5. Redis recovery

PostgreSQL is authoritative for jobs, leases, schedules, and business records; Redis contains queue acceleration, caches, ephemeral events, rate limits, and token-consumption state.

1. Restore an approved snapshot or create a new private encrypted TLS/auth replication group.
2. Write a new `REDIS_URL` secret version without exposing it.
3. Redeploy API, both workers, scheduler, and migration task definition consumers.
4. Verify `/ready`, Redis metrics, no eviction, and worker heartbeats.
5. Reconcile durable PostgreSQL jobs through supported application behavior; do not hand-edit queue/job tables.
6. Expect ephemeral event history/cache loss and outstanding token-consumption implications; document customer impact.

## 6. Secret-specific recovery

- Database/Redis/SMTP: rotate provider credential, update secret, redeploy all consumers, verify, then revoke old credential.
- Download/metrics signing secrets: coordinate redeploy; existing signed URLs/tokens may become invalid for their remaining TTL.
- `CONNECTION_ENCRYPTION_KEY`: frozen V1 supports one active key. Do not replace it and strand ciphertext. Treat compromise as a security incident requiring controlled recovery/re-encryption and a new certified application capability if needed.
- Bootstrap credential: delete immediately after first-admin creation. If exposure is suspected, reset the admin password and revoke all sessions.

## 7. Exit criteria

- [ ] Intended image digests/task definitions are running and stable.
- [ ] Runtime version is unambiguous and recorded.
- [ ] Alembic head is compatible and recorded; no unapproved downgrade/manual version edit occurred.
- [ ] Web/API health and readiness pass.
- [ ] Workers and singleton scheduler are healthy; no unexplained stale leases/duplicate jobs.
- [ ] RDS, Redis, EFS, SMTP, logs, metrics, backups, and alerts are healthy.
- [ ] Relevant authenticated smoke flows pass.
- [ ] Security/secret exposure is contained and evidence preserved.
- [ ] Achieved RPO/RTO and customer impact are recorded.
- [ ] Incident/change owner and application/infrastructure approvers close the recovery.

