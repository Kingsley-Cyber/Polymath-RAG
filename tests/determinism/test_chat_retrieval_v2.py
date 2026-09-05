"""CHAT-RETRIEVAL-V2 route (P1.a): the shared FastSearcher filter builder is
the one place corpus / generation isolation lives (§3.21 #11, §5b 15–16);
no sparse companion probe when built without a query (#1); live: the chat
path retrieves on chat-retrieval-v2 with provenance on every candidate and
the v1 rollback still answers."""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import fast as fast_api  # noqa: E402
from orchestrator.api.chat_retrieval import chat_retrieval_flag  # noqa: E402


class _Pts:
    def __init__(self, points):
        self.points = points


class FakeClient:
    def __init__(self):
        self.calls = []

    def query_points(self, **kw):
        self.calls.append(kw)
        return _Pts([])


def _filters_of(kw):
    f = kw["query_filter"]
    must = sorted((c.key, getattr(c.match, "value", None) or tuple(getattr(c.match, "any", []) or [])) for c in f.must)
    must_not = sorted((c.key, getattr(c.match, "value", None) or tuple(getattr(c.match, "any", []) or [])) for c in f.must_not)
    return must, must_not


def test_dense_and_sparse_searches_share_one_filter_builder_and_no_companion_probe_without_a_query():
    client = FakeClient()
    s = fast_api.FastSearcher(client, {"cinema": "coll"})            # no query → no sparse companion (§3.21 #1)
    s._hidden_cache = {"cinema": ["gen-rebuilding"]}                 # GENERATION-SWAP-V1 hidden generation, no DB
    filters = {"representation_kind": "routing_child", "corpus_id": "cinema"}
    s._search("coll", [0.1, 0.2], filters, limit=7)
    s.sparse_search("coll", ((1, 2, 3), (0.5, 0.4, 0.3)), filters, limit=9)
    assert len(client.calls) == 2                                    # ONE dense + ONE sparse call, nothing else
    dense, sparse = client.calls
    assert _filters_of(dense) == _filters_of(sparse)
    must, must_not = _filters_of(dense)
    assert ("corpus_id", "cinema") in must and ("representation_kind", "routing_child") in must
    assert ("chunk_contract_version", "gen-rebuilding") in must_not  # rebuilding projection chunks never leak (§5b 16)
    assert dense["limit"] == 7 and sparse["limit"] == 9 and sparse["using"] == "bm25"
    # deepening filters (doc + parent) travel through the same builder
    s._search("coll", [0.1], {**filters, "doc_id": "d1", "parent_id": "p1"}, limit=3)
    must3, _ = _filters_of(client.calls[-1])
    assert ("doc_id", "d1") in must3 and ("parent_id", "p1") in must3
    # no sparse query → typed failure, never a silent empty lane
    with pytest.raises(RuntimeError):
        s.sparse_search("coll", None, filters, limit=5)


def test_companion_probe_still_fires_for_the_v1_routes_built_with_a_query(monkeypatch):
    client = FakeClient()
    s = fast_api.FastSearcher(client, {"cinema": "coll"})
    s._sparse_query = ([1], [1.0])                                   # what the v1 constructor sets from the query text
    s._hidden_cache = {"cinema": []}
    s._search("coll", [0.1], {"representation_kind": "routing_child", "corpus_id": "cinema"}, limit=5)
    assert len(client.calls) == 2 and client.calls[1].get("using") == "bm25"   # v1 behaviour untouched


def test_flag_defaults_to_v2_and_accepts_overrides(monkeypatch):
    monkeypatch.delenv("POLYMATH_CHAT_RETRIEVAL", raising=False)
    assert chat_retrieval_flag() == "v2" and chat_retrieval_flag("v1") == "v1" and chat_retrieval_flag("nonsense") == "v2"
    monkeypatch.setenv("POLYMATH_CHAT_RETRIEVAL", "v1")
    assert chat_retrieval_flag() == "v1" and chat_retrieval_flag("v2") == "v2"


# ---------------- live ----------------

def _stream(body: dict) -> tuple[list[dict], dict]:
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    phases, answer, cur = [], {}, None
    with urllib.request.urlopen(req, timeout=420) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "phase":
                phases.append(json.loads(line[5:].strip()))
            elif line.startswith("data:") and cur == "answer":
                answer = json.loads(line[5:].strip())
    return phases, answer


@pytest.mark.parametrize("retrieval", ["v2", "v1"])
def test_live_chat_hybrid_retrieves_on_v2_with_provenance_and_v1_still_answers(retrieval):
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    phases, answer = _stream({"message": "What does the book say about making your own chroma keyer?", "corpus_id": "cinema",
                              "mode": "HYBRID", "compiler": "on", "retrieval": retrieval, "synthesizer": "deterministic-template-v3"})
    ret = answer.get("retrieval") or {}
    done = next((p for p in phases if p.get("stage") == "retrieve_done"), {})
    if retrieval == "v2":
        assert ret.get("engine") == "chat-retrieval-v2" and done.get("plan") == "chat-retrieval-v2", (ret.get("engine"), done)
        lanes = ret.get("funnel", {}).get("lane_counts") or {}
        assert lanes.get("global_dense_child", 0) > 0 and lanes.get("hierarchical", 0) > 0, lanes
        arrivals = ret.get("arrivals") or {}
        assert arrivals and all(v for v in arrivals.values()), arrivals             # 100 % of final candidates have arrivals
        assert set(arrivals) == {c for c in ret.get("used_evidence", [])} | set(arrivals)
        assert ret["funnel"]["counts"]["union"] >= ret["funnel"]["counts"]["pre_rerank"] >= ret["funnel"]["counts"]["selected"] > 0
    else:
        assert ret.get("engine") == "hybrid-retrieval-v1" and ret.get("funnel", {}).get("counts", {}).get("selected", 0) > 0
