"""Topology discovery. Everything here READS the current system; nothing is hardcoded.

Sources, in order of authority:
    1. the lane registry  (config/cloud_providers.json + limiter seeds)  — what is configured
    2. Postgres                                                          — what actually happened
    3. the running processes / supervisor state                          — what is live now
    4. the repo file graph                                               — what exists in code

A provider, model, account, lane, worker, route or table that appears in ANY of these is
discovered. Replacing a model means editing config and re-firing this module.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


# ── configured topology ──────────────────────────────────────────────────────

@dataclass
class Lane:
    name: str
    function: str
    provider: str            # derived from the endpoint host / model namespace
    model: str
    account_env: str         # ENV NAME ONLY — never a secret value
    enabled: bool
    dedicated: bool
    reachability: str
    role: str
    stage_pin: str | None
    fallback_tier: str | None
    capacity: dict


def _provider_of(model: str, host: str) -> str:
    """Provider identity from the endpoint, not from a hardcoded list of vendor names."""
    if host:
        h = host.lower()
        for token in ("groq", "openrouter", "googleapis", "gemini", "nvidia",
                      "siliconflow", "aliyuncs", "openai", "anthropic", "localhost", "127.0.0.1"):
            if token in h:
                return {"googleapis": "google", "aliyuncs": "alibaba",
                        "localhost": "local", "127.0.0.1": "local"}.get(token, token)
        return h.split(".")[-2] if "." in h else h
    return (model.split("/", 1)[0] if "/" in model else "unknown")


def configured_lanes() -> list[Lane]:
    from polymath_shared.llm_extraction import lane_registry as LR
    reg = LR.build_registry()
    cfg = json.loads((ROOT / "config" / "cloud_providers.json").read_text())
    pins: dict[str, tuple[str, int]] = {}
    for stage, lanes in (cfg.get("stage_pins") or {}).items():
        for i, name in enumerate(lanes):
            pins[name] = (stage, i)
    out: list[Lane] = []
    for l in reg.lanes:
        stage, idx = pins.get(l.name, (None, None))
        c = l.capacity
        out.append(Lane(
            name=l.name, function=str(l.function),
            provider=_provider_of(l.model or "", getattr(l, "provider_host", "") or ""),
            model=l.model or "", account_env=l.api_key_env or "",
            enabled=bool(l.enabled), dedicated=bool(l.dedicated),
            reachability=str(l.reachability), role=str(l.role),
            stage_pin=stage,
            fallback_tier=(None if idx is None else ("primary" if idx == 0 else f"fallback{idx}")),
            capacity={"rpm": c.rpm, "tpm": c.tpm, "rpd": c.rpd,
                      "concurrency": c.conc_cap, "family": c.family,
                      "map_batch_cap": l.map_batch_cap},
        ))
    return out


def configured_functions(lanes: list[Lane]) -> dict[str, list[str]]:
    fns: dict[str, list[str]] = {}
    for l in lanes:
        fns.setdefault(l.function, []).append(l.name)
    return {k: sorted(v) for k, v in sorted(fns.items())}


# ── runtime topology ─────────────────────────────────────────────────────────

def running_processes() -> list[dict]:
    """Live polymath processes, by their own venv path — not by a name allowlist."""
    try:
        out = subprocess.run(["ps", "-Ao", "pid,lstart,command"], capture_output=True,
                             text=True, timeout=15).stdout
    except Exception:
        return []
    rows = []
    for line in out.splitlines():
        if str(ROOT) not in line or "grep" in line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid, rest = parts
        m = re.search(r"(-m |/)([A-Za-z0-9_./]+)$", rest)
        rows.append({"pid": int(pid), "command": rest.strip()[:200],
                     "module": (m.group(2) if m else "")})
    return rows


def supervisor_state() -> dict:
    p = Path(os.environ.get("POLYMATH_FLEET_DIR", "/tmp/polymath_fleet")) / "supervisor_state.json"
    try:
        s = json.loads(p.read_text())
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    slots = s.get("slots", [])
    return {"available": True, "path": str(p), "slots": slots,
            "alive": [x["name"] for x in slots if x.get("alive")],
            "parked": [x["name"] for x in slots if not x.get("alive") and not x.get("quarantined")],
            "quarantined": [x["name"] for x in slots if x.get("quarantined")]}


def live_workers(conn) -> dict:
    rows = conn.execute(
        "SELECT worker_type, status, COUNT(*), COUNT(DISTINCT LEFT(execution_bundle_hash,16)) "
        "FROM worker_registrations WHERE heartbeat_at > now() - interval '60 seconds' "
        "GROUP BY 1,2 ORDER BY 1").fetchall()
    bundles = [r[0] for r in conn.execute(
        "SELECT DISTINCT LEFT(execution_bundle_hash,16) FROM worker_registrations "
        "WHERE heartbeat_at > now() - interval '60 seconds'").fetchall()]
    return {"by_type": [{"worker_type": r[0], "status": r[1], "count": r[2]} for r in rows],
            "total": sum(r[2] for r in rows), "bundles": bundles,
            "bundle_uniform": len(bundles) <= 1}


# ── code topology ────────────────────────────────────────────────────────────

def api_routes() -> list[dict]:
    """Routes from the LIVE app when reachable, else from the router source."""
    import urllib.request
    base = os.environ.get("POLYMATH_BASE_URL", "http://127.0.0.1:7200")
    try:
        with urllib.request.urlopen(f"{base}/openapi.json", timeout=8) as r:
            doc = json.load(r)
        return [{"path": p, "methods": sorted(m.upper() for m in ops if m in
                 ("get", "post", "put", "delete", "patch")), "source": "live"}
                for p, ops in sorted(doc.get("paths", {}).items())]
    except Exception:
        routes = []
        for f in sorted((ROOT / "orchestrator" / "orchestrator" / "api").glob("*.py")):
            for m in re.finditer(r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)', f.read_text()):
                routes.append({"path": m.group(2), "methods": [m.group(1).upper()],
                               "source": f"static:{f.name}"})
        return routes


def worker_modules() -> list[dict]:
    out = []
    for f in sorted((ROOT / "workers" / "workers").glob("*worker*.py")):
        out.append({"module": f"workers.{f.stem}", "path": str(f.relative_to(ROOT))})
    return out


def durable_tables(conn) -> list[dict]:
    """Every BASE TABLE, with row count and last-activity where a timestamp column
    exists. VIEWS are excluded (PRODUCTION-CONFORMANCE-AUDIT-V1 follow-up, 2026-09-12):
    `information_schema.tables` returns both, unfiltered, so a VIEW with no static
    reader — which holds no storage of its own, e.g. `entity_knowledge_refusals` over
    the live `entity_admission_decisions` table — was being classified RETIRE_CANDIDATE
    as if dropping it would reclaim durable state. It would reclaim nothing; the
    underlying table is the actual state, and it is audited on its own row in this
    same list."""
    rows = conn.execute("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""").fetchall()
    out = []
    for (t,) in rows:
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception:
            n = None
        ts_col = conn.execute("""
            SELECT column_name FROM information_schema.columns
             WHERE table_name=%s AND column_name IN ('updated_at','created_at')
             ORDER BY CASE column_name WHEN 'updated_at' THEN 0 ELSE 1 END LIMIT 1""",
            (t,)).fetchone()
        last = None
        if ts_col and n:
            try:
                last = conn.execute(f'SELECT MAX("{ts_col[0]}") FROM "{t}"').fetchone()[0]
            except Exception:
                last = None
        out.append({"table": t, "rows": n, "last_activity": str(last) if last else None})
    return out


