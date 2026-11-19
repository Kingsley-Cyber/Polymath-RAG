# flow: chat-turn
A chat turn end to end: the browser posts /chat/stream (modes FAST, HYBRID, GRAPH, WILDCARD, GNN), the query compiler plans subqueries and facets, retrieval composes evidence, the model synthesises a cited answer, the receipt is written, the SSE frames reach the UI.
ENTRY POST /chat/stream -> orchestrator/orchestrator/api/ui.py:5005 chat_stream (web class: user)

## hops
| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `chat_stream` wraps `chat_events(req)` in a StreamingResponse, media_type `text/event-stream`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | orchestrator/orchestrator/api/ui.py:5005-5010 [DERIVED] | StreamChatRequest -> SSE frame stream | transport-level only; frames come from hop 2+ |
| 2 | Eager validation: empty message -> 422 `message is required`; mode upper-cased, `VECTOR`->`FAST`, whitelist `FAST/HYBRID/GRAPH/ASK/WILDCARD/GNN` else 422 `unknown_mode` | orchestrator/orchestrator/api/ui.py:3990-3998 [DERIVED] | req -> accepted (query, ui_mode) | typed HTTPException before the first frame |
| 3 | Synthesizer check: `ollama:` / `litellm:` prefixes parsed into (llm_model, llm_backend); anything else must be `deterministic-template-v3` else 422 `unknown_synthesizer` | orchestrator/orchestrator/api/ui.py:3999-4008 [DERIVED] | req.synthesizer -> synth, llm_model, llm_backend | 422 before first frame |
| 4 | Role scope parsed ONCE, eagerly: `parse_scope`; `ScopeError` -> 422 `invalid_scope`; malformed scope never read as "both roles" | orchestrator/orchestrator/api/ui.py:4009-4015 [DERIVED] | req.scope -> _role_scope | 422 before first frame |
| 5 | Scope resolved: `resolve_http_scope(conn, req)` inside `tx()`; `scope` / `scope_ok` phase frames; `_mark("scope")` | orchestrator/orchestrator/api/ui.py:4050-4055 [DERIVED] | req -> scope (mode, corpus_ids) | later guards at hop 11 |
| 6 | Product intent: `_detect_product(query, req.history, force)` unless mode ASK or `req.product is False`; `ProductTurn` built; `product_intent` frame | orchestrator/orchestrator/api/ui.py:4059-4070 [DERIVED] | query, history -> _product (or None) | detection miss = no product block |
| 7 | Product library routing when scope has >1 corpus: `_product.route(...)` picks one corpus; scope narrowed to `(_chosen,)`; `product_route` / `product_route_done` frames | orchestrator/orchestrator/api/ui.py:4071-4084 [DERIVED] | corpus_ids -> _chosen | no chosen library = scope unchanged |
| 8 | Compiler: `_compiler_flag(req.compiler)`; if not `off`, `ThreadPoolExecutor(max_workers=1)` submits `_compile_chat_plan` (session_key, titles_rank, corpus_explorer); flag `on` joins now and `_mark("compile")` | orchestrator/orchestrator/api/ui.py:4109, 4129-4142 [DERIVED] | query, history, corpora -> _plan | shadow runs beside retrieval; `on` is the serial stage 0 |
| 9 | Plan applied: product `steer_plan`; `evidence_only` / `require_retrieval` -> `plan_for_evidence_route`; `_skip_retrieval` decided; `_retrieval_text = retrieval_text_for(_plan)`; `_stamp_firing()`; `compile` frame | orchestrator/orchestrator/api/ui.py:4143-4163 [DERIVED] | _plan -> retrieval query or skip | join failure handled at hop 10's helper (row 19) |
| 10 | ASK mode short-circuit: `ask(AskRequest(...))` over stored knowledge objects; `ask_done` frame; `answer` frame kind `ask`; `done` frame; return | orchestrator/orchestrator/api/ui.py:4183-4207 [DERIVED] | question, corpus ids -> objects, counts | typed counts in `ask_done` frame |
| 11 | Scope guards: empty scope -> error frame `QUERY_SCOPE_EMPTY` + receipt + return; `len(corpus_ids) != 1` -> error frame `mode_requires_single_corpus` + receipt + return | orchestrator/orchestrator/api/ui.py:4209-4230 [DERIVED] | scope -> corpus_id (exactly one) | typed refusal, never an IndexError |
| 12 | Engine choice: `_rflag = chat_retrieval_flag(req.retrieval)`; `_v2_mode = _rflag in ("v2", "v2-single") and not req.utility`; GNN without v2 -> 422 `gnn_requires_v2` | orchestrator/orchestrator/api/ui.py:4248-4256 [DERIVED] | req.retrieval, req.utility -> _v2_mode | 422 before retrieval |
| 13 | Skip-retrieval path (plan says conversation): `evidence_rows = []`, empty `fast`, `retrieve_skipped` frame | orchestrator/orchestrator/api/ui.py:4264-4275 [DERIVED] | _plan -> no corpus search | carry artifact mode still runs (hop 20) |
| 14 | GRAPH on v1: `graph_retrieve(_retrieval_text, corpus_id, latent=req.latent, utility=req.utility)`; evidence rows from documents/sections; `graph` / `graph_done` frames | orchestrator/orchestrator/api/ui.py:4276-4320 [DERIVED] | retrieval text -> g (documents, graph_relationships) | rollback boundary (`retrieval: v1` / `latent`) |
| 15 | v2 composition: `chat_retrieve_mode` with budget (intent policy, `req.latent` -> lane D `latent_enabled=True`, skeleton routes), probe gate, subqueries with origin provenance, facets, WILDCARD question gate | orchestrator/orchestrator/api/ui.py:4325-4382 [DERIVED] | retrieval text, plan queries -> fast | flag-gated extras default off |
| 16 | v1 fallbacks: FAST -> `fast_retrieve`; WILDCARD -> `wildcard_retrieve` (bridges ride `fast["wildcard"]`, never the evidence list); else `hybrid_fast_retrieve` | orchestrator/orchestrator/api/ui.py:4402-4415, 4328-4329 [DERIVED] | retrieval text -> fast | v1 engines stay as rollback boundary |
| 17 | Post-retrieval receipts: optional P10 `_maybe_resolve` (env-gated), `_apply_latent_selection` (additive latent pass), `evidence_rows = _evidence_rows(fast["evidence"])`, `retrieve_done` frame; GRAPH `graph`/`graph_done`; `wildcard` frame | orchestrator/orchestrator/api/ui.py:4421-4465 [DERIVED] | fast -> evidence_rows, receipts | latent pass reassigns fast["evidence"] before CA3/CA4 |
| 18 | Summaries + orientation: document summaries from `fast["selected_documents"]`; parent chunk summaries via Postgres `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)`; `_load_orientation` | orchestrator/orchestrator/api/ui.py:4466-4489 [DERIVED] | parent_ids -> rows, orientation | orientation failure degrades silently to `{"docs": [], "maps": []}` |
| 19 | CA3 + CA4 (both env-gated): `align_evidence_for_constraints` reorders evidence_rows per resolved constraints; `grade_evidence` -> `_grades_by_chunk`, `_epistemic` | orchestrator/orchestrator/api/ui.py:4491-4519 [DERIVED] | evidence_rows, _plan -> reordered rows, grades | default-off => byte-identical |
| 20 | Bundle: `assemble_evidence_bundle` with resolvers + summaries; extras added (`evidence_roles`, `evidence_latent`, `evidence_paths`, `facets_uncovered`, `support_roles`/`epistemic`, `orientation`, `derived_insights`); `assemble` / `assemble_done` frames | orchestrator/orchestrator/api/ui.py:4521-4563, 4591-4592 [DERIVED] | evidence_rows, summaries -> bundle | `AssemblyError` -> error frame + receipt + return (4536-4541) |
| 21 | CARRY-V2: `_carry_candidates` + `_admit_carry`; skip-retrieval turns use artifact mode (scorer all `1.0`, floor `0.0`, cap `_CARRY_ARTIFACT_CAP`); admitted items extend `bundle["evidence_bundle"]`; `carry` frame | orchestrator/orchestrator/api/ui.py:4565-4586 [DERIVED] | req.carry_context -> _citems, _carry_meta | no relevance gate on artifact mode (score meaningless) |
| 22 | Presentation: `_evidence_legend(bundle)`, `_render_derived` (`require_proof=_synth_contract_enabled()`), `_render_relations`, chunk_inventory (source_name, title, heading_path, human_locator for the Sources panel) | orchestrator/orchestrator/api/ui.py:4587-4617 [DERIVED] | bundle -> legend, inventory | derived insights need proof under the synth contract |
| 23 | Retrieval receipt dict starts (`mode`: `VECTOR` if FAST else ui_mode, `evidence_count`, `graph_fact_count`, MODE-COMPOSITION receipts) — SOURCE excerpt ends inside this dict | orchestrator/orchestrator/api/ui.py:4621-4625 [DERIVED] | fast, evidence_rows -> retrieval dict | later fields not shown in SOURCE |
| 24 | Synthesis: `grounded_answer` imported at function start; SYNTHESIS-V2 contract per docstring; frames `token`, `reasoning`, `answer`, `done` (frame list from the docstring; the SOURCE excerpt ends before the call site) | orchestrator/orchestrator/api/ui.py:4019, 3972-3976 [DERIVED] | bundle, retrieval -> answer frames | epistemic gate requires >=1 DIRECT/PARTIAL chunk (4557-4561 comment) |
| 25 | Receipt written: one `_receipt_payload` per turn that ran, through `sink` (default `_default_receipt_sink(route)`); sink adds transport `kind` and `client`; error paths also receipt | orchestrator/orchestrator/api/ui.py:4016, 4043-4048, 3984-3988, 4219, 4539 [DERIVED] | turn state -> receipt payload | sink exception swallowed (`except Exception: pass`) |

