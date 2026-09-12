"""The seam-coverage gate must FAIL on the bug it was written for (2026-09-12).

A gate that only ever passes is decoration. The real bug was: `LLMExtractionClient`
grew provider-dispatch seams over time, `record(Attempt(...))` was added to ONE of them,
and nothing noticed the other three for months — 209 ledger rows covering 3 of 13 lanes,
all untagged, while the authority's §15 example is a batched pMAP failover.

So these tests feed the gate a doctored client module and require it to say FAIL and to
NAME the seam that dispatches without recording. The passing case is checked too, so the
gate cannot be satisfied by simply always failing.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_UNCOVERED = '''
import httpx


class LLMExtractionClient:
    def _chat(self, p):
        return httpx.post(self.base_url, json={"p": p})

    def complete_one(self, p):
        from polymath_shared.conformance.attempts import Attempt, record as _rec
        _rec(Attempt(lane="l", limiter_admitted=True, http_dispatched=True, success=True))
        return self._chat(p)

    def extract_batched(self, items):
        """A NEW seam that forgot the ledger — exactly the shipped bug."""
        return httpx.post(self.base_url + "/infer_batch", json={"items": items})
'''

_COVERED = _UNCOVERED.replace(
    '        return httpx.post(self.base_url + "/infer_batch", json={"items": items})',
    '        from polymath_shared.conformance.attempts import Attempt, record as _rec\n'
    '        _rec(Attempt(lane="l", limiter_admitted=True, http_dispatched=True, success=True))\n'
    '        return httpx.post(self.base_url + "/infer_batch", json={"items": items})')


@pytest.fixture()
def verifier():
    """Load the verifier as a module; each test gets a clean results list."""
    spec = importlib.util.spec_from_file_location(
        "vfs_under_test", ROOT / "scripts" / "verify_final_state.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["vfs_under_test"] = m
    spec.loader.exec_module(m)
    m.results.clear()
    return m


def _point_at(verifier, tmp_path: Path, source: str, monkeypatch) -> None:
    client = tmp_path / "shared" / "polymath_shared" / "llm_extraction" / "client.py"
    client.parent.mkdir(parents=True)
    client.write_text(source)
    monkeypatch.setattr(verifier, "ROOT", tmp_path)


def _seam_gate(verifier) -> dict:
    return next(r for r in verifier.results
                if r["gate"] == "attempt_ledger_covers_every_provider_seam")


def test_a_seam_that_dispatches_without_recording_FAILS_the_gate(
        verifier, tmp_path, monkeypatch):
    _point_at(verifier, tmp_path, _UNCOVERED, monkeypatch)
    verifier.check_attempt_telemetry(None)
    g = _seam_gate(verifier)
    assert g["status"] == verifier.FAIL
    assert "extract_batched" in g["detail"], "the gate must NAME the uncovered seam"
    assert "UNACCOUNTED_ATTEMPT" in g["detail"], "§15's own term for this condition"


def test_the_same_module_PASSES_once_that_seam_records(verifier, tmp_path, monkeypatch):
    _point_at(verifier, tmp_path, _COVERED, monkeypatch)
    verifier.check_attempt_telemetry(None)
    assert _seam_gate(verifier)["status"] == verifier.PASS


def test_the_transport_helper_is_excluded_but_named(verifier, tmp_path, monkeypatch):
    """`_chat` dispatches yet must not record — its callers do, and recording in both
    would double-count every attempt. The exclusion is legitimate, so the requirement is
    that it stays VISIBLE: a silent skip list is how the first three seams went unnoticed."""
    _point_at(verifier, tmp_path, _COVERED, monkeypatch)
    verifier.check_attempt_telemetry(None)
    detail = _seam_gate(verifier)["detail"]
    assert "_chat" in detail and "double-count" in detail


def test_the_live_client_is_what_the_gate_reads(verifier):
    """Guards against the gate quietly pointing at a path that no longer exists: a
    missing file must report NOT_TESTED, never a vacuous PASS."""
    import ast
    src = (ROOT / "shared" / "polymath_shared" / "llm_extraction" / "client.py")
    assert src.exists(), "the gate's target moved; the gate would go blind"
    ast.parse(src.read_text())
