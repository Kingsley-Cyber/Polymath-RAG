---
title: "SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1 — current architecture + named-source evidence for the constraint-aware retrieval phase"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "ARCHITECTURE_DIAGNOSED / CONTEXT_ANCHORED (NOT implemented)"
owner: "@king"
scope: "Context-reconstruction anchor for the Semantic Alignment / Constraint-Aware Retrieval phase. Grounds every retrieval stage against live code (HEAD 4ba2dbb), preserves the named-source causal trace + baselines + invariants. No SemanticFrame, no constraint-aware ranking, no evidence-role or synthesis change implemented."
---

# Semantic Alignment context anchor

Authoritative input to the future Constraint-Aware Retrieval implementation plan. Everything here is
grounded against the deployed code (branch `production`, HEAD `4ba2dbb`) + live probes this session.
Proof status: **ARCHITECTURE_DIAGNOSED / CONTEXT_ANCHORED — not IMPLEMENTED.** Companion:
[NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1.md](NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1.md) (`4ba2dbb`).

## Repo truth (verified this session)
- path `/Users/king/Documents/polymath-rebuild/polymath-v4` · branch `production` · HEAD `4ba2dbb` · tree CLEAN.
- Module resolution: `polymath_shared`→ repo `shared/`; `orchestrator/workers/control`→ namespace pkgs, editable `.pth`→ MAIN (= this checkout, which the live fleet runs). `.venv` is MAIN-only. Probes ran the deployed code.
- Live flags: `POLYMATH_PROFILE_SCOUT=1`, `POLYMATH_CHAT_PROFILE_EXPANSION=1`, `POLYMATH_CHAT_RESOLUTION=1`, `POLYMATH_CHAT_INTENT_POLICY=on`, `HIERARCHY_ROUTE_DOCUMENTS=1`, `DOC_PARENT_MAP_ENABLED=1`.
- Stash `49f57e0c` (frontend/ELITE stream) still held. Worktrees: `_graft_polymath`, `pmv4-librarian` (merged), `polymath-v4-handoff`, `polymath-v4-main` (all secondary; the fleet runs `production`).

## 1. CURRENT ARCHITECTURE (deployed chat path, stage → owner)
`POST /chat/stream` (`ui.py:3444`) → `run_chat`:
1. **Profile Scout** — `ui.py::_profile_scout` (embeds whole q0 once; `profile_nominate` + `search_atoms`; `document_profile/profile_scout.py::fuse_profile_scout_hits`, RRF k=60).
2. **Compile plan** — `ui.py::_compile_chat_plan` → `chat_plan.py::compile_plan` (LLM lane + deterministic fallback); scout titles condition the compiler; then `_add_profile_expansion` (P11) + `annotate_subquery_provenance` (P6).
3. **Retrieve** — `ui.py:3035` → `chat_retrieval.py::chat_retrieve_mode` → `chat_retrieve_v2` → `candidate_engine.py::retrieve_candidates`. Modes = compositions: FAST=VECTOR(A+B), HYBRID=A+B+C, GRAPH=HYBRID→bounded hop-1, WILDCARD=HYBRID∥latent frontier. Lanes A HIERARCHICAL_ROUTE / B GLOBAL_DENSE_CHILD / C GLOBAL_SPARSE_CHILD; optional D latent / E dualread(pMAP) / F resolution_lift / G seealso / H graph_dest.
4. **pMAP localization** — `parent_map_projection.py::search_parent_maps` (query-time, lane E dualread + graph_dest), doc set from `profile_nominate` over the q0 vector (semantic, not named-source).
5. **Fusion** — `candidate_engine.py:968-1052` child-level RRF over lane RANKS (k=60, lanes unweighted, subquery `weight`); `fused_score = best + min(best, 0.5·extra)`.
6. **Rerank** — `select_evidence` → `fast.py::_rerank_children` → `rerank.py::apply_rerank` (cross-encoder). **The final ordering authority.**
7. **Evidence assembly** — `evidence_assembly.py::assemble_evidence_bundle` (+ GRAPH fail-open sink).
8. **P10 resolution** — `ui.py::_maybe_resolve` (`evidence_resolution.py`), FAST/HYBRID, one bounded round-2 merged into `fast["evidence"]`.
9. **Synthesis** — `answer_synthesis.py` over `bundle["evidence_bundle"]`; receipt `retrieval.*`.

