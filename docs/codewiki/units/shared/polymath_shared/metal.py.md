# unit: shared/polymath_shared/metal.py
anchor: shared/polymath_shared/metal.py:1-468

## purpose
Metal (MPS) pool discipline shared by every GPU sidecar (1). Three coupled fixes in one module: RELEASING — `gc.collect()` before `torch.mps.empty_cache()`, and only after the OOM traceback is dropped (6-21, 78-95); SPLITTING — halve batches on Metal OOM instead of burning the caller's whole stage attempt (23-28, 98-129); LEASING — METAL-LEASE-V1, a cross-process flock device lease with `interactive`/`background` classes so an interactive rerank/embed is never stuck behind an enrichment batch (30-45, 132-168). A single item that will not fit is a capacity failure, never retried (47-50). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| is_oom | def | (exc: BaseException) -> bool | metal.py:73-75 | — |
| release | def | () -> None | metal.py:78-95 | — |
| run_adaptive | def | (fn, items, what="batch", depth=0) -> list | metal.py:98-129 | — |
| normalize_priority | def | (value: Any) -> str | metal.py:171-176 | — |
| priority_headers | def | (priority: Any) -> dict[str, str] | metal.py:179-181 | — |
| lease_dir | def | () -> Path | metal.py:184-187 | — |
| lease_enabled | def | () -> bool | metal.py:190-193 | — |
| lease_timeout_s | def | (priority: str) -> float | metal.py:196-203 | — |
| lease_stats | def | () -> dict[str, int] | metal.py:206-210 | — |
| interactive_pending | def | () -> bool (diagnostic-only, 297-298) | metal.py:296-308 | — |
| LeaseReceipt | class | fields priority/what/mode/acquired/timed_out/yielded/waited_ms; as_dict() | metal.py:227-238 | — |
| device_lease | contextmanager | (priority=BACKGROUND, *, timeout_s=None, what="batch") -> Iterator[LeaseReceipt] | metal.py:359-423 | — |
| priority_scope | contextmanager | (priority=BACKGROUND) -> Iterator[bool] | metal.py:427-447 | — |
| leased_run_adaptive | def | (priority, fn, items, what="batch", *, receipts=None, timeout_s=None) -> list | metal.py:450-468 | — |
| PRIORITY_HEADER | constant | "X-Polymath-Priority" | metal.py:141 | — |

Module imported by: shared/polymath_shared/clients.py, sidecars/embedder/server.py, sidecars/reranker/server.py (FACTS.importers); per-symbol usage not recorded. The lease rationale names the embedder and the reranker as the two processes on one Metal device (30-31). [DERIVED]

## contracts
**is_oom(exc)** — in: any BaseException; out: `isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()` (75). [DERIVED]

**release()** — post: if `torch.backends.mps.is_available()` then `gc.collect()` then `torch.mps.empty_cache()` (90-92); any Exception swallowed, `pass` (93-95). [DERIVED]

**run_adaptive(fn, items, what, depth)** — pre: fn must be per-item and order-preserving (103-107). post: success -> `list(fn(items))` (110); non-OOM exception or `len(items) <= 1` -> re-raised (112-115); OOM with >1 items -> `exc.__traceback__ = None` (119), `release()` (122), split at `mid = len(items) // 2` (123), recurse halves with `release()` between them (126-128), return `left + right` (129). [DERIVED]

**normalize_priority(value)** — post: `None` -> `BACKGROUND`; `str(value).strip().lower() == "interactive"` -> `INTERACTIVE`; everything else `BACKGROUND` (174-176). [DERIVED]

**device_lease(priority, timeout_s, what)** — pre: none; fcntl missing or dir unwritable degrades, never raises (283-285, 290-293). post: yields `LeaseReceipt` with `mode` one of `"locked"` / `"open"` / `"disabled"` (231, 382, 386); `timeout_s=None` -> `lease_timeout_s(priority)` (377); `waited_ms = round((time.monotonic() - t0) * 1000, 1)` (392, 408); on failure `files.unlock_all()` before yielding and the batch proceeds unleased with `timed_out=True` (409-414); all held flocks released by `files.close()` in `finally` (423). Background-only: `receipt.yielded = True` when the interactive marker is busy (348). [DERIVED]

**priority_scope(priority)** — post: background or `lease_enabled()` False -> yields `False` (432-434); interactive -> attempts `LOCK_SH` on `_INTERACTIVE_LOCK` bounded by `_SCOPE_REGISTER_BUDGET_S` 0.05 (155, 440-444), holds it until context exit (445-447); yields whether registration is held (445). [DERIVED]

