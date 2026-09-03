"""LIVE BUILD FENCE — prove the running fleet is the current code.

A prior acceptance run reported "verified live" for hours while
`launchctl kickstart` silently no-oped and every worker still ran code
from the previous day. No measurement taken that way means anything, so
liveness of the BUILD is now proven before any acceptance claim.

Two deterministic mechanisms, no trust required:

  workers   `worker_registrations.build_sha` is captured from `git
            rev-parse --short HEAD` at process start, so a worker whose
            row carries the current HEAD necessarily started after that
            commit. A recent heartbeat proves the row is that process.

  services  a process whose START TIME is later than the last
            modification of the source file it runs must have loaded
            that source. Sidecars expose no build id, so this is the
            strongest available proof.

Exit code 0 only when every component passes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

#: (slot, listening port, source file that must predate the process)
SERVICES = [
    ("sidecar_gliner", 8740, "sidecars/gliner_runtime/server.py"),
    ("sidecar_embedder", 8742, "sidecars/embedder/server.py"),
    ("sidecar_spacy", 8744, "sidecars/spacy_runtime/server.py"),
    ("orchestrator", 7200, "orchestrator/orchestrator/main.py"),
]

#: reranker is a separately-owned runtime; identity is reported, not enforced.
ADVISORY = [("sidecar_reranker", 8743, None)]


def head_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=str(ROOT))
    return out.stdout.strip()


def _pid_on_port(port: int) -> int | None:
    out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                         capture_output=True, text=True)
    pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    return pids[0] if pids else None


def _proc_start_epoch(pid: int) -> float | None:
    """Process start time, in epoch seconds."""
    out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                         capture_output=True, text=True)
    stamp = out.stdout.strip()
    if not stamp:
        return None
    for fmt in ("%a %b %d %H:%M:%S %Y", "%a %b  %d %H:%M:%S %Y"):
        try:
            return time.mktime(time.strptime(stamp, fmt))
        except ValueError:
            continue
    return None


def in_scope() -> set[str] | None:
    """Slots this run is supposed to be running.

    A capped run (POLYMATH_FLEET_ONLY) deliberately omits slots, and an
    absent slot is not stale code. Scoping keeps the fence honest in both
    directions: it still fails on a RUNNING component that is not the
    current build, and it no longer fails on a component nobody started.
    """
    only = os.environ.get("POLYMATH_FLEET_ONLY", "").strip()
    if not only:
        return None
    return {n.strip() for n in only.split(",") if n.strip()}


#: supervisor slot name -> the identity this checker reports it under
_SLOT_TO_WORKER = {
    "qdrant": "project_qdrant", "neo4j": "project_neo4j",
    "canonicalize": "canonicalize", "intake": "intake",
    "profile": "profile_document", "extract": "extract",
    "summaries": "summaries",
    "project_canonical": "project_canonical", "verify": "verify_projections",
}


def check_workers(sha: str, max_heartbeat_age_s: int = 180) -> list[dict]:
    out = []
    with psycopg.connect(DSN, connect_timeout=10) as conn:
        rows = conn.execute(
            """SELECT worker_type, worker_id, pid, build_sha, status,
                      execution_bundle_hash,
                      EXTRACT(EPOCH FROM (now() - heartbeat_at)) AS age
                 FROM worker_registrations
                ORDER BY worker_type, heartbeat_at DESC""").fetchall()
    seen = set()
    for wtype, wid, pid, build, status, bundle, age in rows:
        fresh = age is not None and age <= max_heartbeat_age_s
        if not fresh:
            # REGISTRATION-RETENTION-V1: a registration past the heartbeat
            # window is a dead process (every spawn registers a new
            # worker_id; the supervisor prunes rows after 24 h). Dead rows
            # are not workers — only a LIVE worker on the wrong build fails
            # the fence. Measured 2026-09-03: 3,145 dead rows beside 1 live.
            continue
        if wtype in seen:
            continue          # newest live registration per type
        seen.add(wtype)
        ok = bool(build == sha)
        why = "" if build == sha else f"build {build} != HEAD {sha}"
        out.append({
            "component": wtype, "kind": "worker", "pid": pid,
            "build_sha": build, "expected": sha,
            "execution_bundle_hash": bundle or "",
            "status": status,
            "heartbeat_age_s": round(age, 1) if age is not None else None,
            "ok": ok, "why": why,
        })
    return out


def check_execution_bundles(components: list[dict]) -> dict:
    """EXECUTION-BUNDLE-FENCE-V1: every healthy in-scope worker must carry
    the SAME execution_bundle_hash; a freshly computed bundle under the
    FLEET'S RECORDED CONFIG (execution_bundles.config) must match it.
    Config comes from the DB, not this shell, so a fence run outside the
    boot environment cannot produce a false stale-memory alarm while
    genuine on-disk drift still fails loudly."""
    import json as _json

    from polymath_shared.execution_bundle import compute_execution_bundle

    with psycopg.connect(DSN, connect_timeout=10) as conn:
        cfg_rows = conn.execute(
            "SELECT config FROM execution_bundles ORDER BY last_seen_at DESC "
            "LIMIT 1").fetchall()
    fresh_env = dict(cfg_rows[0][0]) if cfg_rows else {}
    saved = {k: os.environ.get(k) for k in fresh_env}
    try:
        os.environ.update({k: str(v) for k, v in fresh_env.items() if v})
        fresh = compute_execution_bundle()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    hashes = sorted({c["execution_bundle_hash"] for c in components
                     if c.get("execution_bundle_hash")})
    uniform = len(hashes) <= 1
    matches_disk = bool(hashes) and hashes[0] == fresh["execution_bundle_hash"]
    clean = fresh["tree_dirty"] != "True"
    ok = bool(hashes) and uniform and matches_disk and clean
    why = []
    if not hashes:
        why.append("no worker reported an execution bundle")
    if not uniform:
        why.append(f"fleet split across bundles {hashes}")
    if hashes and not matches_disk:
        why.append(f"recorded {hashes[0][:12]} != fresh "
                   f"{fresh['execution_bundle_hash'][:12]} (stale memory)")
    if not clean:
        why.append("working tree dirty at fence time")
    return {
        "component": "execution_bundle", "kind": "bundle",
        "ok": ok, "why": "; ".join(why),
        "fresh_hash": fresh["execution_bundle_hash"],
        "worker_hashes": hashes,
        "uniform": uniform, "matches_disk": matches_disk,
        "tree_clean": clean,
    }


def check_services(advisory: bool = False) -> list[dict]:
    out = []
    for name, port, source in (ADVISORY if advisory else SERVICES):
        pid = _pid_on_port(port)
        entry = {"component": name, "kind": "service", "port": port, "pid": pid,
                 "advisory": advisory}
        if pid is None:
            entry.update(ok=False, why="nothing listening")
            out.append(entry)
            continue
        started = _proc_start_epoch(pid)
        entry["started_at"] = (time.strftime("%Y-%m-%d %H:%M:%S",
                                             time.localtime(started))
                               if started else None)
        if source is None:
            entry.update(ok=True, why="advisory only")
            out.append(entry)
            continue
        src = ROOT / source
        mtime = src.stat().st_mtime
        entry["source"] = source
        entry["source_mtime"] = time.strftime("%Y-%m-%d %H:%M:%S",
                                              time.localtime(mtime))
        if started is None:
            entry.update(ok=False, why="could not read process start time")
        elif started < mtime:
            entry.update(ok=False,
                         why="process predates its source: STALE CODE")
        else:
            entry.update(ok=True, why="")
        out.append(entry)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    sha = head_sha()
    from polymath_shared.execution import semantic_authority_sha256

    components = check_workers(sha) + check_services() + check_services(True)
    scope = in_scope()
    if scope is not None:
        allowed = {_SLOT_TO_WORKER.get(n, n) for n in scope} | scope
        for c in components:
            if c["component"] not in allowed:
                c["out_of_scope"] = True
                c["why"] = "not started by this capped run"
    enforced = [c for c in components
                if not c.get("advisory") and not c.get("out_of_scope")]
    worker_components = [c for c in components if c.get("kind") == "worker"
                         and not c.get("out_of_scope")]
    bundle_check = check_execution_bundles(worker_components) \
        if worker_components else None
    all_enforced = enforced + ([bundle_check] if bundle_check else [])
    report = {
        "head_sha": sha,
        "semantic_authority_sha256": semantic_authority_sha256()[:16],
        "scope": sorted(scope) if scope else "full fleet",
        "components": components,
        "execution_bundle": bundle_check,
        "enforced": len(all_enforced),
        "passing": sum(1 for c in all_enforced if c["ok"]),
        "verdict": "PASS" if all(c["ok"] for c in all_enforced) else "FAIL",
    }
    if a.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"LIVE BUILD FENCE  HEAD={sha}  "
              f"authority={report['semantic_authority_sha256']}")
        for c in components:
            if c.get("out_of_scope"):
                continue
            mark = "ok  " if c["ok"] else "STALE"
            tag = " (advisory)" if c.get("advisory") else ""
            extra = c.get("build_sha") or c.get("started_at") or ""
            print(f"  [{mark}] {c['component']:22s} pid={str(c.get('pid')):>7} "
                  f"{extra}{tag} {c.get('why','')}")
        if bundle_check:
            mark = "ok  " if bundle_check["ok"] else "FAIL"
            print(f"  [{mark}] execution_bundle        "
                  f"fresh={bundle_check['fresh_hash'][:12]} "
                  f"{bundle_check['why']}")
        print(f"  => {report['verdict']} "
              f"({report['passing']}/{report['enforced']} enforced components)")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
