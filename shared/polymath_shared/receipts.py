"""Receipts. The single transaction boundary for durable writes.

The rule: a stage's durable write + its receipt + its status
transition are one transaction. If they are not, the stage is wrong.

Use the functions in this module. Do not write receipts by hand.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


@contextmanager
def stage_transaction(*, run_id: str, stage: str, contract_hash: str) -> Iterator[Any]:
    """Yield a transaction handle. The caller writes its durable data,
    its receipt, and the status transition inside the with-block.

    Commits on clean exit, rolls back on exception. The contract_hash
    is the idempotency key; re-running with the same key is a no-op.
    """
    raise NotImplementedError  # populated when stores/postgres lands
