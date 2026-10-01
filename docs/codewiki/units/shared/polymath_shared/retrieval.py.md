# unit: shared/polymath_shared/retrieval.py
anchor: shared/polymath_shared/retrieval.py:1-309

## purpose
Deterministic, model-free retrieval primitives (Phase G1/G2). Four independently inspectable lanes — document profile, parent summary, child dense (via injected search), child lexical — fused by reciprocal rank fusion over ranks only; a child hit survives even when its document and parent score zero. Every dense hit carries representation provenance (G2 gate 3). shared/polymath_shared/retrieval.py:1-18 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| tokens | def | text: str -> set[str] | shared/polymath_shared/retrieval.py:54 | — |
| lexical_score | def | query: str, text: str -> float | shared/polymath_shared/retrieval.py:58 | — |
| score_profile | def | query: str, profile: dict -> tuple[float, list[str]] | shared/polymath_shared/retrieval.py:74 | — |
| rrf | def | rankings: list[list[str]], k: int = 60 -> list[str] | shared/polymath_shared/retrieval.py:90 | — |
| RetrievalHit | class | dataclass: source_id, representation_kind, contract_id, raw_score=0.0, rank=-1, corpus_id="", document_id="", parent_id="", chunk_id="", why="" | shared/polymath_shared/retrieval.py:100-111 | — |
| RetrievalResult | class | dataclass: query, 4 rankings, selected_documents, selected_children, graph_facts | shared/polymath_shared/retrieval.py:115-123 | — |
| run_lanes | def | query, *, fetch_profiles, fetch_parents, fetch_children, child_search -> RetrievalResult | shared/polymath_shared/retrieval.py:126-133 | — |
| graph_expansion | def | entity_surfaces: list[str], *, expand -> list[dict] | shared/polymath_shared/retrieval.py:297-301 | — |

Module imported by: orchestrator/orchestrator/api/evidence.py, orchestrator/orchestrator/api/graph.py, orchestrator/orchestrator/api/hybrid.py, orchestrator/orchestrator/api/retrieve.py, shared/polymath_shared/answer_synthesis.py, shared/polymath_shared/_small-modules-1 [DERIVED — FACTS.importers]. Per-symbol call sites not known.

## contracts

**lexical_score(query, text) -> float** — shared/polymath_shared/retrieval.py:58-71
- in: any strings; query tokenized by `_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")` after lowercasing shared/polymath_shared/retrieval.py:26,60 [DERIVED]
- out: `hits / len(q)`; `0.0` when the query yields no tokens shared/polymath_shared/retrieval.py:61-62,71 [DERIVED]
- post: per matched term `hits += 1 + math.log(1 + count) * 1.2` where count = substring occurrences via `re.findall(re.escape(term), body)` shared/polymath_shared/retrieval.py:68-70 [DERIVED]
- post: stopword query terms are skipped in the numerator but still counted in `len(q)` shared/polymath_shared/retrieval.py:65-67,71 [DERIVED]

**score_profile(query, profile) -> (total, why)** — shared/polymath_shared/retrieval.py:74-87
- in: list field values joined with `" "`, others `str()`-ed shared/polymath_shared/retrieval.py:82 [DERIVED]
- out: `total += weight * s` per non-empty field with `s > 0`; `why` = matched field names shared/polymath_shared/retrieval.py:84-87 [DERIVED]
- pre: weights fixed in PROFILE_FIELD_WEIGHTS — semantic_summary 3.0, core_concepts 2.5, use_for_questions_about 2.0, methods 2.0, primary_domains 1.5, secondary_domains 1.2, problems_addressed 1.2, connects_to_domains 1.0 shared/polymath_shared/retrieval.py:39-48 [DERIVED]

**rrf(rankings, k=60) -> list[str]** — shared/polymath_shared/retrieval.py:90-96
- in: ranked id lists
- out: sorted by descending Σ `1.0 / (k + rank + 1)`, ties broken by id ascending shared/polymath_shared/retrieval.py:95-96 [DERIVED]

