"""CHAT-REGRESSION-MANIFEST-V1 (CHAT-QUERY-COMPILER-PLAN §4 P1.g / §5 / §5b): the frozen chat
qualification suite, evaluated offline in CI (determinism.yml — no services, no GPU, no corpus).

For every case in eval/regression/chat_regression_manifest.json:
  recorded-floor  the committed experiment JSON is opened and each metric must clear its floor AND
                  still equal the value the manifest froze (an in-place re-recording is DRIFT;
                  `scripts/chat_regression.py --refresh` re-freezes deliberately);
  offline-test    every referenced pytest function must still exist (import the module, check the
                  attribute) so a deleted test fails this suite;
  pending         skipped with the owner phase and the metric it must record — never a silent pass.
The evaluation helpers are scripts/chat_regression.py (`--check` prints the same rows)."""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location("chat_regression", ROOT / "scripts" / "chat_regression.py")
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)

MANIFEST = cr.load_manifest(ROOT / "eval" / "regression" / "chat_regression_manifest.json")
CASES = MANIFEST["cases"]
CHECKS = [(c, chk) for c in CASES for chk in c.get("checks") or []]
TEST_REFS = [(c, ref) for c in CASES for ref in c.get("offline_tests") or []]
PENDING = [c for c in CASES if c["kind"] == "pending"]
FROZEN_IDS = [
    "01-grounded-qa", "02-exact-identifier", "03-multi-aspect", "04-compare", "05-followup",
    "06-transform-no-retrieval", "07-continue-artifact", "08-corpus-creation", "09-absent-term-abstention",
    "10-carry-contamination", "11-mode-invariants", "12-degraded-deadline", "13-route-parity",
    "14-citation-validity", "15-funnel-accounting", "16-sparse-lane-regression",
]


def test_manifest_is_the_frozen_sixteen_case_contract():
    assert MANIFEST["contract"] == cr.CONTRACT and MANIFEST["frozen"]
    assert [c["id"] for c in CASES] == FROZEN_IDS, "the 16-case list is frozen; add evidence to a case, never a 17th"
    errors = cr.validate_shape(MANIFEST, ROOT)
    assert not errors, "\n".join(errors)
    kinds = cr.counts(MANIFEST)
    # 2026-09-06 acceptance: P1.d / P1.e / P1.f recorded their metrics — no pending entry is left (a new pending
    # entry needs a new owner phase in the plan, never a silent demotion of a recorded floor)
    assert sum(kinds.values()) == 16 and kinds["pending"] == 0, kinds
    for case in CASES:
        if case["kind"] == "pending":
            assert not case.get("checks"), f"{case['id']}: a pending case has no recorded floor by definition"
    for case, check in CHECKS:
        op, bound = cr.bound_of(check)
        if op != "equals" and isinstance(check["recorded"], (int, float)) and not isinstance(check["recorded"], bool):
            # the floor is a bound the recording CLEARS; equality is reserved for all-or-nothing counts
            assert cr.passes(check["recorded"], op, bound), f"{case['id']} {check['metric']}: frozen value does not clear its own floor"


def test_baseline_and_known_bad_references_still_read_their_stated_values():
    errors = cr.reference_mismatches(MANIFEST, ROOT)
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("case,check", CHECKS, ids=[f"{c['id']}/{chk['metric']}" for c, chk in CHECKS])
def test_recorded_metric_clears_its_floor(case, check):
    source = check.get("file") or case["source"]["file"]        # a check may pin a sibling recording
    doc = cr.load_json(ROOT, source)
    op, bound = cr.bound_of(check)
    try:
        value = cr.read_metric(doc, check)
    except KeyError as exc:
        pytest.fail(f"{case['id']} ({case['name']}): metric {check['metric']!r} missing in {source}: {exc}")
    assert cr.passes(value, op, bound), (
        f"{case['id']} ({case['name']}): {check['metric']} = {value!r} violates floor {cr.describe_bound(op, bound)} "
        f"(recorded {check['recorded']!r} in run {case['source']['run']}, file {source})")
    assert value == check["recorded"], (
        f"{case['id']}: {source} now says {check['metric']} = {value!r} but the manifest froze {check['recorded']!r}; "
        f"experiment JSONs are immutable — re-freeze deliberately with scripts/chat_regression.py --refresh {case['id']}=<new json>")


