"""ATTESTATION-LEVELS-V1 (LLM-DIRECT-CANON, ADR-0017): a relation endpoint's
attestation is a recorded level, not a veto. Measured 2026-09-03: the
anchor-chunk substring rule rejected 787 relations in 20 documents, most of
them correct (subject in the neighbouring chunk, or the list phrase the
sentence implies). Junk, unattested quotes and inventions still reject."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

from polymath_shared.llm_extraction.contract import CONTRACT_ID
from polymath_shared.llm_extraction.gate import (
    ATTESTATION_LEVELS, ChunkView, attest_endpoint, attestation_policy, sanitize,
    validate_and_normalize)

CHUNK_A = ("FortiGate firewalls reported VPN tunnel errors after the "
           "firmware update on January 15.")
CHUNK_B = ("The SOC playbook requires analysts to verify the jump host "
           "before re-keying any IPsec tunnel.")
CHUNK_C = "A marine research unit now measures water temperature, salinity and plankton density."


def _packet(relations: list[dict], nid: str = "p1:0") -> str:
    return json.dumps({
        "contract": CONTRACT_ID, "profile": "volume",
        "items": [{
            "neighborhood_id": nid,
            "entities": [{"surface": "FortiGate", "type": "Product", "quote": CHUNK_A}],
            "relations": relations,
            "digest": {"central_claim": "c", "main_mechanism": "m", "retrieval_uses": ["u"]},
        }],
    })


def _views() -> dict[str, list[ChunkView]]:
    return {"p1:0": [ChunkView("chunk_a", CHUNK_A), ChunkView("chunk_b", CHUNK_B)],
            "p1:1": [ChunkView("chunk_c", CHUNK_C)]}


def _run(relations, monkeypatch=None, policy=None):
    if monkeypatch is not None and policy is not None:
        monkeypatch.setenv("POLYMATH_EXTRACTION_ATTESTATION", policy)
    _, packet = sanitize(_packet(relations), {"p1:0"})
    return validate_and_normalize(packet, _views())


def _rel(subject, obj, quote=CHUNK_A, predicate="reported"):
    return {"subject": subject, "predicate": predicate, "object": obj, "quote": quote}


def test_levels_are_ordered_and_pure():
    a = ChunkView("chunk_a", CHUNK_A); b = ChunkView("chunk_b", CHUNK_B); c = ChunkView("chunk_c", CHUNK_C)
    q = (0, len(CHUNK_A))
    assert attest_endpoint("FortiGate", a, q, [a, b], [c], "tiered") == "quote"
    assert attest_endpoint("January 15", a, (0, 20), [a, b], [c], "tiered") == "anchor"
    assert attest_endpoint("jump host", a, q, [a, b], [c], "tiered") == "neighborhood"
    assert attest_endpoint("plankton density", a, q, [a, b], [c], "tiered") == "document"
    assert attest_endpoint("VPN errors", a, q, [a, b], [c], "tiered") == "abstract"   # tokens vpn+errors in the anchor
    assert attest_endpoint("spanning tree", a, q, [a, b], [c], "tiered") is None      # no support: invention
    # junk surfaces never reach attestation: is_term_surface rejects them first (NON_TERM_ENDPOINT)
    # strict = the pre-canon rule: quote/anchor only
    assert attest_endpoint("jump host", a, q, [a, b], [c], "strict") is None
    assert attest_endpoint("January 15", a, (0, 20), [a, b], [c], "strict") == "anchor"
    assert ATTESTATION_LEVELS == ("quote", "anchor", "neighborhood", "document", "abstract")


def test_cross_chunk_endpoint_is_kept_and_its_level_recorded(monkeypatch):
    out = _run([_rel("FortiGate", "jump host")], monkeypatch, "tiered")
    assert out.stats["relations"] == 1 and out.stats["relations_rejected"] == 0
    ev = out.evidence_by_chunk["chunk_a"][0]
    assert ev["attestation"] == {"subject": "quote", "object": "neighborhood"}
    assert out.stats["endpoint_attestation"]["quote"] == 1
    assert out.stats["endpoint_attestation"]["neighborhood"] == 1
    assert out.stats["attestation_policy"] == "tiered"


def test_abstract_endpoint_needs_token_support(monkeypatch):
    kept = _run([_rel("FortiGate", "VPN errors")], monkeypatch, "tiered")
    assert kept.stats["relations"] == 1
    assert kept.evidence_by_chunk["chunk_a"][0]["attestation"]["object"] == "abstract"
    rejected = _run([_rel("FortiGate", "spanning tree")], monkeypatch, "tiered")
    assert rejected.stats["relations"] == 0
    r = rejected.rejections[0]
    assert r["error_class"] == "UNATTESTED_RELATION_ENDPOINT" and r["detail"] == ["spanning tree"]
    assert r["attestation_policy"] == "tiered"


def test_strict_policy_restores_the_anchor_only_rule(monkeypatch):
    out = _run([_rel("FortiGate", "jump host")], monkeypatch, "strict")
    assert out.stats["relations"] == 0
    assert out.rejections[0]["error_class"] == "UNATTESTED_RELATION_ENDPOINT"
    assert out.stats["attestation_policy"] == "strict"
    monkeypatch.delenv("POLYMATH_EXTRACTION_ATTESTATION", raising=False)
    assert attestation_policy() == "tiered"


def test_hard_gates_still_reject(monkeypatch):
    # unattested quote and junk endpoints are unchanged
    out = _run([_rel("FortiGate", "jump host", quote="This sentence is not in any chunk.")], monkeypatch, "tiered")
    assert out.rejections[0]["error_class"] == "UNATTESTED_RELATION_QUOTE"
    out = _run([_rel("FortiGate", "if the tunnel fails")], monkeypatch, "tiered")   # clause, not a term
    assert out.rejections[0]["error_class"] == "NON_TERM_ENDPOINT"


def test_materializer_and_projector_carry_the_open_vocabulary():
    src = (ROOT / "workers" / "workers" / "llm_direct.py").read_text()
    assert '"endpoint_attestation": att or None' in src
    assert '"gate_version": "attestation-levels-v1"' in src
    assert "type_by_norm.get(normalized_for_lookup(subj_s))" in src, "endpoint type by normalized surface, not the type mapper"
    assert "map_core_type(subj_s)" not in src
    proj = (ROOT / "workers" / "workers" / "project_neo4j_worker.py").read_text()
    assert "SET e.raw_types = $raw_types, e.display_type = $display_type" in proj
    assert "SET r.predicate_raw = $predicate_raw" in proj
    from workers.project_neo4j_worker import display_type
    assert display_type("Concept", ["Concept", "Protocol"]) == "Protocol"
    assert display_type("Concept", []) == "Concept"
    assert display_type("Technology", ["technology"]) == "Technology"
