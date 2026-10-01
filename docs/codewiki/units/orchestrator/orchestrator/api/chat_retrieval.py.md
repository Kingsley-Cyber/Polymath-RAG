# unit: orchestrator/orchestrator/api/chat_retrieval.py
anchor: orchestrator/orchestrator/api/chat_retrieval.py:1-1392

## purpose
CHAT-RETRIEVAL-V2: the chat path's HYBRID retrieval on the CANDIDATE-RETRIEVAL-V1 engine, plus the mode compositions (VECTOR/FAST = A+B, HYBRID = A+B+C default, GRAPH = HYBRID + bounded G, WILDCARD = HYBRID ∥ W) and the experimental GNN mode — orchestrator/orchestrator/api/chat_retrieval.py:1-8, 22-34 [DERIVED]. `default_budget` is the one budget every surface starts from (chat, `/retrieve`, the evidence route, deep research's searches, the mode compositions) — orchestrator/orchestrator/api/chat_retrieval.py:260-263 [DERIVED]. Returns the same dict shape as `hybrid_fast_retrieve` so the stream handler, /chat, the bundle assembler and the funnel consume it unchanged — orchestrator/orchestrator/api/chat_retrieval.py:16-17 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| merge_atom_frontier | def | (parents: dict, atoms: list, maps: list) -> dict | orchestrator/orchestrator/api/chat_retrieval.py:98-134 | — |
| graph_dest_parents_from_maps | def | (maps: list, dest_docs: list[str], k: int) -> list[tuple[str, str]] | orchestrator/orchestrator/api/chat_retrieval.py:137-155 | — |
| bind_graph_fact_chunks | def | (facts: list[dict], preferred_chunk_ids: list[str]) -> list[dict] | orchestrator/orchestrator/api/chat_retrieval.py:158-185 | — |
| chat_retrieval_flag | def | (override: str | None) -> str | orchestrator/orchestrator/api/chat_retrieval.py:229-232 | — |
| default_budget | def | () -> CandidateBudget | orchestrator/orchestrator/api/chat_retrieval.py:260-275 | — |
| intent_policy_enabled | def | () -> bool | orchestrator/orchestrator/api/chat_retrieval.py:278-281 | — |
| chat_retrieve_v2 | def | (query, corpus_id, *, exact_terms=(), budget=None, query_id="q0", subqueries=(), lanes=None, latent_bridge_ids=(), on_context=None, scope=None, facets=(), second_pass=None) -> dict | orchestrator/orchestrator/api/chat_retrieval.py:284-289 | — |
| chat_retrieve_mode | def | (mode, query, corpus_id, graph_useful, graph_assist, keep_latent) -> dict | orchestrator/orchestrator/api/chat_retrieval.py:928-964 | — |

Module imported by compare_review.py, deep_research.py, evidence.py, retrieve.py, ui.py (per-symbol use not stated) — orchestrator/orchestrator/api/chat_retrieval.py:1-1392 [DERIVED].

## contracts

**chat_retrieve_v2** — orchestrator/orchestrator/api/chat_retrieval.py:284-820
- in: `corpus_id` must not be None, else HTTPException 422 `corpus_required` — orchestrator/orchestrator/api/chat_retrieval.py:308-311 [DERIVED].
- in: `lanes` must be ⊆ `LANES`, else 422 `unknown_lane` — orchestrator/orchestrator/api/chat_retrieval.py:312-316 [DERIVED].
- pre: `_ensure_fast_ready(corpus_id)`; Qdrant client `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` — orchestrator/orchestrator/api/chat_retrieval.py:317, 324 [DERIVED].
- effect: ONE pool `ThreadPoolExecutor(max_workers=max(1, int(budget.max_workers)), thread_name_prefix="chat-lanes")`; searcher built WITHOUT the query so lane C is the one sparse search of the turn — orchestrator/orchestrator/api/chat_retrieval.py:332-337 [DERIVED].
- post: subqueries truncated `[: budget.max_subqueries]`; texts deduped `list(dict.fromkeys(texts))` for one embedding call — orchestrator/orchestrator/api/chat_retrieval.py:342-344 [DERIVED].
- out: dict shaped like `hybrid_fast_retrieve`; `meta.plan_version` / `trace.plan` say `chat-retrieval-v2` — orchestrator/orchestrator/api/chat_retrieval.py:16-18 [DERIVED].
- `on_context`: called ONCE, in this thread, right after the embedding; it must not raise — orchestrator/orchestrator/api/chat_retrieval.py:302-306 [DERIVED].

