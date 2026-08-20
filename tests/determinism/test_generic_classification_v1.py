"""GENERIC-CLASSIFICATION-V1 — a narrow ATTRIBUTION gate.

Corrects the system's EXPLANATION, not its behaviour: `Researchers` and
`regional dispatchers` were already refused, but recorded as UNKNOWN and
LOCAL_REFERENCE rather than GENERIC. If this gate ever changes what enters
the graph, its scope has exceeded the demonstrated defect.

Structural, never another noun blacklist — `researchers`, `dispatchers`,
`studies`, `findings` cannot all be anticipated, and the next book brings
fifty more.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.generic_classification import (
    GENERIC_CONTRACT, GenericEvidence, classify_generic,
)


def _t(pairs):
    out, pos = [], 0
    for i, p in enumerate(pairs):
        text, tag = p[0], p[1]
        lemma = p[2] if len(p) > 2 else text.lower()
        out.append({"i": i, "text": text, "pos": tag, "lemma": lemma,
                    "char_start": pos, "char_end": pos + len(text)})
        pos += len(text) + 1
    return out


# --- the four evidence families -------------------------------------------

def test_plural_common_noun_without_anchor_is_generic():
    for pairs in ([("Researchers", "NOUN", "researcher")],
                  [("workers", "NOUN", "worker")],
                  [("servers", "NOUN", "server")],
                  [("regional", "ADJ"), ("dispatchers", "NOUN", "dispatcher")]):
        d = classify_generic(" ".join(p[0] for p in pairs), tokens=_t(pairs))
        assert d.is_generic and d.evidence is GenericEvidence.PLURAL_COMMON_NOUN, pairs


def test_quantified_phrases_are_generic():
    for pairs in ([("Several", "ADJ", "several"), ("laboratory", "NOUN"), ("studies", "NOUN", "study")],
                  [("Two", "NUM", "two"), ("documents", "NOUN", "document")],
                  [("Every", "DET", "every"), ("accepted", "ADJ"), ("fact", "NOUN")]):
        d = classify_generic(" ".join(p[0] for p in pairs), tokens=_t(pairs))
        assert d.is_generic and d.evidence is GenericEvidence.QUANTIFIED_PHRASE, pairs


def test_bare_kind_term_is_generic():
    d = classify_generic("system", tokens=_t([("system", "NOUN")]))
    assert d.is_generic and d.evidence is GenericEvidence.BARE_KIND_TERM


def test_class_level_determiner_is_generic():
    """`a user` at class level. `any`/`every` are ALSO quantifiers and label
    as QUANTIFIED_PHRASE — both are generic, only the evidence name differs."""
    d = classify_generic("a user", tokens=_t([("a", "DET", "a"), ("user", "NOUN")]))
    assert d.is_generic and d.evidence is GenericEvidence.GENERIC_DETERMINER
    d2 = classify_generic("any server",
                          tokens=_t([("any", "DET", "any"), ("server", "NOUN")]))
    assert d2.is_generic and d2.evidence is GenericEvidence.QUANTIFIED_PHRASE


# --- adversarial controls: no identity/concept/constituted losses ----------

def test_proper_noun_anchor_blocks_generic():
    for pairs in ([("Researcher", "PROPN"), ("Technologies", "PROPN")],
                  [("West", "PROPN"), ("Coast", "PROPN"), ("Logistics", "PROPN"),
                   ("Consortium", "PROPN")]):
        assert not classify_generic(" ".join(p[0] for p in pairs), tokens=_t(pairs)).is_generic


def test_established_anchor_blocks_generic_even_when_the_tagger_misses_it():
    """spaCy tags `PostgreSQL` as ADV in `PostgreSQL databases`. The caller's
    established-anchor knowledge must still protect the span."""
    pairs = [("PostgreSQL", "ADV"), ("databases", "NOUN", "database")]
    assert classify_generic("PostgreSQL databases", tokens=_t(pairs)).is_generic
    assert not classify_generic("PostgreSQL databases", tokens=_t(pairs),
                                has_identity_anchor=True).is_generic


def test_singular_multiword_common_noun_is_not_generic():
    """`working memory` must remain available to the CONCEPT lane."""
    d = classify_generic("Working memory",
                         tokens=_t([("Working", "NOUN"), ("memory", "NOUN")]))
    assert not d.is_generic


def test_no_syntax_means_no_generic_claim():
    assert not classify_generic("Researchers", tokens=None).is_generic


def test_is_not_a_noun_blacklist():
    """None of the qualification surfaces may appear in executable policy."""
    import ast
    tree = ast.parse((ROOT / "shared/polymath_shared/generic_classification.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(
                    getattr(b[0], "value", None), ast.Constant) and isinstance(
                    b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    code = ast.unparse(tree).lower()
    for noun in ("researcher", "dispatcher", "worker", "server", "database",
                 "study", "finding", "document"):
        assert noun not in code, f"{noun!r} leaked into executable policy"


def test_deterministic():
    toks = _t([("Researchers", "NOUN", "researcher")])
    assert len({repr(classify_generic("Researchers", tokens=toks)) for _ in range(20)}) == 1


def test_contract_pinned():
    assert GENERIC_CONTRACT == "generic-classification-v1"
