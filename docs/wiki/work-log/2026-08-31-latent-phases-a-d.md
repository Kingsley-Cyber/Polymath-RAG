---
change_id: LATENT-PHASES-A-D-V1
owner: control-plane
date: 2026-08-31
status: complete
architecture_impact: new shared/polymath_shared/latent package; migration 0043; enrichment stage in the summary worker (owner-triggered); latent projection + verifier reconciliation; HYBRID latent rescue lane; §0a button endpoints; latent flag through every query surface
last_reviewed: 2026-08-31
---

# WORK LOG — LATENT-TRANSFER-LAYER-V1 Phases A–D + §0a buttons

## Contract
The frozen latent plan v1.1 as reconciled (§1.7 wire contract, §0a
owner-trigger, §0b mixed-era union), executed per the re-anchored §2.2
map. Phase 0 (chunker swap) deliberately deferred — the plan itself
scopes it separately and the compiler takes any parent.

## Changes
- **Phase A** (`shared/polymath_shared/latent/`): contract (bounds +
  integer wire refs), prompt (six outputs, one gist per numbered
  passage), gate (ENRICH_* dispositions; §1.7 subset-hard refs +
  0.8 gist-coverage floor; budget trims never reject; mechanical
  sanitize; children-only source_hash), transport-agnostic compiler
  (ceiling BEFORE any call; ENRICH_NO_RESPONSE for transport silence).
- **Phase B**: migration 0043 (parent_enrichments, one READY per
  parent, PARENT_ENRICHMENT job stage); `client.complete_one`
  (custom-system single completion through the AIMD limiter);
  `_do_enrichment` in the summary worker — pinned cross-provider group
  transport with in-group ring failover, (stage, input_hash)
  idempotency, per-doc scoping; settings knobs; stage is
  NON_BLOCKING and deliberately ABSENT from STAGE_DAG (§0a).
- **§0a buttons**: `POST /corpora/{id}/enrich` + `POST
  /documents/{doc_id}/enrich` mint/re-arm the ticket + event; re-click
  re-sweeps cheaply (only changed parents re-enrich).
- **Phase C**: `latent/projection.py` (two points per READY enrichment,
  chunk_id-free per C5); projector routes them with receipts +
  explicit STALE retirement (the F6 lesson: active receipts shield
  points from the orphan sweep); verifier ROUTING_KINDS + desired/
  receipt reconciliation per the entity-card template; enrichment
  completion re-arms project_qdrant (receipt-incremental).
- **Phase D**: `latent/rescue.py` (two filtered searches, parent
  collapse, budget + fail-open); HYBRID engine union (latent parents
  deepen through ORIGINAL children, arrival LATENT_RESCUE, reserved
  seats via the pre-built rescue_arrivals seam); `apply_latent`
  (settings default OFF, per-request override); flag through
  /retrieve, /chat, /evidence, /chat/stream, MCP, frontend body type.
- **Phase E harness**: eval/v5/latent_transfer (draft cases + P6
  runner writing LATENT-TRANSFER-P6-RESULTS.md). Owner authors ≥20
  cases and calls GO/NO-GO — not this session's call.
- CONTRACT_EXEMPT_EVENTS in worker_runtime: parent_enrichment.v1 is
  exempt from the run-era semantic-bundle pin — an additive
  owner-triggered stage MUST run over mixed-era corpora (§0b); its
  artifact identity hashes its own inputs, so era can never blur.

## Proof
- Phase A gate: 10/10 (every reject class, floor semantics, hash
  sensitivity, pre-call ceiling, deterministic transfer text).
- Phase B qualification canary on BOTH pin-group members with a REAL
  corpus parent: nvidia/lightning READY coverage 1.00, groq5/qwen3.8
  READY coverage 1.00 — the enrichment schema is model-agnostic in
  practice, not just design.
- Phase D: test_latent_rescue 6/6 (fail-open on exception/budget/junk,
  caps, section-skip); test_hybrid_latent 2/2 — latent lane admits
  ONLY original children, and latent_enabled=False is byte-identical
  to running with no latent machinery at all (§0b pin #2).
- LIVE: HYBRID latent:true over the pre-projection store → parents=[],
  degraded=None, evidence identical to latent:false — absence
  invisible, measured.
- Determinism suite at the 8-failure pre-existing baseline.
- Doc-level button pressed on Learning SQL: stage claimed and
  churning through the pinned lane; completion + projection + the
  reach acceptance recorded in the addendum below.

## Debug finds (measured, fixed in-session)
- `complete_one` leaked the limiter's CONCURRENCY SLOT (no release) —
  the stage deadlocked at 2 calls, threads parked in acquire; fixed
  with the same finally-release contract as extract_batched.
- Function-local `from …rescue import ARRIVAL_LATENT_RESCUE` shadowed
  module scope for the whole engine function (the graph.py
  `_embed_query` failure class, now measured TWICE) — imports hoisted.
- The rescue lane passed "" as the collection name (404 →
  UnexpectedResponse degraded) — the searcher expects the resolved
  collection; the API closure resolves it now.
- Run-era compat pin refused the enrichment lease on the mixed-era
  corpus — the CONTRACT_EXEMPT_EVENTS change above.

## Rejected claims
- "Add parent_enrichment to STAGE_DAG for automatic chain minting" —
  rejected: §0a makes the trigger owner-explicit; the DAG would
  enrich on every ingest.
- "Wait for Phase 0 (tier_chunker) before A–E" — rejected: the plan
  itself scopes Phase 0 separately; enrichment units are today's
  parents and re-enriching after a future swap is a button-press.

## Open contract gaps
- Enrichment transport is SEQUENTIAL per doc (one parent at a time on
  the doc's pinned lane, ~30 s/parent on lightning); parallelize
  within the limiter's conc_cap when corpus-scale spend matters.
- P6 cases are DRAFTS; owner must author ≥20 and run the harness for
  the GO/NO-GO before `latent_retrieval_enabled=true` anywhere.
- Frontend has the `latent` body field but no query-bar toggle yet
  (F13-style UI affordance — small follow-up).

## Addendum — live acceptance (same session, all measured)
- Phase B stage run (doc button, Learning SQL): 24 READY + 1 INVALID
  (gate doing its job), ticket done. Real cross-domain abstractions
  persisted ("Constraints enforce data integrity by linking tables…").
- Phase C: 24 latent_abstraction + 24 latent_transfer points projected
  into the routing collection with receipts (payload-tagged
  project_qdrant re-arm; era-exempt ONLY for latent_projection events).
- Phase D reach: HYBRID latent:true on "how do systems automatically
  move things to cheaper storage as they age" → 3 latent parents
  surfaced (abstraction channel), 9 original children admitted,
  degraded None; latent:false byte-stable.
- P6 draft run (3 seed cases): EVERY case gained 2 unique
  latent-sourced evidence items at the same total budget; attribution
  abstraction=18 / transfer=4 unique hits — both kinds live, no kill.
- Two more era-fence finds fixed: the projector hit the same run-era
  refusal (payload-tagged exemption, narrow); the first enrichment run
  deadlocked on a leaked limiter concurrency slot (finally-release).
- `latent_retrieval_enabled` remains FALSE — the owner's P6 GO/NO-GO
  (≥20 authored cases) gates any default-on.
