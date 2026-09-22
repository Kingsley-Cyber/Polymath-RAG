#!/usr/bin/env python3
"""Semantic Transduction Restoration — the DETERMINISTIC VERIFICATION SHELL (docs/migration/DETERMINISTIC_VERIFICATION_SHELL.md).

One tool, three phases, no LLM anywhere, pure reads (git, files, read-only SELECTs); same inputs → byte-identical JSON.

  --phase trail-preflight   predicts whether a Trail evidence bundle is structurally acceptable BEFORE Trail's closing steps (§2.1)
  --phase integration       proves the merged + re-pinned checkout contains the system we think it does, BEFORE the bounce (§2.2)
  --phase benchmark         adjudicates a finished benchmark run from durable state: PASS / FAIL / NOT_EVALUABLE (§2.3); with
                            --preflight it checks the seed against the manifest's seed policy before any run exists

Every check is one of PASS · FAIL · NOT_EVALUABLE (an infrastructure cause, never "hard to judge") · SKIP_LAWFUL (a stage the run
lawfully never reached). The overall verdict is FAIL if any required check FAILS, else NOT_EVALUABLE if any is NOT_EVALUABLE, else
PASS. The agent reports what the JSON says — never a summary of its own. The gate is FROZEN from its recorded commit: never edited
after a benchmark run exists (§4)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

GATE_VERSION = "1.0.0"
PASS, FAIL, NE, SKIP = "PASS", "FAIL", "NOT_EVALUABLE", "SKIP_LAWFUL"
ROOT = Path(__file__).resolve().parents[1]


# ─────────────────────────────────────────────────────────── plumbing
class Report:
    def __init__(self, phase: str, target: dict[str, Any]) -> None:
        self.phase, self.target, self.checks = phase, target, []

    def add(self, cid: str, title: str, status: str, **facts: Any) -> None:
        self.checks.append({"id": cid, "title": title, "status": status, "facts": _jsonable(facts)})

    @property
    def overall(self) -> str:
        statuses = {c["status"] for c in self.checks}
        return FAIL if FAIL in statuses else NE if NE in statuses else PASS

    def payload(self) -> dict[str, Any]:
        return {"gate_version": GATE_VERSION, "gate_commit": _git(ROOT, "rev-parse", "HEAD") or None, "phase": self.phase, "target": self.target,
                "overall": self.overall, "checks": self.checks}


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in (sorted(v) if isinstance(v, set) else v)]
    if isinstance(v, Path):
        return str(v)
    return v


def _git(cwd: Path, *args: str) -> str | None:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 3600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as exc:
        return 127, str(exc)
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def _pytest_counts(out: str) -> dict[str, int]:
    """The counts from pytest's summary line (searched from the end: `-q` may print warnings after it)."""
    for line in reversed(out.strip().splitlines()):
        found = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|error|errors|xfailed|deselected)", line)}
        if found:
            return found
    return {}


def _venv_python() -> str:
    cand = ROOT / ".venv" / "bin" / "python"
    return str(cand) if cand.exists() else sys.executable


def _dbfree_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "POLYMATH_PG_DSN"}
    env["PYTHONPATH"] = str(ROOT)
    return env


def write_outputs(rep: Report, json_path: Path | None, md_path: Path | None, headline: str) -> None:
    payload = rep.payload()
    text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(text, encoding="utf-8")
    if md_path:
        lines = [f"# {headline}", "", f"gate_version `{GATE_VERSION}` · gate_commit `{payload['gate_commit']}` · phase `{rep.phase}` · **overall {rep.overall}**", "",
                 "| id | check | status | facts |", "|---|---|---|---|"]
        for c in rep.checks:
            facts = json.dumps(c["facts"], sort_keys=True, ensure_ascii=False)
            lines.append(f"| {c['id']} | {c['title']} | {c['status']} | `{facts[:300]}` |")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────── phase: integration (§2.2)
FOCUSED_SUITES = ["tests/determinism/test_adapter_semantic_view.py", "tests/determinism/test_adapter_research_fidelity.py", "tests/determinism/test_adapter_product_reality.py",
                  "tests/determinism/test_adapter_dossier_fidelity.py", "tests/determinism/test_chat_evidence_route.py", "tests/determinism/test_adapter_trail_wire.py",
                  "tests/determinism/test_adapter_ecommerce_product_research_e2e.py", "tests/determinism/test_adapter_ecommerce_product_research_embedded_trail.py",
                  "tests/contracts/test_adapter_contract_v1.py", "tests/contracts/test_harness_receipt_trail_parity.py", "tests/contracts/test_deploy_ecommerce_skill.py"]
