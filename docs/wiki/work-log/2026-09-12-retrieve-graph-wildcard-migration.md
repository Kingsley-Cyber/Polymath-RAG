---
title: "WORK LOG — /retrieve GRAPH + WILDCARD reader migration onto the final core (completes RETRIEVE-ENGINE-MIGRATION-V1)"
change_id: RETRIEVE-GRAPH-WILDCARD-MIGRATION-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.213
architecture_impact: "MIGRATE LEGACY READER (not DELETE STATE). /retrieve GRAPH and WILDCARD now ride the final chat_retrieve_mode core by default, behind the existing POLYMATH_RETRIEVE_ENGINE flag (v1 rollback). GRAPH's public response shape changes from v1's nested documents[].sections[].evidence to the flat evidence/selected_documents/selected_sections contract already used by /chat and /compare; WILDCARD's shape is a strict subset of v1's own. No retrieval policy, ranking, or graph semantics changed; graph_retrieve/wildcard_retrieve are untouched and remain reachable via the v1 rollback and via direct import (eval/r2a)."
---

> Executor session, owner directive 2026-09-11 (execution authority
> `POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md` §8 "IMMEDIATE SUBTASK: converge /retrieve GRAPH +
> WILDCARD"). Direct continuation of `RETRIEVE-ENGINE-MIGRATION-V1` (register 11.191), which migrated
> `/retrieve` HYBRID and explicitly left GRAPH/WILDCARD on v1 pending their own shape proof.

## Contract

Requested outcome: migrate `/retrieve`'s GRAPH and WILDCARD modes onto the already-qualified final
core (`chat_retrieve_mode`) where provably safe, preserving or consciously superseding each public
contract with evidence — same acceptance bar as 11.191.

- **Smallest acceptance:** `/retrieve` GRAPH and WILDCARD return the final core's evidence, work on
  legacy (non-vNext) corpora without error, and are reversible via the existing flag.
- **Owner / public contract:** `/retrieve` (GRAPH, WILDCARD) and MCP `retrieve` (which forwards
  `mode` verbatim).
- **Inputs/outputs/persistence:** reads the final core (local sidecars + Neo4j for GRAPH's hop-1);
  no state written; the existing `POLYMATH_RETRIEVE_ENGINE` flag selects engine.
- **Dependency edges:** `orchestrator/api/retrieve.py` → `orchestrator/api/chat_retrieval.chat_retrieve_mode`
  (already an established edge from the HYBRID migration). Reverse dependents: MCP `retrieve`,
  Frontend V2's raw retrieve surface (none currently call `/retrieve` with these modes directly
  today — `/chat` and `/compare` already bypass `/retrieve` and call `chat_retrieve_mode` themselves).
- **Verifier / rollback:** `tests/determinism/test_retrieve_graph_wildcard_engine_routing.py`;
  rollback `POLYMATH_RETRIEVE_ENGINE=v1` (zero code change, identical to 11.191).

## Changes

- `orchestrator/orchestrator/api/retrieve.py` — GRAPH and WILDCARD branches of `_retrieve_impl` gain
  the same `retrieve_engine_flag() == "v2" and not req.utility` gate HYBRID already uses: default
  (`v2`) calls `chat_retrieve_mode("GRAPH"|"WILDCARD", query, cid, **_kw)` with `req.latent` forwarded
  as a `latent_enabled` budget override (identical pattern to HYBRID's `_kw` construction); `v1` or
  `utility=True` falls back to the untouched `graph_retrieve`/`wildcard_retrieve` v1 services.
- `tests/determinism/test_retrieve_graph_wildcard_engine_routing.py` — new file, 7 cases
  (provider-free, monkeypatched `tx`/`resolve_http_scope`/`chat_retrieve_mode`/`graph_retrieve`/
  `wildcard_retrieve`): default-v2 routes to the final core for both modes, `v1` env rollback keeps
  the legacy service for both modes, `utility=True` keeps the legacy service under `v2` for both
  modes, `latent=True` forwards a `latent_enabled=True` budget to the final core.
- `docs/wiki/experiments/retrieve-graph-wildcard-migration-2026-09-12/` — live read-only shape/
  behavior evidence (README + `parity-result.json`) across `rag-canary`/`ecom-meta-v1`/`cinema`.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register **11.213**.
- `scripts/scaffold_polymath_v4.py` — TREE declarations for the new test file, work-log, and
  experiment evidence files.

## Proof

- **Live shape/behavior evidence (read-only, local, no spend):** direct Python calls to v1
  (`graph_retrieve`/`wildcard_retrieve`) and v2 (`chat_retrieve_mode`) on the SAME query per corpus
  across `rag-canary` (vNext), `ecom-meta-v1` (legacy), `cinema` (legacy, partial pMAP hold). Both
  engines succeeded, non-empty, zero errors, on every corpus for both modes.
  - GRAPH: v1 keys `{documents, graph_relationships, meta, query, trace,
    unassigned_rescue_evidence}` vs v2 keys `{evidence, graph_relationships, meta, query,
    selected_documents, selected_sections, trace}` — genuinely different shape, confirmed by design
    (see Rejected claims). `graph_relationships` (identical per-item shape) present on BOTH engines,
    every corpus: facts 10/10 (rag-canary), 9→12 (ecom-meta-v1, richer v2 evidence reseeds hop-1
    differently — same effect 11.191 already measured for HYBRID row counts), 20/20 (cinema, capped
    at `GRAPH_MAX_FACTS`).
  - WILDCARD: v1 keys `{entity_card_lane, evidence, meta, query, selected_documents,
    selected_sections, trace, wildcard}` vs v2 keys `{evidence, meta, query, selected_documents,
    selected_sections, trace, wildcard}` — v2 is a STRICT SUBSET of v1; `rg -n "entity_card_lane"`
    (repo-wide) shows zero readers of the one field lost. `wildcard` bridge count matches EXACTLY
    3/3 on all three corpora.
- **Contract guard: 7 passed** (`test_retrieve_graph_wildcard_engine_routing.py`) +
  **29 passed** (that file + `test_retrieve_engine_migration.py` + `test_document_scoped_retrieve.py`
  together, confirming no regression to the HYBRID migration or the document-filter 422 gate).
- Import/syntax check: `retrieve.py` compiles; both branches import `chat_retrieve_mode`/
  `default_budget` via the identical local-import pattern already proven safe for HYBRID (avoids the
  existing `chat_retrieval` ↔ `retrieve` cycle).
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Open runs = 0 stalled/blocked at edit time (fence-safe; `orchestrator/orchestrator/api/*` sits
  outside the HASH-FENCE-V2 fingerprinted dirs — `shared/polymath_shared`, `workers/workers`,
  `control/control` — so this edit does not trip the stale-bundle fence or require a fleet bounce;
  the running orchestrator serves the change after its next restart regardless).

## Rejected claims

- **"A compatibility adapter should reconstruct v1 GRAPH's nested `documents[]` shape."** REJECTED —
  direct inspection of every current caller found none that reads it: `/chat`'s `ui.py` and
  `/compare`'s `compare_review.py` already call `chat_retrieve_mode` directly for GRAPH/WILDCARD and
  their own docstrings/comments already treat the flat shape as canonical for `/retrieve`; Frontend
  V2's `contracts.ts::RetrieveResponse` is already typed flat; MCP's `retrieve` tool reads
  `out.get("evidence")` first — against today's v1 GRAPH shape (no top-level `evidence` key) this
  ALREADY silently returns nothing, so the migration fixes a live defect rather than risking one;
  `eval/r2a/harness.py` imports `graph_retrieve` directly, bypassing `/retrieve`'s dispatch entirely;
  `eval/i4`/`eval/historical/i3_5doc` already read `documents` OR `selected_documents` defensively.
  Building an unread adapter would be an unrequested abstraction (AGENTS.md §4: "reject any proposed
  file/abstraction... if deleting it would still leave the outcome satisfied").
- **"GRAPH/WILDCARD parity is byte-shape-identical like HYBRID's 11.191 finding."** REJECTED for
  GRAPH specifically — its shape genuinely changes (nested → flat) by design; this work-log makes
  that an explicit, evidence-backed claim rather than implying false byte-parity. WILDCARD, by
  contrast, IS near-total parity (v2 keys ⊂ v1 keys) and is reported as such, not overstated further.
- **"This deletes legacy state or retires graph_retrieve/wildcard_retrieve."** REJECTED — neither
  function is touched; both remain fully reachable via `POLYMATH_RETRIEVE_ENGINE=v1` and via direct
  import (`eval/r2a/harness.py` still imports `graph_retrieve` directly and is unaffected).

## Open contract gaps

- Per directive §10 ("do not stop after GRAPH/WILDCARD"), the remaining `graph.py`/`wildcard.py`/
  `hybrid.py`/`fast.py` readers are now classified with FILE:SYMBOL evidence:
  - **`orchestrator/api/evidence.py::evidence()`** (`POST /evidence`) — **RETIRE_CANDIDATE, not
    migrated this slice.** Unlike `/retrieve`, this is not a pass-through response-shape question:
    its GRAPH branch (lines ~71-95) WALKS v1's nested shape as an INPUT extraction pattern
    (`for d in g["documents"] for s in d["sections"] for c in s["evidence"]`) to build
    `child_evidence`/`document_summaries`/`section_summaries` for `assemble_evidence_bundle` — an
    evidence-integrity assembler that "fails LOUDLY... never silently drops." Migrating this
    requires rewriting that extraction against the final engine's flat `evidence`/
    `selected_documents`/`selected_sections`, not just swapping which function is called — real
    internal rewiring, correctly out of scope for "migrate without architectural redesign." Its
    HYBRID branch (line 121, `hybrid_fast_retrieve`) is the same already-known 11.191 gap
    ("evidence.py HYBRID... deferred to a follow-up"). Needs its own slice with its own tests.
  - **`/ask`** (`orchestrator/api/ask.py::ask`/`_ask_impl`) — **NOT_APPLICABLE.** Read in full:
    `/ask` is QUERY-ROUTER-V1, a deterministic knowledge-object lookup (FACT/PROCEDURE/CONCEPT/
    POLYMATH query types reading `procedure_artifacts`/`concept_artifacts`/facts/corpus-map
    directly, "nothing is generated; the response assembles"). It contains zero references to
    `graph_retrieve`/`wildcard_retrieve`/`hybrid_fast_retrieve`/`fast_retrieve`/`chat_retrieve_mode`
    — it was never part of the HYBRID/GRAPH/WILDCARD/FAST engine split this migration converges,
    confirming (not just repeating) 11.191's "distinct composite" note.
  - **`/retrieve` FAST (multi-corpus)** — **LEGACY_REQUIRED, structural.** `fast_retrieve` fans a
    query across N corpora; every final-core entrypoint (`chat_retrieve_mode`, and GRAPH/WILDCARD's
    own `single_corpus_or_422` gate) is single-corpus by design. Not a shape gap, an architecture
    mismatch — no migration is applicable until/unless the final core grows multi-corpus support,
    which is out of scope here (§4: "do not redesign the frozen architecture absent direct defect
    evidence").
  - **MCP `retrieve`/`retrieve_evidence`** (`orchestrator/mcp_server.py`) — **no code change
    needed.** Both forward `mode` verbatim to `/retrieve` and read `evidence` generically
    (`out.get("evidence") or out.get("hits")`); they benefit from this migration automatically
    (see Proof: this actually fixes a live `mode=GRAPH` defect, not just a compatibility no-op).
  - **`eval/r2a/harness.py`, `eval/i4`, `eval/historical/i3_5doc`** — **out of scope, unaffected.**
    Direct Python importers of `graph_retrieve`/`hybrid_fast_retrieve` (bypass `/retrieve` entirely)
    or already shape-defensive; not part of the `/retrieve` dispatch this migration changes.
- `/retrieve` FAST (multi-corpus) and the default/LEGACY (`retrieval_summaries`) path remain on v1
  machinery for reasons unrelated to shape (FAST is multi-corpus; the final core is single-corpus by
  design — `corpus_required`; LEGACY reads state that is DELETE-STATE/cutover-gated, not a reader
  migration).
- The §20A hot-path projection migration (Control Plane/Files performance) and the Frontend V2
  real-URL cutover gate are separate, larger slices — not addressed here.
