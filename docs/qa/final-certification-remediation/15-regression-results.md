# Regression Results

## Final clean gates

| Suite | First-attempt result |
|---|---|
| Backend unit | 249/249 |
| PostgreSQL integration run 1 | 64/64, 93.43s |
| PostgreSQL integration run 2 | 64/64, 86.95s |
| PostgreSQL integration run 3 | 64/64, 82.31s |
| Frontend unit | 303/303 across 49 files |
| Firefox dashboard batch 1 | 20/20 |
| Firefox dashboard batch 2 | 20/20 |
| Governed pipeline | 10/10 |
| Chromium full browser | 66/66 |
| Firefox full browser | 66/66 |
| WebKit final full browser | 66/66 |
| Accessibility/high-DPI/mobile | 28/28 (18 accessibility, 5 high-DPI mobile tags, 5 mobile viewport) |
| Focus regression Chrome+Firefox | 6/6 |
| API operation classification | 247/247 |
| All-widget parity rows | 20/20 across 11 channels |
| Artifact secret scan | 0 findings |
| Production build/static/Alembic | all pass |

Integration count is 64 rather than the older requested 61 because three real contract/lifecycle tests were added; the required 61 are included, not skipped.

## First failures and retries retained

- Pre-fix Chromium: 42/48; six deterministic fixture/test defects. Post-fix full run: 48/48.
- Tenant-persona refactor: 2/4 first run; corrected run 4/4.
- Initial WebKit launch: 0/48 infrastructure failures because the pinned runtime was absent. After installation, first product run: 45/48; three focus-restoration defects. Focused correction: 3/3, cross-browser check 6/6, final full WebKit 48/48.
- All-widget lifecycle: two runs reached product assertions but failed teardown ordering; corrected exact teardown run 1/1.
- Final Firefox selector attempt: 0 tests matched (setup-only); corrected final batches were 20/20 and 20/20.
- Initial Alembic check: setup-only missing `REDIS_URL`; corrected run reached product checks and passed.
- Initial standalone API coverage generation: setup-only missing database/Redis settings; corrected full-environment generation classified 247/247.
- Final-tree Firefox full run before SSE correction: 65/66; route smoke received one 429 from the user-shared event-subscription bucket. Artifact sanitation made 11 redactions and left zero findings. Session-scoped rate limiting was added; the corrected full run passed 66/66, followed by WebKit 66/66 and Chromium 66/66.

No Playwright retry was enabled. Setup failures are not counted as product passes.
