"""STEP 2b: Neo4j navigation edges against the live graph.

HAS_SUMMARY navigation is derived-only: MERGE on stable keys, delete,
replay, assert identical relationship set.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.summary_projection import project_navigation_edges

URI = "bolt://127.0.0.1:7688"
AUTH = ("neo4j", "polymath-dev")


def test_live_navigation_replay_identical():
    tag = uuid.uuid4().hex[:8]
    driver = GraphDatabase.driver(URI, auth=AUTH)
    edges = [
        {"source_label": "Document", "source_key": f"doc_{tag}",
         "target_label": "DocumentSummary",
         "target_key": f"sum_{tag}", "relation": "HAS_SUMMARY"},
        {"source_label": "Concept", "source_key": f"cpt_{tag}",
         "target_label": "DocumentSummary", "target_key": f"sum_{tag}",
         "relation": "SUPPORTED_BY"},
    ]
    try:
        def project(session):
            return project_navigation_edges(session, corpus_id=f"nav_{tag}",
                                            edges=edges)

        with driver.session() as s:
            project(s)
            snap1 = s.run(
                "MATCH (a)-[r:HAS_SUMMARY|SUPPORTED_BY]->(b) "
                "WHERE a.key CONTAINS $t AND b.key CONTAINS $t "
                "RETURN a.key, type(r), b.key", t=tag).values()

        for e in edges + [{"source_label": "Document",
                           "source_key": f"doc_{tag}",
                           "target_label": "DocumentSummary",
                           "target_key": f"sum_{tag}",
                           "relation": "HAS_SUMMARY"}]:
            pass
        with driver.session() as s:
            s.run("MATCH (a)-[r:HAS_SUMMARY|SUPPORTED_BY]->(b) "
                  "WHERE a.key CONTAINS $t DELETE r", t=tag)
            s.run("MATCH (a) WHERE a.key CONTAINS $t DETACH DELETE a", t=tag)
            project(s)
            snap2 = s.run(
                "MATCH (a)-[r:HAS_SUMMARY|SUPPORTED_BY]->(b) "
                "WHERE a.key CONTAINS $t AND b.key CONTAINS $t "
                "RETURN a.key, type(r), b.key", t=tag).values()

        assert sorted(map(tuple, snap1)) == sorted(map(tuple, snap2))
        assert len(snap2) == 2
    finally:
        with driver.session() as s:
            s.run("MATCH (a) WHERE a.key CONTAINS $t DETACH DELETE a",
                  t=tag)
        driver.close()
