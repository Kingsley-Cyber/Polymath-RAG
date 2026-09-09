---
owner: "@king"
last_reviewed: 2026-09-09
status: FORENSIC HOLD — constraints for the next session
architecture_impact: none (constraints only)
---

# BE AWARE — 2026-09-08/09 (Groq Parent-MAP forensic hold)

Each item is classified: **[INVARIANT]** cannot change · **[FROZEN]** architecture frozen by owner ·
**[CONSTRAINT]** operational rule · **[OWNER]** owner-gated decision · **[DISPUTED]** prior claim now in
doubt.

## Frozen architecture (do NOT change)

- **[FROZEN]** Parent-MAP generation is `ParentSkeleton → plaintext MAP DSL → deterministic map_compiler
  → durable parent maps → projection`. The compiler enforces identity; the model only emits tolerant
  plaintext.
- **[FROZEN]** No **JSON object mode**, no **JSON schema**, no **function/tool calling** for parent MAPs.
  This is deliberate, not an oversight.
- **[FROZEN]** Do not bypass `map_compiler`. Do not weaken **strict parent identity**.
- **[FROZEN]** Do not modify the **chunker** or **parent boundaries**. Parent identity flows from the
  chunker's ParentSkeleton; changing it invalidates existing maps.
- **[INVARIANT]** Routing-inferred artifacts (Profile Atoms, MAPs, latent fields, BRIDGE/ANCHOR, graph
  relationships) ROUTE candidates only — they are **never** factual evidence. Children prove; the
  cross-encoder judges; synthesis presents grounded evidence.

## Provider-spend + backfill rules

- **[CONSTRAINT]** Cinema parent-MAP backfill is **STOPPED**. Do not resume it.
- **[CONSTRAINT]** Do not resume merely because a Groq quota window resets.
- **[CONSTRAINT]** Do not spend provider quota to gather audit evidence. The audit is designed to run on
  observation + reconciliation of existing state; only a bounded, owner-authorized canary spends quota,
  and only after the acceptance gate passes.
- **[CONSTRAINT]** Provider quota consumption = an actual HTTP request Groq accepted/counted. A local
  `LIMITER_REFUSED` is **zero** consumption and must never be accounted as spend.

## Owner-gated decisions (never autonomous)

- **[OWNER]** QUERY_READY flip (S13/S14 cutover). Do not flip it.
- **[OWNER]** Disabling legacy producers/readers (S15/S16), stopping legacy writers (S17), physical
  cleanup / deletion (S18). All gated on a zero-reader proof + rollback window.
- **[OWNER]** Repurposing SiliconFlow (or any non-Groq provider) for parent MAPs — a contract change; the
  owner scoped SiliconFlow to graph EXTRACTION only (see register 11.182/11.183). MAPs stay Groq-pinned.

## Measured vs inferred vs disputed

- **[DISPUTED]** "A +0-parent / 0-errored_docs backfill pass proved the six Groq accounts exhausted daily
  RPD." Downgraded from proven provider fact to unverified inference. Reconcile before trusting.
- **MEASURED (trust):** cinema coverage ≈1254/11,993 (live query); map-batches-v2 improved large-doc
  yield (Hey Whipple 0→75/469); single-account pinning existed and was fixed (BACKFILL-SPREAD-V1);
  compound-mini structured-output reliability degrades above ~15–20 aliases per batch.
- **INFERRED (verify):** the six-account × daily-RPD topology (`6 × 250`? `6 × 500`?) — establish from
  provider headers, do not assume.
- **UNKNOWN (this session did not verify):** exact Groq per-account daily request quota; whether success
  responses preserve rate-limit headers to the limiter; whether `MappingOutcome.errors` can be non-zero
  while `errored_docs=0` (an incidental `mapped=N/N` + `complete=False` discrepancy was observed but not
  audited).

## Environment notes

- **[CONSTRAINT]** Use `.venv/bin/python` with `PYTHONPATH=shared`. The Mac system `python3` is 3.9 (no
  `tomllib`) and will fail the guards.
- **[CONSTRAINT]** Bootstrap order per `AGENTS.md`: this handoff → CONTINUITY-REPORT → PLAN-AUTHORITY-
  REGISTER → two newest work-logs. Chat history is not authoritative; repository is.
