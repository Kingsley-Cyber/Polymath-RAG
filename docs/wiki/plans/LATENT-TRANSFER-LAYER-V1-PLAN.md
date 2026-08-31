---
change_id: LATENT-TRANSFER-LAYER-V1-PLAN
owner: governance
date: 2026-08-30
status: proposed (v1.1 — owner Part 3 target frozen; base validation pending)
architecture_impact: additive — optional lean LLM parent compilation at ingestion + optional latent RESCUE lane inside HYBRID (GRAPH inherits); FAST byte-identical always; everything byte-identical when disabled
last_reviewed: 2026-08-30
---

# LATENT-TRANSFER-LAYER-V1 — implementation plan v1.1 (files, dependencies, execution)

> Inputs (each ingested in its own pass, recorded in
> `LATENT-TRANSFER-LAYER-V1-DESIGN-NOTES.md`): Part 1 `Adapter.txt`,
> Part 2 `Adapter 2.md`, **Part 3 = owner message 2026-08-30, which is the
> frozen design target** and supersedes Parts 1–2 where they differ. Code
> facts: `docs/wiki/architecture/QUERY-TIME-MAP-2026-08-30.md`; every
> path:line below was read on `main@463f52d`.
>
> **Gate before any implementation (owner rule):** (1) owner validates the
> current base e2e — UI, MCP, query time, ingestion, extraction — and it
> works as intended; (2) then a code-base MAPPING pass produces per-file
> notes with citations of exactly where/what changes (this plan is the
> skeleton for that mapping, not a substitute); (3) then build phases
> A→E. The base is NOT yet validated.
>
> **ANCHOR STALENESS (2026-08-30, session 4):** every path:line below was
> read on `main@463f52d`; session 4 moved several of them (client.py
> signatures, tickets.py STAGE_DAG gained `compile_objects`,
> project_qdrant_worker gained entity cards + sparse, pass1 truncation).
> The mapping pass required by the gate above must re-anchor against
> CURRENT HEAD. Two Phase B/D items are ALREADY BUILT ahead of this plan
> (see MASTER-BUILD-SEQUENCE.md C3/C4): `pass1._truncate_reserving_rescue`
> now takes `rescue_arrivals` (ADDITIVE-SEED-SEAM-V1), and
> `llm_extraction/client.py` has the `system_prompt` override +
> `complete_batched` (BATCH-API-STABILIZATION-V1, live-smoked). Hard new
> dependency: latent points carry `chunk_id=None` and would have been
> DELETED by the pre-CHUNK-SWEEP-SCOPE-V1 verifier (measured on entity
> cards) — that fix (`0ea4cf8`) is REQUIRED, and Phase C must extend
> ROUTING_KINDS + reconciliation for both latent kinds per the
> `routing_entity` template.

## 0a. Owner trigger directive (2026-08-30, supersedes automatic-stage sequencing where they differ)

Enrichment is OWNER-TRIGGERED, not automatic at ingest: a button at the
CORPUS level and a button at the DOCUMENT level each mint the
`parent_enrichment.v1` work for their scope (corpus button = every
document; document button = that document only). Query-time latent
rescue then extends retrieval when the request's `latent` flag (D10) is
on. Implementation shape: the buttons call an orchestrator endpoint that
enqueues the non-blocking stage tickets for the scope — the stage,
gate, storage and projection are unchanged from this plan; only the
TRIGGER moves from chain-advancement to explicit owner action.

## 0b. Owner contract directive (2026-08-30): MIXED-ERA UNION SEMANTICS

**Retrieval reads what exists, per document, per layer.** Enrichment is
additive per-parent; ABSENCE IS INVISIBLE at query time. If a document's
enriched layer exists, it is included in retrieval; if not, the base
layers retrieve alone — no discrimination, no special-casing, no
penalty in either direction. An enriched document simply has one more
way to be FOUND; every lane still grounds to the same verbatim
children.

This is the union semantics Adapter 2 already specifies
(`baseline ∪ latent`), promoted to a NAMED CONTRACT because the live
corpus already demonstrates the mixed-era half: AWS for Solutions
Architects (60 facts / 175 LLM-era raw rows) and Learning SQL (46 / 79)
sit in one index, answer the same queries through identical
FAST/HYBRID/GRAPH lanes, and neither is advantaged by extraction era.

**What Phase E MUST pin (test contract, non-negotiable):** same query,
mixed corpus — one enriched document, one base-only document —
1. both retrievable through every lane, neither advantaged by STYLE
   (era/layer-presence), only by content;
2. the base-only document's results are BYTE-IDENTICAL to a corpus
   where enrichment does not exist at all (absence truly invisible —
   no empty-lane penalty, no liveness noise, no rank shift);
3. the enriched document's latent hits ground to its ORIGINAL children
   (latent text is never evidence);
4. deleting a document's enrichments returns it to base behavior
   exactly (additive means removable).

Combined with §0a: the corpus is EXPECTED to be permanently mixed-era —
buttons enrich scopes incrementally, so mixed is the steady state, not
a migration window. Design and test for it as the normal case.

## 0. Frozen design target (Part 3)

```
                         QUERY ── ONE EMBEDDING (qvec)
          ┌────────────────┼────────────────┐
        FAST            HYBRID            GRAPH
     unchanged      FAST + lexical      HYBRID (incl. latent)
                    + LATENT RESCUE     + canonical graph hop1
                    ┌──────┴──────┐
              latent_abstraction  latent_transfer   (2 filtered searches, top_k 8 each)
                    └──────┬──────┘
                 dedupe → ≤ 3 latent parent_ids
                           │
                 ORIGINAL CHILDREN of those parents (≤ 3 each)
                           │
                     UNION with baseline candidates → RERANK → EXACT EVIDENCE
INGESTION: 4 children → one compact LLM call → {summary, children[].gist, abstraction,
           ≤2 mechanisms, ≤2 affordances, ≤3 questions} → validate → Postgres
           → 2 vectors/parent (abstraction, transfer) → Qdrant routing collection
```

