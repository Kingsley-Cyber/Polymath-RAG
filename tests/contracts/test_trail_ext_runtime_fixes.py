"""TRAIL-EXT-BUGHUNT-V1, group `runtime` — the pure half of the fixes (no store, no network, no daemon).

Each test names the finding it reproduces (docs/wiki/experiments/trail-ext-bughunt-2026-09-26). Behaviour through the real runtime
(in-memory store, stub or embedded TrailSignal, the out-of-process ecommerce binding) is in
tests/determinism/test_adapter_trail_ext_runtime_fixes.py. Where TrailSignal's own rule decides, the PINNED Trail model under
`governance/trail/` is asked, never a copy of its rule.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import jsonschema
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "governance" / "trail" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import service
from polymath_shared.adapter import trail_client as TC
from polymath_shared.adapter import transitions as T
from polymath_shared.adapter.transitions import RunState
from trail_signal.contexts.evidence.public.contracts import (
    HarnessResearchReceiptV1,
)

RUN = "adr_" + "a" * 32
EXAMPLE_RECEIPT = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
RECEIPT_STEP = {"run_id": EXAMPLE_RECEIPT["run_id"], "harness_action": {"action_id": EXAMPLE_RECEIPT["action_id"]}}


def test_the_code_under_test_is_this_checkout():
    for mod in (C, service, TC, T):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__
    assert pathlib.Path(sys.modules[HarnessResearchReceiptV1.__module__].__file__).resolve().is_relative_to(ROOT / "governance" / "trail")


# ─────────────────────────────────────────────────────────── B-02 / B-04: a diagnostic longer than its own contract's bound
def _lineage_errors(n: int) -> list[str]:
    """The ecommerce lineage law's own message format with the live 70-char chunk ids (the bug hunt measured 190 chars each)."""
    return [f"latent_structures[{i}]: corpus row {('chunk_' + format(i, '064x'))!r} is UNCLASSIFIED — classify it in row_relevance before it "
            "becomes lineage (fail-closed)" for i in range(n)]


def test_bounded_text_keeps_the_head_and_the_tail_and_counts_what_it_elides():
    text = "evidence_gaps/0/question: '" + "q" * 2600 + "' is too long"
    out = C.bounded_text(text, 1000)
    assert len(out) <= 1000 and out.startswith("evidence_gaps/0/question: 'qqq") and out.endswith("' is too long")   # which field, which rule
    elided = int(out.split("…[+", 1)[1].split(" chars elided]", 1)[0])
    assert len(out) - len(f" …[+{elided} chars elided]… ") + elided == len(text)                                   # every elided char is counted
    assert C.bounded_text("short", 1000) == "short"


def test_b02_a_receipt_bounds_its_copy_of_a_long_reason_instead_of_raising():
    step = {"run_id": RUN, "step_id": "Z_refuse_lineage", "step_type": "DOMAIN_OPERATION", "sequence": 40}
    reason = "law.refuse: " + "; ".join(_lineage_errors(6))
    assert len(reason) > 1000                                                                     # the receipt's cap is 1000 per error
    r = service._receipt(step, "skipped", service.now_iso(), evidence_ids=[], model=None, validation={"ok": False, "errors": [reason, "short"]})
    assert C.validate("adapter_step_receipt", r) == []
    first = r["validation"]["errors"][0]
    assert len(first) <= 1000 and first.startswith(reason[:300]) and first.endswith(reason[-150:]) and "chars elided" in first
    assert r["validation"]["errors"][1] == "short"


def test_b02_a_receipt_bounds_a_failure_message_to_the_failure_contract():
    step = {"run_id": RUN, "step_id": "F_retrieve", "step_type": "POLYMATH_RETRIEVE", "sequence": 7}
    failure = {"code": "STEP_EXECUTOR_ERROR", "message": "RuntimeError: " + "x" * 2500, "step_id": "F_retrieve"}
    r = service._receipt(step, "failed", service.now_iso(), evidence_ids=[], model=None, validation={"ok": False, "errors": [failure["message"]]},
                         failure=failure)
    assert C.validate("adapter_step_receipt", r) == []
    assert len(r["failure"]["message"]) <= 2000 and r["failure"]["message"].startswith("RuntimeError: xxx") and r["failure"]["code"] == "STEP_EXECUTOR_ERROR"


def test_b02_a_gap_message_is_bounded_to_the_gap_contract_of_the_status_and_the_result():
    reason = "; ".join(["admitted/3/detail: '" + "d" * 900 + "' is too long"] * 5)                   # an ADMISSION_INVALID-shaped reason, 4.6k chars
    st = T.terminal_gap(RunState(run_id=RUN, adapter_id="x", status="running"), "ADMISSION_INVALID", reason, step_id="J_admit")
    assert len(st.gap["message"]) <= 2000 and st.gap["message"].startswith("admitted/3/detail") and st.gap["code"] == "ADMISSION_INVALID"
    for name in ("adapter_run_status", "adapter_result"):
        assert list(jsonschema.Draft202012Validator(C.schema(name)["properties"]["gap"]).iter_errors(st.gap)) == [], name


