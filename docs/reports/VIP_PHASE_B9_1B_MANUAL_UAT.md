# VIP Phase B9.1B — Manual UAT: Pipeline & Dataset

**Frontend:** http://localhost:3009 · **API:** http://localhost:8000  
**Mode:** `VITE_API_MODE=live` · base `http://localhost:8000/api/v1`  
Leave running: PostgreSQL, Redis, API, dashboard-worker, pipeline-worker, ClamAV, frontend on 3009.

## Demo credentials (local only, non-production)
| Persona | Email | Password |
|---|---|---|
| Admin / Owner | `governance-admin@vip.demo` | `Enterprise review 2026!` |
| Editor / Developer-capable | `governance-editor@vip.demo` | `Enterprise review 2026!` |
| Viewer | `governance-viewer@vip.demo` | `Enterprise review 2026!` |

> Provisioned via `python -m vip_api.cli configure-governance-demo`. Never production credentials.

For Pipeline ACL personas beyond broad roles, share a published pipeline from Admin with Access levels:
- **Viewer** → view/history/logs/artifacts only  
- **Operator** → start/retry/cancel  
- **Developer** → edit/validate/publish (+ run via ladder)  
- **Owner** → full control including share/archive  

## Resources
| Resource | Notes |
|---|---|
| Test Pipeline | Create in Studio or reuse an existing published pipeline; share with ACL personas |
| Failed-run / retry | Start a run that fails (invalid export / cancelled then forced failed) → Operator **Retry** |
| Artifact example | Pipeline with `file-export` / Protected File node that succeeds → Results → Download |
| Dataset preview | Open `LIVE-UAT–Customers` (or any listed dataset) → Data preview |
| Dataset quality | Data Quality workspace → create rule / Run evaluation |
| Dataset certification | Dataset Overview → Certify / Revoke (requires certify capability) |

---

## UAT 1 — Pipeline Viewer vs Operator
1. As Admin, publish a pipeline and grant **Viewer** ACL to a second user; grant **Operator** to a third.
2. Sign in as Viewer → open pipeline. *Expected:* graph read-only; Run/Retry/Cancel disabled; palette shows Developer-required hint; can open run history/logs.
3. Sign in as Operator → Run succeeds without broad `pipeline.execute`. *Expected:* status/progress/logs update; Cancel works while queued/running; Retry on failed.

## UAT 2 — Pipeline Developer / Owner
1. Developer ACL: edit/validate/save/publish available; Run available (ladder includes operator).
2. Owner ACL: Share + archive/delete available; full toolbar.

## UAT 3 — Artifacts
1. Run a pipeline that produces a file-export artifact.
2. Results tab (or Runs drawer) lists name/type/size/created/expires.
3. Download opens signed URL. *Expected:* file downloads; expired/missing token → clear error (no UUID leak).

## UAT 4 — Dataset live tabs (no mocks)
1. Open a dataset detail page.
2. Lineage: real upstream/downstream or empty — **no** “Revenue Nightly ETL”.
3. Access: real ACL rows or empty grants — **no** “analytics-service” mock.
4. Activity: real audit events or empty — **no** fabricated “Nightly Scheduler” feed.
5. Versions: “Version history unavailable” — **no** fake v12/v11 rows.

## UAT 5 — Certification
1. User with **edit** only: Certify controls disabled/explained; PATCH cannot set certification.
2. User with **certify**: Certify with note → status Certified, by/at/note persist after reload; audit `dataset.certified`.
3. Revoke → uncertified; audit `dataset.certification.revoked`.

## UAT 6 — Preview & quality
1. Preview shows real columns/rows with pagination; denied without query access.
2. Quality workspace: create rule, run evaluation, see job/results (certify-gated mutations).

## Expected outcomes summary
- ACL Operator can run/retry/cancel without broad execute permission; Viewer cannot.
- Studio mutations blocked for non-developers; toolbar matches backend access.
- Artifacts listable/downloadable for authorized viewers+.
- Dataset detail tabs are live or honestly unavailable — never mock rows in live mode.
- Certification is certify-gated, audited, and reload-persistent.
