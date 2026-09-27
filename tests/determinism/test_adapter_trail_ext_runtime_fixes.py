"""TRAIL-EXT-BUGHUNT-V1, group `runtime` — adapter behaviour through the REAL runtime (`service.start / advance / next_step / submit /
result`, the worker's executors and its claim loop, the real out-of-process ecommerce binding) over the in-memory store, with the stub
TrailSignal of the ecommerce e2e test or the EMBEDDED pinned TrailSignal core. No database, no network, no daemon.

Each test names the finding it reproduces (docs/wiki/experiments/trail-ext-bughunt-2026-09-26). The pure half of the fixes is in
tests/contracts/test_trail_ext_runtime_fixes.py.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import pathlib
import sys

import httpx
import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", pathlib.Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import test_adapter_ecommerce_product_research_e2e as SCRIPT
import workers.adapter_step_worker as W
from _adapter_memory_store import MemoryStore
from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import service
from polymath_shared.adapter import trail_client as TC
from polymath_shared.adapter.transitions import SubmissionRejected


def test_the_code_under_test_is_this_checkout():
    for mod in (C, service, TC, W, SCRIPT):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── rigs
def _stub(monkeypatch, trail=None):
    store, trail = MemoryStore(), trail or SCRIPT.StubTrail()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(trail.handle)))
    service.reset_registry()
    SCRIPT.NEEDS.clear()
    return store, trail


@pytest.fixture
def stub(monkeypatch):
    yield _stub(monkeypatch)
    service.reset_registry()


@pytest.fixture
def embedded(monkeypatch, tmp_path):
    pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need packageurl")
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setenv("POLYMATH_TRAIL_MODE", "embedded")
    monkeypatch.setenv("POLYMATH_TRAIL_STORE", str(tmp_path / "trail_audit.sqlite3"))
    monkeypatch.setattr(W, "_TRAIL", None)
    service.reset_registry()
    SCRIPT.NEEDS.clear()
    yield store
    monkeypatch.setattr(W, "_TRAIL", None)
    service.reset_registry()


def _drive(agent, harness=None, *, max_iter=300, knowledge=None):
    """SCRIPT._run, except that an exception escaping `service.advance` is RETURNED with the step it escaped at (what the worker's loop
    would have to survive), and a rejected answer or receipt is handed back once (the harness sees attempt 1), as a real one would retry."""
    harness = harness or (lambda step, rid, attempt: SCRIPT._harness(step, rid))
    knowledge = knowledge or SCRIPT._knowledge
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": knowledge, "POLYMATH_COMPILE_PLAN": knowledge, "POLYMATH_GRAPH_EXPAND": knowledge}
    rid = service.start(None, adapter_id=SCRIPT.ADAPTER_ID, input_payload={"seed": SCRIPT.SEED, "corpus_ids": ["probe"]},
                        request_options={"corpus_ids": ["probe"]})["run_id"]
    actions: dict[str, list] = {}
    rejected: dict[str, list] = {}
    st = None
    for _ in range(max_iter):
        try:
            st = service.advance(None, rid, execs, max_steps=1)
        except Exception as exc:  # noqa: BLE001 — the finding is precisely that something escapes
            return rid, st, actions, rejected, exc, (service.store.current_step(None, rid) or {}).get("step_id")
        if st.terminal:
            break
        if st.status in ("awaiting_agent", "awaiting_harness"):
            nxt = service.next_step(None, rid)
            step = nxt["step"]
            if st.status == "awaiting_agent":
                for attempt in (0, 1):                               # a rejected answer is corrected once, as a real agent would
                    try:
                        service.submit(None, rid, {"step_id": step["step_id"], "payload": agent.answer(nxt), "submitted_by": {"agent_identity": "test-agent"}})
                        break
                    except SubmissionRejected as exc:
                        rejected.setdefault(step["step_id"], []).append(exc.errors)
                continue
            actions.setdefault(step["step_id"], []).append(step["harness_action"])
            for attempt in (0, 1):
                try:
                    service.submit(None, rid, {"step_id": step["step_id"], "payload": harness(step, rid, attempt), "submitted_by": {"agent_identity": "test-harness"},
                                               "kind": "receipt"})
                    break
                except SubmissionRejected as exc:
                    rejected.setdefault(step["step_id"], []).append(exc.errors)
    return rid, st, actions, rejected, None, None


def _rows(store, rid, step_id):
    return [r for r in store.list_steps(None, rid) if r["step_id"] == step_id]


# ─────────────────────────────────────────────────────────── B-04 (+ B-02): a refusal longer than the receipt's error cap
def _chunk(i: int) -> str:                                    # the live chunk-id format: "chunk_" + 64 hex (70 chars)
    return "chunk_" + hashlib.sha256(f"hallucinated-{i}".encode()).hexdigest()


class StubbornLineageAgent(SCRIPT.Agent):
    """Never repairs its lineage: six latent structures, each citing a chunk id that is not a corpus row of this run."""
    def answer(self, nxt):
        out = super().answer(nxt)
        if nxt["step"]["step_id"] == "C_primitives":
            prim = out["primitives"]
            prim["row_relevance"] = {"chunk_k1": "SEMANTIC_MATCH"}
            prim["latent_structures"] = [dict(prim["latent_structures"][0], id=f"ls{i}", evidence_refs=[_chunk(i)]) for i in range(6)]
        return out


def test_b04_a_domain_refusal_over_1000_chars_ends_the_run_as_its_typed_gap(stub):
    store, _ = stub
    rid, st, _a, _r, leaked, at = _drive(StubbornLineageAgent())
    assert leaked is None, (at, repr(leaked))                                              # the defect: ContractViolation(adapter_step_receipt) escaped here
    assert st.status == "terminal_gap" and st.gap["code"] == "LINEAGE_LAW_UNSATISFIED" and st.gap["step_id"] == "Z_refuse_lineage"
    assert len(st.gap["message"]) > 1000                                                    # the domain's whole reason stays on the run …
    receipt = _rows(store, rid, "Z_refuse_lineage")[-1]["receipt"]
    err = receipt["validation"]["errors"][0]
    assert C.validate("adapter_step_receipt", receipt) == []
    assert len(err) <= 1000 and "chars elided" in err and err.startswith(st.gap["message"][:200]) and err.endswith(st.gap["message"][-100:])   # … the receipt keeps a bounded copy
    assert service.status(None, rid)["gap"]["code"] == "LINEAGE_LAW_UNSATISFIED"          # the status view still validates
    assert service.result(None, rid)["gap"]["code"] == "LINEAGE_LAW_UNSATISFIED"


# ─────────────────────────────────────────────────────────── B-02: every other route to a record that outgrows its contract
def _fixture_manifest(d: pathlib.Path, adapter_id: str, steps: list[dict], entry: str, *, max_agent_reason: int = 2) -> None:
    raw = {"adapter_id": adapter_id, "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0",
           "input_schema_version": "1.0.0", "output_schema_version": "1.0.0", "description": "bug-hunt fixture",
           "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
           "budgets": {"max_steps": 12, "max_agent_reason": max_agent_reason, "max_branch_loops": 0, "max_external_operations": 0},
           "entry_step_id": entry, "terminal_step_id": "X_compile",
           "steps": steps + [{"step_id": "X_compile", "type": "COMPILE_RESULT", "title": "compile", "next": None, "config": {"include": ["lineage"]}}]}
    (d / f"{adapter_id}.json").write_text(json.dumps(raw))


@pytest.fixture
def fixtures_dir(tmp_path, monkeypatch):
    d = tmp_path / "adapters"
    d.mkdir()
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    service.reset_registry()
    yield d, store
    service.reset_registry()


def test_b02_a_1500_char_executor_error_is_recorded_as_step_executor_error(fixtures_dir):
    d, store = fixtures_dir
    _fixture_manifest(d, "fixture.boom", [{"step_id": "check", "type": "DOMAIN_OPERATION", "title": "check", "next": "X_compile",
                                           "config": {"domain": "ecommerce", "operation": "law.refuse"}}], "check")
    rid = service.start(None, adapter_id="fixture.boom", input_payload={"q": "x"}, directory=d)["run_id"]

    def boom(step, state, m):
        raise RuntimeError("x" * 1500)
    st = service.advance(None, rid, {"DOMAIN_OPERATION": boom}, max_steps=1, directory=d)
    assert st.status == "failed" and st.failure["code"] == "STEP_EXECUTOR_ERROR" and st.failure["message"] == "RuntimeError: " + "x" * 1500
    row = store.current_step(None, rid)
    assert row["status"] == "failed" and C.validate("adapter_step_receipt", row["receipt"]) == [] and len(row["receipt"]["validation"]["errors"][0]) <= 1000


def test_b02_a_long_rejection_reason_is_a_submission_rejection_not_a_receipt_crash(fixtures_dir):
    d, store = fixtures_dir
    _fixture_manifest(d, "fixture.reject", [{"step_id": "brief", "type": "AGENT_REASON", "title": "brief", "next": "X_compile", "objective": "write",
                                             "output_schema": {"type": "object", "properties": {"statement": {"type": "string", "maxLength": 2000}}}}], "brief")
    rid = service.start(None, adapter_id="fixture.reject", input_payload={"q": "x"}, directory=d)["run_id"]
    service.advance(None, rid, {}, max_steps=1, directory=d)
    sub = {"run_id": rid, "step_id": "brief", "payload": {"statement": "y" * 2001}, "submitted_by": {"agent_identity": "t"}}
    with pytest.raises(SubmissionRejected) as exc:                                           # the agent's own error, not a receipt ContractViolation
        service.submit(None, rid, sub, directory=d)
    assert any("is too long" in e for e in exc.value.errors)
    row = store.current_step(None, rid)
    assert row["status"] == "issued" and row["receipt"]["status"] == "rejected" and C.validate("adapter_step_receipt", row["receipt"]) == []
    assert service.status(None, rid, d)["status"] == "awaiting_agent"                           # the agent can still correct it


class LongGapTrail(SCRIPT.StubTrail):
    """STUBBED INPUT (external review M1-04): TrailSignal echoes a gap question longer than HarnessActionV1 carries (its wire allows 4096)."""
    def handle(self, req):
        resp = super().handle(req)
        body = json.loads(req.content)
        payload = (body["params"]["arguments"].get("request") or {}).get("payload") or {}
        if body["params"]["name"] == "gaps.compile" and payload.get("stage") != "supply":
            env = resp.json()
            value = env["result"]["structuredContent"]
            value["result"]["research_directive"]["evidence_gaps"][0]["question"] = "q" * 2001
            env["result"]["content"][0]["text"] = json.dumps(value)
            return httpx.Response(200, json=env)
        return resp


def test_b02_a_step_that_cannot_be_issued_under_its_contract_ends_the_run_typed_not_leaked(monkeypatch):
    store, _ = _stub(monkeypatch, LongGapTrail())
    rid, st, _a, _r, leaked, at = _drive(SCRIPT.Agent())
    service.reset_registry()
    assert leaked is None, (at, repr(leaked)[:300])                                        # the defect: ContractViolation(harness_action) left advance
    assert st.status == "failed" and st.failure["code"] == "STEP_CONTRACT_VIOLATION" and st.failure["step_id"] == "I_research"
    msg = st.failure["message"]
    assert "harness_action" in msg and "evidence_gaps/0/question" in msg and "is too long" in msg     # which contract, which field, which rule …
    assert len(msg) <= 2000 and "q" * 600 not in msg                                                   # … without echoing the oversized value
    assert service.status(None, rid)["status"] == "failed" and "I_research" not in [r["step_id"] for r in store.list_steps(None, rid)]


# ─────────────────────────────────────────────────────────── B-03: a timestamp TrailSignal refuses, refused at submit (embedded Trail)
def test_b03_a_non_utc_receipt_is_handed_back_at_submit_and_the_corrected_one_completes_the_run(embedded):
    store = embedded

    def harness(step, rid, attempt):
        rec = SCRIPT._harness(step, rid)
        if step["step_id"] == "I_research" and attempt == 0 and not _rows(store, rid, "J_admit"):
            rec.update(started_at="2026-09-13T14:11:00-06:00", completed_at="2026-09-13T14:26:30-06:00")   # valid RFC 3339, not UTC
        return rec
    rid, st, _a, rejected, leaked, at = _drive(SCRIPT.Agent(), harness)
    assert leaked is None, (at, repr(leaked))
    assert rejected.get("I_research") and any("started_at" in e for e in rejected["I_research"][0])   # the defect: accepted, then TRAIL_REFUSED at J_admit
    assert st.status == "completed", (st.status, st.gap, st.failure)
    first = _rows(store, rid, "I_research")[0]
    assert first["status"] == "accepted" and first["output"]["started_at"] == "2026-09-13T20:11:00Z"


# ─────────────────────────────────────────────────────────── B-05: a budgeted receipt over TrailSignal's 64 KB request ceiling (embedded Trail)
def _reality_receipt(step, rid, n_obs=80, n_src=20):
    """R7-calibrated observations (claim ~77, excerpt ~189, context ~279 chars): 80 of them are the manifest's own budget and ~824 B each."""
    action = step["harness_action"]
    concept = next((i["intent_id"].split(":")[1] for i in action["search_intents"] if ":pc_" in i["intent_id"]), "pc_1")
    hyp = action["hypothesis_ids"][0]
    rec = copy.deepcopy(SCRIPT.RECEIPT_TPL)
    rec.update({"action_id": action["action_id"], "run_id": rid, "harness_id": "test-harness", "tool_trace": [], "limitations": []})
    rec["sources"] = [{"source_id": f"src_{i}", "url": f"https://www.retailer-{i}.example/p/item-{i:04d}-running-belt-key-holder",
                       "source_class": "marketplace_listing", "retrieved_at": "2026-09-26T05:40:00Z", "published_at_if_known": None} for i in range(n_src)]
    tail = " · listing reviewed on the retailer page, price as shown on the day, variant sizes compared against the concept's form factor and use"
    rec["observations"] = [{
        "observation_id": f"obs_{i}", "source_id": f"src_{i % n_src}",
        "claim": f"listing {i}: a zip belt holds keys but reviewers say it rides up when running ({i})"[:77],
        "paraphrase_or_excerpt": ("several reviewers describe the belt bouncing and the zip being hard to open with gloves; "
                                  "one says keys still jingle and the pocket is too small for a phone in a case ") + f"#{i}",
        "metric_if_present": None,
        "context": (f"concept: {concept} · relation: competitor · product: running belt model {i} · price as listed: US$19.99 · retailer: shop {i % n_src}" + tail)[:279],
        "evidence_role_claimed": "competition" if i % 2 else "price",
        "hypothesis_ids": [hyp], "hypothesis_relations": [{"hypothesis_id": hyp, "relation": "NEUTRAL"}]} for i in range(n_obs)]
    return rec


