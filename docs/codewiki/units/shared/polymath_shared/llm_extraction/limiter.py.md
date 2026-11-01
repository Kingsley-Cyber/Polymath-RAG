# unit: shared/polymath_shared/llm_extraction/limiter.py
anchor: shared/polymath_shared/llm_extraction/limiter.py:1-1168

## purpose
Adaptive per-(provider, api_key) admission control for the LLM extraction fleet: local providers (MLX/Ollama) get an AIMD dynamic semaphore (GPU/VRAM bottleneck), cloud providers get RPM/TPM token buckets plus daily budgets (RPD, rolling TPD) — limiter.py:1-17 [DERIVED]. Each lane also honors Retry-After, runs a closed→open→half-open circuit breaker, and shares a per-family damp gate persisted through the controller store — limiter.py:14-18, 425-430 [DERIVED]. Threading-only, no third-party dependencies; static config values are seeds and ceilings, `adaptive` moves the effective limit at runtime — limiter.py:24-27 [DERIVED].

## public surface
Module-level importers (FACTS.importers): `shared/polymath_shared/document_profile/groq_routing.py`, `shared/polymath_shared/llm_extraction/client.py`, `workers/workers/llm_provider.py`. Per-symbol users unknown beyond that.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ControllerStore | Protocol | load(key: str) -> dict \| None; save(key: str, state: dict) -> None | limiter.py:55-60 | state_store.PostgresControllerStore implements it |
| ProviderLimit | dataclass | kind, init=2, min=1, max=6, rpm/tpm/conc_cap=None, adaptive=True, use_headers=False, rpd/family/tpd/otpm=None; from_config(base, cfg) -> ProviderLimit | limiter.py:63-97 | — |
| parse_retry_after | function | (value) -> float \| None | limiter.py:110-119 | — |
| parse_reset_seconds | function | (value) -> float \| None | limiter.py:156-169 | — |
| LimiterDecision | frozen dataclass | admitted, reason=None, retry_after=None, reserved_tokens=0.0, reserved_output=0.0, tpd_slot=None | limiter.py:139-149 | — |
| AdaptiveLimiter | class | (name: str, spec: ProviderLimit); acquire, admit, settle, state, capacity_snapshot, restore, spec_fingerprint, release, record_success, record_failure, flush_rpd, park_provider_day, _sync_headers, effective, breaker_open, not_before, … | limiter.py:492-983 | module importers above |
| AdaptiveBudget | class | AIMD scalar budget; effective, ceiling, record_success, record_oom, state, restore | limiter.py:986-1066 | — |
| LimiterRegistry | class | lane, get_lane, budget, attach_store, ensure_store; (provider, api_key) -> AdaptiveLimiter | limiter.py:1069-1164 | module importers above |
| FAMILY_GATE | module singleton | _FamilyGate(); note_failure(family, store), allowed(family, store) | limiter.py:479, 425-476 | — |

## contracts

**AdaptiveLimiter.admit** — limiter.py:687-781
- in: `est_tokens: float = 0.0, block: bool = True, *, reserved_output: float = 0.0` — limiter.py:687-688
- gate order: retry-after (695) → family (699-701) → breaker (702-712) → concurrency (713-717) → RPM (721) → TPM (723-727) → OTPM (728-735) → PROVIDER_RPD (739-744) → TPD (747-754) → local RPD (755-771) — limiter.py:695-771
- out: `LimiterDecision`; `admitted=False` ALWAYS means zero HTTP dispatch and zero provider consumption — limiter.py:141-142, 690-691
- post: every rate refusal refunds what it took — `self._rpm.refund(1.0)` (726, 733), `self._tpm.refund(est_tokens)` (734), `_refund_rate(...)` (744, 754, 768), `self._tpd.remove(tpd_slot)` (769-770), `self._sem.release()` + `self._breaker.release_probe()` (772-774)
- post: on admitted RPD admission, `_day_count += 1`, `_last_dispatch_at = _utc_iso()`, `_rpd_dirty = True` — limiter.py:763-766

**AdaptiveLimiter.acquire** — limiter.py:681-685
- in: `est_tokens: float = 0.0, block: bool = True` → bool; thin wrapper over `admit(...).admitted`; False return never leaves anything held.

**AdaptiveLimiter.settle** — limiter.py:783-791 (body beyond excerpt)
- in: `(decision, tokens_in=None, tokens_out=None, *, failed=False)`; returns immediately when `not decision.admitted` — limiter.py:788-789
- post: "Never raises"; unused reserved tokens go back to TPM/OTPM, deficit charged, rolling daily window trued up, failed call removes its daily reservation — limiter.py:786-788

