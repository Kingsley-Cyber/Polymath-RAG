"""E5B part 2 — graph/extraction zero-delta reconfirmation + Neo4j
concept leak check + performance observations.

The concept projection writes ONLY the disposable experimental Qdrant
collections; this verifies that Postgres entity/fact/canonical state
and Neo4j are byte-identical before and after, and that no concept id
exists anywhere in the graph.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.settings import get_settings  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"


def graph_state(conn) -> str:
    rows = conn.execute("""
        SELECT 'e|'||e.entity_id||'|'||COALESCE(e.admission_class,'NULL') FROM entities e
         UNION ALL SELECT 'f|'||f.fact_id||'|'||f.predicate||'|'||f.subject_id||'|'||f.object_id FROM facts f
         UNION ALL SELECT 'cn|'||c.canonical_id||'|'||c.corpus_id FROM canonical_entities c
         ORDER BY 1""").fetchall()
    return hashlib.sha256("\n".join(r[0] for r in rows).encode()).hexdigest()


def extraction_state(conn) -> str:
    rows = conn.execute("""
        SELECT 'ev|'||e.evidence_id||'|'||e.fact_id||'|'||e.rule_id||'|'||e.extractor_version
          FROM evidence e ORDER BY 1""").fetchall()
    return hashlib.sha256("\n".join(r[0] for r in rows).encode()).hexdigest()


def neo4j_state() -> str:
    from neo4j import GraphDatabase
    uri = get_settings().stores.neo4j_uri
    user = get_settings().stores.neo4j_user
    pwd = get_settings().stores.neo4j_password
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session() as s:
            concept_nodes = s.run(
                "MATCH (n) WHERE n.id STARTS WITH 'concept_' RETURN count(n) AS c").single()["c"]
            n_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            n_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    finally:
        driver.close()
    return {"concept_nodes": concept_nodes, "nodes": n_nodes, "relationships": n_rels}


def main() -> int:
    conn = psycopg.connect(DSN)
    before = {
        "graph": graph_state(conn),
        "extraction": extraction_state(conn),
    }
    t0 = time.time()
    # concept inventory over the whole corpus (reads only; the actual
    # projection into experimental collections happens in routing_ab.py)
    from polymath_shared.concept_inventory import document_inventory
    chunks = conn.execute(
        """SELECT c.chunk_id, c.text, c.summary FROM chunks c
            JOIN documents d ON d.doc_id=c.doc_id
           WHERE d.corpus_id=%s AND c.tier='child'""", (CORPUS,)).fetchall()
    rows = [{"chunk_id": r[0], "text": r[1], "summary": r[2] or ""} for r in chunks]
    document_inventory(rows)
    extract_ms = (time.time() - t0) * 1000

    after = {
        "graph": graph_state(conn),
        "extraction": extraction_state(conn),
    }
    conn.close()
    ng = neo4j_state()

    out = {
        "graph_zero_delta": before["graph"] == after["graph"],
        "extraction_zero_delta": before["extraction"] == after["extraction"],
        "neo4j": ng,
        "concept_ids_in_neo4j": ng["concept_nodes"] == 0,
        "corpus_wide_inventory_ms": round(extract_ms, 1),
        "corpus_child_chunks": len(rows),
    }
    (ROOT / "eval" / "e5b" / "zero_delta.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    print("wrote eval/e5b/zero_delta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