CALL_SITE_SUITE = "tests/determinism/test_worker_call_sites_merged.py"
TRAIL_PARITY_SUITES = ["tests/contracts/test_trail_core_embedding.py", "tests/determinism/test_trail_core_recorded_equivalence.py"]
GUARDS = [("agent_preflight", ["scripts/agent_preflight.py"]), ("repo_guard", ["scripts/repo_guard.py"]), ("wiki_worm", ["scripts/wiki_worm.py", "--check"]),
          ("bundle_integrity", ["shared/polymath_shared/bundle_integrity.py"])]


def phase_integration(a: argparse.Namespace) -> Report:
    rep = Report("integration", {"repo": str(ROOT), "head": _git(ROOT, "rev-parse", "HEAD"), "restoration_tip": a.restoration_tip, "trail_commit": a.trail_commit,
                                 "manifest_version": a.manifest_version})
    # I1 ancestry
    if a.restoration_tip:
        ok = subprocess.run(["git", "merge-base", "--is-ancestor", a.restoration_tip, "HEAD"], cwd=ROOT).returncode == 0
        rep.add("I1", "production contains the restoration tip", PASS if ok else FAIL, tip=a.restoration_tip)
    else:
        rep.add("I1", "production contains the restoration tip", NE, reason="no --restoration-tip given")
    # I2 + I3 the pin
    prov_path = ROOT / "governance" / "trail" / "PROVENANCE.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    pinned = prov.get("source_commit_full") or prov.get("source_commit")
    if a.trail_commit:
        rep.add("I2", "Trail pin == the accepted HR6 commit", PASS if pinned and (pinned == a.trail_commit or a.trail_commit.startswith(pinned)) else FAIL, pinned=pinned, expected=a.trail_commit)
    else:
        rep.add("I2", "Trail pin == the accepted HR6 commit", NE, pinned=pinned, reason="no --trail-commit given")
    wrong = [p for p, h in prov["files"].items() if not (ROOT / "governance" / "trail" / p).is_file() or _sha(ROOT / "governance" / "trail" / p) != h]
    blob_mismatch: list[str] = []
    if a.trail_worktree and pinned:
        for p in prov["files"]:
            blob = subprocess.run(["git", "show", f"{pinned}:{p}"], cwd=a.trail_worktree, capture_output=True)
            if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != prov["files"][p]:
                blob_mismatch.append(p)
    rep.add("I3", "every embedded Trail file equals its pinned sha256 (and the commit's blob when the Trail worktree is given)",
            PASS if not wrong and not blob_mismatch else FAIL, files=len(prov["files"]), sha_mismatch=wrong, blob_mismatch=blob_mismatch, blob_checked=bool(a.trail_worktree))
    # I4 manifest
    m = json.loads((ROOT / "config" / "adapters" / "ecommerce.product_research.json").read_text(encoding="utf-8"))
    trail_steps = [s for s in m["steps"] if s.get("type") == "EXTERNAL_OPERATION"]
    opted = all((s.get("config") or {}).get("hypotheses_from") == "context.semantics.trail" for s in trail_steps)
    rep.add("I4", "manifest adapter_version == expected and every Trail step opts in to the extended wire",
            PASS if (not a.manifest_version or m["adapter_version"] == a.manifest_version) and opted else FAIL, adapter_version=m["adapter_version"], trail_steps=len(trail_steps), opted_in=opted)
    # I5 four-copy receipt contract
    c1, c2 = ROOT / "contracts/adapter/v1/harness_receipt.schema.json", ROOT / "adapters/ecommerce/schemas/harness_receipt.schema.json"
    adm = json.loads((ROOT / "contracts/adapter/v1/evidence_admission.schema.json").read_text(encoding="utf-8"))
    obs = json.loads(c1.read_text(encoding="utf-8"))["properties"]["observations"]["items"]["properties"]
    same = c1.read_bytes() == c2.read_bytes()
    rel = "hypothesis_relations" in obs and "hypothesis_relations" in adm["properties"]["admitted"]["items"]["properties"]
    rep.add("I5", "receipt contract: contract and engine copy byte-equal; hypothesis_relations in the receipt and the admission contract", PASS if same and rel else FAIL, byte_equal=same, relation_field=rel)
    # I6 clean tree
    dirty = _git(ROOT, "status", "--porcelain") or ""
    rep.add("I6", "working tree clean", PASS if not dirty else FAIL, dirty=dirty.splitlines()[:20])
    # I7 no stale generated contract copies
    stale = [p.name for p in (ROOT / "adapters/ecommerce/schemas").glob("*.json") if (ROOT / "contracts/adapter/v1" / p.name).exists() and p.read_bytes() != (ROOT / "contracts/adapter/v1" / p.name).read_bytes()]
    rep.add("I7", "no stale generated contract copy under adapters/ecommerce/schemas", PASS if not stale else FAIL, stale=stale)
    if a.no_suites:
        for cid, title in (("I8", "call sites"), ("I9", "focused adapter suites"), ("I10", "engine suite"), ("I11", "repository guards"), ("I12", "embedded Trail parity")):
            rep.add(cid, title, NE, reason="--no-suites")
    else:
        py, env = _venv_python(), _dbfree_env()
        # I8 the three call sites, on THIS checkout, never skipped
        code, out = _run([py, "-m", "pytest", "-o", "addopts=", "-q", CALL_SITE_SUITE], ROOT, env)
        n = _pytest_counts(out)
        rep.add("I8", "the three previously untestable call sites pass on this checkout (never skipped)", PASS if code == 0 and n.get("passed", 0) >= 4 and not n.get("skipped") else FAIL, **n, exit=code)
        # I9 focused suites
        present = [s for s in FOCUSED_SUITES if (ROOT / s).exists()]
        code, out = _run([py, "-m", "pytest", "-o", "addopts=", "-q", *present], ROOT, env)
        n = _pytest_counts(out)
        rep.add("I9", "focused adapter suites pass (DB-free)", PASS if code == 0 and n.get("passed", 0) > 0 else FAIL, suites=present, **n, exit=code)
        # I10 the engine suite under the Hermes venv, temp loop db
        hermes = Path.home() / ".hermes/hermes-agent/venv/bin/python"
        if hermes.exists():
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                eenv = {**env, "OPPORTUNITY_RESEARCH_DB": str(Path(td) / "loop.sqlite")}
                code, out = _run([str(hermes), "tests/run_all.py"], ROOT / "adapters" / "ecommerce", eenv)
            mm = re.search(r"(\d+)\s*/\s*(\d+)", out.strip().splitlines()[-1] if out.strip() else "")
            rep.add("I10", "engine suite passes (adapters/ecommerce, Hermes venv, temp loop db)", PASS if code == 0 else FAIL, exit=code, tail=out.strip().splitlines()[-1:] if out.strip() else [], ratio=mm.group(0) if mm else None)
        else:
            rep.add("I10", "engine suite passes", NE, reason="Hermes venv not found")
        # I11 guards
        results = {}
        for name, cmd in GUARDS:
            code, out = _run([py, *cmd], ROOT, env)
            results[name] = {"exit": code, "tail": out.strip().splitlines()[-1:] if out.strip() else []}
        ready = "READY" in " ".join(results["bundle_integrity"]["tail"])
        rep.add("I11", "repository guards 0 / 0 / 0 / READY", PASS if all(r["exit"] == 0 for r in results.values()) and ready else FAIL, **results)
        # I12 embedded Trail parity
        present = [s for s in TRAIL_PARITY_SUITES if (ROOT / s).exists()]
        code, out = _run([py, "-m", "pytest", "-o", "addopts=", "-q", *present], ROOT, env)
        n = _pytest_counts(out)
        rep.add("I12", "embedded Trail parity (sha pins + recorded envelopes replay)", PASS if code == 0 and n.get("passed", 0) > 0 and not n.get("skipped") else FAIL, suites=present, **n, exit=code)
    # I13 runtime quiescence
    dsn = os.environ.get("POLYMATH_PG_DSN")
    if not dsn:
        rep.add("I13", "0 open adapter runs, 0 leased tickets", NE, reason="POLYMATH_PG_DSN not set")
    else:
        try:
            import psycopg  # type: ignore
            with psycopg.connect(dsn) as conn, conn.cursor() as cur:
                cur.execute("select count(*) from adapter_runs where status not in ('completed','failed','terminated','cancelled','refused','terminal_gap')")
                open_runs = cur.fetchone()[0]
                if _table_exists(cur, "stage_tickets"):
                    cur.execute("select count(*) from stage_tickets where status='leased'")
                    leased = cur.fetchone()[0]
                else:
                    leased = 0
            rep.add("I13", "0 open adapter runs, 0 leased tickets", PASS if open_runs == 0 and leased == 0 else FAIL, open_runs=open_runs, leased_tickets=leased)
        except Exception as exc:  # noqa: BLE001 — the database not answering is an infrastructure cause
            rep.add("I13", "0 open adapter runs, 0 leased tickets", NE, reason=f"{type(exc).__name__}: {exc}"[:300])
    return rep


