# Remaining Risks

## Release-blocking

1. Firefox authenticated dashboard scenario has not achieved 20 consecutive passes.
2. CSV, PDF, and PNG do not satisfy the required complete definition/visual parity contract; Arabic chart/mixed-direction output is not acceptable evidence.
3. Incomplete AI Knowledge/Studio content can be exposed through a feature flag without the claimed entitlement boundary.
4. API production validation does not exercise authenticated success/error schemas and security semantics across all operations.
5. The repository's current static-analysis gate is not green, and live browser certification relies on stale or externally configured fixtures.

## Non-blocking but material

- A save request that joins an in-flight save does not queue a follow-up persistence operation for edits made during that flight; the editor remains dirty, but another explicit/autosave trigger is required.
- Production database TLS is configurable rather than enforced.
- Retained browser failure artifacts can include QA credentials.
- Synthetic parity evidence covers only KPI, bar, table, and text widgets rather than the complete 20-type matrix.
- Browser route smoke uses fixed waits and can miss late asynchronous failures.

## Required re-certification evidence

- A new isolated Firefox 20/20 run after resolving the login/bootstrap race, plus behavioral tests for stale edits, failed-save navigation, publish-on-save-failure, leave guard, and cache refresh.
- Lifecycle-generated parity fixtures covering all widget types and every output channel, with pixel/layout and machine-definition comparisons including Arabic/Unicode.
- Complete production navigation/command inventory proving incomplete modules cannot be enabled.
- Authenticated operation-level contract tests derived from OpenAPI with representative RBAC, tenant, suspended-user, validation, pagination/filter/sort, and payload-bound cases.
- A green, self-contained regression gate: MyPy, browser tenant personas, configured pipeline destination, accessibility, unit/integration/build, scheduler/workers/connections.
