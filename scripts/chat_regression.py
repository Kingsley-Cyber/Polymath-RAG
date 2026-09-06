#!/usr/bin/env python3
"""CHAT-REGRESSION-MANIFEST-V1 — the frozen chat qualification suite (CHAT-QUERY-COMPILER-PLAN §4 P1.g, §5, §5b).

The manifest `eval/regression/chat_regression_manifest.json` names one entry per case of the 16-case
pre-promotion list. Every entry is one of three kinds:

  recorded-floor  a committed experiment JSON under docs/wiki/experiments/ holds the metric; the entry
                  freezes a FLOOR the recorded value clears with margin (never the accidental exact
                  value) and the recorded value with its source run. Re-recording is deliberate:
                  `--refresh <case-id>=<json-path>` re-points the source and re-freezes the values.
  offline-test    the capability is proven by named pytest functions; the suite asserts each still
                  exists, so a deleted test fails the suite.
  pending         the instrument does not exist yet; the entry names the owner phase and the exact
                  metric that owner must record. The suite SKIPS these (never a silent pass).

Any entry may additionally carry `checks` (recorded metrics) and `offline_tests`; all are evaluated
regardless of kind — `kind` names the primary evidence class.

A check reads one value from the source JSON:
  pointer   RFC 6901 JSON pointer into the file
  select    optional {key: value} — when the pointer lands on a list of rows, pick the unique row matching
  field     optional pointer applied inside the selected row
  reduce    optional len | sum | max | min applied to a list (sum/max/min of a dict use its values)
  minus     optional second pointer whose value is subtracted (latency deltas)
  file      optional recording that overrides case.source.file for this one check (a sibling recording of the
            same run family, e.g. the rerank-deadline probe next to the lane-deadline probe); `--refresh` leaves
            such checks alone — re-record them by editing the manifest deliberately
and compares it with exactly one bound: `min` (value ≥ bound), `max` (value ≤ bound), `equals`.

Usage (repo root, no services needed):
  .venv/bin/python scripts/chat_regression.py --check
  .venv/bin/python scripts/chat_regression.py --refresh 01-grounded-qa=docs/wiki/experiments/chat-baseline-<tag>.json
  .venv/bin/python scripts/chat_regression.py --table
Exit 1 when any check fails or any referenced test is missing. tests/determinism/test_chat_regression_suite.py
imports this module and runs the same evaluation in CI (determinism.yml).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "eval" / "regression" / "chat_regression_manifest.json"
CONTRACT = "CHAT-REGRESSION-MANIFEST-V1"
KINDS = ("recorded-floor", "offline-test", "pending")
OPS = ("min", "max", "equals")
CASE_COUNT = 16
CASE_FIELDS = ("id", "name", "kind", "gate_owner", "plan_refs")


# ------------------------------------------------------------------ manifest + JSON access
def load_manifest(path: Path = MANIFEST) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("contract") != CONTRACT:
        raise ValueError(f"{path}: contract {manifest.get('contract')!r} is not {CONTRACT}")
    return manifest


def load_json(root: Path, relative: str) -> dict:
    return json.loads((Path(root) / relative).read_text(encoding="utf-8"))


def resolve_pointer(doc: Any, pointer: str) -> Any:
    """RFC 6901: '' is the whole document; '/a/0/b~1c' walks dicts by key and lists by index."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise KeyError(f"pointer must start with '/': {pointer!r}")
    node = doc
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                raise KeyError(f"{pointer}: key {token!r} absent (have {sorted(node)[:12]}…)")
            node = node[token]
        elif isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError) as exc:
                raise KeyError(f"{pointer}: bad list index {token!r} ({exc})") from exc
        else:
            raise KeyError(f"{pointer}: cannot descend into {type(node).__name__} at {token!r}")
    return node


