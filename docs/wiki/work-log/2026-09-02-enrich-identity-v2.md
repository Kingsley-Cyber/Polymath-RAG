---
change_id: ENRICH-IDENTITY-V2 + ENRICH-OWN-DOC-FIRST
owner: governance
date: 2026-09-02
status: complete (live receipt below; tail receipt appended when the run settles)
architecture_impact: enrichment identity (latent/runtime.py input_hash_for + enrichment_contract_id); summary worker sweep order; one-time DB re-key (scripts/migrate_enrichment_identity.py)
last_reviewed: 2026-09-02
---

# WORK LOG — the enrichment identity contained the lane; every pin change re-enriched the corpus

## Contract
Found by the owner's MCP test (upload → status → ask): the new book was
`query_ready` in 390 s but its enrichment sat at 0/54 for 20+ minutes
while the summaries worker wrote 218 enrichment rows for four OLD books
that were already 100 % enriched. Owner law: anything stuck > 3 min is a
defect to trace to root cause. Traced, fixed, re-keyed, verified.

## Root cause (three interacting facts)
1. `input_hash_for(source_hash, f"{lane.name}:{lane.model}")` — the LANE
   was part of the enrichment identity. ENRICH-PARENT-SHARD picks the lane
   per parent over the pin group; adding openrouter1/2 (05–07 h) and
   openrouter3/5 (11 h) re-sharded parents, minted new identities, and
   `persist_compiled_parent` found no READY row → re-enrich. Measured:
   1,309 enrichment rows on 2026-09-02 for a 1,374-parent corpus; 188
   parents re-enriched with an identical source_hash.
2. One run's enrichment ticket sweeps EVERY document of the corpus
   (`_run_docs`), in `created_at` order — the fresh upload came last.
3. The sweep's outer ticket transaction stayed open 23 minutes holding
   row locks on parent_enrichments (the first re-key attempt blocked on
   them) — recorded as an open gap, not changed here.

## Changes
1. `polymath_shared/latent/runtime.py`: `enrichment_contract_id(bounds)` =
   `"parent-enrichment-v1|tokens=<max_tokens>"`; `input_hash_for` takes
   the contract id. Identity = source content + prompt hash + contract +
   output bounds. Provider/model remain provenance columns.
2. `summary_worker_impl._do_enrichment`: hashes with the contract id, not
   the lane; `_run_docs` orders the run's OWN document first
   (ENRICH-OWN-DOC-FIRST), then the rest of the corpus by created_at.
3. `scripts/migrate_enrichment_identity.py` (registry row): re-keys every
   parent_enrichments row to the lane-free hash — batched UPDATE, `SKIP
   LOCKED`, `lock_timeout` 5 s, idempotent, keeps enrichment_id, never
   deletes; formula pinned equal to runtime's by test.

## Proof
- tests/determinism/test_enrichment_identity.py 6 green: same source +
  same contract → same hash regardless of lane; different bounds/source →
  different; worker source no longer formats the lane into the hash;
  migration formula == runtime formula; `_run_docs` puts the run's own
  document first (real DB, rolled back); re-key is idempotent and keeps
  enrichment_id (real DB, rolled back). Summary-job idempotency and
  microbatch tests still green (20 total).
- RE-KEY EXECUTED: 2,506 rows — first pass 2,386 re-keyed in 0.4 s with
  88 rows locked by the running sweep; after a graceful restart of the
  summaries worker (leases handed back via the supervisor helper, no
  attempt consumed) the second pass re-keyed the remaining 120; 0 locked.
- LIVE RECEIPT (11:56:18Z restart onto the new code): the worker claimed
  the new book's ticket FIRST — StoryBrand enrichment 14 → 25 READY in
  2.5 min while "new rows for old books in the last 3 min" decayed 61 → 0:
  the corpus-wide re-enrichment STOPPED the moment identities were
  lane-free (old parents resolve as EXISTING).
- Tail receipt (54/54 + summary tickets): appended below when settled.

## Rejected claims
- Keeping the lane in the identity "so a better model can re-enrich" — a
  re-enrichment policy is a contract/bounds change (which IS in the
  identity), not a side effect of load balancing.
- Narrowing the sweep to the run's own document — the corpus sweep is the
  designed backstop for absence-invisible enrichment; with a stable
  identity it costs a SELECT per parent, so ordering fixes the latency.

## Open contract gaps
- ENRICH-TXN-SCOPE: the outer enrichment ticket transaction holds row
  locks for the whole sweep (23 min measured); per-batch persists commit
  in their own transactions, the outer one should not touch
  parent_enrichments rows at all.
- Lease/re-mint interplay: the ticket flipped to `ready` (attempt 0, no
  note) mid-sweep and the rescue clause re-opened its event while the
  worker was still working it — a second worker could double-process.
  Needs a trace on the next occurrence (stall tracer has the timeline).
