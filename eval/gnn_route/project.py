"""GNN-RETRIEVAL-V1 — PROJECT graph-enriched PARENT vectors into the ISOLATED experimental Qdrant collection (plan §12–§13).

    polymath_gnn_parent_<embedding_contract>_<gnn_contract>        one collection per (family, variant); the production parent-MAP
                                                                    collection is never written (G8 / G9)
Payload: representation_kind=experimental_gnn_parent, corpus_id, doc_id, parent_id, embedding_contract, gnn_contract, graph_snapshot_id,
model_digest. Point ids are deterministic (uuid5 over corpus | parent | gnn_contract). Removing the experiment = dropping these
collections (G19): no ingestion, no extraction, no production projection is touched.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for sub in ("shared",):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import gnn_route as gr  # noqa: E402

NAMESPACE = uuid.UUID("7f3d2c1e-5a6b-4c8d-9e0f-1a2b3c4d5e6f")
PRODUCTION_PREFIXES = ("polymath_document_parent_maps", "polymath_document_profile", "polymath_document_profiles")


def point_id(corpus_id: str, parent_id: str, contract: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{corpus_id}|{parent_id}|{contract}"))


def assert_isolated(collection: str) -> None:
    if not collection.startswith(gr.COLLECTION_PREFIX) or any(collection.startswith(p) for p in PRODUCTION_PREFIXES):
        raise RuntimeError(f"refusing to write a non-experimental collection: {collection}")


def project(client, snap, z_parent: np.ndarray, *, family: str, variant: str, model_digest: str, recreate: bool = True, batch: int = 512, log=print) -> dict:
    from qdrant_client import models as M
    contract = gr.gnn_contract(family, variant)
    collection = gr.collection_name(snap.embedding_contract, contract)
    assert_isolated(collection)
    dim = int(z_parent.shape[1])
    if dim != snap.dim:
        raise RuntimeError(f"projected dim {dim} != embedding dim {snap.dim}")
    if recreate:
        client.recreate_collection(collection, vectors_config=M.VectorParams(size=dim, distance=M.Distance.COSINE))
        for key in ("representation_kind", "corpus_id", "doc_id", "parent_id"):
            client.create_payload_index(collection, field_name=key, field_schema=M.PayloadSchemaType.KEYWORD)
    n = 0
    present = (np.abs(z_parent).sum(axis=1) > 0)
    for start in range(0, len(snap.parent_ids), batch):
        pts = []
        for i in range(start, min(start + batch, len(snap.parent_ids))):
            if not present[i]:
                continue
            pid = snap.parent_ids[i]
            pts.append(M.PointStruct(id=point_id(snap.corpus_id, pid, contract), vector=z_parent[i].astype(np.float32).tolist(),
                                     payload={"representation_kind": gr.PAYLOAD_KIND, "corpus_id": snap.corpus_id, "doc_id": snap.parent_doc[i], "parent_id": pid,
                                              "embedding_contract": snap.embedding_contract, "gnn_contract": contract, "graph_snapshot_id": snap.graph_snapshot_id,
                                              "model_digest": model_digest}))
        if pts:
            client.upsert(collection, points=pts, wait=True)
            n += len(pts)
    info = client.get_collection(collection)
    log(f"[project] {collection}: {n} parents upserted ({int(getattr(info, 'points_count', 0) or 0)} points)")
    return {"collection": collection, "gnn_contract": contract, "points": n, "dim": dim, "graph_snapshot_id": snap.graph_snapshot_id, "model_digest": model_digest}
