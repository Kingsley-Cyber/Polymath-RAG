---
change_id: GROQ-EXTRACTION-FLEET-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: fenced (contract strict schema, client level-1 dispatch, pool dedicated flag) + registry/limiter/.env; extraction fleet = primary + 5 Groq accounts, NVIDIA lanes enrichment-exclusive
last_reviewed: 2026-08-30
---

# WORK LOG — GROQ-EXTRACTION-FLEET-V1 (5 unlinked accounts join baseline extraction)

## Contract
Owner 2026-08-30: "for entity extraction in baseline i want groq to join
cloud with ollama. i own 5 devices" + per-lane spec: model
qwen/qwen3.8-27b, reasoning_effort none, temperature 0, structured
output = STRICT JSON SCHEMA, max output tokens tightly bounded. Five
unlinked Groq accounts, each with its own rate limit.

## Changes
- `groq1..groq5` endpoints (registry): qwen/qwen3.8-27b,
  reasoning_effort "none", `structured: "schema"`, keys
  GROQ_API_KEY_1..5 in the gitignored .env. The old single `groq`
  endpoint (the hermes voice key) is DROPPED from the pool — its rate
  budget stays with voice STT.
- STRICT-SCHEMA-V1 (level-1 goes real): `EXTRACTION_JSON_SCHEMA` in
  contract.py — the volume packet as a deliberately boring strict
  schema (no oneOf, additionalProperties:false, all required). Client
  dispatches `response_format: json_schema` when the endpoint declares
  "schema"; the LOCAL gate still validates identically (validator is
  the contract; the schema only raises the provider floor). The former
  schema→json downgrade is removed — "schema" is declared per
  provider+model only after a live canary.
- DEDICATED-V1: `dedicated: true` on nvidia/nvidia2 — dedicated
  endpoints serve ONLY their pinned stages and are excluded from
  general extraction sharding (their RPM is reserved for enrichment).
  All-dedicated rosters fail open to the full roster, logged.
- limiter.yaml groq1..groq5 blocks: rpm 30 / tpm 120k / conc_cap 6
  each (unlinked accounts = independent AIMD buckets; combined
  extraction seed ≈150 RPM + primary). Temperature 0 was already the
  locked generation config; output stays bounded by output_budget_for.

## Proof (all live)
- Knob probe on qwen3.8-27b (account 1): baseline, reasoning none,
  json_object, AND strict json_schema all finish:stop with exact JSON.
- Probe: all 8 endpoints OK (5 groq 185–327 ms, 2 nvidia, primary).
- Sharding: 300 docs → groq1..5 + primary only (54/46/54/59/41/46),
  NVIDIA excluded; enrichment 100 docs → nvidia 51 / nvidia2 49.
- STRICT-SCHEMA extraction canary through groq1 with the REAL prompt:
  sanitize ok, no salvage, 5 typed entities + 4 relations, 449 output
  tokens, 1.26 s.
- test_extraction_pool.py 15/15; suite at the 8-failure baseline.

## Rejected claims
- "Reuse the hermes GROQ_API_KEY as lane 6" — rejected: that key funds
  voice STT; extraction on it would starve an unrelated system.
- "Schema dispatch everywhere now that one provider passed" — rejected:
  "schema" stays a per-provider+model declaration behind a live canary
  (the primary daemon still silently ignores strict schemas).

## Open contract gaps
- Five accounts on one machine's IP: Groq may rate-limit or flag by IP
  irrespective of per-account limits — watch the AIMD lanes on the
  first corpus-wide run; the 429 backoff handles it but throughput may
  be below the 150 RPM seed.
- contract_identity now shifts (roster + models changed): already-
  extracted docs keep receipts; new work hashes under the new pool.
