"""GENERATION-SWAP-V1 (blue/green re-ingest) — structural pins, no stores.

The live proof is tests/integration/test_generation_swap.py (a seeded
lineage: mint beside, hidden while in flight, swapped on promotion).
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "control", ROOT / "workers", ROOT / "orchestrator"):
    sys.path.insert(0, str(p))

from polymath_shared.generation import (  # noqa: E402
    CHUNK_VISIBLE_SQL,
    IN_FLIGHT_STATUSES,
    chunk_visible_sql,
)


def test_visibility_fragment_is_a_correlated_guard_over_in_flight_runs():
    sql = chunk_visible_sql("n", "d")
    assert sql.startswith("NOT EXISTS (SELECT 1 FROM runs hr")
    assert "hr.corpus_id = d.corpus_id" in sql
    assert "= n.chunk_contract_version" in sql
    for st in IN_FLIGHT_STATUSES:
        assert f"'{st}'" in sql
    # a serving or retired successor never hides anything
    assert "'query_ready'" not in CHUNK_VISIBLE_SQL and "'superseded'" not in CHUNK_VISIBLE_SQL
    # no bind parameters: safe to paste into any parametrised query
    assert "%s" not in sql


def test_execution_contract_carries_the_gate_and_extract_depends_on_it():
    from control.reconciliation import STAGE_CONTRACT_DEPENDENCIES
    from polymath_shared.execution import worker_contracts
    from polymath_shared.llm_extraction.gate import GATE_VERSION, attestation_policy

    c = worker_contracts()
    assert c["extraction_gate"] == f"{GATE_VERSION}/{attestation_policy()}"
    assert "extraction_gate" in STAGE_CONTRACT_DEPENDENCIES["extract"]
    assert "ontology_file_sha" in STAGE_CONTRACT_DEPENDENCIES["extract"]
    for stage in ("project_neo4j", "canonicalize", "project_canonical"):
        assert "extraction_gate" in STAGE_CONTRACT_DEPENDENCIES[stage], stage
    # the retired rule pack key is gone from every dependency list
    assert not any("rule_pack" in deps for deps in STAGE_CONTRACT_DEPENDENCIES.values())


def test_receipt_identity_and_execution_contract_share_one_gate_version():
    src = (ROOT / "workers" / "workers" / "llm_provider.py").read_text()
    assert '"version": GATE_VERSION' in src
    assert '"attestation-levels-v1"' not in src, "gate version duplicated as a literal"


def test_every_chunk_reader_applies_the_visibility_guard():
    api = ROOT / "orchestrator" / "orchestrator" / "api"
    expectations = {
        "fast.py": ["chunk_visible_sql(\"n\", \"d\")", "self._hidden_for(filters.get(\"corpus_id\"))"],
        "hybrid.py": ["_chunk_visible_sql(\"ch\", \"d\")", "hidden_generations(_conn, corpus_id)"],
        "retrieve.py": ["chunk_visible_sql(\"c\", \"d\")"],
        "evidence.py": ["chunk_visible_sql(\"c\", \"d\")"],
        "chat.py": ["chunk_visible_sql(\"c\", \"d\")"],
    }
    for name, needles in expectations.items():
        src = (api / name).read_text()
        for needle in needles:
            assert needle in src, f"{name} lost the generation guard: {needle}"
    # retrieve applies it to BOTH the parent and the children query
    assert (api / "retrieve.py").read_text().count('chunk_visible_sql("c", "d")') == 2


def test_intake_skips_the_purge_for_blue_green_runs_and_swap_owns_it():
    intake = (ROOT / "workers" / "workers" / "intake_worker.py").read_text()
    assert "if chunks and not is_blue_green_run(conn, run_id):" in intake
    sched = (ROOT / "control" / "control" / "scheduler.py").read_text()
    start = sched.index("def apply_promotions(")
    body = sched[start:sched.index("\ndef ", start + 1)]
    assert "_generation_swap(conn, run_id, row[0])" in body
    assert body.index("UPDATE runs SET status = 'query_ready'") < body.index("_generation_swap(")


def test_persister_refreshes_supporting_chunks_on_replay():
    src = (ROOT / "workers" / "workers" / "knowledge_artifacts.py").read_text()
    assert "ON CONFLICT (concept_id) DO UPDATE SET\n                supporting_chunks = EXCLUDED.supporting_chunks" in src
    assert "ON CONFLICT (procedure_id) DO UPDATE SET\n                source_chunk_ids = EXCLUDED.source_chunk_ids" in src
    assert "DO NOTHING" not in src.split("INSERT INTO procedure_artifacts")[1].split("INSERT INTO concept_artifacts")[0]


def test_projector_stamps_the_generation_on_chunk_points():
    src = (ROOT / "workers" / "workers" / "project_qdrant_worker.py").read_text()
    assert src.count('"chunk_contract_version": ') >= 2, "chunk points must carry their generation"


def test_swap_is_idempotent_and_atomic_by_construction():
    src = (ROOT / "control" / "control" / "generation_swap.py").read_text()
    assert "if not bg or bg.get(\"swapped_at\"):\n        return None" in src
    # store sweeps never raise into the promotion transaction
    assert "def _sweep_stores(" in src and "except Exception as exc:" in src
    # the migration that makes two generations coexist
    mig = (ROOT / "stores" / "postgres" / "migrations" / "0050_generation_swap.sql").read_text()
    assert "DROP CONSTRAINT IF EXISTS chunks_doc_id_chunk_index_key" in mig
    assert "COALESCE(chunk_contract_version, '')" in mig
