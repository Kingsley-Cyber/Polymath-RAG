"""AUTORESEARCH-SOURCES-AND-HARNESS-V1, slice R7: the smallest MCP harness shim — one JSON-RPC call to Polymath MCP Server A per
invocation, so an agent in a shell (Claude Code here) can drive a governed adapter run exactly as any MCP client would.

    mcp_call.py tool <name> '<json arguments>'   -> the tool's structured result (JSON) on stdout
    mcp_call.py prompt <name> '<json arguments>' -> the prompt's messages
    mcp_call.py resource <uri>                    -> the resource's text
    mcp_call.py tools                             -> the tool names this key may call

Environment: POLYMATH_MCP_URL (default http://127.0.0.1:8930/mcp, the loopback listener); the bearer key is
POLYMATH_MCP_API_KEY (load the main .env first), else the file POLYMATH_MCP_KEY_FILE. The key is never printed. Reuses the acceptance client
(scripts/hosted_mcp_acceptance.py `Client`: bearer header, protocol negotiation, a normal User-Agent)."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
URL = os.environ.get("POLYMATH_MCP_URL", "http://127.0.0.1:8930/mcp")
KEY_FILE = pathlib.Path(os.path.expanduser(os.environ.get("POLYMATH_MCP_KEY_FILE", "~/PolymathRuntime/polymath-v4-mcp.key")))


def _client_cls():
    spec = importlib.util.spec_from_file_location("hosted_acceptance", ROOT / "scripts" / "hosted_mcp_acceptance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Client


async def _session():
    base = URL[: -len("/mcp")] if URL.endswith("/mcp") else URL
    key = os.environ.get("POLYMATH_MCP_API_KEY", "").strip() or (KEY_FILE.read_text().strip() if KEY_FILE.is_file() else "")
    c = _client_cls()(base, key or None, None, 600.0)
    resp, body = await c.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "autoresearch-e2e-harness", "version": "1"}})
    init = body.get("result") or {}
    if resp.status_code != 200 or not init.get("protocolVersion"):
        raise SystemExit(f"initialize answered {resp.status_code}")
    c.extra["MCP-Protocol-Version"] = init["protocolVersion"]
    if resp.headers.get("mcp-session-id"):
        c.extra["mcp-session-id"] = resp.headers["mcp-session-id"]
    await c.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return c


def _structured(result: dict) -> object:
    if isinstance(result, dict) and result.get("structuredContent") is not None:
        sc = result["structuredContent"]
        return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
    texts = [c.get("text") for c in (result or {}).get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
    for t in texts:
        try:
            return json.loads(t)
        except (TypeError, json.JSONDecodeError):
            continue
    return result


async def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    c = await _session()
    try:
        if argv[0] == "tools":
            _, body = await c.rpc("tools/list", {})
            print(json.dumps(sorted(t["name"] for t in (body.get("result") or {}).get("tools") or [])))
        elif argv[0] == "tool":
            _, body = await c.rpc("tools/call", {"name": argv[1], "arguments": json.loads(argv[2]) if len(argv) > 2 else {}})
            if body.get("error"):
                print(json.dumps({"rpc_error": body["error"]}, indent=1))
                return 1
            result = body.get("result") or {}
            out = _structured(result)
            print(json.dumps(out, indent=1, ensure_ascii=False))
            return 1 if result.get("isError") else 0
        elif argv[0] == "prompt":
            _, body = await c.rpc("prompts/get", {"name": argv[1], "arguments": json.loads(argv[2]) if len(argv) > 2 else {}})
            print(json.dumps(body.get("result") or body, indent=1, ensure_ascii=False))
        elif argv[0] == "resource":
            _, body = await c.rpc("resources/read", {"uri": argv[1]})
            for item in (body.get("result") or {}).get("contents") or []:
                print(item.get("text", ""))
        else:
            print(__doc__)
            return 2
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
