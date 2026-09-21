"""ADR-0020 / consolidation migration Phase 3 — DOMAIN_OPERATION: a manifest step runs a domain's own code through the EXISTING
adapter runtime (same `service.advance`, same `EXECUTORS` table, same typed gaps and failures). No second scheduler, state machine
or ledger; the runtime never names a domain.

No database, no network: `service.store` is replaced by the in-memory double and `conn` is None. The domain code that runs IS the
imported engine (`adapters/ecommerce/binding.py` -> `python/bridge.py`), out of process, exactly as the worker runs it.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "adapter_domain_binding"
ADAPTER_ID = "fixture.domain_binding"

_BASE = {"source": "s", "path": ["a", "b", "c"], "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["?"],
         "status": "WORKING_HYPOTHESIS", "alternatives": ["alt explanation"], "falsifiers": ["killer observation"],
         "grounding": "CORPUS_ONLY", "hop_refs": {"0": ["chunk_1"]}}       # hop_refs is keyed by hop INDEX
#: one mechanism three times: the portfolio law ("variants of one mechanism are ONE hypothesis") must reject it
INADMISSIBLE = [dict(_BASE, id=f"p{i}", target_mechanism="magnet") for i in (1, 2, 3)]
ADMISSIBLE = [dict(_BASE, id=f"p{i}", target_mechanism=mech) for i, mech in enumerate(("magnet", "clamp", "strap"), 1)]


def test_the_code_under_test_is_this_checkout():
    """The editable install resolves `workers` / `polymath_shared` to the MAIN checkout unless sys.path is patched before the first
    import. If another test imported them first, this proof is void — fail loudly instead of passing against the wrong tree."""
    for mod in (C, M, service, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"
    assert W._DOMAINS_DIR == ROOT / "adapters"


def test_domain_operation_is_an_automatic_step_type_with_an_executor():
    assert "DOMAIN_OPERATION" in C.STEP_TYPES and "DOMAIN_OPERATION" in C.AUTOMATIC_STEP_TYPES
    assert "DOMAIN_OPERATION" not in C.AGENT_ANSWERED_STEP_TYPES
    assert W.EXECUTORS["DOMAIN_OPERATION"] is W.exec_domain


def _manifest_with(tmp_path, mutate) -> pathlib.Path:
    raw = json.loads((FIXTURES / f"{ADAPTER_ID}.json").read_text())
    mutate({s["step_id"]: s for s in raw["steps"]})
    path = tmp_path / f"{ADAPTER_ID}.json"
    path.write_text(json.dumps(raw))
    return path


@pytest.mark.parametrize("mutate, needle", [
    (lambda s: s["check"]["config"].pop("domain"), "needs config.domain"),
    (lambda s: s["check"]["config"].update(domain="../ecommerce"), "needs config.domain"),
    (lambda s: s["check"]["config"].update(domain="Ecommerce"), "needs config.domain"),
    (lambda s: s["check"]["config"].pop("operation"), "needs config.operation"),
    (lambda s: s["check"]["config"].update(operation="hypotheses/validate"), "needs config.operation"),
    (lambda s: s["check"]["config"].update(inputs={"hypotheses": 7}), "config.inputs maps a name to a dotted path"),
    (lambda s: s["check"]["config"].update(inputs={"hypotheses": []}), "config.inputs maps a name to a dotted path"),
    (lambda s: s["check"]["config"].update(inputs={"hypotheses": ["outputs.draft.portfolio", 3]}), "config.inputs maps a name to a dotted path"),
    (lambda s: s["route"].update(config={"domain": "ecommerce"}), "only valid on DOMAIN_OPERATION"),
])
def test_manifest_validation_refuses_a_malformed_domain_binding(tmp_path, mutate, needle):
    with pytest.raises(M.ManifestError) as exc:
        M.load_manifest(_manifest_with(tmp_path, mutate))
    assert needle in str(exc.value)


def test_shipped_manifests_are_untouched_by_the_new_step_type():
    for m in M.list_manifests():
        assert not any(s["type"] == "DOMAIN_OPERATION" for s in m.steps.values()), m.adapter_id


# ─────────────────────────────────────────────────────────── the executor, against the real engine
def _state(outputs):
    return RunState(run_id="adr_" + "0" * 32, adapter_id=ADAPTER_ID, status="running", input={"seed": "runners lose small items"}, outputs=outputs)


def _step(step_id="check"):
    return {"run_id": "adr_" + "0" * 32, "step_id": step_id, "sequence": 2, "step_type": "DOMAIN_OPERATION", "context": {}}


def test_executor_runs_the_engines_own_law_and_records_lineage():
    m = M.load_manifest(FIXTURES / f"{ADAPTER_ID}.json")
    bad = W.exec_domain(_step(), _state({"draft": {"portfolio": INADMISSIBLE}}), m)["output"]
    assert bad["admissible"] is False and any("duplicate mechanism families" in e for e in bad["portfolio_errors"])
    good = W.exec_domain(_step(), _state({"draft": {"portfolio": ADMISSIBLE}}), m)["output"]
    assert good["admissible"] is True and good["bridge_errors"] == [] and good["portfolio_errors"] == [] and good["hypotheses_checked"] == 3
    assert good["_domain"]["domain"] == "ecommerce" and good["_domain"]["operation"] == "hypotheses.validate_bridge"
    assert len(good["_domain"]["binding_sha256"]) == 64


def test_a_domain_refusal_is_a_typed_gap_with_the_domains_own_code():
    m = M.load_manifest(FIXTURES / f"{ADAPTER_ID}.json")
    out = W.exec_domain(_step(), _state({"draft": {}}), m)                       # the selected input does not exist
    assert out == {"gap": {"code": "HYPOTHESES_MISSING", "message": out["gap"]["message"]}} and "hypotheses.validate_bridge" in out["gap"]["message"]


def test_an_unknown_operation_and_a_missing_domain_are_typed_gaps(tmp_path):
    m = M.load_manifest(_manifest_with(tmp_path, lambda s: s["check"]["config"].update(operation="not.an_operation")))
    assert W.exec_domain(_step(), _state({"draft": {"portfolio": ADMISSIBLE}}), m)["gap"]["code"] == "DOMAIN_OPERATION_UNKNOWN"
    m = M.load_manifest(_manifest_with(tmp_path, lambda s: s["check"]["config"].update(domain="nowhere")))
    assert W.exec_domain(_step(), _state({"draft": {"portfolio": ADMISSIBLE}}), m)["gap"]["code"] == "DOMAIN_BINDING_MISSING"


def _fake_domain(tmp_path, monkeypatch, body: str):
    (tmp_path / "ecommerce").mkdir()
    (tmp_path / "ecommerce" / "binding.py").write_text(body)
    monkeypatch.setattr(W, "_DOMAINS_DIR", tmp_path)
    return M.load_manifest(FIXTURES / f"{ADAPTER_ID}.json")


@pytest.mark.parametrize("body, needle", [
    ("import sys; sys.exit(3)", "exited 3"),
    ("print('not json')", "did not return one JSON object"),
    ("print('{\"ok\": \"yes\"}')", "no boolean `ok`"),
    ("print('{\"ok\": false, \"code\": \"lower case\", \"message\": \"x\"}')", "refused without a typed code"),
    ("print('{\"ok\": true}')", "ok without an output object"),
    ("import time; time.sleep(5)", "timed out"),
])
def test_a_crash_a_timeout_or_a_malformed_response_raises_for_the_runtime_to_type(tmp_path, monkeypatch, body, needle):
    m = _fake_domain(tmp_path, monkeypatch, body)
    monkeypatch.setattr(W, "DOMAIN_TIMEOUT_S", 1.0)
    with pytest.raises(RuntimeError) as exc:
        W.exec_domain(_step(), _state({"draft": {"portfolio": ADMISSIBLE}}), m)
    assert needle in str(exc.value)


def test_the_binding_runs_with_a_minimal_environment(tmp_path, monkeypatch):
    """No DSN, token or key reaches domain code: the worker's environment is not inherited."""
    monkeypatch.setenv("POLYMATH_PG_DSN", "postgresql://secret")
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", "secret")
    m = _fake_domain(tmp_path, monkeypatch, "import json, os; print(json.dumps({'ok': True, 'output': {'env': sorted(os.environ)}}))")
    env = W.exec_domain(_step(), _state({"draft": {"portfolio": ADMISSIBLE}}), m)["output"]["env"]
    assert not [k for k in env if k.startswith("POLYMATH_")] and "PATH" in env


