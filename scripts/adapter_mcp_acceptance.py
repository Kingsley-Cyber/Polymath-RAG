#!/usr/bin/env python
"""ADAPTER MCP ACCEPTANCE (COGNITIVE-ADAPTER-TRAIL-E2E-V1 final-acceptance shape, Trail-free half).

Drives ONE real adapter run through the OFFICIAL `mcp` Python client connected ONLY to Polymath's MCP server:
adapter_list → adapter_start → adapter_next … adapter_submit (scripted agent answers that cite only supplied
evidence) → adapter_status → adapter_result, with a CONTROLLED RESTART of the supervised `adapter_step` worker
between the first AGENT_REASON step's issue and its submission (the supervisor must respawn it and the run must
resume). The client never calls TrailSignal. Prints a JSON receipt (run_id, evidence counts, restart pids, the
rejected-submission reason, result lineage). Exit 0 only when every observable check holds.

    set -a; . ./.env; set +a
    .venv/bin/python scripts/adapter_mcp_acceptance.py --adapter polymath.knowledge_brief --corpus cinema
    .venv/bin/python scripts/adapter_mcp_acceptance.py --adapter substack.article_development --corpus cinema
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from typing import Any


def supervised_worker_pid() -> int | None:
    out = subprocess.run(["pgrep", "-f", "workers.adapter_step_worke[r]"], capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else None


def restart_supervised_worker() -> dict[str, Any]:
    """SIGKILL the supervised adapter_step worker; the process supervisor must respawn it (restart budget permitting)."""
    pid = supervised_worker_pid()
    if not pid:
        raise SystemExit("no supervised adapter_step worker is running (is the fleet booted on E2+ code?)")
    os.kill(pid, signal.SIGKILL)
    for _ in range(60):
        time.sleep(2)
        new = supervised_worker_pid()
        if new and new != pid:
            return {"killed_pid": pid, "respawned_pid": new}
    raise SystemExit("the supervisor did not respawn the adapter_step worker within 120 s")


# ── scripted "agent" answers per adapter: each returns a payload citing ONLY ids from the issued step's context ──
def _ids(step: dict[str, Any]) -> list[str]:
    return sorted({r["id"] for r in step["context"]["evidence_refs"]})


def answer_knowledge_brief(step: dict[str, Any]) -> dict[str, Any]:
    ids = _ids(step)
    return {"brief": {"thesis": "cutting rhythm signals control and danger: longer takes read as competence, fragmentation as chaos",
                      "key_points": [{"point": "shot duration carries the stakes", "supporting_evidence_ids": ids[:2]}],
                      "unknowns": ["how genre conventions shift this"]}}


def answer_substack(step: dict[str, Any]) -> dict[str, Any]:
    ids = _ids(step)
    if step["step_id"] == "thesis":
        return {"theses": [
            {"claim": "The camera's framing, not the physical contact, creates the audience's belief in a hit", "mechanism": "eyeline and shot scale hide the miss and sell the reaction",
             "tension": "realism versus legibility", "counterargument": "practical contact reads more convincingly in wide shots",
             "supporting_evidence_ids": ids[:2], "counterargument_evidence_ids": ids[2:3], "unknowns": ["how much is lost on small screens"]},
            {"claim": "Choreography is authored for the lens first and the performer second", "mechanism": "beats are staged to the camera position before rehearsal",
             "tension": "performer safety versus visual clarity", "counterargument": "stunt-first rehearsal produces safer coverage",
             "supporting_evidence_ids": ids[1:3], "counterargument_evidence_ids": []}]}
    if step["step_id"] == "narrative":
        return {"chosen_thesis": "The camera's framing creates the audience's belief in a hit", "analogy": {"text": "a magician's misdirection", "evidence_ids": ids[:1]},
                "implications": ["directors should block fights from the lens outward"],
                "sections": [{"title": "Hook", "narrative_role": "hook", "evidence_ids": []}, {"title": "The claim", "narrative_role": "claim", "evidence_ids": ids[:1]},
                             {"title": "How the trick works", "narrative_role": "mechanism", "evidence_ids": ids[:2]}, {"title": "But contact sells", "narrative_role": "counterargument", "evidence_ids": ids[2:3]},
                             {"title": "What it means", "narrative_role": "implication", "evidence_ids": []}, {"title": "Close", "narrative_role": "close", "evidence_ids": []}]}
    if step["step_id"] == "draft":
        body = "Framing decides what the audience believes about a punch; the reaction shot, not the contact, carries the hit. " * 2
        return {"article": {"title": "The Camera Throws the Punch", "citation_ids": ids[:3], "word_count": 120,
                            "sections": [{"title": "Hook", "narrative_role": "hook", "body": body, "citation_ids": []},
                                         {"title": "The claim", "narrative_role": "claim", "body": body + f" [{ids[0]}]", "citation_ids": ids[:1]},
                                         {"title": "But contact sells", "narrative_role": "counterargument", "body": body + f" [{ids[2]}]", "citation_ids": ids[2:3]}]}}
    raise SystemExit(f"no scripted answer for step {step['step_id']}")


ADAPTERS = {
    "polymath.knowledge_brief": {"input": lambda corpus: {"question": "How does editing rhythm shape the audience's sense of a fight's stakes?", "corpus_ids": [corpus], "top_k": 10},
                                 "answer": answer_knowledge_brief, "expect_status": "completed"},
    "substack.article_development": {"input": lambda corpus: {"seed_idea": "Fight choreography is storytelling: the camera, not the punch, decides what the audience believes", "corpus_ids": [corpus], "audience": "film students"},
                                     "answer": answer_substack, "expect_status": "completed"},
}


async def run(adapter_id: str, corpus: str, mcp_url: str, key: str, restart: bool) -> dict[str, Any]:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    spec = ADAPTERS[adapter_id]
    receipts: dict[str, Any] = {"adapter_id": adapter_id, "mcp_url": mcp_url, "client": "mcp python client (streamable-http)",
                                "trail_calls_by_client": 0, "supervised_worker_pid": supervised_worker_pid()}

    def val(r: Any) -> Any:
        sc = getattr(r, "structured_content", None)
        if sc is None:
            sc = getattr(r, "structuredContent", None)
        if sc is not None:
            return sc["result"] if isinstance(sc, dict) and set(sc) == {"result"} else sc
        return json.loads(r.content[0].text)

    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=120) as http:
        async with streamable_http_client(mcp_url, http_client=http) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                tools = {t.name for t in (await s.list_tools()).tools}
                receipts["adapter_tools_present"] = sorted(t for t in tools if t.startswith("adapter_"))
                missing = {"adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status", "adapter_result", "adapter_cancel"} - tools
                if missing:
                    raise SystemExit(f"adapter tools missing on the MCP server: {sorted(missing)}")
                listing = val(await s.call_tool("adapter_list", {}))
                receipts["adapters"] = [a["adapter_id"] for a in listing["adapters"]]
                ref = val(await s.call_tool("adapter_start", {"adapter_id": adapter_id, "input": spec["input"](corpus),
                    "request_options": {"corpus_ids": [corpus], "agent_identity": "mcp-acceptance", "idempotency_key": f"accept-{adapter_id}-{int(time.time())}"}}))
                rid = ref["run_id"]; receipts["run_id"] = rid; receipts["run_ref"] = ref
                receipts["agent_steps"] = []; restarted = not restart; rejected_once = False
                for _ in range(400):
                    nxt = val(await s.call_tool("adapter_next", {"run_id": rid}))
                    if nxt["kind"] == "status":
                        st = nxt["status"]
                        if st["status"] in ("completed", "terminal_gap", "failed", "cancelled"):
                            break
                        await asyncio.sleep(2)
                        continue
                    step = nxt["step"]
                    ids = _ids(step)
                    receipts["agent_steps"].append({"step_id": step["step_id"], "sequence": step["sequence"], "evidence_refs": len(ids)})
                    if not restarted:
                        receipts["restart"] = restart_supervised_worker(); restarted = True
                    if not rejected_once:
                        bad = val(await s.call_tool("adapter_submit", {"run_id": rid, "step_id": step["step_id"], "agent_identity": "mcp-acceptance",
                            "payload": {"invented": True, "supporting_evidence_ids": ["chunk_invented"]}}))
                        receipts["rejected_submission"] = bad; rejected_once = True
                        if "error" not in bad and "rejected" not in json.dumps(bad):
                            raise SystemExit(f"an invented submission was not rejected: {bad}")
                    ok = val(await s.call_tool("adapter_submit", {"run_id": rid, "step_id": step["step_id"], "agent_identity": "mcp-acceptance",
                                                                  "model": "scripted-acceptance", "payload": spec["answer"](step)}))
                    if "error" in ok:
                        raise SystemExit(f"submission rejected unexpectedly: {ok}")
                    await asyncio.sleep(1)
                st = val(await s.call_tool("adapter_status", {"run_id": rid}))
                receipts["final_status"] = {k: st.get(k) for k in ("status", "steps_issued", "steps_accepted", "branch_loops", "gap", "failure")}
                res = val(await s.call_tool("adapter_result", {"run_id": rid}))
                receipts["result"] = {"status": res["status"], "output_keys": sorted(res["output"]), "lineage_evidence": len(res["lineage"]["polymath_evidence_ids"]),
                                      "receipts": len(res["lineage"]["step_receipt_hashes"]), "external_operations": res["lineage"]["external_operations"],
                                      "unknowns": res["unknowns"], "gap": res.get("gap")}
                if res["status"] != spec["expect_status"]:
                    raise SystemExit(f"run ended {res['status']}: {res.get('gap') or receipts['final_status']}")
                cited = set()
                for step_rec in receipts["agent_steps"]:
                    pass
                for k in ("brief", "article"):
                    if k in res["output"]:
                        blob = json.dumps(res["output"][k])
                        cited = {i for i in res["lineage"]["polymath_evidence_ids"] if i in blob}
                receipts["result"]["cited_ids_in_lineage"] = len(cited)
                if not cited:
                    raise SystemExit("the output cites no evidence id present in the lineage")
    return receipts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=sorted(ADAPTERS), default="polymath.knowledge_brief")
    ap.add_argument("--corpus", default=os.environ.get("POLYMATH_ADAPTER_TEST_CORPUS", "cinema"))
    ap.add_argument("--mcp-url", default=os.environ.get("POLYMATH_MCP_URL", "http://127.0.0.1:8930/mcp"))
    ap.add_argument("--no-restart", action="store_true", help="skip the supervised-worker restart proof")
    args = ap.parse_args(argv)
    key = os.environ.get("POLYMATH_MCP_API_KEY")
    if not key:
        raise SystemExit("POLYMATH_MCP_API_KEY is required (source .env)")
    receipts = asyncio.run(run(args.adapter, args.corpus, args.mcp_url, key, restart=not args.no_restart))
    print(json.dumps(receipts, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
