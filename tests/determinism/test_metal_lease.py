"""METAL-LEASE-V1 (P1.d, plan §3.16 / §3.21 #18): the embedder and the
reranker share ONE Metal device across two processes. Measured 2026-09-06:
an 8-text enrichment embed landing during an interactive 20-pair rerank
pushed both past the pool ("rerank batch OOM at 8 pairs; retrying at 4";
4.5 s -> 27-52 s) and a 1-2 text chat embed waited 3-4 s behind enrichment
batches. The lease makes device batches mutually exclusive across
processes and gives the interactive class priority; every failure mode is
fail-open and bounded. Pure: no GPU, no network, temp lock dir."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import clients as C  # noqa: E402
from polymath_shared import metal  # noqa: E402
from polymath_shared.metal import (  # noqa: E402
    BACKGROUND,
    INTERACTIVE,
    PRIORITY_HEADER,
    device_lease,
    interactive_pending,
    is_oom,
    leased_run_adaptive,
    normalize_priority,
    priority_headers,
    priority_scope,
    release,
    run_adaptive,
)


@pytest.fixture
def fleet_dir(tmp_path, monkeypatch):
    """Every test coordinates on its own lock dir — never the live fleet's."""
    d = tmp_path / "fleet"
    monkeypatch.setenv("POLYMATH_FLEET_DIR", str(d))
    monkeypatch.delenv("POLYMATH_METAL_LEASE", raising=False)
    monkeypatch.delenv("POLYMATH_METAL_LEASE_INTERACTIVE_TIMEOUT_S", raising=False)
    monkeypatch.delenv("POLYMATH_METAL_LEASE_BACKGROUND_TIMEOUT_S", raising=False)
    return d


def _wait_until(pred, budget_s: float = 2.0) -> None:
    deadline = time.monotonic() + budget_s
    while not pred():
        assert time.monotonic() < deadline, "condition not reached in time"
        time.sleep(0.001)


# ------------------------------------------------------------- existing surface

def test_existing_public_surface_is_unchanged():
    """run_adaptive / release / is_oom keep their signatures and semantics."""
    assert is_oom(RuntimeError("MPS backend out of memory")) and not is_oom(ValueError("out of memory"))
    release()                                               # no torch on the path → silent no-op
    seen: list[int] = []

    def fn(items):
        seen.append(len(items))
        if len(items) > 2:
            raise RuntimeError("MPS backend out of memory")
        return [i * 10 for i in items]

    assert run_adaptive(fn, [1, 2, 3, 4, 5], what="t") == [10, 20, 30, 40, 50]
    assert seen == [5, 2, 3, 1, 2]                              # 5 → 2+3, 3 → 1+2; order preserved


# ------------------------------------------------------------- (a) two processes

_CHILD = r'''
import json, sys, time
sys.path.insert(0, sys.argv[2])
import polymath_shared.metal as m
with m.device_lease(sys.argv[1], timeout_s=10) as r:
    t_in = time.time(); time.sleep(0.2); t_out = time.time()
print(json.dumps({"t_in": t_in, "t_out": t_out, "receipt": r.as_dict()}))
'''


def test_mutual_exclusion_across_two_processes(fleet_dir):
    """The real fcntl implementation: while this process holds the device,
    neither child acquires; afterwards their hold intervals are disjoint and
    the interactive child goes first."""
    env = dict(os.environ, POLYMATH_FLEET_DIR=str(fleet_dir))
    with device_lease(BACKGROUND, what="holder") as holder:
        assert holder.acquired and holder.mode == "locked"
        procs = [subprocess.Popen([sys.executable, "-c", _CHILD, prio, str(ROOT / "shared")],
                                  stdout=subprocess.PIPE, text=True, env=env)
                 for prio in (BACKGROUND, INTERACTIVE)]
        time.sleep(0.5)                                     # both children are now waiting
        t_release = time.time()
    outs = [json.loads(p.communicate(timeout=30)[0]) for p in procs]
    for o in outs:
        assert o["receipt"]["acquired"] and o["receipt"]["mode"] == "locked", o
        assert o["t_in"] >= t_release - 0.01, (o, t_release)   # nobody ran while the parent held
    first, second = sorted(outs, key=lambda o: o["t_in"])
    assert first["t_out"] <= second["t_in"] + 0.001, (first, second)   # disjoint holds
    assert first["receipt"]["priority"] == INTERACTIVE          # priority honoured across processes
    assert second["receipt"]["yielded"] is True and second["receipt"]["waited_ms"] >= 600


