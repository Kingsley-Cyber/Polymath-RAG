"""EXECUTION-BUNDLE-FENCE-V1: identity of the exact code+configuration
that a worker process is executing.

A worker's build_sha == HEAD does not prove its in-memory code matches
the repository: files edited after process start leave build_sha stale
while behavior drifts (observed live during P0.7 parity). This module
gives every worker a computed-at-boot bundle plus a cheap per-tick
fingerprint so drift becomes loud refusal instead of silent divergence.

Deterministic: same repo state + same env => same bundle hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: Code surfaces whose on-disk drift invalidates a running worker's
#: self-description. Kept to the deterministic policy + stage layers;
#: sidecars and stores are pinned through their own contracts.
_FINGERPRINT_DIRS = (
    ROOT / "shared" / "polymath_shared",
    ROOT / "workers" / "workers",
    ROOT / "control" / "control",
)
_FINGERPRINT_SUFFIXES = {".py", ".yaml", ".yml"}

#: Environment variables that participate in extraction semantics. Any
#: change here must change the bundle hash (config drift detection).
_CONFIG_ENV_KEYS = (
    "POLYMATH_QUERY_POLICY",
    "POLYMATH_RESCUE",
    "POLYMATH_CHUNKER",
    "POLYMATH_WORKER_RULE_PACK_VERSION",
    "POLYMATH_RELATION_PIPELINE",
    "POLYMATH_PREDICATE_V2",
    "POLYMATH_SYNTAX_PROVIDER",
    "POLYMATH_ENTITY_ADMISSION_ENFORCE",
    "POLYMATH_FACT_ADMISSION_ENFORCE",
    "POLYMATH_EXTRACTION_CONTEXT",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_state() -> dict[str, str]:
    """HEAD sha + dirty flag over tracked files. 'unknown' degrades to a
    distinct hash rather than silently matching anything."""
    sha = os.environ.get("POLYMATH_BUILD_SHA", "").strip()
    dirty = False
    try:
        if not sha:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5, cwd=str(ROOT))
            sha = out.stdout.strip() if out.returncode == 0 else "unknown"
        st = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT))
        dirty = bool(st.stdout.strip()) if st.returncode == 0 else False
    except Exception:
        sha = sha or "unknown"
        dirty = True  # cannot prove cleanliness -> refuse to look clean
    return {"git_sha": sha or "unknown", "tree_dirty": str(bool(dirty))}


def semantic_file_hashes() -> dict[str, str]:
    """File-content hashes of the lexical/semantic authorities that are
    NOT python modules and therefore escape the semantic-authority code
    hash (measured: the ontology realization edit moved no existing
    fence until this field existed)."""
    base = ROOT / "shared" / "polymath_shared" / "rulepack"
    out: dict[str, str] = {}
    for name in ("core-predicates-v1.5.0.yaml",
                 "scientific-predicate-ontology-v2.yaml"):
        p = base / name
        out[name] = _sha256_file(p) if p.exists() else "missing"
    allow = ROOT / "resources" / "predicates" / "trigger_allowlist.yaml"
    out["trigger_allowlist"] = (_sha256_file(allow)
                                if allow.exists() else "missing")
    return out


def config_fingerprint() -> dict[str, str]:
    return {k: os.environ.get(k, "") for k in _CONFIG_ENV_KEYS}


#: HASH-FENCE-V2 content cache: rel -> (size, mtime_ns, sha256). A file
#: whose stat is unchanged reuses its hash; a touched file is re-read.
_CONTENT_HASH_CACHE: dict[str, tuple[int, int, str]] = {}


def fast_code_fingerprint() -> str:
    """Content-hash drift detector over the pinned code surfaces.

    HASH-FENCE-V2 (2026-08-30): V1 fingerprinted rel:size:mtime_ns, so a
    content-preserving rewrite tripped the fence — MEASURED: the
    determinism suite re-serializes the ontology yaml byte-identically,
    and one `pytest` run quarantined the entire fleet
    (BUNDLE_STALE_CODE_DRIFT) while the control plane idled for hours.
    Every other integrity authority in this repo is content-addressed
    (bundle hash, contracts, artifact ids); the fence now matches:
    same bytes => same fingerprint, regardless of touches. The per-file
    cache keyed on (size, mtime_ns) keeps the steady-state per-poll cost
    at one stat() per pinned file; only files whose stat changed are
    re-read and re-hashed."""
    h = hashlib.sha256()
    for d in _FINGERPRINT_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if p.suffix not in _FINGERPRINT_SUFFIXES or "__pycache__" in str(p):
                continue
            st = p.stat()
            rel = str(p.relative_to(ROOT))
            cached = _CONTENT_HASH_CACHE.get(rel)
            if cached and cached[0] == st.st_size and cached[1] == st.st_mtime_ns:
                sha = cached[2]
            else:
                try:
                    sha = _sha256_file(p)
                except OSError:
                    sha = "unreadable"  # distinct value: drift, loudly
                _CONTENT_HASH_CACHE[rel] = (st.st_size, st.st_mtime_ns, sha)
            h.update(f"{rel}:{sha}".encode())
    return h.hexdigest()[:16]


def compute_execution_bundle() -> dict[str, Any]:
    from polymath_shared.execution import (
        semantic_authority_sha256,
        worker_contracts,
    )

    files = semantic_file_hashes()
    bundle = {
        **git_state(),
        "semantic_authority": semantic_authority_sha256(),
        "rule_pack_file": files["core-predicates-v1.5.0.yaml"],
        "ontology_file": files["scientific-predicate-ontology-v2.yaml"],
        "trigger_allowlist": files["trigger_allowlist"],
        "config": config_fingerprint(),
        "contracts": worker_contracts(),
    }
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    bundle["execution_bundle_hash"] = hashlib.sha256(
        canonical.encode()).hexdigest()[:16]
    return bundle


def bundle_id(bundle: dict[str, Any]) -> str:
    return f"bundle_{bundle.get('execution_bundle_hash', 'unknown')}"
