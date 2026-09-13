"""E4 — the Polymath→TrailSignal connector, hermetic: strict-mode request builders, JWT claims, receipt mapping, and the
stateless JSON-RPC transport against an httpx MockTransport that behaves like Trail's daemon (structuredContent,
`{"result": …}` unwrap, isError, JSON-RPC error, HTTP 401, header discipline, no session/initialize)."""
from __future__ import annotations

import json
import pathlib
import sys

import httpx
import jwt
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.adapter.contracts import validate  # noqa: E402

SECRET = "x" * 40


def test_identifier_matches_trails_pattern_and_drops_underscores():
    for raw in ("adr_ab12:D_discover:5", "_leading", "with space/ok", "é"):
        ident = TC.identifier(raw)
        assert TC._IDENT_BAD.search(ident) is None and ident[0].isalnum() and "_" not in ident
    assert TC.identifier("adr_ab12", "D_discover", "5") == "adr-ab12:D-discover:5"


def test_discovery_request_is_strict_mode_ready():
    r = TC.discovery_request("  cold   plunge\nrecovery ", key="adr_1:D_discover:5", categories=("general", "general"), maximum_candidates=99)
    assert r["query"] == "cold plunge recovery" and r["categories"] == ["general"] and r["time_range"] is None
    assert r["maximum_candidates"] == 64 and r["request_id"].startswith("request:") and r["idempotency_key"].startswith("idempotency:")
    with pytest.raises(ValueError):
        TC.discovery_request("x" * 600, key="k")


def test_crawl_and_batch_requests_reject_credential_urls_and_keep_ordinals():
    c = TC.crawl_request("https://example.com/a?page=2", key="k")
    assert c["domain_profile_ref"] is None and c["requested_route"] == "STATIC" and c["source_policy_ref"] == TC.POLICY_REF
    for bad in ("https://example.com/#frag", "https://user:pw@example.com/", "https://example.com/?token=abc", "https://example.com/?apikey=1"):
        with pytest.raises(ValueError):
            TC.crawl_request(bad, key="k")
    b = TC.batch_request(["https://a.example/1", "https://a.example/1", "https://b.example/2"], key="k")
    assert [i["ordinal"] for i in b["items"]] == [0, 1] and len({i["item_id"] for i in b["items"]}) == 2
    assert all(i["parser_profile_ref"] == TC.PARSER_PROFILE_REF and i["domain_profile_ref"] is None for i in b["items"])
    with pytest.raises(ValueError):
        TC.batch_request([f"https://x.example/{'p' * 900}/{i}" for i in range(64)], key="k")     # > 65536-byte canonical JSON


def test_extraction_reference_page_and_cancel_shapes():
    e = TC.extraction_request("artifact:1", key="k", maximum_records=500)
    assert e["maximum_records"] == 64 and e["result_policy_ref"] == TC.RESULT_POLICY_REF
    ref = TC.operation_reference({"operation_id": "op1", "operation_kind": "discover.submit", "submitted_at": "2026-09-13T00:00:00Z"})
    assert ref["temporal_workflow_id"] == "op1" and ref["temporal_run_id"] is None and ref["status_revision"] == 0
    p = TC.page_request("URL_CANDIDATE_RESULT", "res1", key="k", page_size=99)
    assert p["cursor"] is None and p["page_size"] == 64
    with pytest.raises(ValueError):
        TC.page_request("NOPE", "x", key="k")
    c = TC.cancel_command("op1", expected_revision=3, key="k")
    assert c["command"] == "CANCEL" and c["expected_revision"] == 3 and c["reason_code"] == "CLIENT_CANCELLED" and c["requested_at"].endswith("Z")


def test_jwt_carries_exactly_trails_required_claims():
    import time
    now = int(time.time())
    tok = TC.mint_principal_jwt(SECRET, principal_id="polymath", now=now, ttl_s=60)
    claims = jwt.decode(tok, SECRET, algorithms=["HS256"], audience=TC.AUDIENCE, issuer=TC.ISSUER)
    assert claims["sub"] == "polymath" == claims["audit_identity"] and claims["capabilities"] == list(TC.CAPABILITIES_V5)
    assert claims["policy_ref"] == TC.POLICY_REF and claims["budget_ref"] == TC.BUDGET_REF
    assert claims["credential_binding_hash"].startswith("sha256:") and claims["exp"] == claims["iat"] + 60 and "nbf" not in claims
    assert TC.credential_binding_hash("polymath") == claims["credential_binding_hash"]      # stable across calls
    with pytest.raises(ValueError):
        TC.mint_principal_jwt("short", principal_id="polymath")
    assert TC.token_from_env({}) is None and TC.token_from_env({"TRAIL_SIGNAL_MCP_TOKEN_POLYMATH": "abc"}) == "abc"
    assert TC.token_from_env({"TRAIL_SIGNAL_MCP_JWT_SECRET": SECRET}).count(".") == 2


