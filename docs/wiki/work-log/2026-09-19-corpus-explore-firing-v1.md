---
change_id: CORPUS-EXPLORE-FIRING-V1
owner: "@king"
date: 2026-09-19
status: complete
architecture_impact: "Observability-first hardening of the CORPUS-EXPLORER-V1 activation path. NEW pure shared module (corpus_explore_firing: one cause code per non-firing request) + additive diag fields (bridge_compiler.json_status, activate_corpus(diag=), explorer diag) + live receipt wiring in ui.py + the EvidencePacket `firing` receipt. Phase A changes NO gate, threshold, weight or ranking; any behavioral fix is a separate, evidence-gated slice recorded below."
last_reviewed: 2026-09-20
---

## Contract
Owner /goal 2026-09-19 — CORPUS-EXPLORE-FIRING-V1 (v1-finish-line item 1): make Corpus Explore activation
fire reliably. Baseline CE7 (`eval/corpus_explorer/CE7-ACTIVATION-RELIABILITY-2026-09-19.json`): 14/18
"fired" (n_activations>0), content-stability-when-fired 1.0. LOCKED: **Phase A attributes, no fix** (every
non-firing request records exactly ONE cause code; $0 substrate probe first; live runs START at 5-8 and
expand in batches <=8 only while the diagnosis is unresolved, ask the owner before run 25) → **Phase B**
narrow fix for PROVEN causes only → **Phase C** re-measure on Phase A queries + fresh ones (accept: firing
>=95% on-target, negatives quiet, content-stability 1.0, provenance complete, flag-off evidence-id set
equality, safety sentinel clean, latency p50/p95). HARD RULES: no tuning of thresholds/weights/
`POLYMATH_CORPUS_EXPLORER_*` to the query set; no new fusion weight; no parent-map/entity/graph activation;
extraction + bridge reasoning + extraction contract hash untouched; NO_ATOM_COVERAGE is classified and handed
to the coverage audit, never backfilled here; BRIDGE and CORPUS_EXPLORE origins stay separate; q0
authoritative; fail-open. Tag LOCALLY at close; **no push of any ref**.

## Changes
- **Baseline re-read (no code).** CE7's 4 "non-firing" runs are 2 on-target misses (`physical_weight__f2`
  2.2 s; `suppressed_grief__same0` 30.6 s — the SAME query fired on repeats 1 and 2) + 2 negatives that are
  SUPPOSED to stay quiet. On-target baseline = **13/15 (0.867)**. All four carry NO receipt at all
  (`reason=None`, no `corpus_activation`): the gate closed before activation, silently. `neg_birthday`
  "fired" under CE7's loose definition (8 activations) but added 0 subqueries (`intent_not_latent`).
- **Definition pinned (stricter than CE7, never looser).** `fired` = the explorer ADDED >=1 CORPUS_EXPLORE
  subquery to a plan whose retrieval ran. CE7's `activated` (n_activations>0) is reported alongside.
- **Phase A.1 instrumentation (observation only).**
  - NEW `shared/polymath_shared/corpus_explore_firing.py` (pure): `FiringState` + `classify` (first closed
    gate in pipeline order → exactly one of CAPABILITY_OFF, REQUEST_OFF, PLAN_FALLBACK, INTENT_INELIGIBLE,
    ATOMS_EMPTY, ATOMS_ERROR_OR_TIMEOUT, NO_ATOM_COVERAGE, CANDIDATES_FILTERED, BRIDGE_COMPILE_EMPTY,
    BRIDGE_JSON_INVALID, SUBQUERY_DROPPED, OTHER) + `firing_receipt` + `turn_receipt` (a plan-level fire is
    still a turn-level miss when the compiler flag is not `on` or retrieval was skipped) + `record` (JSONL
    rate ledger `POLYMATH_CE_FIRING_RECEIPT`, requested turns only, q0 hashed) + `summarize`.
  - `bridge_compiler`: `_loads_status` → `parse_and_validate` diag gains `json_status`
    (ok / empty_output / invalid_json); `_loads` unchanged. Additive diag key (BRIDGE path included).
  - `corpus_activation.activate_corpus(diag=)`: optional out-param counting the per-corpus fetch failures
    it already swallowed (`n_hits`, `fetch_errors`, `n_candidates`). Returned candidates identical.
  - `corpus_explore.plan_corpus_explore_expansion` diag: + `json_status`, `generate_error`,
    `deduped_existing`.
  - `evidence_packet`: `firing` admitted as a 5th bounded receipt key.
  - `ui.py` (live-only): `_add_corpus_explore_expansion` fills the state at every gate and ALWAYS stamps
    `plan.compiler['corpus_explore_firing']`; `_finish` now COUNTS an upstream finish-step exception
    (previously it skipped the explorer silently) — explorer still skipped, behavior unchanged;
    `_turn_firing_receipt` + `_stamp_firing` stamp the turn-level receipt (flag-on compile, late join,
    no-plan turns), record it once, surface it at `retrieval.corpus_explore_firing` for REQUESTED turns
    and in the EvidencePacket `receipts.firing`. Un-requested turns get no new top-level key.
  - NEW runner `eval/corpus_explorer/ce8_firing_attribution.py` (staged batches <=8, refuses to pass 24
    without `--owner-approved`, cause table, fresh query bank held out for Phase C).
