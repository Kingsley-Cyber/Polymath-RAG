"""POST /product/search (product-search-v1): the contract S2's MCP product_search tool and S6's UI build on.

  * with `hypotheses` — the caller's agent did the reasoning: CJ / Alibaba lookups only, no retrieval, no model;
  * without — ONE chat-runtime turn in forced product mode with the app's default LLM (unless `model`): the answer, the block,
    compact evidence (tag, chunk_id, source, text <= 400), the retrieval summary and the phases;
  * no corpus = the scope the runtime resolves for the caller: nothing → QUERY_SCOPE_EMPTY, several → CORPUS_REQUIRED (422),
    both naming list_corpora; the caller's principal reaches the supplier search; one receipt per call, kind `product`.
In process: the stores, sidecars, LLM and supplier are faked (the chat-runtime harness); no network, no database."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "orchestrator", ROOT / "tests" / "determinism"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from test_chat_runtime import _fake_tx  # noqa: E402
from test_product_runtime import PRODUCT, Product  # noqa: E402

from orchestrator.api import product as product_mod  # noqa: E402
from orchestrator.api import ui  # noqa: E402
from polymath_shared.principal_context import PrincipalContextMiddleware  # noqa: E402
from polymath_shared.product_search import service as PS  # noqa: E402

UA = "product-contract-test/1.0"


@pytest.fixture()
def rig(monkeypatch):
    def make(**runtime):
        p = Product(monkeypatch, **runtime)
        p.route_receipts = []

        def rec(tx_factory, **kw):
            p.route_receipts.append(kw)
            return "q_product"
        monkeypatch.setattr(product_mod, "record_query_receipt", rec)
        monkeypatch.setattr(product_mod, "tx", _fake_tx)
        monkeypatch.setattr(ui, "_default_synthesizer", lambda: "ollama:fake")      # the app's default, without asking a daemon
        app = FastAPI()
        app.add_middleware(PrincipalContextMiddleware)
        app.include_router(product_mod.router)
        p.client = TestClient(app)
        return p
    return make


def _post(p, body: dict, principal: str | None = None):
    headers = {"user-agent": UA, **({"X-Polymath-Principal": principal} if principal else {})}
    return p.client.post("/product/search", json=body, headers=headers)


def test_the_route_is_registered_on_the_app():
    src = (ROOT / "orchestrator" / "orchestrator" / "main.py").read_text(encoding="utf-8")
    assert "from orchestrator.api.product import router as product_router" in src and "app.include_router(product_router)" in src


def test_with_hypotheses_only_the_lookups_run_as_the_callers_principal(rig):
    p = rig()
    body = {"message": PRODUCT, "corpus_id": "cinema", "geography": "US", "limit_per_hypothesis": 4,
            "hypotheses": [{"title": "Smart pet feeder", "search_terms": ["automatic pet feeder"]},
                           {"title": "Calming dog bed", "search_terms": ["calming dog bed", "donut pet bed"]}]}
    r = _post(p, body, principal="prn_fred")
    assert r.status_code == 200, r.text[:400]
    out = r.json()
    assert p.engine_calls == [] and p.system == []                           # no retrieval, no model
    assert out["contract"] == "product-search-v1" and out["kind"] == "product" and out["source"] == "agent_hypotheses"
    assert out["verdict"] == PS.VERDICT and out["evidence"] == [] and out["retrieval"] is None and out["phases"] == []
    block = out["product_research"]
    assert [h["title"] for h in block["hypotheses"]] == ["Smart pet feeder", "Calming dog bed"]
    assert block["hypotheses"][0]["cj"]["items"][0]["title"] == "Automatic Pet Feeder 6L"
    assert block["hypotheses"][1]["cj"]["status"] == "EMPTY" and block["hypotheses"][1]["cj"]["fallback"]["kind"] == "AGENT_REACH"
    assert block["next"]["full_research"]["input"] == {"seed": "products for pet owners", "corpus_ids": ["cinema"], "geography": "US"}
    assert "### Supplier finds (CJ Dropshipping)" in out["answer"]
    # the principal flowed from the header to every CJ search, with the request's limit
    assert [(c["principal_id"], c["current"], c["query"], c["limit"]) for c in p.calls] == [
        ("prn_fred", "prn_fred", "automatic pet feeder", 4), ("prn_fred", "prn_fred", "calming dog bed", 4)]
    # one receipt, kind product: counts and statuses only
    assert len(p.route_receipts) == 1
    rec = p.route_receipts[0]
    assert rec["kind"] == "product" and rec["client"] == UA and rec["scope_corpora"] == ["cinema"] and rec.get("error") is None
    assert rec["question"] == PRODUCT and rec["scope_kind"] == "corpus"
    meta = rec["out"]["meta"]
    assert meta["route"] == "product/search" and meta["verdict"] == PS.VERDICT and meta["product_search"]["lookups"] == 2
    assert "Automatic Pet Feeder" not in json.dumps(meta)


def test_without_hypotheses_the_runtime_runs_in_forced_product_mode_with_the_default_model(rig):
    p = rig()
    r = _post(p, {"message": "what should I sell to pet owners in the US?", "corpus_id": "cinema"}, principal="prn_fred")
    assert r.status_code == 200, r.text[:400]
    out = r.json()
    assert out["kind"] == "llm" and out["model"] == "fake" and out["runtime"] == "chat-runtime-v1"     # ui._default_synthesizer()
    assert out["verdict"] in (PS.VERDICT, PS.VERDICT_THIN)
    block = out["product_research"]
    assert block["contract"] == "product-search-v1" and block["corpus_ids"] == ["cinema"] and block["hypotheses"]
    assert "### Supplier finds (CJ Dropshipping)" in out["answer"] and "```product-hypotheses" not in out["answer"]
    # compact evidence: the [S#] passages with their source and at most 400 characters of text
    assert out["evidence"] and all(set(e) == {"tag", "chunk_id", "source", "text"} and len(e["text"]) <= 400 for e in out["evidence"])
    assert [e["tag"] for e in out["evidence"]][:2] == ["S1", "S2"] and out["evidence"][0]["text"]
    assert out["retrieval"]["mode"] == "HYBRID" and out["retrieval"]["corpus_ids"] == ["cinema"] and out["retrieval"]["evidence_count"]
    stages = [ph["stage"] for ph in out["phases"]]
    assert "product_intent" in stages and stages[-2:] == ["product_search", "product_search_done"]
    assert {c["principal_id"] for c in p.calls} == {"prn_fred"} and p.engine_calls             # retrieval ran, CJ as the principal
    # the runtime's ONE receipt, under the route's transport tags
    assert len(p.route_receipts) == 1 and p.route_receipts[0]["kind"] == "product" and p.route_receipts[0]["client"] == UA
    assert p.route_receipts[0]["out"]["meta"]["route"] == "product/search"
    assert p.route_receipts[0]["out"]["meta"]["product_search"]["verdict"] == out["verdict"]


def test_a_question_that_is_not_a_product_request_is_still_answered_in_product_mode(rig):
    p = rig()
    out = _post(p, {"message": "tell me about the history of Alibaba", "corpus_id": "cinema", "model": "ollama:fake"}).json()
    assert out["product_research"]["intent"]["rule"] == "forced" and "PRODUCT HYPOTHESIS CONTRACT" in p.system[0]


def test_a_named_model_is_used(rig):
    p = rig()
    out = _post(p, {"message": PRODUCT, "corpus_id": "cinema", "model": "ollama:other-model"}).json()
    assert out["model"] == "other-model"


@pytest.mark.parametrize("body,code", [({"message": "   ", "corpus_id": "cinema"}, "message_required"),
                                       ({"message": PRODUCT, "corpus_id": "cinema", "hypotheses": [{"title": " "}]}, "bad_hypotheses")])
def test_a_bad_request_is_a_typed_422_and_receipted_once(rig, body, code):
    p = rig()
    r = _post(p, body)
    assert r.status_code == 422 and r.json()["detail"]["error_code"] == code
    assert len(p.route_receipts) == 1 and p.route_receipts[0]["kind"] == "product" and code in p.route_receipts[0]["error"]


def test_no_corpus_and_several_libraries_is_routed_to_the_best_library(rig, monkeypatch):
    from test_product_runtime import _route_fakes
    p = rig(corpora=("cinema", "commerce-v1"))
    q, embedded = _route_fakes(monkeypatch, [("cinema", "a1"), ("commerce-v1", "b1")])
    r = _post(p, {"message": PRODUCT}, principal="prn_fred")
    assert r.status_code == 200, r.text[:300]
    out = r.json()
    routing = out["product_research"]["receipts"]["routing"]
    assert routing["chosen"] == "cinema" and routing["runner_up"] == "commerce-v1" and routing["method"] == "profile_rrf"
    assert out["retrieval"]["corpus_ids"] == ["cinema"] and {c["corpus_id"] for c in p.engine_calls} == {"cinema"}
    assert len(q.calls) == 1 and embedded == [PRODUCT]
    assert "product_route" in [ph["stage"] for ph in out["phases"]]
    assert len(p.route_receipts) == 1 and p.route_receipts[0]["scope_corpora"] == ["cinema"]


def test_no_corpus_and_nothing_to_search_is_the_typed_scope_empty_refusal(rig):
    p = rig(corpora=())
    r = _post(p, {"message": PRODUCT})
    assert r.status_code == 404 and r.json()["detail"]["error_code"] == "QUERY_SCOPE_EMPTY"
    assert "list_corpora" in json.dumps(r.json()["detail"]) and p.calls == []


def test_agent_hypotheses_without_any_library_still_get_their_lookups_and_say_what_the_offer_needs(rig):
    p = rig(corpora=())
    r = _post(p, {"message": PRODUCT, "hypotheses": [{"title": "Smart pet feeder", "search_terms": ["automatic pet feeder"]}]})
    assert r.status_code == 200, r.text[:300]
    block = r.json()["product_research"]
    assert block["corpus_ids"] == [] and block["hypotheses"][0]["cj"]["status"] == "OK"
    assert any("no library was resolved" in x for x in block["limitations"])