**AdaptiveLimiter.state / restore** — limiter.py:544-566, 607-646
- state() returns keys `effective, streak, floor, ceiling, increases, decreases, day, day_count, last_dispatch_at, adopted_rpm, adopted_tpm, spec_fingerprint, tpd_hours, provider_rpd_limit, provider_rpd_remaining` — limiter.py:546-566
- restore clamps `effective` into `[floor, ceil]`; restores `day_count` only when persisted `day == today`; restores `adopted_rpm/adopted_tpm` and `tpd_hours` only when `spec_fingerprint` matches — limiter.py:617-618, 622-625, 636-644

**AdaptiveLimiter.capacity_snapshot** — limiter.py:568-596
- read-only report for the selection layer (`groq_router.choose`); the limiter remains the enforcement authority — limiter.py:569-572

**ProviderLimit.from_config** — limiter.py:89-97
- unknown config keys are ignored — "a typo in limiter.yaml must not crash the first extraction call" — limiter.py:91-93

**parse_retry_after** — limiter.py:110-119: None when absent or HTTP-date form; else `max(0.0, seconds)`.
**parse_reset_seconds** — limiter.py:156-169: plain seconds or Groq duration (`"2m59.56s"`, `"1h2m3s"`); None when unparseable.

## effect surface
- Postgres tables: none read/written directly (FACTS.tables_read/tables_written empty); durable state flows through the `ControllerStore` Protocol — limiter.py:55-60 — and `state_store.PostgresControllerStore` is imported (FACTS.imports).
- Env: `POLYMATH_PG_DSN` (default `''`), read at limiter.py:1114 (FACTS.env).
- Store row keys written/read by `_FamilyGate`: `family:{family}` — limiter.py:451, 467.
- Network: none in this unit; HTTP dispatch lives in callers, `admitted=False` guarantees no dispatch — limiter.py:141-142.
- Concurrency: `threading.Lock`/`Condition` at limiter.py:187, 249, 306, 361, 433, 517.

## invariants
INVARIANT: `_TokenBucket.rate == capacity / 60.0` (refill per second for a per-minute window) — limiter.py:247 [DERIVED]
  fails-if: RPM/TPM gates refill at the wrong rate and over-/under-throttle.
INVARIANT: bucket request `n = min(float(n), self.capacity)` on every acquire — limiter.py:261 [DERIVED]
  fails-if: a blocking acquire for an oversized request waits forever.
INVARIANT: `tokens >= -capacity` after `debit` — limiter.py:284 [DERIVED]
  fails-if: unbounded deficit never refills and the lane stalls.
INVARIANT: breaker opens only when `len(outcomes) >= 10` and success rate `< 0.5` — limiter.py:407-408 [DERIVED]
  fails-if: opens early/late on noise, hammering or idling a down provider.
INVARIANT: honored Retry-After sleep `<= RETRY_AFTER_MAX_S` (60.0) — limiter.py:50, 670 [DERIVED]
  fails-if: a hostile header parks the lane indefinitely.
INVARIANT: bucket acquire sleeps `<= 1.0` s per iteration and outside the lock — limiter.py:273-277 [DERIVED]
  fails-if: header sync and other acquirers convoy behind a sleeper.
INVARIANT: restore clamps `effective` into `[floor, ceil]` — limiter.py:617-618 [DERIVED]
  fails-if: a stale persisted value escapes the configured range.
INVARIANT: `adopted_rpm/adopted_tpm` restored only when persisted `spec_fingerprint` equals the current one — limiter.py:636-644 [DERIVED]
  fails-if: measured case at limiter.py:632-635 — `adopted_tpm: 70000` from retired models restored onto lanes now configured at 8,000 TPM.
INVARIANT: family gate opens at `>= 8` failures within `30.0` s, cooldown `45.0` s — limiter.py:418-420, 445-447 [DERIVED]
  fails-if: correlated 429 storm across keys of one family goes undamped.
INVARIANT: `_RollingTokens.WINDOW_S == 86400.0`; entries with `ts <= now - 86400.0` pruned — limiter.py:183, 189-192 [DERIVED]
  fails-if: TPD budget counts expired usage or lets stale usage expire early.
INVARIANT: `admitted=False` ⇒ no HTTP request dispatched and no provider quota consumed — limiter.py:141-142, 690-691 [DERIVED]
  fails-if: callers double-charge or dispatch on refusal.
