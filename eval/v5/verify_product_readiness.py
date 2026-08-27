"""PRODUCT-READINESS-GATE-V1: is the QUERY PRODUCT healthy — not just
the ingestion fleet?

The worker fence (verify_live_build.py, 13/13) proves the PIPELINE is
running its declared bundle; the 2026-08-26 SMART verification showed
it passing while the product API could not even import. This gate
covers the product surface:

  stores        Postgres / Qdrant / Neo4j reachable
  query app     7200 /health + every required route registered
  dependencies  embedder (8742) + reranker (8743) /ready
  scope         missing scope on /retrieve is a typed 422 (live probe
                of the fail-closed contract, not a unit test)
  semantics     /semantic_readiness answers for a named corpus
  abstention    a scoped nonce /chat abstains (verdict
                insufficient_evidence)  [--corpus required]

Exit 0 only when every enforced check passes. Run it AFTER the fence,
in the retrieval (or full) profile.

Usage:
  .venv/bin/python eval/v5/verify_product_readiness.py [--corpus CID]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

BASE = "http://127.0.0.1:7200"
REQUIRED_ROUTES = {"/health", "/ready", "/sidecars", "/intake", "/ask",
                   "/retrieve", "/evidence", "/chat",
                   "/semantic_readiness"}

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'ok' if ok else 'FAIL':4s}] {name:28s} {detail}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None,
                    help="corpus for semantic-readiness + abstention probes")
    args = ap.parse_args()

    # stores
    try:
        import psycopg

        from polymath_shared.settings import get_settings

        s = get_settings()
        psycopg.connect(s.postgres.dsn, connect_timeout=5).close()
        check("postgres", True)
    except Exception as exc:
        check("postgres", False, f"{type(exc).__name__}: {exc}")
    try:
        r = httpx.get(f"{s.stores.qdrant_url}/collections", timeout=5)
        check("qdrant", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as exc:
        check("qdrant", False, f"{type(exc).__name__}")
    try:
        from polymath_shared.stores import neo4j_driver

        d = neo4j_driver()
        with d.session() as session:
            session.run("RETURN 1").consume()
        d.close()
        check("neo4j", True)
    except Exception as exc:
        check("neo4j", False, f"{type(exc).__name__}")

    # query application
    try:
        r = httpx.get(f"{BASE}/health", timeout=5)
        check("query_app_health", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as exc:
        check("query_app_health", False, f"{type(exc).__name__} (port 7200 down)")
    try:
        r = httpx.get(f"{BASE}/openapi.json", timeout=10)
        paths = set((r.json().get("paths") or {}).keys())
        missing = REQUIRED_ROUTES - paths
        check("required_routes", not missing,
              f"missing: {sorted(missing)}" if missing else f"{len(REQUIRED_ROUTES)} present")
    except Exception as exc:
        check("required_routes", False, f"{type(exc).__name__}")

    # required query dependencies
    for name, url in (("embedder_ready", "http://127.0.0.1:8742/ready"),
                      ("reranker_ready", "http://127.0.0.1:8743/ready")):
        try:
            r = httpx.get(url, timeout=15)
            ready = r.status_code == 200 and r.json().get("ready") is True
            check(name, ready, "" if ready else r.text[:80])
        except Exception as exc:
            check(name, False, f"{type(exc).__name__}")

    # scope fail-closed (live probe)
    try:
        r = httpx.post(f"{BASE}/retrieve", json={"query": "readiness probe"},
                       timeout=15)
        detail = r.json().get("detail") if r.status_code == 422 else None
        ok = (r.status_code == 422 and isinstance(detail, dict)
              and detail.get("error_code") == "QUERY_SCOPE_REQUIRED")
        check("scope_fail_closed", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        check("scope_fail_closed", False, f"{type(exc).__name__}")

    if args.corpus:
        try:
            r = httpx.get(f"{BASE}/semantic_readiness",
                          params={"corpus_id": args.corpus}, timeout=30)
            v = r.json().get("verdict") if r.status_code == 200 else None
            check("semantic_readiness", r.status_code == 200,
                  f"{args.corpus}: {v}")
        except Exception as exc:
            check("semantic_readiness", False, f"{type(exc).__name__}")
        try:
            r = httpx.post(f"{BASE}/chat", json={
                "message": "what is the glorbofex spindle quotient",
                "corpus_id": args.corpus}, timeout=60)
            meta = (r.json() or {}).get("meta") or {}
            ok = (r.status_code == 200 and meta.get("abstained") is True
                  and meta.get("verdict") == "insufficient_evidence")
            check("nonce_abstains", ok,
                  f"verdict={meta.get('verdict')}" if r.status_code == 200
                  else f"HTTP {r.status_code}")
        except Exception as exc:
            check("nonce_abstains", False, f"{type(exc).__name__}")

    failed = [n for n, ok, _ in RESULTS if not ok]
    total = len(RESULTS)
    print(f"\n  => {'PASS' if not failed else 'FAIL'} "
          f"({total - len(failed)}/{total} product checks)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
