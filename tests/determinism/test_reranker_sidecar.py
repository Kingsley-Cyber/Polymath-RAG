"""JUDGE-FAST-PATH-V1 (2026-09-06): the reranker sidecar's pure parts — memo, non-finite handling, one-pass batching
with the OOM safety net, defaults and receipts. The model is never loaded here (lifespan only)."""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("reranker_sidecar_server", ROOT / "sidecars" / "reranker" / "server.py")
srv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srv)


def test_defaults_are_fp16_384_tokens_one_pass_and_a_bounded_memo(monkeypatch):
    monkeypatch.delenv("POLYMATH_RERANKER_DTYPE", raising=False)
    assert srv.RERANK_DTYPE in ("fp16", "fp32", "bf16")            # env may pin it; the shipped default is fp16
    assert srv.RERANK_MAX_LENGTH >= 32 and srv.RERANK_BATCH >= 1 and srv.RERANK_MEMO_MAX >= 0
    src = (ROOT / "sidecars" / "reranker" / "server.py").read_text()
    assert 'os.environ.get("POLYMATH_RERANKER_DTYPE", "fp16")' in src
    assert 'os.environ.get("POLYMATH_RERANK_MAX_LENGTH", "384")' in src      # sweep-chosen (judge-v2): 256 cost top-1 agreement
    assert 'os.environ.get("POLYMATH_RERANK_BATCH", "64")' in src
    assert "torch.inference_mode()" in src and "max_length=RERANK_MAX_LENGTH" in src


def test_memo_hits_are_per_scope_lru_touched_and_bounded(monkeypatch):
    monkeypatch.setattr(srv, "RERANK_MEMO_MAX", 3)
    srv._MEMO.clear()
    k = [srv.memo_key("rev|fp16|256", "q", d) for d in ("a", "b", "c")]
    assert srv.memo_lookup(k) == {}                                       # cold
    srv.memo_store(k, [0.1, 0.2, float("nan")])                            # a non-finite score is never memoized
    assert srv.memo_lookup(k) == {0: 0.1, 1: 0.2}
    assert srv.memo_lookup([srv.memo_key("rev|fp32|256", "q", "a")]) == {}   # another dtype / length = another scope
    srv.memo_lookup([k[0]])                                                # touch a → b is now the oldest
    srv.memo_store([srv.memo_key("s", "q", "d"), srv.memo_key("s", "q", "e")], [0.4, 0.5])
    assert len(srv._MEMO) == 3 and srv.memo_lookup([k[1]]) == {} and srv.memo_lookup([k[0]]) == {0: 0.1}
    monkeypatch.setattr(srv, "RERANK_MEMO_MAX", 0)
    srv.memo_store(k, [1.0, 1.0, 1.0])
    assert srv.memo_lookup(k) == {}                                       # off = no hits, no growth


def test_nonfinite_scores_rank_last_and_are_counted():
    scores, n = srv.sanitize_scores([0.5, float("nan"), -2.0, float("inf")])
    assert n == 2 and scores == [0.5, -3.0, -2.0, -3.0]
    assert srv.sanitize_scores([]) == ([], 0) and srv.sanitize_scores([float("nan")]) == ([-1.0e4], 1)


def test_one_forward_pass_per_request_and_the_oom_safety_net_halves(monkeypatch):
    calls: list[int] = []

    def predict(chunk):
        calls.append(len(chunk))
        return [float(i) for i in range(len(chunk))]
    pairs = [["q", f"d{i}"] for i in range(24)]
    assert srv.score_in_batches(predict, pairs, batch=64) == [float(i) for i in range(24)] and calls == [24]
    calls.clear()
    state = {"failed": False}

    def oom_above_12(chunk):
        if len(chunk) > 12:
            raise RuntimeError("MPS backend out of memory (MPS allocated: 3.40 GB)")
        calls.append(len(chunk))
        return [1.0] * len(chunk)
    out = srv.score_in_batches(oom_above_12, pairs, batch=64)
    assert len(out) == 24 and calls == [8, 8, 8]      # cap 64 → 32 → 16 → 8 until the batch fits; nothing lost, order kept


def test_rerank_response_carries_the_judge_receipts():
    r = srv.RerankResponse(scores=[1.0], order=[0], model_id="m", model_revision="r")
    assert r.dtype is None and r.memo_hits == 0 and r.memo_misses == 0 and r.nonfinite == 0 and r.dtype_fallback is None
    r2 = srv.RerankResponse(scores=[1.0], order=[0], model_id="m", model_revision="r", dtype="fp16", max_length=256, batch=64, memo_hits=3, memo_misses=21)
    assert r2.model_dump()["dtype"] == "fp16" and r2.max_length == 256 and r2.batch == 64


def test_the_endpoint_scores_without_torch_installed(monkeypatch):
    """CI has no torch: the inference scope degrades to a no-op and the wire contract (scores, order, receipts) holds."""
    import sys
    from fastapi.testclient import TestClient
    monkeypatch.setitem(sys.modules, "torch", None)                 # `import torch` raises ImportError inside the request

    class FakeCrossEncoder:
        def predict(self, pairs):
            return [float(len(p[1])) for p in pairs]
    srv._MEMO.clear()
    srv.app.state.model = FakeCrossEncoder()
    srv.app.state.device = "cpu"
    srv.app.state.dtype = "fp32"
    srv.app.state.dtype_fallback = None
    srv.app.state.manifest = {"identity": {"model": {"id": "m", "revision": "r"}}}
    body = TestClient(srv.app).post("/rerank", json={"query": "q", "documents": ["a", "bbb", "cc"]}).json()
    assert body["scores"] == [1.0, 3.0, 2.0] and body["order"] == [1, 2, 0]
    assert body["dtype"] == "fp32" and body["memo_misses"] == 3 and body["memo_hits"] == 0 and body["nonfinite"] == 0
    again = TestClient(srv.app).post("/rerank", json={"query": "q", "documents": ["bbb", "zzzz"]}).json()
    assert again["scores"] == [3.0, 4.0] and again["memo_hits"] == 1 and again["memo_misses"] == 1   # memo across requests

