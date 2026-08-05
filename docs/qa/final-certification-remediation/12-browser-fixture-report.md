# Browser Fixture Report

`tests/e2e/run-local-certification.ps1` is the documented idempotent bootstrap command. It obtains current QA credentials from the protected local credential provider without printing or committing values, verifies named organizations/workspaces/personas, repairs only exact missing state, and provisions/resolves:

- `QA Browser Certification Dataset` on the exact destination connection;
- `QA Browser Certification Semantic Model` bound to that exact dataset;
- an exact deny for the explicitly denied persona on that model;
- the exact healthy PostgreSQL destination `QA_PostgreSQL_Valid`;
- current organization/workspace and role/ACL persona mappings.

The governed pipeline test rejects duplicate names, non-PostgreSQL types, and unhealthy connections; it never chooses by list position. Result: 10/10 first attempts.

The bootstrap is local/CI compatible, idempotent by immutable key/name, does not delete legitimate data, and uses exact IDs for any test-owned cleanup. One exact failed quota-test workspace was archived during diagnosis; normal governed-pipeline test resources were cleaned by their own exact-ID teardown. Older QA artifacts were retained because safe ownership for broad cleanup was not established.