**leased_run_adaptive(priority, fn, items, ...)** — post: every `fn(chunk)` call runs inside its own `device_lease(priority, timeout_s=timeout_s, what=what)` (463-467); each receipt appended to `receipts` when not None (465-466); delegates ordering to `run_adaptive` (468). [DERIVED]

## effect surface
- Postgres: none — FACTS tables_read/tables_written empty. [DERIVED]
- Qdrant: none; FACTS.collections lists `polymath_fleet` (157) but that is the local lock directory `/private/tmp/polymath_fleet`, not a collection (157, 184-187). [DERIVED]
- Files: opens/creates `metal_lease.device`, `metal_lease.interactive`, `metal_lease.gate` (`os.O_RDWR | os.O_CREAT`, mode `0o644`) under `lease_dir()` (158-160, 253, 288); files are never unlinked in this module. [DERIVED]
- Env: `POLYMATH_FLEET_DIR` = unset -> `/private/tmp/polymath_fleet` (157, 187); `POLYMATH_METAL_LEASE` = `"1"`; `"0"`, `"off"`, `"false"`, `"no"` disable (193); `POLYMATH_METAL_LEASE_INTERACTIVE_TIMEOUT_S` / `POLYMATH_METAL_LEASE_BACKGROUND_TIMEOUT_S` = unset -> 10.0 / 30.0 s (148-149, 196-203).
- GPU/VM: `gc.collect()` (91), `torch.mps.empty_cache()` (92), gated by `torch.backends.mps.is_available()` (90); `fcntl.flock` LOCK_EX/LOCK_SH/LOCK_UN/LOCK_NB (262, 267). [DERIVED]
- Process-local state: `_STATS` Counter (163), `_WARNED` set (165), `_LOCAL_FALLBACK` threading.Lock (168). [DERIVED]
- Network / subprocess: none in SOURCE. [DERIVED]

## invariants
INVARIANT: at most one device batch fleet-wide — both classes take `_DEVICE_LOCK` with `fcntl.LOCK_EX` (320, 344) — metal.py:320,344 [DERIVED]
  fails-if: concurrent MPS batches overlap; measured 4.5 s -> 27-52 s rerank regression (33-35).
INVARIANT: no background acquisition while an interactive caller is registered — `_acquire_background` probes `_INTERACTIVE_LOCK` `LOCK_EX` (fails iff held SHARED) before touching the device, under the gate (329-330, 342-344) — metal.py:342-344 [DERIVED]
  fails-if: chat path queues behind enrichment; 1-2 text embed waited 3-4 s vs 0.35 s fresh (35-37).
INVARIANT: background holds no lock while sleeping — `_GATE_LOCK` released in `finally` (350) before `time.sleep(_POLL_S[BACKGROUND])` (355) — metal.py:350,355 [DERIVED]
  fails-if: background checkers deadlock each other on the gate.
INVARIANT: `exc.__traceback__ = None` (119) executes before `release()` (122) — metal.py:119-122 [DERIVED]
  fails-if: release inside a live handler frees nothing; pool stuck at 3.45 GiB instead of 1.14 GiB (19-21).
INVARIANT: single-item OOM is raised, never split — `len(items) <= 1` -> `raise` (112-115) — metal.py:112-115 [DERIVED]
  fails-if: infinite recursion or silently returning nothing (47-50).
INVARIANT: lease machinery never blocks inference — timeout -> proceeds unleased (409-414); lock dir failure -> `mode="open"` + `_LOCAL_FALLBACK` (388-399); `POLYMATH_METAL_LEASE=0` -> `mode="disabled"` (381-382) — metal.py:409-414,388-399 [DERIVED]
  fails-if: inference latency becomes gated on lock files (43-45).
INVARIANT: per-attempt leasing — `leased_run_adaptive` re-leases each sub-batch so the device is released between OOM-halving retries (463-467) — metal.py:463-467 [DERIVED]
  fails-if: background 8-item batch keeps the device for seconds; embed p50 5.8 s, max 107 s (457-461).
INVARIANT: wait budgets — INTERACTIVE 10.0 s / poll 0.002 s; BACKGROUND 30.0 s / poll 0.02 s; gate poll 0.001 s (147, 153-154) — metal.py:147,153-154 [DERIVED]
  fails-if: chat turn waits longer than one long batch plus slack (144-147).

## determinism & idempotency
determinism: NONDETERMINISTIC — clock `time.monotonic()` at 317, 321, 336, 353, 376, 389, 392, 408, 440, 442 (FACTS.nondeterminism); env reads 187, 193, 196-203; cross-process flock + thread concurrency (262, 163-168) [DERIVED]
idempotency: SAFE — effects are flock acquire/release (freed by fd close or process death, 242-245, 423), monotonic diagnostic counters (213-215), and lock-file creation; no other persistent state [DERIVED]

