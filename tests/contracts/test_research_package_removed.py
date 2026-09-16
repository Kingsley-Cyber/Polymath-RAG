"""HARNESS-RESEARCH-MIGRATION-V1 R5/O6 — dead-path guard: the `research/` package (TRAIL OS), its `research_*` MCP tools and
helpers, and the `research-harness` workflow are retired from this repo. The Hermes opportunity-research skill is preserved as
a standalone user-level skill OUTSIDE this repository (it calls Polymath's public surface); nothing executable here revives the
old path. History (work-logs, register, CONTINUITY, the E0 matrix, the plans) keeps the names on purpose; active code does not."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

RESEARCH_TOOLS = ("research_init", "research_step", "research_submit", "research_status", "research_corpus", "research_report")
RESEARCH_HELPERS = ("_RESEARCH_ROOT", "_RESEARCH_STATE", "_research_env", "_research_cli", "_research_state_path")

# Active runtime/config/contract surfaces only — never history or docs.
SCAN = [ROOT / "shared/polymath_shared", ROOT / "workers/workers", ROOT / "control/control",
        ROOT / "orchestrator/orchestrator", ROOT / "config", ROOT / "contracts", ROOT / "scripts"]


def _code_files():
    for base in SCAN:
        if base.is_file():
            yield base
        else:
            for p in base.rglob("*"):
                if p.is_file() and p.suffix in (".py", ".json", ".yaml", ".yml") and "__pycache__" not in p.parts:
                    yield p


def test_research_package_directory_is_gone():
    assert not (ROOT / "research").exists(), "research/ package is back in the repo"


def test_research_harness_workflow_is_gone():
    assert not (ROOT / ".github" / "workflows" / "research-harness.yml").exists(), "research-harness workflow is back"


def test_no_research_tools_or_helpers_in_active_code():
    offenders = []
    for path in _code_files():
        if path.name == "test_research_package_removed.py":
            continue
        text = path.read_text(errors="ignore")
        for sym in RESEARCH_TOOLS + RESEARCH_HELPERS:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(sym)}(?![A-Za-z0-9_])", text):
                offenders.append(f"{path.relative_to(ROOT)}: {sym}")
    assert not offenders, "retired research machinery is back in active code: " + "; ".join(offenders[:20])


def test_scaffold_declares_no_research_package():
    tree = (ROOT / "scripts" / "scaffold_polymath_v4.py").read_text()
    assert '"research/' not in tree, "scaffold TREE still declares research/ files"
    assert "research-harness.yml" not in tree, "scaffold TREE still declares the research-harness workflow"
