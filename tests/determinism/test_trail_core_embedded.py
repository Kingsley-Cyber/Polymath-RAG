"""Consolidation migration Phase 6 — Polymath's UNCHANGED `TrailMCPClient` reaches the embedded TrailSignal core through an in-process
transport exactly as it reaches the daemon: same request envelope, same result envelope, same refusal path, idempotent replay, and an
audit store that survives a restart. No daemon, no Postgres, no Temporal, no network.

Needs TrailSignal's one extra dependency (`packageurl`, pulled by its platform contracts). Until it is added to this repo's environment in the
merge window, run this file with TrailSignal's interpreter:  ~/trail-signal-os-worktrees/A41/.venv/bin/python -m pytest <this file>
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

import pytest

pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need `packageurl`; add it in the merge window (ADR-TRAIL-EMBEDDING) or run with TrailSignal's interpreter")

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "governance" / "trail"):
    sys.path.insert(0, str(_p))

from polymath_shared.adapter import trail_client as TC  # noqa: E402
import embedded as E  # noqa: E402

RUN = "adr_" + "c" * 32
HID = "hyp_" + hashlib.sha256(b"embedded").hexdigest()[:24]
HYPS = [{"hypothesis_id": HID, "revision": 0, "status": "proposed", "statement": "runners lose access to small items mid-stride because pockets bounce"}]


def _client(service=None) -> TC.TrailMCPClient:
    return TC.TrailMCPClient("http://trail.embedded/mcp", "in-process", transport=E.transport(service))


def _request(kind: str, payload: dict, seq: int, snapshot_id: str | None):
    return TC.bounded_request(kind, payload, key=TC.identifier(RUN, kind.replace(".", "-"), str(seq)), run_ref=RUN, registry_snapshot_id=snapshot_id)


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(TC.__file__).resolve().is_relative_to(ROOT) and pathlib.Path(E.__file__).resolve().is_relative_to(ROOT)
    import trail_signal.contexts.workflow.application.research_operations as ro
    assert pathlib.Path(ro.__file__).resolve().is_relative_to(ROOT / "governance" / "trail")          # the EMBEDDED copy, not TrailSignal's own checkout


def test_the_unchanged_client_gets_a_real_registry_projection_and_an_idempotent_replay():
    client = _client()
    first = client.operate("registry.project", _request("registry.project", {"hypotheses": HYPS}, 1, None))
    assert first["operation_kind"] == "registry.project" and first["status_revision"] == 1 and first["registry_snapshot"]["snapshot_id"].startswith("trs-")
    assert first["result"]["priors"] and all(HID in p["hypothesis_ids"] for p in first["result"]["priors"])       # TrailSignal's real registry, compiled from the embedded data
    assert client.operate("registry.project", _request("registry.project", {"hypotheses": HYPS}, 1, None)) == first


def test_a_refusal_reaches_the_caller_as_the_same_typed_tool_error_the_daemon_gives():
    client = _client()
    with pytest.raises(TC.TrailToolError):                                                              # every operation after the first names the snapshot it was planned against
        client.operate("gaps.compile", _request("gaps.compile", {"hypotheses": HYPS, "stage": "field_evidence", "knowledge_gaps": []}, 2, "trs-not-the-snapshot"))
    with pytest.raises(TC.TrailToolError):
        client.operate("registry.project", {**_request("registry.project", {"hypotheses": HYPS}, 3, None), "operation_kind": "opportunity.score"})


def test_the_audit_store_survives_a_restart(tmp_path):
    path = tmp_path / "trail_audit.sqlite3"
    first = _client(E.build_service(store=E.SqliteResearchStore(path))).operate("registry.project", _request("registry.project", {"hypotheses": HYPS}, 1, None))
    restarted = E.build_service(store=E.SqliteResearchStore(path))                                      # a new process: nothing in memory
    assert _client(restarted).operate("registry.project", _request("registry.project", {"hypotheses": HYPS}, 1, None)) == first      # replayed from the store, not recomputed
    rows = E.SqliteResearchStore(path)._db.execute("SELECT operation_kind, run_ref FROM research_operations").fetchall()
    assert len(rows) == 1 and rows[0][0] == "registry.project"                                          # first commit wins: one audit operation, one immutable result
