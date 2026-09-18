---
title: "CONSTRAINT-AWARE-RETRIEVAL-V1 — implementation plan for explicit-constraint satisfaction as a first-class ranking dimension"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "PROPOSED — awaiting owner sanction of the flagged decisions + admission; NO code until admitted"
owner: "@king"
scope: "Phased plan to make explicit query-constraint satisfaction (named source/scope) a first-class ranking + evidence-grade dimension distinct from semantic relevance, extending existing contracts. Grounded in NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1 + SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1."
---

# Constraint-Aware Retrieval — implementation plan (PROPOSED)

Authoritative inputs: [SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1.md](SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1.md)
and [NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1.md](NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1.md) (both `588198b`/`4ba2dbb`).
**This plan is PROPOSED.** No production code is written until the owner sanctions the DECISIONS below and
the plan is admitted. Base checkout: `production` @ `588198b`.

## Problem (proven)
Explicit query constraints ("in Murch's book", "according to X", "in document Y", section scope) are
extracted nowhere, represented nowhere, applied nowhere. The Scout resolves the named source to rank #1 and
it wins fusion, but the constraint-blind cross-encoder reranker — the final ordering authority, fed only
`(q0, chunk_text)` — buries it (Murch 5.34 rerank / 6th vs Ed Hooks 9.46). A no-named-source control ranks
the same → the constraint changes ranking ≈ 0.

## Goal
Explicit-constraint satisfaction becomes a **first-class ranking dimension, distinct from semantic
relevance, applied only when q0 states an explicit constraint**, deterministic and cheap, extending existing
contracts, preserving every invariant and all control-case behavior. Target: named-source single-target
MRR ≥ 0.80 with no regression on §9/§24 baselines and the four control classes.

## Design decisions

### D1 — Minimum semantic representation (extend, do not fork)
Add to `ChatPlan` (`chat_plan.py`): `explicit_constraints: list[Constraint]`, default `[]`.
`Constraint = {kind, value, strength, resolved_targets, confidence}`:
- `kind ∈ {SOURCE, DOCUMENT, SCOPE}` — start with **SOURCE** only (the proven failure); field extensible.
- `value` — surface text ("Walter Murch", "Save the Cat").
- `strength ∈ {HARD, SOFT, EXPLORATORY}` (see D4).
- `resolved_targets: list[str]` (doc_ids; filled by CA1), `confidence: float`.
Reuse for the rest of the "SemanticFrame" — do NOT invent a parallel ontology: information needs =
`ChatPlan.must_answer`; per-subquery semantics = `CompiledQuery.{type, role, origin, target}`; abstraction/
exploratory intent = `ChatPlan.intent`. **`entities` stays as-is** (not promoted here).

### D2 — Detection is DETERMINISTIC (not LLM)
`detect_explicit_constraints(q0) -> list[Constraint]` in `shared/` — deterministic patterns
("in/according to/from/per <Proper Noun>['s book]", "in (the )?document/chapter/section …", "what does
<Proper Noun> say"). Rationale: the qualification proved the LLM compiler is nondeterministic (it emitted a
spurious PRIMARY for out-of-domain queries → the hallucination gate); constraint detection must be reliable
and cheap, not model-dependent. A bare topical query yields `[]` (control-safe).

