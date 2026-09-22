#!/usr/bin/env python3
"""Governed run JOURNAL (GOVERNED-CONVERGENCE-V1 TG4, docs/27) — what happened in ONE governed product-discovery run.

In governed mode the Polymath cognitive adapter (`trail.product_discovery`) decides what runs next, TrailSignal decides
what counts as evidence and computes the only score, and the AGENT (Hermes / Claude Code / Codex) drives the run with
the adapter's MCP tools: adapter_start -> adapter_next -> adapter_submit ... -> adapter_result. This module does not
drive anything and talks to nothing: the agent hands it the tool outputs it already has, and it keeps them — every
issued step WITH the readable evidence it carried, every submission and the adapter's answer to it, every receipt and
what the receipt builder omitted, and the final AdapterResultV1. The journal is the run's own memory (the adapter
keeps the authoritative one) and the ONLY input of the governed report (`report.build_model_from_governed`).

    python3 python/governed_run.py start         --journal J --run-ref ref.json --input input.json --agent-identity claude-code
    python3 python/governed_run.py record-next   --journal J --file next.json
    python3 python/governed_run.py action        --journal J --out action.json          # the awaiting HarnessActionV1
    python3 python/governed_run.py record-submit --journal J --step-id S --kind reasoning|receipt --payload p.json --response r.json [--receipt-report rr.json]
    python3 python/governed_run.py record-result --journal J --file result.json
    python3 python/governed_run.py status        --journal J
    python3 python/governed_run.py report        --journal J --out dossier.html [--layout FULL_RESEARCH]

Laws: append-only (an event is never rewritten); no score is computed, copied from standalone mode, or re-ranked here;
a rejected submission is recorded as a rejection, never dropped; the journal never holds a credential.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_VERSION = "governed-run-journal-v1"
KINDS = ("start", "step", "status", "submission", "result", "note")
MAX_EVIDENCE_ROWS = 60            # == the adapter's own adapter_next cap; the journal never grows past what was issued
MAX_MATERIALS_BYTES = 300_000      # per step, all shown values together; MAX_MATERIAL_VALUE_BYTES per value — larger ones are named + sized
MAX_MATERIAL_VALUE_BYTES = 120_000


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_path(run_id: str) -> str:
    return os.path.join(ROOT, "state", f"{run_id}.governed.json")


def _skill_version() -> str:
    try:
        with open(os.path.join(ROOT, "manifest.yaml"), encoding="utf-8") as f:
            return next((l.split(":", 1)[1].strip() for l in f if l.startswith("version:")), "unknown")
    except OSError:
        return "unknown"


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


# ----------------------------------------------------------------- journal --
def new_journal(run_ref: dict, input_payload: dict, *, agent_identity: str, harness_id: str | None = None,
                corpus_ids: list | None = None, at: str | None = None) -> dict:
    j = {"journal_version": JOURNAL_VERSION, "skill_version": _skill_version(), "run_id": run_ref.get("run_id"),
         "adapter_id": run_ref.get("adapter_id"), "adapter_version": run_ref.get("adapter_version"),
         "workflow_version": run_ref.get("workflow_version"), "created_at": at or now_iso(), "agent_identity": agent_identity,
         "harness_id": harness_id or agent_identity, "input": dict(input_payload or {}),
         "corpus_ids": list(corpus_ids or (input_payload or {}).get("corpus_ids") or []), "events": []}
    _append(j, "start", {"run_ref": run_ref}, at)
    return j


def _append(journal: dict, kind: str, data: dict, at: str | None = None) -> dict:
    assert kind in KINDS, kind
    ev = {"seq": len(journal["events"]) + 1, "at": at or now_iso(), "kind": kind, "data": data}
    journal["events"].append(ev)
    return ev


def _materials_record(materials) -> dict | None:
    """The `materials` sibling of an issued step (prior step outputs and the derived semantic view the manifest chose to show),
    BOUNDED: a value that fits is kept, a larger one is recorded by name and size only. Execution semantics and ids — never model
    reasoning (there is none in `materials`)."""
    if not isinstance(materials, dict):
        return None
    values, oversized, room = {}, {}, MAX_MATERIALS_BYTES
    for name, val in (materials.get("values") or {}).items():
        size = len(json.dumps(val, ensure_ascii=False, default=str).encode("utf-8"))
        if size <= min(room, MAX_MATERIAL_VALUE_BYTES):
            values[name] = val
            room -= size
        else:
            oversized[name] = size
    return {"values": values, "oversized_bytes": oversized, "missing": list(materials.get("missing") or []), "too_large": list(materials.get("too_large") or []),
            **({"error": materials["error"]} if materials.get("error") else {})}


def record_next(journal: dict, payload: dict, at: str | None = None) -> dict | None:
    """One adapter_next payload. A step is recorded ONCE per (step_id, sequence) — polling returns the same step many times —
    together with the readable evidence it carried. A status payload is recorded only when the status changed."""
    if not isinstance(payload, dict) or payload.get("error"):
        return _append(journal, "note", {"what": "adapter_next returned an error", "payload": payload}, at)
    if payload.get("kind") == "step":
        step = payload.get("step") or {}
        key = (step.get("step_id"), step.get("sequence"))
        if any(e["kind"] == "step" and (e["data"]["step"].get("step_id"), e["data"]["step"].get("sequence")) == key for e in journal["events"]):
            return None
        ev = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        data = {"step": step, "status": (payload.get("status") or {}).get("status"),
                "evidence": {"rows": list(ev.get("rows") or [])[:MAX_EVIDENCE_ROWS], "receipts": list(ev.get("receipts") or []),
                             "coverage": ev.get("coverage"), **({"allocation": ev["allocation"]} if ev.get("allocation") else {}),
                             **({"error": ev["error"]} if ev.get("error") else {})}}
        mats = _materials_record(payload.get("materials"))
        if mats is not None:
            data["materials"] = mats                       # what the agent was SHOWN beside the step — so the dossier can reconstruct it
        return _append(journal, "step", data, at)
    st = payload.get("status") or {}
    last = next((e for e in reversed(journal["events"]) if e["kind"] == "status"), None)
    view = {k: st.get(k) for k in ("status", "current_step_id", "steps_issued", "steps_accepted", "branch_loops", "gap", "failure")}
    if last and last["data"] == view:
        return None
    return _append(journal, "status", view, at)


def record_submission(journal: dict, step_id: str, kind: str, payload: dict, response: dict, *, receipt_report: dict | None = None,
                      at: str | None = None) -> dict:
    """The agent's answer AND what the adapter said about it. A rejection (`error` in the response) is kept as a rejection:
    the step stays open on the adapter's side and the corrected submission becomes its own event."""
    rejected = isinstance(response, dict) and bool(response.get("error"))
    data = {"step_id": step_id, "kind": kind, "payload": payload, "payload_hash": _hash(payload), "accepted": not rejected,
            "response": response if rejected else {k: (response or {}).get(k) for k in ("status", "current_step_id", "steps_accepted", "gap", "failure")}}
    if receipt_report:
        data["receipt_report"] = {k: receipt_report.get(k) for k in ("action_kind", "items_in", "observations", "sources", "omitted", "omitted_by_reason", "notes", "roles", "source_classes", "queries_recorded")}
    return _append(journal, "submission", data, at)