def select_row(rows: Any, select: dict) -> dict:
    if not isinstance(rows, list):
        raise KeyError(f"select needs a list of rows, got {type(rows).__name__}")
    hits = [r for r in rows if isinstance(r, dict) and all(r.get(k) == v for k, v in select.items())]
    if len(hits) != 1:
        raise KeyError(f"select {select} matched {len(hits)} rows (need exactly 1)")
    return hits[0]


def _reduce(value: Any, how: str) -> Any:
    items = list(value.values()) if isinstance(value, dict) else list(value)
    if how == "len":
        return len(items)
    numbers = [0 if v is None else v for v in items]
    if how == "sum":
        return sum(numbers)
    if how == "max":
        return max(numbers) if numbers else 0
    if how == "min":
        return min(numbers) if numbers else 0
    raise KeyError(f"unknown reduce {how!r}")


def read_metric(doc: Any, check: dict) -> Any:
    value = resolve_pointer(doc, check["pointer"])
    if "select" in check:
        value = select_row(value, check["select"])
    if "field" in check:
        value = resolve_pointer(value, check["field"])
    if "reduce" in check:
        value = _reduce(value, check["reduce"])
    if "minus" in check:
        value = round(float(value) - float(resolve_pointer(doc, check["minus"])), 3)
    return value


def bound_of(check: dict) -> tuple[str, Any]:
    ops = [op for op in OPS if op in check]
    if len(ops) != 1:
        raise ValueError(f"check {check.get('metric')!r} must carry exactly one of {OPS}, has {ops}")
    return ops[0], check[ops[0]]


def passes(value: Any, op: str, bound: Any) -> bool:
    if op == "equals":
        return value == bound
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value >= bound if op == "min" else value <= bound


def describe_bound(op: str, bound: Any) -> str:
    return {"min": "≥", "max": "≤", "equals": "=="}[op] + f" {json.dumps(bound)}"


# ------------------------------------------------------------------ offline test references
def offline_test_exists(node_id: str, root: Path = ROOT) -> tuple[bool, str]:
    """`<file>::<function>` — import the test module from its file and check the attribute is callable."""
    file_part, _, func = node_id.partition("::")
    path = Path(root) / file_part
    if not func or not path.exists():
        return False, f"{node_id}: file missing or node id malformed"
    spec = importlib.util.spec_from_file_location("chat_regression_ref_" + path.stem, path)
    if spec is None or spec.loader is None:
        return False, f"{node_id}: cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — a broken module is a missing instrument
        return False, f"{node_id}: import failed: {type(exc).__name__}: {str(exc)[:160]}"
    if not callable(getattr(module, func, None)):
        return False, f"{node_id}: function {func!r} not found in {file_part}"
    return True, "exists"


# ------------------------------------------------------------------ evaluation
def evaluate_case(case: dict, root: Path = ROOT) -> list[dict]:
    """One row per check / offline test / pending metric: PASS, FAIL, MISSING, DRIFT, EXISTS, ABSENT, PENDING."""
    rows: list[dict] = []
    source = (case.get("source") or {}).get("file")
    docs: dict[str, tuple[Any, str | None]] = {}

    def _doc(path: str) -> tuple[Any, str | None]:
        if path not in docs:
            try:
                docs[path] = (load_json(root, path), None)
            except Exception as exc:  # noqa: BLE001
                docs[path] = (None, f"{path}: {type(exc).__name__}: {exc}")
        return docs[path]

    for check in case.get("checks") or []:
        op, bound = bound_of(check)
        src = check.get("file") or source            # a check may pin a sibling recording of the same run family
        doc, doc_error = _doc(src)
        row = {"case": case["id"], "kind": case["kind"], "metric": check["metric"], "floor": describe_bound(op, bound),
               "recorded": check.get("recorded"), "source": src, "value": None, "result": "MISSING", "detail": ""}
        if doc_error:
            row["detail"] = doc_error
        else:
            try:
                value = read_metric(doc, check)
            except KeyError as exc:
                row["detail"] = str(exc)
            else:
                row["value"] = value
                if not passes(value, op, bound):
                    row["result"], row["detail"] = "FAIL", f"{value} violates {row['floor']}"
                elif "recorded" in check and value != check["recorded"]:
                    row["result"], row["detail"] = "DRIFT", f"file says {value}, manifest froze {check['recorded']} — re-freeze with --refresh"
                else:
                    row["result"] = "PASS"
        rows.append(row)
    for ref in case.get("offline_tests") or []:
        ok, why = offline_test_exists(ref, root)
        rows.append({"case": case["id"], "kind": case["kind"], "metric": ref, "floor": "test exists", "recorded": None,
                     "source": ref.partition("::")[0], "value": None, "result": "EXISTS" if ok else "ABSENT", "detail": why})
    if case["kind"] == "pending":
        pend = case.get("pending") or {}
        rows.append({"case": case["id"], "kind": case["kind"], "metric": pend.get("metric", "")[:90], "floor": "not recorded",
                     "recorded": None, "source": pend.get("instrument"), "value": None, "result": "PENDING",
                     "detail": f"owner {pend.get('owner')}"})
    return rows


