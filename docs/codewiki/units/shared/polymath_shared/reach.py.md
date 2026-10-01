# unit: shared/polymath_shared/reach.py
anchor: shared/polymath_shared/reach.py:1-402

## purpose
R1E Pass-2 corpus reach: finds complementary documents beyond the direct Pass-1 winner set (shared/polymath_shared/reach.py:1-2) [DERIVED]. Builds a deterministic reach query = original query + bounded Pass-1 concepts (no LLM, no HyDE), searches summary lanes over documents excluded from Pass 1, and returns evidence tagged `reach_pass=2` that is never direct factual support (shared/polymath_shared/reach.py:7-12, 23) [DERIVED]. Consumed by retrieval orchestration via `reach_retrieve`.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `CorpusReachPlan` | frozen dataclass | fields incl. `max_seed_concepts=6`, `document_summary_top_k=15`, `section_summary_top_k=15`, `lexical_enabled=False`, `lexical_top_k=15`, `rrf_k=60`, `max_reach_documents=3`, `max_sections_per_document=2`, `max_children_per_section=2`, `max_reach_children=6`, `rerank_enabled=True` | shared/polymath_shared/reach.py:43-64 | — |
| `REACH_DEFAULT_PLAN` | constant | `CorpusReachPlan()` | shared/polymath_shared/reach.py:66 | — |
| `Pass1ConceptState` | dataclass | fields `original_query, concepts, entities, relationships, section_themes, source_doc_ids`; methods `expansion_terms`, `serialized_query` | shared/polymath_shared/reach.py:92-110 | — |
| `build_concept_state` | def | `(pass1_result: Pass1Result, *, max_seed_concepts=6, profile_concepts=None, entities_for_evidence=None, predicates_for_evidence=None) -> Pass1ConceptState` | shared/polymath_shared/reach.py:120-190 | — |
| `ReachDocumentCandidate` | dataclass | fields `doc_id, corpus_id, summary_hits, section_hits, lexical_hits, rrf_contributions, aggregate_score, aggregate_rank, seed_concepts` | shared/polymath_shared/reach.py:193-203 | — |
| `ReachResult` | dataclass | fields `query, plan, concept_state, reach_query, excluded_doc_ids, documents, selected_documents, selected_sections, final_evidence, trace` | shared/polymath_shared/reach.py:206-217 | — |
| `reach_retrieve` | def | `(query, pass1_result, *, plan=REACH_DEFAULT_PLAN, embed_query, routing_search, lexical_search=None, rerank_children=None, concept_state=None) -> ReachResult` | shared/polymath_shared/reach.py:220-402 | — |

Module constants: `REACH_PLAN_VERSION="corpus-reach-v1"` (shared/polymath_shared/reach.py:34), `ARRIVAL_REACH_SECTION_LED="REACH_SECTION_LED"` (39), `ARRIVAL_REACH_LEXICAL="REACH_LEXICAL"` (40) [DERIVED].

## contracts

**`reach_retrieve`** (shared/polymath_shared/reach.py:220-402)
- in: `query: str`, `pass1_result: Pass1Result`; keyword-only `embed_query` and `routing_search` are required with no defaults (shared/polymath_shared/reach.py:225-226) [DERIVED].
- pre: `pass1_result.plan.corpus_ids` is accessed (shared/polymath_shared/reach.py:239, 318); `routing_search` must return rows with `score` and `payload` keys `corpus_id/doc_id/parent_id/chunk_id/summary_id/source_name/text` (shared/polymath_shared/reach.py:243-256, 322-333) [DERIVED].
- out: `ReachResult`; `excluded_doc_ids` = sorted unique Pass-1 selected doc_ids (shared/polymath_shared/reach.py:231) [DERIVED].
- post: `len(final_evidence) <= plan.max_reach_children` (shared/polymath_shared/reach.py:359); every evidence dict carries `"reach_pass": 2` (335, 354); rerank preserves candidate-set membership (367); trace records `reach_query`, `lane_sizes`, `pre_g3_order`, `post_g3_order` (373-389) [DERIVED].

