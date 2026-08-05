# All-Widget Parity Matrix

`widget-parity-results.json` contains 20 rows and 11 channels per row: editor creation, save, reload, publish, viewer, PDF, PNG, CSV, JSON, scheduled export, and email attachment.

Widget types: KPI, metric comparison, table, pivot, bar, stacked bar, column, line, area, pie, donut, scatter, gauge, progress, text, rich text, image, filter, date filter, and map.

Proof is compositional but uses production paths:

- `test_all_widget_types_traverse_real_publish_and_export_contract` creates, saves, reloads, publishes, views, and exports through the real PostgreSQL/API/worker contract.
- `test_all_twenty_widget_types_render_and_preserve_definition` verifies all renderer families and lossless manifests.
- scheduler and email integration tests prove immutable version/artifact dispatch and attachment preservation.
- the generated 20-page PDF and long-form PNG were visually inspected page by page; distinct metric comparison, stacked, scatter, gauge, progress, and map output is visible, and no glyph clipping/truncation was found.

The evidence directory also contains deterministic PDF, PNG, CSV, JSON, SHA-256 hashes, and generation metadata.
