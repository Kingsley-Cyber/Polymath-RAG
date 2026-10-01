# unit: shared/polymath_shared/llm_extraction/limiter.py
anchor: shared/polymath_shared/llm_extraction/limiter.py:1-1158

## purpose
Adaptive per-(provider, api_key) rate limiting for the LLM extraction fleet — limiter.py:1-4 [DERIVED].
Local providers (MLX/Ollama) are limited by CONCURRENCY (dynamic semaphore, seeded low); cloud providers by RATE (RPM+TPM token buckets with a concurrency safety cap) — limiter.py:6-9 [DERIVED].
Both kinds adapt AIMD-style (+1 per K clean successes, ×0.5 on 429/503/timeout), honor Retry-After, sync from rate-limit headers, and guard each lane with a circuit breaker plus a cross-process family damp gate — limiter.py:11-18, 417-422 [DERIVED].
Threading-only, no third-party dependencies; static config values are seeds and ceilings, `adaptive` moves the effective limit inside [min, max] at runtime — limiter.py:24-27 [DERIVED].

## public surface
File-level importers (FACTS.importers): `shared/polymath_shared/document_profile/groq_routing.py`, `shared/polymath_shared/llm_extraction/client.py`, `workers/workers/llm_provider.py`. Per-symbol callers not distinguishable from FACTS.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ControllerStore | Protocol | load(key: str) -> dict \| None; save(key: str, state: dict) -> None | limiter.py:55-60 | implemented by state_store.PostgresControllerStore (FACTS.imports) |
| ProviderLimit | dataclass | kind/init=2/min=1/max=6/rpm/tpm/conc_cap/adaptive=True/use_headers=False/rpd/family/tpd/otpm; from_config(base, cfg: dict \| None) -> ProviderLimit | limiter.py:63-97 | — |
| parse_retry_after | function | (value) -> float \| None | limiter.py:110-119 | — |
| parse_reset_seconds | function | (value) -> float \| None | limiter.py:156-169 | — |
| LimiterDecision | dataclass (frozen) | admitted / reason / retry_after / reserved_tokens=0.0 / reserved_output=0.0 / tpd_slot=None | limiter.py:139-149 | — |
| AdaptiveLimiter | class | (name: str, spec: ProviderLimit); admit/acquire/settle/restore/state/capacity_snapshot/spec_fingerprint/record_success/record_failure/release/flush_rpd/park_provider_day | limiter.py:484-973 | client.py, llm_provider.py (file-level) |
| AdaptiveLimiter.capacity_snapshot | method | (*, now: float \| None = None) -> dict | limiter.py:560-588 | groq_routing.py (docstring names groq_router.choose) [INFERRED] |
| AdaptiveBudget | class | AIMD over a scalar budget; effective/ceiling/record_success/record_oom/state/restore | limiter.py:976-1056 | — |
| LimiterRegistry | class | lane/get_lane/budget/attach_store/ensure_store/store_attached | limiter.py:1059-1154 | — |
| FAMILY_GATE | module singleton | _FamilyGate() | limiter.py:471 | — |

## contracts

**ProviderLimit.from_config(base, cfg)** — limiter.py:89-97 [DERIVED]
- in: code-level seed `base` + config mapping `cfg` (may be None).
- post: unknown keys ignored — "a typo in limiter.yaml must not crash the first extraction call" (limiter.py:91-93).

**parse_retry_after(value)** — limiter.py:110-119 [DERIVED]
- out: `max(0.0, float(value))`; None when absent, unparseable, or HTTP-date form (not honored by the fleet).

**parse_reset_seconds(value)** — limiter.py:156-169 [DERIVED]
- out: plain seconds ("60", "60.5") or duration form ("2m59.56s", "1h2m3s" via `_DURATION_RE`, limiter.py:152-153); None when unparseable.

