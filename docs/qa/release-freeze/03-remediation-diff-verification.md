# Remediation Diff Verification

The release manager inspected implementation and tests rather than relying only on QA
reports. The tracked diff passed `git diff --check`; it contains 60 modified files,
2,744 insertions, and 587 deletions before newly added files are included.

| Claimed remediation | Repository evidence | Freeze result |
| --- | --- | --- |
| Deterministic login/bootstrap | Auth store generation guard and joined bootstrap promise; post-login session confirmation; tenant bootstrap before success; one checked router replacement; auth behavioral tests | Found |
| Dashboard single-flight save | Joined save promise, immutable request snapshot, dirty revision preservation, publish prerequisite, one-time navigation bypass, conflict/error tests | Found |
| Save failure behavioral coverage | Dashboard Studio tests cover failed create/update, 409/422/500, joined saves, later edits, publish failure, leave guard, navigation rejection, duplicate and autosave interaction, refresh | Found |
| Canonical parity manifest / CSV v2 | One immutable published snapshot is carried by `RenderDocument`; JSON and CSV preserve it; PDF/PNG embed it; CSV includes widget definitions and data sections | Found |
| PDF/PNG and Arabic/BiDi | Per-widget deterministic rendering, format/conditional/legend helpers, Arabic reshaping, BiDi ordering, wrapping, and bundled production-safe fonts | Found |
| All 20 widgets | Shared 20-type fixtures, real save/publish/export integration lifecycle, rendering assertions, and selected sanitized output evidence | Found |
| AI fail-closed | `developmentMockOnly` route/navigation metadata, live-mode router denial, palette/search/quick-action suppression, and four-way flag/entitlement tests | Found |
| Authenticated API coverage | OpenAPI-derived 247-operation classification plus real-database authenticated, suspended, forbidden, cross-tenant, invalid-input, and schema sweeps | Found |
| MyPy corrections | Narrow config typing correction and explicit string return around Arabic display helper; no broad ignore added | Found |
| Self-contained browser fixtures | DPAPI-backed ephemeral persona credentials, idempotent fixture verification/repair, exact resource names/IDs, local wrapper, CI provisioning | Found |
| Deterministic PostgreSQL pipeline target | Exact immutable QA connection name, exactly-one check, PostgreSQL type check, and health check | Found |
| Event-driven route smoke | Fixed waits removed; URL, response, loading, readiness, and locator assertions used | Found |
| Credential artifact sanitation | Playwright input redaction, global teardown sanitizer, CI sanitation and upload ordering, artifact secret scan | Found |
| SSE rate-limit session scoping | Rate key includes organization, workspace, user, and authenticated session identifiers | Found |
| Local integration `ssl=disable` only | Query parameter appears in integration `conftest.py`; production settings and database engine retain normal URL/TLS handling | Found |

No Alembic version was modified or added. No claim in the blocker matrix was missing
from source. The full post-commit release gates remain authoritative for the freeze.

