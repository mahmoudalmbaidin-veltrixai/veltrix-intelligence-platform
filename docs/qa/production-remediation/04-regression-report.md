# Regression Report

## Required reliability evidence

| Gate | Result |
|---|---:|
| Firefox dashboard save, uninterrupted repeat | **20/20 passed** in 6.8 minutes |
| PostgreSQL original suite run 1 | **60/60 passed** in 134.23 s |
| PostgreSQL original suite run 2 | **60/60 passed** in 128.27 s |
| PostgreSQL original suite run 3 | **60/60 passed** in 98.32 s |
| Final integration suite plus contract sweep | **61/61 passed** in 62.47 s |

The Firefox regression observed one dashboard create and one editor update per run despite a deliberate duplicate keyboard-save dispatch. All runs reached the stable dashboard ID route and saved status.

## Consolidated regression

| Layer | Result |
|---|---:|
| Backend unit | **243/243 passed** (final rerun 5.28 s) |
| Backend integration | **61/61 passed** |
| Frontend unit | **280/280 passed** across 46 files |
| Frontend production build/typecheck | **passed**, 535 modules transformed |
| Frontend ESLint | **passed** |
| Backend Ruff | **passed** |
| Backend mypy | **passed**, 165 source files |
| Dashboard delivery targeted unit | **9/9 passed** |
| Dashboard lifecycle/persistence/scheduler integration | **7/7 passed** |
| Dashboard mapper targeted frontend | **16/16 passed** across 3 files |
| Chromium dashboard/studio/route/pipeline-authoring selection | **9/9 product assertions passed** |
| Accessibility, Chromium | **18/18 passed**, no critical/serious axe findings |

Two additional B9 browser cases did not reach product assertions: one legacy persona login returned 401 because `governance-admin@vip.demo` is not present in the current QA credential vault, and one initial Vite navigation timed out. These are retained as fixture/environment evidence and were not converted to mocks or disabled. The same run passed both pipeline-authoring scenarios, while backend pipeline/permission behavior passed in the integration suite.

## Export evidence

- Reproducible PDF, PNG, CSV, JSON and manifest generated successfully.
- PDF page rendered through Poppler and visually inspected.
- PNG visually inspected.
- Both showed the same widget grid, labels, values, formatting, and connected Arabic text.
- Scheduled attachment unit regression verifies exact output bytes.

## Runtime image verification

API, dashboard worker, pipeline worker, PostgreSQL, Redis, and supporting services were rebuilt/started from the final lock. API health returned 200. The production container reports `arabic-reshaper 3.0.1` and `python-bidi 0.6.11`.

No test was disabled, mocked in place of an integration, or made green by increasing the PostgreSQL timeout.

