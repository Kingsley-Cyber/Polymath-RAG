"""RETRIEVAL-FUNNEL-V1 (CHAT-QUERY-COMPILER plan §3.9, phase P0.0).

Law 1  the funnel is a pure function of the stage id lists: counts, ranks and
       the death classification are deterministic and total.
Law 2  receipts never lose the funnel to JSON slicing: meta serialization is
       structurally shrunk, always valid JSON.
Law 3  (live, skipped when the orchestrator is not reachable) one /chat/stream
       turn writes a `chat_stream` receipt whose meta carries all six stages.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

from polymath_shared import funnel as F  # noqa: E402
from polymath_shared.query_receipts import _meta_json, summarize_response  # noqa: E402


def _f():
    return F.build_funnel(
        lanes={"hierarchical": ["a", "b", "c"], "global_dense_child": ["c", "d", "e"], "global_sparse_child": ["e", "f"]},
        union=["a", "b", "c", "d", "e", "f"],
        pre_rerank=["a", "b", "c", "d", "e"],          # f truncated before the reranker
        post_rerank=["c", "a", "e", "b", "d"],
        selected=["c", "a", "e"],                       # b, d lost at selection
        cited=["c"],                                    # a, e ignored by the LLM
        plan_version="hybrid-retrieval-v1")


def test_funnel_counts_ranks_and_arrivals_are_deterministic():
    f = _f(); g = _f()
    assert f == g
    assert f["counts"] == {"retrieved": 6, "union": 6, "pre_rerank": 5, "post_rerank": 5, "selected": 3, "cited": 1}
    assert f["lane_counts"] == {"hierarchical": 3, "global_dense_child": 3, "global_sparse_child": 2}
    assert f["multi_lane"] == 2                       # c and e were found by two lanes
    assert f["arrivals"]["c"] == ["global_dense_child", "hierarchical"]
    r = F.rank_at(f, "c")
    assert (r["union"], r["post_rerank"], r["selected"], r["cited"]) == (3, 1, 1, 1)
    assert r["lane:global_sparse_child"] is None


def test_every_candidate_gets_exactly_one_death():
    f = _f()
    deaths = {cid: F.where_did_it_die(f, cid) for cid in "abcdefz"}
    assert deaths == {"a": "IGNORED_BY_LLM", "b": "LOST_AT_SELECTION", "c": "CITED", "d": "LOST_AT_SELECTION",
                      "e": "IGNORED_BY_LLM", "f": "LOST_AT_UNION_TRUNCATION", "z": "NEVER_RETRIEVED"}
    assert set(deaths.values()) <= set(F.DEATHS)


def test_funnel_from_trace_reads_the_engine_trace_keys():
    trace = {"plan": "pass1-retrieval-v2", "funnel_lanes": {"hierarchical": ["x"], "global_dense_child": ["y"]},
             "funnel_union": ["x", "y"], "pre_g3_order": ["x", "y"], "post_g3_order": ["y", "x"]}
    f = F.funnel_from_trace(trace, selected=["y"], cited=[])
    assert f["plan_version"] == "pass1-retrieval-v2"
    assert f["stages"]["post_rerank"] == ["y", "x"] and f["stages"]["selected"] == ["y"]
    assert F.where_did_it_die(f, "x") == "LOST_AT_SELECTION" and F.where_did_it_die(f, "y") == "IGNORED_BY_LLM"


def test_stage_cap_and_compact_keep_valid_json():
    big = F.build_funnel(lanes={"global_dense_child": [f"c{i}" for i in range(500)]}, union=[f"c{i}" for i in range(500)],
                         pre_rerank=[f"c{i}" for i in range(40)], post_rerank=[f"c{i}" for i in range(40)],
                         selected=[f"c{i}" for i in range(12)], cited=["c1"])
    assert len(big["stages"]["retrieved"]) == F.STAGE_CAP and big["counts"]["retrieved"] == 500
    small = F.compact(big, max_chars=2000)
    assert json.loads(json.dumps(small)) and small.get("truncated") in ("ids_capped", "counts_only")
    assert small["counts"] == big["counts"]


def test_receipt_meta_is_never_sliced_into_invalid_json():
    huge = {"funnel": _f(), "legend": [{"tag": f"S{i}", "locator": "chunk:" + "x" * 80} for i in range(3000)], "mode": "HYBRID"}
    txt = _meta_json(huge)
    assert len(txt) <= 64_000
    back = json.loads(txt)                       # would raise on a sliced string
    assert back["mode"] == "HYBRID" and back["funnel"]["counts"]["cited"] == 1
    summ = summarize_response("chat_stream", {"answer": "x", "meta": {"funnel": _f(), "chat_plan": {"a": 1}, "junk": 1}})
    assert "funnel" in summ["meta"] and "chat_plan" in summ["meta"] and "junk" not in summ["meta"]


def test_live_stream_turn_writes_a_receipt_with_all_six_stages():
    """Law 3 — against the running orchestrator and dev Postgres; skips otherwise."""
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    try:
        import psycopg
        dsn = os.environ.get("POLYMATH_TEST_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
        conn = psycopg.connect(dsn, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"dev postgres not reachable: {exc}")
    q = "funnel-probe: what is the 180-degree rule?"
    body = json.dumps({"message": q, "corpus_id": "cinema", "mode": "HYBRID",
                       "synthesizer": "deterministic-template-v3"}).encode()
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=body,
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    saw_answer = False
    with urllib.request.urlopen(req, timeout=240) as r:
        for raw in r:
            if raw.startswith(b"event: answer"):
                saw_answer = True
    assert saw_answer
    row = conn.execute("""SELECT kind, meta FROM query_receipts WHERE kind='chat_stream' AND question_head=%s
                          ORDER BY received_at DESC LIMIT 1""", (q,)).fetchone()
    conn.close()
    assert row is not None, "the streaming turn wrote no receipt"
    fun = (row[1] or {}).get("funnel") or {}
    assert fun.get("version") == F.FUNNEL_VERSION
    assert set(fun.get("counts", {})) == set(F.STAGES), fun
    assert fun["counts"]["retrieved"] >= fun["counts"]["selected"] >= fun["counts"]["cited"]
    assert "phase_ms" in row[1] and "retrieve" in row[1]["phase_ms"]
