"""Postgres access for the workflow authority. No other module opens its
own connections — pool and advisory locks live here.

Rule (ISSUES_REPORT §1.2): a stage's durable write + receipt + status
transition commit in one transaction. Callers use `tx()` for exactly that.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg
from psycopg import Connection
from psycopg_pool import ConnectionPool

from polymath_shared.settings import get_settings

_pool: Optional[ConnectionPool] = None
_lock = threading.Lock()


def _build_pool() -> ConnectionPool:
    dsn = get_settings().postgres.dsn
    return ConnectionPool(
        dsn,
        min_size=1,
        max_size=8,
        open=False,
        kwargs={"autocommit": False},
    )


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = _build_pool()
            _pool.open()
        return _pool


@contextmanager
def tx() -> Iterator[Connection]:
    """One transaction on the workflow authority. Commits on clean exit,
    rolls back on exception."""
    pool = get_pool()
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


@contextmanager
def advisory_lock(conn: Connection, key: str) -> Iterator[None]:
    """Deterministic lock key = content hash, not a wall-clock field
    (ISSUES_REPORT §2.2 fix). Serializes competing writers on the same
    logical entity."""
    import hashlib

    lock_id = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") & 0x7FFFFFFFFFFFFFFF
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
    yield
