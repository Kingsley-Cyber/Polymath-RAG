"""SYNTAX-BOOTSTRAP: spaCy syntax sidecar integration contract.

Requires the sidecar live: `make dev-spacy` (port 8744) with
POLYMATH_INTEGRATION=1. Tests syntax plumbing only — NO Polymath
relation assertions (spaCy is a syntax-evidence source; GLiNER remains
the entity model).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="set POLYMATH_INTEGRATION=1 with the syntax sidecar running",
)

STRUCTURAL_SENTENCES = [
    ("s1", "Crestline Automation deployed a controller."),
    ("s2", "The team installed robots and connected the workflow to Manhattan Active."),
    ("s3", "CareChart EMR platform routes requests through the gateway."),
    ("s4", "After validating the token, the service forwards the request to Kubernetes."),
]


@pytest.fixture(scope="module")
def client():
    from polymath_shared.clients import SpacySyntaxClient

    c = SpacySyntaxClient()
    if not c.ready():
        c.close()
        pytest.fail("spaCy syntax sidecar not ready on POLYMATH_SPACY_URL (make dev-spacy)")
    yield c
    c.close()


@pytest.fixture(scope="module")
def annotated(client):
    response = client.syntax([{"sentence_id": sid, "text": text} for sid, text in STRUCTURAL_SENTENCES])
    return {sid: text for sid, text in STRUCTURAL_SENTENCES}, response


def test_manifest_pinned(client):
    manifest = client.manifest()
    identity = manifest["identity"]
    assert identity["name"] == "spacy-syntax"
    assert identity["version"] == "syntax-evidence-v1"
    model = identity["model"]
    assert model["id"] == "en_core_web_sm"
    assert model["revision"] == "3.8.0"
    assert not model["weights_sha256"].startswith("__PIN_")
    assert manifest["weights_verification"]["verified"] is True


def test_health_provenance_and_ner_disabled(client):
    import httpx

    from polymath_shared.settings import get_settings

    health = httpx.get(f"{get_settings().sidecars.spacy_url}/health", timeout=10).json()
    assert health["status"] == "ok"
    assert health["ner_disabled"] is True
    assert health["release"] == "syntax-evidence-v1"
    runtime = health
    assert runtime["spacy_version"] == "3.8.15"
    assert runtime["model"] == "en_core_web_sm"
    assert runtime["model_version"] == "3.8.0"
    assert runtime["thinc_version"] == "8.3.13"
    assert runtime["backend"] in ("apple", "cpu")
    assert runtime["batch_size"] >= 1
    # backend is reported, never silent; apple flag matches the reported ops
    assert (runtime["backend"] == "apple") == (runtime["apple_ops_active"] is True)
    active = health["pipeline_components"]["active"]
    assert "ner" not in active and "senter" not in active
    for component in ("tok2vec", "tagger", "parser", "attribute_ruler", "lemmatizer"):
        assert component in active


def test_batch_identity_and_order(annotated):
    texts_by_id, response = annotated
    expected = [sid for sid, _ in STRUCTURAL_SENTENCES]
    assert [r["sentence_id"] for r in response["results"]] == expected
    assert response["contract"] == "syntax-evidence-v1"
    assert response["model_release"] == "syntax-evidence-v1"


def test_pos_lemma_dependencies_heads(annotated):
    texts_by_id, response = annotated
    for result in response["results"]:
        assert result["tokens"], "no tokens returned"
        n = len(result["tokens"])
        for token in result["tokens"]:
            assert token["pos"], f"empty pos on {token}"
            assert token["tag"], f"empty tag on {token}"
            assert token["lemma"], f"empty lemma on {token}"
            assert token["dep"], f"empty dep on {token}"
            assert 0 <= token["head_i"] < n, "head out of range"
        roots = [t for t in result["tokens"] if t["head_i"] == t["i"] and t["dep"] == "ROOT"]
        assert len(roots) == 1, "expected exactly one ROOT token"
    # lemma sanity: routes -> route (s3)
    s3 = next(r for r in response["results"] if r["sentence_id"] == "s3")
    routes = next(t for t in s3["tokens"] if t["text"] == "routes")
    assert routes["lemma"] == "route"


def test_noun_chunks_returned(annotated):
    texts_by_id, response = annotated
    for result in response["results"]:
        assert result["noun_chunks"], "no noun chunks returned"
    s1 = next(r for r in response["results"] if r["sentence_id"] == "s1")
    chunk_texts = [c["text"] for c in s1["noun_chunks"]]
    assert "Crestline Automation" in chunk_texts  # structural chunk, not a relation claim


def test_offsets_exact(annotated):
    texts_by_id, response = annotated
    for result in response["results"]:
        text = texts_by_id[result["sentence_id"]]
        for token in result["tokens"]:
            assert text[token["char_start"]:token["char_end"]] == token["text"]
        for chunk in result["noun_chunks"]:
            assert text[chunk["char_start"]:chunk["char_end"]] == chunk["text"]


def test_duplicate_texts_independent_results(client):
    payload = [
        {"sentence_id": "dup-a", "text": "HarborPay uses Envoy Proxy."},
        {"sentence_id": "dup-b", "text": "HarborPay uses Envoy Proxy."},
    ]
    response = client.syntax(payload)
    a, b = response["results"]
    assert a["sentence_id"] == "dup-a" and b["sentence_id"] == "dup-b"
    assert a["tokens"] == b["tokens"]
    assert a["noun_chunks"] == b["noun_chunks"]
