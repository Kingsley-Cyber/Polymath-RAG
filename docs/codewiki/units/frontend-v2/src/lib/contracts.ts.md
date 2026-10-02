# unit: frontend-v2/src/lib/contracts.ts
anchor: frontend-v2/src/lib/contracts.ts:1-412

## purpose
Typed mirrors of the backend contracts the V2 frontend consumes (header, "FRONTEND-V2-PLAN §0.2"). The backend is the authority: every type describes a response shape the backend already owns (verified live 2026-09-10, F0 / register 11.195); nothing here computes policy — an absent field is shown as unknown, never derived. — frontend-v2/src/lib/contracts.ts:2-8 [DERIVED]

## public surface
File-level importers (FACTS.importers): `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/deep.ts`, `frontend-v2/src/lib/readiness.ts`. No finer-grained usage data exists, so "used by" is "—" per row.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| SemanticReadiness | interface | mirror of `/semantic_readiness?corpus_id=` (contract `semantic-readiness-v1`) | contracts.ts:13-34 | — |
| DocSummary | interface | row of `/documents/summary?corpus_id=` (per-document vNext truth) | contracts.ts:37-61 | — |
| DocumentRow, DocumentRun, DocumentsResponse | interface | `GET /documents?corpus_id=` identity + runs | contracts.ts:67-91 | — |
| UploadResult | interface | `POST /upload` reply fields | contracts.ts:94-100 | — |
| LlmProvider, ProviderUpsertBody, LlmTestResult | interface | `/llm/providers`, upsert body, `/llm/test` | contracts.ts:106-133 | — |
| ControlPlane, ControlPlanePool | interface | `/control_plane` (CONTROL-PLANE-STATUS-V1) | contracts.ts:141-161 | — |
| PoolLanes, PoolLane | interface | `/control_plane/pool/{function}` | contracts.ts:164-178 | — |
| Corpus | interface | `/corpora` | contracts.ts:181-188 | — |
| PUBLIC_MODES | const | `["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const` | contracts.ts:196 | — |
| PublicMode | type | `(typeof PUBLIC_MODES)[number]` | contracts.ts:197 | — |
| Synthesizer, ReasoningMode | interface | `/synthesizers` catalog row; reasoning mode | contracts.ts:202-207 | — |
| RetrievalReceipt, AnswerFrame | interface | `answer.retrieval` on `/chat/stream` answer frame + frame | contracts.ts:213-247 | — |
| RetrieveResponse | interface | `/retrieve` | contracts.ts:251-258 | — |
| GraphEntity, GraphEntities, GraphSource, GraphRelationship, GraphRelationships | interface | GRAPH-BROWSE-V1 | contracts.ts:262-284 | — |
| CompareArm, CompareResponse, ReviewScores, ReviewResponse | interface | COMPARE-REVIEW-V1 | contracts.ts:288-315 | — |
| RunSummary, RunProgressRow, GateResult, OpenGap, Qualification, ScoreRefusal, Admission, LivedCluster, ProductConcept, ConceptReality, HypothesisView, RegistryPrior, RegistryTerritory, RunRegistry, RunView | interface | TRAIL-INTERFACE-V1 (`GET /adapter/runs`, `GET /adapter/{id}/view`) | contracts.ts:318-364 | — |
| DeepResearchPlan, DeepPlanGoal, DeepCoverage, DeepCoverageGoal, DeepReportModel, DeepReportGoal, DeepFinding, DeepCounterFinding, DeepReportSource, DeepAudit | interface | DEEP-RESEARCH-MODE-V1 §11.3 (DR7) | contracts.ts:368-389 | — |
| ChatSynthesisFacet, ChatSynthesis, ChatGapClaim, ChatGapCheck | interface | FACET-RETRIEVAL-V1 F5 / F6 | contracts.ts:397-411 | — |

58 interfaces + 1 const + 1 type = 60 exported symbols; zero runtime functions. — FACTS symbols (material lines 3-358) [DERIVED]