def evaluate(manifest: dict, root: Path = ROOT) -> list[dict]:
    rows: list[dict] = []
    for case in manifest["cases"]:
        rows.extend(evaluate_case(case, root))
    return rows


def failures(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["result"] in ("FAIL", "MISSING", "DRIFT", "ABSENT")]


def validate_shape(manifest: dict, root: Path = ROOT) -> list[str]:
    """Structural errors in the manifest itself (not metric outcomes)."""
    errors: list[str] = []
    cases = manifest.get("cases") or []
    if len(cases) != CASE_COUNT:
        errors.append(f"expected {CASE_COUNT} cases, found {len(cases)}")
    ids = [c.get("id") for c in cases]
    if len(set(ids)) != len(ids):
        errors.append(f"duplicate case ids: {sorted(i for i in ids if ids.count(i) > 1)}")
    for case in cases:
        cid = case.get("id", "?")
        for field in CASE_FIELDS:
            if not case.get(field):
                errors.append(f"{cid}: missing {field}")
        if case.get("kind") not in KINDS:
            errors.append(f"{cid}: kind {case.get('kind')!r} not in {KINDS}")
        checks = case.get("checks") or []
        tests = case.get("offline_tests") or []
        if case.get("kind") == "recorded-floor" and not checks:
            errors.append(f"{cid}: recorded-floor without checks")
        if case.get("kind") == "offline-test" and not tests:
            errors.append(f"{cid}: offline-test without offline_tests")
        if case.get("kind") == "pending":
            pend = case.get("pending") or {}
            if not pend.get("owner") or not pend.get("metric") or not pend.get("instrument"):
                errors.append(f"{cid}: pending entry needs owner, metric and instrument")
        elif case.get("pending"):
            errors.append(f"{cid}: only pending entries carry a pending block")
        if checks:
            src = (case.get("source") or {}).get("file")
            if not src or not (Path(root) / src).exists():
                errors.append(f"{cid}: source file missing: {src}")
            if not (case.get("source") or {}).get("run"):
                errors.append(f"{cid}: source.run missing")
        for check in checks:
            if check.get("file") and not (Path(root) / check["file"]).exists():
                errors.append(f"{cid}: check {check.get('metric')!r} file missing: {check['file']}")
            try:
                bound_of(check)
            except ValueError as exc:
                errors.append(f"{cid}: {exc}")
            if not check.get("metric"):
                errors.append(f"{cid}: check without metric name")
            if "recorded" not in check:
                errors.append(f"{cid}: check {check.get('metric')!r} without a recorded value")
            for label in ("baseline", "known_bad"):
                ref = check.get(label)
                if ref and not {"file", "pointer", "value"} <= set(ref):
                    errors.append(f"{cid}: {label} of {check.get('metric')!r} needs file, pointer, value")
        for ref in tests:
            if "::" not in ref or not ref.startswith("tests/"):
                errors.append(f"{cid}: offline test reference must be tests/<file>.py::<function>: {ref}")
    return errors


