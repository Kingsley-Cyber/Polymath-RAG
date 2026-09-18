---
title: "CONSTRAINT-AWARE-RETRIEVAL-V1 — implementation plan for explicit-constraint satisfaction as a first-class ranking dimension"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "ADMITTED 2026-09-18 with owner amendments (see ## ADMISSION); executing CA0→CA5 under slice discipline"
owner: "@king"
scope: "Phased plan to make explicit query-constraint satisfaction (named source/scope) a first-class ranking + evidence-grade dimension distinct from semantic relevance, extending existing contracts. Grounded in NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1 + SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1."
---

# Constraint-Aware Retrieval — implementation plan (PROPOSED)

Authoritative inputs: [SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1.md](SEMANTIC-ALIGNMENT-CONTEXT-ANCHOR-V1.md)
and [NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1.md](NAMED-SOURCE-CONSTRAINT-DIAGNOSIS-V1.md) (both `588198b`/`4ba2dbb`).
**ADMITTED 2026-09-18** with owner amendments (## ADMISSION). Base checkout: `production` @ `04113a9`.
The ADMISSION section is the BINDING spec where it refines the original decisions below.

## ADMISSION — owner decisions + amendments (BINDING)

**Governing invariant.** Semantic relevance tells us how *useful* the evidence is; constraint satisfaction
tells us whether it *answers the question the user actually asked*. **Neither signal may erase the other.**

**Key architectural rule.** Retrieval mode determines *discovery strategy*; semantic alignment determines
*evidentiary meaning*. **No retrieval mode may redefine or erase an explicit query constraint.** There is
ONE SemanticFrame, ONE constraint model, ONE evidence-role model, ONE synthesis contract across all four
modes (FAST/HYBRID/GRAPH/WILDCARD).

**D3 (source resolution) — APPROVED.** Deterministic corpus title/author/source index owns source identity
resolution, with Scout nomination as confirmation/fallback. A miss is fail-open and must not block ordinary
retrieval; Scout is never a hard retrieval gate.

**D4 (strength) — APPROVED WITH CORRECTION.** Strength comes from the RELATIONSHIP expressed in q0, not the
mere presence of a proper noun.
- HARD = explicit attribution / source-scoped truth ("What does X say…", "According to X…", "In X's book…").
  Direct-answer evidence must prioritize constraint-satisfying evidence.
- SOFT = framing/lens ("Using X as a lens…", "From X's perspective…", "Consider X alongside…"). Strong
  preference, but semantically superior supplemental evidence stays important.
- EXPLORATORY = deliberate expansion ("Starting from X…", "What ideas connect…", "Use X's idea to explore…").
  Anchor only; must not dominate discovery.
- **CORRECTION:** a bare author/source mention is NOT automatically HARD ("Murch, editing rhythm, and
  attention" → default SOFT/neutral). Default ambiguous bare mentions to SOFT/neutral unless the relation
  clearly establishes attribution.

**D2 (detection) — deterministic HARD, planner may enrich SOFT/EXPLORATORY.** Deterministic patterns detect
high-confidence HARD ("according to X", "what does X say", "in X's book", "from X's work") — protected from
planner nondeterminism. The existing semantic planner output MAY suggest SOFT/EXPLORATORY framing but MUST
NOT promote a source to HARD on its own. Resolved source identity is confirmed by the deterministic resolver
/ Scout. **No new LLM call**; reuse existing planner output.

**D5 (integration) — APPROVED IN MODIFIED FORM: portfolio partition, not a numeric boost.** Pipeline:
`semantic rerank → constraint alignment → evidence-role partition/order`. NO `rerank_score + source_bonus`,
no weight tuning. The cross-encoder stays the semantic-relevance authority.
- **HARD:** after rerank, partition candidates → constraint-satisfying = **DIRECT/PRIMARY portfolio**;
  non-satisfying-but-relevant = **RELATED/SUPPLEMENTAL portfolio**. **Preserve the reranker's ordering
  WITHIN each portfolio.** A highly relevant non-source passage (Rabiger/Ed Hooks) stays valuable but
  cannot displace valid source (Murch) evidence as the primary answer source when it exists. This is
  query-role / constraint preservation, not a Murch boost.
- **SOFT:** bounded preference / interleaving; do not force all source-matching evidence ahead of
  dramatically stronger evidence.
- **EXPLORATORY:** source is an anchor; broad semantic ranking may dominate supplemental discovery.

**CA4 (evidence role) — MODIFIED: role is multi-signal, not rerank-score bands.** Role principally reflects
information-need satisfaction + constraint satisfaction + semantic relevance + coverage (the semantic score
is ONE signal, not the definition):
- DIRECT = directly addresses a required information need AND satisfies all material explicit constraints.
- PARTIAL = supports a required need but leaves material elements unsupported.
- RELATED = grounded and semantically useful but does not directly establish the requested proposition.
RELATED is usable, not failed. When DIRECT is absent but RELATED exists, synthesis states what could not be
established, retains the grounded RELATED material, and may produce an interpretation **explicitly marked
`SYNTHETIC_INSIGHT`** (a reasoning product, never a source-supported claim). Unsupported / direct-not-found
is NOT automatically "return nothing".

**V1 scope — APPROVED: SOURCE constraints only** (representation stays extensible; DOCUMENT/SECTION/CHAPTER = V2).

**Performance — no new inference stage.** Constraint resolution/alignment is metadata/index work. Hot path:
planning → Scout → retrieval → fusion → cross-encoder → deterministic constraint alignment → evidence
portfolio → synthesis. Benchmark before/after latency and report the delta.

**Added acceptance cases (prove in CA5, beyond the plan's gates):** (1) explicit attribution → correct
source leads primary evidence; (2) no explicit source → behavior effectively unchanged; (3) legitimate
supplemental source stays available as RELATED, not discarded; (4) soft framing → preference without a hard
filter; (5) exploratory framing → source anchors, broad discovery effective; (6) missing direct + useful
related → states the gap, retains RELATED, may synthesize a clearly-distinguished interpretation.

**Non-negotiable.** No Murch-specific rule; no arbitrary numeric boosts for MRR; no gold change; no
cross-encoder removal; no second planner/retrieval engine; no extra LLM pass; no Graph multi-hop; abstraction
or semantic similarity may not erase an explicit HARD constraint.

---
_The original PROPOSED decisions below stand where the ADMISSION does not refine them._

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
