# File upload security notes (VIP-BUG-007)

Unchanged controls:
- `file.upload` permission + CSRF + rate limit
- Extension/MIME allowlist + ext↔MIME match
- Magic/signature inspection (executables blocked; OOXML validated for XLSX only)
- ClamAV after signature
- Tenant-scoped file rows and ingest ACL

Added:
- Password-protected workbook rejection (`XLSX_ENCRYPTED`)
- Macro-enabled package rejection (`XLSX_MACROS_FORBIDDEN`)
- Corrupt/invalid OOXML rejection
