"""DOC-PARENT-MAP STAGE worker (RAG-PIPELINE-FINISH) — provider-free unit tests.

Pins the auto-minted pMAP stage's NEW behavior without a DB or a provider call:
in-run cross-lane failover (the PMAP pool-drain), the stage contract, transient vs
deterministic incompleteness, and the process_event wiring (resolve → load → grounding
→ run_document_mapping → project → artifact → requeue/complete).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "workers"):
    sys.path.insert(0, str(_p))

from workers import doc_parent_map_stage_worker as W  # noqa: E402
from workers.doc_parent_map_worker import MapInferError, MappingOutcome  # noqa: E402
from polymath_shared.document_profile.parent_skeleton import build_parent_skeletons  # noqa: E402


class _Ep:
    def __init__(self, name):
        self.name = name
        self.url = f"https://api.groq.com/{name}"
        self.model = "groq/compound-mini"
        self.limiter_key = name
        self.api_key = "x"
        self.cloud_opts = {"structured": "text", "json_mode": False}


def _skels():
    parents = [{"chunk_id": f"c{i}", "chunk_index": i, "char_start": i * 100,
                "heading_path": [f"Chapter {i}"], "text": f"section {i} about topic{i} identifier ID{i:04d}",
                "region_role": "body"} for i in range(3)]
    return build_parent_skeletons(parents).skeletons


def _install_lanes(monkeypatch, names):
    monkeypatch.setattr(W, "_pmap_lanes", lambda run_key: [_Ep(n) for n in names])


class _FakeClient:
    """Scripted client: `script[name]` = ("raw", err, dispatched)."""
    script: dict = {}

    def __init__(self, *a, **k):
        self.endpoint_name = None
        self._last_http_dispatched = False

    def complete_one(self, user, system_prompt=None, max_tokens=None):
        raw, err, dispatched = _FakeClient.script[self.endpoint_name]
        self._last_http_dispatched = dispatched
        return raw, err


def _patch_client(monkeypatch, script):
    _FakeClient.script = script
    monkeypatch.setattr("polymath_shared.llm_extraction.client.LLMExtractionClient", _FakeClient)


# ---------------------------------------------------- in-run cross-lane failover
def test_first_healthy_lane_finishes_the_batch(monkeypatch):
    _install_lanes(monkeypatch, ["map_groq1", "map_groq2", "map_groq3"])
    # lane 1 refuses (local, 0 HTTP), lane 2 429s (dispatched), lane 3 succeeds.
    _patch_client(monkeypatch, {
        "map_groq1": ("", "LIMITER_REFUSED", False),
        "map_groq2": ("", "HTTP_429", True),
        "map_groq3": ("\n".join(f"MAP|{s.alias}|sig|a;b;c" for s in _skels()), None, True),
    })
    infer = W._make_pmap_infer("run-x")
    raw = infer(_skels(), is_combined=False, grounding=None)
    assert raw.count("MAP|") == 3          # lane 3 produced the maps — the pool drained the batch


def test_all_lanes_dark_raises_with_dispatch_flag(monkeypatch):
    _install_lanes(monkeypatch, ["map_groq1", "map_groq2"])
    # both refuse locally → zero HTTP → dispatched False (the durable core defers, no attempt burned).
    _patch_client(monkeypatch, {
        "map_groq1": ("", "LIMITER_REFUSED", False),
        "map_groq2": ("", "LIMITER_REFUSED", False),
    })
    infer = W._make_pmap_infer("run-x")
    with pytest.raises(MapInferError) as ei:
        infer(_skels())
    assert ei.value.dispatched is False
    # if one lane actually dispatched a 429, the flag reflects real provider consumption.
    _patch_client(monkeypatch, {
        "map_groq1": ("", "LIMITER_REFUSED", False),
        "map_groq2": ("", "HTTP_429", True),
    })
    with pytest.raises(MapInferError) as ei2:
        infer(_skels())
    assert ei2.value.dispatched is True


def test_empty_pool_raises_pool_dark(monkeypatch):
    _install_lanes(monkeypatch, [])
    with pytest.raises(MapInferError) as ei:
        W._make_pmap_infer("run-x")(_skels())
    assert ei.value.dispatched is False and "pool_dark" in (ei.value.reason or "")


# ---------------------------------------------------- contract + transient logic
def test_contract_is_deterministic_and_binds_versions():
    from polymath_shared.document_profile import map_compiler
    c1, c2 = W.contract(), W.contract()
    assert c1 == c2 and isinstance(c1, str) and c1


def _outcome(**kw):
    base = dict(doc_id="d", map_contract="mc", eligible_parents=3, excluded_parents=0, batches_total=1,
                batches_done=1, batches_partial=0, parents_mapped=3)
    base.update(kw)
    return MappingOutcome(**base)


def test_transient_vs_deterministic_incompleteness():
    # capacity signal present -> transient (requeue)
    assert W._is_transient_incomplete(_outcome(parents_mapped=1, limiter_refusals=2))
    assert W._is_transient_incomplete(_outcome(parents_mapped=1, http_429=1))
    assert W._is_transient_incomplete(_outcome(parents_mapped=1, http_failures=1))
    assert W._is_transient_incomplete(_outcome(parents_mapped=1, empty_completions=1))
    # no capacity signal -> deterministic (real failed attempt)
    assert not W._is_transient_incomplete(_outcome(parents_mapped=1, compiler_invalid=2))


# ---------------------------------------------------- process_event wiring
class _FakeConn:
    def __init__(self, parents=3):
        self._parents = parents

    def execute(self, sql, params=()):
        return _FakeCursor(sql, self._parents)


class _FakeCursor:
    def __init__(self, sql, parents):
        self.sql, self.parents = sql, parents

    def fetchone(self):
        if "outbox_events" in self.sql:
            return ({"doc_id": "docA", "corpus_id": "corpA"},)
        if "FROM documents" in self.sql:
            return ("docA", "corpA", "a.md", "text/markdown", {"title": "A"}, "chash")
        return None

    def fetchall(self):
        return [(f"c{i}", i, i * 100, [f"Chapter {i}"], f"section {i} topic{i} ID{i:04d}", "body")
                for i in range(self.parents)]


class _FakeWriter:
    def __init__(self): self.artifacts = []
    def artifact(self, a): self.artifacts.append(a)


def _patch_stage_tx(monkeypatch):
    writer = _FakeWriter()
    import contextlib

    @contextlib.contextmanager
    def _st(conn, *, run_id, stage, contract_hash):
        yield writer
    monkeypatch.setattr(W, "stage_transaction", _st)
    return writer


def _run_process(monkeypatch, outcome, *, parents=3):
    writer = _patch_stage_tx(monkeypatch)
    monkeypatch.setattr(W, "run_document_mapping", lambda *a, **k: outcome)
    W.HOOKS["project"] = lambda document, parents, corpus_id, mc: {"points": 3}
    W.HOOKS["tx"] = lambda: (_ for _ in ()).throw(AssertionError("tx should not be used when run_document_mapping is patched"))
    try:
        W.process_event(_FakeConn(parents), {"run_id": "runA"})
    finally:
        W.HOOKS["project"] = None
        W.HOOKS["tx"] = None
    return writer


def test_process_event_complete_writes_artifact(monkeypatch):
    writer = _run_process(monkeypatch, _outcome(parents_mapped=3, batches_done=1))
    assert len(writer.artifacts) == 1
    art = writer.artifacts[0]["doc_parent_map"]
    assert art["complete"] is True and art["parents_mapped"] == 3
    assert art["grounding_version"] == W.GROUNDING_CONTEXT_VERSION and art["grounding_hash"]
    assert art["projection"] == {"points": 3}


def test_process_event_transient_incomplete_requeues(monkeypatch):
    with pytest.raises(W.TransientStageHold):
        _run_process(monkeypatch, _outcome(parents_mapped=1, batches_partial=1, limiter_refusals=1,
                                           unresolved_parent_ids=("c2",)))


def test_process_event_deterministic_incomplete_fails(monkeypatch):
    with pytest.raises(RuntimeError) as ei:
        _run_process(monkeypatch, _outcome(parents_mapped=1, batches_partial=1, compiler_invalid=1,
                                           unresolved_parent_ids=("c2",)))
    assert "DOC_PARENT_MAP_INCOMPLETE" in str(ei.value)


def test_process_event_no_parents_completes_empty(monkeypatch):
    writer = _run_process(monkeypatch, _outcome(), parents=0)
    assert writer.artifacts[0]["doc_parent_map"]["note"] == "no_parent_chunks"
    assert writer.artifacts[0]["doc_parent_map"]["complete"] is True
