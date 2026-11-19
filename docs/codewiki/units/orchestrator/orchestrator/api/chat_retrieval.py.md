# unit: orchestrator/orchestrator/api/chat_retrieval.py
anchor: orchestrator/orchestrator/api/chat_retrieval.py:1-1493

## purpose
The chat path's HYBRID retrieval on the CANDIDATE-RETRIEVAL-V1 engine (plan §3.14, P1.a/P1.d) — one readiness check, lane C head start, one embedding, lanes A/B concurrent, one bounded rerank — orchestrator/orchestrator/api/chat_retrieval.py:1-14 [DERIVED].
Also owns MODE-COMPOSITION-V1 (§3.15/§3.18/§3.19): VECTOR (FAST) = A+B, HYBRID = A+B+C, GRAPH = HYBRID + bounded G over final evidence, WILDCARD = HYBRID ∥ W — orchestrator/orchestrator/api/chat_retrieval.py:22-34 [DERIVED].
Returns the same dict shape as `hybrid_fast_retrieve`, so the stream handler, /chat, the bundle assembler and the funnel consume it unchanged; `/retrieve`, `/ask`, TRAIL stay on `hybrid-retrieval-v1` (rollback: `POLYMATH_CHAT_RETRIEVAL=v1` or per-request `retrieval: "v1"`) — orchestrator/orchestrator/api/chat_retrieval.py:16-20 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| chat_retrieve_v2 | def | (query, corpus_id, exact_terms, budget, query_id, subqueries, lanes, latent_bridge_ids, on_context, scope, facets, second_pass) -> dict | orchestrator/orchestrator/api/chat_retrieval.py:370-375 | — |
| chat_retrieve_mode | def | (mode, query, corpus_id, graph_useful, graph_assist, keep_latent) -> dict | orchestrator/orchestrator/api/chat_retrieval.py:1014 | — |
| default_budget | def | () -> CandidateBudget | orchestrator/orchestrator/api/chat_retrieval.py:346 | — |
| chat_retrieval_flag | def | (override) -> str | orchestrator/orchestrator/api/chat_retrieval.py:315 | — |
| intent_policy_enabled | def | () -> bool | orchestrator/orchestrator/api/chat_retrieval.py:364 | — |
| merge_atom_frontier | def | (parents: dict, atoms: list, maps: list) -> dict | orchestrator/orchestrator/api/chat_retrieval.py:99 | — |
| graph_dest_parents_from_maps | def | (maps: list, dest_docs: list[str], k: int) -> list[tuple[str, str]] | orchestrator/orchestrator/api/chat_retrieval.py:138 | — |
| bind_graph_fact_chunks | def | (facts: list[dict], preferred_chunk_ids: list[str]) -> list[dict] | orchestrator/orchestrator/api/chat_retrieval.py:159 | — |
| order_facts_by_query_similarity | def | (facts, qvec, evidence_chunk_ids, *, embed, floor, cap) -> (list[dict], dict) | orchestrator/orchestrator/api/chat_retrieval.py:279-280 | — |
| fact_query_sim_enabled | def | () -> bool | orchestrator/orchestrator/api/chat_retrieval.py:238 | — |
| fact_sentence | def | (fact: dict) -> str | orchestrator/orchestrator/api/chat_retrieval.py:251 | — |

Module importers (per-symbol callers unknown): compare_review.py, deep_research.py, evidence.py, retrieve.py, ui.py — orchestrator/orchestrator/api/chat_retrieval.py (FACTS.importers) [DERIVED].
Internal helpers (underscore-prefixed): `_run_second_pass` 909, `_with_graph_assist` 987, `_fast_budget` 1006, `_retrieve_gnn` 1053, `_attach_graph` 1079, `_unverified_bridges` 1151, `_jaccard_tokens` 1185, `_facet_query_texts` 1190, `_retrieve_wildcard` 1201 — orchestrator/orchestrator/api/chat_retrieval.py:909-1201 [DERIVED].

## contracts

