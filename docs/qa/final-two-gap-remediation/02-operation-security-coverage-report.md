# Operation-Level Security Coverage

## Contract

Applicable-dimension rules are explicit in `vip_api.api.operation_coverage`. The
generator validates every evidence test ID against a real test function and fails when
a required dimension is absent, an unsupported dimension is claimed, or an executed
dimension lacks an exact passing observation with persona, resource, and HTTP status.

Classification-only output does not claim execution. Execution output distinguishes
required, applicable, executed, passed, not applicable, and unavailable/fail-closed
states per operation.

## Observed summary

- Paths: 192
- Operations classified/mapped/generically probed/executed/passed: 247/247
- Unsupported claims: 0
- Claimed dimensions without evidence: 0
- Authenticated success and response-schema validation: 43 each
- Authenticated empty-payload and invalid-payload validation: 95 each
- Direct ACL allow/deny: 5/4
- Group ACL allow/deny: 4/4
- Explicit deny: 4
- Suspended-user probes/rejections: 240/240
- Cross-tenant header/isolation probes: 205/205
- Real cross-tenant resource probes: 8
- Restricted-role probes and observed forbidden responses: 205/118
- Payload/query lower and upper bounds: 11/11
- Pagination/filter validation: 11/1
- Authenticated invalid UUID probes: 169
- Authenticated successful schema validations: 43

Empty or malformed bodies are claimed only when separate authenticated requests reached
validation and returned 422. Invalid UUID observations use authenticated requests and
are not substituted for ACL or cross-tenant resource tests. The real dashboard ACL
sequence creates owned resources and exercises direct allow/deny, group allow/deny,
explicit deny, effective access, simulation, and exact revocation. Suspended sessions
are established while active and then tested after direct database suspension.

The report intentionally does not claim that every operation has an authenticated
success. It records the exact 43 successes reached by the sweep and retains domain-test
links for operation-specific behavior. Placeholder/unavailable behavior is represented
as fail-closed rather than a false success.

The generated report was regenerated from its own execution evidence; the source and
regenerated SHA-256 were identical:
`a35d63e1afb4d3b8983b61d63ed09f6b6dcf3096b41afb63ca6a2e83ad892c32`.
