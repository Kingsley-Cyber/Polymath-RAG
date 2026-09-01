---
change_id: ENRICH-MICROBATCH-V1
owner: governance
date: 2026-09-01
status: complete
architecture_impact: enrichment call granularity (6-8 item-isolated parents/call); eligibility gate; pin group reshape; 12 gemini model-variant lanes; groq declared-truth limits
last_reviewed: 2026-09-01
---

# WORK LOG — ENRICH-MICROBATCH-V1 (+ fleet capacity truth)

## Contract
Owner-blessed 2026-09-01 (outside design reconciled; owner added:
"ensure all gemini keys call the available gemini models to increase
speed and actually use the full capacity"). Amends the recorded
one-parent-per-call D-row. Driven by measurement: the key-health
probe showed groq keys at 8,000 TPM (provider-declared) — ~1
extraction or ~4 enrichment calls/min — and gemini free tier is
RPM-scarce/TPM-rich, so call granularity, not compute, was the
enrichment bottleneck (979 parents ≈ 16+ min at one-per-call).

## Changes
1. MICROBATCH: MICROBATCH_SYSTEM_PROMPT (item-isolated envelope,
   verbatim parent_refs, per-item child ordinals),
   sanitize_microbatch (envelope discipline; ITEM validation IS the
   existing per-parent gate — one contract, two transports),
   compile_parents_microbatched (token-aware packing ≤8/call with
   per-parent ceiling checks; split ladder 8→4→2→1 whose floor is
   the proven single-parent compiler; partial acceptance intrinsic),
   compile_microbatched_with_hard_case (item failures walk the
   EXISTING semantic-failover → cross-family minimal escape →
   typed-terminal ladder).
2. ELIGIBILITY GATE (worker): TOC/bibliography/front-matter parents
   (region_role noise — the same signal extraction skips) never
   reach an LLM. Dedupe was already structural (input_hash).
3. PIN GROUP: groq5 REMOVED (8K TPM = pure failover churn);
   parent_enrichment = [nvidia, gemini5, gemini5b, gemini6,
   gemini6b].
4. GEMINI VARIANT LANES: Google quotas are PER MODEL per key —
   gemini{1..6}b run gemini-3.5-flash-lite on the SAME keys with
   independent quotas → 12 gemini lanes from 6 keys. Canary receipts:
   3.5-flash-lite strict-schema PASS; 2.5 family retired upstream;
   non-lite flashes FAILED strict schema (parked pending a json-mode
   canary).
5. GROQ TRUTH: limiter TPM 120000 → 8000 (provider-declared, header
   probe); registry request budget 7000 chars (single-neighborhood
   calls) — groq stays as honest trickle extraction capacity.

## Proof
- test_enrich_microbatch.py — 9 green: envelope ref discipline
  (missing → NO_RESPONSE, invented ignored, duplicate first-wins),
  unparseable envelope fails every ref, item validation = the
  single-parent gate (coverage floor fires through the envelope),
  ONE call enriches six parents, partial acceptance (bad P2 keeps
  P0/P1/P3 READY), split ladder reaches the single-parent floor,
  per-parent ceiling isolation, hard-case integration recovers item
  failures on the minimal contract.
- test_latent_contract_gate.py still green (16) — the single-parent
  contract is untouched.
- Live measurement = the resumed 979-parent run (baseline: the
  stopped one-per-call run managed ~5-8 calls/min and persisted 0
  rows in ~25 min).

## Rejected claims
- "Enrichment must block query_ready" — was never true here; the
  paste's #7 is the live early-kick architecture (ecom promoted with
  enrichment still queued).
- "Buy more API keys first" — granularity first (this change), then
  variant lanes multiply existing keys; new spend is the LAST lever.
- COMPACT-CONTRACT default — deferred behind a P6 A/B (gists are the
  fidelity gate, not just output tokens); owner gate.
- Provider Batch APIs (BULK_CHEAP tier) — future plan row for
  500-book backfills; new async transport, not this change.

## Open contract gaps
- input_hash keeps the parent-sharded lane as its model_contract
  identity while EXECUTION runs per-batch (first-parent lane) —
  idempotency key vs provenance divergence, recorded; provider
  column carries actual provenance.
- Non-lite gemini flashes (3-flash-preview, 3.5-flash) await a
  json-mode canary before joining as third lanes.
- The stopped equivalence bench should re-run after resume for the
  tiering table.