### D3 — Resolution reuses the Scout, backed by a title/author index
`resolve_constraint_targets(constraints, corpus_id) -> constraints'` in `shared/`: resolve SOURCE value →
doc_id(s) by lexical match against the corpus source_name/author index (deterministic), with the existing
Scout nomination as fallback/confirmation (the Scout already ranks the named doc #1). `confidence` reflects
match quality; a miss leaves `resolved_targets=[]` and the query degrades to ordinary retrieval (invariant:
a miss never blocks retrieval).

### D4 — Constraint strength governs application (§12)
- **HARD** (default for "what does X say", "in X's book"): constraint-satisfying evidence must lead; the
  named source's best qualifying chunk ranks first among evidence.
- **SOFT** ("using X as the main lens"): a bounded prior for constraint-satisfying evidence; strong
  alternatives still contribute substantially.
- **EXPLORATORY** ("starting from X, what connects"): the source anchors, broad semantic expansion dominates.
Strength inferred deterministically from the constraint phrasing (patterns), default **HARD** for a bare
named source.

### D5 — Reranker integration = POST-RERANK deterministic alignment  ⟵ **DECISION REQUIRED (owner sanction)**
Keep the cross-encoder pure (it does real semantic work, §17). After rerank, when an explicit constraint is
present and confidently resolved, apply a **deterministic constraint-alignment re-order** governed by
strength (D4). Distinct signal (§7), deterministic/cheap (§16, no new model pass), **identity when no
explicit constraint** (control-safe), and reuses the resolved targets (D3).
- Alternatives considered + why not primary: (b) augment reranker input with source text — blends the two
  signals into one score (owner wants them distinct) and perturbs all queries; (d) additive term into
  `fused_score` before rerank — **proven futile** (rerank overrides fusion; savecat had the exact term and
  still lost). A partition-then-rerank variant (§17) is a fallback if post-rerank re-order proves too blunt.
- **This embodies the sanction the diagnosis flagged:** a resolved explicit constraint (via Scout/index)
  now *adds rank* — a deliberate, bounded shift from "scout informs, never gates" that applies ONLY when the
  query states an explicit constraint. The Scout stays purely advisory for unconstrained queries.

### D6 — Evidence support-grade + synthesis mirroring (later phase)
Add per-evidence `support_role ∈ {DIRECT, PARTIAL, RELATED}`, deterministic from (rerank-score band +
constraint satisfaction + lexical coverage) — distinct from the existing lane role (DIRECT/PRECISION/
RELATIONAL/LATENT). Thread `need → evidence → support_role` into `assemble_evidence_bundle`, reusing the
`POLYMATH_CHAT_SYNTH_ROLES` seam. `SYNTHETIC_INSIGHT` stays a reasoning product (already separate via
`derived_insights`). This is where the §23 "unsupported hallucination" gate is properly resolved: genuinely
unsupported queries have only negative-rerank evidence → graded RELATED/none → the answer states what could
not be established rather than fabricating (per the owner's epistemic-output requirement).

## Phased slices (change-slice discipline; each admittable + proven)
| Phase | Layer | Change | Proof | Acceptance |
|---|---|---|---|---|
| **CA0** | `shared/` | `Constraint` + `ChatPlan.explicit_constraints`; `detect_explicit_constraints` | UNIT (worktree) | named-source qs → correct kind/value/strength; controls → `[]` |
| **CA1** | `shared/` | `resolve_constraint_targets` (index + scout fallback) | UNIT | Murch/Lumet/SaveTheCat → correct doc_id; miss → `[]`+low confidence |
| **CA2** | `orchestrator/` | plumb resolved constraints/strength from `ui.py` into the post-retrieval stage (new channel, NOT the stripped subquery tuple) | LIVE (bounce) | receipt shows resolved constraints; ranking unchanged (no-op wiring) |
| **CA3** | `shared/` helper + `ui.py` wiring | `align_by_constraint(ranked, targets, strength)` (pure) + post-rerank call, flag `POLYMATH_CHAT_CONSTRAINT_ALIGN` (default off → byte-identical) | UNIT (helper) + LIVE qual | named-source MRR↑ ≥0.80; controls unchanged; success@10 ≥0.90 |
| **CA4** | `shared/` + `ui.py` | `support_role` grades + need→evidence threading into the bundle (reuse `POLYMATH_CHAT_SYNTH_ROLES`) | UNIT + LIVE | unsupported → graded RELATED/none (halluc gate → 0); DIRECT/PARTIAL/RELATED present |
| **CA5** | `eval/` | extend gold with named-source × strength + control classes; full 64×4 + controls | LIVE qual | all acceptance gates green; one final authoritative run |

Editing `shared/`/`orchestrator` trips the stale-bundle fence / needs a port-gated bounce; CA2–CA5 are
live-only proof (§2b: orchestrator not worktree-unit-testable). CA0/CA1/CA3-helper are pure `shared/`,
worktree-unit-provable.

## Acceptance gates (measure before/after vs committed baselines)
- Named-source **single-target MRR ≥ 0.80** (all modes) — the primary target.
- **No regression:** success@10 ≥ 0.90 all modes; the four control classes (direct-no-source, exploratory,
  unsupported, legit-alternate-source) unchanged within tolerance; provenance 1.0; q0 1.0.
- **The 3 open qualification gates** closed: single-target MRR (CA3), unsupported hallucination (CA4),
  resolution_trigger (assessed — may be a distinct mode-ranking item, scoped separately if so).
- **Latency:** negligible increase (deterministic alignment; rerank remains the hot path — §8 baseline).
- Do NOT lower a gate, redefine gold, Murch-boost, or weight-tune (§29).

## Invariants preserved
Profiles nominate · pMAPs localize · children prove · synthetic ≠ evidence · q0 authoritative · scout
advisory for unconstrained queries · abstraction may not erase explicit constraints · RRF is fusion not
interpretation · expand only as needed · cross-encoder retained. No second planner/engine/candidate/RAG path.

## Risks + rollback
Every behavioral slice is flag-gated (`POLYMATH_CHAT_CONSTRAINT_ALIGN`, and CA4 via `POLYMATH_CHAT_SYNTH_ROLES`)
and default-off → byte-identical when off (instant rollback). Over-application risk (forcing a weak named
source over a genuinely better answer) is bounded by `strength` + `confidence` gating and measured on the
control classes.

## DECISIONS REQUIRED (owner sanction before CA3 executes)
1. **D5 reranker integration = post-rerank deterministic alignment** (recommended) vs partition-then-rerank vs
   reject the "constraint adds rank" shift entirely.
2. **D4 strength model** — confirm HARD default for a bare named source; confirm the SOFT/EXPLORATORY phrasings.
3. **D3 resolution** — build the deterministic title/author index resolver (recommended) vs rely on the Scout
   nomination alone.
4. **Scope** — SOURCE constraints only in V1 (defer DOCUMENT/SECTION scope) — confirm.

## Do not do (until admitted + sanctioned)
Write any CA0–CA5 code; Murch-specific boost; RRF/rerank weight tuning; gold change; second engine; remove the
cross-encoder; Graph multi-hop; `git push`; restore the frontend stash.

## Admission checklist
- [ ] Owner sanctions D3/D4/D5 + scope.
- [ ] Register rows reserved (next after 11.304) per slice.
- [ ] Baseline re-confirmed green before CA3.
- [ ] Each slice: work-log + register + scaffold decl + proof at the true level.
