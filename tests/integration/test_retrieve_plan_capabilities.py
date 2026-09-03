"""Live: GET /capabilities advertises the contracts; POST /retrieve/plan
returns a plan + merged rows with query provenance. Skips when the
orchestrator is not up or no corpus is query_ready."""
import json
import os
import urllib.request

import pytest

URL = os.environ.get("POLYMATH_ORCHESTRATOR_URL", "http://127.0.0.1:7200")


def _get(path):
    with urllib.request.urlopen(URL + path, timeout=15) as r:
        return json.loads(r.read())


def _post(path, body):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def _ready_corpus():
    try:
        _get("/health")
    except Exception:
        pytest.skip("orchestrator not running")
    cid = os.environ.get("POLYMATH_TEST_CORPUS", "mark-builds-brands-v1")
    return cid


def test_capabilities_advertise_contracts():
    _ready_corpus()
    caps = _get("/capabilities")
    assert caps["backend"] == "polymath"
    assert caps["contracts"]["retrieve-evidence-rows"] == "v1"
    assert caps["contracts"]["corpus-plan"] == "v1"
    assert "compile_plan" in caps["mcp_tools"]


def test_retrieve_plan_returns_plan_and_provenance():
    cid = _ready_corpus()
    out = _post("/retrieve/plan", {"signal": "SEED: sell a boring product to a market with no expert brand. LATENT INTERPRETATION: the buyer is an anxious first-time caregiver; the tension is dignity vs safety.",
                                   "corpus_id": cid, "limit": 12})
    if out.get("errors") and not out.get("evidence_rows"):
        pytest.skip(f"corpus not query_ready: {out['errors'][:1]}")
    assert out["plan_contract"] == "corpus-plan-v1" and 3 <= len(out["plan"]) <= 5
    ids = {q["id"] for q in out["plan"]}
    assert out["evidence_rows"] and all(r["query_ids"] and set(r["query_ids"]) <= ids for r in out["evidence_rows"])
    assert len({r["id"] for r in out["evidence_rows"]}) == len(out["evidence_rows"])
