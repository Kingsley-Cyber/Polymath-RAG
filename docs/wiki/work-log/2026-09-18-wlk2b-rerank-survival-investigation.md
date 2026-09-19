---
change_id: WLK2B-RERANK-SURVIVAL-FINDINGS-V1
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "INVESTIGATION ONLY — NULL RESULT, no production/fleet/shared code change (eval/ + docs/ only, no bounce). Forensically determined that WLK2B's premise (deep material discovered, entered candidate pool, suppressed by generic reranker/portfolio) is REFUTED: deep chunks reaching the judge score far below the relevance floor (best −1.20/sig 0.231; floor = logit 0), winners are not redundant (dup pairs ~0), and deep chunks frequently never enter the chunk union. No portfolio-survival mechanism ships; a floor-respecting one would fire on nothing. Loss is upstream candidate under-population (WLK2A) + literal-vs-conceptual rerank relevance, not survivable portfolio crowding."
last_reviewed: 2026-09-18
---

## Contract
WLK2B (admitted 2026-09-18 with owner amendments) asked whether high-value ALREADY-DISCOVERED deep
material is being unnecessarily discarded by the generic reranker/portfolio for wc01/wc05/wc07 across
FAST/HYBRID/GRAPH/WILDCARD, and if so to ship the smallest GENERIC, floor-respecting, redundancy-aware
survival mechanism (no numeric boost, no second ranking system, no model call, cross-encoder untouched,
CA0–CA5 frozen). The admission REQUIRED an investigation before any modification and declared a
properly-evidenced NULL RESULT a successful outcome. Measurement authorities: the immutable
`BASELINE-2026-09-18.json` / `SURVIVAL-2026-09-18.json`.

## Changes
No production, fleet, or `shared/` code changed. No fleet bounce. Added (eval/ + docs/ only):
- `eval/wildcard_latent_knowledge/wlk2b_forensics.py` — READ-ONLY forensic probe. Wraps
  `candidate_engine.select_evidence` (observe + delegate, behaviour unchanged) to capture the full
  `CandidateResult.union` for the three cases × four modes and report each deep chunk's fused rank /
  judged-prefix membership / cross-encoder logit / final survival, the winners' logits, winner
  redundancy (4-gram Jaccard), and the composition trace. Deep detection via `doc_id → cinema_docmap`.
- `eval/wildcard_latent_knowledge/WLK2B-FORENSICS-2026-09-18.json` — the frozen evidence (155 KB).
- `docs/wiki/plans/WLK2B-RERANK-SURVIVAL-FINDINGS-V1.md` — the findings/decision record.
- Register row 11.313; this work-log; scaffold TREE declarations for the two eval files, this
  work-log, and the findings plan doc; CONTINUITY refreshed.

## Proof
`LIVE_PATH_PROVEN` (read-only). The probe runs the real deployed v2 retrieval path
(`chat_retrieve_mode` → `chat_retrieve_v2` → `select_evidence`) against the live embed/rerank sidecars;
the executed path is the production code (editable `.pth` resolves `orchestrator`/`polymath_shared` to
MAIN = HEAD `7e63621` = the deployed bundle). Evidence, unanimous across 12 case×mode runs:
- **No deep chunk clears the relevance floor** (`aspect_weak_floor` 0.5 on the sigmoid ⟺ logit ≥ 0).
  Best deep logit = −1.20 (sigmoid 0.231, wc05/HYBRID); all others −2.9 … −11.3. Winners score
  +3.7 … +7.5. Verified programmatically against the frozen artifact: deep chunks with logit ≥ 0 = NONE.
- **Winners are not redundant** — `winner_dup_pairs` = 0 in every case but wc07/FAST (=1); winner-vs-deep
  max Jaccard ≤ 0.002. No redundant winner exists to displace.
- **Deep chunks frequently absent from the chunk union** — wc01/FAST deep-in-union = 0 (routed as a
  document, never deepened). The SURVIVAL "0.90 candidate reach" measured the document-routing layer.
Conclusion: a floor-respecting redundancy-aware survival pass (the correct generic shape — reuse
`evidence_utility.utility_cut`, already the v1 HYBRID cut, not wired into the v2 chat path) would
reproduce the current selection byte-for-byte. Shipping survival for these cases requires dropping the
floor or reserving Scout-nominated slots, both forbidden. → NULL RESULT, no change.

## Rejected claims
- REJECTED "deep material is discovered, enters the candidate pool, and is suppressed by redundant
  higher-scoring winners at rerank" (the WLK2B admission premise) — refuted: no redundant winners; deep
  candidates are sub-floor; deep chunks often never reach the union.
- REJECTED "the reranker is flattening a survivable portfolio across modes" for these cases — the
  cross-encoder is making a correct literal-relevance judgement (creative-imperative q0 vs conceptually
  adjacent textbook chunk), not a crowding artifact.
- REJECTED the reading of SURVIVAL-2026-09-18 "deep candidate reach 0.90" as chunk-level reach — it is
  document-routing-layer reach; chunk-union reach is materially lower.
- NOT rejected but out of scope: WLK2A (candidate under-population) and a new literal-vs-conceptual
  rerank-relevance concern are the real levers; neither is a portfolio-survival change.

## Open contract gaps
None. No contract, interface, schema, or flag changed (`scripts/contract_impact.py` scope = eval/docs
only → no impacted production contract). BASELINE/SURVIVAL-2026-09-18 remain immutable and untouched.
Deferred to owner decision: WLK2A (nomination/candidate depth); literal-vs-conceptual rerank relevance
(query-representation / latent expansion). WLK1 (routing) and WLK3 (synthesis-spend) unaffected.
