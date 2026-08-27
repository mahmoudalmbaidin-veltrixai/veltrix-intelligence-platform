# Scoring model

## Principle

An **80+** module or category score means the auditor would deploy that capability for a paying customer on this revision, in a real hosted environment, without founder babysitting.

Tests passing, UI existing, or prior certifications existing **do not** raise a score.

## Module dimensions (0–10 each)

1. Functional completeness
2. UI/UX quality
3. Backend completeness
4. Data integrity
5. Reliability
6. Error handling
7. Security
8. RBAC correctness
9. Performance
10. Production readiness
11. Enterprise readiness
12. Commercial/resell readiness

**Module Readiness Score /100** = round(sum(dimensions) / 12 × 10)

The summary table may collapse related dimensions:

| Table column | Source dimensions |
| --- | --- |
| Functionality | 1, 4 |
| UX | 2 |
| Backend | 3 |
| Reliability | 5, 6, 9 |
| Security | 7, 8 |
| Production | 10 |
| Enterprise | 11 |
| Resell | 12 |
| Overall /100 | all 12 |

## Verdicts (use exactly one per module)

| Verdict | Meaning |
| --- | --- |
| NOT IMPLEMENTED | No usable customer path |
| PLACEHOLDER | Route/API/catalog exists; empty or stubbed |
| MOCK / DEVELOPMENT ONLY | Works only in mock mode, file outbox, or APP_ENV development tricks |
| BROKEN | Implemented path fails under live use |
| PARTIAL | Some real path exists; cannot be sold as complete |
| DEMO READY | Can be shown by a trained presenter with scripted data |
| PILOT READY | A supervised customer can use it with written limitations |
| PRODUCTION READY | Paying customer, hosted, supported, without daily founder intervention |
| ENTERPRISE READY | Survives CIO/CISO/procurement questions for this capability |

## Stage scores

| Score | Question |
| --- | --- |
| Demo Readiness | Can a trained presenter show the V1 path without lying? |
| Pilot Readiness | Can one supervised customer use it for weeks? |
| Production Readiness | Can Veltrix host and charge with operational honesty? |
| Enterprise Readiness | Can a CISO/procurement process be answered with evidence? |
| Resell Readiness | Can this be packaged and sold repeatedly? |

## Final letter verdict (exactly one)

| Grade | Meaning |
| --- | --- |
| F | NOT DEMO READY |
| E | INTERNAL DEMO READY ONLY |
| D | CLIENT DEMO READY |
| C | PILOT READY |
| B | PRODUCTION READY WITH LIMITED COMMERCIAL SCOPE |
| A | MARKET-READY V1 PRODUCT |

Do not award **A** unless Veltrix can sell, onboard, and support a paying customer on the exact SHA and a real hosted environment.

## Regression snapshot

Each report must write `reports/<date>-<sha>-scorecard.json` with the numeric fields listed in the prompt Part 36 so a later audit can compute deltas instead of “it seems better.”
