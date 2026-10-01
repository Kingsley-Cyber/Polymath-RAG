"""CODE-WIKI-V1: the code wiki's checker runs only safe assertions (never a shell) and catches drift; the static spine reads
what the pages are built on (routes, flag defaults, broad handlers) without a model."""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "codewiki"))

import spine as S
import verify as V

HERE = "tests/contracts/test_codewiki_verify.py"
OTHER = "scripts/codewiki/verify.py"     # a file that never contains the absent token below
ABSENT = "NO_SUCH_" + "TOKEN_ANYWHERE_42"


@pytest.mark.parametrize("line", [
    f"grep -Fq 'def test_' {HERE}",
    f"grep -Eq '^import (ast|pathlib)$' {HERE}",
    f"! grep -Fq '{ABSENT}' {OTHER}",
    f'test "$(grep -c -F \'def test_\' {HERE})" -ge 3',
    "grep -Rq 'CODE-WIKI-V1' scripts/codewiki",
])
def test_the_allowed_shapes_run_and_pass(line):
    assert V.run_line(line) == (True, "")


@pytest.mark.parametrize("line", [
    "rm -rf docs",
    "grep -Fq x /etc/passwd",
    "grep -Fq x ../outside",
    "grep -Fq a b; rm -rf x",
    "grep -Fq a scripts/codewiki",                                     # a directory needs -R
    f"grep -Fq --include=*.py a {HERE}",                              # an option outside the allowed flags
    f'test "$(cat {HERE})" -ge 1',
    f"grep -Fq 'x' {HERE} && touch pwned",
    "echo hi",
])
def test_anything_else_is_refused_and_counts_as_a_failure(line):
    ok, why = V.run_line(line)
    assert not ok and why.startswith("refused")
    assert not (ROOT / "pwned").exists()


def test_a_false_claim_fails_with_a_reason():
    assert V.run_line(f"grep -Fq '{ABSENT}' {OTHER}") == (False, "pattern not found")
    assert V.run_line(f"! grep -Fq 'def test_' {HERE}") == (False, "pattern present")
    ok, why = V.run_line(f'test "$(grep -c -F \'def test_\' {HERE})" -ge 999')
    assert not ok and why.startswith("count")


def test_anchors_to_missing_files_fail_and_past_the_end_only_warn(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "WIKI", tmp_path)
    page = tmp_path / "p.md"
    page.write_text(f"# unit: x\nsee `{HERE}:1-3` and `shared/polymath_shared/no_such_file.py:10` and `{HERE}:999999`\n"
                    f"```verify\ngrep -Fq 'def test_' {HERE}\n```\n")
    rep = V.check_page(page)
    assert rep["missing_anchors"] == ["shared/polymath_shared/no_such_file.py:10"]
    assert rep["drifted_anchors"] == [f"{HERE}:999999"]
    assert rep["assertions"] == 1 and not rep["failed"] and rep["ok"] is False    # a missing file fails the page
    assert V.check_page(page, strict_anchors=True)["ok"] is False


def test_the_spine_reads_routes_flag_defaults_and_swallowed_handlers():
    src = '''
import os
from fastapi import APIRouter
router = APIRouter()
FLAG = "POLYMATH_EXAMPLE_FLAG"
KINDS = ("alpha", "beta", "gamma")

@router.get("/things/{thing_id}")
def get_thing(thing_id: str):
    try:
        return os.environ.get(FLAG, "7")
    except Exception:
        pass
    try:
        return os.getenv("POLYMATH_OTHER", "x")
    except Exception as exc:
        raise RuntimeError("boom") from exc
'''
    facts = S.analyse_py("orchestrator/orchestrator/api/example.py", src)
    assert facts["routes"] == [{"method": "GET", "path": "/things/{thing_id}", "handler": "get_thing", "line": 9}]   # the def line
    assert {(e["name"], e["default"]) for e in facts["env"]} == {("POLYMATH_EXAMPLE_FLAG", "'7'"), ("POLYMATH_OTHER", "'x'")}
    does = [f["does"] for f in facts["fallbacks"]]
    assert does[0].startswith("SWALLOWED") and does[1].startswith("handled")
    assert {"name": "KINDS", "line": 6, "value": ["alpha", "beta", "gamma"]} in facts["constants"]


def test_the_code_wiki_itself_is_in_step_with_the_code():
    """The committed wiki passes its own checker (the CI gate)."""
    if not (ROOT / "docs" / "codewiki" / "index.md").exists():
        pytest.skip("the code wiki is not generated in this checkout")
    reports = [V.check_page(p) for p in sorted((ROOT / "docs" / "codewiki").rglob("*.md"))]
    bad = [(r["page"], r["failed"][:2], r["missing_anchors"][:2]) for r in reports if not r["ok"]]
    assert not bad, bad[:5]
    assert ast.parse((ROOT / "scripts" / "codewiki" / "pages.py").read_text())
