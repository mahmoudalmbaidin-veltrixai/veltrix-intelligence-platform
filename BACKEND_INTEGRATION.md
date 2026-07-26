# Backend Integration Map

Every mocked service documents its intended backend contract inline (search
`INTEGRATION POINT`). This file is the consolidated map. All endpoints are
workspace-scoped and require the noted permission; the backend is the security
boundary (frontend checks are UX only).

## Configuration & transport (see src/shared/config/env.ts, lib/apiClient.ts)

- Local development is intentionally hybrid: B1â€“B4 authentication, tenancy, governance, audit,
  administration mutations, and connections always use the backend, while later business domains
  remain mock-backed. `VITE_API_MODE=live` + `VITE_API_BASE_URL` switch those later services to live
  adapters only when their APIs exist. The client sends cookie
  credentials, a CSRF header on unsafe methods, scoped context headers, and
  `X-Correlation-Id`. Errors use `{ error: { code, message, details, correlation_id } }`.
  Status codes map to normalized `ApiErrorKind` (401→unauthorized, 409→conflict,
  429→rate-limit, 503→maintenance, …).

## Auth / session (Phase B1 implemented, see services/auth)

- `POST /auth/login` `{email,password}` → `{ user, session }` plus session/CSRF cookies
- `POST /auth/logout` → `{ success: true }` and deleted cookies
- `GET  /auth/me` → `{ user, session }`
- `POST /auth/refresh` → rotated `{ user, session }` plus replacement cookies
- Access and refresh values remain in `HttpOnly` cookies; the frontend stores neither token.
- One coordinated refresh retries concurrent 401 responses once before clearing auth state.
- Organizations, workspaces, explicit memberships, invitations, and tenant switching are implemented
  in Phase B2. B3 scoped RBAC/governance is implemented; MFA and SSO remain later-phase concerns.

## Governance (Phase B3 implemented)

- `GET /api/v1/authorization/context` supplies server-resolved roles, permissions, effective flags,
  active entitlements, and quota snapshots for the validated tenant context.
- Roles, permission catalog, entitlement/flag/quota inventory, and scoped audit-event reads are
  backend APIs protected by explicit governance dependencies.
- Frontend navigation and reusable gates consume the in-memory authorization store; logout and
  tenant switches clear it. No role, permission, flag, entitlement, or quota grant is mocked.
- Permission keys use `resource.action`; future-module entries without a B3 permission remain
  hidden until their backend policy is introduced.

## Tenancy (Phase B2 implemented)

- `GET/POST /api/v1/organizations`
- `GET/PATCH /api/v1/organizations/:organizationId`
- `GET/POST /api/v1/organizations/:organizationId/workspaces`
- `GET/PATCH /api/v1/organizations/:organizationId/workspaces/:workspaceId`
- Membership and invitation management live beneath the authorized organization path.
- Organization profile and workspace create/update/archive workflows in the frontend persist through
  these endpoints and refresh the validated tenant selector after successful mutations.
- `GET /api/v1/tenant-context` validates `X-Organization-ID` and optional `X-Workspace-ID`.
- The frontend stores selected IDs only as user-bound preferences, revalidates them on bootstrap,
  and qualifies cache/storage scopes by user, organization, and workspace.

## Semantic layer (powers dashboards, insights, explore, home)

- `GET  /api/v1/semantic/models` → `SemanticModel[]`
- `POST /api/v1/semantic/query` body `SemanticQuery` → `QueryResult` ← **the key analytics seam**
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

Datasets, Data Quality, Lineage, Semantic models/metrics/glossary, Reports + deliveries + approvals,
AI assistant (streaming), AI Studio, Knowledge bases, Agents + runs, Automations + runs + approvals,
Notifications, Activity, Usage, Marketplace, Developer (API keys/webhooks), Billing, and the
post-B4 analytics modules remain mock-backed. Each `*.service.ts` declares its future routes.

Connections are live B4 APIs. The Audit Center uses the live B3 audit-event API. Organization,
workspace, member, role, feature, and governance foundation screens use B2/B3 APIs; controls for
capabilities without a corresponding backend mutation endpoint remain read-only rather than
simulating success.

## Cross-cutting backend dependencies

- **Streaming**: AI assistant responses, pipeline/automation run events.
- **File upload**: file connections, knowledge-base documents, report assets.
- **Background jobs**: pipeline/automation runs, report rendering/export, KB indexing.
- **Secrets**: B4 submits connection credentials once to the server-side provider boundary. They
  are authenticated-encrypted, never returned, and never stored in frontend query caches.
- **Auth/RBAC/entitlements/feature flags**: served by `/me`; frontend maps to the
  same typed shapes in `src/shared/types/identity.ts`.