## contracts
- `SemanticReadiness` — in: `/semantic_readiness?corpus_id=` response; `contract` literal `"semantic-readiness-v1"`; `verdict` ∈ `SEMANTIC_COMPLETE | SEMANTIC_INCOMPLETE`; `vnext.verdict` ∈ `VNEXT_COMPLETE | VNEXT_INCOMPLETE`; `vnext.parents` = `{ eligible, mapped, excluded, unresolved }`; `vnext.profiled` / `vnext_served` optional (absent on older backend / unreadable profile index). — contracts.ts:12-31 [DERIVED]
- `DocSummary` — per-document written vs served distinction: `profile_vnext` = latest card written by vNext writer; `profile_served` ∈ `"vnext" | "basic" | null` = writer of the card SEARCH serves; `run_status` (FILES-STATUS-TRUTH-V1, `query_ready` = every required step done) optional; `work_open` (ready/leased/pending) and `work_failed` (stage + note) optional. — contracts.ts:45-60 [DERIVED]
- `ControlPlane` — `control_ready.state` ∈ `"ready" | "blocked" | "degraded"` (composed server-side, UI does not re-derive from `/ready` + `/health/pipeline`); `summary` counts `documents/semantic_ready/vnext_served?/basic_profile?/processing/processing_active/processing_stalled/blocked`; `pools` is a map keyed by function name with queue counters at the TOP level of each pool. — contracts.ts:135-151 [DERIVED]
- `RetrievalReceipt` — `answer.retrieval` on the `/chat/stream` answer frame, the Query Inspector's whole source of truth; `latency_ms` is `number | Record<string, number | null>` (v1 one number; v2 per-stage map) — "Render `total`, never the map itself (it rendered as 'NaNs')". — contracts.ts:209-239 [DERIVED]
- `GraphRelationship` — `direction` ∈ `"in" | "out"`; `sources: GraphSource[]` is the attestation "the reason this relationship may be shown at all"; `GraphRelationships.dropped_unattested` counts relationships withheld because nothing in this corpus attests them. — contracts.ts:272-284 [DERIVED]
- `RunView` — TRAIL-INTERFACE-V1; `registry` is the owner's view only ("a friend's view has no `registry` key"); `report.available` marks whether `GET /adapter/{id}/report` exists. — contracts.ts:317-364 [DERIVED]
- `DeepReportModel` / `DeepFinding` — `confidence` ∈ `strong | single_source | contested` (§11.4); `DeepAudit.uncited` = indices of prose sentences without a valid `[cN]`. — contracts.ts:377-389 [DERIVED]
- `ChatSynthesis` / `ChatGapCheck` — present only on GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turns; "Absent on a QA / lookup turn and on every turn saved before F5"; `ChatGapCheck` records refuted "not covered" claims and wording edits. — contracts.ts:391-411 [DERIVED]

## effect surface
None. Type declarations plus one const; no functions executed, no I/O. FACTS: `tables_read: []`, `tables_written: []`, `constants: []`. — FACTS (material lines 367-369) [DERIVED]

## invariants
INVARIANT: `PUBLIC_MODES.length` = 5, members exactly `"FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"` — contracts.ts:196 [DERIVED]
  fails-if: a backend mode not in the const is invisible to the mode picker and rejected by `PublicMode`.
INVARIANT: `PublicMode` = elementwise union of `PUBLIC_MODES` — contracts.ts:197 [DERIVED]
  fails-if: hand-editing the union lets a value through that the const (and picker UI) does not carry.
INVARIANT: `SemanticReadiness.vnext.parents` keys = `{ eligible, mapped, excluded, unresolved }` — contracts.ts:23 [DERIVED]
  fails-if: backend renames a counter; readiness UI reads `undefined`.
INVARIANT: `DocSummary.profile_served` ∈ `{"vnext", "basic", null}` — contracts.ts:54 [DERIVED]
  fails-if: a third writer label renders as an unknown state; UI must keep showing the written state when the field is absent.
INVARIANT: `ControlPlane.control_ready.state` ∈ `{"ready", "blocked", "degraded"}` — contracts.ts:144 [DERIVED]
  fails-if: new server state string falls through exhaustive switch in the control-plane panel.
