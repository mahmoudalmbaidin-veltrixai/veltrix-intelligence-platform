# Release Candidate Commit Plan

The tested remediation crosses auth, dashboards, exports, authorization, workers, and
shared route/bootstrap files. A ten-commit split would require risky partial-file staging
and would not reproduce the tested tree. The release therefore uses three coherent
commits:

1. `fix(platform): freeze production certification remediation`
   - backend and frontend production source;
   - runtime dependency locks and container configuration;
   - no migrations.
2. `test(certification): add deterministic release coverage`
   - backend/frontend/E2E tests;
   - OpenAPI coverage and artifact tooling;
   - self-contained browser fixture scripts, Playwright config, and CI gate.
3. `docs(qa): preserve certification evidence and freeze handoff`
   - repository documentation;
   - prior QA reports;
   - release-freeze records;
   - selected sanitized parity evidence.

The exact post-commit MyPy gate identified test annotation defects, so a fourth
test-only corrective commit was required. A fifth documentation-only commit records the
resulting clean gates and handoff. Neither additional commit changes product behavior.

Raw generated artifacts and local state are excluded. No commit is empty, no existing
history is rewritten, and no push or pull request is performed.
