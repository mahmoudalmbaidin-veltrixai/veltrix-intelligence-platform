# Verified Fix Matrix

| Claim | Independent evidence | Verified? | Risk |
|---|---|---:|---|
| Dashboard saves are single-flight | `DashboardStudioView.vue` joins `saveInFlight`; the Firefox test observed one POST and one PUT for duplicate key events in passing iterations | Yes, implementation | Low |
| Concurrent responses cannot overwrite later edits | Save owns a cloned snapshot and adopts only server identity/version when editor state changed during the request | Yes, implementation | Medium: no behavioral regression test |
| Publish waits for a successful save | `publish()` awaits `save()` and exits on false/conflict | Yes | Low |
| Leave guard and first-save navigation are safe | Guard bypass is scoped to successful stable-ID navigation; navigation failure is checked | Yes, implementation | Medium: failure cases are not behaviorally tested |
| Cache invalidation and duplicate prevention work | Dashboard query prefix is invalidated after persistence; duplicate key events join the same promise | Yes | Low |
| Firefox dashboard flow is deterministic | Fresh independent run: 19/20; one iteration remained on `/login` after login returned 200 | No | Critical |
| Firefox tests prove all claimed save scenarios | New test proves duplicate-save happy path and lifecycle ordering, but not edits-during-save, publish failure ordering, failed-save navigation, leave-guard decisions, or cache refresh | No | High |
| PostgreSQL timeout was fixed rather than hidden | Three fresh 61/61 runs; no leaked test-engine cleanup found; local TLS double-handshake removed | Yes | Low |
| PostgreSQL timeout was not increased | Integration setting remains 2.0 seconds | Yes | Low |
| `ssl=disable` is local/CI only and production TLS remains possible | Only test fixture and test CI URLs were changed; runtime settings do not rewrite `DATABASE_URL` | Yes | Low: TLS is supported, not mandated by the URL validator |
| Viewer/export/schedule/email share an immutable version | Export jobs bind a published `DashboardVersion.id`; worker loads that exact version; schedule creates the same export; email attaches exact artifact bytes | Yes | Low |
| JSON preserves canonical dashboard definition | JSON emits the parity manifest plus safe widget data | Yes | Low |
| CSV preserves complete parity | CSV emits IDs, types, grid and tables, but omits widget config/formatting/interactions/per-widget filters and can omit non-tabular widget definitions | No | High |
| PDF/PNG visual formatting matches editor/viewer | Renderers use grid coordinates and type families but ignore several style/number/legend/conditional-format settings | No | Critical |
| Arabic/Unicode rendering is certified | Fresh output showed Arabic in titles/tables, but chart category truncation removed the Arabic half of bilingual labels and mixed-direction note layout was poor | No | High |
| Generated parity evidence proves end-to-end delivery | Generator directly constructs a synthetic `RenderDocument`, covers 4 of 20 widget types, and does not traverse save/publish/viewer/schedule/email | No | High |
| Placeholder modules are hidden in production | Default flags/entitlements hide many surfaces and route smoke passes under default grants | Partly | Medium |
| AI placeholders and mocks cannot be exposed | AI Studio/Knowledge lack the entitlement used by other AI routes; enabling the flag exposes hard-coded mock documents and a stated visual placeholder | No | High |
| Production cannot silently use global mock mode | Staging/production config requires live mode; live provider registry exports no fabricated search providers | Yes | Low |
| All production endpoints have meaningful contract validation | Sweep validates counts, refs, metadata, declared 2xx and anonymous non-5xx errors | Partly | Medium |
| Sweep validates authenticated schemas/RBAC/tenant/payload behavior per endpoint | Anonymous calls usually stop at authentication; no per-operation happy response validation or comprehensive RBAC/tenant/pagination/filter/sort/large-payload matrix exists | No | High |
| XLSX is intentionally unsupported consistently | Dataset input accepts delimited text, UI gives CSV UTF-8 guidance, API allowlists omit XLSX, Office ZIP magic is rejected | Yes | Low |
| Archived user is intentionally unsupported consistently | User status enum has no archive state; API/UI expose suspend/activate, not archive/restore | Yes | Low |
| No migration/schema change was introduced | Git status/diff contain no migration path | Yes | Low |
| No sensitive debug instrumentation was added | Save telemetry contains phase/time/route and bounded identifiers, not definitions or credentials | Yes | Low |
| Full regression gate is healthy | Unit/build/a11y/integration mostly pass, but MyPy fails and selected live browser/legacy persona fixtures are not green | No | High |
