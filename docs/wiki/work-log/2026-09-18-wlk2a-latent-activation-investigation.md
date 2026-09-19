---
change_id: WLK2A-LATENT-ACTIVATION-FINDINGS-V1
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "INVESTIGATION ONLY — no production/fleet/shared change (eval/ + docs/ only, no bounce). Traced the deep/expert family for wc01/wc03/wc05/wc06/wc07/wc10 and tested the owner's Retrieval-Lineage architecture. Findings: (1) the reranker judges every candidate against the PRIMARY q0 only (retrieval_text_for = primary), discarding the retrieving bridge; (2) the existing PROFILE-expansion bridges are misdirected and rescue 0 sub-floor chunks; (3) the DECISIVE bridge-as-primary end-to-end test VALIDATES the architecture — running full retrieval+rerank with a good bridge surfaces the right expert chunks and seats them in FINAL (wc01 union 2→91, best rerank −6.58→+5.52, in-final 0→10; wc05 +5.87/5; wc07 +6.07/8); (4) this CORRECTS the earlier ceiling read — wc01/wc05 are NOT chunk-quality-limited (the corpus has strong chunks; q0-driven retrieval just wasn't surfacing them); all are BRIDGE-limited; wc03/wc10 are nomination misses. Mechanism proven; crux = bridge generation (existing deterministic bridges insufficient). Ready to admit as an implementation plan, owner-gated. Not implemented."
last_reviewed: 2026-09-18
---

## Contract
WLK2A (owner-admitted 2026-09-18, investigation-first) asked whether the existing architecture can
give legitimately useful latent corpus knowledge a grounded semantic bridge to the user's objective
BEFORE final reranking, derived generically from existing runtime signals (Scout/Wildcard/pMAP),
without lowering the rerank floor, without hard-coding concepts/titles, without ingestion changes, and
without a new LLM call unless existing signals are demonstrably insufficient. Deliverable = a
stage-by-stage table for wc01/wc03/wc05/wc06/wc07/wc10 + the smallest generic intervention (a valid
outcome being: preserve an existing bridge, improve deepening, both, or no change). Do not implement
until the failure mechanism is proven sufficiently to identify the correct owner. Preserve q0 primary,
DIRECT grounding, CA0–CA5 epistemics, unsupported-hallucination = 0.

## Changes
No production, fleet, or `shared/` code changed. No fleet bounce. Added (eval/ + docs/ only):
- `eval/wildcard_latent_knowledge/wlk2a_forensics.py` — READ-ONLY stage tracer (6 cases × 4 modes):
  nomination / plan bridges / document candidate + selected-for-deepening / chunk union / rerank
  query, plus a RE-SCORE experiment (`_rerank_children`) of each expert union chunk against its
  retrieving subqueries + PROFILE bridges.
- `eval/wildcard_latent_knowledge/wlk2a_ceiling.py` — READ-ONLY ceiling test: re-scores the best deep
  chunk against q0, the existing profile bridge, and an *ideal* diagnostic concept bridge (a
  query-need paraphrase; NOT a production concept/title) to separate bridge-quality from chunk-quality.
- `eval/wildcard_latent_knowledge/wlk2a_bridge_retrieval.py` — the DECISIVE end-to-end test: runs the
  full pipeline with the bridge as the primary query (bridge-driven retrieval + deepening + rerank) vs
  q0-primary, measuring expert chunks reaching union/final and their rerank scores.
- `eval/wildcard_latent_knowledge/WLK2A-FORENSICS-2026-09-18.json`, `WLK2A-CEILING-2026-09-18.json`,
  `WLK2A-BRIDGE-2026-09-18.json` — frozen evidence.
- `docs/wiki/plans/WLK2A-LATENT-ACTIVATION-FINDINGS-V1.md` — the findings/decision record (table + 6
  answers + recommendation).
- Register row 11.314; this work-log; scaffold TREE declarations; CONTINUITY refreshed.

