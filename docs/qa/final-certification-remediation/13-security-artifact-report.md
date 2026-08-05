# Security and Artifact Report

Controls verified:

- Playwright uses trace/video retention only on failure and screenshots only on failure.
- Global teardown scans text files and ZIP trace contents for environment-provided password/token/secret values, replaces findings with `[REDACTED]`, rescans, and fails if any remain.
- CI runs the same scan before upload and retains artifacts for three days.
- Browser specs retrieve protected/ephemeral credentials; no reusable plaintext QA password is committed or reported.
- Final scan: 3 current artifact files, 0 redactions required, 0 findings.

Security review found no CSRF/header bypass, RBAC/ACL relaxation, tenant isolation relaxation, validation removal, secret logging, or public API expansion. Explicit resource denies were strengthened for collection endpoints.

The SSE subscription-attempt limit remains 30/minute and is now isolated per authenticated tenant session. This prevents one legitimate session from exhausting another session's reconnect budget without removing abuse protection; login and active-session controls bound the number of available session buckets.

Database safety: the two-second timeout was not increased. `ssl=disable` appears only in the explicit local integration URL. Production settings retain TLS-capable PostgreSQL URLs and connection validation; no global SSL override was introduced.
