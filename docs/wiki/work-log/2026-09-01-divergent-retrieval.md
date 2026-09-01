---
change_id: DIVERGENT-RETRIEVAL-V1
owner: governance
date: 2026-09-01
status: complete
architecture_impact: fourth retrieval mode (WILDCARD); §0b display carve-out (owner-blessed); ASK hidden from the UI mode picker
last_reviewed: 2026-09-01
---

# WORK LOG — DIVERGENT-RETRIEVAL-V1 (the WILDCARD mode)

## Contract
Owner-blessed design 2026-09-01 ("i bless off on this design"):
a TRUE fourth mode with a different objective — maximize surprise
subject to usefulness and source grounding. Reward latent similarity,
punish ordinary similarity; two-hop validation instead of the
query↔child rerank that kills distant-vocabulary discoveries; hard
bounds (≤3 bridges); the wildcard lane NEVER displaces answer
evidence. Owner clarified "/ask replacement" = hide ASK from the UI
picker only — the endpoint stays.

§0b CARVE-OUT (owner-blessed with the design): a bridge DISPLAYS the
enrichment's abstraction/transfer text as a clearly-labelled DERIVED
INSIGHT with its real source child attached as grounding. Never cited
as source evidence, never graph truth — query-time reasoning only.

## Changes
- `shared/polymath_shared/divergent.py`: the engine — broad two-
  channel latent sweep, per-parent channel merge (hop1 = best score),
  PARENT-level hard exclusion of the baseline neighborhood, two-hop
  validation (hop2 = cross-encoder scoring the (latent surface,
  source child) pair — the sole relevance authority, fail-open),
  novelty damp (in-neighborhood child or high query overlap →
  borderline factor; same-document → half-damp), WildcardValue =
  hop1 × hop2 × novelty (multiplicative: surprising-but-ungrounded
  and useful-but-obvious both die), ≤3 bridges, everything fail-open
  to an empty lane.
- `orchestrator/api/wildcard.py`: mode service — answer evidence =
  plain FAST (untouched); wires live stores + reranker (logits
  squashed to 0-1 so the support floor and value share one scale).
- Mode registry (MODE_WILDCARD in EXPOSED_MODES), /retrieve branch,
  chat/stream branch (WILDCARD = FAST bundle + wildcard frames +
  a "frontier bridges" phase line), retrieval frame carries
  `wildcard`.
- UI: mode picker = VECTOR/HYBRID/GRAPH/WILDCARD (ASK removed per
  owner — endpoint untouched); MessageBubble renders 🃏 cards
  (principle, why-it-transfers, grounded source quote, provenance
  label "derived insight").

## Proof
- test_divergent.py — 8 green: neighborhood exclusion, support floor
  kills ungrounded bridges, novelty damps obvious children, hard
  bounds + channel merge, fail-open on broken stores, fail-open
  without reranker, determinism, configurable bounds.
- LIVE bugs found by the probe and fixed:
  (1) doc-level hard exclusion emptied the frontier on a small corpus
  (36/36 candidates excluded — FAST touches every doc of a 2-doc
  corpus); same-doc is now a novelty damp, parent-level exclusion
  stays hard. (2) transfer-only hits displayed an empty principle.
  (3) raw reranker logits leaked into the multiplicative value.
- LIVE receipts post-fix (test corpus): "libraries → off-site
  storage" → "Lifecycle management of IT assets defines migration,
  retention, or retirement based on utilization" (support 0.99);
  "shop resilient to supplier failure" → "Infrastructure providers
  reduce operational risk by decoupling capacity from fixed
  hardware" (support 0.92). Cross-domain, grounded, bounded at 3.

## Rejected claims
- "Replace /ask" — narrowed by the owner to hiding ASK in the UI.
- "Triple structural-analogy boost (X-MODULATES-Y)" — deferred to v2;
  needs fact coverage the test corpus barely has.
- "Novelty via a second embedding pass" — membership + lexical
  overlap, deterministic, per the design's own suggestion.

## Open contract gaps
- Real qualification belongs to the REAL corpus after re-ingest (the
  test corpus is 2 books; every bridge inevitably carries the
  same-doc damp). The diagnostics frame (candidates/excluded/
  support_filtered/returned) is the harness raw material.
- Bridge quality depends on enrichment quality; the 7 minimal-
  contract sections produce shorter principles (provenance-visible).
- The triple-analogy boost is the strongest v2 candidate once fact
  extraction runs at scale.
