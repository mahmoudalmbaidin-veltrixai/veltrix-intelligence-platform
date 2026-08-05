# Module Test Matrix

| Module | Evidence | Fail/blocked | Readiness |
|---|---|---|---|
| Authentication/session | Unit, integration, Chromium, Firefox | Firefox suite timeout passed on retry; archive unsupported | Conditional |
| Tenancy/admin/RBAC | Integration governance/persona/security tests; browser admin | Four legacy browser tests blocked by unavailable demo passwords | Conditional |
| Connections | PostgreSQL/MySQL live positive; invalid credential; browser persona tests | Unreachable/timeout/rotation concurrency not fully certified | Conditional |
| Datasets/files | Live CSV upload, preview/profile; unit/integration | Full format/size/malware matrix incomplete; XLSX unsupported | Blocked |
| Semantic | Unit/integration and persona browser coverage | Exhaustive formula/dependency matrix incomplete | Conditional |
| Pipelines | Live upload→publish→worker→profile; integration transforms/ACL | Full every-node/function matrix not manually enumerated | Conditional |
| Dashboards | Studio/action/share/a11y tests; worker integration | Firefox order/timing flake; export parity matrix incomplete | Blocked |
| Reports/exports/email | Worker/unit/integration coverage present | UI/report module parity and full delivery matrix incomplete/placeholder | Blocked |
| Scheduler/jobs | Integration coverage | Reliability/load/restart/outage matrix incomplete | Blocked |
| Notifications | Route/unit coverage | No exhaustive delivery/isolation matrix | Blocked |
| Platform operations/audit | Browser platform console; integration audit | Full search/filter/pagination matrix incomplete | Conditional |
| Billing/marketplace/developer/automation/AI/insights | Route inventory | Deliberate mocks/placeholders or feature-gated | Blocked |

No result was fabricated for a placeholder or unexercised path.
