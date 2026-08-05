# Full Regression Results

| Check | Command summary | Result |
|---|---|---|
| Ruff lint | `uv run ruff check .` | Pass |
| Ruff format | `uv run ruff format --check .` | 245 files formatted |
| Mypy strict | `uv run mypy` | 218 files, no issues |
| Backend non-integration | `uv run pytest -m 'not integration' -q` | 240 passed, 60 deselected |
| Backend integration run 1 | live `vip_test` + Redis 15 | 60 passed, 240 deselected |
| Backend integration run 2 | same isolated services | 59 passed, 1 setup error (DB connect timeout) |
| Failed case retry | password recovery case | 1 passed |
| Backend integration run 3 | same isolated services | 59 passed, 1 failure (different DB connect timeout) |
| Frontend lint/type/format | `pnpm lint`, `pnpm typecheck`, `pnpm format:check` | Pass |
| Frontend unit | `pnpm test` | 45 files, 279 passed |
| Frontend build | `pnpm build` | Pass; 535 modules |
| Chromium core initial | live services | 41 passed, 2 fixture failures; affected tests later passed |
| Firefox core | live services | 35 passed, 3 failed; 2 passed in isolated triage; dashboard flake persisted then passed twice |
| Accessibility | high-DPI Chromium | 18 passed |
| Mobile | Chromium 390×844/320px | 5 passed |
| Security-marked tests | included in clean unit/integration runs | 18 passed |
| Worker/job/scheduler-related tests | included in clean unit/integration runs | 48 passed |
| Alembic | heads/current | one head `20260803_0019` |

Two skip/error harness attempts were rejected from pass totals: one omitted `RUN_INTEGRATION_TESTS`, and one used the wrong local database password. The two-repeat clean-integration exit criterion is not met.
