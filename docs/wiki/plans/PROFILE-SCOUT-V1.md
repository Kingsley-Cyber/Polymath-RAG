---
title: "PROFILE-SCOUT-V1 — the frozen P5 Profile Scout semantic contract"
date: 2026-09-18
last_reviewed: 2026-09-18
status: "FROZEN CONTRACT"
owner: "@king"
scope: "P5 Profile Scout — deterministic dual-projection fusion; the output schema P6 depends on"
---

# PROFILE-SCOUT-V1 — the frozen P5 semantic contract

Owner-frozen 2026-09-18 (librarian checklist **P5**, critical-path slice 3). This is the
authority the P5a/P5b/P6 slices implement against. The scout's **output schema is itself a
semantic contract** that P6 depends on, so it is frozen here before any code. Refined
2026-09-18 with the owner's fusion/purity constraints (this file is the additive follow-on to
the frozen design commit; the design commit is left historically frozen, not rewritten).

## The one question this contract answers
**What may the scout contribute to interpretation, and what is it forbidden from changing?**
The scout contributes *reconnaissance context* ("what can this corpus contribute to
understanding this question?"). It never changes the meaning of the query, never plans,
never retrieves evidence, never labels what a match *means*.

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

## One logical scout over TWO existing projections (grounded producers)
The scout is **one logical reconnaissance** fusing nominations from two projections that
already exist and are already searchable. Atoms are **not** duplicated into the
document-profile point. The two real producers expose **different amounts** — proven against
the code, not assumed:

| Projection | Real search primitive (grounded) | What a hit exposes |
|---|---|---|
| `DOCUMENT_PROFILE` | `projection.profile_nominate(client, collection, qvec, corpus_id, k)` — RRF-fuses the answer surfaces (identity/theme/title + questions/searches multivectors) **internally** and returns **ordered `doc_id`s only** | `{doc_id, rank}` — **thin**: no per-surface attribution, no text, no per-doc score (surfaces are fused away inside Qdrant) |
| `PROFILE_ATOM` | `profile_atom_projection.search_atoms(client, collection, qvec, kinds, k)` | `{doc_id, atom_kind, text, score, rank}` — **rich**: per-atom surface + verbatim snippet + score |

**Producer asymmetry (do not paper over it).** The normalized `ScoutHit` makes the atom-only
fields optional; a profile hit is honestly just `{doc_id, rank}`. This still gives BRIDGE + the
discovery surfaces at **v1** (through the atom lane) with no atom→profile projection work.

## Output schema (frozen)
The normalized input hit — **P5b** produces these from the two real searches; **P5a** fuses them:
```
ScoutHit:                                     # one normalized hit from one projection
  doc_id: str
  source: "profile" | "atom"
  rank:   int                                 # 1-based rank within its projection's ranked list
  surface:      str | None                    # atom_kind for atom hits; None for profile
  surface_type: str | None                    # SurfaceRegistry group for atom hits; None for profile
  text:         str | None                    # verbatim stored snippet for atom hits; None for profile
  score:        float | None                  # raw projection score for atom hits; None for profile
```
The fused result — what the planner receives:
```
ProfileScoutResult:
  nominations: list[ProfileNomination]        # bounded, top-K by fused_score; NOTHING else
ProfileNomination:
  doc_id: str
  fused_score: float                          # Σ of the per-projection RRF contributions
  rank:  int                                  # 1-based rank in the fused result
  matched_surfaces: list[str]                 # every surface/atom_kind that matched (from provenance)
  surface_types:    list[str]                 # SurfaceRegistry groups present
  representative_surface: str | None          # the best hit's surface (verbatim pointer; None if profile-only)
  representative_text:    str | None          # the best hit's stored snippet (verbatim; NO synthesis, NO LLM)
  contributions: list[ProjectionContribution] # AT MOST ONE per projection (see the RRF rule)
  provenance:    list[ScoutHit]               # EVERY contributing hit, verbatim (all surfaces/atoms kept)
ProjectionContribution:
  source: "profile" | "atom"
  best_rank: int                              # the doc's best (lowest) rank in that projection
  rrf_contribution: float                     # 1/(rrf_k + best_rank)
```
**No `capability`.** The scout exposes verbatim pointers (`representative_text` /
`representative_surface`) and full provenance; the adaptive **planner** decides what those
matches *mean* for the request. The deterministic scout never derives or labels a semantic
capability — that would smuggle interpretation into the fusion layer.
**Forbidden fields** (they would make the scout a hidden planner): `recommended_mode`,
`required_subquery`, `must_use_graph`, `intent_override`, `answer_strategy`.

## RRF fuses candidates — it does not interpret the query (owner tightening 2026-09-18)
Fusion uses **RRF** (reciprocal-rank fusion) at the **projection-level document ranking**:
each projection contributes **at most ONE** RRF vote per document — its raw hits are first
collapsed to the doc's **best (lowest) rank**, so a document with many atom rows cannot gain
artificial fusion weight from row count. A doc's `fused_score = Σ 1/(rrf_k + best_rank)` over
the projections it appears in. Rank-based, so the two score scales (dense-profile vs atom
cosine) are never compared — raw `score`s survive **only as provenance**, never as
cross-projection authority. Critically, RRF decides only **how already-produced ranked
candidates are combined**; it is deterministic *fusion*, **not** deterministic
*interpretation*. The scout does **not** decide what `q0` means, does **not** select a
retrieval recipe, and is **not** a gate: its nominations *inform* the adaptive planner while
`q0` and the planner stay authoritative. A scout miss must **never** prevent normal direct
child retrieval — the scout only *adds* context, it never subtracts candidates.

## Determinism (K-bound, not wall-clock)
Same normalized `ScoutHit` inputs ⇒ **identical** `ProfileScoutResult`. Bounded by
`max_documents` (top-K), never by a wall-clock cutoff that could truncate the set. Order:
`fused_score desc`, tie-break `doc_id asc`. `representative_text` is a verbatim stored snippet.
**No LLM anywhere in the scout.**

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
- **P5a — `document_profile/profile_scout.py` (GENUINELY pure, unit-proven).** The normalized
  `ScoutHit` / `ProfileScoutResult` types and the pure
  `fuse_profile_scout_hits(profile_hits, atom_hits, *, rrf_k, max_documents)` — deterministic
  RRF fusion over already-normalized ranked hits, full provenance retained. **No retrieval
  backend, no I/O, no injected search callables** (a callable that hits Qdrant is still I/O).
  `SurfaceRegistry` supplies the surface→group map only.
- **P5b — search + normalize + pre-plan wiring + retire the title injection (flagged, reversible).**
  Run the two real searches (`projection.profile_nominate` → ordered doc_ids; `search_atoms`
  → atom hits), **normalize** them into `ScoutHit`s, call the pure P5a fusion, run it before
  `compile_plan`, thread `PrePlanContext` in, and **retire `_compiler_titles`**
  (`ui.py:1671`/`:1764`, B16 register 11.122) atomic with the wiring so there is no
  pre-plan-recon gap. Default-off-in-code / on-in-`.env` `POLYMATH_PROFILE_SCOUT` (P12).
  Fleet-bounce-gated; dualread untouched.
- **P6 — typed subquery provenance.** `compile_plan` consumes nominations; each subquery
  carries `inspired_by_profile` / `profile_surface` / `reason` / role / `target`.

## Non-goals for v1
No atom→profile projection duplication. No mode/intent decisions inside the scout. No injected
search backend inside the pure P5a primitive. No derived semantic `capability` in deterministic
scout code.

**Title injection retired (owner 2026-09-18).** The scout is the SOLE pre-plan reconnaissance:
`_compiler_titles` / the title concept injection (B16, register 11.122) is RETIRED, not kept
alongside — the scout's profile/atom nomination replaces it. The retirement lands in P5b (the
`ui.py` edit), atomic with the scout wiring. dualread (post-plan) is untouched.
