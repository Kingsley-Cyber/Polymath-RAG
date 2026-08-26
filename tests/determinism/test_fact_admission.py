"""POLYMATH-FACT-ADMISSION-V1 development suite.

Every case is drawn from a mechanism the forensic pass actually
measured on the 25-book corpus (FINAL_FORENSIC_REPORT.md §7), or is the
control that proves the gate does not over-reject.

Parses are hand-built token fixtures rather than live spaCy calls: the
gates are pure functions of the persisted syntax-evidence-v1 shape, so
fixing the shape here tests the gate and not the parser.
"""
import pytest

from polymath_shared.fact_admission import (
    FactContext, PASS, QUALIFY, REJECT, admit,
    f2_region, f3_endpoints, f4_assertion, f5_predicate_evidence,
    f6_signature, f7_direction, f8_direct_support,
)
from polymath_shared.rulepack.compiler import load_rule_pack
from polymath_shared.source_region import (
    BIBLIOGRAPHY, BODY_PROSE, CAPTION, CODE_OR_CONFIG, HEADING, INDEX,
    TABLE_OF_CONTENTS, classify_chunk, region_at,
)


@pytest.fixture(scope="module")
def pack():
    return load_rule_pack()


def tok(i, text, pos, dep, head_i, char_start, lemma=None):
    return {"i": i, "text": text, "pos": pos, "dep": dep, "head_i": head_i,
            "char_start": char_start, "char_end": char_start + len(text),
            "lemma": (lemma or text).lower()}


def ctx(**kw):
    base = dict(
        doc_id="doc_1", chunk_id="chunk_1", predicate="uses",
        subject_entity_id="ent_a", object_entity_id="ent_b",
        subject_type="Organization", object_type="Technology",
        subject_admission_class="GLOBAL", object_admission_class="GLOBAL",
        subject_surface="Acme", object_surface="Kubernetes",
        trigger_lemma="use", trigger_surface="uses",
        evidence_class="usage_application",
        subject_start=0, subject_end=4,
        evidence_start=5, evidence_end=9,
        object_start=10, object_end=20,
        chunk_text="Acme uses Kubernetes in production.",
        region=BODY_PROSE, scope={}, sentence_start=0,
    )
    base.update(kw)
    return FactContext(**base)


ACME_USES_K8S_PARSE = {"tokens": [
    tok(0, "Acme", "PROPN", "nsubj", 1, 0),
    tok(1, "uses", "VERB", "ROOT", 1, 5, "use"),
    tok(2, "Kubernetes", "PROPN", "dobj", 1, 10),
]}


# --------------------------------------------------------------------------
# REGION
# --------------------------------------------------------------------------

def test_region_body_prose_is_licensed(pack):
    assert f2_region(ctx(region=BODY_PROSE), pack).outcome == PASS


@pytest.mark.parametrize("region,reason", [
    (BIBLIOGRAPHY, "REGION_BIBLIOGRAPHY"),
    (INDEX, "REGION_INDEX"),
    (TABLE_OF_CONTENTS, "REGION_TOC"),
    (CAPTION, "REGION_CAPTION"),
    (HEADING, "REGION_HEADING"),
    (CODE_OR_CONFIG, "REGION_CODE"),
])
def test_unsafe_regions_cannot_assert_relations(pack, region, reason):
    v = f2_region(ctx(region=region), pack)
    assert v.outcome == REJECT and v.reason == reason


def test_classify_bibliography_from_real_shape():
    # the smq3 reference list that produced alias_of(nakamura, nomoto)
    text = ("Nakamura, H., Tanaka, A., Nomoto, Y., Ueno, Y., & Nakayama, Y. "
            "~2000!. Activation of fronto-limbic system. Keio J Med.\n"
            "Ingvar, M., Ghatan, P. ~1998!. Regional cerebral blood flow.\n"
            "Mathew, R., Wilson, W. ~1992!. Regional cerebral blood flow.\n"
            "Volpe, B., & Swett, C. ~1970!. Social behavior deficits.")
    assert classify_chunk(text) == BIBLIOGRAPHY


