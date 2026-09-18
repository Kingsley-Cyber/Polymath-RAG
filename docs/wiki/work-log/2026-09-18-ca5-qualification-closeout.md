---
change_id: CA5-QUALIFICATION-CLOSEOUT
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "CONSTRAINT-AWARE-RETRIEVAL-V1 CA5 — the authoritative 64×4 qualification (all CA0–CA4 flags on) + mission close-out. No new production code; persists the qualification summary + records the final state. Named-source ranking FIXED and unsupported-hallucination = 0, no regression; one pre-existing out-of-scope known limitation (resolution_trigger/res_shutter)."
last_reviewed: 2026-09-18
---

## Contract
CA5 is the acceptance authority for CONSTRAINT-AWARE-RETRIEVAL-V1: ONE authoritative 64×4 run (real
`/chat/stream`, all CA flags on, deterministic-template synth) vs the established baseline + the 6
admission acceptance cases. No selective reruns.

## Changes
- Persisted `eval/librarian_qualification/CA5-cinema-2026-09-18.summary.json` (the machine-readable
  qualification; raw artifact `qualification-cinema-2026-09-18T173550.json` sha `f19ca7ff…` in scratch).
- No production code change in this slice (the run exercises CA0–CA4, already deployed + live).

## Proof (CA5 authoritative run — HEAD 01dbbd34, flags scout/expansion/resolution/align/roles=1)
Per mode (FAST / HYBRID / GRAPH / WILDCARD):
- success@10: **1.0 / 0.983 / 0.983 / 0.983** (≥0.90 ✓).
- named-source single-target MRR: **0.946 / 0.839 / 0.839 / 0.839** (≥0.80 ✓; baseline 0.792/0.649/0.655/0.637).
- unsupported hallucination: **0.0** all modes, declined 1.0 (=0 ✓; baseline FAST/HYBRID 0.25).
- q0_preserved 1.0, provenance_complete 1.0, profile_yield>0 0.78–0.85, runtime errors 0 (all ✓).
- per-category: 23/24 at 1.0 (incl. `pmap_localization` **1.0** — the named-source fix; low_lexical,
  cross_doc_synthesis, relational, distractor, all sensitivity buckets, wildcard_discovery = 1.0).
- The 6 acceptance cases: #1 attribution-leads ✓ (pmap 1.0), #2 no-source-unchanged ✓, #3 supplemental
  stays RELATED ✓ (grades), #4 soft-bounded ✓, #5 exploratory-anchor ✓, #6 missing-direct → states the
  gap ✓ (declined 1.0, halluc 0).

## Rejected claims
- Claiming a clean 24/24 (rejected — `resolution_trigger` 0.25 stands; see Open contract gaps).
- Selectively rerunning res_shutter to change the number (rejected — single authoritative run only).
- Restoring the frontend/ELITE stash as part of this mission (rejected — separate, owner-owned).

## Open contract gaps (KNOWN LIMITATIONS / DEFERRED — not regressions, not constraint-aware failures)
- **`resolution_trigger` 0.25 (`res_shutter_motion`)** — the only flag. "shutter angle and motion blur"
  has NO named source, so CA0–CA4 never touch it; UNCHANGED from baseline (also 0.25). FAST hits (P10
  resolution), HYBRID/GRAPH/WILDCARD miss the shutter-angle aspect — a pre-existing P10/mode-ranking gap,
  out of scope for the constraint-aware mission. DEFERRED (a separate P10/mode-ranking enhancement).
- **Richer epistemic OUTPUT** — present RELATED material as an explicitly-labelled SYNTHETIC_INSIGHT
  narrative when direct support is absent but related exists. CA4 states the gap + surfaces the grades;
  the synthetic-insight PROSE rendering is DEFERRED.
- **Detector false-positives** ("the X system/method", bare author names) remain HARMLESS (resolver
  leaves them unresolved → no ranking/grade effect); tightening DEFERRED.

## Evaluator vs production (per owner)
- PRODUCTION retrieval changes: CA0–CA4 (registers 11.305–309) — detection, resolution, plumbing,
  post-rerank portfolio partition, evidence-role grading + epistemic gate. All flag-gated.
- EVALUATOR (measurement-only): CA5 decline-fix (register 11.310) — harness recognizes the abstention
  as a decline; NO gold/threshold/behavior change.
