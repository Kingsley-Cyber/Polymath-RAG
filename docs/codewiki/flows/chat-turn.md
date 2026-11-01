# flow: chat-turn

A chat turn end to end: the browser posts /chat/stream (modes FAST, HYBRID, GRAPH, WILDCARD, GNN), the query compiler plans subqueries and facets, retrieval composes evidence, the model synthesises a cited answer, the receipt is written, the SSE frames reach the UI.

Entry: POST /chat/stream -> `chat_stream` at orchestrator/orchestrator/api/ui.py:4978 [DERIVED]. One runtime, `chat_events`, serves both `/chat/stream` (SSE) and `/chat` / MCP `ask` (drained through `run_chat`): same request => same plan, same evidence ids, same synthesis contract. orchestrator/orchestrator/api/ui.py:3947-3955 [DERIVED]

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | SSE entry: `chat_stream` wraps `chat_events(req)` in `StreamingResponse`, media_type `"text/event-stream"`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | orchestrator/orchestrator/api/ui.py:4978-4983 [DERIVED] | StreamChatRequest -> SSE frames (`phase`, `token`, `reasoning`, `answer`, `done`, `error` per docstring) | none at this hop |
| 2 | Eager validation before first frame: message required; mode defaults `"HYBRID"`, alias `VECTOR`->`FAST`, must be in `("FAST", "HYBRID", "GRAPH", "ASK", "WILDCARD", "GNN")`; synthesizer = `_default_synthesizer()` or `deterministic-template-v3` or `ollama:`/`litellm:` prefix | orchestrator/orchestrator/api/ui.py:3969-3987 [DERIVED] | req -> query, ui_mode, synth, llm_model/llm_backend | 422 `"message is required"`; 422 `unknown_mode`; 422 `unknown_synthesizer` |
| 3 | Knowledge-role scope parsed ONCE, EAGERLY (K1) | orchestrator/orchestrator/api/ui.py:3990-3994 [DERIVED] | req.scope -> `_role_scope` via `parse_scope` | 422 `invalid_scope` (ScopeError); never read as "both roles" |
| 4 | Scope resolution + `scope`/`scope_ok` frames; `_mark("scope")` | orchestrator/orchestrator/api/ui.py:4029-4034 [DERIVED] | req -> scope (mode, corpus_ids) via `resolve_http_scope(conn, req)` under `tx()` | DB error untyped in excerpt |
| 5 | Product intent (PRODUCT-INTENT-V1): `_detect_product(query, req.history, force)`; ProductTurn; if >1 corpus, product-library-routing-v1 picks one library via `_product.route(..., embed=_route_embed, role_scope=_role_scope)` | orchestrator/orchestrator/api/ui.py:4039-4063 [DERIVED] | query, history -> `_product`, scope narrowed to `(_chosen,)` | detection none shown; later CJ lookup failure degrades (failure 6) |
| 6 | Compiler submit (CHAT-INTENT-PLAN-V1): `_compiler_flag(req.compiler)` in off/shadow/on; `ThreadPoolExecutor(max_workers=1).submit(_compile_chat_plan, query, history, corpora, session_key, titles_rank, corpus_explorer, scope_kwargs)` | orchestrator/orchestrator/api/ui.py:4108-4117 [DERIVED] | query + history -> `_plan_future` | exception deferred to join (hop 9) |
| 7 | flag `"on"` = serial stage 0: plan joins, `_product.steer_plan`, `evidence_only`/`require_retrieval` rewrite via `plan_for_evidence_route` (override_rule `"corpus_chat:retrieval_required"`), `retrieval_text_for(_plan)`, `_skip_retrieval` decision (COMPILED-RETRIEVAL-V1), `compile` frame | orchestrator/orchestrator/api/ui.py:4119-4142 [DERIVED] | `_plan_future` -> `_plan`, `_plan_receipt`, `_retrieval_text`, `_skip_retrieval` | `_plan.fallback` reported as "Query compiler fell back" |
| 8 | ONE firing receipt to the JSONL rate ledger (CORPUS-EXPLORE-FIRING-V1) via `_stamp_firing` | orchestrator/orchestrator/api/ui.py:4093-4106, 4136 [DERIVED] | plan, req.corpus_explorer, flag, skip -> ledger record | swallowed; observation only, never breaks a turn |
| 9 | shadow join: `_join_plan` waits `future.result(timeout=8.0)`; any exception -> `fallback_plan(query, reason="join_failed:{type}")` | orchestrator/orchestrator/api/ui.py:4146-4160 [DERIVED] | `_plan_future` -> `_plan` (or fallback) | silent fallback plan |
| 10 | ASK branch: `ask(AskRequest(...))` over stored knowledge objects; `answer` frame kind `"ask"`; `done`; return | orchestrator/orchestrator/api/ui.py:4162-4186 [DERIVED] | question, corpus ids -> result objects + counts | none typed here |
| 11 | Scope guards: empty corpus_ids -> `error` frame QUERY_SCOPE_EMPTY; `len != 1` -> `error` frame `mode_requires_single_corpus`; both receipted then return | orchestrator/orchestrator/api/ui.py:4188-4209 [DERIVED] | scope -> typed refusal | turn ends with error frame, never IndexError |
| 12 | Engine choice: `chat_retrieval_flag(req.retrieval)`; `_v2_mode = _rflag in ("v2", "v2-single") and not req.utility` | orchestrator/orchestrator/api/ui.py:4227-4232 [DERIVED] | req.retrieval, req.utility -> `_rflag`, `_v2_mode` | 422 `gnn_requires_v2` when ui_mode GNN and not `_v2_mode` (ui.py:4233-4235) |
| 13 | No-retrieval routing: `_skip_retrieval` -> `evidence_rows=[]`, empty `fast`, `retrieve_skipped` frame; corpus not searched | orchestrator/orchestrator/api/ui.py:4243-4254 [DERIVED] | — -> empty retrieval state | intended path, not a failure |
| 14 | GRAPH on v1 engines: `graph_retrieve(_retrieval_text, corpus_id, latent=req.latent, utility=req.utility, scope_kwargs)` -> fast{meta,trace}, evidence_rows, graph_facts, doc/section summaries | orchestrator/orchestrator/api/ui.py:4255-4299 [DERIVED] | retrieval text -> lanes evidence + hop-1 facts | none typed in excerpt |
| 15 | v2 composition (MODE-COMPOSITION-V1): budget (intent policy P2b default-off; `req.latent` -> `latent_enabled=True` lane D; skeleton routes), PROBE-GATE-V1 drops missed non-PRIMARY probes via `_rerank_children`, then `chat_retrieve_mode("VECTOR" if ui_mode=="FAST" else ui_mode, text, corpus_id, graph_useful, graph_assist, keep_latent, exact_terms, subqueries with origin, latent_bridge_ids, facets, question)`; facet coverage F1 with `floor=float(getattr(_budget, "aspect_weak_floor", 0.5))` | orchestrator/orchestrator/api/ui.py:4304-4369 [DERIVED] | plan + text -> `fast` (evidence, aspects, weak_aspects, lanes) | probe gate fail-open; GNN route lives in the candidate engine only (ui.py:4233) |
| 16 | v1 engines: FAST -> `fast_retrieve`; WILDCARD -> `wildcard_retrieve` (bridges ride `fast["wildcard"]`, never the evidence list); else `hybrid_fast_retrieve(latent, utility)` | orchestrator/orchestrator/api/ui.py:4379-4392 [DERIVED] | retrieval text -> `fast` | none typed in excerpt |
| 17 | Additive passes: P10 bounded round-2 resolution `_maybe_resolve` (flag-gated, modes FAST/HYBRID, fail-open); WLK2C `_apply_latent_selection` reassigns `fast["evidence"]`; `evidence_rows = _evidence_rows(fast["evidence"])`; `_mark("retrieve")`; `retrieve_done` frame | orchestrator/orchestrator/api/ui.py:4395-4422 [DERIVED] | fast, plan -> merged evidence rows | resolution failure -> `_resolution = None` (silent) |
| 18 | Parent summaries + orientation: SQL `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)` over parent_ids; `_load_orientation` fail-open | orchestrator/orchestrator/api/ui.py:4443-4466 [DERIVED] | parent_ids -> section_summaries, orientation | orientation failure -> `{"docs": [], "maps": []}` |
| 19 | CA3 constraint alignment: `align_evidence_for_constraints` reorders the already-reranked rows; `_constraint_align` receipt | orchestrator/orchestrator/api/ui.py:4468-4486 [DERIVED] | evidence_rows, plan constraints -> reordered rows | reorders only when a resolved constraint is present; else byte-identical |
| 20 | CA4 evidence roles: `grade_evidence` -> `_grades_by_chunk`, `_epistemic` | orchestrator/orchestrator/api/ui.py:4488-4496 [DERIVED] | fast evidence + plan -> grades, epistemic state | default-off ⇒ no grades, byte-identical |
| 21 | Bundle assembly: `assemble_evidence_bundle(query, graph_facts, evidence_rows, evidence_order, resolve_* callbacks, document_summaries, section_summaries, unresolved=stale)` | orchestrator/orchestrator/api/ui.py:4498-4518 [DERIVED] | evidence -> bundle | `AssemblyError` -> `error` frame (error_code = class name, message[:300]) + receipt + return |
| 22 | Bundle enrichment: `evidence_roles` (P8b), `evidence_latent` (E3), `evidence_paths` (S8), `facets_uncovered` (F5), `support_roles`+`epistemic` (CA4), `orientation`, `derived_insights = wildcard_lane` | orchestrator/orchestrator/api/ui.py:4520-4540 [DERIVED] | bundle -> annotated bundle | none; additive keys |
| 23 | CARRY-V2 admission: `_carry_candidates` + `_admit_carry`; artifact mode when `_skip_retrieval` (scorer all `1.0`, `floor=0.0`, cap `_CARRY_ARTIFACT_CAP`) else judged against `plan.resolved_request` or query; `carry` frame | orchestrator/orchestrator/api/ui.py:4541-4563 [DERIVED] | req.carry_context -> admitted items in bundle | admission miss = fewer items, not a failure |
| 24 | Presentation: `_evidence_legend(bundle)`, `_render_derived(require_proof=_synth_contract_enabled())`, `_render_relations`, `assemble_done` frame | orchestrator/orchestrator/api/ui.py:4564-4569 [DERIVED] | bundle -> legend, counts | none shown |
| 25 | Sources inventory + retrieval receipt: chunk_inventory entries (locator, doc_id, kind, carried, preview[:220], source_name, title, heading_path, human_locator — UI-V3 §4.1); `retrieval` dict starts `{mode, evidence_count, graph_fact_count, graph_bounds, ...}` | orchestrator/orchestrator/api/ui.py:4571-4605 [DERIVED] | bundle -> UI payload | excerpt ends at ui.py:4605 mid-dict |