def record_result(journal: dict, result: dict, at: str | None = None) -> dict:
    return _append(journal, "result", {"result": result}, at)


def current_action(journal: dict) -> dict | None:
    """The HarnessActionV1 of the most recently issued HARNESS_ACTION step that has no ACCEPTED receipt yet."""
    for e in reversed(journal["events"]):
        if e["kind"] == "step" and e["data"]["step"].get("step_type") == "HARNESS_ACTION":
            action = e["data"]["step"].get("harness_action") or {}
            done = any(s["kind"] == "submission" and s["data"]["accepted"] and s["data"]["kind"] == "receipt"
                       and (s["data"]["payload"] or {}).get("action_id") == action.get("action_id") for s in journal["events"])
            return None if done else action
    return None


def summary(journal: dict) -> dict:
    ev = journal["events"]
    steps = [e["data"] for e in ev if e["kind"] == "step"]
    subs = [e["data"] for e in ev if e["kind"] == "submission"]
    result = next((e["data"]["result"] for e in reversed(ev) if e["kind"] == "result"), None)
    adms = ((result or {}).get("output") or {}).get("evidence_admissions") or []
    return {"run_id": journal["run_id"], "adapter": f"{journal.get('adapter_id')} {journal.get('adapter_version')}", "events": len(ev),
            "steps_issued": len(steps), "agent_reason_steps": sum(1 for s in steps if s["step"].get("step_type") == "AGENT_REASON"),
            "harness_actions": sum(1 for s in steps if s["step"].get("step_type") == "HARNESS_ACTION"),
            "steps_with_readable_evidence": sum(1 for s in steps if (s.get("evidence") or {}).get("rows")),
            "submissions": len(subs), "rejected_submissions": sum(1 for s in subs if not s["accepted"]),
            "receipts": sum(1 for s in subs if s["kind"] == "receipt" and s["accepted"]),
            "observations_submitted": sum(len((s["payload"] or {}).get("observations") or []) for s in subs if s["kind"] == "receipt" and s["accepted"]),
            "observations_admitted": sum(len(a.get("admitted") or []) for a in adms), "observations_rejected": sum(len(a.get("rejected") or []) for a in adms),
            "terminal": (result or {}).get("status"), "gap": (result or {}).get("gap"), "awaiting_action": (current_action(journal) or {}).get("action_id")}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    if j.get("journal_version") != JOURNAL_VERSION:
        raise SystemExit(f"{path}: not a {JOURNAL_VERSION} journal")
    return j


