"""K1 live check ($0 — no model call; register 11.485). Run after the merge + bounce that deploys K1, from the main
checkout with the main .env loaded. Four /retrieve calls in GRAPH mode for one question, against the live orchestrator:
  1. no scope → 200, and its receipt carries no `knowledge_scope` (a request without a scope is unchanged);
  2. Trail's reference-only scope → 200, and its receipt keeps `knowledge_scope == {"roles": ["reference"]}`. Its
     passages are compared with call 1 and reported (no implementation material exists yet, so they should match up to
     run noise);
  3. a malformed scope → 422 `invalid_scope`, and its error receipt keeps `knowledge_scope == {"invalid": true}`;
  4. implementation-only → 200 with 0 passages. Nothing is implementation material yet, so this is the proof that the
     role clause reaches the live Qdrant searches. Graph facts are reported, not judged: they are authorized in Postgres,
     which cannot filter by role before migration 0067 (gap K-03, C1).
Then orchestrator.log must hold no Traceback written while the calls ran. Pre-K1 code fails 2, 3 and 4 (it ignores the
scope). Exit 0 only when all hold. Writes live_check.json next to this file (ids and counts only, no text)."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import httpx
import psycopg

HERE = pathlib.Path(__file__).resolve().parent
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200")
LOG = pathlib.Path(os.environ.get("POLYMATH_ORCH_LOG", "/private/tmp/polymath_fleet/orchestrator.log"))
QUESTION = "How do editors and directors build suspense without dialogue?"
CALLS = (("none", None), ("reference", {"roles": ["reference"]}), ("malformed", {"roles": "reference"}),
         ("implementation", {"roles": ["implementation"]}))


def _call(scope) -> dict:
    body = {"query": QUESTION, "corpus_id": "cinema", "mode": "GRAPH", "limit": 10}
    if scope is not None:
        body["scope"] = scope
    t0 = time.perf_counter()
    r = httpx.post(f"{ORCH}/retrieve", json=body, timeout=180)
    out = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    detail = out.get("detail") if isinstance(out, dict) else None
    return {"http": r.status_code, "wall_ms": round((time.perf_counter() - t0) * 1000),
            "evidence": [e.get("chunk_id") for e in (out.get("evidence") or []) if isinstance(e, dict)],
            "graph_facts": len(out.get("graph_relationships") or []),
            "error_code": detail.get("error_code") if isinstance(detail, dict) else None}


def main() -> int:
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=True)
    started = conn.execute("select clock_timestamp()").fetchone()[0]
    log_from = LOG.stat().st_size if LOG.exists() else 0
    runs = {name: _call(scope) for name, scope in CALLS}
    time.sleep(2)                                                   # receipts are written after the response
    rows = conn.execute("select meta->'knowledge_scope', status, error is not null from query_receipts "
                        "where kind = 'retrieve' and question_head = %s and received_at >= %s order by received_at",
                        (QUESTION, started)).fetchall()
    for (name, _), row in zip(CALLS, rows):
        runs[name]["receipt"] = {"knowledge_scope": row[0], "status": row[1], "error": row[2]}
    new_log = LOG.read_bytes()[log_from:].decode("utf-8", "replace") if LOG.exists() else ""
    none, ref, bad, impl = (runs[n] for n, _ in CALLS)
    checks = {
        "four_receipts": len(rows) == len(CALLS),
        "none_ok_and_unchanged_receipt": none["http"] == 200 and bool(none["evidence"])
                                         and (none.get("receipt") or {}).get("knowledge_scope") is None,
        "reference_ok_and_recorded": ref["http"] == 200 and bool(ref["evidence"])
                                     and (ref.get("receipt") or {}).get("knowledge_scope") == {"roles": ["reference"]},
        "malformed_refused_and_recorded": bad["http"] == 422 and bad["error_code"] == "invalid_scope"
                                          and (bad.get("receipt") or {}).get("knowledge_scope") == {"invalid": True},
        "implementation_only_finds_nothing": impl["http"] == 200 and impl["evidence"] == [],
        "no_new_traceback": "Traceback" not in new_log,
    }
    report = {"question": QUESTION, "started": str(started), "runs": runs, "checks": checks,
              "reference_vs_none": {"same": ref["evidence"] == none["evidence"],
                                    "new_in_reference": sum(1 for c in ref["evidence"] if c not in none["evidence"]),
                                    "of": len(none["evidence"])}}
    (HERE / "live_check.json").write_text(json.dumps(report, indent=1, default=str))
    for name, _ in CALLS:
        r = runs[name]
        print(name, "http", r["http"], "evidence", len(r["evidence"]), "facts", r["graph_facts"], "error_code",
              r["error_code"], "receipt", r.get("receipt"), "wall_ms", r["wall_ms"], flush=True)
    print("reference_vs_none", report["reference_vs_none"])
    print(checks)
    ok = all(checks.values())
    print("ALL CHECKS PASS" if ok else "A CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
