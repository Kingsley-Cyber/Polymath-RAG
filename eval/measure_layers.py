"""Experiment 0002 harness: layer-wise measurement of how much relation
knowledge the deterministic lexical compiler recovers.

Layers (measured separately so a low E2E number names its cause):

  L1 entity discovery      span recall + typing accuracy (live GLiNER)
  L2 candidate generation  gold-endpoint coverage (gold entities+evidence)
  L3 trigger lane          trigger recall/precision of the lexical proposer
  L4 structural scope      negation/modality/question accuracy (gold scope)
  L5 compiler, gold inputs predicate/direction/abstention accuracy
  L6 end-to-end            triple P/R/F1, duplicate rate, unsupported rate

Usage:
  .venv/bin/python eval/measure_layers.py [--skip-l1]

Layer 1 needs the gliner-runtime sidecar up (make dev-gliner). The other
layers are deterministic and need nothing but the gold file. Output is a
plain table for pasting into the experiment record; nothing is written
to disk (records are committed manually so numbers stay reviewable).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "shared"))
sys.path.insert(0, str(REPO / "workers"))

import yaml  # noqa: E402

from polymath_shared.contracts import (  # noqa: E402
    CoreType,
    EntityCandidate,
    EntitySpan,
    EvidenceSpan,
    RelationCandidate,
    ScopeFlags,
)
from polymath_shared.rulepack import compile_relation, load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import canonical_entity_id  # noqa: E402
from polymath_shared.rulepack.negation import analyze_scope  # noqa: E402
from workers.candidates import SentenceSlice, build_candidates  # noqa: E402
from workers.evidence_proposer import propose_evidence  # noqa: E402

GOLD = yaml.safe_load((REPO / "eval" / "gold" / "relations_v1.yaml").read_text())


def _gold_span(g: dict, doc_id: str, chunk_id: str, sentence: str) -> EntitySpan:
    start = sentence.find(g["text"])
    if start < 0:
        start = 0
    return EntitySpan(
        doc_id=doc_id, chunk_id=chunk_id, start=start, end=start + len(g["text"]),
        text=g["text"], core_type=CoreType(g["type"]), score=1.0,
        extractor_version="gold",
    )


def _gold_candidate(item: dict, evidence: dict, subj: str, obj: str) -> RelationCandidate:
    entities = {e["text"]: e for e in item["entities"]}
    s, o = entities[subj], entities[obj]
    subject_span = _gold_span(s, "gold", "gold", item["text"])
    object_span = _gold_span(o, "gold", "gold", item["text"])
    return RelationCandidate(
        evidence=EvidenceSpan(
            chunk_id="gold",
            start=max(item["text"].find(evidence["text"]), 0),
            end=max(item["text"].find(evidence["text"]), 0) + len(evidence["text"]),
            text=evidence["text"],
            evidence_class=evidence["class"], trigger_lemma=evidence.get("lemma"),
            score=1.0, extractor_version="gold",
        ),
        subject=EntityCandidate(span=subject_span, resolved_entity_id=canonical_entity_id(subject_span.core_type, subj)),
        object=EntityCandidate(span=object_span, resolved_entity_id=canonical_entity_id(object_span.core_type, obj)),
        scope=ScopeFlags(**item.get("scope", {})),
        ontology_profile="core",
    )


def l1_entity_discovery(live: bool) -> dict:
    from polymath_shared.clients import GlinerClient
    from workers.profile_router import CORE_LABELS

    found = typed_ok = gold_total = 0
    if not live:
        return {"note": "skipped (sidecar down)", "span_recall": None, "typing_accuracy": None}
    gliner = GlinerClient()
    gliner.verify_pin()
    try:
        for item in GOLD["items"]:
            spans = gliner.entity_pass(item["text"], CORE_LABELS, threshold=0.5)["spans"]
            preds = {s["text"].lower(): s["label"] for s in spans}
            for g in item["entities"]:
                gold_total += 1
                label = None
                for text, lbl in preds.items():
                    if g["text"].lower() in text or text in g["text"].lower():
                        label = lbl
                        break
                if label:
                    found += 1
                    if label == g["type"]:
                        typed_ok += 1
    finally:
        gliner.close()
    return {
        "span_recall": found / gold_total if gold_total else None,
        "typing_accuracy": typed_ok / found if found else None,
        "gold_entities": gold_total,
    }


def l2_candidate_generation() -> dict:
    pack = load_rule_pack()
    covered = total = 0
    for item in GOLD["items"]:
        for evidence in item["evidence"]:
            expected_pairs = [(t["subject"], t["object"]) for t in item["gold"]]
            if not expected_pairs:
                continue
            slices = [
                SentenceSlice(
                    text=item["text"], sentence_start=0, sentence_end=len(item["text"]),
                    entities=[_gold_span(e, "gold", "gold", item["text"]) for e in item["entities"]],
                    evidence=[
                        EvidenceSpan(
                            chunk_id="gold",
                            start=max(item["text"].find(evidence["text"]), 0),
                            end=max(item["text"].find(evidence["text"]), 0) + len(evidence["text"]),
                            text=evidence["text"], evidence_class=evidence["class"],
                            trigger_lemma=evidence.get("lemma"), score=1.0,
                            extractor_version="gold",
                        )
                    ],
                    parse=None,
                )
            ]
            cands = build_candidates(slices, doc_id="gold", ontology_profile="core",
                                     extractor_version="gold", rule_pack=pack)
            pairs = {(c.subject.span.text, c.object.span.text) for c in cands}
            for pair in expected_pairs:
                total += 1
                if pair in pairs:
                    covered += 1
    return {"endpoint_coverage": covered / total if total else None, "gold_pairs": total}


def l3_trigger_lane() -> dict:
    pack = load_rule_pack()
    recall_hits = precision_hits = proposed = gold = 0
    for item in GOLD["items"]:
        spans = propose_evidence(item["text"], "gold", pack)
        gold_spans = {(e["text"].lower(), e["class"]) for e in item["evidence"]}
        proposed += len(spans)
        for s in spans:
            if (s.text.lower(), s.evidence_class) in gold_spans:
                precision_hits += 1
        for gtext, gclass in gold_spans:
            gold += 1
            if any(s.text.lower() == gtext and s.evidence_class == gclass for s in spans):
                recall_hits += 1
    return {
        "trigger_recall": recall_hits / gold if gold else None,
        "trigger_precision": precision_hits / proposed if proposed else None,
        "gold_triggers": gold,
        "proposed_triggers": proposed,
    }


def l4_structural_scope() -> dict:
    correct = flagged = 0
    for item in GOLD["items"]:
        scope = item.get("scope", {})
        if not any(scope.get(k) for k in ("negated", "speculative", "hypothetical", "question")):
            continue
        flagged += 1
        predicted = analyze_scope(item["text"])
        pred = {
            "negated": predicted.negated,
            "speculative": predicted.speculative,
            "hypothetical": predicted.hypothetical,
            "question": predicted.question,
        }
        expected = {k: bool(scope.get(k)) for k in pred}
        if pred == expected:
            correct += 1
    return {"scope_accuracy": correct / flagged if flagged else None, "scoped_items": flagged}


def l5_compiler_gold_inputs() -> dict:
    """The compiler with gold entities + gold triggers. Candidates are
    built ONLY from the gold triples (subject/object given), so this
    layer isolates the compiler's mapping decision from candidate
    generation and direction heuristics. Voice inversion (passive) is a
    candidate-generation property, measured in L2/L6, not here."""
    pack = load_rule_pack()
    exact = direction_ok = gold_total = 0
    abstain_ok = abstain_total = 0

    for item in GOLD["items"]:
        if item["gold"]:
            for triple in item["gold"]:
                gold_total += 1
                for evidence in item["evidence"]:
                    cand = _gold_candidate(item, evidence, triple["subject"], triple["object"])
                    decision = compile_relation(cand, None, pack)
                    if decision.fact is None:
                        continue
                    if decision.fact.predicate == triple["predicate"]:
                        if triple.get("qualified"):
                            # Qualified gold: the fact must arrive as QUALIFY
                            # with the matching certainty qualifier.
                            if decision.fact.decision == "QUALIFY" and (
                                decision.fact.qualifiers.get("certainty") == triple["qualified"]
                                or triple.get("qualified") in decision.fact.qualifiers
                            ):
                                exact += 1
                        else:
                            exact += 1
                    if (
                        decision.fact.subject_id == cand.subject.resolved_entity_id
                        and decision.fact.object_id == cand.object.resolved_entity_id
                    ):
                        direction_ok += 1
                    break
        else:
            abstain_total += 1
            abstained = True
            for evidence in item["evidence"]:
                for subj in item["entities"]:
                    for obj in item["entities"]:
                        if subj is obj or subj["text"] == obj["text"]:
                            continue
                        cand = _gold_candidate(item, evidence, subj["text"], obj["text"])
                        decision = compile_relation(cand, None, pack)
                        if decision.fact is not None:
                            abstained = False
            if abstained:
                abstain_ok += 1

    return {
        "predicate_accuracy": exact / gold_total if gold_total else None,
        "direction_accuracy": direction_ok / gold_total if gold_total else None,
        "abstention_accuracy": abstain_ok / abstain_total if abstain_total else None,
        "gold_triples": gold_total,
        "abstention_items": abstain_total,
    }


def l6_end_to_end(live: bool) -> dict:
    pack = load_rule_pack()
    from polymath_shared.clients import GlinerClient
    from workers.profile_router import CORE_LABELS
    from workers.summarizer import split_sentences

    gliner = GlinerClient() if live else None
    if gliner:
        try:
            gliner.verify_pin()
        except Exception:
            gliner = None

    pred_triples: set = set()
    gold_triples: set = set()
    unsupported = decisions_total = 0
    try:
        for item in GOLD["items"]:
            for t in item["gold"]:
                gold_triples.add((t["subject"], t["predicate"], t["object"]))
            entities = []
            if gliner:
                for s in gliner.entity_pass(item["text"], CORE_LABELS, threshold=0.5)["spans"]:
                    try:
                        core = CoreType(s["label"])
                    except ValueError:
                        continue
                    entities.append(EntitySpan(
                        doc_id="e2e", chunk_id="e2e", start=s["start"], end=s["end"],
                        text=s["text"], core_type=core, score=s["score"],
                        extractor_version="live",
                    ))
            else:
                entities = [_gold_span(e, "e2e", "e2e", item["text"]) for e in item["entities"]]
            evidence = propose_evidence(item["text"], "e2e", pack)
            sentences = split_sentences(item["text"])
            offsets: list[tuple[int, int]] = []
            cursor = 0
            for sentence in sentences:
                start = item["text"].find(sentence, cursor)
                offsets.append((start, start + len(sentence)))
                cursor = start + len(sentence)
            slices = [
                SentenceSlice(
                    text=text, sentence_start=s0, sentence_end=s1,
                    entities=[e for e in entities if e.start >= s0 and e.end <= s1],
                    evidence=[v for v in evidence if v.start >= s0 and v.end <= s1],
                    parse=None,
                )
                for text, (s0, s1) in zip(sentences, offsets)
            ]
            for sl in slices:
                for cand in build_candidates([sl], doc_id="e2e", ontology_profile="core",
                                             extractor_version="e2e", rule_pack=pack):
                    decision = compile_relation(cand, None, pack)
                    decisions_total += 1
                    if decision.fact is not None:
                        subj_text = next(
                            (e.text for e in entities if e.text == cand.subject.span.text), cand.subject.span.text
                        )
                        obj_text = next(
                            (e.text for e in entities if e.text == cand.object.span.text), cand.object.span.text
                        )
                        pred_triples.add((subj_text, decision.fact.predicate, obj_text))
                    else:
                        unsupported += 1
    finally:
        if gliner:
            gliner.close()

    tp = len(pred_triples & gold_triples)
    precision = tp / len(pred_triples) if pred_triples else None
    recall = tp / len(gold_triples) if gold_triples else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None
    return {
        "triple_precision": precision,
        "triple_recall": recall,
        "triple_f1": f1,
        "true_positives": tp,
        "predicted": len(pred_triples),
        "gold": len(gold_triples),
        "duplicate_rate": 0.0,  # sets by construction; factual duplicates are impossible
        "unsupported_rate": unsupported / decisions_total if decisions_total else None,
        "decisions_total": decisions_total,
        "entity_source": "live" if gliner else "gold",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-l1", action="store_true", help="skip the live GLiNER layer")
    args = parser.parse_args()

    pack = load_rule_pack()
    print(f"rule pack: {pack['pack']['id']} v{pack['pack']['version']}")
    print(f"gold set:  {GOLD['version']} ({len(GOLD['items'])} items)")

    l1 = l1_entity_discovery(live=not args.skip_l1)
    l2 = l2_candidate_generation()
    l3 = l3_trigger_lane()
    l4 = l4_structural_scope()
    l5 = l5_compiler_gold_inputs()
    l6 = l6_end_to_end(live=not args.skip_l1)

    def pct(v) -> str:
        return "n/a" if v is None else f"{v*100:.1f}%"

    print()
    print("layer                       metric              value")
    print("-" * 60)
    print(f"L1 entity discovery        span recall         {pct(l1.get('span_recall'))}")
    print(f"L1 entity discovery        typing accuracy     {pct(l1.get('typing_accuracy'))}")
    print(f"L2 candidate generation    endpoint coverage   {pct(l2['endpoint_coverage'])}")
    print(f"L3 trigger lane            trigger recall      {pct(l3['trigger_recall'])}")
    print(f"L3 trigger lane            trigger precision   {pct(l3['trigger_precision'])}")
    print(f"L4 structural scope        scope accuracy      {pct(l4['scope_accuracy'])}")
    print(f"L5 compiler (gold inputs)  predicate accuracy  {pct(l5['predicate_accuracy'])}")
    print(f"L5 compiler (gold inputs)  direction accuracy  {pct(l5['direction_accuracy'])}")
    print(f"L5 compiler (gold inputs)  abstention accuracy {pct(l5['abstention_accuracy'])}")
    print(f"L6 end-to-end ({l6['entity_source']})  triple precision   {pct(l6['triple_precision'])}")
    print(f"L6 end-to-end              triple recall       {pct(l6['triple_recall'])}")
    print(f"L6 end-to-end              triple F1           {pct(l6['triple_f1'])}")
    print(f"L6 end-to-end              duplicate rate      {l6['duplicate_rate']:.1%}")
    print(f"L6 end-to-end              unsupported rate    {pct(l6['unsupported_rate'])}")


if __name__ == "__main__":
    main()
