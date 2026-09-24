"""C0 fleet / receipts baseline before any code corpus exists (CODE-KNOWLEDGE-V1 C0, register 11.458).

Read-only: SELECTs on the fleet Postgres + GET /ready. Nothing is written, no model is called. Later slices compare
against this snapshot (a code corpus must not disturb the document corpora, their receipts or the fleet shape).

Run from the fleet checkout with its .env loaded:
    set -a; . ./.env; set +a
    .venv/bin/python <this file> > baseline.json
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import UTC, datetime

import psycopg


def rows(cur, sql: str, params=()) -> list[list]:
    cur.execute(sql, params)
    return [[(v.isoformat() if hasattr(v, "isoformat") else v) for v in r] for r in cur.fetchall()]


def main() -> dict:
    cur = psycopg.connect(os.environ["POLYMATH_PG_DSN"]).cursor()
    try:
        ready = json.loads(urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=5).read())
    except Exception as exc:  # noqa: BLE001 — a down orchestrator is a baseline fact, not a crash
        ready = {"error": type(exc).__name__}
    return {
        "baseline": "CODE-KNOWLEDGE-V1 C0 fleet / receipts baseline",
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ready": ready,
        "fleet_healthy_by_type": rows(cur, """
            select worker_type, count(*), count(distinct left(execution_bundle_hash, 12))
            from worker_registrations where heartbeat_at > now() - interval '60 seconds' and status = 'healthy'
            group by 1 order by 1"""),
        "fleet_bundles": rows(cur, """
            select left(execution_bundle_hash, 12), count(*) from worker_registrations
            where heartbeat_at > now() - interval '60 seconds' and status = 'healthy' group by 1"""),
        "corpora": rows(cur, """
            select c.corpus_id, c.name, c.query_enabled, c.purpose,
                   (select count(*) from documents d where d.corpus_id = c.corpus_id),
                   (select count(*) from chunks k join documents d on d.doc_id = k.doc_id
                     where d.corpus_id = c.corpus_id)
            from corpora c order by 1"""),
        "document_media_types": rows(cur, "select media_type, count(*) from documents group by 1 order by 2 desc"),
        "chunk_contract_versions": rows(cur, """
            select chunk_contract_version, count(*) from chunks group by 1 order by 2 desc limit 12"""),
        "runs_by_status": rows(cur, "select status, count(*) from runs group by 1 order by 2 desc"),
        "receipts_7d_by_kind_mode_status": rows(cur, """
            select kind, coalesce(mode, '-'), status, count(*),
                   percentile_cont(0.5) within group (order by wall_ms)::int
            from query_receipts where received_at > now() - interval '7 days'
            group by 1, 2, 3 order by 4 desc"""),
        "receipts_total": rows(cur, "select count(*), min(received_at), max(received_at) from query_receipts"),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
