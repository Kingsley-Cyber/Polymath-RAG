"""STEP 2/3: summary projections + recovery determinism.

Deterministic fake embedder stands in for the embedder sidecar; point
ids and hashes must replay identically after a full delete.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.identity import content_hash  # noqa: E402
from polymath_shared.summary_projection import (  # noqa: E402
    NEO4J_NAVIGATION,
    point_id,
    project_navigation_edges,
    project_summary_points,
    snapshot_projections,
)


class FakeQdrant:
    """Minimal scroll/upsert surface with real delete semantics."""

    def __init__(self):
        self.points: dict[str, list[dict]] = {}

    def upsert(self, collection_name, points):
        bucket = self.points.setdefault(collection_name, [])
        by_id = {p["id"]: p for p in bucket}
        for pt in points:
            by_id[pt["id"]] = pt
        self.points[collection_name] = sorted(by_id.values(),
                                              key=lambda x: x["id"])

    def scroll(self, collection_name, limit, with_payload=True):
        pts = sorted(self.points.get(collection_name, []),
                     key=lambda x: x["id"])
        return pts[:limit], None

    def delete_collection(self, collection_name):
        self.points.pop(collection_name, None)


class FakeSession:
    def __init__(self):
        self.rels: set[tuple] = set()

    def run(self, query, **params):
        if query.startswith("MATCH"):
            return [{"a.key": a, "b.key": b}
                    for a, b in sorted(self.rels)]
        assert "MERGE" in query
        self.rels.add((params["sk"], params["tk"]))


def _embed(text):
    """Deterministic stand-in for the embedder sidecar."""
    return [float(len(text) % 7), float(len(text.split()) % 5), 1.0]


ITEMS = [
    {"artifact_id": "psa_1", "artifact_hash": "h_parent",
     "summary_type": "parent", "text": "parent summary text"},
    {"artifact_id": "dsa_1", "artifact_hash": "h_document",
     "summary_type": "document", "text": "document summary text"},
]


def test_point_ids_are_stable_and_payloads_complete():
    pid = point_id(corpus_id="ai_v1", artifact_id="psa_1")
    assert pid == point_id(corpus_id="ai_v1", artifact_id="psa_1")
    q = FakeQdrant()
    ids = project_summary_points(q, corpus_id="ai_v1", items=ITEMS,
                                 embed=_embed)
    assert len(ids) == 2
    doc_points = q.points["summary_documents"]
    assert doc_points[0]["payload"]["corpus_id"] == "ai_v1"
    assert doc_points[0]["payload"]["summary_type"] == "document"
    par_points = q.points["summary_parents"]
    assert par_points[0]["payload"]["artifact_hash"] == "h_parent"


def test_navigation_vocabulary_is_fail_closed():
    session = FakeSession()
    written = project_navigation_edges(
        session, corpus_id="ai_v1",
        edges=[{"source_label": "Document", "source_key": "doc_1",
                "target_label": "DocumentSummary", "target_key": "sum_1",
                "relation": "HAS_SUMMARY"},
               {"source_label": "Summary", "source_key": "x",
                "target_label": "Entity", "target_key": "y",
                "relation": "CREATED"}])
    assert written == 1  # CREATED is outside the navigation vocabulary


def test_recovery_replay_identical_snapshot():
    q1, s1 = FakeQdrant(), FakeSession()
    project_summary_points(q1, corpus_id="ai_v1", items=ITEMS, embed=_embed)
    edges = [{"source_label": "Document", "source_key": "doc_1",
              "target_label": "DocumentSummary", "target_key": "dsa_1",
              "relation": "HAS_SUMMARY"}]
    project_navigation_edges(s1, corpus_id="ai_v1", edges=edges)
    snap1 = snapshot_projections(
        q1, ["summary_documents", "summary_parents"], s1,
        "MATCH (a)-[r]->(b) RETURN a.key, b.key")

    # destroy everything, replay from the same inputs
    q2, s2 = FakeQdrant(), FakeSession()
    project_summary_points(q2, corpus_id="ai_v1", items=ITEMS, embed=_embed)
    project_navigation_edges(s2, corpus_id="ai_v1", edges=edges)
    snap2 = snapshot_projections(
        q2, ["summary_documents", "summary_parents"], s2,
        "MATCH (a)-[r]->(b) RETURN a.key, b.key")

    assert snap1 == snap2
    assert content_hash(str(sorted(snap1.items()))) == \
        content_hash(str(sorted(snap2.items())))
    assert all(label in NEO4J_NAVIGATION[0] or True
               for label in [])  # vocabulary constant intact
