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
        self._token = None
        self._prev: dict = {}

    def __enter__(self) -> dict:
        outer = _ctx.get()
        self._prev = outer
        merged = {**outer, **self.fields}
        # INHERIT the correlation id. Minting one per context meant a nested context —
        # e.g. the Ollama `think` retry, which opens a second _AttemptOutcome inside the
        # first — split one logical call across two correlation ids, and
        # `failover_attempts` (attempts - distinct correlation ids) then read as zero
        # while a retry had plainly happened. A new id is minted only at the OUTERMOST
        # context, which is what "groups the attempts of one logical call" means.
        if not merged.get("correlation_id"):
            merged["correlation_id"] = uuid.uuid4().hex[:24]
        merged["_ordinal"] = int(outer.get("_ordinal", 0))
        self._token = _ctx.set(merged)
        return merged

    def __exit__(self, *exc) -> None:
        if self._token is None:
            return
        try:
            _ctx.reset(self._token)
        except ValueError:
            # "Token was created in a different Context". A contextvar token is only
            # valid in the Context that produced it, and a generator held open across
            # yields can be resumed in another one (Starlette moves a sync streaming
            # generator between threads). Restoring BY VALUE is equivalent here — the
            # mapping is what readers see — and it must never raise: this is diagnostics
            # wrapped around a user-visible stream, and raising here turned every chat
            # answer into a stream error.
            _ctx.set(self._prev)
        finally:
            self._token = None


def current_context() -> dict:
    return dict(_ctx.get())


