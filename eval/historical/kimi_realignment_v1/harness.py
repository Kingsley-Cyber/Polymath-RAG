"""Kimi v1 qualification harness over the frozen Phase H corpus.

Reuses the same frozen gold items as eval/phase_h/harness.py but runs
the kimi_v1 path (UD-anchored candidates + PropBank role assignment +
VN/PB/FN/SemLink-active compiler + role-based direction). The legacy
path is run as the baseline for comparison.

Usage:
    .venv/bin/python eval/kimi_realignment_v1/harness.py \
        [--outdir eval/kimi_realignment_v1/artifacts]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import yaml  # noqa: E402

from polymath_shared.contracts import (  # noqa: E402
    CoreType,
    EntitySpan,
    EvidenceSpan,
    RelationCandidate,
    ScopeFlags,
)
from polymath_shared.rulepack import compile_relation_kimi, load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import canonical_entity_id  # noqa: E402
from workers.candidates import SentenceSlice  # noqa: E402
from workers.kimi_candidates import build_candidates_kimi  # noqa: E402

GOLD_PATH = ROOT / "eval" / "gold" / "relations_v1.yaml"
GOLD_SHA256_BEFORE = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()

DECISION_ORDER = ("ACCEPT", "QUALIFY", "REJECT", "AMBIGUOUS", "UNSUPPORTED", "CONFLICT")


class _Result:
    def __init__(self):
        self.predictions: list[dict] = []
        self.waterfall: list[dict] = []


def _gold_span(g: dict, item: dict, doc_id: str, chunk_id: str) -> EntitySpan:
    start = item["text"].find(g["text"])
    if start < 0:
        start = 0
    return EntitySpan(
        doc_id=doc_id, chunk_id=chunk_id, start=start, end=start + len(g["text"]),
        text=g["text"], core_type=CoreType(g["type"]), score=1.0,
        extractor_version="frozen-gold",
    )


def _frozen_evidence(item: dict, evidence: dict, chunk_id: str) -> EvidenceSpan:
    start = max(item["text"].find(evidence["text"]), 0)
    return EvidenceSpan(
        chunk_id=chunk_id, start=start, end=start + len(evidence["text"]),
        text=evidence["text"], evidence_class=evidence["class"],
        trigger_lemma=evidence.get("lemma"), score=1.0,
        extractor_version="frozen-gold",
    )


def _synthetic_syntax(item: dict, evidence: EvidenceSpan) -> dict:
    """Best-effort UD-style parse from the frozen item text.

    The Phase H corpus is small and mostly SVO. We synthesize a token
    sequence with dependency heads for the trigger and the nearest
    left/right entity tokens. This is enough to exercise the kimi_v1
    UD binding path; it is not a substitute for a real spaCy parse.
    """
    text = item["text"]
    tokens: list[dict] = []
    offset = 0
    for word in text.replace(",", " , ").replace(".", " . ").replace(";", " ; ").split():
        if not word.strip():
            continue
        start = text.find(word, offset)
        if start < 0:
            start = offset
        end = start + len(word)
        tokens.append({
            "i": len(tokens),
            "text": word,
            "char_start": start,
            "char_end": end,
            "lemma": word.lower(),
            "pos": "VERB" if word == evidence.text else "NOUN",
            "dep": "ROOT",
            "head_i": len(tokens),
        })
        offset = end

    # Heuristic: find trigger token and attach nearest left/right entities.
    trig_i = None
    for i, t in enumerate(tokens):
        if t["char_start"] == evidence.start:
            trig_i = i
            break
    if trig_i is None:
        for i, t in enumerate(tokens):
            if t["char_start"] <= evidence.start < t["char_end"]:
                trig_i = i
                break
    if trig_i is None:
        return {"tokens": tokens}

    # Attach tokens whose span overlaps a gold entity to the trigger.
    for ent in item["entities"]:
        ent_start = max(item["text"].find(ent["text"]), 0)
        ent_end = ent_start + len(ent["text"])
        for i, t in enumerate(tokens):
            if t["char_start"] < ent_end and t["char_end"] > ent_start:
                if t["char_end"] <= evidence.start:
                    t["dep"] = "nsubj"
                    t["head_i"] = trig_i
                elif t["char_start"] >= evidence.end:
                    t["dep"] = "dobj"
                    t["head_i"] = trig_i
    return {"tokens": tokens}


def _run_kimi(items: list[dict], pack: dict) -> _Result:
    res = _Result()
    for item in items:
        item_id = item["id"]
        doc_id = f"frozen-{item_id}"
        chunk_id = f"chunk-{item_id}"
        entity_spans = [_gold_span(g, item, doc_id, chunk_id) for g in item["entities"]]
        evidence_spans = [_frozen_evidence(item, ev, chunk_id) for ev in item["evidence"]]
        scope = ScopeFlags(**item.get("scope", {}))

        # Build one SentenceSlice per item; kimi_v1 expects the syntax
        # evidence on the slice. We synthesize it from the frozen text.
        sl = SentenceSlice(
            text=item["text"],
            sentence_start=0,
            sentence_end=len(item["text"]),
            entities=entity_spans,
            evidence=evidence_spans,
            parse=item.get("parse"),
            sentence_index=0,
            syntax=_synthetic_syntax(item, evidence_spans[0]) if evidence_spans else None,
        )

        # Passive parse spec from frozen item -> syntactic dict for compiler.
        syntactic = None
        parse_spec = item.get("parse")
        if parse_spec:
            agent_text = parse_spec["agent"]
            agent_type = next(g["type"] for g in item["entities"] if g["text"] == agent_text)
            syntactic = {
                "voice": parse_spec.get("voice", "passive"),
                "agent": {"entity_id": canonical_entity_id(CoreType(agent_type), agent_text)},
            }

        candidates = build_candidates_kimi(
            [sl],
            doc_id=doc_id,
            corpus_id="kimi-eval",
            ontology_profile="core",
            extractor_version="kimi-v1",
            rule_pack=pack,
            observer=None,
        )

        compiled: list[dict] = []
        for cand in candidates:
            decision = compile_relation_kimi(cand, syntactic, pack, syntax=sl.syntax)
            if decision.fact is not None:
                compiled.append({
                    "subject": cand.subject.span.text,
                    "predicate": decision.fact.predicate,
                    "object": cand.object.span.text,
                    "decision": decision.fact.decision,
                    "rule_id": decision.fact.rule_id,
                    "roleset": decision.fact.provenance.get("roleset"),
                    "verbnet_classes": decision.fact.provenance.get("verbnet_classes", []),
                    "framenet_frames": decision.fact.provenance.get("framenet_frames", []),
                    "semlink_resolved": decision.fact.provenance.get("semlink_resolved", False),
                    "orientation": decision.fact.provenance.get("orientation"),
                    "assigned_roles": decision.fact.provenance.get("assigned_roles", {}),
                })
            else:
                compiled.append({
                    "subject": cand.subject.span.text,
                    "object": cand.object.span.text,
                    "decision": decision.decision,
                    "reason": decision.reason,
                })

        res.predictions.append({
            "item_id": item_id,
            "arm": "kimi_v1",
            "scope": item.get("scope", {}),
            "compiled": compiled,
        })

        res.waterfall.append({
            "item_id": item_id,
            "arm": "kimi_v1",
            "candidate_count": len(candidates),
            "accepted_count": len([c for c in compiled if c.get("predicate")]),
            "W8_assertion_gate": _assertion_gate(item.get("scope", {})),
        })
    return res


def _assertion_gate(scope: dict) -> str:
    for flag, expected in {
        "negated": "NO_FACT",
        "conditional": "NO_FACT",
        "question": "NO_FACT",
        "hypothetical": "QUALIFY",
        "speculative": "QUALIFY",
    }.items():
        if scope.get(flag):
            return expected
    if scope.get("attributed"):
        return "QUALIFY_ATTRIBUTED"
    return "ASSERT"


def score(predictions: list[dict], items: list[dict]) -> dict:
    """Same unit scoring as Phase H harness for comparability."""
    by_item = {p["item_id"]: p for p in predictions}
    units: list[dict] = []
    for item in items:
        item_id = item["id"]
        pred = by_item[item_id]
        facts = [
            (c["subject"], c["predicate"], c["object"], c.get("decision"))
            for c in pred["compiled"] if "predicate" in c
        ]
        if item["gold"]:
            matched_facts: set = set()
            for triple in item["gold"]:
                qualified = ("qualified" in triple) or ("attributed" in triple)
                subj, predname, obj = triple["subject"], triple["predicate"], triple["object"]
                expected_decision = "QUALIFY" if qualified else "ACCEPT"
                exact = (subj, predname, obj, expected_decision)
                if exact in facts:
                    outcome = "CORRECT"
                    matched_facts.add(exact)
                elif (subj, predname, obj, "ACCEPT") in facts and qualified:
                    outcome = "INCORRECT_ASSERTION"
                    matched_facts.add((subj, predname, obj, "ACCEPT"))
                elif any(f[0] == subj and f[2] == obj and f[1] != predname for f in facts):
                    outcome = "INCORRECT_PREDICATE"
                elif any(f[1] == predname and f[0] == obj and f[2] == subj for f in facts):
                    outcome = "INCORRECT_DIRECTION"
                else:
                    outcome = "MISSED"
                units.append({
                    "kind": "triple",
                    "item_id": item_id,
                    "subject": subj, "predicate": predname, "object": obj,
                    "qualified": qualified,
                    "outcome": outcome,
                })
            for fact in sorted(set(facts) - matched_facts):
                units.append({
                    "kind": "spurious",
                    "item_id": item_id,
                    "subject": fact[0], "predicate": fact[1], "object": fact[2],
                    "decision": fact[3],
                    "outcome": "INCORRECT",
                })
        else:
            spurious = bool(facts)
            units.append({
                "kind": "abstention",
                "item_id": item_id,
                "reason": item.get("abstain", ""),
                "outcome": "INCORRECT" if spurious else "CORRECT",
            })
    return {"units": units}


def summarize(units: list[dict]) -> dict:
    correct = sum(1 for u in units if u["outcome"] == "CORRECT")
    incorrect = sum(1 for u in units if u["outcome"].startswith("INCORRECT"))
    missed = sum(1 for u in units if u["outcome"] == "MISSED")
    total = correct + incorrect + missed
    precision = correct / (correct + incorrect) if (correct + incorrect) else 0.0
    recall = correct / (correct + missed) if (correct + missed) else 0.0
    return {
        "correct": correct,
        "incorrect": incorrect,
        "missed": missed,
        "total": total,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=str(ROOT / "eval" / "kimi_realignment_v1" / "artifacts"))
    parser.add_argument("--gold", default=str(GOLD_PATH))
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    gold = yaml.safe_load(Path(args.gold).read_text())
    items = gold.get("items", []) if isinstance(gold, dict) else gold

    pack = load_rule_pack(pack_version="1.0.1")
    res = _run_kimi(items, pack)
    scored = score(res.predictions, items)
    metrics = summarize(scored["units"])

    # Load legacy Phase H baseline metrics for the same corpus.
    legacy_metrics = {}
    legacy_path = ROOT / "eval" / "phase_h" / "artifacts" / "metrics.json"
    if legacy_path.exists():
        legacy_metrics = json.loads(legacy_path.read_text()).get("baseline", {})

    output = {
        "corpus": str(args.gold),
        "corpus_sha256": GOLD_SHA256_BEFORE,
        "rule_pack": pack["pack"]["version"],
        "kimi_v1": metrics,
        "legacy_v1": legacy_metrics,
        "delta": {
            "correct": metrics.get("correct", 0) - legacy_metrics.get("correct", 0),
            "incorrect": metrics.get("incorrect", 0) - legacy_metrics.get("incorrect", 0),
            "missed": metrics.get("missed", 0) - legacy_metrics.get("missed", 0),
        },
        "units": scored["units"],
        "predictions": res.predictions,
        "waterfall": res.waterfall,
    }

    (outdir / "metrics.json").write_text(json.dumps(output, indent=2, sort_keys=False))
    (outdir / "predictions.jsonl").write_text(
        "\n".join(json.dumps(p, sort_keys=True) for p in res.predictions))
    print(json.dumps({
        "kimi_v1": metrics,
        "legacy_v1": legacy_metrics,
        "delta": output["delta"],
        "outdir": str(outdir),
    }, indent=2))


if __name__ == "__main__":
    main()