Excerpt boundary: SOURCE stops at orchestrator/orchestrator/api/ui.py:4605; token/answer/done emission, `grounded_answer` invocation (imported at orchestrator/orchestrator/api/ui.py:3998 [DERIVED]) and the receipt write happen downstream of the provided material.

## state written

- Turn receipt: built once in the runtime for every turn that ran (`_receipt_payload(req, question=query, scope=scope, route=route, **kw)`), written through `sink = receipt or _default_receipt_sink(route)`; the sink only adds transport `kind` and `client`; `meta.route` = the route. orchestrator/orchestrator/api/ui.py:3963-3967, 3995, 4022-4027 [DERIVED]
- CORPUS-EXPLORE-FIRING-V1 record to the JSONL rate ledger via `polymath_shared.corpus_explore_firing.record(rec, q0=query)` — exactly one cause per miss, recorded once. orchestrator/orchestrator/api/ui.py:4093-4101 [DERIVED]
- Probe-gate receipt stored at `fast["trace"]["probe_gate"]`, receipted with the turn (S1d). orchestrator/orchestrator/api/ui.py:4362-4363 [DERIVED]
- Postgres reads on this path (not writes): `tx()` for `resolve_http_scope` (orchestrator/orchestrator/api/ui.py:4030-4031) and the chunks summary query (orchestrator/orchestrator/api/ui.py:4451-4455). [DERIVED]
- No durable table/collection write is visible in the excerpt; the receipt's destination is behind `_default_receipt_sink` (not shown). [DERIVED]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `req.compiler` | not shown in excerpt (values off / shadow / on) | `shadow`: plan compiled beside retrieval, receipted, changes nothing downstream; `on`: serial stage 0 + COMPILED-RETRIEVAL-V1 (search the compiled text, or not at all) | orchestrator/orchestrator/api/ui.py:4108-4142 [DERIVED] |
| `req.retrieval` / POLYMATH_CHAT_RETRIEVAL | not shown; `"v2"` required for GNN per error text | `chat_retrieval_flag` -> `"v2"`/`"v2-single"` enables the v2 composition; other values keep the v1 engines (rollback boundary) | orchestrator/orchestrator/api/ui.py:4227-4235 [DERIVED] |
| POLYMATH_CHAT_RESOLUTION | `"0"` | bounded round-2 evidence resolution merged into `fast["evidence"]` before the bundle; fail-open, at most one round | orchestrator/orchestrator/api/ui.py:4398-4406 [DERIVED] |
| POLYMATH_CHAT_CONSTRAINT_ALIGN | `"0"` | CA3 post-rerank portfolio partition; reorders only when a resolved constraint is present | orchestrator/orchestrator/api/ui.py:4468-4486 [DERIVED] |
| POLYMATH_CHAT_EVIDENCE_ROLES | `"0"` | CA4 DIRECT/PARTIAL/RELATED grading + epistemic state driving the answerability gate | orchestrator/orchestrator/api/ui.py:4488-4496 [DERIVED] |
| POLYMATH_CHAT_SYNTH_ROLES | default-off per comment | role-aware synthesis presentation from `bundle["evidence_roles"]` | orchestrator/orchestrator/api/ui.py:4520-4522 [DERIVED] |
| `req.latent` (B12) | off | enables lane D inside the v2 composition (`_replace(_budget, latent_enabled=True)`, `keep_latent=True`); no longer drops the turn to the v1 engine | orchestrator/orchestrator/api/ui.py:4230-4231, 4318-4319, 4343 [DERIVED] |
| `req.utility` | off | v1 plan knob; truthy forces `_v2_mode` False (v1 engines) | orchestrator/orchestrator/api/ui.py:4229-4232 [DERIVED] |
| `req.evidence_only` / `req.require_retrieval` | off | rewrite the plan via `plan_for_evidence_route`; require_retrieval uses override_rule `"corpus_chat:retrieval_required"` | orchestrator/orchestrator/api/ui.py:4125-4129 [DERIVED] |
| `req.product` | None (admitted unless explicitly False) | True forces product mode; False turns it off | orchestrator/orchestrator/api/ui.py:4037-4039 [DERIVED] |
| intent policy (P2b) | default off, byte-identical when off | intent-conditioned budget via `apply_intent(_plan.intent, _default_budget())` | orchestrator/orchestrator/api/ui.py:4313-4317 [DERIVED] |
| skeleton routes | default off | `apply_skeleton_routes(_budget, mode=ui_mode, plan=_plan)`; when enabled, an owner-chosen GRAPH mode keeps the hop — the compiler verdict cannot veto | orchestrator/orchestrator/api/ui.py:4240-4242, 4320-4322 [DERIVED] |
| probe gate | off (needs `probe_gate_floor > 0`) | drops non-PRIMARY probes that miss the user's resolved question before they spend retrieval; FAST / GNN never gated | orchestrator/orchestrator/api/ui.py:4328-4340 [DERIVED] |
| `req.corpus_explorer` | off | passed into the compiler; feeds the firing receipt's `requested` flag | orchestrator/orchestrator/api/ui.py:4097-4099, 4117 [DERIVED] |