**AdaptiveLimiter.acquire(est_tokens=0.0, block=True) -> bool** — limiter.py:673-677 [DERIVED]
- post: True iff admitted; a False return never leaves anything held (slot, tokens, probe).

**AdaptiveLimiter.admit(est_tokens=0.0, block=True, *, reserved_output=0.0) -> LimiterDecision** — limiter.py:679-771 [DERIVED]
- gate order (actual code): retry-after (687) → family (691) → breaker (694) → concurrency (703) → RPM (711) → TPM (713) → OTPM (718) → provider-RPD (729) → TPD rolling window (737) → local RPD (745).
- post: `admitted=False` ALWAYS means zero HTTP dispatch and zero provider consumption — limiter.py:141-142, 683-684; every refusal path releases what it briefly held (limiter.py:716, 722-724, 734, 758-761, 762-765).
- post: `admitted=True` returns `reserved_tokens=max(est_tokens, 0.0)`, `reserved_output=max(reserved_output, 0.0)`, `tpd_slot` set when a TPD budget exists — limiter.py:770-771, 742.
- provider-declared daily exhaustion refuses BEFORE the local cap is charged (limiter.py:729-734).

**AdaptiveLimiter.settle(decision, tokens_in=None, tokens_out=None, *, failed=False) -> None** — limiter.py:773-792 [DERIVED]
- pre: no-op when `decision.admitted` is False (limiter.py:781-782).
- post: TPM refund of unused reservation / debit of deficit (limiter.py:783-787); OTPM refunds surplus output (limiter.py:788-790); TPD entry trued up / removed on failure (limiter.py:791-792).
- post: never raises (limiter.py:777).

**AdaptiveLimiter.restore(state) -> bool** — limiter.py:599-638 [DERIVED]
- out: False when state empty or missing "effective" (limiter.py:606-607).
- post: effective clamped into [floor, ceil], streak reset to 0 (limiter.py:610-611); day_count restored only when persisted day == today (limiter.py:614-617); adopted ceilings + tpd_hours restored only when `spec_fingerprint` matches (limiter.py:628-636).

**AdaptiveLimiter.capacity_snapshot(\*, now=None) -> dict** — limiter.py:560-588 [DERIVED]
- read-only REPORT for the selection layer; limiter stays the enforcement authority (limiter.py:561-564). Keys: remaining_rpd, rolling_rpm, tpm_used, in_flight, locked_until, breaker_open, day_count, rpd_budget, provider_rpd_limit, provider_rpd_remaining (limiter.py:576-588).

**AdaptiveLimiter.state() -> dict** — limiter.py:536-558 [DERIVED]
- durable row: effective, streak, floor, ceiling, increases, decreases, day, day_count, last_dispatch_at, adopted_rpm, adopted_tpm, spec_fingerprint, tpd_hours, provider_rpd_limit, provider_rpd_remaining; provider values are re-observed live, never restored (limiter.py:555-556).

## effect surface
- Postgres: no direct tables (`tables_read: []`, `tables_written: []`, FACTS). Durability delegated to the ControllerStore protocol (limiter.py:55-60) via state_store.PostgresControllerStore (FACTS.imports).
- Store keys written/read: `f"family:{family}"` — save at limiter.py:443-445, load at limiter.py:459; lane rows via the `_on_change` callback (limiter.py:649-651) and RPD persist (`_persist_rpd_if_due`, limiter.py:769).
- env: `POLYMATH_PG_DSN` default `''` at limiter.py:1104 (FACTS.env).
- Network: none in this unit — imports are stdlib + `polymath_shared.llm_extraction.state_store` only (limiter.py:31-40; FACTS.imports).
- Files / Qdrant / subprocesses: none visible.

## invariants
INVARIANT: breaker opens iff len(outcomes) >= 10 and sum(outcomes)/len(outcomes) < 0.5 — limiter.py:47-48, 399-401 [DERIVED]
  fails-if: down provider gets hammered (never opens) or healthy lane parked (opens early)
