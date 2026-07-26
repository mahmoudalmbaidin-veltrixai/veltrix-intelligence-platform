# Phase B6 — Dashboard Studio

## Architecture

The dashboard is the aggregate root. Dashboards, pages, widgets, filters, immutable versions,
shares, and snapshots store the validated organization and workspace. Queries include both tenant
identifiers. Dashboard UUIDs are stable URL identifiers; renaming does not change them.

The editable aggregate is stored in PostgreSQL. Every mutation requires `expected_version`, locks
the dashboard row, validates the token, writes atomically, and increments `row_version`. A stale
token returns `DASHBOARD_VERSION_CONFLICT` (409). The browser offers reload, save-as-copy, or
cancel and never retries a stale save.

Publishing validates the aggregate and B5 semantic references, then inserts a schema-versioned,
immutable `dashboard_versions` snapshot. Viewer routes resolve only `published_version_id`, so
draft changes cannot leak. Restore creates a new draft/history record without modifying old
versions.

Shares support tenant-member users and role principals with `view`, `interact`, `edit`, and
`manage`, expiry, and revocation. B3 membership, permissions, features, and entitlements remain
authoritative. Snapshots reference an immutable published version and use bounded JSON plus a
configured retention time.

## Query and content safety

Widget types and configurations are allowlisted by strict Pydantic contracts. Layouts fit a
12-column grid. Executable HTML, scripts, CSS, iframe URLs, arbitrary expressions, and SQL are
rejected. Filters contain semantic keys, allowlisted operators, and typed values.

`POST /api/v1/dashboards/{dashboard_id}/widgets/{widget_id}/data` validates dashboard, immutable
version, widget, access, tenant, filters, and limits, then calls the existing B5 `execute_query`
service. B6 does not compile SQL or read credentials. B5 owns metadata resolution, parameterization,
read-only execution, timeouts, quota, result bounds, and driver-error sanitization. Published
viewers use published widget definitions; draft preview requires edit access.

## Governance

Core feature/entitlement keys are `dashboard_studio`, `dashboard_publishing`, `dashboard_sharing`,
and `dashboard_snapshots`. Workspace admins receive the complete dashboard permission set; editors
author drafts; viewers read/query published dashboards; restricted users are denied. Quotas cover
dashboards, pages, widgets, versions, snapshots, queries, and result rows. B5 semantic query quota
is the execution source of truth to prevent double charging.

## Development

```powershell
docker compose up -d postgres redis
cd apps/api
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m vip_api.cli seed-dashboard-governance
.\.venv\Scripts\python.exe -m vip_api.cli seed-dashboard-demo
cd ../..
docker compose up -d --build api
pnpm dev --host 0.0.0.0 --port 3009
```

Open `http://localhost:3009/dashboards`. Create a dashboard, choose a published semantic model, add
KPI/chart/table widgets, save, reload, publish, and open the stable viewer URL.

Quality commands:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src tests
.\.venv\Scripts\pytest.exe
$env:RUN_INTEGRATION_TESTS='1'; .\.venv\Scripts\pytest.exe -m integration
cd ../..
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
pnpm test:a11y
```

## Extension rules and limits

New widget types require backend and TypeScript registry entries, a configuration allowlist, result
transformer, tests, and accessible UI. Filter types and share levels require server validation and
authorization tests. Never accept raw SQL, HTML, JavaScript, CSS, or iframe URLs. Every mutation
uses optimistic concurrency; published versions stay immutable.

B6.5 completes export rendering, protected artifacts, scheduler-ready definitions, email delivery,
and optional tenant-safe widget caching. The durable dashboard worker is intentionally compatible
with a future common B7 job adapter. See
`docs/backend/DASHBOARD_EXPORTS_DELIVERY_CACHE.md` for API, security, operation, and extension
details. Favorites remain outside the B6 aggregate.
