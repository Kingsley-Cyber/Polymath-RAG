---
title: "WLK2A-LATENT-ACTIVATION-FINDINGS-V1 — investigation: latent concept activation / retrieval lineage"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "INVESTIGATED — no production change. Failure mechanism PROVEN; the owner's Retrieval-Lineage architecture is VALIDATED end-to-end (a good query-grounded bridge surfaces + ranks + seats the expert material q0 misses). Crux = bridge generation. Ready to admit as an implementation plan, owner-gated. Not implemented."
owner: "@king"
scope: "Stage-trace of the expert/deep family for wc01/wc03/wc05/wc06/wc07/wc10 (q0 → scout → bridge → doc-candidate → deepening → union → rerank-query → outcome); a re-score experiment (does the retrieving bridge rescue a sub-floor chunk?); a ceiling test (bridge-quality vs chunk-quality of the surfaced chunk); and a bridge-as-primary end-to-end test (does bridge-driven retrieval+rerank surface floor-clearing expert chunks into final?). Investigation-first; no shared/ or orchestrator change made."
---

# WLK2A — latent concept activation / retrieval lineage (INVESTIGATION OUTCOME)

**Question (owner):** can the existing architecture give useful latent knowledge a *grounded semantic
bridge* to the user's objective before final reranking — and are Scout/Wildcard/pMAP already producing
the reason a source was nominated, which we then lose before deepening and reranking?

**Answer:** **YES to the mechanism, with one caveat.** The reason IS produced (on `CompiledQuery`:
`origin`/`role`/`reason`/`inspired_by_profile`/`target`) and IS discarded before rerank (the reranker
sees only q0). And when a *good* query-grounded bridge is carried through — used as the retrieval AND
rerank query — the expert material q0 misses is surfaced, scored **well above the floor**, and seated
in **final**. The **caveat**: the bridges the system *currently* produces (profile-expansion) are
**misdirected**, so "just stop discarding them" is necessary but not sufficient — the binding
constraint is **bridge quality**. The owner's Retrieval-Lineage architecture is the right frame and is
validated end-to-end.

## Method (READ-ONLY, no repository/production change)
- `wlk2a_forensics.py` — stage tracer (6 cases × 4 modes) + a re-score of each expert union chunk
  against its retrieving subqueries + PROFILE bridges. Frozen `WLK2A-FORENSICS-2026-09-18.json`.
- `wlk2a_ceiling.py` — re-scores the best *q0-surfaced* deep chunk against q0 / existing bridge /
  an ideal concept bridge. Frozen `WLK2A-CEILING-2026-09-18.json`.
- `wlk2a_bridge_retrieval.py` — the decisive test: runs the FULL pipeline (`chat_retrieve_mode`) with
  the bridge as the primary query (bridge-driven retrieval + deepening + rerank) vs q0-primary, and
  measures expert chunks reaching union/final and their rerank scores. Frozen
  `WLK2A-BRIDGE-2026-09-18.json`. The ideal bridges are a DIAGNOSTIC instrument (query-need paraphrase),
  never production concepts/titles. Floor unchanged: `aspect_weak_floor` 0.5 sigmoid ⟺ logit ≥ 0.

## The decisive result — bridge-as-primary (the owner's architecture, measured)
| case | q0-primary: expert in union / best rerank / **in final** | bridge-primary: expert in union / best rerank / **in final** |
|---|---|---|
| wc01 FACS | 2 / −6.58 / **0** | **91 / +5.52 / 10** |
| wc05 Timing | 7 / +3.83 / **1** | **29 / +5.87 / 5** |
| wc07 Laban | 16 / −2.43 / **2** | **46 / +6.07 / 8** |

The bridge surfaces the RIGHT passages (wc01 "codification of facial action"; wc05 "the basis of
timing is 24 frames"; wc07 "Space Effort Indirect and Direct") — not the tangential ones q0 found.
This **corrects** the ceiling test's read: the ceiling only re-scored the *q0-surfaced* chunk (a weak
passage, −4.9 even to an ideal bridge), so it read "chunk-quality-limited". The corpus in fact holds
strong, floor-clearing expert chunks; q0-driven RETRIEVAL wasn't surfacing them. wc01/wc05/wc07 are
**all bridge-limited** — a good bridge fixes both retrieval and rerank.

