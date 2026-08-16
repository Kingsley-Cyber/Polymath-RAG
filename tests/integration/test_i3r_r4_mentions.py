"""I3R-R4: durable mentions/entities integration test.

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up + db-migrate).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="set POLYMATH_INTEGRATION=1 with live stores",
)


def test_factless_proposals_become_durable_mentions():
    import psycopg

    from polymath_shared.contracts import CoreType, EntitySpan
    from workers.extract_worker import _persist_mentions

    corpus = "i3r-r4-test"
    doc = "doc_r4test"
    spans = [
        EntitySpan(doc_id=doc, chunk_id="chunk_r4", start=0, end=19,
                   text="Northwind Outfitters", core_type=CoreType("Organization"),
                   score=0.97, extractor_version="test"),
        EntitySpan(doc_id=doc, chunk_id="chunk_r4", start=20, end=25,
                   text="pilot", core_type=CoreType("Event"),
                   score=0.6, extractor_version="test"),
    ]
    conn = psycopg.connect(os.environ.get(
        "POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"))
    try:
        _persist_mentions(conn, corpus, doc, spans)
        conn.commit()
        rows = conn.execute(
            """SELECT surface, admission_class, entity_id FROM mentions
               WHERE doc_id=%s ORDER BY surface""", (doc,)).fetchall()
        assert [r[0] for r in rows] == ["Northwind Outfitters", "pilot"]
        northwind = next(r for r in rows if r[0] == "Northwind Outfitters")
        pilot = next(r for r in rows if r[0] == "pilot")
        # referential entity durable WITHOUT fact participation
        assert northwind[1] in ("GLOBAL", "CORPUS_SCOPED", "DOCUMENT_SCOPED")
        assert northwind[2] is not None
        e_rows = conn.execute(
            "SELECT core_type, admission_class FROM entities WHERE entity_id=%s",
            (northwind[2],)).fetchall()
        assert e_rows
        # MENTION_ONLY: durable mention, NO entities row
        assert pilot[1] == "MENTION_ONLY"
        assert pilot[2] is None
    finally:
        conn.execute("DELETE FROM mentions WHERE doc_id=%s", (doc,))
        conn.execute("DELETE FROM entities WHERE entity_id IN ("
                     "SELECT entity_id FROM mentions WHERE doc_id=%s)", (doc,))
        conn.commit()
        conn.close()
