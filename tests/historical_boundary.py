"""Test-only wrappers that pin the HISTORICAL admission contract.

After the S4c cutover, `build_candidates` is a consumer: it reads identities
decided once at the extract stage's admission boundary. A test that calls it
directly must therefore say which contract it means.

These tests predate admission-harbor-v2 and assert pre-V2 behaviour (role
direction, frame binding, observability neutrality). Pinning v1.1 keeps them
honest about what they cover, rather than silently reinterpreting them under
semantics they were never written against. v1.1 sets
`referential_surface == proposal_surface`, so the ids are byte-identical to
the pre-cutover ones and these tests still assert exactly what they did.

This is explicit per-execution contract pinning, NOT a fallback: nothing here
chooses a contract based on what happens to be available at runtime.
"""
from polymath_shared.execution import SEMANTIC_CONTRACT_V1_1


def _ids(slices, doc_id, corpus_id, history=None):
    from polymath_shared.admission_interpreter import interpret_admission
    from polymath_shared.identity_allocation import (
        allocate_identity, span_identity_key,
    )
    from workers.candidates import identities_for

    ids = identities_for(slices, corpus_id=corpus_id, doc_id=doc_id,
                         contract_version=SEMANTIC_CONTRACT_V1_1)
    # In production a cross-sentence antecedent is always a span from an
    # EARLIER slice of the same document, so it is already in the map. These
    # tests hand `doc_entities_history` synthetic spans that belong to no
    # slice, so admit them here under the same pinned contract.
    for span in history or []:
        key = span_identity_key(span, corpus_id)
        if key in ids:
            continue
        result = interpret_admission(
            contract_version=SEMANTIC_CONTRACT_V1_1,
            proposal_surface=span.text, core_type=span.core_type.value,
            extraction_score=span.score, sentence_initial=False)
        ids[key] = allocate_identity(
            result, corpus_id=corpus_id, doc_id=span.doc_id or doc_id,
            chunk_id=span.chunk_id, span_start=span.start, span_end=span.end)
    return ids


def build_candidates(slices, *, doc_id, corpus_id="eval", **kwargs):
    from workers.candidates import build_candidates as _build

    return _build(slices, doc_id=doc_id, corpus_id=corpus_id,
                  identities=_ids(slices, doc_id, corpus_id,
                                  kwargs.get("doc_entities_history")), **kwargs)


def build_candidates_kimi(slices, *, doc_id, corpus_id="eval", **kwargs):
    from workers.kimi_candidates import build_candidates_kimi as _build

    return _build(slices, doc_id=doc_id, corpus_id=corpus_id,
                  identities=_ids(slices, doc_id, corpus_id,
                                  kwargs.get("doc_entities_history")), **kwargs)
