# VIP — Manual Test Scenario (Live End-to-End)

A step-by-step manual test you can run in the browser to verify the platform works
front-to-back. Each step lists the action and the **expected result**. Mark each ✅/❌.

> Only the modules below are wired to the **real backend**. Demonstration modules
> (AI Studio, Automation, Billing, Marketplace, Insights, Reports, Operations, Developer,
> Home widgets) use mock data — don't treat them as live.

---

## 0. Start the environment

```bash
# From the repo root (C:\Users\MahmoudAlmbaidin\Downloads\VIP)
docker compose up -d                                  # postgres, redis, api, workers
docker compose --profile connectors up -d mysql       # optional: for the MySQL connector test
npm run dev                                            # frontend on http://localhost:3009
```

Expected:
- `http://localhost:8000/health` → `{"status":"healthy",...}`
- `http://localhost:8000/ready` → database + redis `healthy`
- `http://localhost:3009` loads the sign-in page.

If credentials were reset, they are provided separately (not committed). This scenario uses:

| Field | Value |
| --- | --- |
| URL | http://localhost:3009 |
| Admin email | `tenant-a@vip.demo` |
| Password | (provided in chat) |
| Org / Workspace | Organization Alpha / Alpha Workspace 1 |
| Governance personas | `governance-editor@vip.demo`, `governance-viewer@vip.demo`, `governance-restricted@vip.demo` (same password) |

Sample data to upload lives in **`sample-data/`**: `vip_sales_sample.csv` and `vip_sales_sample.xlsx`.

---

## 1. Authentication (B1)

| # | Action | Expected |
| --- | --- | --- |
| 1.1 | Open `/login`, enter admin email + wrong password, submit | Clear error; no crash; stays on login |
| 1.2 | Enter correct credentials, submit | Redirects to `/home`; your name + org/workspace show top-right |
| 1.3 | Refresh the browser (F5) | Stays logged in (session persists) |
| 1.4 | Open a second tab to `/dashboards` | Loads without re-login |
| 1.5 | Click user menu → Logout | Returns to login; visiting `/dashboards` redirects to `/login` |

Re-login as admin before continuing.

---

## 2. Tenancy & governance (B2/B3)

| # | Action | Expected |
| --- | --- | --- |
| 2.1 | Open the Organization switcher (top bar) | Shows **Organization Alpha** (only your orgs) |
| 2.2 | Open the Workspace switcher | Shows Alpha's workspaces; switching refetches data |
| 2.3 | Go to `/admin/members` | Members list loads from backend |
| 2.4 | (New tab) log in as `governance-viewer@vip.demo` | Read-only: create/delete actions hidden or blocked |
| 2.5 | As viewer, open a dashboard's ⋯ menu | No Delete/Archive (permission-gated) |

---

## 3. Connections & connector catalog (B4)

| # | Action | Expected |
| --- | --- | --- |
| 3.1 | Go to `/connections` | Existing connections list (≥1, e.g. a PostgreSQL) with health status |
| 3.2 | Open the ⋯ menu on a connection | Menu opens fully (not clipped); actions visible |
| 3.3 | Click **Test** on the PostgreSQL connection | Result **healthy** with latency (live test) |
| 3.4 | Go to **Connector catalog** | ~100 connectors; **"N available now"** count |
| 3.5 | Use the **Status** filter → *Available* | Shows PostgreSQL, REST API, Local file upload |
| 3.6 | Use the **Category** filter → *Databases* | Only database connectors |
| 3.7 | Search "snowflake" → click **View requirements** | Dialog shows status **Planned**, auth methods, network requirements; **no** Create button |
| 3.8 | (If mysql profile up) Filter *Beta* → **MySQL** → **Create connection** | Wizard opens |
| 3.9 | Fill MySQL: host `mysql`, port `3306`, db `vip_demo`, user `vip_reader`, SSL `disable`, password `vip_reader_dev` → Save → **Test** | **healthy** (live). Re-open: password never shown, only "configured" |
| 3.10 | Confirm no secret in the page (no plaintext password anywhere) | Only masked/"configured" indicators |

---

## 4. Datasets — including device upload (B5)

