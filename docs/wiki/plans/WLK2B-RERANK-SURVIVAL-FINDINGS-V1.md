---
title: "WLK2B-RERANK-SURVIVAL-FINDINGS-V1 — investigation outcome: shared post-candidate deep-material survival"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "INVESTIGATED — NULL RESULT (no production change). Evidenced per owner 'null result is explicitly valid' clause."
owner: "@king"
scope: "Forensic determination of whether high-value already-discovered deep material is suppressed by the generic reranker/portfolio (a survivable crowding artifact) for wc01/wc05/wc07 across FAST/HYBRID/GRAPH/WILDCARD. Investigation-first per the WLK2B admission; no shared/ or orchestrator change made."
---

# WLK2B — shared rerank survival (INVESTIGATION OUTCOME: NULL RESULT)

**Verdict: no production change.** The WLK2B premise — *useful material is discovered, enters the
candidate pool, and the generic reranker/portfolio unnecessarily discards it because redundant
higher-scoring winners crowd it out* — is **refuted by runtime evidence** on all three admitted cases
across all four modes. The material that reaches the candidate pool is judged **far below the
relevance floor** by the cross-encoder, the winners are **not redundant** (nothing to displace), and
the deep material frequently never enters the chunk union at all. A floor-respecting, redundancy-aware
survival mechanism would fire on **nothing**; forcing survival would require overriding the
cross-encoder for Scout-nominated material — explicitly forbidden by the admission.

This is a successful WLK2B investigation under the admission's *"A properly evidenced null result is a
successful WLK2B investigation… do not lower standards merely to move deep survival from 0.70 toward
0.90."*

## Method (READ-ONLY, no repository/production change)
`eval/wildcard_latent_knowledge/wlk2b_forensics.py` wraps `candidate_engine.select_evidence`
(observe + delegate — behaviour unchanged) to capture the full `CandidateResult.union` (the fused
chunk pool the reranker scores, not exposed by `chat_retrieve_mode`) for wc01/wc05/wc07 ×
{FAST,HYBRID,GRAPH,WILDCARD}. Deep-family detection is by `doc_id → cinema_docmap` name (the
SURVIVAL-2026-09-18 detector; union rows carry an empty `source_name`). Evidence frozen at
`eval/wildcard_latent_knowledge/WLK2B-FORENSICS-2026-09-18.json`. Flags on: profile-scout, expansion,
resolution, constraint-align, evidence-roles (production defaults).

## The required investigation capture (owner-mandated)
Relevance floor in force: the composer's `aspect_weak_floor = 0.5` on the **sigmoid** of the
cross-encoder logit — i.e. a candidate is judge-accepted only at **logit ≥ 0**. This is the existing
production admissibility threshold (the admission said to reuse one if it exists; it does).

| case / mode | union (chunks/docs) | deep chunks in union | deep in judged prefix | **best deep logit (sigmoid)** | winners above floor | winner redundancy (dup pairs / max J vs deep) |
|---|---|---|---|---|---|---|
| wc01 FAST | 111 / 23 | **0** | 0 | — (never enters union) | 9/15 | 0 / — |
| wc01 HYBRID·GRAPH·WILDCARD | 120 / 28 | 2 | 2 | **−4.16 (0.015)** | 8/15 | 0 / 0.002 |
| wc05 FAST | 110 / 22 | 14 | 3 | **−2.91 (0.051)** | 15/15 | 0 / 0.0 |
| wc05 HYBRID·GRAPH·WILDCARD | 120 / 27 | 4 | 4 | **−1.20 (0.231)** | 15/15 | 0 / 0.0 |
| wc07 FAST | 120 / 23 | 13 | 5 | **−5.23 (0.005)** | 12/15 | 1 / 0.0 |
| wc07 HYBRID·GRAPH·WILDCARD | 120 / 26 | 6 | 5 | **−5.23 (0.005)** | 10/15 | 0 / 0.0 |

Deep families **are** Scout-nominated (Ekman/Facial Action/Classifying Facial for wc01; Timing for
Animation for wc05; Laban for wc07) — nomination is not the miss here. The miss is downstream, and its
cause is relevance, not crowding:

