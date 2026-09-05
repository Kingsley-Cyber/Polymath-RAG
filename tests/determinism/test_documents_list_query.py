"""DOCUMENTS-LIST-SUBQUERY-V1 — GET /documents must not cross-join chunks with
enrichments. Measured 2026-09-05: 80 s per request on a 67-document corpus,
the Files view showed nothing. Pins: (1) the endpoint's SQL uses correlated
subqueries, never a chunks × parent_enrichments join; (2) on the dev store the
numbers equal the old aggregate and the query finishes fast."""
from __future__ import annotations

import inspect
import os
import pathlib
import sys
import time

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator", "control"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

DSN = os.environ.get("POLYMATH_TEST_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

OLD_SQL = """
SELECT d.doc_id,
       COUNT(DISTINCT c.chunk_id) FILTER (WHERE c.tier='child') AS children,
       COUNT(DISTINCT c.parent_id) FILTER (WHERE c.tier='child') AS parents,
       COUNT(DISTINCT pe.parent_id) FILTER (WHERE pe.status='READY') AS enriched
  FROM documents d
  LEFT JOIN chunks c ON c.doc_id = d.doc_id
  LEFT JOIN parent_enrichments pe ON pe.doc_id = d.doc_id
 WHERE d.corpus_id = %s
 GROUP BY d.doc_id"""

NEW_SQL = """
SELECT d.doc_id,
       (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id AND c.tier = 'child') AS children,
       (SELECT COUNT(DISTINCT c.parent_id) FROM chunks c WHERE c.doc_id = d.doc_id AND c.tier = 'child') AS parents,
       (SELECT COUNT(DISTINCT pe.parent_id) FROM parent_enrichments pe WHERE pe.doc_id = d.doc_id AND pe.status = 'READY') AS enriched
  FROM documents d
 WHERE d.corpus_id = %s"""


def test_endpoint_sql_has_no_cross_join():
    from orchestrator.api import ui
    src = inspect.getsource(ui.documents)
    assert "LEFT JOIN chunks c ON c.doc_id = d.doc_id" not in src, "the documents listing cross-joins chunks again"
    assert "LEFT JOIN parent_enrichments pe ON pe.doc_id = d.doc_id" not in src
    assert "(SELECT COUNT(*) FROM chunks c" in src


def test_subquery_form_matches_aggregate_and_is_fast():
    try:
        conn = psycopg.connect(DSN, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"dev postgres not reachable: {exc}")
    with conn:
        corpus = conn.execute(
            """SELECT d.corpus_id FROM documents d JOIN chunks c ON c.doc_id = d.doc_id
                GROUP BY d.corpus_id ORDER BY count(*) DESC LIMIT 1""").fetchone()
        if not corpus:
            pytest.skip("no chunked corpus on this store")
        cid = corpus[0]
        t0 = time.perf_counter()
        new = {r[0]: tuple(r[1:]) for r in conn.execute(NEW_SQL, (cid,)).fetchall()}
        new_s = time.perf_counter() - t0
        assert new_s < 5.0, f"subquery listing took {new_s:.1f}s on {cid}"
        # the old aggregate is only checked on a bounded sample (it is the slow one)
        sample = list(new)[:3]
        old = {r[0]: tuple(r[1:]) for r in conn.execute(
            OLD_SQL.replace("WHERE d.corpus_id = %s", "WHERE d.corpus_id = %s AND d.doc_id = ANY(%s)"), (cid, sample)).fetchall()}
        for doc in sample:
            assert old[doc] == new[doc], f"{doc}: old {old[doc]} != new {new[doc]}"
