---
change_id: LATENT-TRANSFER-LAYER-V1-PLAN
owner: governance
date: 2026-08-30
status: proposed
architecture_impact: additive — optional LLM-enriched parent compilation at ingestion + optional latent seed lane at query time; baseline FAST/HYBRID/GRAPH byte-identical when disabled
last_reviewed: 2026-08-30
---

# LATENT-TRANSFER-LAYER-V1 — implementation plan (files, dependencies, execution)

> Inputs, each ingested in its own pass (see
> `LATENT-TRANSFER-LAYER-V1-DESIGN-NOTES.md`): `~/Downloads/Adapter.txt`
> (PARENT_ENRICHMENT adapter) and `~/Downloads/Adapter 2.md` (latent
> transfer sidecar). Code facts from
> `docs/wiki/architecture/QUERY-TIME-MAP-2026-08-30.md`. Every path:line
> below was verified on `main@8f418d7`.
>
> Sequencing agreed with the owner: (1) this plan → (2) owner tests the
> current base (UI, MCP, query time, ingestion, extraction) for bugs and
> contract drift → (3) build phases A–E below in order.

## 0. Decision summary

| # | Decision | Source |
|---|---|---|
| D1 | Deterministic parent summary (`build_parent_summary`, `retrieval_summaries`) is UNCHANGED. Enrichment is a SEPARATE artifact: `PARENT_ENRICHMENT`, one LLM forward pass per parent. | Pt1 §headline, Pt2 §"keep separate" |
| D2 | Output contract = `parent-enrichment-v1` (Pt1 superset shape: `parent_summary`, `hierarchy[]`, `extract{}`, `latent{}`, `coverage{}`) with Pt2 bounds and Pt2's abstraction shape (`principle`, `domain_independent_description`). | reconciliation |
| D3 | Storage: `parent_enrichments` (typed authority) + `summary_artifacts.stage='PARENT_ENRICHMENT'` (immutable envelope). NEVER `retrieval_summaries`. | Pt1 §storage |
| D4 | Projection: five bounded Qdrant kinds `latent_parent_summary / latent_abstraction / latent_mechanism / latent_affordance / latent_pseudo_query` in the EXISTING routing collection (payload-filtered like every other kind). Never the JSON blob; parent `summary_vector` stays pure. | Pt1 §embed, Pt2 §purity |
| D5 | **Hard interface boundary: the latent layer produces additional `parent_id`s.** Latent hits are never evidence; they nominate parents that flow into the EXISTING section → child deepening → rerank → evidence bundle. | Pt1 §retrieval, Pt2 §boundary |
| D6 | `candidates = baseline ∪ latent`; fail-open; latency budget (default 250 ms); timeout/failure/missing enrichment → zero latent candidates; never HTTP 5xx from the latent lane. | Pt2 §fail-open |
| D7 | Flag-gated: `POLYMATH_LATENT_RETRIEVAL_ENABLED=false` default + per-channel flags + request-level `latent` override for A/B. Existing modes and `plan_version` are byte-identical when disabled. | Pt2 §flags |
| D8 | Enrichment is a NON-BLOCKING summary-family stage: never a readiness dependency (FAST fails only on its routing projection). | Pt1 §runtime, `control/control/tickets.py:52 NON_BLOCKING_STAGES` |
| D9 | Query time stays deterministic: no LLM call at query time. | Pt2 §query-time |
| D10 | Neo4j UNCHANGED in this plan. Mechanism/Abstraction/PseudoQuery nodes, `ANALOG_OF`/`BRIDGES` edges and the cross-domain abstraction forest are a later phase (F), gated on P6 evidence. | Pt2 §"delay Neo4j" |
| D11 | Its own evaluation suite (P6 LATENT_TRANSFER_RECALL) with per-channel attribution; channels that add no unique recall are removed. | Pt2 §evaluation |
| D12 | LLM transport reuses the extraction lane (`llm_extraction/client.py`): same local sidecar, same limiter/controller, same 300 KB cloud rule keyed on `documents.byte_length`; default provider `disabled`. | owner rules 2026-08-29 |

## 1. Contracts

### 1.1 `parent-enrichment-v1` (Pydantic, new `shared/polymath_shared/latent/contract.py`)

