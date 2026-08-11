# Dataset Version E2E evidence (VIP-BUG-010)

- Obsolete assertion `Version history unavailable` removed
- Test now requires a visible `.dd__version` entry with version number, type badge (created/certified/restored), timestamp, and change note
- Chrome desktop result: **PASSED** (2026-08-11 Phase 4 remediation run)
- Backend integration `test_dataset_versions.py`: included in 28-pass unit/integration focused run
