# VIP Phase B9.1A — Dashboard Delivery & Studio Completion Report

**Date:** 2026-08-03
**Branch:** `phase-b9/dashboard-delivery-completion`
**Base:** `frontend/enterprise-ui-enhancement` (B9.0 merged, `01aaff2`)
**Scope:** recurring dashboard delivery scheduler; dashboard editor/viewer/export parity; dashboard data export; dashboard-focused testing. No Pipeline/Dataset/Connection/Semantic/Reports work.

---

## Executive summary

The B9.0 production-readiness assessment identified the **recurring dashboard-delivery scheduler as the single largest gap**: `next_run_at` was stored but never consumed, cron was unparsed, and only the manual "send test" path created runs. This slice **closes that gap with a production-safe scheduler** built on the existing job/worker platform (no second queue), plus real cron/timezone math. Editor/viewer/PDF/PNG/scheduled parity and CSV/JSON/PDF/PNG data export were **audited and confirmed already consistent** (all read the published version and real queried widget data) and are documented here with their guarantees and limits.

**Verified live end-to-end on the running stack:** a due schedule was claimed by the worker tick → a delivery run + export were created → the export rendered a CSV of real widget data → the email was delivered to the outbox → the run recorded `sent`, `last_run_at` was set, and `next_run_at` advanced to the next occurrence.

---

## 1. Recurring delivery scheduler (implemented)

### Design
A scheduler **tick** runs inside the existing generic job worker (`dashboard-worker` = `python -m vip_api.jobs.worker`) — no new process or queue. Each tick (`dashboard_delivery/scheduler.py::dispatch_due_deliveries`):

1. **Claims due schedules** with `SELECT … WHERE enabled AND next_run_at IS NOT NULL AND next_run_at <= now ORDER BY next_run_at FOR UPDATE SKIP LOCKED LIMIT n` (uses the existing `ix_dashboard_delivery_schedules_due` index).
2. For each claimed schedule, **inside the same claim transaction**: creates a `DashboardDeliveryRun` (status `queued`), **advances `next_run_at`** to the next occurrence (`None` + disables for one-time), and commits. Advancing within the locked transaction is the duplicate-prevention primitive — a concurrent scheduler or a re-tick never re-claims the same slot.
3. Per claimed slot (separate transaction): builds the **schedule creator's** authorization context and calls the existing `create_export(…, delivery_run_id=run.id, queue=…)`, linking `run.export_id`. Delivery then flows through the existing `dashboard.export` job handler → render → `_complete_delivery` → email.

### Cron / timezone / interval math (`scheduling.py`)
- **`parse_cron` / `next_cron`**: full five-field cron (`* , - /`, DoW 0–7 with Sunday=0/7, standard DoM-OR-DoW semantics), evaluated in **wall-clock local time within the schedule's timezone** then converted to UTC, so a "09:00" schedule stays at 09:00 local across DST. Bounded scan guards non-matching expressions.
- **`next_interval`**: daily/weekly/monthly step from the previous run's wall-clock anchor; **monthly is calendar-aware** (Jan 31 → Feb 28/29, not +30 days). **Missed slots collapse to one** — after downtime the next future occurrence fires once, not a backlog.
- **`advance_next_run`**: used by the scheduler to move an existing schedule to its next slot (`None` for one-time).

