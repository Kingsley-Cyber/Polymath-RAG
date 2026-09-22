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


# ─────────────────────────────────────────────────────────── phase: benchmark (§2.3) — adjudicates a FINISHED run from durable state
TERMINAL_RUN_STATUSES = {"completed", "failed", "terminated", "cancelled", "refused", "terminal_gap"}
#: the gate's ONE declared mapping from the runtime's terminal fields to the manifest's outcome vocabulary (§8, open point 3)
GAP_CODE_OUTCOMES = {"LINEAGE_LAW_UNSATISFIED": "NO_DEFENSIBLE_BRIDGE", "BRIDGE_LAW_UNSATISFIED": "NO_DEFENSIBLE_BRIDGE", "NO_DEFENSIBLE_BRIDGE": "NO_DEFENSIBLE_BRIDGE",
                     "MARKET_ALREADY_SOLVED": "MARKET_ALREADY_SOLVED", "SUPPLY_UNPROVEN": "SUPPLY_UNPROVEN", "HARD_GATE_UNMET": "HARD_GATE_UNMET", "LAWFUL_REFUSAL": "LAWFUL_REFUSAL"}
SOFTWARE_FAILURE_CODES = {"STEP_EXECUTOR_ERROR", "SCHEMA_ERROR", "LINEAGE_SOFTWARE_FAILURE", "UNHANDLED_EXCEPTION", "TRAIL_REFUSED", "EVIDENCE_CONTRACT_MISMATCH", "SUBMISSION_REJECTED"}
INFRA_MARKERS = ("provider", "timeout", "timed out", "connection", "transport", "unreachable", "503", "502", "429", "rate limit", "econn", "dns")
PLACEHOLDER = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


def load_run_from_db(run_id: str) -> dict[str, Any]:
    """Read-only SELECTs of exactly what the gate needs; contexts are reduced to ids (the evidence rows themselves are never needed)."""
    import psycopg  # type: ignore

    dsn = os.environ.get("POLYMATH_PG_DSN")
    if not dsn:
        raise RuntimeError("POLYMATH_PG_DSN not set")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select run_id, adapter_id, adapter_version, status, input, outputs, output_order, gap, failure, request_options from adapter_runs where run_id=%s", (run_id,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"run {run_id} not found")
        run = {"run_id": row[0], "adapter_id": row[1], "adapter_version": row[2], "status": row[3], "input": row[4], "outputs": row[5] or {}, "output_order": row[6] or [],
               "gap": row[7], "failure": row[8], "request_options": row[9]}
        cur.execute("select sequence, step_id, step_type, status, step->'harness_action', step->'context'->'hypotheses', step->'context'->'evidence_refs', submission, output, receipt->'failure' "
                    "from adapter_steps where run_id=%s order by sequence", (run_id,))
        run["steps"] = [{"sequence": r[0], "step_id": r[1], "step_type": r[2], "status": r[3], "harness_action": r[4],
                         "context_hypothesis_ids": [h.get("hypothesis_id") for h in (r[5] or []) if isinstance(h, dict)],
                         "context_evidence_ref_ids": [x.get("id") for x in (r[6] or []) if isinstance(x, dict)],
                         "submission": (r[7] or {}).get("payload") if isinstance(r[7], dict) else None, "output": r[8], "receipt_failure": r[9]} for r in cur.fetchall()]
        cur.execute("select hypothesis_id, revision, status, state from adapter_hypotheses where run_id=%s order by seq", (run_id,))
        run["hypotheses"] = [{"hypothesis_id": r[0], "revision": r[1], "status": r[2], "state": r[3]} for r in cur.fetchall()]
        cur.execute("select evidence_id, action_id, observation_id, evidence_role, polarity, independence_group, hypothesis_ids, record from adapter_admitted_evidence where run_id=%s order by admitted_at, evidence_id", (run_id,))
        run["admitted"] = [{"evidence_id": r[0], "action_id": r[1], "observation_id": r[2], "evidence_role": r[3], "polarity": r[4], "independence_group": r[5], "hypothesis_ids": r[6] or [], "record": r[7]} for r in cur.fetchall()]
    return run


def load_run_file(path: Path) -> dict[str, Any]:
    import gzip
    raw = gzip.open(path, "rb").read() if str(path).endswith(".gz") else path.read_bytes()
    return json.loads(raw.decode("utf-8"))


