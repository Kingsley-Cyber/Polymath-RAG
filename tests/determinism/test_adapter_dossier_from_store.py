"""TRAIL-INTERFACE-V1 T5 — the journal the server rebuilds from a run's stored rows is the journal a host keeps beside the run.

One complete scripted ecommerce.product_research run (stub TrailSignal, in-memory store), journaled by the host exactly as
`governed_run.py` documents (test_adapter_ecommerce_dossier._journaled_run); the same run read back through run_view.dossier_journal.
Same steps, same readable evidence, same accepted submissions and status answers, the same result plus the gates of every qualify step
— and the engine draws the same dossier from both. No database, no network."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", pathlib.Path(__file__).resolve().parent):
    sys.path.insert(0, str(_p))

import test_adapter_ecommerce_dossier as DOSSIER
import test_adapter_ecommerce_product_research_e2e as SCRIPT
from polymath_shared.adapter import dossier, run_view

runtime = DOSSIER.runtime                                   # the same in-memory store + stub TrailSignal fixture


def _events(journal: dict, kind: str) -> list[dict]:
    return [e["data"] for e in journal["events"] if e["kind"] == kind]


def test_the_code_under_test_is_this_checkout():
    for mod in (dossier, run_view):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


def test_the_journal_rebuilt_from_the_store_is_the_one_the_host_kept(runtime, monkeypatch, tmp_path):
    monkeypatch.setattr(run_view, "store", runtime)          # the view reads the same in-memory rows the service wrote
    host = DOSSIER._journaled_run(SCRIPT.Agent())
    ours = run_view.dossier_journal(None, host["run_id"])

    assert {k: ours[k] for k in ("journal_version", "skill_version", "run_id", "adapter_id", "input", "corpus_ids", "agent_identity")} == \
           {k: host[k] for k in ("journal_version", "skill_version", "run_id", "adapter_id", "input", "corpus_ids", "agent_identity")}
    # every step the agent answered, with the readable evidence adapter_next showed beside it
    assert [(s["step"], s["status"], s["evidence"]) for s in _events(ours, "step")] == \
           [(s["step"], s["status"], s["evidence"]) for s in _events(host, "step")]
    assert sum(1 for s in _events(ours, "step") if s["evidence"]["rows"]) > 0
    # every accepted submission, with adapter_submit's status answer
    keys = ("step_id", "kind", "payload", "payload_hash", "accepted", "response")
    assert [tuple(s[k] for k in keys) for s in _events(ours, "submission")] == [tuple(s[k] for k in keys) for s in _events(host, "submission")]

    # the result: the one the host received, plus the gates of every qualify step (the compiled result keeps the newest step's only)
    theirs, mine = _events(host, "result")[0]["result"], _events(ours, "result")[0]["result"]
    assert {k: mine[k] for k in ("status", "gap", "contradictions", "unknowns")} == {k: theirs[k] for k in ("status", "gap", "contradictions", "unknowns")}
    assert {k: v for k, v in mine["output"].items() if k != "qualifications"} == {k: v for k, v in theirs["output"].items() if k != "qualifications"}
    stages = [q["stage"] for q in mine["output"]["qualifications"]]
    assert "market_delta" in stages and all(q in mine["output"]["qualifications"] for q in theirs["output"]["qualifications"])

    # the engine draws the same dossier from both
    (tmp_path / "host").mkdir()
    (tmp_path / "ours").mkdir()
    _, m_host = DOSSIER._dossier(host, tmp_path / "host")
    _, m_ours = DOSSIER._dossier(ours, tmp_path / "ours")
    assert m_ours["run"]["verdict"] == m_host["run"]["verdict"] == "GOVERNED — TRAIL SCORED"
    for key in ("leads", "product_concepts", "corpus_packets", "quotes", "held_rejected", "bridges"):
        assert m_ours[key] == m_host[key], key
    for key in ("trail_scores", "score_refusals", "admitted", "rejected", "hypotheses", "lived_clusters", "lived_situations", "transduction",
                "product_reality", "coordinates", "registry_snapshot", "agent_identity", "harness_ids", "hypothesis_state_from"):
        assert m_ours["governed"][key] == m_host["governed"][key], key
