# Release Gate Results

All final product gates ran from committed product/test SHA
`1e286a20eb535633a3eb341a2e0d3e38693fa5ac`. Retries are reported separately.

## First-failure history

The first exact MyPy run (`mypy src tests`) failed with five test-only annotation errors
and a MyPy internal error caused by an untyped nested assignment. Ruff and Ruff format
had already passed. The earlier remediation report used narrower `mypy src`, so it did
not exercise these test annotations. The first corrected MyPy rerun found one remaining
Pillow metadata annotation error. After the second narrow correction, targeted renderer
tests passed 13/13 and the third MyPy attempt passed 0 errors across 221 files. Two test
files received explicit annotations and casts; no application behavior or assertion was
weakened.

The parallel frontend result from the aborted first orchestration was not treated as a
pass because its output was not returned. Every frontend gate was rerun independently.
No browser or integration retry was required.

## Final clean results

| Gate | Final result | First run / retry accounting |
| --- | --- | --- |
| Ruff | pass | first reported run passed |
| Ruff formatting | 252 files formatted | first reported run passed |
| MyPy `src tests` | 0 errors / 221 files | attempt 1: five errors/internal error; attempt 2: one error; attempt 3: passed |
| Backend unit | 249 passed, 64 deselected | final run passed |
| PostgreSQL integration | 64 passed, 249 deselected in 89.73s | first run passed; 2.0s timeout unchanged |
| Frontend ESLint | pass | independent final run passed |
| Frontend typecheck | pass | independent final run passed |
| Frontend format | pass | independent final run passed |
| Frontend unit | 303/303 in 49 files | independent final run passed |
| Production build | 538 modules transformed | independent final run passed |
| Firefox dashboard-save | 1/1 | first run passed |
| Chromium core/route/AI | 3/3 | first run passed |
| WebKit core/route/AI | 3/3 | first run passed |
| Governed PostgreSQL pipeline | 1/1 | first run passed |
| AI flag/entitlement matrix | 5/5 | targeted run passed |
| Alembic current / heads | `20260803_0019` / one head | pass |
| Alembic check | no new upgrade operations | pass |
| API operation classification | 247/247 | committed artifact validated |
| Widget parity evidence | 20 widgets; PDF/PNG/CSV/JSON hashes 4/4 | committed artifact validated |
| Browser artifact secrets | 0 findings across 39 exact/canary values | final scan passed |
| Repository secret audit | 0 high-risk findings across 705 tracked files | final scan passed |

This is a release-freeze sanity suite, not the independent 20-run certification matrix.
The independent commands are in `07-independent-certification-handoff.md`.