def save(journal: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(journal, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


# --------------------------------------------------------------------- cli --
def _read(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="governed_run")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("start", "record-next", "action", "record-submit", "record-result", "status", "report"):
        sp = sub.add_parser(name)
        sp.add_argument("--journal", required=(name != "start"), help="journal path (start: default state/<run_id>.governed.json)")
        if name == "start":
            sp.add_argument("--run-ref", required=True, dest="run_ref", help="the adapter_start result (AdapterRunRefV1)")
            sp.add_argument("--input", required=True, help="the `input` object passed to adapter_start")
            sp.add_argument("--agent-identity", required=True, dest="agent_identity")
            sp.add_argument("--harness-id", dest="harness_id", default=None)
        if name in ("record-next", "record-result"):
            sp.add_argument("--file", required=True)
        if name == "action":
            sp.add_argument("--out", required=True)
        if name == "record-submit":
            sp.add_argument("--step-id", required=True, dest="step_id")
            sp.add_argument("--kind", required=True, choices=["reasoning", "receipt"])
            sp.add_argument("--payload", required=True)
            sp.add_argument("--response", required=True, help="the adapter_submit result")
            sp.add_argument("--receipt-report", dest="receipt_report", default=None, help="the JSON note adapter_receipt.py printed on stderr")
        if name == "report":
            sp.add_argument("--out", required=True)
            sp.add_argument("--layout", default="FULL_RESEARCH", choices=["FULL_RESEARCH", "SOURCING", "EXECUTIVE", "COMMERCIAL"])
            sp.add_argument("--model-out", dest="model_out", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "start":
        ref = _read(args.run_ref)
        if ref.get("error") or not ref.get("run_id"):
            print(json.dumps({"ok": False, "error": "adapter_start did not return a run reference", "run_ref": ref})); return 1
        path = args.journal or default_path(ref["run_id"])
        if os.path.exists(path):
            print(json.dumps({"ok": False, "error": f"journal already exists: {path} (a journal is append-only; never restarted)"})); return 1
        save(new_journal(ref, _read(args.input), agent_identity=args.agent_identity, harness_id=args.harness_id), path)
        print(json.dumps({"ok": True, "journal": path, "run_id": ref["run_id"]})); return 0
    journal = load(args.journal)
    if args.cmd == "record-next":
        ev = record_next(journal, _read(args.file)); save(journal, args.journal)
        print(json.dumps({"ok": True, "recorded": (ev or {}).get("kind"), "seq": (ev or {}).get("seq"), "awaiting_action": (current_action(journal) or {}).get("action_id")})); return 0
    if args.cmd == "action":
        action = current_action(journal)
        if not action:
            print(json.dumps({"ok": False, "error": "no HARNESS_ACTION step is awaiting a receipt in this journal"})); return 1
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(action, f, indent=1, ensure_ascii=False)
        print(json.dumps({"ok": True, "action_id": action.get("action_id"), "action_kind": action.get("action_kind"), "budget": action.get("budget"),
                          "search_intents": [i.get("intent_id") for i in action.get("search_intents") or []], "hypothesis_ids": action.get("hypothesis_ids")})); return 0
    if args.cmd == "record-submit":
        ev = record_submission(journal, args.step_id, args.kind, _read(args.payload), _read(args.response),
                               receipt_report=_read(args.receipt_report) if args.receipt_report else None)
        save(journal, args.journal)
        print(json.dumps({"ok": True, "seq": ev["seq"], "accepted": ev["data"]["accepted"]})); return 0
    if args.cmd == "record-result":
        record_result(journal, _read(args.file)); save(journal, args.journal)
        print(json.dumps({"ok": True, **summary(journal)})); return 0
    if args.cmd == "status":
        print(json.dumps(summary(journal), indent=1)); return 0
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import report as _report
    model = _report.build_model_from_governed(journal)
    if args.model_out:
        with open(args.model_out, "w", encoding="utf-8") as f:
            json.dump(model, f, indent=1, ensure_ascii=False)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(_report.render(model, args.layout))
    print(json.dumps({"ok": True, "report": args.out, "verdict": model["run"]["verdict"]})); return 0


if __name__ == "__main__":
    raise SystemExit(main())
