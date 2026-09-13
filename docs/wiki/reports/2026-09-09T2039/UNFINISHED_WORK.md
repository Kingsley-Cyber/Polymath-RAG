---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE — ranked unfinished work
---

# UNFINISHED_WORK (2026-09-09T2039)

Ranked. Every item: PRIORITY · PROBLEM · EVIDENCE · FILE:SYMBOL · DEPENDENCY · ACCEPTANCE · NEXT ACTION.
No vague "finish migration" items.

## U-1 · Intent routing is built but OFF — decide/enable the vNext chat routing
- **STATUS (2026-09-09): COMPLETE / QUALIFIED** (register 11.189). Read-only A/B on `rag-canary`, no default
  changed, no provider spend, baseline fleet untouched: `IMPLEMENTATION PROVEN · LIVE WIRING PROVEN · CANDIDATE
  CONTRIBUTION PROVEN · NON-REGRESSION PROVEN · FINAL-EVIDENCE UPLIFT NOT PROVEN · PRODUCTION DEFAULT OFF/GATED`.
  Evidence `docs/wiki/experiments/u1-intent-routing-ab-2026-09-09/`; contract guard
  `tests/determinism/test_u1_intent_routing_contract.py`. `POLYMATH_CHAT_INTENT_POLICY` stays OFF. Uplift needs a
  richly-covered corpus (cinema, behind U-2). **Next slice = MASTER PRODUCTION MIGRATION PLANNING** (bidirectional
  dependency archaeology → `PRODUCTION-RAG-MIGRATION-CUTOVER-V1.md`, NOT YET MATERIALIZED); that closure decides
  whether U-2 is the first execution phase.
- **PRIORITY:** P1 (this is the whole retrieval-migration lane).
- **PROBLEM:** `INTENT × FIELD × TECHNIQUE × BUDGET` (the plan-of-record) is not active. Chat classifies intent
  then ignores it; no Resolution Lift, micro-latent-by-intent, SEEALSO/BRIDGE, graph auto-assist, or evidence
  roles fire on a live turn.
- **EVIDENCE:** `POLYMATH_CHAT_INTENT_POLICY` unset in `.env`/scripts/settings/process-env; live `/chat/stream`
  receipt `mode HYBRID · counts {} · evidence_roles None` on a `SYNTHESIS`-intent relational query. BE_AWARE item 1.
- **FILE:SYMBOL:** `orchestrator/orchestrator/api/chat_retrieval.py:intent_policy_enabled` /
  `orchestrator/orchestrator/api/ui.py:2597` (`_ip = _ip_on() and _plan.intent`) /
  `shared/polymath_shared/query_intent.py:policy_for` / `apply_intent_policy`.
- **DEPENDENCY:** the measurable *uplift* (plan rows D-10/D-11) is GATED on **parent-MAP corpus coverage**
  (cinema ~420/11,993 at pause, behind the forensic hold). Enabling the flag routes but does not lift until
  coverage fills.
- **ACCEPTANCE:** a live A/B on a covered corpus shows intent-selected lanes firing (seealso_fanout / graph_dest
  / resolution_lift counts > 0) AND role-grouped synthesis, with `chat_regression` still 0-regression flag-off.
- **NEXT ACTION:** run the throwaway A/B — `POLYMATH_CHAT_INTENT_POLICY=1` on a scratch process vs the default,
  same `rag-canary` queries, diff the retrieval `counts`/roles. No running-default change, no spend. Then bring
  the owner the measured delta before any default flip.

## U-2 · Cinema pMAP forensic hold — bounded Groq live probe (owner-gated)
- **PRIORITY:** P1, but BLOCKED on owner authorization.
- **PROBLEM:** cinema parent-MAP coverage ≈ 420–1,254 / 11,993; backfill STOPPED under forensic hold. The
  disputed "Groq RPD exhausted" claim was never reconciled to provider truth.
- **EVIDENCE:** register 11.184/11.185; `docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md`. Control-plane
  repair (11.185) instrumented the conservation chain (limiter_refused vs http_429 now separable).
- **FILE:SYMBOL:** `shared/polymath_shared/llm_extraction/*` (limiter/lane), `scripts/parent_map_backfill.py`.
- **DEPENDENCY:** owner authorization for a bounded provider spend (probe quota topology + MAP-batch benchmark).
- **ACCEPTANCE:** provider per-account RPD observable + reconciles with local `day_count`; refusal/error
  accounting correct; request→valid-map efficiency measured; benchmark of MAP batch sizes.
