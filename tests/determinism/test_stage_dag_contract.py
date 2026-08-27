"""STAGE-DAG artifact-key contract pins.

MEASURED LIVE (Stage-K pilot, 2026-08-25): STAGE_DAG declared
verify_projections artifact key 'docs' while the verify worker writes
{qdrant, routing_qdrant, neo4j, canonical}. Every ticket-advancement
check failed on the phantom key, so runs whose chains were minted after
the verifier's reconciliation rewrite could never promote.

These tests parse the WORKER SOURCES for the literal writer.artifact()
keys and require every STAGE_DAG declaration to be a subset of what its
worker actually writes — drift fails CI, not production.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "shared"))

from control.tickets import STAGE_DAG

WORKERS = ROOT / "workers" / "workers"


def _literal_dict_keys(fn_src: str, call_name: str) -> set[str] | None:
    """Keys of a direct dict literal passed to <call_name>(...), if the
    call site uses one. Returns None when the argument is dynamic."""
    tree = ast.parse(fn_src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == call_name):
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Dict):
                return {k.value for k in arg.keys
                        if isinstance(k, ast.Constant)}
    return None


def _worker_source(stage: str) -> str | None:
    candidates = {
        "verify_projections": "verify_worker.py",
        "project_qdrant": "project_qdrant_worker.py",
        "extract": "extract_worker.py",
    }
    name = candidates.get(stage)
    if not name:
        return None
    return (WORKERS / name).read_text()


def test_verify_dag_keys_match_worker_artifact():
    declared = next(art for stage, _e, art, _r in STAGE_DAG
                    if stage == "verify_projections")
    src = _worker_source("verify_projections")
    actual = _literal_dict_keys(src, "artifact")
    assert actual is not None, (
        "verify worker no longer uses a literal artifact dict; update "
        "this contract test to the new shape")
    assert set(declared) <= actual, (
        f"STAGE_DAG declares {set(declared)} but verify worker writes "
        f"{actual} — advancement checks fail on phantom keys")


def test_no_phantom_keys_in_parseable_stage_declarations():
    for stage, _evt, art, _rec in STAGE_DAG:
        src = _worker_source(stage)
        if src is None:
            continue
        actual = _literal_dict_keys(src, "artifact")
        if actual is None:
            continue          # dynamic payload; can't check statically
        assert set(art) <= actual, (
            f"{stage}: DAG declares {sorted(set(art) - actual)} which "
            "the worker never writes")
