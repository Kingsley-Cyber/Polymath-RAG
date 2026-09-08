---
title: "WORK LOG — S5 profile-vNext budget canary (LIVE, budget selected = 500)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S5-CANARY
date: 2026-09-07
owner: governance (canary tool + measured decision; owner-authorized spend)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.146
package: scripts/profile_vnext_canary.py, shared/polymath_shared/document_profile/fingerprint.py, tests/determinism/test_document_fingerprint.py, docs/wiki/experiments/document-profile-vnext-canary-2026-09-07.md, docs/wiki/experiments/document-profile-vnext-canary-2026-09-07.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "The first LIVE migration gate crossed (owner-authorized controlled canary). Runs the vNext fingerprint at 500/1000/1500/2000 on a 5-doc cinema cohort through the EXISTING doc_profile Groq pool (20 groq/compound calls, 0 errors) and selects the smallest acceptable budget. Decision: DEFAULT_BUDGET_TOKENS 1000 -> 500. Reuses fingerprint + profile_prompt_vnext + workers.doc_profile_worker._pool_complete (no new provider path, no second scheduler). Read-only against Postgres; no fleet-config/schema/live-stage change; scripts/ is fence-free (the fingerprint default is a shared/ one-liner)."
---

# WORK LOG — S5 profile-vNext budget canary

## Contract

Owner /goal (2026-09-07) authorized crossing the live gates, starting with the S5
canary: "small controlled real-document cohort, record quality/cost/latency evidence,
select the smallest acceptable fingerprint budget, then continue into S8." Plan §18 /
S5 exit: "global profile quality ≥ current gate, no late-structure bias; pick the
smallest quality plateau."

Owner: `governance` (a canary tool + a one-line default selection). Verifier +
evidence: `scripts/profile_vnext_canary.py` + the experiment report/JSON. Rollback:
revert `DEFAULT_BUDGET_TOKENS` to 1000 (the fingerprint is unchanged otherwise).

## Changes

- **`scripts/profile_vnext_canary.py`** (new, SPENDS): per (doc, budget) builds the
  fingerprint, renders `profile_prompt_vnext`, and calls the existing `doc_profile`
  pool once; records input tokens / latency / field + tag coverage / a late-structure
  (no-first-400-bias) ratio; paced; `--preflight` (1 call); writes evidence JSON.
- **`fingerprint.py`**: `DEFAULT_BUDGET_TOKENS` 1000 → **500** (canary-selected floor),
  with the evidence cited in the comment. The adaptive 500-2000 range is unchanged.
- **test**: `test_default_budget_is_canary_selected_floor` pins the decision.
- **experiment report + JSON**, **scripts/README** registry row, **TREE** lines, this
  work-log.

## Proof

```
.venv/bin/python scripts/profile_vnext_canary.py --corpus cinema --docs 5 \
   --out docs/wiki/experiments/document-profile-vnext-canary-2026-09-07.json
     -> 20/20 calls ok, 0 errors (fleet idle on profiles; no shared-budget collision)
.venv/bin/python -m pytest tests/determinism/test_document_fingerprint.py -q  -> 18 passed
.venv/bin/python scripts/repo_guard.py / wiki_worm.py --check / agent_preflight.py -> ok
```

Per-budget means (5-doc cinema cohort): **500** → input 969 tok, lat 10.0 s, 16 fields,
7 research tags, late-structure 0.824; 1000/1500/2000 → input 1350/1633/1748 tok, same
or slightly LOWER coverage (2000: 14.4 fields / 5.6 tags), late-structure 0.77/0.78/0.93.
Field + tag coverage saturates at 500; the no-first-400-bias gate is already met at 500
(the coverage surface spans the whole document at every budget); higher budgets nearly
double input cost for no gain. **Selected budget: 500 (the floor).** Full analysis:
`docs/wiki/experiments/document-profile-vnext-canary-2026-09-07.md`.

## Rejected claims

- **Not** a self-retrieval qualification: the canary answers the BUDGET question
  (coverage + bias + cost), not the profile self-retrieval rank vs the current gate
  (top-1 85.8%) — that needs the vNext profile projected + queried, which is the
  S8/projection step.
- **Not** a bigger-is-better result: 2000 tokens measured WORSE coverage than 500; the
  fingerprint's value is the coverage distribution, not the token count.

## Open contract gaps

- Self-retrieval qualification of the vNext profile (project → query → rank) is the
  S8/projection gate; the budget is now fixed at 500 for it.
- The canary parses raw labelled items (light); the authoritative parse of the research
  tags is the S8 compiler extension.
