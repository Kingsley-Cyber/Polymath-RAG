# unit: frontend-v2/src/lib/contracts.ts
anchor: frontend-v2/src/lib/contracts.ts:1-393

## purpose
Typed mirrors of the backend response contracts that frontend-v2 consumes; the backend is the authority (FRONTEND-V2-PLAN §0.2), shapes verified live 2026-09-10 (F0 / register 11.195) and 2026-09-12. frontend-v2/src/lib/contracts.ts:1-8 [DERIVED]
The module computes no policy: if a field is absent the UI shows it as unknown, it never derives a substitute. frontend-v2/src/lib/contracts.ts:6-7 [DERIVED]
Pure type declarations plus one exported const (`PUBLIC_MODES`); no runtime code. frontend-v2/src/lib/contracts.ts:1-393 [DERIVED]

## public surface
Module-level importers (FACTS.importers, per-symbol mapping not recorded): `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/deep.ts` — materials/material-6207205376-902399024365833.md:359-365 [DERIVED]

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SemanticReadiness | interface | `/semantic_readiness?corpus_id=` reply, contract `semantic-readiness-v1` | contracts.ts:12-29 | — |
| DocSummary | interface | one row of `/documents/summary?corpus_id=` (per-document vNext truth) | contracts.ts:31-44 | — |
| DocumentRow, DocumentRun, DocumentsResponse | interface | `GET /documents?corpus_id=` identity rows + runs | contracts.ts:46-74 | — |
| UploadResult | interface | `POST /upload` reply fields | contracts.ts:76-83 | — |
| LlmProvider, ProviderUpsertBody, LlmTestResult | interface | `/llm/providers` GET/POST bodies, `/llm/test` result | contracts.ts:85-116 | — |
| ControlPlane, ControlPlanePool | interface | `/control_plane?corpus_id=` (CONTROL-PLANE-STATUS-V1) | contracts.ts:118-142 | — |
| PoolLanes, PoolLane | interface | `/control_plane/pool/{function}` model→account lanes | contracts.ts:144-159 | — |
| Corpus | interface | `/corpora` row | contracts.ts:161-169 | — |
| PUBLIC_MODES | const | `["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const` | contracts.ts:177 | — |
| PublicMode | type | `(typeof PUBLIC_MODES)[number]` | contracts.ts:178 | — |
| Synthesizer, ReasoningMode | interface | `/synthesizers` catalog row; reasoning option | contracts.ts:180-188 | — |
| RetrievalReceipt, AnswerFrame | interface | `answer.retrieval` on the `/chat/stream` answer frame | contracts.ts:190-228 | — |
| RetrieveResponse | interface | `/retrieve` reply | contracts.ts:230-239 | — |
| GraphEntity, GraphEntities, GraphSource, GraphRelationship, GraphRelationships | interface | GRAPH-BROWSE-V1 shapes | contracts.ts:241-265 | — |
| CompareArm, CompareResponse | interface | COMPARE-REVIEW-V1 compare | contracts.ts:267-286 | — |
| ReviewScores, ReviewResponse | interface | COMPARE-REVIEW-V1 review | contracts.ts:288-296 | — |
| RunSummary | interface | `GET /adapter/runs` row (TRAIL-INTERFACE-V1) | contracts.ts:298-304 | — |
| RunProgressRow, GateResult, OpenGap, Qualification, ScoreRefusal, Admission, LivedCluster, ProductConcept, ConceptReality, HypothesisView, RegistryPrior, RegistryTerritory, RunRegistry | interface | RunView payload pieces | contracts.ts:305-329 | — |
| RunView | interface | `GET /adapter/{id}/view` | contracts.ts:330-345 | — |
| DeepResearchPlan, DeepPlanGoal | interface | `POST /research/deep/plan` (DR7) | contracts.ts:347-354 | — |
| DeepCoverage, DeepCoverageGoal | interface | `event: coverage` frames after each level | contracts.ts:355-357 | — |
| DeepReportModel, DeepReportGoal, DeepFinding, DeepCounterFinding, DeepReportSource, DeepAudit | interface | `result.meta.deep_research.report_model` + sentence audit (§11.4) | contracts.ts:358-370 | — |
| ChatSynthesisFacet, ChatSynthesis | interface | `result.meta.synthesis` (FACET-RETRIEVAL-V1 F5/F6) | contracts.ts:372-386 | — |
| ChatGapClaim, ChatGapCheck | interface | `result.meta.gap_check` | contracts.ts:387-392 | — |

## contracts
**PUBLIC_MODES / PublicMode** — contracts.ts:173-178
- in: none (const literal).
- out: exactly five modes `"FAST"`, `"HYBRID"`, `"GRAPH"`, `"WILDCARD"`, `"GNN"`; `PublicMode` derives from the const.
- pre: `"VECTOR"` is a backend primitive, not a public mode (plan §2); `"GNN"` is the experimental fifth mode (GNN-RETRIEVAL-V1) — graph-neural PARENT routing, original children prove, same reranker judges.
- post: GNN is sent as `mode: "GNN"` through the very same `/chat` path as every other mode.

