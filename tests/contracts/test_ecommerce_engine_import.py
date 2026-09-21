"""CONSOLIDATION MIGRATION Phase 2 — the ecommerce engine (TRAIL_AGENT_AUTORESEARCH @ a7baa66) lives at `adapters/ecommerce/`.

Pins, in the order the migration policy cares about them:
  * INV-7 (privacy by default): no private runtime artifact, ledger, DB, env file or machine-local path is a repository file;
  * the import is additive and complete enough to run: the engine's OWN suite and `doctor` pass in this location, under this
    repo's interpreter, against a throwaway loop DB (never the real Hermes loop SQLite);
  * the O6 retirement stays true: nothing here revives the `research/` package or its `research_*` MCP tools — the engine is
    bound through the adapter runtime (Phase 3), not through a second MCP surface.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "adapters" / "ecommerce"

#: never repository files (MIGRATION_POLICY INV-7 + the engine's own .gitignore)
FORBIDDEN_NAMES = {".env", "MIRROR_RECEIPT.json"}
FORBIDDEN_SUFFIXES = (".sqlite3", ".sqlite3-shm", ".sqlite3-wal", ".patch", ".pyc")
FORBIDDEN_PREFIXES = ("state/", "exports/", "registry/compiled/", "registry/patches/", ".github/")
FORBIDDEN_FILES = {"registry/research_evidence.csv"}       # the private field-evidence ledger (Reddit authors + quotes)
#: a real home directory. One-character names (`/Users/x/…`) are the engine suite's synthetic title fixtures, not a machine.
HOME_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]{2,}/")


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "--", "adapters/ecommerce"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line[len("adapters/ecommerce/"):] for line in out.stdout.splitlines() if line]


def test_engine_is_present_with_its_own_layout():
    for rel in ("python/controller.py", "python/lived_world.py", "python/executors.py", "python/adapter_receipt.py",
                "graph/control_graph.yaml", "graph/policies.yaml", "tests/run_all.py", "SKILL.md"):
        assert (ENGINE / rel).is_file(), f"adapters/ecommerce/{rel} is missing — the import preserves the source layout"


def test_no_private_or_machine_local_artifact_is_tracked():
    offenders = []
    for rel in _tracked():
        name = rel.rsplit("/", 1)[-1]
        if (name in FORBIDDEN_NAMES or rel in FORBIDDEN_FILES or rel.endswith(FORBIDDEN_SUFFIXES) or rel.startswith(FORBIDDEN_PREFIXES)
                or (rel.startswith("candidates/") and name != ".gitkeep")):
            offenders.append(rel)
    assert not offenders, f"private / runtime artifacts are tracked under adapters/ecommerce: {offenders}"


def test_no_machine_local_path_in_tracked_text():
    offenders = []
    for rel in _tracked():
        text = (ENGINE / rel).read_text(encoding="utf-8", errors="ignore")
        if HOME_PATH.search(text):
            offenders.append(rel)
    assert not offenders, f"machine-local paths in tracked files: {offenders}"


def test_trailsignal_evidence_ledger_is_header_only():
    ledger = ENGINE / "registry" / "trailsignal" / "research_evidence.csv"
    lines = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, "registry/trailsignal/research_evidence.csv carries rows — field evidence is never a repository file"


def test_engine_suite_and_doctor_pass_in_this_location(tmp_path):
    env = dict(os.environ, OPPORTUNITY_RESEARCH_DB=str(tmp_path / "loop.sqlite3"), PYTHONDONTWRITEBYTECODE="1",
               POLYMATH_V4_PYTHON=sys.executable)
    suite = subprocess.run([sys.executable, "tests/run_all.py"], cwd=ENGINE, env=env, capture_output=True, text=True)
    tail = suite.stdout.strip().splitlines()[-1] if suite.stdout.strip() else suite.stderr[-400:]
    assert suite.returncode == 0 and tail.startswith("ALL ") and tail.endswith(" CHECKS PASSED"), tail
    # the cross-repo pins compare against THIS repo (not a sibling checkout), so none of them may fall back to a skip
    assert "not on this machine" not in suite.stdout and "venv not present" not in suite.stdout, "a cross-repo pin skipped"
    doctor = subprocess.run([sys.executable, "python/controller.py", "doctor"], cwd=ENGINE, env=env, capture_output=True, text=True)
    assert doctor.returncode == 0, doctor.stdout[-400:] + doctor.stderr[-400:]

