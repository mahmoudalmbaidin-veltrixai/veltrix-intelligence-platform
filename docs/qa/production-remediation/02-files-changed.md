# Files Changed

## Dashboard reliability and parity

- `src/modules/dashboards/DashboardStudioView.vue` — single-flight save lifecycle, stale-response protection, navigation verification, cache invalidation, publish failure handling, and non-sensitive lifecycle instrumentation.
- `src/modules/dashboards/dashboards.service.ts` — lossless widget/filter/config/interaction mapping.
- `src/modules/dashboards/dashboards.service.spec.ts` — Unicode and full-definition round-trip regression.
- `src/modules/dashboards/DashboardShareDialog.vue` and `delivery.service.ts` — JSON scheduled-delivery parity.
- `apps/api/src/vip_api/dashboards/schemas.py` — all 20 production widget contracts and their configuration fields.
- `apps/api/src/vip_api/dashboard_delivery/rendering.py` — canonical parity manifest, exact grid layout, format-specific rendering, PNG/PDF definition metadata, Arabic/bidi support.
- `apps/api/src/vip_api/dashboard_delivery/schemas.py` — all export formats accepted for schedules.
- `apps/api/Dockerfile`, `pyproject.toml`, `uv.lock`, and `requirements.runtime.lock` — deterministic Unicode renderer dependencies and DejaVu production font.
- `apps/api/tests/unit/test_dashboards.py`, `test_dashboard_delivery.py`, and `tests/integration/test_dashboard_lifecycle_integrity.py` — widget coverage, immutable viewer snapshot, export metadata/layout, schedule, Unicode, and attachment-byte regressions.
- `apps/api/scripts/render-dashboard-parity-evidence.py` — reproducible evidence artifact generator.
- `tests/e2e/dashboard-save-reliability.spec.ts` — duplicate-save, request-count, route-stability, and lifecycle assertion.

## PostgreSQL reliability

- `apps/api/tests/conftest.py` — local test default uses `127.0.0.1` and explicitly disables TLS negotiation; the two-second bound remains unchanged.
- `.github/workflows/quality-gate.yml`, `apps/api/README.md`, and `docs/backend/PIPELINE_BACKEND.md` — identical deterministic local/CI integration URL.

## Production gating

- `src/app/router/index.ts` and `src/app/navigation.ts` — automation/developer entitlement parity.
- `src/shared/ui/command/CommandPalette.vue` and `providers.ts` — feature-gated AI action and no mock search providers in live mode.
- `tests/e2e/route-smoke.spec.ts` — gated production-route assertions.

## API contract and type safety

- `apps/api/tests/integration/test_production_api_contract_sweep.py` — all-operation schema/error sweep.
- `apps/api/src/vip_api/core/config.py`, `dashboards/services.py`, `dashboards/query.py`, `dashboard_delivery/services.py`, `scheduler.py`, `worker.py`, `home/routes.py`, `governance/role_assignment_service.py` — typed validation at environment/database boundaries; no public contract was loosened.

Pre-existing QA seed/report files and unrelated dirty-worktree edits were preserved. No migration was added.

