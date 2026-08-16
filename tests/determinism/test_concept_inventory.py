"""Pure determinism tests for the E5B deterministic concept inventory.

No stores, no sidecars, no I/O — the layer must be a pure function of
its inputs. These tests run in the regular unit suite.
"""
from __future__ import annotations

import hashlib
import re

from polymath_shared.concept_inventory import (
    DOC_BUDGET_GRID,
    SECTION_BUDGET_GRID,
    _pre_filter,
    apply_overlap_policy,
    concept_id,
    document_inventory,
    enriched_representation,
    generate_candidates,
    normalize_concept_v1,
    section_inventory,
)


def chunkify(text: str) -> list[dict]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 20]
    return [
        {
            "chunk_id": "chunk_" + hashlib.sha256(s.encode()).hexdigest()[:16],
            "text": s,
            "summary": "",
        }
        for s in sents
    ]


SAMPLE = (
    "Metacognitive monitoring refers to judgments of learning accuracy. "
    "Working-memory demands reduce processing fluency. Retrieval practice "
    "improves retention. Metacognitive monitoring and control appear in the "
    "title, and cognitive load interacts with working-memory resources."
)


def inventory_json(chunks, budget=8):
    return [
        {
            "id": c.concept_id,
            "norm": c.normalized,
            "surfaces": c.surfaces,
            "occs": sorted((o.chunk_id, o.char_start, o.surface) for o in c.occurrences),
        }
        for c in document_inventory(chunks, budget=budget)
    ]


def test_normalization_hyphen_equivalence():
    assert normalize_concept_v1("working-memory") == normalize_concept_v1("working memory")
    assert normalize_concept_v1("Self-Regulated Learning") == normalize_concept_v1("self regulated learning")
    assert normalize_concept_v1("  ﬁle  ") == "file"  # NFKC compatibility + collapse
    assert normalize_concept_v1("ＡＴＬＡＳ") == "atlas"  # NFKC fullwidth fold
    assert normalize_concept_v1("a/b") == normalize_concept_v1("a b")  # slash equivalence


def test_concept_identity_is_content_derived():
    assert concept_id("working memory") == concept_id("working-memory")
    assert concept_id("working memory") != concept_id("working memory x")
    assert concept_id("a").startswith("concept_")


def test_budget_grids_frozen():
    assert DOC_BUDGET_GRID == (4, 8, 12)
    assert SECTION_BUDGET_GRID == (3, 6, 8)


def test_candidate_generation_deterministic_and_offset_consistent():
    chunks = chunkify(SAMPLE)
    a = generate_candidates(chunks[0]["chunk_id"], chunks[0]["text"])
    b = generate_candidates(chunks[0]["chunk_id"], chunks[0]["text"])
    assert [(c.concept_id, c.normalized, c.surfaces) for c in a] == \
           [(c.concept_id, c.normalized, c.surfaces) for c in b]
    for c in a:
        for o in c.occurrences:
            assert chunks[0]["text"][o.char_start:o.char_end] == o.surface


def test_order_independence_shuffled_chunks():
    chunks = chunkify(SAMPLE)
    perm = [chunks[2], chunks[0], chunks[1], chunks[3]] if len(chunks) >= 4 else chunks[::-1]
    assert inventory_json(chunks) == inventory_json(perm)


def test_concurrent_repeated_runs_identical():
    from concurrent.futures import ThreadPoolExecutor
    chunks = chunkify(SAMPLE)
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda _: inventory_json(chunks), range(4)))
    assert all(r == results[0] for r in results)


def test_no_cross_call_state_in_overlap_policy():
    chunks = chunkify(SAMPLE)
    cands = []
    for ch in chunks:
        cands.extend(generate_candidates(ch["chunk_id"], ch["text"]))
    a = apply_overlap_policy(cands)
    b = apply_overlap_policy(cands)
    assert [c.concept_id for c in a] == [c.concept_id for c in b]
    # a second, unrelated candidate list must not be influenced by the first
    other = generate_candidates("chunk_x", "cognitive load theory studies cognitive load effects")
    c1 = apply_overlap_policy(other)
    c2 = apply_overlap_policy(other)
    assert [c.concept_id for c in c1] == [c.concept_id for c in c2]


def test_budget_bounds_respected():
    chunks = chunkify(SAMPLE)
    for b in DOC_BUDGET_GRID:
        assert len(document_inventory(chunks, budget=b)) <= b
    for b in SECTION_BUDGET_GRID:
        assert len(section_inventory(chunks, budget=b)) <= b


def test_enriched_representation_is_deterministic():
    chunks = chunkify(SAMPLE)
    inv = document_inventory(chunks, budget=4)
    e1 = enriched_representation("summary text", inv)
    e2 = enriched_representation("summary text", document_inventory(chunks, budget=4))
    assert e1 == e2
    assert "[KEY CONCEPTS]" in e1


def test_verb_fragment_rejected_gold_compounds_kept():
    chunks = chunkify(SAMPLE)
    raw = [c for ch in chunks for c in generate_candidates(ch["chunk_id"], ch["text"])]
    kept = apply_overlap_policy(_pre_filter(raw))
    norms = {c.normalized for c in kept}
    assert "metacognitive monitoring" in norms
    assert "working memory" in norms or "retrieval practice" in norms
    assert not any("refers" in n.split() for n in norms)
