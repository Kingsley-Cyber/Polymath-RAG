---
change_id: U2-RELEASE-GATE
date: 2026-09-10
last_reviewed: 2026-09-10
status: evidence (frozen)
architecture_impact: none (the gate decision itself)
---

# U-2 release gate — evaluated against the owner's five criteria

Owner gate (2026-09-10). Evaluated on the SHIPPED code after D-3 and D-4 landed.

| criterion | verdict | evidence |
|---|---|---|
| Persistence chain | **PASS** | Proven four times through the REAL production path: 5→5→5, 9→9→9, 10→10→10, 11→11→11 (compiled = persisted = projected every time, byte-checked against new `map_id`s and Qdrant counts). |
| D-3 completion truth | **PASS** | `MappingOutcome.complete` is now `not unresolved_parent_ids` — current durable state. Proven on the exact defect case: the SAME document with the SAME 2 stale never-dispatched rows now completes with **zero dispatch**, ticket `done`, watched 60 s with no re-arm and no re-dispatch. Regression tests pin both directions (6 cases). |
| D-4 durable accounting | **PASS** | `llm_controller_state` now carries pMAP rows — `llm_cloud[map_groq3]` and `llm_cloud[map_groq5]`, each `day` + `day_count` + `last_dispatch_at`. The first such rows that have ever existed. Restart continuity proven with zero spend: a fresh `LimiterRegistry` restores the count instead of the yaml seed (5 tests). |
| Bounded post-fix canary | **PASS** | Canary 5 (`doc_b239c387…`, 11 parents) on the shipped code: **`reconciles: true`, all six checks PASS** including `limiter_matches_dispatch`. Ticket `done` at attempt 0, no error note. |
| No unexplained accounting | **PASS** | Within every canary: requested = eligible, dispatch fully classified, returned = persisted = projected, unresolved 0, limiter delta = dispatch count. No unexplained parents, no unexplained requests, no silent loss. |

```
U-2 FORENSIC HOLD: CLEARED
```

Evidence: this folder (`before.json`, `canary-result.json`, `postfix/`, `postfix2/`, `final/`),
`../u2-forensic-closure-audit-2026-09-10/`, `../u2-groq-map-forensic-probe-2026-09-10/`.
Registers 11.192 · 11.196 · 11.200 · 11.202.

## What is CLEARED, stated precisely

The chain `provider response → MappingOutcome → compiler → durable pMAP → projection` reconciles end to end,
and the two defects that blocked it (D-3 completion truth, D-4 durable accounting) are fixed, tested and
proven live. Total forensic spend across the whole U-2 effort: **17 probe requests + 4 canary requests**.

## What is NOT fixed — carry these into any resumption

- **D-1 (11.196) — OPEN.** 3 historical batches carry a `raw_response_hash` with `valid_count=0` yet are
  terminally booked `LIMITER_REFUSED`: real provider consumption recorded as a LOCAL refusal. Bounded and
  explained, but the CLASSIFIER is unchanged, so a dispatched-but-empty batch during a backfill would be
  misbooked the same way and corrupt the control plane's refused-vs-429 distinction — exactly the signal an
  operator would watch during a long run. **Recommended before a FULL cinema backfill** (a one-line change:
  classify terminal state by whether HTTP was dispatched).
- **D-2 (11.196) — OPEN.** 6 batches frozen on leases expired 2026-09-09 04:54Z, holding **90 parents**. A
  resumption will not pick them up until they are reaped **by pinned batch id** (never a status sweep).
- **Real-parent batch reliability above 15 is still unmeasured.** `MAP_RELIABILITY_CAP` stays 15. The three
  batch-60 failures in the historical record (D-1) were all `expected_count=60` on real parents, which is
  evidence AGAINST raising it without a benchmark.

## Documented stop conditions for bounded cinema resumption

A resumption run must halt and report on ANY of:

1. any batch ending `status='partial'` with `raw_response_hash IS NOT NULL` and `valid_count = 0`
   (a dispatched-but-empty completion — the D-1 signature);
2. `http_429` > 0 on two distinct lanes within one hour (provider pushback, not local shaping);
3. `limiter_refused` rising while `http_dispatches` stays flat (a refusal cascade re-forming — the 11.185
   failure mode);
4. any document reporting `DOC_PARENT_MAP_INCOMPLETE` with `unresolved = 0` (D-3 regression);
5. `maps_persisted` ≠ `maps_projected` for any document (projection drift);
6. any lane's durable `day_count` exceeding 80% of its configured RPD;
7. any ticket reaching `attempt >= 3`.

Resumption remains scoped by pinned run/document ids. `POLYMATH_DOC_PARENT_MAP_CORPUS` stays `rag-canary`;
cinema work is minted explicitly, never by broadening auto-mint.