def qdrant_collections() -> list[dict]:
    import urllib.request
    url = os.environ.get("POLYMATH_QDRANT_URL", "http://127.0.0.1:6334")
    try:
        with urllib.request.urlopen(f"{url}/collections", timeout=8) as r:
            names = [c["name"] for c in json.load(r)["result"]["collections"]]
        out = []
        for n in names:
            try:
                with urllib.request.urlopen(f"{url}/collections/{n}", timeout=8) as r2:
                    out.append({"collection": n,
                                "points": json.load(r2)["result"].get("points_count")})
            except Exception:
                out.append({"collection": n, "points": None})
        return out
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{type(exc).__name__}: {exc}"}]


def neo4j_summary() -> dict:
    try:
        from polymath_shared.stores import neo4j_driver
        d = neo4j_driver()
        with d.session() as s:
            out = {
                "entities": s.run("MATCH (e:Entity) RETURN count(e) AS n").single()["n"],
                "relationships": s.run("MATCH ()-[r:REL]->() RETURN count(r) AS n").single()["n"],
                "labels": sorted(s.run("CALL db.labels() YIELD label RETURN label").value()),
            }
        d.close()
        return out
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# ── legacy scan (§11) ────────────────────────────────────────────────────────

#: Names to SEARCH for, not names assumed dead. Discovery decides; this list only says
#: "these are worth looking at because a replacement is known to exist".
LEGACY_PROBES = ("parent_enrichment", "parent_summaries", "summary_jobs",
                 "retrieval_summaries", "document_summaries", "hybrid-retrieval-v1",
                 "retrieval:v1", "query_ready")


def legacy_scan(probes: tuple[str, ...] = LEGACY_PROBES) -> list[dict]:
    """Static reader/writer census for each probe. `rg` over tracked files only."""
    out = []
    for probe in probes:
        try:
            res = subprocess.run(
                ["git", "grep", "-n", "--", probe],
                cwd=ROOT, capture_output=True, text=True, timeout=60)
            hits = [l for l in res.stdout.splitlines() if l.strip()]
        except Exception:
            hits = []
        files: dict[str, int] = {}
        for h in hits:
            f = h.split(":", 1)[0]
            files[f] = files.get(f, 0) + 1
        code = {f: n for f, n in files.items()
                if f.endswith((".py", ".ts", ".tsx", ".sql")) and not f.startswith("tests/")}
        out.append({
            "probe": probe,
            "total_hits": len(hits),
            "files": len(files),
            "code_files": sorted(code),
            "test_only": not code and bool(files),
            "docs_only": all(f.startswith("docs/") for f in files) if files else False,
        })
    return out


def snapshot(conn=None) -> dict:
    lanes = configured_lanes()
    snap: dict[str, Any] = {
        "lanes": [asdict(l) for l in lanes],
        "functions": configured_functions(lanes),
        "routes": api_routes(),
        "workers_on_disk": worker_modules(),
        "processes": running_processes(),
        "supervisor": supervisor_state(),
        "qdrant": qdrant_collections(),
        "neo4j": neo4j_summary(),
        "legacy_scan": legacy_scan(),
    }
    if conn is not None:
        snap["live_workers"] = live_workers(conn)
        snap["tables"] = durable_tables(conn)
    return snap
