"""Projection acceptance with a resource guard.

Resumes the checkpointed routing projection and watches it converge,
recording the evidence the release needs: that progress RESUMES rather
than restarting, that completed rows are never recomputed, that no
ticket burns a retry while merely waiting, and that the control plane
stays responsive.

The guard exists because the previous attempt burned hours in a
thrashing state: once swap saturated, provider throughput collapsed more
than 10x. It OBSERVES only — it never kills anything it does not own.
When the host degrades persistently it stops the run gracefully, leaving
the durable checkpoint intact, because a capacity stop is always
preferable to hours of thrash or a restarted projection.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.runtime_budget import footprint_gb  # noqa: E402

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def swap_used_mb() -> float:
    out = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True)
    for tok in out.stdout.replace("=", " ").split():
        if tok.endswith("M") and "used" in out.stdout[:out.stdout.find(tok)][-12:]:
            try:
                return float(tok[:-1])
            except ValueError:
                pass
    # fallback: parse positionally
    parts = out.stdout.split()
    for i, p in enumerate(parts):
        if p == "used" and i + 2 < len(parts):
            try:
                return float(parts[i + 2].rstrip("M"))
            except ValueError:
                return 0.0
    return 0.0


def free_pct() -> float:
    """Genuinely AVAILABLE memory as a percentage of physical.

    `memory_pressure`'s own "free percentage" is an instantaneous sample
    that swung 6% -> 59% -> 47% -> 7% within four minutes on this host and
    tripped the guard while the embedder was perfectly healthy. What
    matters is reclaimable memory: free + inactive + speculative pages,
    since macOS evicts inactive pages on demand.
    """
    out = subprocess.run(["vm_stat"], capture_output=True, text=True)
    pages, page_size = {}, 16384
    for line in out.stdout.splitlines():
        if "page size of" in line:
            try:
                page_size = int(line.split("page size of")[1].split()[0])
            except Exception:
                pass
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().rstrip(".")
        if v.isdigit():
            pages[k.strip()] = int(v)
    if not pages:
        return -1.0
    avail = (pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
             + pages.get("Pages speculative", 0))
    total_bytes = _physical_bytes()
    if not total_bytes:
        return -1.0
    return round(100.0 * avail * page_size / total_bytes, 1)


def _physical_bytes() -> int:
    out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                         capture_output=True, text=True)
    try:
        return int(out.stdout.strip())
    except ValueError:
        return 0


def snapshot(conn, corpus: str) -> dict:
    ck = conn.execute(
        "SELECT COUNT(*) FROM projection_receipts "
        "WHERE projection='qdrant' AND active").fetchone()[0]
    tickets = dict(conn.execute(
        "SELECT status, COUNT(*) FROM stage_tickets WHERE corpus_id=%s GROUP BY 1",
        (corpus,)).fetchall())
    qready = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='query_ready'",
        (corpus,)).fetchone()[0]
    faults = conn.execute(
        "SELECT COUNT(*) FROM stage_tickets WHERE corpus_id=%s "
        "AND last_error_note LIKE 'lease_expired_while_owner_alive%%'",
        (corpus,)).fetchone()[0]
    blocked = conn.execute(
        "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='polymath' "
        "AND wait_event_type='Lock'").fetchone()[0]
    control = conn.execute(
        "SELECT COUNT(*) FROM control_heartbeats "
        "WHERE occurred_at > now() - interval '3 minutes'").fetchone()[0]
    return {"checkpoint": ck, "tickets": tickets, "query_ready": qready,
            "lease_faults": faults, "blocked": blocked, "control_ticks": control}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="release-books-v1")
    ap.add_argument("--minutes", type=int, default=180)
    ap.add_argument("--target-docs", type=int, default=25)
    ap.add_argument("--out")
    # graceful capacity stop
    ap.add_argument("--min-free-pct", type=float, default=12.0,
                    help="SECONDARY floor: stop when the HOST is genuinely "
                         "starved, whoever caused it. Deliberately low, "
                         "because the primary guard is Polymath's own "
                         "allocation, not the owner's applications.")
    ap.add_argument("--low-ticks", type=int, default=3,
                    help="consecutive minutes below the floor before stopping")
    ap.add_argument("--stall-minutes", type=int, default=25,
                    help="no checkpoint progress for this long => stop")
    a = ap.parse_args()

    conn = psycopg.connect(DSN, connect_timeout=10)
    first = snapshot(conn, a.corpus)
    start = time.time()
    base_fp = footprint_gb()
    print(json.dumps({"event": "resume_baseline", **first,
                      "swap_used_mb": swap_used_mb(),
                      "free_pct": free_pct(),
                      "polymath_gb": base_fp["total_gb"],
                      "budget_gb": base_fp["budget_gb"]}))
    history = [(start, first["checkpoint"])]
    last_progress = start
    low_streak = over_streak = 0
    verdict, detail = "TIMEOUT", ""

    while time.time() - start < a.minutes * 60:
        time.sleep(60)
        try:
            snap = snapshot(conn, a.corpus)
        except Exception as exc:                       # store bounced
            print(json.dumps({"event": "store_unreachable", "error": str(exc)[:120]}))
            conn = psycopg.connect(DSN, connect_timeout=10)
            continue
        now = time.time()
        swap, free = swap_used_mb(), free_pct()
        fp = footprint_gb()
        if snap["checkpoint"] > history[-1][1]:
            last_progress = now
        history.append((now, snap["checkpoint"]))
        window = [h for h in history if h[0] >= now - 600]
        rate = 0.0
        if len(window) > 1 and window[-1][0] > window[0][0]:
            rate = (window[-1][1] - window[0][1]) / ((window[-1][0] - window[0][0]) / 60)
        print(json.dumps({
            "event": "tick", "min": round((now - start) / 60),
            "checkpoint": snap["checkpoint"], "rows_per_min": round(rate, 1),
            "query_ready": snap["query_ready"], "tickets": snap["tickets"],
            "lease_faults": snap["lease_faults"], "blocked": snap["blocked"],
            "control_ticks": snap["control_ticks"],
            "swap_used_mb": swap, "free_pct": free,
            "polymath_gb": fp["total_gb"], "budget_gb": fp["budget_gb"],
            "headroom_gb": fp["headroom_gb"]}), flush=True)

        if snap["query_ready"] >= a.target_docs:
            verdict, detail = "CONVERGED", f"{snap['query_ready']} docs query_ready"
            break

        # PRIMARY: Polymath's own footprint against its own allocation.
        # That allocation is the contract the owner set, and exceeding it
        # is a defect regardless of what else the machine is doing.
        if not fp["within_budget"]:
            over_streak += 1
        else:
            over_streak = 0
        if over_streak >= a.low_ticks:
            verdict, detail = ("BUDGET_EXCEEDED",
                               f"Polymath held {fp['total_gb']} GB against a "
                               f"{fp['budget_gb']} GB allocation for "
                               f"{over_streak} consecutive minutes")
            break

        # SECONDARY: genuine host starvation, whoever caused it. The floor
        # is deliberately low. A previous run stopped at 34% free while
        # Polymath held 6.93 GB of its 16 GB allocation -- the rest of the
        # machine was the owner's own applications, which are entitled to
        # it. Stopping there measured somebody else's memory, not ours.
        if 0 <= free < a.min_free_pct:
            low_streak += 1
        else:
            low_streak = 0
        if low_streak >= a.low_ticks:
            verdict, detail = ("HOST_STARVED",
                               f"host free memory below {a.min_free_pct}% for "
                               f"{low_streak} consecutive minutes while "
                               f"Polymath held {fp['total_gb']} GB of "
                               f"{fp['budget_gb']} GB")
            break
        if now - last_progress > a.stall_minutes * 60:
            verdict, detail = "STALLED", f"no checkpoint progress for {a.stall_minutes}m"
            break

    final = snapshot(conn, a.corpus)
    report = {
        "verdict": verdict, "detail": detail,
        "checkpoint_before": first["checkpoint"],
        "checkpoint_after": final["checkpoint"],
        "resumed": final["checkpoint"] > first["checkpoint"],
        "rows_added": final["checkpoint"] - first["checkpoint"],
        "elapsed_min": round((time.time() - start) / 60, 1),
        "polymath_gb": footprint_gb()["total_gb"],
        "budget_gb": footprint_gb()["budget_gb"],
        "lease_faults": final["lease_faults"],
        "blocked_queries": final["blocked"],
        "query_ready": final["query_ready"],
        "tickets": final["tickets"],
    }
    print(json.dumps({"event": "final", **report}, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1))
    return 0 if verdict == "CONVERGED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
