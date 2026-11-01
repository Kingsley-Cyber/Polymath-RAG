"""DOMAIN_OPERATION runner (ADR-0020): the ONE door to a domain's own code, shared by every caller that runs it.

A domain binding (`adapters/<domain>/binding.py`) runs OUT OF PROCESS — one JSON request on stdin, one JSON object on stdout — with a
MINIMAL environment (no DSN, no token, no key), so its module names never enter the caller and a crash is a typed failure, not a dead
process. The domain computes; it never reads or writes run state, the ledger or a store.

Callers (PRODUCT-SEARCH-E2E): the step worker (`exec_domain`, a DOMAIN_OPERATION step), `service.start` (an entry step's start-time
check, e.g. whether a seed can generate anything at all) and `service.submit` (the law that follows a reasoning step, run at submit so
the agent gets the verdict in the submit response — F2). The manifest NAMES the domain and the operation; this module never does.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from . import trail_client as TC
from .contracts import _REPO

DOMAINS_DIR = _REPO / "adapters"
DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
REQUEST_VERSION = "domain_operation_request.v1"
TIMEOUT_S = float(os.environ.get("POLYMATH_DOMAIN_OPERATION_TIMEOUT_S", "120"))
OUTPUT_MAX_BYTES = 1_000_000
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,60}$")
#: bug hunt B-69 (ADR-0020: the domain computes, it never decides): output keys the runtime reads as TrailSignal's — its result fields,
#: the admission it records, the φ verdicts it applies, its operation kind — or as its own (`_…`, `trail_…`, the transition ids). A
#: domain enriches Trail's `research_directive` with HOW (governance fields untouched) by design, so that one key stays allowed.
RESERVED_KEYS = (frozenset(TC.RESULT_FIELDS) - {"research_directive"}) | {"hypothesis_verdicts", "hypothesis_transition_ids",
                                                                          "operation_kind", "qualification"}


class DomainCrash(RuntimeError):
    """The binding crashed, timed out or answered something that is not one typed response: the caller records it as a step failure
    (STEP_EXECUTOR_ERROR) — or, for a check that only accelerates the normal path (a law at submit), falls back to that path."""


def _path(obj: Mapping[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in str(dotted).split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def request(*, domain: str, operation: str, run_id: str, step_id: str, run_input: Mapping[str, Any], scope: Mapping[str, Any],
            config: Mapping[str, Any]) -> dict[str, Any]:
    """The binding's request: the run input, the values the manifest step SELECTED (`config.inputs`: name -> dotted path over `scope`,
    or a list of paths) and the rest of the step config."""
    return {"schema_version": REQUEST_VERSION, "domain": domain, "operation": operation, "run_id": run_id, "step_id": step_id,
            "input": dict(run_input or {}),
            "inputs": {name: ([_path(scope, d) for d in sel] if isinstance(sel, list) else _path(scope, sel))
                       for name, sel in (config.get("inputs") or {}).items()},
            "config": {k: v for k, v in config.items() if k not in ("domain", "operation", "inputs")}}


def binding(domain: str, domains_dir: Path | None = None) -> Path | None:
    """`adapters/<domain>/binding.py`, or None when the name is not a domain name or no such binding exists under the domains dir."""
    if not DOMAIN_RE.match(str(domain or "")):
        return None
    root = Path(domains_dir or DOMAINS_DIR).resolve()
    path = (root / domain / "binding.py").resolve()
    return path if root in path.parents and path.is_file() else None


def run(domain: str, operation: str, req: Mapping[str, Any], *, domains_dir: Path | None = None,
        timeout_s: float | None = None) -> dict[str, Any]:
    """-> {"output": {...}} (the domain's output, plus `_domain` provenance) or {"gap": {code, message}} (a typed refusal, or a binding
    that does not exist). A crash, a timeout or a malformed response raises DomainCrash."""
    if not DOMAIN_RE.match(str(domain or "")):
        return {"gap": {"code": "DOMAIN_BINDING_INVALID", "message": f"{req.get('step_id')}: config.domain {domain!r} is not a domain name"}}
    path = binding(domain, domains_dir)
    if path is None:
        return {"gap": {"code": "DOMAIN_BINDING_MISSING", "message": f"{req.get('step_id')}: no binding for domain {domain!r}"}}
    env = {"PATH": os.environ.get("PATH", ""), "LANG": os.environ.get("LANG", "en_US.UTF-8"), "PYTHONDONTWRITEBYTECODE": "1"}
    limit = TIMEOUT_S if timeout_s is None else float(timeout_s)
    try:
        proc = subprocess.run([sys.executable, str(path)], input=json.dumps(dict(req)), capture_output=True, text=True,
                              timeout=limit, cwd=str(path.parent), env=env)
    except subprocess.TimeoutExpired as exc:
        raise DomainCrash(f"domain operation {operation} timed out after {limit:g}s") from exc
    if proc.returncode != 0:
        raise DomainCrash(f"domain operation {operation} exited {proc.returncode}: {proc.stderr.strip()[-600:]}")
    if len(proc.stdout.encode()) > OUTPUT_MAX_BYTES:
        raise DomainCrash(f"domain operation {operation} returned more than {OUTPUT_MAX_BYTES} bytes")
    try:
        resp = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise DomainCrash(f"domain operation {operation} did not return one JSON object: {exc}") from exc
    if not isinstance(resp, dict) or not isinstance(resp.get("ok"), bool):
        raise DomainCrash(f"domain operation {operation} returned no boolean `ok`")
    if not resp["ok"]:
        code, message = str(resp.get("code") or ""), str(resp.get("message") or "")
        if not _CODE.match(code):
            raise DomainCrash(f"domain operation {operation} refused without a typed code: {code!r}")
        return {"gap": {"code": code, "message": f"{operation}: {message}"[:2000]}}
    if not isinstance(resp.get("output"), dict):
        raise DomainCrash(f"domain operation {operation} returned ok without an output object")
    output = dict(resp["output"])
    reserved = sorted(k for k in output if k.startswith(("_", "trail_")) or k in RESERVED_KEYS)
    if reserved:
        raise DomainCrash(f"domain operation {operation} wrote keys only TrailSignal or the runtime may write: {', '.join(reserved[:10])}")
    output["_domain"] = {"domain": domain, "operation": operation, "binding_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"output": output}
