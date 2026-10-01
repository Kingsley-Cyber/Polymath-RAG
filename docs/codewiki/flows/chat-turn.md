# flow: chat-turn

A chat turn end to end: the browser posts `/chat/stream`, the query compiler plans subqueries and facets, retrieval composes evidence, the bundle is assembled, and SSE frames stream back. All anchors are in `orchestrator/orchestrator/api/ui.py` unless another path is given. The excerpt ends at the evidence boundary (line 4492); synthesis/tokens frames are documented only in the `chat_events` docstring.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `chat_stream` wraps `chat_events(req)` in a `StreamingResponse`, `media_type="text/event-stream"`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | ui.py:4760-4765 [DERIVED] | `StreamChatRequest` -> SSE stream | transport-level only; frames come from the generator |
| 2 | Eager validation: empty message -> 422 `"message is required"`; `mode` default `"HYBRID"`, `"VECTOR"` remapped to `"FAST"`; mode must be in `("FAST","HYBRID","GRAPH","ASK","WILDCARD","GNN")` else 422 `unknown_mode`; synthesizer must be `deterministic-template-v3` or `ollama:`/`litellm:`-prefixed else 422 `unknown_synthesizer`; `parse_scope` failure -> 422 `invalid_scope` — all typed HTTPExceptions before the first frame | ui.py:3852-3877 [DERIVED] | `req` fields -> validated `query`, `ui_mode`, `synth`, `_role_scope` | 422s listed; a streaming response cannot change status after the first frame (ui.py:3842-3844 [DERIVED]) |
| 3 | Receipt sink bound: `sink = receipt or _default_receipt_sink(route)`; `route` and `receipt` are transport tags only | ui.py:3846-3851, 3878 [DERIVED] | `route`, optional `receipt` -> `sink` | sink exceptions swallowed later (never breaks a turn) |
| 4 | `scope` phase: `with tx() as conn: scope = resolve_http_scope(conn, req)`; emits `scope_ok` with `mode`, `corpora`; `_mark("scope")` | ui.py:3912-3917 [DERIVED] | `req` + Postgres conn -> `scope` (`.corpus_ids`, `.mode`) | scope resolution error (not caught here) |
| 5 | Compiler launched if `_flag != "off"`: `ThreadPoolExecutor(max_workers=1).submit(_compile_chat_plan, query, req.history, _corpora, ...)`; session key = `req.workspace or req.corpus_id or query[:64]`; `shadow` runs beside retrieval (no added latency) | ui.py:3923, 3943-3952 [DERIVED] | query + history + corpora -> plan future | compiler failure surfaces at join (hop 7) |
| 6 | Compiler `on`: plan joined synchronously; `evidence_only` -> `plan_for_evidence_route(_plan)`; `require_retrieval` -> same with `override_rule="corpus_chat:retrieval_required"`; `_skip_retrieval = (not _plan.retrieval_required) and ui_mode != "ASK"`; `_retrieval_text = query if _skip_retrieval else retrieval_text_for(_plan)`; firing stamped; `compile` frame | ui.py:3953-3975 [DERIVED] | plan future -> `_plan`, `_plan_receipt`, `_skip_retrieval`, `_retrieval_text` | `fallback=True` reported in the `compile` frame (ui.py:3970) |
| 7 | `_join_plan()` for the shadow future: `result(timeout=8.0)`; any exception -> `fallback_plan(query, reason=f"join_failed:{type(exc).__name__}")` | ui.py:3977-3991 [DERIVED] | future -> `_plan` | silent fallback to a fallback plan on join failure/timeout |
| 8 | ASK short-circuit: `ask(AskRequest(question=query, corpus_id=..., corpus_ids=..., workspace=..., all_authorized=...))`; emits `ask`, `ask_done`, `answer` (kind `"ask"`), `done`; returns | ui.py:3993-4017 [DERIVED] | query -> stored objects result | error inside `ask` (not caught here) |
| 9 | Single-corpus guard: `len(scope.corpus_ids) != 1` -> `error` frame `mode_requires_single_corpus`, receipt with error, return | ui.py:4019-4027 [DERIVED] | `scope.corpus_ids` -> error frame | mid-stream error frame (status already sent) |
| 10 | Engine selection: `_rflag = chat_retrieval_flag(getattr(req, "retrieval", None))`; `_v2_mode = _rflag in ("v2","v2-single") and not req.utility`; `ui_mode == "GNN" and not _v2_mode` -> 422 `gnn_requires_v2` | ui.py:4045-4053 [DERIVED] | `req.retrieval`, `req.utility`, `ui_mode` -> `_v2_mode` | GNN 422 raised after `scope`/`scope_ok` frames were yielded (ui.py:3912, 3916 vs 4052) [DERIVED] |
| 11 | Graph bounds: `_graph_useful` defaults true when compiler off / no plan / fallback, else `plan.graph_useful`; skeleton routes on + GRAPH mode forces True (compiler verdict does not veto the owner's GRAPH choice) | ui.py:4056-4060 [DERIVED] | plan -> `_graph_useful` | — |
| 12 | No-retrieval routing (`_skip_retrieval`): `evidence_rows = []`, empty `fast` shape, `retrieve_skipped` frame ("answered from the conversation") | ui.py:4061-4070 [DERIVED] | — -> empty evidence set | corpus never searched; intentional |
| 13 | GRAPH on v1 (`retrieval: v1` / `latent`): `graph_retrieve(_retrieval_text, corpus_id, latent=req.latent, utility=req.utility, **scope_kwargs(_role_scope))`; builds `fast`, `evidence_rows`, `graph_facts`, document/section summaries; emits `retrieve_done`, `graph`, `graph_done` | ui.py:4073-4117 [DERIVED] | retrieval text -> v1 graph result | engine-internal degradation rides `meta` |
| 14 | v2 composition: budget built (`_apply_intent` when intent policy on; `req.latent` -> `latent_enabled=True` (lane D); `_skeleton_routes(budget, mode, plan)`); PROBE-GATE-V1 drops non-PRIMARY probes missing the resolved question via `gate_probes(..., _cr_mod._rerank_children, floor=_budget.probe_gate_floor)`; `fast = chat_retrieve_mode("VECTOR" if ui_mode == "FAST" else ui_mode, _retrieval_text, corpus_id, ...)` with `subqueries` (id/type/query/weight/origin/derived_from), `latent_bridge_ids`, `facets`, WILDCARD `question` | ui.py:4122-4179 [DERIVED] | plan + budget -> composed `fast` | probe gate is fail-open, default off (ui.py:4146-4147) |
| 15 | Post-retrieval receipts: `fast.setdefault("trace", {})["probe_gate"]`; facet coverage `_facet_coverage(_plan.facets, final_detail, floor=float(getattr(_budget, "aspect_weak_floor", 0.5)))`; wildcard lane and graph facts extracted from `fast` | ui.py:4180-4196 [DERIVED] | `fast` -> `_facet_cov`, `wildcard_lane`, `graph_facts` | — |
| 16 | v1 engines: FAST -> `fast_retrieve`; WILDCARD -> `wildcard_retrieve` (bridges ride the separate `wildcard` lane, never displace evidence); else `hybrid_fast_retrieve(..., latent=req.latent, utility=req.utility, ...)` | ui.py:4197-4210 [DERIVED] | retrieval text -> `fast` | engine-internal degradation |
| 17 | P10 resolution (flag-gated, fail-open, one bounded round) + WLK2C latent second pass `_apply_latent_selection(fast, _plan, _retrieval_text, mode=ui_mode)` before CA3/CA4; `evidence_rows = _evidence_rows(fast["evidence"])`; `retrieve_done` frame | ui.py:4216-4240 [DERIVED] | `fast` + plan -> final `evidence_rows`, `_resolution`, `_latent_receipt` | resolution exception -> `_resolution = None` (turn continues) |
| 18 | Orientation + section summaries: parent_ids from `fast["selected_sections"]`; Postgres `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)`; `_load_orientation(conn, doc_ids, parent_ids)` | ui.py:4267-4284 [DERIVED] | parent/doc ids -> `orientation`, `section_summaries` | orientation exception -> `{"docs": [], "maps": []}` (silent, additive) |
| 19 | CA3 constraint alignment (flag): `align_evidence_for_constraints(evidence_rows, _plan.explicit_constraints)` — reorder only, semantic order preserved within each portfolio | ui.py:4291-4304 [DERIVED] | evidence + resolved SOURCE constraints -> reordered evidence | only reorders when a resolved constraint is present |
| 20 | CA4 evidence roles (flag): `grade_evidence(fast.get("evidence") or [], _plan)` -> `_grades_by_chunk`, `_epistemic`; epistemic state drives the answerability gate | ui.py:4311-4314 [DERIVED] | evidence + plan -> grades + epistemic | default off -> no grades, byte-identical |
| 21 | Bundle assembly: `assemble_evidence_bundle(query, graph_facts, evidence_rows, ... resolvers ..., document_summaries, section_summaries, unresolved=stale)`; `AssemblyError` -> `error` frame + receipt + return | ui.py:4316-4336 [DERIVED] | evidence + summaries -> `bundle`, `stale` | `AssemblyError` terminates the turn with an error frame |
| 22 | Bundle enrichment: `evidence_roles`, `evidence_latent` (seat/via), `evidence_paths`, `facets_uncovered`, `support_roles` + `epistemic`, `orientation`, `derived_insights = wildcard_lane`; CARRY-V2 admission (`_carry_candidates` + `_admit_carry`; artifact mode on skip-retrieval: constant scorer `[1.0]*len(texts)`, `floor=0.0`, cap `_CARRY_ARTIFACT_CAP`; else judged against resolved request); legend + `_render_derived`/`_render_relations`; `assemble_done` frame | ui.py:4338-4387 [DERIVED] | bundle + `req.carry_context` -> enriched bundle, `_carry_meta`, `_legend` | — |
| 23 | Retrieval receipt dict: mode, counts, `graph_bounds`/`graph_seeds`/`graph_degraded`, `wildcard_diagnostics`, `latent`, `carry`, `engine`, `arrivals`, `lane_sizes`, `gnn` (GNN only), `latency_ms`, `aspects`/`weak_aspects`, facets, `explicit_constraints`, `constraint_alignment`, `epistemic`, `latent_selection`, `profile_yield`, `resolution`, `final_detail`, `composition`, `degraded` (`_merged_degraded(fast, stale)`) | ui.py:4416-4489 [DERIVED] | fast/bundle state -> `retrieval` payload | degraded lanes listed, never silent |
| 24 | Evidence boundary: `if getattr(req, "evidence_only", False):` — REASONING-BOUNDARY-V1; excerpt ends here. Docstring: the generator emits `phase`, `token`, `reasoning`, `answer`, `done`, `error` frames; `/chat` drains them through `run_chat` | ui.py:4491-4492, 3835-3838 [DERIVED] | bundle + retrieval -> answer frames | synthesis stage not in excerpt |

## state written

- SSE frame stream to the client: frames `phase`, `token`, `reasoning`, `answer`, `done`, `error` (ui.py:3835-3836 [DERIVED]).
- Turn receipt, built once in the runtime: `sink(_receipt_payload(req, question=query, scope=scope, route=route, **kw))`; default sink `_default_receipt_sink(route)` adds the transport's `kind` and `client` (ui.py:3847-3851, 3878, 3905-3910 [DERIVED]). Sink exceptions swallowed.
- Corpus-explore firing receipt, "recorded once to the JSONL rate ledger": `polymath_shared.corpus_explore_firing.record(rec, q0=query)` (ui.py:3928-3935 [DERIVED]). Exceptions swallowed.
- Postgres on this path is read-only in the excerpt: `tx()` for scope resolution (ui.py:3913-3914) and the `chunks` select (ui.py:4270-4273). No table write is visible in the excerpt [DERIVED].

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `req.mode` | `"HYBRID"` | selects FAST/HYBRID/GRAPH/ASK/WILDCARD/GNN; `VECTOR` remapped to `FAST` | ui.py:3855-3860 |
| `req.compiler` -> `_compiler_flag` | not shown in excerpt | `off` = no plan; `shadow` = plan receipted beside retrieval, changes nothing downstream; `on` = serial stage 0, drives `_skip_retrieval` and typed subqueries | ui.py:3923, 3943-3975 |
| `req.retrieval` -> `chat_retrieval_flag` | not shown in excerpt | `"v2"`/`"v2-single"` = v2 composition (unless `req.utility`); `v1`/`latent`/`utility` keep v1 engines; GNN needs v2 | ui.py:4044-4053 |
| `req.latent` (✨) | falsy | no longer drops to v1 — enables lane D: `latent_enabled=True`, `keep_latent=True` | ui.py:4136-4137, 4161 |
| `req.utility` | falsy | keeps the turn on the v1 engines (`_v2_mode` forced false) | ui.py:4050 |
| `POLYMATH_CHAT_RESOLUTION` | `"0"` | P10 bounded round-2 evidence resolution, fail-open, at most one round | ui.py:4217-4224 |
| `POLYMATH_CHAT_CONSTRAINT_ALIGN` | `"0"` | CA3 post-rerank portfolio partition; default-off is byte-identical | ui.py:4291-4292 |
| `POLYMATH_CHAT_EVIDENCE_ROLES` | `"0"` | CA4 grading + epistemic state on the bundle; default-off is byte-identical | ui.py:4311-4312 |
| intent policy (`intent_policy_enabled`) | off ("default off, byte-identical when off") | intent-conditioned budget + graph ASSIST (`RELATIONSHIP` -> graph=auto) | ui.py:4132-4145 |
| skeleton routes (`skeleton_routes.enabled`) | off ("default off, byte-identical when off") | skeleton doors follow plan+mode; GRAPH mode owner choice overrides compiler verdict | ui.py:4058-4060, 4139-4142 |
| `probe_gate_floor` (budget) | `0.0` | PROBE-GATE-V1: drop probes missing the resolved question; fail-open; FAST/GNN never gated | ui.py:4146-4158 |
| `req.evidence_only` | falsy | evidence-route plan override + REASONING-BOUNDARY-V1 return path | ui.py:3958-3960, 4491 |
| `req.require_retrieval` | falsy | forces `override_rule="corpus_chat:retrieval_required"` | ui.py:3961-3962 |
| `req.carry_context` | empty | CARRY-V2 admission (artifact vs judged) | ui.py:4360-4375 |
| `POLYMATH_CHAT_SYNTH_ROLES` | not shown in excerpt | role-aware synthesis presentation reading `bundle["evidence_roles"]` | ui.py:4338-4342 (comment) |

## failure modes

1. 422 before any frame — empty message, unknown mode, unknown synthesizer, invalid scope -> typed HTTPException; look at ui.py:3852-3877.
2. `mode_requires_single_corpus` — FAST/HYBRID/GRAPH/WILDCARD/GNN over a multi-corpus scope -> `error` SSE frame + error receipt, turn ends; ui.py:4019-4027.
3. `gnn_requires_v2` — GNN with v1 retrieval or a utility turn -> 422 raised inside the generator after `scope`/`scope_ok` frames were already yielded (status can no longer change, ui.py:3842-3844); ui.py:4051-4053.
4. Silent plan fallback — shadow join timeout (>8.0s) or compiler exception -> `fallback_plan(query, reason="join_failed:...")`, turn continues with default breadth; ui.py:3982-3985.
5. Silent receipt loss — `_receipt` and `_stamp_firing` wrap their writers in `except Exception: pass`; a broken sink or ledger drops the record without failing the turn; ui.py:3905-3910, 3939-3940.
6. Silent resolution/orientation loss — P10 resolution exception -> `_resolution = None`; orientation exception -> empty `{"docs": [], "maps": []}`; ui.py:4223-4224, 4279-4280.
7. `AssemblyError` — bundle assembly failure -> `error` frame (`error_code` = exception class name), error receipt, return; ui.py:4331-4336.
8. Degraded lane (e.g. reranker parked behind extraction, "NEVER-ERROR-ON-A-COLD-MODEL") — the turn still answers; `degraded` lists why via `_merged_degraded(fast, stale)`; ui.py:4481-4488.

## invariants

- INVARIANT same request ⇒ same plan, same evidence ids, same synthesis contract on every route (ui.py:3836-3838).
- INVARIANT request validation is eager, typed HTTPExceptions before the first frame (ui.py:3840-3843).
- INVARIANT the scope is parsed once, eagerly; a malformed scope is refused, never read as "both roles"; every search of the turn honours it (ui.py:3871-3873).
- INVARIANT exactly one receipt per turn, through the transport's writer; it never breaks a turn (ui.py:3847-3848, 3905-3910).
- INVARIANT one firing receipt per turn, exactly one cause per miss, observation only (ui.py:3928-3929).
- INVARIANT wildcard bridges ride `fast["wildcard"]`, never the evidence list; wildcard never displaces answer evidence (ui.py:4125-4126, 4201-4203).
- INVARIANT `_skip_retrieval` means the corpus is not searched — the task lives in the conversation (ui.py:4061-4063).
- INVARIANT a degraded lane still answers; the answer event, /chat JSON and receipt all say why (ui.py:4481-4488).
- INVARIANT `route` and `receipt` are transport tags only — neither changes plan, retrieval decision, evidence ids or synthesis (ui.py:3846-3851).
- INVARIANT flag-gated additions (CA3, CA4) are default-off and byte-identical when off (ui.py:4289-4292, 4310-4312).

## VERIFY

```verify
grep -Fq 'async def chat_stream(req: StreamChatRequest) -> StreamingResponse:' orchestrator/orchestrator/api/ui.py
grep -Fq 'raise HTTPException(422, "message is required")' orchestrator/orchestrator/api/ui.py
grep -Fq 'mode_requires_single_corpus' orchestrator/orchestrator/api/ui.py
grep -Eq 'POLYMATH_CHAT_(RESOLUTION|CONSTRAINT_ALIGN|EVIDENCE_ROLES)", "0"' orchestrator/orchestrator/api/ui.py
grep -Fq 'timeout=8.0' orchestrator/orchestrator/api/ui.py
! grep -Fq 'chat_events_v2' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'yield _phase(' orchestrator/orchestrator/api/ui.py)" -ge 10
```
