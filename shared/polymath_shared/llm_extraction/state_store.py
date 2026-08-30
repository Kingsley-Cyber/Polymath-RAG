"""Durable store for the adaptive controllers (limiter.py).

Postgres is the control plane (AGENTS.md): the effective concurrency /
batch budget a lane has FOUND must survive worker restarts and reboots,
or the controller re-learns the same ceiling on every boot and never
holds it. Writes happen only on change (rare) on a short autocommit
connection of their own — never inside a stage transaction, because a
stage failure is exactly when the controller halves and that halving
must persist.

Fail-soft by design: a missing table (migration 0040 not applied) or an
unreachable database logs ONE warning and the controllers continue
in-memory. Controller state is an optimization; it never blocks
extraction.
"""
from __future__ import annotations

import json
import logging

log = logging.getLogger("polymath.llm_controller_state")

TABLE = "llm_controller_state"


class PostgresControllerStore:
    def __init__(self, dsn: str, *, connect_timeout: float = 3.0) -> None:
        self.dsn = dsn
        self.connect_timeout = connect_timeout
        self._warned = False

    def _warn_once(self, what: str, exc: BaseException) -> None:
        if not self._warned:
            self._warned = True
            log.warning("llm controller state %s unavailable (%s: %s); "
                        "continuing in-memory", what, type(exc).__name__, exc)

    def load(self, key: str) -> dict | None:
        try:
            import psycopg
            with psycopg.connect(self.dsn, connect_timeout=self.connect_timeout,
                                 autocommit=True) as conn:
                row = conn.execute(
                    f"SELECT state FROM {TABLE} WHERE key = %s", (key,)).fetchone()
            return dict(row[0]) if row and isinstance(row[0], dict) else None
        except Exception as exc:
            self._warn_once("load", exc)
            return None

    def save(self, key: str, state: dict) -> None:
        try:
            import psycopg
            with psycopg.connect(self.dsn, connect_timeout=self.connect_timeout,
                                 autocommit=True) as conn:
                conn.execute(
                    f"INSERT INTO {TABLE} (key, state, updated_at) "
                    f"VALUES (%s, %s::jsonb, now()) "
                    f"ON CONFLICT (key) DO UPDATE SET state = EXCLUDED.state, "
                    f"updated_at = now()",
                    (key, json.dumps(state, sort_keys=True)))
        except Exception as exc:
            self._warn_once("save", exc)
