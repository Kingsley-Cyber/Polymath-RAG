"""I3R-R6: exact-evidence-v1 provenance offsets (pure)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import EntitySpan, CoreType, EvidenceSpan  # noqa: E402
from workers.extract_worker import _evidence_offsets  # noqa: E402


class _Cand:
    def __init__(self):
        self.evidence = EvidenceSpan(
            chunk_id="c1", start=40, end=47, text="applied",
            evidence_class="usage_application", trigger_lemma="apply",
            trigger_lexical_class="VERB", trigger_predicate_id="uses",
            trigger_match_source="verbs", score=1.0, extractor_version="t")
        self.subject = type("S", (), {})()
        self.subject.span = EntitySpan(
            doc_id="d1", chunk_id="c1", start=0, end=9,
            text="HarborPay", core_type=CoreType("Organization"),
            score=0.9, extractor_version="t")
        self.subject.resolved_entity_id = "HarborPay"
        self.object = type("O", (), {})()
        self.object.span = EntitySpan(
            doc_id="d1", chunk_id="c1", start=20, end=31,
            text="Envoy Proxy", core_type=CoreType("Technology"),
            score=0.9, extractor_version="t")
        self.object.resolved_entity_id = "Envoy Proxy"
        self.sentence_index = 2


def test_offsets_are_chunk_relative_and_exact():
    chunk_row = {"char_start": 500, "char_end": 900}
    cand = _Cand()
    decision = type("D", (), {})()
    fact = type("F", (), {})()
    fact.subject_id = cand.subject.span.text
    fact.object_id = cand.object.span.text
    decision.fact = fact
    offsets = _evidence_offsets(chunk_row, cand, decision)
    assert offsets["provenance_contract"] == "exact-evidence-v1"
    assert offsets["chunk_char_start"] == 500
    assert offsets["chunk_char_end"] == 900
    assert offsets["sentence_index"] == 2
    assert offsets["evidence_start"] == 40
    assert offsets["evidence_end"] == 47
    assert offsets["subject_start"] == 0
    assert offsets["subject_end"] == 9
    assert offsets["object_start"] == 20
    assert offsets["object_end"] == 31
    # verify the exactness contract: chunk_text[start:end] == surface
    chunk_text = [" "] * 400
    for span_start, surface in ((0, "HarborPay"), (20, "Envoy Proxy"), (40, "applied")):
        for j, ch in enumerate(surface):
            chunk_text[span_start + j] = ch
    chunk_text = "".join(chunk_text)
    assert chunk_text[offsets["subject_start"]:offsets["subject_end"]] == "HarborPay"
    assert chunk_text[offsets["object_start"]:offsets["object_end"]] == "Envoy Proxy"
    assert chunk_text[offsets["evidence_start"]:offsets["evidence_end"]] == "applied"
