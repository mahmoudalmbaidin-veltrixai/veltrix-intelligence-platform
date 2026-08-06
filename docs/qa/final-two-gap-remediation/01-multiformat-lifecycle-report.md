# Real Multi-Format Delivery Lifecycle

## Executed path

`test_all_twenty_widgets_traverse_every_real_delivery_format` creates a real
organization, workspace, PostgreSQL connection, source table, dataset, semantic model,
saved dashboard, and immutable published version. It then creates four due schedules
and invokes the production scheduler, generic job queue, real dashboard worker, file
storage, delivery record, and email builder.

The test does not construct a synthetic `RenderDocument` for lifecycle certification.
The worker builds the render input from the persisted published version and real query
results. Cleanup targets only generated IDs and the exact generated source-table name.

## Observed result

Dashboard: `f1266fac-f85b-46b0-b099-0ee88b07ee91`

Published version: `d85fae82-1fa4-463e-9783-ced06c997ce5`

| Format | Widgets | Visible | Queried | Artifact equals email | Result |
| --- | ---: | ---: | ---: | --- | --- |
| PDF | 20 | 20 | 15 | SHA-256 equal | pass |
| PNG | 20 | 20 | 15 | SHA-256 equal | pass |
| CSV | 20 | 20 | 15 | SHA-256 equal | pass |
| JSON | 20 | 20 | 15 | SHA-256 equal | pass |

The machine evidence records the schedule, delivery run, platform job, export, stored
file, artifact hash, email hash, version, counts, result, and exact test ID per format.

## Format verification

- PDF: 20 pages; visual inspection covered every rendered page and detailed bar, line,
  pie, and map pages. Legends, X/Y axis titles, bilingual labels, formatting, and real
  map points are visible.
- PNG: one complete 20-widget image; the full image was visually inspected and all
  widgets, legends, axes, bilingual text, and real data were present.
- CSV: structured manifest preserves the canonical dashboard definition, filters,
  formatting, interactions, non-tabular definitions, and tabular sections.
- JSON: preserves the complete canonical definition and result set.

Initial targeted failures are retained: loopback querying was correctly rejected by
the production SSRF control, so the test uses a non-loopback private address only with
the test-only private-network setting; the first PDF metadata assertion assumed raw
text rather than ReportLab UTF-16 escaping and was corrected; the map fixture was then
extended with real latitude/longitude data after visual inspection exposed its empty
state. These were test-fixture/evidence defects, not weakened runtime controls.
