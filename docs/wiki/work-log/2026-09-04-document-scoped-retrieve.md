---
change_id: DOCUMENT-SCOPED-RETRIEVE-V1
owner: orchestrator
date: 2026-09-04
status: DONE (pure suite green; not yet fleet-restarted / merged)
architecture_impact: none — an ADDITIVE optional `document_ids` filter on the retrieval read path (POST /retrieve default lane + EXPLORE, POST /retrieve/plan), advertised in GET /capabilities. Ranking, fusion, scope resolution and the extraction pipeline are untouched; with the field absent every statement is byte-identical to before.
last_reviewed: 2026-09-04
---

# WORK LOG — DOCUMENT-SCOPED-RETRIEVE-V1: restrict a retrieve to a subset of documents

Request: let a caller restrict `/retrieve` (default lane and EXPLORE) and
`/retrieve/plan` to a subset of documents inside the resolved corpus scope,
without touching extraction and with zero behaviour change when the field
is absent.

## Contract

1. `RetrieveRequest.document_ids: Optional[list[str]] = None`;
   `PlanRequest.document_ids` is threaded into every reformulation's
   `RetrieveRequest`. `None`, `[]` and blank-only lists mean NO filter;
   ids are trimmed and de-duplicated in request order.
2. With a non-empty filter only documents in the list may appear: their
   chunks (dense, lexical, parent lanes), their summaries (document rows)
   and the graph facts their chunks attest. The resolved corpus scope
   still applies — an id outside the scope yields nothing, never an error.
   The response echoes `document_ids` (only when supplied).
3. Applied at the stores, before `limit`: `doc_id = ANY(%s)` in
   `_fetch_profiles` / `_fetch_parents` / `_fetch_children_rows`, a Qdrant
   payload filter `doc_id ∈ list` on the child lane, `ev.doc_id = ANY(%s)`
   in graph seed resolution and fact authorization (the Cypher allowlist),
   `e.doc_id = ANY(%s)` on the EXPLORE hop. `build_evidence_rows` keeps only
   in-filter attestations for graph-fact rows and drops any row of another
   document (a no-op unless a lane leaked).
4. FAST / HYBRID / GRAPH / WILDCARD do not honour the filter: a non-empty
   `document_ids` with those modes is a typed 422
   `{"error_code": "document_filter_unsupported"}` (fail closed, never a
   silently unfiltered page).
5. `GET /capabilities.contracts.document_ids = true` (additive sibling of
   `explore`; `retrieve-evidence-rows` stays `"v1"` so consumers switching
   on `== "v1"` are unaffected). `api` date → 2026-09-04.

## Changes

- `orchestrator/orchestrator/api/retrieve.py`: field, `document_filter()`,
  `_document_clause()`, the mode gate, and `document_ids=` threaded through
  `_fetch_profiles`, `_fetch_parents`, `_fetch_children_rows`,
  `_qdrant_search`, `graph_expand_or_502`, `_neo4j_expand`,
  `_corpus_seed_ids`, `_authorized_fact_ids` (all keyword, default `None`;
  `chat.py` / `evidence.py` / eval callers unchanged).
- `orchestrator/orchestrator/api/evidence_rows.py`: `build_evidence_rows(...,
  document_ids=None)`, `_graph_hop(..., document_ids=None)`.
- `orchestrator/orchestrator/api/corpus_plan.py`: `PlanRequest.document_ids`,
  threaded + echoed.
- `orchestrator/orchestrator/api/capabilities.py`: `document_ids: True`, API date.
- `tests/determinism/test_document_scoped_retrieve.py` (NEW, pure: faked
  Postgres/Qdrant/Neo4j that apply the clause the way the stores would).
- `scripts/scaffold_polymath_v4.py`: TREE rows for the test and this entry.

## Proof

- `pytest tests/determinism/test_document_scoped_retrieve.py` → 17 passed (12 tests, 17 with parametrisation):
  every lane restricted to the listed documents with the clause + parameter
  present in each fetcher and passed to Qdrant/graph; out-of-scope id → zero
  rows, no error; absent / `None` / `[]` / blank list → unfiltered lane and
  the pre-filter statements (asserted text + params); EXPLORE threads the
  normalised list into the evidence rows; FAST/HYBRID/GRAPH/WILDCARD → 422
  `document_filter_unsupported` before any store call; Qdrant `must` gains
  exactly one `doc_id` MatchAny condition (and none without the filter);
  graph seeds + authorization narrowed end to end into the Cypher params;
  evidence rows keep only in-filter fact attestations, drop facts attested
  only elsewhere, keep the hop inside the filter (6 vs 5 placeholders);
  plan endpoint threads the field into every reformulation; capabilities
  advertise it additively.
- Full `pytest tests` from the worktree (`python -m pytest tests -p no:cacheprovider`):
  1426 passed, 81 skipped (live-store / integration gates), 1 failed — the pre-existing, unrelated
  `tests/determinism/test_llm_controller.py::test_batched_client_sizes_calls_from_the_budget`
  (fake arity vs `_infer_batch_call`; fails identically on the untouched base
  commit b095761, also with `PYTHONPATH` pinned to the worktree).
- `scripts/repo_guard.py` → `repo guard: ok`; `scripts/agent_preflight.py` →
  `preflight: ok`; `scripts/wiki_worm.py --check` fails on the pre-existing
  `docs/wiki/decisions/0017-llm-direct-canon.md: missing front matter` (same on base).
- Worktree trap, measured: the shared venv installs `orchestrator` through a
  setuptools EDITABLE finder that maps `orchestrator.api` to the MAIN checkout;
  `python -m pytest` from a worktree binds `orchestrator` to the namespace dir
  `<root>/orchestrator`, so every `from orchestrator.api...` (tests AND the
  production code's own intra-package imports) resolves to the main checkout's
  files, while `orchestrator.orchestrator.*` imports resolve to the worktree.
  A plain worktree run therefore tested the main checkout's `orchestrator.api`
  and failed 13/17 of these tests until the suite bound `orchestrator.api` to
  its own checkout (`_bind_api_to_this_checkout`, top of the test module; the
  top-level `orchestrator` binding is left alone so both import styles keep
  working). Pinning `PYTHONPATH=<root>/orchestrator` instead breaks the 8
  integration modules that import `orchestrator.orchestrator.*` (collection
  errors) — do not use it.

## Rejected claims

- "Thread the filter through FAST/HYBRID/GRAPH too" — rejected for this
  slice: four engines (pass1 plan, hybrid lexical scan, graph seeding,
  wildcard) would each need their own store-side clause; a typed 422 is
  smaller and never lies. Addable per engine later without a contract change.
- "Trim the rows after retrieval" — rejected: `limit` must count filtered
  rows, so the clause runs in SQL / the Qdrant payload filter; the row-level
  drop in `build_evidence_rows` is a belt-and-braces invariant, not the mechanism.
- "Version `retrieve-evidence-rows` to v2" — rejected: the row shape is
  unchanged; TRAIL switches on `== "v1"`.

## Open contract gaps

- MCP `retrieve` / `compile_plan` tools do not yet expose `document_ids`
  (HTTP-only for now).
- Evidence-less facts stay authorized under a filter (unchanged R3a
  "fail loudly in assembly" rule); they never become evidence rows.
- Not yet live-probed against the fleet; no fleet restart in this slice.