**`build_concept_state`** (shared/polymath_shared/reach.py:120-190)
- in: `pass1_result`; optional `profile_concepts: dict[str, list[str]]`, `entities_for_evidence: Callable[[list[str]], list[dict]]`, `predicates_for_evidence: Callable[[list[str]], list[str]]` (shared/polymath_shared/reach.py:120-127) [DERIVED].
- pre: each `final_evidence` child must have `"chunk_id"` (KeyError otherwise, shared/polymath_shared/reach.py:132) [DERIVED].
- out: `Pass1ConceptState` with concepts sorted `(-weight, term)`, capped at `max_seed_concepts`, each carrying `"provenance": "pass1"` (shared/polymath_shared/reach.py:176-185) [DERIVED].
- post: every admitted term passed `_admit_term` (shared/polymath_shared/reach.py:136-139) [DERIVED].

**`Pass1ConceptState.serialized_query`** (shared/polymath_shared/reach.py:105-110)
- out: `original_query` alone when no expansion terms, else `original_query + " " + " ".join(expansion_terms)`; deterministic, recorded in trace (shared/polymath_shared/reach.py:107-110, 375) [DERIVED].

## effect surface
- Postgres tables: none (FACTS `tables_read=[]`, `tables_written=[]`).
- Vector store: accessed only via injected `routing_search`; filters `{"representation_kind", "corpus_id", "exclude_doc_ids"}` (shared/polymath_shared/reach.py:237-241) and `{"representation_kind": "routing_child", "corpus_id", "doc_id", "parent_id"}` (316-321) [INFERRED: implies a payload-indexed vector store behind the callable, per filter key names].
- External calls: `embed_query(reach_query)` (shared/polymath_shared/reach.py:234), `routing_search("", qvec, filters)` (243, 322), `lexical_search(reach_query, plan.lexical_top_k)` (263), `rerank_children(query, final_evidence)` (365) [DERIVED].
- Files, subprocesses, env flags: none.

## invariants
INVARIANT: concept weight `profile_core_concept`=5 > `entity`=4 > `relationship`=3 > `multi_child`=2 > `summary`=1 — shared/polymath_shared/reach.py:151,157,161,169,174 [DERIVED]
  fails-if: weak summary terms outrank profile concepts and consume the seed budget.
INVARIANT: `multi_child` term requires document frequency `>= 2` across selected children — shared/polymath_shared/reach.py:168-169 [DERIVED]
  fails-if: single-child noise becomes an expansion seed.
INVARIANT: `len(concepts) <= max_seed_concepts` (default 6) — shared/polymath_shared/reach.py:179, 49 [DERIVED]
INVARIANT: `len(selected_documents) <= max_reach_documents` (default 3) — shared/polymath_shared/reach.py:299, 58 [DERIVED]
INVARIANT: `len(sections) <= max_sections_per_document * len(selected_documents)` (default 2*3=6) — shared/polymath_shared/reach.py:311, 59 [DERIVED]
INVARIANT: children per section `<= max_children_per_section` (default 2) — shared/polymath_shared/reach.py:322, 60 [DERIVED]
INVARIANT: `len(final_evidence) <= max_reach_children` (default 6) — shared/polymath_shared/reach.py:359, 61 [DERIVED]
INVARIANT: `set(post_g3) == set(pre_g3)` after rerank — shared/polymath_shared/reach.py:367 [DERIVED]
  fails-if: AssertionError `"G3 changed the reach candidate set"`.
INVARIANT: reach doc_ids ∩ `excluded_doc_ids` = ∅ — shared/polymath_shared/reach.py:231, 240, 264, 344 [DERIVED]
  fails-if: Pass-1 documents re-enter as reach evidence.
INVARIANT: RRF contribution per hit = `1.0 / (plan.rrf_k + hit.rank + 1)` with `rrf_k=60` — shared/polymath_shared/reach.py:286-287, 56 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (depends on injected callables `embed_query` shared/polymath_shared/reach.py:234, `routing_search` 243/322, `lexical_search` 263, `rerank_children` 365 — external model/store results). All internal tie-breaks are deterministic: `(-weight, term)` 178, `(-aggregate_score, doc_id)` 296, `(doc_id, arrival, chunk_id)` 358-359.
idempotency: SAFE (pure computation; no table/file writes, FACTS `tables_written=[]`; reads only via injected callables).

