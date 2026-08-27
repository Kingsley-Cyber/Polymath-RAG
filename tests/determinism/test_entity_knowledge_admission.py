"""ENTITY-KNOWLEDGE-ADMISSION-V1 development suite.

Every REJECT case is a class the 25-book forensics actually produced, and
every one is paired with a well-formed control that must still PASS —
because a gate that refuses everything is not a fix.
"""
import pytest

from polymath_shared.entity_knowledge_admission import (
    PASS, REJECT, EntityContext, admit_entity, e2_region, e3_span, e4_extent,
    e5_structural, e6_type, e7_durability,
)
from polymath_shared.source_region import (
    BIBLIOGRAPHY, BODY_PROSE, CAPTION, HEADING, INDEX,
)


def tok(i, text, pos, dep, head_i, char_start):
    return {"i": i, "text": text, "pos": pos, "dep": dep, "head_i": head_i,
            "char_start": char_start, "char_end": char_start + len(text),
            "lemma": text.lower()}


def ctx(**kw):
    base = dict(
        entity_id="ent_abc", surface="Kubernetes",
        normalized_surface="kubernetes", core_type="Technology",
        admission_class="GLOBAL", doc_id="doc1", chunk_id="chunk1",
        char_start=0, char_end=10, score=0.91,
        chunk_text="Kubernetes orchestrates containers.",
        region=BODY_PROSE, parse=None, sentence_start=0,
    )
    base.update(kw)
    return EntityContext(**base)


# --------------------------------------------------------------------------
# E1 provenance
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kw", [
    {"doc_id": None}, {"chunk_id": None}, {"char_start": None},
    {"surface": "  "}, {"entity_id": ""},
])
def test_missing_provenance_cannot_be_asserted(kw):
    d = admit_entity(ctx(**kw))
    assert d.outcome == REJECT and d.reason == "E_PROV"


def test_degenerate_span_refused():
    d = admit_entity(ctx(char_start=5, char_end=5))
    assert d.outcome == REJECT and d.reason == "E_PROV"


# --------------------------------------------------------------------------
# E2 region
# --------------------------------------------------------------------------

def test_body_prose_entity_is_admissible():
    assert e2_region(ctx()).outcome == PASS


@pytest.mark.parametrize("region,reason", [
    (BIBLIOGRAPHY, "E_REGION_BIBLIOGRAPHY"),
    (INDEX, "E_REGION_INDEX"),
    (CAPTION, "E_REGION_CAPTION"),
    (HEADING, "E_REGION_HEADING"),
])
def test_structural_regions_do_not_license_entities(region, reason):
    v = e2_region(ctx(region=region))
    assert v.outcome == REJECT and v.reason == reason


# --------------------------------------------------------------------------
# E3 span integrity — the `Pavlovian -> pavlov` class
# --------------------------------------------------------------------------

def test_span_that_starts_inside_a_word_is_refused():
    text = "the Soviets employed Pavlovian conditioning widely."
    start = text.index("Pavlovian")
    v = e3_span(ctx(surface="Pavlov", char_start=start,
                    char_end=start + len("Pavlov"), chunk_text=text,
                    core_type="Person"))
    assert v.outcome == REJECT and v.reason == "E_SPAN_CUTS_WORD"


def test_span_that_ends_inside_a_word_is_refused():
    text = "microservices architecture"
    v = e3_span(ctx(surface="micro", char_start=0, char_end=5, chunk_text=text))
    assert v.outcome == REJECT and v.reason == "E_SPAN_CUTS_WORD"


def test_whole_word_span_passes():
    text = "the Soviets employed Pavlov himself."
    start = text.index("Pavlov")
    v = e3_span(ctx(surface="Pavlov", char_start=start,
                    char_end=start + 6, chunk_text=text, core_type="Person"))
    assert v.outcome == PASS


def test_surface_disagreeing_with_its_offsets_is_refused():
    v = e3_span(ctx(surface="Docker", char_start=0, char_end=6,
                    chunk_text="Kubernetes orchestrates containers."))
    assert v.outcome == REJECT and v.reason == "E_SPAN_SURFACE_MISMATCH"


def test_span_outside_the_chunk_is_refused():
    v = e3_span(ctx(char_start=900, char_end=910))
    assert v.outcome == REJECT and v.reason == "E_SPAN_OUT_OF_RANGE"


# --------------------------------------------------------------------------
# E4 extent — adjectival propers
# --------------------------------------------------------------------------

def test_person_named_by_an_adjective_is_refused():
    """'Pavlovian conditioning' does not mention Pavlov."""
    text = "the Soviets employed Pavlovian conditioning."
    start = text.index("Pavlovian")
    parse = {"tokens": [
        tok(0, "the", "DET", "det", 1, 0),
        tok(1, "Soviets", "PROPN", "nsubj", 2, 4),
        tok(2, "employed", "VERB", "ROOT", 2, 12),
        tok(3, "Pavlovian", "ADJ", "amod", 4, start),
        tok(4, "conditioning", "NOUN", "dobj", 2, start + 10),
    ]}
    v = e4_extent(ctx(surface="Pavlovian", char_start=start,
                      char_end=start + 9, chunk_text=text,
                      core_type="Person", parse=parse))
    assert v.outcome == REJECT and v.reason == "E_EXTENT_ADJECTIVAL"


