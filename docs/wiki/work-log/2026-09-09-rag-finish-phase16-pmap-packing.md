---
title: "WORK LOG — RAG-finish Phase 16: pMAP packing/capacity sanity (provider-free)"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (offline capacity sanity; no runtime behavior change, no provider spend)
last_reviewed: 2026-09-09
status: complete
register: 11.196 (pending)
package: tests/determinism/test_map_batches.py, tests/determinism/test_doc_parent_map_worker.py
architecture_impact: "No architecture change. Provider-free 60-parent planning + durable persistence tests over the lane-qualified batch cap built in Phase 7, plus inspection of the live canary pMAP receipts. Confirms the architectural target of ~60 maps/request is honored where a lane qualifies, without forcing compound-mini beyond its measured 15. No live 60-benchmark (envelope known). No provider spend."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 16** + register **11.196** (pending).

## Contract

After the micro-canary gate passes, sanity-check pMAP packing: (1) inspect measured canary receipts,
(2) verify the selected lane's qualified batch size is honored, (3) run provider-free synthetic
planning/persistence tests for a 60-parent manifest, (4) do NOT spend provider quota proving 60 live when
compound-mini is already known to require 15.

## Changes / evidence

- **(1) Canary receipts (live, read-only):** the 3 passing canaries each recorded `eligible=5 mapped=5
  batches=1/done1/partial0 cap=15 refusals=0 http_dispatches=1 compiler_complete=1 projection_pts=5` —
  **5 maps / 1 request**, the cap-15 lane honored (5 ≤ 15), zero refusals/partials.
- **(2)+(3) Provider-free 60-parent planning** (`test_map_batches::test_60_parent_lane_qualified_packing_
  honors_target_60`): effective capacity cap15→15, cap40→40, cap60→60, cap100→60 (a lane claiming >60 is
  capped at the token target). A 60-parent manifest packs as cap15→[15,15,15,15], cap40→[40,20],
  **cap60→[60] (the architectural target: 60 maps in ONE request)**; every split preserves all 60 aliases
  with no loss/dup; efficiency (fewer requests) strictly improves as a lane qualifies higher.
- **(3) Provider-free 60-parent persistence** (`test_doc_parent_map_worker::
  test_60_parent_multibatch_persistence_and_idempotent_restart`, DB-gated): 60 parents at cap 15 → 4
  batches, all 60 persisted active; a second run re-infers NOTHING (idempotent) and the active set is
  unchanged.

## Proof

- `pytest tests/determinism/test_map_batches.py` → **16/16**; `tests/determinism/test_doc_parent_map_worker.py`
  → **10/10** (incl. the new 60-parent case). No provider call.
- `bundle_integrity` READY; `repo_guard` / `wiki_worm` ok.

## Rejected claims

- **NO live 60-parent benchmark run** (plan Phase 16 action 4 + do-not-do list): compound-mini's reliable
  envelope is already measured at 15 (11.178); the lane-qualified cap makes 40/60 a config flip, so no
  provider spend was needed. The 60-in-one-request path is proven with synthetic manifests + fake inference.
- **NOT claiming compound-mini maps 60 live** — its qualified cap stays 15; the target-60 packing applies to
  a lane that ACTUALLY qualifies at 60 (none configured today).

## Open contract gaps

- A live 40/60 qualification for a NEW lane/model remains the only path to raise a lane's `map_batch_cap`
  above 15 — owner/measurement-gated, and only if such a lane is added.