## 2. CURRENT TYPES / OWNERS
- **`ChatPlan`** (`chat_plan.py:143-164`): contract, original/resolved_request, task_type, evidence_policy, retrieval_required, retrieval_goal, `queries`, semantic_queries, `exact_terms`, `entities`, `must_answer`, `user_constraints`, response_type, antecedent, `graph_useful`, `intent`, compiler.
- **`CompiledQuery`** (`chat_plan.py:113-140`): id, type, query, weight, `role` (direct/prerequisite/complement/bridge/contrast/inversion/resolution), reason, `inspired_by_profile` (list), `profile_surface`, `target` (free-text need), `origin` (USER/PROFILE/GRAPH/EVIDENCE_GAP).
- **`SubQuery`** (`candidate_engine.py:366-375`): id, type, query, weight — **no target/doc_id** (this is the retrieval boundary shape).
- **`CandidateEvidence`** (`candidate_engine.py:378-412`): chunk_id, doc_id, source_name, text, `arrivals` (lanes), `query_ids`, hierarchy_rank/dense_rank/sparse_rank, dense/sparse_score, `rerank_score`, `fused_score`, `document_rank` (carried, NOT scored), query_scores.
- **`ScoutHit` / `ProfileNomination`** (`profile_scout.py:26-64`): doc_id, rank, fused_score, representative_surface/text — deliberately no recommended_mode/subquery/mode-override.
- **`ClaimState` / `EVIDENCE_STATES`** (`evidence_resolution.py:29`): UNSUPPORTED/PARTIAL/CONFLICTING/SUPPORTED (claim-level, drives P10).

## 3. CURRENT RANKING CONTRACT
- Two RRF levels: **doc-level** (`pass1.aggregate_documents`, routing/localization only) and **child-level** (`candidate_engine.py:968-1052`, the real evidence ranking). Both fuse RANKS, k=60, lanes unweighted.
- Doc identity enters fusion **only to SUPPRESS** (per-doc non-best vote halved; region/noise demotion) — anti-dominance, never a source boost. `document_rank` carried, never scored.
- **Reranker = the final authority** and scores **`(q0 retrieval_text, chunk_text[:4000])` only** — never doc_id/source_name/heading/scout-rank/constraint. One cross-encoder score is the whole final signal.
- Only hard per-doc scope = `document_ids` (DOCUMENT-SCOPED-RETRIEVE-V1) — **rejected by the chat engine with 422**, never derived from q0.
- `exact_terms` → lane-C BM25 admission only (token overlap on chunk text), fused like any lane; not a constraint/boost/filter.

## 4. CURRENT SYNTHESIS CONTRACT
- `assemble_evidence_bundle(query, graph_facts, evidence_rows, …)` → `bundle["evidence_bundle"]` (chunk items: source_span/locator, presentation title/heading, applicability source_name, text_kind).
- `bundle["evidence_roles"]` = per-chunk **lane role DIRECT/PRECISION/RELATIONAL/LATENT** (from `synthesis_role(arrivals)`), flag `POLYMATH_CHAT_SYNTH_ROLES` (default off → byte-identical prompt). **This is retrieval-lane provenance, not support-strength.**
- `bundle["derived_insights"]` = wildcard bridges, rendered as DERIVED, **never part of `chunks` evidence** (invariant already honored).
- Graph facts render with an epistemic prefix (`answer_synthesis.py::_epistemic_prefix`); per-claim `epistemics{certainty,attributed,attribution_source,negated}`.
- **Lost at synthesis:** the per-information-need→evidence mapping (which `must_answer`/`target`/aspect each chunk answers), the query's explicit constraints, and any DIRECT/PARTIAL/RELATED support grade. `query_ids`/aspects exist in the receipt but are NOT threaded into the synthesis bundle.

## 5. NAMED-SOURCE LIVE TRACE (primary motivation; from live probes + artifact `…140711.json` sha `95767ad1…`)
| Case | Scout rank | best fused | best RERANK (rerank-rank) | final doc rank | winner rerank |
|---|---|---|---|---|---|
| Murch / *In the Blink of an Eye* | **#1** | 0.0568 | 5.34 (6th/15) | 3 | Ed Hooks 9.46 |
| Lumet / *Making Movies* | **#1** | 0.0317 | 2.36 (4th) | 4 | Cinematic Motion 4.88 |
| Save the Cat | **#1** | 0.0292 | 2.19 (4th) | 4 | Anatomy of Story 5.80 |

