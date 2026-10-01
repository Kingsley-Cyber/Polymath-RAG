# flow: chat-turn

Path prefix used in anchors: `ui.py` = `orchestrator/orchestrator/api/ui.py`. All SOURCE lines are from that file; the excerpt ends mid-turn at ui.py:4491, so post-bundle steps are anchored to the function docstring (ui.py:3831-3851) and imports.

A chat turn: browser POSTs `/chat/stream`, `chat_stream` wraps the `chat_events` generator as SSE, the generator validates eagerly, resolves scope, optionally compiles a plan, retrieves (v2 composition or v1 engines), assembles an evidence bundle, and streams `phase`/`token`/`reasoning`/`answer`/`done`/`error` frames (ui.py:3835-3836 [DERIVED]). `/chat` and MCP `ask` drain the same frames through `run_chat` (ui.py:3836-3837 [DERIVED]).

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | SSE transport: `chat_stream` returns `StreamingResponse(chat_events(req), media_type="text/event-stream")` with `Cache-Control: no-cache`, `X-Accel-Buffering: no` | ui.py:4760-4765 [DERIVED] | `StreamChatRequest` -> SSE byte stream | status cannot change after first frame; later errors are `error` frames (ui.py:3842-3844) |
| 2 | Eager validation: empty message; mode normalized (`VECTOR`→`FAST`; allowed `FAST/HYBRID/GRAPH/ASK/WILDCARD/GNN`); synthesizer (`ollama:`/`litellm:` prefix or `deterministic-template-v3`); scope parsed once via `parse_scope` | ui.py:3852-3877 [DERIVED] | req fields -> `query`, `ui_mode`, `synth`, `_role_scope` | 422 `message is required` / `unknown_mode` / `unknown_synthesizer` / `invalid_scope`, all before first frame |
| 3 | Receipt sink bound: `sink = receipt or _default_receipt_sink(route)` | ui.py:3878 [DERIVED] | `route="chat/stream"` -> sink callable | sink exceptions swallowed later, never break a turn (ui.py:3905-3910) |
| 4 | Scope resolved over DB: `resolve_http_scope(conn, req)` inside `tx()`; `scope_ok` frame carries `mode`, `corpora` | ui.py:3912-3917 [DERIVED] | conn + req -> `scope.mode`, `scope.corpus_ids` | — |
| 5 | Compiler dispatched: `_compiler_flag(req.compiler)`; if not `off`, `_compile_chat_plan` submitted on `ThreadPoolExecutor(max_workers=1)` with `query, req.history, corpora, session_key=(req.workspace or req.corpus_id or query[:64]), titles_rank, corpus_explorer` | ui.py:3923-3952 [DERIVED] | query + history + corpora -> plan future | `shadow` = receipt only, no latency; `on` = serial stage 0 (ui.py:3947-3948) |
| 6 | Plan joined (`on`): `evidence_only` / `require_retrieval` route override via `plan_for_evidence_route`; `_skip_retrieval = (not _plan.retrieval_required) and ui_mode != "ASK"`; `_retrieval_text = query if _skip_retrieval else retrieval_text_for(_plan)`; firing stamped; `compile` frame | ui.py:3953-3975 [DERIVED] | plan -> `_plan_receipt`, `_retrieval_text`, `_skip_retrieval` | fallback plan -> frame text "Query compiler fell back" (ui.py:3970-3971) |
| 7 | ASK short-circuit: `ask(AskRequest(...))` over stored knowledge objects; `answer` frame (kind `ask`) + `done` frame; return | ui.py:3993-4017 [DERIVED] | query -> `result["objects"]`, counts, route | — |
| 8 | Single-corpus guard: non-ASK modes need exactly one corpus | ui.py:4019-4027 [DERIVED] | `scope.corpus_ids` -> `corpus_id` | SSE `error` frame `mode_requires_single_corpus` + receipt, turn ends |
| 9 | Engine selection: `_rflag = chat_retrieval_flag(req.retrieval)`; `_v2_mode = _rflag in ("v2","v2-single") and not req.utility`; GNN guard; `_graph_useful` from plan verdict (`graph_useful: false` keeps expansion definitional, ≤ 2 seeds); skeleton-routes forces the GRAPH hop | ui.py:4045-4060 [DERIVED] | req.retrieval, req.utility, plan -> `_rflag`, `_v2_mode`, `_graph_useful` | 422 `gnn_requires_v2` (ui.py:4051-4053); no compiler or fallback plan keeps default graph breadth (ui.py:4056-4057) |
| 10 | No-retrieval routing (`_skip_retrieval`): corpus not searched; empty `fast`, `evidence_rows`, summaries; `retrieve_skipped` frame carries `task_type`, `evidence_policy` | ui.py:4061-4071 [DERIVED] | plan verdict -> empty evidence set | none; conversation-only answer |
| 11 | GRAPH v1 branch (`GRAPH and not _v2_mode`): `graph_retrieve(_retrieval_text, corpus_id, latent=req.latent, utility=req.utility, ...)`; evidence rows flattened from documents/sections; `graph_facts` from `g["graph_relationships"]` | ui.py:4073-4117 [DERIVED] | retrieval text -> `fast`, `graph_facts`, `evidence_rows`, summaries | rollback boundary: v1 engines live behind `retrieval: v1` / `latent` (ui.py:4043-4044) |
| 12 | v2 composition: budget built (`_apply_intent` if intent policy on; `req.latent` sets `latent_enabled=True` = lane D; `_skeleton_routes(budget, mode, plan)`); `_graph_assist` from intent policy; PROBE-GATE-V1 drops probes via `gate_probes(..., _cr_mod._rerank_children, floor=budget.probe_gate_floor)`; `fast = chat_retrieve_mode(mode, _retrieval_text, corpus_id, graph_useful, graph_assist, keep_latent, exact_terms, subqueries=(id,type,query,weight,origin,derived_from), latent_bridge_ids, facets, question, scope)` | ui.py:4122-4179 [DERIVED] | plan + budget + scope -> `fast` | probe gate is fail-open, one cross-encoder call (ui.py:4146-4150); gated-out ids excluded from subqueries (ui.py:4166) |
| 13 | v1 engines: FAST -> `fast_retrieve`; WILDCARD -> `wildcard_retrieve` (bridges on separate `wildcard` lane); else `hybrid_fast_retrieve(..., latent=req.latent, utility=req.utility)` | ui.py:4197-4210 [DERIVED] | retrieval text + corpus -> `fast` | — |
| 14 | Post-retrieval receipts: `fast["trace"]["probe_gate"]`; `_aspects`/`_weak` from meta; `_facet_cov = _facet_coverage(_plan.facets, final_detail, floor=aspect_weak_floor)`; `wildcard_lane`; `graph_facts`; `retrieve_done` frame; `_arrivals` per chunk; `graph`/`graph_done`/`wildcard` frames | ui.py:4180-4196, 4229-4260 [DERIVED] | `fast` -> aspects, facet coverage, lane sizes, degraded list | degraded lanes surface in the frame's `degraded` field instead of failing (ui.py:4235) |
| 15 | P10 bounded round-2 resolution (flag-gated, one round, same engine) + WLK2C latent second pass `_apply_latent_selection` (runs before CA3/CA4, reassigns `fast["evidence"]`) + `evidence_rows = _evidence_rows(fast["evidence"])` (role + latent seat kept) | ui.py:4213-4228 [DERIVED] | plan, fast, aspects -> `_resolution`, `_latent_receipt`, `evidence_rows` | resolution exceptions -> `_resolution = None` (fail-open, ui.py:4223-4224) |
| 16 | Summaries + orientation: `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)` over `parent_ids` from `fast["selected_sections"]`; `document_summaries` from `selected_documents`; `_load_orientation(conn, doc_ids, parent_ids)` | ui.py:4261-4284 [DERIVED] | parent_ids, doc_ids -> `section_summaries`, `orientation` | orientation exception -> `{"docs": [], "maps": []}` (ui.py:4277-4280) |
| 17 | CA3 constraint alignment: `align_evidence_for_constraints(evidence_rows, _plan.explicit_constraints)` reorders reranked evidence per constraint strength; receipt `{applied, strength, targets, value}` | ui.py:4286-4304 [DERIVED] | evidence + resolved SOURCE constraints -> reordered rows | reorder only; no score added/tuned (ui.py:4288-4290) |
| 18 | CA4 grading: `grade_evidence(fast["evidence"], _plan)` -> `_grades_by_chunk` (DIRECT/PARTIAL/RELATED) + `_epistemic` query state | ui.py:4306-4314 [DERIVED] | evidence + plan -> grades, epistemic verdict | drives the answerability gate: states the gap instead of fabricating (ui.py:4306-4310) |
| 19 | Bundle assembly: `assemble_evidence_bundle(query, graph_facts, evidence_rows, evidence_order, resolve_fact/evidence/entity/document/chunk, document_summaries, section_summaries, unresolved=stale)`; then decorators `evidence_roles`, `evidence_latent`, `evidence_paths`, `facets_uncovered`, `support_roles`+`epistemic`, `orientation`, `derived_insights` | ui.py:4316-4358 [DERIVED] | all of the above -> `bundle` | `AssemblyError` -> SSE `error` frame (`error_code` = class name, message capped 300) + receipt + return (ui.py:4331-4336) |
| 20 | CARRY-V2 admission: `_carry_candidates(req.carry_context, chunk_ids)`; if `_skip_retrieval` -> artifact mode (scorer all `1.0`, `floor=0.0`, `cap=_CARRY_ARTIFACT_CAP`); else judged against `resolved_request` or query; admitted items extend `bundle["evidence_bundle"]`; `carry` frame | ui.py:4359-4381 [DERIVED] | carry_context + query -> `_citems`, `_carry_meta` | — |
| 21 | Presentation: `_evidence_legend(bundle)`, `_render_derived(wildcard_lane, tags, require_proof=_synth_contract_enabled())`, `_render_relations`; `assemble_done` frame; `chunk_inventory` (locator, doc_id, kind, carried, 220-char preview, source_name, title, heading_path, human_locator); `retrieval` receipt dict (engine, arrivals, lane_sizes, gnn route receipt, latency_ms, aspects, facets, constraints, epistemic, composition, `degraded=_merged_degraded(fast, stale)`) | ui.py:4382-4489 [DERIVED] | bundle -> legend, inventory, retrieval receipt | — |
| 22 | Evidence boundary + synthesis + close-out: `evidence_only` stops at the evidence boundary (comment truncated at 4491); otherwise `grounded_answer` (imported ui.py:3881) synthesises the cited answer and the stream emits `token`/`reasoning`/`answer`/`done` frames; `_receipt(...)` writes the turn's one receipt | ui.py:4491, 3881, 3834-3836, 3905-3910 [INFERRED: the call site is past the excerpt cutoff; frames and SYNTHESIS-V2 are stated in the docstring, the import shows the synthesiser] | bundle -> SSE frames + receipt | receipt writer failure swallowed (ui.py:3905-3910) |

