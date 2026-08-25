"""OFFLINE COLD-TICK ATTRIBUTION (COLD-TICK-ATTRIBUTION-V1).

Runs ONE authoritative full census against the LIVE Postgres inside a
transaction that is ROLLED BACK — zero durable writes, no fleet effect —
and attributes every millisecond:

  phase telemetry  from control.census.pop_census_timing()
                   (runs query / attempts fetch / python loop /
                   receipt checks)
  SQL buckets      every statement timed and classified by table shape
                   via a measuring cursor wrapper

Output: eval/v5/scale/cold-tick-attribution-<UTCSTAMP>.json + .md

Usage:
  POLYMATH_PG_DSN=... .venv/bin/python \
      eval/v5/scale/cold_tick_attribution.py [--label cold-seed]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from control.census import compute_census, pop_census_timing  # noqa: E402

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

#: classification rules, first match wins; order matters.
_BUCKETS = [
    ("receipt_anti_join", re.compile(r"projection_receipts", re.I)),
    ("runs_active_scan", re.compile(r"FROM\s+runs\b", re.I)),
    ("stage_attempts", re.compile(r"FROM\s+stage_attempts\b", re.I)),
    ("chunks", re.compile(r"FROM\s+chunks\b", re.I)),
    ("facts_evidence", re.compile(r"FROM\s+(facts|evidence)\b", re.I)),
    ("canonical", re.compile(
        r"FROM\s+(canonical_\w+|retrieval_summaries)\b", re.I)),
    ("scheduler_cursors", re.compile(r"scheduler_cursors", re.I)),
]


def classify(sql: str) -> str:
    head = " ".join(sql.split())[:48]
    for name, rx in _BUCKETS:
        if rx.search(sql):
            return name
    return f"other:{head[:24]}"


class MeasuringCursor:
    """Times every execute() and buckets it by SQL shape."""

    def __init__(self, parent_cursor, ledger: dict):
        self._cur = parent_cursor
        self._ledger = ledger

    def execute(self, sql, params=None):
        t0 = time.perf_counter()
        out = self._cur.execute(sql, params)
        ms = (time.perf_counter() - t0) * 1000
        b = classify(sql if isinstance(sql, str) else str(sql))
        e = self._ledger.setdefault(b, {"ms": 0.0, "n": 0})
        e["ms"] += ms
        e["n"] += 1
        return out

    def __getattr__(self, name):
        return getattr(self._cur, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="cold-seed")
    args = ap.parse_args()

    ledger: dict[str, dict] = {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with psycopg.connect(DSN, connect_timeout=10) as conn:
        conn.execute("SET statement_timeout = '35min'")
        cur = conn.cursor()
        wrapped = MeasuringCursor(cur, ledger)

        class ConnShim:
            """compute_census expects conn.execute(...).fetchall()"""
            def execute(self, sql, params=None):
                return wrapped.execute(sql, params)

        t0 = time.perf_counter()
        census = compute_census(ConnShim(), mode="full")
        total_ms = (time.perf_counter() - t0) * 1000
        phases = pop_census_timing() or {}
        # the watermark INSERT happens in our tx; discard everything.
        conn.rollback()

    sql_ms = round(sum(e["ms"] for e in ledger.values()), 1)
    receipt_ms = phases.get("receipt_checks_ms", 0.0)
    loop_ms = phases.get("python_loop_ms", 0.0)
    accounted = {
        "sql_total_ms": sql_ms,
        "census_total_ms": phases.get("census_total_ms"),
        "wall_offline_ms": round(total_ms, 1),
    }
    gaps = len(census.gaps)

    report = {
        "label": args.label,
        "captured_at": stamp,
        "mode": "full (forced)",
        "accounting": accounted,
        "phases": phases,
        "sql_buckets": {k: {"ms": round(v["ms"], 1), "queries": v["n"]}
                        for k, v in sorted(ledger.items(),
                                           key=lambda kv: -kv[1]["ms"])},
        "gaps": gaps,
        "promote": len(census.promote),
        "fail": len(census.fail),
        "note": "transaction rolled back; watermark NOT seeded; "
                "zero durable writes",
    }

    outdir = ROOT / "eval" / "v5" / "scale"
    jpath = outdir / f"cold-tick-attribution-{stamp}.json"
    jpath.write_text(json.dumps(report, indent=1))

    lines = [
        "# COLD-TICK ATTRIBUTION (offline, MEASURED)",
        "",
        f"- captured: {stamp}  label: {args.label}",
        f"- wall (offline full census): **{total_ms/1000:.1f} s**",
        f"- census_total_ms: {phases.get('census_total_ms')}",
        f"- runs evaluated: {phases.get('runs_evaluated')}  "
        f"gaps={gaps} promote={len(census.promote)} fail={len(census.fail)}",
        "",
        "| phase | ms | share of census_total |",
        "|---|---|---|",
    ]
    ct = float(phases.get("census_total_ms") or 1)
    for k in ("runs_query_ms", "dirty_select_ms", "attempts_fetch_ms",
              "python_loop_ms", "receipt_checks_ms"):
        v = float(phases.get(k) or 0.0)
        lines.append(f"| {k} | {v:.1f} | {100*v/ct:.1f}% |")
    lines += ["", "| SQL bucket | ms | queries |", "|---|---|---|"]
    for k, v in sorted(ledger.items(), key=lambda kv: -kv[1]["ms"]):
        lines.append(f"| {k} | {v['ms']:.1f} | {v['n']} |")
    lines += [
        "",
        f"SQL total: {sql_ms:.1f} ms across "
        f"{sum(v['n'] for v in ledger.values())} statements.",
        "Transaction rolled back — no watermark seeded, no writes.",
    ]
    (outdir / f"cold-tick-attribution-{stamp}.md").write_text(
        "\n".join(lines) + "\n")
    print(json.dumps(report["accounting"], indent=1))
    print(f"written: {jpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
