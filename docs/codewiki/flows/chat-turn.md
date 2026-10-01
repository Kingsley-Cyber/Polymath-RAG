# flow: chat-turn
A chat turn end to end: the browser posts /chat/stream (modes FAST, HYBRID, GRAPH, WILDCARD, GNN — plus ASK), the query compiler plans subqueries and facets, retrieval composes evidence, the model synthesises a cited answer, the receipt is written, the SSE frames reach the UI.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `chat_stream` wraps `chat_events(req)` in a `StreamingResponse`, `media_type="text/event-stream"`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | orchestrator/orchestrator/api/ui.py:4758-4763 | `StreamChatRequest` -> SSE frame stream (`phase`, `token`, `reasoning`, `answer`, `done`, `error`) | transport only; validation is downstream |
| 2 | Eager validation before the first frame: `message` required; mode whitelist `FAST`/`HYBRID`/`GRAPH`/`ASK`/`WILDCARD`/`GNN` with alias `VECTOR`->`FAST`; synthesizer must be `ollama:`/`litellm:` prefixed or `deterministic-template-v3`; `parse_scope` once; receipt sink bound | ui.py:3852-3878 | req fields -> validated `query`, `ui_mode`, `synth`, `_role_scope`, `sink` | typed `HTTPException` 422: `message is required` / `unknown_mode` / `unknown_synthesizer` / `invalid_scope` |
| 3 | `scope` phase: `resolve_http_scope(conn, req)` inside `tx()`; `scope_ok` frame carries `mode` + `corpora` | ui.py:3912-3917 | req -> `scope.mode`, `scope.corpus_ids` | not shown in slice |
| 4 | Compiler dispatch: `_compiler_flag(req.compiler)` in off/shadow/on; `!= "off"` submits `_compile_chat_plan(query, req.history, corpora, session_key, titles_rank, corpus_explorer, scope kwargs)` on `ThreadPoolExecutor(max_workers=1)` | ui.py:3919-3952 | query + history + corpora -> plan future | shadow runs beside retrieval (no added latency); failures surface only at join (row 5) |
| 5 | `on`: serial join, `_mark("compile")`; `evidence_only` / `require_retrieval` overrides via `plan_for_evidence_route`; `_skip_retrieval` decision (COMPILED-RETRIEVAL-V1); `_stamp_firing()` writes the turn's ONE firing receipt; `compile` frame. Shadow joins later via `_join_plan` | ui.py:3953-3991 | plan -> `task_type`, `queries`, `facets`, `retrieval_required`, `graph_useful`, `exact_terms`, `resolved_request`, `explicit_constraints`, `intent` | join failure after `timeout=8.0` -> `fallback_plan(query, reason="join_failed:<ExcType>")` (silent fallback); fallback announced in the `compile` frame |
| 6 | ASK mode: `ask(AskRequest(...))` over stored knowledge objects; `ask_done`; `answer` frame `kind: "ask"`; `done`; return | ui.py:3993-4017 | question -> object counts per kind + `route` | returns before retrieval; errors not shown in slice |
| 7 | Corpus guard: non-ASK modes need `len(scope.corpus_ids) == 1` | ui.py:4019-4027 | scope -> single `corpus_id` | SSE `error` frame `mode_requires_single_corpus` + receipt `error`; HTTP status can no longer change |
| 8 | Engine flag: `_rflag = chat_retrieval_flag(req.retrieval)`; `_v2_mode = _rflag in ("v2", "v2-single") and not req.utility`; GNN requires v2; `_graph_useful` follows the plan verdict (skeleton routes force `True` on GRAPH) | ui.py:4045-4060 | `req.retrieval`, `req.utility`, plan -> `_v2_mode`, `_graph_useful` | `HTTPException` 422 `gnn_requires_v2` raised inside the generator |
| 9 | `_skip_retrieval` path (evidence_policy=conversation): corpus not searched, empty evidence, `retrieve_skipped` frame | ui.py:4061-4072 | plan verdict -> `evidence_rows=[]`, empty `fast` | by design; carried evidence still admitted later in artifact mode (row 19) |
| 10 | GRAPH on v1 engines (rollback boundary `retrieval: v1` / `latent`): `graph_retrieve(...)`; `fast` rebuilt from `meta`/`trace`; evidence rows from `documents -> sections -> evidence`; `graph_facts`; doc/section summaries | ui.py:4073-4117 | retrieval text -> evidence rows + graph facts + summaries | lane degradations ride `meta`, not exceptions |
| 11 | v2 composition (MODE-COMPOSITION-V1): budget = intent policy + `req.latent` -> `latent_enabled=True` (lane D) + skeleton routes; PROBE-GATE-V1 drops non-PRIMARY probes missing `resolved_request` (one `_rerank_children` call, fail-open); `chat_retrieve_mode(...)` with `exact_terms`, typed `subqueries` (origin/derived_from lineage), `latent_bridge_ids` (`LATENT_ORIGINS`), `facets`, WILDCARD `question`; `_facet_coverage` verdict | ui.py:4122-4187 | plan + budget -> fused `fast`, `_aspects`, `_weak`, `_facet_cov`, `probe_gate` receipt in `fast["trace"]` | gated probes dropped before spending retrieval; FAST/GNN never gated (budget floor) |
| 12 | v1 lanes: FAST -> `fast_retrieve`; WILDCARD -> `wildcard_retrieve` (evidence IS FAST, bridges ride the separate `wildcard` lane); else `hybrid_fast_retrieve(latent, utility)` | ui.py:4197-4210 | retrieval text + corpus -> `fast` | wildcard never displaces answer evidence |
| 13 | P10 evidence-resolution: `POLYMATH_CHAT_RESOLUTION=1` -> `_maybe_resolve(_plan, fast, _aspects, _weak, retriever)`; bounded round 2, same engine, merged into `fast["evidence"]` before the bundle | ui.py:4213-4224 | weak aspects -> round-2 evidence + `_resolution` receipt | fail-open: any exception -> `_resolution = None` |
| 14 | WLK2C latent second pass `_apply_latent_selection` (runs before CA3/CA4, reassigns `fast["evidence"]`); `evidence_rows = _evidence_rows(fast["evidence"])`; `retrieve_done` frame; GRAPH `graph`/`graph_done` frames (bounds, seeds); arrivals map; `wildcard` frame | ui.py:4226-4260 | fast -> evidence rows, `_arrivals`, `wildcard_lane`, `latent_meta` | degradations reported in the frame, never raised |
| 15 | Summaries + orientation: `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)` over section parents; `_load_orientation(conn, doc_ids, parent_ids)` | ui.py:4261-4284 | parent_ids -> `section_summaries`, `orientation` docs/maps | orientation exception -> `{"docs": [], "maps": []}` (silent) |
| 16 | CA3 constraint alignment: `POLYMATH_CHAT_CONSTRAINT_ALIGN=1` + resolved constraints -> `align_evidence_for_constraints` reorders reranked evidence by strength; semantic order kept within each portfolio | ui.py:4286-4304 | evidence rows + `explicit_constraints` -> reordered rows + `_constraint_align` receipt | flag off or no resolved constraint -> byte-identical |
| 17 | CA4 grading: `POLYMATH_CHAT_EVIDENCE_ROLES=1` -> `grade_evidence(fast["evidence"], _plan)` | ui.py:4306-4314 | evidence + plan -> `_grades_by_chunk` (DIRECT/PARTIAL/RELATED), `_epistemic` | flag off -> no grades, byte-identical |
| 18 | Bundle assembly: `assemble_evidence_bundle(query, graph_facts, evidence_rows, evidence_order, resolvers, doc/section summaries, unresolved=stale)` | ui.py:4316-4336 | all evidence -> `bundle` (+ `stale` list) | `AssemblyError` -> SSE `error` frame (`error_code` = class name, `message[:300]`) + receipt, turn ends |
| 19 | Bundle enrichment: `evidence_roles`, `evidence_latent` (seat COMPLEMENTARY/DIVERGENT + via origin_query), `evidence_paths`, `facets_uncovered`, `support_roles`/`epistemic`, `orientation`, `derived_insights`; CARRY-V2 admission — `judged` mode scored against the resolved request, or `artifact` mode when skipping retrieval (scorer all `1.0`, `floor=0.0`, `cap=_CARRY_ARTIFACT_CAP`); legend; `assemble_done` frame | ui.py:4338-4387 | bundle + `req.carry_context` -> enriched bundle + `_carry_meta` | artifact mode admits without relevance gate (by design); carry never displaces corpus evidence |
| 20 | UI receipts: chunk inventory (`locator`, `preview[:220]`, `source_name`, `title`, `heading_path`, `human_locator`) and the `retrieval` dict (`engine`, `arrivals`, `lane_sizes`, `gnn`, `latency_ms`, `aspects`, `facets_covered`/`facets_uncovered`, `explicit_constraints`, `constraint_alignment`, `epistemic`, `latent_selection`, `profile_yield`, `resolution`, `composition`, `degraded`) | ui.py:4389-4489 | bundle + fast -> `retrieval` receipt payload | `degraded` list always says WHY evidence differs (never silent) |
| 21 | `evidence_only` short-circuit: REASONING-BOUNDARY-V1, the evidence boundary | ui.py:4491-4492 | retrieval dict -> evidence-only output | slice ends here; downstream not in SOURCE |
| 22 | Synthesis + close: SYNTHESIS-V2 via `grounded_answer`; `token`/`reasoning`/`answer`/`done` frames per the CHAT-RUNTIME-V1 contract; then the turn's one receipt `sink(_receipt_payload(req, question=query, scope=scope, route=route, **kw))` | ui.py:3834-3838, 3881, 3905-3910 | bundle -> answer frames + receipt (keys `wall_ms`, `ui_mode`, `answer`, `meta`, `error` visible at 4025-4026, 4334-4335) | receipt writer wrapped in `except Exception: pass` — never breaks a turn; frame emission code past the slice cap [INFERRED: contract stated in docstring, code beyond 4492 not shown] |