| # | Decision | Source |
|---|---|---|
| D1 | Deterministic parent summary / `retrieval_summaries` / chunker UNCHANGED. Enrichment = separate `PARENT_ENRICHMENT` artifact, one LLM call per parent. | Pt1, Pt3 §5 |
| D2 | Model output is LEAN: `summary, children[{id,gist}], abstraction, mechanisms[≤2], affordances[≤2], questions[≤3]`. No extract{}, no coverage lists, no ids/hashes — the worker attaches all metadata deterministically. | Pt3 §3, §6, §7 |
| D3 | Model input is STRIPPED: `PARENT_ID` + the parent's children (`CHILD <ordinal> | <child_id>` + text). No old parent summary, no facts/entities/profile/corpus map/provenance. Real model-token input ceiling enforced by the worker. | Pt3 §4, §5, §8 |
| D4 | Storage: `parent_enrichments` (typed authority) + `summary_artifacts.stage='PARENT_ENRICHMENT'` envelope. Never `retrieval_summaries`. | Pt1 |
| D5 | Projection: exactly TWO kinds per parent — `latent_abstraction`, `latent_transfer` (mechanisms + affordances rendered as one text) — in the EXISTING routing collection, payload-filtered. `gist`s and `questions` stay in Postgres, not vectorized, until P6 proves a third kind adds unique recall. | Pt3 §9–10 |
| D6 | **FAST unchanged. HYBRID is the consumer. GRAPH inherits via HYBRID.** Latent is RESCUE (union of parent ids), never extra RRF votes. | Pt3 §1–2 |
| D7 | **Hard boundary: latent produces parent_ids only** → original children of those parents → the existing reranker adjudicates. Latent text is never evidence. `LLM mechanism → Neo4j` never happens. | Pt1/Pt2/Pt3 |
| D8 | Caps: `abstraction_top_k=8`, `transfer_top_k=8`, dedupe by parent, `max_latent_parents=3` (qualification 2), `≤ max_children_per_section` children each, reserved seats so dense corpora cannot evict them. | Pt3 §12 |
| D9 | Fail-open + budget (250 ms): timeout/failure/missing enrichment → zero latent parents; never 5xx from the lane; degradation visible only in telemetry/meta. | Pt2 |
| D10 | Flags: `POLYMATH_WORKER_LATENT_RETRIEVAL_ENABLED=false` default + request `latent` override (HYBRID/GRAPH only; FAST ignores). Modes, `plan_version`s, `DEFAULT_MODE=LEGACY` frozen. | Pt2, G1/G2 golden |
| D11 | Enrichment is a NON-BLOCKING summary-family stage; never a readiness dependency. Query time is deterministic (no LLM). | Pt1, Pt2 |
| D12 | Its own P6 LATENT_TRANSFER_RECALL suite with per-channel attribution; channels/kinds that add nothing are removed. | Pt2 |
| D13 | Neo4j unchanged. There is NO graph-layer phase: the three-layer graph design (L0/L1/L2, PPR/Connect-4 modes, community reports, mechanism/abstraction nodes) was never blessed and is REMOVED from every plan (owner 2026-08-30). GRAPH mode stays HYBRID + the existing canonical hop-1 expansion. | owner 2026-08-30 |
| D14 | LLM transport = the extraction lane (`llm_extraction/client.py`, controller, limiter), same byte rule on `documents.byte_length` (floor 300 KB, set 450 KB); provider default `disabled`. | owner rules 2026-08-29 |
| D15 | **Canonical chunker = polymath v3.3 `tier_chunker`** (a Docling fork without OCR support): heading-bounded parents ~850 w target / 1,400 w max, tables atomic, ChunkKind noise skip, <15-word stub drop. The v4 `semantic_chunker` (fan-out 4, ~1,200-char children) is the INTERIM chunker; the swap is a re-ingest and is scheduled as its own change (§4 Phase 0). Enrichment always compiles ONE canonical parent per call. | owner 2026-08-30; register 1.16/4.1.1 |
| D16 | Local model setup is LOCKED to the 2026-08-29 config-fix result (§1.6): Qwen3.5-4B MLX 4-bit, `repetition_penalty=1.15 / repetition_context_size=400 / max_tokens=2500 / enable_thinking=false`, batch 40, salvage parser, dedup, noise filter. Enrichment reuses it unchanged. | Parent-Chunk Extraction: Config Fix Report |

## 1. Contracts

### 1.1 `parent-enrichment-v1` — model output (new `shared/polymath_shared/latent/contract.py`)
```
EnrichmentOutput (what the model returns; strict, extra keys ignored by the gate)
  summary:      str   80–120 words  (hard cap 1,000 chars)
  children:     list[{id: str, gist: str}]   gist 20–35 words (cap 320 chars); EXACTLY one per input child
  abstraction:  str   25–45 words  (cap 400 chars)
  mechanisms:   list[str]  ≤ 2 (cap 240 chars each)
  affordances:  list[str]  ≤ 2 (cap 200 chars each)
  questions:    list[str]  ≤ 3 (cap 160 chars each)
ParentEnrichment (what the worker persists = system metadata + EnrichmentOutput)
  enrichment_id, parent_id, doc_id, corpus_id, source_child_ids[], source_hash, input_hash,
  compiler_contract="parent-enrichment-v1", provider ("llm:<lane>"), model, prompt_version,
  status: READY|STALE|INVALID, created_at
```
Over-cap lists are TRIMMED in order (budget, not rejection), same pattern as `llm_extraction/gate.py:_enforce_budgets`.

