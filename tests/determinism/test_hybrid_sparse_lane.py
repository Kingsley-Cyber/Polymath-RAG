"""R2 (2026-09-06): the v1 HYBRID child lexical lane (`hybrid-retrieval-v1`, still the
authority for /retrieve HYBRID, /ask consumers and chat `retrieval: v1`).

Defect fixed: `_sparse_lexical_search` iterated `_corpus_collections(...)` — a dict
corpus_id → collection name — and passed the KEYS to Qdrant as collection names, so
every sparse query 404'd and `_lexical_search` silently fell back to the in-memory
Postgres scan on every turn. These tests pin: (1) the mapped collection is what the
sparse lane queries and no chunk scan runs when it answers; (2) a genuine failure
still degrades to the scan — and says so in `degradations()`; (3) an empty sparse
result is counted as a fallback too (silent-fallback accounting)."""
from __future__ import annotations

import pathlib
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("", "shared", "orchestrator"):
    p = str(ROOT / sub) if sub else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import fast as fast_api  # noqa: E402
from orchestrator.api import hybrid as hybrid_api  # noqa: E402


class _Points:
    def __init__(self, points):
        self.points = points


class FakeQdrant:
    """Records the collection each sparse query targets; answers with one routing child."""
    calls: list[dict] = []
    fail: Exception | None = None
    empty: bool = False

    def __init__(self, url=None, timeout=None):
        pass

    def query_points(self, **kw):
        FakeQdrant.calls.append(kw)
        if FakeQdrant.fail is not None:
            raise FakeQdrant.fail
        if FakeQdrant.empty:
            return _Points([])
        return _Points([SimpleNamespace(score=7.5, payload={"doc_id": "d1", "parent_id": "p1", "chunk_id": "k1",
                                                             "source_name": "book.md", "text": "the chroma keyer chapter"})])

    def close(self):
        pass


class FakeConn:
    sql: list[str] = []

    def execute(self, sql, params=None):
        FakeConn.sql.append(" ".join(sql.split()))
        if "FROM chunks" in sql:
            return SimpleNamespace(fetchall=lambda: [("k9", "d9", "p9", "chroma keyer text from the scan")])
        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: None)


@contextmanager
def _fake_tx():
    yield FakeConn()


@pytest.fixture(autouse=True)
def _wire(monkeypatch):
    FakeQdrant.calls, FakeQdrant.fail, FakeQdrant.empty, FakeConn.sql = [], None, False, []
    monkeypatch.setattr(hybrid_api, "QdrantClient", FakeQdrant)
    monkeypatch.setattr(hybrid_api, "tx", _fake_tx)
    monkeypatch.setattr(hybrid_api, "get_settings", lambda: SimpleNamespace(stores=SimpleNamespace(qdrant_url="http://fake:6334")))
    import polymath_shared.generation as gen
    monkeypatch.setattr(gen, "hidden_generations", lambda conn, corpus_id: [])
    fast_api._begin_retrieval()
    yield


def test_sparse_lane_queries_the_mapped_collection_and_no_postgres_scan_runs():
    hits = hybrid_api._lexical_search("chroma keyer", "cinema", 5)
    expected = fast_api._corpus_collections(["cinema"])["cinema"]
    assert FakeQdrant.calls and FakeQdrant.calls[0]["collection_name"] == expected != "cinema"   # the value, not the key
    assert [h.chunk_id for h in hits] == ["k1"] and hits[0].representation_kind == "child_lexical"
    assert not any("FROM chunks" in s for s in FakeConn.sql)                                     # no in-memory scan
    assert fast_api.degradations() == []                                                       # nothing degraded


def test_sparse_outage_degrades_to_the_scan_and_is_counted():
    FakeQdrant.fail = RuntimeError("Not found: Collection `x` doesn't exist!")
    hits = hybrid_api._lexical_search("chroma keyer", "cinema", 5)
    assert [h.chunk_id for h in hits] == ["k9"] and any("FROM chunks" in s for s in FakeConn.sql)  # genuine degradation path
    deg = fast_api.degradations()
    assert [d["component"] for d in deg] == ["sparse_lexical"] and deg[0]["reason"] == "sparse_error:RuntimeError"


def test_empty_sparse_result_falls_back_and_is_counted_as_sparse_empty():
    FakeQdrant.empty = True
    hits = hybrid_api._lexical_search("chroma keyer", "cinema", 5)
    assert [h.chunk_id for h in hits] == ["k9"]
    assert [(d["component"], d["reason"]) for d in fast_api.degradations()] == [("sparse_lexical", "sparse_empty")]
    fast_api._begin_retrieval()                                                                # per-request state resets
    assert fast_api.degradations() == []
