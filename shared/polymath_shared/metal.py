"""Metal (MPS) pool discipline, shared by every GPU sidecar.

This exists because the same defect was fixed twice and would have been
fixed a third time. Both fixes belong in one place:

  RELEASING     `torch.mps.empty_cache()` returns only blocks with no
                live reference. Two things keep references alive that
                callers do not expect -- an unreachable cycle (so a
                collection must happen first) and, far more subtly, a
                LIVE EXCEPTION HANDLER. While `except ... as exc:` is
                executing, `exc.__traceback__` references the frames of
                the call that raised, and those frames still reference
                the half-built activations that caused the OOM. A
                release from inside the handler therefore frees nothing.

                Measured on a 32 GB Mac Studio, identical cap and batch,
                the release site the only difference:

                  inside the handler   FAILED; pool stuck at 3.45 GiB
                  after clearing the   OK; pool returned to 1.14 GiB
                  traceback, outside   (weights only)

  SPLITTING     Batches are planned from an approximate token count,
                because putting the tokenizer on the hot path costs more
                than it saves. An approximation is occasionally wrong in
                the expensive direction. When it is, the work should
                cost a retry of that batch -- not the caller's whole
                stage ticket plus one of its bounded attempts.

  LEASING       METAL-LEASE-V1 (measured 2026-09-06): the embedder and
                the reranker are two processes on ONE Metal device. An
                8-text enrichment embed landing during an interactive
                20-pair rerank pushed both past the pool ("rerank batch
                OOM at 8 pairs; retrying at 4"; 4.5 s -> 27-52 s), and a
                1-2 text chat embed waited 3-4 s (0.35 s fresh) behind
                enrichment batches. Recycling clears fragmentation, not
                contention. `device_lease()` is a cross-process lease
                over the device with two classes: at most one device
                batch runs at a time, and while an INTERACTIVE caller is
                registered no BACKGROUND caller acquires -- the chat
                path takes the device as soon as the running batch
                releases (plan §3.16 / §3.21 #18). Waits are bounded and
                every failure mode is FAIL-OPEN: a lock that cannot be
                created or a budget that expires never blocks inference,
                it only shows up in the receipt.

A single item that still will not fit is NOT retried. That is a real
capacity failure: the budget cannot process this corpus and must be
raised deliberately. Pretending otherwise would either loop forever or
silently return nothing.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import Counter
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

try:  # Metal hosts are macOS/Linux; keep the module importable elsewhere (fail-open).
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

log = logging.getLogger("metal")


def is_oom(exc: BaseException) -> bool:
    """Metal reports exhaustion as a plain RuntimeError."""
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


def release() -> None:
    """Return Metal blocks to the system.

    Collect first: `empty_cache()` frees only unreferenced blocks, so a
    tensor still owned by an unreachable cycle stays pinned and the pool
    never shrinks.
    """
    try:
        import gc

        import torch

        if torch.backends.mps.is_available():
            gc.collect()
            torch.mps.empty_cache()
    except Exception:
        # Releasing is an optimisation; never let it fail a request.
        pass


def run_adaptive(fn: Callable[[Sequence[Any]], list],
                 items: Sequence[Any],
                 what: str = "batch",
                 depth: int = 0) -> list:
    """Apply `fn` to `items`, halving on Metal exhaustion.

    `fn` must be per-item and order-preserving -- that is what makes
    splitting invisible in the result. Every current caller (embedding,
    entity tagging) satisfies this: each text is processed independently
    and returned in input order, so any grouping yields identical output.
    """
    try:
        return list(fn(items))
    except Exception as exc:
        if not is_oom(exc) or len(items) <= 1:
            # One item that will not fit is a capacity failure, not a
            # batching one, and no amount of splitting will fix it.
            raise
        # Drop the traceback BEFORE releasing: its frames still hold the
        # activations that caused the OOM, so a release while the handler
        # is live frees nothing and every retry inherits a full pool.
        exc.__traceback__ = None

    # Outside the handler: no frame of the failed attempt survives.
    release()
    mid = len(items) // 2
    log.warning("mps oom on %d %s items (depth %d); splitting to %d + %d",
                len(items), what, depth, mid, len(items) - mid)
    left = run_adaptive(fn, items[:mid], what, depth + 1)
    release()
    right = run_adaptive(fn, items[mid:], what, depth + 1)
    return left + right


# ---------------------------------------------------------------------------
# METAL-LEASE-V1: cross-process device lease with interactive priority
# ---------------------------------------------------------------------------

INTERACTIVE = "interactive"
BACKGROUND = "background"
PRIORITIES = (INTERACTIVE, BACKGROUND)

#: Request header carrying the lease class (absent or unknown = background).
PRIORITY_HEADER = "X-Polymath-Priority"

#: Default wait budgets before a caller proceeds UNLEASED (fail-open).
#: Interactive: a chat turn must not wait longer than one long batch plus
#: slack. Background: enrichment can absorb a queue; past this something is
#: wedged and the lease must not become a second stall.
DEFAULT_TIMEOUT_S = {INTERACTIVE: 10.0, BACKGROUND: 30.0}
_ENV_TIMEOUT = {INTERACTIVE: "POLYMATH_METAL_LEASE_INTERACTIVE_TIMEOUT_S",
                BACKGROUND: "POLYMATH_METAL_LEASE_BACKGROUND_TIMEOUT_S"}
#: Poll cadence: the interactive class polls tightly so it takes the device
#: within milliseconds of a release; background polls looser and never
#: competes with a registered interactive caller.
_POLL_S = {INTERACTIVE: 0.002, BACKGROUND: 0.02}
_GATE_POLL_S = 0.001
_SCOPE_REGISTER_BUDGET_S = 0.05

DEFAULT_FLEET_DIR = "/private/tmp/polymath_fleet"
_DEVICE_LOCK = "metal_lease.device"          # the device mutex (one batch at a time)
_INTERACTIVE_LOCK = "metal_lease.interactive"  # SHARED-held by every registered interactive caller
_GATE_LOCK = "metal_lease.gate"              # serialises background checkers so a failed
#                                              interactive probe means "interactive", not "another checker"

_STATS: Counter = Counter()
_STATS_LOCK = threading.Lock()
_WARNED: set[str] = set()
#: Process-local serialisation when the file lease is disabled or unavailable
#: (no priority, but never two device batches from one process at once).
_LOCAL_FALLBACK = threading.Lock()


def normalize_priority(value: Any) -> str:
    """Header/argument value -> lease class. Anything not exactly the
    interactive class (case-insensitive, trimmed) is background."""
    if value is None:
        return BACKGROUND
    return INTERACTIVE if str(value).strip().lower() == INTERACTIVE else BACKGROUND


def priority_headers(priority: Any) -> dict[str, str]:
    """The one header a client sends to declare its lease class."""
    return {PRIORITY_HEADER: normalize_priority(priority)}


def lease_dir() -> Path:
    """Lock files live under the fleet run dir so every process of the fleet
    (and only this fleet) coordinates on the same inodes."""
    return Path(os.environ.get("POLYMATH_FLEET_DIR") or DEFAULT_FLEET_DIR)


def lease_enabled() -> bool:
    """POLYMATH_METAL_LEASE=0 disables the file lease (rollback knob): callers
    fall back to process-local serialisation without priority."""
    return os.environ.get("POLYMATH_METAL_LEASE", "1").strip().lower() not in ("0", "off", "false", "no")


def lease_timeout_s(priority: str) -> float:
    raw = os.environ.get(_ENV_TIMEOUT[normalize_priority(priority)])
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return DEFAULT_TIMEOUT_S[normalize_priority(priority)]


def lease_stats() -> dict[str, int]:
    """Process-local counters (acquired / yielded / timed_out / open /
    disabled per class) for receipts and diagnostics."""
    with _STATS_LOCK:
        return dict(_STATS)


def _count(key: str) -> None:
    with _STATS_LOCK:
        _STATS[key] += 1


def _warn_once(key: str, msg: str, *args: Any) -> None:
    if key in _WARNED:
        log.debug(msg, *args)
        return
    _WARNED.add(key)
    log.warning(msg, *args)


@dataclass
class LeaseReceipt:
    """What one lease attempt cost; callers surface `waited_ms` as `queued_ms`."""
    priority: str
    what: str = "batch"
    mode: str = "locked"      # locked (file lease) | open (lock unavailable) | disabled (env)
    acquired: bool = False    # the device was held exclusively for the batch
    timed_out: bool = False   # the budget expired; the batch ran unleased
    yielded: bool = False     # background only: backed off for interactive work at least once
    waited_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class _LockFiles:
    """The lock fds of one lease attempt. flock() locks belong to the OPEN
    FILE DESCRIPTION, so every attempt opens its own fds: two threads of one
    process exclude each other exactly like two processes, and closing the
    fds (or the process dying) releases everything."""

    NAMES = (_DEVICE_LOCK, _INTERACTIVE_LOCK, _GATE_LOCK)

    def __init__(self, root: Path) -> None:
        self.fds: dict[str, int] = {}
        try:
            for name in self.NAMES:
                self.fds[name] = os.open(root / name, os.O_RDWR | os.O_CREAT, 0o644)
        except Exception:
            self.close()
            raise

    def lock(self, name: str, flags: int) -> bool:
        """Non-blocking flock; False when another holder conflicts."""
        try:
            fcntl.flock(self.fds[name], flags | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, PermissionError):
            return False

    def unlock(self, name: str) -> None:
        with suppress(OSError):
            fcntl.flock(self.fds[name], fcntl.LOCK_UN)

    def unlock_all(self) -> None:
        for name in list(self.fds):
            self.unlock(name)

    def close(self) -> None:
        for fd in self.fds.values():
            with suppress(OSError):
                os.close(fd)
        self.fds = {}


def _open_lock_files() -> _LockFiles | None:
    """Fail-open: None when the lock dir cannot be created or written."""
    if fcntl is None:
        _warn_once("open", "metal lease: fcntl unavailable; device batches run unleased")
        return None
    root = lease_dir()
    try:
        root.mkdir(parents=True, exist_ok=True)
        return _LockFiles(root)
    except Exception as exc:  # noqa: BLE001 — never block inference on a lock file
        _warn_once("open", "metal lease unavailable at %s (%s: %s); device batches run unleased",
                   root, type(exc).__name__, exc)
        return None


def interactive_pending() -> bool:
    """True while any interactive caller is registered (waiting or running).
    Diagnostic; the lease itself never calls this."""
    files = _open_lock_files()
    if files is None:
        return False
    try:
        if files.lock(_INTERACTIVE_LOCK, fcntl.LOCK_EX):
            files.unlock(_INTERACTIVE_LOCK)
            return False
        return True
    finally:
        files.close()


def _acquire_interactive(files: _LockFiles, deadline: float) -> bool:
    """Register (SHARED on the interactive marker: many interactive callers
    coexist), then poll the device mutex tightly. The marker stays held for
    the whole lease so background never competes for the device meanwhile."""
    while not files.lock(_INTERACTIVE_LOCK, fcntl.LOCK_SH):
        # Only a background checker's microsecond EX probe can conflict.
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_S[INTERACTIVE])
    while not files.lock(_DEVICE_LOCK, fcntl.LOCK_EX):
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_S[INTERACTIVE])
    return True


def _acquire_background(files: _LockFiles, deadline: float, receipt: LeaseReceipt) -> bool:
    """Take the device only when NO interactive caller is registered: under
    the gate, probe the interactive marker EXCLUSIVELY (fails iff an
    interactive caller holds it SHARED), then try the device. Both probes
    are non-blocking and the gate is released before every sleep, so a
    background caller never holds anything while it waits."""
    while True:
        if not files.lock(_GATE_LOCK, fcntl.LOCK_EX):
            # Another background checker is mid-probe (microseconds) — not interactive work.
            if time.monotonic() >= deadline:
                return False
            time.sleep(_GATE_POLL_S)
            continue
        got = False
        try:
            if files.lock(_INTERACTIVE_LOCK, fcntl.LOCK_EX):
                try:
                    got = files.lock(_DEVICE_LOCK, fcntl.LOCK_EX)
                finally:
                    files.unlock(_INTERACTIVE_LOCK)
            else:
                receipt.yielded = True
        finally:
            files.unlock(_GATE_LOCK)
        if got:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_S[BACKGROUND])


@contextmanager
def device_lease(priority: str = BACKGROUND, *, timeout_s: float | None = None,
                 what: str = "batch") -> Iterator[LeaseReceipt]:
    """Hold the Metal device for ONE batch, across processes, by class.

    interactive  registers, then takes the device as soon as the running
                 batch releases (no background batch gets in first).
    background   waits while any interactive caller is registered; among
                 background callers, whoever polls first wins.

    Bounded: after `timeout_s` (default per class, env-tunable) the caller
    PROCEEDS UNLEASED and the receipt says `timed_out`. Fail-open: an
    unwritable lock dir or POLYMATH_METAL_LEASE=0 degrades to a process-
    local lock (`mode` open/disabled) — inference is never blocked by the
    lease machinery. The yielded receipt's `waited_ms` is the queue time.
    """
    priority = normalize_priority(priority)
    receipt = LeaseReceipt(priority=priority, what=what)
    t0 = time.monotonic()
    budget = lease_timeout_s(priority) if timeout_s is None else max(0.0, float(timeout_s))
    deadline = t0 + budget

    files: _LockFiles | None = None
    if not lease_enabled():
        receipt.mode = "disabled"
    else:
        files = _open_lock_files()
        if files is None:
            receipt.mode = "open"

    if files is None:
        got = _LOCAL_FALLBACK.acquire(timeout=max(0.0, deadline - time.monotonic()))
        receipt.acquired = got
        receipt.timed_out = not got
        receipt.waited_ms = round((time.monotonic() - t0) * 1000, 1)
        _count(f"{priority}.{receipt.mode}")
        try:
            yield receipt
        finally:
            if got:
                _LOCAL_FALLBACK.release()
        return

    try:
        if priority == INTERACTIVE:
            acquired = _acquire_interactive(files, deadline)
        else:
            acquired = _acquire_background(files, deadline, receipt)
        receipt.acquired = acquired
        receipt.timed_out = not acquired
        receipt.waited_ms = round((time.monotonic() - t0) * 1000, 1)
        if not acquired:
            files.unlock_all()   # never run with a half-registration
            _count(f"{priority}.timed_out")
            _warn_once(f"timeout:{priority}",
                       "metal lease: %s %s waited %.0f ms (budget %.1f s) and proceeds unleased",
                       priority, what, receipt.waited_ms, budget)
        else:
            _count(f"{priority}.acquired")
            if receipt.yielded:
                _count(f"{priority}.yielded")
                log.info("metal lease: background %s batch yielded to interactive work; queued %.0f ms",
                         what, receipt.waited_ms)
        yield receipt
    finally:
        files.close()   # closing the fds releases every flock this attempt holds


@contextmanager
def priority_scope(priority: str = BACKGROUND) -> Iterator[bool]:
    """Register interactive presence for a WHOLE request (several device
    batches), so no background batch slips into the gap between two of its
    `device_lease()` batches. No-op for background. Yields whether the
    registration is held (False under fail-open)."""
    if normalize_priority(priority) != INTERACTIVE or not lease_enabled():
        yield False
        return
    files = _open_lock_files()
    if files is None:
        yield False
        return
    try:
        deadline = time.monotonic() + _SCOPE_REGISTER_BUDGET_S
        registered = files.lock(_INTERACTIVE_LOCK, fcntl.LOCK_SH)
        while not registered and time.monotonic() < deadline:
            time.sleep(_GATE_POLL_S)
            registered = files.lock(_INTERACTIVE_LOCK, fcntl.LOCK_SH)
        yield registered
    finally:
        files.close()


def leased_run_adaptive(priority: str,
                        fn: Callable[[Sequence[Any]], list],
                        items: Sequence[Any],
                        what: str = "batch",
                        *,
                        receipts: list[LeaseReceipt] | None = None,
                        timeout_s: float | None = None) -> list:
    """`run_adaptive` under one device lease: the batch AND its OOM-halving
    retries run while the device is held, so the other process cannot pile
    on mid-recovery. Appends the lease receipt to `receipts` when given."""
    with device_lease(priority, timeout_s=timeout_s, what=what) as lease:
        if receipts is not None:
            receipts.append(lease)
        return run_adaptive(fn, items, what)