## Stage-by-stage table (deepest expert family per case)
| case | deep family | scout-nominated? | doc candidate → **deepened (top-6)?** | in union (q0) | **rerank query** | q0 rerank | existing bridge rescues? | **bridge-primary → final?** | loss driver |
|---|---|---|---|---|---|---|---|---|---|
| wc01 fake_smile | FACS/Ekman | yes | yes → 1/3 | 2 | q0 only | −6.58 | no | **YES (+5.52, 10 in final)** | BRIDGE (retrieval+rerank) |
| wc03 villain_won | Murch/Blink | **no** | no | 0 | q0 only | — | — | (not tested) | NOMINATION (Murch never scouted) |
| wc05 ordinary_fast | Laban/Timing | Timing yes | yes → 3/6 | 7 | q0 only | −1.20…−5.4 | no | **YES (+5.87, 5 in final)** | BRIDGE |
| wc06 unpredictable | Laban | yes | yes → 2/2 | many | q0 only | sub-floor | no | (not tested) | BRIDGE (expected) |
| wc07 silent_authority | Laban/Bartenieff | yes | yes → 3/5 | 16 | q0 only | −2.43 | no | **YES (+6.07, 8 in final)** | BRIDGE |
| wc10 suppressed_grief | FACS/Murch | **no** (Laban only) | no → 0/3 | 2–8 | q0 only | sub-floor | no | (not tested) | NOMINATION + BRIDGE |

## The six questions answered
1. **Why is a nominated expert doc sometimes not deepened?** `selected_documents = documents[:6]`; on a
   literal q0 the general textbooks outrank specialists, which land rank 7+ and aren't deepened (wc01
   1/3, wc10 0/3). Their chunks still reach the union via global lanes — so deepening-cap is not the
   binding constraint. The binding constraint is that q0-driven retrieval surfaces the WRONG chunks;
   bridge-driven retrieval surfaces the right ones (wc01 union 2 → 91).
2. **What query nominated the expert source?** Document level: hierarchy lanes on the PRIMARY vector +
   Scout. Chunk level: global dense/sparse on the primary + PROFILE-expansion subqueries. The only
   "bridges" are the PROFILE subqueries — and they are misdirected (wc01 "Augmenting prompts for
   text-to-video generation"; wc07 "Using spoken dialogue instead of physical combat").
3. **Is the richer representation discarded before rerank?** YES (code-confirmed): `retrieval_text_for`
   = PRIMARY q0 only; `select_evidence` reranks `(ctx.query, chunk)`. The retrieving bridge is not used.
4. **Does Scout/Wildcard already produce a preservable bridge?** The plumbing YES (`CompiledQuery`
   carries origin/role/reason/inspired_by_profile/target), but the CONTENT is misdirected — the current
   profile-expansion bridges rescue nothing (0 genuine re-score rescues). A *good* bridge works
   (bridge-primary test). So existing signals are demonstrably insufficient for bridge CONTENT.
5. **Can chunks be judged against the bridge that retrieved them, q0 staying primary?** YES and it is
   the fix — but only with a good bridge. Bridge-primary retrieval+rerank surfaces + seats the expert
   material in final (wc01 0 → 10). q0 stays the answer authority; the bridge earns COMPLEMENTARY /
   DIVERGENT evidence, bounded.
6. **Nomination vs deepening vs query-representation?** MIXED: NOMINATION = wc03/wc10 (Murch/FACS never
   scouted); everything else = the LINEAGE gap (bridge discarded before deepening + rerank), fixed by
   carrying a good bridge. Not a corpus/chunk-quality limit.

## Recommendation — the owner's Retrieval-Lineage architecture, validated (owner-gated, NOT implemented)
The mechanism is proven. The smallest real intervention is **query-anchored evidence lineage**:
1. **Preserve lineage** — every non-q0 candidate keeps `origin_query` (the bridge/subquery/graph path)
   and `discovered_by`; this plumbing already exists on `CompiledQuery`, just carry it to selection.
2. **Deepen + rerank with the bridge** — retrieve inside nominated docs and score candidates against
   `q0` AND their `origin_query`. Bridge-primary proves this surfaces + ranks the right chunks.
3. **Two-dimensional, conservative roles** (extend CA4, do not replace): DIRECT = chunk↔q0 strong;
   COMPLEMENTARY = chunk↔bridge strong AND bridge↔q0 defensible; DIVERGENT = wildcard bridge, tighter
   floor. Bounded portfolio (DIRECT dominates, COMPLEMENTARY/DIVERGENT capped). NOT `max(q0, bridge)`.
4. **The crux = bridge generation.** The existing deterministic profile-expansion bridges are
   misdirected; a good bridge is required and demonstrably unlocks the corpus. Owner decision on the
   source: **(a)** a bounded LLM concept-bridge (now justified by the admission's own "demonstrably
   insufficient" criterion AND a proven large payoff), or **(b)** a materially better deterministic
   profile→concept derivation (needs the doc profiles to hold good concept text — unverified), or
   **(c)** the GRAPH path as the bridge for graph-discovered candidates (cheap, existing signal —
   untested, promising for GRAPH mode). Separate: Scout coverage for wc03/wc10 nomination misses.

**Do not implement under WLK2A.** Preserve q0 primary, DIRECT grounding, CA0–CA5 epistemics,
unsupported-hallucination = 0, and the rerank floor. This is ready to admit as an implementation plan
once the owner picks the bridge-generation source.
