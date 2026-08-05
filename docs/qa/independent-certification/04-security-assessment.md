# Security Assessment

## Preserved controls

- No inspected remediation change bypasses authentication, tenant headers, RBAC, ACLs, CSRF, or governance dependencies.
- The single-flight dashboard change does not alter backend authorization and does not log dashboard payloads.
- Export workers reauthorize the current actor and tenant before loading the exact published version.
- Local PostgreSQL `ssl=disable` is confined to test fixture/CI URLs. Production database URLs remain unmodified and may require TLS.
- Production frontend configuration rejects mock mode; debug/governance fail-closed/cookie/scanner/signing-key production validators remain present.
- No migration, plaintext production secret, or public API authentication relaxation was found in the remediation diff.
- Fresh integration coverage passed tenant isolation, suspended-user, RBAC, ACL, connection-secret, scheduler, dashboard-delivery, and worker behavior.

## Security concerns

1. Failed Playwright error-context files contain the entered QA password value, and the quality workflow uploads `test-results/` and `playwright-report/` for 14 days. CI uses an ephemeral generated credential, but local/shared audit artifacts can still expose reusable QA credentials. Password fields should be redacted from retained snapshots/traces or the credentials must be rotated after runs.
2. AI Knowledge contains mock enterprise documents and a nonfunctional upload control reachable if `ai_studio` is enabled. This is both an incomplete-surface and trust-boundary risk.
3. Production database TLS is supported but not enforced by configuration validation. This is not a regression from the remediation, but deployment policy must require a TLS-bearing production URL.
4. API sweep breadth may create false assurance: anonymous authentication rejection does not test authorization or tenant isolation inside each endpoint.

## Security conclusion

No direct authorization weakening was found, but credential-bearing browser artifacts and an enableable mock/placeholder AI surface prevent an unqualified production-safety statement.
