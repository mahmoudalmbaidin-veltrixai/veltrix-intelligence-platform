# Phase 2 regression summary

Date: 2026-08-10 (Asia/Riyadh)

- Backend unit: 270 passed.
- Focused Phase 2 backend: 59 passed after final formatting.
- Backend integration full directory: 94 passed, 2 failed only on the excluded
  OpenAPI 255-versus-256 inventory drift assertions.
- Semantic parity harness: 24 passed.
- Real 20-widget worker lifecycle: 1 passed in 15.17 seconds.
- Frontend unit/component: 315 passed across 54 files.
- Chromium configured Pivot/Scatter lifecycle: PASS (6.0 seconds).
- Firefox configured Pivot/Scatter lifecycle: PASS (9.6 seconds).
- WebKit configured Pivot/Scatter lifecycle: PASS (8.9 seconds).
- Chromium/Firefox/WebKit Phase 1 bounded hydration and atomic first save: 3 passed.
- Ruff check: PASS; Ruff format check: PASS (263 files).
- Targeted mypy for all changed production modules: PASS.
- Full mypy: two pre-existing `Settings()` call-site errors in
  `vip_api/core/config.py:358`; no changed Phase 2 module errors.
- Frontend scoped lint (`src`, `tests`): PASS. The repository-wide lint command
  also traverses retained generated Playwright trace JavaScript under the
  pre-existing untracked evidence tree and fails there; source lint is clean.
- Frontend typecheck: PASS.
- Frontend Prettier check: PASS.
- Production build: PASS.
