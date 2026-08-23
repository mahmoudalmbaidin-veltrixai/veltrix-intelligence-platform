# VIP Local PostgreSQL Restore Drill

> Historical local drill evidence only. It does not satisfy the required managed staging RDS/EFS restore test for production acceptance.

Date: 2026-08-16  
Scope: local QA data only  
Certified application SHA: `869e7c092bd887c636cad4a35ec1fb622de8f181`

## Result

`LOCAL RESTORE DRILL = PASS`

`AWS MANAGED RESTORE = NOT EXECUTED`

The active local `vip` PostgreSQL database was dumped in custom format, restored into the isolated temporary database `vip_restore_drill_20260816`, and validated with the production API image. The source database was not changed.

## Evidence

| Check | Result |
| --- | --- |
| `pg_dump` custom-format backup | PASS |
| Restore into a new database | PASS |
| Alembic current | `20260808_0024` |
| Public tables | 162 |
| Users present | 100 |
| Datasets present | 424 |
| Dashboards present | 809 |
| Production image `/health` | PASS |
| Production image `/ready` (database and Redis) | PASS |
| Runtime revision | Certified SHA matched |
| Temporary API container removed | PASS |
| Temporary database removed | PASS; post-cleanup database count was 0 |
| Temporary dump removed | PASS |

Counts are non-sensitive integrity indicators from the local QA dataset; no raw records or credentials were recorded.

## Limitation

This drill validates the certified schema, PostgreSQL dump/restore mechanics, application compatibility, and cleanup. It does not validate RDS PITR, AWS Backup recovery points, KMS permissions, cross-region copy, RDS networking, or an AWS-measured RPO/RTO. Those checks remain mandatory in staging before production approval.
