"""Consolidation migration Phase 4 — EvidencePacket integration: the imported ecommerce engine's understanding logic consumes
CURRENT Polymath evidence (the adapter runtime's evidence-boundary rows, produced from an `evidence-packet-v1`) and yields valid
downstream structures — through the existing runtime, with no nested synthesis and no HTTP from domain code.

The knowledge executors are replaced by one that returns the AUTHORITATIVE contract example
(`contracts/evidence/v1/evidence_packet.example.json`) mapped by the runtime's own `evidence_boundary.rows_from_packet`, so the rows
have exactly the shape a live `B_retrieve` stores. No database (in-memory store), no network.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "adapter_domain_binding"
ADAPTER_ID = "fixture.knowledge_intake"
PACKET = json.loads((ROOT / "contracts" / "evidence" / "v1" / "evidence_packet.example.json").read_text())
CORPUS = "corpus_fixture"
ROWS = EB.rows_from_packet(PACKET, CORPUS)
SEED = "people carrying a load away from the body tire quickly"


def _knowledge(step, state, m):
    return {"output": {"surface": EB.SURFACE_BOUNDARY, "rows": ROWS, "evidence_contract": EB.PACKET_SCHEMA_VERSION}, "evidence_refs": EB.refs_from_rows(ROWS)}


def _graph(step, state, m):
    return {"output": {"surface": EB.SURFACE_BOUNDARY, "rows": ROWS[:1] + [{"id": "fact_1", "kind": "graph_fact", "corpus_id": CORPUS}]}, "evidence_refs": []}


EXECUTORS = {**W.EXECUTORS, "POLYMATH_RETRIEVE": _knowledge, "POLYMATH_GRAPH_EXPAND": _graph}


def _domain(operation: str, inputs: dict, step_id: str):
    """Run ONE operation through the real executor by giving the run state the outputs its manifest step selects."""
    m = M.load_manifest(FIXTURES / f"{ADAPTER_ID}.json")
    state = RunState(run_id="adr_" + "1" * 32, adapter_id=ADAPTER_ID, status="running", input={"seed": SEED, "corpus_ids": [CORPUS]}, outputs=inputs)
    assert m.step(step_id)["config"]["operation"] == operation
    return W.exec_domain({"run_id": state.run_id, "step_id": step_id, "sequence": 3, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def test_the_code_under_test_is_this_checkout():
    for mod in (EB, M, service, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


def test_governed_rows_become_engine_corpus_rows_with_one_id_space_and_nothing_lost():
    assert ROWS and all(r["kind"] == "chunk" for r in ROWS)
    out = _domain("knowledge.corpus_evidence", {"retrieve": {"rows": ROWS}, "graph": {"rows": ROWS[:1] + [{"id": "fact_1", "kind": "graph_fact", "corpus_id": CORPUS}]}}, "intake")["output"]
    rows = out["corpus_evidence"]
    assert [r["id"] for r in rows] == [r["id"] for r in ROWS]                     # the runtime's evidence ids, de-duplicated across lanes, no prefix
    assert out["row_count"] == len(ROWS) and out["skipped"] == 1 and out["corpora"] == [CORPUS]          # the text-less graph fact is counted, not dropped silently
    for src, row in zip(ROWS, rows):
        assert row["text"] == src["text"] and row["summary"] and row["corpus"] == CORPUS and row["doc_id"] == src.get("doc_id")
        assert row["utility_role"] == src.get("utility_role") and row["ca4_grade"] == src.get("ca4_grade") and row["c4_valid"] == src.get("c4_valid")
        assert row["origin"] == src.get("origin") and row["text_truncated"] == src.get("text_truncated") and row["text_chars"] == src.get("text_chars")
        assert "evidence_packet" in row["tags"] and "current_demand" in row["cannot_establish"]          # corpus knowledge never establishes demand
    assert out["_domain"]["operation"] == "knowledge.corpus_evidence"


def test_no_usable_knowledge_is_a_typed_gap():
    assert _domain("knowledge.corpus_evidence", {"retrieve": {"rows": []}, "graph": {}}, "intake")["gap"]["code"] == "KNOWLEDGE_ROWS_MISSING"
    only_facts = {"retrieve": {"rows": [{"id": "fact_1", "kind": "graph_fact", "corpus_id": CORPUS}]}, "graph": {"rows": []}}
    assert _domain("knowledge.corpus_evidence", only_facts, "intake")["gap"]["code"] == "KNOWLEDGE_ROWS_UNUSABLE"


def _engine_rows():
    return _domain("knowledge.corpus_evidence", {"retrieve": {"rows": ROWS}, "graph": {"rows": []}}, "intake")["output"]["corpus_evidence"]


def test_lens_selection_reads_the_seed_and_the_evidence_and_is_never_empty():
    out = _domain("understanding.lenses", {"intake": {"corpus_evidence": _engine_rows()}}, "lenses")["output"]
    assert out["lenses"] and all(set(l) == {"name", "question"} for l in out["lenses"])
    assert _domain("understanding.lenses", {"intake": {}}, "lenses")["gap"]["code"] == "CORPUS_EVIDENCE_MISSING"


def test_the_lineage_law_is_the_engines_own():
    ev = _engine_rows()
    rid = ev[0]["id"]
    run = lambda prim: _domain("understanding.validate_primitives", {"interpret": {"primitives": prim}, "intake": {"corpus_evidence": ev}}, "lineage")["output"]  # noqa: E731
    unclassified = run({"evidence_refs": {"physical_jobs": [rid]}})
    assert unclassified["valid"] is False and "UNCLASSIFIED" in unclassified["errors"][0]
    assert "does not exist in this run" in run({"evidence_refs": {"physical_jobs": ["chunk_never_retrieved"]}})["errors"][0]
    assert "dead for lineage" in run({"row_relevance": {rid: "IRRELEVANT"}, "evidence_refs": {"physical_jobs": [rid]}})["errors"][0]
    assert "not in" in run({"row_relevance": {rid: "DIRECT"}})["errors"][0]                                # a CA4 grade is not a relevance class
    ok = run({"row_relevance": {rid: "SEMANTIC_MATCH"}, "evidence_refs": {"physical_jobs": [rid]}})
    assert ok["valid"] is True and ok["errors"] == [] and ok["row_relevance"] == {rid: "SEMANTIC_MATCH"}


# ─────────────────────────────────────────────────────────── the gate: through service.advance
@pytest.fixture
def runtime(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    service.reset_registry()
    yield store
    service.reset_registry()


def test_engine_understanding_consumes_current_polymath_evidence_through_the_runtime(runtime):
    rid = service.start(None, adapter_id=ADAPTER_ID, input_payload={"seed": SEED, "corpus_ids": [CORPUS]}, directory=FIXTURES)["run_id"]
    cited = ROWS[0]["id"]
    drafts = iter([{"evidence_refs": {"physical_jobs": [cited]}},                                            # cites an unclassified row
                   {"row_relevance": {cited: "STRUCTURAL_ANALOGY"}, "evidence_refs": {"physical_jobs": [cited]}}])
    shown: list[list[str]] = []
    for _ in range(40):
        st = service.advance(None, rid, EXECUTORS, max_steps=1, directory=FIXTURES)
        if st.terminal:
            break
        if st.status == "awaiting_agent":
            step = service.next_step(None, rid, directory=FIXTURES)["step"]
            shown.append([r["id"] for r in step["context"]["evidence_refs"]])
            service.submit(None, rid, {"step_id": step["step_id"], "payload": {"primitives": next(drafts)}, "submitted_by": {"agent_identity": "test-agent"}}, directory=FIXTURES)
    assert st.status == "completed" and st.branch_loops == 1
    rows = runtime.list_steps(None, rid)
    assert [r["step_id"] for r in rows] == ["retrieve", "graph", "intake", "lenses", "interpret", "lineage", "route", "interpret", "lineage", "route", "compile"]
    assert all(cited in ids for ids in shown)                                  # the id the agent was SHOWN is the id the engine's law checked
    intake = next(r for r in rows if r["step_id"] == "intake")["output"]
    assert [r["id"] for r in intake["corpus_evidence"]] == [r["id"] for r in ROWS]
    lineage = [r["output"] for r in rows if r["step_id"] == "lineage"]
    assert lineage[0]["valid"] is False and lineage[1]["valid"] is True and lineage[1]["row_relevance"] == {cited: "STRUCTURAL_ANALOGY"}
    assert next(r for r in rows if r["step_id"] == "lenses")["output"]["lenses"]
