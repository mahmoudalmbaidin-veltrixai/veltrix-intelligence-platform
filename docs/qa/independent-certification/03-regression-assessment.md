# Regression Assessment

## Fresh passing checks

- Backend unit: 243 passed, 61 integration tests deselected.
- Backend integration: 61/61 passed three consecutive times against the same local PostgreSQL service.
- Frontend: 46 files, 280 tests passed.
- Production frontend build: passed with live production configuration.
- Frontend ESLint and Vue TypeScript checks: passed.
- Backend Ruff: passed.
- Accessibility and route smoke: 21/21 passed, including 18 Axe cases and three live placeholder/route cases.
- Dashboard actions, dashboard/pipeline studio keyboard journeys, responsive studios, and platform-admin authorization: 10 selected cases passed.
- Dashboard and pipeline workers, API, PostgreSQL, MySQL, Redis, and ClamAV containers reported healthy during the audit.

## Fresh failures and gaps

- MyPy failed with two errors: an unused ignore in `core/config.py` and an `Any` return from the remediation-touched Arabic display helper in `dashboard_delivery/rendering.py`.
- Firefox repeat requirement failed 19/20 at authenticated bootstrap. A successful API login did not reliably transition the application from `/login`.
- The initial governed CSV pipeline test chose the first selectable connection, which was MySQL, and received 422. It passed when rerun with `VIP_E2E_DESTINATION_CONNECTION_NAME=QA_PostgreSQL_Valid`. The test is not self-contained or deterministic in the current seeded environment.
- Four tenant-isolation browser cases use `tenant-a@vip.demo` / `tenant-c@vip.demo` with the unrelated current QA password and failed 401 before assertions. Their backend tenancy equivalents passed in integration, but the browser certification layer remains unusable.
- The API sweep is one broad test with weak depth. Passing it is not equivalent to per-endpoint contract certification.
- The route-smoke test uses fixed 100/250 ms waits, contrary to the requested rejection of artificial waits. Assertions around stable state should be event/locator driven.

## Regression conclusion

Core unit, integration, build, accessibility, worker, dashboard, and configured pipeline paths are generally healthy. The total regression gate is not releasable because required browser determinism and static typing are not green, and several browser suites depend on obsolete/external fixture state.