# ------------------------------------------------------------- (b) priority order

def test_interactive_waiter_is_served_before_a_queued_background_caller(fleet_dir):
    """Deterministic: background B queues first, interactive I registers
    second; when the holder releases, I acquires and B waits for I."""
    order: list[tuple[str, metal.LeaseReceipt]] = []
    b_started = threading.Event()

    def background():
        b_started.set()
        with device_lease(BACKGROUND, timeout_s=5) as r:
            order.append((BACKGROUND, r))

    def interactive():
        with device_lease(INTERACTIVE, timeout_s=5) as r:
            order.append((INTERACTIVE, r))
            time.sleep(0.05)                                # hold: B must not be running meanwhile

    with device_lease(BACKGROUND, what="holder"):
        tb = threading.Thread(target=background); tb.start()
        b_started.wait(1.0); time.sleep(0.05)               # B is polling behind the holder
        ti = threading.Thread(target=interactive); ti.start()
        _wait_until(interactive_pending)                    # I is registered before the release
    tb.join(5); ti.join(5)
    assert [name for name, _ in order] == [INTERACTIVE, BACKGROUND]
    i_receipt, b_receipt = order[0][1], order[1][1]
    assert i_receipt.acquired and not i_receipt.yielded and i_receipt.waited_ms < 1000
    assert b_receipt.acquired and b_receipt.yielded and b_receipt.waited_ms >= i_receipt.waited_ms
    assert metal.lease_stats()["background.yielded"] >= 1


def test_priority_scope_keeps_background_out_between_interactive_batches(fleet_dir):
    """An interactive REQUEST spans several device batches; the scope keeps
    it registered in the gaps so a background batch cannot slip in."""
    with priority_scope(INTERACTIVE) as registered:
        assert registered is True and interactive_pending()
        with device_lease(BACKGROUND, timeout_s=0.3) as r:
            assert r.timed_out and not r.acquired and r.yielded and r.waited_ms >= 250
        with device_lease(INTERACTIVE, timeout_s=1) as r:  # interactive batches still run
            assert r.acquired
    assert not interactive_pending()
    with priority_scope(BACKGROUND) as registered:          # no-op for background
        assert registered is False
    with device_lease(BACKGROUND, timeout_s=1) as r:
        assert r.acquired and not r.yielded and r.waited_ms < 200


# ------------------------------------------------------------- (c) fail-open

def test_fail_open_when_the_lock_dir_cannot_be_created(fleet_dir, monkeypatch):
    blocker = fleet_dir.parent / "blocker"
    blocker.write_text("a regular file where the fleet dir should be")
    monkeypatch.setenv("POLYMATH_FLEET_DIR", str(blocker / "fleet"))   # mkdir fails: parent is a file
    ran = False
    with device_lease(INTERACTIVE, timeout_s=1) as r:
        ran = True
        assert r.mode == "open" and r.acquired and not r.timed_out
    assert ran
    with priority_scope(INTERACTIVE) as registered:
        assert registered is False
    assert interactive_pending() is False


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory modes")
def test_fail_open_when_the_lock_dir_is_unwritable(fleet_dir):
    fleet_dir.mkdir(parents=True)
    fleet_dir.chmod(0o500)
    try:
        with device_lease(BACKGROUND, timeout_s=1) as r:
            assert r.mode == "open" and r.acquired
        assert list(fleet_dir.iterdir()) == []              # nothing was created
    finally:
        fleet_dir.chmod(0o700)


def test_kill_switch_disables_the_file_lease(fleet_dir, monkeypatch):
    monkeypatch.setenv("POLYMATH_METAL_LEASE", "0")
    with device_lease(INTERACTIVE) as r:
        assert r.mode == "disabled" and r.acquired and r.waited_ms < 50
    assert not fleet_dir.exists()                           # no lock files touched


# ------------------------------------------------------------- (d) bounded waits

