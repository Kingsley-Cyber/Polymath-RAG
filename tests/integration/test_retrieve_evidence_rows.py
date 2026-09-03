"""RETRIEVE-EVIDENCE-ROWS-V1 live contract (Postgres + Qdrant + a query_ready
corpus with transcripts; skipped when the corpus is absent)."""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "orchestrator"):
    sys.path.insert(0, str(p))

CORPUS = os.environ.get("POLYMATH_EVIDENCE_TEST_CORPUS", "mark-builds-brands-v1")


def _corpus_ready() -> bool:
    try:
        from polymath_shared.db import tx
        with tx() as c:
            return bool(c.execute("SELECT 1 FROM runs WHERE corpus_id=%s AND status='query_ready' LIMIT 1", (CORPUS,)).fetchone())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _corpus_ready(), reason=f"corpus {CORPUS} not query_ready")


def _retrieve(**body):
    from orchestrator.api.retrieve import RetrieveRequest, _retrieve_impl
    return asyncio.run(_retrieve_impl(RetrieveRequest(**body)))


def test_evidence_rows_satisfy_the_agent_contract():
    out = _retrieve(query="forgetting supplements at night", corpus_id=CORPUS, limit=8, evidence=True)
    rows = out["evidence_rows"]
    assert rows and out["evidence_contract"] == "retrieve-evidence-rows-v1"
    for r in rows:
        assert r["id"] and r["text"] and r["source"] and r["title"], r
        assert "/Users/" not in r["source"] and "/Users/" not in r["title"], "a path is not an auditable title"
    chunk_rows = [r for r in rows if r["kind"] == "chunk"]
    assert chunk_rows and all("**[" not in r["text_clean"] for r in chunk_rows), "timestamps leave text_clean"
    assert any(r.get("timecode") for r in chunk_rows), "transcript rows carry a timecode range"
    assert all(r.get("evidence") for r in rows if r["kind"] == "graph_fact"), "graph facts only with provenance"


def test_explore_mode_is_breadth_over_precision():
    out = _retrieve(query="carve a sub-market inside a proven market", corpus_id=CORPUS, limit=24, mode="EXPLORE")
    rows = out["evidence_rows"]
    chunks = [r for r in rows if r["kind"] == "chunk"]
    per_doc = {}
    for r in chunks:
        per_doc[r["doc_id"]] = per_doc.get(r["doc_id"], 0) + 1
    assert chunks and max(per_doc.values()) <= 2, "explore caps chunk rows per document"
    assert len(per_doc) >= 3, "explore reaches several documents"
