# Phase 4 API manifest evidence

- Live OpenAPI operation count after `/api/v1/files/capabilities`: **257**
- Reviewed committed manifest: `apps/api/tests/contracts/api_operation_manifest.json`
- Authentication levels: public=6, authenticated=4, platform=32, workspace=215
- Hard-coded `== 255` assertions replaced with `assert_manifest_matches()` / `build_manifest()`
- New operation: `GET /api/v1/files/capabilities` (`file_format_capabilities_api_v1_files_capabilities_get`, workspace-scoped)

Copy of reviewed manifest is in this folder.
