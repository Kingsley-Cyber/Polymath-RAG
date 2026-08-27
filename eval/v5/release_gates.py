"""RELEASE GATES — the checks that must pass before any QUALIFIED verdict.

This exists so a favourable semantic result cannot, on its own, produce a
"production ready" claim while operational evidence is still weak. Every
gate is evaluated from live state or committed artefacts; a gate whose
evidence is absent reports UNPROVEN, never PASS.

Two gates were added deliberately after the verdict was first drafted,
because both were quietly weak:

  BOOT_RECOVERY   macOS blocks launchd from executing the boot script
                  under ~/Documents (exit 126), so `launchctl` silently
                  no-ops and the fleet does NOT come back after a
                  reboot. Until the bootstrap path is relocated and
                  proven, "unattended production recovery" is not a
                  claim we may make.

  EXACT_REPLAY    the fact-replay harness tolerated six extra facts
                  ("replay-permissive"). Operationally harmless, but a
                  report saying "deterministic replay: PASS" on top of a
                  harness that silently accepts differences is weaker
                  evidence than the sentence implies. Replay must mean
                  set equality, or the exceptions must be declared.

Ordering mirrors the qualification plan: mechanical convergence, then
sealed semantic qualification, then retrieval, then recovery. A gate
that depends on an earlier one reports BLOCKED rather than FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

PASS, FAIL, UNPROVEN, BLOCKED = "PASS", "FAIL", "UNPROVEN", "BLOCKED"

#: where each gate's evidence is expected to live
EVIDENCE = ROOT / "eval" / "v5" / "release_evidence"


def _ev(name: str) -> dict | None:
    p = EVIDENCE / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PHASE A/B — mechanical convergence
# ---------------------------------------------------------------------------

def gate_convergence(conn, corpus: str) -> dict:
    docs = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE corpus_id=%s", (corpus,)).fetchone()[0]
    ready = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='query_ready'",
        (corpus,)).fetchone()[0]
    unresolved = conn.execute(
        """SELECT COUNT(*) FROM stage_tickets WHERE corpus_id=%s
             AND status IN ('ready','leased','pending')""", (corpus,)).fetchone()[0]
    ok = docs > 0 and ready >= docs and unresolved == 0
    return {"gate": "CONVERGENCE", "status": PASS if ok else FAIL,
            "detail": f"{ready}/{docs} query_ready, {unresolved} unresolved tickets"}


def gate_incrementality() -> dict:
    """A delta must cost delta-sized work, and a restart must resume."""
    ev = _ev("incrementality")
    if ev is None:
        return {"gate": "INCREMENTALITY", "status": UNPROVEN,
                "detail": "no incrementality evidence recorded"}
    scales = ev.get("rows_projected", 0) <= max(ev.get("rows_changed", 0) * 3, 50)
    resumed = bool(ev.get("resume_no_recompute"))
    ok = scales and resumed
    return {"gate": "INCREMENTALITY", "status": PASS if ok else FAIL,
            "detail": (f"projected {ev.get('rows_projected')} for "
                       f"{ev.get('rows_changed')} changed; "
                       f"resume_no_recompute={resumed}")}


def gate_reliability(conn, corpus: str) -> dict:
    faults = conn.execute(
        """SELECT COUNT(*) FROM stage_tickets WHERE corpus_id=%s
             AND last_error_note LIKE 'lease_expired_while_owner_alive%%'""",
        (corpus,)).fetchone()[0]
    blocked = conn.execute(
        """SELECT COUNT(*) FROM pg_stat_activity WHERE datname='polymath'
             AND wait_event_type='Lock'""").fetchone()[0]
    ok = faults == 0 and blocked == 0
    return {"gate": "RELIABILITY", "status": PASS if ok else FAIL,
            "detail": f"lease_faults={faults}, blocked_queries={blocked}"}


# ---------------------------------------------------------------------------
# PHASE C/D/E — retrieval baseline and the sealed exam
# ---------------------------------------------------------------------------

def gate_text_retrieval() -> dict:
    ev = _ev("retrieval_fast_hybrid")
    if ev is None:
        return {"gate": "FAST_HYBRID", "status": UNPROVEN,
                "detail": "no FAST/HYBRID panel recorded"}
    ok = ev.get("fast_ok") and ev.get("hybrid_ok") and ev.get("isolation_ok")
    return {"gate": "FAST_HYBRID", "status": PASS if ok else FAIL,
            "detail": json.dumps({k: ev.get(k) for k in
                                  ("fast_ok", "hybrid_ok", "isolation_ok")})}


def gate_holdout() -> dict:
    """The decisive measurement. Development numbers are NOT admissible."""
    ev = _ev("sealed_holdout")
    if ev is None:
        return {"gate": "SEALED_HOLDOUT", "status": UNPROVEN,
                "detail": "holdout not run; development results are not "
                          "release evidence"}
    sup, wrong = ev.get("supported_pct", 0), ev.get("wrong_pct", 100)
    unexplained = ev.get("unexplained", 1)
    zero_bars = ev.get("zero_tolerance", {})
    zeros_ok = all(v == 0 for v in zero_bars.values()) if zero_bars else False
    ok = sup >= 90 and wrong <= 5 and unexplained == 0 and zeros_ok
    return {"gate": "SEALED_HOLDOUT", "status": PASS if ok else FAIL,
            "detail": (f"supported {sup}% (need >=90), wrong {wrong}% "
                       f"(need <=5), unexplained {unexplained}, "
                       f"zero-tolerance clean={zeros_ok}")}


def gate_graph(holdout_status: str) -> dict:
    if holdout_status != PASS:
        return {"gate": "GRAPH", "status": BLOCKED,
                "detail": "T2 not qualified; GRAPH remains experimental and "
                          "non-asserted by design"}
    ev = _ev("retrieval_graph")
    if ev is None:
        return {"gate": "GRAPH", "status": UNPROVEN,
                "detail": "no GRAPH panel against a qualified T2 projection"}
    return {"gate": "GRAPH", "status": PASS if ev.get("useful") else FAIL,
            "detail": json.dumps(ev)[:160]}


# ---------------------------------------------------------------------------
# PHASE G — the two closure gates
# ---------------------------------------------------------------------------

def gate_boot_recovery() -> dict:
    """Can the machine come back on its own?

    A LaunchAgent pointing into a TCC-protected tree (~/Documents,
    ~/Desktop, ~/Downloads) exits 126 and silently does nothing, which is
    exactly what happened here: `launchctl kickstart` reported success
    for hours while the fleet ran stale code.
    """
    plist = Path.home() / "Library/LaunchAgents/com.polymath.v5.plist"
    if not plist.exists():
        return {"gate": "BOOT_RECOVERY", "status": FAIL,
                "detail": "no LaunchAgent installed"}
    text = plist.read_text()
    protected = [p for p in ("/Documents/", "/Desktop/", "/Downloads/")
                 if p in text]
    if protected:
        return {"gate": "BOOT_RECOVERY", "status": FAIL,
                "detail": (f"bootstrap path is inside a TCC-protected tree "
                           f"({protected[0]}): launchd cannot execute it "
                           f"(exit 126). Relocate before claiming unattended "
                           f"recovery.")}
    ev = _ev("boot_recovery")
    if ev is None:
        return {"gate": "BOOT_RECOVERY", "status": UNPROVEN,
                "detail": "path is outside the protected tree but no live "
                          "launchd recovery test recorded"}
    ok = ev.get("fleet_returned") and ev.get("build_fence_passed")
    return {"gate": "BOOT_RECOVERY", "status": PASS if ok else FAIL,
            "detail": json.dumps(ev)[:160]}


def gate_exact_replay() -> dict:
    """Replay must mean set equality, or the exceptions must be declared.

    The harness previously tolerated six extra facts. That is
    operationally harmless — replay is permissive, so production never
    gains unattested edges — but "deterministic replay: PASS" printed on
    top of a tolerant comparison overstates the evidence.
    """
    ev = _ev("exact_replay")
    if ev is None:
        return {"gate": "EXACT_REPLAY", "status": UNPROVEN,
                "detail": "no replay result recorded"}
    extra, missing = ev.get("extra", -1), ev.get("missing", -1)
    declared = ev.get("declared_exceptions", [])
    if extra == 0 and missing == 0:
        return {"gate": "EXACT_REPLAY", "status": PASS,
                "detail": "replayed fact set is identical"}
    if extra > 0 and len(declared) == extra and missing == 0:
        return {"gate": "EXACT_REPLAY", "status": PASS,
                "detail": f"{extra} differences, all declared contract "
                          f"exceptions"}
    return {"gate": "EXACT_REPLAY", "status": FAIL,
            "detail": f"extra={extra} missing={missing}, "
                      f"declared={len(declared)} — replay is permissive"}


# ---------------------------------------------------------------------------

def evaluate(corpus: str) -> dict:
    conn = psycopg.connect(DSN, connect_timeout=10)
    gates = [gate_convergence(conn, corpus), gate_incrementality(),
             gate_reliability(conn, corpus), gate_text_retrieval()]
    holdout = gate_holdout()
    gates.append(holdout)
    gates.append(gate_graph(holdout["status"]))
    gates.append(gate_boot_recovery())
    gates.append(gate_exact_replay())

    blocking = [g for g in gates if g["status"] in (FAIL, UNPROVEN)]
    if not blocking:
        verdict = "PRODUCTION RELEASE — QUALIFIED"
    elif all(g["gate"] in ("GRAPH",) or g["status"] == BLOCKED for g in blocking):
        verdict = "PRODUCTION RELEASE — QUALIFIED WITH KNOWN LIMITATIONS"
    else:
        verdict = "NOT PRODUCTION READY"
    return {"corpus": corpus, "gates": gates,
            "blocking": [g["gate"] for g in blocking], "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="release-books-v1")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = evaluate(a.corpus)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        print("RELEASE GATES")
        for g in rep["gates"]:
            print(f"  [{g['status']:8s}] {g['gate']:16s} {g['detail']}")
        print(f"\n  VERDICT: {rep['verdict']}")
        if rep["blocking"]:
            print(f"  blocking: {', '.join(rep['blocking'])}")
    return 0 if rep["verdict"].startswith("PRODUCTION RELEASE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
