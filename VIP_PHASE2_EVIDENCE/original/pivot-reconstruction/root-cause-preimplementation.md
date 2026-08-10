# Pivot reconstruction — pre-implementation finding

Date: 2026-08-10 (Asia/Riyadh)

The written independent finding says the retained 20-widget Pivot was blank in
PDF and PNG while structured data contained three rows. The retained evidence
does not reproduce that statement:

- `VIP_TEST_EVIDENCE/export-parity/lifecycle.json` identifies dashboard
  `46156077-2b53-45a6-97b4-3d2151ec7b30`, published version
  `d0b8dec0-6b96-4655-9c84-9dceee62368d`, and the exact PDF/PNG hashes.
- The retained files match those hashes (`140dbdc...af7` for PDF and
  `941bdfab...5c1` for PNG).
- PDF page 4 visibly contains the Pivot headers `Category` and `Orders` and the
  Dammam/Jeddah/Riyadh rows with values 5/8/12.
- The corresponding section of the retained PNG contains the same table.
- The structured JSON contains the exact persisted Pivot definition and the
  same three rows.
- The original dashboard/version IDs no longer exist in PostgreSQL; the
  lifecycle fixture intentionally cleans generated state.
- Re-running the current real 20-widget save/reload/publish/scheduler/job/
  storage/email lifecycle passes.

Therefore the reported blank artifact is **not reproducible from the retained
artifact set**. The original report most likely referred to a transient or
different artifact that was not retained, or the page was misclassified during
inspection. This is an evidence mismatch, not a proven renderer defect.

Two related architectural gaps are nevertheless proven in current source:

1. Pivot is named as a distinct widget but is shaped and rendered as a flat
   table. There is no canonical matrix contract, so multi-dimension Pivot
   meaning cannot be certified across live/PDF/PNG channels.
2. Scatter accepts one metric at save/publish time. Live rendering duplicates
   that metric as X and Y, while the pre-existing export renderer fell through
   to Bar. Claude's renderer patch stops the fall-through, but save/publish and
   live configuration remain inconsistent.

Implementation will address those proven contract gaps without claiming the
retained Pivot artifact was blank.
