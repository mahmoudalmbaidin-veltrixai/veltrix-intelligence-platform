# QA User Persona Matrix

All users use `qa_<purpose>` usernames and `@vip.qa.local` synthetic addresses. Passwords are unique and retrievable only through the local DPAPI mechanism described in the UAT guide.

| Personas | Organization/workspace | Expected access | Expected denial |
|---|---|---|---|
| Platform Super Admin | Both QA orgs | Platform console and tenant bypass | Archived-state protections still apply |
| Platform Support Admin | Both QA orgs | Organization support/admin paths | No full super-admin authority |
| Organization Admin / Member | QA A | Admin / baseline membership | Member cannot administer platform |
| Workspace Admin / Editor / Operator / Viewer | QA A Default/Analytics | Role-bounded workspace actions | Higher actions hidden and API-forbidden |
| Custom Role / Group Role | QA A | Custom or group-resolved permissions | No implicit tenant-wide elevation |
| Direct ACL / Group ACL / Explicit Deny / Expired | QA A | Resource-specific precedence scenarios | Deny/expiry must fail closed |
| Suspended / Archived candidate | QA A | Suspended login denied | Archive is unsupported; candidate remains active |
| Cross-Tenant Attacker | QA B | QA B only | QA A UUIDs must be non-disclosing |
| Dataset Query / Editor / Certifier | QA A | Separated dataset operations | No privilege substitution |
| Pipeline Owner / Developer / Operator / Viewer | QA A | Ownership, edit, run, view matrix | No higher pipeline operation |
| Dashboard Viewer / Interactive / Editor / Manager | QA A | Dashboard action matrix | No export/manage elevation |
| Connection Use / Test / Edit / Rotate / Admin | QA A | Split connection capabilities | Secrets never retrievable |
| Semantic Query / Report Consumer / Scheduler / File Upload / API Developer | QA A | Specialized feature paths | Unrelated mutations denied |

There are 38 personas total. Detailed identifiers are in `qa-users.json`; direct assignments, groups, expiry, and expected resources are in the ignored local `qa-resource-manifest.json`.
