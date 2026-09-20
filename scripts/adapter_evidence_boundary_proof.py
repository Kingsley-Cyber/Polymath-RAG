#!/usr/bin/env python
"""ADAPTER EVIDENCE-BOUNDARY PROOF (GOVERNED-CONVERGENCE-V1 TG2) — READ-ONLY verifier for ONE adapter run.

Given a run id, reads the run's stored steps/result and the query-receipt ledger and asserts, from durable state only:

  1. BOUNDARY RECEIPTS — every evidence-boundary call this run made left a query receipt whose verdict is `evidence_only`
     (correlated by the worker's `User-Agent: polymath-adapter-step/<run>/<step>/<seq>` = `query_receipts.client`), and the
     run left NO synthesis receipt at all (no chat receipt with another verdict, no ask receipt).
  2. PACKETS VALIDATE — every boundary call recorded the consumer-side contract verdict `evidence-packet-v1`,
     `synthesis_performed=false`, `valid=true`. (The packet itself is not stored; the worker validates it against
     contracts/evidence/v1 at call time and a packet that fails ends the run with EVIDENCE_CONTRACT_MISMATCH — so a
     completed boundary step IS a validated packet. This check reads that recorded verdict.)
  3. ROLES ON THE WIRE — at least one issued AdapterStepV1 evidence ref carries `utility_role`.
  4. adapter_next CARRIES TEXT — for every AGENT_REASON step that listed knowledge evidence, the readable-evidence view
     (the SAME pure `hydrate` adapter_next serves, replayed over the outputs stored BEFORE that step) has rows with text.
     The LIVE observation of the same fact is scripts/adapter_mcp_acceptance.py --require-evidence-text.
  5. ADMISSIONS VISIBLE — for trail.product_discovery >= 2.2.0 the result output carries `evidence_admissions`
     (admitted AND rejected, with reason codes), one per evidence.admit step.

Writes nothing. Exit 0 only when every check holds; `--allow-degraded` tolerates a recorded legacy fallback / partial outage
(reported either way). Prints one JSON verdict.

    set -a; . ./.env; set +a
    .venv/bin/python scripts/adapter_evidence_boundary_proof.py --run-id adr_...
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402

KNOWLEDGE_KINDS = ("chunk", "document", "graph_fact", "graph_hop")


def _j(v: Any) -> Any:
    return json.loads(v) if isinstance(v, (str, bytes)) else v


def prove(conn, run_id: str, *, allow_degraded: bool = False) -> dict[str, Any]:
    cur = conn.cursor()
    cur.execute("SELECT adapter_id, adapter_version, retrieval_policy_version, status FROM adapter_runs WHERE run_id=%s", (run_id,))
    run = cur.fetchone()
    if not run:
        raise SystemExit(f"unknown adapter run {run_id!r}")
    cur.execute("SELECT sequence, step_id, step_type, status, step, output FROM adapter_steps WHERE run_id=%s ORDER BY sequence", (run_id,))
    steps = [{"sequence": r[0], "step_id": r[1], "step_type": r[2], "status": r[3], "step": _j(r[4]) or {}, "output": _j(r[5])} for r in cur.fetchall()]
    failures: list[str] = []
    verdict: dict[str, Any] = {"run_id": run_id, "adapter_id": run[0], "adapter_version": run[1], "retrieval_policy_version": run[2], "status": run[3],
                               "steps": len(steps)}

    # ── 1 + 2: boundary calls, their recorded contract verdict, and their receipts
    boundary = [s for s in steps if isinstance(s["output"], dict) and s["output"].get("surface") == EB.SURFACE_BOUNDARY]
    per_step = []
    for s in boundary:
        out = s["output"]
        calls = [c for c in (out.get("calls") or []) if isinstance(c, dict)]
        bad = [c for c in calls if (c.get("contract") or {}) != {"schema_version": EB.PACKET_SCHEMA_VERSION, "synthesis_performed": False, "valid": True}]
        ua = EB.user_agent(run_id, s["step_id"], s["sequence"])
        cur.execute("SELECT kind, verdict, status, mode, evidence FROM query_receipts WHERE client=%s ORDER BY received_at", (ua,))
        rcpts = [{"kind": r[0], "verdict": r[1], "status": r[2], "mode": r[3], "evidence": r[4]} for r in cur.fetchall()]
        chat = [r for r in rcpts if r["kind"] == "chat"]
        per_step.append({"step_id": s["step_id"], "sequence": s["sequence"], "mode": out.get("mode"), "calls": len(calls), "rows": len(out.get("rows") or []),
                         "graph_rows": len(out.get("graph_rows") or []), "retrieval_completed": out.get("retrieval_completed"),
                         "degraded_reasons": out.get("degraded_reasons") or [], "truncated": out.get("truncated") or [],
                         "boundary_receipts": len(chat), "verdicts": sorted({str(r["verdict"]) for r in chat}),
                         "grades": {k: sum((c.get("grades") or {}).get(k, 0) for c in calls) for k in sorted({g for c in calls for g in (c.get("grades") or {})})},
                         "corpus_explorer_used": sum(1 for c in calls if c.get("corpus_explorer_used"))})
        if bad:
            failures.append(f"{s['step_id']}#{s['sequence']}: {len(bad)} call(s) without a valid evidence-packet-v1 contract verdict")
        if len(chat) < len(calls):
            failures.append(f"{s['step_id']}#{s['sequence']}: {len(calls)} boundary call(s) but {len(chat)} query receipt(s) for {ua}")
        if any(r["verdict"] != "evidence_only" for r in chat):
            failures.append(f"{s['step_id']}#{s['sequence']}: a boundary receipt is not evidence_only: {sorted({str(r['verdict']) for r in chat})}")
    verdict["boundary_steps"] = per_step
    verdict["boundary_calls"] = sum(p["calls"] for p in per_step)
    if not boundary:
        failures.append("no step ran on the evidence_boundary surface")
    cur.execute("SELECT kind, verdict, count(*) FROM query_receipts WHERE client LIKE %s GROUP BY 1, 2 ORDER BY 1, 2", (f"polymath-adapter-step/{run_id}/%",))
    ledger = [{"kind": r[0], "verdict": r[1], "n": r[2]} for r in cur.fetchall()]
    verdict["run_receipts"] = ledger
    synthesis = [r for r in ledger if r["kind"] == "ask" or (r["kind"] == "chat" and r["verdict"] != "evidence_only")]
    verdict["synthesis_receipts"] = sum(r["n"] for r in synthesis)
    if synthesis:
        failures.append(f"the run left synthesis receipts: {synthesis}")
    degraded = [p for p in per_step if p["degraded_reasons"]] + [
        {"step_id": s["step_id"], "sequence": s["sequence"], "degraded_reasons": s["output"].get("degraded_reasons")}
        for s in steps if isinstance(s["output"], dict) and s["output"].get("surface") != EB.SURFACE_BOUNDARY and s["output"].get("degraded_reasons")]
    verdict["degraded"] = [{"step_id": d["step_id"], "sequence": d["sequence"], "reasons": d["degraded_reasons"]} for d in degraded]
    if degraded and not allow_degraded:
        failures.append(f"{len(degraded)} knowledge step(s) ran degraded (pass --allow-degraded to tolerate): {verdict['degraded']}")

    # ── 3: roles on the wire
    with_role = sum(1 for s in steps for r in ((s["step"].get("context") or {}).get("evidence_refs") or []) if r.get("utility_role"))
    verdict["issued_refs_with_utility_role"] = with_role
    if not with_role:
        failures.append("no issued evidence ref carries utility_role")

    # ── 4: adapter_next carries TEXT (the same pure hydrate, replayed over what was stored before each agent step)
    views = []
    for s in steps:
        if s["step_type"] != "AGENT_REASON":
            continue
        refs = (s["step"].get("context") or {}).get("evidence_refs") or []
        knowledge = sum(1 for r in refs if r.get("kind") in KNOWLEDGE_KINDS)
        ev = EB.hydrate(refs, [{"step_id": p["step_id"], "sequence": p["sequence"], "output": p["output"]} for p in steps if p["sequence"] < s["sequence"]])
        text_rows = sum(1 for r in ev["rows"] if str(r.get("text") or "").strip())
        views.append({"step_id": s["step_id"], "sequence": s["sequence"], "refs": len(refs), "knowledge_refs": knowledge, "rows": len(ev["rows"]), "rows_with_text": text_rows,
                      "text_chars": sum(len(str(r.get("text") or "")) for r in ev["rows"]), "rows_with_utility_role": sum(1 for r in ev["rows"] if r.get("utility_role")),
                      "kinds": sorted({str(r.get("kind")) for r in ev["rows"]}), "unresolved": ev["coverage"]["unresolved"]})
        if knowledge and not text_rows:
            failures.append(f"{s['step_id']}#{s['sequence']}: {knowledge} knowledge refs but no readable evidence text")
        if len(ev["rows"]) > EB.HYDRATE_MAX_ROWS or any(len(str(r.get("text") or "")) > EB.HYDRATE_MAX_CHARS for r in ev["rows"]):
            failures.append(f"{s['step_id']}#{s['sequence']}: readable evidence exceeds the {EB.HYDRATE_MAX_ROWS} x {EB.HYDRATE_MAX_CHARS} cap")
    verdict["adapter_next_views"] = views
    if not views:
        failures.append("the run issued no AGENT_REASON step")

    # ── 5: admissions visible in the result
    cur.execute("SELECT result FROM adapter_results WHERE run_id=%s", (run_id,))
    row = cur.fetchone()
    result = _j(row[0]) if row else None
    admit_steps = [s for s in steps if isinstance(s["output"], dict) and isinstance(s["output"].get("evidence_admission"), dict)]
    adms = ((result or {}).get("output") or {}).get("evidence_admissions") or []
    verdict["admissions"] = {"admit_steps": len(admit_steps), "in_result": len(adms), "admitted": sum(len(a.get("admitted") or []) for a in adms),
                             "rejected": sum(len(a.get("rejected") or []) for a in adms),
                             "rejection_reason_codes": sorted({str(r.get("reason_code")) for a in adms for r in (a.get("rejected") or [])})}
    if run[0] == "trail.product_discovery" and result is not None and result.get("status") == "completed":
        if len(adms) != len(admit_steps) or not admit_steps:
            failures.append(f"result.output.evidence_admissions has {len(adms)} entries for {len(admit_steps)} evidence.admit step(s)")
        if any("admitted" not in a or "rejected" not in a for a in adms):
            failures.append("an evidence admission in the result lacks its admitted/rejected lists")
    verdict["failures"] = failures
    verdict["ok"] = not failures
    return verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--dsn", default=os.environ.get("POLYMATH_PG_DSN"), help="Postgres DSN (default: $POLYMATH_PG_DSN)")
    ap.add_argument("--allow-degraded", action="store_true", help="tolerate a recorded legacy fallback / partial outage (still reported)")
    args = ap.parse_args(argv)
    if not args.dsn:
        raise SystemExit("POLYMATH_PG_DSN is required (source .env)")
    with psycopg.connect(args.dsn, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")          # this verifier never writes
        verdict = prove(conn, args.run_id, allow_degraded=args.allow_degraded)
    print(json.dumps(verdict, indent=1, default=str))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