@pytest.mark.parametrize("case,ref", TEST_REFS, ids=[f"{c['id']}/{ref.rsplit('::', 1)[-1]}" for c, ref in TEST_REFS])
def test_offline_test_reference_still_exists(case, ref):
    ok, why = cr.offline_test_exists(ref, ROOT)
    assert ok, f"{case['id']} ({case['name']}) lost its instrument: {why}"


@pytest.mark.parametrize("case", PENDING, ids=[c["id"] for c in PENDING])
def test_pending_case_names_its_owner_and_the_metric_to_record(case):
    pend = case["pending"]
    assert pend["owner"] == case["gate_owner"] and pend["metric"] and pend["instrument"] and pend["why_pending"]
    pytest.skip(f"{case['id']} pending — {pend['owner']} must record: {pend['metric'][:160]} …")


# ------------------------------------------------------------------ the evaluator itself
def _synthetic(tmp_path, summary: dict, rows: list | None = None) -> str:
    (tmp_path / "docs").mkdir(exist_ok=True)
    path = tmp_path / "docs" / f"run-{len(list((tmp_path / 'docs').glob('*.json')))}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows or []}))
    return path.relative_to(tmp_path).as_posix()


def _case(source: str, checks: list[dict]) -> dict:
    return {"id": "01-grounded-qa", "name": "synthetic", "kind": "recorded-floor", "gate_owner": "P1.a", "plan_refs": "test",
            "source": {"file": source, "run": "synthetic"}, "checks": checks}


def test_evaluator_reports_pass_fail_drift_and_missing(tmp_path):
    good = _synthetic(tmp_path, {"hit@10_selected": 0.7, "deaths": {"CITED": 20, "LOST": 10}, "per_arm": {"multi": {"wall_p50_s": 10.76}, "single": {"wall_p50_s": 10.35}}},
                      rows=[{"set": "fixture", "name": "brainrot_transform", "queries": [], "retrieval_required": False}])
    checks = [
        {"metric": "hit", "pointer": "/summary/hit@10_selected", "min": 0.6, "recorded": 0.7},
        {"metric": "deaths", "pointer": "/summary/deaths", "reduce": "sum", "equals": 30, "recorded": 30},
        {"metric": "delta", "pointer": "/summary/per_arm/multi/wall_p50_s", "minus": "/summary/per_arm/single/wall_p50_s", "max": 3.0, "recorded": 0.41},
        {"metric": "queries", "pointer": "/rows", "select": {"set": "fixture", "name": "brainrot_transform"}, "field": "/queries", "reduce": "len", "max": 0, "recorded": 0},
        {"metric": "flag", "pointer": "/rows", "select": {"name": "brainrot_transform"}, "field": "/retrieval_required", "equals": False, "recorded": False},
    ]
    rows = cr.evaluate_case(_case(good, checks), tmp_path)
    assert [r["result"] for r in rows] == ["PASS"] * 5, rows
    regressed = _synthetic(tmp_path, {"hit@10_selected": 0.5, "deaths": {"CITED": 20, "LOST": 9}})
    rows = cr.evaluate_case(_case(regressed, checks[:2] + [{"metric": "gone", "pointer": "/summary/nope", "max": 0, "recorded": 0}]), tmp_path)
    assert [r["result"] for r in rows] == ["FAIL", "FAIL", "MISSING"], rows
    assert "violates" in rows[0]["detail"] and "nope" in rows[2]["detail"]
    drifted = _synthetic(tmp_path, {"hit@10_selected": 0.75})
    rows = cr.evaluate_case(_case(drifted, checks[:1]), tmp_path)
    assert rows[0]["result"] == "DRIFT" and "re-freeze" in rows[0]["detail"]
    assert cr.failures(rows) and not cr.failures(cr.evaluate_case(_case(good, checks), tmp_path))


