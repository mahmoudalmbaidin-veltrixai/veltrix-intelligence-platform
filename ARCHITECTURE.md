# VIP Frontend Architecture

VIP — Veltrix Intelligence Platform — is an AI-native, multi-tenant enterprise
analytics & data platform frontend built with **Vue 3 + TypeScript + Vite +
Vue Router + Pinia**. It is structured to connect to real backend APIs without
rebuilding the UI: every data access goes through a typed service + a
mock adapter that shares the exact contract the backend will implement.

## Stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | Vue 3 `<script setup>` | Strict TS, typed props/emits |
| Build | Vite 6 | Dev + prod, port **3009** (`strictPort`) |
| Routing | Vue Router 4 | Route-level code splitting, typed meta, guards |
| Global state | Pinia | Only for truly global concerns (see below) |
| Server state | `@/shared/lib/query` | Dependency-free `useQuery`/`useMutation` (cache, dedup, retry, cancel, invalidate). Swappable for TanStack Query. |
| Styling | CSS custom properties (design tokens) | `src/styles/tokens.css`, light/dark/system |
| Charts | Custom SVG viz library | `src/shared/viz/*` — zero chart deps |
| Icons | Inline SVG registry | `src/shared/ui/icons.ts` — zero icon deps |
| Tests | Vitest + @vue/test-utils | unit + component |

## Directory layout

```
src/
  app/            # shell, layouts, router, navigation registry
    layouts/      # AppLayout, StudioLayout, SettingsLayout, BlankLayout
    shell/        # AppSidebar, AppTopbar, MobileNav, NotificationDrawer
    router/       # routes + typed meta + guards
  shared/
    types/        # identity, api, semantic, pipeline, dashboard, insight
    lib/          # query, mock, format
    permissions/  # roles + hasPermission
    stores/       # platform (auth ctx), theme, ui
    services/     # semanticModels (shared mock query engine)
    composables/  # useResizable
    ui/           # design-system components (Vip*)
    viz/          # SVG chart library + VisualRenderer
  modules/
    home/ connections/ pipelines/ datasets/ semantic/
    dashboards/ insights/ explore/ reports/ ai/ automation/
    operations/ admin/ billing/ marketplace/ developer/
    settings/ errors/
```

## State-management boundaries

- **Server state** → `useQuery`/`useMutation`. Keyed cache, invalidation by
  prefix, request cancellation on key change. Call sites never touch caching.
- **Global client state** (Pinia) → `platform` (user, org, workspace, role,
  permissions, entitlements, feature flags), `theme`, `ui` (sidebar, command
  palette, toasts, notification drawer). Nothing else.
- **Local component state** → editor selections, drawers, tabs, wizard steps,
  unsaved canvas changes. The Pipeline and Dashboard **editor engines**
  (`usePipelineEditor`, `useDashboardEditor`) are composables, not stores, so
  their state is scoped to the studio and unit-testable in isolation.

## API-ready pattern (mock → live)

Each module owns a `*.service.ts` exposing an async, typed interface. Today it
resolves against in-memory/localStorage mocks with simulated latency and error
scenarios (`src/shared/lib/mock.ts`). The top of every service documents the
intended backend route, request/response contract and required permission
(search the repo for `INTEGRATION POINT`). To go live, replace the mock body
with `fetch`/client calls — call sites and types are unchanged. `VITE_API_MODE`
(`mock` | `live`) is the intended switch.

The analytics surfaces (dashboards, insights, explore, home) never emit SQL:
they build a typed `SemanticQuery` and receive a typed `QueryResult` from
`semanticService`. This is the single seam the backend semantic engine plugs
into.

## Routing & governance

`src/app/router/index.ts` declares the full route hierarchy with typed
`meta` (`requiresAuth`, `permission`, `entitlement`, `featureFlag`, `layout`,
`title`, `fullBleed`). A global `beforeEach` guard redirects to `/forbidden`
(missing permission), `/upgrade` (missing entitlement) or `/not-found`
(disabled feature flag). **Frontend checks are UX only — the backend remains
the security boundary.**

## Design language

One token system (`tokens.css`) drives light/dark/system themes, tenant brand
overrides, semantic status colors, spacing, radius, shadows, motion and a
data-viz palette. Components consume `var(--vip-*)` exclusively; no hard-coded
colors. Reduced-motion is respected globally.

## Flagship studios

- **Pipeline Studio** (`modules/pipelines`) — Alteryx-style node canvas:
  drag-from-palette, connect ports, marquee/multi-select, move, duplicate,
  copy/paste, undo/redo, zoom/pan/minimap, snap, dynamic typed node inspector,
  validation markers, simulated run with live node states + logs, autosave,
  unsaved-change protection, publish lifecycle.
- **Dashboard Studio** (`modules/dashboards`) — Power BI-style editable grid:
  drag/resize/snap widgets, multi-page, field wells with aggregation,
  context-aware Build/Format/Interactions/General inspector, cross-filtering &
  drill foundation, 18 visual types, edit/preview modes, viewer, autosave.
- **Insights** (`modules/insights`) — auto-surfaced trend/variance/anomaly
  findings, NL query entry, explain, pin/save/share. Clearly labelled simulated.
- **Explore** (`modules/explore`) — lightweight ad-hoc analysis workspace.

See `MODULE_STATUS.md` for per-module depth and `BACKEND_INTEGRATION.md` for the
endpoint map.

## Commands

```
npm run dev         # dev server on http://localhost:3009 (strict)
npm run build       # vue-tsc typecheck + production build
npm run typecheck   # types only
npm run test        # vitest unit + component tests
npm run lint        # eslint
```