1. **No deep chunk clears the floor — anywhere.** The single best deep chunk across all 12 case×mode
   runs is wc05/HYBRID at logit **−1.20 (sigmoid 0.231)**; every other is worse (down to −11.3).
   Winners score **+3.7 … +7.5**. The cross-encoder cleanly separates them: these specific deep chunks
   are judged **not relevant to q0**. q0 is a creative *imperative* ("write a video-generation prompt
   for a man faking a smile"); a FACS/Timing/Laban textbook passage is *conceptually* adjacent but
   *literally* off-topic to the surface request, and the cross-encoder scores it as such.
2. **Winners are not redundant.** `winner_dup_pairs` = 0 in every case but one (wc07 FAST: 1);
   winner-vs-deep lexical redundancy ≤ 0.002. There is **no redundant winner to swap out** — the
   selection principle's "replace redundant evidence with useful distinct evidence" has no trigger.
   (This matches EVIDENCE-UTILITY-V1's own measurement: mean pairwise J = 0.072, "text redundancy NOT
   a disease.")
3. **The deep chunks are frequently not even in the candidate pool.** wc01/FAST has **zero** deep
   chunks in the union: the FACS/Ekman doc is routed at the *document* layer but is not in the top-6
   `selected_documents` (so never deepened into chunks) and its children don't win the global
   dense/sparse lanes. The SURVIVAL-2026-09-18 "deep candidate reach = 0.90" was measured at the
   **document-routing** layer (`document_candidates`), not the chunk union — the chunk-level reach is
   much lower.

## Why no generic mechanism ships
The mechanism WLK2B would have built (the correct generic shape) is a redundancy-aware survival pass
reusing the existing, proven `polymath_shared/evidence_utility.py::utility_cut`
(redundancy-veto + parent-saturation + requirement-coverage + relevance-floor, deterministic, already
the v1 HYBRID cut, **not** wired into the v2 chat path) inside `compose_evidence` — no second ranking
system, no model call. It is well-formed. It simply has **no work to do here**: with zero redundant
winners and every deep candidate below the floor, `utility_cut` (which vetoes redundancy and *honours
the floor*) would reproduce the current selection byte-for-byte. The only way to change the outcome is
to drop the relevance floor or reserve unconditional slots for Scout-nominated material — both
explicitly forbidden by the admission ("must still clear a defensible relevance floor"; "Scout
nomination… must never individually guarantee survival"; "do not tune a threshold specifically to make
wc01/wc05/wc07 pass").

## Refined diagnosis — where the real levers are (NOT WLK2B)
The `RERANK` stage-of-loss label in SURVIVAL-2026-09-18 is *where* the deep family disappears, but the
cause is a correct sub-floor relevance judgement, not a survivable portfolio artifact. The loss is a
two-stage upstream problem, both out of WLK2B scope:

- **(A) Candidate under-population / nomination depth (WLK2A).** Deep docs route at the document layer
  but under-populate the chunk union (not top-6 → not deepened; children lose the global lanes). This
  is nomination/candidate-formation, which the admission explicitly excluded from WLK2B.
- **(B) Literal-vs-conceptual relevance (new concern, neither WLK2A nor portfolio survival).** Even the
  deep chunks that reach the judge are scored irrelevant because the reranker sees the *creative
  imperative q0*, not the *concept*. Bridging this is a query-representation / latent-expansion
  question (rerank the concept aspects, or let synthesis spend conceptually-adjacent RELATED evidence),
  not a final-portfolio survival change. This is the core "latent knowledge" thesis of the benchmark.

## Acceptance (adapted for a null result)
No change → nothing to re-measure: no benchmark rerun, no fleet bounce, no CA5 regression. The frozen
`BASELINE-2026-09-18.json` / `SURVIVAL-2026-09-18.json` remain the untouched authorities. All
production invariants are trivially preserved (no code changed): unsupported hallucination, named-source
behaviour, success@10, q0/provenance are exactly as at HEAD `7e63621`.

## Recommendation (owner-gated — not executed)
Redirect to **WLK2A** (nomination/candidate depth — get better deep chunks into the union) and treat
**(B)** as a separate latent-relevance concern. Do **not** implement a portfolio-survival mechanism for
these cases. Reproduce anytime with `wlk2b_forensics.py`.