## state written

- SSE frame stream to the browser — the transport itself; frame set `phase`/`token`/`reasoning`/`answer`/`done`/`error` — ui.py:4757-4763, 3834-3836 [DERIVED]
- Firing receipt: exactly one per turn, appended to the JSONL rate ledger via `polymath_shared.corpus_explore_firing.record` — ui.py:3928-3938 [DERIVED]
- Turn receipt: one per turn that ran, `sink(_receipt_payload(req, question=query, scope=scope, route=route, **kw))`; default `_default_receipt_sink(route)` adds the transport's `kind` and `client`; storage backend not in slice — ui.py:3846-3851, 3905-3910 [DERIVED]
- Postgres reads on this path (no writes visible in slice): `chunks` (`chunk_id`, `doc_id`, `summary`) at ui.py:4269-4273; `tx()` connection for scope at ui.py:3913-3914 [DERIVED]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `compiler` (request) | not shown; `off` skips compile entirely | `shadow` = plan receipted beside retrieval, changes nothing downstream; `on` = serial stage 0 driving skip-retrieval, subqueries, facets | ui.py:3919-3921, 3943-3969 |
| `retrieval` (request, via `chat_retrieval_flag`) | not shown | `v2`/`v2-single` -> composition on the v2 engine; `v1`/`latent` keep the v1 engines (rollback boundary) | ui.py:4045-4050 |
| `utility` (request) | not shown | v1 plan knob; forces `_v2_mode` False, blocks GNN | ui.py:4049-4053 |
| `latent` (request, ✨) | not shown | no longer drops to v1; enables lane D (`latent_enabled=True`) in the v2 budget | ui.py:4048-4049, 4136-4137 |
| `POLYMATH_CHAT_RESOLUTION` (env) | `"0"` | bounded round-2 evidence resolution on FAST/HYBRID | ui.py:4217-4218 |
| `POLYMATH_CHAT_CONSTRAINT_ALIGN` (env) | `"0"` | CA3 post-rerank portfolio reorder on resolved constraints | ui.py:4291-4293 |
| `POLYMATH_CHAT_EVIDENCE_ROLES` (env) | `"0"` | CA4 DIRECT/PARTIAL/RELATED grading + epistemic state on the bundle | ui.py:4311-4313 |
| `POLYMATH_CHAT_SYNTH_ROLES` (env, named in comment) | default-off per comment | role-aware synthesis reads `bundle["evidence_roles"]`; off => grounded prompt byte-identical | ui.py:4338-4342 |
| intent policy (`intent_policy_enabled`) | default off | intent -> budget policy; byte-identical when off | ui.py:4132-4135 |
| skeleton routes (`skeleton_routes.enabled`) | default off | skeleton doors follow plan + mode; GRAPH forces `_graph_useful = True` | ui.py:4058-4060, 4139-4141 |
| `probe_gate_floor` (budget field) | `0.0` (off) | one cross-encoder call per non-PRIMARY probe; failing probes dropped before retrieval; FAST/GNN never gated | ui.py:4146-4158 |
| `evidence_only` (request) | not shown | plan forced onto the evidence route; turn ends at the evidence boundary | ui.py:3958-3960, 4491-4492 |
| `require_retrieval` (request) | not shown | `plan_for_evidence_route(..., override_rule="corpus_chat:retrieval_required")` | ui.py:3961-3962 |
| `carry_context` (request) | not shown (empty -> skip) | CARRY-V2 admission: `judged` (scored vs resolved request) or `artifact` (all `1.0`, `floor=0.0`, cap) | ui.py:4360-4374 |