```
ParentEnrichmentPacket
  schema_version: Literal["parent-enrichment-v1"]
  parent_id: str
  parent_summary: str                       (≤ 1,200 chars)
  hierarchy: list[HierarchyEntry]           (EXACTLY the input children, any order)
      child_id, ordinal:int, heading_path:list[str], summary:str (≤400), key_points:list[str] (≤5, ≤160 each)
  extract: Extract
      claims[{text, source_child_ids}] ≤12   definitions[{term, definition, source_child_ids}] ≤12
      principles[{text, source_child_ids}] ≤8  relationships[{subject, relation, object, source_child_ids}] ≤12
      procedures[{text, source_child_ids}] ≤6  constraints[{text, source_child_ids}] ≤6  examples[{text, source_child_ids}] ≤6
  latent: Latent
      abstraction{principle, domain_independent_description, source_child_ids}   (exactly 1)
      mechanisms[{cause, relation, effect, conditions[], source_child_ids}]      ≤ MAX_MECHANISMS
      affordances[{capability, action, desired_effect, source_child_ids}]       ≤ MAX_AFFORDANCES
      pseudo_queries[{text, source_child_ids}]                                  ≤ MAX_PSEUDO_QUERIES
  coverage: {input_child_ids[], covered_child_ids[], omitted_child_ids[]}
```
Bounds are settings with these defaults — qualification profile
`MAX_MECHANISMS=2, MAX_AFFORDANCES=2, MAX_PSEUDO_QUERIES=3` (8 latent
vectors + 1 parent summary = 9/parent); production profile `3/3/4`
(12/parent). Over-cap lists are TRIMMED in order (budget, not rejection),
mirroring `llm_extraction/gate.py:_enforce_budgets`.

### 1.2 Validation (non-negotiable, `latent/gate.py`) — REJECT on any failure
1. `sanitize` (reuse `llm_extraction.gate.strip_thinking`, `_repair_truncated`, `_loads_lenient`) → JSON or `ENRICH_UNPARSEABLE`.
2. `packet.parent_id == input parent_id` else `ENRICH_WRONG_PARENT`.
3. `set(h.child_id for h in hierarchy) == set(input_child_ids)` (no missing, no unknown, no duplicates) else `ENRICH_HIERARCHY_INCOMPLETE`.
4. every `source_child_ids` element ∈ input set and non-empty else `ENRICH_UNKNOWN_SOURCE`.
5. `coverage.omitted_child_ids == []` and `covered == input` else `ENRICH_COVERAGE`.
6. `heading_path` per hierarchy entry must equal the input child's heading_path (the model may not rewrite structure) else `ENRICH_STRUCTURE_DRIFT`.
7. Text fields are free text (LLM-generated by design) — NO attestation requirement; that is the documented difference from `polymath-extraction-v1` and the reason nothing here is ever evidence (D5).
Rejections are durable: `summary_jobs.state='FAILED'` + `summary_artifacts` row with `stage='PARENT_ENRICHMENT_REJECTED'` carrying `{error_class, raw_head}` (same "recorded, never silent" rule as extraction).

### 1.3 Identity and staleness
- `source_hash = content_hash({"compiler": COMPILER_CONTRACT, "children": [[child_id, heading_path, char_start, char_end, text] in chunk_index order]})`.
- `prompt_hash = content_hash(SYSTEM_PROMPT + bounds)`; `model_contract = f"{lane}:{model}"`.
- `input_hash = content_hash({source_hash, prompt_hash, model_contract})` → `summary_jobs (stage='PARENT_ENRICHMENT', input_hash)` logical identity (same rule as `_job_done`, `summary_worker_impl.py:44`).
- `enrichment_id = "penr_" + content_hash({input_hash})[:32]`.
- Any child change → new `source_hash` → old row `status='STALE'` (UPDATE by parent_id where source_hash differs) → regenerate → re-project; stale rows' points are DELETED from Qdrant by id (deterministic ids, §1.4).