# ─────────────────────────────────────────────────────────── B-03: a receipt TrailSignal refuses is refused at submit, not at admission
def _trail_refuses(receipt: dict) -> bool:
    try:
        HarnessResearchReceiptV1.model_validate_json(json.dumps(receipt))
    except Exception:  # noqa: BLE001 — pydantic's ValidationError, whatever the rule
        return True
    return False


@pytest.mark.parametrize("label, edit, field", [
    ("utc_offset_-06:00", lambda r: r.update(started_at="2026-09-13T14:11:00-06:00", completed_at="2026-09-13T14:26:30-06:00"), "started_at"),
    ("offset_+01:00", lambda r: r["sources"][1].update(retrieved_at="2026-09-13T21:19:40+01:00"), "retrieved_at"),
    ("date_only_published", lambda r: r["sources"][0].update(published_at_if_known="2026-05-02"), "published_at_if_known"),
    ("naive_retrieved", lambda r: r["sources"][0].update(retrieved_at="2026-09-13T20:14:02"), "retrieved_at"),
    ("relative_age", lambda r: r["sources"][0].update(published_at_if_known="2 years ago"), "published_at_if_known"),
    ("integer_valued_float_sample_n", lambda r: r["observations"][0]["metric_if_present"].update(sample_n=4.0), "sample_n"),
    ("integer_valued_float_query_count", lambda r: r["tool_trace"][0].update(query_count=6.0), "query_count"),
])
def test_b03_what_trail_refuses_on_timestamps_and_integers_is_refused_at_submit(label, edit, field):
    rec = copy.deepcopy(EXAMPLE_RECEIPT)
    edit(rec)
    assert _trail_refuses(rec), label                                                           # TrailSignal refuses it at evidence.admit …
    errors = T.validate_receipt(RECEIPT_STEP, rec)
    assert any(field in e for e in errors), (label, errors)                                     # … so the submit path refuses it first, naming the field


@pytest.mark.parametrize("value", ["2026-09-13T20:14:02Z", "2026-09-13T20:14:02+00:00", "2026-09-13T20:14:02.250Z", "2026-09-13T20:14:02.1234567Z"])
def test_b03_utc_date_times_trail_accepts_still_pass_at_submit(value):
    rec = copy.deepcopy(EXAMPLE_RECEIPT)
    rec["sources"][0]["retrieved_at"] = value
    assert not _trail_refuses(rec) and T.validate_receipt(RECEIPT_STEP, rec) == []
    assert T.validate_receipt(RECEIPT_STEP, EXAMPLE_RECEIPT) == []


def test_b03_the_receipt_rules_tell_the_harness_the_utc_form():
    assert any("UTC" in r and "Z" in r for r in T.HARNESS_RECEIPT_RULES)
    assert all(len(r) <= 500 for r in T.HARNESS_RECEIPT_RULES)                                   # the step contract's item bound


# ─────────────────────────────────────────────────────────── B-05: an admission request over TrailSignal's 64 KB ceiling
KEY, SNAP = "adr-aaaa:Q_admit:40", "trs-x"


def _admit_payload(n_obs: int, n_src: int = 20) -> dict:
    """R7-calibrated product-reality observations (the bug hunt used 824 B each; R7 measured 872 B)."""
    hyp = "hyp_" + "c" * 24
    rec = copy.deepcopy(EXAMPLE_RECEIPT)
    rec.update({"action_id": "hact_" + "a" * 24, "run_id": RUN, "harness_id": "test-harness", "tool_trace": [], "limitations": []})
    rec["sources"] = [{"source_id": f"src_{i}", "url": f"https://www.retailer-{i}.example/p/item-{i:04d}-running-belt-key-holder",
                       "source_class": "marketplace_listing", "retrieved_at": "2026-09-26T05:40:00Z", "published_at_if_known": None} for i in range(n_src)]
    rec["observations"] = [{"observation_id": f"obs_{i}", "source_id": f"src_{i % n_src}", "claim": f"listing {i}: a zip belt holds keys but rides up ({i})",
                            "paraphrase_or_excerpt": "several reviewers describe the belt bouncing and the zip being hard to open with gloves " * 2,
                            "metric_if_present": None, "context": f"concept: pc_1 · relation: competitor · product: running belt model {i} · " + "c" * 310,
                            "evidence_role_claimed": "competition", "hypothesis_ids": [hyp]} for i in range(n_obs)]
    hyps = [{"hypothesis_id": f"hyp_{i:024x}", "revision": 1, "status": "proposed", "statement": "runners lose small items mid stride " * 4} for i in range(6)]
    return {"stage": "product_reality", "hypotheses": hyps, "admitted_evidence_ids": [f"fev_{i:024x}" for i in range(60)],
            "action_id": rec["action_id"], "receipt": rec}