def test_a_check_may_pin_a_sibling_recording_and_refresh_leaves_it_alone(tmp_path):
    main = _synthetic(tmp_path, {"tag": "main", "per_arm": {"single": {"degraded_turns": 10, "errors": 0}}})
    sibling = _synthetic(tmp_path, {"tag": "sibling", "per_arm": {"single": {"degraded_turns": 10, "errors": 1}}})
    checks = [{"metric": "lane: degraded", "pointer": "/summary/per_arm/single/degraded_turns", "min": 10, "recorded": 10},
              {"metric": "rerank: errors", "file": sibling, "pointer": "/summary/per_arm/single/errors", "max": 0, "recorded": 0}]
    rows = cr.evaluate_case(_case(main, checks), tmp_path)
    assert [r["result"] for r in rows] == ["PASS", "FAIL"] and rows[1]["source"] == sibling, rows
    assert cr.validate_shape({"contract": cr.CONTRACT, "cases": [_case(main, [dict(checks[1], file="docs/absent.json")])] * 16}, tmp_path)
    better = _synthetic(tmp_path, {"tag": "better", "per_arm": {"single": {"degraded_turns": 12, "errors": 0}}})
    manifest = {"contract": cr.CONTRACT, "cases": [_case(main, [dict(c) for c in checks])]}
    cr.refresh(manifest, "01-grounded-qa", better, tmp_path, today="2026-09-06")
    case = manifest["cases"][0]
    assert case["source"]["file"] == better and case["checks"][0]["recorded"] == 12
    assert case["checks"][1]["file"] == sibling and case["checks"][1]["recorded"] == 0     # pinned check untouched


def test_refresh_refreezes_a_better_recording_and_refuses_a_regressed_one(tmp_path):
    old = _synthetic(tmp_path, {"tag": "old", "hit@10_selected": 0.7})
    better = _synthetic(tmp_path, {"tag": "better", "hit@10_selected": 0.8})
    worse = _synthetic(tmp_path, {"tag": "worse", "hit@10_selected": 0.55})
    manifest = {"contract": cr.CONTRACT, "cases": [_case(old, [{"metric": "hit", "pointer": "/summary/hit@10_selected", "min": 0.6, "recorded": 0.7}])]}
    with pytest.raises(ValueError, match="violates floor"):
        cr.refresh(manifest, "01-grounded-qa", worse, tmp_path, today="2026-09-05")
    assert manifest["cases"][0]["source"]["file"] == old and manifest["cases"][0]["checks"][0]["recorded"] == 0.7   # untouched
    rows = cr.refresh(manifest, "01-grounded-qa", better, tmp_path, today="2026-09-05")
    case = manifest["cases"][0]
    assert case["source"]["file"] == better and case["source"]["run"] == "better"
    assert case["source"]["refreshed"] == {"from": old, "previous_run": "synthetic", "on": "2026-09-05"}
    assert case["checks"][0]["recorded"] == 0.8 and case["checks"][0]["min"] == 0.6      # the floor never moves
    assert [r["result"] for r in rows] == ["PASS"]
    with pytest.raises(ValueError, match="unknown case id"):
        cr.refresh(manifest, "99-nope", better, tmp_path)


def test_offline_reference_lookup_detects_a_missing_function(tmp_path):
    ok, _ = cr.offline_test_exists("tests/determinism/test_chat_regression_suite.py::test_manifest_is_the_frozen_sixteen_case_contract", ROOT)
    assert ok
    ok, why = cr.offline_test_exists("tests/determinism/test_chat_regression_suite.py::test_that_never_existed", ROOT)
    assert not ok and "not found" in why
    ok, why = cr.offline_test_exists("tests/determinism/no_such_file.py::test_x", ROOT)
    assert not ok and "missing" in why


def test_acceptance_table_has_one_row_per_check_test_and_pending_case():
    table = cr.acceptance_table(MANIFEST, ROOT).splitlines()
    assert table[0] == "| capability | baseline | final | gate | result |"
    expected = len(CHECKS) + len(TEST_REFS) + len(PENDING)
    assert len(table) - 2 == expected, (len(table) - 2, expected)
    assert sum(1 for line in table if "| PENDING (" in line) == len(PENDING)
    assert all(("| PASS |" in line) or ("| EXISTS |" in line) or ("| PENDING (" in line) for line in table[2:]), \
        [line for line in table[2:] if not (("| PASS |" in line) or ("| EXISTS |" in line) or ("| PENDING (" in line))]
