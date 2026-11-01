# unit: frontend-v2/src/lib/contracts.ts
anchor: frontend-v2/src/lib/contracts.ts:1-462

## purpose
Typed mirrors of the backend contracts the V2 frontend consumes; the backend is the authority (FRONTEND-V2-PLAN §0.2) — frontend-v2/src/lib/contracts.ts:2-4 [DERIVED]. Declaration-only module: 65 `export interface` + 1 `export type` + 1 `export const`, no function has a body here — frontend-v2/src/lib/contracts.ts:1-462 [DERIVED]. Nothing computes policy: an absent field is shown as unknown, never substituted — frontend-v2/src/lib/contracts.ts:6-7 [DERIVED].

## public surface
Importers (FACTS, per-file not per-symbol): frontend-v2/src/App.tsx, frontend-v2/src/lib/_small-modules, frontend-v2/src/lib/api.ts, frontend-v2/src/lib/chat.ts, frontend-v2/src/lib/deep.ts, frontend-v2/src/lib/readiness.ts — materials/material-6161838080-550323405364583.md:407-414 [DERIVED].

| symbol (name:line) | kind | mirrors / signature | anchor | used by |
|---|---|---|---|---|
| SemanticReadiness:13, DocSummary:37, DocumentRow:67, DocumentRun:80, DocumentsResponse:87, UploadResult:94, LlmProvider:106, ProviderUpsertBody:119, LlmTestResult:128, ControlPlane:141, ControlPlanePool:153, PoolLanes:164, PoolLane:169, Corpus:181 | interface | `/semantic_readiness?corpus_id=` (`semantic-readiness-v1`), `/documents/summary?corpus_id=`, `GET /documents?corpus_id=`, `POST /upload`, `GET /llm/providers`, `POST /llm/providers`, `POST /llm/test`, `/control_plane?corpus_id=` (`CONTROL-PLANE-STATUS-V1`), `/control_plane/pool/{function}`, `/corpora` | frontend-v2/src/lib/contracts.ts:13-188 | — (file-level) |
| PUBLIC_MODES:196, PublicMode:197, Synthesizer:202, ReasoningMode:207, RetrievalReceipt:213, AnswerFrame:242 | const + type + interface | `["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const`; `/synthesizers` row; `answer.retrieval` on the `/chat/stream` answer frame (plan §3) | frontend-v2/src/lib/contracts.ts:196-247 | — (file-level) |
| RetrieveResponse:251 | interface | `/retrieve` | frontend-v2/src/lib/contracts.ts:251-258 | — (file-level) |
| GraphEntity:262, GraphEntities:266, GraphSource:269, GraphRelationship:272, GraphRelationships:279 | interface | GRAPH-BROWSE-V1 | frontend-v2/src/lib/contracts.ts:262-284 | — (file-level) |
| CompareArm:288, CompareResponse:303, ReviewScores:307, ReviewResponse:312 | interface | COMPARE-REVIEW-V1 | frontend-v2/src/lib/contracts.ts:288-315 | — (file-level) |
| RunSummary:318, RunProgressRow:324, GateResult:325, OpenGap:326, Qualification:327, ScoreRefusal:330, Admission:331, LivedCluster:335, ProductConcept:339, ConceptReality:340, HypothesisView:341, RegistryPrior:343, RegistryTerritory:344, RunRegistry:345, RunView:349 | interface | TRAIL-INTERFACE-V1 (`GET /adapter/runs`, `GET /adapter/{id}/view`) | frontend-v2/src/lib/contracts.ts:318-364 | — (file-level) |
| DeepResearchPlan:368, DeepPlanGoal:373, DeepCoverage:375, DeepCoverageGoal:376, DeepReportModel:378, DeepReportGoal:383, DeepFinding:385, DeepCounterFinding:386, DeepReportSource:387, DeepAudit:389 | interface | DEEP-RESEARCH-MODE-V1 §11.3 (DR7); `POST /research/deep/plan`; `event: coverage`; `result.meta.deep_research.report_model` / `.audit` | frontend-v2/src/lib/contracts.ts:368-389 | — (file-level) |
| ChatSynthesisFacet:397, ChatSynthesis:400, ChatGapClaim:408, ChatGapCheck:411 | interface | FACET-RETRIEVAL-V1 F5/F6: `result.meta.synthesis`, `result.meta.gap_check` | frontend-v2/src/lib/contracts.ts:397-411 | — (file-level) |
| ProductResearchResult:418, ProductHypothesis:428, CjItem:439, AgentReachInstall:444, AgentReachCommand:447, AgentReachFallback:449, FullResearchOffer:456, AdapterRunRef:460 | interface | PRODUCT-SEARCH-E2E (`product-search-v1`); `POST /adapter/start` → `AdapterRunRefV1` | frontend-v2/src/lib/contracts.ts:418-462 | — (file-level) |