def test_classify_index_from_real_shape():
    # the Sikorski index page that produced part_of(process, ida pro)
    text = ("dialog in Process Monitor, 484\n"
            "exploits, 245\n"
            "filters explorer.exe in procmon, 44–46\n"
            "code search for, 732\n"
            "in Wireshark, 53\n"
            "writing path into process, 588")
    assert classify_chunk(text) == INDEX


def test_classify_toc_and_code():
    toc = ("Introduction .......... 1\n"
           "Chapter 1 Networking ......... 12\n"
           "Chapter 2 Sensors ......... 40\n"
           "Chapter 3 Detection ......... 88\n"
           "Index ......... 300")
    assert classify_chunk(toc) == TABLE_OF_CONTENTS
    code = ("af-packet:\n"
            "  - interface: eth01\n"
            "    cluster-id: 99\n"
            "rule-files:\n"
            '  - "*.rules"')
    assert classify_chunk(code) == CODE_OR_CONFIG


def test_caption_detected_at_span_level_inside_body_chunk():
    text = ("The service denormalizes user records.\n"
            "Figure 4-7. A User is denormalized based on location.\n"
            "This reduces load on the data store.")
    cap_off = text.index("A User")
    assert region_at(text, cap_off, cap_off + 6) == CAPTION
    body_off = text.index("The service")
    assert region_at(text, body_off, body_off + 11) == BODY_PROSE


def test_layout_evidence_outranks_structure():
    text = "Applied Network Security Monitoring"
    assert region_at(text, 0, 7, layout_spans=[("heading", 0, 40)],
                     chunk_char_start=0) == HEADING


# --------------------------------------------------------------------------
# ENDPOINTS
# --------------------------------------------------------------------------

def test_durable_eligible_endpoints_pass(pack):
    assert f3_endpoints(ctx(parse=ACME_USES_K8S_PARSE), pack).outcome == PASS


def test_non_durable_endpoint_rejected(pack):
    v = f3_endpoints(ctx(subject_entity_id="mention_abc"), pack)
    assert v.outcome == REJECT and v.reason == "ENDPOINT_SUBJ_NOT_DURABLE"


def test_mention_only_admission_class_rejected(pack):
    v = f3_endpoints(ctx(object_admission_class="MENTION_ONLY"), pack)
    assert v.outcome == REJECT and v.reason == "ENDPOINT_OBJ_INELIGIBLE"


def test_pronoun_endpoint_rejected_on_grammar_not_wordlist(pack):
    """Harbor minted CORPUS_SCOPED ids for 'we'/'they'/'you'. They are
    durable AND graph-eligible, so only grammar stops them."""
    parse = {"tokens": [
        tok(0, "We", "PRON", "nsubj", 1, 0),
        tok(1, "use", "VERB", "ROOT", 1, 3, "use"),
        tok(2, "CORBA", "PROPN", "dobj", 1, 7),
    ]}
    v = f3_endpoints(ctx(
        subject_entity_id="entc_we", subject_admission_class="CORPUS_SCOPED",
        subject_surface="We", chunk_text="We use CORBA for messaging.",
        subject_start=0, subject_end=2, evidence_start=3, evidence_end=6,
        object_start=7, object_end=12, parse=parse), pack)
    assert v.outcome == REJECT and v.reason == "ENDPOINT_SUBJ_PRONOMINAL"


def test_endpoint_gate_abstains_from_grammar_without_parse(pack):
    """No parse => no grammatical claim. The semantic test still runs."""
    assert f3_endpoints(ctx(parse=None), pack).outcome == PASS


def test_self_edge_rejected(pack):
    v = f3_endpoints(ctx(object_entity_id="ent_a"), pack)
    assert v.outcome == REJECT and v.reason == "ENDPOINT_SELF_EDGE"


