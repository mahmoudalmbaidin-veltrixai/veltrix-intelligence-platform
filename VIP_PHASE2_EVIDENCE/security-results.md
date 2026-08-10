# Phase 2 security results

- Owner/admin: PASS through the real governed-tenant browser save/reload/publish lifecycle.
- Viewer/direct ACL: PASS in resource permission and dashboard persistence integration tests.
- Explicit deny: PASS; direct deny overrides user and group grants.
- Cross-workspace: PASS through workspace-qualified dashboard/export lookups and signed-token mismatch rejection.
- Cross-organization: PASS; tenant-qualified dashboard integration returns not found outside its organization.
- Anonymous: PASS; live dashboard list and export download-token requests return HTTP 401.
- Signed downloads: PASS; tokens bind user, organization, workspace and export, and are single use.

No authorization, tenant, workspace, ACL, or token-validation branch was bypassed
by the Pivot/Scatter projection and rendering changes.
