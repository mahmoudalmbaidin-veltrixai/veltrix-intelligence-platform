# Backup and restore

## What must be protected

- PostgreSQL, including Alembic state and tenant/application records;
- the shared filesystem roots for uploads, dashboard artifacts, pipeline artifacts, and any retained outbox files;
- secret-manager configuration and encryption-key version metadata;
- immutable image digests, release SHA, infrastructure state, and deployment manifests.

Redis is coordination/cache infrastructure, not the only system of record for durable jobs. Its backup policy should still match the chosen managed service and recovery objectives.

## Minimum policy

- automated encrypted database backups with point-in-time recovery;
- periodic snapshots before schema or infrastructure changes;
- versioned/encrypted filesystem backups;
- retention and deletion policies approved for customer and audit requirements;
- backup monitoring and restore tests;
- off-account/off-environment protection where required.

## Restore drill

1. Select and record a recovery point without copying customer payloads into evidence.
2. Restore PostgreSQL and filesystem data into isolated resources, never over the source.
3. Inject temporary recovery secrets.
4. Run `alembic current` and compare with `alembic heads`.
5. Start isolated API/workers without public ingress.
6. Verify tenant-scoped entity counts, authentication, representative dataset/dashboard metadata, and artifact integrity.
7. Record RPO/RTO, checks, issues, and cleanup.
8. Destroy temporary resources after approval.

Never store database dumps or recovered customer data in this repository.
