# VIP Phase B9.1A — Manual UAT: Dashboard Delivery

**Frontend:** http://localhost:3009 · **API:** http://localhost:8000 (live mode)
All Docker services healthy; Alembic single head `20260728_0018`.

## Demo credentials (local only, non-production)
| Persona | Email | Password |
|---|---|---|
| Admin | `governance-admin@vip.demo` | `Enterprise review 2026!` |
| Editor | `governance-editor@vip.demo` | `Enterprise review 2026!` |

> These are local development credentials provisioned idempotently via `python -m vip_api.cli configure-governance-demo`. They are never stored in the repo and are not production credentials.

## What was delivered
The recurring **dashboard delivery scheduler** now consumes due schedules automatically. Previously schedules were stored but never fired; now the `dashboard-worker` process runs a tick every ~15s that claims due schedules, creates a delivery run + export, renders it, emails it, records success/failure, and advances the next run.

---

## UAT 1 — Recurring delivery fires automatically (primary)
1. Sign in and open a **published** dashboard (or publish one in Dashboard Studio: edit → Save → Publish).
2. Open **Deliveries / Schedule** for that dashboard. Create a schedule:
   - Format **CSV**, recipients `ops@vip.demo`, subject "Nightly", type **Daily** (or **Cron** `*/2 * * * *` for a fast demo), timezone `UTC`, **Enabled**.
3. To force an immediate run without waiting, an operator can set the row due (local dev only):
   ```bash
   docker compose exec postgres psql -U vip -d vip -c "update dashboard_delivery_schedules set next_run_at = now() - interval '1 minute' where name = 'Nightly';"
   ```
4. Within ~15–30s the worker tick fires. **Verify:**
   - A delivery run appears with status **sent** and the schedule's **Last run** populates.
   - The schedule's **Next run** advances to the next occurrence (recurrence continues).
   - The rendered email lands in the outbox:
     ```bash
     docker compose exec api sh -c "ls -t /data/vip-email-outbox/*.eml | head -1"
     ```
   *Expected:* an `.eml` with your subject and a `dashboard.csv` attachment of real widget data from the **published** version.

## UAT 2 — Pause / resume
1. Toggle the schedule **off** (pause). *Expected:* `enabled=false`, `next_run_at` cleared; the tick no longer claims it (no new runs).
2. Toggle **on** (resume). *Expected:* `next_run_at` recomputed; the next due tick fires it again.

## UAT 3 — Failed delivery is recorded (revoked access)
1. As Admin, create a schedule owned by a second user, then remove that user's workspace membership.
2. Force the schedule due (as in UAT 1 step 3). *Expected:* a delivery run is created with status **failed** and error code **DELIVERY_ACCESS_REVOKED**; no export/email is produced. Scheduled deliveries respect live access revocation.

## UAT 4 — Export parity (editor ↔ viewer ↔ export)
1. In Dashboard Studio: **edit → Save → reload** (edits persist) → **Publish**.
2. Open the **Viewer** (published) — confirm pages, widget placement/dimensions, titles, KPI/number formats, tables/charts, filters, and styling match the editor.
3. **Export** the dashboard as **CSV** / **JSON** / **PDF** / **PNG**. *Expected:* all outputs use the **published** version and real queried data; CSV/JSON contain the same values shown in the viewer. Draft edits do not alter the published export.

## UAT 5 — Cron & timezone correctness
1. Create a **Cron** schedule `0 9 * * *` with timezone `Asia/Riyadh`. *Expected:* Next run computes to 09:00 Riyadh (06:00 UTC). A `*/15 * * * *` schedule fires every 15 minutes. Monthly `0 0 1 * *` fires on the 1st.

---

## Live-verified example (already run)
A daily schedule "B9.1A Live Nightly" on the published **Sales Performance** dashboard was dispatched by the worker: run **sent**, `.eml` "Nightly Sales Performance" in the outbox, `last_run_at` set, `next_run_at` advanced. (It has been paused after verification so it does not accumulate daily emails; re-enable via the UI to demo.)

## Expected outcomes summary
- Enabled + due schedule → automatic delivery within one tick; run `sent`; last/next run updated.
- Paused schedule → never claimed.
- Revoked creator access → run `failed` (`DELIVERY_ACCESS_REVOKED`), no email.
- Export/scheduled outputs use the published version with real data.
- Cron/timezone next-run times are correct and DST-stable.