def _table_exists(cur: Any, name: str) -> bool:
    cur.execute("select to_regclass(%s) is not null", (name,))
    return bool(cur.fetchone()[0])


# ─────────────────────────────────────────────────────────── phase: trail-preflight (§2.1)
ALLOWED_EXACT = {"git diff --check"}
PY_SCRIPTS = {"scripts/architecture/validate_v2_governance.py"}


def _command_allowed(cmd: str) -> bool:
    if cmd in ALLOWED_EXACT:
        return True
    parts = cmd.split()
    if not parts or Path(parts[0]).name not in {"python", "python3"}:
        return False
    if len(parts) > 2 and parts[1] == "-m" and parts[2] == "pytest":
        return all(not t.startswith("/") and ".." not in t for t in parts[3:])
    if len(parts) > 1 and parts[1] in PY_SCRIPTS:
        args = parts[2:]
        return args == ["--root", ".", "--check"] or (len(args) == 4 and args[:3] == ["--root", ".", "--measure-run"] and re.fullmatch(r"build_runs/[A-Za-z0-9_.-]+/slice\.yaml", args[3]) is not None)
    return False


def phase_trail_preflight(a: argparse.Namespace) -> Report:
    import yaml  # type: ignore

    wt = Path(a.trail_worktree).resolve()
    run_dir = wt / "build_runs" / a.run_id
    rep = Report("trail-preflight", {"trail_worktree": str(wt), "run_id": a.run_id, "head": _git(wt, "rev-parse", "HEAD")})
    if not run_dir.is_dir():
        rep.add("P0", "run directory exists", FAIL, run_dir=str(run_dir))
        return rep
    sl = yaml.safe_load((run_dir / "slice.yaml").read_text(encoding="utf-8"))
    slice_id, status = sl["slice_id"], sl["status"]
    # P1 ADR accepted + index parity
    adr_ids = [x for x in sl.get("adrs", []) if x == a.adr] if a.adr else []
    adr_ok, index_ok = None, None
    if a.adr:
        num = a.adr.split("-")[-1]
        adr_files = sorted((wt / "docs/adr").glob(f"{num}_*.md"))
        text = adr_files[0].read_text(encoding="utf-8") if adr_files else ""
        adr_ok = bool(re.search(r"^\*{0,2}Status\*{0,2}:?\*{0,2}\s*Accepted", text, flags=re.M | re.I)) or "Status: Accepted" in text or "| Accepted |" in text
        idx = (wt / "docs/adr/README.md")
        index_ok = (num in idx.read_text(encoding="utf-8") and "Accepted" in "".join(l for l in idx.read_text(encoding="utf-8").splitlines() if f"{num}" in l)) if idx.exists() else None
    rep.add("P1", "ADR accepted (status + index row parity) and named by the slice", PASS if (a.adr is None or (adr_ok and adr_ids and index_ok is not False)) else FAIL, adr=a.adr, status_accepted=adr_ok, slice_names_it=bool(adr_ids), index=index_ok)
    # P2 task ↔ slice binding
    task_path = wt / ".agent-control/tasks" / slice_id / "task.json"
    task = json.loads(task_path.read_text(encoding="utf-8")) if task_path.exists() else {}
    gb = task.get("governance_binding") or {}
    rep.add("P2", "task.json ↔ slice.yaml binding", PASS if gb.get("run_id") == a.run_id and gb.get("slice_id") == slice_id and gb.get("slice_path") == f"build_runs/{a.run_id}/slice.yaml" else FAIL, binding=gb)
    # P3 owned paths cover every file in the run dir; every owned run file exists non-empty
    owned = list(sl["change_budget"]["owned_paths"])
    in_dir = sorted(str(p.relative_to(wt)) for p in run_dir.rglob("*") if p.is_file())
    unowned = [p for p in in_dir if p not in owned]
    missing = [p for p in owned if p.startswith(f"build_runs/{a.run_id}/") and (not (wt / p).is_file() or (wt / p).stat().st_size == 0)]
    rep.add("P3", "owned_paths cover the run directory; every owned evidence file exists and is non-empty", PASS if not unowned and not missing else FAIL, unowned=unowned, missing_or_empty=missing)
    # P4 + P5 verification commands
    ver = json.loads((run_dir / "verification.json").read_text(encoding="utf-8"))
    cmds = ver.get("commands") or []
    not_allowed = [c["command"] for c in cmds if not _command_allowed(c["command"])]
    bad_hash = [c["detail_path"] for c in cmds if not (wt / c["detail_path"]).is_file() or (wt / c["detail_path"]).stat().st_size == 0 or "sha256:" + _sha(wt / c["detail_path"]) != c["output_sha256"] or c["exit_code"] != 0 or c["result"] != "PASS"]
    rep.add("P4", "verification commands are repository commands only", PASS if not not_allowed else FAIL, commands=[c["command"] for c in cmds], not_allowed=not_allowed)
    rep.add("P5", "every command record: PASS / 0, log exists, non-empty, hash matches", PASS if not bad_hash and cmds else FAIL, bad=bad_hash)
    # P6 measurement stable
    py = str(wt / ".venv/bin/python") if (wt / ".venv/bin/python").exists() else sys.executable
    code, out = _run([py, "scripts/architecture/validate_v2_governance.py", "--root", ".", "--measure-run", f"build_runs/{a.run_id}/slice.yaml"], wt)
    p = subprocess.run([py, "scripts/architecture/validate_v2_governance.py", "--root", ".", "--measure-run", f"build_runs/{a.run_id}/slice.yaml"], cwd=wt, capture_output=True)
    digest = "sha256:" + hashlib.sha256(p.stdout).hexdigest()
    ca = sl.get("change_actual") or {}
    try:
        metrics = json.loads(p.stdout)["metrics"]
    except Exception:  # noqa: BLE001
        metrics = {}
    within = {k: (ca.get(k), sl["change_budget"].get(k)) for k in ("contexts", "adapters", "hand_edited_files", "non_test_added_lines", "production_runtime_lines", "migrations")}
    ceilings_ok = all(v is None or (c is not None and c <= v) for c, v in within.values())
    rep.add("P6", "measurement inputs stable (recomputed hash == recorded) and within the ceilings", PASS if p.returncode == 0 and digest == ca.get("measurement_output_sha256") and ceilings_ok else FAIL,
            recorded=ca.get("measurement_output_sha256"), recomputed=digest, metrics=metrics, ceilings=within)
    # P7 journal ordering
    events = [json.loads(l) for l in (run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    order_ok = bool(events) and events[0]["event"] == "STATUS" and all(e.get("next_admissible_action") for e in events)
    final_ok = bool(events) and (status != "VERIFIED" or (events[-1]["event"] in {"GATE_RESULT", "STATUS"} and events[-1]["status"] == "VERIFIED" and events[-1].get("exit_code") in (None, 0)))
    rep.add("P7", "journal: STATUS first, every event names its next admissible action, VERIFIED ends with a passing GATE_RESULT", PASS if order_ok and final_ok else FAIL, events=[(e["event"], e["status"]) for e in events])
    # P8 graph node
    graph = yaml.safe_load((wt / "build_graph_v2.yaml").read_text(encoding="utf-8"))
    nodes = graph["nodes"] if isinstance(graph, dict) else graph
    node = next((n for n in nodes if n.get("id") == slice_id), None) if isinstance(nodes, list) else nodes.get(slice_id)
    expected_ranks = {k: int(v) for k, v in (x.split("=") for x in (a.expect_rank or []))}
    ranks = {n.get("id"): n.get("execution_rank") for n in nodes if n.get("id") in expected_ranks} if isinstance(nodes, list) else {}
    node_ok = bool(node) and node.get("status") == status and (node.get("run_id") in (None, a.run_id)) and all(ranks.get(k) == v for k, v in expected_ranks.items())
    rep.add("P8", "graph node exists with the slice's status, this run id and the expected ranks", PASS if node_ok else FAIL, node_status=(node or {}).get("status"), node_run_id=(node or {}).get("run_id"), ranks=ranks, expected=expected_ranks)
    # P9 no pre-written PASS: the governance log equals a captured REAL run
    gov_log = run_dir / "governance.log"
    p = subprocess.run([py, "scripts/architecture/validate_v2_governance.py", "--root", ".", "--check"], cwd=wt, capture_output=True)
    real = p.stdout + p.stderr
    diagnostics = re.search(rb"v2 governance: (PASS|FAIL) \((\d+) diagnostic", real)
    equal = gov_log.is_file() and gov_log.read_bytes() == real
    rep.add("P9", "governance.log equals a captured real `--check` run (never a pre-written PASS); Trail's own validator verdict", PASS if equal and p.returncode == 0 else FAIL,
            validator_exit=p.returncode, validator=diagnostics.group(0).decode() if diagnostics else real[-200:].decode(errors="replace"), log_equals_real_output=equal)
    # P10 nothing outside owned_paths changed against the measurement base (agent-control lifecycle excluded, as the validator does)
    base = ca.get("measurement_base_ref")
    changed = (_git(wt, "diff", "--name-only", base) or "").splitlines() if base else []
    untracked = (_git(wt, "ls-files", "--others", "--exclude-standard") or "").splitlines()
    outside = [p for p in changed + untracked if p not in owned and not p.startswith(".agent-control/")]
    rep.add("P10", "no changed or untracked path outside owned_paths", PASS if base and not outside else (NE if not base else FAIL), base=base, outside=outside[:30])
    return rep


# ─────────────────────────────────────────────────────────── phase: benchmark (§2.3) — built at G7b, frozen before G8
def phase_benchmark(a: argparse.Namespace) -> Report:
    raise SystemExit("benchmark phase: built at G7b (docs/migration/DETERMINISTIC_VERIFICATION_SHELL.md §2.3); not available in this gate version")


# ─────────────────────────────────────────────────────────── main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", required=True, choices=["trail-preflight", "integration", "benchmark"])
    ap.add_argument("--json", type=Path, help="write the machine-readable verdict here")
    ap.add_argument("--md", type=Path, help="write the human summary here")
    # integration
    ap.add_argument("--restoration-tip", help="commit that must be an ancestor of HEAD")
    ap.add_argument("--trail-commit", help="the accepted Trail commit the pin must equal")
    ap.add_argument("--trail-worktree", help="Trail checkout (blob verification; trail-preflight target)")
    ap.add_argument("--manifest-version", help="expected adapter_version of ecommerce.product_research")
    ap.add_argument("--no-suites", action="store_true", help="skip the test / guard executions (they become NOT_EVALUABLE)")
    # trail-preflight
    ap.add_argument("--run-id", help="Trail build_runs/<run id>")
    ap.add_argument("--adr", help="ADR id the slice must name as Accepted, e.g. ADR-069")
    ap.add_argument("--expect-rank", nargs="*", help="graph rank expectations, e.g. A46=149 HR6=151")
    # benchmark
    ap.add_argument("--manifest", type=Path, help="benchmark manifest yaml")
    ap.add_argument("--preflight", action="store_true", help="check the seed against the manifest before any run exists")
    ap.add_argument("--seed", help="the seed text (preflight)")
    a = ap.parse_args(argv)
    if a.phase == "integration":
        rep = phase_integration(a)
        headline = f"INTEGRATION_GATE: {rep.overall} · safe_to_bounce: {'true' if rep.overall == PASS else 'false'}"
    elif a.phase == "trail-preflight":
        if not (a.trail_worktree and a.run_id):
            ap.error("--trail-worktree and --run-id are required")
        rep = phase_trail_preflight(a)
        fails = [c["id"] for c in rep.checks if c["status"] == FAIL]
        headline = f"TRAIL_PREFLIGHT: {rep.overall} · diagnostics: {len(fails)}"
    else:
        rep = phase_benchmark(a)
        headline = f"BENCHMARK_GATE: {rep.overall}"
    write_outputs(rep, a.json, a.md, headline)
    for c in rep.checks:
        print(f"  {c['id']:<4} {c['status']:<14} {c['title']}")
    print(headline)
    return 0 if rep.overall == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
