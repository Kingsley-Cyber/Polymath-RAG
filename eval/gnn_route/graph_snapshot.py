"""GNN-RETRIEVAL-V1 — the deterministic heterograph SNAPSHOT of one corpus, from the substrate Polymath already produced.

Read-only over the three stores; nothing is inferred, nothing is invented:
  ENTITY  = entity ids that have a `routing_entity` vector (Qdrant)              h = that vector
  CHILD   = chunk ids that have a `routing_child` vector (Qdrant)                 h = that vector
  PARENT  = parent ids of the corpus's chunks (Postgres `chunks`)                 h = the parent-MAP vector (Qdrant) — missing ones are recorded
  E→E     = accepted relations projected to Neo4j (`(:Entity)-[:REL]->(:Entity)`), restricted to the corpus's entities; the predicate is kept,
            no confidence exists on the projection and none is fabricated
  E→C     = Postgres `mentions` (entity_id, chunk_id, doc_id) with a canonical entity id
  C→P     = Postgres `chunks` (chunk_id, parent_id, doc_id) — the existing hierarchy, no heuristic

Indexes are assigned over SORTED ids (never database order). `graph_snapshot_id` is a sha256 over the sorted node keys and the sorted
edge triples — content identity, not a timestamp. The arrays live OUTSIDE the repository (`~/PolymathRuntime/gnn_route/<corpus>/<id>/`);
only the manifest is small enough to keep beside the experiment record.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

SNAPSHOT_CONTRACT = "gnn-graph-snapshot-v1"
RUNTIME_DIR = Path(os.environ.get("POLYMATH_GNN_RUNTIME_DIR", str(Path.home() / "PolymathRuntime" / "gnn_route")))
EDGE_TYPES = ("entity_entity", "entity_child", "child_parent")


@dataclass
class Snapshot:
    corpus_id: str
    embedding_contract: str
    dim: int
    entity_ids: list[str]
    child_ids: list[str]
    parent_ids: list[str]
    x_entity: np.ndarray            # (E, D) float32; a zero row where the vector is missing (see `missing`)
    x_child: np.ndarray             # (C, D)
    x_parent: np.ndarray            # (P, D)
    ee: np.ndarray                  # (n, 2) int32 entity→entity indexes
    ee_predicate: list[str]         # relation type per ee edge (sorted with the edge)
    ec: np.ndarray                  # (n, 2) int32 entity→child
    cp: np.ndarray                  # (n, 2) int32 child→parent
    child_doc: list[str]            # doc_id per child index
    parent_doc: list[str]           # doc_id per parent index
    missing: dict[str, int] = field(default_factory=dict)
    graph_snapshot_id: str = ""

    def manifest(self, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        degree_e = np.bincount(self.ee[:, 0], minlength=len(self.entity_ids)) if len(self.ee) else np.zeros(len(self.entity_ids), dtype=int)
        preds: dict[str, int] = {}
        for p in self.ee_predicate:
            preds[p] = preds.get(p, 0) + 1
        return {"contract": SNAPSHOT_CONTRACT, "corpus_id": self.corpus_id, "embedding_contract": self.embedding_contract, "dim": self.dim,
                "graph_snapshot_id": self.graph_snapshot_id,
                "node_counts": {"entity": len(self.entity_ids), "child": len(self.child_ids), "parent": len(self.parent_ids)},
                "edge_counts": {"entity_entity": int(len(self.ee)), "entity_child": int(len(self.ec)), "child_parent": int(len(self.cp))},
                "predicates": dict(sorted(preds.items(), key=lambda kv: (-kv[1], kv[0]))[:40]),
                "missing_vectors": dict(self.missing),
                "orphans": {"entities_without_relation": int((degree_e == 0).sum()) if len(self.entity_ids) else 0,
                            "children_without_mention": int(len(self.child_ids) - len(set(self.ec[:, 1].tolist()))) if len(self.ec) else len(self.child_ids),
                            "parents_without_child": int(len(self.parent_ids) - len(set(self.cp[:, 1].tolist()))) if len(self.cp) else len(self.parent_ids)},
                **(extra or {})}


def content_id(entity_ids: Iterable[str], child_ids: Iterable[str], parent_ids: Iterable[str], edges: Iterable[tuple[str, str, str, str]]) -> str:
    h = hashlib.sha256()
    for name, ids in (("entity", entity_ids), ("child", child_ids), ("parent", parent_ids)):
        h.update(f"#{name}\n".encode()); h.update("\n".join(sorted(ids)).encode()); h.update(b"\n")
    h.update(b"#edges\n"); h.update("\n".join("\t".join(e) for e in sorted(edges)).encode())
    return "gs_" + h.hexdigest()[:24]


# ─────────────────────────────────────────────────────────── store readers (read-only)
def _pg_rows(dsn: str, sql: str, args: tuple) -> list[tuple]:
    import psycopg
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def _qdrant_vectors(client, collection: str, must: list, *, id_key: str, page: int = 1024, extra_keys: tuple[str, ...] = ()) -> dict[str, tuple[np.ndarray, dict]]:
    from qdrant_client import models as M
    out: dict[str, tuple[np.ndarray, dict]] = {}
    offset = None
    flt = M.Filter(must=must)
    while True:
        pts, offset = client.scroll(collection, scroll_filter=flt, limit=page, offset=offset, with_payload=True, with_vectors=True)
        for p in pts:
            key = str((p.payload or {}).get(id_key) or "")
            vec = p.vector
            if isinstance(vec, dict):                        # named vectors: the unnamed dense one ("") is the routing vector; sparse (bm25) is not
                vec = vec.get("") if "" in vec else next((v for v in vec.values() if isinstance(v, list)), None)
            if key and vec is not None:
                out[key] = (np.asarray(vec, dtype=np.float32), {k: (p.payload or {}).get(k) for k in extra_keys})
        if offset is None:
            break
    return out


def build_snapshot(corpus_id: str, *, progress: bool = True) -> Snapshot:
    from qdrant_client import models as M
    from qdrant_client import QdrantClient
    from polymath_shared.settings import get_settings
    from polymath_shared.stores import neo4j_driver
    from polymath_shared.embedding_contracts import active_contract
    from orchestrator.api.fast import _corpus_collections
    from polymath_shared.document_profile import parent_map_projection as pmp

    t0 = time.perf_counter()
    dsn = os.environ["POLYMATH_PG_DSN"]
    contract = active_contract().contract_id
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    collection = _corpus_collections([corpus_id])[corpus_id]
    say = (lambda *a: print("[snapshot]", *a, flush=True)) if progress else (lambda *a: None)

    # C→P from the hierarchy, E→C from mentions (Postgres, read-only)
    cp_rows = _pg_rows(dsn, "SELECT ch.chunk_id, ch.parent_id, ch.doc_id FROM chunks ch JOIN documents d ON d.doc_id = ch.doc_id "
                             "WHERE d.corpus_id = %s AND ch.parent_id IS NOT NULL", (corpus_id,))
    ec_rows = _pg_rows(dsn, "SELECT entity_id, chunk_id, doc_id FROM mentions WHERE corpus_id = %s AND entity_id IS NOT NULL AND chunk_id IS NOT NULL", (corpus_id,))
    say(f"postgres: {len(cp_rows)} chunk→parent, {len(ec_rows)} mentions")
    # vectors (Qdrant, read-only)
    corpus_must = [M.FieldCondition(key="corpus_id", match=M.MatchValue(value=corpus_id))]
    kind = lambda k: [M.FieldCondition(key="representation_kind", match=M.MatchValue(value=k))] + corpus_must  # noqa: E731
    child_vec = _qdrant_vectors(client, collection, kind("routing_child"), id_key="chunk_id", extra_keys=("doc_id", "parent_id"))
    say(f"qdrant: {len(child_vec)} routing_child vectors")
    entity_vec = _qdrant_vectors(client, collection, kind("routing_entity"), id_key="entity_id")
    say(f"qdrant: {len(entity_vec)} routing_entity vectors")
    parent_vec = _qdrant_vectors(client, pmp.collection_name(contract), corpus_must, id_key="parent_id", extra_keys=("doc_id",))
    say(f"qdrant: {len(parent_vec)} parent-MAP vectors")
    dim = int(next(iter(child_vec.values()))[0].shape[0])

    # node sets: CHILD = chunks with a routing vector; PARENT = parents of the corpus's chunks; ENTITY = mentioned entities with a vector
    child_parent = {str(c): (str(p), str(d)) for c, p, d in cp_rows}
    child_ids = sorted(c for c in child_parent if c in child_vec)
    parent_doc_map: dict[str, str] = {}
    for c in child_ids:
        p, d = child_parent[c]
        parent_doc_map.setdefault(p, d)
    parent_ids = sorted(parent_doc_map)
    mentioned = {str(e) for e, c, _ in ec_rows if str(c) in child_parent}
    entity_ids = sorted(e for e in mentioned if e in entity_vec)
    e_ix = {e: i for i, e in enumerate(entity_ids)}; c_ix = {c: i for i, c in enumerate(child_ids)}; p_ix = {p: i for i, p in enumerate(parent_ids)}
    missing = {"entity_without_vector": len(mentioned - set(entity_ids)), "child_without_vector": len(set(child_parent) - set(child_ids)),
               "parent_without_map_vector": sum(1 for p in parent_ids if p not in parent_vec)}
    # E→E from Neo4j (the accepted projection), restricted to the corpus's entity set
    ee_set: set[tuple[str, str, str]] = set()
    with neo4j_driver() as drv, drv.session() as sess:
        for rec in sess.run("MATCH (s:Entity)-[r:REL]->(o:Entity) RETURN s.entity_id AS s, coalesce(r.predicate, 'related_to') AS p, o.entity_id AS o"):
            s_, p_, o_ = str(rec["s"]), str(rec["p"]), str(rec["o"])
            if s_ in e_ix and o_ in e_ix and s_ != o_:
                ee_set.add((s_, p_, o_))
    say(f"neo4j: {len(ee_set)} accepted entity→entity relations inside the corpus")
    ee_sorted = sorted(ee_set)
    ec_sorted = sorted({(str(e), str(c)) for e, c, _ in ec_rows if str(e) in e_ix and str(c) in c_ix})
    cp_sorted = sorted((c, child_parent[c][0]) for c in child_ids)
    edges_for_id = [("entity_entity", s, p, o) for s, p, o in ee_sorted] + [("entity_child", e, "mentions", c) for e, c in ec_sorted] + [("child_parent", c, "belongs_to", p) for c, p in cp_sorted]
    gid = content_id(entity_ids, child_ids, parent_ids, edges_for_id)

    def stack(ids: list[str], vecs: dict) -> np.ndarray:
        x = np.zeros((len(ids), dim), dtype=np.float32)
        for i, k in enumerate(ids):
            if k in vecs:
                x[i] = vecs[k][0]
        return x

    snap = Snapshot(corpus_id=corpus_id, embedding_contract=contract, dim=dim, entity_ids=entity_ids, child_ids=child_ids, parent_ids=parent_ids,
                    x_entity=stack(entity_ids, entity_vec), x_child=stack(child_ids, child_vec), x_parent=stack(parent_ids, parent_vec),
                    ee=np.asarray([(e_ix[s], e_ix[o]) for s, _, o in ee_sorted], dtype=np.int32).reshape(-1, 2), ee_predicate=[p for _, p, _ in ee_sorted],
                    ec=np.asarray([(e_ix[e], c_ix[c]) for e, c in ec_sorted], dtype=np.int32).reshape(-1, 2),
                    cp=np.asarray([(c_ix[c], p_ix[p]) for c, p in cp_sorted], dtype=np.int32).reshape(-1, 2),
                    child_doc=[child_parent[c][1] for c in child_ids], parent_doc=[parent_doc_map[p] for p in parent_ids], missing=missing, graph_snapshot_id=gid)
    say(f"snapshot {gid} in {time.perf_counter() - t0:.1f}s: E={len(entity_ids)} C={len(child_ids)} P={len(parent_ids)}")
    return snap


# ─────────────────────────────────────────────────────────── persistence (outside the repository)
def snapshot_dir(corpus_id: str, graph_snapshot_id: str) -> Path:
    return RUNTIME_DIR / corpus_id / graph_snapshot_id


def save(snap: Snapshot, *, extra: dict[str, Any] | None = None) -> Path:
    d = snapshot_dir(snap.corpus_id, snap.graph_snapshot_id)
    d.mkdir(parents=True, exist_ok=True)
    np.savez(d / "graph.npz", x_entity=snap.x_entity, x_child=snap.x_child, x_parent=snap.x_parent, ee=snap.ee, ec=snap.ec, cp=snap.cp)
    (d / "ids.json").write_text(json.dumps({"entity_ids": snap.entity_ids, "child_ids": snap.child_ids, "parent_ids": snap.parent_ids, "ee_predicate": snap.ee_predicate,
                                             "child_doc": snap.child_doc, "parent_doc": snap.parent_doc}), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps(snap.manifest(extra=extra), indent=1, sort_keys=True), encoding="utf-8")
    return d


def load(corpus_id: str, graph_snapshot_id: str) -> Snapshot:
    d = snapshot_dir(corpus_id, graph_snapshot_id)
    arr = np.load(d / "graph.npz")
    ids = json.loads((d / "ids.json").read_text(encoding="utf-8"))
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    return Snapshot(corpus_id=corpus_id, embedding_contract=man["embedding_contract"], dim=int(man["dim"]), entity_ids=ids["entity_ids"], child_ids=ids["child_ids"],
                    parent_ids=ids["parent_ids"], x_entity=arr["x_entity"], x_child=arr["x_child"], x_parent=arr["x_parent"], ee=arr["ee"], ee_predicate=ids["ee_predicate"],
                    ec=arr["ec"], cp=arr["cp"], child_doc=ids["child_doc"], parent_doc=ids["parent_doc"], missing=man.get("missing_vectors") or {}, graph_snapshot_id=graph_snapshot_id)


def synthetic(seed: int = 0, *, n_entity: int = 12, n_child: int = 20, n_parent: int = 6, dim: int = 8) -> Snapshot:
    """A small deterministic graph for the gate's own tests (no store)."""
    rng = np.random.default_rng(seed)
    ent = [f"ent_{i:02d}" for i in range(n_entity)]; ch = [f"ch_{i:02d}" for i in range(n_child)]; par = [f"p_{i:02d}" for i in range(n_parent)]
    x = lambda n: rng.standard_normal((n, dim)).astype(np.float32)  # noqa: E731
    cp = [(i, i % n_parent) for i in range(n_child)]
    ec = sorted({(int(rng.integers(n_entity)), i) for i in range(n_child) for _ in range(2)})
    ee = sorted({(int(a), int(b)) for a, b in rng.integers(n_entity, size=(n_entity * 2, 2)) if a != b})
    edges = [("entity_entity", ent[a], "related_to", ent[b]) for a, b in ee] + [("entity_child", ent[a], "mentions", ch[c]) for a, c in ec] + [("child_parent", ch[c], "belongs_to", par[p]) for c, p in cp]
    return Snapshot(corpus_id="synthetic", embedding_contract="embed_test", dim=dim, entity_ids=ent, child_ids=ch, parent_ids=par, x_entity=x(n_entity), x_child=x(n_child), x_parent=x(n_parent),
                    ee=np.asarray(ee, dtype=np.int32).reshape(-1, 2), ee_predicate=["related_to"] * len(ee), ec=np.asarray(ec, dtype=np.int32).reshape(-1, 2), cp=np.asarray(cp, dtype=np.int32).reshape(-1, 2),
                    child_doc=[f"d{c % 2}" for c in range(n_child)], parent_doc=[f"d{p % 2}" for p in range(n_parent)], missing={}, graph_snapshot_id=content_id(ent, ch, par, edges))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    a = ap.parse_args()
    s = build_snapshot(a.corpus)
    print(json.dumps(s.manifest(), indent=1, sort_keys=True))
    print("saved to", save(s))
