# Audit prompt (reuse)

Paste the operator prompt below into a new agent session after checking out the target SHA. Do not edit product code to make the audit pass.

The prompt is the original **FINAL ADVERSARIAL PRODUCT READINESS, LIVE-SERVICE, AND RESELL CERTIFICATION AUDIT** specification (Parts 1–36).

Keep these non-negotiables:

- Do not compliment the product.
- Do not protect previous certifications.
- Do not assume code existence equals production readiness.
- Do not classify file-outbox email, mock UI, empty catalogs, or local-only storage as live.
- Record the exact SHA in `CURRENT_BASELINE.md` and write a new file under `reports/` (never overwrite an old report).
- Write `reports/<date>-<shortsha>-scorecard.json` for regression comparison.
- Do not save passwords, tokens, API keys, or production customer data.

After scoring, update:

1. `CURRENT_BASELINE.md`
2. A new markdown report in `reports/`
3. A new JSON scorecard in `reports/`
4. The comparison table against the previous scorecard

Scoring rules: `SCORING_MODEL.md`.
Checklist: `AUDIT_CHECKLIST.md`.
