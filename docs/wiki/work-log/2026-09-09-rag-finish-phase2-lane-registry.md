---
title: "WORK LOG — RAG-finish Phase 2: LANE-REGISTRY-V1 (explicit account/model lane registry)"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (read-only observability over the provider control plane; no runtime behavior change)
last_reviewed: 2026-09-09
status: complete
register: 11.187 (pending)
package: shared/polymath_shared/llm_extraction/lane_registry.py, scripts/lane_inventory.py, tests/determinism/test_lane_registry.py
architecture_impact: "Adds an explicit, sanitized, queryable account/model lane registry + query views over the existing pool/limiter config. Pure policy (reads config + env PRESENCE, no network, no provider call, no secret). NOT wired into any worker — the bundle-integrity hash is unchanged (7e97368daa92ec19), so no fleet fence/restart. Makes one-key-one-account explicit and cross-function credential sharing visible (plan §1.5 rule 7). No provider quota spent."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 2** (freeze/implement the account/model lane registry) + register **11.187** (pending). Forensic hold unaffected.

## Contract

Make provider capacity explicit and stop provider-wide shared-family behavior (plan Phase 2). Deliver a
lane registry answering the required query views (function→lanes, account/key→functions/models,
model→functions/accounts, lane→configured/credential-present/active/reachable) plus a sanitized inventory
the offline gate can print WITHOUT a provider call, with NO secret ever rendered.

**Acceptance:** the four functional pools + the parent_enrichment bridge are represented; one-key-one-account
isolation is visible; cross-function credential sharing (the six Groq accounts on compound + compound-mini)
is surfaced; the inventory renders api_key_env NAMES only; tests green; guards green.

## Changes

- `shared/polymath_shared/llm_extraction/lane_registry.py` (LANE-REGISTRY-V1): reads the SAME config the
  pool/limiter use (`config/cloud_providers.json` endpoints+stage_pins, `config/extraction_models/limiter.yaml`
  per-lane family+capacity) and resolves credential PRESENCE (bool only). Emits `LaneInfo` per configured
  lane (active AND parked) with function, account_id (=api_key_env), model, provider_host, dedicated, role,
  reachability (active/configured_credential_absent/disabled), and declared `LaneCapacity` seed. Query views:
  `by_function`, `by_account`, `by_model`, `shared_accounts` (cross-function credential audit),
  `reachability`, `unreachable_pins` (whole-dark pools that would raise `PinnedProviderUnavailable`).
  `sanitized_inventory()` renders a secret-free table.
- `scripts/lane_inventory.py`: operator entrypoint (`--json`), declared in `scripts/README.md`. Prints the
  sanitized effective-capacity table with no provider call (Phase 2 + Phase 3 gate).
- `tests/determinism/test_lane_registry.py`: 9 provider-free tests.

## Proof

- `pytest tests/determinism/test_lane_registry.py` → **9/9 green**.
- `scripts/lane_inventory.py` output (live config): 4 functional pools mapped — CHAT (compiler1-4,
  compiler_alt), GRAPH_EXTRACTION (gemini1-4/1b-4b, nvidia2, siliconflow1-3, primary), DOCUMENT_PROFILE
  (profile_groq1-6 + 3 fallbacks), PMAP (map_groq1-6) + parent_enrichment bridge. Cross-function credential
  sharing surfaced: GROQ_API_KEY_1..6 → {DOCUMENT_PROFILE, PMAP} (the intended exception), and also
  GEMINI_API_KEY_1..4 → {CHAT, GRAPH_EXTRACTION} (separate limiter lanes, one shared per-key-per-model Google
  quota — documented), GEMINI_API_KEY_5/6 & OPENROUTER keys → {profile/enrichment}. No secret rendered
  (planted-sentinel test asserts the value never appears).
- `bundle_integrity` READY, hash **unchanged** `7e97368daa92ec19` (module unwired) → no fleet fence/restart.
- `repo_guard` ok, `wiki_worm --check` ok, `agent_preflight` ok.

## Rejected claims

- **NOT claimed:** that Phase 2 removes a live provider-family coupling defect. The 11.185 repair already
  isolated Groq to `family: groq_acct_N`; this slice makes the isolation + the intentional shares VISIBLE
  and testable. No coupling defect remained to remove; the doc-profile fallback path is already reachable
  (`attempt_lanes`, verified in Phase 1).
- **Runtime cooldown/breaker excluded** from the static registry (config-only) so the offline gate is
  deterministic; runtime lane health belongs to the limiter/controller-store and to Phase 12 status.

## Open contract gaps

- The Groq `rpd 230` seed shown is the limiter.yaml value — UNVERIFIED against provider headers (forensic
  finding). Phase 3 layers the effective-capacity precedence (runtime headers > explicit account config >
  vendored catalog seed). No live probe run.
- The registry is not yet surfaced in a runtime endpoint; Phase 12 (canonical status) will expose it.
