# V1 capabilities

This list describes implemented, API-backed V1 surfaces in live mode. Availability still depends on deployment configuration and role/entitlement/feature controls.

## Platform and governance

- users, sessions, password change/recovery, organizations, workspaces, invitations, and platform administration;
- system and custom roles, groups, resource-level access, tenant isolation, entitlements, feature flags, quotas, and audit events;
- jobs, files, event streams, in-app operational notifications, activity, and settings.

## Data and analytics

- PostgreSQL connection setup/testing with encrypted write-only credentials;
- CSV/XLSX upload, ingestion, metadata discovery, datasets, fields, preview, profiling, quality, versions, and lineage;
- visual pipeline graph authoring, validation, versions, runs, schedules, transformations, and protected artifacts;
- semantic models, dimensions, measures, metrics, glossary, validation, publish lifecycle, and bounded query execution;
- dashboard studio, multiple pages/widgets/filters, versioning, publish/viewer lifecycle, export jobs, PDF/PNG/JSON/CSV output, and scheduled delivery definitions.

## Operational delivery

- containerized API and frontend images;
- generic/dashboard and pipeline workers;
- recurring schedule ticks with singleton production topology;
- health, readiness, release version, and protected metrics endpoints;
- ClamAV/Defender scanning adapters, local/shared filesystem storage, SMTP or development file-outbox providers.

Connector catalog statuses are authoritative. Only entries marked available should be presented as ready; beta, planned, driver-required, and agent-required entries require separate qualification.