def test_timeouts_bound_the_wait_and_the_caller_proceeds(fleet_dir, monkeypatch):
    with device_lease(BACKGROUND, what="holder"):
        t0 = time.monotonic()
        with device_lease(INTERACTIVE, timeout_s=0.2) as r:
            assert r.timed_out and not r.acquired and 150 <= r.waited_ms <= 2000
        assert time.monotonic() - t0 < 2.0
        with device_lease(BACKGROUND, timeout_s=0.2) as r:
            assert r.timed_out and not r.acquired and 150 <= r.waited_ms <= 2000
        monkeypatch.setenv("POLYMATH_METAL_LEASE_INTERACTIVE_TIMEOUT_S", "0.1")
        with device_lease(INTERACTIVE) as r:                # default budget comes from the env
            assert r.timed_out and 80 <= r.waited_ms <= 1500
    assert not interactive_pending()                        # a timed-out interactive left no registration
    assert metal.lease_timeout_s(INTERACTIVE) == 0.1 and metal.lease_timeout_s(BACKGROUND) == 30.0
    monkeypatch.delenv("POLYMATH_METAL_LEASE_INTERACTIVE_TIMEOUT_S")
    assert metal.lease_timeout_s(INTERACTIVE) == 10.0
    stats = metal.lease_stats()
    assert stats["interactive.timed_out"] >= 2 and stats["background.timed_out"] >= 1


def test_leased_run_adaptive_keeps_oom_splitting_and_receipts(fleet_dir):
    seen: list[int] = []

    def fn(items):
        seen.append(len(items))
        if len(items) > 2:
            raise RuntimeError("MPS backend out of memory")
        return [i + 100 for i in items]

    receipts: list[metal.LeaseReceipt] = []
    out = leased_run_adaptive(BACKGROUND, fn, [1, 2, 3, 4], what="embed", receipts=receipts)
    assert out == [101, 102, 103, 104] and seen == [4, 2, 2]
    # per-attempt leasing (P1.d arm 2 fix): one receipt per device call — the failed 4-item attempt and both 2-item retries —
    # so the device is released between OOM-halving sub-batches and an interactive waiter gets in
    assert len(receipts) == 3 and all(r.acquired and r.what == "embed" for r in receipts)
    with pytest.raises(ValueError):
        leased_run_adaptive(INTERACTIVE, lambda items: (_ for _ in ()).throw(ValueError("x")), [1])
    assert not interactive_pending()                        # the lease is released on error


# ------------------------------------------------------------- (e) header plumbing

class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class _RecordingHttp:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[dict] = []

    def post(self, path, **kw):
        self.calls.append({"path": path, **kw})
        return _Resp(self.payload)

    def close(self):
        pass


def _swap_http(client, payload):
    C.SidecarClient._refused_until.clear()
    client._client.close()
    fake = _RecordingHttp(payload)
    client._client = fake
    return fake


def test_priority_helpers():
    assert normalize_priority(None) == BACKGROUND
    assert normalize_priority(" Interactive ") == INTERACTIVE
    assert normalize_priority("urgent") == BACKGROUND
    assert priority_headers(None) == {PRIORITY_HEADER: BACKGROUND}
    assert priority_headers("interactive") == {PRIORITY_HEADER: INTERACTIVE}
    assert PRIORITY_HEADER == "X-Polymath-Priority"


def test_embedder_client_sends_the_priority_header_default_background():
    client = C.EmbedderClient()
    fake = _swap_http(client, {"vectors": [[0.0]]})
    try:
        client.embed(["t"], "query")
        assert fake.calls[-1]["headers"] == {PRIORITY_HEADER: BACKGROUND}
        assert fake.calls[-1]["json"] == {"texts": ["t"], "representation_kind": "query"}
        client.embed(["t"], "query", priority="interactive")             # per-call override
        assert fake.calls[-1]["headers"] == {PRIORITY_HEADER: INTERACTIVE}
    finally:
        client.close()
    client = C.EmbedderClient(priority="interactive")                    # instance class (the chat path)
    fake = _swap_http(client, {"vectors": [[0.0]]})
    try:
        client.embed(["t"], "query")
        assert fake.calls[-1]["headers"] == {PRIORITY_HEADER: INTERACTIVE}
        assert client.infer({"texts": ["t"], "representation_kind": "query"}) == {"vectors": [[0.0]]}
        assert fake.calls[-1]["headers"] is None                         # bare infer(): no header, as before
    finally:
        client.close()


def test_reranker_client_sends_the_priority_header_default_background():
    payload = {"scores": [0.5], "order": [0], "model_id": "m", "model_revision": "r"}
    client = C.RerankerClient()
    fake = _swap_http(client, payload)
    try:
        client.rerank("q", ["d"])
        assert fake.calls[-1]["path"] == "/rerank"
        assert fake.calls[-1]["headers"] == {PRIORITY_HEADER: BACKGROUND}
        assert fake.calls[-1]["json"] == {"query": "q", "documents": ["d"], "top_k": None}
        client.rerank("q", ["d"], priority="interactive")
        assert fake.calls[-1]["headers"] == {PRIORITY_HEADER: INTERACTIVE}
    finally:
        client.close()
    client = C.RerankerClient(priority="interactive")
    fake = _swap_http(client, payload)
    try:
        client.rerank("q", ["d"], top_k=1)
        assert fake.calls[-1]["headers"] == {PRIORITY_HEADER: INTERACTIVE}
    finally:
        client.close()