## failure modes

1. 422 before the first frame — empty message / unknown mode / unknown synthesizer / malformed scope -> typed HTTPExceptions raised eagerly, because a streaming response cannot change its status once the first frame is out -> look at orchestrator/orchestrator/api/ui.py:3957-3961, 3969-3994 [DERIVED]
2. SSE `error` frame QUERY_SCOPE_EMPTY -> resolved scope has no corpus -> detail from `QueryScopeEmpty().detail()` or the fallback dict (`error_code` `"QUERY_SCOPE_EMPTY"`, message `"There is no library to search for this caller."`); typed refusal, never an IndexError -> orchestrator/orchestrator/api/ui.py:4188-4200 [DERIVED]
3. SSE `error` frame `mode_requires_single_corpus` -> mode retrieves over exactly one corpus, scope has N -> orchestrator/orchestrator/api/ui.py:4201-4209 [DERIVED]
4. 422 `gnn_requires_v2` -> GNN mode with non-v2 retrieval or a utility turn -> orchestrator/orchestrator/api/ui.py:4233-4235 [DERIVED]
5. Silent fallback — compiler join fails or exceeds `timeout=8.0` -> `fallback_plan(query, reason="join_failed:{type}")`; downstream then keeps default graph breadth (`_graph_useful` True on fallback) -> orchestrator/orchestrator/api/ui.py:4146-4154, 4238-4239 [DERIVED]
6. Silent degradation — a product CJ lookup raises -> `retrieval["degraded"]` entry `{component: product_search, state: failed, reason: type name}`, `out = None`; the answer stands without the product block and says so -> orchestrator/orchestrator/api/ui.py:4065-4082 [DERIVED]
7. Silent drops — orientation failure -> `{"docs": [], "maps": []}`; P10 resolution failure -> `_resolution = None`; receipt-sink and firing-ledger exceptions swallowed -> orchestrator/orchestrator/api/ui.py:4022-4027, 4100-4105, 4398-4406, 4459-4462 [DERIVED]
8. `AssemblyError` -> SSE `error` frame with `error_code` = exception class name and `message[:300]`; receipt error field recorded; turn returns -> orchestrator/orchestrator/api/ui.py:4513-4518 [DERIVED]

