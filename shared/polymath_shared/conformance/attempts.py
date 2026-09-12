"""PROVIDER-ATTEMPT-LEDGER-V1 — one row per provider attempt.

The distinction this module exists to preserve:

    map_groq2 -> HTTP 429      attempt 1   failed
    map_groq3 -> HTTP 429      attempt 2   failed
    map_groq5 -> HTTP 200      attempt 3   ok
    ------------------------------------------------
    PMAP batch -> SUCCESS                  outcome

All four facts are true. Before this ledger only the last line was durable, so a run
could sit at an 82% provider rejection rate with every counter and dashboard green.

Writes are fail-soft by construction: accounting must never block or fail an
extraction call. A missing table, an unreachable database or a bad row logs once and
the call proceeds.
"""
from __future__ import annotations

import contextvars
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("polymath.attempt_ledger")

TABLE = "llm_provider_attempts"

#: Ambient context so a worker can tag its attempts without threading arguments through
#: every provider call site. Set once per ticket/run; read by the recorder.
_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("attempt_ctx", default={})

_warned = threading.Event()
_ENABLED_ENV = "POLYMATH_ATTEMPT_LEDGER"


def enabled() -> bool:
    """On by default; `POLYMATH_ATTEMPT_LEDGER=0` disables (e.g. a unit-test process)."""
    return os.environ.get(_ENABLED_ENV, "1").strip().lower() not in ("0", "false", "no", "off")


class attempt_context:
    """Tag every attempt made inside this block.

    Usage:
        with attempt_context(function="PMAP", stage="doc_parent_map", run_id=run_id):
            ...provider calls...
    """

    def __init__(self, **fields: Any) -> None:
        self.fields = {k: v for k, v in fields.items() if v is not None}
        self.fields.setdefault("correlation_id", uuid.uuid4().hex[:24])
        self._token = None

    def __enter__(self) -> dict:
        merged = {**_ctx.get(), **self.fields}
        merged["_ordinal"] = 0
        self._token = _ctx.set(merged)
        return merged

    def __exit__(self, *exc) -> None:
        if self._token is not None:
            _ctx.reset(self._token)


def current_context() -> dict:
    return dict(_ctx.get())


def next_ordinal() -> int:
    c = _ctx.get()
    if not c:
        return 1
    c = dict(c)
    c["_ordinal"] = int(c.get("_ordinal", 0)) + 1
    _ctx.set(c)
    return c["_ordinal"]


@dataclass
class Attempt:
    lane: str
    limiter_admitted: bool
    http_dispatched: bool
    success: bool
    http_status: int | None = None
    retry_after_s: float | None = None
    error_class: str | None = None
    latency_ms: int | None = None
    response_hash: str | None = None
    model: str | None = None
    provider: str | None = None
    account_env: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


def record(a: Attempt) -> None:
    """Persist one attempt. Never raises."""
    if not enabled():
        return
    dsn = os.environ.get("POLYMATH_PG_DSN", "").strip()
    if not dsn:
        return
    ctx = _ctx.get()
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=3, autocommit=True) as conn:
            conn.execute(
                f"""INSERT INTO {TABLE}
                    (correlation_id, run_id, ticket_id, function, stage, lane, provider,
                     model, account_env, attempt_ordinal, limiter_admitted, http_dispatched,
                     http_status, retry_after_s, error_class, success, latency_ms,
                     response_hash, tokens_in, tokens_out)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (ctx.get("correlation_id"), ctx.get("run_id"), ctx.get("ticket_id"),
                 ctx.get("function"), ctx.get("stage"), a.lane, a.provider, a.model,
                 a.account_env, next_ordinal(), a.limiter_admitted, a.http_dispatched,
                 a.http_status, a.retry_after_s, a.error_class, a.success, a.latency_ms,
                 a.response_hash, a.tokens_in, a.tokens_out))
    except Exception as exc:  # noqa: BLE001
        if not _warned.is_set():
            _warned.set()
            log.warning("attempt ledger unavailable (%s: %s); continuing without it",
                        type(exc).__name__, exc)


# ── readers (used by the auditor and the control plane) ──────────────────────

def ledger_available(conn) -> bool:
    try:
        return bool(conn.execute(
            "SELECT to_regclass(%s) IS NOT NULL", (TABLE,)).fetchone()[0])
    except Exception:
        return False


def attempt_summary(conn, window: str = "24 hours") -> dict:
    """Attempt-level truth: what the provider actually did, per lane and per function."""
    q = f"""
        SELECT COUNT(*)                                            AS attempts,
               COUNT(*) FILTER (WHERE NOT limiter_admitted)        AS limiter_refused,
               COUNT(*) FILTER (WHERE http_dispatched)             AS dispatched,
               COUNT(*) FILTER (WHERE http_status = 429)           AS http_429,
               COUNT(*) FILTER (WHERE success)                     AS succeeded,
               COUNT(DISTINCT correlation_id)                      AS logical_calls
          FROM {TABLE} WHERE created_at > now() - interval '{window}'"""
    try:
        r = conn.execute(q).fetchone()
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)[:200]}
    attempts, refused, dispatched, h429, ok, calls = r
    per_lane = conn.execute(f"""
        SELECT lane, COUNT(*), COUNT(*) FILTER (WHERE http_status=429),
               COUNT(*) FILTER (WHERE success)
          FROM {TABLE} WHERE created_at > now() - interval '{window}'
         GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    return {
        "available": True, "window": window,
        "attempts": attempts, "logical_calls": calls,
        "limiter_refused": refused, "dispatched": dispatched,
        "http_429": h429, "succeeded": ok,
        "attempts_per_success": (round(attempts / ok, 2) if ok else None),
        "rejection_rate": (round(h429 / dispatched, 3) if dispatched else None),
        "failover_attempts": max(0, attempts - calls),
        "per_lane": [{"lane": l, "attempts": n, "http_429": q4, "succeeded": s}
                     for l, n, q4, s in per_lane],
    }


def reconcile(conn, window: str = "24 hours") -> dict:
    """Cross-check the attempt ledger against the durable outcome tables.

    Reports the failure modes §6 names, each as a COUNT rather than a boolean, so a
    small leak is visible instead of rounding to 'fine'.
    """
    s = attempt_summary(conn, window)
    if not s.get("available"):
        return {"available": False}
    findings = []
    if s["dispatched"] and s["http_429"] and s["rejection_rate"] and s["rejection_rate"] > 0.25:
        findings.append({"code": "PROVIDER_PRESSURE",
                         "detail": f"{s['http_429']}/{s['dispatched']} dispatches rejected "
                                   f"({s['rejection_rate']:.0%})"})
    if s["failover_attempts"]:
        findings.append({"code": "FAILOVER_ATTEMPTS",
                         "detail": f"{s['failover_attempts']} extra attempt(s) beyond the "
                                   f"{s['logical_calls']} logical calls"})
    try:
        outcomes = dict(conn.execute("""
            SELECT COALESCE(last_error,'SUCCESS'), COUNT(*)
              FROM document_parent_map_batches
             WHERE updated_at > now() - interval '24 hours' GROUP BY 1""").fetchall())
    except Exception:
        outcomes = {}
    if s["http_429"] and not outcomes.get("HTTP_429"):
        findings.append({
            "code": "HIDDEN_429",
            "detail": f"{s['http_429']} HTTP 429 attempt(s) recorded, but 0 batch outcomes "
                      f"carry HTTP_429 — failover absorbed them. Outcome counters alone "
                      f"cannot see provider pressure."})
    return {"available": True, "summary": s, "batch_outcomes": outcomes, "findings": findings}