def test_rerank_wrapper_threads_priority_and_keeps_legacy_clients_working():
    """`_batched_scores` spells the class out only when elevated, so a
    duck-typed client without the kwarg (every existing test double) still
    works on the default path; `queued_ms` is summed into the merged shape."""
    from polymath_shared import rerank as R

    class Legacy:
        def __init__(self):
            self.calls = []

        def rerank(self, query, documents, top_k=None):
            self.calls.append(len(documents))
            return {"scores": [float(len(d)) for d in documents], "order": [],
                    "model_id": "m", "model_revision": "r", "queued_ms": 1.5}

    class Recording(Legacy):
        def rerank(self, query, documents, top_k=None, priority=None):
            self.priority = priority
            return super().rerank(query, documents, top_k)

    surfaces = [f"{'x' * i}" for i in range(1, 71)]        # 70 → 64 + 6 (JUDGE-FAST-PATH-V1: one request per judge call ≤ 64)
    legacy = Legacy()
    resp = R._batched_scores(legacy, "q", surfaces)
    assert legacy.calls == [64, 6] and resp["queued_ms"] == 3.0
    assert resp["order"][0] == 69 and resp["scores"][69] == 70.0
    rec = Recording()
    R._batched_scores(rec, "q", surfaces, priority="interactive")
    assert rec.priority == "interactive"
    _, kids = R.rerank_fused("q", [], [{"chunk_id": "a", "text": "aa"}, {"chunk_id": "b", "text": "b"}],
                             client=rec, priority="interactive")
    assert [k["chunk_id"] for k in kids] == ["a", "b"] and rec.priority == "interactive"
    _, kids = R.rerank_fused("q", [], [{"chunk_id": "a", "text": "aa"}], client=Legacy())   # default path
    assert kids[0]["rerank_score"] == 2.0


def test_apply_rerank_builds_an_interactive_client_for_the_chat_path(monkeypatch):
    from polymath_shared import rerank as R

    built = {}

    class FakeReranker:
        def __init__(self, timeout=60.0, *, priority="background"):
            built["priority"] = priority

        def rerank(self, query, documents, top_k=None, priority=None):
            built["call_priority"] = priority
            return {"scores": [1.0] * len(documents), "order": list(range(len(documents))),
                    "model_id": "m", "model_revision": "r"}

        def close(self):
            pass

    monkeypatch.setattr(C, "RerankerClient", FakeReranker)
    monkeypatch.setattr(R, "rerank_enabled", lambda: True)
    monkeypatch.setattr(R, "_await_reranker", lambda client: None)
    R.apply_rerank("q", [], [{"chunk_id": "a", "text": "t"}], priority="interactive")
    assert built == {"priority": "interactive", "call_priority": "interactive"}
    R.apply_rerank("q", [], [{"chunk_id": "a", "text": "t"}])
    assert built == {"priority": "background", "call_priority": None}     # default = the pre-lease shape


def test_orchestrator_chat_path_declares_interactive():
    """Static fence on the two chat-path call sites (the integrator edits
    fast.py concurrently; a merge must not drop the class)."""
    tree = ast.parse((ROOT / "orchestrator/orchestrator/api/fast.py").read_text())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    embed_src = ast.unparse(fns["_embed_queries"])
    rerank_src = ast.unparse(fns["_rerank_children"])
    assert "EmbedderClient(priority='interactive')" in embed_src, embed_src
    assert "apply_rerank(query, [], children, priority='interactive')" in rerank_src, rerank_src


# ------------------------------------------------------------- (f) sidecar mapping