def _rpc_body_bytes(req: dict) -> int:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": req["operation_kind"], "arguments": {"request": req}}}
    return len(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def test_b05_an_admission_over_the_ceiling_is_trimmed_to_fit_trails_own_measure_and_the_trim_is_recorded():
    pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need packageurl")
    from trail_signal.contexts.workflow.application.research_operations import (
        canonical_text,
    )
    from trail_signal.contexts.workflow.public.operations import (
        BoundedResearchRequestV1,
    )
    payload = _admit_payload(80)
    before = copy.deepcopy(payload)
    with pytest.raises(ValueError, match="65536"):                                              # the defect: a budgeted receipt cannot be sent at all
        TC.bounded_request("evidence.admit", payload, key=KEY, run_ref=RUN, registry_snapshot_id=SNAP)
    fitted, trimmed = TC.fit_admission_request(payload, key=KEY, run_ref=RUN, registry_snapshot_id=SNAP)
    assert payload == before                                                                    # the stored receipt is never mutated
    req = TC.bounded_request("evidence.admit", fitted, key=KEY, run_ref=RUN, registry_snapshot_id=SNAP)
    assert len(canonical_text(BoundedResearchRequestV1.model_validate(req)).encode("utf-8")) <= TC.REQUEST_BYTES_MAX   # Trail's measure, defaults included
    assert _rpc_body_bytes(req) <= TC.REQUEST_BYTES_MAX                                         # and the JSON-RPC body the client sends
    kept = fitted["receipt"]["observations"]
    assert 0 < len(kept) < 80 and kept == payload["receipt"]["observations"][:len(kept)]       # the harness's order: the tail is what is dropped
    dropped = [o["observation_id"] for o in payload["receipt"]["observations"][len(kept):]]
    assert trimmed["dropped_observation_ids"] == dropped and trimmed["observations_submitted"] == 80 and trimmed["observations_sent"] == len(kept)
    assert trimmed["limit_bytes"] == TC.REQUEST_BYTES_MAX and trimmed["reason"] == "REQUEST_CEILING"
    listed = {s["source_id"] for s in fitted["receipt"]["sources"]}
    assert {o["source_id"] for o in kept} <= listed                                              # no observation names an unlisted source
    assert _trail_refuses(fitted["receipt"]) is False


def test_b05_an_admission_that_fits_is_sent_untouched():
    payload = _admit_payload(10)
    fitted, trimmed = TC.fit_admission_request(payload, key=KEY, run_ref=RUN, registry_snapshot_id=SNAP)
    assert trimmed is None and fitted == payload


# ═══════════════════════════════════════════════════════════ batch B
import importlib.util

import httpx
from polymath_shared.adapter import evidence_boundary as EB
from polymath_shared.adapter import hypotheses as H
from polymath_shared.adapter import research_gaps as RG
from polymath_shared.adapter.manifest import ADAPTER_DIR, load_manifest
from pydantic import ValidationError

NOW = "2026-09-26T00:00:00Z"
ECOM = load_manifest(ADAPTER_DIR / "ecommerce.product_research.json")
WORKER = ROOT / "workers" / "workers" / "adapter_step_worker.py"


@pytest.fixture()
def worker():
    """The worker loaded BY FILE PATH from this checkout (the editable .pth may resolve the `workers` package to another checkout)."""
    spec = importlib.util.spec_from_file_location("adapter_step_worker_bughunt", WORKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert pathlib.Path(mod.__file__).resolve() == WORKER.resolve()
    return mod


def _trail_payload_errors(**fields) -> list:
    pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need packageurl")
    from trail_signal.contexts.workflow.public.operations import ResearchPayloadV1
    try:
        ResearchPayloadV1.model_validate_json(json.dumps(fields))
    except ValidationError as exc:
        return exc.errors()
    return []


# ─────────────────────────────────────────────────────────── B-20: SPLIT children of a later loop round
def _ledger(n: int = 3):
    refs = [{"kind": "chunk", "id": "chunk_k1"}, {"kind": "chunk", "id": "chunk_k2"}]
    states, trs = H.generate(RUN, {"run_id": RUN, "step_id": "C_hypotheses", "sequence": 11, "context": {"evidence_refs": refs}},
                             [{"statement": f"hypothesis number {i} statement", "supporting_evidence_ids": ["chunk_k1"]} for i in range(n)],
                             registry_snapshot_id=None, recorded_at=NOW)
    return {s["hypothesis_id"]: s for s in states}, trs


def _split(current, sequence, parent, tag):
    allowed = {"chunk_k1": "chunk", "chunk_k2": "chunk", **{h: "hypothesis" for h in current}}
    step = {"run_id": RUN, "step_id": "G_mechanisms", "sequence": sequence}
    return H.apply(RUN, step, current, [{"hypothesis_id": parent, "kind": "SPLIT", "cause_refs": [{"kind": "chunk", "id": "chunk_k1"}],
                                         "children": [{"statement": f"{tag} child A statement", "supporting_evidence_ids": ["chunk_k2"]},
                                                      {"statement": f"{tag} child B statement", "supporting_evidence_ids": ["chunk_k2"]}]}],
                   actor="theta", allowed_causes=allowed, recorded_at=NOW, max_hypotheses=8)


def test_b20_split_children_of_a_later_round_get_their_own_ids_and_the_lineage_stays_intact():
    current, trs = _ledger()
    h0, h1 = list(current)[:2]
    s1, t1 = _split(current, 20, h0, "round-one")                                  # G_mechanisms, loop round 1
    current.update({s["hypothesis_id"]: s for s in s1})
    s2, t2 = _split(current, 40, h1, "round-two")                                  # the same step re-entered through M_loop
    kids1 = next(t for t in t1 if t["kind"] == "SPLIT")["child_hypothesis_ids"]
    kids2 = next(t for t in t2 if t["kind"] == "SPLIT")["child_hypothesis_ids"]
    assert len(set(kids1) | set(kids2)) == 4                                       # the defect: kids2 == kids1, the new children silently dropped
    new = {s["hypothesis_id"]: s for s in s2}
    assert all(new[k]["parent_hypothesis_ids"] == [h1] and new[k]["statement"].startswith("round-two") for k in kids2)
    current.update(new)
    assert H.lineage_intact(list(current.values()), trs + t1 + t2) == []


def test_b20_a_child_id_already_in_the_ledger_is_refused_never_silently_dropped():
    current, _ = _ledger()
    h0 = next(iter(current))
    s1, _t = _split(current, 20, h0, "first")
    current.update({s["hypothesis_id"]: s for s in s1})
    with pytest.raises(H.HypothesisRejected, match="already"):                     # the same issuance applied twice: the store would DO NOTHING
        _split(current, 20, h0, "again")


# ─────────────────────────────────────────────────────────── B-21: the SUPPLY directive and the legacy gather
def _gaps_state(extra_gap_key=None):
    hid = "hyp_" + "d" * 24
    agent_gap = {"hypothesis_id": hid, "question": "how often does it happen per run?", "evidence_role": "behavior", **(extra_gap_key or {})}
    gate = {"gap_id": "gap-dddddddd-price", "hypothesis_id": hid, "question": "is there a supplier under the target landed cost?", "evidence_role": "price"}
    return hid, gate, RunState(run_id=RUN, adapter_id=ECOM.adapter_id, status="running", outputs={
        "G_mechanisms": {"transitions": [], "knowledge_gaps": [agent_gap]},
        "K_revise": {"transitions": [], "open_gaps": [dict(agent_gap, question="do they still carry keys in a pocket?")]},
        "R_qualify": {"operation_kind": "opportunity.qualify", "trail_operation_id": "op-9", "qualifications": [], "open_gaps": [gate]}},
        output_order=("G_mechanisms", "K_revise", "R_qualify"))


def test_b21_the_supply_directive_is_compiled_from_the_qualifications_gate_gaps_only(worker):
    _hid, gate, state = _gaps_state()
    cfg = ECOM.step("S_gaps")["config"]
    p = worker._payload_for("gaps.compile", {"step_id": "S_gaps", "context": {"hypotheses": [], "admitted_evidence_ids": []}}, state, cfg)
    assert p["stage"] == "supply" and p["knowledge_gaps"] == []                   # the defect: G_mechanisms' field question was sent to the supply stage
    assert p["open_gaps"] == [gate]
    assert _trail_payload_errors(knowledge_gaps=p["knowledge_gaps"], open_gaps=p["open_gaps"]) == []


def test_b21_the_legacy_gather_sends_trails_closed_gap_shape_never_an_agents_raw_dict(worker):
    hid, _gate, state = _gaps_state({"note": "the agent's own annotation", "priority": "high"})
    cfg = {"stage": "supply"}                                                      # a gaps.compile step without gaps_from (the legacy gather)
    p = worker._payload_for("gaps.compile", {"step_id": "S_gaps", "context": {"hypotheses": [], "admitted_evidence_ids": []}}, state, cfg)
    assert p["knowledge_gaps"] and all(set(g) <= set(RG.TRAIL_GAP_FIELDS) for g in p["knowledge_gaps"] + p["open_gaps"])
    assert _trail_payload_errors(knowledge_gaps=p["knowledge_gaps"], open_gaps=p["open_gaps"]) == []   # the defect: extra_forbidden -> TRAIL_REFUSED
    long_q = {"transitions": [], "knowledge_gaps": [{"hypothesis_id": hid, "question": "q" * 3000, "evidence_role": "behavior"}]}
    state2 = RunState(run_id=RUN, adapter_id=ECOM.adapter_id, status="running", outputs={"G_mechanisms": long_q}, output_order=("G_mechanisms",))
    p2 = worker._payload_for("gaps.compile", {"step_id": "S_gaps", "context": {}}, state2, cfg)
    assert len(p2["knowledge_gaps"][0]["question"]) == 2000                        # bounded as the harvested path bounds it (HarnessActionV1 carries 2000)


# ─────────────────────────────────────────────────────────── B-22 / B-26: agent-written values that cross Trail's strict wire
@pytest.mark.parametrize("role", ["Behavior", "customer behavior", "Workaround", "b"])
def test_b22_a_gap_role_trail_refuses_is_refused_at_submit(role):
    pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need packageurl")
    from trail_signal.contexts.planning.domain.gap_compiler import EvidenceGap
    hid = "hyp_" + "b" * 24
    with pytest.raises(ValidationError):                                           # Trail's gap compiler refuses the role at H_gaps …
        EvidenceGap(gap_id="gap_1", hypothesis_id=hid, question="q", evidence_role=role)
    for key in ("knowledge_gaps", "open_gaps"):                                    # … so the submit-time law names it first
        errors = RG.gap_wire_errors({key: [{"hypothesis_id": hid, "question": "q", "evidence_role": "behavior"}, {"hypothesis_id": hid, "question": "q", "evidence_role": role}]})
        assert len(errors) == 1 and f"{key}[1]" in errors[0] and repr(role) in errors[0], errors
    assert RG.gap_wire_errors({"knowledge_gaps": [{"hypothesis_id": hid, "question": "q", "evidence_role": "behavior"}]}) == []


def test_b22_a_ledger_gap_id_trail_refuses_is_refused_by_the_ledger():
    assert _trail_payload_errors(knowledge_gaps=[{"gap_id": "gap about gloves", "question": "q?", "evidence_role": "friction"}])   # Trail's Identifier
    current, _ = _ledger()
    hid = next(iter(current))
    allowed = {"chunk_k1": "chunk", **{h: "hypothesis" for h in current}}
    step = {"run_id": RUN, "step_id": "G_mechanisms", "sequence": 20}
    bad = [{"hypothesis_id": hid, "kind": "REVISE", "cause_refs": [{"kind": "chunk", "id": "chunk_k1"}],
            "changes": {"knowledge_gaps": [{"gap_id": "gap about gloves", "question": "do hikers take gloves off?", "evidence_role": "friction"}]}}]
    with pytest.raises(H.HypothesisRejected, match="gap about gloves"):
        H.apply(RUN, step, current, bad, actor="theta", allowed_causes=allowed, recorded_at=NOW)
    gen = {"run_id": RUN, "step_id": "C_hypotheses", "sequence": 12, "context": {"evidence_refs": [{"kind": "chunk", "id": "chunk_k1"}]}}
    with pytest.raises(H.HypothesisRejected, match="gap about gloves"):
        H.generate(RUN, gen, [{"statement": "a statement long enough", "supporting_evidence_ids": ["chunk_k1"],
                              "knowledge_gaps": [{"gap_id": "gap about gloves", "question": "q?", "evidence_role": "friction"}]}],
                   registry_snapshot_id=None, recorded_at=NOW, ordinal_base=3)
    ok = [dict(bad[0], changes={"knowledge_gaps": [{"gap_id": "gap-gloves-1", "question": "do hikers take gloves off?", "evidence_role": "friction"}]})]
    assert H.apply(RUN, step, current, ok, actor="theta", allowed_causes=allowed, recorded_at=NOW)[0]


def test_b26_physical_jobs_reach_trail_in_its_closed_shape(worker):
    hid = "hyp_" + "f" * 24
    job = {"hypothesis_id": hid, "job": "keep fingers warm while operating a shutter", "mechanism": "thin conductive tips", "evidence_ids": ["fev_1"], "unknowns": ["fit"]}
    state = RunState(run_id=RUN, adapter_id=ECOM.adapter_id, status="running", outputs={"N_jobs": {"transitions": [], "physical_jobs": [job]}}, output_order=("N_jobs",))
    p = worker._payload_for("territory.project", {"step_id": "O_territory", "context": {"hypotheses": []}}, state, ECOM.step("O_territory")["config"])
    assert p["physical_jobs"] == [{"hypothesis_id": hid, "job": job["job"], "mechanism": job["mechanism"]}]   # the defect: forwarded raw (extra_forbidden)
    assert _trail_payload_errors(physical_jobs=p["physical_jobs"]) == []


@pytest.mark.parametrize("edit", [{"job": "x" * 513}, {"mechanism": "m" * 600}, {"hypothesis_id": "H1"}])
def test_b26_a_physical_job_trails_wire_refuses_is_refused_by_the_n_jobs_schema(edit):
    job = {"hypothesis_id": "hyp_" + "f" * 24, "job": "quick access", "mechanism": "glove-operable clip", **edit}
    payload = {"transitions": [], "physical_jobs": [job]}
    assert list(jsonschema.Draft202012Validator(ECOM.step("N_jobs")["output_schema"]).iter_errors(payload))   # the defect: N_jobs accepted it
    ok = {"transitions": [], "physical_jobs": [{"hypothesis_id": "hyp_" + "f" * 24, "job": "j" * 512, "mechanism": "glove-operable clip"}]}
    assert list(jsonschema.Draft202012Validator(ECOM.step("N_jobs")["output_schema"]).iter_errors(ok)) == []


# ─────────────────────────────────────────────────────────── B-23: one targeted retrieval per live hypothesis
def test_b23_every_live_hypothesis_gets_its_own_retrieval_call_on_a_single_corpus():
    needs = [f"hypothesis number {i} statement" for i in range(6)]                 # the portfolio law allows 3-6; R7 ran with 6
    for sid in ("F_retrieve", "F_graph"):
        cfg = ECOM.step(sid)["config"]
        assert cfg.get("query_from") == "hypotheses"
        assert int(cfg["max_calls"]) >= int(ECOM.budgets["max_hypotheses"]), sid       # the defect: max_calls 3 dropped needs 3, 4, 5
        plan = EB.plan_calls(needs, ["cinema"], max_calls=int(cfg["max_calls"]))
        assert [c["need_index"] for c in plan["calls"]] == list(range(6)) and plan["truncated"] == []
    two = EB.plan_calls(needs[:4], ["cinema", "second"], max_calls=6)               # a tight cap drops the later CORPUS first, never a need
    assert [c["corpus_id"] for c in two["calls"]][:4] == ["cinema"] * 4 and {t["corpus_id"] for t in two["truncated"]} == {"second"}


# ─────────────────────────────────────────────────────────── B-30: a transient transport failure is retried, bounded
class _Script:
    """httpx MockTransport handler answering from a queue; an Exception instance is raised as the transport failure."""
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), 0

    def __call__(self, request):
        self.calls += 1
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception):
            raise a
        return a


