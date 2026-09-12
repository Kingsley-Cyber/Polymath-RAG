"""Evidence gathering: the observations the assessment turns into verdicts."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def controller_state(conn) -> dict[str, dict]:
    """Durable limiter ledger, keyed by LANE name (the row key is `llm_cloud[<lane>]`)."""
    out: dict[str, dict] = {}
    for key, state, updated in conn.execute(
            "SELECT key, state, updated_at FROM llm_controller_state").fetchall():
        name = key[len("llm_cloud["):-1] if key.startswith("llm_cloud[") and key.endswith("]") else key
        s = state if isinstance(state, dict) else {}
        out[name] = {"day": s.get("day"), "day_count": s.get("day_count"),
                     "effective": s.get("effective"), "ceiling": s.get("ceiling"),
                     "decreases": s.get("decreases"), "increases": s.get("increases"),
                     "last_dispatch_at": s.get("last_dispatch_at"),
                     "updated_at": str(updated) if updated else None}
    return out


def stage_activity(conn, window: str = "24 hours") -> dict[str, dict]:
    rows = conn.execute(f"""
        SELECT stage,
               COUNT(*) FILTER (WHERE updated_at > now() - interval '{window}') recent,
               COUNT(*) total,
               MAX(updated_at) last
          FROM stage_tickets GROUP BY 1""").fetchall()
    return {r[0]: {"recent": r[1], "total": r[2], "last": str(r[3]) if r[3] else None}
            for r in rows}


def reader_writer_census(tables: list[str]) -> dict[str, dict]:
    """Static reader/writer census per table, from tracked source only.

    A SELECT/JOIN/FROM mention counts as a reader; INSERT/UPDATE/DELETE as a writer.
    Deliberately conservative: anything ambiguous is recorded as a reader, because
    over-counting readers only DELAYS a retirement, while under-counting enables a
    wrong deletion.

    `docs/` and `tests/` are NOT excluded (PRODUCTION-CONFORMANCE-AUDIT-V1 follow-up,
    2026-09-12): they were, and it silently contradicted this function's own stated
    philosophy — measured false negative: `tests/contracts/test_admission_boundary.py`
    asserts `"knowledge_tier_facts" in src` (a live contract test proving the symbol
    is load-bearing), and `docs/SEMANTIC_CONTRACTS.md`/`docs/WAY_AHEAD.md` both
    document it, yet the census reported ZERO readers/writers and the table was
    classified RETIRE_CANDIDATE. A contract-test assertion is exactly the kind of
    strong, unambiguous liveness signal this function exists to catch, not the kind of
    incidental mention worth discarding.
    """
    out: dict[str, dict] = {}
    for t in tables:
        try:
            res = subprocess.run(["git", "grep", "-n", "-i", "--", t],
                                 cwd=ROOT, capture_output=True, text=True, timeout=45)
            lines = [l for l in res.stdout.splitlines() if l.strip()]
        except Exception:
            out[t] = {}
            continue
        readers, writers = set(), set()
        for line in lines:
            f = line.split(":", 1)[0]
            if not f.endswith((".py", ".sql", ".ts", ".tsx", ".md")):
                continue
            low = line.lower()
            if any(k in low for k in ("insert into", "update ", "delete from", "create table", "alter table")):
                writers.add(f)
            else:
                readers.add(f)
        # a migration that creates the table is not a live writer
        writers = {w for w in writers if "migrations/" not in w}
        readers = {r for r in readers if "migrations/" not in r}
        out[t] = {"readers": sorted(readers), "writers": sorted(writers)}
    return out


def probe_routes(paths: list[str], base: str | None = None,
                 timeout: int = 10) -> dict[str, dict]:
    """GET-probe read-only routes. Never probes a mutating method or an unknown param."""
    base = base or os.environ.get("POLYMATH_BASE_URL", "http://127.0.0.1:7200")
    out: dict[str, dict] = {}
    for p in paths:
        if "{" in p:          # needs a real id — left to the function-level canaries
            continue
        try:
            with urllib.request.urlopen(f"{base}{p}", timeout=timeout) as r:
                out[p] = {"ok": 200 <= r.status < 300, "status": r.status}
        except urllib.error.HTTPError as e:   # noqa: F821
            # 422 on a route that requires query params is NOT a failure of the route
            out[p] = {"ok": e.code in (400, 422), "status": e.code,
                      "error": "missing required parameters" if e.code in (400, 422) else e.reason}
        except Exception as exc:  # noqa: BLE001
            out[p] = {"ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}"}
    return out


def git_state() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"sha": g("rev-parse", "HEAD"), "branch": g("branch", "--show-current"),
            "dirty": bool(g("status", "--porcelain")),
            "unpushed": g("rev-list", "--count", "@{u}..HEAD") or "unknown"}


def runtime_bundle(conn) -> dict:
    rows = conn.execute(
        "SELECT DISTINCT LEFT(execution_bundle_hash,16) FROM worker_registrations "
        "WHERE heartbeat_at > now() - interval '60 seconds'").fetchall()
    live = [r[0] for r in rows]
    try:
        from polymath_shared.execution_bundle import compute_execution_bundle
        repo = compute_execution_bundle().get("execution_bundle_hash", "")[:16]
    except Exception:
        repo = ""
    return {"live": live, "repo_computed": repo, "uniform": len(live) <= 1}


def config_hashes() -> dict:
    import hashlib
    out = {}
    for rel in ("config/cloud_providers.json", "config/extraction_models/limiter.yaml"):
        p = ROOT / rel
        if p.exists():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out