## failure behaviour
- `release()` `except Exception: pass` (93-95) — fully swallowed; "Releasing is an optimisation; never let it fail a request" (94). Caller sees success with a possibly-unshrunk pool. [DERIVED]
- `run_adaptive` `except Exception as exc` (111) — non-OOM or single-item re-raised (112-115); OOM multi-item converted into halved retries, never surfaces to caller (119-129). [DERIVED]
- `_LockFiles.__init__` `except Exception` (254-255) — `self.close()` then re-raise; surfaces only via `_open_lock_files`. [DERIVED]
- `_open_lock_files` `except Exception` (290-293) — swallowed: `_warn_once` log, `return None`; caller degrades to `mode="open"` + `_LOCAL_FALLBACK` (388-399). [DERIVED]
- `fcntl` ImportError at import time — `fcntl = None` (67-68); `_open_lock_files` returns None (283-285). [DERIVED]
- `_LockFiles.lock` — `BlockingIOError, PermissionError` -> `False`, no raise (264-265). [DERIVED]
- Lease timeout raises nothing: proceeds unleased, `timed_out=True`, one warning per priority class (410-414, 218-223). [DERIVED]

## dumb-code flags
- Magic numbers: 10.0 / 30.0 s budgets (147); 0.002 / 0.02 s polls (153); 0.001 gate poll (154); 0.05 s scope budget (155); `0o644` (253); `round(... * 1000, 1)` ms duplicated at 392 and 408. [DERIVED]
- Default `"batch"` duplicated four times: 101, 230, 360, 453. [DERIVED]
- Stats key families disagree by path: fallback path counts `f"{priority}.{receipt.mode}"` (393) -> e.g. `interactive.open`; file path counts `f"{priority}.acquired"` / `.timed_out` / `.yielded` (411, 416, 418). Dashboards must handle both. [DERIVED]
- FACTS.constants records `_WARNED = []` at 165, but SOURCE has `_WARNED: set[str] = set()` — analyzer artifact, not a list. [DERIVED]
- `lease_timeout_s` silently ignores unparsable env values: `except ValueError: pass` -> default (199-203). An env typo falls back with no warning. [DERIVED]
- `interactive_pending()` is never called by the module itself — diagnostic-only (297-298). [DERIVED]
- Docstrings cite external specs not in this unit: "plan §3.16 / §3.21 #18" (42) and "P1.d arm 2 finding, 2026-09-06" (457). [DERIVED]

## refactor notes
- `PRIORITY_HEADER = "X-Polymath-Priority"` (141) is the wire header emitted by `priority_headers` (181); all three importers (clients.py, embedder, reranker; FACTS.importers) must change together.
- Lock file names `_DEVICE_LOCK` / `_INTERACTIVE_LOCK` / `_GATE_LOCK` and the fleet dir (157-160, 187) are the cross-process coordination point — every fleet process must resolve the same inodes; renaming mid-fleet splits the lease.
- Class literals `"interactive"` / `"background"` (136-137) double as header values; `normalize_priority` (171-176) is the single mapping chokepoint — keep it the only one.
- `run_adaptive`'s fn contract — per-item, order-preserving (103-107) — is what makes splitting invisible; `leased_run_adaptive` (450-468) inherits it.
- Ordering `exc.__traceback__ = None` -> `release()` (119-122) is measured (19-21); moving release inside the handler re-pins the pool.
- Every fail-open path (67-68, 290-293, 388-399, 409-414) is contractual (43-45); converting a swallow or timeout into a raise blocks inference.
- `_LockFiles` relies on flock belonging to the open file description (242-245); two threads of one process must keep excluding each other — do not swap for process-global locks.
- `priority_scope` budget 0.05 s (155, 440-444): lowering it blocks interactive registration under a background checker's EX probe.

## VERIFY
```verify
grep -Fq 'PRIORITY_HEADER = "X-Polymath-Priority"' shared/polymath_shared/metal.py
grep -Fq 'DEFAULT_TIMEOUT_S = {INTERACTIVE: 10.0, BACKGROUND: 30.0}' shared/polymath_shared/metal.py
grep -Fq 'exc.__traceback__ = None' shared/polymath_shared/metal.py
grep -Fq 'DEFAULT_FLEET_DIR = "/private/tmp/polymath_fleet"' shared/polymath_shared/metal.py
grep -Fq 'fcntl.flock(self.fds[name], flags | fcntl.LOCK_NB)' shared/polymath_shared/metal.py
test "$(grep -c -F 'time.monotonic' shared/polymath_shared/metal.py)" -ge 10
! grep -Fq 'psycopg' shared/polymath_shared/metal.py
```