**chat_retrieve_mode** — orchestrator/orchestrator/api/chat_retrieval.py:928-964
- VECTOR/FAST = lanes A + B; HYBRID = A + B + C (the default); GRAPH = HYBRID → bounded G over the FINAL evidence; WILDCARD = HYBRID ∥ W — orchestrator/orchestrator/api/chat_retrieval.py:25-34 [DERIVED].

**default_budget** — orchestrator/orchestrator/api/chat_retrieval.py:260-275
- Applies `facet_diversity_budget(b)` first when `facet_diversity_enabled()`, then env knobs `POLYMATH_CHAT_<NAME.upper()>` per `_INT_KNOBS`/`_FLOAT_KNOBS`/`_STR_KNOBS`; `ValueError` on a knob is ignored (pass) — orchestrator/orchestrator/api/chat_retrieval.py:264-274 [DERIVED].

**chat_retrieval_flag** — orchestrator/orchestrator/api/chat_retrieval.py:229-232
- Resolution order: `override` → env `POLYMATH_CHAT_RETRIEVAL` → `"v2"`; only `"v1"`, `"v2"`, `"v2-single"` accepted, anything else returns `"v2"` — orchestrator/orchestrator/api/chat_retrieval.py:231-232 [DERIVED].

**merge_atom_frontier** — orchestrator/orchestrator/api/chat_retrieval.py:98-134
- Existing latent slots keep precedence: `hop1` is max'd with the atom score; `abstraction` fills only when empty; empty atoms/maps leave `parents` unchanged (fail-open) — orchestrator/orchestrator/api/chat_retrieval.py:101-103, 124, 130-131 [DERIVED].

**graph_dest_parents_from_maps** — orchestrator/orchestrator/api/chat_retrieval.py:137-155
- Unique `parent_id`, capped at `k`; empty maps ⇒ empty list. Note: empty `dest_docs` makes `allowed` empty and the filter `if allowed and did not in allowed` is skipped, so all maps pass — orchestrator/orchestrator/api/chat_retrieval.py:139-151 [DERIVED].

**bind_graph_fact_chunks** — orchestrator/orchestrator/api/chat_retrieval.py:158-185
- SQL `SELECT DISTINCT ON (fact_id) fact_id, chunk_id FROM evidence ... ORDER BY fact_id, (chunk_id = ANY(%s)) DESC, chunk_id` prefers judged evidence chunks; a failing read leaves facts unchanged — orchestrator/orchestrator/api/chat_retrieval.py:168-176 [DERIVED].

## effect surface
- Postgres read: `evidence` (fact→chunk bind) — orchestrator/orchestrator/api/chat_retrieval.py:168-174 [DERIVED]; `document_parent_maps` (routing_signature lookup) — orchestrator/orchestrator/api/chat_retrieval.py:404-406 [DERIVED]; `mentions` — orchestrator/orchestrator/api/chat_retrieval.py:1-1392 [DERIVED] (per static analysis; site outside the shown excerpt).
- Postgres written: none — orchestrator/orchestrator/api/chat_retrieval.py:1-1392 [DERIVED].
- Qdrant: client at orchestrator/orchestrator/api/chat_retrieval.py:324 [DERIVED]; dense/latent searches via `searcher._search` — orchestrator/orchestrator/api/chat_retrieval.py:359, 363 [DERIVED]; profile/atom/parent-map collections via `_pj/_pap/_pmp.collection_name(cid)` — orchestrator/orchestrator/api/chat_retrieval.py:379, 388, 395 [DERIVED].
- Embedding calls: `_embed_queries` — orchestrator/orchestrator/api/chat_retrieval.py:250, 438 [DERIVED].
- Env flags: `POLYMATH_CHAT_RETRIEVAL` = `'v2'` — orchestrator/orchestrator/api/chat_retrieval.py:231 [DERIVED]; `POLYMATH_CHAT_INTENT_POLICY` = `''` — orchestrator/orchestrator/api/chat_retrieval.py:281 [DERIVED]; `POLYMATH_CHAT_LATENT_SELECTION` = `'0'` — orchestrator/orchestrator/api/chat_retrieval.py:741 [DERIVED]; `POLYMATH_LATENT_POOL_MAX` = `'60'` — orchestrator/orchestrator/api/chat_retrieval.py:745 [DERIVED]; generic `POLYMATH_CHAT_<KNOB>` overrides — orchestrator/orchestrator/api/chat_retrieval.py:269 [DERIVED].
- No subprocess or file writes visible in the shown material.

