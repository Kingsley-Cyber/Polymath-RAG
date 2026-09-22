"""Consolidation migration Phase 6 — the embedded TrailSignal core is BYTE-IDENTICAL to its source commit, and the only Polymath-authored
file beside it is the composition module. Pure file checks: no third-party import, so this pin runs in every environment.

A change to TrailSignal's behaviour is made upstream or as a separate, documented change that re-pins PROVENANCE.json — never as a quiet edit
(docs/migration/ADR-TRAIL-EMBEDDING.md; MIGRATION_POLICY INV-5: embedding changes the deployment boundary only)."""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRAIL = ROOT / "governance" / "trail"
PROV = json.loads((TRAIL / "PROVENANCE.json").read_text())
AUTHORED = {"embedded.py", "PROVENANCE.json"}


def _files() -> set[str]:
    return {p.relative_to(TRAIL).as_posix() for p in TRAIL.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def test_every_imported_file_matches_its_pinned_sha256():
    assert PROV["source_commit"] == "829a0ab" and len(PROV["files"]) == 30      # ADR-069 re-pin: HR6 on codex/r1-semantic-restoration
    wrong = [rel for rel, sha in PROV["files"].items() if hashlib.sha256((TRAIL / rel).read_bytes()).hexdigest() != sha]
    assert not wrong, f"embedded TrailSignal files differ from the source commit: {wrong}"


def test_nothing_is_added_beside_the_pinned_files_and_the_composition_module():
    assert _files() == set(PROV["files"]) | AUTHORED


def test_the_closure_is_the_sixteen_modules_and_the_registry_data_it_reads():
    modules = sorted(f for f in PROV["files"] if f.endswith(".py"))
    assert len(modules) == 16 and "src/trail_signal/contexts/workflow/application/research_operations.py" in modules
    assert {f for f in PROV["files"] if f.startswith("config/")} == {"config/evidence_gates.json", "config/scoring_weights.json", "config/weights.yaml"}
    assert len([f for f in PROV["files"] if f.startswith("data/")]) == 10 and "LICENSE" in PROV["files"]


def test_the_composition_module_imports_nothing_of_the_polymath_runtime():
    """TrailSignal never reads or writes Polymath state: the boundary is the JSON-RPC request, not an import."""
    tree = ast.parse((TRAIL / "embedded.py").read_text())
    tops = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
           {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not tops & {"polymath_shared", "workers", "orchestrator", "control", "sidecars"}, tops
