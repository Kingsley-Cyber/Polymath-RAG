---
title: "WORK LOG — GROQ-ROUTING-POLICY-V1 + slice S7a: account/model routing decision core"
change_id: GROQ-ROUTING-POLICY-V1
date: 2026-09-07
owner: governance + shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.134
package: docs/wiki/plans/GROQ-ROUTING-POLICY-V1.md (new), shared/polymath_shared/document_profile/groq_router.py (new), tests/determinism/test_groq_router.py (new), docs/wiki/plans/CONTINUITY-REPORT.md, docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md, scripts/scaffold_polymath_v4.py
architecture_impact: "Admits the Groq routing policy of record (six accounts = six capacity domains; each account's two models — groq/compound and groq/compound-mini — share ONE account RPD/TPM/RPM budget; per-model latency/density/error EWMAs; compound = global profile / mini = overflow mapping; tools disabled during ingestion; dynamic account+model selection by remaining RPD/TPM/rolling-RPM/Retry-After/latency/billed-tokens/429/in-flight; NO round-robin, NO key burning; durable shared rate state) and lands its deterministic DECISION core `groq_router.choose(work_class, accounts, now, est_total_tokens)` — a pure selection layer above the existing per-lane limiter (which stays the enforcement authority; no second scheduler). Additive: no config change, no fleet change, no live wiring yet. The wiring (compound-mini lanes in cloud_providers.json, per-account family budgets in limiter.yaml, _FamilyGate -> account budget + ControllerStore persistence in limiter.py, capacity-aware selection in pool.py) is the remainder of S7, gated behind the reindex canary."
---

# WORK LOG — GROQ-ROUTING-POLICY-V1 + slice S7a

## Contract

The owner's corrective goal (2026-09-07, Part 3) requires Groq routing to be
production-safe before any reindex: account-level budget coordination across the
two models, dynamic capacity-aware selection (no round-robin, no key burning),
per-model measured EWMAs, tools disabled, and durable shared rate state. Make the
policy repository truth and land the deterministic decision core; gate the live
wiring behind the canary (Part 4).

Owner: governance (policy) + `shared` (the decision core). Public contract:
`groq_router.choose(...) -> RouteDecision` and `AccountState` / `RouteDecision`.
Inputs: injected account states + `now` + estimated request tokens (no clock, no
I/O). Output: `(account, model)` or a typed wait. Verifier:
`tests/determinism/test_groq_router.py`. Rollback: additive doc + module + test.

## Changes

- **`docs/wiki/plans/GROQ-ROUTING-POLICY-V1.md`** (new): the policy of record —
  account = capacity domain (§1), model by work class (§2), per-account budget +
  per-model EWMAs (§3), dynamic selection signals + rules (§4), durable shared
  state via the existing `ControllerStore` (§5), tools-disabled (§6), canary-
  before-scale rollout (§7), and the EXTEND-not-replace build map onto
  `cloud_providers.json` / `limiter.yaml` / `limiter.py` / `pool.py` (§8).
- **`shared/polymath_shared/document_profile/groq_router.py`** (new): the pure
  decision core. `AccountState` keys RPD / rolling-RPM / TPM on the ACCOUNT (both
  models share it) and latency per model. `choose` filters feasible accounts
  (not breaker-open, not Retry-After-locked, RPD > 0, rolling-RPM under the §14.4
  token-guarded ceiling via the corrected `token_feasible_rpm`, TPM headroom for
  the request), picks the one with the most remaining capacity (RPD, then TPM
  headroom, then fewest in-flight, then lowest RPM; deterministic name tie-break),
  and otherwise returns a typed wait (`all_locked` with the soonest unlock,
  `rpd_exhausted`, `no_capacity`, `empty_pool`).
- **CONTINUITY-REPORT / PLAN-AUTHORITY-REGISTER / scaffold**: hooked + declared;
  register row 11.134.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_groq_router.py -q  -> 13 passed
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
```

Pins: work class -> model; picks the account with the most remaining capacity
(NOT a hash ring / round-robin); the account budget is shared by both models (an
RPD-exhausted account serves neither); a Retry-After lock skips the account (and a
sibling is used — no key burning), all-locked waits for the soonest unlock; the
breaker skips an account; TPM headroom and the RPM ceiling are respected, and a
heavy (>15k-token) request drops the ceiling via the corrected token guard;
typed no-capacity vs rpd-exhausted; empty pool; deterministic name tie-break; and
a static AST purity pin.

## Rejected claims

- **Not** a second scheduler authority (AGENTS.md §5.2 / plan §21): this is the
  SELECTION layer; the existing `llm_extraction.limiter` remains per-lane
  ENFORCEMENT. The two models coordinate through the account key, mapping onto the
  limiter's existing `family` / `_FamilyGate` and durable `ControllerStore`.
- **Not** wired live: no `cloud_providers.json` / `limiter.yaml` / `pool.py`
  change in this slice — no fleet or provider-spend change. The current pool still
  runs its doc-hash ring until S7's wiring lands behind the canary.
- **Not** a claim that routing is production-safe yet (AGENTS.md §9): the decision
  core is proven; live safety needs the wiring + the canary (Part 4).

## Open contract gaps

- **S7 remainder (the wiring), gated behind the reindex canary:** add
  `profile_groqN_mini` lanes (groq/compound-mini) beside each compound lane with
  `family: groq_acct_N`; per-account family budgets (rpd 250 / tpm 70000 / rpm 30)
  in `limiter.yaml`; extend `_FamilyGate` to a per-account budget with
  `ControllerStore` persistence and account-level Retry-After locks; replace the
  profile/map `_ring_pick` in `pool.py` with `groq_router.choose`. These touch the
  live fleet + provider spend — do them deliberately, then canary.
- **Part 4 (reindex) remains gated**: run a small controlled document-profile/MAP
  reindex canary proving correct model selection, no oversubscription, partial MAP
  recovery, artifact/projection independence, and no duplicated completed API work
  before expanding concurrency (policy §7). Blocked on S4 (persistence) + S8/S9
  (workers) existing.
- **Part 2 (FINAL retrieval plan) still blocked**: `POLYMATH_FINAL_RETRIEVAL_ROUTING_SYNTHESIS_IMPLEMENTATION_PLAN_2026-09-07.md`
  was not in `~/Downloads`; admit it when supplied (same flow as S0).
