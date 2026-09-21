"""Consolidation migration Phase 9 — ONE source, a deterministic copy, a version receipt, parity verification. Proven against a TEMP target:
nothing here touches a real agent host."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "deploy_ecommerce_skill.py"


def _run(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT)
    return proc.returncode, proc.stdout


def _objects(text: str) -> list[dict]:
    out, dec, i = [], json.JSONDecoder(), 0
    while i < len(text):
        if text[i] == "{":
            obj, j = dec.raw_decode(text, i)
            out.append(obj); i = j
        else:
            i += 1
    return out


def test_dry_run_writes_nothing_and_a_deploy_is_verified_receipted_and_idempotent(tmp_path):
    target = tmp_path / "host" / "opportunity-research"
    code, out = _run("--target", str(target))
    assert code == 0 and not target.exists() and _objects(out)[0]["mode"] == "dry-run" and _objects(out)[0]["to_write"] == _objects(out)[0]["total"] > 100

    code, out = _run("--target", str(target), "--execute", "--no-hermes-link", "--allow-dirty")
    planned, verified = _objects(out)
    assert code == 0 and verified["parity"] is True and verified["missing_in_deployed"] == [] and verified["drift"] == []
    receipt = json.loads((target / "MIRROR_RECEIPT.json").read_text())
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert receipt["reference"]["commit"] == head and receipt["reference"]["containing_repo_subdir"] == "adapters/ecommerce"      # the receipt names THIS repository's commit
    assert receipt["reference"]["version"] == receipt["deployed"]["version"] and receipt["reference"]["files"] == planned["total"]
    assert (target / "python" / "controller.py").is_file() and (target / "binding.py").is_file()

    # never deployed: runtime state, caches, databases, the private ledger, repo-only files
    deployed = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    assert not [f for f in deployed if f.startswith(("state/", "candidates/", "exports/", "registry/compiled/", "registry/patches/")) or f.endswith((".sqlite3", ".pyc")) or f == "registry/research_evidence.csv"]
    assert ".gitignore" not in deployed

    code, out = _run("--target", str(target), "--execute", "--no-hermes-link", "--allow-dirty")
    assert code == 0 and _objects(out)[0]["to_write"] == 0                                                                         # idempotent


def test_check_mode_fails_on_drift_and_names_the_file(tmp_path):
    target = tmp_path / "opportunity-research"
    assert _run("--target", str(target), "--execute", "--no-hermes-link", "--allow-dirty")[0] == 0
    (target / "python" / "bridge.py").write_text("# edited on the host\n")
    code, out = _run("--target", str(target), "--check", "--no-hermes-link")
    assert code == 1 and _objects(out)[0]["parity"] is False and _objects(out)[0]["drift"] == ["python/bridge.py"]
    (target / "hand_made.txt").write_text("x")
    assert _run("--target", str(target), "--execute", "--no-hermes-link", "--allow-dirty")[0] == 0 and (target / "hand_made.txt").exists()   # repaired; nothing deleted


def test_the_source_is_refused_as_a_target():
    code, out = _run("--target", str(ROOT / "adapters" / "ecommerce" / "x"))
    assert code == 2 and "must not be the source" in out
