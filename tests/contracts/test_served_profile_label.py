"""SERVED-PROFILE-LABEL (the owner, 2026-10-01: "fix the cinema badge so this confusion doesnt happen"): the labels say which
document card SEARCH serves, read from the profile index — not the latest card written. Cinema had a vNext card on 77 / 77
files and was served by 0 (the selection guard kept the richer basic cards), yet read green "vNext complete".
The written-card fields (`vnext_ready`, `profile_vnext`, `semantic_ready`, the vNext verdict) are unchanged.
In process: the profile index, the database and the access checks are faked; no network."""
from __future__ import annotations

import contextlib
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from polymath_shared.document_profile import served as SV


class _Index:
    """A profile index with two pages: a basic card, a vNext card, a giant file's SECTION card and a doc-less point."""
    def __init__(self, fail: bool = False):
        self.fail, self.calls, self.closed = fail, [], False
        self.pages = {None: ([_pt("d1", "doc-profile-v3.2", "h1"), _pt("d2", "doc-profile-vnext-v1", "h2")], "next"),
                      "next": ([_pt("d3", "doc-profile-vnext-v1", "h3", scope="section"), _pt(None, "doc-profile-v3.2", "hx")], None)}

    def scroll(self, *, collection_name, scroll_filter, limit, offset, with_payload, with_vectors):
        self.calls.append((collection_name, offset))
        if self.fail:
            raise RuntimeError("index down")
        return self.pages[offset]

    def close(self):
        self.closed = True


def _pt(doc_id, prompt_version, compiled_hash, scope=None):
    payload = {"doc_id": doc_id, "prompt_version": prompt_version, "compiled_hash": compiled_hash, "corpus_id": "c"}
    if scope:
        payload["scope"] = scope
    return SimpleNamespace(payload=payload)


def test_the_served_card_comes_from_the_index_and_section_cards_are_not_a_files_card():
    idx = _Index()
    got = SV.served_profiles("c", client=idx, embedding_contract_id="embed_x")
    assert got == {"d1": {"writer": "basic", "prompt_version": "doc-profile-v3.2", "compiled_hash": "h1"},
                   "d2": {"writer": "vnext", "prompt_version": "doc-profile-vnext-v1", "compiled_hash": "h2"}}
    assert idx.calls == [("polymath_document_profiles_embed_x", None), ("polymath_document_profiles_embed_x", "next")]
    assert idx.closed is False                                     # an injected client belongs to the caller
    assert SV.served_profiles("c", client=_Index(fail=True), embedding_contract_id="embed_x") is None     # fail-open
    assert [SV.writer_of(v) for v in ("doc-profile-vnext-v1", "doc-profile-v3.2", None)] == ["vnext", "basic", None]


def test_served_labels_are_added_only_when_the_index_answered():
    summaries = {"d1": {"vnext_ready": True}, "d2": {"vnext_ready": True}, "d9": {"vnext_ready": False}}
    SV.apply_served(summaries, {"d1": {"writer": "basic"}, "d2": {"writer": "vnext"}})
    assert [summaries[d]["profile_served"] for d in ("d1", "d2", "d9")] == ["basic", "vnext", None]
    untouched = {"d1": {"vnext_ready": True}}
    SV.apply_served(untouched, None)
    assert untouched == {"d1": {"vnext_ready": True}}              # index unread: the labels keep the written state
    assert SV.served_vnext_count(["d1", "d2", "d9"], {"d1": {"writer": "basic"}, "d2": {"writer": "vnext"}}) == 1
    assert SV.served_vnext_count(["d1"], None) is None


@contextlib.contextmanager
def _fake_tx():
    yield SimpleNamespace(execute=lambda *a, **k: SimpleNamespace(fetchone=lambda: (1,), fetchall=list))


