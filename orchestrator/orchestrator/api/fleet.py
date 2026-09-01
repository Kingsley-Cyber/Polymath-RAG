"""FLEET-BOARD-V1 — the control plane's live answer to "who is doing
what, and how many jobs" (owner 2026-09-01).

Read-only aggregation of state that already exists — the provider
roster (registry), per-lane AIMD limiter state (llm_controller_state),
worker registrations/heartbeats, the ticket queue, and enrichment
coverage. No new state, no scheduling authority: visibility only.
"""
from __future__ import annotations

import time

from fastapi import APIRouter

from polymath_shared.db import tx

router = APIRouter()


def _lane_rows() -> list[dict]:
    from polymath_shared.llm_extraction.pool import (
        cloud_endpoints,
        stage_pin,
    )
    pins = stage_pin("parent_enrichment") or []
    rows = []
    for e in cloud_endpoints():
        rows.append({
            "name": e.name,
            "model": e.model,
            "role": ("enrichment" if e.name in pins
                     else "extraction" if not getattr(e, "dedicated", False)
                     else "dedicated"),
            "structured": getattr(e, "structured", None),
        })
    return rows


@router.get("/fleet")
def fleet() -> dict:
    lanes = _lane_rows()
    with tx() as conn:
        # per-lane AIMD state: key shapes like 'llm_cloud[groq1]'
        limiter = {}
        for key, state, updated in conn.execute(
                "SELECT key, state, updated_at FROM llm_controller_state"):
            limiter[key] = {**(state or {}),
                            "updated_at": updated.isoformat()}
        workers = [{
            "worker_id": w[0], "worker_type": w[1], "status": w[2],
            "processed": w[3], "current_ticket": w[4],
            "last_error": w[5],
            "heartbeat_age_s": (int(time.time() - w[6].timestamp())
                                if w[6] else None),
        } for w in conn.execute(
            """SELECT worker_id, worker_type, status, processed_count,
                      current_ticket, last_error, heartbeat_at
                 FROM worker_registrations
                ORDER BY heartbeat_at DESC NULLS LAST LIMIT 40""")]
        queue = [{"stage": s, "status": st, "count": n}
                 for s, st, n in conn.execute(
                     """SELECT stage, status, count(*) FROM stage_tickets
                         WHERE status IN ('pending','ready','leased',
                                          'failed')
                         GROUP BY 1, 2 ORDER BY 1, 2""")]
        enrichment = dict(conn.execute(
            """SELECT pe.status, count(*) FROM parent_enrichments pe
                JOIN chunks ch ON ch.chunk_id = pe.parent_id
                GROUP BY 1""").fetchall())
        parents_total = conn.execute(
            "SELECT count(*) FROM chunks WHERE tier='parent'"
        ).fetchone()[0]
    for lane in lanes:
        for key, st in limiter.items():
            if f"[{lane['name']}]" in key:
                lane["limiter"] = st
                break
    return {"lanes": lanes, "workers": workers, "queue": queue,
            "enrichment": {"parents": parents_total, **enrichment}}