@pytest.fixture()
def orch(worker, monkeypatch):
    real, sleeps = httpx.Client, []
    monkeypatch.setattr(worker.time, "sleep", sleeps.append)

    def install(*answers):
        script = _Script(*answers)
        monkeypatch.setattr(worker.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(script), **kw))
        return script
    return worker, install, sleeps


def test_b30_an_orchestrator_restart_is_retried_with_a_bounded_backoff(orch):
    worker, install, sleeps = orch
    script = install(httpx.ConnectError("connection refused"), httpx.Response(502, text="bad gateway"), httpx.Response(200, json={"rows": []}))
    assert worker._orch_post("/retrieve", {"query": "q"}) == {"rows": []}          # the defect: the first refusal ended the step
    assert script.calls == 3 and sleeps == list(worker.TRANSIENT_BACKOFF_S[:2])


@pytest.mark.parametrize("answer, error", [(httpx.Response(500, text="boom"), "OrchUnavailable"), (httpx.Response(503, text="unavailable"), "OrchUnavailable"),
                                           (httpx.Response(422, text="bad"), "OrchRejected"), (httpx.ReadTimeout("read timed out"), "OrchUnavailable")])
def test_b30_a_server_error_a_rejection_or_a_full_timeout_keeps_its_meaning_at_once(orch, answer, error):
    worker, install, sleeps = orch
    script = install(answer)
    with pytest.raises(getattr(worker, error)):
        worker._orch_post("/retrieve", {"query": "q"})
    assert script.calls == 1 and sleeps == []


