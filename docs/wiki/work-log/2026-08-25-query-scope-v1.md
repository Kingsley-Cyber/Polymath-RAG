---
change_id: QUERY-SCOPE-V1
owner: orchestrator
date: 2026-08-25
status: implemented
architecture_impact: /ask gains explicit fail-closed scoping; corpora gain purpose/query_enabled classification; workspaces table added
---

# QUERY-SCOPE-V1 (2026-08-25)

## Contract

Every /ask request resolves ONE explicit scope (CORPUS / CORPORA /
WORKSPACE / ALL_AUTHORIZED). Missing scope → typed
QUERY_SCOPE_REQUIRED (422), matching the existing error style. No
stage may widen scope. ALL_AUTHORIZED includes only
purpose='production' AND query_enabled corpora — evaluation, fixture,
and probe mass can never leak.

## Changes

1. Migration 0035: corpora.purpose + corpora.query_enabled (+ index);
   query_workspaces table for WORKSPACE mode. Backfill measured and
   fail-closed: everything starts probe/disabled except sealed→
   evaluation, fixture/qualification families, and a six-corpus
   production allowlist of real user material.
2. shared/polymath_shared/query_scope.py: deterministic resolver
   (QueryScopeRequired / UnknownQueryScope typed errors).
3. ask.py: scope resolved at entry (422/404 typed); helpers take the
   resolved corpus set via `= ANY(%s)`; the implicit None→all-corpora
   fallbacks are DELETED (regression-pinned); response echoes scope.
4. Operational incident during migration: a worker backend orphaned by
   an earlier kill held 'idle in transaction' 43 min on artifacts —
   blocked ALTER TABLE (handoff trap #2 again). Terminated; sweep clean.

## Proof

- tests/determinism/test_query_scope.py 16/16: A no-scope, B single-
  corpus, C multi-corpus, D all_authorized=6 production only, E probe
  exclusion, F–J propagation pins (procedures/concepts/facts/
  concept_graph SQL receives exact scope; dense lane filters payload
  corpus_id at Qdrant; graph seeds derive from scoped fusion with
  doc-bounded fact backfill), K documented (corpus-map expansion not
  yet built — contract recorded in resolver docstring).
- Focused core 54/54 green.
- Live: no-scope→422 QUERY_SCOPE_REQUIRED; scoped FACT_QUERY returns
  release-books facts with scope echo; ALL_AUTHORIZED resolves exactly
  the 6 production corpora.

## Rejected claims

- WORKSPACE mode ships as persisted id→corpus-set lookup; management
  UI/API for workspace CRUD is future work.
- Corpus-map expansion does not exist yet; its scope rule is pre-
  committed in the resolver contract (never widen).

## Open contract gaps

- Dense lanes inside /ask (VECTOR/HYBRID modes) arrive with the
  evidence-bundle work; they must consume resolve_query_scope output.
