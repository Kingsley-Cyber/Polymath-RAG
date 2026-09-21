#!/usr/bin/env python
"""HOSTED MCP ACCEPTANCE — the SURFACE half of migration Phase 13 (docs/migration/EXECUTION_PLAN.md).

What a friend's agent host (Claude Code, another MCP client) meets when it connects to Polymath through the owner's
domain: the edge, the bearer gate, the MCP handshake, tool discovery, the knowledge tools, adapter discovery, and the
error / isolation behaviour of a surface that is reachable from the internet. Raw JSON-RPC over streamable HTTP — the
wire a client really speaks — so an edge block, a 401 and a typed tool error stay distinguishable.

READ-ONLY by default: nothing is ingested, no adapter run is started, no model is called. Two opt-ins change that:
`--explore` (polymath_explore plans retrieval: provider spend) and `--cycle` (starts ONE adapter run, reads its first
step, cancels it). The adapter LIFECYCLE with scripted answers is the existing driver, reused, not rebuilt:

    .venv/bin/python scripts/adapter_mcp_acceptance.py --mcp-url https://<host>/mcp --no-restart --adapter <id>

and the REAL ecommerce workflow through the hosted surface is run by a real agent host, not by a script.

    POLYMATH_MCP_API_KEY=... .venv/bin/python scripts/hosted_mcp_acceptance.py --url https://mcp.kingsleylab.xyz
    .venv/bin/python scripts/hosted_mcp_acceptance.py --url https://mcp.kingsleylab.xyz --key-file ~/path/to.key \
        --expect-adapter ecommerce.product_research --out /tmp/hosted_receipt.json

The key is read from `--key-file` or POLYMATH_MCP_API_KEY, sent only as the Authorization header to `--url`, and is
never printed or written to the receipt. Without a key the unauthenticated checks still run; the rest are SKIP.
Exit 0 only when no check FAILs. WARN and SKIP never fail the run — and never count as proof.

WHERE it ran is part of the evidence: a run from the host itself proves DNS + edge + tunnel + gate; only a run from
another machine / network proves external access. `--vantage` records which one this was.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
import time
from typing import Any

import httpx

SCHEMA = "hosted_mcp_acceptance.v1"
ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
ADAPTER_TOOLS = ("adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status", "adapter_result", "adapter_cancel")
REQUIRED_TOOLS = ADAPTER_TOOLS + ("list_corpora", "polymath_search", "polymath_explore")
# user agents an agent host plausibly sends; the zone's bot protection has blocked some at the EDGE before (403, no origin hit)
USER_AGENTS = ("python-httpx/0.28.1", "node", "claude-code/2.0.0", "Python-urllib/3.11", "OpenAI/Python 1.0",
               "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
NO_SUCH_RUN = "adr_00000000000000000000000000000000"
NO_SUCH_CORPUS = "acceptance_no_such_corpus"
PROBE_PATH = "/nonexistent/polymath-hosted-acceptance-probe.md"      # never exists: the probe can not ingest anything


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, check_id: str, status: str, detail: str, **evidence: Any) -> str:
        self.checks.append({"id": check_id, "status": status, "detail": detail, **({"evidence": evidence} if evidence else {})})
        return status

    def summary(self) -> dict[str, int]:
        return {s: sum(1 for c in self.checks if c["status"] == s) for s in ("PASS", "FAIL", "WARN", "SKIP")}


def _rpc_body(resp: httpx.Response) -> dict[str, Any]:
    text = resp.text
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = data[-1] if data else ""
    try:
        out = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {"_unparsed": text[:300]}
    return out if isinstance(out, dict) else {"_unparsed": str(out)[:300]}


def _tool_payload(result: dict[str, Any]) -> Any:
    """The dict a Polymath tool returned: structuredContent when the server sends it, else the JSON text block."""
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    for block in result.get("content") or []:
        if block.get("type") == "text":
            try:
                return json.loads(block.get("text") or "")
            except json.JSONDecodeError:
                return {"_text": (block.get("text") or "")[:400]}
    return {}


class Client:
    def __init__(self, base_url: str, key: str | None, transport: httpx.AsyncBaseTransport | None, timeout: float) -> None:
        self.base = base_url.rstrip("/")
        self.key = key
        self.http = httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False)
        self.extra: dict[str, str] = {}
        self._id = 0

    async def close(self) -> None:
        await self.http.aclose()

    async def post(self, body: dict[str, Any], *, auth: str | None = "key", headers: dict[str, str] | None = None) -> httpx.Response:
        h = {**ACCEPT, **self.extra, **(headers or {})}
        if auth == "key" and self.key:
            h["Authorization"] = f"Bearer {self.key}"
        elif auth not in (None, "key"):
            h["Authorization"] = auth
        return await self.http.post(f"{self.base}/mcp", json=body, headers=h)

    async def rpc(self, method: str, params: dict[str, Any] | None = None) -> tuple[httpx.Response, dict[str, Any]]:
        self._id += 1
        resp = await self.post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        return resp, _rpc_body(resp)

    async def tool(self, name: str, arguments: dict[str, Any]) -> tuple[int, dict[str, Any], Any]:
        resp, body = await self.rpc("tools/call", {"name": name, "arguments": arguments})
        result = body.get("result") or {}
        return resp.status_code, body, _tool_payload(result) if result else {}


def _typed_client_error(payload: Any) -> bool:
    """A Polymath tool error is {"error": ..., "status": 4xx}: typed, the caller's fault, no server fault."""
    return isinstance(payload, dict) and "error" in payload and 400 <= int(payload.get("status") or 0) < 500


