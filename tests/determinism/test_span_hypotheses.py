
"""V5 L2 — rescue as hypothesis records (Phase 3).

R5: the ACTIVE working set keeps V4-effective semantics — these tests assert
the records exist AND behavior is unchanged. Destruction becomes disposition,
never activation.
"""
import pytest

from polymath_shared.contracts import CoreType, EntitySpan
from polymath_shared.raw_evidence import hypothesis_row
from workers.candidates import SentenceSlice
from workers.rescue import apply_boundary


class _FakeGliner:
    def __init__(self, responses):
        self.responses = responses
    def verify_pin(self): pass
    def close(self): pass
    def manifest(self):
        return {"identity": {"model": {"id": "m", "revision": "r"}}}
    def infer_rescue_batch(self, requests):
        out = []
        for req in requests:
            out.append(self.responses.get(req["text"], []))
        return out


def _slice(entities):
    text = "Crestline Automation deployed a controller."
    syntax = {"tokens": [
        {"i": 0, "text": "Crestline", "char_start": 0, "char_end": 9,
         "lemma": "crestline", "pos": "PROPN", "tag": "NNP", "dep": "compound", "head_i": 1},
        {"i": 1, "text": "Automation", "char_start": 10, "char_end": 20,
         "lemma": "automation", "pos": "PROPN", "tag": "NNP", "dep": "nsubj", "head_i": 2},
    ], "noun_chunks": [{"char_start": 0, "char_end": 20, "text": "Crestline Automation", "root_i": 1}]}
    return SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                         entities=entities, evidence=[], parse=None, syntax=syntax)


def _span():
    return EntitySpan(doc_id="d1", chunk_id="c1", start=0, end=9, text="Crestline",
                      core_type=CoreType("Organization"), score=0.9,
                      extractor_version="gliner-2pass-v1")


def _run(monkeypatch, responses):
    import polymath_shared.clients as C
    import workers.rescue as R
    monkeypatch.setattr(C, "GlinerClient", lambda: _FakeGliner(responses))
    monkeypatch.setattr(R, "_gliner_revision", lambda: "r")
    sl = _slice([_span()])
    report = apply_boundary([({"chunk_id": "c1", "doc_id": "d1"}, sl)])
    return sl, report


def test_refused_widening_records_suppression_and_keeps_v4_behavior(monkeypatch):
    sl, report = _run(monkeypatch, {"Crestline Automation": []})
    # RESCUE-SPAN-PRESERVATION-V1 (restored 2026-08-24): refused widening
    # keeps the original provider span; the V4 "source removed from
    # binding" deletion was ledger row 63's limitation and contradicted
    # apply_boundary's own preservation docstring.
    assert [(e.text, e.start, e.end) for e in sl.entities] == \
        [("Crestline", 0, 9)]
    assert sl.entities[0].pass_kind == "discovery"
    # ...but no longer silent: the decision is a durable hypothesis record
    (h,) = report["hypotheses"]
    assert h["mechanism"] == "boundary_widening"
    assert h["status"] == "REJECTED" and h["disposition"] == "SUPPRESSED_SOURCE"
    assert (h["source_surface"], h["proposed_surface"]) == ("Crestline", "Crestline Automation")


def test_accepted_widening_records_supersession(monkeypatch):
    sl, report = _run(monkeypatch, {"Crestline Automation": [
        {"text": "Crestline Automation", "start": 0, "end": 20,
         "label": "Organization", "score": 0.8}]})
    assert [e.text for e in sl.entities] == ["Crestline Automation"]
    (h,) = report["hypotheses"]
    assert h["status"] == "ACCEPTED" and h["disposition"] == "SUPERSEDED_SOURCE"
    assert h["evidence"]["accepted_raw_label"] == "Organization"


def test_hypothesis_ids_are_deterministic():
    h = {"chunk_id": "c1", "mechanism": "boundary_widening",
         "source_char_start": 0, "source_char_end": 9, "source_surface": "Crestline",
         "proposed_char_start": 0, "proposed_char_end": 20,
         "proposed_surface": "Crestline Automation", "status": "REJECTED",
         "disposition": "SUPPRESSED_SOURCE", "evidence": {}}
    assert hypothesis_row("d1", h) == hypothesis_row("d1", dict(h))
    assert hypothesis_row("d1", h)[0].startswith("hyp_")


def test_hypotheses_do_not_change_the_semantic_bundle():
    from polymath_shared.execution import semantic_authority_sha256

    # Pin history: ADMISSION-IMPL-MEMO-V1 (behavior-identical
    # memoization, licensed by test_concept_evidence_equivalence.py +
    # B8 identical-state run) moved it to 6976e483…; SCIENTIFIC-KAG-V1
    # slice A (9d0fce4: scientific entity ontology + concept gate) and
    # the enforcement wiring (266aa81) moved it again — both committed,
    # qualified semantic-layer work; bundle integrity is READY at this
    # hash. The pin exists to catch UNNOTICED movement.
    assert semantic_authority_sha256().startswith("557afbc3a60af163")


def test_hypothesis_surfaces_always_match_their_own_offsets(monkeypatch):
    """A hypothesis row whose surface disagrees with its offsets poisons
    ledger replay (caught live by the settlement frame check on the Sanders
    baseline). Every lane must record the INSTALLED surface."""
    import inspect

    import workers.rescue as R

    src = inspect.getsource(R.apply_type_reconciliation)
    assert 'sl.text[chunk_cs - sl.sentence_start' in src.split(
        '"proposed_surface":')[1][:200]