| # | Action | Expected |
| --- | --- | --- |
| 4.1 | Go to `/datasets` | Dataset list loads (search/filter/sort work) |
| 4.2 | Click **Import CSV** | Dialog "Import CSV dataset" opens |
| 4.3 | Click **Upload CSV file…**, choose `sample-data/vip_sales_sample.csv` | Filename shown; CSV text fills the box; **Target table** & **Display name** auto-fill |
| 4.4 | Pick the destination connection, click **Import and catalog** | Success toast; dataset appears in the list |
| 4.5 | Open the new dataset → **Data preview** tab | Rows render (region, revenue, …) from the backend |
| 4.6 | Open the **Profile** tab | Live statistics over sampled rows |
| 4.7 | **Excel test:** Import CSV → Upload → choose `vip_sales_sample.xlsx` | Clear message: "Excel workbooks are not parsed… Save As CSV". (Then convert in Excel and use 4.3.) |
| 4.8 | Open a dataset ⋯ menu | Menu opens fully; actions visible |

---

## 5. Semantic layer (B5)

| # | Action | Expected |
| --- | --- | --- |
| 5.1 | Go to `/semantic` | Semantic model list loads |
| 5.2 | Open a model | Dimensions / measures / metrics render from backend |
| 5.3 | Go to `/semantic/metrics` | Metrics & KPIs list loads |

---

## 6. Dashboards, Studio & export (B6/B6.5)

| # | Action | Expected |
| --- | --- | --- |
| 6.1 | Go to `/dashboards` | Dashboard cards load |
| 6.2 | Click a card's **⋯** menu | Menu opens fully (not clipped); Rename/Duplicate/Archive/Delete visible |
| 6.3 | Click **New dashboard** | Dashboard Studio opens |
| 6.4 | Add a widget (e.g., a **Text** or a chart), edit its title | Widget appears on the canvas |
| 6.5 | Click **Save** | Saves; URL becomes `/dashboards/<id>/edit`; reload keeps the layout |
| 6.6 | Click **Publish** | Status becomes **published** |
| 6.7 | **Share → Exports** tab, format **PDF**, **Queue export** | Job appears, progresses to **completed** |
| 6.8 | Click **Download** on the completed job | A real **.pdf** file downloads |
| 6.9 | Repeat 6.7–6.8 with **PNG** | A real **.png** downloads |
| 6.10 | On a *draft* dashboard, open **Share → Exports** | Notice "Publish this dashboard to enable exports"; Queue disabled |
| 6.11 | Back on the list, a test dashboard **⋯ → Delete** → type name → confirm | Row disappears; success toast; list refreshes |

---

## 7. Pipelines & async execution (B7)

| # | Action | Expected |
| --- | --- | --- |
| 7.1 | Go to `/pipelines` | Pipeline list loads |
| 7.2 | Click **New pipeline** | Pipeline Studio opens |
| 7.3 | Add a **Dataset** source node → source type **file** → upload `vip_sales_sample.csv` → **Upload and register** | "Bound N fields"; preview rows show |
| 7.4 | Add an output/protected-file node and connect the nodes | Edge created |
| 7.5 | Name the pipeline, click **Save** | URL becomes `/pipelines/<id>`; reload restores the graph |
| 7.6 | Click **Validate** | **Validation passed** |
| 7.7 | Click **Publish** | Immutable version created (201) |
| 7.8 | Click **Run** | Status progresses queued → running → **succeeded** with **Rows: N** (real worker) |
| 7.9 | Open logs/results | Node logs + result rows visible |

---

## 8. Security spot-checks

| # | Action | Expected |
| --- | --- | --- |
| 8.1 | As `governance-viewer`, try to delete a dashboard/connection | Denied (no control, or 403) |
| 8.2 | As `governance-restricted`, open studios | Restricted per role |
| 8.3 | Log out; visit `/dashboards` directly | Redirected to `/login` |
| 8.4 | Open browser DevTools → Network on any secret field | No plaintext secret in requests/responses |
| 8.5 | Open DevTools → Console during the whole run | **No unexpected errors** |

---

## 9. Responsive / accessibility spot-checks

| # | Action | Expected |
| --- | --- | --- |
| 9.1 | Resize to mobile (~390px) or DevTools device mode; open a dashboard ⋯ menu | Menu stays on-screen and usable; Delete reachable |
| 9.2 | Keyboard only: Tab to a ⋯ button, Enter, Arrow keys, Esc | Menu opens, navigates, Esc closes, focus returns |

---

## Do NOT test as "live" (mock/demo modules)
AI Studio, Automation, Billing, Marketplace, Insights, Reports, Operations (activity/audit/usage),
Developer portal, Home widgets — these render but use mock data (later phases).

## Pass criteria
All rows in sections 1–8 ✅, no unexpected console errors (8.5), and the full
**connect → upload → model → dashboard+export → pipeline run** path completes end-to-end.