**RetrievalReceipt** — contracts.ts:190-221
- in: backend `answer.retrieval` on the `/chat/stream` answer frame.
- out: `arrivals?: Record<string, string[]>` = chunk_id → lanes that delivered it; `lane_sizes?: Record<string, number>`.
- post: the Query Inspector's whole source of truth (plan §3).
- `latency_ms?: number | Record<string, number | null>`: v2 = per-stage map (embed, lanes, rerank, compose, total; absent stage is null); v1 = one number. Render `total`, never the map itself (it rendered as "NaNs").

**ControlPlane / ControlPlanePool** — contracts.ts:118-142
- in: `/control_plane?corpus_id=` response.
- out: `pools: Record<string, ControlPlanePool>` keyed by function name; queue counters (`queued`, `processing`, `retry`, `failed`) sit at the TOP level of each pool, not nested.
- `control_ready` (GAP-1): state `"ready" | "blocked" | "degraded"`; `summary.processing_active`/`processing_stalled` (GAP-4). Both composed server-side (added 2026-09-12); the UI renders them and must not re-derive from `/ready` + `/health/pipeline`.
- `provider` counters: `limiter_refused` is LOCAL (0 HTTP); `http_429` cost a real provider request.

**LlmProvider / ProviderUpsertBody / LlmTestResult** — contracts.ts:85-116
- `api_key: string` is masked (last 4 chars) or `"env:NAME"` — never the real key; `api_key_set: boolean` says whether a usable key resolves.
- `POST /llm/providers` with empty `api_key` on an existing provider keeps the stored key (masked round-trip).

**GraphRelationship / GraphRelationships** — contracts.ts:253-265
- each relationship carries `sources: GraphSource[]` — the attestation, "the reason this relationship may be shown at all".
- `dropped_unattested: number` = relationships withheld because nothing in THIS corpus attests them.

**RunView / RunRegistry** — contracts.ts:323-345
- `report?: { available: boolean }` — T5: `GET /adapter/{id}/report` exists for this run's adapter.
- `registry?: RunRegistry | null` — owner's view only; a friend's view has no `registry` key.

**ChatSynthesis / ChatGapCheck** — contracts.ts:372-392
- facet `confidence` per §11.4: `strong` = two or more books, `single_source`, `contested`; `sources` reuse the deep report shape, cids are the answer's own `[S#]` tags resolved through the chat receipt.
- absent on a QA / lookup turn and on every turn saved before F5.
- ChatGapCheck: the answer's "not covered" claims re-searched; a refuted claim gets a "More on this" addition carrying citations; `edited` records wording changes.

**DeepReportModel / DeepAudit** — contracts.ts:358-370
- `DeepFinding.confidence`: `strong | single_source | contested` (§11.4).
- audit checks every prose sentence (headings skipped) for a valid `[cN]`; `uncited` holds the offending indices.

## effect surface
None. No tables, collections, files, network calls, subprocesses, or env reads; FACTS report `tables_read: []`, `tables_written: []`, `constants: []` — materials/material-6207205376-902399024365833.md:366-368 [DERIVED]
No import statements anywhere in the file. frontend-v2/src/lib/contracts.ts:1-393 [DERIVED]

## invariants
INVARIANT: PUBLIC_MODES length = 5, exactly `"FAST"`, `"HYBRID"`, `"GRAPH"`, `"WILDCARD"`, `"GNN"` — contracts.ts:177 [DERIVED]
  fails-if: a new public mode shipped without updating the const disappears from every `PublicMode`-typed picker.
INVARIANT: `"VECTOR"` ∉ PUBLIC_MODES (backend primitive, plan §2) — contracts.ts:173-174 [DERIVED]
  fails-if: exposing VECTOR advertises a non-public backend primitive as a user mode.
INVARIANT: LlmProvider.api_key ∈ {last-4-chars mask, `env:NAME`} — never a raw key — contracts.ts:85-87,92 [DERIVED]
  fails-if: a raw credential lands in UI state/logs.
INVARIANT: ControlPlane.pools keys = function names; queue counters at pool top level — contracts.ts:119-123,131 [DERIVED]
  fails-if: nested-counter lookup returns undefined and queue UI reads zero.
INVARIANT: Corpus.query_ready exists only so the UI can refuse to use it (plan §7) — contracts.ts:161,168 [DERIVED]
  fails-if: UI starts gating queries on it, contradicting plan §7.
INVARIANT: RetrievalReceipt.latency_ms shape = `number | Record<string, number | null>` (v1 | v2) — contracts.ts:219-221 [DERIVED]
  fails-if: renderer assumes the map shape → the documented "NaNs" display returns.
