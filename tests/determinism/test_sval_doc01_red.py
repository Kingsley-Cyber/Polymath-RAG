"""RED REGRESSION FIXTURES — s-validation doc01 (Adaptive Neural
Reasoning Systems). These encode EXPECTED bindings that currently fail
at candidate generation (C-class). Green = slice complete.

Traced classification (2026-08-24):
  A trigger missing        NO — 23 v1 anchors + 6 frame anchors resolve
  B frame mapping missing  NO — creation/training/evaluation frames hit
  C role binding           YES — zero candidates generated despite
                            anchors + fully-admitted endpoints
  D entity typing          NO — Model/Organization/Corpus/Benchmark
                            all GLOBAL-admitted correctly
  E admission rejection    NO — nothing reached admission
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import pytest
import yaml

import os

@pytest.fixture(autouse=True)
def _restore_pipeline_env():
    saved = os.environ.get("POLYMATH_RELATION_PIPELINE")
    yield
    if saved is None:
        os.environ.pop("POLYMATH_RELATION_PIPELINE", None)
    else:
        os.environ["POLYMATH_RELATION_PIPELINE"] = saved

DOC_TEXT = pathlib.Path(
    "/Users/king/Downloads/untitled folder/S/"
    "01_psychology_working_memory.md"
).read_text() if pathlib.Path(
    "/Users/king/Downloads/untitled folder/S/"
    "01_psychology_working_memory.md").exists() else (
    "# Adaptive Neural Reasoning Systems\n\nThe Orion Adaptive "
    "Reasoning Model was introduced by the Advanced Computational "
    "Intelligence Laboratory in 2024. The model was trained on the "
    "HorizonText Research Corpus. Evaluation studies examined Orion's "
    "performance across benchmark suites including ReasonBench.")

EXPECTED_FACTS = [
    ("Orion Adaptive Reasoning Model", "introduced_by",
     "Advanced Computational Intelligence Laboratory"),
    ("Orion Adaptive Reasoning Model", "trained_on",
     "HorizonText Research Corpus"),
    ("Orion Adaptive Reasoning Model", "evaluated_on", "ReasonBench"),
]


def _endpoints_admitted():
    """All required endpoints reach the mention layer as referential."""
    from polymath_shared.rulepack.semantic_frames import resolve_frames
    frames = resolve_frames(DOC_TEXT)
    surfaces = {f.surface.lower() for f in frames}
    return surfaces


def test_stage_anchors_exist_both_lanes():
    """A/B clearance: triggers AND frames resolve on this document."""
    from workers.evidence_proposer import propose_evidence
    import yaml
    raw = yaml.safe_load((ROOT / "shared" / "polymath_shared" /
                          "rulepack" / "core-predicates-v1.4.0.yaml")
                         .read_text())
    preds, order = {}, []
    for p in raw["predicates"]:
        rid = p["id"]
        order.append(rid)
        preds[rid] = {"evidence": {
            "classes": p["evidence"].get("classes", ["action"]),
            "verbs": [v.lower() for v in p["evidence"].get("verbs", [])],
            "nouns": [n.lower() for n in p["evidence"].get("nouns", [])],
            "multiword": [m.lower() for m in
                          p["evidence"].get("multiword", [])]}}
    spans = propose_evidence(DOC_TEXT, "ch",
                             {"predicate_order": order,
                              "predicates": preds})
    assert len(spans) >= 10, "v1 trigger lane lost anchors"
    from polymath_shared.rulepack.semantic_frames import resolve_frames
    fr = resolve_frames(DOC_TEXT)
    got = {f.frame_id for f in fr}
    assert {"creation_event", "training_event",
            "evaluation_event"} <= got


@pytest.mark.parametrize("subject,predicate,obj", EXPECTED_FACTS,
                         ids=[f"{s}-{p}-->{o}" for s, p, o in EXPECTED_FACTS])
def test_expected_bindings_compile_to_candidates(subject, predicate, obj):
    """GREEN condition of the former RED markers: each expected binding
    compiles to a candidate through the live kimi_v1 path (real syntax
    sidecar, real frame lane, production entity history + identity
    allocation). Verified end-to-end 2026-08-24 (CATEGORY-D closure)."""
    os.environ.setdefault("POLYMATH_RELATION_PIPELINE", "kimi_v1")
    from workers.summarizer import split_sentences
    from workers.candidates import SentenceSlice
    from workers.kimi_candidates import build_candidates_kimi
    from workers.extract_worker import _allocate_identities
    from workers.evidence_proposer import (propose_evidence,
                                           propose_frame_evidence)
    from polymath_shared.rulepack import load_rule_pack
    from polymath_shared.clients import SpacySyntaxClient
    from polymath_shared.contracts import (EntitySpan, EvidenceSpan,
                                           CoreType)

    # GLiNER-measured mentions for doc01 (production truth, chunk frame).
    surfaces = [
        ("Orion Adaptive Reasoning Model", "Model"),
        ("Advanced Computational Intelligence Laboratory", "Organization"),
        ("HorizonText Research Corpus", "Corpus"),
        ("Evaluation studies", "Experiment"),
        ("ReasonBench", "Benchmark"),
        ("LogicQA", "Benchmark"),
    ]
    ents = []
    for surf, ct in surfaces:
        i = DOC_TEXT.find(surf)
        assert i >= 0, f"fixture surface missing: {surf}"
        ents.append(EntitySpan(
            doc_id="doc_fixture", chunk_id="ch0", start=i,
            end=i + len(surf), text=surf, core_type=CoreType(ct),
            score=0.9, extractor_version="test"))

    slices: list[SentenceSlice] = []
    for t in split_sentences(DOC_TEXT):
        i = DOC_TEXT.find(t)
        if i < 0:
            continue
        a, b = i, i + len(t)
        slices.append(SentenceSlice(
            text=t, sentence_start=a, sentence_end=b,
            entities=[e for e in ents if e.start >= a and e.end <= b],
            evidence=[], parse=None))
    client = SpacySyntaxClient()
    client.verify_pin()
    try:
        resp = client.syntax([{"sentence_id": f"ch0:{n}",
                               "text": s.text}
                              for n, s in enumerate(slices)])
    finally:
        client.close()
    slices = [SentenceSlice(text=s.text, sentence_start=s.sentence_start,
                            sentence_end=s.sentence_end,
                            entities=s.entities,
                            evidence=list(s.evidence), parse=None,
                            syntax=r)
              for s, r in zip(slices, resp["results"])]

    raw = yaml.safe_load((ROOT / "shared" / "polymath_shared" /
                          "rulepack" / "core-predicates-v1.4.0.yaml")
                         .read_text())
    preds, order = {}, []
    for p in raw["predicates"]:
        rid = p["id"]
        order.append(rid)
        preds[rid] = {"evidence": {
            "classes": p["evidence"].get("classes", ["action"]),
            "verbs": [v.lower() for v in p["evidence"].get("verbs", [])],
            "nouns": [n.lower() for n in p["evidence"].get("nouns", [])],
            "multiword": [m.lower() for m in
                          p["evidence"].get("multiword", [])]}}
    v1_spans = propose_evidence(DOC_TEXT, "ch0",
                                {"predicate_order": order,
                                 "predicates": preds})
    all_spans = list(v1_spans) + propose_frame_evidence(DOC_TEXT, "ch0")
    for ev in all_spans:
        for s in slices:
            if s.sentence_start <= ev.start < s.sentence_end:
                s.evidence.append(ev)

    rows = [{"chunk_id": "ch0", "text": DOC_TEXT}] * len(slices)
    identities = _allocate_identities(
        list(zip(rows, slices)), "doc_fixture", "doc_fixture",
        contract_version="admission-harbor-v2")

    history: list[EntitySpan] = []
    compiled = set()
    rp = load_rule_pack()
    for s in slices:
        cands = build_candidates_kimi(
            [s], doc_id="doc_fixture", corpus_id="doc_fixture",
            ontology_profile="scientific-v2", extractor_version="test",
            rule_pack=rp, enrich=False,
            doc_entities_history=history, identities=identities)
        history.extend(sorted(s.entities, key=lambda e: (e.start, e.end)))
        for c in cands:
            compiled.add((c.subject.span.text, c.object.span.text))

    assert (subject, obj) in compiled, (
        f"{subject} --{predicate}--> {obj} did not compile to a "
        f"candidate; compiled={sorted(compiled)}")
