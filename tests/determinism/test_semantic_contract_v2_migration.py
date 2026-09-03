"""S2 — semantic contract migration + pinning. CAPACITY ONLY.

S2 must make the system able to REPRESENT and REPRODUCE V2 semantics
without changing any production behaviour. These tests assert the
no-behaviour-change property as hard as they assert the new capacity,
because a migration that quietly reinterprets rows would fabricate
provenance for decisions that were never made.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.entity_admission import POLICY_VERSION, decide
from polymath_shared.execution import (
    SEMANTIC_CONTRACT_V1_1, SEMANTIC_CONTRACT_V2, semantic_authorities,
    semantic_bundle_sha256, worker_contracts,
)

MIGRATION = ROOT / "stores/postgres/migrations/0015_semantic_contract_v2.sql"


# --- no behaviour change ---------------------------------------------------

def test_production_admission_is_untouched():
    """S2 changes representation, not interpretation."""
    assert POLICY_VERSION == "entity-admission-v1.1"
    gold = json.loads((ROOT / "eval/admission/admission_gold_v1.1.json").read_text())["items"]
    wrong = [i["surface"] for i in gold
             if decide(i["surface"], i["core_type"], 0.5).reference_class != i["label"]]
    assert not wrong, wrong


def test_migration_performs_no_backfill():
    """Inferring `anchor_kind` from `normalized_surface` would be exactly the
    normalized-surface classification the contract forbids."""
    sql = MIGRATION.read_text().upper()
    assert "UPDATE MENTIONS" not in sql
    assert "UPDATE RUNS" not in sql
    assert "SET ANCHOR_KIND" not in sql


def test_every_new_column_is_nullable_and_added_idempotently():
    sql = MIGRATION.read_text()
    for col in ("proposal_surface", "referential_surface", "anchor_kind",
                "decision_status", "reference_basis", "admission_reason",
                "canonical_entity_id", "semantic_contract"):
        assert f"ADD COLUMN IF NOT EXISTS {col}" in sql, col
    assert "NOT NULL" not in sql, "new columns must be nullable for historical rows"


def test_no_stored_graph_eligible_column():
    """Wiring invariant 3: eligibility has exactly one derived authority.

    Checks for a COLUMN DECLARATION, not the substring — the migration
    comment names `graph_eligible` precisely to record why it is absent.
    """
    sql = MIGRATION.read_text().lower()
    assert "add column if not exists graph_eligible" not in sql
    assert "graph_eligible" in sql, "the absence should be documented, not silent"


# --- new capacity ----------------------------------------------------------

def test_three_surface_representations_are_representable_and_distinct():
    sql = MIGRATION.read_text()
    assert "proposal_surface" in sql and "referential_surface" in sql
    # normalized_surface already exists and keeps its lookup-only role
    assert "normalized_surface" in sql   # named in the contract comment


def test_semantic_authorities_cover_the_required_surface():
    a = semantic_authorities()
    for required in ("identity_precision_contract", "entity_harbor_contract",
                     "referential_envelope_contract", "discourse_reference_contract",
                     "discourse_reference_policy_sha256", "concept_evidence_contract",
                     "contraction_resolution_contract", "graph_eligibility_contract",
                     "canonical_fact_gate_contract"):
        assert required in a, required
        assert a[required] is not None


def test_bundle_hash_changes_when_any_authority_changes():
    base = semantic_bundle_sha256()
    import polymath_shared.execution as ex
    real = ex.semantic_authorities
    try:
        ex.semantic_authorities = lambda: {**real(), "entity_harbor_contract": "entity-harbor-v2"}
        assert ex.semantic_bundle_sha256() != base
    finally:
        ex.semantic_authorities = real
    assert semantic_bundle_sha256() == base      # restored, deterministic


def test_bundle_hash_is_deterministic():
    assert len({semantic_bundle_sha256() for _ in range(20)}) == 1


def test_historical_and_v2_contracts_are_distinguishable():
    """Old execution contracts must never be rewritten to claim V2."""
    assert SEMANTIC_CONTRACT_V1_1 == "admission-v1.1"
    assert SEMANTIC_CONTRACT_V2 == "admission-harbor-v2"
    assert SEMANTIC_CONTRACT_V1_1 != SEMANTIC_CONTRACT_V2


def test_no_v2_identities_are_created_by_s2():
    """S2 grants capacity only: no V2 entities, no fact rewrites, no
    eligibility changes."""
    sql = MIGRATION.read_text().upper()
    for forbidden in ("INSERT INTO ENTITIES", "INSERT INTO FACTS",
                      "DELETE FROM", "DROP TABLE", "DROP COLUMN"):
        assert forbidden not in sql, forbidden