INVARIANT: `capacity_snapshot.remaining_rpd == 1_000_000_000` when `spec.rpd` is None — limiter.py:577 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` limiter.py:107; wall clock `time.time` limiter.py:195, 201, 218, 228, 453, 470; threading locks/conditions limiter.py:187, 249, 306, 361, 517; controller-store I/O limiter.py:55-60)
idempotency: SAFE for `restore()`/`load_hours()` (clamped value limiter.py:617-618; hour buckets merged limiter.py:637-638, 230-238); UNSAFE for `admit()` — each admitted call increments `_day_count` and stamps `_last_dispatch_at` — limiter.py:763-766 [INFERRED: re-calling admit double-charges the daily budget by design]

## failure behaviour
- `_registry_store`: any `Exception` → return None; the family gate then runs without cross-process persistence — limiter.py:486-489 (FACTS.fallbacks "SWALLOWED: return None").
- `_FamilyGate.note_failure`: `store.save` failure swallowed (`pass`) — limiter.py:450-455; the in-process gate still opens.
- `_FamilyGate.allowed`: `store.load` failure swallowed (`pass`) → gate fails OPEN — limiter.py:466-475.
- Two broader `Exception` handlers swallow-with-log at limiter.py:832 and limiter.py:1122 (bodies beyond the excerpt; FACTS.fallbacks).
- `settle` "Never raises" — limiter.py:786-788.
- No error codes raised in the visible range; refusals are values (`LimiterDecision.reason`), not exceptions.

## dumb-code flags
- `1_000_000_000` sentinel for "no RPD" in `capacity_snapshot` vs `None` in `spec.rpd` — two representations of "unlimited" — limiter.py:577 vs 78.
- Docstring gate order omits the OTPM and TPD gates the code actually checks — limiter.py:692-694 vs 728-735, 747-754 (doc drift).
- Hardcoded poll/sleep literals not tied to constants: `1.0` — limiter.py:273; `0.5` — limiter.py:328; `0.05`/`1.0` — limiter.py:676.
- `ts += 1e-6` same-tick collision bump in `_RollingTokens.add` — limiter.py:203-204.
- `BREAKER_WAIT_MAX_S = 75.0` vs `RETRY_AFTER_MAX_S = 60.0`: two separately maintained wait caps — limiter.py:50-51.
- `ProviderLimit.use_headers` (limiter.py:74) and `adaptive` (limiter.py:73): no read of either in the visible range (lines 1-791) [INFERRED — likely consumed in `_sync_headers`/registry beyond the excerpt; verify before removal].

## refactor notes
- Importers (FACTS.importers): `document_profile/groq_routing.py`, `llm_extraction/client.py`, `workers/llm_provider.py` — signature changes to `admit`/`acquire`/`capacity_snapshot` ripple to all three; `capacity_snapshot` is explicitly consumed by `groq_router.choose` — limiter.py:569-570.
- `REFUSE_*` string values are caller-facing API (refusal receipts name the gate) — limiter.py:127-136, 709-712; renaming breaks callers' reason handling.
- `state()` keys are the durable row schema; `spec_fingerprint` hashes every ProviderLimit field `[kind, init, min, max, rpm, tpm, conc_cap, rpd, family, tpd, otpm]` — adding/removing a field invalidates every persisted adopted ceiling — limiter.py:603-605, 636-644.
- `LimiterDecision` is `frozen=True` — limiter.py:139; making it mutable changes caller assumptions.
- `FAMILY_GATE` singleton (limiter.py:479) plus store keys `family:{family}` (limiter.py:451, 467) form a cross-process contract with the controller store.
- Store-key prefix `family:` and `state()` key names must stay stable across worker versions — limiter.py:451, 546-566.

## VERIFY
```verify
grep -Fq 'SUCCESS_STREAK_FOR_INCREASE = 4' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'REFUSE_PROVIDER_RPD = "PROVIDER_RPD"' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'n = min(float(n), self.capacity)' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'self.tokens = max(-self.capacity, self.tokens - float(n))' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'WINDOW_S = 86400.0' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'FAMILY_FAILURE_THRESHOLD = 8' shared/polymath_shared/llm_extraction/limiter.py
grep -Fq 'def admit(self, est_tokens: float = 0.0, block: bool = True, *' shared/polymath_shared/llm_extraction/limiter.py
! grep -Fq 'import asyncio' shared/polymath_shared/llm_extraction/limiter.py
```
