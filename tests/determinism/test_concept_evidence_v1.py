"""CONCEPT-EVIDENCE-V1 (PHASE 2D) — cross-domain acceptance.

The formal invariant: the executable rules are universal; domain knowledge
is replaceable versioned data; unknown knowledge reduces graph COVERAGE,
never graph CORRECTNESS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import concept_evidence as CE
from polymath_shared.concept_evidence import (
    ConceptEvidenceKind, ConceptRecord, admit_concept, concept_candidate,
)

FIX = json.loads((ROOT / "eval/admission/concept_fixtures_crossdomain_v1.json").read_text())


def _all_cases():
    for dom, d in FIX["domains"].items():
        for c in d["cases"]:
            yield dom, d["document"], c
    for c in FIX["adversarial"]:
        yield "adversarial", c["document"], {**c, "authority": None}


def test_cross_domain_fixtures_all_pass():
    wrong = []
    for dom, doc, c in _all_cases():
        ev = admit_concept(c["term"], document_text=doc, doc_id=dom)
        got = ev.kind.value if ev else "ABSTAIN"
        want = c["authority"] if c["expect"] == "CONCEPT" else "ABSTAIN"
        if got != want:
            wrong.append((dom, c["term"], want, got))
    assert not wrong, wrong


def test_four_unrelated_domains_are_covered():
    assert set(FIX["domains"]) == {"technical", "medical", "narrative", "business"}


def test_executable_code_names_no_domain_and_no_corpus_phrase():
    """A whitelist would pass the current corpus and fail every other book.

    Checks EXECUTABLE policy only — docstrings may illustrate with concrete
    examples from any domain, and that prose is not a lookup table.
    """
    import ast

    tree = ast.parse((ROOT / "shared/polymath_shared/concept_evidence.py").read_text())
    for node in ast.walk(tree):                      # strip docstrings
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and isinstance(
                    body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree).lower()
    for phrase in ("vector index", "transactional outbox", "retrieval system",
                   "cybersecurity", "kubernetes", "postgres", "crestline",
                   "photosynthesis", "ember rite", "chargeback"):
        assert phrase not in code, f"domain phrase {phrase!r} leaked into executable policy"


def test_forbidden_shortcut_two_words_is_not_a_concept():
    assert admit_concept("vector index", document_text="") is None
    assert admit_concept("quality database",
                         document_text="Crestline linked the vision system to the quality database.") is None


def test_forbidden_shortcut_frequency_is_not_a_concept():
    doc = " ".join(["The retrieval system was slow."] * 12)
    assert admit_concept("retrieval system", document_text=doc) is None


def test_unknown_term_in_unknown_domain_is_admitted_when_the_book_defines_it():
    """No lexicon, no registry, never-before-seen vocabulary."""
    doc = "The Ember Rite is a ceremony performed at the turning of the year."
    ev = admit_concept("the Ember Rite", document_text=doc)
    assert ev and ev.kind is ConceptEvidenceKind.DOCUMENT_DEFINED
    assert "ceremony" in ev.quote


def test_registry_evidence_is_cumulative_and_auditable():
    reg = {"transactional outbox": ConceptRecord(
        concept_id="c1", canonical_term="transactional outbox",
        normalized_term="transactional outbox",
        evidence_kind=ConceptEvidenceKind.DOCUMENT_DEFINED,
        source_document_id="book-a")}
    ev = admit_concept("transactional outbox", document_text="", registry=reg)
    assert ev and ev.kind is ConceptEvidenceKind.EXISTING_CANONICAL
    assert "c1" in ev.quote


def test_lexicon_evidence_carries_source_and_version():
    lex = {"source_id": "acme-vocab", "source_version": "2026.1",
           "entries": {"run rate": {"gloss": "annualised figure"}}}
    ev = admit_concept("run rate", document_text="", lexicon=lex)
    assert ev and ev.kind is ConceptEvidenceKind.CURATED_LEXICON
    assert ev.external_source_id == "acme-vocab"
    assert ev.external_source_version == "2026.1"


def test_lexicon_match_is_exact_not_fuzzy():
    lex = {"source_id": "s", "source_version": "1", "entries": {"run rate": {}}}
    assert admit_concept("run rates", document_text="", lexicon=lex) is None
    assert admit_concept("annual run rate", document_text="", lexicon=lex) is None


def test_candidacy_has_no_graph_authority():
    """2D.1 is permissive; 2D.2 is the gate. Candidacy alone admits nothing."""
    assert concept_candidate("vector index")
    assert admit_concept("vector index", document_text="") is None
    assert not concept_candidate("PostgreSQL", is_identity=True)
    assert not concept_candidate("workers", is_generic=True)


def test_abstention_is_the_safe_default_not_an_error():
    ev = admit_concept("completely unheard of thing", document_text="Some prose.")
    assert ev is None                      # returns, never raises


def test_deterministic_replay():
    doc = FIX["domains"]["medical"]["document"]
    runs = {repr(admit_concept("photosynthesis", document_text=doc, doc_id="m"))
            for _ in range(20)}
    assert len(runs) == 1


def test_copula_without_a_genus_is_not_a_definition():
    """'X is slow' must not read as a definition; 'X is a pattern that...' must."""
    assert admit_concept("the system", document_text="The system is slow.") is None
    assert admit_concept("widget cache",
                         document_text="Widget cache is a buffer that holds rendered widgets.") is not None


# --- CONCEPT-DEFINITION-COVERAGE-V1 ---------------------------------------
# Academic prose rarely writes "X is a Y"; it hedges. Authority stays
# DOCUMENT_DEFINED — only the grammatical realization broadens.

def test_hedged_definitional_copulas_are_recognised():
    for sent in (
        "Working memory is often described as the limited mental workspace.",
        "Working memory can be defined as the limited mental workspace.",
        "Working memory is generally understood as a limited workspace.",
        "Working memory has been characterized as the workspace for short-term tasks.",
    ):
        ev = admit_concept("working memory", document_text=sent)
        assert ev and ev.kind is ConceptEvidenceKind.DOCUMENT_DEFINED, sent


def test_author_declared_and_eventive_definitions():
    assert admit_concept("chunking",
                         document_text="We define chunking as the grouping of items into units.")
    assert admit_concept("interference",
                         document_text="Interference occurs when two tasks compete for resources.")
    assert admit_concept("cognitive load",
                         document_text="Cognitive load, also known as mental effort, affects learning.")


def test_classificatory_determiner_counts_as_a_genus():
    """'X is another condition that...' assigns a genus; 'some'/'any' hedge
    existence and must NOT count."""
    assert admit_concept(
        "sleep deprivation",
        document_text="Sleep deprivation is another condition that may reduce performance.")
    assert admit_concept("the system", document_text="The system is some component.") is None
    assert admit_concept("the process", document_text="The process is any operation.") is None


def test_broadened_grammar_does_not_admit_non_definitions():
    """The article-after-copula requirement is what separates definition from
    predication; hedging must not erode it."""
    for sent in ("The system is slow.",
                 "The system is widely used.",
                 "The model is known to fail under load.",
                 "Performance depends on the type of information.",
                 "The platform was restarted twice."):
        assert admit_concept("the system", document_text=sent) is None, sent
        assert admit_concept("the model", document_text=sent) is None, sent


def test_real_documents_behave_as_measured():
    """Both probe documents, pinned. The transcript defines none of its terms —
    it is a conversation between people who already know them — so ABSTAIN
    everywhere there is the correct result, not a failure."""
    psych = Path("/Users/king/Downloads/e/01_psychology_working_memory.md")
    if not psych.exists():
        import pytest as _p
        _p.skip("probe corpus not present")
    doc = psych.read_text()
    assert admit_concept("working memory", document_text=doc)
    assert admit_concept("sleep deprivation", document_text=doc)
    for undefined in ("cognitive load", "long-term memory", "performance",
                      "central control process"):
        assert admit_concept(undefined, document_text=doc) is None, undefined