## Proof
`LIVE_PATH_PROVEN` (read-only). Probes run the real deployed v2 path (`chat_retrieve_mode` →
`chat_retrieve_v2` → `select_evidence`, editable `.pth` resolves to MAIN = HEAD = deployed bundle)
against the live embed/rerank sidecars. Evidence:
- **Rerank query is q0 only** — code-confirmed (`retrieval_text_for` returns the PRIMARY compiled
  query; `select_evidence` reranks `(result.context.query, chunk)`).
- **Existing bridges rescue nothing** — across 6 cases, re-scoring sub-floor expert chunks against
  their retrieving subqueries + PROFILE bridges = 0 genuine rescues (1 borderline, wc03 Ed Hooks
  q0 −0.05 → 3.24). The PROFILE bridges are misdirected (e.g. wc01 "Augmenting prompts for text-to-
  video generation"; wc07 "Using spoken dialogue instead of physical combat").
- **Ceiling test (re-score the q0-surfaced chunk)** — wc07 Laban chunk q0 −6.5 → ideal bridge **+4.25**;
  wc01 FACS q0 −2.63 → ideal −4.9; wc05 Laban q0 −5.4 → ideal −4.7. Read at the time as
  "wc01/wc05 chunk-quality-limited" — CORRECTED below (it only re-scored the *q0-surfaced* chunk).
- **Bridge-as-primary end-to-end (DECISIVE)** — running the full pipeline with a good bridge as the
  query surfaces the RIGHT expert passages, scores them well above floor, and seats them in FINAL:
  wc01 expert-in-union 2 → **91**, best rerank −6.58 → **+5.52**, in-final **0 → 10**; wc05 +3.83 →
  **+5.87**, in-final 1 → **5**; wc07 −2.43 → **+6.07**, in-final 2 → **8**. So wc01/wc05/wc07 are
  BRIDGE-limited, NOT chunk-quality-limited — the corpus holds strong chunks that q0-driven retrieval
  wasn't surfacing. The owner's Retrieval-Lineage architecture is validated end-to-end.
- **Deepening gap** — nominated expert docs frequently not in the top-6 `selected_documents`
  (wc01 1/3, wc10 0/3); q0-driven retrieval surfaces the wrong chunks, bridge-driven retrieval the
  right ones.
Conclusion: the mechanism is PROVEN (good bridge → surface + rank + final). Crux = bridge generation.
Ready to admit as an implementation plan; owner-gated (bridge-generation source). Not implemented.

## Rejected claims
- REJECTED "Scout/Wildcard already produce a preservable semantic bridge" (owner option 1 / Q4) — the
  existing PROFILE-expansion bridges are misdirected and rescue nothing (re-score: 0 genuine rescues).
- REJECTED "reranking candidates against their retrieving subquery would rescue deep material" (Q5) —
  true only with a GOOD bridge (wc07 ideal), not the existing ones; viable only paired with better
  bridge generation.
- REJECTED (self-correction) "wc01/wc05 are chunk-quality-limited (corpus lacks a usable chunk)" — the
  ceiling test only re-scored the *q0-surfaced* chunk. The bridge-as-primary test shows the corpus holds
  strong floor-clearing expert chunks (wc01 union 2→91, in-final 0→10); they are BRIDGE-limited. The
  earlier claim is withdrawn.
- CONFIRMED: the demonstrably-working lever is query-anchored evidence lineage — carry the origin bridge,
  deepen + rerank against q0 AND the bridge, bounded COMPLEMENTARY/DIVERGENT roles (q0 primary, floor
  unchanged). Proven end-to-end. The remaining gap is bridge CONTENT quality (the deterministic
  expansion is misdirected) → owner decision on the bridge-generation source (bounded LLM concept-bridge,
  now justified; or a better deterministic profile→concept derivation; or the graph path as bridge).

## Open contract gaps
None. No contract, interface, schema, or flag changed (`contract_impact` scope = eval/docs only → no
impacted production contract). BASELINE/SURVIVAL/WLK2B-FORENSICS-2026-09-18 remain immutable + untouched.
Deferred to owner decision: authorize a bounded concept-bridge generator + secondary rerank authority
(lever A, fixes bridge-quality class incl. wc07); document→chunk localization/deepening (lever B, for
the chunk-quality class); Scout coverage for wc03/wc10 nomination misses.