- **Phase A deploy.** Merge `3366d8c` → production; open runs: 63 `reconciling` + 1 `intake` are the dormant
  HELD backlog (last activity 2026-09-07), 0 leased/running stage tickets → nothing in flight; ONE
  port-gated bounce (supervisor TERM → 0 supervisors / 0 children / 0 listeners → one boot): bundle
  `90983885cba7`, `/ready` true, sidecars up, all five live flags intact.
- **Phase B — NARROW FIX for the one PROVEN, fixable cause (`PLAN_FALLBACK`).** The explorer skipped EVERY
  fallback plan. The plan-of-record justified that as "mirror `_add_bridge_expansion`" — which has NO
  fallback gate (code + ledger: BRIDGE attempts/admits on fallback plans). `corpus_explore_firing` now
  splits fallback reasons: **NO JUDGMENT** (`transport:` / `budget_exceeded:` / `invalid_json` /
  `compiler_unavailable:` / `join_failed:` — the compiler said nothing usable) lets the explorer run;
  **INVALID JUDGMENT** (`invalid_plan:*` — the compiler answered and failed validation, e.g.
  `no_queries_for_retrieval`, a non-latent task type) and any unknown reason stay closed (fail closed).
  Kill switch `POLYMATH_CORPUS_EXPLORER_FALLBACK_OPEN` (default 0 = the pre-fix gate, byte-for-byte);
  live `.env` opts in. A fire on a fallback plan is visible as such (`stages.plan_fallback`). No threshold,
  weight, bound or `POLYMATH_CORPUS_EXPLORER_*` value changed; no new fusion weight; origins unchanged.
- **Receipt detail for the by-design class.** `no_primary` now carries
  `:retrieval_not_required:<task_type>` so a q0-authority no-retrieval turn is distinguishable at a glance.
- NEW asserting live proof `eval/corpus_explorer/ce8_fallback_gate_live.py` (function-level against the
  real embedder / Qdrant / bridge model — a compiler transport fallback cannot be produced on demand over
  HTTP); `eval/corpus_explorer/ce8_substrate_probe.py` (the Phase A.2 probe, kept reproducible).

## Proof
- **Phase A.2 $0 SUBSTRATE PROBE — substrate EXONERATED at idle.** 4 queries (both CE7 on-target misses, one
  firing control, one negative) x10, embed → `search_atoms` → `build_activation_candidates`, fresh Qdrant
  client each time (the live path), no LLM: **40/40 no errors, 0 empties, 1 distinct vector / hit-list /
  candidate-list per query**, 8 candidates every time; embed p50 ~190 ms (first 261 ms), search p50 ~4 ms
  (max 6 ms). Both CE7 miss queries produce 8 candidates here → their misses are UPSTREAM of `search_atoms`.
  Side observation (not a firing cause): the negative also returns 8 candidates (top score 0.276 vs
  0.43–0.51 on-target) — ANN top-k always answers; negatives are kept quiet by intent eligibility + C4,
  not by the substrate.
