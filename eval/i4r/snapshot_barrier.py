"""Evaluation snapshot barrier helper (CONTROL-PLANE-V2, ADR-0014).

Usage for any NON-frozen evaluator (the frozen I4 harness is never
modified):

    from eval_i4r.snapshot_barrier import guarded_evaluation

    with guarded_evaluation("i4-fresh-acceptance-v1") as snap:
        ... measure retrieval / facts / anything ...

If the corpus is not at the generation barrier, acquisition REFUSES.
If the corpus state changes during evaluation, validation ABORTS
loudly — an evaluator never again measures a reconciling corpus
(the retrieval 0/30 class).

Run as a script for a one-shot barrier check:
    .venv/bin/python eval/i4r/snapshot_barrier.py <corpus_id>
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from polymath_shared.db import tx  # noqa: E402


@contextmanager
def guarded_evaluation(corpus_id: str):
    from control.snapshots import acquire_snapshot, validate_snapshot

    with tx() as conn:
        snapshot_id = acquire_snapshot(conn, corpus_id, require_query_ready=True)
    try:
        yield {"snapshot_id": snapshot_id, "corpus_id": corpus_id}
    finally:
        with tx() as conn:
            validate_snapshot(conn, snapshot_id)


def main() -> int:
    corpus_id = sys.argv[1] if len(sys.argv) > 1 else "i4-fresh-acceptance-v1"
    try:
        with guarded_evaluation(corpus_id) as snap:
            print(f"barrier OK: {snap['snapshot_id']}")
        print("state stable across check")
        return 0
    except RuntimeError as exc:
        print(f"barrier REFUSED/ABORTED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