INVARIANT: `RetrievalReceipt.latency_ms` is `number` OR `Record<string, number | null>`, never both — contracts.ts:237-239 [DERIVED]
  fails-if: rendering the v2 map directly reproduces the "NaNs" display bug the comment records.
INVARIANT: exported runtime values = 1 (`PUBLIC_MODES`); everything else is type-only — FACTS symbols [DERIVED]
  fails-if: adding runtime code here silently changes this module from an effect-free types module.

## determinism & idempotency
determinism: DETERMINISTIC — pure declarations plus one const literal; no clock/random/uuid/network/db/env access anywhere in 1-412. [INFERRED: no statement in SOURCE performs work.]
idempotency: SAFE — importing has no side effects; see effect surface.

## dumb-code flags
- `RetrievalReceipt` carries ~14 `unknown`-typed fields (`funnel`, `composition`, `aspects`, `weak_aspects`, `legend`, `chunks`, `used_evidence`, `final_detail`, `graph_seeds`, `graph_bounds`, `graph_degraded`, `wildcard`, `wildcard_diagnostics`, `latent`) — untyped passthrough. — contracts.ts:218-234 [DERIVED]
- `latency_ms` v1/v2 dual shape with a known "NaNs" rendering failure documented in-code. — contracts.ts:237-239 [DERIVED]
- `DeepCoverageGoal.documents` / `DeepReportGoal.documents` typed `number | string[]` — "a count, or the doc ids", ambiguous per consumer. — contracts.ts:374-376, 383 [DERIVED]
- Version-drift optional fields documented as "absent on an older backend": `vnext.profiled`, `vnext.vnext_served`, `DocSummary.run_status`. — contracts.ts:25-30, 55 [DERIVED]
- Confidence vocabulary `strong | single_source | contested` (§11.4) duplicated in two comment sites, not a shared type. — contracts.ts:384, 393-396 [DERIVED]
- `AnswerFrame.result` typed `unknown`. — contracts.ts:245 [DERIVED]
- `Corpus.query_ready` is carried ONLY so the UI can refuse to use it (plan §7) — a field whose contract is to be distrusted. — contracts.ts:180 [DERIVED]

## refactor notes
- Blast radius: all six importers (`App.tsx`, `lib/_small-modules`, `lib/api.ts`, `lib/chat.ts`, `lib/deep.ts`, `lib/readiness.ts`) consume this module file-level; renaming/removing any exported member breaks all of them at once. — FACTS.importers (material lines 359-366) [DERIVED]
- Backend is the authority: field changes must match live backend shapes, not frontend convenience; several shapes cite live-verification dates (2026-09-10, 2026-09-12) against `orchestrator/api/ui.py` routes (`documents`, `llm_providers`, control plane). — contracts.ts:2-8, 63-66, 102-105, 135-140 [DERIVED]
- Never add derivation logic here: the header contract forbids computing substitutes for absent fields. — contracts.ts:6-8 [DERIVED]
- GNN is "sent as `mode: \"GNN\"` through the very same /chat path as every other mode" — keep it inside `PUBLIC_MODES`, not a parallel path. — contracts.ts:192-195 [DERIVED]
- `profile_vnext` (written) vs `profile_served` (served) is a deliberate two-label distinction scripts depend on; do not collapse into one field. — contracts.ts:45-54 [DERIVED]

## VERIFY
```verify
grep -Fq 'export interface SemanticReadiness' frontend-v2/src/lib/contracts.ts
grep -Fq 'PUBLIC_MODES = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const' frontend-v2/src/lib/contracts.ts
grep -Fq 'SEMANTIC_COMPLETE | SEMANTIC_INCOMPLETE' frontend-v2/src/lib/contracts.ts
grep -Fq 'latency_ms?: number | Record<string, number | null>' frontend-v2/src/lib/contracts.ts
grep -Fq 'export type PublicMode = (typeof PUBLIC_MODES)[number]' frontend-v2/src/lib/contracts.ts
test "$(grep -c -F 'export interface' frontend-v2/src/lib/contracts.ts)" -ge 55
```
