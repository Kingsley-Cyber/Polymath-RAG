"""CORPUS-PLAN-V1 parity: Polymath's compiler is the TRAIL OS compiler."""
import json
from pathlib import Path

from orchestrator.api.corpus_plan import compile_plan

ROOT = Path(__file__).resolve().parents[2]
FIX = json.loads((ROOT / "contracts/retrieve/v1/corpus_plan_fixture.json").read_text())


def test_plan_matches_frozen_fixture_ids_and_kinds():
    plan = compile_plan(FIX["signal"])
    assert [(q["id"], q["kind"], q["query"]) for q in plan] == [(q["id"], q["kind"], q["query"]) for q in FIX["expected"]]


def test_plan_is_deterministic_and_bounded():
    a = compile_plan(FIX["signal"]); b = compile_plan(FIX["signal"])
    assert a == b and 3 <= len(a) <= 5
    assert len({q["query"] for q in a}) == len(a)


def test_plain_signal_still_gets_a_plan():
    assert len(compile_plan("context probe signal")) >= 1


def test_sample_rows_validate_against_the_row_contract():
    import jsonschema  # type: ignore
    schema = json.loads((ROOT / "contracts/retrieve/v1/evidence_row.schema.json").read_text())
    sample = json.loads((ROOT / "contracts/retrieve/v1/evidence_rows_sample.json").read_text())
    for row in sample["evidence_rows"]:
        jsonschema.validate(row, schema)
