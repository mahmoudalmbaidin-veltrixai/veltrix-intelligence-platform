# Security and Negative Test Report

Passing automated coverage includes generic invalid-login responses, inactive/suspended handling, refresh replay, CSRF, cookie flags, session revocation, tenancy repository filters, organization/workspace isolation, custom-role isolation, privilege ceilings, group-assignment ceilings, explicit deny/expiry, ACL elevation prevention, pipeline action matrices, connection secret sanitization/destination blocking, quota enforcement, and direct API denial for viewer/restricted personas.

QA B contains the cross-tenant attacker persona; QA A/B immutable IDs are available for manual IDOR verification. The suspended persona is truly suspended. The archived persona is only a candidate because user archival is unsupported. Connection secrets are encrypted in the database, masked in responses, and absent from committed artifacts/log excerpts.

Not exhaustively completed: every 247-endpoint negative permutation, safe SQL/NoSQL injection corpus, stored/reflected XSS corpus, path traversal/unsafe filenames, CSV formula injection through every export, CORS matrix, brute-force timing, signed-URL expiry/cross-tenant matrix, cross-workspace ACL creation for all principals, and soft-delete access for all resources. No external system was attacked.
