# unit: shared/polymath_shared/document_profile/groq_routing.py
anchor: shared/polymath_shared/document_profile/groq_routing.py:1-155

## purpose
Wires `groq_router.choose` over the live limiter registry: given a pin of Groq lanes (compound + compound-mini across six accounts), pick the (account, model) with the most shared remaining budget and map it back to the lane to call. Reversible via `POLYMATH_GROQ_ROUTER` (off = default, callers keep existing rotation). Adds no scheduler; reuses `groq_accounts.account_states`, `groq_router.choose`, and the limiter registry. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:1-16

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router_enabled` | def | () -> bool | shared/polymath_shared/document_profile/groq_routing.py:39-40 | — |
| `reset_reservations` | def | () -> None | shared/polymath_shared/document_profile/groq_routing.py:61-64 | tests + fresh campaign (per docstring) |
| `account_maps` | def | (pin: Iterable[str], providers: list[dict] \| None = None) -> tuple[dict, dict] | shared/polymath_shared/document_profile/groq_routing.py:87-96 | — |
| `select_lane` | def | (pin, decision: GR.RouteDecision, account_of: Mapping[str, str], model_of: Mapping[str, str]) -> str \| None | shared/polymath_shared/document_profile/groq_routing.py:99-107 | — |
| `route` | def | (pin: list[str], work_class: str, \*, est_total_tokens: float, registry=None, providers=None, account_rpd=None, now=None, get_lane=None) -> tuple[str \| None, GR.RouteDecision] | shared/polymath_shared/document_profile/groq_routing.py:110-155 | — |

## contracts

`route` — shared/polymath_shared/document_profile/groq_routing.py:110-155
- in: pin lanes, `work_class`, kw-only `est_total_tokens: float`; optional `registry`, `providers`, `account_rpd`, `now`, `get_lane`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:110-113
- out: `(lane_name, decision)`; lane is `None` when the router yields a wait/no-capacity. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:117
- pre: none enforced; empty account pool → `(None, GR.RouteDecision(None, None, "empty_pool"))`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:121-122
- post: a routed pick appends `now` to `_PENDING[decision.account]` under `_PENDING_LOCK`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:152-154
- clock: `now` defaults to `time.monotonic()`, matching the limiter's `_not_before`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:116,119
- default lane lookup: `registry.get_lane(DEFAULT_PROVIDER, name)` with `DEFAULT_PROVIDER = "llm_cloud"`, registry lazily imported as `REGISTRY` when `get_lane is None`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:123-126

`account_maps` — shared/polymath_shared/document_profile/groq_routing.py:87-96
- in: pin lanes; `providers=None` → read from `config/cloud_providers.json`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:82,89
- out: `(account_of: lane → api_key_env, model_of: lane → model)`; only lanes whose provider entry has `api_key_env`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:93-95

`select_lane` — shared/polymath_shared/document_profile/groq_routing.py:99-107
- pure; returns `None` when `decision.routed` is false; first pin lane matching both account and model. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:101-106

`router_enabled` — shared/polymath_shared/document_profile/groq_routing.py:39-40
- out: `True` iff `POLYMATH_GROQ_ROUTER` `.strip().lower()` is in `("1", "true", "yes", "on")`. [DERIVED]

`_pending_counts_locked(now)` — shared/polymath_shared/document_profile/groq_routing.py:67-77
- pre: caller holds `_PENDING_LOCK`; keeps stamps where `now - t < RESERVATION_TTL_S`, drops the account when none remain. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:68,70-76

## effect surface
- env read: `POLYMATH_GROQ_ROUTER` = `''` default. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:40
- file read: `config/cloud_providers.json` (via `_ROOT = Path(__file__).resolve().parents[3]`). [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:28-29,82
- in-process mutable state: `_PENDING: dict[str, list[float]]` guarded by `_PENDING_LOCK` (`threading.Lock`). [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:57-58,144-154
- lazy import: `polymath_shared.llm_extraction.limiter.REGISTRY`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:123-124
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty); no network or subprocess in this file.

## invariants
INVARIANT: RESERVATION_TTL_S == 6.0 seconds — shared/polymath_shared/document_profile/groq_routing.py:56 [DERIVED]
  fails-if: sequential calls closer than 6 s start seeing each other's picks as extra `in_flight`; the "map calls ~8 s apart are unaffected" assumption (comment 53-54) breaks.
INVARIANT: default per-account daily budget == 230 (`DEFAULT_ACCOUNT_RPD`) when `account_rpd` is falsy — shared/polymath_shared/document_profile/groq_routing.py:32,127 [DERIVED]
  fails-if: placeholder snapshots mis-state capacity vs the real Groq quota when limiter config is absent.
INVARIANT: registry lane lookup provider == `"llm_cloud"` (registry keys are `(f"llm_{client_lane}", limiter_key)`) — shared/polymath_shared/document_profile/groq_routing.py:33-36,125 [DERIVED]
  fails-if: `get_lane` finds no limiter row, every lane falls to the placeholder snapshot — the 8-doc backfill's single-account pinning traced here (comment 33-35).
INVARIANT: every pin lane gets a snapshot — live via `capacity_snapshot(now=now)` if the limiter lane exists, else a fresh full-budget placeholder — shared/polymath_shared/document_profile/groq_routing.py:132-140 [DERIVED]
  fails-if: unused accounts become invisible and the router pins to the first-used lane (43/43 calls on `map_groq1`, comment 129-131).
INVARIANT: pending picks are injected as extra `in_flight` only when `pending.get(acct, 0)` is nonzero — shared/polymath_shared/document_profile/groq_routing.py:146-149 [DERIVED]
  fails-if: a simultaneous burst all reads near-identical snapshots and concentrates on one account (measured 633/640 on `map_groq1`, comment 47-48).
INVARIANT: reservation recorded only when `decision.routed and decision.account` — shared/polymath_shared/document_profile/groq_routing.py:152-154 [DERIVED]
  fails-if: wait/no-capacity decisions pollute pending counts and suppress healthy accounts.
INVARIANT: reservation is advisory (never blocks); the limiter stays the enforcement authority; state is process-local — shared/polymath_shared/document_profile/groq_routing.py:52-54 [DERIVED]
  fails-if: removal of the limiter check would turn this module into a scheduler it explicitly is not.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` shared/polymath_shared/document_profile/groq_routing.py:119; env read :40; file read :82; concurrency on shared `_PENDING` :57-58,144-154)