### 1.4 Projection contract
- Kinds (new constants in `project_qdrant_worker.py` next to `:295-303`): `latent_parent_summary`, `latent_abstraction`, `latent_mechanism`, `latent_affordance`, `latent_pseudo_query`.
- Point id = `qdrant_point_uuid(f"{enrichment_id}:{kind}:{ordinal}")` (deterministic; text is inside enrichment_id via input_hash).
- Payload = existing routing payload keys (`summary_id=None, chunk_id=None, representation_kind, corpus_id, doc_id, parent_id, source_name, embedding_contract, text`) + `enrichment_id, ordinal, source_child_ids[], compiler_contract, source_hash`.
- Receipt: `receipt_hash(PROJECTION_QDRANT, kind, f"{enrichment_id}:{ordinal}", CONTRACT_VERSION)` through the existing `_already_current` guard (`project_qdrant_worker.py:419`) so re-runs are incremental.
- Embedded text per kind: parent_summary → `parent_summary`; abstraction → `principle + " — " + domain_independent_description`; mechanism → `f"{cause} {relation} {effect}" + (" when " + "; ".join(conditions))`; affordance → `f"{action} to {desired_effect}" (+ capability)`; pseudo_query → `text`.

### 1.5 Retrieval contract (`latent/seeds.py`)
```
latent_seed_parents(query_vector, *, corpus_id, plan, routing_search, clock) -> LatentSeeds
LatentSeeds: parents: list[LatentParent]  (parent_id, doc_id, best_score, channels: {kind: rank}), degraded: str|None, latency_ms
```
- One `routing_search` call per ENABLED channel (`top_k = plan.latent_top_k_per_channel`, default 10), same query vector as pass-1 (no second embed).
- Collapse to `parent_id` with max-score aggregation; keep `channels` for attribution (D11).
- Budget: stops issuing channel searches once `clock() - t0 > plan.latent_budget_ms`; any exception → `parents=[]`, `degraded="latent_<reason>"`.
- Cap: `plan.latent_max_parents` (default 6).
Consumption inside `pass1_retrieve`: latent parents are added as SECTION candidates with arrival label `LATENT_LED` (new constant beside `pass1.py:33-39`), ranked AFTER hierarchy-derived sections, BEFORE global rescue; they then go through the unchanged `max_children_per_section` deepening, rerank, `final_max_children` cut and `rescue_reserved_slots`. Latent never touches `final_evidence` directly.

## 2. Component map

### 2.1 New files
| Path | Purpose | Public surface |
|---|---|---|
| `shared/polymath_shared/latent/__init__.py` | package doc: "ENRICHMENT ROUTES / CHILDREN PROVE" | — |
| `shared/polymath_shared/latent/contract.py` | §1.1 models, bounds, `COMPILER_CONTRACT="parent-enrichment-v1"`, `LATENT_KINDS` | `ParentEnrichmentPacket`, `EnrichmentBounds`, `latent_kinds()` |
| `shared/polymath_shared/latent/prompt.py` | system prompt + `render_parent_input(parent_id, existing_summary, children, facts, entities)` producing the `[PARENT]/[EXISTING_PARENT_SUMMARY]/[CHILD]…/[SETTLED_FACTS]/[CANONICAL_ENTITIES]` blocks (Pt1 §input) | `SYSTEM_PROMPT`, `render_parent_input`, `prompt_hash()` |
| `shared/polymath_shared/latent/gate.py` | §1.2 sanitize → validate → trim; returns `(EnrichmentResult, packet|None)` | `sanitize_enrichment`, `validate_enrichment` |
| `shared/polymath_shared/latent/compiler.py` | one call per parent via the extraction transport; batching across parents on the local lane | `compile_parents(client, parents:list[ParentInput], bounds) -> list[CompiledParent]` |
| `shared/polymath_shared/latent/runtime.py` | `run_parent_enrichment_ticket(conn, ...)` — claim → idempotency → compile → gate → persist (`summary_artifacts` + `parent_enrichments`) → supersede/STALE → job COMPLETE; mirrors `summary_runtime.run_parent_summary_ticket` (`summary_runtime.py:36-100`) | `run_parent_enrichment_ticket` |
| `shared/polymath_shared/latent/projection.py` | `latent_rows(conn, run_id) -> list[dict]` (READY rows only) + `embed_text_for(kind, item)` (§1.4) | used by the Qdrant worker |
| `shared/polymath_shared/latent/seeds.py` | §1.5 fail-open seed lane | `latent_seed_parents`, `LatentSeeds`, `LatentParent` |
| `stores/postgres/migrations/0041_parent_enrichments.sql` | table + indexes (Pt1 DDL) + `ALTER TABLE summary_jobs DROP CONSTRAINT …stage_check; ADD CHECK (… 'PARENT_ENRICHMENT')` | — |
| `config/latent/parent-enrichment-v1.yaml` | bounds profiles (qualification/production), lane policy, budget defaults | read by settings |
| `eval/v5/latent_transfer/cases.yaml` | P6 cases (query, obvious_domains, latent_domains, acceptable_mechanisms, forbidden_shortcuts, expected_parent_ids) | — |
| `eval/v5/latent_transfer/p6_latent_transfer_recall.py` | runs baseline vs baseline+latent through `/retrieve`, computes §5 metrics + channel attribution table | CLI |
| `tests/determinism/test_latent_contract_gate.py` | §1.2 rules, trimming, staleness hash | — |
| `tests/determinism/test_latent_seeds.py` | fail-open, budget, collapse/attribution, cap | — |
| `tests/determinism/test_pass1_latent.py` | `LATENT_LED` sections deepen through the unchanged pipeline; disabled ⇒ byte-identical `Pass1Result` | — |
| `tests/determinism/test_latent_projection.py` | rows/ids/payload/receipt determinism; STALE rows excluded | — |
| `tests/integration/test_latent_enrichment_stage.py` | DB-backed: ticket → artifacts → table → STALE on child change (needs conftest DB) | — |

