# VIP Final Product Certification Audit

Repeatable adversarial certification for demo, pilot, production, enterprise, and resell readiness.

This package is **documentation and measurement only**. It does not change product behavior.

## Current certified baseline

See [CURRENT_BASELINE.md](CURRENT_BASELINE.md) and the latest report under [reports/](reports/).

**Reference SHA for this package's first run:** `fa02d9e2484f6b603efe5af9e7586975342b485c`

## Workflow

1. Checkout the target SHA.
2. Start required services (`docker compose up -d` plus frontend `npm run dev` if browser checks are in scope).
3. Verify environment (`/health`, `/ready`, Alembic head, worker heartbeats).
4. Run static gates (optional; do not treat pass as production proof).
5. Run backend tests (optional evidence, not a readiness substitute).
6. Run frontend tests (optional).
7. Run browser tests (optional).
8. Run product journey tests / live API probe.
9. Run infrastructure and configuration checks.
10. Perform defined manual audits.
11. Generate the scorecard using [SCORING_MODEL.md](SCORING_MODEL.md).
12. Compare with the previous certification using the JSON snapshot in `reports/`.

Windows (this repository's primary local environment):

```powershell
.\scripts\certification\run-product-certification.ps1
```

Make target (same script):

```bash
make product-certification
```

The collector records SHA, service health, Alembic head, and configuration **names** only. It does not print secrets.

## Rules

- Do not mark a capability ready because code or tests exist.
- File-outbox email is not live email.
- Mock, gated, empty-catalog, and development-only surfaces are not V1 product.
- The runtime database is not implied by the Git SHA. Record both.
- Do not copy passwords, tokens, or API keys into reports.

## Files

| File | Purpose |
| --- | --- |
| [AUDIT_PROMPT.md](AUDIT_PROMPT.md) | Full adversarial prompt for a future re-run |
| [AUDIT_CHECKLIST.md](AUDIT_CHECKLIST.md) | Automated vs manual checks |
| [SCORING_MODEL.md](SCORING_MODEL.md) | 0–10 dimensions, verdicts, stage scores |
| [CURRENT_BASELINE.md](CURRENT_BASELINE.md) | Exact SHA and runtime of the last run |
| [reports/](reports/) | Immutable dated reports + machine-readable scorecards |
