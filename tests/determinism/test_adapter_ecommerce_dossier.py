"""Consolidation migration Phase 8 — the governed dossier is the ENGINE'S existing renderer (`adapters/ecommerce/python/report.py`) fed by
the engine's existing governed-run journal (`governed_run.py`); nothing new renders. The mapping now uses what `ecommerce.product_research`
really returns — typed product concepts with variations, the supplier join, per-concept coverage, the lived world — and every block says
who stands behind it: POLYMATH KNOWLEDGE · LIVE-WORLD OBSERVATION · AGENT INFERENCE · TRAIL DETERMINATION · TRAIL REGISTRY.

The journal is recorded from a complete scripted run (stub TrailSignal, in-memory store); the report is built OUT OF PROCESS through the
engine's own CLI, exactly as a host would. No database, no network.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", pathlib.Path(__file__).resolve().parent, ROOT / "adapters" / "ecommerce" / "python"):
    sys.path.insert(0, str(_p))

from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402
import governed_run as JOURNAL  # noqa: E402  (stdlib-only module of the engine: the journal a host keeps)
import test_adapter_ecommerce_product_research_e2e as SCRIPT  # noqa: E402

ENGINE = ROOT / "adapters" / "ecommerce"
LABELS = ("POLYMATH KNOWLEDGE", "LIVE-WORLD OBSERVATION", "AGENT INFERENCE", "TRAIL DETERMINATION", "TRAIL REGISTRY")


def _journaled_run(agent) -> dict:
    """The scripted run, with a host-side journal kept exactly as `governed_run.py` documents: every adapter_next payload, every
    submission with the adapter's answer, the final result."""
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": SCRIPT._knowledge, "POLYMATH_COMPILE_PLAN": SCRIPT._knowledge, "POLYMATH_GRAPH_EXPAND": SCRIPT._knowledge}
    inp = {"seed": SCRIPT.SEED, "corpus_ids": ["probe"]}
    ref = service.start(None, adapter_id=SCRIPT.ADAPTER_ID, input_payload=inp, request_options={"corpus_ids": ["probe"]})
    rid = ref["run_id"]
    journal = JOURNAL.new_journal(ref, inp, agent_identity="test-agent", harness_id="test-harness", at="2026-09-20T12:00:00Z")
    for _ in range(220):
        st = service.advance(None, rid, execs, max_steps=1)
        if st.terminal:
            break
        if st.status in ("awaiting_agent", "awaiting_harness"):
            nxt = service.next_step(None, rid)
            JOURNAL.record_next(journal, nxt, at="2026-09-20T12:00:01Z")
            step = nxt["step"]
            kind = "reasoning" if st.status == "awaiting_agent" else "receipt"
            payload = agent.answer(nxt) if kind == "reasoning" else SCRIPT._harness(step, rid)
            sub = {"step_id": step["step_id"], "payload": payload, "submitted_by": {"agent_identity": "test-agent" if kind == "reasoning" else "test-harness"}}
            response = service.submit(None, rid, {**sub, "kind": "receipt"} if kind == "receipt" else sub)
            JOURNAL.record_submission(journal, step["step_id"], kind, payload, response, at="2026-09-20T12:00:02Z")
    try:
        JOURNAL.record_result(journal, service.result(None, rid), at="2026-09-20T12:00:03Z")
    except Exception:  # noqa: BLE001 — a terminal gap has a status, not a result body; the journal then holds the last status only
        JOURNAL.record_next(journal, service.next_step(None, rid), at="2026-09-20T12:00:03Z")
    journal["built_at"] = "2026-09-20T12:00:04Z"
    return journal


def _dossier(journal: dict, tmp_path: pathlib.Path) -> tuple[str, dict]:
    jpath, out = tmp_path / "journal.json", tmp_path / "dossier.html"
    jpath.write_text(json.dumps(journal))
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "OPPORTUNITY_RESEARCH_DB": str(tmp_path / "loop.sqlite3")}
    proc = subprocess.run([sys.executable, "python/governed_run.py", "report", "--journal", str(jpath), "--out", str(out)], cwd=ENGINE, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
    model = subprocess.run([sys.executable, "-c", "import json,sys; sys.path.insert(0,'python'); import report; print(json.dumps(report.build_model_from_governed(json.load(open(sys.argv[1])))))", str(jpath)],
                           cwd=ENGINE, env=env, capture_output=True, text=True)
    assert model.returncode == 0, model.stderr[-800:]
    return out.read_text(), json.loads(model.stdout)


@pytest.fixture
def runtime(monkeypatch):
    store, trail = MemoryStore(), SCRIPT.StubTrail()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(trail.handle)))
    service.reset_registry()
    SCRIPT.NEEDS.clear()
    yield store
    service.reset_registry()


def test_the_dossier_shows_the_complete_product_structure_with_an_authority_label_on_every_block(runtime, tmp_path):
    html, model = _dossier(_journaled_run(SCRIPT.Agent()), tmp_path)
    assert all(label in html for label in LABELS), [l for l in LABELS if l not in html]
    # the engine's typed product set replaces the single concept the older mapping synthesized
    assert [c["id"] for c in model["product_concepts"]] == ["pc_1", "pc_2", "pc_3"] and all(len(c["variations"]) == 2 for c in model["product_concepts"])
    assert "stride magnetic belt clip" in html and "reflective" in html and "UNSOURCED" in html            # concepts, variations, and the honestly unsourced third concept
    assert [l["concept_id"] for l in model["leads"]] == ["pc_1", "pc_2"] and all(l["governed"] and "evidence_score" not in l for l in model["leads"])
    assert "$1.2 / unit" in html and "MOQ 500" in html and "Example Hardware Co" in html and "supplier not named on the listing" in html
    assert {c["concept_id"]: c["status"] for c in model["sourcing_coverage"]} == {"pc_1": "sourced", "pc_2": "sourced", "pc_3": "unsourced"}
    g = model["governed"]
    assert g["lived_clusters"][0]["authority"] == "ANCHOR" and g["lived_situations"][0]["authority"] == "FIELD_ANCHORED" and g["population_leads"]
    assert "Lived Situations" in html and "Lived Clusters" in html and "Populations Worth Looking At" in html
    assert g["trail_scores"][0]["record_id"] == "score-1" and len(g["score_refusals"]) == 2 and "HARD_GATE_UNMET" in html       # TrailSignal's record, verbatim
    assert model["run"]["verdict"] == "GOVERNED — TRAIL SCORED" and "trs_stub_e2e" in html                                      # and the registry snapshot it was decided against
    assert "evidence score" not in html                                                                                        # no domain score anywhere in a governed dossier


def test_a_refused_run_reads_as_a_refusal(runtime, tmp_path):
    html, model = _dossier(_journaled_run(SCRIPT.OneIdeaAgent()), tmp_path)
    assert model["run"]["status"] != "completed" or model["governed"]["gap"]
    assert "PRODUCT_PORTFOLIO_LAW_UNSATISFIED" in json.dumps(model) or "PRODUCT_PORTFOLIO_LAW_UNSATISFIED" in html
    assert model["leads"] == [] and not model["governed"]["trail_scores"]
