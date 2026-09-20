"""REASONING-BOUNDARY-V1 RB1 — EvidencePacket mapper (pure, offline)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.evidence_packet import (  # noqa: E402
    SCHEMA_VERSION,
    build_evidence_packet,
)

PLAN = [
    {"id": "q0", "type": "PRIMARY", "origin": "USER", "role": "direct", "query": "how to convey silent authority"},
    {"id": "ce0", "type": "ENTITY", "origin": "CORPUS_EXPLORE", "role": "bridge",
     "inspired_by_profile": ["docLaban"], "target": "spatial-control",
     "reason": "bridge/complementary <- spatial-control: nonverbal dominance via space"},
]
ROWS = [
    {"chunk_id": "c_q0", "doc_id": "docA", "source_name": "Directing · ch3", "text": "block the scene so she owns the room",
     "query_ids": ["q0"], "role": "DIRECT"},
    {"chunk_id": "c_ce", "doc_id": "docLaban", "source_name": "Laban · effort", "text": "weight and space effort qualities",
     "query_ids": ["ce0"], "role": "LATENT", "latent_role": "COMPLEMENTARY",
     "latent_lineage": {"proposed_role": "COMPLEMENTARY"}},
]
GRADES = {"c_q0": "DIRECT", "c_ce": "RELATED"}
RECEIPTS = {"activation": {"n_activations": 8}, "corpus_explore": {"added": 1},
            "bridges": [1, 2, 3], "fusion": {"k": 60}, "SHOULD_DROP": {"x": 1}}


def _packet(**kw):
    return build_evidence_packet(q0="how to convey silent authority", retrieval_mode="HYBRID",
                                 plan_queries=PLAN, evidence_rows=ROWS, ca4_grades=GRADES, receipts=RECEIPTS,
                                 corpus_explorer_requested=True, corpus_explorer_used=True, **kw)


def test_packet_shape_and_no_synthesis():
    p = _packet().to_dict()
    assert p["schema_version"] == SCHEMA_VERSION
    assert p["synthesis_performed"] is False           # evidence, never an answer
    assert p["q0"] == "how to convey silent authority" and p["retrieval_mode"] == "HYBRID"
    assert p["plan"]["corpus_explorer_requested"] is True and p["plan"]["corpus_explorer_used"] is True


def test_direct_row_maps():
    ev = {e["chunk_id"]: e for e in _packet().to_dict()["evidence"]}
    q0 = ev["c_q0"]
    assert q0["document_id"] == "docA" and q0["source"].startswith("Directing")
    assert q0["origin"] == "USER" and q0["utility_role"] == "DIRECT"
    assert q0["ca4_grade"] == "DIRECT" and q0["c4_valid"] is True


def test_corpus_explore_row_carries_role_and_provenance():
    ev = {e["chunk_id"]: e for e in _packet().to_dict()["evidence"]}
    ce = ev["c_ce"]
    assert ce["origin"] == "CORPUS_EXPLORE"
    assert ce["utility_role"] == "COMPLEMENTARY"            # C5 seat role wins over synthesis_role
    assert ce["synthesis_role"] == "LATENT"                 # auxiliary, not lost
    assert ce["ca4_grade"] == "RELATED"
    assert ce["c4_valid"] is True                           # RELATED but C5-seated => answerability-valid
    assert ce["provenance"]["derived_from"] == "spatial-control"
    assert ce["provenance"]["inspired_by_profile"] == ["docLaban"]


def test_c4_valid_related_only_is_false():
    rows = [{"chunk_id": "c1", "doc_id": "d", "text": "t", "query_ids": ["ce0"], "role": "RELATIONAL"}]
    p = build_evidence_packet(q0="x", retrieval_mode="HYBRID", plan_queries=PLAN, evidence_rows=rows,
                              ca4_grades={"c1": "RELATED"}, receipts={})
    assert p.to_dict()["evidence"][0]["c4_valid"] is False   # RELATED + not seated => not answerability-valid


def test_size_bounds():
    p = _packet(max_rows=1, max_text=5).to_dict()
    assert len(p["evidence"]) == 1                           # row cap
    assert len(p["evidence"][0]["text"]) <= 5                # text cap
    assert "SHOULD_DROP" not in p["receipts"]                # only the 4 known receipt keys survive
    assert set(p["receipts"]) <= {"activation", "corpus_explore", "bridges", "fusion"}


def test_receipt_list_bounded():
    big = {"bridges": list(range(100))}
    p = build_evidence_packet(q0="x", retrieval_mode="FAST", plan_queries=[], evidence_rows=[], receipts=big)
    assert len(p.to_dict()["receipts"]["bridges"]) <= 12


def test_rows_without_chunk_id_skipped():
    rows = [{"doc_id": "d", "text": "t", "query_ids": ["q0"]}, {"chunk_id": "", "text": "t2"}]
    p = build_evidence_packet(q0="x", retrieval_mode="FAST", plan_queries=PLAN, evidence_rows=rows)
    assert p.to_dict()["evidence"] == []


def test_deterministic():
    assert _packet().to_dict() == _packet().to_dict()