- **NEXT ACTION:** owner authorizes the bounded probe → run it → benchmark → bounded canary → owner review.
  **Do NOT resume backfill on a quota reset.**

## U-3 · Production pMAP default for fresh uploads (owner-gated spend)
- **PRIORITY:** P2.
- **PROBLEM:** pMAP auto-mint is transient/scoped to `rag-canary`. Making it the default for all NEW uploads is
  an owner decision (begins Groq spend per fresh doc).
- **EVIDENCE:** BE_AWARE item 9; `POLYMATH_DOC_PARENT_MAP_SINCE` guard exists (register, commit `0a42f10`).
- **FILE:SYMBOL:** `POLYMATH_DOC_PARENT_MAP_ENABLED` / `_CORPUS` / `_SINCE`; `control/control/fleet_autopilot.py`.
- **DEPENDENCY:** owner authorization; the new-uploads-only guard (`_SINCE`) ensures history is never swept.
- **ACCEPTANCE:** enable globally with `_ENABLED=1` + `_SINCE=<now>` and NO `_CORPUS`; every pre-boundary run
  (cinema + history) stays untouched; fresh uploads mint pMAP.
- **NEXT ACTION:** owner sets `_ENABLED=1` + `_SINCE=<cutover timestamp>` in the durable fleet env (not transient).

## U-4 · Phase B — doc_profile DAG cutover
- **PRIORITY:** P2.
- **PROBLEM:** doc_profile fires EARLY (out of STAGE_DAG) for the canary; the clean DAG cutover is deferred.
- **EVIDENCE:** register 11.186 "REMAINING = owner-gated: … the Phase B doc_profile DAG cutover"; commit `8366b0b`.
- **FILE:SYMBOL:** `workers/…` STAGE_DAG; `doc_profile` stage ordering.
- **DEPENDENCY:** owner sign-off on the DAG reorder (affects every fresh run's ordering).
- **ACCEPTANCE:** doc_profile is a first-class DAG stage that still completes within the < 4-min budget; canary 3/3 holds.
- **NEXT ACTION:** design the DAG insert point, run the 3-canary gate, then commit behind an owner review.

## U-5 · Chat `[S11]` citation rendering (owner declined this session)
- **PRIORITY:** P3 (cosmetic; owner said "nvm").
- **PROBLEM:** short `[S#]` tags render raw; legend ignored.
- **EVIDENCE:** BE_AWARE item 7.
- **FILE:SYMBOL:** `frontend/src/components/MessageBubble.tsx:compactCitations` (regex `{12,}`).
- **DEPENDENCY:** owner decision on citation display (compact-clickable / small-styled / strip).
- **ACCEPTANCE:** `[S11]` renders as an intended citation, not raw text; evidence panel mapping via `retrieval.legend`.
- **NEXT ACTION:** only if owner asks — handle `[S\d+]` in `compactCitations` using the legend.

## U-6 · Two determinism gate reds (pre-existing, forensic-hold-entangled)
- **PRIORITY:** P3.
- **PROBLEM:** `test_no_active_fact_has_a_pronoun_endpoint` (cinema `you` fact) + `test_live_artifact_tasks[brainrot_transform]` (live LLM variance) fail in the full determinism run.
- **EVIDENCE:** BE_AWARE item 10; spawned background task this session.
- **FILE:SYMBOL:** `tests/determinism/test_fact_endpoint_eligibility.py:test_no_active_fact_has_a_pronoun_endpoint`; `tests/determinism/test_chat_synthesis.py`.
- **DEPENDENCY:** the pronoun fix touches cinema data (forensic hold) — needs owner gating OR a filter fix at
  extraction eligibility; the brainrot test should likely be marked live-skip-by-default.
- **ACCEPTANCE:** either the pronoun endpoint is rejected at extraction (root cause) or the gate scopes out held
  corpora; the live synthesis test is excluded from the offline gate.
- **NEXT ACTION:** root-cause why `you` survived the pronoun eligibility filter in the 2026-09-05 cinema extraction; propose an owner-gated data or gate fix.

## U-7 · Push / PR the branch (33+ local commits unpushed)
- **PRIORITY:** P2 (owner call — prior work was deliberately kept local).
- **PROBLEM:** `architecture/evidence-first-v5` is 32 commits ahead of its origin, 37 ahead of `origin/main`, with no PR.
- **EVIDENCE:** START-HERE Repo truth.
- **DEPENDENCY:** owner decision to push / open a PR / merge.
- **ACCEPTANCE:** branch pushed and/or PR opened against `main` with CI green.
- **NEXT ACTION:** on owner say-so, `git push origin architecture/evidence-first-v5` and open a PR.
