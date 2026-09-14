"""POLYMATH → TRAILSIGNAL CONNECTOR (ADR-0019 §8 / HARNESS-RESEARCH-MIGRATION-V1 R4; originally E4 under ADR-0018).

ONE typed client over TrailSignal's public production boundary — the authenticated FastMCP streamable-HTTP daemon
(`POST {url}/mcp`, stateless JSON-RPC 2.0 `tools/call`, HS256 bearer JWT). Nothing here touches Trail's CSV, Postgres,
blob store or private modules. The product-discovery adapter uses Trail's seven BOUNDED SYNCHRONOUS deterministic
operations (Trail ADR-063 / HR3): `registry.project`, `gaps.compile`, `evidence.admit`, `hypotheses.judge`,
`territory.project`, `opportunity.qualify`, `opportunity.score` — each returns its immutable result at once (no Temporal
state), so the adapter never submits, polls or pages a Trail acquisition operation. Requests mirror Trail's strict-mode
contracts (`extra=forbid`, `strict=True`): explicit nulls, `Identifier` ids, a 65536-byte canonical-JSON ceiling.
Generic `operation.get` / `operation.command` remain for cancellation of any long-running operation a future adapter
might own.

Env (worker side):  POLYMATH_TRAIL_MCP_URL (default http://127.0.0.1:8767/mcp)
                    TRAIL_SIGNAL_MCP_TOKEN_POLYMATH  — a pre-minted JWT for the `polymath` principal, OR
                    TRAIL_SIGNAL_MCP_JWT_SECRET      — the daemon's HS256 secret (>= 32 chars) to mint one
                    POLYMATH_TRAIL_PRINCIPAL (default polymath), POLYMATH_TRAIL_AUDIT_IDENTITY (default = principal)
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import time
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:8767/mcp"
ISSUER, AUDIENCE = "trail-signal", "trail-signal-mcp"
BOUNDED_OPERATIONS = ("registry.project", "gaps.compile", "evidence.admit", "hypotheses.judge", "territory.project",
                      "opportunity.qualify", "opportunity.score")
#: the `polymath` principal's capability set (Trail ADR-063 / PrincipalCapabilityV6): the seven bounded operations + lifecycle
POLYMATH_CAPABILITIES = ("operation.get", "operation.command") + BOUNDED_OPERATIONS
POLICY_REF, BUDGET_REF = "public-static-v1", "p1-static-default-v1"
PURPOSE_REF = "purpose:product-discovery"
REQUEST_BYTES_MAX = 65536                   # config/v2/limits.yaml mcp.maximum_request_bytes
_IDENT_BAD = re.compile(r"[^A-Za-z0-9._:/-]")
_URL_BAD_QUERY_KEYS = ("apikey", "authorization", "auth", "bearer", "jwt", "key", "session", "sid", "sig")


class TrailError(RuntimeError):
    """Base: anything Trail refused or the transport could not complete."""


class TrailTransportError(TrailError):
    def __init__(self, status: int, text: str) -> None:
        super().__init__(f"HTTP {status}: {text[:300]}")
        self.status = status


class TrailProtocolError(TrailError):
    """A JSON-RPC `error` object — the request envelope was wrong."""


class TrailToolError(TrailError):
    """`result.isError` — Trail refused the operation (policy, validation, permission, unknown tool)."""


# ─────────────────────────────────────────────────────────── identifiers / auth
def identifier(*parts: str, max_len: int = 200) -> str:
    """A Trail `Identifier`: ^[A-Za-z0-9][A-Za-z0-9._:/-]*$, 1..256. Underscores (Polymath ids use them) become '-'."""
    raw = ":".join(str(p) for p in parts if p is not None and str(p) != "")
    out = _IDENT_BAD.sub("-", raw.replace("_", "-")).strip("._:/-")
    if not out or not re.match(r"^[A-Za-z0-9]", out):
        out = "p" + out
    return out[:max_len]


def credential_binding_hash(principal_id: str, binding_secret: str | None = None) -> str:
    """Stable per principal (Trail keys operation ownership on it — it must never rotate mid-run)."""
    seed = f"polymath-trail-binding-v1:{principal_id}:{binding_secret or ''}"
    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def mint_principal_jwt(secret: str, *, principal_id: str = "polymath", audit_identity: str | None = None,
                       capabilities: tuple[str, ...] = POLYMATH_CAPABILITIES, policy_ref: str = POLICY_REF, budget_ref: str = BUDGET_REF,
                       binding_hash: str | None = None, ttl_s: int = 3600, now: int | None = None) -> str:
    """HS256 JWT with exactly the claims Trail's AuthRuntime requires (sub, audit_identity, capabilities, policy_ref,
    budget_ref, credential_binding_hash, iat, exp, iss, aud). `nbf` is neither required nor sent."""
    import jwt  # PyJWT
    if len(secret) < 32:
        raise ValueError("Trail's MCP JWT secret must contain at least 32 characters")
    iat = int(now if now is not None else time.time())
    claims = {"sub": principal_id, "audit_identity": audit_identity or principal_id, "capabilities": list(capabilities),
              "policy_ref": policy_ref, "budget_ref": budget_ref,
              "credential_binding_hash": binding_hash or credential_binding_hash(principal_id),
              "iat": iat, "exp": iat + int(ttl_s), "iss": ISSUER, "aud": AUDIENCE}
    return jwt.encode(claims, secret, algorithm="HS256")


def token_from_env(env: dict[str, str] | None = None) -> str | None:
    e = env if env is not None else os.environ
    if e.get("TRAIL_SIGNAL_MCP_TOKEN_POLYMATH"):
        return e["TRAIL_SIGNAL_MCP_TOKEN_POLYMATH"]
    secret = e.get("TRAIL_SIGNAL_MCP_JWT_SECRET")
    if secret:
        pid = e.get("POLYMATH_TRAIL_PRINCIPAL", "polymath")
        return mint_principal_jwt(secret, principal_id=pid, audit_identity=e.get("POLYMATH_TRAIL_AUDIT_IDENTITY") or pid)
    return None


# ─────────────────────────────────────────────────────────── request builders (pure)
def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def bounded_request(kind: str, payload: dict[str, Any], *, key: str, run_ref: str, registry_snapshot_id: str | None = None,
                    purpose_ref: str = PURPOSE_REF) -> dict[str, Any]:
    """The request envelope of a bounded synchronous Trail operation: identity, idempotency, purpose, the Polymath run
    reference, the registry snapshot the caller reasons against (null before `registry.project`) and the typed payload."""
    if kind not in BOUNDED_OPERATIONS:
        raise ValueError(kind)
    req = {"request_id": identifier("request", key), "idempotency_key": identifier("idempotency", key), "purpose_ref": purpose_ref,
           "run_ref": identifier("run", run_ref), "operation_kind": kind, "registry_snapshot_id": registry_snapshot_id, "payload": payload}
    if len(json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) > REQUEST_BYTES_MAX:
        raise ValueError(f"{kind} request exceeds Trail's {REQUEST_BYTES_MAX}-byte canonical JSON ceiling — bound the payload")
    return req


def operation_reference(ref: dict[str, Any], *, minimum_revision: int = 0) -> dict[str, Any]:
    """Echo an OperationRefV1 back (operation.get). `status_revision` is a server-side minimum-revision barrier: 0 for
    plain polling; revision+1 only for read-your-writes after a command."""
    return {"operation_id": ref["operation_id"], "operation_kind": ref["operation_kind"],
            "temporal_workflow_id": ref.get("temporal_workflow_id") or ref["operation_id"], "temporal_run_id": ref.get("temporal_run_id"),
            "submitted_at": ref["submitted_at"], "status_revision": int(minimum_revision)}


def cancel_command(operation_id: str, *, expected_revision: int, key: str, reason_code: str = "CLIENT_CANCELLED") -> dict[str, Any]:
    return {"command_id": identifier("command", key), "operation_id": operation_id, "command": "CANCEL",
            "expected_revision": int(expected_revision), "idempotency_key": identifier("idempotency", key, "cancel"),
            "requested_at": _utc_now(), "reason_code": reason_code}


# ─────────────────────────────────────────────────────────── receipt mapping (pure)
def receipt_from_ref(run_id: str, step_id: str, ref: dict[str, Any], *, idempotency_key: str, principal: str) -> dict[str, Any]:
    """ExternalOperationReceiptV1 right after submit (phase PENDING until the first poll)."""
    return {"run_id": run_id, "step_id": step_id, "external_system": "trailsignal", "operation_kind": ref["operation_kind"],
            "operation_id": ref["operation_id"], "idempotency_key": idempotency_key, "principal": principal,
            "submitted_at": ref["submitted_at"] if isinstance(ref["submitted_at"], str) else _utc_now(),
            "status_revision": int(ref.get("status_revision") or 0), "temporal_workflow_id": ref.get("temporal_workflow_id"),
            "temporal_run_id": ref.get("temporal_run_id"), "phase": "PENDING", "outcome": None, "terminal_at": None,
            "record_ids": [], "dataset_ids": [], "export_ids": [], "poll_count": 0, "last_polled_at": None, "failure": None}


def receipt_after_poll(receipt: dict[str, Any], status: dict[str, Any], *, record_ids: list[str] | None = None) -> dict[str, Any]:
    """Fold an OperationStatusV4 into the receipt."""
    out = dict(receipt)
    out["phase"] = status.get("phase") or out["phase"]
    out["outcome"] = status.get("terminal_outcome")
    out["status_revision"] = int(status.get("revision") or out.get("status_revision") or 0)
    out["terminal_at"] = status.get("terminal_at")
    out["poll_count"] = int(out.get("poll_count") or 0) + 1
    out["last_polled_at"] = _utc_now()
    if record_ids:
        out["record_ids"] = sorted(set(out.get("record_ids") or []) | set(record_ids))
    if status.get("failure_code"):
        out["failure"] = {"code": str(status["failure_code"])[:60], "message": f"trail operation failed: {status['failure_code']}"}
    return out


def bounded_receipt(run_id: str, step_id: str, kind: str, response: dict[str, Any], *, idempotency_key: str, principal: str,
                    record_ids: list[str] | None = None) -> dict[str, Any]:
    """ExternalOperationReceiptV1 for a bounded synchronous operation: TERMINAL + SUCCEEDED at once, the audit operation id
    Trail committed, and the record ids its result named."""
    now = _utc_now()
    return {"run_id": run_id, "step_id": step_id, "external_system": "trailsignal", "operation_kind": kind,
            "operation_id": str(response.get("operation_id") or identifier("op", kind, idempotency_key)), "idempotency_key": idempotency_key,
            "principal": principal, "submitted_at": now, "status_revision": int(response.get("status_revision") or 1),
            "temporal_workflow_id": None, "temporal_run_id": None, "phase": "TERMINAL", "outcome": "SUCCEEDED", "terminal_at": now,
            "record_ids": sorted(set(record_ids or [])), "dataset_ids": [], "export_ids": [], "poll_count": 0, "last_polled_at": None, "failure": None}


# ─────────────────────────────────────────────────────────── transport
class TrailMCPClient:
    """Stateless streamable-HTTP JSON-RPC client (no initialize, no session header). One method: call_tool."""

    def __init__(self, url: str = DEFAULT_URL, token: str | None = None, *, timeout_s: float = 30.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.url = url
        self.token = token
        self.timeout_s = timeout_s
        self._transport = transport
        self._id = 0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, **kw: Any) -> "TrailMCPClient":
        e = env if env is not None else os.environ
        return cls(e.get("POLYMATH_TRAIL_MCP_URL", DEFAULT_URL), token_from_env(e), **kw)

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise TrailError("no Trail principal token (TRAIL_SIGNAL_MCP_TOKEN_POLYMATH or TRAIL_SIGNAL_MCP_JWT_SECRET)")
        self._id += 1
        body = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(raw) > REQUEST_BYTES_MAX:
            raise TrailError(f"request body {len(raw)} bytes exceeds Trail's {REQUEST_BYTES_MAX}-byte ceiling")
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        with httpx.Client(timeout=self.timeout_s, transport=self._transport, follow_redirects=False, trust_env=False) as c:
            r = c.post(self.url, content=raw, headers=headers)
        if r.status_code >= 400:
            raise TrailTransportError(r.status_code, r.text)
        try:
            env = r.json()
        except ValueError:
            raise TrailProtocolError(f"non-JSON response: {r.text[:200]}")
        if env.get("error"):
            raise TrailProtocolError(json.dumps(env["error"])[:400])
        result = env.get("result") or {}
        if result.get("isError"):
            msg = "; ".join(str(c.get("text", "")) for c in result.get("content") or [] if isinstance(c, dict)) or "tool error"
            raise TrailToolError(msg[:400])
        value = result.get("structuredContent")
        if value is None:
            texts = [c.get("text") for c in result.get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
            value = json.loads(texts[0]) if texts else {}
        if isinstance(value, dict) and set(value) == {"result"}:
            value = value["result"]
        return value

    # thin typed wrappers
    def operate(self, kind: str, request: dict[str, Any]) -> dict[str, Any]:
        """One bounded synchronous operation → its immutable result envelope ({operation_id, operation_kind, status_revision,
        registry_snapshot?, result})."""
        if kind not in BOUNDED_OPERATIONS:
            raise ValueError(kind)
        return self.call_tool(kind, {"request": request})

    def status(self, ref: dict[str, Any], *, minimum_revision: int = 0) -> dict[str, Any]:
        return self.call_tool("operation.get", {"reference": operation_reference(ref, minimum_revision=minimum_revision)})

    def cancel(self, command: dict[str, Any]) -> dict[str, Any]:
        return self.call_tool("operation.command", {"command": command})
