"""CONTROL-PLANE-V2 execution identity (ADR-0014).

Workers advertise WHO they are (build SHA + contract versions); runs
pin WHAT they require (the execution contract). Leasing checks the
two against each other — an incompatible or stale worker is refused
and marked, never mysteriously served.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
import uuid
from typing import Any

from psycopg import Connection

STALE_AFTER_S = 90.0  # ~3 control ticks + margin


def _build_sha() -> str:
    sha = os.environ.get("POLYMATH_BUILD_SHA", "").strip()
    if sha:
        return sha
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(repo_root),
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def worker_contracts() -> dict[str, Any]:
    """The contract surface a worker runs with, resolved from settings —
    the same identity inputs the extraction contract hash uses."""
    from polymath_shared.query_policy import active_policy_version
    from polymath_shared.settings import get_settings

    s = get_settings()
    return {
        "query_policy": active_policy_version(),
        "rule_pack": s.worker.rule_pack_version,
        "syntax_provider": s.sidecars.syntax_provider,
        "rescue_stages": sorted(s.rescue_policy.enabled_stages()),
        "gliner_url": s.sidecars.gliner_url,
        "chunker": s.worker.chunker,
    }


def worker_identity(worker_type: str) -> dict[str, Any]:
    return {
        "worker_id": f"{worker_type}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
        "worker_type": worker_type,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "build_sha": _build_sha(),
        "contracts": worker_contracts(),
        "started_at": time.time(),
    }


def register_worker(conn: Connection, identity: dict[str, Any]) -> None:
    import json

    conn.execute(
        """
        INSERT INTO worker_registrations
            (worker_id, worker_type, pid, host, build_sha, contracts, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'healthy')
        ON CONFLICT (worker_id) DO UPDATE SET
            pid = EXCLUDED.pid, host = EXCLUDED.host,
            build_sha = EXCLUDED.build_sha, contracts = EXCLUDED.contracts,
            status = 'healthy', started_at = now(), heartbeat_at = now()
        """,
        (identity["worker_id"], identity["worker_type"], identity["pid"],
         identity["host"], identity["build_sha"],
         json.dumps(identity["contracts"])),
    )


def heartbeat(conn: Connection, worker_id: str, *,
              current_ticket: str | None = None,
              processed_count: int | None = None,
              last_error: str | None = None) -> None:
    """Touch the registration; revive from stale on activity."""
    conn.execute(
        """
        UPDATE worker_registrations SET
            heartbeat_at = now(),
            status = CASE WHEN status = 'stale' THEN 'healthy' ELSE status END,
            current_ticket = COALESCE(%s, current_ticket),
            processed_count = COALESCE(%s, processed_count),
            last_error = %s
        WHERE worker_id = %s
        """,
        (current_ticket, processed_count, last_error, worker_id),
    )


def compatible(worker_contracts: dict[str, Any],
              execution_contract: dict[str, Any]) -> bool:
    """Lease rule: the worker must run the build the run pinned (when
    the run pinned one) and the same semantic-policy surface. URL-level
    identity (which sidecar instance) must match exactly; semantic
    versions must match; unspecified run requirements pass."""
    required_build = execution_contract.get("worker_build")
    if required_build and worker_contracts.get("build_sha") != required_build:
        return False
    for key in ("query_policy", "rule_pack", "syntax_provider", "chunker"):
        want = execution_contract.get(key)
        if want is not None and worker_contracts.get(key) != want:
            return False
    want_rescue = execution_contract.get("rescue_stages")
    if want_rescue is not None and sorted(want_rescue) != sorted(worker_contracts.get("rescue_stages", [])):
        return False
    return True


def default_execution_contract() -> dict[str, Any]:
    """What a run pins when the submitter doesn't say: the fleet's
    CURRENT configuration — captured at ticket creation by the control
    plane, not by the worker."""
    return dict(worker_contracts())