**run_lanes(query, *, fetch_profiles, fetch_parents, fetch_children, child_search) -> RetrievalResult** — shared/polymath_shared/retrieval.py:126-294
- in: row shapes — fetch_profiles `[{doc_id, retrieval_profile, corpus_id?}]`, fetch_parents `[{chunk_id, doc_id, summary}]`, fetch_children `[{chunk_id, doc_id, parent_id, text, corpus_id?}]`, child_search `[{chunk_id, doc_id, parent_id, text, vector_score, contract_id, corpus_id}]` (may be empty) shared/polymath_shared/retrieval.py:138-142 [DERIVED]
- pre: `child_search(50)` called once shared/polymath_shared/retrieval.py:191; `fetch_children(2000)` once shared/polymath_shared/retrieval.py:214 [DERIVED]
- post: document/parent/lexical hits kept only when score > 0 shared/polymath_shared/retrieval.py:153,173,221; dense rows skipped unless chunk_id truthy and vector_score is not None shared/polymath_shared/retrieval.py:194-195 [DERIVED]
- post: each child ranking capped `[:50]` shared/polymath_shared/retrieval.py:209,235; selected_documents capped `[:10]` shared/polymath_shared/retrieval.py:256; selected_children (dense ∪ lexical ∪ sibling expansion) capped `[:40]` shared/polymath_shared/retrieval.py:293 [DERIVED]
- post: fusion input is four id lists (doc ids, parent chunk→doc, dense chunk→doc, lexical chunk→doc) — ranks only, no scores shared/polymath_shared/retrieval.py:244-249 [DERIVED]

**graph_expansion(entity_surfaces, *, expand) -> list[dict]** — shared/polymath_shared/retrieval.py:297-309
- out: `[]` for empty surfaces shared/polymath_shared/retrieval.py:306-307; otherwise `expand(entity_surfaces[:10])` truncated to GRAPH_MAX_FACTS shared/polymath_shared/retrieval.py:308-309 [DERIVED]

## effect surface
- Postgres: no tables read or written in this file (FACTS.tables_read = [], tables_written = []).
- Qdrant: not called here; the dense lane's `child_search` callable is documented as "Qdrant vectors under the active embed contract" shared/polymath_shared/retrieval.py:7 — the caller owns the access. [DERIVED]
- Files / network / subprocess / env flags: none; all I/O injected via callables shared/polymath_shared/retrieval.py:129-132,300. [DERIVED]

## invariants

INVARIANT: dense fetch limit = 50 = child_dense_ranking cap = child_lexical_ranking cap — shared/polymath_shared/retrieval.py:191,209,235 [DERIVED]
  fails-if: silent truncation drift between what child_search returns and what enters fusion
INVARIANT: selected_documents ≤ 10, selected_children ≤ 40, graph facts ≤ GRAPH_MAX_FACTS (20), expansion seeds ≤ 10 — shared/polymath_shared/retrieval.py:256,293,51,308 [DERIVED]
  fails-if: downstream bundle sizes change for every importer
INVARIANT: rrf contribution = 1.0 / (k + rank + 1) with k = 60 — shared/polymath_shared/retrieval.py:95,90 [DERIVED]
  fails-if: fused order changes; rank-only fusion contract (G2 gate 6) breaks
INVARIANT: every sort tie-breaks on ascending id (`kv[0]`, `h.source_id`, `c["chunk_id"]`) — shared/polymath_shared/retrieval.py:96,156,183,208,234,292 [DERIVED]
  fails-if: equal-score ordering becomes nondeterministic
INVARIANT: sum(PROFILE_FIELD_WEIGHTS.values()) = 14.4 — shared/polymath_shared/retrieval.py:39-48 [DERIVED]
  fails-if: field priorities shift and score_profile totals stop being comparable
INVARIANT: lexical/document/parent hits carry contract_id "lexical-v1"; dense hits carry row contract_id or "unknown" — shared/polymath_shared/retrieval.py:37,161,177,225,199 [DERIVED]
  fails-if: G2-gate-3 provenance misreports which representation produced a hit
INVARIANT: child hits enter fusion regardless of document/parent scores (hierarchy enriches, never suppresses) — shared/polymath_shared/retrieval.py:12-14,244-249 [DERIVED]
  fails-if: recall regression — children of zero-score documents disappear
INVARIANT: sibling expansion uses `evidence.setdefault`, add-only — shared/polymath_shared/retrieval.py:283 [DERIVED]
  fails-if: recall-monotonicity promise (G4 policy) shared/polymath_shared/retrieval.py:304-305 breaks

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/db/env/network reads; inputs come only from injected callables and every sort has an id tie-break shared/polymath_shared/retrieval.py:96,156,183,208,234,292 [DERIVED]
idempotency: SAFE — pure computation, mutates only local/result structures, no writes shared/polymath_shared/retrieval.py:126-294 [DERIVED]

