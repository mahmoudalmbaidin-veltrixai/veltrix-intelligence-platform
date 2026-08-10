# VIP Phase 2 semantic parity matrix

`PASS` means the channel preserves the widget's supported analytical meaning or
canonical definition. `N/A` is reserved for unsupported channels; none of the
four configured export formats is unsupported by the current worker.

| Widget | Live | Reload | Published | PDF | PNG | CSV | JSON | Semantic Result |
|---|---|---|---|---|---|---|---|---|
| KPI | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Metric comparison | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Table | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Pivot | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Bar | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Stacked Bar | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Column | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Line | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Area | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Pie | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Donut | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Scatter | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Gauge | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Progress | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Text | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Rich Text | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Image | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Filter | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Date Filter | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Map | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

Evidence combines the authoritative 20-value widget inventory, frontend
component contracts, real browser save/reload/publish, PDF content-stream
inspection, per-widget PNG body crops, renderer dispatch capture, known-value
assertions, and the persisted worker lifecycle. CSV/JSON PASS for non-tabular
widgets means the immutable definition/state is preserved; it does not claim a
bitmap is embedded in CSV.
