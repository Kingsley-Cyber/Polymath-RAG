---
title: "WORK LOG — P10: evidence-driven bounded resolution (EVIDENCE-RESOLUTION-V1)"
change_id: EVIDENCE-RESOLUTION-P10
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Adds the deterministic, bounded, evidence-driven resolution round (checklist P10). New pure module evidence_resolution.py: RetrievalState (q0 immutable) + ClaimState {claim_id, importance, evidence_state, next_information_need} + plan_resolution_round (fires ONE targeted resolution query only for an important unresolved gap, never past MAX_RESOLUTION_ROUNDS) + advance_state + resolution_receipt. Also adds an additive `origin` field to CompiledQuery (USER|PROFILE|GRAPH|EVIDENCE_GAP) — the resolution query is origin=EVIDENCE_GAP, and the P6 annotate step now stamps origin=PROFILE on a surviving scout link. Distinct from the existing aspect/Resolution-Lift second pass. Reuses the planner (CompiledQuery) and the normal retrieval engine; no second RAG pipeline, no recursion. The driver loop wiring is orchestrator-side (pre-live)."
---

## Contract
Checklist P10: after round-1 evidence is assembled, assess the required claims; if an IMPORTANT
information need is still `UNSUPPORTED / PARTIAL / CONFLICTING`, fire ONE targeted resolution query
for that specific gap (`role=resolution`, `origin=EVIDENCE_GAP`), fold the new evidence back, and
stop. It must be **distinct** from the existing aspect / Resolution-Lift second pass (which expands
vocabulary *before* evidence exists); **bounded** (`MAX_RESOLUTION_ROUNDS`, default 2 = round 1 +
one resolution); **observable** (a receipt per decision); have **explicit stop conditions**;
**preserve q0** lineage; **reuse** the existing planner/retrieval machinery; and never allow
runaway recursion. The next-round query comes ONLY from the RetrievalState (never invented ad hoc).

## Changes
- `shared/polymath_shared/evidence_resolution.py` (NEW, pure):
  - `EVIDENCE_STATES` (`UNSUPPORTED|PARTIAL|CONFLICTING|SUPPORTED`) + `ClaimState`
    (`claim_id/importance/evidence_state/next_information_need`, clamped/validated) + `RetrievalState`
    (`original_query` immutable, `round`, discovered docs/parents/concepts/bridges, evidence_chunks,
    answered_claims, unresolved_needs, retrieval_history).
  - `assess_claims(must_answer, evidence_texts, *, conflict_ids)` — deterministic LEXICAL gap
    detection: each required dimension → a claim whose state is SUPPORTED/PARTIAL/UNSUPPORTED by
    content-word coverage of the assembled evidence (CONFLICTING only when the caller flags it);
    importance is position-weighted. A bounded gap *signal*, not a semantic support judgment (the
    synthesizer still judges support from the children).
  - `plan_resolution_round(state, *, max_rounds, importance_floor)` → `ResolutionDecision` — fires
    for the single most important / most severe gap at/above the floor; STOPs (`stop:max_rounds` |
    `stop:no_material_gap`) otherwise. The query is a `CompiledQuery(role="resolution",
    origin="EVIDENCE_GAP", target=claim_id, type=MECHANISM)`.
  - `advance_state(...)` folds a completed round back (round+1 monotonic, evidence/docs appended, a
    SUPPORTED claim retired to `answered_claims`, history appended); `resolution_receipt(...)` emits
    the observable `{hop_2_fired, reason, resolution_query, unresolved, history}` block (P11-facing).
- `shared/polymath_shared/chat_plan.py`: additive `ORIGIN_TYPES` + `CompiledQuery.origin`
  (default `USER`, validated in `__post_init__`); `validate_plan` reads an optional `origin`.
- `shared/polymath_shared/subquery_provenance.py`: `annotate_subquery_provenance` stamps
  `origin=PROFILE` on a non-primary subquery whose scout link survived (q0 stays `USER`); the
  receipt row carries `origin`.

## Proof
`tests/determinism/test_evidence_resolution.py` — 13 asserting tests: coverage→state mapping;
conflict flag; ClaimState normalization; no-gap / low-importance STOP; a gap fires a targeted
resolution query (role=resolution ∈ ROLE_TYPES, origin=EVIDENCE_GAP ∈ ORIGIN_TYPES, target=claim);
most-important-then-most-severe selection; `max_rounds` STOP; **advance retires a SUPPORTED claim
and preserves q0**; **the full loop is bounded to exactly one resolution round (no runaway)**;
receipt shape (fired + stopped). Plus 2 new P6 origin tests (annotate stamps PROFILE on a kept
link / USER on a dropped one; validate reads origin). All green; executed path = worktree
(`polymath_shared.evidence_resolution.__file__` → `pmv4-librarian/shared/...`), genuine
UNIT_PROVEN. Regression: 48/48 pure chat_plan determinism + the P6 suite stay green after the
`origin` additions.

## Rejected claims
- Let the planner LLM re-decide Round 2 (rejected — the checklist forbids an arbitrary round; the
  next query comes ONLY from the RetrievalState's unresolved needs, deterministically).
- Infer CONFLICTING semantically in the deterministic core (rejected — conflict is caller-flagged;
  the core only measures lexical coverage, matching "children prove, no LLM in the core").
- Build a new retrieval engine / recursive loop (rejected — the resolution query is an ordinary
  `CompiledQuery` the existing engine runs; the loop is capped at `MAX_RESOLUTION_ROUNDS`).
- Wire the driver loop into `chat_retrieval.py`/`ui.py` in this slice (rejected — orchestrator is
  not worktree-importable (editable `.pth` → MAIN); the driver wiring lands in the pre-live slice
  and is qualified live L1–L5 with the resolution-round acceptance cases (mission §22)).

## Open contract gaps (impact dispositions)
- `RESOLUTION_STATE`: **UPDATED** — deferred → live; `paths`=`evidence_resolution.py`, tests filled.
  Unit-proven; the driver-loop call site is the one remaining live gate.
- `QUERY_PLANNER` (`chat_plan.py`): **UPDATED (additive, TESTED)** — new `origin` field + read;
  signatures unchanged; pure regression green.
- `SUBQUERY_PROVENANCE` (`subquery_provenance.py`): **UPDATED (TESTED)** — annotate now stamps
  `origin`; the P6 receipt row gains `origin`.
- `RETRIEVAL_RECEIPT`: **NOT_AFFECTED** yet — `resolution_receipt` is a new producer; the receipt
  assembly that embeds it is orchestrator-side (pre-live).
- `CANDIDATE_ENGINE`: **NOT_AFFECTED** — it consumes its own `SubQuery` (`sq.qtype/text/weight`),
  not `CompiledQuery`; the new `origin` field is not read there. Determinism suite green.
- `ACCEPTANCE` / `PROFILE_YIELD_RECEIPT` (P11): **DEFERRED** — P11 reads the resolution receipt +
  yield; the acceptance harness (mission §22) exercises the live loop.
- LIVE GATE: drive `plan_resolution_round`/`advance_state` in the chat retrieval loop (bounded,
  flag/budget-governed), emit `resolution_receipt` into the query receipt, qualify the
  resolution-round acceptance cases live (round-1-gap → round-2-fills → terminates; round-1-
  sufficient → no round 2).
