"""Entity admission identity allocation (E2/C1.1, entity-admission-v1.1).

Deterministic, model-free reference classification and identity
allocation. These are the production rules wired at the identity
boundary in build_candidates / _allocate_parse_entity.

Rules under test:
  GLOBAL          byte-compatible with canonical_entity_id
  CORPUS_SCOPED   merges within a corpus, splits across corpora
  DOCUMENT_SCOPED distinct per document, stable within a document
  MENTION_ONLY    stable per span, distinct across spans
"""
from __future__ import annotations

import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan  # noqa: E402
from polymath_shared.entity_admission import allocate_entity_id, decide  # noqa: E402
from polymath_shared.rulepack.compiler import canonical_entity_id  # noqa: E402
from workers.candidates import SentenceSlice, build_candidates  # noqa: E402


def _alloc(surface, ctype, *, corpus="c1", doc="d1", chunk="k1", start=0, end=None):
    return allocate_entity_id(
        surface, ctype.value, corpus_id=corpus, doc_id=doc, chunk_id=chunk,
        span_start=start, span_end=end if end is not None else start + len(surface),
    )


def test_global_byte_compat_with_canonical_entity_id():
    for surface in ("Acme Corp", "Polaris", "Sarah", "M3 chip"):
        d = _alloc(surface, CoreType.ORGANIZATION if surface == "Acme Corp" else
                   CoreType.PERSON if surface == "Sarah" else CoreType.TECHNOLOGY)
        if surface != "Acme Corp":
            continue
        assert d.reference_class == "GLOBAL"
        assert d.mention_id == canonical_entity_id(CoreType.ORGANIZATION, surface)


def test_global_id_normalizes_whitespace_like_canonical():
    d = _alloc("  Acme   Corp ", CoreType.ORGANIZATION)
    assert d.mention_id == canonical_entity_id(CoreType.ORGANIZATION, "Acme Corp")


def test_corpus_scoped_merges_within_corpus():
    a = _alloc("vector index", CoreType.TECHNOLOGY, corpus="c1", doc="d1")
    b = _alloc("vector index", CoreType.TECHNOLOGY, corpus="c1", doc="d2",
               start=17, end=29)
    assert a.reference_class == "CORPUS_SCOPED"
    assert a.mention_id == b.mention_id


def test_corpus_scoped_splits_across_corpora_and_types():
    a = _alloc("vector index", CoreType.TECHNOLOGY, corpus="c1")
    b = _alloc("vector index", CoreType.TECHNOLOGY, corpus="c2")
    c = _alloc("vector index", CoreType.CONCEPT, corpus="c1")
    assert a.mention_id != b.mention_id
    assert a.mention_id != c.mention_id


def test_document_scoped_stable_within_doc_distinct_across_docs():
    a = _alloc("our engine", CoreType.TECHNOLOGY, doc="d1", start=0, end=10)
    b = _alloc("our engine", CoreType.TECHNOLOGY, doc="d1", start=30, end=40)
    c = _alloc("our engine", CoreType.TECHNOLOGY, doc="d2", start=0, end=10)
    assert a.reference_class == "DOCUMENT_SCOPED"
    assert a.mention_id == b.mention_id
    assert a.mention_id != c.mention_id


def test_mention_only_stable_per_span_distinct_across_spans():
    a = _alloc("the system", CoreType.TECHNOLOGY, start=0, end=10)
    b = _alloc("the system", CoreType.TECHNOLOGY, start=0, end=10)
    c = _alloc("the system", CoreType.TECHNOLOGY, start=40, end=50)
    assert a.reference_class == "MENTION_ONLY"
    assert a.mention_id.startswith("mention_")
    assert a.mention_id == b.mention_id
    assert a.mention_id != c.mention_id


def test_decide_class_table():
    cases = [
        ("AcmeCorp", "GLOBAL"),
        ("TensorRT 8.5", "GLOBAL"),
        ("vector index", "CORPUS_SCOPED"),
        ("our engine", "DOCUMENT_SCOPED"),
        ("the system", "MENTION_ONLY"),
    ]
    for surface, expected in cases:
        d = decide(surface, "TECHNOLOGY", 0.9)
        assert d.reference_class == expected, f"{surface!r} -> {d.reference_class}"


def test_build_candidates_allocates_admission_identity():
    """The production boundary: build_candidates must allocate ids
    through the admission layer, not blanket canonical_entity_id."""
    from polymath_shared.rulepack import load_rule_pack

    pack = load_rule_pack()
    text = "AcmeCorp runs on the vector index."
    chunk = "k1"
    entities = [
        EntitySpan(doc_id="d1", chunk_id=chunk, start=0, end=8, text="AcmeCorp",
                   core_type=CoreType.ORGANIZATION, score=0.9, extractor_version="t"),
        EntitySpan(doc_id="d1", chunk_id=chunk, start=17, end=34,
                   text="the vector index", core_type=CoreType.TECHNOLOGY,
                   score=0.9, extractor_version="t"),
    ]
    evidence = [EvidenceSpan(chunk_id=chunk, start=9, end=13, text="runs on",
                             evidence_class="usage_application",
                             trigger_lemma="run", score=0.9, extractor_version="t")]
    sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                       entities=entities, evidence=evidence, parse=None)
    cands = build_candidates([sl], doc_id="d1", corpus_id="c1",
                             ontology_profile="core", extractor_version="t",
                             rule_pack=pack, enrich=False)
    assert cands, "expected at least one candidate"
    subject_id = cands[0].subject.resolved_entity_id
    object_id = cands[0].object.resolved_entity_id
    assert subject_id == canonical_entity_id(CoreType.ORGANIZATION, "AcmeCorp")
    expected_obj = _alloc("the vector index", CoreType.TECHNOLOGY,
                          corpus="c1", doc="d1", chunk=chunk, start=17, end=34)
    assert object_id == expected_obj.mention_id
    assert object_id.startswith("entc_")
