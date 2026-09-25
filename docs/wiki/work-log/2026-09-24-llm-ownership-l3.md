---
change_id: LLM-BACKEND-L3-OWNERSHIP
owner: "@king"
date: 2026-09-24
status: complete
status_note: "L-11 (Cloudflare account ids 1, 3, 4, 5, 6) stays OPEN in the gap register: the six tokens list 0 accounts, so the ids come from the owner. L4 (the canary) waits on the owner's word."
architecture_impact: "config (the registry + the two GENERATED runtime files) + shared registry / pool helpers + the profile and pMAP workers' lane order + extraction batch placement + supervisor slots (pMAP 4 -> 6) and slot indexes. Each Groq (key, model) pair gets exactly one calling process. Fence + one bounce."
last_reviewed: 2026-09-24
---

# LLM-BACKEND L3: ownership and wiring

## Contract
- The owner, 2026-09-24 (the L3 prompt): "each of the 18 Groq key × model pairs is owned by exactly one worker slot;
  one Gemini limiter family per account; Cloudflare account ids wired; the runtime files are generated from
  config/llm_accounts.yaml". Cloudflare ids through a read-only `GET /client/v4/accounts` per token, else the owner
  pastes them. No model calls in L3; stop before the L4 test calls.
- Roadmap `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 4; gap rows L-02, L-07, L-11, L-14, L-15, L-20.

## Changes
- The registry `config/llm_accounts.yaml` (the only file edited by hand from now on):
  - `slots.<stage>.owners` maps a slot name to the lanes it owns: doc_profile slot N owns profile_groqN; doc_parent_map
    slot N owns map_groqN + map_groqNq. `slots.doc_parent_map.count` 4 -> 6, with
    `lane_offset_env: POLYMATH_DOC_PARENT_MAP_LANE_OFFSET`.
  - Groq: profile_groq2..6 and map_groq1 enabled; a new lane map_groq1q (key 1 × qwen3.8-27b, a copy of map_groq2q with
    its own family). The doc_profile pin is profile_groq1..6 + the OpenRouter fallback; the pMAP pin is
    map_groq1..6 + map_groq1q..6q + the OpenRouter fallback + cloudflare_map1..2. Every owned Groq lane: rpd 950,
    tpd 190,000 (95 % of the pair; one caller). rpm 2 / tpm 8,000 unchanged.
  - Limiter families: Gemini one per (account, model), 12 (`gemini_acct_N_gemini_3_1_flash_lite`,
    `gemini_acct_N_gemini_3_5_flash_lite`); NVIDIA one per account (both lanes parked).
  - `compiler_alibaba_qwen` disabled (unpinned by 11.464; it was the LANE_UNUSED warning).
  - The notes that lived as comments in `limiter.yaml` (seed semantics, the ollama_cloud ceiling, the SiliconFlow and
    Cloudflare measurements, the Groq per-model limits and measured call sizes) moved into the registry next to each
    account; a docs line marks the JSON as generated.
- Generation: `accounts.py` `render_runtime` / `write_runtime` / `runtime_not_generated`; `scripts/llm_accounts.py write`
  (refuses while the registry has errors). `validate` and `diff` also report runtime bytes that are not the writer's
  output; `report` shows the owning slot. `cloud_providers.json` gains `stage_owners` (list index k-1 = slot k's lanes);
  `limiter.yaml` carries a GENERATED header and lists the local seeds first.
- Registry checks (`accounts.py`): ownership helpers `slot_index`, `stage_owner_groups`, `owned_lanes`, `lane_slots`;
  errors OWNER_UNKNOWN_LANE, OWNER_NOT_PINNED, OWNED_TWICE, OWNER_BAD_SLOT, OWNER_WITHOUT_OFFSET; warnings
  SLOT_WITHOUT_OWN_LANE, OWNER_SPANS_ACCOUNTS. PAIR_SHARED_BY_SLOTS and BUDGET_EXCEEDS_QUOTA now count ONE caller for an
  owned lane and every slot of a stage for a shared one.
- Runtime:
  - `pool.py`: `stage_owners(stage)` and `owned_lane_order(pin, owners, offset, run_key)`: the slot's own lanes (rotated
    by run), then the shared tier (non-"fallback" lanes rotated by run, "fallback" lanes last); another slot's own lanes
    are never included; a slot index past the owner list calls the shared tier only.
  - `doc_profile_worker.py`: `lane_order` / `attempt_lanes` take the owners; with its slot index a profile slot tries
    its own key, then the OpenRouter fallback (L-07). Without an index (one worker, tests): unchanged.
  - `doc_parent_map_stage_worker.py`: `lane_offset()`; `_pmap_lanes` walks the slot's own gpt-oss-20b + qwen lanes,
    then cloudflare_map1 / 2, then map_fallback_openrouter (L-14). Without an index: unchanged.
  - `llm_provider.py`: `batch_lane_indices(slice_idx, n_batches, doc_id)`: batch i goes to slice lane
    (i + hash(document)) mod n_lanes (L-15). Rank slices, the call cache key and the 413 / 429 ladders are unchanged.
  - `process_supervisor.py`: slots doc_parent_map5 and doc_parent_map6 (rollback line in the comment);
    `LANE_OFFSET_ENV` + `lane_offset_env(slot_name)` give profile AND pMAP slots their 1-based index.
    `fleet_autopilot.py`: the pMAP demand cap 4 -> 6. `scripts/bounce_fleet.sh`: expects 26 workers.
- Tests that asserted the pre-L3 config snapshot, updated with the invariant each protects kept:
  - `test_llm_accounts`: 7 idle Groq pairs -> none;
  - `test_llm_limiter_l2`: per-minute overshoot "on shared pairs until L3" -> none for Groq;
  - `test_document_profile_stage`: one profile key -> six, isolation per (key, model) pair; a grep of the supervisor's
    source -> a behavioural check of `lane_offset_env`; the limiter comment phrases are read from the registry;
  - `test_groq_routing`: key-level de-sharing (11.193) -> pair-level (no pMAP lane on a profile pair);
  - `test_lane_registry`: one function per key -> one per (key, model) pair, with the per-key sharing still visible in
    `shared_accounts`; pMAP lane counts 13 -> 15 and 10 -> 12.

## Proof
- `tests/determinism/test_llm_ownership_l3.py`, 21 tests:
  - every Groq pair has one enabled lane, one owner and one caller;
  - budgets are 95 % of the pair and fit the quota;
  - no family spans accounts; each Gemini family covers exactly one (account, model);
  - no registry error, unused lane or ownerless slot;
  - the runtime files are the writer's output; the writer is idempotent; a hand edit is reported;
  - registry slot counts = the supervisor FLEET; owner names = FLEET slot names; the offset variables match;
  - the supervisor gives each slot its index;
  - an owning slot's order for both stages over 30 runs;
  - the real profile and pMAP lane walks on monkeypatched endpoints, including a dark own account and no index;
  - extraction batch placement over 600 documents;
  - the ownership checks on a small registry.

  `test_fleet_autopilot_demand` gains a test: pMAP scales to six.
- The impacted suites (29 files + the new one) ran in the worktree, with import origins verified inside the worktree.
  Recipe: no `.env`, a dead `POLYMATH_TEST_DSN`, `POLYMATH_ATTEMPT_LEDGER=0`, `-k "not test_live_"`.
  - The branch: 308 tests, 0 failures, 3 skipped.
  - Production (a detached worktree, the same 29 files): 286 tests, 0 failures, 3 skipped.
  - Before the test updates, the branch showed 10 failures, every one a pre-L3 config snapshot (listed above).
  - `test_adapter_worker_registration.py` was left out: its fallback DSN is the fleet database.
- `scripts/llm_accounts.py validate` (with `.env`): 0 errors, 10 warnings (was 43).
  - PAIR_SHARED_BY_SLOTS ×5: the shared tier, i.e. cloudflare_map1 / 2 on 6 pMAP slots, profile_fallback_openrouter
    on 6, map_fallback_openrouter on 6, openrouter5 on 2 enrichment slots (-> L5).
  - ACCOUNT_ID_UNSET ×5 (L-11).
- The data diff of the runtime files against production is exactly the change set above (EXECUTED):
  - 6 lanes enabled, 1 added (map_groq1q), 1 disabled;
  - 18 Groq rpd / tpd values;
  - 16 Gemini and 2 NVIDIA families;
  - 2 pins, `stage_owners`, `_doc`.
- Nothing in the change enters the execution contract:
  - `semantic_file_hashes` / `_CONFIG_ENV_KEYS` cover neither provider file nor the slot variables;
  - `reconcile_contract_drift` keys are unchanged;
  - no corpus is re-extracted (READ).

  `cloud_ring` / `pool_fingerprint` (the extraction contract input) are unchanged until the Cloudflare ids arrive.
  Then cloudflare3..6 join the extraction ring, as the owner's 2026-09-13 split intends.
- Cloudflare, EXECUTED read-only under the owner's allowance: `GET /client/v4/accounts` with each of the 6 tokens
  returned HTTP 200, success, 0 accounts (Workers-AI-scoped tokens; the same result as 2026-09-13). No id was found.
- Lint: the changed files carry production's findings minus one (the pMAP worker's unused `os` is now used). The new
  test file is clean. Contract impact (`--staged`): none.

## Rejected claims
- "Fail over to the NEXT slot's key, as the profile pool did": that gives an owned pair two calling processes, and a
  per-process budget of the whole pair would overshoot. Overflow now goes to the shared tier. Borrowing idle budget
  across keys needs a budget shared across processes (L5).
- "Give every pMAP slot its own Cloudflare account": it would change the owner's 2026-09-13 split (accounts 1-2 pMAP,
  3-6 extraction). The two pMAP accounts stay the shared tier.
- "Silence PAIR_SHARED_BY_SLOTS for the fallback lanes": the sharing is real (each of N processes holds a full
  per-process budget). The warning stays until L5.
- "Record Cloudflare's per-account limits as quota": they were not measured here. The 3036 daily park stays the
  enforcement.
- "11.193's rule (one Groq key = one function) still holds": the owner's 2026-09-24 intent (3 models per key, all used)
  replaces it. Since GROQ-MODEL-SWAP-2026-09-23 the limits are per (key, model), so the protection holds per pair,
  and three tests now assert it that way.

## Open contract gaps
- None mapped by `contract_impact.py`: NOT_AFFECTED for every architecture contract.
- L-11 OPEN: CLOUDFLARE_ACCOUNT_ID_1, _3, _4, _5, _6 must come from the owner's dashboard. The pool reads `.env` at
  call time, so the lanes activate with no code change.
- L-06 partly addressed: every Groq pair has one caller. The shared tier's five pairs still hold per-process
  budgets (-> L5).
- New L-22: the operator backfill `scripts/parent_map_backfill.py` walks the whole pMAP pin without a slot index. While
  it runs, an owned pair has a second caller (-> L5, or run it with `--lanes` on the shared tier).
- New O-04: the runtime-budget profiles list no doc_profile / doc_parent_map / adapter_step slot. It is latent because
  the live `.env` sets no `POLYMATH_PROFILE`.
- Live proof waits for L4 and the owner's word:
  - the first profile ticket lands on its slot's own key, and a pMAP document on its slot's pairs;
  - stage tags and settle-to-usage are seen on real traffic (L-03, L-19).