- **Phase A.1 UNIT_PROVEN** (executed path verified = worktree `pmv4-firing`):
  `tests/determinism/test_corpus_explore_firing.py` — open gates fire with no cause; every closed gate →
  exactly one known cause; every cause code reachable; first-closed-gate ordering; detail carries the
  evidence; turn-level no-plan / not-applied / retrieval-skipped; cause-table summarize; record only
  requested + never raises + q0 not stored; `_loads_status` declined vs empty vs garbage and `_loads`
  unchanged; compile diag json_status/error; `activate_corpus(diag=)` counts swallowed failures with
  identical output; EvidencePacket carries `firing` and still drops unknown keys. Neighbouring suites
  (corpus_explore / corpus_activation / bridge_compiler / bridge_integration / evidence_packet) green.
- `ui.py` wiring is live-only (editable .pth resolves `orchestrator` to MAIN under pytest): py_compile OK;
  real proof = the live receipts after merge + bounce.
- **Phase A.3 LIVE BATCH A1 (8 executions; the ONLY Phase A batch — diagnosis resolved without expanding).**
  Question: what cause do CE7's receipt-less misses carry, and does the same-query miss reproduce?
  `eval/corpus_explorer/CE8-FIRING-ATTRIBUTION-2026-09-19.json`. Every turn carried a receipt (0
  `NO_RECEIPT`). On-target 4/6 fired: `suppressed_grief` 3/3, `nonverbal_authority_f0` 1/1;
  `physical_weight_f2` 0/2 → `OTHER no_primary` (compiler: `TRANSFORM_USER_CONTENT`,
  `retrieval_required=False`, 0 queries, whole turn ~1 s, 0 evidence). Negatives 0/2 fired: `neg_cooking`
  → `OTHER no_primary` (`GENERAL_CONVERSATION`); `neg_vacation` → `PLAN_FALLBACK
  invalid_plan:no_queries_for_retrieval`. Every ATTEMPTED run: n_hits 12, n_candidates 8, fetch_errors 0,
  json_status ok, generated == admitted == added (3–4).
