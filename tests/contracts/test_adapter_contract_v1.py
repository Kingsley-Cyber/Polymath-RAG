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
         "adapter_submission", "adapter_step_receipt", "external_operation_receipt", "adapter_result",
         "harness_action", "harness_receipt", "hypothesis_state", "hypothesis_transition", "evidence_admission"]
STEP_TYPES = {"POLYMATH_RETRIEVE", "POLYMATH_COMPILE_PLAN", "POLYMATH_GRAPH_EXPAND", "EXTERNAL_OPERATION",
              "AGENT_REASON", "HARNESS_ACTION", "VALIDATE", "BRANCH", "COMPILE_RESULT"}
ROLE_PATTERN = "^[a-z][a-z0-9_]{1,40}$"
ACTION_KINDS = {"AGENT_RESEARCH", "PRODUCT_REALITY_CHECK", "SUPPLIER_RESEARCH"}


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


# ─────────────────────────────────────────────────────────── ADR-0019 (HARNESS-RESEARCH-MIGRATION-V1 R1)
def _enum_at(schema, *path):
    node = schema
    for k in path:
        node = node[k]
    return set(x for x in node["enum"] if x is not None)


def test_evidence_roles_are_domain_data_and_action_kinds_are_closed():
    """Roles are declared by the manifest (`evidence_roles`) and the Trail registry snapshot; the generic contracts only fix their shape."""
    ha, hr, adm, hs, mf = (_load(n)[0] for n in ("harness_action", "harness_receipt", "evidence_admission", "hypothesis_state", "adapter_manifest"))
    assert ha["properties"]["evidence_gaps"]["items"]["properties"]["evidence_role"]["pattern"] == ROLE_PATTERN
    assert ha["properties"]["search_intents"]["items"]["properties"]["evidence_roles"]["items"]["pattern"] == ROLE_PATTERN
    assert hr["properties"]["observations"]["items"]["properties"]["evidence_role_claimed"]["pattern"] == ROLE_PATTERN
    assert adm["properties"]["admitted"]["items"]["properties"]["evidence_role"]["pattern"] == ROLE_PATTERN
    assert hs["properties"]["knowledge_gaps"]["items"]["properties"]["evidence_role"]["pattern"] == ROLE_PATTERN
    assert mf["properties"]["evidence_roles"]["items"]["pattern"] == ROLE_PATTERN
    assert _enum_at(ha, "properties", "action_kind") == ACTION_KINDS
    assert _enum_at(mf, "$defs", "harness_action_kind") == ACTION_KINDS


def test_receipt_and_submission_cannot_carry_a_score_field():
    """LAW 1 at the wire: no model/harness payload has a place for an opportunity score."""
    for name, key in (("harness_receipt", "score"), ("harness_receipt", "opportunity_score"), ("harness_action", "score")):
        schema, example = _load(name)
        bad = {**example, key: 0.9}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(bad)
    schema, example = _load("harness_receipt")
    obs = {**example["observations"][0], "score": 0.9}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate({**example, "observations": [obs]})


def test_hypothesis_transition_requires_a_cause_and_state_keeps_lineage():
    schema, example = _load("hypothesis_transition")
    v = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    with pytest.raises(jsonschema.ValidationError):
        v.validate({**example, "cause_refs": []})
    assert example["cause_refs"] and example["kind"] in {"GENERATE", "REVISE", "SPLIT", "MERGE", "WEAKEN", "STRENGTHEN", "CONTRADICT", "KILL", "PROMOTE"}
    hs_schema, hs = _load("hypothesis_state")
    assert {"parent_hypothesis_ids", "knowledge_support", "trail_priors", "field_evidence_ids", "revision"} <= set(hs)
    ks = jsonschema.Draft202012Validator(hs_schema, format_checker=jsonschema.FormatChecker())
    no_support = {**hs["knowledge_support"][0], "chunk_id": None, "document_id": None, "graph_fact_id": None, "retrieval_trace_id": None}
    with pytest.raises(jsonschema.ValidationError):
        ks.validate({**hs, "knowledge_support": [no_support]})


def test_harness_action_never_names_a_tool_or_engine():
    """The action states intent; the harness picks tools. Contract text stays engine-neutral."""
    text = (V1 / "harness_action.schema.json").read_text().lower() + (V1 / "harness_action.example.json").read_text().lower()
    import re
    for word in ("google", "searxng", "playwright", "crawl4ai", "camofox", "exa", "scraper", "selenium", "puppeteer", "reddit", "amazon", "alibaba"):
        assert re.search(rf"(?<![a-z0-9_]){word}(?![a-z0-9_])", text) is None, word
    _, ex = _load("harness_action")
    assert ex["registry_snapshot"]["snapshot_id"] and ex["minimum_independent_sources"] >= 1


def test_step_context_evidence_kinds_include_admitted_field_evidence_and_priors():
    kinds = _enum_at(_load("adapter_step")[0], "properties", "context", "properties", "evidence_refs", "items", "properties", "kind")
    assert {"field_evidence", "trail_prior"} <= kinds
    lineage = _load("adapter_result")[0]["properties"]["lineage"]["properties"]
    assert {"hypothesis_ids", "admitted_evidence_ids", "harness_action_ids", "harness_ids", "registry_snapshot_ids", "trail_score_record_ids"} <= set(lineage)