### 1.2 Gate (`latent/gate.py`) — REJECT classes, all durable
1. `ENRICH_UNPARSEABLE` — after `strip_thinking` / `_repair_truncated` / `_loads_lenient` (reused from `llm_extraction/gate.py:35/50/159`) no object.
2. `ENRICH_GISTS_INCOMPLETE` — `{c.id for c in children} != set(input_child_ids)` (missing, unknown, or duplicate id).
3. `ENRICH_EMPTY` — any of `summary`, `abstraction` empty after strip, or a gist empty.
4. `ENRICH_INPUT_OVER_CEILING` — raised BEFORE the call when the rendered input exceeds `enrichment_input_token_ceiling` (default 6,000 tokens via the same `estimate_input_tokens` as extraction); the parent is recorded `INVALID(reason)` and skipped, never truncated silently.
No attestation requirement (LLM text by design) — which is exactly why nothing here is evidence (D7).
Rejection = `summary_jobs.state='FAILED'` + `summary_artifacts` row `stage='PARENT_ENRICHMENT_REJECTED'` with `{error_class, raw_head}`.

### 1.3 Identity / staleness
- `source_hash = content_hash({"compiler": COMPILER_CONTRACT, "children": [[child_id, chunk_index, text] …]})` (heading_path excluded — not sent to the model in v1.1).
- `prompt_version = "parent-enrichment-prompt-v1"`; `prompt_hash = content_hash(SYSTEM_PROMPT + json(bounds))`.
- `input_hash = content_hash({source_hash, prompt_hash, model_contract})` = `summary_jobs(stage='PARENT_ENRICHMENT', input_hash)` logical identity (`summary_worker_impl.py:44 _job_done`).
- `enrichment_id = "penr_" + content_hash({input_hash})[:32]`.
- Child change → new `source_hash` → previous READY row for that parent → `STALE` → regenerate → re-project; STALE points deleted by deterministic id, row → `INVALID`.

### 1.4 Projection (`latent/projection.py` + Qdrant worker)
- Kinds: `LATENT_KIND_ABSTRACTION="latent_abstraction"`, `LATENT_KIND_TRANSFER="latent_transfer"`.
- Texts: abstraction → `abstraction`; transfer → `"Mechanisms: " + "; ".join(mechanisms) + ". Useful for: " + "; ".join(affordances) + "."`.
- Point id = `qdrant_point_uuid(f"{enrichment_id}:{kind}")`; payload = routing payload keys (`summary_id=None, chunk_id=None, representation_kind, corpus_id, doc_id, parent_id, source_name, embedding_contract, text`) + `enrichment_id, compiler_contract, source_hash`.
- Receipt `receipt_hash(PROJECTION_QDRANT, kind, enrichment_id, CONTRACT_VERSION)` through `_already_current` (`project_qdrant_worker.py:419`) → incremental.

### 1.5 Latent rescue (`latent/rescue.py`) — HYBRID only
```
latent_rescue_parents(qvec, *, corpus_id, plan, routing_search, clock=time.monotonic) -> LatentRescue
LatentRescue: parents: list[LatentParent(parent_id, doc_id, source_name, best_score, channels{kind: rank})],
              degraded: str | None, latency_ms: float
```
- Two `routing_search` calls with the SAME `qvec` (`abstraction_top_k`, `transfer_top_k`, default 8 each), corpus-filtered; any exception or budget overrun → `parents=[]`, `degraded` set.
- Collapse by `parent_id` (max score, channels kept), skip parents already in HYBRID's `sections`, cap `max_latent_parents`.
- Deepening (inside `hybrid_retrieve`): for each latent parent, `routing_search(collection, qvec, {representation_kind: "routing_child", corpus_id, parent_id})[:max_children_per_section]` — the same filtered-child primitive pass-1 uses — producing candidates with `arrival="LATENT_RESCUE"`, `latent_rank`, `latent_channels`.
- Union: appended after neural + lexical rescue, deduped by `chunk_id`, region demotion applied as today, then `_truncate_reserving_rescue` with `latent_reserved_slots` (default 2) so the lane can seat its best hits (`pass1.py:285` currently reserves for `GLOBAL_CHILD_RESCUE` only → generalize with a `rescue_arrivals` parameter; default behaviour unchanged).
- Rerank and `final_max_total_items` cut unchanged; `trace["latent"] = {parents, channels, degraded, latency_ms, admitted_chunk_ids}`.


### 1.6 Model setup — local lane (LOCKED; distilled from "Parent-Chunk Extraction: Config Fix Report", 2026-08-29)
| Item | Locked value | Why (measured) |
|---|---|---|
| Model | `mlx-community/Qwen3.5-4B-MLX-4bit`, pinned snapshot `32f3e8ec…` (`sidecars/local_extractor/batched_server.py`) | hybrid linear/full attention: only 8 of 32 layers grow KV → 15 K tokens ≈ 469 MB; input size is not the constraint |
| Unit of work | ONE parent-sized, heading-bounded chunk per prompt (~850 w target / 1,400 w max = canonical `tier_chunker` parent, D15) | ~5× fewer chunks and ~10× fewer batches than 300 w on the same text; entities 56 vs 63 = noise removal, not loss (parent caught 7 editor names 300 w fragmented; 300 w invented `city`, `ZIP code`, `the Wiley logo`) |
| Generation | `max_tokens=2500`, `repetition_penalty=1.15`, `repetition_context_size=400`, `enable_thinking=false`, temperature 0 | baseline: 45% consecutive-repeat degeneration, every chunk hit the cap; frequency penalties killed JSON structure tokens (15 entities); rep-penalty 1.15 → 0% degeneration, self-terminates ~600 tokens, clean JSON |
| Batch | 40 prompts per `batch_generate` (peak 6.4 GB on 32 GB) — served by `/infer_batch`; the AIMD batch-token budget (`llm_controller_state`, seed 28 K tokens/call, halves on GPU-OOM) bounds it when the fleet is resident | a 45 K-token batch OOMed Metal with GLiNER/spaCy/embedder co-resident |
| Parsing | `json.loads` → truncation repair → per-object salvage → dedup entities by normalized name, relations by (subj, pred, obj) (`llm_extraction/gate.py`) | a parser that discarded truncated JSON was the original "0 entities" bug |
| Noise filter | drop chunks < 15 words; ChunkKind structural skip (TOC / copyright / cover / license / index / bibliography) from `chunk_kind.py` | dominant token cost for zero value |
| Lanes | ≤ byte threshold (floor 300 KB, set 450 KB) → local batch; above → cloud (Qwen3.5-397B via the Ollama daemon), both under the persisted AIMD controller | owner rule; controller measured 13–14× cloud parallelism |
| Enrichment | ~~same model~~ SUPERSEDED (owner 2026-08-30): DEDICATED `nvidia` pool endpoint via `select_endpoint_for_stage("parent_enrichment", …)` (STAGE-PIN-V1), model `nvidia/nemotron-3.5-lightning-30b-a3b`, thinking OFF (`reasoning_effort:"none"` — LIVE-VERIFIED: baseline burns the whole budget thinking, "none" → finish:stop clean JSON), temp 0, JSON mode ON, output bounded (`max_tokens` 700 qual / 900 prod), limiter seed 36 RPM / conc_cap 4 PER ACCOUNT — DUAL LANE (owner 2026-08-30): pin group `["nvidia","nvidia2"]`, two unlinked accounts each with an independent AIMD bucket (~72 RPM combined), docs sharded deterministically between them. Never rerouted outside the group; one dark = reduced capacity (logged), all dark = loud fail. Phase B qualification must canary the parent-enrichment-v1 schema on THIS model (extraction-schema canary parsed clean but yielded 0 entities — different schema, different behavior) | owner directive 2026-08-30 + Part 3 budget |
Still open from the report (tracked in the register, not this plan): real full-file completion time on the 838 KB book at batch 40; corpus-level entity dedup + `promote()` merge layer (recovers recurring certs missed in one chunk); optional 600 w middle-ground test.

