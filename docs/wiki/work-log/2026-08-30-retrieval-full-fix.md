---
change_id: RETRIEVAL-FULL-FIX-V1
owner: orchestrator
date: 2026-08-30
status: complete
architecture_impact: fenced (pass1, query_shape, knowledge_objects, projector, verifier) + orchestrator query tree; parent chunk-lane points retired store-wide
last_reviewed: 2026-08-30
---

# WORK LOG — RETRIEVAL-FULL-FIX-V1 (audit F2/F6/F7/F8/F10/F11/F12)

## Contract
Owner 2026-08-30: "i think i need all this fixed" — the remaining audit
scoreboard, with F7+F10 (breadth/depth caps, synthesis evidence budget)
explicitly delegated to be AI-designed against the owner's retrieval
style ("summaries for breadth and depth"; completeness questions must
enumerate), and F12 confirmed stale GLiNER-era naming contract.

## Changes
- ENTITY-CARD-LANE fusion (F2), `pass1-retrieval-v2`: routing_entity is
  a FUSED fourth RRF lane in the engine. A card votes once per document
  it evidences (payload doc_ids, capped `entity_card_max_docs_per_card=4`,
  card pool capped `entity_card_top_k=8`), so attribution lands in
  `rrf_contributions["routing_entity"]`. fast.py's advisory doc-vote
  re-sort REMOVED (double-counted against RRF, hid attribution); the
  probe there now only surfaces cards for the ask layer/response.
- BREADTH-V2 (F7 breadth, AI-designed): plan defaults widened where the
  owner's style concentrates value — sections 10→12, global children
  20→24, docs' section quota 2→3, final children 10→12, total 12→15.
  Derivation comment in pass1.py.
- DEPTH-V2 (F7 depth, AI-designed): completeness questions get
  sections-per-doc 8, final children 28, total 32, and depth-widened
  lanes (`section_summary_top_k=24`, `global_child_top_k=40`) — sized
  to carry a full chapter run (8 sections × 4 children) so "list ALL…"
  enumerates instead of truncating. query_shape.py depth_plan.
- EVIDENCE-BUDGET-V2 (F10): synthesis per-item text 1600→2000 chars
  (clears the measured chunk-size distribution, avg 1,197), bundle cap
  40→48 items so depth-profile evidence is not silently dropped at the
  synthesis door. ui.py.
- PARENT-POINT-RETIREMENT (F6): chunk lane projects tier='child' only
  (projector `_chunks_for_run` + verifier `_desired_chunk_ids`);
  `scripts/retire_parent_points.py` superseded receipts then deleted
  the 65 live parent points (cysa-study-v1) — receipts first, so a
  crash mid-script leaves true orphans the next verify sweep deletes.
- MULTI-CORPUS-FAST-V1 (F8): fast_retrieve accepts a corpus id list;
  pass1 already fans lanes out per corpus. Readiness stays per-corpus
  fail-closed. retrieve/chat/evidence FAST call sites pass the full
  authorized scope; HYBRID/GRAPH keep `single_corpus_or_422` (their
  engines are corpus-local) — documented in the gate docstring.
- SPARSE-TOKENIZER-CONTRACT (F11):
  tests/determinism/test_sparse_tokenizer_contract.py pins that every
  sparse-querying orchestrator module imports polymath_shared.sparse_bm25
  (source-level: no local tokenize/sparse_vector forks) and value-pins
  the shared derivation.
- OBJECT-NAME-CONTRACT-V2 (F12): `object_name_admissible` in
  knowledge_objects/concept.py = shared `is_term_surface` (ONE
  definition of "term" across extraction and objects) + repeated
  content-token rejection ("AWS Cloud DevOps Engineer Path DevOps").
  Wired into concept_name_admissible, legacy compile_concepts,
  procedure title fallback, AND /ask serve time: stale concept rows
  with junk names are never served; stale procedure rows keep their
  steps under the deterministic fallback title.

## Proof
- Determinism suite green except two PRE-EXISTING failures reproduced
  on the committed tree with this batch stashed:
  test_llm_controller.py::test_batched_client_sizes_calls_from_the_budget
  and test_sval_doc01_red (needs syntax sidecar :8744; fleet fenced).
- test_sparse_tokenizer_contract.py: 3/3 green.
- test_pass1/test_hybrid/test_batched_pass1/test_depth_policy: green
  against v2 plan values; r1c pin updated to `pass1-retrieval-v2`.
- Name gate probed: junk case rejects (`repeated_content_token`),
  "Chain of Custody of Evidence" admits (function words may repeat).
- retire_parent_points.py output: "cysa-study-v1: retired 65 parent
  points" — exactly the audit's count.
- LIVE acceptance (post-restart, serve orchestrator :7200):
  - FAST "what uses Amazon S3": plan `pass1-retrieval-v2`, top doc's
    rrf_contributions include `routing_entity: 0.0164` — card lane
    fused AND attributable (F2).
  - DEPTH "list all the CySA+ exam domains and all their subdomains":
    16 sections, **32 evidence items** — the full depth budget engaged
    (F7); previously capped at 10-16.
  - GRAPH same query: 7 graph_relationships — F1 baseline preserved.
  - /ask "aws cloud devops engineer path": CONCEPT route, every served
    name passes object_name_admissible; the junk winner is gone (F12).
  - /chat/stream FAST: streamed clean, latency_ms 4072 — within the
    4.9 s baseline despite the 2000×48 evidence budget (F10).
  - Multi-corpus FAST (F8) could not be exercised live — cysa-study-v1
    is the only corpus in this DB; the single-corpus path through the
    new list plumbing is proven above, per-corpus fan-out is
    unit-covered in test_pass1.

## Rejected claims
- "Verify will clean parent points on its own" — false: they hold
  ACTIVE receipts, so they are neither orphans (store−receipts) nor
  missing; explicit retirement was required.
- "Card doc-votes re-sort + fused lane can coexist" — rejected: the
  same signal applied twice, once outside RRF, unexplainable in traces.

## Open contract gaps
- test_llm_controller budget-sizing failure predates this batch
  (other-session territory) — untouched, needs its owner.
- HYBRID remains single-corpus by design; if the owner wants
  multi-corpus HYBRID, the in-memory lexical scan needs a per-corpus
  fan-out and score-space decision first.
- Stale concept/procedure rows are filtered at serve time only; a
  compile_objects re-run under OBJECT-NAME-CONTRACT-V2 retires them
  from Postgres (latent build, enrichment button).
