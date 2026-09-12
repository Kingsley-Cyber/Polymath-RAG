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
    """Resolve a corpus that actually EXISTS and is query_ready, and say so up front.

    The default `mark-builds-brands-v1` is not present in every deployment; when it is
    absent the request came back with `QUERY_SCOPE_UNKNOWN`, which the test then reported
    as "corpus not query_ready" — a skip reason that was a guess. `/corpora` answers the
    question directly, so the skip names the real condition.
    """
    try:
        _get("/health")
    except Exception:
        pytest.skip("orchestrator not running")
    want = os.environ.get("POLYMATH_TEST_CORPUS")
    rows = (_get("/corpora") or {}).get("corpora") or []
    by_id = {r.get("corpus_id"): r for r in rows}
    if want:
        if want not in by_id:
            pytest.skip(f"POLYMATH_TEST_CORPUS={want} is not present in this deployment")
        if not by_id[want].get("query_ready"):
            pytest.skip(f"POLYMATH_TEST_CORPUS={want} is present but not query_ready")
        return want
    ready = [r["corpus_id"] for r in rows if r.get("query_ready")]
    if not ready:
        pytest.skip(f"no query_ready corpus in this deployment ({len(rows)} corpora)")
    return sorted(ready)[0]


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
        # "errors present" is not the same as "corpus not ready": any server-side fault
        # landed here and was reported as an environment condition. Match the ERROR CODE,
        # never a substring of the payload — `corpus_id` appears in every error as a FIELD
        # NAME, so matching it made the guard admit everything (the same match-the-mention
        # bug the conformance censuses had).
        _codes = {str(e.get("detail", "")) + str(e.get("error_code", ""))
                  for e in out["errors"] if isinstance(e, dict)}
        _blob = " ".join(_codes)
        if not any(k in _blob for k in ("QUERY_SCOPE_UNKNOWN", "NOT_QUERY_READY",
                                        "QUERY_NOT_READY", "CORPUS_NOT_READY")):
            pytest.fail(f"/retrieve/plan returned errors that are NOT a readiness "
                        f"condition: {out['errors'][:2]}")
        pytest.skip(f"corpus not query_ready: {out['errors'][:1]}")
    assert out["plan_contract"] == "corpus-plan-v1" and 3 <= len(out["plan"]) <= 5
    ids = {q["id"] for q in out["plan"]}
    assert out["evidence_rows"] and all(r["query_ids"] and set(r["query_ids"]) <= ids for r in out["evidence_rows"])
    assert len({r["id"] for r in out["evidence_rows"]}) == len(out["evidence_rows"])
