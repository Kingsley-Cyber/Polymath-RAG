"""TRAIL-INTERFACE-V1 T5 — a run's research dossier, rendered on the server.

The journal rebuilt from a run's stored rows is, byte for byte, the one `governed_run.py` writes (the engine's own functions build the
reference); the engine renders it out of process, unchanged; what comes back keeps only the renderer's own markup, so field text stays
text; the route sends it under a CSP that allows no script, to the run's owner only (the same check as every run route); an adapter
without a renderer has no dossier; the web boundary opens the route to signed-in users; the owner alone sees the registry block.
Rows are synthetic, built from the shapes TrailSignal and the adapter store use. No database, no network, no model."""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / sub))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from orchestrator.api import adapter as adapter_api
from polymath_shared.adapter import dossier, run_view, service
from polymath_shared.adapter.transitions import RunState
from polymath_shared.principal_context import PrincipalContextMiddleware

from orchestrator import web_boundary as B

ENGINE = ROOT / "adapters" / "ecommerce"
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"


def _engine_journal_module():
    """governed_run.py imports the standard library only: loaded by file under a private name, the engine's module names stay out."""
    spec = importlib.util.spec_from_file_location("_engine_governed_run", ENGINE / "python" / "governed_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GR = _engine_journal_module()

# ─────────────────────────────────────────────────────────── one run, as the store holds it
RUN_ID = "adr_" + "5e" * 16
HYP, ACTION, FEV = "hyp_0a1b2c3d4e5f", "hact_0a1b2c3d4e5f6a7b8c9d0e1f", "fev_0a1b2c3d4e5f"
SNAP = {"snapshot_id": "trs_2026_09_26", "content_hash": "sha256:" + "ab" * 32}
CREATED, ENDED = "2026-09-26T10:00:00Z", "2026-09-26T10:40:00Z"
SCRIPT, IMG = "<script>alert(1)</script>", "<img src=x onerror=alert(2)>"
INPUT = {"seed": "cold hands while filming outdoors", "corpus_ids": ["probe"]}
PRIORS = [{"registry_record_id": "reg_friction_07", "prior_role": "friction_primitive", "hypothesis_ids": [HYP], "label": "access_interruption",
           "section": "frictions", "match_strength": 2, "mapping_path": "structured"}]
TERRITORIES = [{"territory_id": "ter_03", "territory": "friction_primitive", "hypothesis_ids": [HYP], "territory_name": "Cold-weather handling",
                "mapping_path": "structured"}]
RECEIPT = {"action_id": ACTION, "run_id": RUN_ID, "harness_id": "claude-code", "started_at": "2026-09-26T10:05:00Z", "completed_at": "2026-09-26T10:09:00Z",
           "sources": [{"source_id": "src_1", "url": "https://www.reddit.com/r/filmmakers/comments/abc/", "source_class": "community_discussion",
                        "retrieved_at": "2026-09-26T10:06:00Z", "published_at_if_known": None}],
           "observations": [{"observation_id": "obs_1", "source_id": "src_1", "claim": "the dial needs bare fingers", "metric_if_present": None,
                             "paraphrase_or_excerpt": f"{SCRIPT} my fingers go numb on the dial", "hypothesis_ids": [HYP], "evidence_role_claimed": "friction"}],
           "tool_trace": [{"search_intent_id": "si_1", "tool_class": "exa.search", "query_count": 3}], "limitations": []}
ADMISSION = {"run_id": RUN_ID, "action_id": ACTION, "admission_id": "hadm_1", "registry_snapshot": SNAP, "rejected": [],
             "admitted": [{"observation_id": "obs_1", "admitted_evidence_id": FEV, "evidence_role": "friction", "polarity": "supporting", "freshness": "fresh",
                           "source_class": "community_discussion", "independence_group": "reddit", "stage_relevance": "field_evidence",
                           "source_suitability": "suitable", "hypothesis_ids": [HYP]}]}
QUAL_MARKET = {"record_id": "qual-market-1", "stage": "market_delta", "state": "UNPROVEN", "hypothesis_ids": [HYP]}
QUAL_SUPPLY = {"record_id": "qual-supply-1", "stage": "supply", "state": "UNPROVEN", "hypothesis_ids": [HYP]}
REFUSAL = {"record_id": "score-refusal-1", "hypothesis_id": HYP, "reason_code": "HARD_GATE_UNMET", "detail": "one platform where three are required", "as_of": ENDED}


def _row(seq: int, step_id: str, step_type: str, status: str, output=None, *, refs=(), hypotheses=(), submission=None, action=None) -> dict:
    step = {"run_id": RUN_ID, "step_id": step_id, "step_type": step_type, "sequence": seq, "issued_at": f"2026-09-26T10:{seq:02d}:00Z",
            "context": {"evidence_refs": list(refs), "hypotheses": list(hypotheses)}, "harness_action": action}
    sub = None if submission is None else {"step_id": step_id, "payload": submission, "submitted_by": {"agent_identity": "claude-code"},
                                           "run_id": RUN_ID, "submitted_at": f"2026-09-26T10:{seq:02d}:30Z", "submission_hash": "0" * 64}
    return {"sequence": seq, "step_id": step_id, "step_type": step_type, "status": status, "step": step, "submission": sub, "output": output,
            "receipt": None, "external_operation": None}


def _rows(*, live: bool = False) -> list[dict]:
    hyps = [{"hypothesis_id": HYP, "statement": f"{IMG} filmmakers lose feeling in their fingers", "status": "proposed"}]
    rows = [
        _row(1, "A_understand", "VALIDATE", "executed", {"valid": True}),
        _row(2, "B_retrieve", "POLYMATH_RETRIEVE", "executed", {
            "surface": "evidence_boundary", "mode": "WILDCARD", "needs": [INPUT["seed"]], "corpus_ids": ["probe"],
            "rows": [{"id": "chunk_k1", "kind": "chunk", "doc_id": "doc_k", "corpus_id": "probe", "text": "Cold hands lose dexterity first.", "ca4_grade": "DIRECT"}],
            "calls": [{"grades": {"DIRECT": 1}, "compiled_queries": 2, "corpus_explorer_requested": True, "corpus_explorer_used": False}]}),
        _row(3, "C_hypotheses", "AGENT_REASON", "accepted", {"hypotheses": [{"statement": "x"}], "hypothesis_ids": [HYP]},
             refs=[{"kind": "chunk", "id": "chunk_k1"}], submission={"hypotheses": [{"statement": "x", "supporting_evidence_ids": ["chunk_k1"]}]}),
        _row(4, "D_project", "EXTERNAL_OPERATION", "executed", {"operation_kind": "registry.project", "registry_snapshot": SNAP, "priors": PRIORS,
                                                                "redundancy_groups": [], "unsupported_hypothesis_ids": []}),
        _row(5, "I_research", "HARNESS_ACTION", "accepted", {**RECEIPT, "_harness_action_id": ACTION}, hypotheses=hyps, submission=RECEIPT,
             action={"action_id": ACTION, "action_kind": "AGENT_RESEARCH", "hypothesis_ids": [HYP]}),
        _row(6, "J_admit", "EXTERNAL_OPERATION", "executed", {"operation_kind": "evidence.admit", "registry_snapshot": SNAP, "evidence_admission": ADMISSION}),
        _row(7, "W_interpret", "AGENT_REASON", "issued" if live else "accepted", None if live else {"interpretation": "one platform so far"},
             refs=[{"kind": "field_evidence", "id": FEV}], hypotheses=hyps, submission=None if live else {"interpretation": "one platform so far"}),
    ]
    if not live:
        rows += [_row(8, "O_territory", "EXTERNAL_OPERATION", "executed", {"operation_kind": "territory.project", "registry_snapshot": SNAP, "territories": TERRITORIES}),
                 _row(9, "R_qualify", "EXTERNAL_OPERATION", "executed", {"operation_kind": "opportunity.qualify", "registry_snapshot": SNAP, "qualifications": [QUAL_MARKET]}),
                 _row(10, "U_qualify", "EXTERNAL_OPERATION", "executed", {"operation_kind": "opportunity.qualify", "registry_snapshot": SNAP, "qualifications": [QUAL_SUPPLY]}),
                 _row(11, "V_score", "EXTERNAL_OPERATION", "executed", {"operation_kind": "opportunity.score", "registry_snapshot": SNAP, "trail_scores": [],
                                                                        "score_refusals": [REFUSAL], "qualifications": []}),
                 _row(12, "X_compile", "COMPILE_RESULT", "executed", {"result_hash": "f" * 64})]
    return rows


def _run_meta() -> dict:
    return {"run_id": RUN_ID, "adapter_id": "ecommerce.product_research", "adapter_version": "0.7.0", "workflow_version": "0.7.0",
            "created_at": CREATED, "updated_at": ENDED, "agent_identity": "claude-code", "input": INPUT}


class _Store:
    """The adapter store functions the view, the journal and the owner check read, over in-memory rows."""

    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}

    def add(self, run_id: str, rows: list[dict], *, adapter_id: str = "ecommerce.product_research", owner: str | None = None,
            gap: dict | None = None) -> None:
        done = [r for r in rows if r["status"] in ("accepted", "executed")]
        live = any(r["status"] == "issued" for r in rows)
        state = RunState(run_id=run_id, adapter_id=adapter_id, status="awaiting_agent" if live else "terminal_gap" if gap else "completed",
                         current_step_id=rows[-1]["step_id"], sequence=len(rows), steps_accepted=len(done), input=dict(INPUT),
                         outputs={r["step_id"]: r["output"] for r in done}, output_order=tuple(r["step_id"] for r in done), gap=gap)
        meta = {"adapter_version": "0.7.0", "workflow_version": "0.7.0", "agent_identity": None, "created_at": CREATED, "updated_at": ENDED,
                "terminal_at": None if live else ENDED}
        self.runs[run_id] = {"state": state, "meta": meta, "owner": owner, "rows": rows}

    def load_run(self, conn, run_id, *, for_update=False):
        r = self.runs.get(run_id)
        return (r["state"], dict(r["meta"])) if r else None

    def run_owner(self, conn, run_id):
        r = self.runs.get(run_id)
        return (True, r["owner"]) if r else (False, None)

    def list_steps(self, conn, run_id):
        return copy.deepcopy(self.runs[run_id]["rows"])

    def load_result(self, conn, run_id):
        return None

    def current_hypotheses(self, conn, run_id):
        return {}

    def list_harness_actions(self, conn, run_id):
        return []

    def admitted_evidence_refs(self, conn, run_id):
        return []


