"""SPARSE-BM25-V1 migration: give an EXISTING routing collection the named
`bm25` sparse vector (qdrant 1.13 cannot add sparse config post-creation —
measured 400 "Not existing vector name").

Copy-out -> recreate sparse-native -> copy-back with sparse computed from
each point's payload text (dense vectors preserved verbatim — zero
re-embedding). Owner-gated: pass --apply; the default is a dry run.

Usage:
  .venv/bin/python scripts/migrate_routing_sparse.py <corpus_id> [--apply]
"""
import sys

sys.path.insert(0, "shared")

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import (  # noqa: E402
    Distance,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT  # noqa: E402
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.sparse_bm25 import SPARSE_VECTOR_NAME, sparse_vector  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    corpus_id = sys.argv[1]
    apply = "--apply" in sys.argv
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    name = qdrant_collection_name(corpus_id, NEURAL_EMBED_CONTRACT.contract_id)
    try:
        info = client.get_collection(name)
    except Exception as exc:
        print(f"collection {name} not found: {exc}")
        return 1
    sparse_cfg = getattr(info.config.params, "sparse_vectors", None) or {}
    if SPARSE_VECTOR_NAME in sparse_cfg:
        print(f"{name}: already sparse-capable; nothing to do")
        return 0
    dim = info.config.params.vectors.size
    total = client.count(name).count
    print(f"{name}: {total} points, dense dim {dim}, sparse ABSENT")
    if not apply:
        print("dry run — pass --apply to migrate")
        return 0

    # copy-out (payload + dense vectors)
    points, batch, offset = [], None, None
    while True:
        batch, offset = client.scroll(name, limit=1024, offset=offset,
                                      with_payload=True, with_vectors=True)
        points.extend(batch)
        if offset is None:
            break
    print(f"copied out {len(points)} points")
    assert len(points) == total, "scroll under-read; refusing to recreate"

    client.delete_collection(name)
    client.create_collection(
        name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF)},
    )
    out = []
    for p in points:
        dense = p.vector if isinstance(p.vector, list) else (p.vector or {}).get("")
        text = (p.payload or {}).get("text") or ""
        idx, vals = sparse_vector(text)
        out.append(PointStruct(
            id=p.id,
            vector={"": dense,
                    SPARSE_VECTOR_NAME: SparseVector(indices=idx, values=vals)},
            payload=p.payload))
        if len(out) >= 256:
            client.upsert(name, points=out, wait=True)
            out = []
    if out:
        client.upsert(name, points=out, wait=True)
    after = client.count(name).count
    print(f"recreated {name}: {after}/{total} points, sparse ON")
    return 0 if after == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