# --------------------------------------------------------------------------
# ASSERTION MODE
# --------------------------------------------------------------------------

def test_plain_assertion_passes(pack):
    assert f4_assertion(ctx(parse=ACME_USES_K8S_PARSE), pack).outcome == PASS


@pytest.mark.parametrize("modal", ["might", "may", "could", "would"])
def test_epistemic_modal_blocks_assertion(pack, modal):
    """'an architect might make a decision to use React.js' produced an
    asserted acquired edge in the forensic sample."""
    parse = {"tokens": [
        tok(0, "An", "DET", "det", 1, 0),
        tok(1, "architect", "NOUN", "nsubj", 3, 3),
        tok(2, modal, "AUX", "aux", 3, 13, modal),
        tok(3, "use", "VERB", "ROOT", 3, 13 + len(modal) + 1, "use"),
        tok(4, "React", "PROPN", "dobj", 3, 13 + len(modal) + 5),
    ]}
    v = f4_assertion(ctx(
        subject_start=3, subject_end=12,
        evidence_start=13 + len(modal) + 1, evidence_end=13 + len(modal) + 4,
        object_start=13 + len(modal) + 5, object_end=13 + len(modal) + 10,
        parse=parse), pack)
    assert v.outcome == REJECT and v.reason == "MODALITY"


def test_deontic_modal_qualifies_not_asserts(pack):
    parse = {"tokens": [
        tok(0, "Teams", "NOUN", "nsubj", 2, 0),
        tok(1, "should", "AUX", "aux", 2, 6, "should"),
        tok(2, "use", "VERB", "ROOT", 2, 13, "use"),
        tok(3, "TLS", "PROPN", "dobj", 2, 17),
    ]}
    v = f4_assertion(ctx(subject_start=0, subject_end=5, evidence_start=13,
                         evidence_end=16, object_start=17, object_end=20,
                         parse=parse), pack)
    assert v.outcome == QUALIFY and v.reason == "MODALITY_DEONTIC"


def test_attitude_verb_blocks_assertion(pack):
    """'decide to use X' proposes; it does not report."""
    parse = {"tokens": [
        tok(0, "Acme", "PROPN", "nsubj", 1, 0),
        tok(1, "decided", "VERB", "ROOT", 1, 5, "decide"),
        tok(2, "to", "PART", "aux", 3, 13),
        tok(3, "use", "VERB", "xcomp", 1, 16, "use"),
        tok(4, "React", "PROPN", "dobj", 3, 20),
    ]}
    v = f4_assertion(ctx(subject_start=0, subject_end=4, evidence_start=16,
                         evidence_end=19, object_start=20, object_end=25,
                         parse=parse), pack)
    assert v.outcome == REJECT and v.reason == "IRREALIS"


@pytest.mark.parametrize("flag,reason", [
    ("negated", "NEG_SCOPE"),
    ("question", "INTERROGATIVE"),
    ("hypothetical", "MODALITY"),
    ("conditional", "MODALITY"),
])
def test_persisted_scope_flags_respected(pack, flag, reason):
    v = f4_assertion(ctx(scope={flag: True}), pack)
    assert v.outcome == REJECT and v.reason == reason


def test_speculative_and_attributed_qualify(pack):
    assert f4_assertion(ctx(scope={"speculative": True}), pack).outcome == QUALIFY
    assert f4_assertion(ctx(scope={"attributed": True}), pack).outcome == QUALIFY


# --------------------------------------------------------------------------
# PREDICATE EVIDENCE
# --------------------------------------------------------------------------

def test_valid_trigger_licenses_predicate(pack):
    assert f5_predicate_evidence(ctx(predicate="uses", trigger_lemma="use"),
                                 pack).outcome == PASS


