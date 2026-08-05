# Root Cause Report

Date: 2026-08-05  
Branch: `frontend/enterprise-ui-enhancement` (unchanged)

This remediation used the prior reports in `docs/qa/full-platform` as its baseline. The full platform QA was not regenerated.

## Blocker 1 — Firefox dashboard save

Two independent issues were present:

1. The editor allowed manual save, keyboard save, autosave, and publish to enter the same persistence lifecycle concurrently. A late response could adopt a stale snapshot or route, the leave guard could intercept the post-create ID transition, and publish could continue after a failed ordinary save.
2. The retained failing Playwright trace showed that one reported repeat failure completed login, save, route adoption, and every assertion, then exceeded the original 30-second test budget during teardown. Live Firefox authentication alone took about 25 seconds in the slow runs.

The product root cause was a missing single-flight/state-ownership boundary. The harness root cause was a suite-wide timeout that included slow live authentication and teardown rather than the scoped save operation.

## Blocker 2 — PostgreSQL integration reliability

Every test-created asyncpg engine used the host `localhost` URL with asyncpg's default `ssl=prefer`. Against the local non-TLS PostgreSQL container, each fresh engine first attempted TLS, received a rejection, and then opened a second plaintext connection. High connection churn plus Windows/Docker event-loop scheduling and PostgreSQL checkpoint load intermittently consumed the unchanged two-second connection bound. The failing test changed between runs because the defect was connection setup overhead, not test-specific logic.

Pool inspection showed no leaked `vip_test` connections and no exhausted live API pool. Explicit `127.0.0.1` alone did not fix the issue; explicit local `ssl=disable` did.

## Blocker 3 — dashboard/export/report/email parity

The frontend supported 20 widget types while the API accepted 13. The transport mapper read widget filters from a field it did not write, and omitted formatting, interaction, lock, and accessibility properties. PDF and PNG renderers stacked cards instead of applying the dashboard's 12-column grid. JSON exported a reduced definition. Scheduled delivery excluded JSON. PDF/PNG also lacked a reliable Arabic shaping/font path.

The common cause was that each output path projected its own partial dashboard model instead of consuming the immutable published definition as the parity contract.

## Blocker 4 — placeholder modules

Live navigation and the command palette had inconsistent entitlement coverage. Automation runs/approvals, developer settings, the AI command, and mocked command-search results could be discoverable independently of a production capability grant.

The cause was distributed gating: route metadata, navigation metadata, quick actions, and command providers were not all driven by the same entitlement/feature state.

## Blocker 5 — API production validation

The application exposed the expected OpenAPI surface, but no single automated sweep checked every production operation for resolvable schemas, path-parameter consistency, declared success responses, safe anonymous invalid-UUID/empty-payload behavior, and non-5xx error envelopes. Domain integration tests covered authorization and tenant cases, but surface-wide contract drift could escape.

## Conditional capabilities

- XLSX upload is intentionally not a production capability. The product accepts CSV/TSV/text, rejects Office ZIP containers, has no workbook parser dependency, and instructs users to save as UTF-8 CSV.
- Archived-user lifecycle is not a production requirement. The QA `archived_user` record is explicitly an active “candidate (unsupported)”; production user administration exposes suspend/activate, not archive/restore. No archived-user control is exposed.

