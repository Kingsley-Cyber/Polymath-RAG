"""GOVERNED-CONVERGENCE-V1 TG2b — the EvidencePacket wire contract (contracts/evidence/v1).

The packet had a producer (shared/polymath_shared/evidence_packet.py) and NO schema. Its first consumer (the adapter's
evidence boundary) validates it consumer-side and FAILS CLOSED, so producer and schema must never drift apart: this test
builds packets with the real producer and validates them against the schema the consumer enforces.
"""
import json
import pathlib
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import evidence_packet as producer  # noqa: E402
from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402

assert pathlib.Path(producer.__file__).resolve().is_relative_to(ROOT), producer.__file__      # executed path == this checkout

V1 = ROOT / "contracts" / "evidence" / "v1"
SCHEMA = json.loads((V1 / "evidence_packet.schema.json").read_text())
EXAMPLE = json.loads((V1 / "evidence_packet.example.json").read_text())


def _validator():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    return jsonschema.Draft202012Validator(SCHEMA)


def test_schema_is_valid_and_the_example_satisfies_it():
    _validator().validate(EXAMPLE)
    assert EB.packet_schema() == SCHEMA and EB.PACKET_SCHEMA_PATH == V1 / "evidence_packet.schema.json"


def test_one_version_string_across_producer_schema_and_consumer():
    assert producer.SCHEMA_VERSION == SCHEMA["properties"]["schema_version"]["const"] == EB.PACKET_SCHEMA_VERSION == "evidence-packet-v1"
    assert SCHEMA["properties"]["synthesis_performed"]["const"] is False


def test_the_real_producer_emits_packets_the_consumer_accepts():
    plan = [{"id": "q0", "origin": "USER", "role": "PRIMARY"}, {"id": "ce1", "origin": "CORPUS_EXPLORE", "role": "SUPPORT", "target": "damping", "reason": "adjacent mechanism"}]
    rows = [{"chunk_id": "c1", "doc_id": "d1", "source_name": "Book", "text": "direct", "query_ids": ["q0"], "role": "DIRECT"},
            {"chunk_id": "c2", "doc_id": "d2", "source_name": "Book", "text": "seated", "query_ids": ["ce1"], "role": "LATENT", "latent_role": "COMPLEMENTARY"},
            {"chunk_id": "c3", "doc_id": "d3", "source_name": "Book", "text": "divergent", "query_ids": ["ce1"], "role": "LATENT", "latent_role": "DIVERGENT"},
            {"chunk_id": "c4", "doc_id": "d4", "source_name": "Book", "text": "related only", "query_ids": [], "role": "RELATIONAL", "latent_role": "RELATED"},
            {"chunk_id": "c5", "doc_id": "d5", "source_name": "Book", "text": "ungraded", "query_ids": ["q0"]}]
    packet = producer.build_evidence_packet(q0="why do belts bounce", retrieval_mode="WILDCARD", plan_queries=plan, evidence_rows=rows,
                                            ca4_grades={"c1": "DIRECT", "c2": "RELATED", "c3": "PARTIAL", "c4": "related"},
                                            receipts={"firing": {"requested": True, "fired": True, "cause": None}},
                                            corpus_explorer_requested=True, corpus_explorer_used=True).to_dict()
    _validator().validate(packet)
    assert EB.check_response({"evidence_packet": packet, "synthesis_performed": False}) == []
    assert {e["utility_role"] for e in packet["evidence"]} == {"DIRECT", "COMPLEMENTARY", "DIVERGENT", "RELATED"}
    assert {e["ca4_grade"] for e in packet["evidence"]} == {"DIRECT", "PARTIAL", "RELATED", None}
    # an EMPTY packet is lawful: the corpus not supporting a need is a finding, not a contract failure
    empty = producer.build_evidence_packet(q0="x", retrieval_mode="FAST", plan_queries=[], evidence_rows=[]).to_dict()
    _validator().validate(empty)
    assert EB.check_response({"evidence_packet": empty}) == [] and EB.rows_from_packet(empty, "cinema") == []


def test_the_vocabularies_the_adapter_step_wire_accepts_match_the_packet():
    step = json.loads((ROOT / "contracts/adapter/v1/adapter_step.schema.json").read_text())
    ref = step["properties"]["context"]["properties"]["evidence_refs"]["items"]["properties"]
    item = SCHEMA["$defs"]["evidence_item"]["properties"]
    assert ref["utility_role"]["enum"] == item["utility_role"]["enum"] == list(EB.UTILITY_ROLES)
    assert ref["ca4_grade"]["enum"] == [g for g in item["ca4_grade"]["enum"] if g is not None] == list(EB.CA4_GRADES)
    required = step["properties"]["context"]["properties"]["evidence_refs"]["items"]["required"]
    assert required == ["kind", "id"]                                   # the four boundary properties are OPTIONAL (additive)
    for prop in ("utility_role", "ca4_grade", "c4_valid", "origin"):
        assert prop in ref
