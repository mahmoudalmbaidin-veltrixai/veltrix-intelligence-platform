# QA Data Catalog

Organizations: `QA_Enterprise_A_20260804` (`17a4e171-ced9-40cf-883d-e42ff2dc4267`) and `QA_Enterprise_B_20260804` (`e1520ab1-01e5-4623-91d2-1e6b4cb70696`). Each has Default plus two named QA workspaces. QA A groups are `QA_Group_Role_Assignees` and `QA_Group_Resource_Access`.

Controlled connections in QA A Default:

| Name | Type | Expected/result |
|---|---|---|
| `QA_PostgreSQL_Valid` | PostgreSQL | healthy; live test success |
| `QA_PostgreSQL_Invalid_Credentials` | PostgreSQL | unhealthy; `CONNECTION_AUTHENTICATION_FAILED` |
| `QA_PostgreSQL_Unreachable` | PostgreSQL | unknown/unreachable scenario retained |
| `QA_MySQL_Valid` | MySQL | healthy; live test success |

Browser journeys created traceable dashboards, datasets, pipelines, files, audit events, and three `E2E Client *` organizations. Successful pipeline tests soft-deleted/archived their logical resources, which remain visible in the persistence inventory by design.

CSV ingestion was verified with the repository certification sample. Existing sample assets cover CSV/JSON/XLSX content, but the full requested dataset corpus was not created. XLSX upload is blocked by the file service's supported MIME/extension list, and ZIP-signature validation rejects XLSX containers. Invalid, large, empty, malformed, schema-evolution, high-column, formula-injection, and every Unicode/date variant were not all exercised live; this is a certification blocker.
