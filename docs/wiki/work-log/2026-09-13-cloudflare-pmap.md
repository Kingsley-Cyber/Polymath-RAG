---
title: "WORK LOG — CLOUDFLARE-PMAP-V1: qualify Cloudflare Workers AI for Parent-MAP, re-split the six keys (2 pMAP / 4 graph extraction), activate, and run the cinema backfill"
change_id: CLOUDFLARE-PMAP-V1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.255
architecture_impact: "Owner reversal of 11.254's 'Parent-MAP untouched': two Cloudflare lanes (accounts 1-2) join the doc_parent_map pool as dedicated TEXT-mode lanes after a production-path qualification (100% single-pass at cap 15, 0 empties); accounts 3-6 become graph-extraction helpers; 0 Cloudflare on doc_profile. Compiler gains a hook-separator tolerance (a '|'-separated hook tail compiles to three hooks, same map_hash). run_document_mapping labels each batch with the provider FAMILY/model that served it. The backfill ring fails LOCAL refusals over to the next lane. All six lanes enabled:true; the fleet was bounced (ONE hash a6be8823bc0b); 5/6 lanes park until their account ids arrive. §19 forensic hold lifted by the owner for cinema."
---

> Owner (2026-09-13): "qualify cloudflare for pmap and run the backfill on cinema. i literally want 2 keys on
> pmap and 4 on graph extractions." — reverses the 11.254 "do not touch Parent-MAP" scope and lifts the §19
> cinema spend hold. Everything below is measured (nothing from memory); numbers come from the pass evidence.