def test_b05_a_budgeted_receipt_over_the_ceiling_is_trimmed_counted_and_admitted_and_the_run_goes_on(embedded):
    store = embedded

    def harness(step, rid, attempt):
        return _reality_receipt(step, rid) if step["harness_action"]["action_kind"] == "PRODUCT_REALITY_CHECK" else SCRIPT._harness(step, rid)
    rid, st, actions, _r, leaked, at = _drive(SCRIPT.Agent(), harness)
    assert leaked is None, (at, repr(leaked))
    assert actions["P_reality"][0]["budget"]["max_observations"] == 80                       # the manifest's own budget …
    assert _rows(store, rid, "P_reality")[0]["status"] == "accepted"
    q = _rows(store, rid, "Q_admit")[0]
    assert q["status"] == "executed", (st.status, st.failure, st.gap)                        # … the defect: `failed` STEP_EXECUTOR_ERROR (65536) here
    trim = q["output"]["receipt_trimmed"]
    assert trim["observations_submitted"] == 80 and 0 < trim["observations_sent"] < 80 and len(trim["dropped_observation_ids"]) == 80 - trim["observations_sent"]
    adm = q["output"]["evidence_admission"]
    judged = {a["observation_id"] for a in adm["admitted"]} | {r["observation_id"] for r in adm["rejected"]}
    assert judged and not judged & set(trim["dropped_observation_ids"])                        # TrailSignal judged exactly what was sent
    assert st.status == "completed", (st.status, st.gap, st.failure)


