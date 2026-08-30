---
change_id: SUMMARY-COMPILER-V1
owner: worker
date: 2026-08-30
status: complete
architecture_impact: profile_document stage output contract (retrieval-summary-v3), dual-summary slot (migration 0041); no new process
last_reviewed: 2026-08-30
---

# WORK LOG — SUMMARY-COMPILER-V1 (2026-08-30, Slice 2)

## Requested outcome (owner)
Owner spec "Build: Deterministic Parent / Section Summary Compiler"
(session 3) + "include it in slice 2": one model-free, deterministic,
source-derived, hierarchy-aware, triple-aware, coverage-preserving,
bounded, provenance-preserving compiler replaces the three summary
generators; the extractor's per-neighborhood digest is the additional
adapter for abstract summaries — when present and clean it is the ACTIVE
routing vector, the deterministic card always exists as fallback.

Measured trigger (session 3 sample read, 20 parents): `retrieval_summaries.py`
v2 was called without `background`, so its "salience" degenerated to the
longest sentence per child; the document card for Learning SQL was 1,594
chars of OCR garbage; sentences were split inside "(i.e."; the 600-char cap
starved the fourth child; S2 `parent_summaries` were 201/206 first-180-char
heads with junk "concepts" and no query-time reader; `_REL_PHRASE` knew only
lowercase rule-pack predicates (uppercase ontology facts would render nothing).

## Smallest acceptance criteria
1. `compile_section` / `compile_document` are pure and byte-deterministic;
   every selected sentence is a verbatim source slice with chunk offsets.
2. Coverage first: each non-noise child contributes its best sentence
   before any child contributes a second; the receipt records it.
3. Triples: trusted facts linked by evidence offsets boost their sentence
   and are serialized as the relation capsule; untrusted only rank.
4. Output `{summary, relations, keywords}` + one serialized embed text
   (`SUMMARY / RELATIONSHIPS / KEY CONCEPTS`) is what Qdrant embeds.
5. Dual slot: deterministic row always written; `llm_digest` row active
   when the digest is clean; exactly one active row per slot (unique
   partial index); projector/census/verifier read active rows only.
6. Verifier gates: every non-noise parent has an active card; a card whose
   coverage receipt shows an uncovered child degrades the run.
7. S2 `parent_summaries` consumes the compiled card (summary, relations
   as fact sentences, keywords as concepts); the duplicate head/concept
   logic is gone; uppercase ontology predicates render.

## Owner and contract
`worker` (profile_document writes the cards; project_qdrant embeds them;
verify gates), `shared` for the pure compiler. Public contract:
`retrieval-summary-v3` rows with `variant/active/plain_summary/relations/
keywords/coverage` (migration 0041); Qdrant payload gains `variant`.
Plan D1 ("retrieval_summaries UNCHANGED") is DEVIATED by owner request —
register 1.18 / 4.4.8.

## Dependency edges
`workers.profile_worker` → `polymath_shared.{summary_compiler,retrieval_summaries,region_role}`;
`workers.summary_worker_impl` → `retrieval_summaries` rows (read);
`polymath_shared.parent_summary` → `summary_compiler.RELATION_PHRASES`.
Reverse dependents: `project_qdrant_worker._routing_rows`,
`verify_worker._desired_routing_ids`, `census._missing_projection_receipts`
(active filter), `tests/determinism/test_retrieval_summaries.py` (API kept).

## Verifier and rollback boundary
`tests/determinism/test_summary_compiler.py` + the kept
`test_retrieval_summaries.py`. Rollback: revert the commit; migration 0041
is additive (defaults keep v2 rows valid and active).

## Contract
`retrieval-summary-v3` (`shared/polymath_shared/retrieval_summaries.py`,
API kept; `summary_id` now hashes the EMBEDDED text). Row shape
(migration 0041, additive): `variant` (`deterministic|llm_digest`),
`active`, `plain_summary`, `relations[{predicate,subject,object,text,
fact_id,chunk_id}]`, `keywords[]`, `coverage{level,units_total,
units_covered,regions,uncovered,no_prose_units,sentences,chars,truncated,
relations,keywords,contract}`; `summary_text` = the serialized embed text
`SUMMARY / RELATIONSHIPS / KEY CONCEPTS` (empty blocks omitted); one active
row per `(doc, kind, parent)` slot (unique partial index). Qdrant routing
payload gains `variant`. Compiler contract `summary-compiler-v1`
(`summary_compiler.contract_fingerprint`). profile_document stage
contract `1.2.0`. S2 `parent_summaries` payload gains `fact_sentences`,
`compiled_from`, `variant`; its `input_hash` includes the card id.
Verify artifact gains `summaries{}`; `parents_without_card` and
`cards_uncovered` (starved children only) are problems → `degraded`.