def test_use_cannot_become_acquired(pack):
    """forensic: 'an architect might decide to use React.js' -> acquired."""
    v = f5_predicate_evidence(ctx(predicate="acquired", trigger_lemma="use",
                                  trigger_surface="use"), pack)
    assert v.outcome == REJECT
    assert v.reason in ("PRED_STRENGTHENED", "PRED_FRAME")


def test_write_in_cannot_become_created(pack):
    """forensic: 'an architect can write Java code in ArchUnit'
    -> created(architect, archunit). 'use'-class evidence, not creation."""
    v = f5_predicate_evidence(ctx(predicate="created", trigger_lemma="use"), pack)
    assert v.outcome == REJECT


def test_roll_out_cannot_become_developed(pack):
    """forensic: 'Large enterprises may roll out a Kerberos-based system'
    -> developed(large enterprises, active directory)."""
    v = f5_predicate_evidence(ctx(predicate="developed", trigger_lemma="use"), pack)
    assert v.outcome == REJECT


def test_weak_evidence_cannot_strengthen(pack):
    v = f5_predicate_evidence(ctx(predicate="owns", trigger_lemma="include"), pack)
    assert v.outcome == REJECT
    assert v.reason in ("PRED_STRENGTHENED", "PRED_FRAME")


# --------------------------------------------------------------------------
# SIGNATURE
# --------------------------------------------------------------------------

def test_licensed_signature_passes(pack):
    assert f6_signature(ctx(predicate="uses", subject_type="Organization",
                            object_type="Technology"), pack).outcome == PASS


def test_unlicensed_subject_type_rejected(pack):
    v = f6_signature(ctx(predicate="acquired", subject_type="Concept",
                         object_type="Organization"), pack)
    assert v.outcome == REJECT and v.reason == "SIGNATURE"


def test_untyped_endpoint_fails_closed(pack):
    v = f6_signature(ctx(subject_type=None), pack)
    assert v.outcome == REJECT and v.reason == "SIGNATURE_UNTYPED"


# --------------------------------------------------------------------------
# DIRECTION
# --------------------------------------------------------------------------

INCLUDE_PARSE = {"tokens": [
    tok(0, "High-level", "ADJ", "amod", 1, 0),
    tok(1, "languages", "NOUN", "nsubj", 2, 11, "language"),
    tok(2, "include", "VERB", "ROOT", 2, 21, "include"),
    tok(3, "C++", "PROPN", "dobj", 2, 29),
]}


def test_include_flips_part_of_when_grammar_places_the_part_second(pack):
    """forensic: 'High-level languages include C, C++' emitted
    part_of(high-level languages, c++) — inverted. The flip is licensed
    only because the parse shows `languages` is the syntactic subject
    (the whole) and `C++` the object (the part)."""
    v = f7_direction(ctx(predicate="part_of", trigger_lemma="include",
                         trigger_surface="include",
                         subject_type="Technology", object_type="Technology",
                         subject_start=0, subject_end=21,
                         evidence_start=21, evidence_end=28,
                         object_start=29, object_end=32,
                         chunk_text="High-level languages include C++.",
                         parse=INCLUDE_PARSE),
                     pack)
    assert v.outcome == PASS and v.flip is True


def test_inverse_trigger_without_grammar_refuses_rather_than_guessing(pack):
    """Iteration 1 flipped blindly and inverted four part_of edges. With
    no parse the orientation is unwitnessed, so nothing is asserted."""
    v = f7_direction(ctx(predicate="part_of", trigger_lemma="include",
                         trigger_surface="include",
                         subject_type="Technology", object_type="Technology",
                         parse=None), pack)
    assert v.outcome == REJECT and v.reason == "DIRECTION_UNWITNESSED"