def test_proper_noun_person_passes_extent():
    text = "Ken Thompson created Unix."
    parse = {"tokens": [
        tok(0, "Ken", "PROPN", "compound", 1, 0),
        tok(1, "Thompson", "PROPN", "nsubj", 2, 4),
        tok(2, "created", "VERB", "ROOT", 2, 13),
        tok(3, "Unix", "PROPN", "dobj", 2, 21),
    ]}
    v = e4_extent(ctx(surface="Ken Thompson", char_start=0, char_end=12,
                      chunk_text=text, core_type="Person", parse=parse))
    assert v.outcome == PASS


def test_concept_headed_by_a_common_noun_is_unaffected():
    """Only NAMING classes are constrained; concepts head on common nouns."""
    text = "declarative configuration is preferred."
    parse = {"tokens": [
        tok(0, "declarative", "ADJ", "amod", 1, 0),
        tok(1, "configuration", "NOUN", "nsubj", 2, 12),
        tok(2, "is", "AUX", "ROOT", 2, 26),
    ]}
    v = e4_extent(ctx(surface="declarative configuration", char_start=0,
                      char_end=25, chunk_text=text, core_type="Concept",
                      parse=parse))
    assert v.outcome == PASS


def test_extent_abstains_without_a_parse():
    assert e4_extent(ctx(core_type="Person", parse=None)).outcome == PASS


# --------------------------------------------------------------------------
# E5 structural — the `Figure 4-7` class
# --------------------------------------------------------------------------

@pytest.mark.parametrize("surface", [
    "Figure 4-7", "figure 18-4", "Table 13.7", "Chapter 5", "Section 2.1",
    "Appendix B", "Listing 2-1", "Equation 3", "page 484", "Footnote 12",
    "Chapter 2 of this book", "this book", "the following section",
])
def test_document_structure_references_are_not_entities(surface):
    v = e5_structural(ctx(surface=surface, core_type="Document"))
    assert v.outcome == REJECT and v.reason == "E_STRUCT"


@pytest.mark.parametrize("surface", [
    "Table Mountain", "Chapter One Records", "Figure Eight Inc",
    "Kubernetes", "Apache Kafka", "Snort",
])
def test_real_names_containing_structural_words_survive(surface):
    assert e5_structural(ctx(surface=surface)).outcome == PASS


# --------------------------------------------------------------------------
# E6 / E7
# --------------------------------------------------------------------------

def test_unknown_class_fails_closed():
    v = e6_type(ctx(core_type="Sparkle"))
    assert v.outcome == REJECT and v.reason == "E_TYPE"


def test_missing_class_fails_closed():
    v = e6_type(ctx(core_type=None))
    assert v.outcome == REJECT and v.reason == "E_TYPE_MISSING"


def test_non_durable_identity_is_not_knowledge():
    v = e7_durability(ctx(entity_id="mention_abc"))
    assert v.outcome == REJECT and v.reason == "E_DURABLE"


def test_mention_only_admission_class_is_not_knowledge():
    v = e7_durability(ctx(admission_class="MENTION_ONLY"))
    assert v.outcome == REJECT and v.reason == "E_DURABLE_INELIGIBLE"


def test_pronoun_headed_entity_is_refused_on_grammar():
    """Harbor minted CORPUS_SCOPED ids for 'we'/'they'; only grammar
    stops them, and it is a POS fact rather than a stoplist."""
    text = "We use CORBA for messaging."
    parse = {"tokens": [
        tok(0, "We", "PRON", "nsubj", 1, 0),
        tok(1, "use", "VERB", "ROOT", 1, 3),
    ]}
    v = e7_durability(ctx(entity_id="entc_we", surface="We", char_start=0,
                          char_end=2, chunk_text=text, parse=parse,
                          admission_class="CORPUS_SCOPED"))
    assert v.outcome == REJECT and v.reason == "E_PRONOMINAL"


# --------------------------------------------------------------------------
# chain
# --------------------------------------------------------------------------

def test_clean_entity_is_admitted():
    assert admit_entity(ctx()).outcome == PASS


def test_first_reject_decides_and_trace_is_recorded():
    d = admit_entity(ctx(region=INDEX))
    assert d.outcome == REJECT and d.gate == "E2_REGION"
    assert d.trace[0][0] == "E1_PROVENANCE"
    assert d.trace[-1][0] == "E2_REGION"


def test_decision_is_deterministic():
    c = ctx()
    first = admit_entity(c)
    for _ in range(5):
        again = admit_entity(c)
        assert (again.outcome, again.reason, again.gate) == (
            first.outcome, first.reason, first.gate)
