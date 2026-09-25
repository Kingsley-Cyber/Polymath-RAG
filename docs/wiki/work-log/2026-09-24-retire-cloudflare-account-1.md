---
change_id: RETIRE-CLOUDFLARE-ACCOUNT-1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Config + one registry check. Cloudflare account 1 is retired: cloudflare_map1 disabled and off the doc_parent_map pin (the pMAP shared tier is cloudflare_map2, then the OpenRouter fallback). The credential check skips accounts with no enabled lane. Fence + one bounce."
last_reviewed: 2026-09-24
---

# Retire Cloudflare account 1

## Contract
- The owner, 2026-09-24: "its okays for key 1 dispost of it". Account 1's id was never found. The id list sent for it
  held account 2's id (…1efb): token 1 got 403 on the catalog lookup and 401 on a real call (register 11.468).
- Gap row L-11 (Cloudflare accounts parked for want of ids).

## Changes
- Registry `config/llm_accounts.yaml`:
  - `cloudflare_map1` enabled: false and removed from the `doc_parent_map` pin;
  - the Cloudflare notes record the retirement and the rollback (set the id, re-enable, re-pin, run the writer);
  - the account entry stays as the record.
- `config/cloud_providers.json` regenerated (`scripts/llm_accounts.py write`). `limiter.yaml` is unchanged: the lane's
  seed stays.
- `accounts.py` W4: KEY_UNSET / ACCOUNT_ID_UNSET only for accounts with at least one enabled lane. A parked or retired
  account's credentials are not called.
- The live `.env` is untouched: `CLOUDFLARE_API_TOKEN_1` stays, unused. Deleting or revoking the key is the owner's step.
- Tests updated to the new pin, deriving the Cloudflare tier from the config where they can:
  - `test_cloudflare_provider`: the pin ends with `cloudflare_map2`; `cloudflare_map1` is disabled and off the pin;
  - `test_lane_registry`: pMAP lanes 15 → 14;
  - `test_llm_ownership_l3`: the shared tier is read from the pin.

  One new test in `test_llm_accounts`: a parked account is not flagged for missing credentials, and an account in use
  still is.

## Proof
- The impacted suites (the L3 list, 30 files), worktree recipe (PYTHONPATH, no `.env`, dead `POLYMATH_TEST_DSN`,
  `POLYMATH_ATTEMPT_LEDGER=0`, `-k "not test_live_"`): 309 tests, 0 failures, 3 skipped.
- `scripts/llm_accounts.py validate` (with `.env`): 0 errors, 4 warnings (was 6). Only the shared tier remains
  (cloudflare_2 on 6 pMAP slots, profile_fallback_openrouter on 6, map_fallback_openrouter on 6, openrouter5 on 2) → L5.
- Working Cloudflare accounts: 2, 3, 4, 5, 6. Each answered a real call on 2026-09-25 (register 11.468).

## Rejected claims
- "Delete account 1 from the registry": the registry keeps retired and parked accounts as records (the NVIDIA and
  SiliconFlow accounts are parked the same way). A disabled lane is one line to roll back.
- "Remove the key from `.env`": that destroys a credential's only local copy. It is the owner's step, as permanent
  deletes are.

## Open contract gaps
- None mapped by `contract_impact.py` (no architecture contract touched).
- L-11 CLOSED 11.469: accounts 2-6 wired and live; account 1 retired by the owner.
