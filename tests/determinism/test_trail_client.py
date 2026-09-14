"""The ONE Polymath → TrailSignal client (ADR-0019 §8): bounded synchronous operations, strict-mode envelopes, the polymath
principal's JWT, TERMINAL receipts, transport discipline and error surfaces. Hermetic (httpx MockTransport)."""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import sys
import time

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.adapter.contracts import validate  # noqa: E402

SECRET = "s" * 40


def test_identifier_matches_trails_pattern_and_drops_underscores():
    i = TC.identifier("adr_ab12", "D_project", "7")
    assert "_" not in i and TC.identifier("x") == "x" and len(TC.identifier("a" * 300)) <= 200


def test_bounded_requests_are_closed_strict_and_byte_bounded():
    req = TC.bounded_request("registry.project", {"stage": None, "hypotheses": [{"hypothesis_id": "hyp_1", "statement": "s"}]}, key="k1", run_ref="adr_ab12")
    assert req["operation_kind"] == "registry.project" and req["registry_snapshot_id"] is None and req["run_ref"].startswith("run:")
    assert req["request_id"].startswith("request:") and req["idempotency_key"].startswith("idempotency:") and req["purpose_ref"] == TC.PURPOSE_REF
    with pytest.raises(ValueError):
        TC.bounded_request("discover.submit", {}, key="k", run_ref="r")                 # acquisition is not a bounded operation
    with pytest.raises(ValueError):
        TC.bounded_request("evidence.admit", {"blob": "x" * 70000}, key="k", run_ref="r")   # 65536-byte ceiling
    assert set(TC.BOUNDED_OPERATIONS) == {"registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project", "opportunity.qualify", "opportunity.score"}


def test_jwt_carries_the_polymath_principal_claims():
    tok = TC.mint_principal_jwt(SECRET, principal_id="polymath")
    h, p, _ = tok.split(".")
    claims = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    assert claims["sub"] == "polymath" and claims["audit_identity"] == "polymath"
    assert claims["capabilities"] == list(TC.POLYMATH_CAPABILITIES) and set(TC.BOUNDED_OPERATIONS) <= set(claims["capabilities"])
    assert claims["policy_ref"] == TC.POLICY_REF and claims["budget_ref"] == TC.BUDGET_REF and claims["credential_binding_hash"] == TC.credential_binding_hash("polymath")
    assert claims["iss"] == TC.ISSUER and claims["aud"] == TC.AUDIENCE and claims["exp"] > claims["iat"] >= int(time.time()) - 5 and "nbf" not in claims
    with pytest.raises(ValueError):
        TC.mint_principal_jwt("short", principal_id="polymath")
    assert TC.token_from_env({"TRAIL_SIGNAL_MCP_TOKEN_POLYMATH": "pre.minted.token"}) == "pre.minted.token"
    assert TC.token_from_env({"TRAIL_SIGNAL_MCP_JWT_SECRET": SECRET}).count(".") == 2 and TC.token_from_env({}) is None


def test_bounded_receipt_is_terminal_and_validates_the_contract():
    rc = TC.bounded_receipt("adr_" + "a" * 32, "D_project", "registry.project", {"operation_id": "op-1", "status_revision": 1},
                            idempotency_key="idempotency:k", principal="polymath", record_ids=["pt-02", "fr-03"])
    assert validate("external_operation_receipt", rc) == [] and rc["phase"] == "TERMINAL" and rc["outcome"] == "SUCCEEDED" and rc["record_ids"] == ["fr-03", "pt-02"]
    assert rc["temporal_workflow_id"] is None and rc["poll_count"] == 0
    generic = TC.receipt_from_ref("adr_" + "a" * 32, "X", {"operation_id": "op-9", "operation_kind": "dataset.export", "submitted_at": "2026-09-13T20:00:00Z"}, idempotency_key="k", principal="polymath")
    assert validate("external_operation_receipt", generic) == [] and generic["phase"] == "PENDING"
    folded = TC.receipt_after_poll(generic, {"phase": "TERMINAL", "terminal_outcome": "FAILED", "revision": 3, "failure_code": "SOURCE_DENIED"})
    assert folded["outcome"] == "FAILED" and folded["failure"]["code"] == "SOURCE_DENIED" and folded["poll_count"] == 1


def _client(handler):
    return TC.TrailMCPClient("http://trail.stub/mcp", "tok", transport=httpx.MockTransport(handler))


def test_operate_uses_stateless_tools_call_with_the_request_envelope():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content); seen.update(body["params"]); seen["headers"] = dict(req.headers)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "{}"}],
                                         "structuredContent": {"result": {"operation_id": "op-1", "operation_kind": "gaps.compile", "status_revision": 1, "result": {"research_directive": {"search_intents": []}}}}, "isError": False}})
    out = _client(handler).operate("gaps.compile", TC.bounded_request("gaps.compile", {"stage": "field_evidence"}, key="k", run_ref="r"))
    assert seen["name"] == "gaps.compile" and "request" in seen["arguments"] and seen["arguments"]["request"]["operation_kind"] == "gaps.compile"
    assert seen["headers"]["authorization"] == "Bearer tok" and "mcp-session-id" not in seen["headers"]
    assert out["result"]["research_directive"] == {"search_intents": []}
    with pytest.raises(ValueError):
        _client(handler).operate("scrape.submit", {})


def test_transport_error_surfaces():
    def tool_error(req):
        body = json.loads(req.content)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "policy denied"}], "isError": True}})
    with pytest.raises(TC.TrailToolError):
        _client(tool_error).operate("opportunity.score", TC.bounded_request("opportunity.score", {}, key="k", run_ref="r"))
    with pytest.raises(TC.TrailProtocolError):
        _client(lambda r: httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "bad"}})).operate("opportunity.score", TC.bounded_request("opportunity.score", {}, key="k", run_ref="r"))
    with pytest.raises(TC.TrailTransportError) as exc:
        _client(lambda r: httpx.Response(401, text="unauthorized")).operate("opportunity.score", TC.bounded_request("opportunity.score", {}, key="k", run_ref="r"))
    assert exc.value.status == 401
    with pytest.raises(TC.TrailError):
        TC.TrailMCPClient("http://trail.stub/mcp", None).operate("opportunity.score", {})
