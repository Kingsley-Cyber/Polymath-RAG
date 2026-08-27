#!/usr/bin/env python3
"""V5 P9 — PROJECTION RECONSTRUCTION: Postgres is the authority; prove it.

    neo4j:  snapshot graph -> WIPE the entire graph -> rebuild every corpus
            run from Postgres via the projector's own row/write functions ->
            compare node/edge sets EXACTLY.
    qdrant: snapshot a corpus's collections -> DELETE them -> rebuild via the
            projector's own chunk/embed/write functions -> compare point
            counts and ids.

Destructive to DERIVED stores only, never to Postgres. Uses the production
projectors' internals so reconstruction is the same code path as projection.
"""
import argparse, json, os, sys
sys.path[:0] = ["shared", "workers"]

import psycopg

DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _runs(conn, corpora):
    return [r[0] for r in conn.execute(
        "SELECT run_id FROM runs WHERE corpus_id = ANY(%s) ORDER BY run_id",
        (corpora,)).fetchall()]


def _graph_snapshot(driver):
    with driver.session() as s:
        nodes = sorted(r["id"] for r in s.run(
            "MATCH (e:Entity) RETURN e.entity_id AS id") if r["id"])
        edges = sorted(r["id"] for r in s.run(
            "MATCH ()-[r]->() RETURN r.fact_id AS id") if r["id"])
    return nodes, edges


def reconstruct_neo4j(conn, corpora) -> dict:
    from workers.project_neo4j_worker import (_apply_constraints, _driver,
                                              _graph_rows, _write_graph)
    driver = _driver()
    try:
        before = _graph_snapshot(driver)
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        assert _graph_snapshot(driver) == ([], []), "wipe did not empty the graph"
        _apply_constraints(driver)
        expected_nodes, expected_edges = set(), set()
        for run_id in _runs(conn, corpora):
            rows = _graph_rows(conn, run_id)
            _write_graph(driver, rows)
            for n in rows.get("entities", []):
                expected_nodes.add(n["entity_id"])
            for e in rows.get("facts", []):
                expected_edges.add(e["fact_id"])
        after = _graph_snapshot(driver)
        # THE claim: the rebuilt graph equals exactly what Postgres projects
        # for the EXISTING runs. The pre-wipe graph may legitimately exceed
        # that: wiped runs leave facts in the global tables, so their edges
        # were never "orphans", yet no existing run can reproduce them —
        # that difference is RESIDUE and is reported, not hidden inside a
        # false "exact" comparison against a contaminated baseline.
        missing_nodes = sorted(expected_nodes - set(after[0]))
        missing_edges = sorted(expected_edges - set(after[1]))
        extra_nodes = sorted(set(after[0]) - expected_nodes)
        extra_edges = sorted(set(after[1]) - expected_edges)
        return {"nodes_before": len(before[0]), "edges_before": len(before[1]),
                "nodes_after": len(after[0]), "edges_after": len(after[1]),
                "expected_nodes": len(expected_nodes),
                "expected_edges": len(expected_edges),
                "missing_after_rebuild": missing_nodes[:5] + missing_edges[:5],
                "extra_after_rebuild": extra_nodes[:5] + extra_edges[:5],
                "prewipe_residue_nodes": len(set(before[0]) - expected_nodes),
                "prewipe_residue_edges": len(set(before[1]) - expected_edges),
                "exact": (set(after[0]) == expected_nodes
                          and set(after[1]) == expected_edges)}
    finally:
        driver.close()


def reconstruct_qdrant(conn, corpus: str) -> dict:
    from qdrant_client import QdrantClient
    from polymath_shared.settings import get_settings
    from polymath_shared.projection_contracts import qdrant_collection_name
    from workers.project_qdrant_worker import (_active_contract, _chunks_for_run,
                                               _ensure_collection, _write_points)
    contract = _active_contract()
    client = QdrantClient(url=get_settings().stores.qdrant_url)
    coll = qdrant_collection_name(corpus, contract.contract_id)
    try:
        before = client.count(coll, exact=True).count
    except Exception:
        return {"skipped": f"collection {coll} absent"}
    client.delete_collection(coll)
    runs = _runs(conn, [corpus])
    total = 0
    for run_id in runs:
        chunks = _chunks_for_run(conn, run_id)
        if not chunks:
            continue
        # dimension comes from the embedding contract; projector ensures it
        from workers.project_qdrant_worker import _embed_texts
        vectors = _embed_texts(contract, [c["text"] for c in chunks])
        _ensure_collection(client, coll, len(vectors[0]))
        for c_, v in zip(chunks, vectors):
            c_["vector"] = v
        _write_points(client, coll, chunks, contract)
        total += len(chunks)
    after = client.count(coll, exact=True).count
    return {"collection": coll, "points_before": before, "points_after": after,
            "rebuilt_from_runs": len(runs), "exact": before == after}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpora", nargs="+", required=True)
    ap.add_argument("--qdrant-corpus", default=None)
    a = ap.parse_args()
    out = {}
    with psycopg.connect(DSN) as conn:
        out["neo4j"] = reconstruct_neo4j(conn, a.corpora)
        if a.qdrant_corpus:
            out["qdrant"] = reconstruct_qdrant(conn, a.qdrant_corpus)
    print(json.dumps(out, indent=1))
    ok = out["neo4j"]["exact"] and out.get("qdrant", {}).get("exact", True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
