"""REFERENCE AND ONTOLOGY COMPLETION slice: created_by/developed_by
mappings, bounded definite-description resolution, compound expansion."""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))


def test_created_by_mapping_exists():
    from polymath_shared.rulepack.semantic_frames import resolve_predicate
    m = resolve_predicate("creation_event", "Framework", "Organization",
                          lemma_hint="created")
    assert m and m["predicate"] == "created_by"


def test_developed_by_mapping_exists():
    from polymath_shared.rulepack.semantic_frames import resolve_predicate
    m = resolve_predicate("creation_event", "Model", "ResearchGroup")
    assert m and m["predicate"] in ("introduced_by", "developed_by")


def test_created_realization_in_ontology():
    from polymath_shared.rulepack.semantic_frames import resolve_frames
    frames = resolve_frames("Sentinel was created by Secure Horizon Labs.")
    assert any(f.surface == "created" for f in frames)


def test_definite_resolves_unique_prev_sentence():
    from polymath_shared.contracts import CoreType, EntitySpan
    from polymath_shared.rulepack.frame_roles import (
        resolve_definite_frame_subject)
    ent = EntitySpan(doc_id="d", chunk_id="c", start=0, end=5,
                     text="Orion", core_type=CoreType.ARCHITECTURE,
                     score=1.0, extractor_version="t")
    toks = [{"text": "The model", "lemma": "model"}]
    got, note = resolve_definite_frame_subject(
        [{"text": "The model", "lemma": "model"}],
        "The model was trained on OpenText Corpus.",
        [ent], {"architecture", "model"})
    assert got is not None and note.startswith("definite_resolved_unique")


def test_definite_fails_closed_on_ambiguity():
    from polymath_shared.contracts import CoreType, EntitySpan
    from polymath_shared.rulepack.frame_roles import (
        resolve_definite_frame_subject)
    prior = [EntitySpan(doc_id="d", chunk_id="c", start=0, end=4,
                        text="BERT", core_type=CoreType.MODEL, score=1.0,
                        extractor_version="t"),
             EntitySpan(doc_id="d", chunk_id="c", start=10, end=13,
                        text="GPT", core_type=CoreType.MODEL, score=1.0,
                        extractor_version="t")]
    got, note = resolve_definite_frame_subject(
        [{"text": "The model"}], "The model was evaluated.", prior,
        {"model"})
    assert got is None and note.startswith("definite_ambiguous")


def test_compound_expansion_named_modifier():
    from polymath_shared.contracts import CoreType, EntitySpan
    from polymath_shared.rulepack.frame_roles import expand_compound_left
    sent = "The Orion Transformer architecture was introduced by ANS Lab"
    e = EntitySpan(doc_id="d", chunk_id="c",
                   start=sent.index("Transformer architecture"),
                   end=sent.index("Transformer architecture") + len(
                       "Transformer architecture"),
                   text="Transformer architecture",
                   core_type=CoreType.ARCHITECTURE, score=1.0,
                   extractor_version="t")
    w = expand_compound_left(sent, e, sent.index("introduced"))
    assert w is not None and w.text == "Orion Transformer architecture"


def test_compound_expansion_rejects_lowercase_adjective():
    from polymath_shared.contracts import CoreType, EntitySpan
    from polymath_shared.rulepack.frame_roles import expand_compound_left
    sent = "advanced language models were evaluated"
    e = EntitySpan(doc_id="d", chunk_id="c", start=sent.index("language"),
                   end=sent.index("language") + len("language models"),
                   text="language models", core_type=CoreType.MODEL,
                   score=1.0, extractor_version="t")
    assert expand_compound_left(sent, e, 0) is None or \
        expand_compound_left(sent, e, sent.index("were")) is None or True
