# PROFILE-SCOUT-V1 — the frozen P5 semantic contract

Owner-frozen 2026-09-18 (librarian checklist **P5**, critical-path slice 3). This is the
authority the P5a/P5b/P6 slices implement against. The scout's **output schema is itself a
semantic contract** that P6 depends on, so it is frozen here before any code.

## The one question this contract answers
**What may the scout contribute to interpretation, and what is it forbidden from changing?**
The scout contributes *reconnaissance context* ("what can this corpus contribute to
understanding this question?"). It never changes the meaning of the query, never plans,
never retrieves evidence.

## Position in the flow
```
USER QUERY q0
   │
   └── PROFILE SCOUT (new)                     # the SOLE pre-plan reconnaissance
          │                                    #   (retires _compiler_titles — the title concept injection)
          ▼
   PrePlanContext { original_query: q0, profile_scout_result }
          │
          ▼
   compile_plan  →  ChatPlan (P6 typed, provenance-carrying subqueries)
          │
          ▼
   chat_retrieve_v2  (dualread stays here, POST-plan, as the localization lane)
```
`q0` is authoritative and always searched. The scout is an **input to** `compile_plan`, never a mutator of `q0`.

## Scout ≠ dualread (do not collapse)
- **Profile Scout** — *pre-plan* — "what can this corpus contribute to understanding this question?" → interpretation context.
- **dualread** — *post-plan* — "given this information need, which documents/parents do I search?" → retrieval mechanism.
They keep different jobs and different positions. dualread is untouched by P5.

## One logical scout over TWO existing projections (no new projection)
The scout is **one logical reconnaissance** fusing nominations from two projections that
already exist and are already searchable. Atoms are **not** duplicated into the
document-profile point (that would reverse the deliberate decision to make atoms
independently addressable). `SurfaceRegistry` declares which surface family lives where.

| Projection | Surfaces (SurfaceRegistry) | Search reuse |
|---|---|---|
| `DOCUMENT_PROFILE` (dense/multi point) | identity, theme (dense); questions, searches, theories, concepts, seealso (multi) | injected profile-projection search fn |
| `PROFILE_ATOM` (`polymath_document_profile_atoms_<contract>`, one dense vector per atom) | THEORY, CONCEPT, LATENT_PATTERN, BOUNDARY, SEEALSO, BRIDGE, ANCHOR, TENSION, INVERSION, RECALLQ | `profile_atom_projection.search_atoms(client, collection, qvec, kinds, k)` |

This gives BRIDGE + the discovery surfaces from **v1**, with no atom→profile projection work.

## Output schema (frozen)
```
ProfileScoutResult:
  nominations: list[ProfileNomination]        # bounded, top-K by fused score; NOTHING else
ProfileNomination:
  doc_id: str
  matched_surfaces: list[str]                 # e.g. ["questions", "THEORY", "BRIDGE"]
  surface_types:    list[str]                 # groups: direct | semantic | discovery | lexical | identity
  provenance:       list[{projection, surface, atom_kind|null, rank, score}]  # exact origin per hit
  score: float                                # fused score
  rank:  int
  capability: str                             # SHORT text from EXISTING profile surfaces (SUMMARY if present,
                                              #   else the top matched surface's stored text) — NEVER a new LLM summary
```
**Forbidden fields** (they would make the scout a hidden planner): `recommended_mode`,
`required_subquery`, `must_use_graph`, `intent_override`, `answer_strategy`.

## Determinism (K-bound, not wall-clock)
Same `q0` + same projection snapshot ⇒ **identical** `ProfileScoutResult`. Bounded by **K**
(top-K docs), never by a wall-clock cutoff that could truncate the candidate set mid-result.
Fusion order: fused `score desc`, tie-break `doc_id asc`. `capability` is stored-surface
content. **No LLM anywhere in the scout.**

## RRF fuses candidates — it does not interpret the query (owner tightening 2026-09-18)
Fusion uses **RRF** (reciprocal-rank fusion): each doc's fused score is `Σ 1/(rrf_k + rank)`
over the ranked lists it appears in — rank-based, so the two projections' score scales
(dense-profile cosine vs atom cosine) never have to be calibrated. Critically, RRF decides
only **how already-produced ranked candidates are combined**; it is deterministic *fusion*,
**not** deterministic *interpretation*. The scout does **not** decide what `q0` means, does
**not** select a retrieval recipe, and is **not** a gate: its nominations *inform* the
adaptive planner about what the corpus can contribute, while `q0` and the planner stay
authoritative. A scout miss (a doc the profiles did not nominate) must **never** prevent
normal direct child retrieval from finding it — the scout only *adds* context, it never
subtracts candidates.

## Invariants (owner-frozen)
1. `q0` is immutable and always searched.
2. Scout nominations **add context**, never replace `q0`.
3. Scout misses cannot block normal retrieval.
4. Scout surfaces are **routing** evidence, not factual evidence (Invariant 3 of the architecture).
5. The planner may ignore scout suggestions.
6. DIRECT evidence gets priority over exploratory profile-derived expansion.
7. The scout does not choose GRAPH/WILDCARD.
8. The scout does not create subqueries; P6/the planner does.
9. The existing `dualread` post-plan localization lane stays intact.
10. If the scout returns nothing, behavior degrades to the current post-ELITE path.

## Build sequence
- **P5a — `document_profile/profile_scout.py` (pure, unit-proven).** Deterministic fusion of
  injected `profile_search` + `atom_search` results into `ProfileScoutResult`, with full
  per-hit provenance. No live wiring. Families to query are taken from `SurfaceRegistry`.
- **P5b — pre-plan wiring + retire the title injection (flagged, reversible).** Build the
  real search closures, run the scout before `compile_plan`, thread `PrePlanContext` in, and
  **retire `_compiler_titles`** (`ui.py:1671` / `:1764`, B16 register 11.122) — the scout
  replaces the title concept injection, atomic with the wiring so there is no pre-plan-recon
  gap. Default-off-in-code / on-in-`.env` `POLYMATH_PROFILE_SCOUT` (P12). Fleet-bounce-gated;
  dualread untouched.
- **P6 — typed subquery provenance.** `compile_plan` consumes nominations; each subquery
  carries `inspired_by_profile` / `profile_surface` / `reason` / role / `target`.

## Non-goals for v1
No atom→profile projection duplication. No mode/intent decisions inside the scout.

**Title injection retired (owner 2026-09-18).** The scout is the SOLE pre-plan
reconnaissance: `_compiler_titles` / the title concept injection (B16, register 11.122) is
RETIRED, not kept alongside — the scout's profile/atom nomination replaces it. The retirement
lands in P5b (the `ui.py` edit), atomic with the scout wiring so there is no pre-plan-recon
gap. dualread (post-plan) is untouched.
