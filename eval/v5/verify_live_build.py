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


def check_workers(sha: str, max_heartbeat_age_s: int = 180) -> list[dict]:
    out = []
    with psycopg.connect(DSN, connect_timeout=10) as conn:
        rows = conn.execute(
            """SELECT worker_type, worker_id, pid, build_sha, status,
                      EXTRACT(EPOCH FROM (now() - heartbeat_at)) AS age
                 FROM worker_registrations
                ORDER BY worker_type, heartbeat_at DESC""").fetchall()
    seen = set()
    for wtype, wid, pid, build, status, age in rows:
        if wtype in seen:
            continue          # newest registration per type
        seen.add(wtype)
        fresh = age is not None and age <= max_heartbeat_age_s
        out.append({
            "component": wtype, "kind": "worker", "pid": pid,
            "build_sha": build, "expected": sha, "status": status,
            "heartbeat_age_s": round(age, 1) if age is not None else None,
            "ok": bool(build == sha and fresh),
            "why": ("" if build == sha else f"build {build} != HEAD {sha}")
                   or ("" if fresh else f"heartbeat {age:.0f}s old"),
        })
    return out


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
    enforced = [c for c in components if not c.get("advisory")]
    report = {
        "head_sha": sha,
        "semantic_authority_sha256": semantic_authority_sha256()[:16],
        "components": components,
        "enforced": len(enforced),
        "passing": sum(1 for c in enforced if c["ok"]),
        "verdict": "PASS" if all(c["ok"] for c in enforced) else "FAIL",
    }
    if a.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"LIVE BUILD FENCE  HEAD={sha}  "
              f"authority={report['semantic_authority_sha256']}")
        for c in components:
            mark = "ok  " if c["ok"] else "STALE"
            tag = " (advisory)" if c.get("advisory") else ""
            extra = c.get("build_sha") or c.get("started_at") or ""
            print(f"  [{mark}] {c['component']:22s} pid={str(c.get('pid')):>7} "
                  f"{extra}{tag} {c.get('why','')}")
        print(f"  => {report['verdict']} "
              f"({report['passing']}/{report['enforced']} enforced components)")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