### Required behaviors — coverage
| Requirement | How |
|---|---|
| Parse validated cron | `parse_cron`/`next_cron`; `ScheduleCreate` already validates 5-field |
| Time zones | wall-clock stepping in `ZoneInfo(schedule.timezone)` |
| Find + claim due schedules | `FOR UPDATE SKIP LOCKED` on the due index |
| Prevent duplicate delivery | `next_run_at` advanced inside the claim transaction |
| Transaction-safe locking | `SKIP LOCKED`; claim and advance are one commit |
| Advance `next_run_at` | `advance_next_run` (per type; catch-up aware) |
| Record last run | `schedule.last_run_at` set by `_complete_delivery` on success |
| Record success/failure | `DashboardDeliveryRun.status` (`sent`/`failed` + `safe_error_code`) |
| Pause / resume | existing `enabled`/`next_run_at` toggles; paused rows are not claimed |
| Retry failed delivery | export runs as a `Job` with `max_attempts` (existing retry/dead-letter) |
| Worker restart | the tick is stateless + idempotent; the generic worker already recovers leases |
| Missed schedules | `next_interval` catch-up fires the next future slot once |
| Preserve tenant boundaries | every run/export carries the schedule's org+workspace; export re-authorizes per-tenant |
| Audit | `dashboard.delivery.scheduled` on claim; `dashboard.delivery.sent` on delivery |
| Metrics | `vip_dashboard_delivery_scheduled_total{outcome=dispatched|access_revoked|export_error}` |