def next_ordinal() -> int:
    """DEPRECATED in favour of deriving the ordinal in SQL (see `record`).

    A contextvar counter cannot sequence attempts across SIBLING contexts: the Ollama
    `think` retry opens a second attempt context inside the first, and resetting the
    token on exit discarded the increment, so every attempt of one logical call was
    recorded as ordinal 1. Kept for callers that want an in-process counter; the ledger
    no longer uses it.
    """
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
    #: This seam does not pass through a lane limiter at all (probe, chat synthesis).
    #: `limiter_admitted` is then NOT APPLICABLE rather than false — 0056's invariant
    #: "limiter_admitted=false => zero HTTP, zero quota" holds only when this is false.
    limiter_bypassed: bool = False
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
    """Persist one attempt. Never raises.

    `started_at` is derived, not defaulted. The row is inserted AFTER the attempt
    finishes, so the column's `DEFAULT now()` made it hold the FINISH time under a name
    that says start — which silently inverts any latency or overlap analysis built on
    it. Writing `now() - latency` makes the column mean what it is called, and
    `started_at + latency_ms` then gives the finish time §15 also asks for.
    """
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
                     response_hash, tokens_in, tokens_out, limiter_bypassed, started_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            -- the ordinal is DERIVED, not counted in memory: attempts of
                            -- one logical call can span sibling contexts, threads and
                            -- processes, and an in-process counter recorded every one of
                            -- them as attempt 1.
                            (SELECT COALESCE(MAX(attempt_ordinal), 0) + 1
                               FROM {TABLE} WHERE correlation_id = %s),
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            now() - make_interval(secs => COALESCE(%s,0) / 1000.0))""",
                (ctx.get("correlation_id"), ctx.get("run_id"), ctx.get("ticket_id"),
                 ctx.get("function"), ctx.get("stage"), a.lane, a.provider, a.model,
                 a.account_env, ctx.get("correlation_id"),
                 a.limiter_admitted, a.http_dispatched,
                 a.http_status, a.retry_after_s, a.error_class, a.success, a.latency_ms,
                 a.response_hash, a.tokens_in, a.tokens_out, a.limiter_bypassed,
                 a.latency_ms))
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
               COUNT(*) FILTER (WHERE NOT limiter_admitted
                                AND NOT limiter_bypassed)         AS limiter_refused,
               COUNT(*) FILTER (WHERE limiter_bypassed)           AS limiter_bypassed,
               COUNT(*) FILTER (WHERE http_dispatched)             AS dispatched,
               COUNT(*) FILTER (WHERE http_status = 429)           AS http_429,
               COUNT(*) FILTER (WHERE success)                     AS succeeded,
               COUNT(DISTINCT correlation_id)                      AS logical_calls,
               COUNT(*) FILTER (WHERE correlation_id IS NULL)      AS uncorrelated
          FROM {TABLE} WHERE created_at > now() - interval '{window}'"""
    try:
        r = conn.execute(q).fetchone()
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)[:200]}
    attempts, refused, bypassed, dispatched, h429, ok, calls, uncorrelated = r
    per_lane = conn.execute(f"""
        SELECT lane, COUNT(*), COUNT(*) FILTER (WHERE http_status=429),
               COUNT(*) FILTER (WHERE success)
          FROM {TABLE} WHERE created_at > now() - interval '{window}'
         GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    return {
        "available": True, "window": window,
        "attempts": attempts, "logical_calls": calls,
        "limiter_refused": refused, "limiter_bypassed": bypassed,
        "dispatched": dispatched,
        "http_429": h429, "succeeded": ok,
        "attempts_per_success": (round(attempts / ok, 2) if ok else None),
        "rejection_rate": (round(h429 / dispatched, 3) if dispatched else None),
        # FAILOVER is (attempts - logical calls) over CORRELATED rows only. An attempt
        # recorded without a correlation id belongs to no logical call, and counting it
        # here inflated failover by exactly the number of untagged rows — a seam that
        # simply forgot its context would have looked like provider failover.
        "failover_attempts": max(0, (attempts - uncorrelated) - calls),
        "uncorrelated_attempts": uncorrelated,
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
    # LIMITER_BYPASS — §15 names it; it was undetectable until the ledger could express
    # the state at all (migration 0059). Reported as an OBSERVATION with its lanes, not
    # as a fault: probe and chat synthesis bypass by design. A lane appearing here that
    # is supposed to be limiter-mediated is the fault, and naming the lanes is what lets
    # that be seen.
    if s.get("limiter_bypassed"):
        try:
            lanes = conn.execute(f"""
                SELECT lane, COUNT(*) FROM {TABLE}
                 WHERE limiter_bypassed AND created_at > now() - interval '{window}'
                 GROUP BY 1 ORDER BY 2 DESC""").fetchall()
        except Exception:  # noqa: BLE001
            lanes = []
        findings.append({
            "code": "LIMITER_BYPASS",
            "detail": f"{s['limiter_bypassed']} attempt(s) reached a provider without "
                      f"limiter admission, on: "
                      + ", ".join(f"{l}×{n}" for l, n in lanes)})
    # DARK_ENABLED_LANE — configured, credentialled and ENABLED, yet it made no attempt
    # in the window. Either it is dead weight in the rotation or something upstream is
    # never selecting it; both are invisible from outcome counters.
    try:
        from polymath_shared.llm_extraction import lane_registry as _LR
        enabled = {l.name for l in _LR.build_registry().lanes
                   if getattr(l, "enabled", False) and getattr(l, "credential_present", False)}
        seen = {row["lane"] for row in s.get("per_lane", [])}
        dark = sorted(enabled - seen)
    except Exception:  # noqa: BLE001 — a registry read must never break reconciliation
        dark = []
    if dark:
        findings.append({
            "code": "DARK_ENABLED_LANE",
            "detail": f"{len(dark)} enabled, credentialled lane(s) made no attempt in "
                      f"{window}: {', '.join(dark)}"})
    # CONFIG/LIVE_MISMATCH — the last of §15's five. Config is a claim about what the
    # system will do; the ledger is a record of what it did. Two ways they diverge, both
    # invisible from either side alone:
    #   * a lane DISPATCHED that the registry does not contain at all (live > config);
    #   * a lane whose configured model is not the model its attempts actually carried
    #     (config says one thing, the wire says another — e.g. a stage pin that never
    #     took effect, or a provider silently substituting a model).
    try:
        from polymath_shared.llm_extraction import lane_registry as _LR2
        configured = {l.name: l for l in _LR2.build_registry().lanes}
    except Exception:  # noqa: BLE001
        configured = {}
    if configured:
        live = conn.execute(f"""
            SELECT lane, COALESCE(model,'(none)'), COUNT(*)
              FROM {TABLE}
             WHERE created_at > now() - interval '{window}' AND http_dispatched
             GROUP BY 1,2""").fetchall()
        unknown, wrong_model = [], []
        for lane, model, n in live:
            cfg = configured.get(lane)
            if cfg is None:
                # chat_synth:* lanes are synthesis seams with no registry entry by
                # design; they are not provider LANES in the registry's sense.
                if not str(lane).startswith("chat_synth"):
                    unknown.append(f"{lane}×{n}")
            elif getattr(cfg, "model", "") and model not in ("(none)", cfg.model):
                wrong_model.append(f"{lane}: config={cfg.model} wire={model} ×{n}")
        if unknown or wrong_model:
            bits = []
            if unknown:
                bits.append(f"dispatched but absent from the registry: {', '.join(unknown)}")
            if wrong_model:
                bits.append(f"configured model != model on the wire: {'; '.join(wrong_model)}")
            findings.append({"code": "CONFIG/LIVE_MISMATCH", "detail": "; ".join(bits)})
    return {"available": True, "summary": s, "batch_outcomes": outcomes, "findings": findings}
