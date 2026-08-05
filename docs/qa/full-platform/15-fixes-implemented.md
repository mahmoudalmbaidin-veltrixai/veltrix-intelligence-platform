# Fixes Implemented

| ID | Root cause | Minimum fix | Evidence |
|---|---|---|---|
| VIP-QA-011 | `ConsoleMessage.text()` is opaque for object arguments in Firefox | Serialize console arguments and source location; await pending serialization | Route smoke passed in isolated Firefox rerun |
| VIP-QA-012 | E2E selected destination connection by list index | Add `VIP_E2E_DESTINATION_CONNECTION_NAME`; resolve the option by stable name prefix/value | Full pipeline E2E passed in Chromium, and in the Firefox 35/38 run |
| VIP-QA-013 | Auth fixture hard-coded `Organization Alpha` | Add `VIP_E2E_ORGANIZATION_NAME` | QA A Chromium/Firefox suites entered the isolated tenant |
| VIP-QA-014 | Platform-admin negative test hard-coded a demo user | Add explicit normal-user email/password variables | Super-admin and normal-user targeted rerun passed |
| VIP-QA-015 | Manual persona construction was error-prone/interrupted | Add idempotent seed/resume, bootstrap reset, and DPAPI retrieval scripts | 38 users, 2 orgs, 6 workspaces, 13 roles, 2 groups verified |

No application authorization was weakened. No migration was added. No unrelated subsystem was refactored.
