"""S4b — PRODUCTION-WIRING-GATE-V1: one admission per mention.

Invariant (settled in REFERENTIAL-ADMISSION-V2-PLAN.md, S4 SETTLEMENT):

    "Admission is computed once per mention interpretation. Every downstream
     representation carries the resulting identity; none recomputes it."

Two independent admissions of the same span can disagree — that is a second
semantic authority, which the wiring gate forbids. These tests hold the
structural property (parse filling is a pure consumer) and the observable
property (every consumer yields the same id for the same span).
"""
import ast
import inspect
from pathlib import Path

import pytest

from polymath_shared.contracts import CoreType, EntitySpan
from polymath_shared.execution import SEMANTIC_CONTRACT_V1_1
from workers.candidates import SentenceSlice, _allocate
from workers.extract_worker import (
    _allocate_identities,
    _allocate_parse_entity,
    _fill_parse_entities,
    _span_identity_key,
)

CORPUS = "s4b-gate"
DOC = "doc-1"


def _slice() -> SentenceSlice:
    text = "  Ada Lovelace joined the Analytical Engine project in London."
    spans = [
        EntitySpan(doc_id=DOC, chunk_id="c0", start=2, end=13,
                   text="Ada Lovelace", core_type=CoreType.PERSON,
                   score=0.9, extractor_version="test"),
        EntitySpan(doc_id=DOC, chunk_id="c0", start=25, end=42,
                   text="Analytical Engine", core_type=CoreType.ORGANIZATION,
                   score=0.8, extractor_version="test"),
        EntitySpan(doc_id=DOC, chunk_id="c0", start=54, end=60,
                   text="London", core_type=CoreType.LOCATION,
                   score=0.7, extractor_version="test"),
    ]
    return SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                         entities=spans, evidence=[], parse=None,
                         sentence_index=0)


def test_parse_filling_never_computes_admission():
    """_allocate_parse_entity is a CONSUMER: it may not call any admission
    authority. If this fails, a second semantic authority has re-entered the
    parse path and the two ids can silently diverge."""
    tree = ast.parse(inspect.getsource(_allocate_parse_entity))
    called = {
        n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    forbidden = {"decide", "decide_v1_1_historical", "interpret_admission",
                 "allocate_entity_id", "classify"}
    assert not (called & forbidden), (
        f"_allocate_parse_entity recomputes admission via {called & forbidden}")


def test_every_consumer_agrees_on_the_same_span():
    """candidate entity_id == parse entity_id, for every proposed span."""
    sl = _slice()
    identities = _allocate_identities([({'chunk_id': 'c0', 'text': sl.text}, sl)],
                                    CORPUS, DOC,
                                    contract_version=SEMANTIC_CONTRACT_V1_1)

    for span in sl.entities:
        from_map = identities[_span_identity_key(span, CORPUS)].entity_id
        from_candidates = _allocate(span, sl, DOC, CORPUS, identities)
        from_parse = _allocate_parse_entity(span, CORPUS, {}, identities)
        assert from_map == from_candidates == from_parse, (
            f"identity disagreement on {span.text!r}: "
            f"map={from_map} candidates={from_candidates} parse={from_parse}")


def test_allocation_is_idempotent_per_span():
    """A span appearing in two slices allocates once, not twice."""
    sl = _slice()
    ident_once = _allocate_identities([({'chunk_id': 'c0', 'text': sl.text}, sl)],
                                    CORPUS, DOC,
                                    contract_version=SEMANTIC_CONTRACT_V1_1)
    ident_twice = _allocate_identities(
        [({'chunk_id': 'c0', 'text': sl.text}, sl)] * 2, CORPUS, DOC,
        contract_version=SEMANTIC_CONTRACT_V1_1)
    assert ident_once == ident_twice
    assert len(ident_twice) == len(sl.entities)


def test_parse_records_are_filled_from_the_map_only():
    """With no identities map, filling assigns NOTHING — it cannot invent an
    id of its own. This is what makes the map the single authority."""
    sl = _slice()
    parse = {"subject": {"token_text": "Ada Lovelace", "head_text": "joined"}}
    _fill_parse_entities(parse, sl.entities, CORPUS, None)
    assert "entity_id" not in parse["subject"]

    identities = _allocate_identities([({'chunk_id': 'c0', 'text': sl.text}, sl)],
                                    CORPUS, DOC,
                                    contract_version=SEMANTIC_CONTRACT_V1_1)
    _fill_parse_entities(parse, sl.entities, CORPUS, identities)
    assert parse["subject"]["entity_id"] == _allocate(sl.entities[0], sl, DOC, CORPUS, identities)


def test_slices_construction_does_not_allocate():
    """_slices() runs BEFORE syntax exists (S4a ordering), so it must not be
    an admission authority under a syntax-dependent contract."""
    src = Path("workers/workers/extract_worker.py").read_text()
    body = src[src.index("def _slices("):]
    body = body[:body.index("\ndef ", 1)]
    assert "_fill_parse_entities" not in body, (
        "_slices() allocates parse entity ids before syntax is available")
