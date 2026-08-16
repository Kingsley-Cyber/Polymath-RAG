"""I3R-R1: typed trigger contract + narrowed vocab + bounded verb forms.

RED fixtures are the I3 failure sentences; GREEN fixtures prove the
legitimate arms still fire. Pack under test: core-predicates-v1.2.0.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from workers.evidence_proposer import (  # noqa: E402
    _bounded_verb_form,
    localize_trigger,
    propose_evidence,
)
from polymath_shared.contracts import EvidenceSpan  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402

PACK = load_rule_pack(pack_version="1.2.0")


def triggers_for(text: str):
    return propose_evidence(text, "chunk_t", PACK)


def test_bounded_verb_forms():
    assert _bounded_verb_form("started", "start")
    assert _bounded_verb_form("starts", "start")
    assert _bounded_verb_form("starting", "start")
    assert not _bounded_verb_form("startled", "start")
    assert not _bounded_verb_form("startling", "start")
    assert _bounded_verb_form("applied", "apply")
    assert not _bounded_verb_form("application", "apply")
    assert _bounded_verb_form("using", "use")
    assert _bounded_verb_form("used", "use")
    assert _bounded_verb_form("stopped", "stop")
    assert _bounded_verb_form("tries", "try")
    assert _bounded_verb_form("tried", "try")


def test_application_logs_does_not_fire_uses():
    text = ("HarborPay also updated its Token Handling Standard to prohibit "
            "application logs from recording Authorization headers.")
    spans = triggers_for(text)
    assert not any(s.trigger_lemma == "application" for s in spans)


def test_started_event_does_not_compile_to_founded():
    """R1B generalized invariant: 'started <Event>' must not produce a
    founded fact (founded is Organization-object only); 'started
    <Organization>' remains a legitimate founding expression."""
    from polymath_shared.contracts import EntitySpan, RelationCandidate
    from polymath_shared.rulepack import compile_relation
    from workers.candidates import SentenceSlice

    def compile_sentence(sent, entities):
        spans = triggers_for(sent)
        sl = SentenceSlice(text=sent, sentence_start=0, sentence_end=len(sent),
                           entities=entities, evidence=spans, parse=None)
        from workers.candidates import build_candidates
        out = []
        for cand in build_candidates(
            [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
            extractor_version="test", rule_pack=PACK):
            d = compile_relation(cand, None, PACK)
            if d.decision in ("ACCEPT", "QUALIFY") and d.fact:
                out.append((d.fact.predicate, cand.subject.span.text, cand.object.span.text))
        return out

    summit = EntitySpan(doc_id="d1", chunk_id="chunk_t", start=0, end=18,
                        text="Summit Fulfillment", core_type="Organization",
                        score=0.9, extractor_version="test")
    pilot = EntitySpan(doc_id="d1", chunk_id="chunk_t", start=30, end=35,
                       text="pilot", core_type="Event", score=0.7,
                       extractor_version="test")
    facts = compile_sentence("Summit Fulfillment started its automation pilot.",
                             [summit, pilot])
    assert not any(f[0] == "founded" for f in facts), f"founded leaked: {facts}"


def test_started_organization_still_compiles_to_founded():
    from polymath_shared.contracts import EntitySpan
    from polymath_shared.rulepack import compile_relation
    from workers.candidates import SentenceSlice, build_candidates

    founder = EntitySpan(doc_id="d1", chunk_id="chunk_t", start=0, end=11,
                         text="The founder", core_type="Person", score=0.9,
                         extractor_version="test")
    company = EntitySpan(doc_id="d1", chunk_id="chunk_t", start=23, end=34,
                         text="the company", core_type="Organization", score=0.9,
                         extractor_version="test")
    sent = "The founder started the company in 2019."
    sl = SentenceSlice(text=sent, sentence_start=0, sentence_end=len(sent),
                       entities=[founder, company],
                       evidence=triggers_for(sent), parse=None)
    facts = []
    for cand in build_candidates([sl], doc_id="d1", corpus_id="c1",
                                 ontology_profile="core",
                                 extractor_version="test", rule_pack=PACK):
        d = compile_relation(cand, None, PACK)
        if d.decision in ("ACCEPT", "QUALIFY") and d.fact:
            facts.append(d.fact.predicate)
    assert "founded" in facts


def test_verb_arm_still_fires_uses():
    spans = triggers_for("HarborPay uses Okta Workforce Identity.")
    hit = [s for s in spans if s.trigger_lemma == "use"]
    assert hit
    assert hit[0].trigger_lexical_class == "VERB"
    assert hit[0].trigger_predicate_id == "uses"
    assert hit[0].trigger_match_source == "verbs"


def test_use_of_multiword_fires_uses():
    spans = triggers_for("the use of the bearer token was recorded.")
    hit = [s for s in spans if s.trigger_predicate_id == "uses"
           and s.trigger_match_source == "multiword"]
    assert hit


def test_founded_still_fires_on_real_founding():
    spans = triggers_for("John founded Acme in 2012.")
    hit = [s for s in spans if s.trigger_lemma == "found"
           and s.trigger_predicate_id == "founded"]
    assert hit


def test_typed_trigger_contract_fields_populated():
    spans = triggers_for("HarborPay uses Okta Workforce Identity.")
    verb_hits = [s for s in spans if s.trigger_match_source == "verbs"]
    assert verb_hits
    for s in verb_hits:
        assert s.trigger_lexical_class == "VERB"
        assert s.trigger_predicate_id
    multi_hits = [s for s in spans if s.trigger_match_source == "multiword"]
    for s in multi_hits:
        assert s.trigger_lexical_class == "MULTIWORD"
        assert s.trigger_predicate_id
