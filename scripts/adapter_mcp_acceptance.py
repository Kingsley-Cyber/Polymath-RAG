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
    # HARNESS-RESEARCH-MIGRATION-V1 (ADR-0019): the harness-executed loop. A HARNESS_ACTION step pauses the run until a
    # HarnessResearchReceiptV1 arrives — either from a REAL harness (Hermes / Claude Code / Codex answering through its own
    # MCP connection while this driver polls: --harness wait) or from receipt files for a scripted acceptance
    # (--harness-receipts DIR with AGENT_RESEARCH.json / PRODUCT_REALITY_CHECK.json / SUPPLIER_RESEARCH.json).
    .venv/bin/python scripts/adapter_mcp_acceptance.py --adapter trail.product_discovery --corpus cinema --harness wait
    .venv/bin/python scripts/adapter_mcp_acceptance.py --adapter trail.product_discovery --corpus cinema --harness-receipts /path/to/receipts
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


def answer_product_discovery(step: dict[str, Any]) -> dict[str, Any]:
    """θ answers for trail.product_discovery 2.0.0 — every citation is an id from the step context; no score anywhere (LAW 1)."""
    ctx = step["context"]
    knowledge = sorted({r["id"] for r in ctx["evidence_refs"] if r["kind"] in ("chunk", "document", "graph_fact", "graph_hop", "parent_map")})
    field = sorted({r["id"] for r in ctx["evidence_refs"] if r["kind"] == "field_evidence"})
    live = [h["hypothesis_id"] for h in ctx.get("hypotheses") or [] if h["status"] not in ("killed", "merged")]
    sid = step["step_id"]
    if sid == "C_hypotheses":
        return {"hypotheses": [
            {"statement": "audiences read a screen hit from the reaction shot and framing, not from physical contact", "mechanism": "eyeline and shot scale hide the miss and sell the reaction",
             "population": "film students staging fights", "activity": "staging screen fights", "task": "sell a punch to camera", "context": "coverage and editing", "suspected_friction": "legibility versus realism",
             "supporting_evidence_ids": knowledge[:2], "knowledge_gaps": [{"question": "do practitioners describe the trade-off in the field?", "evidence_role": "behavior"}]},
            # HR4 (ADR-064) portfolio canary: a SECOND live hypothesis. The scripted harness tags every field observation to the
            # non-first hypothesis (see load_receipt), so a correct portfolio scores this one and records a typed refusal for the first.
            {"statement": "stunt coordinators lose the hit's legibility in wide coverage because the camera cannot hide the miss", "mechanism": "wide shot scale exposes the gap the reaction shot would have hidden",
             "population": "stunt coordinators rehearsing screen fights", "activity": "rehearsing wide-shot fight coverage", "task": "keep the hit legible in one wide shot", "context": "single-camera wide coverage", "suspected_friction": "legibility collapses at wide shot scale",
             "supporting_evidence_ids": (knowledge[2:4] or knowledge[:2]), "knowledge_gaps": [{"question": "do coordinators report re-blocking wide shots for legibility?", "evidence_role": "friction"}]}]}
    if sid in ("G_mechanisms", "K_revise"):
        cause = ([{"kind": "field_evidence", "id": field[0]}] if field
                 else [{"kind": "chunk", "id": knowledge[0]}] if knowledge and any(r["kind"] == "chunk" and r["id"] == knowledge[0] for r in ctx.get("evidence_refs") or [])
                 else [{"kind": "hypothesis", "id": live[0]}] if live else [])
        return {"transitions": ([{"hypothesis_id": live[0], "kind": "REVISE", "cause_refs": cause, "changes": {"mechanism": "framing, eyeline and cutting rhythm carry the hit"}, "reason_code": "MECHANISM_REFINED"}] if live and cause else []),
                **({"knowledge_gaps": [{"hypothesis_id": live[0], "question": "how often do practitioners lose legibility in wide coverage?", "evidence_role": "behavior"}]} if sid == "G_mechanisms" and live else {}),
                **({"open_gaps": []} if sid == "K_revise" else {})}
    if sid == "N_jobs":
        return {"transitions": [], "physical_jobs": [{"hypothesis_id": h, "job": "make the hit legible in one wide shot", "mechanism": "blocking to the lens with a hidden miss"} for h in live]}
    if sid == "W_interpret":
        score_refs = [str(x) for x in (step["context"].get("inputs") or {}).get("trail_score_refs", [])]
        return {"product_opportunity": {"product_concept": {"title": "lens-first fight blocking guide", "mechanism_explanation": "framing carries the hit", "population": "film students", "activity": "staging screen fights",
                                                            "context": "coverage and editing", "problem": "legibility versus realism"},
                                        "evidence_chain": [{"hypothesis_id": h, "supporting_evidence_ids": knowledge[:2]} for h in live], "field_evidence_ids": field[:2], "contradictions": [], "competing_products": [], "product_delta": None, "supply": None,
                                        "trail_score_refs": score_refs, "remaining_uncertainty": ["field population size"], "cheapest_falsification_experiment": "interview ten fight coordinators"}}
    raise SystemExit(f"no scripted answer for step {sid}")


