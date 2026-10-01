# flow: chat-turn
A chat turn end to end: the browser posts /chat/stream (modes FAST, HYBRID, GRAPH, WILDCARD, GNN), the query compiler plans subqueries and facets, retrieval composes evidence, the model synthesises a cited answer, the receipt is written, the SSE frames reach the UI.

Anchors: `ui.py` = `orchestrator/orchestrator/api/ui.py`. Source excerpt ends mid-function at ui.py:4510; the synthesis call site is beyond it.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `chat_stream` wraps `chat_events(req)` in a `StreamingResponse`, `media_type="text/event-stream"`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | ui.py:4778-4783 [DERIVED] | `StreamChatRequest` -> SSE byte stream | transport only; logic errors surface as frames |
| 2 | Eager validation before the first frame: non-empty message; `mode` upper-cased, `VECTOR`→`FAST`, allowed set `("FAST", "HYBRID", "GRAPH", "ASK", "WILDCARD", "GNN")`; synthesizer `ollama:`/`litellm:` prefix or `deterministic-template-v3`; `parse_scope` | ui.py:3870-3895 [DERIVED] | req -> query, ui_mode, synth, _role_scope | typed `HTTPException(422, ...)`: `message is required`, `unknown_mode`, `unknown_synthesizer`, `invalid_scope` |
| 3 | `scope` phase: `resolve_http_scope(conn, req)` inside `tx()`; emits `scope_ok` with `mode`, `corpora` | ui.py:3930-3935 [DERIVED] | req + conn -> `scope.corpus_ids`, `scope.mode` | untyped exception inside the generator |
| 4 | Compiler dispatch: `_compiler_flag(req.compiler)`; any non-`off` submits `_compile_chat_plan` on `ThreadPoolExecutor(max_workers=1)` with `query, req.history, _corpora, session_key, titles_rank, corpus_explorer`; `on` joins immediately (serial stage 0), `shadow` runs beside retrieval | ui.py:3961-3974 [DERIVED] | query + history + corpora -> `ChatPlan` future | `shadow` adds no latency; `on` blocks on compile |
| 5 | Plan applied (`on` only): `evidence_only` -> `plan_for_evidence_route`; `require_retrieval` -> override rule `"corpus_chat:retrieval_required"`; `_skip_retrieval = (not _plan.retrieval_required) and ui_mode != "ASK"`; `_retrieval_text = retrieval_text_for(_plan)`; firing receipt stamped; `compile` phase frame (task_type, queries, fallback, wall_ms, scout) | ui.py:3975-3993 [DERIVED] | ChatPlan -> retrieval decision + `_plan_receipt` | compiler `fallback` is shown in the frame, turn continues |
| 6 | Shadow join `_join_plan`: `_plan_future.result(timeout=8.0)`; any exception -> `fallback_plan(query, reason=f"join_failed:{type(exc).__name__}")` | ui.py:3995-4009 [DERIVED] | future -> `_plan`, `_plan_receipt` | silent fallback to `fallback_plan` |
| 7 | `ASK` mode: `ask(AskRequest(...))` over stored objects; `ask_done` frame with counts; `answer` frame kind `"ask"`; `done`; return | ui.py:4011-4035 [DERIVED] | query -> stored object result | bypasses corpus retrieval entirely |
| 8 | Single-corpus guard: `len(scope.corpus_ids) != 1` -> SSE `error` frame `mode_requires_single_corpus`, receipt with error, return | ui.py:4037-4045 [DERIVED] | scope -> `corpus_id` | error frame mid-stream (status already sent; see ui.py:3860-3862) |
| 9 | Engine flag: `_rflag = chat_retrieval_flag(req.retrieval)`; `_v2_mode = _rflag in ("v2", "v2-single") and not req.utility`; GNN + not v2 -> `HTTPException(422, gnn_requires_v2)`; graph bounds from `_plan.graph_useful` (compiler off / no plan / fallback keeps `True`); skeleton routes force GRAPH | ui.py:4063-4078 [DERIVED] | req.retrieval, req.utility, plan -> `_v2_mode`, `_graph_useful` | 422 `gnn_requires_v2` |
| 10 | Skip-retrieval turn (`evidence_policy=conversation`): `evidence_rows = []`, empty `fast` shape, `retrieve_skipped` frame | ui.py:4079-4090 [DERIVED] | plan verdict -> no corpus search | by design: answered from conversation |
| 11 | GRAPH v1 (rollback boundary `retrieval: v1` / `latent`): `graph_retrieve(_retrieval_text, corpus_id, latent, utility)`; `fast` built from `g` meta/trace; evidence rows from documents->sections->evidence; `retrieve_done`, `graph`, `graph_done` frames | ui.py:4091-4135 [DERIVED] | query -> fast, graph_facts, summaries | v1 engine behaviour |
| 12 | v2 budget: `_apply_intent(plan.intent, default_budget())` when intent policy on; `req.latent` -> `_replace(_budget, latent_enabled=True)` (lane D); `_skeleton_routes(_budget, mode, plan)`; `_graph_assist` from `policy_for(intent).graph` else `"off"`; PROBE-GATE-V1 when `probe_gate_floor > 0` gates non-PRIMARY queries via `gate_probes(..., _cr_mod._rerank_children, floor=...)` | ui.py:4140-4176 [DERIVED] | intent + knobs -> budget, `_gated_out` | probe gate is fail-open, one cross-encoder call |
| 13 | `chat_retrieve_mode("VECTOR" if ui_mode == "FAST" else ui_mode, _retrieval_text, corpus_id, ...)` with `subqueries` tuples `(id, type, query, weight, origin, derived_from)` minus gated ids, `latent_bridge_ids`, `facets`, `question` (WILDCARD only), `exact_terms`; afterwards: probe-gate receipt into trace, `_aspects`/`_weak`, facet coverage with `floor=float(getattr(_budget, "aspect_weak_floor", 0.5))`, `wildcard_lane`, `graph_facts` | ui.py:4177-4214 [DERIVED] | everything -> `fast` | engine degradation receipts ride `fast["meta"]` |
| 14 | v1 engines: FAST -> `fast_retrieve`; WILDCARD -> `wildcard_retrieve` (bridges on `fast["wildcard"]`, never the evidence list); else `hybrid_fast_retrieve(..., latent=req.latent, utility=req.utility)` | ui.py:4215-4228 [DERIVED] | query -> fast | v1 rollback path |
| 15 | P10 evidence resolution (bounded round 2): flag on + plan + mode in `(FAST, HYBRID)` + aspects -> `_maybe_resolve(plan, fast, aspects, weak, resolve_retrieve)`; merged into `fast["evidence"]` before the bundle | ui.py:4231-4242 [DERIVED] | fast -> `_resolution` | except -> `_resolution = None`; never breaks the turn |
| 16 | Latent second pass `_apply_latent_selection(fast, _plan, _retrieval_text, mode=ui_mode)` (runs before CA3/CA4); `evidence_rows = _evidence_rows(fast["evidence"])` keeping role + latent seat; `retrieve_done` frame; GRAPH and `wildcard` frames; `_arrivals` per chunk | ui.py:4243-4278 [DERIVED] | fast -> evidence_rows, `_latent_receipt` | — |
| 17 | Summaries + orientation: SQL `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)` over `parent_ids`; doc_ids fall back to evidence doc_ids; `_load_orientation(conn, doc_ids, parent_ids)` | ui.py:4279-4302 [DERIVED] | parent_ids -> section_summaries, orientation | orientation except -> `{"docs": [], "maps": []}` |
| 18 | CA3 (`POLYMATH_CHAT_CONSTRAINT_ALIGN=1`): `align_evidence_for_constraints` reorders reranked evidence by resolved constraint strength, no score added; CA4 (`POLYMATH_CHAT_EVIDENCE_ROLES=1`): `grade_evidence` -> `_grades_by_chunk`, `_epistemic` | ui.py:4304-4332 [DERIVED] | evidence + plan -> ordered rows, grades | default-off => byte-identical |
| 19 | Bundle: `assemble_evidence_bundle(query, graph_facts, evidence_rows, evidence_order, resolve_fact/evidence/entity/document/chunk, document_summaries, section_summaries, unresolved=stale)` | ui.py:4334-4354 [DERIVED] | rows -> bundle | `AssemblyError` -> SSE `error` frame (`error_code` = exception class name), receipt with error, return |
| 20 | Bundle enrichment: `evidence_roles`, `evidence_latent` (seat + via origin_query), `evidence_paths` (query_ids), `facets_uncovered`, `support_roles`+`epistemic`, `orientation`, `derived_insights = wildcard_lane`; CARRY-V2: `_carry_candidates` + `_admit_carry` — artifact mode on skip-retrieval turns (scorer constant `1.0`, `floor=0.0`, `cap=_CARRY_ARTIFACT_CAP`) vs judged mode against `resolved_request`; `carry` phase frame | ui.py:4356-4399 [DERIVED] | bundle + carry_context -> enriched bundle | carry items extend `evidence_bundle`; accounting in `_carry_meta` |
| 21 | Legend + inventory + receipt: `_evidence_legend`; `_render_derived(..., require_proof=_synth_contract_enabled())`, `_render_relations`; `assemble_done`; `chunk_inventory` rows (locator, doc_id, kind, carried, preview `[:220]`, source_name, title, heading_path, human_locator); `retrieval` dict (engine, arrivals, lane_sizes, `gnn` only in GNN mode, `degraded = _merged_degraded(fast, stale)`); `evidence_only` branch cuts the pipeline here | ui.py:4400-4510 [DERIVED] | bundle -> UI payload | source excerpt ends at ui.py:4510 |
| 22 | SYNTHESIS-V2 consumes the bundle via `grounded_answer` (imported at generator start) and emits the remaining frames `token`, `reasoning`, `answer`, `done`; `/chat` drains the same frames through `run_chat` | ui.py:3899, ui.py:3853-3856 [DERIVED] for import + docstring; call site beyond excerpt [INFERRED: docstring names the frames and stage] | bundle -> cited answer frames | not visible in this excerpt |

