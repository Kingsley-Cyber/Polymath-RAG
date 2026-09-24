---
change_id: GROQ-MODEL-SWAP-2026-09-23
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "config + one pool function on branch feat/groq-model-swap. Profile lane profile_groq1 → openai/gpt-oss-120b (reasoning low). pMAP lanes map_groq2..6 → openai/gpt-oss-20b (low), plus new map_groq2q..6q → qwen/qwen3.8-27b (reasoning none) on the same keys. Each (key, model) has its own limiter family (Groq limits are independent per model per key). pool_fingerprint() now covers only lanes extraction can dispatch to, so dedicated-lane re-models never move the extraction contract or cache. Pool batch cap stays 15."
last_reviewed: 2026-09-23
---

# GROQ-MODEL-SWAP-2026-09-23: compound is gone; profiles and pMAP move to gpt-oss / qwen, qualified first

## Contract
- The owner, 2026-09-23:
  - "groq provider model needs to be updated to support these models": openai/gpt-oss-120b, openai/gpt-oss-20b,
    openai/gpt-oss-safeguard-20b, qwen/qwen3.8-27b.
  - "compound and mini compound are no longer supported".
  - Limits are "interdependent" per model per key: 30 RPM / 1K RPD / 8K TPM / 200K TPD.
  - "low and none is fine and perfect" for reasoning.
- AskUserQuestion answer: "Canary + mapping OK" (≤ 40 calls). The mapping: key 1 → profiles on gpt-oss-120b; keys 2–6 →
  pMAP on gpt-oss-20b + qwen3.8-27b.
- The provider's own reasoning docs, pasted by the owner: gpt-oss takes `reasoning_effort` low; qwen3.8-27b takes `none`.
  `openai/gpt-oss-safeguard-20b` is a policy classifier, so it gets no generation lane.

## Changes
- `config/cloud_providers.json`:
  - `profile_groq1..6` → `openai/gpt-oss-120b`, `reasoning_effort: "low"`. Only 1 is enabled, as before.
  - `map_groq1..6` → `openai/gpt-oss-20b`, `"low"`. 2–6 are enabled, as before.
  - NEW `map_groq2q..6q` → `qwen/qwen3.8-27b`, `"none"`, same key as `map_groqN`, dedicated, `map_batch_cap` 15. They are
    pinned to `doc_parent_map` after the gpt-oss lanes.
  - A `_doc` entry records the swap and the canary.
- `config/extraction_models/limiter.yaml`: every Groq lane has its own family per (key, model), e.g. `groq_acct_2_gpt_oss_20b`
  and `groq_acct_2_qwen3_8_27b`.
  - Why: `record_failure` opens a family-wide cooldown, so a qwen refusal must never cool gpt-oss on the same key.
  - Budgets are per PROCESS: `tpm 8000`, `rpm 2`; `rpd 150` for profiles (6 slots share key 1), `rpd 200` for pMAP
    (4 slots).
- `shared/polymath_shared/llm_extraction/pool.py::pool_fingerprint()` fingerprints only the extraction roster: the
  non-dedicated lanes, or all lanes when every lane is dedicated (the rule `select_cloud_endpoint` / `cloud_ring` apply).
  - A dedicated lane cannot extract, so re-modelling it cannot change what a document is extracted by.
  - Before, the swap would have silently re-keyed the extraction call cache (`llm_provider._key`).
- `.env.example`: comment.
- Tests updated to the owner's rule (the owner: "you can change it"):
  - `test_document_profile_stage` (profile model + reasoning; the limiter comment);
  - `test_groq_routing` (pin + models);
  - `test_control_plane_status` (two pMAP model groups of 5 lanes);
  - `test_lane_registry` (13 pinned lanes, 10 Groq caps, per-model families);
  - `test_groq_account_isolation` (per-model families).
  - New test: `test_extraction_pool::test_fingerprint_is_the_extraction_roster_so_a_dedicated_lane_never_moves_it`.

## Proof
- **Canary** (`docs/wiki/experiments/groq-model-canary-2026-09-23/`, 17 calls):
  - Raw HTTPS with the production payload, parsed by the production compilers. Nothing written to the fleet.
  - `groq/compound-mini` → 404 "does not exist". The live profile / pMAP lanes were dead for every new document.
  - pMAP gpt-oss-20b: 6/6 calls, 15/15 and 8/8 valid maps, 0 rejected lines, 0.6–0.9 s, 2.0–3.0K prompt + 0.2–0.4K
    completion tokens.
  - pMAP qwen3.8-27b: 4/5 calls valid (15/15, 8/8), 0.9–1.4 s. One call was refused: key 5's org enforces an
    output-tokens-per-minute cap (OTPM 1000) on this model. The error names it; the pool's lane failover absorbs it.
  - Profiles gpt-oss-120b: 3/3 valid, full field counts (10 / 10 / 15 / 15 / 10 / 10 / 10), 2.5–2.7 s.
  - qwen3.8-27b and gpt-oss-20b: valid and full (candidate fallbacks).
- **Tests:** 17 Groq / lane / pMAP / pool suites: 153 passed, 15 skipped.
- **Blast radius checked:** `pool_fingerprint` feeds only the extract stage's receipt identity and call cache, not the
  execution contract (`worker_contracts()` = query_policy / chunker / semantic_bundle / ontology / extraction_gate). So the
  reconciler mints no successors and nothing re-extracts. The batch planner's cap stays 15, so batch identities are unchanged.

## Rejected claims
- **"The 8K TPM forces smaller pMAP batches":** false. A 15-parent batch is 2.3–3.4K total tokens.
- **"The Groq router must be re-pointed":** `groq_routing.route` has no production caller (test-only).
  - Its `WORK_CLASS_MODEL` still names compound. Left alone and noted; a separate cleanup.

## Open contract gaps
- The limiter is per process and cannot enforce a key's TPM across processes, and it has no OTPM notion. Overshoot shows up
  as 429s that AIMD and failover absorb (pre-existing, recorded in the forensic audit).
- `groq_router.WORK_CLASS_MODEL` still names compound (dead path).
- The 3 pending `profile_document` tickets are not advanced by this change:
  - 1 belongs to a cinema run parked in `intake` since 2026-09-07;
  - 2 belong to commerce-v1 `reconciling` runs (2026-09-21), which are inside the owner's cleanup scope.