INVARIANT: honored Retry-After sleep = min(delay, 60.0) s (RETRY_AFTER_MAX_S) — limiter.py:50, 662 [DERIVED]
  fails-if: a bogus header stalls the lane indefinitely
INVARIANT: blocking breaker wait <= 75.0 s (BREAKER_WAIT_MAX_S) — limiter.py:51, 666-671 [DERIVED]
  fails-if: blocking caller wedges on a permanently open breaker
INVARIANT: family gate opens at >= 8 failures within 30.0 s, closed 45.0 s, cross-process re-read every 10.0 s — limiter.py:410-413, 437-439, 454-455 [DERIVED]
  fails-if: correlated 429 storm across one family's keys keeps dispatching
INVARIANT: bucket tokens ∈ [-capacity, capacity]; oversized acquire clamps n = min(n, capacity) — limiter.py:253-254, 261, 284 [DERIVED]
  fails-if: oversized request blocks forever, or deficit drives tokens unbounded negative
INVARIANT: bucket refill rate = capacity / 60.0 tokens per second — limiter.py:247 [DERIVED]
  fails-if: RPM/TPM throttle diverges from the configured per-minute budget
INVARIANT: rolling TPD window WINDOW_S = 86400.0; entries pruned when ts <= now - 86400.0; wall-clock timestamps so the window survives restart — limiter.py:180-183, 189-191 [DERIVED]
  fails-if: TPD refusals computed from stale usage after restart
INVARIANT: concurrency seed = max(spec.min, min(seed, ceil)), ceil = max(conc_cap or spec.max, spec.min) for kind "rate"; AIMD seeds LOW and climbs — limiter.py:491-497 [DERIVED]
  fails-if: lane starts above provider ceiling or below floor
INVARIANT: exactly one half-open probe at a time (probe_in_flight) — limiter.py:368-373 [DERIVED]
  fails-if: probe thundering herd when breaker half-opens
INVARIANT: AIMD move is +1 per 4 clean successes (SUCCESS_STREAK_FOR_INCREASE=4), ×0.5 on throttle/timeout (DECREASE_FACTOR=0.5) — limiter.py:11-12, 45-46 [DERIVED]
  fails-if: effective limit diverges from provider tolerance
INVARIANT: ceiling adoption is grow-only (adopt_capacity), clamped by caller to seed × CEILING_ADOPT_MAX_MULTIPLE = 4 — limiter.py:286-294, 414 [DERIVED]
  fails-if: a bogus large header lifts the ceiling unbounded
INVARIANT: day_count restored only when persisted day == today; adopted ceilings/tpd_hours restored only when spec_fingerprint matches — limiter.py:614-617, 628-636 [DERIVED]
  fails-if: ceilings from a retired config bind live lanes (measured 2026-09-24, comment limiter.py:624-627)
INVARIANT: no lock held while sleeping — bucket sleep outside its lock (limiter.py:271-273), on_change callback outside the lane lock (limiter.py:649-651), contract at limiter.py:20-22 [DERIVED]
  fails-if: header sync and other acquirers convoy behind a sleeper

## determinism & idempotency
determinism: NONDETERMINISTIC (clocks: time.monotonic limiter.py:107; time.time limiter.py:195, 201, 218, 228, 445, 462; concurrency: threading locks/conditions throughout, e.g. limiter.py:249, 306, 361; db: controller-store writes limiter.py:443-445, 649-651; env: POLYMATH_PG_DSN limiter.py:1104) [DERIVED]
idempotency: UNSAFE (admission is consumption: a semaphore slot until release, bucket tokens until settle/refund, `day_count += 1` at limiter.py:753; the reclaim path is settle(decision, failed=True) limiter.py:773-792 — refused admits leak nothing by contract limiter.py:762-765) [DERIVED]

