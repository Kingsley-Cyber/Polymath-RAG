#!/usr/bin/env python3
"""DOCUMENT-PROFILE-V1 step 5 — backfill: mint a `doc_profile` ticket for every run whose document has landed, and
report progress. Idempotent (ON CONFLICT on the ticket id). The profile worker (fleet slot `doc_profile`, demand-
driven) does the work; this script only creates the tickets and reads the receipts.

  .venv/bin/python scripts/backfill_document_profiles.py --corpus cinema --dry-run      # what would be minted
  .venv/bin/python scripts/backfill_document_profiles.py --corpus cinema                # mint (READY + outbox event)
  .venv/bin/python scripts/backfill_document_profiles.py --corpus cinema --status       # tickets / artifacts / points / lanes

Prerequisites: the six GROQ_API_KEY_n values in .env (tier 0) — without them every call falls to the Gemini fallbacks;
the fleet booted with the `doc_profile` slot (control/process_supervisor FLEET).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "control", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.db import tx  # noqa: E402

STAGE = "doc_profile"
EVENT_TYPE = "doc_profile.v1"


def landed_runs(conn, corpus_id: str) -> list[tuple[str, str, str]]:
    """(run_id, doc_id, source_name) for every run whose intake document exists — one per document."""
    return conn.execute(
        """SELECT DISTINCT ON (d.doc_id) r.run_id, d.doc_id, d.source_name
             FROM runs r JOIN documents d ON d.corpus_id = r.corpus_id
                                          AND d.source_name = (r.metadata->'intake_payload'->>'source_name')
            WHERE r.corpus_id = %s
            ORDER BY d.doc_id, r.created_at DESC""", (corpus_id,)).fetchall()


def mint(conn, corpus_id: str, *, dry_run: bool, limit: int | None) -> dict:
    from control.tickets import _emit_ticket_event, ticket_id
    rows = landed_runs(conn, corpus_id)
    if limit:
        rows = rows[:limit]
    minted = skipped = 0
    for run_id, doc_id, _name in rows:
        tid = ticket_id(run_id, STAGE)
        if conn.execute("SELECT 1 FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone():
            skipped += 1
            continue
        if dry_run:
            minted += 1
            continue
        conn.execute(
            """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status)
               VALUES (%s, %s, %s, %s, %s, 'pending') ON CONFLICT (run_id, stage, generation) DO NOTHING""",
            (tid, run_id, corpus_id, STAGE, EVENT_TYPE))
        _emit_ticket_event(conn, tid, run_id, STAGE)          # READY + outbox event (the only claimable path)
        minted += 1
    return {"corpus": corpus_id, "documents": len(rows), "minted": minted, "already_had_ticket": skipped, "dry_run": dry_run}


def rearm(conn, corpus_id: str, *, limit: int | None) -> dict:
    """Re-arm the doc_profile stage for landed runs: reset each existing ticket to READY and
    re-emit its outbox event (the sanctioned re-processing path, `_emit_ticket_event`) so the
    fleet regenerates the profile — under vNext when POLYMATH_DOC_PROFILE_VNEXT=1. Idempotent;
    only re-arms runs that already have a doc_profile ticket (fresh runs still go through mint)."""
    from control.tickets import _emit_ticket_event, ticket_id
    rows = landed_runs(conn, corpus_id)
    if limit:
        rows = rows[:limit]
    rearmed = missing = 0
    for run_id, _doc_id, _name in rows:
        tid = ticket_id(run_id, STAGE)
        if not conn.execute("SELECT 1 FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone():
            missing += 1
            continue
        _emit_ticket_event(conn, tid, run_id, STAGE)      # READY + re-armed (claimable) outbox event
        rearmed += 1
    return {"corpus": corpus_id, "documents": len(rows), "rearmed": rearmed, "no_ticket_use_mint": missing}


def status(conn, corpus_id: str) -> dict:
    tickets = dict(conn.execute(
        "SELECT status, count(*) FROM stage_tickets WHERE corpus_id=%s AND stage=%s GROUP BY 1", (corpus_id, STAGE)).fetchall())
    arts = conn.execute(
        """SELECT a.payload FROM artifacts a JOIN runs r ON r.run_id=a.run_id
            WHERE r.corpus_id=%s AND a.stage=%s""", (corpus_id, STAGE)).fetchall()
    quality, lanes, valid, vectors = [], Counter(), Counter(), Counter()
    for (payload,) in arts:
        p = payload if isinstance(payload, dict) else json.loads(payload)
        dp, pq = p.get("doc_profile") or {}, p.get("doc_profile_qdrant") or {}
        if dp:
            quality.append(dp.get("quality") or 0.0); lanes[dp.get("lane")] += 1; valid[bool(dp.get("valid"))] += 1
        for k, n in (pq.get("vectors") or {}).items():
            vectors[k] += int(n or 0)
    holds = conn.execute(
        """SELECT left(last_error_note, 90), count(*) FROM stage_tickets WHERE corpus_id=%s AND stage=%s
            AND last_error_note IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 5""", (corpus_id, STAGE)).fetchall()
    out = {"corpus": corpus_id, "tickets": tickets, "profiles_written": len(arts), "valid": dict(valid),
           "quality_p50": (sorted(quality)[len(quality) // 2] if quality else None), "lanes": dict(lanes),
           "vectors_total": dict(vectors), "recent_holds": holds}
    try:
        from polymath_shared.embedding_contracts import active_contract
        from polymath_shared.document_profile.projection import collection_name
        from polymath_shared.settings import get_settings
        from qdrant_client import QdrantClient
        c = QdrantClient(url=get_settings().stores.qdrant_url, timeout=10)
        name = collection_name(active_contract().contract_id)
        out["profile_points"] = c.count(name, exact=True).count if c.collection_exists(name) else 0
        out["collection"] = name
        c.close()
    except Exception as exc:  # noqa: BLE001
        out["profile_points"] = f"n/a ({type(exc).__name__})"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--rearm", action="store_true",
                    help="re-arm existing doc_profile tickets (re-emit event) to regenerate — vNext when the flag is set")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    with tx() as conn:
        if a.status:
            out = status(conn, a.corpus)
        elif a.rearm:
            out = rearm(conn, a.corpus, limit=a.limit)
        else:
            out = mint(conn, a.corpus, dry_run=a.dry_run, limit=a.limit)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
