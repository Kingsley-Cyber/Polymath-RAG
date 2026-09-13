"""contracts/adapter/v1 (ADR-0018, COGNITIVE-ADAPTER-TRAIL-E2E-V1 E1): every example validates against its schema and the
invariants the schema cannot express hold — closed step vocabulary, manifest graph integrity (unique ids, every `next`/branch
target exists, entry/terminal declared, terminal reachable, COMPILE_RESULT is the only terminal type), identity fields shared by
run/status/result, and no executable definitions anywhere in a manifest."""
from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
V1 = ROOT / "contracts" / "adapter" / "v1"
NAMES = ["adapter_manifest", "adapter_run_request", "adapter_run_ref", "adapter_run_status", "adapter_step",
         "adapter_submission", "adapter_step_receipt", "external_operation_receipt", "adapter_result"]
STEP_TYPES = {"POLYMATH_RETRIEVE", "POLYMATH_COMPILE_PLAN", "POLYMATH_GRAPH_EXPAND", "EXTERNAL_OPERATION",
              "AGENT_REASON", "VALIDATE", "BRANCH", "COMPILE_RESULT"}


def _load(name):
    return (json.loads((V1 / f"{name}.schema.json").read_text()), json.loads((V1 / f"{name}.example.json").read_text()))


@pytest.mark.parametrize("name", NAMES)
def test_example_validates_against_schema(name):
    schema, example = _load(name)
    assert schema["$id"] == f"polymath/contracts/adapter/v1/{name}.schema.json"
    assert schema["title"] and schema["description"]
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(example)


def test_step_vocabulary_is_closed_and_identical_everywhere():
    for name, path in (("adapter_manifest", ("$defs", "step_def", "properties", "type", "enum")),
                       ("adapter_step", ("properties", "step_type", "enum")),
                       ("adapter_step_receipt", ("properties", "step_type", "enum"))):
        node = _load(name)[0]
        for k in path:
            node = node[k]
        assert set(node) == STEP_TYPES, name


def test_manifest_graph_integrity():
    _, m = _load("adapter_manifest")
    ids = [s["step_id"] for s in m["steps"]]
    assert len(ids) == len(set(ids)), "duplicate step_id"
    by_id = {s["step_id"]: s for s in m["steps"]}
    assert m["entry_step_id"] in by_id and m["terminal_step_id"] in by_id
    assert by_id[m["terminal_step_id"]]["type"] == "COMPILE_RESULT"
    for s in m["steps"]:
        nxt = s.get("next")
        if s["type"] == "COMPILE_RESULT":
            assert nxt is None, "the terminal step has no successor"
        else:
            assert nxt in by_id, f"{s['step_id']} -> unknown next {nxt!r}"
        for b in s.get("branches", []):
            assert b["next"] in by_id, f"{s['step_id']} branch -> unknown {b['next']!r}"
        if s["type"] == "AGENT_REASON":
            assert s.get("objective") and s.get("output_schema"), "an AGENT_REASON step must carry objective + output_schema"
        if s["type"] == "EXTERNAL_OPERATION":
            assert s["external"]["system"] == "trailsignal"
            if s["external"].get("availability") == "planned":
                assert s["external"].get("planned_node"), "a planned Trail capability names its graph node"
    # the terminal step is reachable from the entry by following next/branches
    seen, todo = set(), [m["entry_step_id"]]
    while todo:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.add(cur)
        s = by_id[cur]
        todo += [x for x in ([s.get("next")] + [b["next"] for b in s.get("branches", [])]) if x]
    assert m["terminal_step_id"] in seen


def test_manifest_carries_no_executable_definitions():
    raw = (V1 / "adapter_manifest.example.json").read_text().lower()
    for forbidden in ("python", "exec(", "eval(", "subprocess", "import ", "lambda", "callback", "shell"):
        assert forbidden not in raw, forbidden


def test_identity_fields_agree_across_run_ref_status_and_result():
    _, m = _load("adapter_manifest"); _, ref = _load("adapter_run_ref"); _, st = _load("adapter_run_status"); _, res = _load("adapter_result")
    keys = ("adapter_id", "adapter_version", "workflow_version", "retrieval_policy_version", "input_schema_version", "output_schema_version")
    for k in keys:
        assert st[k] == m[k] == res[k]
    assert ref["adapter_id"] == m["adapter_id"] and ref["run_id"] == st["run_id"] == res["run_id"]


def test_submission_example_satisfies_its_step_output_schema_and_evidence_rule():
    _, step = _load("adapter_step"); _, sub = _load("adapter_submission")
    assert sub["step_id"] == step["step_id"] and sub["run_id"] == step["run_id"]
    jsonschema.Draft202012Validator(step["output_schema"]).validate(sub["payload"])
    allowed = {r["id"] for r in step["context"]["evidence_refs"]}
    for h in sub["payload"]["hypotheses"]:
        assert set(h["supporting_evidence_ids"]) <= allowed          # cite only supplied evidence


def test_result_lineage_references_only_known_receipts_and_operations():
    _, res = _load("adapter_result"); _, rcpt = _load("adapter_step_receipt"); _, ext = _load("external_operation_receipt")
    assert rcpt["receipt_hash"] in res["lineage"]["step_receipt_hashes"]
    ops = {o["operation_id"] for o in res["lineage"]["external_operations"]}
    assert ext["operation_id"] in ops
    if res["status"] == "terminal_gap":
        assert res["gap"] and res["gap"]["code"]