## invariants

- INVARIANT: one chat runtime — same request => same plan, same evidence ids, same synthesis contract on every route; `/chat/stream` streams the frames, `/chat` (and MCP `ask`) drains them through `run_chat`. orchestrator/orchestrator/api/ui.py:3947-3955 [DERIVED]
- INVARIANT: request validation is eager and typed before the first frame, so both transports reject the same requests with the same status. orchestrator/orchestrator/api/ui.py:3957-3961 [DERIVED]
- INVARIANT: the scope is parsed once, eagerly; a malformed scope is refused, never read as "both roles"; every search of the turn (scout, Corpus Explore, lanes) honours it. orchestrator/orchestrator/api/ui.py:3988-3989 [DERIVED]
- INVARIANT: the answer event reads the retrieval result through `fast` on every path. orchestrator/orchestrator/api/ui.py:4261-4262 [DERIVED]
- INVARIANT: wildcard bridges ride `fast["wildcard"]` (the separate lane / `derived_insights`), never the evidence list. orchestrator/orchestrator/api/ui.py:4307-4308, 4382-4386, 4540 [DERIVED]
- INVARIANT: with `_skip_retrieval` the corpus is not searched; the request is answered from the conversation. orchestrator/orchestrator/api/ui.py:4243-4252 [DERIVED]
- INVARIANT: one receipt per turn that ran, built in the runtime; the transport only adds `kind`/`client`; a receipt failure never breaks a turn. orchestrator/orchestrator/api/ui.py:3963-3967, 4022-4027 [DERIVED]
- INVARIANT: mode names are normalized — `VECTOR` alias becomes `FAST` at admission, and the retrieval receipt reports `"VECTOR"` when ui_mode is `FAST`. orchestrator/orchestrator/api/ui.py:3972-3974, 4598-4599 [DERIVED]

## VERIFY

```verify
grep -Fq 'async def chat_stream(req: StreamChatRequest) -> StreamingResponse:' orchestrator/orchestrator/api/ui.py
grep -Fq 'deterministic-template-v3' orchestrator/orchestrator/api/ui.py
grep -Fq 'gnn_requires_v2' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_CHAT_RESOLUTION' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_CHAT_CONSTRAINT_ALIGN' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_CHAT_EVIDENCE_ROLES' orchestrator/orchestrator/api/ui.py
grep -Fq 'SELECT chunk_id, doc_id, summary FROM chunks ' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'mode_requires_single_corpus' orchestrator/orchestrator/api/ui.py)" -ge 2
```