def test_b30_a_sustained_outage_is_still_unavailable_after_the_bounded_retries(orch):
    worker, install, sleeps = orch
    script = install(httpx.ConnectError("connection refused"))
    with pytest.raises(worker.OrchUnavailable, match="attempts"):
        worker._orch_post("/retrieve", {"query": "q"})
    assert script.calls == 1 + len(worker.TRANSIENT_BACKOFF_S) and sleeps == list(worker.TRANSIENT_BACKOFF_S)


def test_b30_the_trail_client_names_an_unreachable_daemon():
    client = TC.TrailMCPClient("http://trail.test/mcp", "token", transport=httpx.MockTransport(_Script(httpx.ConnectError("connection refused"))))
    with pytest.raises(TC.TrailUnreachable):
        client.operate("gaps.compile", {"request_id": "r"})


def _trail_step(worker, monkeypatch, *answers):
    spec = {"step_id": "H_gaps", "type": "EXTERNAL_OPERATION", "config": {"stage": "field_evidence"},
            "external": {"system": "trailsignal", "operation_kind": "gaps.compile", "availability": "working"}}

    class _M:
        def step(self, sid):
            return spec
    value = {"operation_id": "op-1", "operation_kind": "gaps.compile", "status_revision": 1, "registry_snapshot": None,
             "result": {"research_directive": {"search_intents": [{"intent_id": "i1"}]}}}
    ok = httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})
    script = _Script(*[ok if a == "ok" else a for a in answers])
    monkeypatch.setattr(worker, "_TRAIL", TC.TrailMCPClient("http://trail.test/mcp", "token", transport=httpx.MockTransport(script)))
    state = RunState(run_id=RUN, adapter_id="x", status="running", outputs={}, output_order=())
    return script, worker.exec_external({"run_id": RUN, "step_id": "H_gaps", "sequence": 9, "context": {}}, state, _M())