## state written
- JSONL rate ledger: the turn's ONE corpus-explore firing receipt (`CORPUS-EXPLORE-FIRING-V1`), recorded once via `_ce_record(rec, q0=query)` — orchestrator/orchestrator/api/ui.py:4114-4122 [DERIVED]
- Turn receipt: `_receipt_payload(req, question=query, scope=scope, route=route, ...)` through `sink`; default `_default_receipt_sink(route)`; final store not shown in SOURCE — orchestrator/orchestrator/api/ui.py:4016, 4043-4048, 3984-3988 [DERIVED]
- Postgres, read only on this path: scope resolution in `tx()` (orchestrator/orchestrator/api/ui.py:4051-4052 [DERIVED]); chunk summaries `SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)` (orchestrator/orchestrator/api/ui.py:4474-4478 [DERIVED]). No Postgres write is shown in SOURCE.

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `req.compiler` (off / shadow / on) | not shown in SOURCE | shadow: plan compiled beside retrieval, receipt only, no added latency; on: serial stage 0, sets `_skip_retrieval` and the retrieval text | orchestrator/orchestrator/api/ui.py:4109, 4129-4141 |
| `req.retrieval` (v1 / v2 / v2-single; `latent` / `utility` are v1 knobs) | not shown in SOURCE | `v2`/`v2-single` -> MODE-COMPOSITION engine; v1 knobs keep the v1 engines | orchestrator/orchestrator/api/ui.py:4248-4253 |
| `POLYMATH_CHAT_RETRIEVAL` | not shown in SOURCE | named in the `gnn_requires_v2` error: GNN needs `v2`, no utility turn | orchestrator/orchestrator/api/ui.py:4254-4256 |
| `req.latent` (B12 ✨) | off | no longer drops to v1; enables lane D: `_replace(_budget, latent_enabled=True)` | orchestrator/orchestrator/api/ui.py:4251-4252, 4339-4340 |
| `req.product` | auto (detect) | True forces product mode, False turns it off | orchestrator/orchestrator/api/ui.py:4056-4064 |
| `req.evidence_only` / `req.require_retrieval` | off | evidence route plan; `require_retrieval` overrides rule `corpus_chat:retrieval_required` | orchestrator/orchestrator/api/ui.py:4146-4150 |
| `POLYMATH_CHAT_RESOLUTION` | `"0"` | bounded round-2 evidence resolution for unsupported needs; flag-gated, fail-open, at most one round | orchestrator/orchestrator/api/ui.py:4421-4429 |
| `POLYMATH_CHAT_CONSTRAINT_ALIGN` | `"0"` | CA3: post-rerank reorder so constraint-satisfying evidence leads; default-off => byte-identical | orchestrator/orchestrator/api/ui.py:4491-4501 |
| `POLYMATH_CHAT_EVIDENCE_ROLES` | `"0"` | CA4: DIRECT/PARTIAL/RELATED grading + epistemic state driving the answerability gate | orchestrator/orchestrator/api/ui.py:4511-4519 |
| `POLYMATH_CHAT_SYNTH_ROLES` | not shown in SOURCE | role-aware synthesis presentation (named in comment) | orchestrator/orchestrator/api/ui.py:4543-4545 |
| skeleton routes `enabled()` | not shown in SOURCE | GRAPH chosen by owner keeps the hop; budget doors follow plan + mode | orchestrator/orchestrator/api/ui.py:4261-4263, 4341-4343 |
| intent policy `intent_policy_enabled()` | off ("default off, byte-identical when off") | intent -> budget policy; explicit `req.latent` always wins the latent toggle | orchestrator/orchestrator/api/ui.py:4335-4340 |
| probe gate `budget.probe_gate_floor` | `0.0` (default off) | cross-encoder gate drops probes that miss the resolved question; fail-open; FAST / GNN never gated | orchestrator/orchestrator/api/ui.py:4348-4361 |