## failure behaviour
- Exception → `return None` in `_registry_store` (store access before attach) — limiter.py:479-481; family gate then fails open [DERIVED].
- Exception → `pass` on `store.save(f"family:{family}")` in note_failure — limiter.py:446-447; the cross-process family signal is lost, local gate still works [DERIVED].
- Exception → `pass` on `store.load` in allowed — limiter.py:466-467; gate fails open ("fail-open on any store trouble", limiter.py:423-424) [DERIVED].
- Exception → log at limiter.py:822 (FACTS.fallbacks; RPD-persist region — `_persist_rpd_if_due` called at limiter.py:769); day counter stays memory-only until next persist [DERIVED].
- Exception → log at limiter.py:1112 (FACTS.fallbacks; inside LimiterRegistry limiter.py:1059-1154, the store-setup region around POLYMATH_PG_DSN limiter.py:1104) [DERIVED].
- settle() never raises — limiter.py:777 [DERIVED].
- No custom exceptions; parse helpers return None on bad input (limiter.py:117-119, 163-169) [DERIVED].

## dumb-code flags
- Day-string literal `time.strftime("%Y-%m-%d", time.gmtime())` duplicated at 4 sites: limiter.py:515, 567, 614, 747 [DERIVED].
- Magic numbers: `1e-6` timestamp nudge (limiter.py:204); `0.5` s condition wait (limiter.py:311); `1.0` s bucket sleep cap (limiter.py:273); `0.05` and `/10` breaker poll (limiter.py:668); `1_000_000_000` placeholder remaining_rpd (limiter.py:569); `3600` hour-bucket size (limiter.py:223) [DERIVED].
- capacity_snapshot reads `self._rpm.tokens` / `self._tpm.tokens` without refill or the bucket lock (limiter.py:572-573) — snapshot can understate headroom until the next acquire [INFERRED: no `_refill_locked` call on that path].
- BREAKER_ERROR_RATE = 0.5 is named "error rate" but the test compares the SUCCESS fraction (`sum/len < error_rate`) — limiter.py:47, 400-401 [DERIVED].
- Provider RPD fields are persisted in state() but explicitly never restored (limiter.py:555-556, 540-541) — write-only fields by design [DERIVED].

## refactor notes
- REFUSE_* string taxonomy (limiter.py:127-136) is the cross-unit refusal contract; importers groq_routing.py / client.py / llm_provider.py (FACTS.importers) — renaming a value breaks their refusal handling.
- LimiterDecision + settle() are a paired reservation/true-up protocol (limiter.py:143-149, 773-792) — changing reserved_tokens/reserved_output/tpd_slot semantics requires updating every settle caller.
- state() dict keys (limiter.py:538-558) are the durable row schema consumed by restore() (limiter.py:599-638) — key changes orphan existing controller-store rows.
- spec_fingerprint basis list (limiter.py:595) must track ProviderLimit fields exactly, else adopted ceilings silently stop restoring (limiter.py:628).
- Store key namespace `family:{family}` (limiter.py:443, 459) is shared cross-process — renaming it orphans open-gate rows mid-incident.
- admit() gate order is load-bearing: provider-RPD must refuse BEFORE local RPD charges day_count (limiter.py:729-734 vs 745-756); reordering double-charges or dispatches into a spent day.
- POLYMATH_PG_DSN default `''` at limiter.py:1104 is consumed by LimiterRegistry store setup — moving it changes fail-open behavior.

## VERIFY
```verify
grep -Fq 'SUCCESS_STREAK_FOR_INCREASE = 4' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'DECREASE_FACTOR = 0.5' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'RETRY_AFTER_MAX_S = 60.0' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'FAMILY_FAILURE_THRESHOLD = 8' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'admitted=False' shared/polymath_shared/llm_extraction/limiter.py
! grep -Fq 'import requests' shared/polymath_shared/llm_extraction/limiter.py
test "$(grep -c -F 'time.strftime' shared/polymath_shared/llm_extraction/limiter.py)" -ge 4
```
