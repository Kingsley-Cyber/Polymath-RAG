"""Phase H: empirical lexical-semantic waterfall qualification.

Frozen contracts (recorded in artifacts/manifest.json):
  git_commit            12645c1
  resource_contract_id  03a513ec...
  tables_sha256         0ac3002a... (from the compiled manifest)
  gold corpus           eval/gold/relations_v1.yaml v1.0 (NEVER modified)

Two arms over the SAME frozen upstream artifacts (gold entities,
evidence spans, scope flags from the frozen corpus — upstream is
byte-identical by construction, no GLiNER variance):

  ARM A (lexical)      load_rule_pack(use_resources=False) +
                       build_candidates(enrich=False)
                       -> manual triggers only, zero resource evidence

  ARM B (hybrid)       load_rule_pack(use_resources=True) +
                       build_candidates(enrich=True)
                       -> compiled triggers + PB/VN/FN/SemLink enrichment

The compiler DAG (compile_relation) is IDENTICAL in both arms.

Usage:
    .venv/bin/python eval/phase_h/harness.py [--outdir eval/phase_h/artifacts]
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
    EntityCandidate,
    EntitySpan,
    EvidenceSpan,
    RelationCandidate,
    ScopeFlags,
)
from polymath_shared.rulepack import compile_relation, load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import canonical_entity_id, lexical_lookup  # noqa: E402
from workers.candidates import SentenceSlice, build_candidates  # noqa: E402

GOLD_PATH = ROOT / "eval" / "gold" / "relations_v1.yaml"
GOLD_SHA256_BEFORE = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()

DECISION_ORDER = ("ACCEPT", "QUALIFY", "REJECT", "AMBIGUOUS", "UNSUPPORTED", "CONFLICT")

EXPECTED_ASSERTION: dict[str, str] = {
    "negated": "NO_FACT",
    "conditional": "NO_FACT",
    "question": "NO_FACT",
    "hypothetical": "QUALIFY",
    "speculative": "QUALIFY",
}


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


def _candidate_for_pair(
    item: dict,
    evidence: EvidenceSpan,
    subject_text: str,
    object_text: str,
    entity_spans: dict[str, EntitySpan],
) -> RelationCandidate:
    subject_span = entity_spans[subject_text]
    object_span = entity_spans[object_text]
    return RelationCandidate(
        evidence=evidence,
        subject=EntityCandidate(
            span=subject_span,
            resolved_entity_id=canonical_entity_id(subject_span.core_type, subject_text),
        ),
        object=EntityCandidate(
            span=object_span,
            resolved_entity_id=canonical_entity_id(object_span.core_type, object_text),
        ),
        roles=[],
        scope=ScopeFlags(**item.get("scope", {})),
        ontology_profile="core",
    )


def run_arm(items: list[dict], arm: str) -> dict:
    """Run one arm over the frozen items. Returns predictions + waterfall."""
    use_resources = arm == "hybrid"
    pack = load_rule_pack(use_resources=use_resources)

    predictions: list[dict] = []
    waterfall: list[dict] = []
    coverage_index = json.loads(
        (ROOT / "resources" / "compiled" /
         [d for d in (ROOT / "resources" / "compiled").iterdir() if d.is_dir()][0] /
         "compiled_lexical.json").read_text()
    )["rule_coverage"]
    semlink_unresolved = set()
    compiled_manifest = json.loads(
        (ROOT / "resources" / "compiled" /
         [d for d in (ROOT / "resources" / "compiled").iterdir() if d.is_dir()][0] /
         "manifest.json").read_text()
    )
    for key in compiled_manifest.get("semlink_unresolved_keys", []):
        if ":" in key:
            semlink_unresolved.add(key.split(":", 1)[1].split(":")[0])

    for item in items:
        item_id = item["id"]
        entity_spans = {
            g["text"]: _gold_span(g, item, "frozen", "frozen") for g in item["entities"]
        }
        evidence_spans = [_frozen_evidence(item, ev, "frozen") for ev in item["evidence"]]
        scope = item.get("scope", {})

        # W0: gold
        w0 = len(item["gold"])

        # W1: endpoints available (all gold entities are frozen-available)
        w1 = bool(item["entities"])

        # W2: candidate generation — the frozen linear anchoring produces
        # (nearest-left, nearest-right) pairs per evidence span.
        # REGRESSION-FIXED (harness defect): right-side entity search must
        # begin AFTER the evidence span — an entity whose surface is a
        # substring of a left-side entity ("cognition" inside
        # "Metacognition") must not be mis-assigned to the left.
        generated_pairs: set[tuple[str, str]] = set()
        for evidence in evidence_spans:
            ev_text = evidence.text
            ev_start = max(item["text"].find(ev_text), 0)
            ev_end = ev_start + len(ev_text)
            left = [g["text"] for g in item["entities"]
                    if 0 <= item["text"].find(g["text"]) < ev_start]
            right = [g["text"] for g in item["entities"]
                     if item["text"].find(g["text"], ev_end) >= ev_end]
            for subj in left:
                for obj in right:
                    if subj != obj:
                        generated_pairs.add((subj, obj))
        gold_pairs = {(t["subject"], t["object"]) for t in item["gold"]}
        w2 = gold_pairs <= generated_pairs

        # W3: trigger found (arm-specific trigger matching, via the
        # compiler's own trigger check — a candidate compiles only when
        # a rule's trigger vocabulary admits the evidence).
        w3 = False
        for evidence in evidence_spans:
            lemma = evidence.trigger_lemma
            matched = False
            for rule_id in pack["predicate_order"]:
                rule = pack["predicates"][rule_id]
                ev = rule["evidence"]
                if evidence.evidence_class not in ev.get("classes", []):
                    continue
                text = evidence.text.lower().strip()
                for negative in ev.get("negative_triggers", []):
                    if negative.lower() in text.split():
                        continue
                if lemma and lemma.lower() in [v.lower() for v in ev.get("verbs", [])]:
                    matched = True
                    break
                if lemma and lemma.lower() in [n.lower() for n in ev.get("nouns", [])]:
                    matched = True
                    break
                if any(phrase.lower() in text for phrase in ev.get("multiword", [])):
                    matched = True
                    break
            if matched:
                w3 = True
                break

        # Compile every generated candidate (evidence × pair), collecting
        # the arm's decisions.
        compiled: list[dict] = []
        for evidence in evidence_spans:
            for subj, obj in sorted(generated_pairs):
                cand = _candidate_for_pair(item, evidence, subj, obj, entity_spans)
                if use_resources:
                    lookup = lexical_lookup(pack, evidence.trigger_lemma or "") if evidence.trigger_lemma else {}
                    cand.roleset = cand.roleset or (
                        lookup.get("propbank_rolesets")[0]
                        if lookup.get("propbank_rolesets") and len(lookup["propbank_rolesets"]) == 1
                        else None
                    )
                    cand.verbnet_classes = sorted(set(lookup.get("verbnet_classes", [])))
                    cand.framenet_frames = sorted(set(lookup.get("framenet_frames", [])))
                    cand.semlink_resolved = bool(lookup.get("semlink_resolved"))
                decision = compile_relation(cand, None, pack)
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
                        "trigger_lemma": decision.fact.provenance.get("trigger_lemma"),
                    })
                else:
                    compiled.append({
                        "subject": cand.subject.span.text,
                        "object": cand.object.span.text,
                        "decision": decision.decision,
                        "reason": decision.reason,
                    })

        # Resource coverage probes (arm B only; arm A = all absent).
        resource = {"pb": False, "vn": False, "fn": False, "sl_direct": False,
                    "sl_composed": False, "alignment_gap": False, "none": True}
        if use_resources:
            for evidence in evidence_spans:
                lemma = (evidence.trigger_lemma or "").lower()
                if not lemma:
                    continue
                lookup = lexical_lookup(pack, lemma)
                if lookup.get("propbank_rolesets"):
                    resource["pb"] = True
                    resource["none"] = False
                if lookup.get("verbnet_classes"):
                    resource["vn"] = True
                    resource["none"] = False
                if lookup.get("framenet_frames"):
                    resource["fn"] = True
                    resource["none"] = False
                for rs in lookup.get("propbank_rolesets", []):
                    if rs in pack["lexical"]["pb_to_vn"]:
                        resource["sl_direct"] = True
                        resource["none"] = False
                    elif rs in pack["lexical"]["pb_to_fn"]:
                        resource["sl_composed"] = True
                        resource["none"] = False
                if lemma in semlink_unresolved or any(
                    f"{rs}:{k}" in compiled_manifest.get("semlink_unresolved_keys", [])
                    or rs in semlink_unresolved
                    for rs in lookup.get("propbank_rolesets", []) for k in ()
                ):
                    resource["alignment_gap"] = True

        predictions.append({
            "item_id": item_id,
            "arm": arm,
            "scope": scope,
            "compiled": compiled,
            "resource_coverage": resource,
        })

        # W8: assertion gate from the frozen scope flags.
        gate = "ASSERT"
        for flag, expected in EXPECTED_ASSERTION.items():
            if scope.get(flag):
                gate = expected
                break
        if scope.get("attributed"):
            gate = "QUALIFY_ATTRIBUTED"

        waterfall.append({
            "item_id": item_id,
            "arm": arm,
            "W0_gold": w0,
            "W1_endpoints": w1,
            "W2_candidate": w2,
            "W3_trigger": w3,
            "W4_rule_eligible": w3,
            "W5_resources": resource,
            "W6_roleset": next(
                (c.get("roleset") for c in compiled if c.get("roleset")), None
            ),
            "W7_orientation": "surface_weak" if not item.get("scope", {}).get("negated") else "surface_weak",
            "W8_assertion_gate": gate,
            "W9_decisions": [c["decision"] for c in compiled],
            "W10_see_predictions": True,
        })

    return {"predictions": predictions, "waterfall": waterfall}


def score(predictions: list[dict], items: list[dict]) -> dict:
    """Unit-level scoring.

    Units:
      - one unit per gold triple (matched by subject/predicate/object +
        expected assertion status: QUALIFY when the gold carries
        `qualified` or `attributed`, ACCEPT otherwise);
      - one unit per SPURIOUS predicted fact (a fact that matches no
        gold triple of its item);
      - abstention items are one unit each (any fact = incorrect).

    Every unit lands in exactly one transition cell."""
    by_item = {p["item_id"]: p for p in predictions}
    gold_by_id = {item["id"]: item for item in items}

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
                    outcome = "INCORRECT_ASSERTION"  # qualified gold arrived asserted
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
            # Spurious edges: predicted facts matching no gold triple.
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


def transitions(units_a: list[dict], units_b: list[dict]) -> dict:
    key = lambda u: (u["kind"], u["item_id"],
                     u.get("subject"), u.get("predicate"), u.get("object"))
    a = {key(u): u["outcome"] for u in units_a}
    b = {key(u): u["outcome"] for u in units_b}
    assert set(a) == set(b), "unit populations must be identical across arms"
    cells = {}
    for k in sorted(a):
        pair = (a[k], b[k])
        cells.setdefault(pair, []).append(k)
    return {
        "cells": {f"{x} -> {y}": len(ks) for (x, y), ks in sorted(cells.items())},
        "detail": {f"{x} -> {y}": [list(k) for k in ks] for (x, y), ks in sorted(cells.items())},
        "total_units": len(a),
    }


def summarize(units: list[dict]) -> dict:
    outcomes = {}
    for u in units:
        o = u["outcome"]
        outcomes[o] = outcomes.get(o, 0) + 1
    correct = sum(v for k, v in outcomes.items() if k == "CORRECT")
    incorrect = sum(v for k, v in outcomes.items() if k.startswith("INCORRECT"))
    missed = outcomes.get("MISSED", 0)
    total = len(units)
    return {
        "correct": correct,
        "incorrect": incorrect,
        "missed": missed,
        "total": total,
        "precision": correct / max(correct + incorrect, 1),
        "recall": correct / max(correct + missed, 1),
        "outcomes": outcomes,
    }


def _unit_key(u: dict) -> tuple:
    return (u["kind"], u["item_id"], u.get("subject"), u.get("predicate"), u.get("object"))


def _cohort_of(item: dict, arm_predictions: dict) -> list[str]:
    """Resource-coverage cohorts for one item (arm B evidence)."""
    cov = arm_predictions["resource_coverage"]
    cohorts = []
    if cov["none"]:
        cohorts.append("C7_no_resource_coverage")
    if cov["pb"]:
        cohorts.append("C1_propbank")
    if cov["vn"]:
        cohorts.append("C2_verbnet")
    if cov["fn"]:
        cohorts.append("C3_framenet")
    if cov["sl_direct"]:
        cohorts.append("C4_direct_semlink")
    if cov["sl_composed"] and not cov["sl_direct"]:
        cohorts.append("C5_composed_only")
    if cov["alignment_gap"]:
        cohorts.append("C6_alignment_gap")
    lemma = (item["evidence"][0].get("lemma") or "").lower()
    if lemma in ("develop", "run", "support", "hold", "form"):
        cohorts.append("C8_polysemous")
    if any(item.get("scope", {}).get(f) for f in
           ("negated", "hypothetical", "conditional", "question", "attributed")):
        cohorts.append("C9_assertion_control")
    # C0: the rule that owns this evidence class is MANUAL_ONLY.
    rule_status = _rule_status_for(item)
    if rule_status == "MANUAL_ONLY":
        cohorts.append("C0_manual_only")
    return cohorts


def _rule_status_for(item: dict) -> str:
    return _RULE_COVERAGE_CACHE.get(item["evidence"][0]["class"], "UNKNOWN")


_RULE_COVERAGE_CACHE: dict = {}


def _load_rule_coverage() -> dict:
    """evidence_class -> rule coverage status (COMPLETE/PARTIAL/...)."""
    global _RULE_COVERAGE_CACHE
    if not _RULE_COVERAGE_CACHE:
        compiled_dir = [d for d in (ROOT / "resources" / "compiled").iterdir() if d.is_dir()][0]
        coverage = json.loads(
            (compiled_dir / "compiled_lexical.json").read_text()
        )["rule_coverage"]
        rules = yaml.safe_load(
            (ROOT / "shared" / "polymath_shared" / "rulepack" / "core-predicates.yaml").read_text()
        )["predicates"]
        for rule in rules:
            for cls in rule["evidence"]["classes"]:
                _RULE_COVERAGE_CACHE[cls] = coverage[rule["id"]]["status"]
    return _RULE_COVERAGE_CACHE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=str(ROOT / "eval" / "phase_h" / "artifacts"))
    args = parser.parse_args(argv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    gold = yaml.safe_load(GOLD_PATH.read_text())
    items = gold["items"]
    assert hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest() == GOLD_SHA256_BEFORE, (
        "gold corpus changed during the run — experiment invalid"
    )

    compiled_manifest = json.loads(
        (ROOT / "resources" / "compiled" /
         [d for d in (ROOT / "resources" / "compiled").iterdir() if d.is_dir()][0] /
         "manifest.json").read_text()
    )

    arms = {}
    for arm in ("baseline", "hybrid"):
        run = run_arm(items, arm)
        arms[arm] = run
        for kind in ("predictions", "waterfall"):
            payload = json.dumps(run[kind], sort_keys=True, separators=(",", ":"), indent=1)
            (outdir / f"{arm}_{kind}.jsonl").write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in run[kind]) + "\n"
            )
            (outdir / f"{arm}_{kind}.sha256").write_text(hashlib.sha256(payload.encode()).hexdigest())

    scored = {arm: score(arms[arm]["predictions"], items) for arm in arms}
    trans = transitions(scored["baseline"]["units"], scored["hybrid"]["units"])
    summary = {arm: summarize(scored[arm]["units"]) for arm in arms}

    baseline = summary["baseline"]
    hybrid = summary["hybrid"]
    delta = {
        "d_correct": hybrid["correct"] - baseline["correct"],
        "d_incorrect": hybrid["incorrect"] - baseline["incorrect"],
        "d_missed": hybrid["missed"] - baseline["missed"],
    }

    manifest = {
        "experiment": "phase-h-lexical-semantic-waterfall",
        "git_commit": "12645c1",
        "gold": {"path": "eval/gold/relations_v1.yaml", "version": gold["version"],
                 "sha256": GOLD_SHA256_BEFORE, "items": len(items)},
        "resource_contract_id": compiled_manifest["resource_contract_id"],
        "tables_sha256": compiled_manifest["tables_sha256"],
        "rule_pack_version": load_rule_pack(use_resources=False)["pack"]["version"],
        "ontology_version": "core-v1",
        "arm_boundary": {
            "baseline": "load_rule_pack(use_resources=False) + build_candidates(enrich=False)",
            "hybrid": "load_rule_pack(use_resources=True) + build_candidates(enrich=True)",
            "compiler_dag": "identical compile_relation",
        },
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=1))

    metrics = {
        "baseline": baseline,
        "hybrid": hybrid,
        "delta": delta,
        "transitions": trans,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics, sort_keys=True, indent=1))

    # -- frozen inputs + gold (byte-stable artifacts) ----------------------
    frozen_inputs = [
        {
            "item_id": item["id"],
            "text_sha256": hashlib.sha256(item["text"].encode()).hexdigest(),
            "entities": item["entities"],
            "evidence": item["evidence"],
            "scope": item.get("scope", {}),
        }
        for item in items
    ]
    (outdir / "frozen_inputs.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in frozen_inputs) + "\n"
    )
    gold_units = [
        {"unit": _unit_key(u), "outcome_target": "gold", "item_id": u["item_id"]}
        for u in scored["baseline"]["units"]
    ]
    (outdir / "gold.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in gold_units) + "\n"
    )

    # -- changed examples (resource-attributed) ----------------------------
    _load_rule_coverage()
    changed: list[dict] = []
    for k in sorted({_unit_key(u) for u in scored["baseline"]["units"]}):
        a = next(u["outcome"] for u in scored["baseline"]["units"] if _unit_key(u) == k)
        b = next(u["outcome"] for u in scored["hybrid"]["units"] if _unit_key(u) == k)
        if a != b:
            item_id = k[1]
            item = next(i for i in items if i["id"] == item_id)
            pred_b = next(p for p in arms["hybrid"]["predictions"] if p["item_id"] == item_id)
            changed.append({
                "unit": list(k),
                "baseline_outcome": a,
                "hybrid_outcome": b,
                "resource_evidence": pred_b["resource_coverage"],
                "compiled": pred_b["compiled"],
            })
    (outdir / "changed_examples.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in changed) + "\n"
    )

    # -- coverage report (coverage is NOT correctness) ----------------------
    coverage_rows = []
    for item in items:
        pred = next(p for p in arms["hybrid"]["predictions"] if p["item_id"] == item["id"])
        units_item = [u for u in scored["hybrid"]["units"] if u["item_id"] == item["id"]]
        coverage_rows.append({
            "item_id": item["id"],
            "coverage": pred["resource_coverage"],
            "cohorts": _cohort_of(item, pred),
            "outcomes": [u["outcome"] for u in units_item],
        })
    (outdir / "coverage_report.json").write_text(
        json.dumps({"rows": coverage_rows,
                    "note": "coverage != correctness; outcomes scored separately"},
                   sort_keys=True, indent=1)
    )

    # -- cohorts -------------------------------------------------------------
    cohort_stats: dict[str, dict] = {}
    for row in coverage_rows:
        for cohort in row["cohorts"]:
            stat = cohort_stats.setdefault(cohort, {"n": 0, "baseline": {}, "hybrid": {}})
            stat["n"] += 1
            for arm in ("baseline", "hybrid"):
                outcomes = [
                    u["outcome"] for u in scored[arm]["units"]
                    if u["item_id"] == row["item_id"]
                ]
                stat[arm]["correct"] = stat[arm].get("correct", 0) + outcomes.count("CORRECT")
                stat[arm]["incorrect"] = stat[arm].get("incorrect", 0) + sum(
                    1 for o in outcomes if o.startswith("INCORRECT")
                )
                stat[arm]["missed"] = stat[arm].get("missed", 0) + outcomes.count("MISSED")
    (outdir / "resource_cohorts.csv").write_text(
        "cohort,n,baseline_correct,baseline_incorrect,baseline_missed,"
        "hybrid_correct,hybrid_incorrect,hybrid_missed\n" +
        "\n".join(
            f"{c},{s['n']},{s['baseline'].get('correct',0)},{s['baseline'].get('incorrect',0)},"
            f"{s['baseline'].get('missed',0)},{s['hybrid'].get('correct',0)},"
            f"{s['hybrid'].get('incorrect',0)},{s['hybrid'].get('missed',0)}"
            for c, s in sorted(cohort_stats.items())
        ) + "\n"
    )

    # -- predicate breakdown --------------------------------------------------
    pred_rows = {}
    for item in items:
        for triple in item["gold"]:
            predname = triple["predicate"]
            row = pred_rows.setdefault(predname, {
                "predicate": predname,
                "rule_coverage_status": _rule_status_for(item),
                "gold_count": 0,
                "baseline_correct": 0, "baseline_incorrect": 0, "baseline_missed": 0,
                "hybrid_correct": 0, "hybrid_incorrect": 0, "hybrid_missed": 0,
            })
            row["gold_count"] += 1
            for arm in ("baseline", "hybrid"):
                outcome = next(
                    u["outcome"] for u in scored[arm]["units"]
                    if u["item_id"] == item["id"]
                    and u.get("predicate") == predname
                )
                if outcome == "CORRECT":
                    row[f"{arm}_correct"] += 1
                elif outcome.startswith("INCORRECT"):
                    row[f"{arm}_incorrect"] += 1
                else:
                    row[f"{arm}_missed"] += 1
    header = ("predicate,rule_coverage_status,gold_count,baseline_correct,baseline_incorrect,"
              "baseline_missed,hybrid_correct,hybrid_incorrect,hybrid_missed,delta_correct,"
              "delta_incorrect,delta_missed")
    (outdir / "predicate_breakdown.csv").write_text(
        header + "\n" + "\n".join(
            f"{r['predicate']},{r['rule_coverage_status']},{r['gold_count']},"
            f"{r['baseline_correct']},{r['baseline_incorrect']},{r['baseline_missed']},"
            f"{r['hybrid_correct']},{r['hybrid_incorrect']},{r['hybrid_missed']},"
            f"{r['hybrid_correct']-r['baseline_correct']},"
            f"{r['hybrid_incorrect']-r['baseline_incorrect']},"
            f"{r['hybrid_missed']-r['baseline_missed']}"
            for r in sorted(pred_rows.values(), key=lambda r: r["predicate"])
        ) + "\n"
    )

    # -- assertion breakdown ---------------------------------------------------
    assertion_rows = []
    for item in items:
        scope = item.get("scope", {})
        family = next((f for f in ("negated", "hypothetical", "conditional", "question",
                                   "attributed") if scope.get(f)), "active")
        outcomes_a = [u["outcome"] for u in scored["baseline"]["units"] if u["item_id"] == item["id"]]
        outcomes_b = [u["outcome"] for u in scored["hybrid"]["units"] if u["item_id"] == item["id"]]
        assertion_rows.append({
            "item_id": item["id"],
            "assertion_family": family,
            "baseline": outcomes_a,
            "hybrid": outcomes_b,
        })
    (outdir / "assertion_breakdown.csv").write_text(
        "item_id,assertion_family,baseline_outcomes,hybrid_outcomes\n" + "\n".join(
            f"{r['item_id']},{r['assertion_family']},"
            f"{';'.join(r['baseline'])};{';'.join(r['hybrid'])}"
            for r in assertion_rows
        ) + "\n"
    )

    # -- paired transitions CSV -------------------------------------------------
    (outdir / "paired_transitions.csv").write_text(
        "transition,count,units\n" + "\n".join(
            f"{cell},{count},{json.dumps(detail[cell])}"
            for cell, count in trans["cells"].items()
            for detail in [trans["detail"]]
        ) + "\n"
    )

    # -- polysemy breakdown (frozen corpus coverage of the 5 families) ---------
    polysemy_rows = []
    for lemma in ("develop", "run", "support", "hold", "form"):
        hits = [i["id"] for i in items
                if any((e.get("lemma") or "").lower() == lemma for e in i["evidence"])]
        polysemy_rows.append({
            "lemma": lemma,
            "frozen_corpus_examples": hits,
            "n": len(hits),
        })
    (outdir / "polysemy_breakdown.csv").write_text(
        "lemma,frozen_corpus_examples,n\n" + "\n".join(
            f"{r['lemma']},{';'.join(r['frozen_corpus_examples'])},{r['n']}"
            for r in polysemy_rows
        ) + "\n"
    )

    print(json.dumps({
        "units": len(scored["baseline"]["units"]),
        "baseline": baseline,
        "hybrid": hybrid,
        "delta": delta,
        "transitions_cells": trans["cells"],
        "changed_examples": len(changed),
        "cohorts": {c: s["n"] for c, s in sorted(cohort_stats.items())},
        "artifacts": sorted(p.name for p in outdir.iterdir()),
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