def _ui_app(monkeypatch, served):
    from orchestrator.api import ui
    monkeypatch.setattr(ui, "tx", _fake_tx)
    monkeypatch.setattr(ui, "require_corpus", lambda *a, **k: None)
    monkeypatch.setattr(ui, "require_document", lambda *a, **k: None)
    monkeypatch.setattr(SV, "served_profiles", lambda corpus_id, **k: served)
    app = FastAPI()
    app.include_router(ui.router)
    return app


def test_the_files_summary_carries_the_served_writer(monkeypatch):
    import polymath_shared.document_status as DS
    monkeypatch.setattr(DS, "corpus_document_summaries", lambda conn, corpus_id: {
        "d1": {"vnext_ready": True, "profile_vnext": True}, "d2": {"vnext_ready": True, "profile_vnext": True}})
    body = TestClient(_ui_app(monkeypatch, {"d1": {"writer": "basic"}, "d2": {"writer": "vnext"}})).get(
        "/documents/summary", params={"corpus_id": "c"}).json()
    assert body["summaries"]["d1"]["profile_served"] == "basic" and body["summaries"]["d2"]["profile_served"] == "vnext"
    assert body["summaries"]["d1"]["vnext_ready"] is True                    # the written-card field is unchanged
    unread = TestClient(_ui_app(monkeypatch, None)).get("/documents/summary", params={"corpus_id": "c"}).json()
    assert "profile_served" not in unread["summaries"]["d1"]


def test_a_files_status_says_whether_its_latest_card_is_the_one_search_uses(monkeypatch):
    import polymath_shared.document_status as DS
    status = {"found": True, "identity": {"doc_id": "d1", "corpus_id": "c"},
              "profile": {"present": True, "vnext": True, "compiled_hash": "h_vnext", "projected": True}}
    monkeypatch.setattr(DS, "document_status", lambda conn, doc_id, detail: {**status, "profile": dict(status["profile"])})
    refused = TestClient(_ui_app(monkeypatch, {"d1": {"writer": "basic", "compiled_hash": "h_basic"}})).get("/documents/d1/status").json()
    assert refused["profile"]["projected"] is False and refused["profile"]["served"] == "basic"    # was: projected true
    used = TestClient(_ui_app(monkeypatch, {"d1": {"writer": "vnext", "compiled_hash": "h_vnext"}})).get("/documents/d1/status").json()
    assert used["profile"]["projected"] is True and used["profile"]["served"] == "vnext"
    unread = TestClient(_ui_app(monkeypatch, None)).get("/documents/d1/status").json()
    assert unread["profile"]["projected"] is True and "served" not in unread["profile"]          # index unread: unchanged


def test_semantic_readiness_reports_vnext_cards_search_uses_beside_the_unchanged_verdict(monkeypatch):
    import polymath_shared.db as DB
    import polymath_shared.semantic_readiness as SR
    from orchestrator.api import health

    from orchestrator import web_scope
    monkeypatch.setattr(DB, "tx", _fake_tx)
    monkeypatch.setattr(web_scope, "require_corpus", lambda *a, **k: None)
    monkeypatch.setattr(SR, "semantic_completion", lambda conn, corpus_id: {
        "verdict": "SEMANTIC_COMPLETE", "vnext": {"verdict": "VNEXT_COMPLETE", "vnext_profiles": 3, "documents": 3}})
    monkeypatch.setattr(SV, "served_profiles", lambda corpus_id, **k: {"d1": {"writer": "basic"}, "d2": {"writer": "basic"},
                                                                       "d3": {"writer": "vnext"}})
    app = FastAPI()
    app.include_router(health.router)
    v = TestClient(app).get("/semantic_readiness", params={"corpus_id": "c"}).json()["vnext"]
    assert v["verdict"] == "VNEXT_COMPLETE" and v["vnext_profiles"] == 3 and v["vnext_served"] == 1
    monkeypatch.setattr(SV, "served_profiles", lambda corpus_id, **k: None)
    assert "vnext_served" not in TestClient(app).get("/semantic_readiness", params={"corpus_id": "c"}).json()["vnext"]
