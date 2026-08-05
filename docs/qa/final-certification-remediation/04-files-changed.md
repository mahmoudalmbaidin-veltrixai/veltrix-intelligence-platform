# Files Changed

The machine-readable inventory is `changed-files.json`. The worktree was already dirty at preflight; existing user and prior-QA changes were preserved and are not represented as newly authored commits.

Primary remediation areas:

- Authentication/bootstrap: `src/shared/stores/auth.ts`, `src/modules/auth/LoginView.vue`, router and store tests.
- Dashboard reliability: `DashboardStudioView.vue`, dashboard service/delivery code, behavioral tests, Firefox scenario.
- Canonical parity/rendering: dashboard delivery schemas/services/worker/rendering, lifecycle tests, evidence generator, `VisualRenderer.vue`, `MapChart.vue`.
- Authorization: connection/dataset/semantic/pipeline/dashboard list services and domain integration tests.
- AI gating/navigation: route metadata, navigation, sidebars, command palette/providers, navigation tests.
- Browser determinism/security: persona manifest, fixture bootstrap, governed pipeline/governance/route tests, global artifact teardown, CI workflow.
- API certification: operation classifier, 247-operation JSON coverage, authenticated contract integration tests.
- Reports/evidence: this directory and its six required machine-readable artifacts.

No migration file, branch, commit, push, or pull request was created.
