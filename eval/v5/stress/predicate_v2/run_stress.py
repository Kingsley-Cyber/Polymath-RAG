"""PREDICATE-COMPILER-V2 frozen stress driver.

Runs the owner decision record's seven categories against kimi_v2 +
compile_relation_kimi (+ FactAdmissionStage for endpoint durability).
Fixtures are frozen; the pytest wrapper locks their hash. This module
is deterministic and store-free.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import EntitySpan  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import compile_relation_kimi  # noqa: E402
from workers.candidates import SentenceSlice, identities_for  # noqa: E402
from workers.kimi_v2_candidates import build_candidates_kimi_v2  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures.json"
PACK = load_rule_pack(pack_version="1.3.0")


def _load():
    return json.loads(FIXTURES.read_text())


def _entity(case_id, chunk_id, spec, index):
    return EntitySpan(
        doc_id=case_id, chunk_id=chunk_id, start=spec["start"],
        end=spec["end"], text=spec["text"],
        core_type=spec["core_type"], score=0.95,
        extractor_version="stress-fixture")


def _slice(case_id, chunk_id, spec):
    ents = [_entity(case_id, chunk_id, e, spec.get("sentence_index", 0))
            for e in spec["entities"]]
    return SentenceSlice(
        text=spec["text"], sentence_start=0,
        sentence_end=len(spec["text"]), entities=ents, evidence=[],
        parse=None, syntax={"tokens": spec["tokens"]},
        sentence_index=spec.get("sentence_index", 0))


def run_case(case):
    """Return {candidates, decisions, admission_rows} for one case."""
    doc_id = case["id"]
    slices = [_slice(doc_id, f"c{i}", s)
              for i, s in enumerate(case["slices"])]
    identities = identities_for(
        slices, corpus_id="stress-v2", doc_id=doc_id,
        contract_version="admission-harbor-v2")

    candidates = []
    per_slice = []
    for sl in slices:
        cands = build_candidates_kimi_v2(
            [sl], doc_id=doc_id, corpus_id="stress-v2",
            ontology_profile="core",
            extractor_version="stress-fixture",
            rule_pack=PACK, identities=identities)
        candidates.extend(cands)
        per_slice.append((sl, cands))

    decisions = []
    for sl, cands in per_slice:
        row = {"chunk_id": sl.entities[0].chunk_id if sl.entities else "c0",
               "text": sl.text, "region": None}
        for cand in cands:
            d = compile_relation_kimi(cand, sl.parse, PACK,
                                      syntax=sl.syntax)
            decisions.append((cand, d))

    from workers.fact_admission_stage import FactAdmissionStage
    stage = FactAdmissionStage("stress-v2", doc_id, enforce=True)
    for cand, dec in decisions:
        if dec.fact is None:
            continue
        sl = next(s for s, cands in per_slice
                  if any(c is cand for c in cands))
        row = {"chunk_id": cand.subject.span.chunk_id,
               "text": sl.text, "region": None}
        stage.admits(row=row, candidate=cand, decision=dec, sl=sl,
                     identities=identities)

    return {
        "candidates": candidates,
        "decisions": decisions,
        "admission_rows": stage.rows,
        "withheld": stage.withheld,
    }


if __name__ == "__main__":
    data = _load()
    for case in data["cases"]:
        r = run_case(case)
        print(f"== {case['id']}: "
              f"candidates={len(r['candidates'])} "
              f"facts={sum(1 for _, d in r['decisions'] if d.fact)} "
              f"admission={len(r['admission_rows'])}")