## contracts
### PUBLIC_MODES / PublicMode — frontend-v2/src/lib/contracts.ts:196-197
- in: none (const, no params).
- out: `["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const`; `PublicMode = (typeof PUBLIC_MODES)[number]`.
- pre: —
- post: exactly 5 public modes; `VECTOR` is a backend primitive, not a public mode (plan §2) — frontend-v2/src/lib/contracts.ts:192 [DERIVED]; GNN is sent as `mode: "GNN"` through the same `/chat` path as every other mode — frontend-v2/src/lib/contracts.ts:195 [DERIVED].

### module policy — frontend-v2/src/lib/contracts.ts:1-8
- in: backend response JSON.
- out: TypeScript shapes only.
- pre: every type describes a backend-owned response shape (verified live 2026-09-10, F0 / register 11.195) — frontend-v2/src/lib/contracts.ts:4-6 [DERIVED].
- post: absent field ⇒ UI shows unknown, never derives a substitute — frontend-v2/src/lib/contracts.ts:6-7 [DERIVED].

### RetrievalReceipt.latency_ms — frontend-v2/src/lib/contracts.ts:237-239
- in: v2 = per-stage map (embed, lanes, rerank, compose, total — ms; absent stage is `null`); v1 = one number.
- out: consumer must render `total`, never the map itself.
- post: the comment records that rendering the map "rendered as 'NaNs'" — frontend-v2/src/lib/contracts.ts:238-239 [DERIVED].

## effect surface
- Postgres: none — `tables_read: []`, `tables_written: []` — materials/material-6161838080-550323405364583.md:415-417 [DERIVED].
- Qdrant / files / network / subprocess / env flags: none — the unit is declaration-only, no call expressions — frontend-v2/src/lib/contracts.ts:1-462 [DERIVED].
- Runtime values emitted: `PUBLIC_MODES` (frontend-v2/src/lib/contracts.ts:196) and derived type `PublicMode` (frontend-v2/src/lib/contracts.ts:197).

## invariants
INVARIANT: `PUBLIC_MODES` length = 5 = {FAST, HYBRID, GRAPH, WILDCARD, GNN}; `VECTOR` ∉ PUBLIC_MODES — frontend-v2/src/lib/contracts.ts:192,196 [DERIVED]
  fails-if: adding VECTOR contradicts the plan §2 exclusion; removing GNN drops the experimental fifth mode.
INVARIANT: `PublicMode` ≡ `(typeof PUBLIC_MODES)[number]` — frontend-v2/src/lib/contracts.ts:197 [DERIVED]
  fails-if: a string outside the tuple passes as a mode.
INVARIANT: `LlmProvider.api_key` ∈ {masked `…last4`, `env:NAME`} — never the real key — frontend-v2/src/lib/contracts.ts:102-109 [DERIVED]
  fails-if: raw key reaches the UI.
INVARIANT: `RetrievalReceipt.latency_ms` is v1 `number` XOR v2 `Record<string, number | null>`; rendered value = `total` — frontend-v2/src/lib/contracts.ts:237-239 [DERIVED]
  fails-if: rendering the map yields "NaNs" (recorded in the comment).
INVARIANT: `ControlPlane.pools` is a map keyed by function name; queue counters (`queued`, `processing`, `retry`, `failed`) sit at the TOP level of each pool, not nested — frontend-v2/src/lib/contracts.ts:136-137,150,153-158 [DERIVED]
  fails-if: UI reading nested counters gets `undefined`.
INVARIANT: a `GraphRelationship` is shown ⇒ `sources` attest it; unattested ones are counted in `dropped_unattested` — frontend-v2/src/lib/contracts.ts:276-283 [DERIVED]
  fails-if: unattested relationship displayed without corpus evidence.
INVARIANT: `ProductHypothesis.cj.status` ∈ {OK, PARTIAL, EMPTY, UNAVAILABLE, AGENT_REACH_REQUIRED} — frontend-v2/src/lib/contracts.ts:433 [DERIVED]
  fails-if: unhandled status string in the CJ panel.
INVARIANT: `DeepFinding.confidence` and `ChatSynthesisFacet.confidence` ∈ {strong, single_source, contested} (§11.4) — frontend-v2/src/lib/contracts.ts:384,393-395 [DERIVED]
  fails-if: two different confidence vocabularies drift apart across report and chat synthesis.
INVARIANT: `SemanticReadiness.verdict` ∈ {SEMANTIC_COMPLETE, SEMANTIC_INCOMPLETE}; `vnext.verdict` ∈ {VNEXT_COMPLETE, VNEXT_INCOMPLETE} — frontend-v2/src/lib/contracts.ts:16-17,20 [DERIVED]
  fails-if: readiness label rendered from an unrecognized verdict.

## determinism & idempotency
determinism: DETERMINISTIC — declarations plus one literal const; no clock/random/uuid/network/db/env reads anywhere in frontend-v2/src/lib/contracts.ts:1-462 [DERIVED]
idempotency: SAFE — importing has no effects; `PUBLIC_MODES` is an immutable `as const` tuple — frontend-v2/src/lib/contracts.ts:196 [DERIVED]