# ─────────────────────────────────────────────────────────── B-06: the worker's claim loop survives what escapes a step unit
class TxStore(MemoryStore):
    """MemoryStore + the lease functions with store.py's SQL semantics (claim = oldest updated_at among free RUNNING runs; updated_at moves
    only in save_state) + a tx() that restores a snapshot on exception, like db.tx's rollback."""
    def __init__(self):
        super().__init__()
        self.clock = 0

    def save_state(self, conn, state):
        super().save_state(conn, state)
        self.clock += 1
        self.runs[state.run_id]["meta"]["updated_at"] = self.clock

    def claim_run(self, conn, owner, lease_s):
        free = sorted((str(r["meta"]["updated_at"]).zfill(8), rid) for rid, r in self.runs.items()
                      if r["state"]["status"] == "running" and r["meta"].get("lease_owner") is None)
        if not free:
            return None
        self.runs[free[0][1]]["meta"]["lease_owner"] = owner
        return free[0][1]

    def renew_lease(self, conn, run_id, owner, lease_s):
        return self.runs[run_id]["meta"].get("lease_owner") == owner

    def release_lease(self, conn, run_id, owner):
        if self.runs[run_id]["meta"].get("lease_owner") == owner:
            self.runs[run_id]["meta"]["lease_owner"] = None

    @contextlib.contextmanager
    def tx(self):
        snap = copy.deepcopy({k: getattr(self, k) for k in ("runs", "steps", "results", "hypotheses", "transitions", "actions", "admitted", "clock")})
        try:
            yield None
        except BaseException:
            for k, v in snap.items():
                setattr(self, k, v)
            raise


