---
change_id: ENRICH-HARD-CASE-V1
owner: governance
date: 2026-09-01
status: complete
architecture_impact: enrichment failure state machine (bounded cross-family minimal escape; typed terminal class); persist upgrade-path fixes
last_reviewed: 2026-09-01
---

# WORK LOG — ENRICH-HARD-CASE-V1 (bounded escape for hard sections)

## Contract
Owner design 2026-09-01 (same outside-design session as EVIDENCE-
UTILITY-V1): when both group lanes reject a section, do NOT hammer
the same lanes forever — one bounded escape (different model family,
minimal contract), else a typed permanent absence. Reconciliation
sharpened the diagnosis with a live receipt: the pin group is FOUR
lanes but ring-adjacency put the 5 gemini5 failures onto gemini6 —
the SAME family; "both lanes rejected" really meant "one family
rejected twice". The escape at ring offset +2 is guaranteed
cross-family in the current group.

## Changes
- `latent/prompt.py`: MINIMAL_SYSTEM_PROMPT / MINIMAL_PROMPT_VERSION —
  the escape asks only for what the latent projection fundamentally
  mints: {abstraction, transfer}.
- `latent/gate.py`: `sanitize_minimal_enrichment` (aggressive: prose
  floors 40/20 chars, hard caps, transfer mapped into mechanisms so
  transfer_text() renders it; summary/children stay empty);
  `ENRICH_HARD_CASE` added to SEMANTIC_FAILOVER_INELIGIBLE — terminal
  by row-truth, sweeps stop retrying.
- `latent/compiler.py`: CompiledParent gains `contract`/
  `prompt_version` provenance; `compile_minimal_parents`;
  `compile_with_hard_case_escape` (A → B semantic failover unchanged →
  ONE minimal escape on a third lane → ENRICH_HARD_CASE carrying all
  three dispositions; over-ceiling never escapes; every count
  returned, per the silent-fallback accounting law).
- `summary_worker_impl.py`: `_complete_escape` = the parent's ring+2
  lane, refused if it collides with lanes A/B; counters logged
  (ENRICHMENT_HARD_CASE_RECOVERED / _TERMINAL).
- `latent/runtime.py` — TWO LIVE BUGS the provenance check caught:
  (1) the READY upsert's DO UPDATE omitted compiler_contract/
  prompt_version, so an escape recovery over a prior INVALID row
  masqueraded as the FULL contract (all 67 live rows read v1);
  (2) the INVALID path was ON CONFLICT DO NOTHING, so marking an
  existing INVALID row terminal silently no-oped — the row stayed
  retryable forever, the exact disease this change cures. Both fixed;
  the 7 mislabeled live rows relabeled by their minimal signature
  (children=[] AND summary='') with a receipt.

## Proof
- Gate/compiler pins (test_latent_contract_gate.py, +4): minimal gate
  accept/reject/parse classes; escape recovery carries
  MINIMAL_CONTRACT (never masquerades); triple-fail → terminal
  ENRICH_HARD_CASE in the INELIGIBLE set; source conditions never
  reach the escape.
- Persist pins (tests/integration/test_enrichment_persist.py, 3):
  minimal recovery keeps minimal provenance over a prior INVALID row;
  terminal disposition STICKS on an existing INVALID row; INVALID
  never downgrades READY.
- LIVE: worker bounced, both runs re-minted — ALL SEVEN hard cases
  recovered on the minimal escape (cross-family lane), final state
  67/67 READY (60 full + 7 minimal), 0 INVALID, 0 open tickets.
  Latent coverage is now COMPLETE for the corpus.

## Rejected claims
- "READY_DEGRADED status enum" — same semantics delivered via
  provenance (compiler_contract='parent-enrichment-minimal-v1')
  instead: a new status value would touch the CHECK constraint, the
  one-READY partial index, and six status='READY' filters for zero
  additional information.
- "Rotate the ring offset on retry" (my own earlier suggestion) —
  superseded by the design's correct observation that reordering the
  same lanes is not materially better; the escape changes FAMILY and
  CONTRACT, not order.

## Open contract gaps
- The minimal escape's quality is unmeasured (7 sections now carry
  short abstractions/transfers); a future P6-style pass can attribute
  their nominations separately via the compiler_contract column.
- If the pin group ever shrinks below 3 distinct lanes, the escape
  refuses (collision check) and hard cases go terminal after two
  lanes — correct, but worth knowing.