## state written

- Firing receipt: one per turn, exactly one cause per miss, written to the JSONL rate ledger via `polymath_shared.corpus_explore_firing.record` — ui.py:3946-3958 [DERIVED]
- Turn receipt: built once by `_receipt_payload` for every turn that ran, written through the transport sink (default `_default_receipt_sink(route)`, `meta.route` = route); also written on the error ends at ui.py:4043-4044 and ui.py:4352-4353 — ui.py:3864-3867, ui.py:3923-3928 [DERIVED]
- Postgres read (no write visible in excerpt): `chunks` table columns `chunk_id, doc_id, summary` — ui.py:4287-4291 [DERIVED]
- In-memory artifacts: the evidence `bundle` — ui.py:4337-4348; the `retrieval` receipt dict — ui.py:4434-4507 [DERIVED]
- Qdrant / file writes: not visible in this excerpt.

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `req.compiler` (`off` \| `shadow` \| `on`) | not shown (resolved by `_compiler_flag`) | `shadow` = compile beside retrieval, receipt only; `on` = serial stage 0 owning the skip decision | ui.py:3941, ui.py:3961-3974 [DERIVED] |
| `req.retrieval` via `chat_retrieval_flag` | not shown | `"v2"`/`"v2-single"` + not `req.utility` -> v2 composition; otherwise v1 engines | ui.py:4063-4068 [DERIVED] |
| `req.latent` (✨) | absent | no longer drops to v1; sets `latent_enabled=True` (lane D) in the v2 budget | ui.py:4066-4067, ui.py:4154-4155 [DERIVED] |
| `req.utility` | absent | v1 plan knob; forces the v1 engines even under a v2 flag | ui.py:4065-4068 [DERIVED] |
| `POLYMATH_CHAT_RESOLUTION` | `"0"` | P10 bounded round-2 resolution, fail-open, at most one round | ui.py:4235 [DERIVED] |
| `POLYMATH_CHAT_CONSTRAINT_ALIGN` | `"0"` | CA3 post-rerank portfolio reorder (no score added/tuned) | ui.py:4309 [DERIVED] |
| `POLYMATH_CHAT_EVIDENCE_ROLES` | `"0"` | CA4 grading + epistemic state on the bundle | ui.py:4329 [DERIVED] |
| `POLYMATH_CHAT_SYNTH_ROLES` | default-off | `evidence_roles` rides the bundle for role-aware synthesis presentation | ui.py:4356-4358 [DERIVED] |
| intent policy (`intent_policy_enabled`) | default off | intent->budget policy; byte-identical when off; `req.latent` always wins the latent toggle | ui.py:4150-4153 [DERIVED] |
| skeleton routes (`skeleton_routes.enabled`) | not shown | GRAPH mode always runs the hop; budget doors follow plan + mode | ui.py:4076-4078, ui.py:4156-4158 [DERIVED] |
| `budget.probe_gate_floor` | `0.0` | PROBE-GATE-V1; FAST/GNN never gated; needs compiler on + v2 | ui.py:4164-4176 [DERIVED] |
| `req.evidence_only` / `req.require_retrieval` | absent | evidence route / forced-retrieval override on the plan | ui.py:3976-3980, ui.py:4509 [DERIVED] |
| `req.corpus_explorer` | absent | passed to the compiler; recorded as `requested` in the firing receipt | ui.py:3951, ui.py:3970 [DERIVED] |

