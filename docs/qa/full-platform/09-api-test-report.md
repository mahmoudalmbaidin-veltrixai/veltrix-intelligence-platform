# API Test Report

Runtime OpenAPI exposes 192 paths and 247 operations. Backend tests cover authentication, CSRF, refresh replay, tenancy, audit, connections, roles/groups/resource ACLs, pipelines, datasets, semantics, dashboards, delivery scheduler, jobs, infrastructure, migrations, and negative authorization. Live API health/readiness/version returned 200 and no stack trace or secret was observed in browser/API results.

The requested Cartesian contract matrix (valid, missing/extra/wrong type/UUID/not-found/unauthorized/forbidden/cross-tenant/suspended/expired/duplicate/pagination/filter/sort/large/empty/method/content type/rate/idempotency) was not executed for all 247 operations. OpenAPI-to-frontend SDK compatibility is partially covered by 279 frontend tests and route smoke. This gap alone prevents complete certification.

Known live outcomes include 201 connection/dashboard creation, sanitized connection tests, 401 generic invalid login, permission-denied direct calls, and 403/404 fail-closed governance paths. Secrets were never returned in connection payloads or written to reports.
