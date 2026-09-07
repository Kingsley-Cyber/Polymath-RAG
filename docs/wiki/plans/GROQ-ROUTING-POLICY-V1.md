---
title: "GROQ ROUTING POLICY V1 — account-level capacity coordination for the ingestion profile/map pool"
change_id: GROQ-ROUTING-POLICY-V1
owner: governance (owner corrective goal 2026-09-07)
date: 2026-09-07
last_reviewed: 2026-09-07
status: accepted (policy of record; the scheduler build is slice S7)
supersedes: "the per-run doc-hash ring rotation of the profile pool for Groq ingestion lanes"
---

# GROQ ROUTING POLICY V1

Production-safety contract for how the ingestion document-profile / parent-map
pool spends the six dedicated Groq accounts. This is the **policy of record**;
the code that implements it is plan slice **S7** (see
`DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` §14 / §35). It EXTENDS the existing limiter
and pool — it does not add a second scheduler authority (AGENTS.md §5.2).

## 1. Account is the capacity domain, not the model

There are **six Groq accounts** (keys `GROQ_API_KEY_1..6`). Each account exposes
**two models**:

```text
groq/compound        strongest semantic work
groq/compound-mini   high-throughput / lower average latency
```

Nominal Free limits are published **per account** (shared by both models):

```text
30 RPM   ·   250 RPD   ·   70K TPM
```

**Invariant (the correction this policy makes):** the two models MUST NOT be
treated as independent quota pools inside one account. Every request on
`compound` and every request on `compound-mini` for account *N* draws down the
**same** account-*N* RPD / TPM / rolling-RPM budget. Six accounts × two models =
twelve *lanes*, but only **six** capacity domains.

Mechanism: reuse the limiter's `family` concept — set `family: groq_acct_N` on
BOTH lanes of account *N* so the existing `_FamilyGate` + a per-account budget
coordinate them. Provider headline numbers are ceilings, never safe scheduler
settings (§14.2); the day (RPD) and TPM budgets are the hard walls.

## 2. Model is chosen by work class

```text
GLOBAL_DOCUMENT_PROFILE   -> groq/compound        (one strong call per document)
PARENT_ROUTING_MAP        -> groq/compound-mini   (packed overflow mapping)
COMBINED_ONE_CALL         -> groq/compound first; Mini only if global quality holds
```

`compound` is agentic (measured: router + answer sub-calls; billed completion
materially exceeds visible output — use the S3 `DensityModel`'s BILLED density for
capacity, never the visible tokens). `compound-mini`'s average latency is
materially lower — it is the throughput model for the map overflow.

## 3. Per-model measured EWMAs, per-account budget

Track, and persist durably (see §5), so restart preserves the day:

```text
per ACCOUNT (shared by both models):
    remaining RPD (resets on the provider's UTC day)
    rolling RPM (last 60 s)
    estimated TPM (last 60 s, from measured billed+input density)
    retry-after / rate-limit-header lock (locked_until)
    429 / 5xx history (breaker)

per (account, MODEL) lane:
    latency EWMA
    billed-tokens/request EWMA (the S3 DensityModel)
    error-rate EWMA
    in-flight count
```

## 4. Dynamic selection — no round-robin, no key burning

Replace the current `pool.select_endpoint_for_stage` doc-hash ring (`_ring_pick`)
for these lanes with capacity-aware selection. Given a work class, the scheduler
chooses `(account, model)` — or **waits** — from:

```text
remaining RPD           (skip an account near its daily wall)
remaining TPM headroom  (would this request's estimated tokens fit?)
rolling RPM             (under the safe per-account RPM ceiling)
retry-after / locked_until (never dispatch into a live lock)
measured latency EWMA   (prefer the faster lane for the work class)
measured billed tokens/request (capacity feasibility, §14.4 guard)
429 / 5xx history       (breaker-open accounts are skipped)
current in-flight work  (spread load; never oversubscribe one account)
```

Rules:

```text
- NO fixed round-robin: pick by remaining capacity, deterministic tie-break by name.
- NO key burning: a 429 / Retry-After locks the ACCOUNT (both models), not just the lane.
- The 4-RPM ceiling is a TARGET, honored only under the §14.4 token guard
  (token_feasible_rpm, corrected 2026-09-07 to drop below 4 above 15k tokens/request).
- Compound keeps the repository's existing conservative pacing until a fresh clean
  canary promotes it; Mini canaries 2 -> 3 -> 4 effective RPM/account under AIMD.
- Fallbacks last: Gemini (fallback 1) then OpenRouter (fallback 2), as today.
```

## 5. Persist shared rate state

Concurrent workers MUST NOT each assume full account capacity. Persist per-account
RPD / rolling-RPM / TPM-estimate / locked_until through the limiter's existing
durable `ControllerStore` (Postgres-backed), the single repository-approved budget
authority (§35). In-process locks alone are insufficient — six profile slots run
concurrently. Restart preserves the day count.

## 6. Tools disabled during ingestion (frozen)

```text
tools = disabled   for every ingestion request (profile + map)
```

No web search / visit / code execution / Wolfram / external retrieval. The model
analyzes supplied corpus material only; SOURCE_DATA is untrusted content, never
obeyed (the P0031 injection regression, §30). This is non-negotiable for ingestion.

## 7. Rollout — canary before scale (gates the reindex)

The scheduler is proven on a small controlled document-profile / MAP reindex
canary BEFORE any concurrency expansion (plan §26 / the owner's Part 4). The
canary must prove:

```text
correct model selection per work class
no quota oversubscription across concurrent workers
partial MAP recovery works (only unresolved aliases retried)
semantic artifacts persist independently of Qdrant projection
restart / retry does not duplicate completed API work
```

Only then expand backfill / reindex concurrency.

## 8. Build map (slice S7 — EXTEND, do not replace)

```text
config/cloud_providers.json   add profile_groqN_mini lanes (groq/compound-mini)
                              beside profile_groqN (compound); family: groq_acct_N
config/extraction_models/limiter.yaml
                              per-account family budgets (rpd 250 / tpm 70000 / rpm 30)
shared/.../llm_extraction/limiter.py
                              extend _FamilyGate -> per-account budget; retry-after
                              locks the account; ControllerStore persists RPD/RPM
shared/.../llm_extraction/pool.py
                              capacity-aware (account, model) selection for the
                              profile/map work classes (replaces _ring_pick there)
shared/.../document_profile/  the deterministic decision core (pure, tested) that
                              pool.py calls; the S3 DensityModel feeds billed density
```

Authorities this policy binds: `PLAN-AUTHORITY-REGISTER` (row 11.134), the
DOCUMENT-SEMANTIC-INDEX plan §14 / §35, and the corrected S3 `token_feasible_rpm`
(11.133).