## state written

| what | where | detail |
|---|---|---|
| JSONL rate ledger row (CORPUS-EXPLORE-FIRING-V1) | ui.py:3928-3936 [DERIVED] | `polymath_shared.corpus_explore_firing.record` called once per turn via `_stamp_firing`; exactly one cause per miss; ledger file path not shown in SOURCE |
| Turn receipt | ui.py:3878, 3905-3910, 3846-3851 [DERIVED] | `sink(_receipt_payload(req, question=query, scope=scope, route=route, **kw))` once per ran turn; `_default_receipt_sink(route)` adds transport `kind` and `client`; sink storage not shown |
| SSE frame stream | ui.py:4760-4765, 3835-3836 [DERIVED] | `phase`, `token`, `reasoning`, `answer`, `done`, `error` frames to the client |
| Reads (context, not writes): scope via `tx()` | ui.py:3912-3914 [DERIVED] | `resolve_http_scope(conn, req)` |
| Reads: Postgres `chunks` table | ui.py:4269-4273 [DERIVED] | `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)` for parent summaries |

No Qdrant collection appears in this excerpt; vector search happens inside `chat_retrieve_mode`/`fast_retrieve`/`hybrid_fast_retrieve`/`graph_retrieve`, whose internals are not in SOURCE.

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `req.compiler` -> `off \| shadow \| on` | unset (`getattr(req, "compiler", None)`) | `shadow`: plan receipted beside retrieval, changes nothing downstream; `on`: serial stage 0, compiled text searched or not at all | ui.py:3923, 3943-3975 [DERIVED] |
| `req.retrieval` -> `chat_retrieval_flag` (`v2`, `v2-single`; v1 knobs `latent`, `utility`) | not shown | v2 = MODE-COMPOSITION-V1 engine (VECTOR = A+B, HYBRID = A+B+C, GRAPH = HYBRID -> bounded G, WILDCARD = HYBRID ∥ W); `utility` forces v1 | ui.py:4043-4050 [DERIVED] |
| `POLYMATH_CHAT_RETRIEVAL` (env) | opt-in; GNN 422 text says needs `=v2` [INFERRED from the error message] | gates GNN mode | ui.py:4051-4053 |
| `POLYMATH_CHAT_RESOLUTION` (env) | `"0"` | bounded round-2 evidence resolution for unsupported aspects, FAST/HYBRID only | ui.py:4217-4222 [DERIVED] |
| `POLYMATH_CHAT_CONSTRAINT_ALIGN` (env) | `"0"` | CA3 post-rerank constraint reorder | ui.py:4291-4297 [DERIVED] |
| `POLYMATH_CHAT_EVIDENCE_ROLES` (env) | `"0"` | CA4 grading + epistemic state | ui.py:4311-4314 [DERIVED] |
| `POLYMATH_CHAT_SYNTH_ROLES` | default-off | role-aware synthesis presentation via `bundle["evidence_roles"]`; off => grounded prompt byte-identical | ui.py:4338-4341 [DERIVED] |
| `req.latent` (✨) | unset | lane D inside the v2 budget (`latent_enabled=True`), `keep_latent=True`; with v1 retrieval it keeps the turn on v1 engines | ui.py:4047-4049, 4136-4137, 4161 [DERIVED] |
| `req.utility` | unset | v1 plan knob; forces `_v2_mode = False` | ui.py:4049-4050 [DERIVED] |
| `intent_policy_enabled()` | off, byte-identical when off | intent->budget policy; also `_graph_assist` for RELATIONSHIP turns | ui.py:4132-4145 [DERIVED] |
| `_skeleton_routes_on()` | off, byte-identical when off | skeleton doors follow plan + mode; GRAPH mode forces `_graph_useful = True` | ui.py:4058-4060, 4139-4141 [DERIVED] |
| `budget.probe_gate_floor` | `0.0` | PROBE-GATE-V1: drop subqueries that miss the resolved question; FAST/GNN never gated | ui.py:4146-4158 [DERIVED] |
| `req.evidence_only` | unset | `plan_for_evidence_route(_plan)`; REASONING-BOUNDARY-V1 evidence boundary | ui.py:3958-3960, 4491 [DERIVED] |
| `req.require_retrieval` | unset | forces retrieval: `override_rule="corpus_chat:retrieval_required"` | ui.py:3961-3962 [DERIVED] |
| `req.corpus_explorer` | unset | `requested` bit in the firing receipt | ui.py:3933 [DERIVED] |
| `req.carry_context` | unset | CARRY-V2 admission (judged, or artifact mode on skip-retrieval turns) | ui.py:4360-4375 [DERIVED] |

