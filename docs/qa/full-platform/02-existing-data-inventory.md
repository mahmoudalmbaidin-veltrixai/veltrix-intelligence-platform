# Existing Data Inventory

Inventory was completed before cleanup. Unknown and pre-existing records were protected. The baseline included 15 users, 13 organizations, 22 workspaces, 8 roles (7 system, 1 custom), 126 permissions, 405 sessions, 111 connections, 86 datasets, 164 pipelines, 188 dashboards, 98 files, 33 jobs, and 10,711 audit events.

After isolated QA activity the primary counts were: users 53, organizations 17, workspaces 30, roles 21, permissions 126, sessions 549, connections 117, datasets 88, pipelines 172, dashboards 200, files 101, jobs 33, audit events 11,391, groups 4, ACL entries 5, feature flags 21, entitlements 21, semantic models 7, semantic metrics 14, KPIs 4, dashboard exports 45, and delivery schedules 7.

The public schema contains platform tables for authentication, tenancy, RBAC, invitations, connections/secrets/types, datasets/fields/quality/lineage, semantics/glossary, pipeline versions/graph/runs/logs/results, dashboard pages/widgets/versions/shares/exports/delivery, files/scans/versions/tokens, jobs/attempts/logs/results/dead-letter, quotas/entitlements/flags, audit, and worker heartbeats. Numerous timestamped `b85_*`, `vip_b5_*`, and certification tables pre-dated this run; their ownership was not provable, so they are classified **unknown/protected**.

Storage inventory before testing: dashboard artifacts 35 files, email outbox 8, pipeline artifacts 70, file storage 102, Redis volume 4, and MySQL volume 173. Redis keyspaces contained DB0=34, DB1=2, DB13=1, DB14=7, DB15=40 keys. All were snapshotted and preserved.

Classification and cleanup policy:

| Category | Classification | References | Cleanup |
|---|---|---|---|
| Alembic, roles, permissions, flags, entitlements, type/catalog tables | Required system/configuration | Broad FK/application use | Never remove |
| Pre-existing users/orgs/workspaces/resources/audit/storage | Legitimate or unknown | Tenant/resource graphs | Preserve |
| Timestamped legacy B5/B8.5 tables | Unknown/test-like | Possible dataset/pipeline references | Preserve pending ownership proof |
| Two `QA_Enterprise_*` tenants and their IDs | This run's QA data | Fully manifest-scoped | Retain for UAT; later ID-scoped cleanup |
| New `E2E Client *` organizations | Browser-created synthetic data | Organization graph | Cleanup candidates by exact ID only |
| Partial-seed bad assignments | Proven synthetic | Exact assignment IDs | Removed via scoped API |
