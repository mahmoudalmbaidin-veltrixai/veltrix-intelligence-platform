# Static Analysis Report

Final commands and results:

| Gate | Result |
|---|---|
| `uv run ruff check .` | pass |
| `uv run ruff format --check .` | pass, 252 files |
| `uv run mypy src` | pass, zero errors in 166 source files |
| `npm run lint -- --quiet` | pass |
| `npm run typecheck` | pass |
| `npm run format:check` | pass |
| `npm run build` | pass, 538 modules transformed |
| `uv run alembic current` | `20260803_0019 (head)` |
| `uv run alembic check` | no new upgrade operations detected |

MyPy corrections were narrow: remove the stale `core/config.py` ignore and explicitly convert the untyped bidi helper output to `str`. No broad ignore was added.

One initial Alembic invocation did not reach Alembic because the standalone shell omitted required `REDIS_URL`; the corrected full-environment command passed and the setup-only failure is retained in the regression report.