async def run(base_url: str, key: str | None, *, corpus: str = "cinema", query: str = "how do films build suspense",
              expect_adapters: tuple[str, ...] = (), explore: bool = False, cycle: dict[str, Any] | None = None,
              vantage: str = "unspecified", transport: httpx.AsyncBaseTransport | None = None, timeout: float = 60.0,
              user_agents: tuple[str, ...] = USER_AGENTS) -> dict[str, Any]:
    rep, c = Report(), Client(base_url, key, transport, timeout)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        await _edge(rep, c, user_agents)
        if not key:
            for cid in ("mcp.initialize", "mcp.tools_list", "knowledge.list_corpora", "knowledge.search", "adapter.list",
                        "errors.unknown_run", "errors.unknown_adapter", "errors.unknown_corpus", "errors.unknown_tool",
                        "isolation.host_path_upload"):
                rep.add(cid, "SKIP", "no bearer key supplied (--key-file or POLYMATH_MCP_API_KEY)")
        else:
            await _authenticated(rep, c, corpus=corpus, query=query, expect_adapters=expect_adapters, explore=explore, cycle=cycle)
    finally:
        await c.close()
    out = {"schema": SCHEMA, "endpoint": base_url.rstrip("/") + "/mcp", "vantage": vantage, "started_at": started,
           "authenticated": bool(key), "read_only": not (explore or cycle), "checks": rep.checks, "summary": rep.summary()}
    out["ok"] = out["summary"]["FAIL"] == 0
    if key and key in json.dumps(out):                                  # belt and braces: a receipt never carries the key
        raise SystemExit("refusing to emit a receipt that contains the bearer key")
    return out


async def _edge(rep: Report, c: Client, user_agents: tuple[str, ...]) -> None:
    try:
        r = await c.http.get(f"{c.base}/health")
        h = r.json() if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError) as exc:
        rep.add("edge.health", "FAIL", f"/health unreachable: {type(exc).__name__}: {exc}")
        return
    ok = r.status_code == 200 and h.get("ok") is True and h.get("auth") == "configured"
    rep.add("edge.health", "PASS" if ok else "FAIL",
            "open /health answers, and the bearer gate is configured" if ok else f"status {r.status_code}, body {str(h)[:200]}",
            http_status=r.status_code, auth=h.get("auth"), tools=len(h.get("tools") or []))

    matrix = {}
    for ua in user_agents:
        try:
            matrix[ua] = (await c.http.get(f"{c.base}/health", headers={"User-Agent": ua})).status_code
        except httpx.HTTPError as exc:
            matrix[ua] = type(exc).__name__
    blocked = sorted(ua for ua, s in matrix.items() if s != 200)
    rep.add("edge.user_agents", "WARN" if blocked else "PASS",
            (f"the edge refuses {len(blocked)} client user agent(s) before the origin is reached: an agent host that sends one "
             f"of them can not connect, whatever its key") if blocked else "every probed client user agent reaches the origin",
            matrix=matrix)

    probe = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = await c.post(probe, auth=None)
    rep.add("auth.missing_bearer", "PASS" if r.status_code == 401 else "FAIL",
            "no Authorization header is refused with 401" if r.status_code == 401 else
            f"an unauthenticated tools/list answered {r.status_code}, expected 401", http_status=r.status_code)
    r = await c.post(probe, auth="Bearer not-the-key")
    rep.add("auth.wrong_bearer", "PASS" if r.status_code == 401 else "FAIL",
            "a wrong bearer is refused with 401" if r.status_code == 401 else
            f"a wrong bearer answered {r.status_code}, expected 401", http_status=r.status_code)