@pytest.fixture
def worker_rig(tmp_path, monkeypatch):
    d = tmp_path / "adapters"
    d.mkdir()
    store = TxStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "tx", store.tx)
    service.reset_registry()
    monkeypatch.setattr(service, "manifest_for", lambda adapter_id, directory=None: service.registry(d)[adapter_id])
    _fixture_manifest(d, "fixture.healthy", [{"step_id": "brief", "type": "AGENT_REASON", "title": "brief", "next": "X_compile", "objective": "o",
                                              "output_schema": {"type": "object"}}], "brief")
    yield d, store
    service.reset_registry()


def _running(store, adapter_id):
    rid = service.start(None, adapter_id=adapter_id, input_payload={"q": "x"})["run_id"]
    store.save_state(None, store.load_run(None, rid)[0])
    return rid


def test_b06_a_run_whose_step_unit_raises_ends_failed_and_the_worker_takes_the_next_run(worker_rig, monkeypatch):
    d, store = worker_rig
    _fixture_manifest(d, "fixture.poison", [{"step_id": "prep", "type": "VALIDATE", "title": "prep", "next": "X_compile"}], "prep")
    service.reset_registry()
    poisoned = _running(store, "fixture.poison")
    healthy = _running(store, "fixture.healthy")
    real = store.insert_step

    def insert_step(conn, step):                          # a deterministic database refusal of THIS run's rows (JSONB refuses \u0000)
        if step["run_id"] == poisoned:
            raise psycopg.DataError("unsupported Unicode escape sequence")
        return real(conn, step)
    monkeypatch.setattr(store, "insert_step", insert_step)
    assert W.process_one("worker-1", 120) == poisoned                                         # the defect: the error escaped (worker exit, re-claim, quarantine)
    st, _ = store.load_run(None, poisoned)
    assert st.status == "failed" and st.failure["code"] == "STEP_RUNTIME_ERROR" and "DataError" in st.failure["message"]
    assert store.runs[poisoned]["meta"]["lease_owner"] is None
    assert W.process_one("worker-1", 120) == healthy                                          # the next claim takes the healthy run …
    assert store.load_run(None, healthy)[0].status == "awaiting_agent"                          # … and drives it
    assert W.process_one("worker-1", 120) is None                                             # the failed run is never claimed again


