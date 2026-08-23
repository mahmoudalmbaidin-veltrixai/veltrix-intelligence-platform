# VIP V1 Production Runbook

> Supporting operations reference. The authoritative release invariants and rollback procedure are in `VIP_V1_INFRASTRUCTURE_HANDOFF.md` and `VIP_V1_ROLLBACK_RUNBOOK.md`.

All examples assume an approved operator role, AWS CLI v2, `jq`, the correct account/region, and a recorded change ticket. Never paste secret values into a terminal transcript, ticket, or chat.

## Release invariants

- Certified application SHA: `4e97591845a93037d6e54b0237bcb3208d1b2696`.
- Expected Alembic head: `20260808_0025`.
- Production images must use ECR digest references and OCI revision labels.
- Application source trees must have zero diff from the certified SHA. Infrastructure commits may change only infrastructure, CI/CD, and operations documentation.
- Production deploys originate from the protected GitHub `production` environment with concurrency enabled and a human approval.

## Deploy

1. Confirm CI is green: frontend static/unit/build, browser, backend static/unit/integration, Alembic check, dependency scans, image scans, secret/IaC scan, Terraform validate.
2. Confirm the change input is the certified SHA and both image references resolve to digests.
3. Confirm RDS, Redis, backup vault, alert topic, SMTP delivery, and `/ready` are healthy.
4. Trigger `Deploy certified VIP release` for staging.
5. The pipeline creates a pre-deploy RDS snapshot (production), runs exactly one migration task, verifies head, updates workers/API/web, updates the singleton scheduler stop-before-start, waits for stable services, and executes infrastructure smoke tests.
6. Complete the authenticated staging smoke matrix and attach results.
7. Obtain production approval and repeat for production.
8. Retain `deployment-manifest.json` for 365 days and record task-definition revisions/image digests in the ticket.

Failure before migration success leaves all services unchanged. During promotion, the deployment script records every prior task definition; an unstable rollout or failed final smoke restores all services and waits for the prior set to stabilize. ECS circuit breakers provide an additional service-level rollback. The successful manifest is not written after a failed rollout. Investigate before retrying; do not bypass a failed gate.

## Run migrations manually only in an incident-approved change

Do not run migrations from an API replica. Use the migration task family in the same private subnets/security group as ECS. Ensure no deployment workflow is active, take a manual RDS snapshot, run one task, wait for `STOPPED`, verify exit code 0, and confirm the log contains current head `20260808_0025`.

The standard command is embedded in the task definition:

```text
alembic upgrade head
alembic current -> 20260808_0025
seed-governance
seed-connection-types
```

Seeds are deterministic baseline definitions. Never run demo/QA seed commands in production.

## Roll back application services

Identify the last known-good task-definition ARN for every changed service from the preceding deployment manifest/ECS history. Run:

```bash
infra/aws/scripts/rollback.sh vip-production \
  api=vip-production-api:PREVIOUS \
  web=vip-production-web:PREVIOUS \
  dashboard-worker=vip-production-dashboard-worker:PREVIOUS \
  pipeline-worker=vip-production-pipeline-worker:PREVIOUS \
  scheduler=vip-production-scheduler:PREVIOUS
```

Then run the infrastructure and authenticated customer workflow smoke tests. This changes application containers only. It does not downgrade the database.

### Database migration rollback policy

- Default: forward-fix with a newly certified release.
- Alembic downgrade is prohibited unless the exact migration has a reviewed, rehearsed, data-safe downgrade and an approved snapshot exists.
- If the new schema makes the old application unsafe, keep traffic disabled, restore the pre-deploy snapshot to a new RDS instance, point a recovery deployment at it, validate, then cut over. Do not overwrite the original database.

## Maintenance / emergency access disable

For planned high-risk changes, first set API desired count to zero only after the ALB listener has been changed to a fixed 503 maintenance response. Keep the web tier available only if it clearly cannot mutate data; otherwise return 503 for both hosts. Preserve the existing listener/task definition in the change record so it can be restored.

For a security incident, associate an emergency WAF ACL that blocks all traffic except approved responder CIDRs, revoke sessions if credentials may be compromised, and preserve logs. Do not delete evidence.

## Restart a service

Use a forced ECS deployment of the current task definition and wait for stability. Restart only the affected service. The scheduler has desired count exactly 1 and stop-before-start deployment settings. Workers recover expired leases after a crash.

## Check health, version, and logs

```bash
curl -fsS https://api.<domain>/health
curl -fsS https://api.<domain>/ready
curl -fsS https://api.<domain>/api/v1/version
aws ecs describe-services --cluster vip-production --services api web dashboard-worker pipeline-worker scheduler
aws logs tail /vip/production/api --since 30m --follow
aws logs tail /vip/production/dashboard-worker --since 30m --follow
aws logs tail /vip/production/pipeline-worker --since 30m --follow
aws logs tail /vip/production/scheduler --since 30m --follow
```

The version response must identify the certified SHA and `production`. Never request or log `/metrics` with its bearer token through a shared terminal session.

## Check queues and workers

- Review CloudWatch worker error alarms and ECS running task count.
- Inspect the protected aggregate metrics endpoint from an approved private diagnostic task: queue depth, stale leases, active/stale workers, job failures/dead letters, pipeline/export/delivery states.
- A stale heartbeat is older than three configured heartbeat periods. Restart the task only after determining whether a long-running operation still owns a live lease.
- Do not edit queue/job rows manually. Use supported retry/cancel operations and preserve audit history.