**Control** ("What is the blink theory of editing?", NO "Murch"): reranker Rabiger 6.84 > Murch 2.89 (Murch rank 4). With "Murch" present, Murch still ranks 3–4 → **the explicit constraint changes ranking ≈ 0**. `pmap_savecat` even had `exact_terms=['Save the Cat','fifteen beats']` and still lost — lexical capture doesn't help because rerank overrides fusion.

## 6. WHERE SEMANTIC INFORMATION IS LOST
1. **Compiler** — the named source is never extracted into a structured field (`exact_terms` regex can't match mixed-case "Murch"; no source/author/title field; compiler is designed to *strip* source names). Survives only as q0 tokens.
2. **Retrieval boundary** (`ui.py:3040`) — subqueries pass only `(id,type,query,weight)`; `CompiledQuery.target/origin/inspired_by_profile` are dropped (`SubQuery` has no target). The scout's #1 resolution and profile-expansion's `target=doc_id` never reach retrieval as a filter/boost.
3. **Reranker** — receives only `(q0, chunk_text)`; discards doc identity, scout rank, lane rank, fused score. **This is where the named source loses its winning position.**
4. **Synthesis bundle** — no per-need / constraint / support-grade structure (§4).

## 7. EXISTING SEMANTIC SIGNALS WORTH REUSING (no new model call needed)
- `ChatPlan.intent` (DEFINITION/SYNTHESIS/PROCEDURE/EXPLORATORY/RELATIONSHIP…), `must_answer` (information needs), `user_constraints`, `exact_terms`, `entities` (currently inert), `retrieval_goal`, `graph_useful`, `evidence_policy`, `retrieval_required`.
- `CompiledQuery.{type, role, origin, target, weight, inspired_by_profile, profile_surface}` — most of a per-subquery semantic frame already exists.
- Scout **nomination rank** (already computed; = the source resolution for "in X's book").
- Receipt `aspects` / `weak_aspects` (per-need candidates in union/final), `profile_yield`, `resolution`.
- Evidence **lane role** DIRECT/PRECISION/RELATIONAL/LATENT + the `POLYMATH_CHAT_SYNTH_ROLES` role-aware synthesis seam (built, default-off).
- **Rerank score itself** as a support-grade signal (control: irrelevant python chunks scored −5…−11; relevant chunks +5…+9) — a natural DIRECT/PARTIAL/RELATED/none band.
- `EVIDENCE_STATES` (UNSUPPORTED/PARTIAL/CONFLICTING/SUPPORTED) claim-level vocabulary.

## 8. PERFORMANCE BASELINE (live probes, HYBRID, ms)
- embed ≈ 230–290; lanes ≈ 1340–1540 (hierarchical_children dominates ≈ 1150–1390); **rerank ≈ 2650 (definition) → 7430 (exploratory)**; union ≈ 2–7; total ≈ 3330–9210.
- End-to-end p50 (qualification): FAST 15.98s, HYBRID 9.23s, GRAPH 8.69s, WILDCARD 11.64s (includes synthesis).
- **Rerank is the hot path** → the alignment layer must be deterministic/cheap; no per-candidate LLM classification (§16).

## 9. QUALIFICATION BASELINE (artifact `…140711.json`; summary committed `BASELINE-cinema-2026-09-18.summary.json`)
- success@10: FAST 1.0 / HYBRID 0.983 / GRAPH 0.983 / WILDCARD 0.983. All categories 1.0 **except resolution_trigger 0.25**.
- single-target MRR: FAST 0.792 / HYBRID 0.649 / GRAPH 0.655 / WILDCARD 0.637 (**below 0.80** — the named-source issue; true single-answer `exact_*` = 1.0).
- unsupported hallucination: FAST 0.25 / HYBRID 0.25 / GRAPH 0 / WILDCARD 0 (the spurious-PRIMARY + P11 amplification case).
- provenance_complete 1.0; q0_preserved 1.0; profile_yield>0 rate 0.74–0.85; runtime errors 0.

## 10. NON-NEGOTIABLE INVARIANTS (preserve unless owner supersedes)
Profiles nominate · pMAPs localize · children prove. Synthetic material (DOCUMENT_PROFILE, PARENT_MAP, PROFILE_ATOM, BRIDGE, TENSION, INVERSION, LATENT_PATTERN, SEEALSO) may guide but must not silently become factual evidence. q0 authoritative · scout informs, does not gate · scout miss never blocks retrieval · generated subqueries supplement q0 · graph nominates/routes, chunks prove · RRF is fusion not interpretation · cross-projection raw scores not assumed calibrated · expand only as much as necessary. **Abstraction may expand meaning; it may not erase explicit query constraints.** Cross-encoder stays (it does real semantic work) — the fix is to stop it *erasing* other valid signals, not to remove it.

## 11. LIKELY IMPLEMENTATION SEAMS (extend, do not fork)
`ChatPlan`/`CompiledQuery` (add `explicit_constraints` + `constraint_strength`; reuse `must_answer`/`target`/`role`/`intent`) → carry constraint state THROUGH the retrieval boundary (widen the subquery tuple or pass plan-level constraints) → resolve source→doc via the existing scout nomination → a **deterministic post-fusion / post-rerank alignment step** that combines cross-encoder relevance with constraint satisfaction (partition or additive term, decided in planning) → thread need→evidence→support-grade into `assemble_evidence_bundle` → role-aware synthesis via the existing `POLYMATH_CHAT_SYNTH_ROLES` seam. No second planner / engine / candidate pipeline / RAG path.

## 12. MINIMUM SEMANTIC CONTRACT — answers (§22)
1. **Exists:** intent, must_answer, user_constraints, exact_terms, entities, target, role, origin, scout rank, aspects, lane role, rerank score. 2. **Lost:** explicit named-source/scope constraint, constraint strength, per-need→evidence→grade mapping into synthesis, scout resolution at ranking. 3. **Boundaries lost:** compiler (not extracted), retrieval boundary `ui.py:3040` (target/origin stripped), reranker (q0×chunk only), synthesis bundle (no need/grade). 4. **Owner type:** `ChatPlan` (+`CompiledQuery`). 5. **Consumer:** candidate ordering/`select_evidence` + `assemble_evidence_bundle`. 6. **Must reach reranker (or a step beside it):** a per-candidate constraint-satisfaction signal (or keep rerank pure + deterministic post-rerank alignment consuming doc_id + resolved target + scout rank). 7. **Stay deterministic:** constraint detection, source→doc resolution (scout), the alignment/ordering term, support-grade banding. 8. **To evidence assembly:** per-chunk support role + the need it answers + constraint-satisfaction flag. 9. **To synthesis:** need→evidence→support-grade structure; derived kept separate. 10. **No model call:** all of the above are deterministic (detection may ride the compiler LLM that already runs).

## 13. OPEN DESIGN QUESTIONS
- Constraint strength (§12): HARD vs SOFT vs EXPLORATORY — minimum representation? (probably an enum on the explicit constraint).
- Reranker integration (§17): partition (rerank within evidence classes) vs additive constraint term vs a post-rerank re-order gated on explicit constraints — which preserves control-case behavior best?
- Support grade source: rerank-score bands vs lexical coverage (`assess_claims`) vs both, for DIRECT/PARTIAL/RELATED.
- Where does source→doc resolution live when the scout misses but the source is named (fallback title index)?
- Does `entities` get promoted from inert to a constraint carrier, or a new field?
- Epistemic output (DIRECT/PARTIAL/RELATED + SYNTHETIC_INSIGHT): reuse `evidence_roles` + `EVIDENCE_STATES`, or a new grade? (Recorded in the diagnosis doc; not an active contract.)

## 14. DO NOT DO
Implement the SemanticFrame / constraint-aware ranking / evidence-role grades / synthesis change (this pass). Murch-specific boost. RRF/rerank weight tuning to satisfy the benchmark. Gold-label change. Second planner/engine/candidate/RAG path. Increase Scout K / add profile searches / duplicate lanes to “fix” ranking. Remove the cross-encoder. Conflate sidecar/memory reliability with the ranking defect. Start Graph multi-hop. `git push`. Restore the frontend stash yet.

## 15. NEXT PLANNING ACTION
Open the **Semantic Alignment / Constraint-Aware Retrieval implementation plan** using this anchor + the diagnosis (`4ba2dbb`) as authoritative input. First planning task: decide the minimum `explicit_constraints` + `constraint_strength` representation on `ChatPlan`/`CompiledQuery` and the reranker-integration shape (§13), with before/after measured against §8 latency + §9 qualification baselines. No code until the plan is admitted.