## failure modes
1. Symptom: 422 with no frame emitted -> cause: eager validation of message / mode / synthesizer / scope (a streaming response cannot change its status after the first frame) -> look at orchestrator/orchestrator/api/ui.py:3978-3982, 3990-4015.
2. Symptom: `error` frame `QUERY_SCOPE_EMPTY` -> cause: resolved scope has no library -> look at orchestrator/orchestrator/api/ui.py:4209-4221 (typed refusal, not IndexError).
3. Silent fallback: the `QueryScopeEmpty` typed class import fails -> the same detail is written as a hardcoded dict -> look at orchestrator/orchestrator/api/ui.py:4212-4217.
4. Symptom: `error` frame `mode_requires_single_corpus` -> cause: this mode retrieves over exactly one corpus, scope has more -> look at orchestrator/orchestrator/api/ui.py:4222-4230.
5. Symptom: 422 `gnn_requires_v2` -> cause: GNN mode on the v1 engine -> look at orchestrator/orchestrator/api/ui.py:4254-4256.
6. Silent fallback: compiler join fails or times out (`timeout=8.0`) -> `fallback_plan(query, reason="join_failed:*")` -> look at orchestrator/orchestrator/api/ui.py:4167-4179.
7. Silent degradation: CJ product lookups raise -> `retrieval["degraded"]` gains `component: "product_search"`, `state: "failed"`; the answer stands without its product block -> look at orchestrator/orchestrator/api/ui.py:4086-4103.
8. Silent swallow: firing-ledger write and receipt sink are wrapped in `except Exception: pass` (never breaks a turn) -> look at orchestrator/orchestrator/api/ui.py:4126, 4043-4048.
9. Silent fallback: P10 resolution raises -> `_resolution = None`, turn continues -> look at orchestrator/orchestrator/api/ui.py:4421-4429.
10. Silent fallback: `_load_orientation` raises -> `orientation = {"docs": [], "maps": []}` -> look at orchestrator/orchestrator/api/ui.py:4479-4485.
11. Symptom: `error` frame named after the exception class -> cause: `AssemblyError` from `assemble_evidence_bundle` -> receipt written, turn ends -> look at orchestrator/orchestrator/api/ui.py:4536-4541.

