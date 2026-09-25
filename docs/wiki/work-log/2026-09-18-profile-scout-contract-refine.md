---
title: "WORK LOG — PROFILE-SCOUT-V1 refinement: pure fusion, grounded producers, representative-not-capability"
change_id: PROFILE-SCOUT-V1-REFINE
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
status_note: "Refined contract built as P5a/P5b (11.289, 11.293, 11.294) and live-proven in 11.301; the scout flag is on. (was: design)"
architecture_impact: "Additive follow-on to the frozen PROFILE-SCOUT-V1 design (that commit is left historically frozen, NOT amended). Tightens P5 per owner constraints: P5a is a GENUINELY pure fusion primitive (no injected search callables — that is still I/O; search + normalization move to P5b); RRF operates at projection-level DOCUMENT ranking with AT MOST ONE contribution per doc per projection (collapse to best rank first, so more atoms != more weight); the scout exposes verbatim representative_text/representative_surface + full provenance, NOT a derived semantic capability; the ScoutHit schema is grounded against the real producers (profile_nominate returns doc_ids only = thin; search_atoms is rich)."
---

## Contract
Refine the frozen P5 contract to the owner's four constraints before P5a code, and ground the
normalized hit schema against what the two real producers actually expose. Acceptance: the
contract states (1) P5a is pure fusion over normalized `ScoutHit` lists with no I/O and no
injected search callables; (2) RRF gives at most one contribution per document per projection
(best-rank collapse); (3) `representative_text`/`representative_surface` replace `capability`
(no derived semantic label in deterministic code); (4) the `ScoutHit` schema reflects the
producer asymmetry — profile hits are `{doc_id, rank}`, atom hits are rich.

## Changes
- `docs/wiki/plans/PROFILE-SCOUT-V1.md` rewritten (additive follow-on): grounded producer table
  (`projection.profile_nominate` → ordered doc_ids; `profile_atom_projection.search_atoms` →
  `{doc_id, atom_kind, text, score}`); `ScoutHit` with optional atom-only fields;
  `ProfileNomination` gains `fused_score`/`representative_surface`/`representative_text`/
  `contributions` (≤1 per projection)/`provenance` (all hits) and drops `capability`; RRF rule
  states best-rank-per-doc-per-projection; build sequence moves search+normalization to P5b.
- Register row 11.288. TREE: this work-log.
- No code, no schema, no flag.

## Proof
Grounded against the rebased tree (`993f686`):
- `shared/polymath_shared/document_profile/projection.py::profile_nominate` returns `list[str]`
  (ordered doc_ids; RRF-fuses `ANSWER_SURFACES` internally via a Qdrant `FusionQuery`, payload
  `["doc_id"]` only) — so a profile hit cannot carry surface/text/score.
- `shared/polymath_shared/document_profile/profile_atom_projection.py::search_atoms` returns
  `[{doc_id, atom_kind, text, atom_id, score}]` — rich.
- `orchestrator/orchestrator/api/chat_retrieval.py::dualread_search` (line 310) confirms both
  are consumed as doc-level nominations today (profile doc_ids + atom `doc_id`s unioned), which
  is why doc-level RRF is the honest fusion.

## Rejected claims
- P5a may call injected `profile_search`/`atom_search` (rejected — a callable that hits Qdrant is still I/O; P5a must be pure over already-normalized hits, search+normalize is P5b).
- The scout derives a `capability` summary from the top surface (rejected — that is deterministic interpretation; expose verbatim `representative_text`/`representative_surface`, the planner infers meaning).
- Per-hit RRF (rejected — a doc with more atom rows would gain artificial weight; collapse to best rank per doc per projection, one contribution each).
- Raw profile/atom scores are cross-projection comparable (rejected — RRF is rank-based; scores survive only as provenance).

## Open contract gaps
- P5b must normalize `profile_nominate`'s bare doc_ids into `ScoutHit(source="profile", rank=i, surface=None, text=None, score=None)` and `search_atoms` hits into rich `ScoutHit`s.
- `representative_*` is `None` for a profile-only nominated doc (nothing verbatim to point at); P5a tests must cover that.
- Live `PROFILE_ATOM` population per corpus is still a P5b/L2 qualification gate.
