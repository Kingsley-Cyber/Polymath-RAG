"""CONTROL-PLANE-STATUS-V1 + corpus document summaries (operational UI backend).

Provider-free, DB-free: a scripted fake connection drives the batch summary + the
control-plane rollup; the lane detail runs against the real committed config with NO
secret rendered. Asserts the four functional pools, the per-document vnext_ready rule,
and the LOCAL limiter_refused vs ACTUAL HTTP 429 distinction.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import control_plane_status as CPS  # noqa: E402
from polymath_shared.document_status import corpus_document_summaries  # noqa: E402


class _Cur:
    def __init__(self, rows): self._rows = rows
    def fetchone(self): return self._rows[0] if self._rows else None
    def fetchall(self): return self._rows


class _Conn:
    """Dispatches by SQL fragment for a 2-document corpus: docA complete, docB pMAP-stalled."""
    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "SELECT doc_id FROM documents WHERE corpus_id" in s:
            return _Cur([("docA",), ("docB",)])
        if "FROM chunks WHERE doc_id = ANY(%s) GROUP BY 1,2" in s:
            return _Cur([("docA", "child", 8), ("docA", "parent", 3), ("docB", "parent", 5)])
        if "tier='parent' AND COALESCE(region_role" in s:
            return _Cur([("docA", 3), ("docB", 5)])
        if "to_regclass('public.document_parent_maps')" in s:
            return _Cur([("document_parent_maps",)])
        if "COUNT(DISTINCT parent_id) FROM document_parent_maps" in s:
            return _Cur([("docA", 3), ("docB", 1)])       # docB only 1/5 mapped
        if "FROM document_parent_exclusions WHERE doc_id = ANY" in s:
            return _Cur([])
        if "a.stage='doc_profile'" in s and "DISTINCT ON" in s:
            return _Cur([("docA", "true"), ("docB", "true")])
        if "a.stage='extract'" in s and "DISTINCT ON" in s:
            return _Cur([("docA", 42, 17), ("docB", 5, 2)])
        if "FROM runs WHERE corpus_id" in s and "IN ('intake'" in s:
            return _Cur([(1,)])                            # one in-flight run
        if "FROM stage_tickets WHERE corpus_id" in s:
            return _Cur([("extract", "ready", 0, 2), ("doc_parent_map", "leased", 0, 1)])
        if "a.stage='doc_parent_map'" in s:                # pMAP provider conservation
            return _Cur([(9, 3, 1, 0, 8, 0)])              # disp, refused, 429, fail, mapped, empty
        if "a.stage='extract'" in s:                       # graph provider
            return _Cur([(12, 47, 0, 1, 47, 19)])
        raise AssertionError(f"unscripted SQL: {s[:80]}")


def test_corpus_summaries_apply_vnext_ready_rule():
    s = corpus_document_summaries(_Conn(), corpus_id="c")
    assert s["docA"]["vnext_ready"] is True                 # 3/3 mapped + vNext profile
    assert s["docB"]["vnext_ready"] is False                # 1/5 mapped -> unresolved 4
    assert s["docA"]["graph_entities"] == 42 and s["docA"]["graph_relations"] == 17
    assert s["docB"]["map_unresolved"] == 4


def test_control_plane_status_four_pools_and_refused_vs_429():
    cp = CPS.control_plane_status(_Conn(), corpus_id="c")
    assert cp["summary"] == {"documents": 2, "semantic_ready": 1, "processing": 1, "blocked": 1}
    assert set(cp["pools"]) == {"GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"}
    # pMAP provider accounting distinguishes LOCAL refusal from ACTUAL HTTP 429
    prov = cp["pools"]["PMAP"]["provider"]
    assert prov["limiter_refused"] == 3 and prov["http_429"] == 1
    assert prov["provider_requests"] == 9 and prov["valid_maps_persisted"] == 8
    assert prov["maps_per_request"] == round(8 / 9, 2)
    # queue mapping: extract(ready)=queued for GRAPH, doc_parent_map(leased)=processing for PMAP
    assert cp["pools"]["GRAPH_EXTRACTION"]["queued"] == 2
    assert cp["pools"]["PMAP"]["processing"] == 1
    # CHAT is a latency pool, not an ingestion queue
    assert cp["pools"]["CHAT"].get("latency_pool") is True


def test_pool_lanes_detail_is_secret_free_and_model_grouped():
    import os
    os.environ.setdefault("GROQ_API_KEY_1", "sk-SENTINEL-xyz")

    class _NoState:
        def execute(self, sql, params=()):
            return _Cur([])   # no controller state rows
    d = CPS.pool_lanes_detail(_NoState(), function="PMAP")
    assert d["function"] == "PMAP"
    models = {m["model"]: m for m in d["models"]}
    assert "groq/compound-mini" in models
    lanes = models["groq/compound-mini"]["lanes"]
    assert len(lanes) == 6
    assert all(l["account_env"].startswith("GROQ_API_KEY_") for l in lanes)
    assert lanes[0]["capacity"]["map_batch_cap"] == 15
    # NEVER a secret value anywhere in the payload
    import json
    assert "sk-SENTINEL-xyz" not in json.dumps(d)
