"""SYNTAX-BOOTSTRAP: provider gate unit contract (no services).

The syntax lane is OFF in production: 'disabled' must execute no
client code on the extraction path; 'spacy' must fail LOUDLY when the
sidecar is unreachable (no silent fallback). A wrong contract id from
the sidecar is also a loud failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))


@pytest.fixture()
def settings(monkeypatch):
    from polymath_shared.settings import get_settings

    get_settings.cache_clear()
    yield get_settings
    get_settings.cache_clear()


def test_provider_defaults_to_disabled(settings):
    assert settings().sidecars.syntax_provider == "disabled"


def test_disabled_provider_attaches_nothing_and_calls_no_http(settings, monkeypatch):
    from workers import extract_worker

    def _no_http(*args, **kwargs):
        raise AssertionError("disabled provider must not construct an HTTP client")

    monkeypatch.setattr("polymath_shared.clients.SpacySyntaxClient", _no_http)
    result = extract_worker._syntax_evidence([({"chunk_id": "c1"}, object())])
    assert result is None


def test_unknown_provider_fails_loud(settings, monkeypatch):
    from workers import extract_worker

    monkeypatch.setenv("POLYMATH_SYNTAX_PROVIDER", "stanza")
    settings.cache_clear()
    with pytest.raises(ValueError, match="unknown syntax provider"):
        extract_worker._syntax_evidence([])


def test_enabled_unreachable_sidecar_fails_loud(settings, monkeypatch):
    from workers import extract_worker

    monkeypatch.setenv("POLYMATH_SYNTAX_PROVIDER", "spacy")
    monkeypatch.setenv("POLYMATH_SPACY_URL", "http://127.0.0.1:59999")
    settings.cache_clear()
    slices = [({"chunk_id": "c1"}, type("Slice", (), {"text": "HarborPay uses Envoy Proxy."})())]
    with pytest.raises(Exception) as excinfo:
        extract_worker._syntax_evidence(slices)
    assert not isinstance(excinfo.value, AssertionError)


def test_syntax_client_rejects_wrong_contract(settings, monkeypatch):
    from polymath_shared.clients import SpacySyntaxClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "contract": "syntax-evidence-v2",
            "results": [],
            "model_release": "x",
        })

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = SpacySyntaxClient()
    with pytest.raises(RuntimeError, match="syntax-evidence-v1"):
        client.syntax([{"sentence_id": "s", "text": "t"}])


def test_syntax_client_accepts_valid_contract(settings, monkeypatch):
    from polymath_shared.clients import SpacySyntaxClient

    body = {
        "contract": "syntax-evidence-v1",
        "results": [{
            "sentence_id": "s1",
            "tokens": [{
                "i": 0, "text": "HarborPay", "char_start": 0, "char_end": 9,
                "lemma": "HarborPay", "pos": "PROPN", "tag": "NNP",
                "dep": "nsubj", "head_i": 1,
            }],
            "noun_chunks": [{
                "char_start": 0, "char_end": 9, "text": "HarborPay", "root_i": 0,
            }],
        }],
        "model_release": "syntax-evidence-v1",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = SpacySyntaxClient()
    response = client.syntax([{"sentence_id": "s1", "text": "HarborPay uses Envoy Proxy."}])
    assert response == body