## invariants
- INVARIANT same request => same plan, same evidence ids, same synthesis contract on every route (`/chat/stream` streams the frames; `/chat` and MCP `ask` drain them through `run_chat`) — orchestrator/orchestrator/api/ui.py:3974-3976
- INVARIANT request validation happens EAGERLY: typed HTTPExceptions before the first frame — orchestrator/orchestrator/api/ui.py:3978-3982
- INVARIANT the receipt payload is built once, in the runtime, for every turn that ran — orchestrator/orchestrator/api/ui.py:3984-3986
- INVARIANT `route` and `receipt` are transport tags only; neither changes the plan, the retrieval decision, the evidence ids or the synthesis — orchestrator/orchestrator/api/ui.py:3984-3989
- INVARIANT a malformed role scope is refused before the first frame, never read as "both roles"; every search of the turn honours it — orchestrator/orchestrator/api/ui.py:4009-4011
- INVARIANT `_skip_retrieval = (not _plan.retrieval_required) and ui_mode != "ASK"` — orchestrator/orchestrator/api/ui.py:4153
- INVARIANT wildcard bridges ride `fast["wildcard"]`, never the evidence list — orchestrator/orchestrator/api/ui.py:4328-4329
- INVARIANT the epistemic state drives the answerability gate: it must be grounded in >=1 DIRECT/PARTIAL chunk, else the answer states the gap — orchestrator/orchestrator/api/ui.py:4557-4561

## VERIFY
```verify
grep -Fq 'def chat_stream' orchestrator/orchestrator/api/ui.py
grep -Fq 'message is required' orchestrator/orchestrator/api/ui.py
grep -Fq 'deterministic-template-v3' orchestrator/orchestrator/api/ui.py
grep -Fq 'mode_requires_single_corpus' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_CHAT_CONSTRAINT_ALIGN' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_CHAT_EVIDENCE_ROLES' orchestrator/orchestrator/api/ui.py
grep -Eq 'gnn_requires_v2' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'yield _phase(' orchestrator/orchestrator/api/ui.py)" -ge 10
```
