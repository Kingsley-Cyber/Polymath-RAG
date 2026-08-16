# I4R — staged repair regression (NOT RUN; authorization suspended)

Status: **NO MEASUREMENT PERFORMED.** The I4R umbrella gate was
authorized 2026-08-16 with staged sub-gates (A boundary reconciliation,
B missing-argument rescue, C type reconciliation, D frame arbitration;
one isolated commit + frozen-I4 measurement after each; combined
configuration as the final result). I4R-A was implemented and unit
tested, then the TEMPORALLY DURABLE EXTRACTION ARCHITECTURE directive
(2026-08-16) halted all acceptance measurement pending the architecture
alignment (now complete) and a fresh explicit authorization.

Bars that any future I4R run must restate (frozen I4 development
regression): **P >= 0.95, R >= 0.70, out-of-envelope abstention 100%,
must-not-assert 100%**, with FROZEN_STATE/capability-matrix/gold hashes
verified before and after, and eval/i4/evidence snapshot+restore
around every run. I4 remains a development set; I5 is the sealed
generalization test.

## Implemented (flag-gated OFF, unmeasured)

- I4R-A boundary reconciliation: `workers/workers/rescue.py`
  (alignment over syntax-evidence noun chunks, determiner-trimmed;
  exact-NP targeted re-query via the GLiNER sidecar's additive
  POST /rescue; exact-full-span-only acceptance; refused ->
  BOUNDARY_UNRESOLVED = durable mention, no argument binding).
  Controlled by `POLYMATH_RESCUE` (default off) and requires
  `POLYMATH_SYNTAX_PROVIDER=spacy`. All query labels resolve through
  semantic-query-policy-v1.
- Batched client `GlinerClient.infer_rescue_batch()`; contract
  `contracts/extraction/v1/gliner_rescue.schema.json`.

## Drafted measurement procedure (not executed)

1. Freeze check: `shasum -a 256` of FROZEN_STATE components, before
   and after.
2. Snapshot `eval/i4/evidence/{evidence.json,verify_i4.log}`; restore
   byte-identically after; keep I4R copies under eval/i4r/.
3. Restart the extract worker with POLYMATH_SYNTAX_PROVIDER=spacy +
   POLYMATH_RESCUE=<stage set>; verify sidecars /ready.
4. `.venv/bin/python eval/i4/verify_i4.py --phase freeze --phase
   ingestion --phase control_chain --phase entities --phase facts
   --phase provenance` per sub-gate; full phase list for the combined
   run.
5. Restore the plain worker env afterwards.

Pre-measurement probe evidence (label-vocabulary sensitivity on bare
NP queries) is recorded in
`docs/wiki/experiments/0005-gliner-label-vocab-probe.md`.