def reference_mismatches(manifest: dict, root: Path = ROOT) -> list[str]:
    """Every baseline / known_bad reference must still read the value the manifest states."""
    errors: list[str] = []
    for case in manifest["cases"]:
        for check in case.get("checks") or []:
            for label in ("baseline", "known_bad"):
                ref = check.get(label)
                if not ref:
                    continue
                try:
                    actual = resolve_pointer(load_json(root, ref["file"]), ref["pointer"])
                    if ref.get("reduce"):
                        actual = _reduce(actual, ref["reduce"])
                except (KeyError, OSError, ValueError) as exc:
                    errors.append(f"{case['id']} {check['metric']} {label}: {exc}")
                    continue
                if actual != ref["value"]:
                    errors.append(f"{case['id']} {check['metric']} {label}: {ref['file']}{ref['pointer']} = {actual}, manifest says {ref['value']}")
    return errors


# ------------------------------------------------------------------ refresh
def refresh(manifest: dict, case_id: str, new_file: str, root: Path = ROOT, today: str | None = None) -> list[dict]:
    """Re-point one entry's source to a newer experiment JSON and re-freeze its recorded values.

    Refuses (raises ValueError, manifest untouched) when the new recording violates a floor or a pointer is
    absent — lowering a floor is a manual, reviewed edit, never a side effect of re-recording."""
    matches = [c for c in manifest["cases"] if c["id"] == case_id]
    if len(matches) != 1:
        raise ValueError(f"unknown case id {case_id!r}; known: {[c['id'] for c in manifest['cases']]}")
    case = matches[0]
    if not case.get("checks"):
        raise ValueError(f"{case_id} has no recorded checks to refresh (kind {case['kind']})")
    new_path = Path(new_file)
    relative = new_path.relative_to(root).as_posix() if new_path.is_absolute() else new_path.as_posix()
    doc = load_json(root, relative)
    new_values: list[tuple[dict, Any]] = []
    problems: list[str] = []
    for check in case["checks"]:
        if check.get("file"):
            continue            # pinned to its own recording; not re-pointed by --refresh
        op, bound = bound_of(check)
        try:
            value = read_metric(doc, check)
        except KeyError as exc:
            problems.append(f"{check['metric']}: {exc}")
            continue
        if not passes(value, op, bound):
            problems.append(f"{check['metric']} = {value} violates floor {describe_bound(op, bound)}")
        new_values.append((check, value))
    if problems:
        raise ValueError(f"{case_id}: {relative} cannot be frozen — " + "; ".join(problems))
    old = dict(case["source"])
    summary = doc.get("summary") if isinstance(doc, dict) else None
    run = (summary or {}).get("tag") or new_path.stem
    stamp = today or dt.date.today().isoformat()
    case["source"] = {**old, "file": relative, "run": run,
                      "refreshed": {"from": old.get("file"), "previous_run": old.get("run"), "on": stamp}}
    if old.get("instrument") and old.get("run"):
        # the procedure text stays; a verbatim old tag inside it is mechanically re-pointed
        case["source"]["instrument"] = old["instrument"].replace(old["run"], run)
    if "recorded_in" in old:
        case["source"]["recorded_in"] = f"refreshed {stamp} from {relative}; add the work-log that recorded run {run}"
    for check, value in new_values:
        check["recorded"] = value
    return evaluate_case(case, root)


def write_manifest(manifest: dict, path: Path = MANIFEST) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ tables
def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    return json.dumps(value) if not isinstance(value, str) else value