## failure modes

1. 422 before any frame — empty message, unknown mode, unknown synthesizer, malformed scope — eager validation, ui.py:3870-3895.
2. 422 `gnn_requires_v2` — GNN mode on the v1 engines or a utility turn — ui.py:4069-4071.
3. SSE `error` frame `mode_requires_single_corpus` mid-stream — non-ASK mode with `len(scope.corpus_ids) != 1` — ui.py:4038-4045.
4. SSE `error` frame with `error_code` = `AssemblyError` subclass name — bundle assembly failed — ui.py:4349-4354.
5. Silent fallback: shadow compile join fails or times out (`timeout=8.0`) -> `fallback_plan` with `join_failed:*` reason; the `compile` frame still emits — ui.py:3999-4003, ui.py:3988.
6. Silent fallback: receipt sink exception swallowed — the turn never breaks on receipting — ui.py:3925-3928.
7. Silent fallback: firing-ledger exception swallowed — ui.py:3956-3958.
8. Silent fallback: P10 resolution exception -> `_resolution = None`, evidence unchanged — ui.py:4240-4242.
9. Silent fallback: orientation load exception -> empty `{"docs": [], "maps": []}` — ui.py:4296-4298.
10. Degraded lanes still answer (e.g. reranker parked behind extraction); the `degraded` list in the answer event / receipt says why — never silent — ui.py:4499-4506.
11. Turn answers with zero retrieval — plan said `retrieval_required` false; `retrieve_skipped` frame is the only signal — ui.py:4079-4090.

