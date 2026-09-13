---
title: "WORK LOG — U-1 intent-routing A/B: PROVEN mechanically + non-regressive, final-evidence uplift NOT proven on current covered corpus; production default OFF/GATED"
change_id: U1-INTENT-ROUTING-AB
date: 2026-09-09
owner: governance
last_reviewed: 2026-09-09
status: complete (QUALIFIED — evidence frozen; POLYMATH_CHAT_INTENT_POLICY stays OFF)
register: 11.189
package: "docs/wiki/experiments/u1-intent-routing-ab-2026-09-09/ (evidence) + tests/determinism/test_u1_intent_routing_contract.py (contract guard)"
architecture_impact: "None. Read-only measurement + a provider-free contract test + living-ledger updates. No code, config, retrieval architecture, or running default changed. No cutover authority created (the master production cutover plan is deferred to a dedicated dependency-closure slice). Records that intent routing reaches the live CHAT-RETRIEVAL-V2 runtime and is non-regressive, while final-evidence uplift remains unproven on the only covered corpus available (rag-canary)."
---

> **Ledger:** UNFINISHED_WORK **U-1** (`docs/wiki/reports/2026-09-09T2039/UNFINISHED_WORK.md`); authorities
> `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` (query-time) + `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` (migration/
> retirement — U-1 recorded in its execution ledger). Register **11.189**. No default changed, no spend. The
> master production cutover plan (`PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md`) is **NOT YET MATERIALIZED** and was
> deliberately NOT created here.

## Contract

Requested outcome: qualify `POLYMATH_CHAT_INTENT_POLICY=1` for the retrieval migration — does it activate the
planned `INTENT × FIELD × TECHNIQUE × BUDGET` routing, does the full `/chat` runtime reach it, and is it
non-regressive — WITHOUT changing the running default or spending provider quota, then persist the result as
durable repository evidence.

- **Smallest acceptance:** intent-selected additive lanes fire on the correct intents; base retrieval +
  source-child evidence preserved; zero regression; result frozen as repository evidence + a contract guard.
- **Owner / public contract:** governance. Public surface = the evidence dir, the contract test, and the
  register/continuity/migration-ledger rows. No runtime contract changed.
- **Inputs / outputs / persistence:** inputs = `rag-canary` retrieval + the intent policy code; outputs =
  evidence JSON + README + the U-1 result block; persistence = docs + one test, NO runtime state.
- **Dependency edges:** reads `orchestrator/orchestrator/api/chat_retrieval.py`, `.../ui.py`,
  `shared/polymath_shared/query_intent.py`, `.../candidate_engine.py`. Reverse dependents: the master cutover
  planning slice + the future U-2 uplift proof reuse this methodology.
- **Verifier / rollback:** `tests/determinism/test_u1_intent_routing_contract.py` (23 cases) + the frozen JSONs.
  Rollback = delete the evidence dir + test + ledger rows; no runtime touched, nothing to revert.

## Changes

Additive, docs + one test only — no runtime code, config, or default modified:

- `docs/wiki/experiments/u1-intent-routing-ab-2026-09-09/` — `README.md` (conditions + both proofs + finding +
  limitation + gate) and the machine-readable `proof-a-result.json` / `proof-b-result.json`. The one-off probe
  scripts were NOT kept (hardcoded corpus/query accidents; not a general harness).
- `tests/determinism/test_u1_intent_routing_contract.py` — provider-free contract guard (23 cases).
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register row **11.189**.
- `docs/wiki/plans/CONTINUITY-REPORT.md` — new latest checkpoint; prior 2026-09-09T2039 demoted; records the
  master cutover plan as NOT YET MATERIALIZED and names the next planning slice.
- `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` — U-1 result added to the execution ledger.
- `docs/wiki/reports/2026-09-09T2039/UNFINISHED_WORK.md` — U-1 marked COMPLETE / QUALIFIED with evidence path.
- `scripts/scaffold_polymath_v4.py` — declared the new files in `TREE`.

## Proof

Method: **Proof A** (retrieval primitive) reuses `scripts/production_routing_qualify.py` — same query/corpus/
engine, `default_budget()` vs `apply_intent_policy(classify_intent(q), default_budget())` → `chat_retrieve_v2`,
isolated by EXPLICIT budget; ephemeral rag-canary queries (frozen L/B fixtures untouched). **Proof B** (full
runtime) = throwaway `uvicorn orchestrator.main:app` on `:7299` differing from the running baseline `:7200` by
EXACTLY `POLYMATH_CHAT_INTENT_POLICY=1` (`POLYMATH_AUTOPILOT=0`, pMAP-mint unset), `/chat/stream` with
`synthesizer=deterministic-template-v3` (no LLM), SEQUENTIAL (one shared reranker/GPU). Baseline untouched;
scratch killed; `:7200` verified healthy.

