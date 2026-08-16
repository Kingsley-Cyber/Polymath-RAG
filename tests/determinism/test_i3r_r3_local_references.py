"""I3R-R3: bounded local definite-description reference resolution."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import EntitySpan, CoreType  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402
from workers.candidates import SentenceSlice, build_candidates  # noqa: E402
from workers.evidence_proposer import propose_evidence  # noqa: E402

PACK = load_rule_pack(pack_version="1.2.0")


def E(text, core, start, doc="d1", chunk="chunk_t"):
    return EntitySpan(doc_id=doc, chunk_id=chunk, start=start,
                      end=start + len(text), text=text,
                      core_type=CoreType(core), score=0.9,
                      extractor_version="test")


def pairs_for(sent, entities, history=None):
    sl = SentenceSlice(text=sent, sentence_start=0, sentence_end=len(sent),
                       entities=entities,
                       evidence=propose_evidence(sent, "chunk_t", PACK),
                       parse=None)
    return {(c.subject.span.text, c.object.span.text)
            for c in build_candidates([sl], doc_id="d1", corpus_id="c1",
                                      ontology_profile="core",
                                      extractor_version="test",
                                      rule_pack=PACK,
                                      doc_entities_history=history or [])}


def test_gateway_head_match_resolves():
    gateway = E("Meridian API Gateway", "Product", 0)
    envoy = E("Envoy Proxy", "Technology", 17)
    pairs = pairs_for("The gateway uses Envoy Proxy.", [envoy], [gateway])
    assert pairs == {("Meridian API Gateway", "Envoy Proxy")}


def test_company_org_unique_resolves():
    northwind = E("Northwind Outfitters", "Organization", 0)
    klaviyo = E("Klaviyo", "Technology", 17)
    pairs = pairs_for("The company uses Klaviyo.", [klaviyo], [northwind])
    assert pairs == {("Northwind Outfitters", "Klaviyo")}


def test_ambiguous_orgs_abstain():
    a = E("Acme Corp", "Organization", 0)
    b = E("Beta Inc", "Organization", 0, doc="d2")
    klaviyo = E("Klaviyo", "Technology", 17)
    pairs = pairs_for("The company uses Klaviyo.", [klaviyo], [a, b])
    assert pairs == set()


def test_head_match_ambiguous_abstain():
    g1 = E("Meridian API Gateway", "Technology", 0)
    g2 = E("Payment Gateway", "Technology", 0, doc="d3")
    envoy = E("Envoy Proxy", "Technology", 17)
    pairs = pairs_for("The gateway uses Envoy Proxy.", [envoy], [g1, g2])
    assert pairs == set()


def test_service_description_unresolved_abstains():
    k8s = E("Kubernetes", "Technology", 16)
    pairs = pairs_for("The service runs on Kubernetes.", [k8s],
                      [E("Order Event Router", "Technology", 0)])
    assert pairs == set()


def test_resolver_never_creates_company_entity():
    from polymath_shared.entity_admission import allocate_entity_id
    northwind = E("Northwind Outfitters", "Organization", 0)
    klaviyo = E("Klaviyo", "Technology", 17)
    sl = SentenceSlice(text="The company uses Klaviyo.", sentence_start=0,
                       sentence_end=22, entities=[klaviyo],
                       evidence=propose_evidence("The company uses Klaviyo.",
                                                 "chunk_t", PACK),
                       parse=None)
    cands = build_candidates([sl], doc_id="d1", corpus_id="c1",
                             ontology_profile="core", extractor_version="test",
                             rule_pack=PACK, doc_entities_history=[northwind])
    assert cands
    for c in cands:
        assert c.subject.span.text == "Northwind Outfitters"
        assert c.subject.resolved_entity_id == allocate_entity_id(
            "Northwind Outfitters", "Organization", corpus_id="c1",
            doc_id="d1", chunk_id="chunk_t", span_start=0, span_end=22,
            extraction_score=0.9, sentence_initial=True).mention_id
