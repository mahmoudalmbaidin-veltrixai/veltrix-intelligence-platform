# Regression Results

## Final results

| Gate | Result |
| --- | --- |
| Ruff | pass |
| Ruff format | pass, 253 files formatted |
| MyPy `src tests` | pass, zero errors |
| Backend unit | 255/255 |
| PostgreSQL integration | 66/66, 66/66, 66/66; timeout 2.0 seconds |
| Frontend ESLint/typecheck/format | pass/pass/pass |
| Frontend unit | 303/303 |
| Production build | pass |
| Firefox dashboard reliability | 20/20 and 20/20; zero retries |
| Chromium full | 66/66 |
| Firefox full | 66/66 |
| WebKit full | 66/66 |
| High-DPI | 23/23 first attempt |
| Mobile | 5/5 |
| Governed pipeline | 10/10 first attempt |
| Four-format real lifecycle | 4/4 formats, same published version |
| API operation evidence | 247/247 executed/passed; zero unsupported claims |
| AI direct API fail-closed | pass in full integration suite |
| Dynamic artifact sanitizer | 2/2; final scan zero findings |
| Alembic current/heads/check | `20260803_0019`; one head; no operations |

## First-attempt and retry history

- Ruff first attempt: pass.
- Ruff formatting first attempt: fail on one new test expression; formatted and passed
  on the second attempt.
- MyPy first attempt: three errors caused by a `Path` variable shadowing a schedule
  variable in new lifecycle test code; renamed and passed on the second attempt.
- Backend unit first attempt: 255/255 pass.
- Frontend gates: all passed on their first attempts.
- Integration full runs: all three passed on first attempts, 66/66 each.
- First Alembic command batch omitted required test `REDIS_URL`; `heads` reported the
  expected head but database-dependent commands did not execute. With the complete
  documented test environment, current, heads, and check all passed. This was a command
  setup error, not a migration retry.
- Every browser gate listed above passed its sole first attempt. No Playwright retry
  converted a failed test into a pass.

Targeted implementation-test failures during development are detailed in the lifecycle
and security reports and are not erased by the final green runs.
