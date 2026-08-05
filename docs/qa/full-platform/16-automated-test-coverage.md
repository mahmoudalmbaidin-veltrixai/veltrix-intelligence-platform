# Automated Test Coverage

- Backend: 53 test files (25 unit, 27 integration plus shared configuration); 240 non-integration and 60 integration tests collected.
- Frontend: 45 Vitest files, 279 tests.
- Browser: 17 Playwright spec files; Chromium desktop/high-DPI/mobile and Firefox projects.
- Runtime API: 192 paths / 247 operations.

New coverage-support code parameterizes isolated organization, normal persona, and pipeline connection selection; console-error evidence is now actionable. Existing tests cover workers, migrations, tenant isolation, role/ACL precedence, pipeline frontend/worker parity, dashboard lifecycle/delivery, connector safety, semantic authorization, responsive behavior, and accessibility.

Gaps: two clean repeat integration runs, WebKit, exhaustive endpoint combinations, full resource/persona Cartesian matrix, every pipeline function/operator/node, dashboard browser/export format parity, full file/malware suite, scheduler time-zone/cron matrix, and performance/outage tests.