INVARIANT: ChatSynthesis present only on GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turns saved at/after F5 — contracts.ts:373-377 [DERIVED]
  fails-if: code assumes every chat answer carries `result.meta.synthesis`.
INVARIANT: friend's run view has no `registry` key (owner-only) — contracts.ts:323 [DERIVED]
  fails-if: registry access on a shared view dereferences a key that does not exist.

## determinism & idempotency
determinism: DETERMINISTIC (type declarations plus one `as const` array; no clock/random/uuid/network/db/env/concurrency anywhere in the file — contracts.ts:1-393) [DERIVED]
idempotency: SAFE (module has no runtime side effects; importing it changes nothing) [DERIVED]

## failure behaviour
No handlers exist — the module executes nothing. Failure semantics it mirrors for callers:
- Absent field ⇒ UI shows unknown; no substitution. contracts.ts:6-7 [DERIVED]
- ControlPlanePool.provider separates local refusals (`limiter_refused`, 0 HTTP) from real provider rejections (`http_429`). contracts.ts:140 [DERIVED]
- LlmTestResult: `ok: boolean` with optional `error`. contracts.ts:111-116 [DERIVED]
- ReviewResponse: `review: ReviewScores | null` alongside `parse_error: string | null` and `raw: string | null` — a parse failure still yields raw text. contracts.ts:293-296 [DERIVED]
- RunView.run.gap: `{ code?, message? } | null` carries the terminal failure. contracts.ts:335 [DERIVED]
- ChatGapCheck: optional `error` on the gap re-check. contracts.ts:392 [DERIVED]

## dumb-code flags
- Dual-typed `latency_ms?: number | Record<string, number | null>` kept for v1/v2 coexistence; the v2 map previously rendered as "NaNs". contracts.ts:218-221 [DERIVED]
- Polymorphic `documents?: number | string[]` (count or doc ids) in both DeepCoverageGoal and DeepReportGoal — consumers must branch on typeof. contracts.ts:357,364 [DERIVED]
- Mixed `open_questions?: (string | { question?: string; text?: string })[]`. contracts.ts:361 [DERIVED]
- RetrievalReceipt leans on `unknown` for `funnel`, `composition`, `aspects`, `weak_aspects`, `legend`, `chunks`, `used_evidence`, `final_detail`, `graph_seeds`, `graph_bounds`, `graph_degraded`, `wildcard`, `wildcard_diagnostics`, `latent`, `chat_plan` values — untyped payload inside a typed mirror. contracts.ts:201-217 [DERIVED]
- Protocol literals documented only in comments, not in code: `env:NAME` prefix (contracts.ts:87,92); verdicts `SEMANTIC_COMPLETE | SEMANTIC_INCOMPLETE` (contracts.ts:16-17) and `VNEXT_COMPLETE | VNEXT_INCOMPLETE` (contracts.ts:21); confidence `strong | single_source | contested` (contracts.ts:365). [DERIVED]
- Verdict/status fields typed plain `string` (e.g. SemanticReadiness.verdict, DocumentRun.status, RunSummary.status) though the legal values are enumerated in comments. contracts.ts:16-17,64-65,300-304 [DERIVED]

## refactor notes
- Blast radius: all five importers (`App.tsx`, `lib/_small-modules`, `lib/api.ts`, `lib/chat.ts`, `lib/deep.ts`) recompile on any field rename/type change — materials/material-6207205376-902399024365833.md:359-365. [DERIVED]
- Shape changes must originate backend-side (backend is the authority, §0.2); fields were verified against live routes 2026-09-10/12 — contracts.ts:3-7,46-49,85-88,118-123. [DERIVED]
- PUBLIC_MODES / PublicMode changes hit every mode picker and the `/chat` send path (GNN rides the same path). contracts.ts:175-178 [DERIVED]
- Do not remove `query_ready` — the UI's refusal-to-use semantics depend on its presence. contracts.ts:161 [DERIVED]
- Keep `latency_ms` a union until v1 single-number responses are gone from the backend. contracts.ts:218-221 [DERIVED]

## VERIFY
```verify
grep -Fq 'export const PUBLIC_MODES = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const' frontend-v2/src/lib/contracts.ts
grep -Fq 'export type PublicMode = (typeof PUBLIC_MODES)[number]' frontend-v2/src/lib/contracts.ts
grep -Eq 'latency_ms\?: number \| Record<string, number \| null>' frontend-v2/src/lib/contracts.ts
grep -Fq 'dropped_unattested: number' frontend-v2/src/lib/contracts.ts
grep -Fq 'query_ready: boolean' frontend-v2/src/lib/contracts.ts
test "$(grep -c -F 'env:NAME' frontend-v2/src/lib/contracts.ts)" -ge 2
test "$(grep -c -F 'export interface' frontend-v2/src/lib/contracts.ts)" -ge 57
```