**chat_retrieve_v2** — orchestrator/orchestrator/api/chat_retrieval.py:370-392
- in: `query: str`, `corpus_id: str` (required), `subqueries` = (id, type, text, weight[, origin, derived_from]) tuples, padded to 6 fields and capped at `budget.max_subqueries` — orchestrator/orchestrator/api/chat_retrieval.py:428.
- in: `facets` = ((facet_id, (query_ids…)), …); empty = per-query aspect seats — orchestrator/orchestrator/api/chat_retrieval.py:378-379.
- in: `second_pass` seam called ONCE, in-thread, between lanes and judge; returns (rows, receipt, deadline) — orchestrator/orchestrator/api/chat_retrieval.py:380-385.
- in: `on_context` called ONCE, in-thread, with the immutable SearchContext + turn pool, right after the embedding; it must not raise — orchestrator/orchestrator/api/chat_retrieval.py:388-392.
- pre: `corpus_id` not None else HTTP 422 `corpus_required` — orchestrator/orchestrator/api/chat_retrieval.py:394-397; `lanes` ⊆ `LANES` else HTTP 422 `unknown_lane` — orchestrator/orchestrator/api/chat_retrieval.py:398-402.
- post: result dict shape identical to `hybrid_fast_retrieve`; `meta.plan_version` / `trace.plan` say `chat-retrieval-v2` — orchestrator/orchestrator/api/chat_retrieval.py:16-19.
- post: one embedding call for all distinct texts (`[query] + subquery texts`, deduped via `dict.fromkeys`) — orchestrator/orchestrator/api/chat_retrieval.py:429-430.

**chat_retrieve_mode** — orchestrator/orchestrator/api/chat_retrieval.py:1014-1017
- in: mode name + query/corpus_id + graph switches. out: dict.
- post: one engine, four compositions — VECTOR/FAST = A + B; HYBRID = A + B + C; GRAPH = HYBRID + bounded G; contract stamp `mode-composition-v1` (constant at 974).

**order_facts_by_query_similarity** — orchestrator/orchestrator/api/chat_retrieval.py:279-309
- in: facts, question vector `qvec`, this turn's evidence chunk ids, injectable `embed`, optional `floor`, `cap` (default `GRAPH_MAX_FACTS`).
- post: each scored fact gains `query_similarity`; order key = (evidence-attested first, then −similarity, then resolver index) — orchestrator/orchestrator/api/chat_retrieval.py:299-307.
- post: with a `floor`, an unattested fact below it is dropped; an attested fact is never dropped — orchestrator/orchestrator/api/chat_retrieval.py:302-305.

**merge_atom_frontier** — orchestrator/orchestrator/api/chat_retrieval.py:99-135
- in: `parents` dict, `atoms` list, `maps` list. out: merged parents dict.
- post: existing latent slots keep precedence — `hop1` is max'd, `abstraction` fills only when empty — orchestrator/orchestrator/api/chat_retrieval.py:125-132.
- post: fail-open — empty atoms or maps leave `parents` unchanged — orchestrator/orchestrator/api/chat_retrieval.py:103-114.

**graph_dest_parents_from_maps** — orchestrator/orchestrator/api/chat_retrieval.py:138-156
- in: maps, allowed `dest_docs`, cap `k`. out: unique `(doc_id, parent_id)` pairs, length ≤ `k` — orchestrator/orchestrator/api/chat_retrieval.py:148-155.

**bind_graph_fact_chunks** — orchestrator/orchestrator/api/chat_retrieval.py:159-186
- in: facts with `fact_id`, preferred chunk ids. out: facts with proving `chunk_id` attached.
- post: SQL prefers chunks in `preferred_chunk_ids` (`ORDER BY fact_id, (chunk_id = ANY(%s)) DESC`) — orchestrator/orchestrator/api/chat_retrieval.py:169-174.

**default_budget** — orchestrator/orchestrator/api/chat_retrieval.py:346-361
- out: `CandidateBudget`; `facet_diversity_budget` applied first when `facet_diversity_enabled()`, then env knobs `POLYMATH_CHAT_<NAME>` override single values — orchestrator/orchestrator/api/chat_retrieval.py:350-360.

**chat_retrieval_flag** — orchestrator/orchestrator/api/chat_retrieval.py:315-318
- out: `"v1" | "v2" | "v2-single"`; anything else falls back to `"v2"`.

