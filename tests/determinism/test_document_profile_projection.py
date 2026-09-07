"""DOCUMENT-PROFILE-V1 step 4 — projection: one point per document, named dense + multivectors, one vector per atomic
unit, stable ids, the projection key / hash, and the projector's half of the readiness contract. Fake client + stub embed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import projection as PJ  # noqa: E402

REPS = {"identity": "A guide to selling punches on camera\nTopics: screen combat, reaction timing",
        "theme": "How camera, reaction and cutting make a strike read as real.",
        "questions": ["How do you make a punch look real on camera?", "Why does the reaction matter?"],
        "searches": ["selling a punch on camera", "fight scene camera angle", "reaction timing stage combat"],
        "theories": ["perceived force is inferred from the receiver's reaction"],
        "concepts": [], "seealso": ["animation timing of impacts", "movement analysis of effort"]}


class FakeQdrant:
    def __init__(self, exists=False):
        self.exists = exists; self.created = []; self.upserts = []
    def collection_exists(self, name): return self.exists
    def create_collection(self, collection_name, vectors_config): self.created.append((collection_name, vectors_config)); self.exists = True
    def upsert(self, collection_name, points, wait=True): self.upserts.append((collection_name, points, wait))


def stub_embed(texts):
    return [[float(len(t) % 7) / 7.0] * 4 + [float(i)] for i, t in enumerate(texts)]      # deterministic 5-d vectors


def test_batch_order_and_named_vectors_keep_one_vector_per_atomic_unit():
    batch = PJ.texts_to_embed("Stage Combat Arts", REPS)
    surfaces = [s for s, _, _ in batch]
    assert surfaces[:3] == ["title", "identity", "theme"]
    assert surfaces.count("questions") == 2 and surfaces.count("searches") == 3 and surfaces.count("theories") == 1 and surfaces.count("seealso") == 2
    assert "concepts" not in surfaces                                                    # empty surface → no vectors, no error
    named = PJ.build_point_vectors(batch, stub_embed([t for _, _, t in batch]))
    assert isinstance(named["identity"][0], float) and len(named["questions"]) == 2 and len(named["searches"]) == 3
    with pytest.raises(ValueError):
        PJ.build_point_vectors(batch, stub_embed([t for _, _, t in batch])[:-1])


def test_project_profile_creates_the_collection_once_upserts_one_point_and_returns_a_receipt():
    q = FakeQdrant()
    kw = dict(embed=stub_embed, embedding_contract_id="embed_abc", dim=5, doc_id="doc_1", corpus_id="cinema",
              title="Stage Combat Arts", representations=REPS, source_doc_hash="sha_doc", schema_version="rag-profile-v3",
              prompt_version="doc-profile-v3", compiled_hash="sha_compiled")
    r1 = PJ.project_profile(q, **kw)
    assert q.created and q.created[0][0] == "polymath_document_profiles_embed_abc"
    cfg = q.created[0][1]
    assert set(cfg) == set(PJ.DENSE_SURFACES) | set(PJ.MULTI_SURFACES)
    assert cfg["questions"].multivector_config is not None and cfg["identity"].multivector_config is None
    assert len(q.upserts) == 1 and len(q.upserts[0][1]) == 1
    pt = q.upserts[0][1][0]
    assert pt.id == PJ.point_id("doc_1") == PJ.point_id("doc_1") and pt.payload["projection_key"] == r1["projection_key"]
    assert pt.payload["surfaces"] == {"title": 1, "identity": 1, "theme": 1, "questions": 2, "searches": 3, "theories": 1, "seealso": 2}
    assert r1["vectors"]["questions"] == 2 and r1["texts_embedded"] == 11 and r1["created_collection"] is True
    r2 = PJ.project_profile(q, **kw)
    assert len(q.created) == 1 and r2["created_collection"] is False and r2["projection_hash"] == r1["projection_hash"]   # idempotent, deterministic
    assert PJ.has_required_vectors(r1) == (True, [])


def test_projection_key_moves_only_with_document_schema_prompt_or_embedding():
    base = dict(source_doc_hash="d", schema_version="s", prompt_version="p", embedding_contract_id="e")
    k = PJ.projection_key(**base)
    assert k == PJ.projection_key(**base)
    for field, val in (("source_doc_hash", "d2"), ("schema_version", "s2"), ("prompt_version", "p2"), ("embedding_contract_id", "e2")):
        assert PJ.projection_key(**{**base, field: val}) != k


def test_readiness_needs_identity_theme_and_a_query_hook_vector():
    assert PJ.has_required_vectors({"vectors": {"identity": 1, "theme": 1, "searches": 3}}) == (True, [])
    assert PJ.has_required_vectors({"vectors": {"identity": 1, "theme": 1}}) == (False, ["query_hook_vector"])
    assert PJ.has_required_vectors({"vectors": {"title": 1, "questions": 2}}) == (False, ["identity_vector", "theme_vector"])
    with pytest.raises(ValueError):
        PJ.project_profile(FakeQdrant(), embed=stub_embed, embedding_contract_id="e", dim=5, doc_id="d", corpus_id="c", title="",
                           representations={}, source_doc_hash="x", schema_version="s", prompt_version="p", compiled_hash="h")