# ─────────────────────────────────────────────────────────── the gate: through service.advance, with the real executor table
@pytest.fixture
def runtime(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    service.reset_registry()
    yield store
    service.reset_registry()


def _drive(portfolios):
    rid = service.start(None, adapter_id=ADAPTER_ID, input_payload={"seed": "runners lose small items"}, directory=FIXTURES)["run_id"]
    drafts = iter(portfolios)
    for _ in range(30):
        st = service.advance(None, rid, W.EXECUTORS, max_steps=1, directory=FIXTURES)
        if st.terminal:
            return rid, st
        if st.status == "awaiting_agent":
            step = service.next_step(None, rid, directory=FIXTURES)["step"]
            service.submit(None, rid, {"step_id": step["step_id"], "payload": {"portfolio": next(drafts)}, "submitted_by": {"agent_identity": "test-agent"}}, directory=FIXTURES)
    raise AssertionError("run did not terminate")


def test_a_real_domain_law_governs_a_run_through_the_existing_runtime(runtime):
    rid, st = _drive([INADMISSIBLE, ADMISSIBLE])
    assert st.status == "completed" and st.branch_loops == 1
    rows = runtime.list_steps(None, rid)
    assert [r["step_id"] for r in rows] == ["draft", "check", "route", "draft", "check", "route", "compile"]
    checks = [r for r in rows if r["step_id"] == "check"]
    assert [r["step_type"] for r in checks] == ["DOMAIN_OPERATION"] * 2 and [r["status"] for r in checks] == ["executed"] * 2
    assert checks[0]["output"]["admissible"] is False and checks[1]["output"]["admissible"] is True          # the law sent the run back to reasoning
    assert checks[1]["receipt"]["step_type"] == "DOMAIN_OPERATION" and checks[1]["receipt"]["validation"]["ok"] is True
    assert service.result(None, rid)["status"] == "completed"


def test_a_domain_crash_is_a_typed_run_failure_not_an_escaped_exception(runtime, tmp_path, monkeypatch):
    (tmp_path / "ecommerce").mkdir()
    (tmp_path / "ecommerce" / "binding.py").write_text("raise SystemExit(9)")
    monkeypatch.setattr(W, "_DOMAINS_DIR", tmp_path)
    rid, st = _drive([ADMISSIBLE])
    assert st.status == "failed" and st.failure["code"] == "STEP_EXECUTOR_ERROR" and st.failure["step_id"] == "check"


def test_a_domain_refusal_stops_the_run_with_the_domains_code(runtime, tmp_path, monkeypatch):
    (tmp_path / "ecommerce").mkdir()
    (tmp_path / "ecommerce" / "binding.py").write_text("print('{\"ok\": false, \"code\": \"POPULATION_NOT_FOUND\", \"message\": \"no population\"}')")
    monkeypatch.setattr(W, "_DOMAINS_DIR", tmp_path)
    rid, st = _drive([ADMISSIBLE])
    assert st.status == "terminal_gap" and st.gap["code"] == "POPULATION_NOT_FOUND" and st.gap["step_id"] == "check"