### 1.7 Wire-contract reconciliation (owner review 2026-08-30)

The owner brought an outside provider-agnostic design ("parent-latent-v1",
drafted without codebase knowledge); reviewed against this plan, its
acceptance DISCIPLINE is adopted and its non-fitting concepts are
explicitly rejected here so the implementing session builds from ONE
reconciled spec:

ADOPTED (amends/extends the contracts above):
- **Integer child refs** in the model payload (0,1,2,…) mapped back to
  real chunk_ids by the worker — the model never reproduces long ids
  (same aliasing trick the extraction client already uses for
  neighborhood ids; reuse that machinery). §1.1's `children[].id`
  becomes the ref integer on the wire; `source_child_ids[]` keeps the
  real ids in system metadata.
- **Subset-hard, coverage-floor gists** — AMENDS §1.2
  `ENRICH_GISTS_INCOMPLETE`: an UNKNOWN or DUPLICATE ref stays a hard
  reject; a MISSING gist is a counted coverage shortfall (durable
  disposition, EXTRACTION-COVERAGE-V1 pattern) with a floor, not a
  binary reject. Rationale: the LEAN survivorship lesson — exact-match
  rejection on real model output silently drops whole parents; the
  design's own "no ingestion failure, backfill later" stance demands
  the floor.
- **Model may never produce** ids, provenance, hashes, timestamps,
  storage identity — already the law here (`finalize()`, content-
  addressed ids); restated as a §1.1 invariant.
- **Two-attempt repair cap** (normal → stricter-format retry →
  durable INVALID). Matches the existing reissue-once pattern; no
  repair loops.
- **Deterministic acceptance, not deterministic generation**: the model
  may vary; parse→validate→sanitize→canonicalize→hash may not.
  Canonicalization/hashing = `identity.content_hash` ONLY (a second
  hand-rolled json.dumps convention is the entity-id hyphen/underscore
  fork class).

REJECTED (concepts that do not fit this codebase):
- **One combined extraction+enrichment call** — §0a makes enrichment
  button-triggered LATER over already-extracted mixed-era parents;
  different granularity, staleness cadence, and failure modes. Stays
  split.
- **Relations in source_hash** — §1.3 already hashes children+compiler
  only; relations churn faster than children and must not stale every
  enrichment. If a bounded relation snapshot is ever SENT as context,
  record its hash in provenance — it never drives staleness.
- **A new UniversalRequest/adapter layer** — the seams exist:
  `LLMExtractionClient` + the endpoint pool + `complete_batched
  (system_prompt=…)` built for this exact stage. Enrichment inherits
  Groq/NVIDIA/etc. from MULTI-PROVIDER-AUTH-V1 with zero adapter work.
  The design's capability negotiation IS adopted, as config not code
  (STRUCTURED-CAPABILITY-V1): every endpoint declares
  `structured: schema|json|text`; "schema" is accepted but dispatches
  as json-object until a strict-schema canary passes per provider
  (measured: the primary silently ignores json_schema strict:true), and
  local parse→validate→sanitize runs REGARDLESS of level — provider
  structured output is an optimization, the validator is the contract.
- **Wider schema (principles/transfer/uses, caps 3/3/3/4)** — PARKED as
  V2 candidates gated on the P6 eval. §1.1's frozen field list stands
  because every field maps to one of the TWO projection kinds (§1.4);
  fields without a projection mapping are dead storage (the
  extraction-vs-metadata-gap failure class).

## 2. Component map

