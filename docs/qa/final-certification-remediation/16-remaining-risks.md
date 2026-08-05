# Remaining Risks

No known release-blocking defect remains in the authoritative audit list.

Residual non-blocking risks for the independent certifier:

- Static exports intentionally do not execute hover/click/drill interactions; the complete interaction definition is preserved in machine-readable metadata and should be independently compared.
- Export rendering can vary slightly with host font rasterization. The implementation resolves production-safe fonts, and the included deterministic evidence hashes apply to this environment.
- Server-side image export does not fetch arbitrary remote image URLs because that would introduce SSRF risk; canonical image configuration/alt/content remains lossless.
- Existing historical QA artifacts were retained when exact ownership could not be proven. They do not affect deterministic exact-name fixture selection.
- The API matrix is classification plus mapped domain/security tests, not a blind happy-path mutation of every destructive endpoint. The independent reviewer should inspect mappings for appropriateness as well as count.

No migration, schema reset, timeout increase, test skip, weakened assertion, authorization relaxation, or production TLS downgrade was used.
