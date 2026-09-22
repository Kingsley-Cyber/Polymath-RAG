"""GNN-RETRIEVAL-V1 — the offline half, pure (a synthetic snapshot; no store, no network): the snapshot identity is content-derived and
deterministic, M0 / M1 / the two controls are deterministic, semantically anchored and distinct, the shallow GNN trains deterministically
on CPU and stays in the original space, the projection writes only an isolated collection with the contract payload."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "eval/gnn_route"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import graph_snapshot as GS  # noqa: E402
import model as MODEL  # noqa: E402
import project as PROJ  # noqa: E402
import propagate as PR  # noqa: E402
from polymath_shared import gnn_route as gr  # noqa: E402


def test_graph_snapshot_is_deterministic_and_content_identified():
    a, b = GS.synthetic(0), GS.synthetic(0)
    assert a.graph_snapshot_id == b.graph_snapshot_id and a.graph_snapshot_id.startswith("gs_")
    assert GS.synthetic(1).graph_snapshot_id != a.graph_snapshot_id                      # different content, different id
    edges = [("entity_child", "e", "mentions", "c")]
    assert GS.content_id(["b", "a"], ["c"], ["p"], edges) == GS.content_id(["a", "b"], ["c"], ["p"], edges)   # order never matters
    m = a.manifest()
    assert m["node_counts"] == {"entity": 12, "child": 20, "parent": 6} and set(m["edge_counts"]) == set(GS.EDGE_TYPES) and "orphans" in m


def _unit(x):
    return np.allclose(np.linalg.norm(x, axis=1), 1.0, atol=1e-5)


def test_m1_propagation_is_deterministic_anchored_and_the_controls_are_distinct():
    s = GS.synthetic(0)
    real1, real2 = PR.propagate(s, lam=0.7, variant="real"), PR.propagate(s, lam=0.7, variant="real")
    assert real1["digest"] == real2["digest"] and np.array_equal(real1["z_parent"], real2["z_parent"]) and _unit(real1["z_parent"])
    assert 0.5 < real1["anchor_cos_parent"] < 1.0                                          # enriched, still the same semantic identity
    nograph = PR.propagate(s, lam=0.7, variant="nograph")
    assert np.allclose(nograph["z_parent"], PR.identity(s)["z_parent"]) and nograph["anchor_cos_parent"] == pytest.approx(1.0)
    sh1, sh2 = PR.propagate(s, lam=0.7, variant="shuffled", seed=3), PR.propagate(s, lam=0.7, variant="shuffled", seed=3)
    assert sh1["digest"] == sh2["digest"] and not np.allclose(sh1["z_parent"], real1["z_parent"]) and _unit(sh1["z_parent"])
    assert PR.propagate(s, lam=0.7, variant="shuffled", seed=4)["digest"] != sh1["digest"]
    with pytest.raises(ValueError):
        PR.propagate(s, variant="random")


def test_shuffled_edges_preserve_counts_and_sources():
    s = GS.synthetic(0)
    sh = PR.shuffle_edges(s.ec, seed=1)
    assert sh.shape == s.ec.shape and np.array_equal(sh[:, 0], s.ec[:, 0]) and sorted(sh[:, 1].tolist()) == sorted(s.ec[:, 1].tolist())


def test_a_parent_without_a_map_vector_takes_its_childrens_message_never_a_zero():
    s = GS.synthetic(0)
    s.x_parent[2] = 0.0
    z = PR.propagate(s, lam=0.7, variant="real")["z_parent"]
    assert np.linalg.norm(z[2]) == pytest.approx(1.0, abs=1e-5)


def test_m2_trains_deterministically_on_cpu_and_stays_in_the_original_space():
    s = GS.synthetic(0, dim=8)
    a = MODEL.train(s, variant="real", epochs=4, batch=16, seed=7, device="cpu", log=lambda *x: None)
    b = MODEL.train(s, variant="real", epochs=4, batch=16, seed=7, device="cpu", log=lambda *x: None)
    assert a["digest"] == b["digest"] and np.array_equal(a["z_parent"], b["z_parent"]) and _unit(a["z_parent"])
    assert a["anchor_cos_parent"] > 0.8 and a["params"]["contract"] == MODEL.M2_CONTRACT and a["params"]["seed"] == 7
    ng = MODEL.train(s, variant="nograph", epochs=4, batch=16, seed=7, device="cpu", log=lambda *x: None)
    assert ng["digest"] != a["digest"] and ng["anchor_cos_parent"] == pytest.approx(1.0, abs=1e-4)   # no neighbourhood ⇒ the residual path alone
    sh = MODEL.train(s, variant="shuffled", epochs=4, batch=16, seed=7, device="cpu", log=lambda *x: None)
    assert sh["digest"] not in (a["digest"], ng["digest"])


class _Client:
    def __init__(self):
        self.created, self.points, self.indexes = [], {}, []

    def recreate_collection(self, name, vectors_config):
        self.created.append((name, vectors_config.size)); self.points[name] = []

    def create_payload_index(self, name, field_name, field_schema):
        self.indexes.append((name, field_name))

    def upsert(self, name, points, wait):
        self.points[name].extend(points)

    def get_collection(self, name):
        from types import SimpleNamespace
        return SimpleNamespace(points_count=len(self.points[name]))


def test_projection_uses_an_isolated_contract_named_collection_with_the_experiment_payload():
    s = GS.synthetic(0)
    z = PR.propagate(s, variant="real")["z_parent"]
    c = _Client()
    out = PROJ.project(c, s, z, family=gr.FAMILY_M1, variant="real", model_digest="m1_x", log=lambda *a: None)
    assert out["collection"] == "polymath_gnn_parent_embed_test_m1-smooth-real" and c.created == [(out["collection"], 8)]
    pl = c.points[out["collection"]][0].payload
    assert pl["representation_kind"] == gr.PAYLOAD_KIND and pl["corpus_id"] == "synthetic" and pl["gnn_contract"] == "m1-smooth-real"
    assert pl["graph_snapshot_id"] == s.graph_snapshot_id and pl["model_digest"] == "m1_x" and pl["embedding_contract"] == "embed_test" and pl["parent_id"] == "p_00"
    assert PROJ.point_id("synthetic", "p_00", "m1-smooth-real") == PROJ.point_id("synthetic", "p_00", "m1-smooth-real")
    with pytest.raises(RuntimeError):
        PROJ.assert_isolated("polymath_document_parent_maps_embed_test")
    with pytest.raises(RuntimeError):
        PROJ.project(c, s, z[:, :4], family=gr.FAMILY_M1, variant="real", model_digest="m1_x", log=lambda *a: None)     # wrong dimension refused