## invariants
- INVARIANT: GRAPH seeds ≤ 8, definitional seeds ≤ 2, facts ≤ 20, hop-1 — orchestrator/orchestrator/api/chat_retrieval.py:27-29 [DERIVED]
  fails-if: unbounded graph expansion breaks the mode's latency budget.
- INVARIANT: WILDCARD bridges ≤ 3 and never in the evidence list — orchestrator/orchestrator/api/chat_retrieval.py:33 [DERIVED]
  fails-if: bridges leak into evidence, changing what the funnel judges.
- INVARIANT: MAPPED_MIN_WINDOW_S (0.35) > MAPPED_MIN_LANES_S (0.2) — orchestrator/orchestrator/api/chat_retrieval.py:86-87 [DERIVED]
  fails-if: gate passes a window too small for the lanes, mapped pass starts then always skips.
- INVARIANT: pool workers = max(1, int(budget.max_workers)) ≥ 1 — orchestrator/orchestrator/api/chat_retrieval.py:333 [DERIVED]
  fails-if: zero workers would deadlock lane submission.
- INVARIANT: subqueries kept ≤ budget.max_subqueries — orchestrator/orchestrator/api/chat_retrieval.py:342 [DERIVED]
  fails-if: plan subqueries beyond the cap silently change retrieval breadth.
- INVARIANT: sparse searches per turn = 1 (lane C; searcher built WITHOUT the query) — orchestrator/orchestrator/api/chat_retrieval.py:335-337 [DERIVED]
  fails-if: a second BM25 probe doubles sparse cost, violating §3.21 #1.
- INVARIANT: embedding is a hard dependency — its breach is receipted, never dropped; lane past `lane_deadline_s` dropped + `<lane>_timeout`; judge past `rerank_deadline_s` → fusion order + `rerank_timeout` — orchestrator/orchestrator/api/chat_retrieval.py:10-14 [DERIVED]
  fails-if: degradation stops being visible in `meta.degraded`.