def test_b06_a_transient_database_error_is_not_turned_into_a_run_failure(worker_rig, monkeypatch):
    _d, store = worker_rig
    rid = _running(store, "fixture.healthy")

    def down(*a, **kw):
        raise psycopg.OperationalError("server closed the connection unexpectedly")
    monkeypatch.setattr(W.service, "advance", down)
    with pytest.raises(psycopg.OperationalError):                                             # the loop backs off and retries it later
        W.process_one("worker-1", 120)
    assert store.load_run(None, rid)[0].status == "running" and store.runs[rid]["meta"]["lease_owner"] is None


def test_b06_the_worker_loop_backs_off_after_an_iteration_error_instead_of_exiting(monkeypatch):
    calls, sleeps = [], []

    def process_one(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        raise KeyboardInterrupt                                                               # stop the loop here
    monkeypatch.setattr(W, "process_one", process_one)
    monkeypatch.setattr(W, "worker_identity", lambda wt: {"worker_id": "w-test", "execution_bundle_id": None})
    monkeypatch.setattr(W, "register_worker", lambda conn, identity: None)
    monkeypatch.setattr(W, "heartbeat", lambda conn, worker_id, processed_count=None: None)
    monkeypatch.setattr(W, "configure_logging", lambda name: None)
    monkeypatch.setattr(W, "tx", lambda: contextlib.nullcontext(None))
    monkeypatch.setattr(W.time, "sleep", sleeps.append)
    with pytest.raises(KeyboardInterrupt):                                                    # the defect: RuntimeError('boom') ended main()
        W.main(["--poll-s", "0.5"])
    assert len(calls) == 2 and sleeps == [W.ERROR_BACKOFF_S]
    calls.clear()
    monkeypatch.setattr(W, "process_one", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):                                                         # --once (scripts, tests) still surfaces it
        W.main(["--once"])


# ═══════════════════════════════════════════════════════════ batch B
import asyncio
import itertools
import threading
import time

from polymath_shared import principal_context
from polymath_shared.adapter import hypotheses as H
from polymath_shared.adapter.transitions import RunState


# ─────────────────────────────────────────────────────────── B-20: a SPLIT in a later loop round reaches the ledger
def test_b20_a_split_in_a_later_round_keeps_its_new_children_in_the_ledger(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    service.reset_registry()
    m = service.manifest_for(SCRIPT.ADAPTER_ID)
    rid = "adr_" + "c" * 32
    store.insert_run(None, RunState(run_id=rid, adapter_id=m.adapter_id, status="awaiting_agent", input={"seed": "x"}), m, idempotency_key=None, agent_identity=None)
    refs = [{"kind": "chunk", "id": "chunk_k1"}]
    states, trs = H.generate(rid, {"run_id": rid, "step_id": "C_hypotheses", "sequence": 11, "context": {"evidence_refs": refs}},
                             [{"statement": f"hypothesis {i} statement text", "supporting_evidence_ids": ["chunk_k1"]} for i in range(3)],
                             registry_snapshot_id=None, recorded_at="2026-09-26T00:00:00Z")
    store.insert_hypothesis_revisions(None, states)
    store.insert_transitions(None, trs)
    h0 = states[0]["hypothesis_id"]

    def split(seq, tag):                                                       # K_revise, re-entered through M_loop
        step = {"run_id": rid, "step_id": "K_revise", "sequence": seq, "context": {"evidence_refs": refs}}
        payload = {"transitions": [{"hypothesis_id": h0, "kind": "SPLIT", "cause_refs": [{"kind": "chunk", "id": "chunk_k1"}],
                                    "children": [{"statement": f"{tag} narrower child", "supporting_evidence_ids": ["chunk_k1"]}]}]}
        return service._apply_theta(None, rid, step, m, store.load_run(None, rid)[0], payload, "2026-09-26T00:00:00Z")

    split(30, "round-one")
    assert store.current_hypotheses(None, rid)[h0]["status"] == "split"           # 'split' is not absorbed: the parent may split again
    split(44, "round-two")
    statements = [s["statement"] for s in store.current_hypotheses(None, rid).values()]
    assert any(s.startswith("round-one") for s in statements) and any(s.startswith("round-two") for s in statements)   # the defect: round two's child vanished
    service.reset_registry()


# ─────────────────────────────────────────────────────────── B-21: the supply directive, end to end (embedded Trail)
class _Edited(SCRIPT.Agent):
    """The scripted agent with per-step edits; an edit keyed `first:<step>` applies to the first answer only (the agent then corrects it)."""
    def __init__(self, edits):
        super().__init__()
        self.edits, self.calls = edits, {}

    def answer(self, nxt):
        out = super().answer(nxt)
        sid = nxt["step"]["step_id"]
        self.calls[sid] = self.calls.get(sid, 0) + 1
        if self.calls[sid] == 1 and f"first:{sid}" in self.edits:
            return self.edits[f"first:{sid}"](out, nxt)
        return self.edits[sid](out, nxt) if sid in self.edits else out


def test_b21_the_supply_directive_carries_the_qualifications_gaps_and_an_agents_extra_gap_key_is_harmless(embedded):
    store = embedded

    def note(out, nxt):
        out["knowledge_gaps"][0]["note"] = "the agent's own annotation"         # the manifest's gap items allow extra keys
        return out
    rid, st, actions, _r, leaked, at = _drive(_Edited({"G_mechanisms": note}))
    assert leaked is None, (at, repr(leaked))
    assert st.status == "completed", (st.status, st.gap, st.failure)           # the defect: TRAIL_REFUSED at S_gaps (extra_forbidden)
    field_q = {g["question"] for r in _rows(store, rid, "G_mechanisms") for g in (r["output"] or {}).get("knowledge_gaps") or []}
    supply = actions["S_supply"][0]
    assert field_q and not [g for g in supply["evidence_gaps"] if g["question"] in field_q]   # the defect: G_mechanisms' field question in the SUPPLY action
    gate = {g["question"] for g in _rows(store, rid, "R_qualify")[0]["output"].get("open_gaps") or []}
    assert {g["question"] for g in supply["evidence_gaps"]} <= gate


# ─────────────────────────────────────────────────────────── B-22 / B-26: agent-written values Trail's wire refuses, end to end
def test_b22_b26_values_trails_wire_refuses_are_handed_back_at_submit_and_the_corrected_run_completes(embedded):
    store = embedded

    def bad_role(out, nxt):
        out["knowledge_gaps"][0]["evidence_role"] = "Behavior"                 # Trail's gap compiler refuses it at H_gaps
        return out

    def long_mechanism(out, nxt):
        out["physical_jobs"][0]["mechanism"] = ("a glove-operable magnetic clip that holds the key ring flat against the hip " * 8)[:600]
        return out

    def extra_key(out, nxt):
        fev = [r["id"] for r in nxt["step"]["context"]["evidence_refs"] if r["kind"] == "field_evidence"]
        out["physical_jobs"][0]["evidence_ids"] = fev[:1]                      # cited from context: submit accepts it; Trail's job forbids it
        return out
    agent = _Edited({"first:G_mechanisms": bad_role, "first:N_jobs": long_mechanism, "N_jobs": extra_key})
    rid, st, _a, rejected, leaked, at = _drive(agent)
    assert leaked is None, (at, repr(leaked))
    assert any("Behavior" in e for e in rejected.get("G_mechanisms", [[]])[0]), rejected   # the defect: accepted, TRAIL_REFUSED at H_gaps
    assert any("mechanism" in e for e in rejected.get("N_jobs", [[]])[0]), rejected        # the defect: accepted, TRAIL_REFUSED at O_territory
    assert st.status == "completed", (st.status, st.gap, st.failure)                        # and the extra key never reached Trail
    assert _rows(store, rid, "O_territory")[0]["status"] == "executed"


# ─────────────────────────────────────────────────────────── B-24: the result's lineage names every knowledge ref the run produced
def _knowledge_per_pass(step, state, m):
    """The stub knowledge lane, plus one ref per K_retrieve pass: each loop round retrieves something new."""
    out = SCRIPT._knowledge(step, state, m)
    if step["step_id"] == "K_retrieve":
        rid_ = f"chunk_kr_{step['sequence']}"
        out["output"]["rows"].append({**SCRIPT.ROW, "id": rid_})
        out["evidence_refs"].append({"kind": "chunk", "id": rid_, "doc_id": "doc_k", "corpus_id": "probe"})
    return out


def test_b24_lineage_names_every_knowledge_ref_of_every_pass_and_every_ledger_citation(embedded):
    store = embedded                                                               # the embedded core reopens gaps: three field rounds
    rid, st, _a, _r, leaked, at = _drive(SCRIPT.Agent(), knowledge=_knowledge_per_pass)
    assert leaked is None and st.status == "completed", (at, leaked, st.status, st.gap)
    produced = {r["id"] for s in store.list_steps(None, rid) for r in ((s.get("output") or {}).get("_evidence_refs") or []) if r["kind"] in service.KNOWLEDGE_KINDS}
    per_pass = {i for i in produced if i.startswith("chunk_kr_")}
    assert len(per_pass) == 3                                                      # three field rounds, three K_retrieve passes
    cited = {v for h in store.current_hypotheses(None, rid).values() for k in h["knowledge_support"] for v in k.values() if isinstance(v, str) and v.startswith("chunk")}
    lineage = set(service.result(None, rid)["lineage"]["polymath_evidence_ids"])
    assert produced <= lineage, sorted(produced - lineage)                         # the defect: only the newest pass (the display window) was named
    assert cited <= lineage


# ─────────────────────────────────────────────────────────── B-25: cancel / submit wait for the run's row lock off the event loop
@pytest.mark.parametrize("route", ["cancel", "submit"])
def test_b25_a_route_waiting_on_the_workers_row_lock_never_blocks_the_event_loop(monkeypatch, route):
    from orchestrator.api import adapter as A
    assert pathlib.Path(A.__file__).resolve().is_relative_to(ROOT)
    row_lock = threading.Lock()
    row_lock.acquire()                                                            # the worker's step transaction holds the adapter_runs row
    seen = {}

    def assert_owner(conn, run_id, principal_id):
        seen["principal"] = principal_id

    def waits_for_the_row(conn, run_id, *a, **kw):                                # store.load_run(conn, run_id, for_update=True)
        with row_lock:
            return {"status": "cancelled"}
    monkeypatch.setattr(A, "tx", lambda: contextlib.nullcontext(None))
    monkeypatch.setattr(A.service, "assert_owner", assert_owner)
    monkeypatch.setattr(A.service, route, waits_for_the_row)
    threading.Timer(1.0, row_lock.release).start()                               # the worker's step commits after 1 s (minutes, live)
    ticks: list[float] = []

    async def other_request():                                                    # /health, or the worker's own /chat/evidence call
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1.4:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.02)

    async def main():
        other = asyncio.create_task(other_request())
        await asyncio.sleep(0.05)
        with principal_context.acting_as("prn_alice"):
            if route == "cancel":
                res = await A.adapter_cancel("adr_" + "c" * 32)
            else:
                res = await A.adapter_submit("adr_" + "c" * 32, A.SubmitRequest(step_id="brief", payload={}))
        await other
        return res
    res = asyncio.run(main())
    stall = max(b - a for a, b in itertools.pairwise(ticks))
    assert res == {"status": "cancelled"}
    assert stall < 0.5, f"the event loop stalled {stall:.2f}s while {route} waited for the row lock"   # the defect: ~1.0 s here (120 s+ live)
    assert seen["principal"] == "prn_alice"                                        # the ownership check still sees the request's principal


# ─────────────────────────────────────────────────────────── B-29 (+ B-14): a run that ended before compiling keeps what it produced
def test_b29_a_no_signal_run_result_carries_the_retained_interpretation(stub):
    rid, st, _a, _r, leaked, at = _drive(SCRIPT.NoSignalAgent())
    assert leaked is None and st.status == "terminal_gap" and st.gap["code"] == "NO_GENERATIVE_SIGNAL", (at, leaked, st.status, st.gap)
    res = service.result(None, rid)
    assert res["status"] == "terminal_gap" and res["gap"]["code"] == "NO_GENERATIVE_SIGNAL"
    assert res["output"]["primitives"]["generative_signal"] is False                # the defect: output == {} ("retained as knowledge" nowhere)
    assert C.validate("adapter_result", res) == []


def test_b14_a_run_refused_after_research_keeps_its_admitted_evidence_in_the_result(stub):
    rid, st, _a, _r, leaked, at = _drive(SCRIPT.OneIdeaAgent())
    assert leaked is None and st.status == "terminal_gap" and st.gap["step_id"] == "Z_refuse_concepts", (at, leaked, st.status, st.gap)
    res = service.result(None, rid)
    admitted = [a["admitted_evidence_id"] for adm in res["output"].get("evidence_admissions") or [] for a in adm["admitted"]]
    assert admitted and sorted(admitted) == res["lineage"]["admitted_evidence_ids"]   # the defect: "admitted 0" beside a lineage that counts them
    assert res["output"]["lived_clusters"] and res["gap"]["code"] == "PRODUCT_PORTFOLIO_LAW_UNSATISFIED"


# ─────────────────────────────────────────────────────────── B-12: both qualify stages reach the result
def test_b12_a_completed_run_result_keeps_the_market_and_the_supply_qualifications(stub):
    rid, st, _a, _r, leaked, at = _drive(SCRIPT.Agent())
    assert leaked is None and st.status == "completed", (at, leaked, st.status, st.gap)
    by_step = service.result(None, rid)["output"]["qualifications_by_step"]
    assert [sorted({q["stage"] for q in step}) for step in by_step] == [["market_delta"], ["supply"]]   # the defect: market_delta never reached it