ADAPTERS = {
    "polymath.knowledge_brief": {"input": lambda corpus: {"question": "How does editing rhythm shape the audience's sense of a fight's stakes?", "corpus_ids": [corpus], "top_k": 10},
                                 "answer": answer_knowledge_brief, "expect_status": "completed"},
    "substack.article_development": {"input": lambda corpus: {"seed_idea": "Fight choreography is storytelling: the camera, not the punch, decides what the audience believes", "corpus_ids": [corpus], "audience": "film students"},
                                     "answer": answer_substack, "expect_status": "completed"},
    "trail.product_discovery": {"input": lambda corpus: {"seed": "fight choreography: the camera, not the punch, decides what the audience believes", "corpus_ids": [corpus]},
                                "answer": answer_product_discovery, "expect_status": "completed"},
}


TAGGED_HYPOTHESES: set[str] = set()   # hypothesis ids the scripted receipts tagged their observations to (HR4 portfolio proof)


def load_receipt(receipts_dir: str, action: dict[str, Any]) -> dict[str, Any]:
    """A scripted harness: `<receipts_dir>/<action_kind>.json` is a HarnessResearchReceiptV1 whose action/run ids are filled in here."""
    path = os.path.join(receipts_dir, f"{action['action_kind']}.json")
    if not os.path.exists(path):
        raise SystemExit(f"no scripted receipt for {action['action_kind']} at {path}")
    with open(path) as f:
        rec = json.load(f)
    rec.update({"action_id": action["action_id"], "run_id": action["run_id"]})
    # HR4 (ADR-064) portfolio canary: observations are tagged to the SECOND live hypothesis whenever the action carries two or more,
    # so the evidence-free first hypothesis must come back as a typed refusal and the non-first one as the deterministic score.
    targets = [str(h) for h in action["hypothesis_ids"]]
    tagged = targets[1:2] or targets[:1]
    TAGGED_HYPOTHESES.update(tagged)
    for o in rec.get("observations") or []:
        o.setdefault("hypothesis_ids", list(tagged))
    return rec


