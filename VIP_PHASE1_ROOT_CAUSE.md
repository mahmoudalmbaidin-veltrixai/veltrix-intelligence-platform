# VIP Phase 1 Root-Cause Note

Recorded after pre-flight and pre-fix reproduction, before production changes.

## VIP-BUG-004 — Dataset quality fan-out

The N+1 pattern is initiated in the frontend, not by ORM relationship loading in the
dataset list endpoint. `datasetService.liveDatasets()` first requests one page of up
to 100 datasets, then runs `Promise.all()` with one
`GET /datasets/{dataset_id}/quality` request per returned dataset. The Dataset list
and Pipeline source selector both consume that service, so both inherit the fan-out.

Each quality request performs independent dataset lookup, authorization/resource
guard evaluation, latest-evaluation lookup, and rule counting. Consequently, one
100-item screen produces 101 HTTP requests and repeats backend authorization and
query work 100 times. The pre-fix populated-tenant browser run measured 106 total API
requests on the Dataset route (one list request and 100 quality requests) and 107 on
the Pipeline source selector (one list request and 100 quality requests).

The list repository itself is bounded and already enforces organization, workspace,
ACL, and explicit-deny filters in SQL. It performs a count and a stable paged query;
the fan-out occurs after that response. The existing dataset table also has a cheap
persisted quality status, while the latest completed evaluation can be projected by
a single bounded SQL subquery when a numeric score is required.

The Pipeline selector compounds the problem by requesting the first 100 records and
performing client-only search/pagination. A tenant with more than 100 authorized
datasets cannot search beyond the initially downloaded page.

## VIP-BUG-001 — First-save reliability

Dataset source readiness is blocked by the fan-out above, which made the normal
first-save path slow and unstable in populated tenants. The save lifecycle has a
separate atomicity defect: creating a pipeline currently sends a metadata-only POST,
then sends a PUT containing the graph. The POST commits before the PUT. If the PUT
fails, a persisted empty/ghost pipeline exists while the browser still treats the
editor as a new pipeline. A retry can therefore create a duplicate.

The editor exposes a visual loading guard, but it has no authoritative single-flight
promise. Keyboard save and other programmatic paths can enter `persist()` while a
request is already active. Failures retain the in-memory graph, but the two-request
create contract cannot guarantee an atomic first save.

## Selected architecture

1. Return a lightweight paginated dataset-list projection with the latest completed
   quality score obtained by a single SQL subquery/outer join. Retain all existing
   tenant, workspace, ACL, and explicit-deny predicates. No per-item quality HTTP
   calls are permitted during list or selector hydration.
2. Add an explicit paginated dataset client contract and use server-side search,
   stable ordering, bounded page sizes, and debounced selector search. Detailed
   quality information remains lazy on the dataset detail screen.
3. Make the create endpoint accept and persist the initial graph in the same database
   transaction as pipeline metadata. The client performs one POST for a first save.
4. Add an explicit editor save state and a shared single-flight promise so all save
   entry points receive the same authoritative operation. A rejected save keeps the
   graph dirty and retryable; only a confirmed response establishes the ID and URL.

This combines list projection and lazy detail hydration. It avoids both O(N) request
growth and an unbounded all-record payload while preserving current authorization.
