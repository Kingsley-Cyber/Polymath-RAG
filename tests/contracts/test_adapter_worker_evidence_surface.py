"""GOVERNED-CONVERGENCE-V1 TG2b — the adapter step worker and the evidence boundary.

Two kinds of proof, both about `workers/workers/adapter_step_worker.py`:

1. STATIC (AST): the worker and the pure boundary module hold NO literal of a Polymath synthesis route; every orchestrator
   POST goes through the allow-listed `_orch_post`; the evidence executor never reads a step output (the ORIGINAL-need rule).
2. BEHAVIOUR with the orchestrator stubbed: exact request body + attributable User-Agent, contract mismatch = terminal gap and
   NEVER a fallback, unreachable = degraded legacy fallback or a typed gap, empty evidence = success, kill switch = the
   pre-boundary legacy call, one call per live hypothesis (bounded), graph union.

The worker module is loaded BY FILE PATH from this checkout: the editable `.pth` resolves the `workers` package to the MAIN
checkout, so a package import would exercise the wrong file inside a worktree. (Live R1 qualification after merge + bounce is
still the proof that the DEPLOYED worker behaves this way; this file proves the logic of the file under review.)
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter.manifest import ADAPTER_DIR, list_manifests  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402

WORKER = ROOT / "workers" / "workers" / "adapter_step_worker.py"
MODULE = ROOT / "shared" / "polymath_shared" / "adapter" / "evidence_boundary.py"
SYNTHESIS_ROUTES = ("/chat", "/chat/stream", "/ask")
EXAMPLE = json.loads((ROOT / "contracts/evidence/v1/evidence_packet.example.json").read_text())


# ─────────────────────────────────────────────────────────── 1. static
def _string_constants(path: pathlib.Path) -> list[str]:
    return [n.value for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


@pytest.mark.parametrize("path", [WORKER, MODULE], ids=["worker", "evidence_boundary"])
def test_no_synthesis_route_literal(path):
    """No string constant — code, f-string part, comment-free docstring — names /chat, /chat/stream or /ask. The ONE lawful
    chat-prefixed path is the evidence route, so it is removed before scanning; anything left that still looks like a
    synthesis route fails."""
    for const in _string_constants(path):
        residue = const.replace(EB.EVIDENCE_PATH, "")
        for route in SYNTHESIS_ROUTES:
            assert route not in residue, f"{path.name}: synthesis route {route!r} in literal {const[:80]!r}"


def test_the_evidence_route_literal_lives_only_in_the_pure_module():
    assert EB.EVIDENCE_PATH in _string_constants(MODULE)
    assert all(EB.EVIDENCE_PATH not in c for c in _string_constants(WORKER))


def _functions(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_every_orchestrator_post_is_allow_listed_and_http_lives_in_one_function():
    tree = ast.parse(WORKER.read_text())
    fns = _functions(tree)
    post = fns["_orch_post"]
    first = next(s for s in post.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)))
    assert isinstance(first, ast.Expr) and ast.unparse(first.value) == "EB.assert_allowed_path(path)"          # checked BEFORE any I/O
    # httpx is touched nowhere else in the worker
    users = {name for name, fn in fns.items() for n in ast.walk(fn) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "httpx"}
    assert users == {"_orch_post"}
    # every call site passes a path that is on the allow-list
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_orch_post"):
        arg = call.args[0]
        if isinstance(arg, ast.Constant):
            assert arg.value in EB.ALLOWED_ORCH_PATHS, arg.value
        else:
            assert ast.unparse(arg) == "EB.EVIDENCE_PATH", ast.unparse(arg)


def test_the_evidence_executor_never_reads_a_step_output():
    fn = _functions(ast.parse(WORKER.read_text()))["exec_evidence"]
    touched = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert "outputs" not in touched and "output_order" not in touched          # a compiled reformulation can not become a need
    called = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "EB.original_needs" in called and "_query_text" not in called


# ─────────────────────────────────────────────────────────── 2. behaviour (orchestrator stubbed)
@pytest.fixture()
def worker(monkeypatch):
    monkeypatch.delenv(EB.ENV_SURFACE, raising=False)
    spec = importlib.util.spec_from_file_location("adapter_step_worker_under_test", WORKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert pathlib.Path(mod.__file__).resolve() == WORKER.resolve()               # the executed path IS the file under review
    assert pathlib.Path(mod.EB.__file__).resolve() == MODULE.resolve()
    return mod


MANIFEST = next(m for m in list_manifests(ADAPTER_DIR) if m.adapter_id == "trail.product_discovery")
SEED = "running belts bounce on long runs"
REFORMULATION = "anti-bounce waist pack ergonomics"
HYPS = [{"hypothesis_id": f"hyp_{i}", "statement": f"hypothesis number {i}"} for i in range(5)]


def _state() -> RunState:
    return RunState(run_id="adr_" + "a" * 32, adapter_id=MANIFEST.adapter_id, status="running", input={"seed": SEED, "corpus_ids": ["cinema"]},
                    options={}, outputs={"B_plan": {"queries": [REFORMULATION], "rows": []}}, output_order=("B_plan",))


def _step(step_id: str, sequence: int = 3, hypotheses=None) -> dict:
    return {"run_id": "adr_" + "a" * 32, "step_id": step_id, "sequence": sequence, "context": {"hypotheses": hypotheses or []}}


class Orch:
    """Records every `_orch_post` call; answers per path from a queue (an Exception instance is raised)."""

    def __init__(self, **answers):
        self.answers = {k.replace("evidence", EB.EVIDENCE_PATH).replace("retrieve", "/retrieve"): list(v) for k, v in answers.items()}
        self.calls: list[dict] = []

    def __call__(self, path, body, *, user_agent=None):
        EB.assert_allowed_path(path)
        self.calls.append({"path": path, "body": body, "user_agent": user_agent})
        queue = self.answers.get(path) or []
        answer = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else {})
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)


PACKET = {"evidence_packet": EXAMPLE, "synthesis_performed": False}
LEGACY = {"evidence_contract": "retrieve-evidence-rows-v1", "graph_facts": [1, 2],
          "evidence_rows": [{"id": "c_legacy", "kind": "chunk", "text": "legacy text", "corpus_id": "cinema"}, {"id": "f_legacy", "kind": "graph_fact", "text": "a -> b"}]}


def test_b_retrieve_sends_the_original_seed_with_the_exact_body_and_an_attributable_user_agent(worker, monkeypatch):
    orch = Orch(evidence=[PACKET]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert [c["path"] for c in orch.calls] == [EB.EVIDENCE_PATH]
    assert orch.calls[0]["body"] == {"message": SEED, "corpus_id": "cinema", "mode": "WILDCARD", "corpus_explorer": True}     # NOT the reformulation
    assert REFORMULATION not in json.dumps(orch.calls) and orch.calls[0]["user_agent"] == f"polymath-adapter-step/adr_{'a' * 32}/B_retrieve/3"
    o = out["output"]
    assert (o["surface"], o["retrieval_completed"], o["evidence_contract"], o["needs"]) == ("evidence_boundary", True, "evidence-packet-v1", [SEED])
    assert [r["id"] for r in o["rows"]] == ["chunk_0001", "chunk_0002"] and o["rows"][0]["text"] and "degraded" not in o
    assert o["calls"][0]["contract"]["valid"] is True and out["evidence_refs"][0]["utility_role"] == "DIRECT" and out["evidence_refs"][1]["origin"] == "CORPUS_EXPLORE"


def test_empty_evidence_is_a_success(worker, monkeypatch):
    monkeypatch.setattr(worker, "_orch_post", Orch(evidence=[{"evidence_packet": {**EXAMPLE, "evidence": []}}]))
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert "gap" not in out and out["output"]["rows"] == [] and out["output"]["retrieval_completed"] is True and out["evidence_refs"] == []
    assert "degraded" not in out["output"]


@pytest.mark.parametrize("bad", [{"evidence_packet": {**EXAMPLE, "schema_version": "evidence-packet-v2"}},
                                 {"evidence_packet": {**EXAMPLE, "synthesis_performed": True}}, {"answer": "a synthesized answer"}])
def test_a_contract_mismatch_is_a_terminal_gap_and_never_a_fallback(worker, monkeypatch, bad):
    orch = Orch(evidence=[bad], retrieve=[LEGACY]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert out["gap"]["code"] == "EVIDENCE_CONTRACT_MISMATCH" and "output" not in out
    assert [c["path"] for c in orch.calls] == [EB.EVIDENCE_PATH]                          # the legacy lane was NOT consulted


def test_an_unreachable_surface_falls_back_to_the_legacy_lane_and_says_so(worker, monkeypatch):
    orch = Orch(evidence=[worker.OrchUnavailable("connection refused")], retrieve=[LEGACY]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    o = out["output"]
    assert [c["path"] for c in orch.calls] == [EB.EVIDENCE_PATH, "/retrieve"] and orch.calls[1]["body"]["explore"] is True
    assert (o["surface"], o["degraded"], o["degraded_reasons"], o["fallback"]) == ("retrieve", True, ["evidence_boundary_unavailable"], "retrieve")
    assert o["boundary_failures"][0]["error"] == "connection refused" and [r["id"] for r in o["rows"]] == ["c_legacy", "f_legacy"]


def test_surface_and_fallback_both_unreachable_is_a_typed_gap(worker, monkeypatch):
    down = worker.OrchUnavailable("connection refused")
    monkeypatch.setattr(worker, "_orch_post", Orch(evidence=[down], retrieve=[down]))
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert out["gap"]["code"] == "EVIDENCE_SURFACE_UNAVAILABLE"


def test_a_rejected_request_is_a_caller_defect_not_an_outage(worker, monkeypatch):
    monkeypatch.setattr(worker, "_orch_post", Orch(evidence=[worker.OrchRejected("422 unknown_mode")], retrieve=[LEGACY]))
    with pytest.raises(worker.OrchRejected):                                             # -> STEP_EXECUTOR_ERROR, never masked by a fallback
        worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)


def test_the_kill_switch_reproduces_the_pre_boundary_legacy_call(worker, monkeypatch):
    monkeypatch.setenv(EB.ENV_SURFACE, "retrieve")
    orch = Orch(retrieve=[LEGACY]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_retrieve(_step("B_retrieve"), _state(), MANIFEST)
    assert [c["path"] for c in orch.calls] == ["/retrieve"]
    assert orch.calls[0]["body"] == {"query": SEED, "corpus_ids": ["cinema"], "limit": 24, "explore": True}     # == adapter 2.1.0's B_retrieve call
    assert (out["output"]["surface"], out["output"]["mode"], out["output"]["degraded_reasons"]) == ("retrieve", "EXPLORE", ["surface_forced_by_env"])
    graph = worker.exec_graph_expand(_step("B_graph", 4), _state(), MANIFEST)
    assert orch.calls[-1]["body"] == {"query": SEED, "corpus_ids": ["cinema"], "explore": True, "limit": 20}
    assert [r["id"] for r in graph["output"]["graph_rows"]] == ["f_legacy"] and graph["output"]["degraded_reasons"] == ["surface_forced_by_env"]


def test_f_retrieve_sends_one_call_per_live_hypothesis_bounded_with_the_skip_recorded(worker, monkeypatch):
    orch = Orch(evidence=[PACKET]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_retrieve(_step("F_retrieve", 9, HYPS), _state(), MANIFEST)
    assert [c["body"]["message"] for c in orch.calls] == ["hypothesis number 0", "hypothesis number 1", "hypothesis number 2"]
    assert all(c["body"]["corpus_id"] == "cinema" for c in orch.calls)                   # ONE corpus per call
    assert out["output"]["truncated"] == [{"corpus_id": "cinema", "need_index": 3, "reason": "max_calls"}, {"corpus_id": "cinema", "need_index": 4, "reason": "max_calls"}]
    assert len(out["output"]["calls"]) == 3 and [r["id"] for r in out["output"]["rows"]] == ["chunk_0001", "chunk_0002"]      # union, deduplicated


def test_a_partial_outage_keeps_the_validated_evidence_and_is_recorded(worker, monkeypatch):
    orch = Orch(evidence=[PACKET, worker.OrchUnavailable("timeout"), PACKET]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_retrieve(_step("F_retrieve", 9, HYPS), _state(), MANIFEST)
    o = out["output"]
    assert o["retrieval_completed"] is False and o["degraded_reasons"] == ["evidence_boundary_partial"] and len(o["calls"]) == 2
    assert o["boundary_failures"] == [{"need_index": 1, "corpus_id": "cinema", "error": "timeout"}] and len(o["rows"]) == 2


def test_graph_steps_union_the_graph_mode_packet_with_the_legacy_graph_facts(worker, monkeypatch):
    orch = Orch(evidence=[PACKET], retrieve=[LEGACY]); monkeypatch.setattr(worker, "_orch_post", orch)
    out = worker.exec_graph_expand(_step("B_graph", 4), _state(), MANIFEST)
    assert orch.calls[0]["body"] == {"message": SEED, "corpus_id": "cinema", "mode": "GRAPH", "corpus_explorer": False}
    assert [c["path"] for c in orch.calls] == [EB.EVIDENCE_PATH, "/retrieve"]
    o = out["output"]
    assert [r["id"] for r in o["rows"]] == ["chunk_0001", "chunk_0002"] and [r["id"] for r in o["graph_rows"]] == ["f_legacy"] and o["graph_facts"] == 2
    assert [r["id"] for r in out["evidence_refs"]] == ["chunk_0001", "chunk_0002", "f_legacy"]


def test_the_real_post_refuses_a_synthesis_route_before_any_io(worker):
    for route in SYNTHESIS_ROUTES:
        with pytest.raises(EB.PathNotAllowed):
            worker._orch_post(route, {"message": "x"})
