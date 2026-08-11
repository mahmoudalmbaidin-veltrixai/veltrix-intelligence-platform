# Phase 4 QA cleanup evidence

Architecture:
- Run IDs: `qa-cert-YYYYMMDD-<8 hex>`
- Registry: `vip_api.qa.CertificationFixtureRegistry` (+ browser helper `tests/e2e/helpers/certification-lifecycle.ts`)
- Cleanup uses exact registered IDs in dependency-safe order
- Environment guard refuses non-test environments
- Stale-name reporter (`identify_likely_stale_names` / `--report-stale`) lists candidates without deleting ambiguous data

Sample cleanup report from unit exercise:

```json
{
  "created": 2,
  "deleted": ["dataset:..."],
  "retained": ["file:..."],
  "failures": []
}
```

CLI: `python -m apps.api.scripts` path `apps/api/scripts/qa_certification_cleanup.py`