idempotency: UNSAFE (`route` appends to `_PENDING` on every routed call shared/polymath_shared/document_profile/groq_routing.py:154, so identical calls rotate picks by design; `account_maps`/`select_lane` are pure :87-107)

## failure behaviour
- `_providers`: broad `except Exception` → `return []` (FACTS fallback `SWALLOWED: return []` at line 83). Caller then sees an empty provider list, so `account_maps` returns empty maps and `route` yields `(None, GR.RouteDecision(None, None, "empty_pool"))`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:83-84,121-122
- No exceptions are raised by this module itself; degradation is expressed as `lane = None` plus the decision object. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:117

## dumb-code flags
- Magic number `230` — "the six Groq accounts' measured quota; the limiter row's rpd is authoritative when available". [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:30-32
- Naming trap: provider must be `"llm_cloud"`, NOT `"cloud"` — documented only in comment. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:33-36
- Bug-history numbers live only in comments, enforced nowhere: `633/640` (:47-48) and `43/43` (:129-131). [DERIVED]
- `route(..., registry=X, get_lane=g)` silently ignores `X`: `registry` is read only inside `if get_lane is None`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:123-126
- `dict(account_rpd) if account_rpd else {...}` — truthiness treats an empty mapping the same as `None`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:127
- Lambda assigned to a name with `# noqa: E731`. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:125

## refactor notes
- `DEFAULT_PROVIDER = "llm_cloud"` must not change without checking the limiter registry's key scheme `(f"llm_{client_lane}", limiter_key)`; wrong value breaks all lane lookups. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:33-36,125
- The placeholder-snapshot branch is the fix for the 43/43 pinning bug; deleting it re-pins the router to the first-used lane. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:128-131
- TTL `6.0` assumes sequential call spacing > TTL (map calls ~8 s apart); faster cadences change routing behavior. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:53-56
- `select_lane` returns the first (account, model) match in pin order; duplicate lanes make pin order significant. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:104-106
- Decision reason literal `"empty_pool"` is part of the observable contract for callers branching on it. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:121-122
- `reset_reservations` is the test seam for `_PENDING`; changing it breaks tests that clear campaign state. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:61-64
- `_PENDING` is process-local by design; it coordinates only this process's threads — a multi-process burst is not covered. [DERIVED] shared/polymath_shared/document_profile/groq_routing.py:54

## VERIFY
```verify
grep -Fq 'DEFAULT_ACCOUNT_RPD = 230' shared/polymath_shared/document_profile/groq_routing.py
grep -Fq 'RESERVATION_TTL_S = 6.0' shared/polymath_shared/document_profile/groq_routing.py
grep -Fq 'DEFAULT_PROVIDER = "llm_cloud"' shared/polymath_shared/document_profile/groq_routing.py
! grep -Fq 'DEFAULT_PROVIDER = "cloud"' shared/polymath_shared/document_profile/groq_routing.py
grep -Fq 'GR.RouteDecision(None, None, "empty_pool")' shared/polymath_shared/document_profile/groq_routing.py
grep -Eq 'in \("1", "true", "yes", "on"\)' shared/polymath_shared/document_profile/groq_routing.py
test "$(grep -c -F '_PENDING' shared/polymath_shared/document_profile/groq_routing.py)" -ge 5
```