class _AsOfIssue(_Store):
    """What adapter_next read when it issued step `sequence`: the rows stored up to it, that step not yet answered."""

    def __init__(self, rows: list[dict], sequence: int) -> None:
        super().__init__()
        self.rows = [dict(r, output=None, status="issued") if r["sequence"] == sequence else r for r in rows if r["sequence"] <= sequence]

    def list_steps(self, conn, run_id):
        return copy.deepcopy(self.rows)


def test_the_code_under_test_is_this_checkout():
    for mod in (dossier, run_view, adapter_api, B):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── the journal
def test_the_journal_rebuilt_from_rows_is_the_one_governed_run_writes(monkeypatch):
    rows = _rows()
    result = {"run_id": RUN_ID, "status": "completed", "terminal_at": ENDED, "gap": None, "unknowns": [], "contradictions": [],
              "lineage": {"harness_ids": ["claude-code"]}, "output": {"evidence_admissions": [ADMISSION], "score_refusals": [REFUSAL]}}
    # the reference: the engine's own journal functions, fed what each tool call returned — adapter_next's evidence from the service's
    # own hydration over the rows stored when the step was issued, adapter_submit's status answer after each acceptance
    ref = {k: _run_meta()[k] for k in ("run_id", "adapter_id", "adapter_version", "workflow_version", "created_at")}
    host = GR.new_journal({**ref, "status": "running"}, INPUT, agent_identity="claude-code", harness_id="claude-code", at=CREATED)
    for r in rows:
        if r["step_type"] not in ("AGENT_REASON", "HARNESS_ACTION"):
            continue
        monkeypatch.setattr(service, "store", _AsOfIssue(rows, r["sequence"]))
        shown = service._readable_evidence(None, RUN_ID, r["step"])
        awaiting, kind = ("awaiting_agent", "reasoning") if r["step_type"] == "AGENT_REASON" else ("awaiting_harness", "receipt")
        GR.record_next(host, {"kind": "step", "step": r["step"], "status": {"status": awaiting}, "evidence": shown}, at=r["step"]["issued_at"])
        answered = sum(1 for x in rows if x["sequence"] <= r["sequence"] and x["status"] in ("accepted", "executed"))
        GR.record_submission(host, r["step_id"], kind, r["submission"]["payload"], {"status": "running", "current_step_id": r["step_id"],
                             "steps_accepted": answered, "gap": None, "failure": None}, at=r["submission"]["submitted_at"])
    GR.record_result(host, result, at=ENDED)
    host["built_at"] = ENDED

    journal = dossier.journal_from_store(_run_meta(), rows, result)
    assert journal == host
    kinds = [e["kind"] for e in journal["events"]]
    assert kinds == ["start", "step", "submission", "step", "submission", "step", "submission", "result"]
    # the readable evidence each step carried: the corpus row, then the admitted observation joined to its receipt
    assert [x["id"] for x in journal["events"][1]["data"]["evidence"]["rows"]] == ["chunk_k1"]
    assert journal["events"][5]["data"]["evidence"]["rows"][0]["id"] == FEV and SCRIPT in journal["events"][5]["data"]["evidence"]["rows"][0]["text"]
    assert dossier.journal_from_store(_run_meta(), list(reversed(rows)), result) == journal          # deterministic, sequence order