### 2.1 New files
| Path | Purpose / public surface |
|---|---|
| `shared/polymath_shared/latent/__init__.py` | package doc "ENRICHMENT ROUTES / CHILDREN PROVE" |
| `shared/polymath_shared/latent/contract.py` | §1.1 models, `EnrichmentBounds` (qualification/production), `COMPILER_CONTRACT`, `LATENT_KINDS=("latent_abstraction","latent_transfer")` |
| `shared/polymath_shared/latent/prompt.py` | `SYSTEM_PROMPT` (six outputs, word budgets, "exactly one gist per child id", JSON only), `render_parent_input(parent_id, children:[{id, ordinal, text}]) -> str`, `prompt_hash()`, `PROMPT_VERSION` |
| `shared/polymath_shared/latent/gate.py` | `sanitize_enrichment(raw, input_child_ids, bounds) -> (EnrichmentGateResult, EnrichmentOutput|None)` (§1.2), `source_hash(children)`, `transfer_text(output)` |
| `shared/polymath_shared/latent/compiler.py` | `compile_parents(complete: Callable[[list[PromptItem]], list[RawItem]], parents:[ParentInput], bounds, ceiling) -> list[CompiledParent]` (transport-agnostic; enforces the input ceiling BEFORE calling) |
| `shared/polymath_shared/latent/runtime.py` | `run_parent_enrichment_ticket(conn, *, ticket_id, corpus_id, doc_id, parent_id, input_hash, compiled, worker_id, provider, model)` — claim → EXISTING on input_hash → persist artifact + row → STALE previous → job COMPLETE/FAILED; mirrors `summary_runtime.py:36-100` |
| `shared/polymath_shared/latent/projection.py` | `latent_rows(conn, run_id) -> list[dict]` (READY rows of the run's corpus, two rows per enrichment), `stale_point_ids(conn, corpus_id)` |
| `shared/polymath_shared/latent/rescue.py` | §1.5 `latent_rescue_parents`, `LatentRescue`, `LatentParent`, `ARRIVAL_LATENT_RESCUE="LATENT_RESCUE"` |
| `stores/postgres/migrations/0043_parent_enrichments.sql` (renumbered 2026-08-30; 0041/0042 applied) | `parent_enrichments(enrichment_id PK, parent_id, corpus_id, doc_id, source_child_ids TEXT[], source_hash, input_hash, compiler_contract, provider, model, prompt_version, summary, children JSONB, abstraction, mechanisms JSONB, affordances JSONB, questions JSONB, status CHECK IN (READY,STALE,INVALID), created_at, superseded_at)`; partial unique index `(parent_id) WHERE status='READY'`; indexes doc_id/corpus_id; `summary_jobs` stage CHECK extended with `PARENT_ENRICHMENT` |
| `config/latent/parent-enrichment-v1.yaml` | bounds profiles, input ceiling, rescue caps/budget defaults (settings read it; env overrides) |
| `eval/v5/latent_transfer/cases.yaml`, `eval/v5/latent_transfer/p6_latent_transfer_recall.py` | P6 suite (§5) |
| `tests/determinism/test_latent_contract_gate.py`, `test_latent_rescue.py`, `test_hybrid_latent.py`, `test_latent_projection.py` | pure suites (§6) |
| `tests/integration/test_latent_enrichment_stage.py` | DB-backed stage test |

### 2.2 Modified files (line anchors verified on main@463f52d)
| Path:line | Change |
|---|---|
| `workers/workers/summary_worker_impl.py:80` | ADD `_parents_of_docs_for_enrichment()` selecting `chunk_id, parent_id, chunk_index, text` (`tier='child' AND parent_id IS NOT NULL ORDER BY chunk_index`) — heading/offsets not needed in v1.1 |
| `summary_worker_impl.py:127 _do_parents` (pattern) → ADD `_do_enrichment(conn, run_id)` | settings gate (`enrichment_provider=="disabled"` → `{"status":"DISABLED"}`); lane per document via `llm_extraction.policy.select_lane(byte_length)`; compute `source_hash/input_hash`; `_job_done("PARENT_ENRICHMENT", …)`; `_ensure_job`; batch parents through `compile_parents`; `run_parent_enrichment_ticket` per parent |
| `summary_worker_impl.py:279 _DISPATCH` | `+ "parent_enrichment.v1": _do_enrichment` |
| `workers/workers/summary_worker.py:21` | `+ "parent_enrichment.v1"` |
| `control/control/tickets.py:43-46 STAGE_DAG` | `+ ("parent_enrichment", "parent_enrichment.v1", (), ())` after `parent_summary`; `:52 NON_BLOCKING_STAGES` `+ "parent_enrichment"` |
| `control/control/fleet_autopilot.py:47` | summary tuple `+ "parent_enrichment"` |
| `control/control/reconciliation.py:72` | `+ "parent_enrichment": ("semantic_bundle",)` |
| `shared/polymath_shared/settings.py:146 WorkerSettings` | `+ enrichment_provider ("disabled"/"llm")`, `enrichment_profile`, `enrichment_max_parents_per_call` (local batch), `enrichment_input_token_ceiling=6000`, `latent_retrieval_enabled=False`, `latent_abstraction_top_k=8`, `latent_transfer_top_k=8`, `latent_max_parents=3`, `latent_reserved_slots=2`, `latent_budget_ms=250` |
| `shared/polymath_shared/llm_extraction/client.py:271 _infer_batch_call` / `:220 extract_batched` | `system_prompt` parameter (default `SYSTEM_PROMPT`); ADD `complete_batched(items:[(id, system, user, max_tokens)]) -> [(id, raw_text, error_class)]` reusing sub-batching, budget AIMD, OOM halving, 404 fallback, controller receipts. Extraction path byte-identical (defaults) |
| `workers/workers/project_qdrant_worker.py:295-303` | `+ LATENT_KIND_*`; routing block (`:600-660`) ADDS `latent_rows(conn, run_id)` under the same collection/contract + receipt guard; STALE cleanup (delete points → rows INVALID) |
| `shared/polymath_shared/pass1.py:285 _truncate_reserving_rescue` | `+ rescue_arrivals: tuple[str,...]=(ARRIVAL_GLOBAL_CHILD_RESCUE,)` param (default unchanged ⇒ FAST byte-identical) |
| `shared/polymath_shared/hybrid.py:48 HybridRetrievalPlan` | `+ latent_enabled=False, latent_abstraction_top_k=8, latent_transfer_top_k=8, latent_max_parents=3, latent_reserved_slots=2, latent_budget_ms=250` (defaults keep `hybrid-retrieval-v1` frozen) |
| `hybrid.py:152 hybrid_retrieve` | `+ latent_rescue: Optional[Callable]=None` kwarg; after `rescue_lexical` (`:~262`) and before `final_candidates`: if `plan.latent_enabled and latent_rescue`, obtain parents (§1.5), deepen via `routing_search` child filter, append `LATENT_RESCUE` candidates; pass `rescue_arrivals=(GLOBAL_CHILD_RESCUE, LATENT_RESCUE)` and `latent_reserved_slots` to the truncation; `trace["latent"]` |
| `shared/polymath_shared/retrieval_modes.py:42 hybrid_mode_plan` | `+ apply_latent(plan, enabled: bool|None)` → `replace(plan, latent_enabled=…)` from settings default / request override; `EXPOSED_MODES`, `DEFAULT_MODE`, `validate_mode` UNCHANGED |
| `orchestrator/orchestrator/api/fast.py:53 FastSearcher._search` | latency key `"latent"` for `latent_*` kinds (no other change; `fast_retrieve` untouched) |
| `orchestrator/orchestrator/api/hybrid.py:73 hybrid_fast_retrieve` | `+ latent: bool|None` param → `apply_latent`; pass `latent_rescue=` closure (`searcher`, `corpus_id`); `meta.latent = trace["latent"]`; `latency_ms["latent"]` |
| `orchestrator/orchestrator/api/graph.py:71 graph_retrieve` | forward `latent` to `hybrid_fast_retrieve` (inherits; graph seeds come from the enriched child evidence, `retrieve.py:360 _corpus_seed_ids`) |
| `orchestrator/orchestrator/api/retrieve.py:35 RetrieveRequest`, `evidence.py:43`, `chat.py:46`, `ui.py:768 StreamChatRequest` | `+ latent: Optional[bool]=None`; dispatch passes it to HYBRID/GRAPH only |
| `orchestrator/orchestrator/api/ui.py:1128-1195 chat_stream.generate()` | forward `latent`; `answer.retrieval.latent = {enabled, parents, degraded}` |
| `mcp_server/polymath_mcp.py:80 polymath_query`, `:103 polymath_retrieve` | `latent: bool|None` passthrough |
| `frontend/src/api.ts:79 streamChat` (+ query-bar toggle) | optional `latent` in body; show `retrieval.latent.parents` count |
| `scripts/scaffold_polymath_v4.py TREE`, `scripts/README.md` | declare new files / register the P6 script |

### 2.3 Not touched (by contract)
`semantic_chunker.py`, `retrieval_summaries.py`, `parent_summary.py`, `summary_runtime.py`, `pass1_retrieve` body, `fast_retrieve`, `evidence_assembly.py`, `answer_synthesis.py`, `project_neo4j_worker.py`, `project_canonical_worker.py`, Neo4j schema, `retrieval_modes.EXPOSED_MODES/DEFAULT_MODE/validate_mode`, `lane_liveness.py`, `query_shape.py`.

## 3. Dependency graph (build order)
```
A  contract.py → prompt.py → gate.py → compiler.py                      pure; tests only
B  0041 migration → runtime.py → summary_worker_impl (_do_enrichment, rich select)
   → tickets/autopilot/reconciliation/worker kinds → settings
   → client.py (system_prompt param + complete_batched)                 needs A
C  projection.py → project_qdrant_worker (kinds, latent_rows, receipts, STALE cleanup)   needs B
D  rescue.py → pass1 truncation param → hybrid plan/engine → retrieval_modes.apply_latent
   → api/hybrid.py + api/graph.py wiring → request flag (4 routes) → MCP/UI passthrough
                                                                        unit-testable after A with fakes; live after C
E  eval/v5/latent_transfer (P6) → channel/kind attribution → keep/kill decision   needs D on a corpus with B+C run
```
Runtime deps: MLX batched server `/infer_batch` (local) or Ollama daemon (cloud) through the existing controller (`llm_controller_state`); embedder sidecar (batch 32, `project_qdrant_worker.py:122`); Qdrant routing collection under `NEURAL_EMBED_CONTRACT`; Postgres.

## 4. Phases with execution notes

### Phase A — contract, prompt, gate, compiler (pure)
1. Write `latent/contract.py`, `prompt.py`, `gate.py`, `compiler.py` (no runtime import).
2. Tests (`test_latent_contract_gate.py`): every §1.2 class; trimming to bounds; `source_hash` changes iff a child's id/index/text changes; input-ceiling rejection happens before any call; transfer text rendering is deterministic.
3. Exit: `pytest --noconftest tests/determinism/test_latent_contract_gate.py` green; `git diff --stat` shows only `shared/polymath_shared/latent/` + tests.

### Phase B — ingestion stage
1. Apply `0041` (idempotent); verify `\d summary_jobs` shows the extended CHECK.
2. `client.py`: `system_prompt` param + `complete_batched`; the 61 LLM tests must stay green (extraction byte-identical).
3. `latent/runtime.py` + `_do_enrichment` + registry/autopilot/reconciliation/worker kinds + settings.
4. Lane: `select_lane(documents.byte_length)` per document; local → `/infer_batch` with `enrichment_max_parents_per_call` prompts per call (≈2K tokens each; `max_tokens` 700 qualification / 900 production); cloud → one parent per call. Batch budget AIMD + limiter already govern both.
5. Exit on the canary corpus: `parent_enrichments` READY for every parent with ≥1 child (INVALID only for ceiling breaches, listed); second run creates zero artifacts; with the LLM sidecar stopped, `parent_summary` stays COMPLETE and the corpus stays `query_ready` (D11 proof); token receipts ≈ 2K/parent.

### Phase C — projection
1. `latent/projection.py` + Qdrant worker changes; STALE → delete points → INVALID.
2. Exit: point count = 2 × READY enrichments; receipts per point; re-run schedules zero embeddings; editing one child regenerates and replaces exactly that parent's two points.

### Phase D — HYBRID rescue lane (GRAPH inherits)
1. `latent/rescue.py`; `_truncate_reserving_rescue` param; hybrid plan/engine; `apply_latent`; api wiring; request flag; MCP + UI.
2. Determinism proofs: `latent_enabled=False` ⇒ `HybridResult` byte-identical to a frozen fixture; `fast_retrieve` output byte-identical regardless of the flag; existing `test_pass1.py`, `test_hybrid.py`, `test_retrieval_invariants.py`, `test_depth_policy.py`, `test_batched_pass1.py` unchanged and green.
3. Fail-open proofs (`test_latent_rescue.py`): `routing_search` raising / slow / unknown payload ⇒ `parents=[]`, `degraded` set, no exception; caps honoured; parents already in `sections` skipped; reserved seats keep ≥1 latent child on a saturated candidate list.
4. Exit: `POST /retrieve {"mode":"HYBRID","latent":true}` returns `meta.latent` on the canary corpus; GRAPH result carries the same children plus canonical facts; `latent:false` equals pre-change output byte-for-byte; `/chat/stream` answer frame carries `retrieval.latent`.

### Phase E — P6 evaluation + kind decision
1. Owner-authored `cases.yaml` (≥20): `query, obvious_domains[], latent_domains[], acceptable_mechanisms[], forbidden_shortcuts[], expected_parent_ids[]`.
2. Metrics: LatentRecall@10/@20, CrossDomainRecall@K, MechanismRecall@K, UniqueDomainCount@K, BridgePrecision@K, FalseAnalogyRate (labelled negatives), AnswerLift with vs without.
3. Attribution: unique relevant hits per kind (`latent_abstraction` vs `latent_transfer`) and, if later added, `latent_question`. Kill rule: a kind with ≤5% unique relevant hits is dropped from projection.
4. Exit: `LATENT-TRANSFER-P6-RESULTS.md`; owner GO/NO-GO to set `latent_retrieval_enabled=true` per corpus.

### Phase 0 (scheduled separately) — canonical chunker swap
Adopt v3.3 `tier_chunker` (D15) as the v4 chunker: new `chunk_contract_version`, re-ingest, all projections rebuilt from the raw documents (everything derived is rebuildable). Enrichment units then equal canonical parents. Not a prerequisite for phases A–E (the compiler takes any parent; the input ceiling guards oversized ones).

## 5. Flags, rollout, rollback
- Ingestion: `POLYMATH_WORKER_ENRICHMENT_PROVIDER=disabled|llm` (default disabled → stage completes `DISABLED`), `POLYMATH_WORKER_ENRICHMENT_PROFILE=qualification|production`, `POLYMATH_WORKER_ENRICHMENT_INPUT_TOKEN_CEILING=6000`.
- Query: `POLYMATH_WORKER_LATENT_RETRIEVAL_ENABLED=false` (default) + request `latent` override on HYBRID/GRAPH; `..._LATENT_MAX_PARENTS=3`, `..._LATENT_BUDGET_MS=250`, top-ks.
- Rollback = flags off: frozen plans, no code-path difference; rows/points inert. Hard rollback: `DELETE FROM parent_enrichments; DELETE points WHERE representation_kind IN ('latent_abstraction','latent_transfer')` — nothing else references them (D13).
- Cost: enrichment calls carry the same receipts as extraction (tokens, wall, lane, `limiter_effective`, `batch_tokens_cap`) in the summary stage artifact.

## 6. Test matrix
| Layer | Tests | Without DB? |
|---|---|---|
| A | `test_latent_contract_gate.py` | yes |
| B | `test_latent_enrichment_stage.py` (ticket, idempotency, STALE, DISABLED provider), existing `test_summary_workers.py`, `test_summary_idempotency.py`, 61 LLM tests | first needs DB |
| C | `test_latent_projection.py`, existing `test_summary_projection.py` | yes |
| D | `test_latent_rescue.py`, `test_hybrid_latent.py`, existing pass1/hybrid/invariants/depth/batched, `tests/integration/test_r1c_fast_endpoint.py`, `test_chat_e2e.py` | mixed |
| E | `p6_latent_transfer_recall.py` on the canary corpus | live stack |

## 7. Open decisions (owner) — assumed defaults until overridden
1. Enrichment lane = extraction's 300 KB byte rule (local ≤ threshold, cloud above). Assumed yes.
2. Exposure = `latent` request flag + settings default on HYBRID/GRAPH; FAST ignores it; no new mode. Assumed yes (Part 3).
3. `questions` are stored, not vectorized, until P6 says otherwise. Assumed yes (Part 3 §9).
4. Orphan children (`parent_id IS NULL`) skipped, as parent summaries do. Assumed yes.
5. `/ask` does not read `parent_enrichments` in v1. Assumed yes.

## 8. Exit criteria for the layer
- Disabled: every existing retrieval/summary/projection test unchanged; all `plan_version`s unchanged; zero extra Qdrant points; FAST output identical with or without the flag.
- Enabled on the canary corpus: ≥95% parents READY; P6 LatentRecall@10 ≥ baseline + 0.15 absolute on the cross-domain subset; FalseAnalogyRate ≤ 10%; P95 latent lane ≤ 250 ms; zero 5xx attributable to the lane; GRAPH inherits latent children without touching Neo4j (no graph-layer work exists in this plan).

## 9. INGESTION-RUNTIME-HARDENING (owner directives 2026-08-30, base-validation session) — prerequisite track

These are base-pipeline changes the owner asked for during validation. They
are NOT part of the latent layer but must land before it (the latent layer
inherits the extraction lanes and the DAG). Each item names the files it
touches; the same "no edits under shared/workers/control while an ingest
runs; restart the fleet after every commit" rule applies.

### 9.1 Measured extraction token sizes (2026-08-30 re-ingest, 2 documents)
| Lane | Unit sent | Per call | Totals |
|---|---|---|---|
| unit | one parent neighborhood = the parent's 4 children ≈ 4.7 K chars ≈ **1.2 K tokens** (CySA+: 721 children → 181 neighborhoods, median 4,648 chars; Learning SQL: 97 → 25). The 60,000-char cap never engages: parents are the unit. | — | — |
| cloud (CySA+, 838 KB) | 4 neighborhoods + system prompt | tokens_in median **5,860**, max **11,738**; tokens_out median ~1,000 | 46 calls, 290,724 in / 40,719 out; 769 entities, 258 relations admitted to the gate; 132 / 111 rejected unattested; 0 quarantined; limiter at 16, 13–14× parallel |
| local (Learning SQL, 114 KB) | 1–3 neighborhoods per `/infer_batch` under the AIMD batch budget (6 K → 10 K tokens during the run) | 17–33 s per call; tokens not recorded (fixed: client now stores the server's `prompt_tokens/completion_tokens`) | 25 calls, **5 quarantined (20%)** = `SANITIZE_UNKNOWN_NEIGHBORHOOD` — the 4B model dropped the `:0` suffix of the 70-char id (fixed: prompts now carry `n1…nk`, mapped back in the client); 30 entities / 25 relations = 1.2 / 1.0 per neighborhood vs cloud 4.25 / 1.43 — **local yield is 3.5× lower**; this is the "holds its own production weight" question and needs a controlled A/B on the same document (cloud vs local) before local carries production alone. |

### 9.2 GLiNER retirement (full migration; owner 2026-08-30)
Scope (18 files reference GLiNER): `workers/workers/extract_worker.py` (69 refs: `gliner` provider mode, `_entity_spans`/`_evidence_spans` GLiNER branches, `_GLINER_PIN`, manifest fields), `rescue.py` (19), `evidence_proposer.py` (9, `merge_gliner_proposals`), `reprocess_worker.py`, `profile_router.py`, `fact_admission_stage.py`, `kimi_v2_candidates.py`; `shared/polymath_shared/{clients.py GlinerClient, settings.py gliner_url, query_policy.py provider passes, contracts.py ExtractionManifest gliner_*, span_repair.py, referential_span.py, rerank.py (_slot_alive gliner), observability.py}`; `control/control/{process_supervisor.py sidecar_gliner slot, fleet_autopilot.py extract-demand set}`; `orchestrator/api/health.py`, `registry.py`, `sidecars/gliner_runtime/`, tests. Plan: (1) `extraction_provider` default → `llm_live`, `gliner` mode removed (contract hash keeps `gliner_pin=retired`); (2) delete the sidecar dir, supervisor slot, autopilot membership, readiness entry, `GlinerClient`; (3) rescue lane (I4R) becomes llm-only or is removed (it re-queried GLiNER per slice); (4) `ExtractionManifest.gliner_*` → `extractor_*`; (5) delete the 9 GLiNER weight caches (~14 GB: `~/.cache/huggingface/hub/models--*gliner*`); (6) register 6.1 → DONE. Byte-identity of the frozen gliner path is no longer a goal (owner).

### 9.3 Chunk-and-embed early (owner: "after parent and child chunks are identified, child chunks are embedded while extraction begins")
Today `STAGE_DAG` (`control/control/tickets.py:24-30`) is intake → extract → profile_document → project_qdrant → …; child embeddings wait for extraction. Change: split `project_qdrant` into `embed_chunks` (chunk lane; depends only on `intake` — `chunk_count` artifact + `qdrant` chunk receipts) and `project_routing` (routing cards; depends on `profile_document`). `workers/workers/project_qdrant_worker.py:522 process_event` already separates the chunk lane and the routing lane internally — the split is at the DAG/event level (`tickets.py STAGE_DAG`, `_STAGE_SPEC`, `census.py STAGE_CHAIN`, `reconciliation.py STAGE_CONTRACT_DEPENDENCIES`, `fleet_autopilot.py` stage groups, verifier keys `qdrant`/`routing_qdrant`). Result: embeddings run in parallel with cloud/local extraction; FAST readiness is unchanged (still needs routing cards).

### 9.4 Job-level completion + lane assist (owner)
- **Job = the set of documents submitted together** (a manifest / one UI upload batch): a `ingest_jobs(job_id, corpus_id, doc_ids[], status)` record; `query_ready` promotion stays per run, but the corpus/job is `COMPLETE` only when every member run is `query_ready` (10 files → all 10). Surface in `/semantic_readiness` and the UI.
- **Lane assignment by file size first** (existing: `select_lane(byte_length)`), then **assist**: when one lane's queue is empty and the other still has extract tickets, the idle lane takes the next ticket regardless of size — cloud may take small files; local may take a big file only if its neighborhoods fit the local budget (they always do: the unit is one parent). Implementation: extract tickets carry `lane`; the extract worker runs two claim loops (one per lane, `llm_concurrency_*`); `select_lane` becomes `preferred_lane`; a claim from the non-preferred lane is allowed when the preferred lane has no idle capacity (`llm_controller_state` effective vs in-flight). The byte rule stays a **privacy** rule for the cloud direction only (≤ threshold never leaves the machine; above threshold MAY run locally).
- **Local must hold its own weight**: the A/B in 9.1 is the gate; until local yield is within an owner-set band of cloud on the same document, assist is cloud→local only for files the cloud lane is allowed to take.

### 9.5 Deterministic lifecycle under the control plane (owner)
- Orchestrator and the batched local server become supervised slots (the orchestrator slot exists in `process_supervisor.py:55` but was never spawned this session; the batched server has no slot at all — both were started by hand).
- Startup order: stores → sidecars (embedder, spaCy, reranker) → batched server → control → workers → orchestrator; readiness = `/ready` per slot; a worker that boots against a stale bundle exits 3 (already) and the supervisor's restart budget must not quarantine it for that (it currently does after 6 exits/300 s).
- Shutdown after job: when the job is COMPLETE and no query demand for `QUERY_GRACE_S`, the autopilot parks the batched server and extraction sidecars (frees ~3–6 GB); re-wake on the next intake event.
- Memory discipline: `batched_server.py` cache/memory caps (landed 2026-08-30) are the reference; every MLX slot declares its ceiling in `config/runtime_budget.yaml` (register 4.2.5).

### 9.6 Landed during validation (2026-08-30)
Stale-projection tolerance + orphan purge; delete_document routing-card purge; MLX cache/memory caps; breaker wait on blocking acquire; GLiNER pin no longer a boot dependency in llm modes; short neighborhood aliases (`n1…`) + batched token accounting.
