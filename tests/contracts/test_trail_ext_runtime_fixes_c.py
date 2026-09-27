"""TRAIL-EXT-BUGHUNT-V1, group `runtime`, batch C — the pure half of the fixes (no store, no network, no daemon).

Each test names the finding it reproduces (docs/wiki/experiments/trail-ext-bughunt-2026-09-26). Behaviour through the runtime is in
tests/determinism/test_adapter_trail_ext_runtime_fixes_c.py. The worker and the embedded TrailSignal composition module are loaded BY
FILE PATH from this checkout; where TrailSignal decides, its embedded core (the pinned copy under `governance/trail/`) is asked.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import harness_guide as HG
from polymath_shared.adapter import hypotheses as H
from polymath_shared.adapter import trail_client as TC
from polymath_shared.adapter import transitions as T
from polymath_shared.adapter.manifest import ADAPTER_DIR, load_manifest
from polymath_shared.adapter.transitions import RunState, SubmissionRejected

RUN = "adr_" + "b" * 32
NOW = "2026-09-26T00:00:00Z"
ECOM = load_manifest(ADAPTER_DIR / "ecommerce.product_research.json")
WORKER = ROOT / "workers" / "workers" / "adapter_step_worker.py"
EMBEDDED = ROOT / "governance" / "trail" / "embedded.py"
HYP = "hyp_" + "1" * 24


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def worker():
    mod = _load(WORKER, "adapter_step_worker_bughunt_c")
    assert pathlib.Path(mod.__file__).resolve() == WORKER.resolve()
    return mod


@pytest.fixture()
def embedded():
    pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need packageurl")
    return _load(EMBEDDED, "trail_embedded_bughunt_c")


def test_the_code_under_test_is_this_checkout():
    for mod in (HG, H, TC, T):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── B-49: the SPLIT cap counts the hypotheses that are alive
def _ledger(n_live: int, n_killed: int) -> dict:
    refs = [{"kind": "chunk", "id": "chunk_k1"}]
    states, _ = H.generate(RUN, {"run_id": RUN, "step_id": "C_hypotheses", "sequence": 11, "context": {"evidence_refs": refs}},
                           [{"statement": f"hypothesis number {i} statement", "supporting_evidence_ids": ["chunk_k1"]} for i in range(n_live + n_killed)],
                           registry_snapshot_id=None, recorded_at=NOW)
    current = {s["hypothesis_id"]: s for s in states}
    for s in states[n_live:]:
        current[s["hypothesis_id"]] = {**s, "status": "killed", "revision": 1}
    return current


def _split(current: dict, parent: str):
    allowed = {"chunk_k1": "chunk", **{h: "hypothesis" for h in current}}
    return H.apply(RUN, {"run_id": RUN, "step_id": "K_revise", "sequence": 60}, current,
                   [{"hypothesis_id": parent, "kind": "SPLIT", "cause_refs": [{"kind": "chunk", "id": "chunk_k1"}],
                     "children": [{"statement": "a narrower child statement", "supporting_evidence_ids": ["chunk_k1"]}]}],
                   actor="theta", allowed_causes=allowed, recorded_at=NOW, max_hypotheses=8)


def test_b49_the_split_cap_counts_live_hypotheses_as_generate_does():
    four_live = _ledger(4, 4)
    _, trs = _split(four_live, next(iter(four_live)))                               # the defect: refused, 4 killed ones counted
    assert [t["kind"] for t in trs] == ["GENERATE", "SPLIT"]
    eight_live = _ledger(8, 0)
    with pytest.raises(H.HypothesisRejected, match="max_hypotheses 8"):
        _split(eight_live, next(iter(eight_live)))


# ─────────────────────────────────────────────────────────── B-50: a typed `*_refs` field resolves against its own records only
def _interpret(trail_score_refs: list[str], record_refs: list[str] | None = None):
    outputs = {"N_concepts": {"product_concepts": [{"id": "pc_agent_invented", "mechanism_id": "m1"}]},
               "R_qualify": {"operation_kind": "opportunity.qualify", "trail_operation_id": "op-7",
                             "qualifications": [{"record_id": "qual-market-1", "hypothesis_ids": [HYP]}]},
               "V_score": {"operation_kind": "opportunity.score", "trail_operation_id": "op-9",
                           "trail_scores": [{"record_id": "score-1", "hypothesis_id": HYP}],
                           "score_refusals": [{"record_id": "score-2", "hypothesis_id": HYP}],
                           "trail_score_record_ids": ["score-1"], "trail_score_refusal_record_ids": ["score-2"]}}
    state = RunState(run_id=RUN, adapter_id=ECOM.adapter_id, status="awaiting_agent", current_step_id="W_interpret", outputs=outputs,
                     output_order=tuple(outputs))
    step = {"run_id": RUN, "step_id": "W_interpret", "step_type": "AGENT_REASON", "sequence": 90,
            "context": {"evidence_refs": [], "hypotheses": [{"hypothesis_id": HYP}]}, "output_schema": ECOM.step("W_interpret")["output_schema"]}
    opportunity = {"product_concept": {k: "x" for k in ("title", "mechanism_explanation", "population", "activity", "context", "problem")},
                   "evidence_chain": [{"hypothesis_id": HYP, "claim": "c", "record_refs": list(record_refs or [])}], "remaining_uncertainty": [],
                   "cheapest_falsification_experiment": "concept interviews", "trail_score_refs": trail_score_refs}
    return T.accept_submission(ECOM, state, step, {"run_id": RUN, "step_id": "W_interpret", "payload": {"product_opportunity": opportunity},
                                                  "submitted_by": {"agent_identity": "test/agent"}})


def test_b50_trail_score_refs_resolve_only_against_the_score_and_refusal_records():
    assert _interpret(["score-1", "score-2"], ["qual-market-1", "score-1"]).status == "running"
    for not_a_score in ("pc_agent_invented", HYP, "op-9", "N_concepts", "qual-market-1"):
        with pytest.raises(SubmissionRejected) as exc:                                      # the defect: every one of these resolved
            _interpret([not_a_score])
        assert "trail_score_refs" in str(exc.value) and not_a_score in str(exc.value), not_a_score
    with pytest.raises(SubmissionRejected, match="score-invented"):
        _interpret(["score-1"], ["score-invented"])                                         # an untyped *_refs field keeps the run-wide rule


# ─────────────────────────────────────────────────────────── B-66: an embedded TrailSignal without its audit store
def _registry_step(worker, monkeypatch):
    spec = {"step_id": "D_project", "type": "EXTERNAL_OPERATION", "config": {},
            "external": {"system": "trailsignal", "operation_kind": "registry.project", "availability": "working"}}

    class _M:
        def step(self, sid):
            return spec
    state = RunState(run_id=RUN, adapter_id="x", status="running", outputs={}, output_order=())
    step = {"run_id": RUN, "step_id": "D_project", "sequence": 9,
            "context": {"hypotheses": [{"hypothesis_id": HYP, "revision": 0, "status": "proposed", "statement": "runners lose small items mid stride"}]}}
    return lambda: worker.exec_external(step, state, _M())


def test_b66_embedded_mode_without_a_store_is_a_typed_gap_not_a_silent_memory_store(worker, embedded, monkeypatch):
    monkeypatch.setenv("POLYMATH_TRAIL_MODE", "embedded")
    monkeypatch.delenv("POLYMATH_TRAIL_STORE", raising=False)
    run = _registry_step(worker, monkeypatch)
    out = run()
    assert out.get("gap", {}).get("code") == "TRAIL_STORE_MISSING", out                    # the defect: an in-memory store, silently
    assert "POLYMATH_TRAIL_STORE" in out["gap"]["message"] and worker._TRAIL is None
    monkeypatch.setenv("POLYMATH_TRAIL_STORE", ":memory:")                                  # asked for explicitly (tests): allowed
    assert run()["output"]["registry_snapshot"]["snapshot_id"].startswith("trs-")


# ─────────────────────────────────────────────────────────── B-67: the daemon token is minted again before it expires
TEST_SECRET = "unit-test-only-hs256-secret-" + "0" * 16          # a throwaway signing secret for this test, never a real credential


def _claims(token: str) -> dict:
    body = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def test_b67_a_daemon_client_is_rebuilt_before_its_minted_token_expires(worker, monkeypatch):
    clock = [1_800_000_000.0]
    monkeypatch.setattr(TC.time, "time", lambda: clock[0])
    monkeypatch.delenv("POLYMATH_TRAIL_MODE", raising=False)
    monkeypatch.delenv("TRAIL_SIGNAL_MCP_TOKEN_POLYMATH", raising=False)
    monkeypatch.setenv("TRAIL_SIGNAL_MCP_JWT_SECRET", TEST_SECRET)
    first = worker.trail()
    assert worker.trail() is first and _claims(first.token)["exp"] == clock[0] + 3600
    clock[0] += 3600 - 600
    assert worker.trail() is first                                                       # still well inside its hour
    clock[0] += 2 * 3600                                                                 # two hours after it was minted
    later = worker.trail()
    assert later is not first and _claims(later.token)["exp"] > clock[0] + 3000           # the defect: the same client, its token expired


def test_b67_a_pre_minted_token_keeps_todays_behaviour(worker, monkeypatch):
    clock = [1_800_000_000.0]
    monkeypatch.setattr(TC.time, "time", lambda: clock[0])
    monkeypatch.delenv("POLYMATH_TRAIL_MODE", raising=False)
    monkeypatch.setenv("TRAIL_SIGNAL_MCP_TOKEN_POLYMATH", "pre-minted-token")
    first = worker.trail()
    clock[0] += 5 * 3600
    assert worker.trail() is first and first.token == "pre-minted-token"


# ─────────────────────────────────────────────────────────── B-68: an internal fault of the embedded core is not a Trail refusal
HYPS = [{"hypothesis_id": HYP, "revision": 0, "status": "proposed", "statement": "runners lose small items mid stride because pockets bounce"}]


def _flaky_client(embedded, failures: int):
    class Flaky(embedded.SqliteResearchStore):
        left = failures

        async def commit(self, operation, result):
            if Flaky.left:
                Flaky.left -= 1
                raise sqlite3.OperationalError("database is locked")                     # what a second writer on the store file raises
            return await super().commit(operation, result)
    return TC.TrailMCPClient("http://trail.embedded/mcp", "in-process", transport=embedded.transport(embedded.build_service(store=Flaky(None))))


def test_b68_a_store_fault_reaches_the_client_as_an_internal_error_and_a_refusal_stays_a_refusal(embedded):
    client = _flaky_client(embedded, 1)
    req = TC.bounded_request("registry.project", {"hypotheses": HYPS}, key=TC.identifier(RUN, "D_project", "9"), run_ref=RUN)
    with pytest.raises(TC.TrailInternalError, match="database is locked") as exc:            # the defect: TrailToolError (a refusal)
        client.operate("registry.project", req)
    assert not isinstance(exc.value, TC.TrailToolError)
    assert client.operate("registry.project", req)["operation_kind"] == "registry.project"    # the same request, once the store is free
    wrong_snapshot = TC.bounded_request("gaps.compile", {"hypotheses": HYPS, "stage": "field_evidence"}, key=TC.identifier(RUN, "H_gaps", "10"),
                                        run_ref=RUN, registry_snapshot_id="trs-not-the-snapshot")
    with pytest.raises(TC.TrailToolError):
        client.operate("gaps.compile", wrong_snapshot)


def test_b68_exec_external_retries_an_internal_fault_and_never_records_it_as_trail_refused(worker, embedded, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(worker.time, "sleep", sleeps.append)
    monkeypatch.setattr(worker, "_TRAIL", _flaky_client(embedded, 1))
    out = _registry_step(worker, monkeypatch)()
    assert "gap" not in out, out.get("gap")                                                   # the defect: TRAIL_REFUSED, run ended
    assert out["output"]["registry_snapshot"]["snapshot_id"].startswith("trs-") and len(out["output"]["transport_retries"]) == 1
    assert sleeps == [worker.TRANSIENT_BACKOFF_S[0]]
    monkeypatch.setattr(worker, "_TRAIL", _flaky_client(embedded, 99))
    with pytest.raises(RuntimeError, match="trail transport"):                               # a lasting fault: a typed step failure, not a refusal
        _registry_step(worker, monkeypatch)()


# ─────────────────────────────────────────────────────────── B-69: a domain operation never writes what the runtime treats as Trail's
def _domain(worker, monkeypatch, tmp_path, output: dict):
    d = tmp_path / "adapters" / "fakedomain"
    d.mkdir(parents=True)
    (d / "out.json").write_text(json.dumps({"ok": True, "output": output}))
    (d / "binding.py").write_text("import sys\nsys.stdin.read()\nprint(open('out.json').read())\n")
    monkeypatch.setattr(worker, "_DOMAINS_DIR", tmp_path / "adapters")
    spec = {"step_id": "S_dom", "type": "DOMAIN_OPERATION", "config": {"domain": "fakedomain", "operation": "probe.run"}}

    class _M:
        def step(self, sid):
            return spec
    state = RunState(run_id=RUN, adapter_id="x", status="running", outputs={}, output_order=())
    return worker.exec_domain({"run_id": RUN, "step_id": "S_dom", "sequence": 5, "context": {}}, state, _M())


@pytest.mark.parametrize("key", ["hypothesis_verdicts", "evidence_admission", "hypothesis_transition_ids", "_harness_action_id", "_evidence_refs",
                                 "trail_scores", "trail_score_record_ids", "score_refusals", "qualifications", "registry_snapshot", "operation_kind"])
def test_b69_a_domain_output_carrying_a_key_the_runtime_reads_as_trails_or_its_own_is_refused(worker, monkeypatch, tmp_path, key):
    with pytest.raises(RuntimeError, match=key):                                             # the defect: passed through verbatim
        _domain(worker, monkeypatch, tmp_path, {"note": "ok", key: [{"hypothesis_id": HYP, "kind": "KILL"}]})


def test_b69_a_domain_output_of_its_own_keys_and_an_enriched_directive_passes(worker, monkeypatch, tmp_path):
    out = _domain(worker, monkeypatch, tmp_path, {"research_directive": {"search_intents": [{"intent_id": "i1"}]}, "leads": [], "note": "ok"})
    assert set(out["output"]) == {"research_directive", "leads", "note", "_domain"}


# ─────────────────────────────────────────────────────────── the guide asks for what submit accepts (B-03's refusal)
def test_the_guide_asks_for_utc_timestamps_ending_in_z_and_whole_counts():
    research = HG.GUIDE[HG.GUIDE.index("## 4."):HG.GUIDE.index("## 5.")]
    assert "ISO-8601" not in research and "UTC" in research and "ending in `Z`" in research, research
    assert "whole number" in research