def test_inverse_trigger_keeps_order_when_candidate_is_already_part_first(pack):
    """Same sentence, candidate built the other way round: subject is
    already the part, so no flip may be applied."""
    v = f7_direction(ctx(predicate="part_of", trigger_lemma="include",
                         trigger_surface="include",
                         subject_type="Technology", object_type="Technology",
                         subject_start=29, subject_end=32,
                         evidence_start=21, evidence_end=28,
                         object_start=0, object_end=21,
                         chunk_text="High-level languages include C++.",
                         parse=INCLUDE_PARSE),
                     pack)
    assert v.outcome == PASS and v.flip is False


def test_canonical_trigger_keeps_orientation(pack):
    v = f7_direction(ctx(predicate="part_of", trigger_lemma="part",
                         trigger_surface="part of",
                         subject_type="Product", object_type="Organization"),
                     pack)
    assert v.outcome == PASS and v.flip is False


def test_unlicensed_orientation_rejected(pack):
    v = f7_direction(ctx(predicate="part_of", trigger_lemma="mention",
                         trigger_surface="mention",
                         subject_type="Product", object_type="Product"), pack)
    assert v.outcome == REJECT and v.reason == "DIRECTION_UNLICENSED"


def test_flip_refused_when_flipped_signature_unlicensed(pack):
    parse = {"tokens": [
        tok(0, "Beta", "PROPN", "nsubjpass", 2, 0),
        tok(1, "was", "AUX", "auxpass", 2, 5, "be"),
        tok(2, "acquired", "VERB", "ROOT", 2, 9, "acquire"),
        tok(3, "by", "ADP", "agent", 2, 18),
        tok(4, "Insight", "PROPN", "pobj", 3, 21),
    ]}
    v = f7_direction(ctx(predicate="acquired", trigger_lemma="acquired by",
                         trigger_surface="acquired by",
                         subject_type="Organization", object_type="Concept",
                         subject_start=0, subject_end=4,
                         evidence_start=9, evidence_end=17,
                         object_start=21, object_end=28,
                         chunk_text="Beta was acquired by Insight.",
                         parse=parse),
                     pack)
    assert v.outcome == REJECT and v.reason in (
        "DIRECTION_FLIP_UNLICENSED", "DIRECTION_UNLICENSED",
        "DIRECTION_UNWITNESSED")


# --------------------------------------------------------------------------
# SPAN SUPPORT
# --------------------------------------------------------------------------

def test_direct_support_passes(pack):
    assert f8_direct_support(ctx(parse=ACME_USES_K8S_PARSE), pack).outcome == PASS


def test_cross_sentence_qualifies_never_asserts(pack):
    text = "PostgreSQL is the primary datastore. The service relies on it."
    v = f8_direct_support(ctx(
        chunk_text=text, subject_start=0, subject_end=10,
        evidence_start=text.index("relies"), evidence_end=text.index("relies") + 6,
        object_start=text.index("service"), object_end=text.index("service") + 7,
        parse=ACME_USES_K8S_PARSE), pack)
    assert v.outcome == QUALIFY and v.reason == "CROSS_SENTENCE"


def test_missing_parse_qualifies_rather_than_asserting(pack):
    v = f8_direct_support(ctx(parse=None), pack)
    assert v.outcome == QUALIFY and v.reason == "SPAN_SUPPORT"


# --------------------------------------------------------------------------
# CHAIN
# --------------------------------------------------------------------------

def test_clean_fact_is_admitted(pack):
    d = admit(ctx(parse=ACME_USES_K8S_PARSE, trigger_lemma="use"), pack)
    assert d.outcome == PASS, d


def test_chain_stops_at_first_reject_and_records_trace(pack):
    d = admit(ctx(region=INDEX, parse=ACME_USES_K8S_PARSE), pack)
    assert d.outcome == REJECT and d.gate == "F2_REGION"
    assert d.trace[0][0] == "F1_PROVENANCE" and d.trace[-1][0] == "F2_REGION"


def test_missing_provenance_fails_closed(pack):
    d = admit(ctx(subject_start=None), pack)
    assert d.outcome == REJECT and d.reason == "MISSING_INPUT"


