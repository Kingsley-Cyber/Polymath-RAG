"""E7 (DOCUMENT-RAG-COMPLETION-V1 Part B, "Fix `target`"): `CompiledQuery.target` is the information need a subquery
localizes, never a reference. The reference a subquery was derived from rides its own field, `derived_from`:
- a profile concept key (bridges / Corpus Explore);
- a nominated doc id (PROFILE expansion);
- a gap claim id (resolution rounds).

The evidence packet's `provenance.derived_from` reads that field, so its values are unchanged. Legacy plan rows (no
`derived_from` key: receipts written before this change) still resolve through `target`."""
from __future__ import annotations

from types import SimpleNamespace

from polymath_shared.bridge_compiler import CompiledBridge, Concept
from polymath_shared.bridge_integration import bridges_to_subqueries
from polymath_shared.chat_plan import CompiledQuery
from polymath_shared.evidence_packet import build_evidence_packet
from polymath_shared.evidence_resolution import ClaimState, _resolution_query
from polymath_shared.subquery_provenance import annotate_subquery_provenance

Q0 = "how to convey silent authority"


def test_bridge_subqueries_carry_the_concept_key_in_derived_from_and_no_target():
    concept = Concept(key="spatial-control", label="Spatial control", source="docLaban")
    bridge = CompiledBridge(bridge_id="b1", bridge_query="how space conveys dominance on stage",
                            derived_from="spatial-control", relation_to_q0="nonverbal dominance via space")
    (q,) = bridges_to_subqueries([bridge], {"spatial-control": concept})
    assert q.derived_from == "spatial-control"
    assert q.target is None                                   # no planner-supplied need, and never a key
    assert q.inspired_by_profile == ["docLaban"] and q.profile_surface == "Spatial control"


def test_profile_expansion_carries_the_doc_id_in_derived_from_and_no_target(monkeypatch):
    from orchestrator.api import ui
    monkeypatch.setenv("POLYMATH_CHAT_PROFILE_EXPANSION", "1")
    plan = SimpleNamespace(queries=[CompiledQuery(id="q0", type="PRIMARY", query=Q0)], compiler={})
    nom = SimpleNamespace(doc_id="docLaban", representative_text="weight and space effort qualities",
                          representative_surface="effort qualities")
    ui._add_profile_expansion(plan, SimpleNamespace(nominations=[nom]))
    added = [q for q in plan.queries if q.origin == "PROFILE"]
    assert len(added) == 1
    assert added[0].derived_from == "docLaban" and added[0].target is None
    assert added[0].inspired_by_profile == ["docLaban"]


def test_resolution_subquery_derives_from_the_claim_and_targets_the_need():
    q = _resolution_query(ClaimState(claim_id="c2", importance=0.9, evidence_state="UNSUPPORTED",
                                     next_information_need="why effort qualities read as status"), 1)
    assert q.derived_from == "c2"
    assert q.target == "why effort qualities read as status"
    bare = _resolution_query(ClaimState(claim_id="c3", importance=0.9, evidence_state="UNSUPPORTED"), 1)
    assert bare.derived_from == "c3" and bare.target is None  # no need recorded: nothing is invented


def test_provenance_receipt_rows_record_derived_from_beside_target():
    plan = SimpleNamespace(queries=[
        CompiledQuery(id="q0", type="PRIMARY", query=Q0),
        CompiledQuery(id="br0", type="ENTITY", query="space and dominance", role="bridge", origin="BRIDGE",
                      derived_from="spatial-control"),
    ], compiler={})
    rows = {r["id"]: r for r in annotate_subquery_provenance(plan, None)["subqueries"]}
    assert rows["br0"]["derived_from"] == "spatial-control" and rows["br0"]["target"] is None
    assert rows["q0"]["derived_from"] is None


def _packet_provenance(plan_queries, query_id):
    rows = [{"chunk_id": "c1", "doc_id": "docLaban", "source_name": "Laban · effort", "text": "weight and space",
             "query_ids": [query_id], "role": "LATENT", "latent_role": "COMPLEMENTARY"}]
    p = build_evidence_packet(q0=Q0, retrieval_mode="HYBRID", plan_queries=plan_queries, evidence_rows=rows)
    return p.to_dict()["evidence"][0]["provenance"]


def test_packet_derived_from_reads_the_reference_field_and_never_the_need():
    q0 = {"id": "q0", "type": "PRIMARY", "origin": "USER", "role": "direct", "query": Q0}
    bridge = {"id": "ce0", "type": "ENTITY", "origin": "CORPUS_EXPLORE", "role": "bridge",
              "inspired_by_profile": ["docLaban"], "derived_from": "spatial-control", "target": None,
              "reason": "bridge/complementary <- spatial-control: nonverbal dominance via space"}
    assert _packet_provenance([q0, bridge], "ce0")["derived_from"] == "spatial-control"
    need_only = {"id": "r1", "type": "MECHANISM", "origin": "EVIDENCE_GAP", "role": "resolution",
                 "derived_from": None, "target": "why effort qualities read as status", "reason": "resolution: c2"}
    assert _packet_provenance([q0, need_only], "r1")["derived_from"] is None   # a need is not a source
    objects = [CompiledQuery(id="q0", type="PRIMARY", query=Q0),
               CompiledQuery(id="br0", type="ENTITY", query="space and dominance", role="bridge", origin="BRIDGE",
                             derived_from="spatial-control")]
    assert _packet_provenance(objects, "br0")["derived_from"] == "spatial-control"