## Failed export

1. Capture export/job ID, tenant context, safe error code, attempt count, worker task ID, and correlation ID.
2. Check dashboard worker logs and EFS availability/space/latency.
3. For email delivery, check SMTP response, SES bounce/complaint dashboards, sender verification, and recipient status without exposing content.
4. Retry through the supported API/UI if retryable and attempts remain.
5. If the artifact exists but delivery failed, do not regenerate until idempotency/duplicate delivery risk is assessed.

## Failed pipeline

1. Capture run ID, node, connector, safe error code, lease owner, and correlation ID.
2. Verify connector network/TLS access and current credential key version.
3. Check pipeline worker CPU/memory, EFS, database, and Redis.
4. Retry only through the supported API/UI. Expired leases are recovered automatically; do not clear them manually.

## Check PostgreSQL

- Use RDS/Performance Insights for CPU, storage, connections, locks, slow queries, replication/Multi-AZ status, backup age, and pending maintenance.
- Direct connections require a short-lived approved diagnostic task in the application subnets. RDS has no public route or public security-group ingress.
- Alert thresholds: CPU 80%, free storage below 20 GiB, connections above 100. Scale before sustained threshold breach.

## Check Redis

- Verify primary/replica health, replication lag, TLS, memory percentage, engine CPU, evictions, and snapshot age.
- Any eviction is actionable because policy is `noeviction` and queue/security keys must not disappear silently.
- If replacement is necessary, create/restore a new encrypted replication group, write a new runtime secret version, redeploy all consumers, then reconcile PostgreSQL-backed queued jobs.

## Back up and restore PostgreSQL

Normal protection is RDS automated PITR plus AWS Backup. For a manual pre-change checkpoint, create a uniquely named RDS snapshot and wait until available. Never restore over the source.

Restore drill:

1. Select a production-like staging recovery point and record its ARN/time/checksum metadata.
2. Restore to a new private recovery RDS identifier and new security group with no public access.
3. Create a temporary recovery runtime secret; never change the main staging secret.
4. Run a one-off migration/current-head verification against the recovery DB.
5. Start an isolated API task with no public listener and execute tenant-scoped checks for users, datasets, dashboard metadata, and Alembic head.
6. Record counts only—no raw customer payloads—in the drill evidence.
7. Destroy the temporary service/DB after approval and confirm deletion of the temporary secret. Retain the recovery point.

Required evidence: recovery point, start/end timestamps, RPO age, actual RTO, head, non-sensitive entity counts, smoke results, operators, issues, and cleanup confirmation.

## Restore EFS artifacts

Restore the AWS Backup recovery point to a new EFS filesystem. Attach a new access point to an isolated task, verify expected tenant-key prefixes and metadata/object consistency without opening customer files, then update task definitions during a maintenance window. Keep the old filesystem read-only until validation completes.

## Rotate secrets

### Signing and metrics secrets

Create a new Secrets Manager version, update task definitions, deploy all consumers, then mark the old version inactive after the maximum token/session overlap. Rotating download signing keys immediately invalidates outstanding short-lived URLs; schedule accordingly.

### Connector encryption key

The certified provider can load one environment key version. Rotation therefore requires a controlled re-encryption procedure/new certified application capability before changing the active key. Do not rotate the KMS/secret value and strand ciphertext encrypted under `prod-v1`. Treat key compromise as a security incident and create a new application RC if multi-key migration support is required.

### Database/Redis/SMTP

- RDS: use managed master password rotation, update the derived runtime `DATABASE_URL`, deploy all consumers, and verify readiness.
- Redis: create/rotate AUTH token using the supported dual-token transition where available, update runtime secret, deploy all consumers, then remove old token.
- SMTP: rotate in the external SMTP secret, deploy workers/API, send a tagged test, verify provider acceptance and bounce visibility, then revoke old credentials.

## Bootstrap the first Super Admin

Do not seed QA users. Run an isolated one-off API image task with the production runtime secret and no public ingress. Generate a unique password in an approved password manager, pipe one line to:

```text
python -m vip_api.cli create-user --email <admin> --display-name <name> --password-stdin
python -m vip_api.cli grant-platform-admin --email <admin>
```

Because ECS `run-task` does not provide interactive stdin, use an approved short-lived bootstrap secret and wrapper command that reads it directly, then delete that secret version immediately. Never put the password in command arguments, Terraform, GitHub outputs, CloudWatch logs, or ticket text. Have the administrator log in, change the password, enroll organizational controls if supported, and verify all bootstrap sessions are revoked. A second break-glass admin requires a separately approved procedure and credential.

## Audit retention

Application audit rows are stored in PostgreSQL and survive container restarts/backups. Keep `AUDIT_RETENTION_DAYS=365` initially, timestamps in UTC, and tenant/workspace context enabled. Quarterly, verify audit counts before/after restore and confirm retention/deletion jobs are authorized and logged.

## Escalation

Page immediately for suspected tenant leakage, secret exposure, authentication bypass, unrecoverable data loss, failed restore, public database/Redis exposure, missing TLS, or deterministic deployment failure. Freeze deployments and preserve evidence until incident command authorizes recovery.