## failure modes

1. HTTP 422 before any frame -> empty message / unknown mode / unknown synthesizer / malformed scope -> eager validation block ui.py:3852-3877.
2. HTTP 422 `gnn_requires_v2` -> mode GNN without the v2 candidate engine or on a utility turn -> ui.py:4051-4053.
3. SSE `error` frame `mode_requires_single_corpus`, turn ends with receipt -> FAST/HYBRID/GRAPH/WILDCARD/GNN over a scope with != 1 corpus -> ui.py:4019-4027.
4. SSE `error` frame with `error_code` = exception class name, message truncated to 300 chars -> `assemble_evidence_bundle` raised `AssemblyError` -> ui.py:4317-4336.
5. Silent fallback: compiler join timeout (`timeout=8.0`) or exception -> `fallback_plan(query, reason=f"join_failed:{type(exc).__name__}")`; `compile` frame reads "Query compiler fell back"; graph breadth returns to default -> ui.py:3977-3988, 3970-3971, 4054-4057.
6. Silent fallback: receipt sink raises -> swallowed by `_receipt`, turn continues -> ui.py:3905-3910.
7. Silent fallback: firing-ledger write raises -> swallowed by `_stamp_firing`, no firing receipt -> ui.py:3928-3941.
8. Silent fallback: P10 resolution raises -> `_resolution = None`, evidence unchanged -> ui.py:4216-4224.
9. Silent fallback: orientation load raises -> `orientation = {"docs": [], "maps": []}` -> ui.py:4277-4280.
10. Degradation, not failure: a lane that degraded (e.g. reranker parked behind extraction; `embed_deadline`, `rerank_timeout`, `<lane>_timeout`, `graph_degraded`, wildcard) still answers; the reason rides `retrieval["degraded"]` so the answer event, /chat JSON and receipt all say why evidence differs -> ui.py:4481-4489.

