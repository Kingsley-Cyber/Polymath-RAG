"""CONTROL-PLANE-STATUS-V1 + corpus document summaries (operational UI backend).

Provider-free, DB-free: a scripted fake connection drives the batch summary + the
control-plane rollup; the lane detail runs against the real committed config with NO
secret rendered. Asserts the four functional pools, the per-document vnext_ready rule,
the LOCAL limiter_refused vs ACTUAL HTTP 429 distinction, the GAP-4 age-qualified
processing split, and the GAP-1 composed control_ready verdict.
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
        if "to_regclass('public.document_chunk_summary')" in s:
            return _Cur([("document_chunk_summary",)])
        if "child_count, parent_count, map_eligible_count" in s:
            return _Cur([("docA", 8, 3, 3), ("docB", 0, 5, 5)])
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
            return _Cur([(1, 0)])                          # one in-flight run, still fresh (GAP-4)
        if "FROM stage_tickets WHERE corpus_id" in s:
            return _Cur([("extract", "ready", 0, 2), ("doc_parent_map", "leased", 0, 1)])
        if "a.stage='doc_parent_map'" in s:                # pMAP provider conservation
            return _Cur([(9, 3, 1, 0, 8, 0)])              # disp, refused, 429, fail, mapped, empty
        if "a.stage='extract'" in s:                       # graph provider
            return _Cur([(12, 47, 0, 1, 47, 19)])
        # pipeline_health() (GAP-1 control_ready composition) — fleet-wide, not
        # corpus-scoped, so these are distinct fragments from the corpus queries above.
        if "FROM worker_registrations" in s:
            return _Cur([])                                # no live workers -> IDLE
        if "WHERE status IN ('ready','leased')" in s:
            return _Cur([(0,)])                             # nothing queued fleet-wide
        # FILES-STATUS-TRUTH-V1: each file's own run and its open / failed tickets
        if "FROM runs r JOIN outbox_events e" in s and "chunked.v1" in s:
            return _Cur([("docA", "run_a", "query_ready"), ("docB", "run_b", "reconciling")])
        if "FROM stage_tickets" in s and "run_id = ANY" in s:
            return _Cur([("run_b", "project_neo4j", "ready", None)])
        raise AssertionError(f"unscripted SQL: {s[:80]}")


def test_corpus_summaries_apply_vnext_ready_rule():
    s = corpus_document_summaries(_Conn(), corpus_id="c")
    assert s["docA"]["vnext_ready"] is True                 # 3/3 mapped + vNext profile
    assert s["docB"]["vnext_ready"] is False                # 1/5 mapped -> unresolved 4
    assert s["docA"]["graph_entities"] == 42 and s["docA"]["graph_relations"] == 17
    assert s["docB"]["map_unresolved"] == 4
    assert (s["docA"]["run_status"], s["docA"]["work_open"]) == ("query_ready", [])
    assert (s["docB"]["run_status"], s["docB"]["work_open"], s["docB"]["work_failed"]) == ("reconciling", ["project_neo4j"], [])


def test_control_plane_status_four_pools_and_refused_vs_429():
    cp = CPS.control_plane_status(_Conn(), corpus_id="c")
    assert cp["summary"] == {
        "documents": 2, "semantic_ready": 1, "vnext_served": None, "basic_profile": 0,
        "processing": 1, "processing_active": 1, "processing_stalled": 0,
        "blocked": 1,                                       # docB: 4 unresolved parents — retrieval misses part of it
    }
    # GAP-1: composed once, here — never left for the UI to derive from two calls.
    assert cp["control_ready"]["state"] == "ready"
    assert cp["control_ready"]["label"] == "IDLE"
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


class _BaseProfileConn(_Conn):
    """docB fully mapped with only the BASE profile (the fleet's default since 2026-09-17), docC never profiled."""
    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "SELECT doc_id FROM documents WHERE corpus_id" in s:
            return _Cur([("docA",), ("docB",), ("docC",)])
        if "child_count, parent_count, map_eligible_count" in s:
            return _Cur([("docA", 8, 3, 3), ("docB", 6, 5, 5), ("docC", 4, 2, 2)])
        if "COUNT(DISTINCT parent_id) FROM document_parent_maps" in s:
            return _Cur([("docA", 3), ("docB", 5), ("docC", 2)])
        if "a.stage='doc_profile'" in s and "DISTINCT ON" in s:
            return _Cur([("docA", "true"), ("docB", "false")])
        if "a.stage='extract'" in s and "DISTINCT ON" in s:
            return _Cur([])
        return super().execute(sql, params)


def test_a_searchable_file_without_the_vnext_profile_is_not_counted_blocked():
    """LIBRARY-READY-LABEL (the owner, 2026-10-01: "why is a corpus for taste showing files as red"): the summary follows the
    per-file rule — mapped + any profile = searchable; only a file retrieval would miss part of is blocked."""
    cp = CPS.control_plane_status(_BaseProfileConn(), corpus_id="c")
    s = cp["summary"]
    assert (s["documents"], s["semantic_ready"], s["basic_profile"], s["blocked"]) == (3, 1, 1, 1)     # docA vNext, docB basic, docC no profile
    assert s["semantic_ready"] + s["basic_profile"] + s["blocked"] == s["documents"]


def test_ready_vnext_counts_cards_search_serves_when_the_index_answered():
    """SERVED-PROFILE-LABEL (2026-10-01): cinema had a vNext card written on every file and served on none — "ready (vNext)"
    must count what search serves; `semantic_ready` (written cards; scripts read it) is unchanged; no index answer = the
    previous counting."""
    cp = CPS.control_plane_status(_BaseProfileConn(), corpus_id="c", served={"docA": {"writer": "basic"}, "docB": {"writer": "basic"}})
    s = cp["summary"]
    assert (s["semantic_ready"], s["vnext_served"], s["basic_profile"], s["blocked"]) == (1, 0, 2, 1)
    s = CPS.control_plane_status(_BaseProfileConn(), corpus_id="c", served={"docA": {"writer": "vnext"}})["summary"]
    assert (s["vnext_served"], s["basic_profile"]) == (1, 1)
    s = CPS.control_plane_status(_BaseProfileConn(), corpus_id="c")["summary"]
    assert (s["vnext_served"], s["basic_profile"]) == (None, 1)


def test_pool_lanes_detail_is_secret_free_and_model_grouped():
    import os
    os.environ.setdefault("GROQ_API_KEY_1", "sk-SENTINEL-xyz")

    class _NoState:
        def execute(self, sql, params=()):
            return _Cur([])   # no controller state rows
    d = CPS.pool_lanes_detail(_NoState(), function="PMAP")
    assert d["function"] == "PMAP"
    models = {m["model"]: m for m in d["models"]}
    # GROQ-MODEL-SWAP-2026-09-23: every pMAP key carries one lane per model (gpt-oss-20b + qwen3.8-27b); since
    # LLM-BACKEND L3 (11.467) all six keys do (11.193 had moved KEY_1 to doc_profile only)
    for model in ("openai/gpt-oss-20b", "qwen/qwen3.8-27b"):
        assert model in models
        lanes = models[model]["lanes"]
        assert len(lanes) == 6
        assert {l["account_env"] for l in lanes} == {f"GROQ_API_KEY_{i}" for i in range(1, 7)}
        assert lanes[0]["capacity"]["map_batch_cap"] == 15
    # NEVER a secret value anywhere in the payload
    import json
    assert "sk-SENTINEL-xyz" not in json.dumps(d)