- INVARIANT: in-flight wildcard validation may overrun the frontier deadline by at most WILDCARD_FINISH_GRACE_S = 1.5 — orchestrator/orchestrator/api/chat_retrieval.py:88-90 [DERIVED]
  fails-if: partial wildcard results are abandoned or the deadline is exceeded unbounded.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` at 328, 633, 650, 830, 1003, 1134 and ~33 more sites; concurrency `ThreadPoolExecutor` at 333 and 1301; Postgres reads at 401-406; env knobs at 269) — orchestrator/orchestrator/api/chat_retrieval.py:328, 333, 1301, 401-406, 269 [DERIVED]
idempotency: SAFE (read-only retrieval: no tables written, no file writes) — orchestrator/orchestrator/api/chat_retrieval.py:1-1392 [DERIVED]

## failure behaviour
- Swallowed, caller sees the default: `Exception` → `return facts` at 175 (proving-child bind is additive) — orchestrator/orchestrator/api/chat_retrieval.py:175-176 [DERIVED]; `Exception` → `return []` at 432 (lift/precision lane) — orchestrator/orchestrator/api/chat_retrieval.py:432-433 [DERIVED]; `return []` at 540, 548, 563 (latent lanes inside chat_retrieve_v2) — orchestrator/orchestrator/api/chat_retrieval.py:540, 548, 563 [DERIVED]; `pass` at 393 (atom lane optional) — orchestrator/orchestrator/api/chat_retrieval.py:393-394 [DERIVED].
- Handled, raises: 422 `corpus_required` — orchestrator/orchestrator/api/chat_retrieval.py:309-311 [DERIVED]; 422 `unknown_lane` — orchestrator/orchestrator/api/chat_retrieval.py:313-316 [DERIVED]; 502 `qdrant_unavailable` — orchestrator/orchestrator/api/chat_retrieval.py:325-327 [DERIVED]; a raise path at 1131 inside `_retrieve_wildcard` — orchestrator/orchestrator/api/chat_retrieval.py:1131 [DERIVED].
- Handled, assign (degrade and continue): 348 (`sparse_q = None`, lane C degrades in the engine), 472 (`q_docs = []`, blend off, global door still runs), 586, 599, 834, 857, 1016, 1026, 1063, 1170, 1178, 1273, 1343 — orchestrator/orchestrator/api/chat_retrieval.py:348, 472, 586, 599, 834, 857, 1016, 1026, 1063, 1170, 1178, 1273, 1343 [DERIVED].
- Error-path returns: `_run_second_pass` returns `(rec, facets, round(...))` at 849; `_retrieve_wildcard` returns `(rows, rec, None)` at 1202 — orchestrator/orchestrator/api/chat_retrieval.py:849, 1202 [DERIVED].
- Degrations land in `meta.degraded`; per-stage `latency_ms` rides the trace — orchestrator/orchestrator/api/chat_retrieval.py:13-14 [DERIVED].

## dumb-code flags
- Mid-file imports after function bodies: `polymath_shared.retrieval_modes` and `polymath_shared.settings` imported at 186-197, below three defined functions (98-185) — orchestrator/orchestrator/api/chat_retrieval.py:186-197 [DERIVED].
- Merge→bounce shim: `ImportError` on `fact_rank_enabled` installs a stub returning `False` (comment dated 2026-09-25: old process serves legacy order until the bounce) — orchestrator/orchestrator/api/chat_retrieval.py:217-224 [DERIVED].
- Magic numbers: 0.35 / 0.2 windows (86-87), 1.5 grace (90), `atom_k` default 12 (389), lift `k=3` (431), `doc_steer_items` 4 (484), Qdrant `timeout=60` (324) — orchestrator/orchestrator/api/chat_retrieval.py:86-87, 90, 389, 431, 484, 324 [DERIVED].
- Defensive `getattr(budget, ...)` with silent defaults tolerates budget schema drift: `"atom_kinds"` at 384/431/455, `"atom_k", 12` at 389, `"doc_steer_kinds"` at 480 — orchestrator/orchestrator/api/chat_retrieval.py:384, 431, 455, 389, 480 [DERIVED].
- Env-name prefix built three ways: f-string `f"POLYMATH_CHAT_{name.upper()}"` (269) vs `_FLAG_ENV = "POLYMATH_CHAT_RETRIEVAL"` (226) vs spelled-out knob comments (237-248) — orchestrator/orchestrator/api/chat_retrieval.py:226, 237-248, 269 [DERIVED].
- Legacy 4-tuple subquery specs padded to 6 fields via `(tuple(x) + ("",) * 6)[:6]` — orchestrator/orchestrator/api/chat_retrieval.py:341-342 [DERIVED].

## refactor notes
- Result dict shape is consumed unchanged by the stream handler, /chat, the bundle assembler and the funnel — any shape change has that blast radius — orchestrator/orchestrator/api/chat_retrieval.py:16-17 [DERIVED].
- Five modules import this file (compare_review, deep_research, evidence, retrieve, ui); symbol renames hit all of them — orchestrator/orchestrator/api/chat_retrieval.py:1-1392 [DERIVED].
- `default_budget` is the single budget authority; renaming entries in `_INT_KNOBS`/`_FLOAT_KNOBS`/`_STR_KNOBS` changes the public `POLYMATH_CHAT_*` env contract — orchestrator/orchestrator/api/chat_retrieval.py:236-257, 261-263 [DERIVED].
- Underscore-private helpers imported cross-module from `orchestrator.api.fast` (`_begin_retrieval`, `_embed_queries`, `_rerank_children`, …) — renaming them there breaks this file — orchestrator/orchestrator/api/chat_retrieval.py:199-212 [DERIVED].
- `POLYMATH_CHAT_RETRIEVAL=v1` is the documented rollback boundary keeping /retrieve, /ask and TRAIL on `hybrid-retrieval-v1` — do not remove until the v2 gate is permanent — orchestrator/orchestrator/api/chat_retrieval.py:18-20 [DERIVED].
- GRAPH/WILDCARD caps come from `polymath_shared.retrieval_modes` (`GRAPH_MAX_SEEDS`, `GRAPH_DEFINITIONAL_MAX_SEEDS`, `GRAPH_MAX_FACTS`) — changing them there changes this route's bounds — orchestrator/orchestrator/api/chat_retrieval.py:186-196 [DERIVED].

## VERIFY
```verify
grep -Fq 'WILDCARD_FINISH_GRACE_S = 1.5' orchestrator/orchestrator/api/chat_retrieval.py
grep -Eq 'MAPPED_MIN_WINDOW_S = 0\.35' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'corpus_required' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'qdrant_unavailable' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'mode-composition-v1' orchestrator/orchestrator/api/chat_retrieval.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/chat_retrieval.py
test "$(grep -c -F 'time.perf_counter' orchestrator/orchestrator/api/chat_retrieval.py)" -ge 30
```