### 2.2 Modified files (line anchors verified)
| Path:line | Change |
|---|---|
| `workers/workers/summary_worker_impl.py:80 _parents_of_docs` | ADD `_parents_of_docs_rich()` selecting `chunk_id, parent_id, chunk_index, heading_path, char_start, char_end, text, summary` (`tier='child' AND parent_id IS NOT NULL ORDER BY chunk_index`). Existing function untouched. |
| `summary_worker_impl.py:127 _do_parents` (pattern) | ADD `_do_enrichment(conn, run_id)`: settings gate (`worker.enrichment_provider != "disabled"` else `{"status":"DISABLED"}`), lane by `documents.byte_length` via `llm_extraction.policy.select_lane`, per-parent `source_hash`/`input_hash`, `_job_done("PARENT_ENRICHMENT", …)`, `_ensure_job`, `run_parent_enrichment_ticket`. Parents batched per local call (`compile_parents`). |
| `summary_worker_impl.py:279 _DISPATCH` | `+ "parent_enrichment.v1": _do_enrichment` |
| `workers/workers/summary_worker.py:21` | `+ "parent_enrichment.v1"` in the event-kind list |
| `control/control/tickets.py:43-46 STAGE_DAG` | `+ ("parent_enrichment", "parent_enrichment.v1", (), ())` AFTER `parent_summary`; `:52 NON_BLOCKING_STAGES` `+ "parent_enrichment"` |
| `control/control/fleet_autopilot.py:47` | summary tuple `+ "parent_enrichment"` |
| `control/control/reconciliation.py:72` | `+ "parent_enrichment": ("semantic_bundle",)` (re-run on bundle change) |
| `shared/polymath_shared/settings.py:146 WorkerSettings` | `+ enrichment_provider: "disabled"|"llm"`, `enrichment_profile: "qualification"|"production"`, `enrichment_max_parents_per_call` (local batch), `latent_retrieval_enabled: bool=False`, `latent_channels: str="parent_summary,abstraction,mechanism,affordance,pseudo_query"`, `latent_budget_ms: int=250`, `latent_top_k_per_channel: int=10`, `latent_max_parents: int=6` |
| `shared/polymath_shared/llm_extraction/client.py:271 _infer_batch_call` | system prompt becomes a parameter (`system_prompt=SYSTEM_PROMPT` default) so the enrichment compiler can batch through `/infer_batch` with its own prompt; ADD `complete_batched(items:[(id, system, user, max_tokens)]) -> [(id, raw, error_class)]` (no extraction `sanitize`). Extraction behaviour unchanged (default arg). |
| `workers/workers/project_qdrant_worker.py:295-303` | `+ LATENT_KIND_*` constants; `:308 _routing_rows` unchanged; ADD `_latent_rows()` call in `process_event` (`:600-660` routing block) under the SAME collection/contract with the §1.4 receipt guard; STALE cleanup: delete points for `parent_enrichments.status='STALE'` rows of the run's corpus, then mark them `INVALID` |
| `shared/polymath_shared/pass1.py:33-39` | `+ ARRIVAL_LATENT_LED = "LATENT_LED"` |
| `pass1.py:43 Pass1RetrievalPlan` | `+ latent_enabled: bool=False, latent_channels: tuple[str,...]=LATENT_KINDS, latent_top_k_per_channel: int=10, latent_max_parents: int=6, latent_budget_ms: int=250` (all defaults keep the frozen plan) |
| `pass1.py:350 pass1_retrieve` | `+ latent_search: Optional[Callable]=None` kwarg; after `resolve_sections` (`:246`) and before rescue: if `plan.latent_enabled and latent_search`, call `latent_seed_parents(...)`, append `LATENT_LED` section candidates for parents not already selected; record `trace["latent"] = {parents, channels, degraded, latency_ms}` |
| `shared/polymath_shared/hybrid.py:48 HybridRetrievalPlan` / `:152 hybrid_retrieve` | mirror the plan fields; pass `latent_search` through to `pass1_retrieve` |
| `shared/polymath_shared/retrieval_modes.py:35/42` | plans gain latent fields from settings + request override (`apply_latent(plan, enabled)`); `EXPOSED_MODES`/`DEFAULT_MODE`/`validate_mode` UNCHANGED (G1/G2 golden) |
| `shared/polymath_shared/query_shape.py:120 plan_for_query` | no change (documented: latent is a plan flag, not a shaping rule) |
| `orchestrator/orchestrator/api/fast.py:53 FastSearcher._search` | latency key `"latent"` for `latent_*` kinds; `:285 fast_retrieve` passes `latent_search=` (closure over `searcher`, `corpus_id`) when enabled; `meta.latent = trace["latent"]` |
| `orchestrator/orchestrator/api/hybrid.py:73 hybrid_fast_retrieve` | same wiring |
| `orchestrator/orchestrator/api/graph.py:71 graph_retrieve` | inherits via hybrid (no separate change) |
| `orchestrator/orchestrator/api/retrieve.py:35 RetrieveRequest`, `evidence.py:43`, `chat.py:46`, `ui.py:768 StreamChatRequest` | `+ latent: Optional[bool]=None` (None → settings default; explicit true/false → A/B) |
| `orchestrator/orchestrator/api/ui.py:1128-1195 chat_stream.generate()` | forward `latent`; `retrieval.latent` in the `answer` frame (`{enabled, parents, degraded}`) |
| `mcp_server/polymath_mcp.py:80/103` | `latent: bool|None` passthrough on `polymath_query` / `polymath_retrieve` |
| `frontend/src/api.ts:79 streamChat` (+ a toggle in the query bar) | optional `latent` in the body; surface `retrieval.latent.parents` count in the answer footer |
| `scripts/scaffold_polymath_v4.py TREE`, `scripts/README.md` | declare every new file / register the P6 script |

