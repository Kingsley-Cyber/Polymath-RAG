---
title: "WORK LOG — RAG-finish Phase 3: RATE-LIMIT-SEED-V1 + EFFECTIVE-CAPACITY-V1"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (capacity metadata + precedence resolver; no runtime behavior change)
last_reviewed: 2026-09-09
status: complete
register: 11.188 (pending)
package: config/rate_limit_seed/catalog.v1.json, shared/polymath_shared/llm_extraction/effective_capacity.py, tests/determinism/test_effective_capacity.py, scripts/lane_inventory.py
architecture_impact: "Adds a vendored (no-CDN) rate-limit reference seed + an effective-capacity precedence resolver (runtime headers > explicit config > seed > unknown). Pure policy; no provider call; not wired into the scheduler runtime (bundle hash unchanged, no fleet fence). No provider quota spent."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 3** + register **11.188** (pending).

## Contract

Stop manually rediscovering published RPM/TPM/RPD while keeping runtime truth authoritative (plan Phase 3):
a versioned LOCAL seed (no hard runtime CDN dependency), exact-identity mapping only (unknowns stay
unknown, never 0), explicit per-account config as higher authority, runtime headers highest, and an
effective-capacity view printable without a provider call.

**Catalog evaluation (Phase 3 action 1):** `llerandi/llm-rate-limits-tracker` — MIT, weekly JSON at
`data/rate-limits.json`. It does **not** cover this deployment's load-bearing lanes (groq/compound,
groq/compound-mini, SiliconFlow, OpenRouter model tiers). So it is used ONLY as a low-authority reference
seed; the explicit `limiter.yaml` config and runtime headers govern every real lane.

## Changes

- `config/rate_limit_seed/catalog.v1.json` — vendored reference snapshot with provenance (source repo,
  path, MIT license, `retrieved_at`). Generic tiers only; unknowns are `null`. LOWEST authority.
- `shared/polymath_shared/llm_extraction/effective_capacity.py` (EFFECTIVE-CAPACITY-V1): `resolve(lane,
  observed=None)` layers, per field (rpm/tpm/rpd/conc_cap), `observed > config > seed > unknown` with a
  `sources` map; `resolve_all(registry)`; `seed_for()` provider/model match (exact/substring then `*`).
  Null never coerced to 0. No provider call. Runtime-header truth is an optional caller input (the limiter
  owns it live).
- `scripts/lane_inventory.py --effective` / `--json` now render the resolved effective-capacity + sources.
- `tests/determinism/test_effective_capacity.py` — 7 provider-free precedence tests.

## Proof

- `pytest tests/determinism/test_effective_capacity.py` → **7/7 green**: config beats seed; seed fills a
  config gap; null seed + absent config stays unknown (not 0); observed beats config; catalog-unavailable
  still resolves from config; provider-slug inference; real-registry resolve is per-lane isolated.
- `scripts/lane_inventory.py --effective` (live config): every Polymath lane resolves from `config`;
  siliconflow resolves `unknown` (concurrency-governed, no rate seed) — correct.
- `bundle_integrity` READY, hash unchanged `7e97368daa92ec19` (unwired) → no fleet fence.
- `repo_guard` / `wiki_worm` / `agent_preflight` ok.

## Rejected claims

- **NOT claimed:** the vendored catalog governs any real lane. It is the lowest authority and covers none
  of the load-bearing models; explicit `limiter.yaml` + runtime headers govern. The seed exists so a NEW
  provider added without explicit config inherits sane published defaults instead of a guess.
- **No runtime CDN dependency introduced** (plan do-not-do list): the seed is a committed local file;
  nothing fetches it at runtime.

## Open contract gaps

- The effective-capacity resolver is not yet consumed by the scheduler/limiter at runtime (config already
  drives the limiter; `observed` header truth is owned live by the 11.185 limiter). Surfacing it in the
  canonical status/diagnostics is a Phase 12 concern.
- Groq per-account real RPD remains UNVERIFIED (forensic hold); the seed leaves it `null` and config shows
  the 230 seed — the live probe (owner-gated) or a Phase 15 canary header capture would reconcile it.