def check_table(rows: list[dict]) -> str:
    lines = ["| case | kind | metric | value | floor | result | source |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} | {r['kind']} | {r['metric']} | {_fmt(r['value'])} | {r['floor']} | {r['result']}"
                     f"{(' — ' + r['detail']) if r['result'] not in ('PASS', 'EXISTS') and r['detail'] else ''} | {_fmt(r['source'])} |")
    return "\n".join(lines)


def acceptance_table(manifest: dict, root: Path = ROOT) -> str:
    """The plan's completion-report skeleton: capability | baseline | final | gate | result, from the manifest."""
    lines = ["| capability | baseline | final | gate | result |", "|---|---|---|---|---|"]
    for case in manifest["cases"]:
        rows = {r["metric"]: r for r in evaluate_case(case, root)}
        label = f"{case['id']} {case['name']}"
        for check in case.get("checks") or []:
            row = rows[check["metric"]]
            base = check.get("baseline")
            baseline = f"{_fmt(base['value'])} ({base.get('run') or base['file'].rsplit('/', 1)[-1]})" if base else "—"
            run_label = check.get("run") or case["source"].get("run")
            final = f"{_fmt(row['value'])} ({run_label})" if row["value"] is not None else f"— ({row['detail']})"
            lines.append(f"| {label} — {check['metric']} | {baseline} | {final} | {row['floor']} | {row['result']} |")
        for ref in case.get("offline_tests") or []:
            row = rows[ref]
            lines.append(f"| {label} — {ref.rsplit('::', 1)[-1]} | — | {row['result'].lower()} | test exists in CI | {row['result']} |")
        if case["kind"] == "pending":
            pend = case["pending"]
            lines.append(f"| {label} | — | — | {pend['metric']} | PENDING ({pend['owner']}) |")
    return "\n".join(lines)


def counts(manifest: dict) -> dict:
    out = {k: 0 for k in KINDS}
    for case in manifest["cases"]:
        out[case["kind"]] += 1
    return out


# ------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="re-evaluate the manifest against the committed JSONs and tests; exit 1 on any failure")
    ap.add_argument("--refresh", default=None, metavar="CASE=JSON", help="re-point one case's source to a newer experiment JSON and re-freeze its recorded values")
    ap.add_argument("--table", action="store_true", help="print the acceptance table skeleton (capability | baseline | final | gate | result)")
    ap.add_argument("--manifest", default=str(MANIFEST), help="manifest path (default eval/regression/chat_regression_manifest.json)")
    ap.add_argument("--root", default=str(ROOT), help="repository root the manifest's paths are relative to")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    manifest_path = Path(a.manifest)
    manifest = load_manifest(manifest_path)
    shape = validate_shape(manifest, root) + reference_mismatches(manifest, root)
    if shape:
        print("MANIFEST INVALID", file=sys.stderr)
        for err in shape:
            print(f"  {err}", file=sys.stderr)
        return 1
    if a.refresh:
        case_id, _, new_file = a.refresh.partition("=")
        if not case_id or not new_file:
            ap.error("--refresh takes <case-id>=<json-path>")
        try:
            rows = refresh(manifest, case_id.strip(), new_file.strip(), root)
        except ValueError as exc:
            print(f"REFRESH REFUSED: {exc}", file=sys.stderr)
            return 1
        write_manifest(manifest, manifest_path)
        print(f"{case_id}: source re-pointed to {new_file}; recorded values re-frozen")
        print(check_table(rows))
        return 0
    if a.table:
        print(acceptance_table(manifest, root))
        return 0
    rows = evaluate(manifest, root)
    print(check_table(rows))
    bad = failures(rows)
    kinds = counts(manifest)
    print(f"\n{CONTRACT}: {len(manifest['cases'])} cases (recorded-floor {kinds['recorded-floor']} / offline-test {kinds['offline-test']} / "
          f"pending {kinds['pending']}), {len(rows)} rows, {sum(1 for r in rows if r['result'] == 'PENDING')} pending, {len(bad)} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