### 2.3 Not touched (by contract)
`semantic_chunker.py`, `retrieval_summaries.py`, `parent_summary.py`,
`build_parent_summary`, `evidence_assembly.py`, `answer_synthesis.py`,
`project_neo4j_worker.py`, `project_canonical_worker.py`, Neo4j schema,
`retrieval_modes.EXPOSED_MODES/DEFAULT_MODE`, `lane_liveness.py`.

## 3. Dependency graph (build order)

```
A  contract.py ── prompt.py ── gate.py ── compiler.py ──────────────┐
   (pure; tests only)                                               │
B  0041 migration ── runtime.py ── summary_worker_impl._do_enrichment│
   ── tickets/autopilot/reconciliation/worker kinds ── settings      │  needs A
   ── client.py complete_batched (system_prompt param)               │
C  projection.py ── project_qdrant_worker (_latent_rows, kinds, receipts, STALE cleanup)   needs B
D  seeds.py ── pass1/hybrid plan+engine ── retrieval_modes.apply_latent ── fast/hybrid wiring
   ── request flag on retrieve/evidence/chat/stream ── MCP/UI passthrough   needs C (data to hit) but unit-testable with fakes after A
E  eval/v5/latent_transfer (P6) ── channel attribution ── decision to keep/kill channels   needs D on a corpus with B+C run
F  (later, gated on E) Neo4j Mechanism/Abstraction/PseudoQuery nodes, ANALOG_OF/BRIDGES, cross-domain abstraction forest
```
External runtime deps: MLX batched server (`sidecars/local_extractor/batched_server.py`, `/infer_batch`) or Ollama daemon (cloud lane) — via the existing controller (`llm_controller_state`); embedder sidecar (`EmbedderClient`, batch 32, `project_qdrant_worker.py:122`); Qdrant routing collection under `NEURAL_EMBED_CONTRACT`; Postgres.

