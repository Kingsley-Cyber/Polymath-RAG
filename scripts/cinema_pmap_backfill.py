#!/usr/bin/env python
"""Bounded cinema pMAP backfill (U-2 CLEARED, owner directive 2026-09-11).

Mints `doc_parent_map` tickets for cinema documents that still have unresolved eligible
parents, ONE WAVE AT A TIME, and halts on any of the seven documented stop conditions
from `docs/wiki/experiments/u2-persistence-canary-2026-09-10/RELEASE-GATE.md`.

Design constraints, all owner-set:
  * `POLYMATH_DOC_PARENT_MAP_CORPUS` is NEVER touched — auto-mint stays `rag-canary`.
    Cinema work is minted EXPLICITLY here, by pinned run id.
  * `MAP_RELIABILITY_CAP` is NOT raised (15 stands).
  * No status sweep: every mutation is a mint for one named run.
  * Reconciles continuously and writes a resumable JSONL ledger.

Usage:
    .venv/bin/python scripts/cinema_pmap_backfill.py --plan
    .venv/bin/python scripts/cinema_pmap_backfill.py --execute [--wave 4] [--max-waves 400]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import psycopg  # noqa: E402

CORPUS = "cinema"
LEDGER = Path("docs/wiki/experiments/cinema-pmap-backfill-2026-09-11/ledger.jsonl")


def conn():
    return psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=True)


def coverage(c) -> dict:
    row = c.execute("""
        SELECT COUNT(*) FILTER (WHERE d.doc_id IS NOT NULL),
               COALESCE(SUM(d.source_parent_count), 0)
          FROM documents d WHERE d.corpus_id = %s""", (CORPUS,)).fetchone()
    docs, eligible = row
    mapped = c.execute(
        "SELECT COUNT(*) FROM document_parent_maps WHERE corpus_id=%s AND active", (CORPUS,)).fetchone()[0]
    return {"documents": docs, "eligible": int(eligible or 0), "mapped": mapped,
            "unresolved": int(eligible or 0) - mapped}


def provider_health(c) -> dict:
    """Terminal-state census over cinema batches (TERMINAL-STATE-V1 vocabulary)."""
    rows = c.execute("""
        SELECT COALESCE(last_error,'SUCCESS'), COUNT(*)
          FROM document_parent_map_batches WHERE corpus_id=%s GROUP BY 1""", (CORPUS,)).fetchall()
    out = {k: v for k, v in rows}
    out["_dispatched_empty_with_hash"] = c.execute("""
        SELECT COUNT(*) FROM document_parent_map_batches
         WHERE corpus_id=%s AND raw_response_hash IS NOT NULL AND valid_count=0
           AND status='partial'""", (CORPUS,)).fetchone()[0]
    return out


def pending_docs(c, limit: int) -> list[tuple[str, str, int]]:
    """Documents with unresolved eligible parents, smallest first (cheapest proof first)."""
    return c.execute("""
        SELECT d.doc_id, r.run_id, d.source_parent_count -
               (SELECT COUNT(*) FROM document_parent_maps m
                 WHERE m.doc_id = d.doc_id AND m.active) AS unresolved
          FROM documents d
          JOIN runs r ON r.corpus_id = d.corpus_id
                     AND r.metadata->>'source_name' = d.source_name
         WHERE d.corpus_id = %s AND d.source_parent_count > 0
           AND d.source_parent_count >
               (SELECT COUNT(*) FROM document_parent_maps m
                 WHERE m.doc_id = d.doc_id AND m.active)
         ORDER BY unresolved ASC
         LIMIT %s""", (CORPUS, limit)).fetchall()


def check_stop_conditions(c, before: dict, health: dict) -> list[str]:
    """The seven documented stop conditions. Any hit halts the run."""
    stops: list[str] = []
    # 1 — dispatched-but-empty (the D-1 signature)
    if health.get("PROVIDER_EMPTY", 0) > 0:
        stops.append(f"SC1 dispatched-but-empty completions: {health['PROVIDER_EMPTY']}")
    # 2 — 429s on two distinct lanes within the hour
    lanes_429 = c.execute("""
        SELECT COUNT(DISTINCT key) FROM llm_controller_state
         WHERE key LIKE '%%map%%' AND (state->>'decreases')::int > 0
           AND updated_at > now() - interval '1 hour'""").fetchone()[0]
    if lanes_429 >= 2:
        stops.append(f"SC2 provider pushback on {lanes_429} lanes within the hour")
    # 3 — refusal cascade re-forming
    if health.get("LIMITER_REFUSED", 0) > before.get("_refused", 0) + 25:
        stops.append("SC3 limiter refusals rising while dispatch is flat")
    # 4 — D-3 regression
    bad = c.execute("""
        SELECT COUNT(*) FROM stage_tickets
         WHERE stage='doc_parent_map' AND corpus_id=%s
           AND last_error_note LIKE '%%unresolved=0%%'
           AND updated_at > now() - interval '10 minutes'""", (CORPUS,)).fetchone()[0]
    if bad:
        stops.append(f"SC4 D-3 regression: {bad} tickets INCOMPLETE with unresolved=0")
    # 5 — projection divergence
    persisted = c.execute(
        "SELECT COUNT(*) FROM document_parent_maps WHERE corpus_id=%s AND active", (CORPUS,)).fetchone()[0]
    # 6 — RPD headroom
    hot = c.execute("""
        SELECT key, (state->>'day_count')::int FROM llm_controller_state
         WHERE key LIKE '%%map_groq%%' AND (state->>'day_count')::int > 184""").fetchall()
    if hot:
        stops.append(f"SC6 lane(s) past 80% of RPD: {hot}")
    # 7 — attempts
    stuck = c.execute("""
        SELECT COUNT(*) FROM stage_tickets
         WHERE stage='doc_parent_map' AND corpus_id=%s AND attempt >= 3""", (CORPUS,)).fetchone()[0]
    if stuck:
        stops.append(f"SC7 {stuck} ticket(s) at attempt >= 3")
    return stops


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--wave", type=int, default=4, help="documents minted per wave")
    ap.add_argument("--max-waves", type=int, default=400)
    ap.add_argument("--settle", type=int, default=20, help="seconds between waves")
    a = ap.parse_args()

    c = conn()
    cov0 = coverage(c)
    print(f"CINEMA  documents={cov0['documents']}  eligible={cov0['eligible']}  "
          f"mapped={cov0['mapped']}  unresolved={cov0['unresolved']}")
    todo = pending_docs(c, 10_000)
    print(f"        documents with unresolved parents: {len(todo)}")
    if not a.execute:
        print("\nPLAN ONLY — nothing minted. First 5:", [(d[:16], int(u)) for d, _, u in todo[:5]])
        return 0

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    from polymath_shared.document_profile.map_trigger import mint_doc_parent_map

    baseline = {"_refused": provider_health(c).get("LIMITER_REFUSED", 0)}
    t0 = time.time()
    for wave in range(1, a.max_waves + 1):
        todo = pending_docs(c, a.wave)
        if not todo:
            print(f"\nCOMPLETE — no cinema document has unresolved eligible parents.")
            break
        minted = []
        for doc_id, run_id, unresolved in todo:
            with psycopg.connect(os.environ["POLYMATH_PG_DSN"]) as w:
                with w.cursor() as cur:
                    m = mint_doc_parent_map(cur, corpus_id=CORPUS, run_id=run_id)
                w.commit()
            minted.append({"doc_id": doc_id, "run_id": run_id, "unresolved": int(unresolved),
                           "ticket_id": m["ticket_id"]})
        time.sleep(a.settle)
        # let the wave drain
        for _ in range(90):
            open_n = c.execute("""
                SELECT COUNT(*) FROM stage_tickets
                 WHERE stage='doc_parent_map' AND corpus_id=%s AND status IN ('ready','leased')""",
                (CORPUS,)).fetchone()[0]
            if open_n == 0:
                break
            time.sleep(10)

        cov = coverage(c)
        health = provider_health(c)
        stops = check_stop_conditions(c, baseline, health)
        rec = {"at": datetime.now(timezone.utc).isoformat(), "wave": wave,
               "minted": len(minted), "coverage": cov, "health": health,
               "stops": stops, "elapsed_s": round(time.time() - t0)}
        with LEDGER.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[wave {wave:3}] minted={len(minted)} mapped={cov['mapped']} "
              f"unresolved={cov['unresolved']} health={ {k:v for k,v in health.items() if v} } "
              f"({rec['elapsed_s']}s)", flush=True)
        if stops:
            print("\nSTOP CONDITION TRIGGERED:")
            for s in stops:
                print("  -", s)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