def test_b30_a_trail_daemon_blip_is_retried_on_the_same_idempotency_key_and_recorded(worker, monkeypatch):
    sleeps = []
    monkeypatch.setattr(worker.time, "sleep", sleeps.append)
    script, out = _trail_step(worker, monkeypatch, httpx.ConnectError("connection refused"), httpx.Response(502, text="bad gateway"), "ok")
    assert out["output"]["research_directive"]["search_intents"] and script.calls == 3          # the defect: STEP_EXECUTOR_ERROR, run failed
    assert len(out["output"]["transport_retries"]) == 2 and sleeps == list(worker.TRANSIENT_BACKOFF_S[:2])


def test_b30_a_trail_refusal_is_never_retried(worker, monkeypatch):
    monkeypatch.setattr(worker.time, "sleep", lambda s: pytest.fail("a refusal must not be retried"))
    refusal = httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "REQUEST_TOO_LARGE"}], "isError": True}})
    script, out = _trail_step(worker, monkeypatch, refusal)
    assert out["gap"]["code"] == "TRAIL_REFUSED" and script.calls == 1


# ═══════════════════════════════════════════════════════════ follow-ups from the other groups
import csv

from polymath_shared.adapter import harness_guide as HG


# ─────────────────────────────────────────────────────────── B-19: a public page declared as a first-party class
def _receipt_with_class(source_class: str, url_of=lambda i: f"https://blog{i}.example/post/{i}") -> dict:
    rec = copy.deepcopy(EXAMPLE_RECEIPT)
    rec["sources"] = [{**rec["sources"][0], "source_id": f"src_{i}", "url": url_of(i), "source_class": source_class} for i in range(2)]
    rec["observations"] = [{**rec["observations"][1], "observation_id": f"obs_{i}", "source_id": f"src_{i % 2}", "evidence_role_claimed": "friction"}
                           for i in range(5)]
    return rec