async def _authenticated(rep: Report, c: Client, *, corpus: str, query: str, expect_adapters: tuple[str, ...], explore: bool,
                         cycle: dict[str, Any] | None) -> None:
    resp, body = await c.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "polymath-hosted-acceptance", "version": "1"}})
    init = body.get("result") or {}
    if resp.status_code != 200 or not init.get("protocolVersion"):
        rep.add("mcp.initialize", "FAIL", f"initialize answered {resp.status_code}: {str(body)[:300]}", http_status=resp.status_code)
        return
    rep.add("mcp.initialize", "PASS", "authenticated MCP handshake through the hosted endpoint",
            protocol=init.get("protocolVersion"), server=(init.get("serverInfo") or {}).get("name"))
    c.extra["MCP-Protocol-Version"] = init["protocolVersion"]
    if resp.headers.get("mcp-session-id"):
        c.extra["mcp-session-id"] = resp.headers["mcp-session-id"]
    await c.post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    resp, body = await c.rpc("tools/list")
    tools = {t.get("name"): t for t in (body.get("result") or {}).get("tools") or []}
    missing = [t for t in REQUIRED_TOOLS if t not in tools]
    rep.add("mcp.tools_list", "FAIL" if missing else "PASS",
            f"tool discovery is missing {missing}" if missing else
            f"{len(tools)} tools discovered, including the seven adapter tools and the evidence tools", tools=sorted(tools))

    status, _, corpora = await c.tool("list_corpora", {})
    names = [x.get("corpus_id") or x.get("id") or x for x in (corpora.get("corpora") if isinstance(corpora, dict) else None) or []]
    rep.add("knowledge.list_corpora", "PASS" if names else "FAIL",
            f"{len(names)} corpora visible" if names else f"no corpora returned ({status}): {str(corpora)[:200]}", corpora=names)

    status, _, found = await c.tool("polymath_search", {"query": query, "corpus_id": corpus, "max_evidence": 5})
    rows = found.get("evidence_rows") if isinstance(found, dict) else None
    rep.add("knowledge.search", "PASS" if rows else "FAIL",
            f"polymath_search returned {len(rows)} evidence rows from corpus {corpus!r}" if rows else
            f"polymath_search returned no evidence rows from {corpus!r} ({status}): {str(found)[:300]}",
            corpus=corpus, rows=len(rows or []), contract=(found or {}).get("evidence_contract") if isinstance(found, dict) else None)

    if explore:
        status, _, packet = await c.tool("polymath_explore", {"query": query, "corpus_id": corpus})
        ok = isinstance(packet, dict) and "error" not in packet and packet.get("synthesis_performed") is not True
        rep.add("knowledge.explore", "PASS" if ok else "FAIL",
                "polymath_explore returned an evidence packet with no synthesis" if ok else f"({status}) {str(packet)[:300]}")
    else:
        rep.add("knowledge.explore", "SKIP", "opt-in (--explore): retrieval planning spends provider budget")

    status, _, listed = await c.tool("adapter_list", {})
    ids = [a.get("adapter_id") or a.get("id") for a in (listed.get("adapters") if isinstance(listed, dict) else None) or []]
    absent = [a for a in expect_adapters if a not in ids]
    rep.add("adapter.list", "FAIL" if (absent or not ids) else "PASS",
            f"adapter discovery lacks {absent}; it lists {ids}" if (absent or not ids) else f"adapter discovery lists {ids}",
            adapters=ids, expected=list(expect_adapters))

    status, _, p = await c.tool("adapter_status", {"run_id": NO_SUCH_RUN})
    rep.add("errors.unknown_run", "PASS" if _typed_client_error(p) else "FAIL",
            "an unknown run id is a typed 4xx tool error" if _typed_client_error(p) else f"({status}) {str(p)[:300]}", payload=p)
    status, _, p = await c.tool("adapter_start", {"adapter_id": "acceptance.no_such_adapter", "input": {}})
    rep.add("errors.unknown_adapter", "PASS" if _typed_client_error(p) else "FAIL",
            "an unknown adapter id is a typed 4xx tool error and starts nothing" if _typed_client_error(p) else f"({status}) {str(p)[:300]}", payload=p)
    status, _, p = await c.tool("polymath_search", {"query": query, "corpus_id": NO_SUCH_CORPUS, "max_evidence": 3})
    lawful = _typed_client_error(p) or (isinstance(p, dict) and "error" not in p and not p.get("evidence_rows"))
    rep.add("errors.unknown_corpus", "PASS" if lawful else "FAIL",
            "an unknown corpus yields a typed 4xx or no evidence — never another corpus's rows" if lawful else f"({status}) {str(p)[:300]}",
            rows=len((p or {}).get("evidence_rows") or []) if isinstance(p, dict) else None)
    resp, body = await c.rpc("tools/call", {"name": "acceptance_no_such_tool", "arguments": {}})
    refused = bool(body.get("error")) or bool((body.get("result") or {}).get("isError"))
    rep.add("errors.unknown_tool", "PASS" if (refused and resp.status_code < 500) else "FAIL",
            "an unknown tool is a protocol-level error, not a server fault" if (refused and resp.status_code < 500) else
            f"({resp.status_code}) {str(body)[:300]}", http_status=resp.status_code)

    # ISOLATION: a hosted surface must not resolve a CALLER-SUPPLIED path on the HOST's filesystem. "file not found"
    # proves it looked: any key holder could then ingest (and read back) any host file with an accepted extension.
    if "upload_document" not in tools:
        rep.add("isolation.host_path_upload", "PASS", "the hosted surface exposes no host-path upload tool")
    else:
        status, _, p = await c.tool("upload_document", {"path": PROBE_PATH, "corpus_id": NO_SUCH_CORPUS})
        looked = isinstance(p, dict) and "file not found" in str(p.get("error", "")).lower()
        rep.add("isolation.host_path_upload", "FAIL" if looked else "PASS",
                ("upload_document resolved a caller-supplied path on the HOST filesystem (it answered 'file not found'): every key "
                 "holder can ingest and read back host files with an accepted extension, and probe which paths exist")
                if looked else "upload_document refuses a caller-supplied host path without touching the filesystem", payload=p)

    if cycle:
        await _cycle(rep, c, cycle)
    else:
        rep.add("adapter.cycle", "SKIP", "opt-in (--cycle): starts ONE adapter run on the live fleet, reads its first step, cancels it")


