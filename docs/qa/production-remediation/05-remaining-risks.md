# Remaining Risks

No verified production blocker remains in the remediated scope.

## Non-blocking release follow-ups

1. The legacy `governance-admin@vip.demo` browser fixture is outside the current DPAPI QA credential inventory. Re-provision that fixture before the next complete browser certification so the two B9 presentation-only cases can run. The underlying RBAC/pipeline contracts are green in integration tests.
2. Interactive drill and navigation actions are meaningful in the viewer, not in static PDF/PNG/CSV attachments. Their complete definitions are preserved in every machine-verifiable export manifest; static output displays the corresponding state but cannot execute an interaction.
3. XLSX and archived-user lifecycle must remain absent from product messaging and navigation unless separately approved, designed, implemented, security-reviewed, and certified. Adding either later is feature work, not part of this remediation.
4. The test-only `ssl=disable` URL is valid only for the local non-TLS container. Production database URLs must continue to require the deployment's TLS policy.

## Explicitly not accepted as fixes

- No authorization bypass or tenant relaxation.
- No timeout increase for PostgreSQL.
- No integration-to-mock conversion.
- No disabled or skipped regression.
- No migration or destructive data cleanup.