## Changes
- `shared/polymath_shared/summary_compiler.py` (new): `split_sentences`
  (offsets; never inside i.e./e.g./vs./etc.), `structural_quality`
  (headings, dumps, OCR garbage, markup, question stems), TF-IDF salience
  vs the document background (mandatory), centrality, trusted-triple
  support, coverage-first over units or ordered REGIONS (documents with
  more parents than the sentence budget), Jaccard dedupe, source-order
  restoration, HARD length bound with reserved-drop as last resort,
  relation capsule (trusted triples, `RELATION_PHRASES` for the 17+1
  ontology ids and the rule-pack ids), keywords (triple endpoints, then
  prose-only TF-IDF terms/bigrams, digit/debris/fragment/plural filters),
  `serialize`, `digest_variant` (the LLM adapter), `contract_fingerprint`.
- `shared/polymath_shared/retrieval_summaries.py`: v3 wrapper; old
  entry points return the plain summary + provenance (their tests pass
  unchanged); `compile_*` / `digest_variant` re-exported.
- `workers/workers/profile_worker.py`: `_facts_for_doc` (evidence
  offsets → triples), `_digests_for_doc` (extract artifact), `_upsert_slot`
  (deactivate slot → upsert variants; replay-identical), noise/dump/code
  children excluded via `region_role.is_summarizable`; artifact
  `routing_cards[]`; stage contract 1.2.0.
- `workers/workers/project_qdrant_worker.py`: active rows only; payload
  `variant`. `workers/workers/verify_worker.py`: `_desired_routing_ids`
  active only; `reconcile_summaries` gate. `control/control/census.py`:
  want-set active only. `workers/workers/extract_worker.py`: all digests
  persist (was `[:400]`).
- `shared/polymath_shared/parent_summary.py`: `build_parent_summary(...,
  compiled=)` consumes the card; phrase map from the compiler (uppercase
  ontology ids render); unreachable duplicate concept loop removed.
  `summary_runtime.run_parent_summary_ticket(compiled=)`;
  `summary_worker_impl._compiled_card` + input hash.
- `shared/polymath_shared/region_role.py`: `NON_SUMMARY_ROLES`
  (noise + output + code), `is_summarizable`, parent rule.
- `stores/postgres/migrations/0041_retrieval_summary_variants.sql`
  (applied live 2026-08-30 via `docker exec … psql`).
- `tests/determinism/test_summary_compiler.py` (new, 17 tests).
- Docs: register 1.18 / 4.4.8, packet §2.12 + §5, TREE declarations.

## Proof
- Pure suites: `test_summary_compiler.py` 17/17; kept
  `test_retrieval_summaries.py` 7/7, `test_parent_summary*.py` 13/13,
  `test_extraction_coverage_gate.py` 20/20 (61 in the group).
- Live dry run (transaction ROLLED BACK): both documents compiled in
  0.66 s + 0.09 s; CySA+ 181 sections (49 `llm_digest` active), Learning
  SQL 25 (12 active); starved children 0 (6 + 7 `no_prose` children =
  OCR/dump-only, reported not gated); document cards 1,452 / 1,594 chars,
  7 / 9 sentences, 12 regions; every selected sentence verbatim at its
  offsets; compile twice → byte-identical; persist twice → identical
  rows and flags (477 rows incl. the deactivated v2 rows); 0 slots with
  more than one active row; `reconcile_summaries`: 206/206 parents with
  an active card, 0 uncovered; `reconcile_ontology`: 270 ledger rows,
  0 off-enum, RELATED_TO share 1.5%.
- Regression: `tests/contracts tests/determinism` = **1,513 passed, 5
  failed, 14 skipped** — the same 5 environmental failures that reproduce
  on pristine `main@c83f3c2` (recorded in the packet traps).
- Guards green.

## Rejected claims
- "The digest replaces the deterministic summary" — no: both rows
  persist; the digest is only the ACTIVE vector when clean, and it always
  carries the deterministic relations/keywords (it never invents a fact).
- "Coverage must include every child" — no: children with no usable
  prose (OCR/dumps) are `no_prose_units`; only STARVED children degrade.
- "Old summary tests were superseded" — not needed: the v2 API returns
  the plain summary and the pins still hold.
- "`chunks.summary` (LEGACY lane) is rewritten" — no: the chunker's parent
  summary stays (a second writer on `chunks` was not admitted); LEGACY
  mode is unchanged.

## Open contract gaps
- No re-profile ticket: cards regenerate on ingest only (contract-drift
  reconciliation ignores terminal runs). The owner's rerun regenerates
  everything; a `reprofile.v1` ticket is the next seam if card iteration
  without re-extraction is wanted.
- The 206 `parent_summary` Qdrant points (parent-tier chunk projection)
  are still embedded and searched by nothing; removal touches the
  chunk-receipt want-set (verifier + census) — separate change.
- Question-bank sections summarize as question stems when no
  explanation exists in the parent; the digest adapter covers that case
  once every neighborhood has a digest (post-rerun).
- Region roles stay NULL on pre-hardening chunks until re-ingest.