async def _cycle(rep: Report, c: Client, cycle: dict[str, Any]) -> None:
    _, _, ref = await c.tool("adapter_start", {"adapter_id": cycle["adapter_id"], "input": cycle["input"],
                                               "request_options": cycle.get("request_options") or {}})
    run_id = ref.get("run_id") if isinstance(ref, dict) else None
    if not run_id:
        rep.add("adapter.cycle", "FAIL", f"adapter_start returned no run id: {str(ref)[:300]}")
        return
    seen, kind = [], None
    try:
        for _ in range(int(cycle.get("polls", 40))):
            _, _, nxt = await c.tool("adapter_next", {"run_id": run_id})
            kind = nxt.get("kind") if isinstance(nxt, dict) else None
            state = (nxt.get("status") or {}).get("status") if kind == "status" else None
            seen.append(kind if kind != "status" else f"status:{state}")
            if kind == "step" or state not in (None, "running"):
                break
            await asyncio.sleep(float(cycle.get("poll_s", 3)))
    finally:
        _, _, cancelled = await c.tool("adapter_cancel", {"run_id": run_id})
    _, _, status = await c.tool("adapter_status", {"run_id": run_id})
    final = status.get("status") if isinstance(status, dict) else None
    ok = kind == "step" and final == "cancelled"
    rep.add("adapter.cycle", "PASS" if ok else "FAIL",
            "start → next reached an awaiting step → cancel → status cancelled, all through the hosted surface" if ok else
            f"start/next/cancel did not reach (step, cancelled): next={seen[-3:]}, final status={final!r}",
            run_id=run_id, next=seen[-5:], final_status=final, cancel=(cancelled or {}).get("status") if isinstance(cancelled, dict) else None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default=os.environ.get("POLYMATH_HOSTED_MCP_URL", "https://mcp.kingsleylab.xyz"),
                    help="the hosted origin (no /mcp suffix)")
    ap.add_argument("--key-file", default=None, help="file holding the bearer key (else POLYMATH_MCP_API_KEY); never printed")
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--query", default="how do films build suspense")
    ap.add_argument("--expect-adapter", action="append", default=[], help="adapter id that adapter_list MUST show (repeatable)")
    ap.add_argument("--explore", action="store_true", help="also call polymath_explore (provider spend)")
    ap.add_argument("--cycle", default=None, help="JSON file {adapter_id, input, request_options}: start ONE run, read its first step, cancel it")
    ap.add_argument("--vantage", default="unspecified", help="where this ran: host | external:<label>")
    ap.add_argument("--out", default=None, help="write the JSON receipt here as well")
    args = ap.parse_args(argv)

    key = os.environ.get("POLYMATH_MCP_API_KEY") or None
    if args.key_file:
        key = pathlib.Path(args.key_file).expanduser().read_text().strip() or None
    cycle = json.loads(pathlib.Path(args.cycle).read_text()) if args.cycle else None
    url = args.url.rstrip("/")
    url = url[:-4] if url.endswith("/mcp") else url
    receipt = asyncio.run(run(url, key, corpus=args.corpus, query=args.query, expect_adapters=tuple(args.expect_adapter),
                              explore=args.explore, cycle=cycle, vantage=args.vantage))
    text = json.dumps(receipt, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).expanduser().write_text(text + "\n")
    print(text)
    for ch in receipt["checks"]:
        print(f"{ch['status']:4} {ch['id']:28} {ch['detail'][:150]}", file=sys.stderr)
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
