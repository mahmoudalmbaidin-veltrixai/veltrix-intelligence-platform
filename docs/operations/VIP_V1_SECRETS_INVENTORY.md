# VIP V1 Secrets Inventory

Authoritative release: `4e97591845a93037d6e54b0237bcb3208d1b2696`

```text
DO NOT COMMIT
DO NOT EMBED IN IMAGE
DO NOT EXPOSE TO FRONTEND
```

Inject server secrets at task start from AWS Secrets Manager encrypted with customer-managed KMS keys, or an approved equivalent. Restrict read access to the ECS execution role and break-glass operators. Never place secret values in GitHub variables, Docker build arguments/labels, Terraform variable files, plan output, ECS plaintext `environment`, CloudWatch logs, tickets, chat, or generated documentation. Terraform remote state is sensitive and must be encrypted, versioned, locked, access-logged, and least-privilege.

## Inventory

| Secret | Consumer | Storage recommendation | Rotation requirement |
| --- | --- | --- | --- |
| RDS master/application password within `DATABASE_URL` | API, dashboard worker, pipeline worker, scheduler, migration | RDS managed master secret; construct/store the complete `DATABASE_URL` as a KMS-encrypted runtime secret JSON key | Managed rotation with coordinated URL secret update and rolling redeploy of all consumers; verify `/ready` before retiring old access |
| Redis AUTH token within `REDIS_URL` | API, both workers, scheduler, migration | KMS-encrypted runtime secret JSON key using `rediss://`; keep endpoint and token out of logs | Use provider-supported dual-token transition where available; deploy all consumers, verify queues, then remove old token |
| `CONNECTION_ENCRYPTION_KEY` | API and workers that read/write connector credentials | KMS-encrypted runtime secret; value must be URL-safe base64 of exactly 32 random bytes | **Do not rotate in place.** Frozen V1 loads one active key/version; changing it can strand existing ciphertext. Rotation requires controlled re-encryption/new certified capability or incident recovery plan |
| `DASHBOARD_DOWNLOAD_SIGNING_KEY` | API and dashboard worker | KMS-encrypted runtime secret, independent random value | Rotate on schedule/incident through a coordinated redeploy; old outstanding short-lived URLs become invalid after rotation |
| `PIPELINE_DOWNLOAD_SIGNING_KEY` | API and pipeline worker | KMS-encrypted runtime secret, independent random value | Same coordinated rotation; account for configured token TTL |
| `FILE_DOWNLOAD_SIGNING_KEY` | API and dashboard worker | KMS-encrypted runtime secret, independent random value | Same coordinated rotation; account for configured token TTL |
| `METRICS_BEARER_TOKEN` | API and approved metrics collector | KMS-encrypted runtime secret; provide collector read/access separately | Rotate on schedule/incident with overlap if the collector supports it; verify scrape before retiring old token |
| `DASHBOARD_SMTP_USERNAME` | API/dashboard worker | Separate KMS-encrypted SMTP secret in workload region | Rotate using provider process, deploy consumers, send tagged test, then revoke old credential |
| `DASHBOARD_SMTP_PASSWORD` | API/dashboard worker | Same SMTP secret; never store in Terraform variables or state as plaintext | Rotate with username/provider credential and verify delivery/bounce events |
| First Super Admin bootstrap password | One-off bootstrap task and approved password manager | Short-lived bootstrap secret with narrowly scoped task access; never an ECS command argument | Delete/disable immediately after bootstrap; admin changes password immediately and revokes other sessions |
| Customer connector credentials | Application-managed encrypted database records | Enter only through the supported application interface; AES-256-GCM ciphertext in PostgreSQL under `CONNECTION_ENCRYPTION_KEY` | Rotate per source-system policy through supported connection update; test access and preserve audit trail |
| RDS/EFS/S3/KMS/Secrets task authorization | ECS task roles, not an application secret value | IAM roles, EFS access point, bucket/key policies; no static AWS access keys | Review quarterly and on role/incident change; prefer short-lived role credentials |
| Terraform backend credentials | Infrastructure automation only | GitHub OIDC -> tightly scoped deploy role; remote encrypted/locked backend | No long-lived access keys; rotate/revoke role trust and sessions on incident/change |

## Important absences

- There is no application `AUTH_SECRET` or static session-signing environment variable in the frozen release. Access/refresh session tokens are generated randomly and persisted as protected session records; do not invent an auth secret setting.
- EFS storage uses task-role/IAM authorization and transport encryption. The application has no S3 storage credential variables in V1 because the certified provider is filesystem-based.
- `CONNECTION_ENCRYPTION_KEY_VERSION` is a non-secret label; it does not replace the encryption key.
- Database, Redis, and SMTP hostnames are operationally sensitive but only the credential-bearing URLs/passwords are injected through the secret channel in current IaC.

## Secret JSON contracts used by current IaC

Runtime secret `/<project>/<environment>/runtime` contains these exact keys:

```text
DATABASE_URL
REDIS_URL
CONNECTION_ENCRYPTION_KEY
DASHBOARD_DOWNLOAD_SIGNING_KEY
PIPELINE_DOWNLOAD_SIGNING_KEY
FILE_DOWNLOAD_SIGNING_KEY
METRICS_BEARER_TOKEN
```

The separate SMTP secret contains:

```text
DASHBOARD_SMTP_USERNAME
DASHBOARD_SMTP_PASSWORD
```

Staging and production must use different secret objects, keys, credentials, databases, Redis groups, and encryption values. Do not clone production secret values into staging.

## Rotation verification

For every rotation, record owner/change ticket, secret version IDs (not values), affected task definitions, deployment time, health/readiness result, authenticated smoke result, old-version retirement, and rollback window. Rotation is incomplete until every consumer is running the intended secret version and no old task remains.

