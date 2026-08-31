---
change_id: MASTER-BUILD-SEQUENCE
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (ordering authority aggregating RETRIEVAL-AUDIT-PRD + LATENT-TRANSFER-LAYER-V1-PLAN + UI-V3-PRESENTATION-PRD)
last_reviewed: 2026-08-30
---

# MASTER BUILD SEQUENCE — audit fixes × latent layer × UI overhaul, de-conflicted

Three plans now target overlapping code. This document is the ONE
ordering authority; each plan keeps its own spec. Aggregated to minimize
rework before the owner implements the latent layer.

## Collisions found (and what was done about them, 2026-08-30)

| # | Collision | Resolution |
|---|---|---|
| C1 | LATENT plan's line anchors were verified on `main@463f52d`; session 4 changed the exact functions it plans to modify (`client.py _infer_batch_call` gained `use_lean`; `tickets.py STAGE_DAG` gained `compile_objects`; `project_qdrant_worker.py:295-303` gained entity cards + sparse; `pass1.py:285` moved). | **Its own gate already requires a re-anchor mapping pass before build** — do that pass against current HEAD, not 463f52d. Annotated in the plan. |
| C2 | LATENT plan claims migration `0041_parent_enrichments.sql` — 0041 and 0042 are applied. | Renumbered to **0043** in the plan. |
| C3 | Three plans converge on `pass1._truncate_reserving_rescue` (latent Phase D) and future entity-card fusion (audit F2). | **DONE ahead: ADDITIVE-SEED-SEAM-V1** — `rescue_arrivals` param landed with byte-identical defaults; latent Phase D and F2 now plug into one seam instead of forking it. |
| C4 | LATENT Phase B needs `system_prompt` param + `complete_batched` on the extraction client — the same function session 4 re-signatured twice. | **DONE ahead: BATCH-API-STABILIZATION-V1** — both landed and live-smoked (per-item system prompts, limiter + AIMD budget + OOM-halving reused, no parse). Phase B's client diff is now zero. |
| C5 | LATENT D5 projects `latent_*` points with `chunk_id=None` into the shared routing collection — the pre-CHUNK-SWEEP-SCOPE-V1 verifier would have DELETED every one as an orphan (measured: it deleted 94 entity cards). | Already fixed (`0ea4cf8`); recorded here as a hard dependency: latent points REQUIRE that fix. Phase C must also extend `ROUTING_KINDS` + desired/receipt reconciliation for the two latent kinds, following the `routing_entity` template in `verify_worker.py`. |
| C6 | LATENT D16 declares the local model setup LOCKED per the 2026-08-29 config report — the batched server has since gained PREFIX-KV-CACHE-V1, per-seq budgets, memory caps; and LEAN extraction is gated OFF for coverage. | Lock text updated in spirit: generation params unchanged (still locked); the SERVER transport is faster, which enrichment inherits for free. Enrichment output (~700 tokens, small JSON) is NOT the lean index form — the LEAN failure class does not apply, but its gate (`sanitize_enrichment`) must be tested against real parents before trusting, per the survivorship lesson. |
| C7 | Audit F7/F10 (breadth/depth caps) and LATENT D8 (latent caps) both extend retrieval plans — two separate plan-version bumps would mean two golden-contract re-qualifications. | Sequenced as ONE plan change: collect owner breadth/depth numbers, add both cap families together, re-qualify once. |
| C8 | UI PRD adds fields to `evidence_assembly.py` + `retrieve.py` responses; audit F1/F3/F4 + F5 touch the same response surface. | Sequenced as one orchestrator pass so the response schema churns once. UI PRD's claim "no other files change" holds only if it rides with, not after, the audit pass. |
| C9 | LATENT Phase 0 = canonical `tier_chunker` swap (re-ingest; every chunk id changes). Tuning breadth/depth caps (F7) on interim chunks would be re-done. | Chunker swap ordered BEFORE cap tuning and before corpus-wide enrichment. |

## The sequence

```
0  DONE 2026-08-30: ADDITIVE-SEED-SEAM-V1 + BATCH-API-STABILIZATION-V1
   (pre-refactors; latent Phases B/D diffs shrink to near-spec-only)

1  ORCHESTRATOR PASS (no fence, one response-schema churn):
   F1 graph seeds via entity cards → F3 ask matching via routing points
   → F4 sparse breadth probes → F5 one summary authority
   → UI-PRD backend fields (evidence titles / heading_path / human_locator)

2  OPS: F9 serve-profile supervisor (reranker + orchestrator supervised)
   + F13 surface the corpus enable step in the UI

3  FENCED WINDOW (one fleet restart):
   F2 entity-card RRF/rescue lane via the new seam
   + F6 drop parent_summary points (projector + verifier want-set together)
   + LATENT re-anchor mapping pass (C1) — read-only, rides the same window

4  FRONTEND: UI-PRD §4 (sources panel, document→section tree)

5  OWNER INPUT GATE: breadth/depth targets → F7 + F10 + LATENT D8 caps
   in ONE plan-version change, one golden re-qualification (C7)

6  LATENT PHASE 0: tier_chunker swap + re-ingest (C9)

7  LATENT PHASES A→E per its plan (anchors refreshed in step 3;
   migration number 0043; Phase C extends ROUTING_KINDS per C5)

8  F8 multi-corpus lane (fuses per-corpus pass1; benefits from 3+7)
   → F14 closes as latent lands · F11/F12 hygiene ride any window
```

## Standing rules while executing

- The latent plan's own build gate holds: owner validates base e2e, then
  the mapping pass, then phases. Steps 1–5 here ARE base hardening and
  precede that validation.
- Single-writer discipline per step: two sessions in this repo commit
  narrowly (the `add -A` sweep and the resurrected scaffold declaration
  both happened today).
- Every step lands with its receipt: live probe numbers in the work-log,
  acceptance criteria from RETRIEVAL-AUDIT-PRD.