## invariants

- INVARIANT same request => same plan, same evidence ids, same synthesis contract on every route (`/chat/stream`, `/chat`, MCP `ask` via `run_chat`) — ui.py:3836-3838 [DERIVED]
- INVARIANT request validation raises typed HTTPExceptions EAGERLY, before the first frame, so both transports reject identically — ui.py:3840-3844 [DERIVED]
- INVARIANT `route` and `receipt` are transport tags only; neither changes the plan, the retrieval decision, the evidence ids or the synthesis — ui.py:3846-3851 [DERIVED]
- INVARIANT a malformed scope is refused before the first frame, never read as "both roles" — ui.py:3871-3872 [DERIVED]
- INVARIANT the turn writes exactly ONE firing receipt, exactly one cause per miss — ui.py:3929-3930 [DERIVED]
- INVARIANT wildcard bridges never enter the evidence list; they ride `fast["wildcard"]` / the separate `wildcard` lane — ui.py:4125-4127, 4430-4434 [DERIVED]
- INVARIANT 100% of final candidates carry lane provenance (`arrivals`) — P1.a gate — ui.py:4442-4444 [DERIVED]
- INVARIANT default-off gates (CA3, CA4, P8b synth roles, intent policy, skeleton routes) leave the turn byte-identical — ui.py:4289-4290, 4310-4311, 4340, 4133, 4140 [DERIVED]

## VERIFY

```verify
grep -Fq 'async def chat_stream(req: StreamChatRequest) -> StreamingResponse:' orchestrator/orchestrator/api/ui.py
grep -Fq 'media_type="text/event-stream"' orchestrator/orchestrator/api/ui.py
grep -Fq 'raise HTTPException(422, "message is required")' orchestrator/orchestrator/api/ui.py
grep -Fq 'gnn_requires_v2' orchestrator/orchestrator/api/ui.py
grep -Eq 'POLYMATH_CHAT_(RESOLUTION|CONSTRAINT_ALIGN|EVIDENCE_ROLES)' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'yield _phase(' orchestrator/orchestrator/api/ui.py)" -ge 10
! grep -Fq 'X-Accel-Buffering: yes' orchestrator/orchestrator/api/ui.py
```
