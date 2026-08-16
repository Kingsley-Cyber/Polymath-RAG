---
change_id: i4r-a-boundary
owner: worker
date: 2026-08-16
status: complete
architecture_impact: adds-rescue-lane-behind-flag-no-default-change
last_reviewed: 2026-08-16
---

# I4R-A: boundary reconciliation (GLiNER-verified span rescue)

## Contract

I4R umbrella gate, explicitly authorized 2026-08-16 with the staged
plan: I4R-A boundary reconciliation → I4R-B missing-argument rescue →
I4R-C type reconciliation → I4R-D dependency/frame arbitration, one
isolated commit + frozen-I4 measurement after each, combined
configuration as the final I4R result. I4 remains a development
regression set (bars: P >= 0.95, R >= 0.70, out-of-envelope 100%
abstention, must-not-assert 100%); I5 is the future sealed
generalization test. The frozen I4 evaluator/corpus/gold stay
byte-identical.

I4R-A (this change): align pass-1 GLiNER entity spans against spaCy
noun chunks over the same sentence slices. Clean alignment retains.
A span strictly inside a larger argument NP becomes a rescue
candidate: GLiNER is re-queried with EXACTLY the target NP text and
ONLY the original label, same pinned model/revision, same frozen 0.5
threshold, via a new batched `/rescue` endpoint on the existing GLiNER
sidecar (model untouched; `/infer` untouched). Acceptance is
exact-full-span-only (start==0, end==len(text), same label): accepted
→ the argument binds to the expanded span; refused → the argument is
BOUNDARY_UNRESOLVED: the original proposal stays a durable
mention/entity, but facts needing that argument in THIS sentence
abstain. No deterministic promotion anywhere. Leading determiners are
trimmed from NP targets (entities never carry "the/a/its").

Policy flag: `POLYMATH_RESCUE` (off | on | comma list from
{boundary, missing_argument, type_reconciliation, frames}), default
off = byte-identical production. Requires
`POLYMATH_SYNTAX_PROVIDER=spacy` when enabled; fails loudly otherwise.

## Changes

- `shared/polymath_shared/settings.py` — `RescueSettings`
  (`POLYMATH_RESCUE`, default off) + `rescue_enabled()` helper.
- `sidecars/gliner_runtime/server.py` — additive `POST /rescue`
  (batched {text, labels} requests against the same resident model,
  frozen threshold carried per request); `/infer` byte-identical.
- `contracts/extraction/v1/gliner_rescue.schema.json` — rescue wire
  contract (request identity fields documented).
- `shared/polymath_shared/clients.py` —
  `GlinerClient.infer_rescue_batch()` with label-set-fingerprint
  grouping.
- `workers/workers/rescue.py` — alignment analysis, determiner
  trimming, request dedup by deterministic identity
  (rescue-v1|kind|revision|threshold|text|ordered labels), exact-span
  acceptance, BOUNDARY_UNRESOLVED argument removal, audit record.
- `workers/workers/extract_worker.py` — rescue applied after syntax
  evidence, before build_candidates; audit artifact + conditional
  contract-hash keys (off → byte-identical).
- Tests: `tests/determinism/test_i4r_a_boundary.py`.
- `eval/i4r/` — measurement reports per sub-gate.

## Proof

- Unit tests: alignment cases (clean / partial / determiner trim /
  no-NP), exact-span acceptance, unresolved-argument removal, dedup,
  identity determinism, provider-gate interactions.
- Full suite green with `POLYMATH_RESCUE` unset (default off):
  production path byte-identical.
- Frozen-I4 measurement with `POLYMATH_RESCUE=boundary`: freeze hash
  check + ingestion + entities + facts + provenance; frozen evidence
  files snapshotted and restored byte-identically around each run;
  numbers in `eval/i4r/REPORT.md`.

## Rejected claims

- No claim that boundary rescue alone requalifies extraction: the
  combined I4R result decides promotion; I5 decides generalization.
- No deterministic span expansion: GLiNER confirms every expanded
  argument or the fact abstains (precision-first).
- The frozen I4 evaluator/matching policy was not touched.

## Open contract gaps

- I4R-B/C/D staged separately; frames live in rule pack v1.3.0 under
  I4R-D. TEST-HARNESS-STABILITY remains a separate unauthorized gate.