def test_qualify_does_not_become_pass(pack):
    d = admit(ctx(scope={"speculative": True}, parse=ACME_USES_K8S_PARSE), pack)
    assert d.outcome == QUALIFY


def test_decision_is_deterministic(pack):
    c = ctx(parse=ACME_USES_K8S_PARSE)
    first = admit(c, pack)
    for _ in range(5):
        again = admit(c, pack)
        assert (again.outcome, again.reason, again.gate) == (
            first.outcome, first.reason, first.gate)


def test_policy_has_no_duplicate_predicate_keys():
    """YAML silently keeps the LAST duplicate key, so a redeclared
    predicate would quietly drop its earlier triggers. A name may repeat
    across sections (orientation vs predicate_strength) — only a repeat
    within one mapping is a defect, which is what this loader detects."""
    import pathlib

    import yaml

    class NoDuplicates(yaml.SafeLoader):
        pass

    def _strict(loader, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            assert key not in seen, f"duplicate policy key: {key}"
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    NoDuplicates.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _strict)
    raw = (pathlib.Path(__file__).parents[2] / "shared/polymath_shared"
           / "fact_admission_policy.yaml").read_text()
    yaml.load(raw, Loader=NoDuplicates)


def test_every_asymmetric_pack_predicate_has_orientation_policy(pack):
    """An asymmetric predicate with no orientation policy can never be
    asserted (F7 QUALIFYs it), so a missing entry silently costs recall."""
    from polymath_shared.fact_admission import policy
    declared = set(policy()["orientation"])
    missing = []
    for pid, rule in (pack.get("predicates") or {}).items():
        symmetry = ((rule.get("direction") or {}).get("symmetry") or "asymmetric")
        if symmetry != "symmetric" and pid not in declared:
            missing.append(pid)
    assert not missing, f"asymmetric predicates without orientation policy: {missing}"


# --------------------------------------------------------------------------
# SPOKEN-RELATION-ADAPTER-V1: created orientation completes the pack's
# own verb inventory (make/build were in created.verbs but not in the
# orientation policy — every make/build candidate died
# DIRECTION_UNLICENSED regardless of grammar).
# --------------------------------------------------------------------------

MADE_PARSE = {"tokens": [
    tok(0, "Facebook", "PROPN", "nsubj", 1, 0),
    tok(1, "made", "VERB", "ROOT", 1, 9, "make"),
    tok(2, "Andromeda", "PROPN", "dobj", 1, 14),
]}


def test_created_make_trigger_licenses_canonical_direction(pack):
    v = f7_direction(ctx(predicate="created", trigger_lemma="make",
                         trigger_surface="made",
                         subject_type="Organization",
                         object_type="Technology",
                         subject_surface="Facebook",
                         object_surface="Andromeda",
                         subject_start=0, subject_end=8,
                         evidence_start=9, evidence_end=13,
                         object_start=14, object_end=23,
                         chunk_text="Facebook made Andromeda.",
                         parse=MADE_PARSE), pack)
    assert v.outcome == PASS, (v.outcome, v.reason)


def test_created_make_contradicted_direction_still_rejects(pack):
    """The witness checks are untouched: an active clause that places
    the candidate's object in subject position still rejects."""
    v = f7_direction(ctx(predicate="created", trigger_lemma="make",
                         trigger_surface="made",
                         subject_type="Organization",
                         object_type="Technology",
                         subject_surface="Facebook",
                         object_surface="Andromeda",
                         # candidate order inverted vs the parse
                         subject_start=14, subject_end=23,
                         evidence_start=9, evidence_end=13,
                         object_start=0, object_end=8,
                         chunk_text="Facebook made Andromeda.",
                         parse=MADE_PARSE), pack)
    assert v.outcome == REJECT, (v.outcome, v.reason)
    assert v.reason == "DIRECTION_CONTRADICTED"
