"""I3R-R2: trigger-scoped argument frames.

RED fixtures are the I3 coordination-explosion sentence and other
ambiguous bindings; GREEN fixtures prove legitimate pairings (default
frame, entity lists, prepositional association frame) still bind.
"""
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


def E(text, core, start=None, end=None, score=0.9, doc="d1", chunk="chunk_t"):
    start = start if start is not None else 0
    end = end if end is not None else start + len(text)
    return EntitySpan(doc_id=doc, chunk_id=chunk, start=start, end=end,
                      text=text, core_type=CoreType(core), score=score,
                      extractor_version="test")


def pair(candidates):
    return {(c.subject.span.text, c.object.span.text) for c in candidates}


def compile_pairs(sent, entities, history=None):
    sl = SentenceSlice(text=sent, sentence_start=0, sentence_end=len(sent),
                       entities=entities, evidence=propose_evidence(sent, "chunk_t", PACK),
                       parse=None)
    return pair(build_candidates([sl], doc_id="d1", corpus_id="c1",
                                 ontology_profile="core",
                                 extractor_version="test", rule_pack=PACK,
                                 doc_entities_history=history or []))


def test_i3_warehouse_sentence_binds_no_cartesian_pairs():
    sent = ("They installed Locus Robotics autonomous mobile robots in the "
            "Reno Distribution Center and connected the workflow to "
            "Manhattan Active Warehouse Management.")
    ent = [
        E("Locus Robotics", "Organization", start=13),
        E("autonomous mobile robots", "Technology", start=28),
        E("Reno Distribution Center", "Location", start=52),
        E("workflow", "Process", start=92),
        E("Manhattan Active Warehouse Management", "Organization", start=115),
    ]
    # The predicate-region boundary before "connected" must leave no
    # subject slot, and the referential gate rejects the generic
    # 'workflow' arg1 -> ZERO candidates from this sentence.
    assert compile_pairs(sent, ent) == set()


def test_default_frame_binds_single_pair():
    sent = "HarborPay uses Okta Workforce Identity to authenticate administrators."
    ent = [E("HarborPay", "Organization", start=0),
           E("Okta Workforce Identity", "Product", start=15)]
    assert compile_pairs(sent, ent) == {("HarborPay", "Okta Workforce Identity")}


def test_entity_list_expands_subject_side():
    sent = "The frontend and backend are part of the platform."
    ent = [E("The frontend", "Product", start=0),
           E("backend", "Product", start=16),
           E("the platform", "Product", start=38)]
    pairs = compile_pairs(sent, ent)
    assert ("The frontend", "the platform") in pairs
    assert ("backend", "the platform") in pairs
    assert len(pairs) <= 2


def test_double_list_is_fail_closed():
    sent = "A and B use C and D."
    ent = [E("A", "Product", start=0), E("B", "Product", start=6),
           E("C", "Product", start=12), E("D", "Product", start=18)]
    assert compile_pairs(sent, ent) == set()


def test_serial_trigger_regions_do_not_cross():
    sent = ("HarborPay disabled the debugging configuration, reduced the "
            "access-token lifetime, and required mutual TLS.")
    ent = [E("HarborPay", "Organization", start=0),
           E("debugging configuration", "Concept", start=19),
           E("access-token lifetime", "Measurement", start=48),
           E("mutual TLS", "Technology", start=84)]
    pairs = compile_pairs(sent, ent)
    # 'required' is its own predicate region; the subject slot inside it
    # is empty (fail-closed) — no cross-region binding of HarborPay to
    # mutual TLS by surface proximity alone.
    assert ("HarborPay", "mutual TLS") not in pairs


def test_no_trigger_no_candidates():
    sent = "Northwind Outfitters kept Shopify Plus, Stripe, and Klaviyo."
    ent = [E("Northwind Outfitters", "Organization", start=0),
           E("Shopify Plus", "Product", start=27),
           E("Stripe", "Product", start=41),
           E("Klaviyo", "Product", start=53)]
    assert compile_pairs(sent, ent) == set()
