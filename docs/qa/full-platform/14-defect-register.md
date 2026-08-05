# Defect Register

| ID | Severity | Defect / evidence | State |
|---|---|---|---|
| VIP-QA-001 | Critical | Several advertised modules are mock/placeholder/feature-gated in live mode | Open blocker |
| VIP-QA-002 | High | Full 247-operation API negative/contract matrix not executed | Coverage blocker |
| VIP-QA-003 | High | Full controlled dataset corpus incomplete; XLSX rejected as unsupported/ZIP container | Open blocker |
| VIP-QA-004 | High | Firefox dashboard first-save navigation is order/timing flaky (2 fail, 2 pass) | Open |
| VIP-QA-005 | High | Repeat integration runs each hit a different >2s PostgreSQL connect timeout (59/60) | Open reliability blocker |
| VIP-QA-006 | Medium | WebKit unavailable | Environment blocker |
| VIP-QA-007 | Medium | Archived-user lifecycle not supported; candidate stays active | Product limitation |
| VIP-QA-008 | Medium | Four legacy tenant E2E cases require unavailable demo passwords | Harness blocker |
| VIP-QA-009 | Medium | Full dashboard export parity and report/email matrix incomplete | Coverage blocker |
| VIP-QA-010 | Medium | Full load/outage/recovery matrix incomplete | Coverage blocker |
| VIP-QA-011 | Low | Route smoke formerly reported Firefox object errors as `JSHandle@object` | Fixed |
| VIP-QA-012 | Low | Pipeline E2E selected first connection, allowing wrong connector type | Fixed |

Machine-readable detail is in `defects.json`.