## Contract
The pMAP pool was provider-TPD-bound (11.253: Groq llama-3.3-70b 100k tokens/day/org ≈ 240 parents/day/org;
cinema had 3,810 unresolved parents across 23 docs at 05:52 UTC). Cloudflare must plug into the EXISTING pool
mechanics (`stage_pins.doc_parent_map`, dedicated lanes, the pool's MIN `map_batch_cap`), be qualified with the
PRODUCTION prompt + request shape + compiler on real unresolved cinema parents, be promoted only on a PASS, and
must not weaken the MAP schema (alias identity, ~10-12-word signature, exactly 3 hooks). Persisted maps must
carry the provider that actually produced them.

## Changes
- **Qualification harness** (scratch, evidence committed): production path `build_parent_skeletons` →
  `build_grounding_context` → `plan_batches(reliability_cap=15)` → `build_map_prompt` →
  `LLMExtractionClient.complete_one(max_tokens=2400)` → `compile_maps`; 3 real cinema docs × 3 batches × 15
  parents per arm (thinking-on vs `/no_think`), nothing persisted. Evidence:
  `docs/wiki/experiments/cloudflare-workers-ai-2026-09-13/pmap-canary.json`, `pmap-format-suffix-probe.json`.
- **config/cloud_providers.json**: the six lanes re-split per the owner — `cloudflare_map1`/`cloudflare_map2`
  (tokens+accounts 1-2; dedicated:true, structured:text, json_mode:false, `think_suffix: null` = thinking ON,
  `map_batch_cap: 15`, request_char_budget 18000) appended to `stage_pins.doc_parent_map`; `cloudflare3..6`
  (tokens 3-6; dedicated:false, json) in the graph-extraction ring; the two former summary lanes removed from
  `stage_pins.doc_profile`. **All six `enabled:true`** (a lane with no account id parks cleanly).
- **config/extraction_models/limiter.yaml**: keys follow the new lane names; families stay per account
  (`cloudflare_acct_1..6`); rpm 30 / conc_cap 2 seeds, AIMD adaptive. **.env.example**: comment only.
- **map_compiler.py** (not a bundle member): SEPARATOR TOLERANCE — when a MAP line's hook tail has more than
  one `|` field and no `;`, the tail is the hook list (three hooks, identical `map_hash` to the `;` form);
  a `;` tail is byte-identical to before; short tails still flag `hooks_count:N`.
- **doc_parent_map_worker.py**: `provider_family(url, name)` (host → `groq`/`openrouter`/`cloudflare`/…) and
  per-batch labels `_batch_labels()` = `infer.last_provider`/`last_model` (set by the boundary before dispatch)
  with the run-level labels as fallback; used on every `persist_maps`/`record_batch_result` in the loop.
- **doc_parent_map_stage_worker.py** `_make_pmap_infer` and **scripts/parent_map_backfill.py** `_routed_infer`
  set `infer.last_provider/last_model` per lane. The backfill ring additionally FAILS OVER a local refusal
  (`_last_http_dispatched=False`) to the next lane (bounded by the ring length) instead of deferring the batch;
  a dispatched fault (429/5xx) still defers. New `refused` counter → summary `lane_local_refusals`.
- **Fleet bounce** (coordinated with the enable flip; the pre-802adbb pool raised on any enabled lane without
  a literal `url`): all three stray supervisors stopped, one clean `scripts/boot_polymath.sh` → 23 healthy /
  ONE hash `a6be8823bc0b` / `/ready` true / 0 quarantines.
- **Tests**: `test_parent_map_compiler.py` +1 (pipe tail → 3 hooks, same hash; `;` tail unchanged; short tail
  flags); `test_parent_map_backfill_spread.py` +5 (failover to next lane + labels, all-refused → undispatched,
  dispatched fault not retried, refusals surfaced, `provider_family`); `test_doc_parent_map_worker.py` +2
  (labels follow the infer lane; plain infer falls back to run labels); `test_cloudflare_provider.py` test 12
  re-pointed to `cloudflare3..6`, +2 (owner split shape; pMAP promotion gate bound to the report's PARENT-MAP verdict).
  `test_lane_registry.py`: the PMAP pool total was a magic `6` (the pre-11.255 composition); re-pinned to
  `len(stage_pins.doc_parent_map)` (= 8) so the test checks the config's contract, not a stale count.

## Proof
- **pMAP qualification (135 parents per arm, same batches)**: thinking-on **9/9 batches COMPLETE, 135/135
  parents, 0 empty, 0 rejected lines, `finish=stop` every call, mean 8.4 s**; `/no_think` 9/9, 135/135, mean
  2.3 s. Groq baseline 98.8% (11.251). Provider usage per request: thinking-on ~2.37k in / 1.37k out.
- **Quality finding**: hook-separator drift — whole responses write `|hook1|hook2|hook3`; the compiler kept ONE
  pipe-joined hook (`hooks_count:1` on 45/135 thinking-on, 75/135 `/no_think`; Groq 5/8,183). A per-lane
  prompt reminder halved it (probe: cured 1/2 and 1/3 drifted batches) → REJECTED; the compiler tolerance
  neutralises it fully and is unit-pinned. Thinking-on writes Groq-like signatures; `/no_think` is terse →
  **PROMOTE thinking ON**.
- **Live lane view after the bounce** (`pool.cloud_endpoints()` + `lane_registry.build_lanes()`): pMAP active =
  map_groq2..6 + map_fallback_openrouter + **cloudflare_map2** (cap 15); cloudflare_map1, cloudflare3..6 =
  `configured_credential_absent`; doc_profile pin = profile_groq1 + profile_fallback_openrouter (0 Cloudflare).
- **Account-id discovery closed**: all five remaining tokens list zero accounts (`GET /accounts` → `n=0`) and
  are refused on `/memberships` and `/user` → the ids must come from the owner.
- **Tests**: 73 green across the compiler / backfill-spread / map-worker / stage-worker / cloudflare /
  completion-truth / store suites (1 pre-existing skip). Guards: repo_guard ok, wiki_worm ok, bundle
  `bundle_integrity` READY (map_compiler/worker files are not lock members).
- **Cinema backfill**: pass loop launched 07:05 UTC (`parent_map_backfill.py --corpus cinema --project
  --concurrency 4`, resumable passes until 0 unresolved or a zero-progress pass). Receipts are appended
  to this log by the follow-up docs commit when the loop finishes; per-pass evidence is committed as
  `docs/wiki/experiments/cloudflare-workers-ai-2026-09-13/cinema-backfill-2026-09-13.json` then.

## Rejected claims
- **"Cloudflare's reasoning burns the 2400-token map budget"** — DISPROVEN for pMAP: `finish=stop` on all 18
  calls; the map task's reasoning is short (~1.4k tokens). (It DID burn small budgets on the extraction canary.)
- **"Fix the hook drift in the prompt"** — REJECTED: the production prompt already demands `;` and exactly 3
  hooks; a per-lane reminder only halved the drift. Format tolerance in the compiler is deterministic and
  identity-preserving; the schema (3 hooks) is unchanged.
- **"Bump MAP_COMPILER_VERSION for the tolerance"** — REJECTED: it would orphan all 8,183 existing maps
  (batch/map identity keys on the contract); the change alters only lines that previously produced a defective
  pipe-joined single hook.
- **"Keep account 2 on graph extraction (original CF1-4 grouping)"** — REJECTED: it is the only account with an
  id; the owner's immediate ask is pMAP throughput, so accounts 1-2 are the pMAP pair (reversible config).
- **"The bounce is optional (config is read live)"** — REJECTED: the running pre-802adbb pool raised
  `provider needs url+model` on any ENABLED lane lacking a literal `url`; enable + bounce are one step.

## Open contract gaps
- **5/6 Cloudflare lanes parked** until `CLOUDFLARE_ACCOUNT_ID_{1,3,4,5,6}` are supplied (tokens cannot
  self-report their account). With one account the pMAP pool gains ~2,800 parents/day (Free tier neurons).
- **Cloudflare Free allocation** — the 3036 park stops a lane at exhaustion (0 HTTP after); the day's remaining
  parents ride Groq/OpenRouter or the next UTC window. Whether account 2 is Free or paid is not known.
- **Bounce hygiene trap recorded in CONTINUITY §6**: `ps | grep control.process_supervisor` matches the calling
  shell and the supervisor runs with a RELATIVE `.venv/bin/python` — match on `python -m control.process_supervisor`
  and kill via `xargs`, never `kill $VAR` with a multi-line variable (zsh: "illegal pid" = nothing killed).
- **Control heartbeat**: the supervisor restarted `control.main` at boot for a stale tick heartbeat (112,149 s —
  predates this session); re-verified after the restart (see CONTINUITY).