def test_receipt_mapping_validates_the_contract():
    ref = {"operation_id": "op_1", "operation_kind": "discover.submit", "temporal_workflow_id": "op_1", "temporal_run_id": None,
           "submitted_at": "2026-09-13T00:00:00Z", "status_revision": 0}
    rc = TC.receipt_from_ref("adr_" + "a" * 32, "D_discover", ref, idempotency_key="idempotency:k", principal="polymath")
    assert validate("external_operation_receipt", rc) == [] and rc["phase"] == "PENDING"
    rc2 = TC.receipt_after_poll(rc, {"phase": "TERMINAL", "terminal_outcome": "SUCCEEDED", "revision": 4, "terminal_at": "2026-09-13T00:01:00Z",
                                     "output_refs": [{"output_kind": "URL_CANDIDATE_RESULT", "output_id": "res1", "generation": None}]}, record_ids=["c1"])
    assert validate("external_operation_receipt", rc2) == [] and rc2["outcome"] == "SUCCEEDED" and rc2["poll_count"] == 1 and rc2["record_ids"] == ["c1"]
    rc3 = TC.receipt_after_poll(rc, {"phase": "TERMINAL", "terminal_outcome": "FAILED", "revision": 2, "failure_code": "SOURCE_UNREACHABLE"})
    assert rc3["failure"]["code"] == "SOURCE_UNREACHABLE"


def _daemon(handler):
    def app(request: httpx.Request) -> httpx.Response:
        return handler(request)
    return httpx.MockTransport(app)


def test_transport_success_unwrap_and_header_discipline():
    seen = {}
    def handler(req):
        seen["headers"] = dict(req.headers); seen["body"] = json.loads(req.content); seen["url"] = str(req.url)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": seen["body"]["id"],
                                         "result": {"content": [{"type": "text", "text": "{}"}], "structuredContent": {"result": {"operation_id": "op1"}}, "isError": False}})
    c = TC.TrailMCPClient("http://trail.test/mcp", "tok", transport=_daemon(handler))
    out = c.call_tool("discover.submit", {"request": {"a": 1}})
    assert out == {"operation_id": "op1"}                                        # {"result": …} unwrapped
    assert seen["url"] == "http://trail.test/mcp" and seen["body"]["method"] == "tools/call" and seen["body"]["params"] == {"name": "discover.submit", "arguments": {"request": {"a": 1}}}
    h = seen["headers"]
    assert h["authorization"] == "Bearer tok" and h["content-type"] == "application/json" and "application/json" in h["accept"]
    assert "mcp-session-id" not in h                                             # stateless: no session, no initialize


def test_transport_error_surfaces():
    def is_error(req):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Error calling tool 'crawl.submit': request policy denied"}], "isError": True}})
    with pytest.raises(TC.TrailToolError, match="policy denied"):
        TC.TrailMCPClient("http://t/mcp", "tok", transport=_daemon(is_error)).call_tool("crawl.submit", {"request": {}})
    def rpc_error(req):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params"}})
    with pytest.raises(TC.TrailProtocolError):
        TC.TrailMCPClient("http://t/mcp", "tok", transport=_daemon(rpc_error)).call_tool("operation.get", {"reference": {}})
    def unauthorized(req):
        return httpx.Response(401, text="invalid_token")
    with pytest.raises(TC.TrailTransportError) as e:
        TC.TrailMCPClient("http://t/mcp", "tok", transport=_daemon(unauthorized)).call_tool("operation.get", {"reference": {}})
    assert e.value.status == 401
    with pytest.raises(TC.TrailError, match="no Trail principal"):
        TC.TrailMCPClient("http://t/mcp", None).call_tool("operation.get", {})
    def text_only(req):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps({"phase": "RUNNING"})}], "isError": False}})
    assert TC.TrailMCPClient("http://t/mcp", "tok", transport=_daemon(text_only)).call_tool("operation.get", {"reference": {}}) == {"phase": "RUNNING"}
