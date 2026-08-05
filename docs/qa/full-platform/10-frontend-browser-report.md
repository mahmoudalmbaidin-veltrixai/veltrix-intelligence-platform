# Frontend Browser Report

Chromium desktop initial core run: 43 executed, 41 passed, 2 failed. Both were test-isolation issues (normal-user credential hard-coded; PostgreSQL-only upload selected the first/MySQL connection). After parameterization, the affected platform-admin and complete pipeline journey passed. Additional harness attempts exposed a wrong environment-variable name and exact-label mismatch; the final pipeline journey passed in 30.2 seconds.

Firefox portable desktop run: 38 executed, 35 passed, 3 failed. Authentication and route smoke passed when rerun. Dashboard share/save failed again after route smoke, then passed twice alone, leaving an order/timing-dependent flake (2 failures and 2 passes across its four Firefox executions).

Accessibility high-DPI Chromium: 18/18. Dedicated mobile Chromium: 5/5. WebKit was not installed/supported. Browser artifacts are in ignored `test-results/` and `playwright-report/` paths.

Test isolation improvements now support an explicit QA organization, explicit normal user, explicit pipeline destination connection, and useful serialized console errors. The four legacy tenant-isolation browser tests remain blocked by unavailable pre-existing demo passwords; the backend tenant-isolation integration coverage passed in the clean run.
