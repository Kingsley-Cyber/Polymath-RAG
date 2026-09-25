"""D1 live check ($0 — no model call; register 11.478). Run after the bounce that deploys D1, from the main checkout with
the main .env loaded:
  1. POST :7200/retrieve in GRAPH mode for three questions (the chat engine's GRAPH path) → the live orchestrator must
     answer `meta.graph_bounds.fact_order: "ranked"` (POLYMATH_GRAPH_FACT_RANK=1 in its environment) with graph facts;
  2. MCP Server A (:8930) `polymath_search` over raw JSON-RPC (the bearer key comes from POLYMATH_MCP_API_KEY and is
     never printed) → at least one row was cut and says so (`truncated: true`, exactly 1,200 characters, a
     `full_length` above 1,200), and no unmarked row is longer than 1,200 characters.
Exit 0 only when both hold. Writes live_check.json next to this file (no key, no row text)."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import pathlib
import sys

import httpx

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
MCP = os.environ.get("POLYMATH_MCP_URL", "http://127.0.0.1:8930")
QUESTIONS = ("How do editors and directors build suspense without dialogue?",
             "How do lighting and color choices change how an audience reads a scene?",
             "What does 'shape' mean in Laban movement terms?")


def _retrieve() -> list[dict]:
    out = []
    for q in QUESTIONS:
        r = httpx.post(f"{ORCH}/retrieve", json={"query": q, "corpus_id": "cinema", "mode": "GRAPH", "limit": 10},
                       timeout=180)
        body = r.json() if r.status_code == 200 else {}
        facts = body.get("graph_relationships") or []
        order = ((body.get("meta") or {}).get("graph_bounds") or {}).get("fact_order")
        out.append({"question": q, "http": r.status_code, "fact_order": order, "facts": len(facts),
                    "related_to": sum(1 for f in facts if f.get("predicate") == "RELATED_TO")})
    return out


async def _mcp() -> dict:
    spec = importlib.util.spec_from_file_location("hosted", ROOT / "scripts" / "hosted_mcp_acceptance.py")
    hosted = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hosted)
    key = os.environ.get("POLYMATH_MCP_API_KEY") or None
    if not key:
        return {"skipped": "POLYMATH_MCP_API_KEY is not set"}
    c = hosted.Client(MCP, key, None, 180.0)
    try:
        resp, body = await c.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                "clientInfo": {"name": "d1-live-check", "version": "1"}})
        init = body.get("result") or {}
        if resp.status_code != 200 or not init.get("protocolVersion"):
            return {"error": f"initialize answered {resp.status_code}"}
        c.extra["MCP-Protocol-Version"] = init["protocolVersion"]
        if resp.headers.get("mcp-session-id"):
            c.extra["mcp-session-id"] = resp.headers["mcp-session-id"]
        await c.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        rows_all = []
        for q in QUESTIONS:
            status, _body, found = await c.tool("polymath_search", {"query": q, "corpus_id": "cinema", "max_evidence": 12})
            rows_all += (found.get("evidence_rows") or []) if isinstance(found, dict) else []
    finally:
        await c.close()
    marked = [r for r in rows_all if r.get("truncated") is True]
    unmarked = [r for r in rows_all if "truncated" not in r and "full_length" not in r]
    return {"rows": len(rows_all), "marked": len(marked),
            "marked_consistent": sum(1 for r in marked if len(r.get("text") or "") == 1200
                                     and int(r.get("full_length") or 0) > 1200),
            "unmarked": len(unmarked),
            "unmarked_over_1200": sum(1 for r in unmarked if len(r.get("text") or "") > 1200),
            "unmarked_at_1200": sum(1 for r in unmarked if len(r.get("text") or "") == 1200)}


def main() -> int:
    ret = _retrieve()
    mcp = asyncio.run(_mcp())
    ok_ret = all(r["http"] == 200 and r["fact_order"] == "ranked" and r["facts"] > 0 for r in ret)
    # the marker path ran: at least one row was cut and says so; every marked row is exactly 1,200 characters with a
    # longer full_length; an unmarked row is never longer than 1,200 (one AT 1,200 was simply that long)
    ok_mcp = ("rows" in mcp and mcp["marked"] > 0 and mcp["marked_consistent"] == mcp["marked"]
              and mcp["unmarked_over_1200"] == 0)
    out = {"retrieve": ret, "mcp": mcp, "ok": {"retrieve_ranked": ok_ret, "mcp_marker": ok_mcp}}
    (HERE / "live_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if ok_ret and ok_mcp else 1


if __name__ == "__main__":
    sys.exit(main())
