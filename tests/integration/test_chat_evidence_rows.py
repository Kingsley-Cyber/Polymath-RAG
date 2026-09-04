"""CHAT-EVIDENCE-ROWS-V1: /chat evidence=true returns the answer plus contract rows. Skips when down."""
import json, os, urllib.request
import pytest

URL = os.environ.get("POLYMATH_ORCHESTRATOR_URL", "http://127.0.0.1:7200")


def test_chat_returns_evidence_rows_with_the_answer():
    try:
        urllib.request.urlopen(URL + "/health", timeout=10)
    except Exception:
        pytest.skip("orchestrator not running")
    body = json.dumps({"message": "What makes an ugly landing page convert?", "corpus_id": os.environ.get("POLYMATH_TEST_CORPUS", "mark-builds-brands-v1"),
                       "mode": "HYBRID", "latent": True, "evidence": True}).encode()
    req = urllib.request.Request(URL + "/chat", data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read())
    assert "answer" in out and "meta" in out
    assert out.get("evidence_contract") == "retrieve-evidence-rows-v1"
    rows = out.get("evidence_rows") or []
    if out["meta"].get("abstained"):
        pytest.skip("corpus abstained on the probe question")
    assert rows and all(r["source"] and r["text_clean"] and r["kind"] in ("chunk", "document", "graph_fact") for r in rows)
    assert not any(r["source"].startswith("/") for r in rows)