## failure behaviour
No handlers and no raised error codes: the module is declaration-only — frontend-v2/src/lib/contracts.ts:1-462 [DERIVED].
Failures travel as payload fields: `DocumentRun.error: string | null` — frontend-v2/src/lib/contracts.ts:84; `ReviewResponse.parse_error` with `review: ReviewScores | null` — frontend-v2/src/lib/contracts.ts:312-315; `ChatGapCheck.error` — frontend-v2/src/lib/contracts.ts:411; `RetrievalReceipt.degraded?: string[]` — frontend-v2/src/lib/contracts.ts:236.
Older-backend absence protocol: `DocSummary.run_status` "absent on an older backend" — frontend-v2/src/lib/contracts.ts:55; `profile_served` absent when the profile index could not be read — frontend-v2/src/lib/contracts.ts:52-54; `SemanticReadiness.vnext.profiled`/`vnext_served` absent — frontend-v2/src/lib/contracts.ts:25-29; `ProductResearchResult` "Every field may be missing (an older or newer backend)" — frontend-v2/src/lib/contracts.ts:415-417; `ChatSynthesis` absent on QA/lookup turns and every turn saved before F5 — frontend-v2/src/lib/contracts.ts:396. Caller then sees `undefined` and must render unknown — frontend-v2/src/lib/contracts.ts:6-7 [DERIVED].

## dumb-code flags
- Dual-shape `latency_ms?: number | Record<string, number | null>` compat wart, with the "NaNs" admission — frontend-v2/src/lib/contracts.ts:237-239; a second, different latency typing `Record<string, unknown> | null` on `CompareArm.retrieval.latency_ms` — frontend-v2/src/lib/contracts.ts:297-298 [DERIVED].
- `unknown` escape hatches: `RetrievalReceipt` fields `funnel`, `composition`, `aspects`, `weak_aspects`, `legend`, `chunks`, `used_evidence`, `final_detail`, `graph_seeds`, `graph_bounds`, `graph_degraded`, `wildcard`, `wildcard_diagnostics`, `latent` — frontend-v2/src/lib/contracts.ts:219-235; `SemanticReadiness.warnings`/`extraction` — frontend-v2/src/lib/contracts.ts:32-33; `RunView.contradictions`/`unknowns` — frontend-v2/src/lib/contracts.ts:361 [DERIVED].
- `documents?: number | string[]` count-or-ids union duplicated in `DeepCoverageGoal` and `DeepReportGoal` — frontend-v2/src/lib/contracts.ts:376,383 [DERIVED].
- `CjItem.price?: string | number | null` — prices arrive as listed strings, e.g. "US$11.85" — frontend-v2/src/lib/contracts.ts:438-441 [DERIVED].
- Hardcoded verification dates in comments that this unit cannot re-verify: 2026-09-10 — frontend-v2/src/lib/contracts.ts:5,136; 2026-09-12 — frontend-v2/src/lib/contracts.ts:66,105,138-140 [DERIVED].
- Stub `report?: { available: boolean }` for `GET /adapter/{id}/report` — frontend-v2/src/lib/contracts.ts:362 [DERIVED].

## refactor notes
- Blast radius: 6 importers — frontend-v2/src/App.tsx, frontend-v2/src/lib/_small-modules, frontend-v2/src/lib/api.ts, frontend-v2/src/lib/chat.ts, frontend-v2/src/lib/deep.ts, frontend-v2/src/lib/readiness.ts — materials/material-6161838080-550323405364583.md:407-414 [DERIVED]. Renaming any of the 67 exports touches all of them.
- Adding/removing a `PUBLIC_MODES` entry changes the `PublicMode` union and every exhaustive mode switch in the importers — frontend-v2/src/lib/contracts.ts:196-197 [DERIVED].
- Making older-backend optional fields required (`run_status`, `profile_served`, `control_ready`, `summary.processing_active`/`processing_stalled` — GAP-1/GAP-4 additions, composed server-side, UI only renders) breaks the absence path — frontend-v2/src/lib/contracts.ts:52-56,138-140 [DERIVED].
- Collapsing `latency_ms` to one shape breaks either v1 or v2 backends; consumers read `total` — frontend-v2/src/lib/contracts.ts:237-239 [DERIVED].
- `Corpus.query_ready` is carried ONLY so the UI can refuse to use it (plan §7) — do not start branching on it — frontend-v2/src/lib/contracts.ts:180 [DERIVED].
- Any new field must mirror an already-owned backend response shape; no client-side derivation of substitutes — frontend-v2/src/lib/contracts.ts:4-7 [DERIVED].

## VERIFY
```verify
grep -Fq 'export const PUBLIC_MODES = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const' frontend-v2/src/lib/contracts.ts
grep -Fq 'export type PublicMode = (typeof PUBLIC_MODES)[number]' frontend-v2/src/lib/contracts.ts
grep -Fq 'latency_ms?: number | Record<string, number | null>' frontend-v2/src/lib/contracts.ts
grep -Fq 'dropped_unattested: number' frontend-v2/src/lib/contracts.ts
grep -Fq 'mode: "GNN"' frontend-v2/src/lib/contracts.ts
test "$(grep -c -F 'export interface' frontend-v2/src/lib/contracts.ts)" -ge 65
! grep -Fq 'export function' frontend-v2/src/lib/contracts.ts
```