def test_b19_a_public_page_declared_as_a_no_web_class_is_refused_at_submit():
    rows = list(csv.DictReader((ROOT / HG.FILES[HG.SOURCES_URI]).open(encoding="utf-8")))
    patterns: dict[str, set] = {}
    for r in rows:
        if r["enabled"].strip().lower() == "true":
            patterns.setdefault(r["source_class"], set()).update(p.strip() for p in r["domains_or_patterns"].split(";"))
    no_web = {c for c, p in patterns.items() if p == {"-"}}
    assert no_web == {"first_party"}                                               # read from the PINNED table (a re-pin changes it here)
    assert all("{participant}" in r["independence_group"] for r in rows if r["source_class"] in no_web)   # one voice per observation
    errors = T.validate_receipt(RECEIPT_STEP, _receipt_with_class("first_party"))
    assert any("sources/0/source_class" in e and "first_party" in e and "public page" in e for e in errors), errors   # the defect: accepted
    assert T.validate_receipt(RECEIPT_STEP, _receipt_with_class("community_discussion")) == []
    assert T.validate_receipt(RECEIPT_STEP, _receipt_with_class("first_party", lambda i: f"urn:interview:participant-{i}")) == []   # a real interview


# ─────────────────────────────────────────────────────────── B-11 / B-13: what the derived view carries about field evidence and gaps
from polymath_shared.adapter import semantic_view as SV