def test_a_live_run_has_no_result_and_its_open_step_no_submission():
    journal = dossier.journal_from_store({**_run_meta(), "agent_identity": None}, _rows(live=True), None)
    assert [e["kind"] for e in journal["events"]] == ["start", "step", "submission", "step", "submission", "step"]
    assert journal["agent_identity"] == "claude-code"                 # the identity the accepted reasoning named
    assert journal["built_at"] == ENDED                               # the run's last update, never now


def test_the_journal_constants_are_the_engines():
    assert (dossier.JOURNAL_VERSION, dossier.MAX_EVIDENCE_ROWS) == (GR.JOURNAL_VERSION, GR.MAX_EVIDENCE_ROWS)
    helptext = subprocess.run([sys.executable, str(dossier.RENDERER), "report", "--help"], capture_output=True, text=True, check=True).stdout
    assert re.search(r"\{([A-Z_,]+)\}", helptext).group(1).split(",") == list(dossier.LAYOUTS)


# ─────────────────────────────────────────────────────────── the page
def test_the_dossier_is_rendered_out_of_process_and_field_text_stays_text(monkeypatch):
    fake = _Store()
    fake.add(RUN_ID, _rows())
    monkeypatch.setattr(service, "store", fake)
    monkeypatch.setattr(run_view, "store", fake)
    journal = run_view.dossier_journal(None, RUN_ID)
    result = journal["events"][-1]["data"]["result"]
    assert [q["record_id"] for q in result["output"]["qualifications"]] == ["qual-market-1", "qual-supply-1"]     # every qualify step's gates
    page = dossier.render_dossier(journal, title="Cold hands")
    assert page.startswith("<!doctype html>") and "<title>Cold hands</title>" in page and "Governed Opportunity Dossier" in page
    assert "GOVERNED — TRAIL REFUSED TO SCORE" in page and "REFUSED: HARD_GATE_UNMET" in page and "Corpus evidence packets" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; my fingers go numb on the dial" in page          # a receipt's quote, as text
    assert "&lt;img src=x onerror=alert(2)&gt;" in page                                              # an agent's statement, as text
    assert not re.search(r"<\s*(script|img|iframe|a)\b", page, re.IGNORECASE) and not re.search(r"<[^>]*\son[a-z]+\s*=", page, re.IGNORECASE)   # no handler
    assert "trs_2026_09_26" in page and "access_interruption" in page                               # the registry lines of the dossier
    assert dossier.render_dossier(journal, title="Cold hands") == page                              # deterministic
    assert not [m for m in ("report", "models", "graph") if str(ENGINE) in str(getattr(sys.modules.get(m), "__file__", ""))]   # out of process


