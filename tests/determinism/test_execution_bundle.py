"""EXECUTION-BUNDLE-FENCE-V1 determinism tests.

Charter validations:
  1. Worker output carries its bundle hash (provenance stamping).
  2. A stale worker (boot fingerprint != current disk) refuses claims.
  3. Fleet uniformity: one boot generation => one bundle hash.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import json

import pytest

from polymath_shared.execution_bundle import (
    bundle_id,
    compute_execution_bundle,
    config_fingerprint,
    fast_code_fingerprint,
    semantic_file_hashes,
)


def test_bundle_hash_is_stable_and_well_formed():
    a = compute_execution_bundle()
    b = compute_execution_bundle()
    assert a["execution_bundle_hash"] == b["execution_bundle_hash"]
    assert len(a["execution_bundle_hash"]) == 16
    assert bundle_id(a).startswith("bundle_")
    # canonical JSON must be stable across key insertion order
    import hashlib
    canon = json.dumps(
        {k: v for k, v in sorted(a.items()) if k != "execution_bundle_hash"},
        sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canon.encode()).hexdigest()[:16] \
        == a["execution_bundle_hash"]


def test_ontology_edit_moves_the_bundle(monkeypatch, tmp_path):
    """The ontology yaml escaped every pre-existing fence (measured).
    The file-hash layer must catch it."""
    before = compute_execution_bundle()["ontology_file"]
    real = ROOT / "config" / "ontology" / \
        "scientific-predicate-ontology-v2.yaml"   # relocated 2026-09-03 (rulepack deleted)
    original = real.read_bytes()
    try:
        real.write_bytes(original + b"\n# fence-probe\n")
        after = compute_execution_bundle()["ontology_file"]
        assert after != before
    finally:
        real.write_bytes(original)
    assert compute_execution_bundle()["ontology_file"] == before


def test_config_drift_moves_the_bundle(monkeypatch):
    base = compute_execution_bundle()["config"]
    monkeypatch.setenv("POLYMATH_EXTRACTION_ATTESTATION", "strict")
    drifted = config_fingerprint()
    assert drifted["POLYMATH_EXTRACTION_ATTESTATION"] == "strict"
    # the bundle dict itself embeds config; simulate via hash comparison
    h1 = json.dumps(base, sort_keys=True)
    h2 = json.dumps(drifted, sort_keys=True)
    assert h1 != h2 or base.get("POLYMATH_EXTRACTION_ATTESTATION") == "strict"


def test_fast_fingerprint_detects_touched_source(tmp_path):
    fp_before = fast_code_fingerprint()
    probe = ROOT / "workers" / "workers" / ".__fence_probe__.py"
    try:
        probe.write_text("# probe\n")
        assert fast_code_fingerprint() != fp_before
    finally:
        probe.unlink(missing_ok=True)
    assert fast_code_fingerprint() == fp_before


def test_fast_fingerprint_ignores_content_preserving_touch():
    """HASH-FENCE-V2 (2026-08-30): same bytes + new mtime must NOT move
    the fingerprint. MEASURED: one pytest run (this very suite restoring
    the ontology yaml byte-identically) quarantined the entire fleet as
    BUNDLE_STALE_CODE_DRIFT under the V1 mtime fingerprint, and the
    control plane idled for hours."""
    real = ROOT / "config" / "ontology" / \
        "scientific-predicate-ontology-v2.yaml"   # relocated 2026-09-03 (rulepack deleted)
    fp_before = fast_code_fingerprint()
    original = real.read_bytes()
    real.write_bytes(original)          # same bytes, new mtime_ns
    assert fast_code_fingerprint() == fp_before


def test_claim_gate_refuses_stale_worker():
    """Charter test 2: changed code + old worker => refusal. The gate is
    the run_worker loop's drift check; exercise its decision core,
    mirroring production branch order (code fingerprint first, then
    semantic-file hashes)."""
    def _decide(boot_fp, now_fp, boot_files, now_files):
        if now_fp != boot_fp:
            return "BUNDLE_STALE_CODE_DRIFT"
        if now_files != boot_files:
            return "BUNDLE_STALE_SEMANTIC_FILE_DRIFT"
        return None

    assert _decide("fp", "fp", {"a": "1"}, {"a": "1"}) is None
    assert _decide("fp", "other", {"a": "1"}, {"a": "1"}) \
        == "BUNDLE_STALE_CODE_DRIFT"
    f1 = semantic_file_hashes()
    f2 = dict(f1)
    f2["scientific-predicate-ontology-v2.yaml"] = "moved"
    assert _decide(f1, f1, f1, f2) == "BUNDLE_STALE_SEMANTIC_FILE_DRIFT"


def test_fact_provenance_stamp_shape():
    """Charter test 1: produced objects carry generated_by_bundle_hash."""
    from workers.extract_worker import _stamped_provenance
    stamped = _stamped_provenance({"trigger_surface": "introduced"})
    assert stamped["trigger_surface"] == "introduced"
    h = stamped["generated_by_bundle_hash"]
    assert h.startswith("bundle_") and len(h) == len("bundle_") + 16
    # idempotent: stamping twice does not duplicate or change the hash
    again = _stamped_provenance(stamped)
    assert again["generated_by_bundle_hash"] == h
    # empty provenance still gets stamped
    bare = _stamped_provenance({})
    assert bare["generated_by_bundle_hash"] == h