## failure behaviour
- No try/except in the file; exceptions from injected fetchers/search propagate to the caller. [DERIVED — no handler in shared/polymath_shared/retrieval.py:1-309; FACTS.fallbacks absent]
- Malformed dense rows silently dropped via `continue` (missing chunk_id or vector_score None), not errored shared/polymath_shared/retrieval.py:194-195 [DERIVED]
- Missing optional keys default to `""` through `row.get(...)`; empty fused ids filtered from selected_documents shared/polymath_shared/retrieval.py:199,201,203,227,229,256 [DERIVED]
- graph_expansion returns `[]` without calling expand on empty seeds shared/polymath_shared/retrieval.py:306-307 [DERIVED]
- No error codes raised by this module.

## dumb-code flags
- `GRAPH_HOPS = 2` defined, never referenced in this file shared/polymath_shared/retrieval.py:50 — hop bounding lives in the caller's `expand`. [INFERRED: constant unused here]
- `RetrievalResult.graph_facts` is never populated by run_lanes shared/polymath_shared/retrieval.py:123 [DERIVED — no assignment in shared/polymath_shared/retrieval.py:126-294]
- Stopword query terms deflate scores: counted in `len(q)` denominator, excluded from numerator shared/polymath_shared/retrieval.py:65-67,71 [DERIVED]
- `lexical_score` counts substrings (`re.findall(re.escape(term), body)`), so "cat" matches inside "concatenate" shared/polymath_shared/retrieval.py:68 — inconsistent with token-based `tokens()` shared/polymath_shared/retrieval.py:54-55 [DERIVED]
- Magic numbers: `50` shared/polymath_shared/retrieval.py:191,209,235, `2000` :214, `10` :256, `40` :293, `10` :308 — only GRAPH_MAX_FACTS is named [DERIVED]
- Literal `"unknown"` contract fallback shared/polymath_shared/retrieval.py:199 vs LEXICAL_CONTRACT_ID `"lexical-v1"` shared/polymath_shared/retrieval.py:37 [DERIVED]
- `""` defaults in fusion lookups are dead: maps are keyed by the same hits being looked up shared/polymath_shared/retrieval.py:240-248 [INFERRED — keys and lookups come from identical lists]

## refactor notes
- run_lanes' row shapes (doc_id, chunk_id, parent_id, text, vector_score, contract_id, corpus_id, retrieval_profile, summary) are the integration contract for all six importers shared/polymath_shared/retrieval.py:138-142 [DERIVED — FACTS.importers]; renaming any key breaks orchestrator api evidence/graph/hybrid/retrieve and answer_synthesis.
- RetrievalHit's fields are the G2-gate-3 provenance contract (source id, representation_kind, contract id, raw rank, raw score) shared/polymath_shared/retrieval.py:16-17,102-111 — field changes ripple to every ranking consumer. [DERIVED]
- Rank-only fusion, no score normalization, is an explicit G2-gate-6 decision shared/polymath_shared/retrieval.py:10-14,239 — score mixing must not be introduced silently. [DERIVED]
- Caps 50/50/10/40 and rrf k=60 are the observed output sizes all importers rely on shared/polymath_shared/retrieval.py:209,235,256,293,90. [DERIVED]
- Recall-monotonicity of graph/sibling expansion is a tested G4 policy shared/polymath_shared/retrieval.py:283,304-305 — expansion must stay additive. [DERIVED]

## VERIFY
```verify
grep -Fq 'LEXICAL_CONTRACT_ID = "lexical-v1"' shared/polymath_shared/retrieval.py
grep -Fq 'GRAPH_HOPS = 2' shared/polymath_shared/retrieval.py
grep -Fq 'GRAPH_MAX_FACTS = 20' shared/polymath_shared/retrieval.py
grep -Fq 'def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:' shared/polymath_shared/retrieval.py
grep -Fq 'dense_rows = child_search(50)' shared/polymath_shared/retrieval.py
grep -Fq 'child_rows = fetch_children(2000)' shared/polymath_shared/retrieval.py
! grep -Fq 'try:' shared/polymath_shared/retrieval.py
```