def _load_sidecar(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_server", ROOT / "sidecars" / name / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                            # lifespan (model load) does not run on import
    return mod


@pytest.mark.parametrize("name", ["embedder", "reranker"])
def test_sidecar_header_to_priority_mapping(name):
    mod = _load_sidecar(name)
    assert mod.request_priority(None) == BACKGROUND
    assert mod.request_priority("interactive") == INTERACTIVE
    assert mod.request_priority(" INTERACTIVE ") == INTERACTIVE
    assert mod.request_priority("background") == BACKGROUND
    assert mod.request_priority("urgent") == BACKGROUND
    endpoint = mod.infer if name == "embedder" else mod.rerank
    import inspect
    param = inspect.signature(endpoint).parameters["x_polymath_priority"]
    assert param.default.alias == PRIORITY_HEADER           # the header is declared on the endpoint
    response_model = mod.EmbedResponse if name == "embedder" else mod.RerankResponse
    fields = response_model.model_fields
    assert fields["queued_ms"].default == 0.0 and fields["priority"].default == BACKGROUND
    assert mod.PROBE_LEASE_TIMEOUT_S <= 10.0


class _Vec(list):
    def tolist(self):
        return list(self)


def test_embedder_endpoint_receipts_queued_ms_and_priority(fleet_dir, monkeypatch):
    from fastapi.testclient import TestClient

    mod = _load_sidecar("embedder")

    class FakeModel:
        def __init__(self):
            self.batches: list[int] = []

        def encode(self, texts, batch_size=None, normalize_embeddings=True):
            self.batches.append(len(texts))
            return [_Vec([float(len(t)), 1.0]) for t in texts]

    mod.app.state.model = FakeModel()
    mod.app.state.weights = {"verified": True}
    mod.app.state.manifest = {"identity": {"version": "test"}}
    client = TestClient(mod.app)
    r = client.post("/infer", json={"texts": ["a", "bb"], "representation_kind": "child_chunk"},
                    headers={PRIORITY_HEADER: "interactive"})
    body = r.json()
    assert r.status_code == 200 and body["priority"] == INTERACTIVE and body["queued_ms"] >= 0.0
    assert body["vectors"] == [[1.0, 1.0], [2.0, 1.0]] and {"contract_id", "dimension", "model_release"} <= set(body)
    r = client.post("/infer", json={"texts": ["a"], "representation_kind": "query"})
    assert r.status_code == 200 and r.json()["priority"] == BACKGROUND    # header absent = background
    assert client.get("/ready").json() == {"ready": True}
    monkeypatch.setenv("POLYMATH_SIDECAR_THREADED", "1")                # threadpool path, same contract
    r = client.post("/infer", json={"texts": ["a", "bb", "ccc"], "representation_kind": "query"},
                    headers={"x-polymath-priority": "INTERACTIVE"})
    assert r.status_code == 200 and r.json()["priority"] == INTERACTIVE and len(r.json()["vectors"]) == 3
    assert not interactive_pending()                                     # nothing left registered


def test_reranker_endpoint_receipts_queued_ms_and_keeps_oom_halving(fleet_dir, monkeypatch):
    from fastapi.testclient import TestClient

    mod = _load_sidecar("reranker")

    class FakeCrossEncoder:
        def predict(self, pairs):
            return [float(len(p[1])) for p in pairs]

    mod.app.state.model = FakeCrossEncoder()
    mod.app.state.device = "cpu"
    mod.app.state.manifest = {"identity": {"model": {"id": "m", "revision": "r"}}}
    client = TestClient(mod.app)
    r = client.post("/rerank", json={"query": "q", "documents": ["a", "bbb", "cc"], "top_k": 2},
                    headers={PRIORITY_HEADER: "interactive"})
    body = r.json()
    assert r.status_code == 200 and body["scores"] == [1.0, 3.0, 2.0] and body["order"] == [1, 2]
    assert body["priority"] == INTERACTIVE and body["queued_ms"] >= 0.0
    assert client.post("/rerank", json={"query": "q", "documents": ["a"]}).json()["priority"] == BACKGROUND
    assert client.get("/ready").json()["ready"] is True
    monkeypatch.setenv("POLYMATH_SIDECAR_THREADED", "1")
    assert client.post("/rerank", json={"query": "q", "documents": ["a", "b"]}).status_code == 200

    calls: list[int] = []

    def predict(chunk):
        calls.append(len(chunk))
        if len(chunk) > 4:
            raise RuntimeError("MPS backend out of memory (MPS allocated: 3.32 GiB)")
        return [float(len(p[1])) for p in chunk]

    pairs = [["q", "d" * (i + 1)] for i in range(21)]
    receipts: list[metal.LeaseReceipt] = []
    out = mod.score_in_batches(predict, pairs, batch=8, priority=INTERACTIVE, receipts=receipts)
    assert out == [float(i + 1) for i in range(21)] and max(calls) == 8 and 4 in calls
    assert len(receipts) == len(calls) and all(x.acquired and x.priority == INTERACTIVE for x in receipts)
    assert not interactive_pending()