## 4. Phases with execution notes

### Phase A — contract, prompt, gate, compiler (offline; ~1 day)
1. Write `latent/contract.py`, `prompt.py`, `gate.py`, `compiler.py`.
2. `compiler.py` calls `LLMExtractionClient.complete_batched` (added in B, but A can stub it) — keep the compiler transport-agnostic: `compile_parents(complete: Callable[[list[PromptItem]], list[RawItem]], ...)`.
3. Tests: `test_latent_contract_gate.py` — every §1.2 rule with a hand-built packet; trimming to profile bounds; `source_hash` changes when any child text/heading/order changes and not otherwise; a truncated stream repairs to a REJECT (coverage incomplete), never a partial persist.
4. Exit: `pytest --noconftest tests/determinism/test_latent_contract_gate.py` green; no runtime file touched.

### Phase B — ingestion stage (~1–2 days)
1. Apply `0041_parent_enrichments.sql` (idempotent; extends the `summary_jobs.stage` CHECK — verify with `\d summary_jobs`).
2. `client.py`: make the system prompt a parameter of `_infer_batch_call`/`extract_batched` (default unchanged) and add `complete_batched`. Run the 61 existing LLM tests — must stay green (extraction byte-identical).
3. `latent/runtime.py`: copy the transaction shape of `run_parent_summary_ticket` (claim → EXISTING short-circuit on `input_hash` → compile → gate → INSERT `summary_artifacts` (stage `PARENT_ENRICHMENT` or `PARENT_ENRICHMENT_REJECTED`) → `UPDATE parent_enrichments SET status='STALE' WHERE parent_id=%s AND source_hash<>%s AND status='READY'` → INSERT READY row → job COMPLETE/FAILED).
4. `summary_worker_impl._do_enrichment` + `_parents_of_docs_rich`; register the stage in `tickets.py`, `fleet_autopilot.py`, `reconciliation.py`, `summary_worker.py`; settings fields.
5. Lane: `select_lane(documents.byte_length)` per document — ≤ threshold → local `/infer_batch` with `enrichment_max_parents_per_call` prompts per call (each prompt ≈ parent text ≤ ~3K tokens + facts/entities; budget `max_tokens` 1,200 qualification / 1,800 production); above threshold → cloud one parent per call. The AIMD batch budget + limiter already govern both.
6. Exit: on a canary corpus, `SELECT status, count(*) FROM parent_enrichments GROUP BY 1` shows READY for every parent with ≥1 child; `summary_jobs` rows COMPLETE; a second run creates zero new artifacts (idempotent); killing the LLM sidecar leaves `parent_summary` COMPLETE and the corpus `query_ready` (D8 proof).

### Phase C — projection (~0.5 day)
1. `latent/projection.py` + Qdrant worker changes (§1.4); STALE → delete points → INVALID.
2. Exit: point count for the corpus = Σ per-READY-enrichment (1+1+|mech|+|aff|+|pq|); `projection_receipts` rows per point; re-running `project_qdrant` schedules zero embeddings (incremental guard); regenerating one parent after editing a child replaces exactly that parent's points.

### Phase D — query lane (~1–2 days)
1. `latent/seeds.py`; `pass1`/`hybrid` plan fields + `latent_search` kwarg + `LATENT_LED`; `retrieval_modes.apply_latent`; `fast.py`/`hybrid.py` wiring; request flag on all four routes; MCP + UI passthrough.
2. Determinism proof: with `latent_enabled=False` (default) every existing test in `test_pass1.py`, `test_hybrid.py`, `test_retrieval_invariants.py`, `test_depth_policy.py`, `test_batched_pass1.py` passes unchanged and `Pass1Result` is byte-identical (new test asserts `dataclasses.asdict` equality against a frozen fixture).
3. Fail-open proof (`test_latent_seeds.py`): `routing_search` raising, sleeping past budget, returning unknown payloads → `parents=[]`, `degraded` set, no exception, no HTTP change.
4. Exit: `POST /retrieve {"mode":"FAST","latent":true}` returns `meta.latent.parents` on the canary corpus; `/chat/stream` answer frame carries `retrieval.latent`; `latent:false` output equals pre-change output.