## failure modes

1. Symptom: 422 JSON before any frame. Cause: empty `message`, mode outside the whitelist, synthesizer without a provider prefix, malformed scope. Look: ui.py:3852-3877 [DERIVED]
2. Symptom: SSE `error` frame `mode_requires_single_corpus`, no answer. Cause: non-ASK mode with `len(scope.corpus_ids) != 1`; the streaming status cannot change after the first frame. Look: ui.py:4019-4027 [DERIVED]
3. Symptom: stream aborts with 422 `gnn_requires_v2`. Cause: `ui_mode == "GNN"` without `_v2_mode` (v2 flag unset, or a `utility` turn). Look: ui.py:4051-4053 [DERIVED]
4. Symptom: `compile` frame says "Query compiler fell back", `fallback` set. Cause: shadow join failed after `timeout=8.0` -> `fallback_plan(query, reason="join_failed:<ExcType>")`. Silent: retrieval proceeds on the fallback plan with default graph breadth. Look: ui.py:3965-3970, 3977-3989 [DERIVED]
5. Symptom: `error` frame with `error_code` = assembly exception class. Cause: `assemble_evidence_bundle` raised `AssemblyError`; receipt records `error` truncated to 200 chars. Look: ui.py:4319-4336 [DERIVED]
6. Silent fallbacks: `_receipt`, `_stamp_firing`, orientation, and P10 resolution are each wrapped in broad `except` — a broken sink or ledger never fails the turn, so receipts can be missing with no visible error. Look: ui.py:3905-3910, 3928-3941, 4216-4224, 4277-4280 [DERIVED]
7. Symptom: fewer/weaker chunks than expected but the answer still returns. Cause: lane degradation (e.g. reranker parked behind extraction); the reason rides the `degraded` list in the answer event, the `/chat` JSON and the query receipt (NEVER-ERROR-ON-A-COLD-MODEL). Look: ui.py:4481-4488 [DERIVED]
8. Symptom: turn answered with zero corpus chunks. Cause: `_skip_retrieval` — the compiled plan's evidence policy is conversation; the `retrieve_skipped` frame announces it. Look: ui.py:4061-4072 [DERIVED]
9. Symptom: probes missing from the subquery set. Cause: PROBE-GATE-V1 dropped them below `probe_gate_floor`; receipt at `fast["trace"]["probe_gate"]`. Look: ui.py:4146-4158, 4180-4181 [DERIVED]