## effect surface
- Postgres read: `evidence` (fact→chunk bind, DISTINCT ON) — orchestrator/orchestrator/api/chat_retrieval.py:169-175; `document_parent_maps`, `mentions` (FACTS.tables_read) [DERIVED]. Postgres written: none (FACTS.tables_written = []) [DERIVED].
- Qdrant: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` per call — orchestrator/orchestrator/api/chat_retrieval.py:410.
- Network: `EmbedderClient(priority="interactive")`, `.embed(..., "child_chunk")` — orchestrator/orchestrator/api/chat_retrieval.py:268-275.
- Concurrency: `ThreadPoolExecutor(max_workers=max(1, int(budget.max_workers)), thread_name_prefix="chat-lanes")` — orchestrator/orchestrator/api/chat_retrieval.py:419; a second pool at 1402.
- Env flags (name = default): `POLYMATH_CHAT_RETRIEVAL` = 'v2' (317), `POLYMATH_GRAPH_FACT_QUERY_SIM` = '0' (239), `POLYMATH_GRAPH_FACT_SIM_FLOOR` = '' (243), `POLYMATH_CHAT_INTENT_POLICY` = '' (367), `POLYMATH_CHAT_LATENT_SELECTION` = '0' (827), `POLYMATH_LATENT_POOL_MAX` = '60' (831), plus the `POLYMATH_CHAT_<NAME>` knob family over `_INT_KNOBS`/`_FLOAT_KNOBS`/`_STR_KNOBS` (322-356) — orchestrator/orchestrator/api/chat_retrieval.py:239-356 [DERIVED].
- Files: none read or written in visible source.

## invariants
INVARIANT: FAST/VECTOR lanes = {A, B} ⊂ HYBRID lanes = {A, B, C} — orchestrator/orchestrator/api/chat_retrieval.py:25-27, 1006 [DERIVED]
  fails-if: FAST budget gains lane C → "FAST isn't [more than A + B]" contract (owner quote, 1006) breaks.
INVARIANT: GRAPH = HYBRID + bounded G with ≤ 8 seeds (≤ 2 when the plan says non-relational), hop-1, ≤ 20 facts, fail-open — orchestrator/orchestrator/api/chat_retrieval.py:27-29 [DERIVED]
  fails-if: unbounded graph expansion changes GRAPH latency and fact count.
INVARIANT: WILDCARD bridges ≤ 3 and never in the evidence list — orchestrator/orchestrator/api/chat_retrieval.py:33-34 [DERIVED]
  fails-if: a bridge in evidence changes the answer's citation surface.
INVARIANT: facts scored per GRAPH turn = `_FACT_SIM_POOL` = 32 = the embedder sidecar's wire cap — orchestrator/orchestrator/api/chat_retrieval.py:234-235 [DERIVED]
  fails-if: pool > 32 breaks the single embedder request.
INVARIANT: kept facts from `order_facts_by_query_similarity` ≤ `cap` (default `GRAPH_MAX_FACTS`) — orchestrator/orchestrator/api/chat_retrieval.py:307-308 [DERIVED]
  fails-if: resolver's 20-fact contract exceeded.
INVARIANT: `graph_dest_parents_from_maps` output has unique `parent_id` and length ≤ `k` — orchestrator/orchestrator/api/chat_retrieval.py:148-155 [DERIVED]
  fails-if: duplicate parents or unbounded list reach lane H.
INVARIANT: `merge_atom_frontier` never lowers `hop1` (max of existing and atom score) — orchestrator/orchestrator/api/chat_retrieval.py:125 [DERIVED]
  fails-if: existing latent slot precedence lost.
INVARIANT: subquery specs accepted per turn ≤ `budget.max_subqueries` — orchestrator/orchestrator/api/chat_retrieval.py:428 [DERIVED]
  fails-if: embedding batch and lane count grow unbounded.
INVARIANT: `POLYMATH_CHAT_INTENT_POLICY` unset leaves the budget byte-identical — orchestrator/orchestrator/api/chat_retrieval.py:365-367 [DERIVED]
  fails-if: default-on policy silently changes retrieval for every surface.

## determinism & idempotency
determinism: NONDETERMINISTIC — clocks `time.perf_counter` at 41 sites (e.g. orchestrator/orchestrator/api/chat_retrieval.py:414, 719, 1408, 1486); concurrency `ThreadPoolExecutor` at 419 and 1402; network Qdrant 410 / embedder 270; db read 169; env flags 239, 317, 367 [DERIVED]
idempotency: SAFE — no tables written (FACTS.tables_written = []), no file writes; all lanes are reads [DERIVED]

## failure behaviour
| site | on | behaviour | anchor |
|---|---|---|---|
| QdrantClient ctor | Exception | raise HTTP 502 `qdrant_unavailable` | orchestrator/orchestrator/api/chat_retrieval.py:411-413 |
| corpus_id None | — | raise HTTP 422 `corpus_required` | orchestrator/orchestrator/api/chat_retrieval.py:394-397 |
| unknown lane name | — | raise HTTP 422 `unknown_lane` | orchestrator/orchestrator/api/chat_retrieval.py:398-402 |
| evidence bind read | Exception | SWALLOWED: return facts unchanged (proving-child bind is additive) | orchestrator/orchestrator/api/chat_retrieval.py:176-177 |
| fact scoring (embed/cosine) | Exception | SWALLOWED: return first `cap` facts untouched, receipt `degraded:<ExcType>` | orchestrator/orchestrator/api/chat_retrieval.py:295-297 |
| `sparse_vector_for(query, …)` | Exception | handled: `sparse_q = None`, lane C degrades in the engine | orchestrator/orchestrator/api/chat_retrieval.py:432-435 |
| wildcard inner paths | Exception | SWALLOWED: `return []` at 518, 626, 634, 649; `pass` at 479 | orchestrator/orchestrator/api/chat_retrieval.py:479-649 [DERIVED] |
| wildcard core | Exception | handled: raise at 1232 | orchestrator/orchestrator/api/chat_retrieval.py:1232 [DERIVED] |
Wall-clock contract: a core lane past `lane_deadline_s` is dropped and receipted `<lane>_timeout`; a judge past `rerank_deadline_s` yields fusion order + `rerank_timeout`; all land in `meta.degraded` — orchestrator/orchestrator/api/chat_retrieval.py:11-14 [DERIVED].

## dumb-code flags
- Magic timeouts/thresholds as bare literals: `0.35`, `0.2` (mapped window/lanes), `1.5` (finish grace), `32` (fact pool), Qdrant `timeout=60` — orchestrator/orchestrator/api/chat_retrieval.py:87-91, 235, 410 [DERIVED].
- `POLYMATH_LATENT_POOL_MAX` default '60' sits beside a fact pool hard-capped at 32; two separate pool knobs, one file — orchestrator/orchestrator/api/chat_retrieval.py:235, 831 [INFERRED: different pools, easy to conflate when tuning].
- `POLYMATH_GRAPH_FACT_SIM_FLOOR` ships uncalibrated: "No value has been measured for this embedder — calibrate on a gold set before setting one" — orchestrator/orchestrator/api/chat_retrieval.py:232-233 [DERIVED].
- Imports placed after function bodies (mid-file): `retrieval_modes` at 187-197, `settings` at 198, `retrieve`/`graph` at 215-216 — orchestrator/orchestrator/api/chat_retrieval.py:187-217 [DERIVED].
- `fact_rank_enabled` ImportError shim hard-returns False during a merge → bounce window (an orchestrator started before D1 keeps the old module; the unguarded import made /retrieve GRAPH answer 500) — orchestrator/orchestrator/api/chat_retrieval.py:219-226 [DERIVED].
- Two env-name patterns: knob family built by f-string `POLYMATH_CHAT_{name.upper()}` (355) vs full-literal flags (230, 233, 312) — orchestrator/orchestrator/api/chat_retrieval.py:230-355 [DERIVED].
- `_run_second_pass` and `_retrieve_wildcard` bodies (910-968, 1202-1492) are not in the visible source window; only FACTS metadata describes them — orchestrator/orchestrator/api/chat_retrieval.py:909-1492 [INFERRED: source capped at line 1409 in the excerpt].

## refactor notes
- Result dict shape is the compatibility contract with `hybrid_fast_retrieve` (stream handler, /chat, bundle assembler, funnel) — changing keys breaks four consumers — orchestrator/orchestrator/api/chat_retrieval.py:16-19 [DERIVED].
- Five importers depend on this module (compare_review, deep_research, evidence, retrieve, ui); renaming any public symbol is a cross-module change — orchestrator/orchestrator/api/chat_retrieval.py (FACTS.importers) [DERIVED].
- `chat_retrieve_v2` is ~536 lines with closures (`dense_search` 441, `latent_search` 447, `dualread_search` 451) capturing `searcher`, `collection`, `vecs`, `budget`, `pool`; the seams `_run_second_pass` / `_with_graph_assist` / `_retrieve_wildcard` depend on these internals — extraction must thread that state — orchestrator/orchestrator/api/chat_retrieval.py:370-451, 909-1201 [INFERRED: closure capture visible at 441-451].
- Knob env names and defaults are the operator contract ("measurement only; the defaults are the contract") — renaming a knob silently disables an operator override — orchestrator/orchestrator/api/chat_retrieval.py:321, 346-361 [DERIVED].
- Keep the `fact_rank_enabled` import guard until the merge-bounce failure mode is retired; removing it reintroduced a /retrieve GRAPH 500 once — orchestrator/orchestrator/api/chat_retrieval.py:219-226 [DERIVED].
- `on_context` must stay single-call, in-thread, non-raising; the graph seeds and the wildcard sweep take the primary vector through it, "never through the result dict" — orchestrator/orchestrator/api/chat_retrieval.py:36-38, 388-392 [DERIVED].

## VERIFY
```verify
grep -Fq 'MAPPED_MIN_WINDOW_S = 0.35' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'WILDCARD_FINISH_GRACE_S = 1.5' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq '_FACT_SIM_POOL = 32' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'MODE_COMPOSITION_CONTRACT' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'qdrant_unavailable' orchestrator/orchestrator/api/chat_retrieval.py
test "$(grep -c -F 'time.perf_counter' orchestrator/orchestrator/api/chat_retrieval.py)" -ge 30
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/chat_retrieval.py
```
