"""CHUNK-SWEEP-SCOPE-V1 — the chunk reconciler must not delete other
lanes' points. MEASURED LIVE (2026-08-30 15:14): once the chunk and
routing lanes resolved to ONE collection, str(chunk_id=None) == "None"
made every entity card / routing summary a "true orphan" and
reconcile_qdrant DELETED all 94 routing_entity cards minutes after
projection, while their receipts stayed active.
"""
from __future__ import annotations

import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import Distance, PointStruct, VectorParams  # noqa: E402

from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.projection_contracts import (  # noqa: E402
    qdrant_collection_name,
    qdrant_point_uuid,
)
from workers.verify_worker import reconcile_qdrant  # noqa: E402
from workers.verify_worker import active_contract  # noqa: E402


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def test_chunk_sweep_ignores_non_chunk_points(conn) -> None:
    corpus = f"sweep-scope-{uuid.uuid4().hex[:8]}"
    run = f"run_sweep_scope_{uuid.uuid4().hex[:8]}"
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s,%s,'t')",
                 (corpus, corpus))
    conn.execute("INSERT INTO runs (run_id, corpus_id, status, metadata) "
                 "VALUES (%s,%s,'reconciling','{}')", (run, corpus))
    collection = qdrant_collection_name(corpus, active_contract().contract_id)
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=30)
    try:
        client.create_collection(
            collection,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE))
        # one undesired, unreceipted CHUNK point (a genuine orphan) and
        # one entity-card-shaped point (chunk_id absent — another lane's)
        client.upsert(collection, wait=True, points=[
            PointStruct(id=qdrant_point_uuid("chunk_sweep_orphan"),
                        vector=[0.1, 0.2, 0.3, 0.4],
                        payload={"chunk_id": "chunk_sweep_orphan",
                                 "corpus_id": corpus,
                                 "representation_kind": "routing_child"}),
            PointStruct(id=qdrant_point_uuid("entcard_sweep_probe"),
                        vector=[0.4, 0.3, 0.2, 0.1],
                        payload={"summary_id": "entcard_sweep_probe",
                                 "chunk_id": None,
                                 "entity_id": "entity-x",
                                 "corpus_id": corpus,
                                 "representation_kind": "routing_entity"}),
        ])
        report = reconcile_qdrant(conn, run, corpus)
        # the genuine chunk orphan is swept ...
        assert "chunk_sweep_orphan" in report["orphans_in_store"]
        assert client.retrieve(collection,
                               ids=[qdrant_point_uuid("chunk_sweep_orphan")]) == []
        # ... the card is INVISIBLE to the chunk sweep and survives
        assert client.retrieve(collection,
                               ids=[qdrant_point_uuid("entcard_sweep_probe")]) != []
        assert "None" not in report["orphans_in_store"]
    finally:
        try:
            client.delete_collection(collection)
        except Exception:
            pass
        client.close()