## invariants

- INVARIANT: same request => same plan, same evidence ids, same synthesis contract on every route (`/chat/stream` frames; `/chat` drains via `run_chat`) — ui.py:3854-3856 [DERIVED]
- INVARIANT: request validation raises typed HTTPExceptions before the first frame — ui.py:3858-3862 [DERIVED]
- INVARIANT: exactly one receipt per turn that ran, including the error ends; the receipt writer never breaks a turn — ui.py:3864-3867, ui.py:3923-3928, ui.py:4043-4044, ui.py:4352-4353 [DERIVED]
- INVARIANT: exactly one firing receipt per turn (exactly one cause per miss) — ui.py:3946-3948 [DERIVED]
- INVARIANT: WILDCARD bridges never displace answer evidence; they ride `fast["wildcard"]` / the separate `wildcard` lane — ui.py:4142-4144, ui.py:4219-4224, ui.py:4451-4452 [DERIVED]
- INVARIANT: additive stages (receipt, firing ledger, P10 resolution, orientation) are fail-open — ui.py:3925-3928, ui.py:3956-3958, ui.py:4240-4242, ui.py:4296-4298 [DERIVED]
- INVARIANT: default-off flags (CA3, CA4, intent policy, synth roles) leave the turn byte-identical — ui.py:4308, ui.py:4332, ui.py:4150-4152, ui.py:4358 [DERIVED]
- INVARIANT: non-ASK retrieval modes run over exactly one corpus — ui.py:4038-4039 [DERIVED]
- INVARIANT: every final candidate carries lane provenance (`arrivals`) — ui.py:4460-4463 [DERIVED]

## VERIFY

```verify
grep -Fq 'async def chat_stream(req: StreamChatRequest) -> StreamingResponse:' orchestrator/orchestrator/api/ui.py
grep -Fq 'media_type="text/event-stream"' orchestrator/orchestrator/api/ui.py
grep -Fq 'mode_requires_single_corpus' orchestrator/orchestrator/api/ui.py
grep -Fq 'gnn_requires_v2' orchestrator/orchestrator/api/ui.py
grep -Eq 'POLYMATH_CHAT_(RESOLUTION|CONSTRAINT_ALIGN|EVIDENCE_ROLES)' orchestrator/orchestrator/api/ui.py
grep -Fq 'SELECT chunk_id, doc_id, summary FROM chunks ' orchestrator/orchestrator/api/ui.py
grep -Fq 'timeout=8.0' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'HTTPException(422' orchestrator/orchestrator/api/ui.py)" -ge 5
```
