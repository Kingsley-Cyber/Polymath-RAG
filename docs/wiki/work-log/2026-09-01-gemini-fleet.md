---
change_id: GEMINI-FLEET-V1
owner: governance
date: 2026-09-01
status: complete
architecture_impact: provider pool grows to 14 endpoints; enrichment pin group widens to 4 lanes
last_reviewed: 2026-09-01
---

# WORK LOG — GEMINI-FLEET-V1 (6 AI Studio lanes: 4 extraction + 2 enrichment)

## Contract
Owner 2026-09-01: six Google AI Studio credentials — "4 for
extractions and 2 for enrichment using the cheapest model", linking
gemini-2.5-flash-lite. Live probe found 2.5-flash-lite RETIRED for
new users (404 "no longer available to new users"); the current
cheapest lite tier was first read as **gemini-3.5-flash-lite**; the
owner then re-pinned to **gemini-3.1-flash-lite** ("its cheaper",
2026-09-01) — strict-schema canary green on 3.1 before the re-pin. Credential
formats: one classic AIza key + five AQ.-format keys — ALL SIX
authenticate against the Generative Language API (the AQ. format is
valid key material, not OAuth debris).

## Changes
- `config/cloud_providers.json`: gemini1..gemini6 on
  gemini-3.1-flash-lite (owner re-pin; initially 3.5-flash-lite) via the OpenAI-compat endpoint
  (`…/v1beta/openai` — the compat layer tolerates the client's
  hardcoded `/v1/chat/completions` suffix, LIVE-VERIFIED, so zero
  client changes). `structured: "schema"` (strict json_schema canary
  GREEN — correct object returned), `reasoning_effort: null` (omit;
  Gemini compat's accepted values differ from Groq's "none").
  gemini1-4 shard extraction; gemini5-6 `dedicated: true` and the
  parent_enrichment pin group widens to [nvidia, groq5, gemini5,
  gemini6].
- `config/extraction_models/limiter.yaml`: gemini1..6 buckets seeded
  conservatively (rpm 12, conc 3, AIMD adaptive) — free-tier lite
  limits are unpublished for 3.5; AIMD climbs on clean successes.
- Keys → gitignored `.env` as GEMINI_API_KEY_1..6 (SECURITY law:
  never in the registry, repr, or logs).

## Proof
- Preflight canary (`scripts/probe_cloud_endpoints.py`, the
  before-batch-spend law): all 6 gemini lanes OK (~0.5 s) on two
  clean runs; full roster 13/14 green.
- Roster proof post-bounce: `cloud_endpoints()` = 14; extraction
  shard = [gemini1-4, groq1-4, nvidia2, primary]; `stage_pin
  ('parent_enrichment')` = [nvidia, groq5, gemini5, gemini6];
  dispatch over 24 doc ids shards across all four pin lanes.
- Strict-schema wire canary green on BOTH 3.5-flash-lite and the
  final 3.1-flash-lite pin: exact requested object at temperature 0;
  all-lane preflight green on 3.1 (a single transient gemini4
  ReadTimeout cleared on rerun).

## Rejected claims
- "Pin gemini-2.5-flash-lite as the owner linked" — impossible:
  retired for new users (live 404). 3.5-flash-lite is the successor
  cheapest-lite; a one-line re-pin if the owner prefers otherwise.
- "The AQ. strings are OAuth tokens, not API keys" — my initial
  read, REFUTED by probe: all five authenticate as keys.

## Open contract gaps
- nvidia2 (super-120b) is FLAPPING upstream (503 ↔ OK across probes)
  — left enabled: it is a ring member and dispatch failover covers a
  dark lane. Watch `EXTRACTION_LANE_FAILOVER` counters; park it
  (`enabled: false`) only if the flap becomes a hard outage.
- Gemini free-tier daily caps (RPD) are enforced upstream, not in
  limiter.yaml; a lane that exhausts its day goes 429 and the ladder
  routes around it — expected, but corpus-scale ingests should watch
  the failover counters.