def _newest_output(run: dict[str, Any], key: str) -> Any:
    """The newest output carrying `key` (bounded-loop passes: the last pass wins), by the run's own output order."""
    outs = run["outputs"]
    for sid in reversed(list(run.get("output_order") or list(outs))):
        o = outs.get(sid)
        if isinstance(o, dict) and key in o:
            return o[key]
    return None


def _ids(v: Any, key: str = "id") -> set[str]:
    return {str(x[key]) for x in v if isinstance(x, dict) and x.get(key)} if isinstance(v, list) else set()


def _strings(v: Any) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [t for x in v.values() for t in _strings(x)]
    if isinstance(v, list):
        return [t for x in v for t in _strings(x)]
    return []


def _norm(t: Any) -> str:
    return " ".join(str(t or "").lower().split())


def phase_benchmark(a: argparse.Namespace) -> Report:
    import yaml  # type: ignore

    manifest = yaml.safe_load(Path(a.manifest).read_text(encoding="utf-8")) if a.manifest else {}
    mid = manifest.get("benchmark_id")
    if a.preflight:
        rep = Report("benchmark-preflight", {"manifest_id": mid, "gate_version_expected": manifest.get("gate_version")})
        seed = a.seed if a.seed is not None else (Path(a.seed_file).read_text(encoding="utf-8") if a.seed_file else None)
        rep.add("B0", "manifest names this gate version and a seed policy", PASS if manifest.get("gate_version") == GATE_VERSION and isinstance(manifest.get("seed_policy"), dict) else FAIL, manifest_gate_version=manifest.get("gate_version"))
        if seed is None:
            rep.add("B1", "the seed is the manifest's pinned seed", NE, reason="no --seed / --seed-file")
        else:
            digest = hashlib.sha256(_norm(seed).encode("utf-8")).hexdigest()
            rep.add("B1", "the seed is the manifest's pinned seed (normalised sha256)", PASS if digest == manifest.get("seed", {}).get("sha256_normalised") else FAIL, seed_sha256=digest, expected=manifest.get("seed", {}).get("sha256_normalised"))
            found = sorted(t for t in (manifest.get("seed_policy", {}).get("forbidden_terms") or []) if re.search(r"\b" + re.escape(t.lower()) + r"\b", _norm(seed)))
            rep.add("B2", "the seed names no market / population / product category / desired product / consumer problem / niche term", PASS if not found else FAIL, forbidden_terms_found=found)
        rep.add("B3", "required stages and allowed terminal states declared", PASS if manifest.get("required_stages") and manifest.get("allowed_terminal_states") else FAIL,
                required_stages=manifest.get("required_stages"), allowed_terminal_states=manifest.get("allowed_terminal_states"))
        return rep

    run = load_run_file(Path(a.run_file)) if a.run_file else load_run_from_db(a.run_id)
    if a.export:
        Path(a.export).parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(run, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        if str(a.export).endswith(".gz"):
            import gzip
            Path(a.export).write_bytes(gzip.compress(data, mtime=0))
        else:
            Path(a.export).write_bytes(data)
    rep = Report("benchmark", {"run_id": run["run_id"], "adapter_id": run.get("adapter_id"), "adapter_version": run.get("adapter_version"), "status": run.get("status"), "manifest_id": mid,
                               "seed_sha256": hashlib.sha256(_norm((run.get("input") or {}).get("seed")).encode("utf-8")).hexdigest()})
    outs = run["outputs"]
    hyps = {h["hypothesis_id"]: h for h in run["hypotheses"]}
    latest: dict[str, dict[str, Any]] = {}
    for h in run["hypotheses"]:
        if h["hypothesis_id"] not in latest or h["revision"] >= latest[h["hypothesis_id"]]["revision"]:
            latest[h["hypothesis_id"]] = h
    retrieved = {i for st in run["steps"] for i in st["context_evidence_ref_ids"] if i}
    admitted_ids = {x["evidence_id"] for x in run["admitted"]} | {x["observation_id"] for x in run["admitted"] if x.get("observation_id")}
    if run.get("status") not in TERMINAL_RUN_STATUSES:
        rep.add("T0", "the run is terminal", NE, run_status=run.get("status"), reason="a benchmark is adjudicated only when finished")
        return rep

    # T1 abstraction
    prim = (outs.get("C_primitives") or {}).get("primitives") if isinstance(outs.get("C_primitives"), dict) else None
    inv = list((prim or {}).get("transferable_invariants") or [])
    structures = _newest_output(run, "latent_structures") or []
    cited = {str(i) for v in ((prim or {}).get("evidence_refs") or {}).values() for i in (v if isinstance(v, list) else [])} if isinstance((prim or {}).get("evidence_refs"), dict) else set()
    unresolved = sorted(i for i in cited if i not in retrieved)
    rep.add("T1", "abstraction: C_primitives with ≥ 1 transferable invariant and ≥ 1 latent structure; every cited evidence ref was retrieved",
            PASS if prim and inv and structures and not unresolved else FAIL, transferable_invariants=len(inv), latent_structures=len(structures) if isinstance(structures, list) else 0, cited=len(cited), unresolved_refs=unresolved[:10])
    # T2 nomination
    pop = outs.get("C_population") if isinstance(outs.get("C_population"), dict) else {}
    leads = [l for l in (pop.get("population_leads") or []) + (pop.get("community_leads") or []) if isinstance(l, dict)]
    lanes = sorted({str(l.get("source_lane") or l.get("search_mode")) for l in leads})       # the engine's lanes: CORPUS / REGISTRY (named) / LATENT
    voi = all(isinstance(l.get("voi"), (int, float)) for l in leads)
    seedflag = all("seed_population" in l for l in leads)
    rep.add("T2", "nomination: C_population with CORPUS / NAMED and LATENT candidates, a VOI per lead, a ranking, the seed_population flag recorded (a LATENT lead need not win)",
            PASS if leads and "LATENT" in lanes and any(k in lanes for k in ("CORPUS", "REGISTRY", "NAMED")) and voi and pop.get("ranked_lead_ids") and seedflag else FAIL,
            leads=len(leads), lanes=lanes, voi_on_every_lead=voi, ranked=bool(pop.get("ranked_lead_ids")), seed_population_recorded=seedflag)
    # T3 origin
    known_leads, known_structures = _ids(leads), _ids(structures)
    origin_linked, bad_origin = [], []
    for hid, h in latest.items():
        st = h.get("state") or {}
        li, si = [str(x) for x in st.get("lead_ids") or []], [str(x) for x in st.get("latent_structure_ids") or []]
        if li or si:
            origin_linked.append(hid)
            bad_origin += [x for x in li if x not in known_leads] + [x for x in si if x not in known_structures]
    seed_pops = {hid: [l.get("seed_population") for l in leads if str(l.get("id")) in (latest[hid].get("state") or {}).get("lead_ids", [])] for hid in origin_linked}
    rep.add("T3", "origin: ≥ 1 hypothesis names its lead / latent-structure origin; every origin id resolves", PASS if origin_linked and not bad_origin else FAIL,
            origin_linked_hypotheses=len(origin_linked), hypotheses=len(latest), unresolved_origins=bad_origin[:10], origin_seed_population=seed_pops, hypothesis_population={hid: (latest[hid].get("state") or {}).get("population") for hid in origin_linked})
    # T4 bridge
    bridges = [b for b in ((outs.get("C_bridge") or {}).get("bridges") or []) if isinstance(b, dict)] if isinstance(outs.get("C_bridge"), dict) else []
    problems = []
    for b in bridges:
        path = [str(x) for x in b.get("path") or []]
        fia = (b.get("evidence_boundary") or {}).get("first_inference_at") if isinstance(b.get("evidence_boundary"), dict) else None
        if len(path) < 3:
            problems.append(f"{b.get('hypothesis_id')}: path {len(path)} < 3")
        if not fia or fia not in path:
            problems.append(f"{b.get('hypothesis_id')}: first_inference_at is not one of the hops")
        if not b.get("evidence_boundary"):
            problems.append(f"{b.get('hypothesis_id')}: no evidence_boundary")
        if b.get("grounding") in ("CORPUS_ONLY", "SPECULATIVE") and not b.get("gaps"):
            problems.append(f"{b.get('hypothesis_id')}: speculative transfer without gaps")
        if not b.get("falsifiers"):
            problems.append(f"{b.get('hypothesis_id')}: no falsifiers")
    rep.add("T4", "bridge: every inference-transfer hypothesis has a path ≥ 3 hops, first_inference_at on the path, an evidence boundary, gaps for a speculative transfer, falsifiers",
            PASS if bridges and not problems else (FAIL if problems or latest else SKIP), bridges=len(bridges), problems=problems[:10])
    # T5 Trail normalization
    priors = [p for sid in ("D_project", "E_filter") for p in ((outs.get(sid) or {}).get("priors") or []) if isinstance(p, dict)]
    terr = [t for t in ((outs.get("O_territory") or {}).get("territories") or []) if isinstance(t, dict)] if isinstance(outs.get("O_territory"), dict) else []
    prior_bad = [p.get("registry_record_id") for p in priors if not p.get("registry_record_id") or not p.get("label") or p.get("mapping_path") not in ("structured", "lexical")]
    terr_bad = [t.get("territory_id") for t in terr if not t.get("territory_id") or not t.get("territory_name") or t.get("mapping_path") not in ("structured", "lexical")]
    distinct_terr = len({t.get("territory_id") for t in terr})
    rep.add("T5", "Trail normalization: every prior / territory id resolves with a meaningful label / name and a recorded mapping_path (structured or lexical)",
            PASS if priors and not prior_bad and (not terr or not terr_bad) else FAIL, priors=len(priors), priors_without_meaning=len(prior_bad), territories=len(terr), territories_without_meaning=len(terr_bad),
            distinct_territories=distinct_terr, mapping_paths=sorted({str(p.get("mapping_path")) for p in priors} | {str(t.get("mapping_path")) for t in terr}))
    # T6 research fidelity
    try:
        sys.path.insert(0, str(ROOT / "adapters" / "ecommerce" / "python"))
        from query_semantics import GOVERNANCE_TERMS  # type: ignore
    except Exception:  # noqa: BLE001
        GOVERNANCE_TERMS = frozenset({"independent", "independence", "corroborate", "corroboration", "observations", "admitted", "admission", "evidence"})
    intents, issues = [], []
    for st in run["steps"]:
        ha = st.get("harness_action") or {}
        for it in ha.get("search_intents") or []:
            if not isinstance(it, dict):
                continue
            intents.append(it)
            iid = str(it.get("intent_id") or "")
            if not iid:
                issues.append(f"{st['step_id']}: intent without id")
            if any(PLACEHOLDER.search(t) for t in _strings(it)):
                issues.append(f"{iid}: unbound placeholder")
            hid = it.get("hypothesis_id")
            if ha.get("action_kind") == "AGENT_RESEARCH" and hid and hid not in hyps:
                issues.append(f"{iid}: hypothesis {hid} unknown")
            if ha.get("action_kind") == "AGENT_RESEARCH" and not hid and not it.get("concept_id"):
                issues.append(f"{iid}: no hypothesis")
            q = _norm(it.get("query"))
            if q and set(q.replace("?", "").split()) <= set(GOVERNANCE_TERMS):
                issues.append(f"{iid}: governance-only query")
    intent_ids = {str(i.get("intent_id")) for i in intents}
    gap_ids = {str(g.get("gap_id")) for st in run["steps"] for g in ((st.get("harness_action") or {}).get("evidence_gaps") or []) if isinstance(g, dict)}
    tagged, chain_bad = 0, []
    for x in run["admitted"]:
        ctx = str((x.get("record") or {}).get("context") or "")
        m = re.search(r"\bintent:\s*([A-Za-z0-9][A-Za-z0-9._:/-]*)", ctx)
        if m:
            tagged += 1
            if m.group(1) not in intent_ids:
                chain_bad.append(m.group(1))
    rep.add("T6", "research fidelity: every issued intent has an id, a resolving hypothesis, no unbound placeholder, no governance-only query; tagged observations resolve to an issued intent",
            PASS if intents and not issues and not chain_bad and tagged else FAIL, intents=len(intents), issues=issues[:10], observations_tagged=tagged, admitted=len(run["admitted"]), unresolved_tags=chain_bad[:10], gaps_issued=len(gap_ids))
    # T7 evidence and revision
    link_bad = [x["evidence_id"] for x in run["admitted"] if any(h not in hyps for h in x["hypothesis_ids"])]
    rel_bad = []
    contradict: set[str] = set()
    for x in run["admitted"]:
        for r in (x.get("record") or {}).get("hypothesis_relations") or []:
            if not isinstance(r, dict) or r.get("hypothesis_id") not in x["hypothesis_ids"] or r.get("relation") not in ("SUPPORTS", "CONTRADICTS", "NEUTRAL"):
                rel_bad.append(x["evidence_id"])
            elif r.get("relation") == "CONTRADICTS":
                contradict.add(str(r["hypothesis_id"]))
        if x.get("polarity") == "contradicting":
            contradict |= {str(h) for h in x["hypothesis_ids"]}
    transitions = [t for st in run["steps"] for t in ((st.get("submission") or {}).get("transitions") or []) if isinstance(t, dict)]
    cause_bad = [t.get("hypothesis_id") for t in transitions for c in t.get("cause_refs") or [] if isinstance(c, dict) and str(c.get("id")) not in admitted_ids | retrieved]
    verdict_kinds = {v.get("kind") for sid in ("L_judge", "R_qualify", "U_qualify") for v in ((outs.get(sid) or {}).get("hypothesis_verdicts") or []) if isinstance(v, dict)}
    represented = [hid for hid in contradict if (latest.get(hid, {}).get("state") or {}).get("contradictions") or latest.get(hid, {}).get("status") in ("weakened", "killed", "split")]
    rep.add("T7", "evidence and revision: admitted links resolve; stated relations are valid; a transition's cause_refs resolve; admitted contradictions are represented in state",
            PASS if not link_bad and not rel_bad and not cause_bad and len(represented) == len(contradict) else FAIL,
            admitted=len(run["admitted"]), unresolved_links=link_bad[:10], invalid_relations=rel_bad[:10], transitions=len(transitions), kinds=sorted({str(t.get("kind")) for t in transitions}),
            unresolved_cause_refs=cause_bad[:10], contradicted_hypotheses=sorted(contradict), represented=sorted(represented), verdict_kinds=sorted(str(k) for k in verdict_kinds))
    # T8 concepts
    nc = outs.get("N_concepts") if isinstance(outs.get("N_concepts"), dict) else {}
    concepts = [c for c in (nc.get("product_concepts") or []) if isinstance(c, dict)]
    mechs = {str(m.get("id")): m for m in (nc.get("mechanisms") or []) if isinstance(m, dict)}
    seed = _norm((run.get("input") or {}).get("seed"))
    c_bad = [c.get("id") for c in concepts if str(c.get("mechanism_id")) not in mechs or str(mechs.get(str(c.get("mechanism_id")), {}).get("hypothesis_id")) not in hyps
             or not all(c.get(k) for k in ("id", "name", "buyer", "form_factor", "target_moment")) or _norm(c.get("name")) == seed or _norm(c.get("problem")) == seed]
    min_concepts = int(manifest.get("min_concepts", 1))
    rep.add("T8", "concepts: N_concepts with ≥ the manifest minimum; each concept's mechanism and hypothesis resolve; typed fields present; concept text is not the seed",
            PASS if len(concepts) >= min_concepts and not c_bad else FAIL, concepts=len(concepts), minimum=min_concepts, invalid=c_bad[:10])
    # T9 product reality
    plan = outs.get("O_plan") if isinstance(outs.get("O_plan"), dict) else {}
    jobs = [j for j in (plan.get("reality_plan") or []) if isinstance(j, dict)]
    join = outs.get("Q_join") if isinstance(outs.get("Q_join"), dict) else {}
    concept_ids = {str(c.get("id")) for c in concepts}
    job_ids = {str(j.get("job_id")) for j in jobs}
    uncovered = sorted(concept_ids - {str(j.get("concept_id")) for j in jobs})
    joined_bad = [p.get("observation_id") for p in (join.get("existing_products") or []) if isinstance(p, dict) and (str(p.get("concept_id")) not in concept_ids or (p.get("job_id") and str(p.get("job_id")) not in job_ids))]
    reality = [r for r in (join.get("concept_reality") or []) if isinstance(r, dict)]
    statuses = sorted({str(r.get("status")) for r in reality})
    rep.add("T9", "product reality: O_plan.reality_plan with ≥ 1 job per concept; every joined existing product resolves to a concept and a job; ≥ 1 concept has a reality disposition",
            PASS if jobs and not uncovered and not joined_bad and reality and any(s in ("EXISTING_PRODUCT_CONTESTS", "EXISTING_PRODUCTS_FOUND", "NO_EXISTING_PRODUCT_JOINED", "NOT_RESEARCHED") for s in statuses) else FAIL,
            jobs=len(jobs), concepts_without_job=uncovered[:10], joined=(join.get("joined") or {}).get("joined") if isinstance(join.get("joined"), dict) else None, invalid_joins=joined_bad[:10], dispositions=statuses)
    # T10 supply
    supply_present = {sid: sid in outs for sid in ("S_plan", "S_supply", "T_admit", "T_leads")}
    contested_all = bool(reality) and all(r.get("status") == "EXISTING_PRODUCT_CONTESTS" for r in reality)
    lawful_gap = isinstance(run.get("gap"), dict) and run["gap"].get("code") in GAP_CODE_OUTCOMES
    if not supply_present["S_plan"] and (contested_all or not concepts or lawful_gap):
        rep.add("T10", "supply: S_plan → S_supply → T_admit → T_leads executed", SKIP, reason="no concept reached supply lawfully", contested_all=contested_all, concepts=len(concepts), gap=(run.get("gap") or {}).get("code") if isinstance(run.get("gap"), dict) else None)
    else:
        rep.add("T10", "supply: S_plan → S_supply → T_admit → T_leads executed", PASS if all(supply_present.values()) else FAIL, **supply_present)
    # T11 terminal outcome
    failure = run.get("failure") if isinstance(run.get("failure"), dict) else None
    gap = run.get("gap") if isinstance(run.get("gap"), dict) else None
    scores = (outs.get("V_score") or {}).get("trail_scores") if isinstance(outs.get("V_score"), dict) else None
    refusals = [r.get("reason_code") for r in ((outs.get("V_score") or {}).get("score_refusals") or []) if isinstance(r, dict)] if isinstance(outs.get("V_score"), dict) else []
    text = _norm(json.dumps([failure, gap], default=str))
    if failure or (gap and gap.get("code") in SOFTWARE_FAILURE_CODES):
        outcome, status = (str((failure or gap or {}).get("code") or "UNHANDLED_EXCEPTION")), (NE if any(m in text for m in INFRA_MARKERS) else FAIL)
    elif run["status"] == "completed" and scores:
        outcome, status = "SCORED", PASS
    elif run["status"] == "completed" and refusals:
        outcome, status = ("HARD_GATE_UNMET" if "HARD_GATE_UNMET" in refusals else str(refusals[0])), PASS
    elif gap and gap.get("code") in GAP_CODE_OUTCOMES:
        outcome, status = GAP_CODE_OUTCOMES[gap["code"]], PASS
    else:
        outcome, status = f"{run['status']}:{(gap or {}).get('code')}", FAIL
    allowed = set(manifest.get("allowed_terminal_states") or [])
    if status == PASS and allowed and outcome not in allowed:
        status = FAIL
    rep.add("T11", "terminal outcome: a lawful terminal state (SCORED / HARD_GATE_UNMET / NO_DEFENSIBLE_BRIDGE / MARKET_ALREADY_SOLVED / SUPPLY_UNPROVEN / LAWFUL_REFUSAL); a software failure is FAIL; an infrastructure cause is NOT_EVALUABLE",
            status, outcome=outcome, run_status=run["status"], gap_code=(gap or {}).get("code"), failure_code=(failure or {}).get("code"), score_refusals=sorted({str(r) for r in refusals}), scored=bool(scores), allowed=sorted(allowed))
    required = set(manifest.get("required_stages") or [])
    missing_required = sorted(t for t in required if not any(c["id"] == t for c in rep.checks))
    if missing_required:
        rep.add("TX", "every required stage was evaluated", FAIL, missing=missing_required)
    return rep


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
    ap.add_argument("--seed-file", help="file holding the seed text (preflight)")
    ap.add_argument("--run-file", help="a run exported by --export (json or json.gz) instead of the database")
    ap.add_argument("--export", help="also write the loaded run (reduced durable state) to this json / json.gz path (fixtures)")
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
        if not a.preflight and not (a.run_id or a.run_file):
            ap.error("--run-id or --run-file is required (or --preflight)")
        rep = phase_benchmark(a)
        headline = f"BENCHMARK_{'PREFLIGHT' if a.preflight else 'GATE'}: {rep.overall}"
    write_outputs(rep, a.json, a.md, headline)
    for c in rep.checks:
        print(f"  {c['id']:<4} {c['status']:<14} {c['title']}")
    print(headline)
    return 0 if rep.overall == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
