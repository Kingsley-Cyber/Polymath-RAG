#!/usr/bin/env python
"""PRODUCTION-CONFORMANCE-AUDIT-V1 — the re-firable auditor.

Thin orchestration only; the reusable logic lives in
`shared/polymath_shared/conformance/`. See
`docs/wiki/plans/PRODUCTION-CONFORMANCE-AUDIT-V1.md` for the authority.

    python scripts/audit_polymath.py --discover          # topology only, no DB writes
    python scripts/audit_polymath.py --no-spend          # CI-safe: full static + live reads
    python scripts/audit_polymath.py --full              # + route probes
    python scripts/audit_polymath.py --function PMAP     # narrow to one function
    python scripts/audit_polymath.py --lane <lane>
    python scripts/audit_polymath.py --provider <name>   # discovered, never hardcoded
    python scripts/audit_polymath.py --model <name>
    python scripts/audit_polymath.py --retirement-candidates
    python scripts/audit_polymath.py --prove-unused <component>

NOTHING about the current topology is hardcoded: providers, models, accounts, lanes,
workers, routes and tables are rediscovered on every run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.conformance import AUDIT_VERSION  # noqa: E402
from polymath_shared.conformance import assess, discovery, evidence, report  # noqa: E402
from polymath_shared.conformance.classify import State  # noqa: E402


def _conn():
    dsn = os.environ.get("POLYMATH_PG_DSN")
    if not dsn:
        return None
    try:
        import psycopg
        return psycopg.connect(dsn, autocommit=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Postgres unavailable ({type(exc).__name__}) — static-only evidence", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Polymath production conformance audit")
    ap.add_argument("--discover", action="store_true", help="topology only")
    ap.add_argument("--no-spend", action="store_true", help="CI-safe: no provider calls")
    ap.add_argument("--full", action="store_true", help="static + live reads + route probes")
    ap.add_argument("--live-canary", action="store_true", help="allow bounded provider spend")
    ap.add_argument("--function", help="narrow to one function (discovered)")
    ap.add_argument("--provider"); ap.add_argument("--model"); ap.add_argument("--lane")
    ap.add_argument("--retirement-candidates", action="store_true")
    ap.add_argument("--prove-unused", metavar="COMPONENT")
    ap.add_argument("--out", help="bundle root (default artifacts/audit)")
    a = ap.parse_args()

    scope = {k: v for k, v in vars(a).items() if v}
    live_calls = 0
    conn = _conn()

    print(f"[{AUDIT_VERSION}] discovering …")
    snap = discovery.snapshot(conn)
    lanes = snap["lanes"]

    # ── narrowing: every filter matches on DISCOVERED values ──────────────
    if a.function:
        lanes = [l for l in lanes if l["function"] == a.function]
    if a.provider:
        lanes = [l for l in lanes if l["provider"] == a.provider]
    if a.model:
        lanes = [l for l in lanes if l["model"] == a.model]
    if a.lane:
        lanes = [l for l in lanes if l["name"] == a.lane]

    controller = evidence.controller_state(conn) if conn else {}
    stage_act = evidence.stage_activity(conn) if conn else {}
    git = evidence.git_state()
    rbundle = evidence.runtime_bundle(conn) if conn else {"live": [], "uniform": None}

    # ── L2/L3/L5 qualification evidence -- already-durable, zero new spend ─────
    from polymath_shared.conformance.attempts import ledger_available, attempt_summary
    attempts_per_lane: dict[str, dict] = {}
    if conn is not None and ledger_available(conn):
        attempts_per_lane = {r["lane"]: r for r in attempt_summary(conn)["per_lane"]}
    receipt_summary = evidence.query_receipt_summary(conn) if conn is not None else {}
    chat_receipts = receipt_summary.get("overall") or {}

    components: list[dict] = []
    components += assess.assess_lanes(lanes, controller)

    if not a.discover:
        components += assess.assess_workers(
            snap["workers_on_disk"], snap["supervisor"],
            snap.get("live_workers", {}), stage_act)

        probes = None
        if a.full:
            paths = [r["path"] for r in snap["routes"]]
            probes = evidence.probe_routes(paths)
            live_calls += len(probes)
        components += assess.assess_routes(snap["routes"], probes)

        tables = snap.get("tables") or []
        readers = evidence.reader_writer_census([t["table"] for t in tables]) if tables else {}
        components += assess.assess_state(tables, readers)

    summary = assess.summarize(components)

    # ── retirement view ───────────────────────────────────────────────────
    retire = [c for c in components
              if c["state"] in (State.RETIRE_CANDIDATE.value, State.DEAD_PROVEN.value)]
    if a.retirement_candidates:
        print("\nRETIREMENT CANDIDATES\n")
        for c in sorted(retire, key=lambda x: (x["kind"], x["name"])):
            print(f"  {c['kind']:7} {c['name']:42} {c['state']:18} {c['notes'][:70]}")
        print(f"\n  {len(retire)} candidate(s). Removal requires the zero-reader proof "
              f"(--prove-unused <component>).")

    if a.prove_unused:
        target = a.prove_unused
        cen = evidence.reader_writer_census([target])
        r = cen.get(target, {})
        print(f"\nUNUSED PROOF for {target!r}\n")
        print(f"  static readers ({len(r.get('readers', []))}): {r.get('readers')}")
        print(f"  static writers ({len(r.get('writers', []))}): {r.get('writers')}")
        proven = not r.get("readers") and not r.get("writers")
        print(f"\n  static verdict: {'ZERO READERS/WRITERS' if proven else 'STILL REFERENCED'}")
        print("  NOTE: static proof alone is NOT sufficient. Runtime readers, scheduler")
        print("        producers, fallback references and rollback need must also be zero.")

    # ── bundle ────────────────────────────────────────────────────────────
    b = report.Bundle(root=Path(a.out) if a.out else None)
    discovered = {
        "functions": len({l["function"] for l in snap["lanes"]}),
        "providers": len({l["provider"] for l in snap["lanes"]}),
        "models": len({l["model"] for l in snap["lanes"] if l["model"]}),
        "accounts": len({l["account_env"] for l in snap["lanes"] if l["account_env"]}),
        "lanes": len(snap["lanes"]),
        "workers": len(snap["workers_on_disk"]),
        "routes": len(snap["routes"]),
        "states": len(snap.get("tables") or []),
    }
    man = report.manifest(git=git, bundle_state=rbundle,
                          config=evidence.config_hashes(), scope=scope,
                          discovered=discovered, live_calls=live_calls)
    b.write("manifest.json", man)
    b.write("runtime_topology.json", snap)
    b.write("function_results.json", components)
    b.write("qualification_matrix.json",
           _matrix(snap["lanes"], controller, attempts_per_lane, stage_act, chat_receipts))
    b.write("retirement_candidates.json", retire)
    b.write("failures.json", [c for c in components if c["severity"] == "red"])
    b.write("legacy_scan.json", snap["legacy_scan"])

    sections = {
        "ATTEMPT ACCOUNTING": _attempt_accounting(conn),
        "LEGACY SCAN": {x["probe"]: {"code_files": len(x["code_files"]),
                                     "docs_only": x["docs_only"]} for x in snap["legacy_scan"]},
        "_discovery": "YES",
        "_agnostic": "see tests/determinism/test_conformance_agnostic.py",
        "_retirement": "PARTIAL — static proof implemented; runtime proof required",
    }
    text = report.render_report(man, components, summary, sections)
    b.write_text("report.md", text)

    print(f"\n  bundle: {b.dir}")
    print(f"  components: {summary['total']}  green {summary['green']} "
          f"amber {summary['amber']} red {summary['red']}")
    for st, n in summary["by_state"].items():
        print(f"    {st:22} {n}")
    if not rbundle.get("uniform", True):
        print(f"\n  ** runtime bundle NOT uniform: {rbundle.get('live')} — a fleet bounce is due")
    return 0


def _matrix(lanes: list[dict], controller: dict, attempts_per_lane: dict[str, dict],
           stage_act: dict[str, dict], chat_receipts: dict) -> list[dict]:
    """Per-lane qualification matrix. L2/L3/L5 are computed from evidence ALREADY durable
    in Postgres (the attempt ledger + stage_tickets + query_receipts) -- see
    `assess.qualify_lane`. A lane/function with genuinely zero recent evidence still
    reports NOT_TESTED honestly; this never dispatches a fresh call to manufacture a
    verdict, so it costs nothing to run and needs no `--live-canary` spend authorization
    to reflect real, already-happened production traffic."""
    rows = []
    for l in lanes:
        st = controller.get(l["name"], {})
        q = assess.qualify_lane(l, attempts_per_lane, controller, stage_act, chat_receipts)
        rows.append({
            "function": l["function"], "provider": l["provider"], "model": l["model"],
            "lane": l["name"], "account_env": l["account_env"],
            "configured": l["enabled"], "reachable": l["reachability"] == "active",
            "observed": bool(st.get("day_count")),
            "contract_qualified": q["contract_qualified"],
            "pipeline_qualified": q["pipeline_qualified"],
            "e2e_qualified": q["e2e_qualified"],
            "qualification_evidence": q["qualification_evidence"],
            "production_eligible": l["enabled"] and l["reachability"] == "active"
                                   and l["function"] != "dedicated_unpinned",
            "last_dispatch_at": st.get("last_dispatch_at"),
            "rpd_used_today": st.get("day_count"),
        })
    return rows


def _attempt_accounting(conn) -> dict:
    """Provider ATTEMPTS vs function OUTCOMES — the gap this framework exists to close."""
    if conn is None:
        return {"available": False}
    out: dict = {}
    try:
        rows = conn.execute("""
            SELECT COALESCE(last_error,'SUCCESS'), COUNT(*)
              FROM document_parent_map_batches
             WHERE updated_at > now() - interval '24 hours' GROUP BY 1""").fetchall()
        out["batch_outcomes_24h"] = {r[0]: r[1] for r in rows}
    except Exception as exc:  # noqa: BLE001
        out["batch_outcomes_24h"] = f"unavailable: {exc}"
    try:
        from polymath_shared.conformance.attempts import ledger_available, attempt_summary
        out["attempt_ledger"] = (attempt_summary(conn) if ledger_available(conn)
                                 else {"available": False,
                                       "note": "no attempt ledger — per-attempt 429s are invisible"})
    except Exception:
        out["attempt_ledger"] = {"available": False,
                                 "note": "no attempt ledger — per-attempt 429s are invisible"}
    return out


if __name__ == "__main__":
    raise SystemExit(main())
