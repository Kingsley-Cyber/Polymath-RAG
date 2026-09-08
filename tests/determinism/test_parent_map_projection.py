"""DOCUMENT-SEMANTIC-INDEX-V1 slice S10 — parent-map Qdrant projection contract.

Pins the deterministic projection contract (§9.2 payload + vector text, §14 count
reconciliation) with an injected fake embedder + fake Qdrant client — no network, no
embedder sidecar, no spend. The embed/upsert I/O is what the live wiring supplies.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import parent_map_projection as PJ  # noqa: E402
from polymath_shared.document_profile import map_compiler  # noqa: E402
from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons  # noqa: E402

DIM = 8


def _parents():
    return [
        {"chunk_id": f"pm-{i}", "chunk_index": i, "char_start": i * 1000,
         "heading_path": [f"Chapter {i + 1}", "Section A"],
         "text": f"Section {i} explains mechanism MK{i} within the control framework and its stability effects.",
         "region_role": "body"}
        for i in range(4)
    ]


def _manifest():
    return build_parent_skeletons(_parents())


def _maps(manifest):
    raw = "\n".join(f"MAP|{s.alias}|routing signature for {s.alias}|weight;time;impact"
                    for s in manifest.skeletons)
    return map_compiler.compile_maps(raw, manifest).maps


class _FakeQdrant:
    def __init__(self):
        self.collections: dict = {}
        self.upserts: list = []

    def collection_exists(self, name):
        return name in self.collections

    def create_collection(self, collection_name, vectors_config):
        self.collections[collection_name] = vectors_config

    def upsert(self, collection_name, points, wait=True):
        self.upserts.append((collection_name, list(points)))


def _embed(texts):
    return [[float(i + 1)] * DIM for i, _ in enumerate(texts)]


def test_collection_name_and_point_id():
    assert PJ.collection_name("e794ec4") == "polymath_document_parent_maps_e794ec4"
    a = PJ.point_id("d1", "p1", "map-compiler-v1")
    assert a == PJ.point_id("d1", "p1", "map-compiler-v1")            # stable
    assert a != PJ.point_id("d1", "p2", "map-compiler-v1")            # per-parent
    assert a != PJ.point_id("d1", "p1", "map-compiler-v2")            # per-contract


def test_vector_text_and_compact_heading():
    t = PJ.vector_text("weight governs perceived force", ["weight", "time"], ["Chapter 3", "Impact"])
    assert "weight governs perceived force" in t
    assert "weight; time" in t
    assert "Chapter 3 › Impact" in t
    assert PJ.compact_heading(["x" * 200]).__len__() <= PJ.COMPACT_HEADING_MAX_CHARS
    # empty hooks / heading degrade gracefully
    assert PJ.vector_text("sig only", [], []) == "sig only"


def test_payload_has_contract_fields():
    p = PJ.build_payload(doc_id="d1", parent_id="p1", corpus_id="c1", alias="P0001",
                         heading_path=["A", "B"], ordinal=0, map_contract="map-compiler-v1",
                         map_hash="mh1", source_text_hash="th1", embedding_contract_id="e1")
    for k in ("doc_id", "parent_id", "corpus_id", "alias", "heading_path", "parent_ordinal",
              "map_contract", "map_hash", "source_text_hash", "embedding_contract", "projection_key"):
        assert k in p
    assert p["parent_ordinal"] == 0 and p["heading_path"] == ["A", "B"]


def test_projection_key_sensitivity():
    base = dict(map_hash="mh1", map_contract="map-compiler-v1", embedding_contract_id="e1")
    assert PJ.projection_key(**base) == PJ.projection_key(**base)
    assert PJ.projection_key(**{**base, "embedding_contract_id": "e2"}) != PJ.projection_key(**base)
    assert PJ.projection_key(**{**base, "map_hash": "mh2"}) != PJ.projection_key(**base)


def test_reconcile_gate():
    assert PJ.reconcile(active_map_count=40, projected_point_count=40)["ok"] is True
    bad = PJ.reconcile(active_map_count=40, projected_point_count=39)
    assert bad["ok"] is False and bad["delta"] == -1


def test_project_parent_maps_end_to_end():
    manifest = _manifest()
    maps = _maps(manifest)
    assert len(maps) == 4
    client = _FakeQdrant()
    receipt = PJ.project_parent_maps(client, embed=_embed, embedding_contract_id="e1", dim=DIM,
                                     doc_id="d1", corpus_id="c1", maps=maps, manifest=manifest,
                                     map_contract="map-compiler-v1")
    assert receipt["points"] == 4
    assert receipt["created_collection"] is True
    assert receipt["collection"] == "polymath_document_parent_maps_e1"
    # one upsert, 4 points, each with the named routing vector + a payload
    (coll, points), = client.upserts
    assert coll == "polymath_document_parent_maps_e1" and len(points) == 4
    assert all(PJ.VECTOR_NAME in pt.vector for pt in points)
    assert {pt.payload["parent_id"] for pt in points} == {s.parent_id for s in manifest.skeletons}
    # deterministic: same inputs -> same point ids + projection hash
    client2 = _FakeQdrant()
    receipt2 = PJ.project_parent_maps(client2, embed=_embed, embedding_contract_id="e1", dim=DIM,
                                      doc_id="d1", corpus_id="c1", maps=maps, manifest=manifest,
                                      map_contract="map-compiler-v1")
    assert receipt2["point_ids"] == receipt["point_ids"]
    assert receipt2["projection_hash"] == receipt["projection_hash"]


def test_project_empty_is_safe():
    manifest = _manifest()
    client = _FakeQdrant()
    receipt = PJ.project_parent_maps(client, embed=_embed, embedding_contract_id="e1", dim=DIM,
                                     doc_id="d1", corpus_id="c1", maps=[], manifest=manifest,
                                     map_contract="map-compiler-v1")
    assert receipt["points"] == 0 and client.upserts == []
