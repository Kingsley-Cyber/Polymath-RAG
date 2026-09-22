"""MERGED-CHECKOUT proof of the three call sites no worktree test could count for (Step 2b of the bootstrap: under pytest `workers` and
`orchestrator` resolve to the MAIN checkout). Runs only where those packages ARE this checkout — the integration gate
(`scripts/semantic_restoration_gate.py --phase integration`) requires it to PASS, never skip, on the merged main checkout.

  1. `workers.adapter_step_worker._payload_for("gaps.compile", …)` sends the HARVESTED per-hypothesis gaps when the step opted in
     (`config.gaps_from`) and the previous payload otherwise (Slice 2, call site 1);
  2. `workers.adapter_step_worker.exec_evidence` hands `step["_compiled_need"]` to the evidence boundary (Slice 2, call site 2);
  3. `orchestrator.api.ui` applies `plan_for_evidence_route` BEFORE the skip decision on the evidence-only route (D-a, zero rows).
No database, no network: the boundary is intercepted before any call."""
from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter import transitions as T  # noqa: E402
from polymath_shared.adapter.manifest import load_manifest  # noqa: E402

W = importlib.import_module("workers.adapter_step_worker")
UI_PATH = ROOT / "orchestrator" / "orchestrator" / "api" / "ui.py"
RUN = "adr_" + "6" * 32
H1 = "hyp_" + "a" * 24


def _this_checkout(mod) -> bool:
    return pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT)


pytestmark = pytest.mark.skipif(not _this_checkout(W), reason=f"workers resolves to another checkout: {W.__file__} — this proof counts only on the merged main checkout")


def test_the_code_under_test_is_this_checkout():
    assert _this_checkout(W) and _this_checkout(EB) and _this_checkout(T)


def _state():
    m = load_manifest(ROOT / "config" / "adapters" / "ecommerce.product_research.json")
    return m, T.start_run(m, RUN, {"seed": "people who photograph landscapes alone, on the trail, in cold or wet weather"})


HARVEST = {"knowledge_gaps": [{"gap_id": "gap_" + "a" * 8 + "_l" + "1" * 8, "hypothesis_id": H1, "question": "do lone photographers miss shots digging for a battery?", "evidence_role": "behavior", "status": "open", "origin": "ledger"}],
           "open_gaps": [{"gap_id": "gap_" + "a" * 8 + "_t" + "2" * 8, "hypothesis_id": H1, "question": "is the friction primitive backed by an independent source?", "evidence_role": "behavior", "status": "open", "origin": "trail"}]}


def test_call_site_1_gaps_compile_sends_the_harvest_when_the_step_opted_in_and_the_previous_payload_otherwise():
    m, state = _state()
    hyps = [{"hypothesis_id": H1, "revision": 0, "status": "proposed", "statement": "s" * 12}]
    step = {"run_id": RUN, "step_id": "F_gaps", "sequence": 9, "context": {"hypotheses": hyps, "admitted_evidence_ids": [], "semantics": {"research_gaps": HARVEST}}, "harness_action": None}
    opted = W._payload_for("gaps.compile", step, state, {"stage": "F_gaps", "gaps_from": "context.semantics.research_gaps"})
    assert opted["hypotheses"] == hyps and [g["hypothesis_id"] for g in opted["knowledge_gaps"]] == [H1] and len(opted["open_gaps"]) == 1
    assert set(opted["knowledge_gaps"][0]) <= {"gap_id", "hypothesis_id", "question", "evidence_role", "status"}     # Trail's gap wire, nothing of the harvest's provenance
    legacy = W._payload_for("gaps.compile", {**step, "context": {**step["context"], "semantics": None}}, state, {"stage": "F_gaps"})
    assert legacy["knowledge_gaps"] == [] and legacy["open_gaps"] == [] and "semantics" not in legacy                # the previous behaviour, untouched


class _Captured(Exception):
    pass


def test_call_site_2_exec_evidence_hands_the_runtime_resolved_need_to_the_boundary(monkeypatch):
    m, state = _state()
    seen: dict = {}

    def capture(cfg, seed, options, hypotheses, *, compiled_need=None):
        seen["compiled_need"] = compiled_need
        raise _Captured()

    monkeypatch.setattr(W.EB, "original_needs", capture)
    step = {"run_id": RUN, "step_id": "K_retrieve", "sequence": 12, "context": {"hypotheses": []}, "harness_action": None, "_compiled_need": "what holds a spare battery within reach of one hand?"}
    with pytest.raises(_Captured):
        W.exec_evidence(step, state, m, ["cinema"], legacy=lambda *a, **k: None)
    assert seen["compiled_need"] == "what holds a spare battery within reach of one hand?"
    seen.clear()
    with pytest.raises(_Captured):
        W.exec_evidence({k: v for k, v in step.items() if k != "_compiled_need"}, state, m, ["cinema"], legacy=lambda *a, **k: None)
    assert seen["compiled_need"] is None                                                                              # no resolved need: exactly as before


def test_call_site_3_the_evidence_route_override_is_wired_before_the_skip_decision():
    ui = UI_PATH.read_text(encoding="utf-8")
    call, skip = ui.index("_plan = plan_for_evidence_route(_plan)"), ui.index("_skip_retrieval = (not _plan.retrieval_required)")
    assert 0 < skip - call < 400
    import polymath_shared.chat_plan as CP
    assert _this_checkout(CP) and callable(CP.plan_for_evidence_route)
