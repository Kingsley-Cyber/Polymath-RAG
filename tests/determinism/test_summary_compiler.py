"""SUMMARY-COMPILER-V1 — the owner's deterministic compiler, pinned.
Pure: no DB, no model. Each test names the rule it guards."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.region_role import (  # noqa: E402
    ROLE_BODY,
    ROLE_CODE,
    ROLE_NOISE_OCR,
    ROLE_OUTPUT,
    is_summarizable,
    parent_role,
)
from polymath_shared.summary_compiler import (  # noqa: E402
    SECTION_MAX_CHARS,
    RELATION_PHRASES,
    build_background,
    compile_document,
    compile_section,
    digest_variant,
    render_relation,
    serialize,
    split_sentences,
    structural_quality,
)

C1 = ("FortiGate firewalls require IPsec tunnels for every site link. The vendor "
      "documentation describes the general configuration process in many pages.")
C2 = ("Splunk correlates alerts with Elastic dashboards during triage. Analysts read "
      "the general documentation before starting any configuration process.")
C3 = ("Wireshark captures packets on the mirror port. The general configuration process "
      "is described in the documentation for analysts.")
C4 = ("Nessus scans hosts for known vulnerabilities nightly. The documentation for the "
      "general configuration process is long.")
GENERIC_BG = ["general configuration process documentation"] * 6


def _children(*texts):
    return [{"chunk_id": f"c{i}", "text": t} for i, t in enumerate(texts)]


def _compile(*texts, facts=None, **kw):
    return compile_section(_children(*texts), parent_id="p", facts=facts, **kw)


def test_deterministic_and_verbatim_with_offsets() -> None:
    a = _compile(C1, C2, C3, C4)
    b = _compile(C1, C2, C3, C4)
    assert a.embed_text == b.embed_text and a.sentences == b.sentences
    texts = dict(zip(("c0", "c1", "c2", "c3"), (C1, C2, C3, C4)))
    for s in a.sentences:
        assert texts[s["chunk_id"]][s["start"]:s["end"]] in a.summary


def test_coverage_first_every_child_is_represented() -> None:
    out = _compile(C1, C2, C3, C4)
    assert {s["chunk_id"] for s in out.sentences} == {"c0", "c1", "c2", "c3"}
    assert out.coverage["units_covered"] == 4 and out.coverage["uncovered"] == []
    assert [s["chunk_id"] for s in out.sentences] == sorted(
        (s["chunk_id"] for s in out.sentences), key=lambda c: int(c[1:]))     # source order


def test_salience_is_not_longest_sentence() -> None:
    long_generic = ("The general configuration process documentation describes the general "
                    "configuration process in the documentation for the general process again.")
    short_specific = "Zeek exports connection logs to Kafka."
    out = compile_section(_children(long_generic + " " + short_specific), parent_id="p",
                          background=build_background(GENERIC_BG + [short_specific]),
                          max_sentences=1, max_chars=200)
    assert out.summary == short_specific


def test_trusted_triples_boost_and_serialize_untrusted_only_rank() -> None:
    text = "Splunk uses Kafka for ingestion. The team likes the office coffee a lot."
    trusted = {"chunk_id": "c0", "predicate": "USES", "subject": "Splunk", "object": "Kafka",
               "start": 0, "end": 31, "trusted": True, "fact_id": "f1", "order": 0}
    untrusted = {"chunk_id": "c0", "predicate": "USES", "subject": "team", "object": "coffee",
                 "start": 32, "end": len(text), "trusted": False, "fact_id": "f2", "order": 0}
    out = compile_section(_children(text), parent_id="p", facts=[trusted, untrusted],
                          max_sentences=1, max_chars=200)
    assert out.summary == "Splunk uses Kafka for ingestion."
    assert out.relations == ["Splunk uses Kafka."]
    assert out.sentences[0]["triples_trusted"] == 1
    assert "team" not in " ".join(out.relations)
    assert out.keywords[:2] == ["Splunk", "Kafka"]            # triple endpoints lead


def test_dedupe_keeps_one_copy_and_source_order() -> None:
    dup = "Repeated sentence about firewall rules and tunnels."
    out = _compile(dup + " Alpha specific statement about Zeek logs.", dup + " Beta note on Kafka topics.")
    assert out.summary.count("Repeated sentence") == 1
    idx = [s["chunk_id"] for s in out.sentences]
    assert idx == sorted(idx)


def test_no_split_inside_abbreviations() -> None:
    text = "Data types are constraints (i.e. tools used to secure integrity) linked with columns. Next sentence here."
    sents = [t for _, _, t in split_sentences(text)]
    assert sents[0].startswith("Data types") and "(i.e. tools" in sents[0]
    assert len(sents) == 2


def test_structural_quality_rejects_headings_and_dumps() -> None:
    assert structural_quality("## Page 44") == 0.0
    assert structural_quality("35 0,111428929 10,0,2.4 10,0.2.15 vOP 60 41015 = 10 Len=0 36") == 0.0
    assert structural_quality("FortiGate firewalls require IPsec tunnels for every site link.") == 1.0


def test_serializer_shape_and_omitted_empty_blocks() -> None:
    assert serialize("S.", ["A uses B."], ["A", "B"]) == "SUMMARY:\nS.\n\nRELATIONSHIPS:\nA uses B.\n\nKEY CONCEPTS:\nA; B"
    assert serialize("S.", [], []) == "SUMMARY:\nS."


def test_relation_rendering_covers_ontology_and_rule_pack() -> None:
    assert render_relation("IS_A", "Tamara", "analyst") == "Tamara is a analyst."
    assert render_relation("instance_of", "fred", "fast flux") == "fred is an instance of fast flux."
    assert render_relation("NOPE", "a", "b") is None
    assert set(RELATION_PHRASES) >= {"IS_A", "PART_OF", "HAS_PROPERTY", "SAME_AS", "USES", "REQUIRES",
                                     "PRODUCES", "CAUSES", "REGULATES", "CORRELATES_WITH",
                                     "CONSTRAINED_BY", "PRECEDES", "MEASURES", "LOCATED_IN",
                                     "ALTERNATIVE_TO", "OPPOSES", "ACTS_ON", "RELATED_TO"}


def test_keywords_exclude_hapax_when_background_is_wide() -> None:
    bg = build_background([C1, C2, C3, C4, "zzqx appears once only here."])
    out = compile_section(_children("Nessus scans hosts nightly. zzqx appears once only here."),
                          parent_id="p", background=bg)
    assert "zzqx" not in out.keywords
    assert len(out.keywords) <= 8


def test_document_compile_preserves_late_parents() -> None:
    parents = [{"chunk_id": f"p{i}", "summary": f"Section {i} explains a distinct topic number {i} clearly."}
               for i in range(9)] + [{"chunk_id": "p9", "summary": "Zephyr closes the book with rare material."}]
    out = compile_document(parents, doc_id="d")
    assert "Zephyr" in out.summary
    assert out.coverage["units_covered"] == 10


def test_digest_adapter_activates_only_on_clean_digest() -> None:
    det = _compile(C1, C2)
    clean = [{"neighborhood_id": "p:0", "central_claim": "FortiGate site links depend on IPsec tunnels.",
              "main_mechanism": "Each site link is built on a tunnel.", "retrieval_uses": ["fortigate ipsec"]}]
    llm = digest_variant(clean, det)
    assert llm is not None and llm.variant == "llm_digest"
    assert llm.embed_text.startswith("SUMMARY:\nFortiGate site links depend on IPsec tunnels. Each site link")
    assert llm.relations == det.relations and "fortigate ipsec" in llm.keywords
    assert digest_variant([{"neighborhood_id": "p:0", "central_claim": "", "main_mechanism": ""}], det) is None
    assert digest_variant([{"neighborhood_id": "p:0", "central_claim": "ee oe ee ee ee ee ee"}], det) is None


def test_document_regions_bound_large_documents() -> None:
    parents = [{"chunk_id": f"p{i}", "summary": f"Section {i} explains topic number {i} with distinct detail {i}."}
               for i in range(40)]
    out = compile_document(parents, doc_id="d")
    assert out.coverage["regions"] == 12 and len(out.sentences) <= 12
    assert out.coverage["uncovered"] == []
    assert len(out.summary) <= 1600
    firsts = sorted({s["child_index"] for s in out.sentences})
    assert firsts[0] < 4 and firsts[-1] > 35              # early and late regions represented


def test_section_summary_is_hard_bounded() -> None:
    long = " ".join(f"Sentence number {i} about distinct firewall topic {i} and its very specific detail." for i in range(20))
    out = _compile(long, long.replace("firewall", "router"), long.replace("firewall", "switch"), long.replace("firewall", "proxy"))
    assert len(out.summary) <= SECTION_MAX_CHARS


def test_ocr_garbage_sentences_never_selected() -> None:
    garbage = "La one ae ee ew ee er ee Pe ee ee ee ee ee ee ee See STi er ee ee et ee ee ee Caren ee wert ter Te."
    prose = "Views are virtual tables whose definitions act as schema objects."
    out = _compile(garbage + " " + prose)
    assert out.summary == prose
    assert structural_quality(garbage) == 0.0


def test_keywords_skip_digits_and_bigram_fragments() -> None:
    text = ("Social engineering attacks rely on social engineering tricks. The 2019-07-11 capture "
            "shows social engineering again on 2019-07-11 and 2019-07-11.")
    out = compile_section(_children(text, text, text), parent_id="p")
    assert "2019-07-11" not in out.keywords
    assert "social engineering" in out.keywords
    assert "social" not in out.keywords and "engineering" not in out.keywords


def test_summarizable_roles_and_parent_rule() -> None:
    assert is_summarizable(None) and is_summarizable(ROLE_BODY)
    assert not is_summarizable(ROLE_OUTPUT) and not is_summarizable(ROLE_CODE) and not is_summarizable(ROLE_NOISE_OCR)
    assert parent_role([ROLE_OUTPUT, ROLE_OUTPUT])[0] == ROLE_OUTPUT
    assert parent_role([ROLE_OUTPUT, ROLE_BODY])[0] == ROLE_BODY
    assert parent_role([ROLE_NOISE_OCR, ROLE_OUTPUT])[0] == ROLE_OUTPUT


def test_units_without_prose_are_reported_not_counted_as_starved() -> None:
    garbage = "La one ae ee ew ee er ee Pe ee ee ee ee ee ee ee See STi er ee ee et ee ee ee Caren."
    out = _compile(C1, garbage)
    assert out.coverage["uncovered"] == []
    assert out.coverage["no_prose_units"] == ["c1"]
    assert out.coverage["units_covered"] == 1


def test_keywords_come_from_prose_only() -> None:
    debris = "Eee eee rere eee eee rere ee oe ee eee rere."
    out = compile_section(_children(C1 + "\n" + debris, C2 + " " + debris, C3 + " " + debris), parent_id="p")
    assert not any(k in ("eee", "rere", "eee eee") for k in out.keywords)


def test_question_stems_rank_below_explanations() -> None:
    text = ("Which of the following tools captures packets on a mirror port for analysis? "
            "Wireshark captures packets on the mirror port for analysis.")
    out = compile_section(_children(text), parent_id="p", max_sentences=1, max_chars=200)
    assert out.summary.startswith("Wireshark captures")
