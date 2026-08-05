# Dashboard Parity Contract

The authoritative source is the immutable published dashboard version. Viewer, direct export, worker, schedule, and email delivery bind to that version ID and consume the same canonical definition.

The manifest preserves dashboard/page titles; widget ID/type/layout/hidden/locked state; query, dataset and semantic bindings; global and per-widget filters; number/currency/decimal/percentage/date/conditional formatting; colors, theme, legend, axes, labels; interactions and drills; accessibility labels; text/image/table/pivot configuration; result metadata; and dashboard version ID.

Format behavior:

- JSON is the canonical definition plus scoped result data.
- CSV v2 contains metadata, one canonical-definition JSON record, page/widget/filter/format/interaction sections, and a data section for every widget, including non-tabular widgets.
- PDF and PNG apply supported visual formatting and embed the complete canonical definition as machine-readable metadata.
- Schedule and email resolve the immutable version/artifact; they do not reconstruct a mutable draft.

Static formats cannot reproduce hover/click execution. Interaction and drill definitions are therefore preserved losslessly in metadata, while the static visual represents the same saved state. Arbitrary remote image URLs are not fetched server-side, preventing SSRF; image configuration and alt/content are preserved and rendered as a safe static representation.
