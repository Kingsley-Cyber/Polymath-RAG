---
change_id: RESTORATION-REFERENCE-ADMITTED
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "none — documents only. The owner's build reference for the semantic-transduction restoration phase admitted byte-identical; a bootstrap prompt and the continuation boundary written around it. Nothing implemented."
last_reviewed: 2026-09-21
---

# Owner restoration reference admitted — handoff to an implementation session

## Contract
Owner, 2026-09-21 (chat): "i created a file called semantic_transduction_restoration in polymath_rebuild path … an implementation specification … grounded in the audit's central finding … For the next Claude session, you can put this file into the repo and
give it only the short goal prompt from Section 26." `/polymath-bootstrap` Step 0: an approved plan that lives only outside the repo is invisible to the next session — admit it (documents only) before anything executes.

## Changes
- `docs/migration/SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE.md` (new, OWNER-CONTROLLED, byte-identical copy of `~/Documents/polymath-rebuild/SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE.md`, sha256 `58310f9c…aa20aa`): locked decisions (§3), confirmed defects (§5),
  what not to build (§6), `OpportunitySemanticViewV1` (§7), slices 1–5 (§8–§13), benchmark (§14–§15), testing / git / continuation discipline (§16–§18), stop conditions (§24), definition of done (§25), goal prompt (§26).
- `docs/migration/RESTORATION_BOOTSTRAP_PROMPT.md` (new, agent-written): the §26 prompt with the path resolved, the read order, and the repository gates.
- `docs/migration/CONTINUATION.md`: decisions LOCKED, queue = the five slices, Next Exact Action = Slice 1 in a worktree, GATES G1–G7, DELTAS D-a … D-e. `AUTO_DECISIONS.md` M-025 (index). `docs/wiki/plans/CONTINUITY-REPORT.md` next action aligned.

## Proof
The reference was READ IN FULL before admission and compared with `TRANSDUCTION_AUDIT.md`: no contradiction with repository evidence found. Copy verified by sha256 (source == installed). Guards 0 / 0 / 0 / READY. No code, manifest, contract, Trail file, fleet, database or provider touched.

## Rejected claims
- "The restoration has begun." It has not: no slice was started in this session (an audit session by the owner's brief).
- "The reference authorizes the benchmark spend / the Trail ADR / production merges in advance." The owner's standing rules make each of those a per-action owner gate; recorded in `CONTINUATION.md`, not resolved here.

## Open contract gaps
- None changed. Every contract the restoration will touch (`adapter_step`, `hypothesis_state`, `harness_receipt`, `evidence_admission`, the manifest, Trail's wire models) is **DEFERRED** to its slice; Slice 4's are additionally gated on an owner-accepted Trail ADR.
