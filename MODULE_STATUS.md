# Module Status Matrix

Depth legend: **Flagship** = deep, novel interaction engine · **Full** = complete
CRUD/detail flows with rich mock data · **Functional** = navigable, realistic,
mock-backed.

| Module | Depth | Highlights |
|---|---|---|
| Application shell | Full | Sidebar (collapse/permission-aware), topbar (org/workspace switch, role sim, theme, search), command palette, mobile nav, notification drawer |
| Home | Full | Role/context header, health KPIs w/ sparklines, recent, activity, getting-started checklist |
| **Pipeline Studio** | Flagship | Node palette, drag/drop, port-to-port edges, marquee + multi-select, move/duplicate/copy-paste, undo/redo, zoom/pan/minimap, snap, dynamic typed inspector (config/schema/docs), validation markers, simulated run w/ live node states + streaming logs + results, autosave, unsaved-change guard, publish lifecycle, fullscreen, keyboard shortcuts |
| Pipeline list / runs | Full | Filters, run history, run-detail drawer w/ correlation IDs |
| **Dashboard Studio** | Flagship | Editable 12-col grid (drag/resize/snap), multi-page, field wells + aggregation, Build/Format/Interactions/General inspector, 18 visual types, cross-filter, edit/preview, undo/redo, copy/paste/duplicate, autosave |
| **Dashboard Viewer** | Full | Global filter bar, page tabs, freshness/refresh, favorite, share/export/snapshot/subscribe menu, accessible data tables |
| **Insights** | Flagship | Auto insight cards (trend/variance/anomaly/target/contribution), NL query entry, explain, pin/save/share, confidence + simulated labelling |
| **Explore** | Flagship | Ad-hoc analysis: model + field pick, live viz type switch, view underlying data, save-as-insight/pin/export |
| Visualization library | Full | SVG bar/column/stacked/line/area/pie/donut/scatter/gauge/KPI/metric/progress/table + sparkline, tooltips, accessible data-table toggle, states |
| Connection Studio | Full | Catalog, list, multi-step wizard (test/diagnostics), detail tabs (schema/preview/health/deps/audit) |
| Dataset Studio | Full | Catalog, detail tabs, data quality rules + incidents, interactive lineage graph w/ list fallback |
| Semantic Studio | Full | Model builder (entities/fields/relationships), metrics/KPI builder w/ preview, business glossary |
| Report Studio | Full | Paginated block builder, approval workflow, deliveries, export history |
| AI Assistant | Full | Streaming chat, sources/citations, tool-call summaries, context + model selectors, stop/usage/limitations |
| AI Studio | Full | Assistant/agent builders, prompt registry, knowledge bases, agent runs w/ step trace |
| Automation Studio | Full | Trigger→conditions→actions builder, runs (incl. dead-letter), approvals |
| Operations | Full | Notifications + preferences, activity center, audit center w/ redaction + correlation, usage/quota |
| Administration | Full | Platform/org/workspace admin, members & roles, feature flags, governance |
| Billing | Full | Plan comparison, usage/quota, invoices, payment (backend-gated) |
| Developer Portal | Full | API keys (secret-show-once), webhooks + delivery logs, docs/quickstart/SDKs |
| Marketplace | Full | Categorised extensions, statuses, install/enable/remove, detail |
| Settings | Full | Personal/workspace/org/platform sections, permission-aware, appearance/theme |
| Errors | Full | 403 / upgrade-required / 404 |

## Cross-cutting
- **Themes**: light / dark / system with persistence and tenant brand tokens.
- **Permissions/entitlements/feature flags**: role simulator in the top bar;
  navigation, routes and actions react live.
- **Responsive**: desktop-first; sidebar collapses, mobile nav drawer; studios
  offer fullscreen; complex canvases degrade gracefully.
- **Accessibility**: focus management in overlays, keyboard nav, visible focus,
  color-independent status (icons + text), accessible chart data tables,
  reduced-motion.
