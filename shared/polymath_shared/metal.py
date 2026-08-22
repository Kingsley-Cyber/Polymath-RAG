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

A single item that still will not fit is NOT retried. That is a real
capacity failure: the budget cannot process this corpus and must be
raised deliberately. Pretending otherwise would either loop forever or
silently return nothing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

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