- **Phase A.4 ROOT CAUSES ($0 receipt-ledger forensics, `query_receipts.meta.chat_plan`).**
  1. **`PLAN_FALLBACK`** — CE7 `suppressed_grief__same0` (09-20 00:47:41 UTC): compiler attempt 3,
     `first_failure=compiler_alibaba_deepseek:transport:ReadTimeout`, final lane qwen `transport:ReadTimeout`
     (6.5 s) → fallback plan → explorer skipped silently. The SAME q0 fired 5/5 whenever the compiler
     answered. Base rate over 1,379 chat turns / 4 days: fallback **73 = 5.3%** (`invalid_plan:*` 36,
     `transport:*` 30, `budget_exceeded` 6, `invalid_json` 1); lane failover in use on 24% of turns
     (`compiler_alt` 429 ×184, `compiler_alibaba_qwen` ReadTimeout ×116). A fallback plan has a q0 PRIMARY
     and a deterministic LATENT intent for every bank query (targets and negatives alike), and the
     substrate yields 8 candidates for it — nothing the explorer needs is missing.
  2. **No PRIMARY (compiler routed the turn as no-retrieval)** — deterministic per phrasing
     (`physical_weight_f2` 3/3 across CE7 + A1). This is the settled **q0-authority** rule
     (`_add_profile_expansion`: an expansion "must never CREATE retrieval where the compiler decided
     none"); base rate `retrieval_required=false` = 107/1,379 = 7.8% (95 `GENERAL_CONVERSATION`). The SAME
     cause is what keeps `neg_cooking` quiet. **By design — classified + receipted, NOT overridden.**
  EXONERATED: `search_atoms` (idle 40/40 + live 12 hits / 8 candidates / 0 fetch errors every attempt),
  intent eligibility (no on-target `INTENT_INELIGIBLE` in 21 on-target runs), bridge JSON, cold state.
- **Phase B UNIT_PROVEN** (executed path = worktree): switch off ⇒ every fallback blocks (pre-fix gate);
  switch on ⇒ only NO-JUDGMENT reasons open, `invalid_plan:*` + unknown reasons stay closed; env default
  off; a fire on a fallback plan is marked `stages.plan_fallback`; `no_primary` carries the q0-authority
  reason; the pure expansion expands a `fallback_plan` exactly like a compiled plan (q0 first + untouched).
  18 tests in `test_corpus_explore_firing.py`; 202-test impacted sweep + the 7 contract-impact suites green.
- **Phase B DEPLOYED + LIVE GATE PROOF — PASS 5/5** (merge `c4391fc` → production; live `.env`
  `POLYMATH_CORPUS_EXPLORER_FALLBACK_OPEN=1`; ONE port-gated bounce, bundle `327bcbd2385f`, `/ready`, all six
  flags in the orchestrator process env). `eval/corpus_explorer/ce8_fallback_gate_live.py` on the DEPLOYED
  module (`ui.__file__` = MAIN), real embedder + Qdrant + bridge model
  (`CE8-FALLBACK-GATE-LIVE-2026-09-19.json`): (1) `transport:ReadTimeout` fallback + switch ON → **FIRES**
  (12 hits → 8 candidates → generated 4 = admitted 4 = added 4, q0 first + untouched, every subquery carries
  `inspired_by_profile`, receipt marks `plan_fallback`); (2) `invalid_plan:no_queries_for_retrieval` →
  `PLAN_FALLBACK`, plan untouched; (3) switch OFF → `PLAN_FALLBACK` and NO activation work (the pre-fix
  gate); (4) request flag off → `REQUEST_OFF`, plan queries untouched, no CE receipts (flag-off invariance);
  (5) no PRIMARY → `OTHER no_primary:retrieval_not_required:TRANSFORM_USER_CONTENT`, nothing created.
  (A compiler transport fallback cannot be produced on demand over HTTP, hence function-level.)
- **Phase C RE-MEASURE — 15 live executions (C1 8 + C2 7); cumulative 24 = the owner ask line.**
  n rationale (stated before running): no n <= 24 can statistically establish >=95% (0 misses in 11 only
  bounds it near 76%), so the matrix tests for NEW miss causes on UNSEEN queries + negatives + stability +
  provenance + latency; the rate claim rests on the cause table x the 1,379-turn base rates.
  | metric | result |
  |---|---|
  | on-target fired (strict: >=1 CORPUS_EXPLORE subquery, retrieval ran) | **10/11 = 0.909** |
  | on-target, turns that ATTEMPTED exploration | **10/10** (all batches: 14/14; + gate proof 1/1) |
  | unseen fresh on-target queries | **6/6 queries, 7/7 runs** — no new miss cause |
  | the one miss | `physical_weight_f2` → `no_primary:retrieval_not_required:TRANSFORM_USER_CONTENT` (by design; 4/4 lifetime) |
  | negatives fired | **0/4** (2 seen + 2 fresh); 0 activated → leakage none (baseline max 0.143) |
  | same-query content stability when fired | **1.0** over 12 pairs (suppressed_grief x5, nonverbal x2, power_shift x2) |
  | provenance complete (all fired) | true |
  | turns without a receipt | **0/23** |
  | explorer added latency, fired turns (embed+search+bridge call) | p50 **1.81 s** · p95 **2.69 s** · max 2.99 s |
  | turn latency | fired p50 24.6 s / p95 32.2 s; no-retrieval turns p50 1.1 s |
  The fix adds latency ONLY to a requested turn that hit a no-judgment fallback (~2.7% of turns), where
  the explorer previously did nothing. No transport fallback occurred naturally in the 15 Phase C turns, so
  the fix's effect is proven at function level on the deployed code, not yet observed over HTTP; the JSONL
  ledger (`stages.plan_fallback` on a fired row) will show it in production.
  MY PREDICTION WRONG: "a fresh negative may fire" — all four negatives were routed no-retrieval.
- **CLOSURE RUNS — owner-approved past the 24 line (AskUserQuestion 2026-09-20: "Approve 10 runs" — 9
  sentinel + 1 flag-off, classified as CLOSURE not exploratory; "no further expansion automatically
  authorized"). TOTAL LIVE EXECUTIONS = 34** (A1 8 + gate proof 1 + C 15 + sentinel 9 + flag-off 1).
  - **Safety sentinel PASS** (`CE-SAFETY-SENTINEL-2026-09-20.json`, 9 q, feature ON, HYBRID): unsupported
    hallucinations **0** (4/4 declined), q0_preserved failures **0**, provenance incomplete **0**, supported
    gold misses **0** (the 09-19 baseline had one feature-inert gold miss). Its firing receipts are all
    sensible: 4 unsupported → `no_primary:retrieval_not_required:GENERAL_CONVERSATION`; 4 direct/named →
    `INTENT_INELIGIBLE` (MECHANISM / EXACT / DEFINITION / COMPARISON); the one EXPLORATORY query fired (4).
  - **Live flag-off structural check PASS** (run 34, `suppressed_grief`, `corpus_explorer=false`): receipt
    `REQUEST_OFF`; plan origins USER 4 / PROFILE 2 / BRIDGE 1 — no `CORPUS_EXPLORE`; no `corpus_activation`,
    no `corpus_explore_expansion`, no top-level `corpus_explore_firing` key; BRIDGE path intact (admitted 1);
    21 evidence rows. The flag-ON run of the same q0 14 min earlier had the identical USER 4 / PROFILE 2 /
    BRIDGE 1 composition plus CORPUS_EXPLORE 4.
- **ACCEPTANCE — final, against the goal's list.**
  | criterion | verdict | evidence |
  |---|---|---|
  | firing >= 95% on-target | **NOT MET on the strict number: 10/11 = 0.909** · 10/10 when retrieval was attempted | the one miss = intentional no-retrieval routing (owner: leave by design) |
  | negatives quiet, none fire, leakage not worse | **MET** — 0/4 fired (0/6 lifetime), 0 activated | C2 |
  | content-stability-when-fired 1.0 | **MET** — 1.0 over 12 same-query pairs | A1 + C |
  | provenance complete | **MET** | every fired run |
  | flag-off pre-feature-equivalent | **MET structurally + at function level**; strict evidence-id SET EQUALITY **NOT MEASURED** | gate proof case 4 + run 34; an A/A flag-off pair (to separate compiler nondeterminism from code) was not run — no runs authorized beyond 34. Retrieval code is untouched and nothing reads the new receipt key, so equality holds by construction |
  | safety sentinel clean | **MET** | 0 / 0 / 0 / 0 |
  | added latency p50/p95 reported | **MET** — 1.81 s / 2.69 s (fired turns) | C |
  Exact reading of the strict miss (owner wording): 1 non-firing on-target phrasing = routed intentionally
  to `TRANSFORM_USER_CONTENT` = no retrieval attempted = Corpus Explore correctly did not override q0
  authority. No routing-policy override was introduced.

## Rejected claims
- REJECTED (my own Phase A prediction): "on-target misses = `PLAN_FALLBACK` or `INTENT_INELIGIBLE`". Half
  wrong — the reproducible miss is a compiler NO-RETRIEVAL routing decision, not a fallback and not intent.
- REJECTED fix: forcing a q0 PRIMARY when Corpus Explore is requested on a no-retrieval turn. It violates
  q0 authority and would make the same-cause negative (`neg_cooking`) fire. Whether the explicit toggle
  should override the compiler's no-retrieval routing is an OWNER product decision (deferred, reported).
- REJECTED fix: opening the gate for ALL fallbacks (the literal BRIDGE mirror). Only `transport:*` is PROVEN
  on-target; `invalid_plan:*` carries a compiler judgment and is unobserved on-target — left closed,
  receipted and countable. (Disclosed: `neg_vacation` is quiet today only because its phrasing
  deterministically yields `invalid_plan:no_queries_for_retrieval`; the BRIDGE expansion already admits 3
  bridges on that same turn. Subquery-level negative quietness was never a designed guard — CE7 measured
  concept LEAKAGE; the designed guards are intent eligibility + C4/C5/CA4.)
- REJECTED: tuning an activation-score threshold to separate targets (top 0.43–0.51) from negatives (0.276)
  — that is tuning to the query set.
- NOT claimed: `search_atoms` is safe under load (embedder/Metal contention during a busy turn is untested
  by an idle probe) — the live `ATOMS_ERROR_OR_TIMEOUT` code exists to catch exactly that.

## Open contract gaps
MISSION COMPLETE (diagnosed · fixed · live-validated · ledgered · tagged locally). Contract dispositions:
`corpus_explore_firing` **NEW**; `bridge_compiler` / `corpus_activation` / `corpus_explore` /
`evidence_packet` **UPDATED** (additive diag/receipt keys; return values TESTED_UNCHANGED);
`_add_corpus_explore_expansion` / `_finish` / `chat_events` **UPDATED** (receipts on every path + the
no-judgment fallback gate behind a default-off switch). `contract_impact`: `PROFILE_SCOUT_WIRING` (ui.py)
changed → ACCEPTANCE / CANDIDATE_ENGINE / PROFILE_YIELD_RECEIPT / QUERY_PLANNER / RESOLUTION_STATE /
RETRIEVAL_RECEIPT / SUBQUERY_PROVENANCE all **TESTED_UNCHANGED** (7 suites green). Extraction, bridge
reasoning and the extraction contract hash **NOT_AFFECTED** (untouched).

**DEFERRED — owner design question (logged, deliberately NOT answered here):** *Should an explicitly enabled
Corpus Explore toggle override a no-retrieval compiler route?* Today: no (q0 authority). Evidence to weigh:
that same guard keeps every measured negative quiet; overriding it trades a false-positive retrieval
problem for a firing percentage. Needs its own mission + qualification.

**DEFERRED — observations handed on, not fixed here:**
- `invalid_plan:*` fallbacks (2.6% of 1,379 turns; `task_type_invalid:PROCEDURE` dominates) still close the
  explorer by design; unobserved on-target. Countable in the JSONL ledger as `PLAN_FALLBACK invalid_plan:*`.
- Compiler lane health: failover used on 24% of turns (`compiler_alt` HTTP 429, `compiler_alibaba_qwen`
  ReadTimeout). Provider flakiness — not removed here; the fix makes the explorer robust to it.
- `_fetch(cid)` ignores `cid`: `search_atoms` searches the whole atom collection, not the scoped corpus.
  Not a firing cause (single-corpus deployment today) — a scoping question for the coverage audit (item 2).
- `NO_ATOM_COVERAGE` never occurred (0/34); nothing to hand to the coverage audit from this mission.
- The fix's HTTP-path effect was not observed naturally (no transport fallback in 25 requested HTTP turns);
  watch `stages.plan_fallback` on fired rows in `/private/tmp/polymath_fleet/corpus_explore_firing.jsonl`.

REVERSIBLE: `POLYMATH_CORPUS_EXPLORER_FALLBACK_OPEN=0` + bounce restores the pre-fix gate (receipts stay).
Two bounces were used (Phase A instrumentation had to be live to attribute; Phase B fix) — the goal's "ONE
port-gated bounce" was applied per deploy.

**OWNER ACCEPTANCE 2026-09-20 (register 11.349) — Item 1 CLOSED + FROZEN.** Owner scorecard: root-cause
attribution PASS · missing-receipt problem FIXED · fallback infrastructure case FIXED · thresholds/weights
untouched PASS · negative controls PASS · same-query stability PASS · fresh-query firing 6/6 ·
attempted-retrieval firing **14/14 across batches** (the meaningful metric; the strict 10/11 miss is the
intentional `TRANSFORM_USER_CONTENT` case) · provenance PASS · safety sentinel PASS · kill switch PRESENT ·
guards/tests PASS. Two caveats stay explicitly OPEN: (1) `FLAG-OFF: structural equivalence PROVEN · exact
candidate/evidence set equality NOT MEASURED` — never to be restated as "exact equivalence proven";
(2) the 24% compiler backup-lane rate is a SEPARATE reliability problem → `OWNER-BACKLOG.md` B19
`CHAT-COMPILER-PROVIDER-RELIABILITY`, not a Corpus Explore defect. The toggle-vs-routing design question is
parked as B20. Freeze: no higher firing target, no opportunistic retries, no `TRANSFORM_USER_CONTENT`
override, no threshold change, no graph/entity enrichment, no further large CE benchmark.