### Scheduler authorization — execution policy
A future delivery executes as the **schedule's `created_by_user_id`**. The export worker rebuilds that user's org/workspace authorization context and re-checks `dashboard.export` + `can_view` on the **live** membership. Consequences:
- **Revoked access** (creator's membership removed) → the actor context cannot be built → the run is recorded `failed` with `DELIVERY_ACCESS_REVOKED`, and no export/email is produced.
- **Dashboard/export permission** are enforced at execution time by the same `authorize`/`_published` checks the interactive export uses.
- **Tenant membership** is required and re-validated every run.
This mirrors the interactive-export identity model and keeps scheduled deliveries from becoming a way to bypass revocation.

### Configuration (additive, `core/config.py`)
`DASHBOARD_DELIVERY_SCHEDULER_ENABLED` (default true), `DASHBOARD_DELIVERY_SCHEDULER_POLL_SECONDS` (15), `DASHBOARD_DELIVERY_SCHEDULER_BATCH` (25).

### Recurring-status fix
`_complete_delivery` previously set `schedule.status="sent"` after every delivery, which would have stranded a recurring schedule. It now preserves `"scheduled"` while the schedule is enabled with a future `next_run_at`, settling to `"sent"` only for a spent one-time schedule.

---

## 2. Delivery formats — verified real support
The render registry (`dashboard_delivery/rendering.py`) implements real renderers for **PDF** (ReportLab), **PNG** (PIL), **CSV**, and **JSON**, each driven by `execute_widget` against the **published version's** snapshot (real queried data, sensitive-metadata scrubbed). **Email delivery** is provided by the file/SMTP provider abstraction (`dashboard_delivery/email.py`); locally the `file` provider writes `.eml` to `/data/vip-email-outbox`. Scheduled delivery accepts `pdf|png|csv` (JSON remains available on the interactive export endpoint). Recipients, signed downloads, retention (`expires_at`), failure reason (`safe_error_code`), retry, delivery history (`DashboardDeliveryRun`), next/last run, pause/resume, and delete already exist on the schedule + export APIs; the scheduler makes them meaningful by actually firing runs.

---

## 3. Dashboard parity & data export — audited, consistent
- **Editor ↔ Viewer**: both render through the same `DashboardGridCanvas`/`WidgetFrame` components; the viewer loads the **published** version. Pages, widget placement/dimensions, titles, KPI/number formats, tables, charts, filters, and styling come from the same snapshot + widget-data path.
- **Export (PDF/PNG/CSV/JSON) & scheduled delivery**: both source the **published `DashboardVersion.snapshot`** (`dashboard_version_id` pinned on the export) and run the **same `execute_widget`** per widget — so numbers match the viewer. PDF/PNG rendering is a server-side reimplementation (ReportLab/PIL), so it is **data-consistent** with visual fidelity as an approximation (documented limit, unchanged this slice).
- **Draft vs published**: exports and schedules always use the pinned published version; draft edits never alter a published delivery.
- **Data export (CSV/JSON)**: the export pipeline emits real queried widget data (not mock). No mock/placeholder path is used in `live` mode.

No confirmed parity defect was found requiring a code change; the guarantees above are covered by the existing renderer unit tests plus the new scheduler test (which links each run to the published `dashboard_version_id`).

---

## Tests
- **Unit — `tests/unit/test_delivery_scheduling.py` (18):** cron parsing (fields/ranges/steps/Sunday 0=7), next-cron (daily, roll-over, timezone offset, `*/15`, monthly, weekday, DoM-OR-DoW), intervals (daily/weekly, calendar-aware monthly, missed-slot catch-up), `advance_next_run` (one-time/cron/interval).
- **Integration — `tests/integration/test_dashboard_delivery_scheduler.py` (5):** due-claim creates run+export and advances `next_run_at` + **duplicate prevention** (re-tick claims nothing); paused/future not claimed (**pause**); one-time completes + disables; **revoked** creator access → run `failed`/`DELIVERY_ACCESS_REVOKED`; **concurrent schedulers** (`asyncio.gather` of two ticks) claim each slot exactly once.
- Existing renderer/email unit tests (`test_dashboard_delivery.py`) and dashboard persistence/parity integration tests remain green.

## Validation (exact totals)
| Gate | Result |
|---|---|
| Backend `ruff check .` | passed |
| Backend `ruff format --check` | passed (237 files) |
| Backend `mypy src tests` | passed (212 files) |
| Backend unit (`pytest -m "not integration"`) | **214 passed** |
| Backend integration run 1 (fresh `_test` DB) | **54 passed** |
| Backend integration run 2 | **54 passed** |
| Frontend `typecheck` / `lint` / `format:check` | passed |
| Frontend unit (`vitest`) | **275 passed** |
| Frontend `build` | passed |
| Alembic | single head `20260728_0018`, `alembic check` clean (no migration needed) |

## Live evidence (running stack)
A due `daily` schedule ("B9.1A Live Nightly") on the published "Sales Performance" dashboard was dispatched by the worker tick: delivery run → `sent`; `.eml` "Nightly Sales Performance" written to `/data/vip-email-outbox`; `schedule.last_run_at` set; `schedule.next_run_at` advanced to the next day (recurrence continues). A manual tick on the live DB dispatched all due schedules and created their runs + exports.

## Database changes
**None.** The scheduler reuses existing tables/indexes (`dashboard_delivery_schedules.ix_…_due`, `dashboard_delivery_runs`, `dashboard_exports`, `jobs`). No migration.

## Files changed
New: `dashboard_delivery/scheduler.py`, `tests/unit/test_delivery_scheduling.py`, `tests/integration/test_dashboard_delivery_scheduler.py`. Modified: `dashboard_delivery/scheduling.py` (cron/tz/interval), `dashboard_delivery/worker.py` (recurring status), `jobs/worker.py` (scheduler tick), `core/config.py` (settings), `core/metrics.py` (counter).

## Not changed this slice (assessed as already-sufficient)
- No dedicated single-widget CSV endpoint was added — dashboard-level CSV/JSON export already emits real per-widget data.
- No Dashboard Studio UX redesign — the assessment found no confirmed usability defect in editing/resize/drag-drop/save/publish/unsaved-indication beyond what already exists; these were left unchanged per the "fix confirmed issues only" instruction.
- PDF/PNG remain a server-side visual approximation (data-consistent) — fidelity work is deferred (B9.1+).
- Browser-driven visual Chromium flows were substituted with the live full-stack delivery verification above (the in-app browser pane is not displayable in this environment).

## Remaining B9.1+ (out of this slice)
Export visual-fidelity (headless rendering), single-widget CSV export endpoint, delivery-history UI polish, pipeline run/retry via resource evaluator, dataset mock tabs, AuditCenter path, MySQL discovery — tracked in the production-readiness assessment.
