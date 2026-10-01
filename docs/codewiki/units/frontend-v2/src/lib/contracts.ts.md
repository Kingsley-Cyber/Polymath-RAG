# unit: frontend-v2/src/lib/contracts.ts
anchor: frontend-v2/src/lib/contracts.ts:1-397

## purpose
Typed mirrors of the backend contracts the V2 frontend consumes; the backend is the authority, verified live 2026-09-10 (F0 / register 11.195) — frontend-v2/src/lib/contracts.ts:2-5 [DERIVED]
Nothing here computes policy: if a field is absent the UI shows it as unknown, it never derives a substitute — frontend-v2/src/lib/contracts.ts:6-8 [DERIVED]
Pure type module: 57 interfaces + 1 const + 1 type, zero functions, zero imports — frontend-v2/src/lib/contracts.ts:1-396 [DERIVED]
File-level importers (FACTS.importers): `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/deep.ts` — per-symbol attribution unknown, so "used by" is "—" below.

## public surface

readiness / documents / corpora
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SemanticReadiness | interface | mirrors `/semantic_readiness?corpus_id=`, contract `semantic-readiness-v1`: `{ contract, corpus_id, verdict, counts, vnext, warnings?, extraction? }` | frontend-v2/src/lib/contracts.ts:13-31 | — |
| DocSummary | interface | one row of `/documents/summary?corpus_id=`: per-doc map/profile/graph counts + `vnext_ready` | frontend-v2/src/lib/contracts.ts:34-46 | — |
| DocumentRow | interface | `GET /documents?corpus_id=` row: identity authority for Files screen (`source_name` survives ingestion) | frontend-v2/src/lib/contracts.ts:48-63 | — |
| DocumentRun | interface | `{ run_id, status, created_at, error: string \| null }` | frontend-v2/src/lib/contracts.ts:65-70 | — |
| DocumentsResponse | interface | `{ corpus_id, documents: DocumentRow[], runs: DocumentRun[] }` | frontend-v2/src/lib/contracts.ts:72-76 | — |
| UploadResult | interface | `POST /upload` reply fields the UI surfaces (incl. `near_duplicate_override`) | frontend-v2/src/lib/contracts.ts:79-85 | — |
| Corpus | interface | `/corpora` row incl. `query_ready`, `query_enabled` | frontend-v2/src/lib/contracts.ts:165-173 | — |

llm / control plane
| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| LlmProvider | interface | `GET /llm/providers` row; `api_key` masked or `env:NAME` | frontend-v2/src/lib/contracts.ts:87-100 | — |
| ProviderUpsertBody | interface | `POST /llm/providers` body; empty `api_key` on existing provider keeps stored key | frontend-v2/src/lib/contracts.ts:102-110 | — |
| LlmTestResult | interface | `POST /llm/test` one-shot check `{ ok, model, reply?, error? }` | frontend-v2/src/lib/contracts.ts:112-118 | — |
| ControlPlane | interface | `/control_plane?corpus_id=` (CONTROL-PLANE-STATUS-V1); `pools` is a map keyed by function name, queue counters at TOP level of each pool | frontend-v2/src/lib/contracts.ts:120-136 | — |
| ControlPlanePool | interface | `{ lanes?, queued?, processing?, retry?, failed?, provider? }` | frontend-v2/src/lib/contracts.ts:138-146 | — |
| PoolLanes | interface | `/control_plane/pool/{function}` — model → lanes, ENV NAMES only | frontend-v2/src/lib/contracts.ts:148-152 | — |
| PoolLane | interface | `{ lane, account_env, configured, reachability, role, family, capacity, live }` | frontend-v2/src/lib/contracts.ts:154-163 | — |

chat
| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| PUBLIC_MODES | const | `["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const` | frontend-v2/src/lib/contracts.ts:181 | — |
| PublicMode | type | `(typeof PUBLIC_MODES)[number]` | frontend-v2/src/lib/contracts.ts:182 | — |
| Synthesizer | interface | `/synthesizers` catalog row (grouping fields come from the catalog, never from parsing ids) | frontend-v2/src/lib/contracts.ts:184-191 | — |
| ReasoningMode | interface | `{ id, label, description }` | frontend-v2/src/lib/contracts.ts:192 | — |
| RetrievalReceipt | interface | `answer.retrieval` on `/chat/stream` answer frame — Query Inspector's whole source of truth | frontend-v2/src/lib/contracts.ts:194-225 | — |
| AnswerFrame | interface | `{ kind, latency_ms?, result?, retrieval? }` | frontend-v2/src/lib/contracts.ts:227-232 | — |

