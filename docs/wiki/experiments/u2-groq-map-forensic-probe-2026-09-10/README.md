---
change_id: GROQ-MAP-FORENSIC-PROBE-V1
date: 2026-09-10
last_reviewed: 2026-09-10
status: evidence (frozen)
architecture_impact: none (read-only forensic observation; synthetic parents, cinema-free, no corpus/DB write)
---

# U-2 — Groq Parent-MAP bounded forensic probe (result)

Owner-authorized bounded probe (2026-09-10) executing the LIVE portion of the acceptance gate in
`docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md`, under the existing forensic limits. Instrument:
`scripts/groq_map_forensic_probe.py` — SYNTHETIC parents → `build_parent_skeletons` → `build_map_prompt` →
production `LLMExtractionClient.complete_one` (`max_attempts=1`) → `compile_maps`, reading the lane limiter's
`state()` before/after each call. **Cinema untouched, no corpus/DB write, no JSON mode, `max_attempts=1`.**
Total spend: **17 `groq/compound-mini` requests** (preflight 1 + benchmark 10 + per-account 6), ~3 RPD/account.
Machine-readable: `preflight.json`, `batch-benchmark.json`, `per-account-rpd.json`.

## Headline findings

1. **Provider RPD is OBSERVABLE and NOT exhausted.** Groq `x-ratelimit-remaining-requests` was captured on every
   success. All six accounts (`map_groq1..6`) reported **~246–248 remaining of ~250** — the RPD limit is ~250/account
   (the config "RPD 250" is now MEASURED, not assumed), and **no account is near exhaustion**. This DIRECTLY
   CONTRADICTS the disputed "six Groq accounts exhausted daily RPD" inference (register 11.178).
2. **The conservation chain reconciles.** Local `day_count` incremented by **exactly 1 per HTTP dispatch**;
   `dispatched_http == requests` (all admitted, 0 `LIMITER_REFUSED`); `provider_rpd_remaining` decremented in step
   with dispatches. Local RPD ↔ provider RPD reconcile.
3. **Batch reliability 15/20/30/40/60 = yield 1.0 (complete maps) on synthetic parents.** 60/60 aliases compiled
   twice. This shows the token envelope is NOT the ceiling and batch 60 is structurally feasible — **but on
   SYNTHETIC (short, uniform) parents; this is a best-case upper bound.** The 11.178 partial-map finding was on
   REAL large-doc parents, so raising `MAP_RELIABILITY_CAP` above 15 requires a REAL-parent (non-cinema) benchmark
   first. The conservative proven cap (15) stands until then.
4. **No retry loop / no quota-burning** (`max_attempts=1`; 1 request → 15–60 valid maps).

Combined with the 11.185 offline census (terminal `LIMITER_REFUSED` on 926 batches = **zero HTTP**), the historical
`+0 parents / 0 errored_docs` pass was a **LOCAL limiter refusal cascade, not provider RPD exhaustion**.

## Acceptance gate (GROQ-FORENSIC-AUDIT.md) — status after this probe

```
[x] provider RPD truth OBSERVABLE (headers on success)         — ~247/250 per account
[x] local RPD (day_count) RECONCILES with provider             — +1 per dispatch, RPD tracks
[x] failure/refusal accounting correct                          — 11.185 offline + 0 refusals here
[x] LIMITER_REFUSED == ZERO provider consumption                — 11.185 census (926, 0 HTTP)
[x] HTTP dispatch separated from selections                     — day_count only on dispatch
[x] retry waste quantified                                      — max_attempts=1 => 1 req/map
[x] request -> valid-map efficiency measured                    — 1 req -> 15..60 maps (synthetic)
[~] MAP batch sizes 15/20/30/40/60 benchmarked                  — 1.0 on SYNTHETIC; real-parent bench pending
[x] no systematic quota-burning retry loop                      — confirmed
[x] plaintext DSL + compiler (no JSON mode)                     — unchanged
```

Only remaining item: a REAL-parent (non-cinema, e.g. a fresh throwaway book) batch benchmark to confirm 20–60
reliability before raising the cap. The core forensic question (exhaustion? accounting?) is ANSWERED.

## Cinema-finish estimate (for OWNER REVIEW — resumption is owner-gated)

Cinema unresolved parents ≈ 11,993 − ~1,254 mapped ≈ **~10,739**. At the proven cap of 15 valid-maps/request:
≈ **716 requests**; at batch 60 (if real-parent reliability confirms): ≈ **179 requests**. Capacity = 6 accounts ×
~250 RPD/day = **~1,500 requests/day**, so cinema finishes in **well under one day** even at batch 15. The forensic
hold's premise (capacity exhaustion) does not hold.

**This does NOT authorize resuming the cinema backfill.** Per the audit: probe → owner review → (bounded cinema
canary) → owner review → full backfill. Those remain owner-gated. Do NOT resume on a quota reset.