## failure behaviour
- `AssertionError("G3 changed the reach candidate set")` if `rerank_children` adds/drops candidates (shared/polymath_shared/reach.py:367); caller receives no `ReachResult` [DERIVED].
- `KeyError` on `c["chunk_id"]` if a Pass-1 evidence child lacks that key (shared/polymath_shared/reach.py:132) [DERIVED].
- No try/except in the unit; exceptions from injected callables propagate (shared/polymath_shared/reach.py:234, 243, 263, 365) [DERIVED].
- Missing payload fields silently degrade to empty strings via `payload.get(...) or ""` / `payload.get(..., "")` (shared/polymath_shared/reach.py:252-255, 325, 329-332) [DERIVED].

## dumb-code flags
- Dead import: `aggregate_documents_n` imported, never used (shared/polymath_shared/reach.py:32) [DERIVED].
- Dead constants: `PASS1_DIRECT` (36) and `PASS2_CORPUS_REACH` (37) defined, unreferenced in this file [DERIVED].
- Lane label asymmetry: lane name `"reach_lexical"` (shared/polymath_shared/reach.py:273) vs `"routing_document_summary"`/`"routing_section_summary"` (269-270); `rrf_contributions` keys mix two naming schemes (286) [DERIVED].
- Hardcoded weights 5/4/3/2/1 not configurable via `CorpusReachPlan` (shared/polymath_shared/reach.py:151-174) [DERIVED].
- `rerank_children` receives the original `query` (shared/polymath_shared/reach.py:365), while retrieval used `reach_query` (233-234) [DERIVED].
- Corpus scope takes only the first id: `(pass1_result.plan.corpus_ids or (None,))[0]` (shared/polymath_shared/reach.py:239, 318); multi-corpus plans are silently scoped to one corpus, empty list yields `None` [INFERRED from the expression].
- `entities_for_evidence(child_ids)` called twice (154, 186) and `predicates_for_evidence(child_ids)` twice (160, 187); if the callables are impure, scoring input and returned state can diverge [DERIVED double-call, INFERRED consequence].
- `seed_concepts` uses substring containment `c["term"].lower() in (h.text or "").lower()` (shared/polymath_shared/reach.py:294) — short terms match inside unrelated words [INFERRED: substring semantics].
- `_STOP` mixes generic stopwords with domain verbs `"actions additional alter attributing provides makes gives requires involves becomes remains appears seems"` (shared/polymath_shared/reach.py:78-79) [DERIVED].
- `lexical_lane` rewrites `hit.rank` in place after exclusion filtering (shared/polymath_shared/reach.py:264-266) [DERIVED].

## refactor notes
- Payload/filter key contract with `routing_search` rows: `score`, `payload.corpus_id/doc_id/parent_id/chunk_id/summary_id/source_name/text` (shared/polymath_shared/reach.py:243-256, 322-333) and filter keys `representation_kind/corpus_id/exclude_doc_ids/doc_id/parent_id` (237-241, 316-321). Renames break the vector-store contract and its payload indexes.
- Evidence keys `reach_pass/arrival/seed_concepts/g3_score` and arrival tags `"REACH_SECTION_LED"`/`"REACH_LEXICAL"` (shared/polymath_shared/reach.py:39-40, 334-338, 353-355, 371) are consumer-facing; module docstring forbids reach evidence as direct factual support (10-12).
- The 367 assert is the rerank contract (reorder-only); removing it hides reranker mutations (shared/polymath_shared/reach.py:364-369).
- `serialized_query` format feeds `embed_query` and is recorded in trace (shared/polymath_shared/reach.py:105-110, 233-234, 375); changing it invalidates reach embeddings and trace comparability.
- `GENERIC_HEAD` is a frozen imported vocabulary; admission depends on it (shared/polymath_shared/reach.py:31, 85, 113-117, 20-21).
- `REACH_DEFAULT_PLAN` (shared/polymath_shared/reach.py:66) is the shared default for `reach_retrieve` (224); changing any `CorpusReachPlan` default changes behavior for every caller that omits `plan`.

## VERIFY
```verify
grep -Fq 'REACH_PLAN_VERSION = "corpus-reach-v1"' shared/polymath_shared/reach.py
grep -Fq 'assert set(post_g3) == set(pre_g3), "G3 changed the reach candidate set"' shared/polymath_shared/reach.py
grep -Fq '1.0 / (plan.rrf_k + hit.rank + 1)' shared/polymath_shared/reach.py
grep -Fq '"reach_pass": 2,' shared/polymath_shared/reach.py
test "$(grep -c -F 'routing_document_summary' shared/polymath_shared/reach.py)" -ge 3
! grep -Fq 'import json' shared/polymath_shared/reach.py
```