## invariants

- INVARIANT same request => same plan, same evidence ids, same synthesis contract on every route (`/chat/stream` streams the frames; `/chat` and MCP `ask` drain them through `run_chat`). ui.py:3834-3838 [DERIVED]
- INVARIANT request validation is eager and typed, before the first frame, so both transports reject the same requests with the same status. ui.py:3840-3844 [DERIVED]
- INVARIANT exactly one receipt per turn that ran, through the transport's writer; `route` and `receipt` are transport tags and never change the plan, retrieval decision, evidence ids or synthesis. ui.py:3846-3851 [DERIVED]
- INVARIANT exactly one firing receipt per turn, exactly one cause per miss, recorded once to the JSONL rate ledger. ui.py:3928-3930 [DERIVED]
- INVARIANT non-ASK modes retrieve over exactly one corpus. ui.py:4020-4023 [DERIVED]
- INVARIANT wildcard bridges never enter the evidence list; they ride `fast["wildcard"]` / `derived_insights`. ui.py:4124-4126, 4201-4206, 4430-4434 [DERIVED]
- INVARIANT every final candidate in a v2 turn carries lane-provenance arrivals (P1.a gate: 100% have arrivals). ui.py:4442-4445 [DERIVED]
- INVARIANT flag-gated stages (intent policy, skeleton routes, CA3, CA4, synth roles) are byte-identical when off. ui.py:4132-4139, 4289-4291, 4310-4311, 4339-4341 [DERIVED]
- INVARIANT additive stages (receipts, firing, orientation, resolution, carry) fail open and never break a turn. ui.py:3905-3910, 3928-3941, 4216-4224, 4277-4280, 4361-4380 [DERIVED]

## VERIFY

```verify
grep -Fq 'async def chat_stream(req: StreamChatRequest) -> StreamingResponse:' orchestrator/orchestrator/api/ui.py
grep -Fq 'text/event-stream' orchestrator/orchestrator/api/ui.py
grep -Fq 'mode_requires_single_corpus' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_CHAT_EVIDENCE_ROLES' orchestrator/orchestrator/api/ui.py
grep -Fq 'SELECT chunk_id, doc_id, summary FROM chunks ' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'yield _phase(' orchestrator/orchestrator/api/ui.py)" -ge 8
```
