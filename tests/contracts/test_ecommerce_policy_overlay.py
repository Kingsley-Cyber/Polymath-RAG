"""TRAIL-EXT-BUGHUNT-V1 B-58 — the ecommerce engine's policy overlay EXTENDS `graph/policies.yaml`, never replaces a law in it.

`graph.load_policies` used `dict.update` with `graph/loadout_policies.yaml`: its `portfolio` block (the loadout set-selection
weights) replaced policies.yaml's hypothesis `portfolio` law, so min/max_hypotheses, max_exploratory, distinct_target_mechanisms and
min_lived_anchored were never read — the laws ran on their hard-coded fallbacks. The loader's own law is "fail closed, never
last-wins".

Out of process, against the engine's own `graph` / `bridge` modules (their flat names never enter this interpreter): the checkout
itself, and scratch copies whose YAML the test edits. No database, no network.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "adapters" / "ecommerce"


def _run(engine: pathlib.Path, code: str) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, 'python'); import graph; " + code],
                          cwd=engine, env=env, capture_output=True, text=True, check=False, timeout=120)


def _scratch(tmp_path: pathlib.Path, *, policies_edit=None, overlay_append: str = "") -> pathlib.Path:
    """A copy of the engine's `graph` + `bridge` modules and its two policy files, edited."""
    (tmp_path / "python").mkdir()
    (tmp_path / "graph").mkdir()
    for name in ("graph.py", "bridge.py"):
        shutil.copy(ENGINE / "python" / name, tmp_path / "python" / name)
    text = (ENGINE / "graph" / "policies.yaml").read_text(encoding="utf-8")
    (tmp_path / "graph" / "policies.yaml").write_text(policies_edit(text) if policies_edit else text, encoding="utf-8")
    (tmp_path / "graph" / "loadout_policies.yaml").write_text((ENGINE / "graph" / "loadout_policies.yaml").read_text(encoding="utf-8") + overlay_append, encoding="utf-8")
    return tmp_path


def test_the_hypothesis_portfolio_law_survives_the_loadout_overlay():
    proc = _run(ENGINE, "p = graph.load_policies(); print(json.dumps({'merged': p['portfolio'], 'law': graph.load_yaml_file('graph/policies.yaml')['portfolio'], "
                        "'loadout': graph.load_yaml_file('graph/loadout_policies.yaml')['portfolio']}))")
    assert proc.returncode == 0, proc.stderr[-800:]
    out = json.loads(proc.stdout)
    assert {"min_hypotheses", "max_hypotheses", "max_exploratory", "distinct_target_mechanisms", "min_lived_anchored"} <= set(out["law"])
    assert {k: out["merged"].get(k) for k in out["law"]} == out["law"]                          # every hypothesis-portfolio law, as policies.yaml says
    assert {k: out["merged"].get(k) for k in out["loadout"]} == out["loadout"]                  # and the loadout selection keys executors.portfolio_gate reads


def test_the_bridge_portfolio_law_reads_the_values_policies_yaml_declares(tmp_path):
    def stricter(text: str) -> str:
        assert "  min_hypotheses: 3" in text and "  max_exploratory: 1" in text
        return text.replace("  min_hypotheses: 3", "  min_hypotheses: 5").replace("  max_exploratory: 1", "  max_exploratory: 0")
    engine = _scratch(tmp_path, policies_edit=stricter)
    hyps = [{"id": f"h{i}", "target_mechanism": f"mechanism family {i}", "status": "WORKING_HYPOTHESIS"} for i in range(2)]
    hyps.append({"id": "h2", "target_mechanism": "a deliberate transfer", "status": "WORKING_ANALOGY", "exploratory": True})
    proc = _run(engine, f"import bridge; print(json.dumps(bridge.validate_portfolio({hyps!r}, graph.load_policies())))")
    assert proc.returncode == 0, proc.stderr[-800:]
    errors = json.loads(proc.stdout)
    assert any("3 hypotheses — need 5-6" in e for e in errors) and any("1 exploratory transfers (max 0)" in e for e in errors), errors


def test_a_policy_key_both_files_declare_fails_closed(tmp_path):
    for clash, name in (("\nbridge:\n  require_hop_refs: false\n", "bridge.require_hop_refs"), ("\nportfolio_note: x\nevidence_channels: [reddit]\n", "evidence_channels"),
                        ("\nlived_world:\n  anchor_threshold:\n    min_records: 1\n", "lived_world.anchor_threshold.min_records")):
        case = tmp_path / name.replace(".", "_")
        case.mkdir()
        proc = _run(_scratch(case, overlay_append=clash), "graph.load_policies()")
        assert proc.returncode != 0 and "YAMLError" in proc.stderr and f"{name} is already declared in policies.yaml" in proc.stderr, (name, proc.stderr[-600:])