Results (full numbers in the evidence JSONs):

- **OFF (both proofs):** additive lanes all 0; base lanes only; `graph_fact_count=0`; roles all `DIRECT`.
- **ON activates ONLY the permitted lanes per intent** — Proof B relationship:
  `dualread 16 · resolution_lift 6 · seealso_fanout 24 · graph_dest 8 · latent_rescue 4 · graph-assist 7 facts`;
  arrivals gain SHADOW_DUALREAD/SEEALSO_FANOUT/GRAPH_DEST; funnel 57→63; selected=15; `degraded=[]`.
- **Non-regression:** union additive (grows/holds), selected=15 constant, ZQX fact chunk preserved,
  `regression_any=False`.
- **Uplift NOT shown:** synthesis roles stayed all-`DIRECT`; additive candidates do not survive rerank into the
  final 15 on rag-canary's 10 homogeneous docs.
- Contract test: **23 passed** (provider-free). Guards: `agent_preflight` ok (`.venv/bin/python`) ·
  `repo_guard` ok · `wiki_worm --check` ok.

U-1 result (record — do not collapse "activates" into "improves"):

    IMPLEMENTATION             PROVEN
    LIVE WIRING                PROVEN
    CANDIDATE CONTRIBUTION     PROVEN
    NON-REGRESSION             PROVEN
    FINAL-EVIDENCE UPLIFT      NOT PROVEN
    PRODUCTION DEFAULT         OFF / GATED

## Rejected claims

- **"Routing does not work."** REJECTED — it works (Proof A + B) and reaches the deployed runtime.
- **"Safe to enable the production default now."** REJECTED — safe ≠ justified; uplift is unproven on a covered
  corpus, so the default stays OFF (`PRODUCTION ENABLEMENT: GATED`).
- **"U-1 completing means the production cutover plan is done / authoritative."** REJECTED — U-1 proves ONE
  migration uncertainty, not the full production dependency archaeology. No cutover authority was created.
- **"The composer has a demonstrated role-selection defect."** REJECTED as a claim — it is an OBSERVATION
  (no role-reserved seat; cross-encoder is sole authority) recorded, NOT changed during U-1.
- **"rag-canary can measure uplift."** REJECTED — its 10 synthetic homogeneous docs let direct retrieval
  saturate the answer; it proves mechanism + non-regression only.
- **"U-2 is confirmed the next execution phase."** REJECTED for now — U-2 is a KNOWN dependency, but the master
  archaeology pass may surface an earlier prerequisite; the previous handoff ordering does not override it.

## Open contract gaps

- **Master production cutover plan is NOT YET MATERIALIZED.** The next coherent slice is the MASTER PRODUCTION
  MIGRATION PLANNING: bidirectional archaeology (ENTRYPOINT→runtime→readers→state AND state/producers→every
  reader/consumer) + `legacy_dependency_census` + semantic state/lane census + Graphify + direct FILE:SYMBOL
  verification + live feature-flag/env inventory + stage/worker/scheduler inventory + UI/API contract inventory
  + delete/purge/rebuild inventory → produce `docs/wiki/plans/PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md` with full
  appendices/matrices. Closure gate: unknown runtime readers / writers / producers / stage-minters / public
  query paths / readiness consumers / cleanup dependencies / feature flags each = 0, or a named blocker per
  non-zero category.
- **Final-evidence / answer uplift is unproven on a heterogeneous, richly-covered corpus** — needs cinema
  (behind the U-2 forensic hold), not rag-canary.
- **U-2 — Groq Parent-MAP forensic closure** is a known dependency (limiter-refusal vs HTTP dispatch,
  account/key isolation, RPD/day-count truth, Retry-After/provider headers, HTTP request accounting, retry
  waste, compiler/MAP yield, persisted-map reconciliation, lane-selection vs dispatch accounting). **Do NOT
  resume cinema pMAP backfill merely to obtain the U-1 uplift test.** Its position in the execution order is
  decided by the master plan's dependency closure, not assumed here.
- No U-2 / master-planning work is started in this slice/commit.