retrieve / graph / compare / review
| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| RetrieveResponse | interface | `/retrieve`: `{ evidence, meta, query, selected_documents, selected_sections, trace }` | frontend-v2/src/lib/contracts.ts:236-243 | — |
| GraphEntity / GraphEntities | interface | GRAPH-BROWSE-V1 entity lookup | frontend-v2/src/lib/contracts.ts:247-253 | — |
| GraphSource | interface | `{ doc_id, chunk_id, source_name, text }` | frontend-v2/src/lib/contracts.ts:254-256 | — |
| GraphRelationship / GraphRelationships | interface | GRAPH-BROWSE-V1 relationships incl. `dropped_unattested` | frontend-v2/src/lib/contracts.ts:257-269 | — |
| CompareArm / CompareResponse | interface | COMPARE-REVIEW-V1 compare arms | frontend-v2/src/lib/contracts.ts:273-290 | — |
| ReviewScores / ReviewResponse | interface | COMPARE-REVIEW-V1 review: `review: ReviewScores \| null`, `parse_error: string \| null` | frontend-v2/src/lib/contracts.ts:292-300 | — |

trail (TRAIL-INTERFACE-V1: `GET /adapter/runs`, `GET /adapter/{id}/view`)
| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| RunSummary | interface | run list row incl. `agent_identity`, `owner`, `outcome` | frontend-v2/src/lib/contracts.ts:303-308 | — |
| RunProgressRow / GateResult / OpenGap / Qualification / ScoreRefusal | interface | progress + qualification/scoring sections | frontend-v2/src/lib/contracts.ts:309-315 | — |
| Admission / LivedCluster / ProductConcept / ConceptReality / HypothesisView | interface | evidence admissions, clusters, concepts | frontend-v2/src/lib/contracts.ts:316-326 | — |
| RegistryPrior / RegistryTerritory / RunRegistry | interface | T5 registry as the run met it (owner's view only) | frontend-v2/src/lib/contracts.ts:327-333 | — |
| RunView | interface | full run view: `{ run, progress, sections, other_output_keys, contradictions, unknowns, stored_result_shadowed, report?, registry? }` | frontend-v2/src/lib/contracts.ts:334-349 | — |

deep research / chat synthesis
| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| DeepResearchPlan / DeepPlanGoal | interface | `POST /research/deep/plan` — planner queries + controller quota (one model call, no run) | frontend-v2/src/lib/contracts.ts:352-358 | — |
| DeepCoverage / DeepCoverageGoal | interface | `event: coverage` frames after each level | frontend-v2/src/lib/contracts.ts:359-361 | — |
| DeepReportModel / DeepReportGoal / DeepFinding / DeepCounterFinding / DeepReportSource / DeepAudit | interface | `result.meta.deep_research.report_model` + `.audit` (§11.4) | frontend-v2/src/lib/contracts.ts:362-374 | — |
| ChatSynthesisFacet / ChatSynthesis | interface | `result.meta.synthesis` on GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turns (FACET-RETRIEVAL-V1 F5/F6); absent on QA/lookup turns and pre-F5 turns | frontend-v2/src/lib/contracts.ts:378-390 | — |
| ChatGapClaim / ChatGapCheck | interface | `result.meta.gap_check` — re-search of "not covered" claims | frontend-v2/src/lib/contracts.ts:391-396 | — |

## contracts
No functions exist; the only runtime export is `PUBLIC_MODES`.
- PUBLIC_MODES — out: the 5 public mode strings; VECTOR is deliberately excluded ("a backend primitive, not a public mode", plan §2) and GNN is "the experimental fifth mode" sent as `mode: "GNN"` through the same `/chat` path — frontend-v2/src/lib/contracts.ts:177-181 [DERIVED]
- PublicMode — derived from the const via `typeof`, never hand-listed — frontend-v2/src/lib/contracts.ts:182 [DERIVED]
- Every interface mirrors a backend-owned response shape; the backend never returns a raw key, and `api_key_set` says whether a usable key resolves — frontend-v2/src/lib/contracts.ts:4-8, 87-95 [DERIVED]

Endpoint → interface couplings (change together):
| interface | backend route / contract | anchor |
|---|---|---|
| SemanticReadiness | `/semantic_readiness?corpus_id=` — `semantic-readiness-v1` | frontend-v2/src/lib/contracts.ts:12-13 |
| DocumentRow | `GET /documents` (orchestrator/api/ui.py::documents, verified 2026-09-12) | frontend-v2/src/lib/contracts.ts:48-52 |
| LlmProvider | `GET /llm/providers` (orchestrator/api/ui.py::llm_providers, verified 2026-09-12) | frontend-v2/src/lib/contracts.ts:87-91 |
| ControlPlane | `/control_plane?corpus_id=` — `CONTROL-PLANE-STATUS-V1` (verified live 2026-09-10) | frontend-v2/src/lib/contracts.ts:120-126 |
| Corpus | `/corpora` | frontend-v2/src/lib/contracts.ts:165-166 |
| RetrievalReceipt | `answer.retrieval` on `/chat/stream` | frontend-v2/src/lib/contracts.ts:194-198 |
| Graph* | GRAPH-BROWSE-V1 | frontend-v2/src/lib/contracts.ts:245-264 |
| Compare*/Review* | COMPARE-REVIEW-V1 | frontend-v2/src/lib/contracts.ts:271-288 |
| Run*/Registry*/Admission… | TRAIL-INTERFACE-V1 (`GET /adapter/runs`, `GET /adapter/{id}/view`) | frontend-v2/src/lib/contracts.ts:302-303 |
| Deep* | DEEP-RESEARCH-MODE-V1 §11.3 (DR7), report model §11.4 | frontend-v2/src/lib/contracts.ts:351-352 |
| ChatSynthesis* / ChatGapCheck | FACET-RETRIEVAL-V1 F5 / F6 | frontend-v2/src/lib/contracts.ts:376-377 |

## effect surface
- Postgres tables read: none; tables written: none (FACTS `tables_read: []`, `tables_written: []`).
- No imports of any kind in the file — frontend-v2/src/lib/contracts.ts:1-396 [DERIVED]
- No network, files, subprocesses, env flags — type declarations only; single runtime binding is the const `PUBLIC_MODES` — frontend-v2/src/lib/contracts.ts:181 [DERIVED]

## invariants
INVARIANT: len(PUBLIC_MODES) = 5, values exactly `FAST`, `HYBRID`, `GRAPH`, `WILDCARD`, `GNN` — frontend-v2/src/lib/contracts.ts:181 [DERIVED]
  fails-if: PublicMode union and the mode strings the backend accepts desync; `/chat` receives an unknown `mode`.
INVARIANT: PublicMode = (typeof PUBLIC_MODES)[number] (derived, not hand-listed) — frontend-v2/src/lib/contracts.ts:182 [DERIVED]
  fails-if: someone re-declares the union by hand and it drifts from the const.
INVARIANT: LlmProvider.api_key ∈ {masked last-4 chars, `"env:NAME"`} — never a raw key — frontend-v2/src/lib/contracts.ts:87-95 [DERIVED]
  fails-if: a raw credential would be rendered or stored by the UI.
INVARIANT: RetrievalReceipt.latency_ms is v1 `number` OR v2 per-stage map (embed, lanes, rerank, compose, total; absent stage = null); UI renders `total`, never the map — frontend-v2/src/lib/contracts.ts:222-224 [DERIVED]
  fails-if: rendering the map directly produced "NaNs" (per the code comment).
INVARIANT: GraphRelationships.dropped_unattested ≥ 0 = relationships withheld because nothing in THIS corpus attests them — frontend-v2/src/lib/contracts.ts:267-268 [DERIVED]
  fails-if: unattested relationships displayed as if sourced.
INVARIANT: DeepFinding.confidence ∈ {`strong`, `single_source`, `contested`} (strong = two or more books) — frontend-v2/src/lib/contracts.ts:369-370, 378-380 [DERIVED]
  fails-if: UI branches on an undocumented confidence string.
INVARIANT: DeepCoverageGoal.documents is `number | string[]` — a count OR doc ids, one meaning per response — frontend-v2/src/lib/contracts.ts:361 [DERIVED]
  fails-if: consumer treats an id array as a count.
INVARIANT: Corpus.query_ready is carried ONLY so the UI can refuse to use it (plan §7); gating uses query_enabled — frontend-v2/src/lib/contracts.ts:165-172 [DERIVED]
  fails-if: consumer queries a corpus because query_ready is true.
INVARIANT: RunView.registry appears only on the owner's view ("a friend's view has no `registry` key") — frontend-v2/src/lib/contracts.ts:327-328, 348 [DERIVED]
  fails-if: non-owner UI assumes registry is present.
INVARIANT: ControlPlane.control_ready.state ∈ {`"ready"`, `"blocked"`, `"degraded"`}; composed server-side, UI does not re-derive it from `/ready` + `/health/pipeline` — frontend-v2/src/lib/contracts.ts:123-130 [DERIVED]
  fails-if: client-side recomputation disagrees with the server's composed state.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env reads; zero import statements, one const literal — frontend-v2/src/lib/contracts.ts:1-396, 181 [DERIVED]
idempotency: SAFE — importing the module has no side effects beyond defining PUBLIC_MODES; everything else is compile-time types — frontend-v2/src/lib/contracts.ts:181 [DERIVED]

## failure behaviour
No runtime handlers exist — all exports are types except PUBLIC_MODES — frontend-v2/src/lib/contracts.ts:181 [DERIVED]
Consumer-facing failure rule: an absent optional field is shown as unknown, never substituted — e.g. `vnext.profiled` is "absent on an older backend" (`number | null`), which must surface as unknown, not 0 — frontend-v2/src/lib/contracts.ts:6-8, 26-27 [DERIVED]
Reviewer parse failure is modelled, not thrown: `ReviewResponse.review = ReviewScores | null` with `parse_error: string | null` and `raw: string | null` — frontend-v2/src/lib/contracts.ts:297-300 [DERIVED]
Backend shape drift appears as TS compile errors here or `undefined` at runtime; comments pin verification dates 2026-09-10 / 2026-09-12 as the drift checkpoint — frontend-v2/src/lib/contracts.ts:4-5, 51, 90, 122 [DERIVED]

## dumb-code flags
- `latency_ms?: number | Record<string, number | null>` — dual-shape field kept for v1/v2 compat; comment records that rendering the map "rendered as NaNs" — frontend-v2/src/lib/contracts.ts:222-224 [DERIVED]
- `documents?: number | string[]` duplicated with two meanings (count vs doc-id list) in DeepCoverageGoal and DeepReportGoal — frontend-v2/src/lib/contracts.ts:361, 368 [DERIVED]
- Long `unknown` passthrough block in RetrievalReceipt (`funnel`, `composition`, `aspects`, `weak_aspects`, `legend`, `chunks`, `used_evidence`, `final_detail`, `graph_seeds`, `graph_bounds`, `graph_degraded`, `wildcard`, `wildcard_diagnostics`, `latent`) — untyped mirrors; typos inside them are invisible to the compiler — frontend-v2/src/lib/contracts.ts:204-219 [DERIVED]
- More loose `unknown`s: SemanticReadiness `warnings?: unknown[]`, `extraction?: unknown`; PoolLane `live: Record<string, unknown>` — frontend-v2/src/lib/contracts.ts:29-30, 163 [DERIVED]
- `contract: string` repeated as a plain string in SemanticReadiness, ControlPlane, GraphEntities, GraphRelationships, CompareResponse, ReviewResponse — no branded type, nothing enforces each equals its contract id — frontend-v2/src/lib/contracts.ts:14, 127, 252, 265, 288, 298 [DERIVED]
- Typing discipline is inconsistent: `control_ready.state` is a real string-literal union (`"ready" | "blocked" | "degraded"`) while `SemanticReadiness.verdict` / `vnext.verdict` are bare `string` with legal values only in comments (`SEMANTIC_COMPLETE | SEMANTIC_INCOMPLETE`, `VNEXT_COMPLETE | VNEXT_INCOMPLETE`) — frontend-v2/src/lib/contracts.ts:17-18, 21-22, 129 [DERIVED]
- Dead-weight compat: `Corpus.query_ready` exists only so the UI can refuse to use it — frontend-v2/src/lib/contracts.ts:165-166 [DERIVED]

## refactor notes
Blast radius: five importers (App.tsx, lib/_small-modules, lib/api.ts, lib/chat.ts, lib/deep.ts per FACTS.importers) — renaming or removing any of the 59 exports touches all of them.
Do not add computed or derived fields — the header contract forbids client-side policy computation; absent field ⇒ unknown — frontend-v2/src/lib/contracts.ts:4-8 [DERIVED]
PUBLIC_MODES values are wire literals sent as `mode: "GNN"` etc.; do not rename or reorder semantics, and do not add `VECTOR` (plan §2 excludes it) — frontend-v2/src/lib/contracts.ts:177-182 [DERIVED]
Field changes require re-verification against the named backend authorities: orchestrator/api/ui.py::documents, orchestrator/api/ui.py::llm_providers, and the live `/control_plane` response shape (`pools` map, top-level queue counters) — frontend-v2/src/lib/contracts.ts:48-51, 87-90, 120-125 [DERIVED]
Narrowing `unknown` fields (e.g. RetrievalReceipt lanes/funnel) is reader-safe; making optional fields required breaks consumers that handle "absent = older backend" (e.g. `vnext.profiled`) — frontend-v2/src/lib/contracts.ts:26-27, 204-219 [DERIVED]

## VERIFY
```verify
grep -Fq 'export const PUBLIC_MODES = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const;' frontend-v2/src/lib/contracts.ts
grep -Fq 'export type PublicMode = (typeof PUBLIC_MODES)[number];' frontend-v2/src/lib/contracts.ts
grep -Fq 'latency_ms?: number | Record<string, number | null>;' frontend-v2/src/lib/contracts.ts
grep -Fq 'dropped_unattested: number;' frontend-v2/src/lib/contracts.ts
! grep -Fq 'import ' frontend-v2/src/lib/contracts.ts
test "$(grep -c -F 'export interface' frontend-v2/src/lib/contracts.ts)" -ge 50
```
