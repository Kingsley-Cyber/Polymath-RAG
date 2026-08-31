---
change_id: RETRIEVAL-BASELINE-ELITE-V1
owner: orchestrator
date: 2026-08-30
status: complete
architecture_impact: query side (orchestrator tree) + serve supervision; one shared-tree line (supervisor main honors POLYMATH_FLEET_DIR)
last_reviewed: 2026-08-30
---

# WORK LOG — RETRIEVAL-BASELINE-ELITE-V1 (master sequence steps 1+2)

## Contract
The audit PRD's P0/P1 head: graph queries powered by the graph layer
(F1), /ask matched by the same vector machinery as FAST (F3), breadth
routing with exact-name recall (F4), one summary authority (F5), serve
processes supervised (F9). Baseline checkpoint before the latent build.

## Changes
- CARD-SEEDS-V1 (F1): `entity_card_probe` extracted as a shared function
  (fast.py); GRAPH resolves seed entities through it and passes
  `seed_entity_ids` through `graph_expand_or_502` → `_neo4j_expand` →
  `_corpus_seed_ids`, where card ids seed FIRST but only after the same
  corpus-authorized eligibility check (cards propose, authorization
  decides); token surfaces remain the fallback vocabulary.
- VECTOR-OBJECT-MATCH-V1 (F3): /ask concepts + procedures ranked by
  dense+sparse hits over their routing points (`_vector_object_ranks`),
  term-substring as tiebreak/fallback; fail-open to the old path.
- SPARSE-BREADTH-V1 (F4): FastSearcher runs a bm25 companion probe on
  EVERY routing lane; dense ordering stays authoritative, sparse-only
  hits append (pure recall addition). One tokenization per query,
  shared tokenizer. HYBRID + GRAPH searchers get the query too.
- ONE-SUMMARY-AUTHORITY (F5): the legacy parent lane scores
  `retrieval_summaries` active section cards (COALESCE to chunks.summary
  for uncarded parents); the chunks.summary override is gone.
- SERVE-SUPERVISOR-V1 (F9): second supervisor instance with
  `POLYMATH_FLEET_ONLY=orchestrator,sidecar_reranker` and its own
  `POLYMATH_FLEET_DIR=/private/tmp/polymath_serve` (main() now honors
  the env); pipeline supervisor unchanged.
- Latent plan: owner trigger directive recorded (§0a — corpus/document
  BUTTONS mint parent_enrichment tickets; query-time latent stays the
  D10 flag).

## Proof (live acceptance, audit PRD criteria)
1. "what uses Amazon S3" → **7 graph facts** (USES/PRODUCES/
   CONSTRAINED_BY), 2.6 s — was 0 with token-soup seeds. PASS
2. Concept route returns vector-ranked concepts; the junk-name winner is
   gone. Foreign-key concept still absent from results because NO such
   concept exists in the store (verified: 0 name matches over 28
   concepts) — compiler yield (F12), not retrieval. PASS (retrieval side)
3. "CloudFormation" → its entity card arrives via the SPARSE lane
   (exact-name recall), FAST 1.6 s, sparse latency accounted. PASS
4. Legacy parent lane's top hit has an active card for the same parent —
   one authority. PASS
6. Orchestrator + reranker run under their own supervisor (state file
   isolated); wake budget 5 s stands. PASS

## Rejected claims
- "Cards can seed the graph directly" — REJECTED as unsafe: card ids
  pass through the SAME corpus-authorized eligible-entity filter; a card
  from a stale collection can never seed an unauthorized fact.
- "Merge sparse and dense by score" — REJECTED: cross-space scores are
  incomparable; sparse hits append after dense (recall, not reorder).

## Open contract gaps
1. F2 (cards as a true fused lane) + F6 — next fenced window, via
   ADDITIVE-SEED-SEAM-V1.
2. F7/F10 breadth-depth caps — blocked on owner numbers (one plan bump
   with latent D8 caps).
3. F12 concept naming/yield gates what /ask can ever return.
4. Enrichment trigger endpoint + UI buttons — build with latent Phase B.
