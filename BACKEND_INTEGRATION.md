# Backend Integration Map

Every mocked service documents its intended backend contract inline (search
`INTEGRATION POINT`). This file is the consolidated map. All endpoints are
workspace-scoped and require the noted permission; the backend is the security
boundary (frontend checks are UX only).

## Auth / tenancy (prerequisite)
- `GET  /api/v1/me` → `AuthContext` (user, org, workspace, role, permissions, entitlements, feature flags)
- `GET  /api/v1/organizations`, `GET /api/v1/workspaces`
- Org/workspace switch, session, MFA, SSO — currently simulated in `platform` store.

## Semantic layer (powers dashboards, insights, explore, home)
- `GET  /api/v1/semantic/models` → `SemanticModel[]`
- `POST /api/v1/semantic/query` body `SemanticQuery` → `QueryResult`  ← **the key analytics seam**
- perms: `semantic:read`

## Pipelines
- `GET  /api/v1/pipelines` → `PipelineListItem[]`
- `GET  /api/v1/pipelines/:id` → `Pipeline`
- `PUT  /api/v1/pipelines/:id` (save draft), `POST /:id/publish`
- `POST /api/v1/pipelines/:id/runs` → `PipelineRun`; run events via WebSocket/SSE `/:id/runs/:runId/events`
- `POST /:id/validate` → `ValidationReport` (currently client-side)
- perms: `pipeline:read|write|run|publish`

## Dashboards
- `GET/PUT /api/v1/dashboards[/:id]`, `POST /:id/publish`, `POST /:id/favorite`
- perms: `dashboard:read|write|publish|share`

## Insights
- `GET  /api/v1/insights?modelId=` → `Insight[]`
- `POST /api/v1/insights/explain` body `{question}` → `Insight` (NLQ)
- `POST /api/v1/insights/:id/pin` / `/save` / `/share`
- perms: `insight:read|write`

## Other modules (typed services present, mock-backed)
Connections, Datasets, Data Quality, Lineage, Semantic models/metrics/glossary,
Reports + deliveries + approvals, AI assistant (streaming), AI Studio,
Knowledge bases, Agents + runs, Automations + runs + approvals, Notifications,
Activity, Audit, Usage, Marketplace, Developer (API keys/webhooks), Admin
(orgs/members/workspaces/flags/governance), Billing. Each `*.service.ts` in its
module declares the specific routes.

## Cross-cutting backend dependencies
- **Streaming**: AI assistant responses, pipeline/automation run events.
- **File upload**: file connections, knowledge-base documents, report assets.
- **Background jobs**: pipeline/automation runs, report rendering/export, KB indexing.
- **Secrets**: connection credentials & API keys — never stored client-side; the
  UI collects them and hands them to a backend vault. Mocks never persist secrets.
- **Auth/RBAC/entitlements/feature flags**: served by `/me`; frontend maps to the
  same typed shapes in `src/shared/types/identity.ts`.
