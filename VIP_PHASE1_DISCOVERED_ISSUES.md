# VIP Phase 1 Discovered Issues

The following issues were observed during pre-flight but are outside BUG-001 and
BUG-004. They were recorded and not remediated in this phase.

- The API development container's file reloader detected an existing, unrelated
  modification in `semantic/services.py` and remained waiting for open connections
  (including an SSE connection) to close. The API container was restarted to restore
  the test environment; no source change was made for this operational condition.
- The repository's `.venv-ci` environment cannot collect the backend suite because
  `arabic_reshaper` is missing. The project `.venv` contains the declared runtime
  dependency and was used for the baseline and remediation suites.
- The pre-fix Chromium navigation emitted transient 401 console responses during
  route/bootstrap transitions. They did not prevent the authenticated Dataset or
  Pipeline measurements and are unrelated to the scoped defects.
- The populated QA workspace contains a duplicate active dataset named
  `vip_b5_sales_demo` whose fields endpoint succeeds but whose preview endpoint
  returns 404 because its physical source is absent. The Phase 1 regression uses
  a healthy authorized first-page dataset and leaves this unrelated fixture/data
  lifecycle issue unchanged.
- The full backend integration baseline and post-fix run both have two failures
  in `test_production_api_contract_sweep.py`: the hard-coded expected operation
  count is 255 while the application exposes 256 operations. All 69 other
  integration tests pass. This pre-existing API-inventory drift is unrelated to
  dataset or pipeline behavior and was not changed.
- The unqualified repository-wide frontend lint command traverses pre-existing
  generated Playwright trace assets under `VIP_TEST_EVIDENCE/` and reports
  thousands of findings in bundled third-party JavaScript. Source lint succeeds
  when generated evidence directories are excluded, and every Phase 1 source,
  test, and measurement script passes its scoped lint/format check.