async def run(adapter_id: str, corpus: str, mcp_url: str, key: str, restart: bool, *, harness: str = "receipts", receipts_dir: str | None = None,
              harness_id: str = "mcp-acceptance-harness") -> dict[str, Any]:
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
                receipts["agent_steps"] = []; receipts["harness_actions"] = []; restarted = not restart; rejected_once = False
                for _ in range(2000):
                    nxt = val(await s.call_tool("adapter_next", {"run_id": rid}))
                    if nxt["kind"] == "status":
                        st = nxt["status"]
                        if st["status"] in ("completed", "terminal_gap", "failed", "cancelled"):
                            break
                        await asyncio.sleep(2)
                        continue
                    step = nxt["step"]
                    if step["step_type"] == "HARNESS_ACTION":
                        action = step["harness_action"]
                        receipts["harness_actions"].append({"step_id": step["step_id"], "action_id": action["action_id"], "action_kind": action["action_kind"],
                                                            "hypothesis_ids": len(action["hypothesis_ids"]), "search_intents": len(action["search_intents"]), "registry_snapshot": action["registry_snapshot"]["snapshot_id"]})
                        if harness == "wait":
                            # a REAL harness answers through its own MCP connection; this driver only shows the action and waits
                            print(json.dumps({"awaiting_harness": action}, indent=1, default=str), flush=True)
                            while True:
                                st = val(await s.call_tool("adapter_status", {"run_id": rid}))
                                if st["status"] != "awaiting_harness":
                                    break
                                await asyncio.sleep(5)
                            continue
                        rec = load_receipt(receipts_dir or "", action)
                        rec["harness_id"] = harness_id
                        ans = val(await s.call_tool("adapter_submit", {"run_id": rid, "step_id": step["step_id"], "agent_identity": harness_id, "kind": "receipt", "payload": rec}))
                        if "error" in ans:
                            raise SystemExit(f"receipt rejected: {ans}")
                        await asyncio.sleep(1)
                        continue
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
                    gap = res.get("gap") or {}
                    if gap.get("code") == "TRAIL_CAPABILITY_PLANNED":
                        # honest state until TrailSignal HR3 is WORKING: the run stops at the first planned Trail operation (exit 3 in main)
                        receipts["planned_gap"] = gap
                        return receipts
                    raise SystemExit(f"run ended {res['status']}: {gap or receipts['final_status']}")
                cited = set()
                for step_rec in receipts["agent_steps"]:
                    pass
                for k in ("brief", "article", "product_opportunity"):
                    if k in res["output"]:
                        blob = json.dumps(res["output"][k])
                        cited = {i for i in res["lineage"]["polymath_evidence_ids"] if i in blob}
                receipts["result"]["cited_ids_in_lineage"] = len(cited)
                if not cited:
                    raise SystemExit("the output cites no evidence id present in the lineage")
                if adapter_id == "trail.product_discovery":
                    # HR4 (ADR-064) portfolio proof: at least two live hypotheses; the hypothesis the receipts tagged carries the
                    # deterministic Trail score; when two or more were still live at scoring, an untagged one carries a typed refusal.
                    lin, out = res["lineage"], res["output"]
                    scores = [s for s in (out.get("trail_scores") or []) if isinstance(s, dict)]
                    refusals = [r for r in (out.get("score_refusals") or []) if isinstance(r, dict)]
                    receipts["portfolio"] = {"hypotheses": len(lin["hypothesis_ids"]), "tagged": sorted(TAGGED_HYPOTHESES), "scored": [s.get("hypothesis_id") for s in scores],
                                             "refused": [(r.get("hypothesis_id"), r.get("reason_code")) for r in refusals], "trail_score_record_ids": lin["trail_score_record_ids"],
                                             "qualifications": len(out.get("qualifications") or [])}
                    if len(lin["hypothesis_ids"]) < 2:
                        raise SystemExit(f"portfolio proof needs two live hypotheses: {receipts['portfolio']}")
                    if not lin["trail_score_record_ids"] or not scores:
                        raise SystemExit(f"no Trail score record reached the result: {receipts['portfolio']}")
                    if not any(s.get("hypothesis_id") in TAGGED_HYPOTHESES for s in scores):
                        raise SystemExit(f"the hypothesis carrying the field evidence was not the one scored: {receipts['portfolio']}")
                    if len(scores) + len(refusals) >= 2 and not any(r.get("hypothesis_id") not in TAGGED_HYPOTHESES for r in refusals):
                        raise SystemExit(f"the evidence-free hypothesis was not refused: {receipts['portfolio']}")
    return receipts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=sorted(ADAPTERS), default="polymath.knowledge_brief")
    ap.add_argument("--corpus", default=os.environ.get("POLYMATH_ADAPTER_TEST_CORPUS", "cinema"))
    ap.add_argument("--mcp-url", default=os.environ.get("POLYMATH_MCP_URL", "http://127.0.0.1:8930/mcp"))
    ap.add_argument("--no-restart", action="store_true", help="skip the supervised-worker restart proof")
    ap.add_argument("--harness", choices=("receipts", "wait"), default="receipts", help="who answers HARNESS_ACTION steps: scripted receipt files, or a real harness through its own MCP connection (this driver waits)")
    ap.add_argument("--harness-receipts", default=os.environ.get("POLYMATH_HARNESS_RECEIPTS"), help="directory of <ACTION_KIND>.json HarnessResearchReceiptV1 files for --harness receipts")
    ap.add_argument("--harness-id", default="mcp-acceptance-harness")
    args = ap.parse_args(argv)
    key = os.environ.get("POLYMATH_MCP_API_KEY")
    if not key:
        raise SystemExit("POLYMATH_MCP_API_KEY is required (source .env)")
    receipts = asyncio.run(run(args.adapter, args.corpus, args.mcp_url, key, restart=not args.no_restart, harness=args.harness,
                               receipts_dir=args.harness_receipts, harness_id=args.harness_id))
    print(json.dumps(receipts, indent=1, default=str))
    if receipts.get("planned_gap"):
        print(f"PLANNED GAP: {receipts['planned_gap']['message']} — the loop resumes once TrailSignal HR3 is WORKING", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