def test_a_run_stopped_by_a_gap_still_shows_what_was_admitted(monkeypatch):
    fake = _Store()
    fake.add(RUN_ID, _rows()[:6], gap={"code": "TRAIL_REFUSED", "message": "hypotheses.judge refused", "step_id": "L_judge"})
    monkeypatch.setattr(service, "store", fake)
    monkeypatch.setattr(run_view, "store", fake)
    result = run_view.dossier_journal(None, RUN_ID)["events"][-1]["data"]["result"]
    assert result["status"] == "terminal_gap" and result["output"]["evidence_admissions"] == [ADMISSION]      # not an empty body
    page = dossier.render_dossier(run_view.dossier_journal(None, RUN_ID))
    assert "GOVERNED GAP — TRAIL_REFUSED" in page and "Field Observations — admitted 1 · rejected 0" in page


def test_the_sanitizer_keeps_the_renderers_markup_and_nothing_active():
    raw = ('<style>.why{color:var(--muted)}</style><div class="card"><h3 title="t">Hi</h3><p class=\'why\' onclick="steal()" style="color:#b00">'
           'a &lt;b&gt; <script>alert(1)</script><img src=x onerror=y><a href="javascript:z">link</a><!-- note --><iframe>inside</iframe>'
           '<td colspan="7">x</td></p></div><br>')
    assert dossier.sanitize(raw) == ('<style>.why{color:var(--muted)}</style><div class="card"><h3 title="t">Hi</h3>'
                                     '<p class="why" style="color:#b00">a &lt;b&gt; link<td colspan="7">x</td></p></div><br>')