H1, H2 = "hyp_" + "1" * 24, "hyp_" + "2" * 24


def _view_state(hid: str, gaps: list[dict]) -> dict:
    return {"hypothesis_id": hid, "revision": 2, "status": "revised", "statement": "runners lose small items mid stride", "parent_hypothesis_ids": [],
            "knowledge_support": [], "field_evidence_ids": [], "knowledge_gaps": gaps, "assumptions": [], "falsifiers": [], "contradictions": []}


def test_b13_the_view_shows_every_open_gap_before_its_cut_and_counts_them():
    closed = [{"gap_id": f"gap_c{i}", "question": f"closed question {i}", "evidence_role": "behavior", "status": "closed"} for i in range(12)]
    opened = [{"gap_id": f"gap_o{i}", "question": f"open question {i}", "evidence_role": "behavior", "status": "open"} for i in range(2)]
    view = SV.for_hypothesis(_view_state(H1, closed + opened), {})
    assert [g["question"] for g in view["knowledge"]["knowledge_gaps"]] == ["open question 0", "open question 1"]   # the defect: 12 closed, 0 open
    assert view["knowledge"]["open_knowledge_gap_count"] == 2
    many = [{"gap_id": f"gap_o{i}", "question": f"open question {i}", "evidence_role": "behavior"} for i in range(15)]   # no status = open
    view = SV.for_hypothesis(_view_state(H1, many), {})
    assert len(view["knowledge"]["knowledge_gaps"]) == SV.MAX_ITEMS and view["knowledge"]["open_knowledge_gap_count"] == 15   # "N more" is sayable


def test_b11_field_evidence_carries_trails_relation_to_each_hypothesis():
    receipt = {"action_id": "hact_1", "observations": [{"observation_id": "obs_1", "source_id": "s1", "claim": "my keys bounced out again"}],
               "sources": [{"source_id": "s1", "url": "https://forum.example/t/1", "source_class": "community_discussion"}]}
    relations = [{"hypothesis_id": H1, "relation": "CONTRADICTS"}, {"hypothesis_id": H2, "relation": "SUPPORTS"}]
    admission = {"evidence_admission": {"action_id": "hact_1", "admitted": [
        {"admitted_evidence_id": "fev_1", "observation_id": "obs_1", "source_id": "s1", "evidence_role": "friction", "polarity": "supporting",
         "hypothesis_ids": [H1, H2], "hypothesis_relations": relations}]}}
    steps = [{"step_id": "I_research", "sequence": 23, "output": receipt}, {"step_id": "J_admit", "sequence": 24, "output": admission}]
    assert EB._index_rows(steps)["fev_1"]["hypothesis_relations"] == relations                   # the defect: dropped, only the global polarity kept
    views = SV.build({H1: _view_state(H1, []), H2: _view_state(H2, [])}, {}, step_outputs=steps)["hypotheses"]
    assert [v["field_evidence"][0]["hypothesis_relations"] for v in views] == [relations, relations]
    assert views[0]["field_evidence"][0]["polarity"] == "supporting"                              # the global polarity is still what Trail said


# ─────────────────────────────────────────────────────────── B-09 / B-12: what the ecommerce manifest hands the bridge law and the result
def test_b09_the_bridge_law_is_given_the_live_ledger(worker, monkeypatch):
    cfg = ECOM.step("C_bridge_law")["config"]
    assert cfg["inputs"].get("live_hypotheses") == "context.hypotheses"                     # the defect: the law never saw the ledger
    sent = {}

    def run(argv, input, **kw):                                                             # the out-of-process binding, captured
        sent.update(json.loads(input))
        return type("P", (), {"returncode": 0, "stdout": json.dumps({"ok": True, "output": {"admissible": True}}), "stderr": ""})()
    monkeypatch.setattr(worker.subprocess, "run", run)
    live = [{"hypothesis_id": H1, "revision": 0, "status": "proposed", "statement": "s1"}, {"hypothesis_id": H2, "revision": 1, "status": "revised", "statement": "s2"}]
    state = RunState(run_id=RUN, adapter_id=ECOM.adapter_id, status="running", outputs={"C_bridge": {"bridges": []}}, output_order=("C_bridge",))
    worker.exec_domain({"run_id": RUN, "step_id": "C_bridge_law", "sequence": 30, "context": {"hypotheses": live}}, state, ECOM)
    assert sent["inputs"]["live_hypotheses"] == live


def test_b12_the_result_keeps_every_qualify_stage():
    include = ECOM.step(ECOM.terminal_step_id)["config"]["include"]
    assert {"collect_all": "qualifications", "as": "qualifications_by_step"} in include      # the defect: only the newest stage's list survived
    assert "qualifications" in include                                                         # the plain key stays for existing readers
