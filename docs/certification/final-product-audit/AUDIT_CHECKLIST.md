# Audit checklist

Mark each item `automated`, `semi-automated`, or `manual`. Do not convert a skipped check into a pass.

## Automated (collector / existing gates)

| Check | How | This run (2026-08-25) |
| --- | --- | --- |
| Git branch, SHA, dirty state | `git rev-parse`, `git status` | **Done** |
| `/health` `/ready` `/api/v1/version` | HTTP | **Done** |
| Docker Compose service health | `docker compose ps` | **Done** |
| Alembic current = heads | `alembic current` / `heads` | **Done** — `20260808_0025` |
| Redis PING | `redis-cli ping` | **Done** |
| Postgres ready | `pg_isready` | **Done** |
| Worker heartbeats | SQL `worker_heartbeats` | **Done** |
| Email provider name | Settings (no secrets) | **Done** — `file` |
| Outbox file count | count `.eml` | **Done** |
| Table/object counts | SQL aggregates | **Done** |
| Frontend port listen | TCP 3009 | **Started during audit** (was down) |
| Live login + tenant-scoped GET matrix | `scripts/certification/live_api_probe.py` | **Done** (QA org admin / viewer) |
| Password-reset request uniformity | HTTP 202 known + unknown identifier | **Done** |
| Cross-tenant dashboard GET | other org headers | **Done** — 404 |
| Viewer pipeline create | POST `/pipelines` | **Done** — 403 |
| Invitation create | POST invitations | **Done** — 201, no mail transport |

## Existing test suites (evidence, not proof)

| Suite | Command | This run |
| --- | --- | --- |
| Frontend lint/typecheck/unit | `npm run lint` `npm run typecheck` `npm test` | **Not re-run** |
| Frontend e2e | `npm run test:e2e` | **Not re-run** |
| Backend unit | `make backend-unit` | **Not re-run** |
| Backend integration | `make backend-integration` | **Not re-run** |
| Stage 4 demo cert scripts | `scripts/demo-stage4/` | **Not re-run**; users/orgs still in DB |

Treat historical Stage 4 “A — ENTERPRISE DEMO ENVIRONMENT CERTIFIED” as **non-authoritative** for this SHA.

## Manual (required for a full recertification)

| Check | Notes |
| --- | --- |
| Browser login, idle warning, logout | Login + forgot-password UI verified this run; full authenticated shell not fully walked |
| Super-admin org/user/workspace create | API exists; not executed as a mutating platform-admin journey this run |
| Analyst path: connection → dataset → pipeline nodes → semantic → dashboard → publish → PDF/PNG | Historical DB rows exist; **not rebuilt from scratch in this audit** |
| Viewer published dashboard filters / no editor chrome | Not re-run in browser this audit |
| Notification prefs after relogin | Code inspection: prefs persist on user JSON and **do not** filter generation or list |
| Notification archive after reload | Client-side only |
| Open `/jobs/:id` from a notification | **No frontend route** |
| Connector catalog “all” vs default available filter | API returns 117 types including junk `pg-*` |
| PDF/PNG visual quality | Historical completed exports exist; files not visually re-inspected this run |
| Schedule fire after restart | `cert-live` pipeline schedule enabled with `next_run_at` 2026-08-25; dedicated scheduler container absent |
| Clean-install empty database | **Not executed** (would destroy local QA data) |
| Terraform apply / live AWS | **Not executed**; no tfstate in repo |
| Real SMTP/Resend send to an external inbox | **Not possible** on current config |
| Legal pack / DPA / SLA | **Absent** from repository |

## Environment prerequisites

- Docker Engine running
- Compose stack: postgres, redis, api, dashboard-worker, pipeline-worker, clamav
- Frontend: `VITE_API_MODE=live` (workspace `.env.local`; do not commit secrets)
- Credentials: local DPAPI helpers or QA vault — **never paste into reports**
- Do not use `scripts/demo/show-vip-demo-credentials.ps1` as proof of a working demo: those three users are **suspended** on this database
