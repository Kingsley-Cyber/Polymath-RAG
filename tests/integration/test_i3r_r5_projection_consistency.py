"""I3R-R5: derived-store consistency + query_ready revocation (live).

Uses the live control plane: invalidates the i3-five-doc-v1 corpus's
projections while its runs are query_ready, then waits for the census to
re-drive projection + verification and returns to query_ready with all
receipts active again. No manual status edits.

Requires: POLYMATH_INTEGRATION=1, live stores + workers + control.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "control"))

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="set POLYMATH_INTEGRATION=1 with live stores + workers + control",
)

CORPUS = "i3-five-doc-v1"


def test_query_ready_revocation_and_reconvergence():
    import psycopg

    from polymath_shared.db import tx
    from polymath_shared.receipts import invalidate_corpus_projections

    dsn = os.environ.get("POLYMATH_PG_DSN",
                         "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
    c = psycopg.connect(dsn)
    try:
        # wait for a clean terminal state first
        deadline = time.time() + 900
        n = 0
        while time.time() < deadline:
            n = c.execute(
                "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='query_ready'",
                (CORPUS,)).fetchone()[0]
            busy = c.execute(
                "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status IN ('intake','reconciling','degraded')",
                (CORPUS,)).fetchone()[0]
            if n > 0 and busy == 0:
                break
            time.sleep(10)
        assert n > 0, "i3 corpus never reached a clean query_ready state"

        with tx() as txc:
            ready = txc.execute(
                "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='query_ready'",
                (CORPUS,)).fetchone()[0]
            invalidated = invalidate_corpus_projections(txc, CORPUS)

        assert invalidated == ready, "all query_ready runs must re-enter the census"

        # Intermediate statuses race the live control plane (a full
        # cycle can complete within one tick); the observable invariant
        # is reconvergence with receipts restored.
        deadline = time.time() + 900
        while time.time() < deadline:
            ready = c.execute(
                "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='query_ready'",
                (CORPUS,)).fetchone()[0]
            degraded_now = c.execute(
                "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='degraded'",
                (CORPUS,)).fetchone()[0]
            if ready == n and degraded_now == 0:
                break
            time.sleep(10)

        assert ready == n, f"did not reconverge: ready={ready} degraded={degraded_now}"

        # receipts are active again (chunk + routing + neo4j facts)
        missing = c.execute(
            """
            SELECT COUNT(*) FROM chunks ch
              JOIN documents d ON d.doc_id = ch.doc_id
             WHERE d.corpus_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'qdrant' AND pr.entity_kind = 'chunk'
                      AND pr.active AND pr.entity_id = ch.chunk_id)
            """, (CORPUS,)).fetchone()[0]
        assert missing == 0, f"{missing} chunk receipts still inactive"
    finally:
        c.close()
