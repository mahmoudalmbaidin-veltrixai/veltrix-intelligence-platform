# VIP Phase 4 — File, API, QA & Browser Remediation Report

## Executive Summary

| Bug | Priority | Status |
| --- | --- | --- |
| VIP-BUG-007 | P1 | **FIXED + VERIFIED** |
| VIP-BUG-008 | P2 | **FIXED + VERIFIED** |
| VIP-BUG-009 | P2 | **FIXED + VERIFIED** |
| VIP-BUG-010 | P2 | **FIXED + VERIFIED** |
| VIP-BUG-012 | P3 | **FIXED + VERIFIED** |

## Environment

| Item | Value |
| --- | --- |
| Branch | `feat/post-core-p1-p2-connectors-scheduling-versions` |
| Start SHA | `be0328e211e0a7bed925758d7c9a842e7e58ae94` |
| Alembic | `20260808_0021` (single head) |
| Frontend | `http://localhost:3009` |
| API | `http://localhost:8000` |
| Services | postgres, redis, clamav, api, dashboard-worker, pipeline-worker — healthy |
| Pre-existing dirty tree | Tenancy/admin/login/query edits preserved and excluded from Phase 4 commits |

## VIP-BUG-007

### Prior mismatch

Catalog advertised CSV/TSV/Excel/JSON. Upload allowlist excluded `.xlsx`. Signature policy rejected all `PK\x03\x04` ZIP/Office payloads. Dataset ingest was CSV-only.

### Final authoritative contract

`GET /api/v1/files/capabilities` + `vip_api.files.capabilities.FORMAT_CAPABILITIES`.

Catalog `local_file` description now matches: CSV/XLSX/JSON upload; CSV+XLSX tabular ingest (first sheet).

### XLSX implementation

- Dependency: `openpyxl`
- Validation: extension + MIME + OOXML ZIP members + encryption/macro rejection
- Parse: first worksheet by default; optional `sheet_name`; `data_only` formula cache; no macro execution
- Ingest: shared tabular write path with CSV

### Security

Executable signatures still blocked. Non-XLSX ZIPs still rejected. Password-protected and macro-enabled packages rejected. ClamAV order unchanged (after signature).

## File Format Matrix

| Format | Advertised | API Accepted | Parsed | Dataset Created | UI Upload | Status |
| ------ | ---------- | ------------ | ------ | --------------- | --------- | ------ |
| CSV | Yes | Yes | Yes | Yes | Yes | SUPPORTED |
| XLSX | Yes | Yes | Yes | Yes | Yes | SUPPORTED |
| XLS | No | No | No | No | Clear reject | NOT SUPPORTED |
| JSON | Yes (upload) | Yes | No tabular | No | Upload-only | PARTIAL |
| TSV | UI-assisted | No binary | Via browser→CSV | Via CSV | Yes (convert) | PARTIAL |
| Parquet | No | No | No | No | No | NOT SUPPORTED |

## VIP-BUG-008

- Original issue: tests pinned `== 255` while live OpenAPI had 256 (now 257 with capabilities).
- Fix: reviewed committed manifest + drift detection for add/remove/id/auth-class changes.
- Current operation count: **257**
- Classification test: passed against manifest (no hard-coded total).

## VIP-BUG-009

- Run ID: `qa-cert-<date>-<run-id>`
- Registry tracks exact IDs; cleanup is dependency-ordered and environment-guarded
- Stale reporter lists likely leftovers without auto-deleting ambiguous data
- Browser helper: `tests/e2e/helpers/certification-lifecycle.ts`

## VIP-BUG-010

- Old expectation: visible text `Version history unavailable`
- Correct contract: persisted version list with `vN`, type, timestamp, summary
- Chrome E2E: **PASSED**

## VIP-BUG-012

- Root cause: hover expand remount race under WebKit
- Fix: tooltip close delay + longer dwell + non-destructive label DOM + keyboard coverage
- Chrome / Firefox / WebKit focused E2E: **PASSED**

## Regression

### Phase 1 / 2 / 3

Phase 3 security-headers commit is present on branch (`VIP-BUG-005`). No Phase 3 code altered in this phase. Targeted Phase 1/2 product paths were not rewritten; XLSX/API/QA/nav changes are additive.

### Platform runs executed

| Check | Result |
| --- | --- |
| XLSX + file validation unit | PASSED |
| QA lifecycle unit | PASSED |
| OpenAPI classification (manifest) | PASSED |
| Dataset versions integration | PASSED (in focused suite) |
| Frontend typecheck | PASSED |
| Frontend production build | PASSED |
| Frontend eslint | Pre-existing mass errors unrelated to Phase 4 files |
| Collapsed nav Chrome/Firefox/WebKit | PASSED |
| Dataset Version Chrome E2E | PASSED |
| Ruff (Phase 4 modules) | PASSED |

## Remaining Risks

1. API/worker images should be rebuilt so `openpyxl` is baked into `requirements.runtime.lock` image layers (installed live in the running container for verification).
2. Full authenticated persona sweep (`executed_count == operation_count`) is long-running and was not fully re-executed end-to-end in this session; classification + manifest governance were verified.
3. Historical stale datasets/files (~241/89) were **not** bulk-deleted; only tooling to clean registered run IDs / report likely stale names was added.

## Evidence

See `VIP_PHASE4_EVIDENCE/`.
