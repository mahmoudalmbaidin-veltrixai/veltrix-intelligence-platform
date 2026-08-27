# Current baseline

This file is overwritten on each certification run. Historical reports remain under `reports/`.

| Field | Value |
| --- | --- |
| Audit date | 2026-08-25 |
| Auditor posture | Adversarial final product / live-service / resell certification |
| Branch | `feat/vip-productization-p1` |
| HEAD SHA | `fa02d9e2484f6b603efe5af9e7586975342b485c` |
| HEAD subject | `docs(demo): add Stage 4 runbook and certification` |
| Describe | `vip-pre-productization-2026-08-23-3-gfa02d9e` |
| Tracking | `origin/feat/vip-productization-p1` **ahead 3** |
| Working tree | **Dirty** — untracked `DECKS/`, client demo markdown/xlsx, `demo-data/vip_demo_sales_orders.csv`, `scripts/demo/` |
| Reproducible application tree | SHA is identifiable. Runtime database and untracked demo files are **not** implied by the SHA. |
| Application version | `0.1.0` (`package.json`, API `APP_VERSION`) |
| Build identifier | `commit_sha=null`, `build_timestamp=null` on `GET /api/v1/version` |
| Frontend runtime | Node `v24.19.0`, npm `11.17.0`, Vite port **3009** |
| Backend runtime | Python `3.14.4` host; API container `uvicorn` reload on `:8000` |
| APP_ENV | `development` |
| Alembic | single head `20260808_0025` (current = head) |
| PostgreSQL | `vip-postgres-1` healthy, port 5432 |
| Redis | `vip-redis-1` healthy, port 6379 |
| API | `vip-api-1` healthy |
| Dashboard/job worker | `vip-dashboard-worker-1` healthy; heartbeat `default,dashboard` seen 2026-08-25 |
| Pipeline worker | `vip-pipeline-worker-1` healthy |
| Dedicated scheduler container | **Not running.** Last `scheduler` heartbeat row is `stopped` at 2026-08-16. Ticks are implemented inside the job worker. |
| ClamAV | `vip-clamav-1` healthy |
| Email provider | `DASHBOARD_EMAIL_PROVIDER=file` → `/data/vip-email-outbox` (75 `.eml` files before this audit; 76 after password-reset probe) |
| SMTP host | empty |
| File storage | `FILE_STORAGE_PROVIDER=local` |
| Malware scanner | `clamav` (API); dashboard worker `noop` |
| Auth cookies | `AUTH_COOKIE_SECURE=false` |
| Frontend URL | `http://localhost:3009` |
| Docs | `ENABLE_DOCS=true`; `/docs` and `/openapi.json` publicly reachable |
| Extra compose project | `vipcertv2-*` Postgres/Redis/ClamAV also running on this machine (ports 55432/56379) — not the audited stack |

## Runtime data (not part of the Git SHA)

| Object | Count on audited DB |
| --- | --- |
| Organizations | 85 |
| Workspaces | 124 |
| Users | 127 |
| Connections | 242 |
| Datasets | 1841 |
| Pipelines | 609 |
| Pipeline runs | 275 (249 succeeded / 21 failed / 5 cancelled) |
| Semantic models | 35 |
| Dashboards | 976 |
| Dashboard exports | 328 |
| Jobs | 343 (44 export `dead_letter`) |
| Audit events | 39853 |
| Files | 478 |
| Connection types visible via API | **117** including leftover `pg-*` test types |

**This database is a local QA/demo landfill, not a clean customer install.**