def test_a_renderer_failure_is_typed(monkeypatch):
    with pytest.raises(dossier.DossierError) as bad:
        dossier.render_dossier({"journal_version": "not-a-journal", "events": []})
    assert bad.value.code == "DOSSIER_RENDER_FAILED"
    with pytest.raises(dossier.DossierError) as layout:
        dossier.render_dossier({}, layout="POSTER")
    assert layout.value.code == "DOSSIER_LAYOUT_UNKNOWN"


# ─────────────────────────────────────────────────────────── the route
@pytest.fixture
def client(monkeypatch):
    fake = _Store()
    fake.add(RUN_ID, _rows(), owner="prn_alice")
    fake.add("adr_" + "1" * 32, _rows(live=True))
    fake.add("adr_" + "2" * 32, _rows()[:3], adapter_id="polymath.knowledge_brief")
    monkeypatch.setattr(service, "store", fake)
    monkeypatch.setattr(run_view, "store", fake)
    monkeypatch.setattr(adapter_api, "tx", contextlib.nullcontext)
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.include_router(adapter_api.router)
    return TestClient(app, base_url="https://testserver")


def test_the_owner_gets_the_dossier_under_a_csp_that_allows_no_script(client):
    r = client.get(f"/adapter/{RUN_ID}/report")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"] == CSP
    assert (r.headers["x-content-type-options"], r.headers["referrer-policy"], r.headers["cache-control"]) == ("nosniff", "no-referrer", "no-store")
    assert "content-disposition" not in r.headers
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.text and not re.search(r"<\s*script", r.text, re.IGNORECASE)
    assert "<title>Dossier · cold hands while filming outdoors</title>" in r.text
    d = client.get(f"/adapter/{RUN_ID}/report?download=1&layout=EXECUTIVE")
    assert d.status_code == 200 and d.headers["content-disposition"] == f'attachment; filename="dossier-{RUN_ID}.html"' and "Executive" in d.text


def test_a_run_reaches_its_owner_only_with_the_same_answer_as_the_view(client):
    theirs = {"x-polymath-principal": "prn_fred"}
    report, view = client.get(f"/adapter/{RUN_ID}/report", headers=theirs), client.get(f"/adapter/{RUN_ID}/view", headers=theirs)
    assert report.status_code == view.status_code == 403 and report.json() == view.json() == {"detail": "no such run for this principal"}
    assert "dossier" not in report.text.lower()
    assert client.get(f"/adapter/{RUN_ID}/report", headers={"x-polymath-principal": "prn_alice"}).status_code == 200   # her own run
    assert client.get("/adapter/adr_" + "9" * 32 + "/report", headers=theirs).status_code == 403                   # none is the same "not yours"
    assert client.get("/adapter/adr_" + "9" * 32 + "/report").status_code == 404


def test_a_live_run_reads_as_in_progress_and_an_adapter_without_a_renderer_has_no_dossier(client):
    live = client.get("/adapter/adr_" + "1" * 32 + "/report")
    assert live.status_code == 200 and "IN PROGRESS" in live.text
    brief = client.get("/adapter/adr_" + "2" * 32 + "/report")
    assert brief.status_code == 404 and brief.json()["detail"]["error_code"] == "NO_DOSSIER"
    bad = client.get(f"/adapter/{RUN_ID}/report?layout=POSTER")
    assert bad.status_code == 422 and bad.json()["detail"]["error_code"] == "UNKNOWN_LAYOUT"


def test_the_view_says_whether_a_dossier_exists_and_shows_the_registry_to_the_owner_only(client):
    owner = client.get(f"/adapter/{RUN_ID}/view").json()
    assert owner["report"] == {"available": True}
    assert owner["registry"] == {"snapshot": SNAP, "snapshot_ids": ["trs_2026_09_26"], "priors": PRIORS, "territories": TERRITORIES}
    friend = client.get(f"/adapter/{RUN_ID}/view", headers={"x-polymath-principal": "prn_alice"}).json()
    assert friend["report"] == {"available": True} and "registry" not in friend
    brief = client.get("/adapter/adr_" + "2" * 32 + "/view").json()
    assert brief["report"] == {"available": False} and brief["registry"] is None             # a Trail-free run has no registry


def test_the_web_boundary_opens_the_report_to_signed_in_users():
    assert B.classify("GET", f"/adapter/{RUN_ID}/report") == B.USER and B.classify("HEAD", f"/adapter/{RUN_ID}/report") == B.USER
    assert B.classify("POST", f"/adapter/{RUN_ID}/report") is None
