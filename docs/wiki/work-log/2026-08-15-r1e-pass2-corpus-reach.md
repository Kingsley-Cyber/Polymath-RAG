---
change_id: r1e-pass2-corpus-reach
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (qualification REJECT; no production exposure)
---

# R1E: Pass-2 corpus reach — REJECT (insufficient complementarity)

## Contract

Qualify ONE additional bounded retrieval pass (corpus-reach-v1) that
discovers complementary documents outside the direct Pass-1 winner
set: exclude Pass-1 docs at retrieval time, build a deterministic
Pass1ConceptState (no LLM, provenance-bound, generic-seed guard),
summary-led reach retrieval, section resolution + filtered deepening,
G3, bounded reach budget, DIRECT vs CORPUS_REACH provenance, no
recursion. FAIL if reach is mostly redundant, ConceptState does not
beat query-only reach, useful complementary docs are not retained,
Pass 1 changes, isolation breaks, or determinism fails. No production
exposure regardless of outcome.

## Changes

- `shared/polymath_shared/reach.py`: CorpusReachPlan (corpus-reach-v1,
  frozen defaults: 6 seed concepts / 3 reach docs / 2 sections / 2
  children per section / 6 reach children / exclude_pass1=true),
  Pass1ConceptState + deterministic concept admission (profile core
  concepts > entities > relationships > multi-child terms > summary
  terms; generic heads + stopword-class terms rejected),
  reach_retrieve (exclusion filter at retrieval time via payload
  must_not, summary-led lanes + optional lexical lane, RRF k=60,
  seed provenance per candidate, reach_pass=2 evidence, G3
  candidate-set invariant, no recursion).
- `orchestrator/orchestrator/api/fast.py`: searcher supports
  exclude_doc_ids (must_not) — additive; FAST/HYBRID unchanged.
- Qualification: frozen 12-query reach set (sha256
  `d6548c68…e8c0`; gold: direct docs, classified complementary docs
  (MECHANISM/LIMITATION/CONTRAST/SUPPORTING_EVIDENCE/
  ALTERNATE_FRAMEWORK/CROSS_DOMAIN_BRIDGE), redundant docs,
  irrelevant docs, complementary child substrings) + frozen corpus.
  Determinism tests (5).

## Proof (frozen measurements)

B (original-query-only reach): precision@3 0.056; useful
complementary doc in 2/12 queries; complementary child recall 0.222;
2 redundant + 3 irrelevant hits.
C (query + ConceptState): IDENTICAL to B — the deterministic concept
sources available in the frozen architecture (profile core concepts,
selected summary terms, multi-child terms, entities, predicates) do
not produce expansion terms that change retrieval outcomes; profile
core concepts are extractive noise at this corpus scale.
D (+lexical reach): precision@3 0.111; useful 3/12; child recall
0.333 — improvement but far below a usable complementary signal.

Pass-1 parity: True. Determinism: True. Generic-seed violations: 0.
Isolation preserved by the corpus filter.

Failure conditions triggered (frozen rules): Pass-2 results are mostly
redundant/topic-adjacent; ConceptState does not outperform
query-only reach; useful complementary documents are not retained
under the final budget for 9-10 of 12 queries. No LLM expansion model
was used to compensate (explicitly forbidden).

Verdict: REJECT. Corpus reach as specified does not qualify on this
frozen corpus: the complementary signal at summary/lexical level is
too weak to distinguish "complementary" from "topically adjacent".

## Rejected claims

- No production exposure: HYBRID remains direct-only; no DEEP/
  RESEARCH variant created; no synthesis integration.
- No MMR reintroduction; no concept blacklist; no model changes.

## Open contract gaps

- Future options for corpus reach (user decision): a qualified
  complementarity signal (e.g., a contrastive expansion model),
  richer deterministic concept provenance, or accepting
  direct-only retrieval. Not started.
