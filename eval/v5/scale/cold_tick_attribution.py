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


def run_one(mode: str) -> dict:
    ledger: dict[str, dict] = {}
    with psycopg.connect(DSN, connect_timeout=10) as conn:
        conn.execute("SET statement_timeout = '35min'")
        cur = conn.cursor()
        wrapped = MeasuringCursor(cur, ledger)

        class ConnShim:
            """compute_census expects conn.execute(...).fetchall()"""
            def execute(self, sql, params=None):
                return wrapped.execute(sql, params)

        t0 = time.perf_counter()
        compute_census(ConnShim(), mode=mode)
        total_ms = (time.perf_counter() - t0) * 1000
        phases = pop_census_timing() or {}
        conn.rollback()

    return {
        "mode": mode,
        "wall_ms": round(total_ms, 1),
        "phases": phases,
        "sql_buckets": {k: {"ms": round(v["ms"], 1), "queries": v["n"]}
                        for k, v in sorted(ledger.items(),
                                           key=lambda kv: -kv[1]["ms"])},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="cold-seed")
    ap.add_argument("--modes", default="full,auto",
                    help="comma list: full, auto(incremental)")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = [run_one(m.strip()) for m in args.modes.split(",") if m.strip()]

    report = {
        "label": args.label,
        "captured_at": stamp,
        "runs": runs,
        "note": "transactions rolled back; watermark NOT touched by "
                "offline runs (full re-seeds inside its own rolled-back "
                "tx); zero durable writes",
    }

    outdir = ROOT / "eval" / "v5" / "scale"
    jpath = outdir / f"cold-tick-attribution-{stamp}.json"
    jpath.write_text(json.dumps(report, indent=1))

    lines = [
        "# COLD-TICK ATTRIBUTION (offline, MEASURED)",
        "",
        f"- captured: {stamp}  label: {args.label}",
    ]
    for r in runs:
        ph = r["phases"]
        ct = float(ph.get("census_total_ms") or r["wall_ms"] or 1)
        lines += [
            "",
            f"## mode={r['mode']} — wall {r['wall_ms']/1000:.2f} s",
            "",
            f"runs evaluated: {ph.get('runs_evaluated')}",
            "",
            "| phase | ms | share of census_total |",
            "|---|---|---|",
        ]
        for k in ("runs_query_ms", "dirty_select_ms", "attempts_fetch_ms",
                  "python_loop_ms", "receipt_checks_ms"):
            v = float(ph.get(k) or 0.0)
            lines.append(f"| {k} | {v:.1f} | {100*v/ct:.1f}% |")
        lines += ["", "| SQL bucket | ms | queries |", "|---|---|---|"]
        for k, v in sorted(r["sql_buckets"].items(),
                           key=lambda kv: -kv[1]["ms"]):
            lines.append(f"| {k} | {v['ms']:.1f} | {v['queries']} |")
        sql_total = sum(v["ms"] for v in r["sql_buckets"].values())
        lines += [
            "",
            f"SQL total {sql_total:.1f} ms / "
            f"{sum(v['queries'] for v in r['sql_buckets'].values())} "
            "statements.",
        ]
    lines += ["", "Transactions rolled back — zero durable writes."]
    (outdir / f"cold-tick-attribution-{stamp}.md").write_text(
        "\n".join(lines) + "\n")
    for r in runs:
        print(f"mode={r['mode']:12s} wall={r['wall_ms']/1000:8.2f}s "
              f"census_total={r['phases'].get('census_total_ms')}ms "
              f"receipt_checks={r['phases'].get('receipt_checks_ms')}ms")
    print(f"written: {jpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
