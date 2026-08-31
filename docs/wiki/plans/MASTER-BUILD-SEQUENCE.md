---
change_id: MASTER-BUILD-SEQUENCE
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (ordering authority aggregating RETRIEVAL-AUDIT-PRD + LATENT-TRANSFER-LAYER-V1-PLAN + UI-V3-PRESENTATION-PRD)
last_reviewed: 2026-08-30
---

# MASTER BUILD SEQUENCE — the consolidated report (audit findings × latent layer × UI overhaul)

**This is the one full read**: every audit finding with location and
dependency, the future build's decisions and phases, the UI overhaul,
the collisions between them, and the de-conflicted order. Deep specs
stay in their own files (RETRIEVAL-AUDIT-PRD.md · LATENT-TRANSFER-
LAYER-V1-PLAN.md · UI-V3-PRESENTATION-PRD.md); this document is
sufficient to plan and start any step without opening them.

## Part I — Audit findings (premise: extraction quality is high; all live-probed)

| # | Sev | Finding | Location | Dependency |
|---|---|---|---|---|
| F1 | P0 | Graph seeding is token soup — "what uses Amazon S3" seeded unigrams (`s3` dropped by len>3, junk burned the 8-seed cap) → 0 facts from 106; the graph never consults the entity registry | graph.py:56, retrieve.py:347 | entity cards + entities table (exist) |
| F2 | P0 | Entity cards advisory-only — absent from pass1 RRF, HYBRID, GRAPH seeding, /ask | fast.py card block; pass1.py fusion | FENCED; now plugs into ADDITIVE-SEED-SEAM-V1 |
| F3 | P0 | /ask object matching = substring fraction — foreign-key question returned an AWS DevOps concept; FACT route shares the scorer | ask.py:67/:98/:136 | routing_concept/procedure points already in Qdrant |
| F4 | P1 | Breadth routing dense-only — no sparse probe on doc/section summary lanes; exact-name breadth = embedding luck | fast.py:55 FastSearcher | bm25 already on summary points; shared tokenizer |
| F5 | P1 | Two summary authorities — legacy parent lane scores chunks.summary, FAST routes on compiled cards (verified different texts) | retrieve.py:252 | retrieval_summaries = declared authority (4.4.8) |
| F6 | P1 | 65 parent_summary points dead weight in the collection | project_qdrant_worker._write_points | verifier/census want-set changes in SAME commit |
| F7 | P1 | Depth = regex heuristic; breadth caps are global constants (docs 5 / sections 2 / children 3 / final 10-12) | pass1.py:43-68, query_shape.py:120 | OWNER breadth/depth numbers |
| F8 | P1 | FAST/HYBRID/GRAPH single-corpus; cross-corpus falls to legacy lane | retrieve.py:137-148 | after F2 (fuse per-corpus pass1) |
| F9 | P1 | Serve processes unsupervised (reranker/orchestrator hand-started; dead-reranker 113s class) | process_supervisor SLOTS; runtime_budget profiles | none — run POLYMATH_PROFILE=retrieval supervisor |
| F10 | P1 | Synthesis evidence budget bounds depth (1,600 chars/item, 10 final children, 30 carried) | ui.py:993; pass1 finals | rides F7's numbers |
| F11 | P2 | Sparse-tokenizer contract untested (future lanes could fork it) | test_sparse_bm25.py extension | none |
| F12 | P2 | Junk object NAMES amplified by F3 ("AWS Cloud DevOps Engineer Path DevOps") | knowledge_objects/concept.py naming | TERM-SURFACE-GATE rule class |
| F13 | P2 | Upload defaults hide corpora from retrieval (probe/query_enabled=false) | ui.py upload; query_scope.py:84 | UI toggle or upload param |
| F14 | P2 | Latent transfer layer not built (roadmap — Part II) | register §10.2/§11.6 | F2's seam (done) |

Acceptance criteria live in RETRIEVAL-AUDIT-PRD.md §Acceptance; the live
artifact page mirrors this table.

## Part II — The future build (LATENT-TRANSFER-LAYER-V1, frozen v1.1) in brief

Goal: latent connections (Laban↔cinematography-class reach) as an
ADDITIVE rescue lane — enrichment routes, children prove.

- **Ingestion**: one compact LLM call per parent (children in →
  `{summary, per-child gists, abstraction, ≤2 mechanisms, ≤2 affordances,
  ≤3 questions}` out), gated by its own sanitize (`ENRICH_*` reject
  classes), persisted to `parent_enrichments` (migration **0043**) —
  never `retrieval_summaries`. Non-blocking summary-family stage
  `parent_enrichment.v1`.
- **Projection**: exactly two new kinds per parent —
  `latent_abstraction`, `latent_transfer` — into the EXISTING routing
  collection, payload-filtered, receipts + STALE cleanup. Points carry
  `chunk_id=None` → **depends on CHUNK-SWEEP-SCOPE-V1** (without it the
  verifier deletes them; measured on entity cards) and Phase C must
  extend ROUTING_KINDS + reconciliation per the routing_entity template.
- **Query time**: HYBRID-only rescue (GRAPH inherits): two filtered
  searches (top_k 8 each, same qvec) → dedupe → ≤3 latent parent_ids →
  those parents' ORIGINAL children → union with baseline → rerank.
  Latent text is NEVER evidence. FAST byte-identical always; everything
  byte-identical when `POLYMATH_WORKER_LATENT_RETRIEVAL_ENABLED=false`.
  Fail-open, 250 ms budget.
- **Phases**: A contract/prompt/gate/compiler (pure) → B ingestion stage
  → C projection → D rescue lane wiring → E P6 recall suite with
  per-channel keep/kill.
- **§0b MIXED-ERA UNION CONTRACT (owner 2026-08-30)**: retrieval reads
  what exists, per document, per layer — enrichment additive
  per-parent, absence INVISIBLE at query time; mixed-era is the steady
  state (button-triggered scopes), and Phase E must pin base-only ==
  no-enrichment-world byte-identically. Full text in the latent plan §0b. Phase 0 (before corpus-wide enrichment):
  canonical `tier_chunker` swap + re-ingest.
- **Pre-built tonight (its two riskiest diffs)**:
  ADDITIVE-SEED-SEAM-V1 (`pass1._truncate_reserving_rescue(rescue_arrivals=…)`)
  and BATCH-API-STABILIZATION-V1 (`client.complete_batched` + per-call
  `system_prompt`, live-smoked). Its line anchors are STALE vs
  `463f52d` — the plan's own mapping-pass gate must re-anchor at HEAD.

## Part III — UI overhaul (UI-V3-PRESENTATION-PRD) in brief

Presentation only + two additive response fields: evidence items gain
`title / heading_path / human_locator` (joins from chunks.heading_path,
documents.source_name, card heads; NULL-safe), answers render a v3.3
Sources panel (human names, verbatim quotes, provenance behind an
expander), documents render as document → section tree from the parent
cards. No retrieval contract change — which holds only if its backend
fields ride the same orchestrator pass as F1/F3/F4/F5 (collision C8).

## Part IV — Collisions and resolutions

Three plans target overlapping code; this section is why the order below
exists.

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