### Phase E — P6 evaluation + channel decision (~1–2 days, owner-authored cases)
1. Author ≥20 `cases.yaml` entries on the cyber corpus (+ any cross-domain books re-admitted for this purpose): each with `latent_domains`, `acceptable_mechanisms`, `forbidden_shortcuts`, and expected parent/document ids.
2. Metrics: LatentRecall@10/@20, CrossDomainRecall@K, MechanismRecall@K, UniqueDomainCount@K, BridgePrecision@K, FalseAnalogyRate (labelled negatives: parents that share surface vocabulary but not mechanism), AnswerLift with vs without (judge: existing deterministic answer path + owner rating).
3. Attribution table per channel (unique relevant hits, overlap). Kill rule: a channel whose unique relevant hits ≤ 5% of the total across the suite is disabled by default (`latent_channels`) and its vectors are no longer projected.
4. Exit: report `docs/wiki/plans/LATENT-TRANSFER-P6-RESULTS.md`; owner GO/NO-GO to flip `latent_retrieval_enabled=true` per corpus.

### Phase F — graph layer (NOT in this plan's scope; recorded for sequencing)
Mechanism/Abstraction/PseudoQuery nodes with `REALIZES_MECHANISM / ABSTRACTS / ANSWERS / ANALOG_OF / BRIDGES` edges; delexicalized mechanism canonicalization; cross-document abstraction forest (global clusters over `latent_abstraction` vectors); deterministic PPR/hop expansion seeded by latent parents. Enters only if P6 shows the vector-only sidecar leaves cross-domain recall on the table.

## 5. Flags, rollout, rollback
- Ingestion: `POLYMATH_WORKER_ENRICHMENT_PROVIDER=disabled` (default) → stage completes as `DISABLED` (no LLM call, no rows). `=llm` turns it on; `POLYMATH_WORKER_ENRICHMENT_PROFILE=qualification|production`.
- Query: `POLYMATH_WORKER_LATENT_RETRIEVAL_ENABLED=false` (default); per-channel list; request `latent` overrides for A/B; budget `POLYMATH_WORKER_LATENT_BUDGET_MS=250`.
- Rollback = flip both flags off: zero code path difference (frozen plans), rows/points stay inert. Hard rollback = `DELETE FROM parent_enrichments; DELETE points WHERE representation_kind LIKE 'latent_%'` — nothing else references them (D10).
- Cost visibility: enrichment calls land in the same `llm_extraction`-style receipts (tokens, wall, lane, `limiter_effective`, `batch_tokens_cap`) under the summary stage artifact.

## 6. Test matrix (what must be green before each phase merges)
| Layer | Tests | Runs without DB? |
|---|---|---|
| A contract/gate | `test_latent_contract_gate.py` | yes (`--noconftest`) |
| B runtime | `test_latent_enrichment_stage.py` (ticket, idempotency, STALE), existing `test_summary_workers.py`, `test_summary_idempotency.py`, 61 LLM tests | needs DB for the first |
| C projection | `test_latent_projection.py`, existing `test_summary_projection.py` | yes |
| D query | `test_latent_seeds.py`, `test_pass1_latent.py`, existing pass1/hybrid/invariants/depth/batched suites, `tests/integration/test_r1c_fast_endpoint.py`, `test_chat_e2e.py` | mixed |
| E eval | `p6_latent_transfer_recall.py` on the canary corpus | live stack |

## 7. Open decisions (owner) — defaults the plan assumes until overridden
1. **Lane for enrichment**: same 300 KB byte rule as extraction (local ≤ threshold, cloud above). Default assumed: yes.
2. **Exposure**: request flag `latent` + settings default, modes unchanged (not a new `FAST_LATENT` mode) — keeps G1/G2 golden contracts and makes A/B one boolean. Default assumed: flag.
3. **`/ask` and `extract{}`**: `/ask` (stored-objects route, `ask.py:219`) does NOT read `parent_enrichments` in this plan; `extract{}` is stored for Phase F / future stored-object answers. Default assumed: not consumed.
4. **Enrichment for `__orphan__` children (no parent_id)**: skipped (`parent_id IS NOT NULL`), same as parent summaries.

## 8. Exit criteria for the whole layer
- Disabled: every existing retrieval/summary/projection test unchanged; `plan_version`s unchanged; zero extra Qdrant points.
- Enabled on the canary corpus: ≥95% of parents READY; P6 LatentRecall@10 ≥ baseline + 0.15 absolute on the cross-domain subset; FalseAnalogyRate ≤ 10%; P95 latent lane latency ≤ 250 ms; zero 5xx attributable to the lane.
