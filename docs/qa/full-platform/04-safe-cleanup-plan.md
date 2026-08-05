# Safe Cleanup Plan

The strategy was isolation rather than cleanup. Only three malformed partial-seed assignments were eligible for immediate removal because their exact IDs and creation cause were known.

Removal order: group-role assignment IDs, group-membership ID, then verification of intended assignments. Selection was by immutable UUID, never name alone. The API was used so authorization and audit behavior remained active. Rollback was restoration from the preflight PostgreSQL custom dump or cluster SQL dump; a QA-only re-seed can also recreate intended assignments.

Retained UAT cleanup must be performed later from `19-qa-data-cleanup-manifest.md` and the local authoritative manifest. Dependency order is: revoke sessions/tokens; ACL/role/group assignments; shares/schedules/runs/exports/jobs/files; resources; workspace memberships/workspaces; organization memberships; QA users not shared elsewhere; organizations. Storage objects must be deleted only after matching DB ownership and checksum. Redis keys must be selected by exact job/session IDs. Audit history is retained.

Verification after any cleanup: compare protected counts/IDs, check orphan FKs, run Alembic current/heads, health/readiness, worker heartbeats, tenant-isolation integration tests, and storage-reference reconciliation.
