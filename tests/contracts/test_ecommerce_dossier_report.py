"""TRAIL-EXT-BUGHUNT-V1 B-11 / B-12 / B-13 / B-14 / B-16 — the governed dossier (`adapters/ecommerce/python/report.py`) shows what the
result holds, counted the way TrailSignal counts it, and says when something is absent or cut.

Each test builds a SYNTHETIC governed-run journal, then builds the ReportModel and renders it OUT OF PROCESS through the engine's own
`report` module (its flat module names never enter this interpreter) and asserts the corrected section. No database, no network,
no field evidence: every text is invented.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "adapters" / "ecommerce"
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import semantic_view as SV

H1, H2 = "hyp_" + "a" * 12, "hyp_" + "b" * 12


def _dossier(journal: dict, tmp_path: pathlib.Path) -> tuple[dict, str]:
    jpath = tmp_path / "journal.json"
    jpath.write_text(json.dumps(journal))
    code = ("import json, sys; sys.path.insert(0, 'python'); import report; "
            "m = report.build_model_from_governed(json.load(open(sys.argv[1]))); print(json.dumps({'model': m, 'html': report.render(m)}))")
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "OPPORTUNITY_RESEARCH_DB": str(tmp_path / "loop.sqlite3")}
    proc = subprocess.run([sys.executable, "-c", code, str(jpath)], cwd=ENGINE, env=env, capture_output=True, text=True, check=False, timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    out = json.loads(proc.stdout)
    return out["model"], out["html"]


def _journal(output: dict, *, status: str = "completed", lineage: dict | None = None, gap: dict | None = None, unknowns: list | None = None,
             events: tuple = ()) -> dict:
    result = {"run_id": "adr_" + "6" * 32, "status": status, "gap": gap, "output": output, "lineage": lineage or {}, "unknowns": unknowns or [],
              "contradictions": []}
    return {"run_id": "adr_" + "6" * 32, "adapter_id": "ecommerce.product_research", "adapter_version": "0.7.0", "created_at": "2026-09-26T10:00:00Z",
            "input": {"seed": "synthetic seed: cold hands cannot turn small camera dials"}, "agent_identity": "test-agent", "harness_id": "test-harness",
            "events": [*events, {"seq": len(events) + 1, "kind": "result", "data": {"result": result}}], "built_at": "2026-09-26T12:00:00Z"}


def _admitted(i: int, *, hyp: str = H1, polarity: str = "supporting", stage: str = "field_evidence", relations: list | None = None, duplicate_of=None) -> dict:
    row = {"admitted_evidence_id": f"fev_{i:03d}", "observation_id": f"o{i}", "source_id": "s1", "evidence_role": "friction", "source_class": "community_discussion",
           "freshness": "fresh", "independence_group": f"grp_{i % 5}", "duplicate_of": duplicate_of, "polarity": polarity, "hypothesis_ids": [hyp],
           "stage_relevance": stage}
    if relations:
        row["hypothesis_relations"] = relations
    return row


def _view(hid: str, *, gaps: list | None = None, field_rows: int = 0) -> dict:
    """The derived hypothesis view exactly as the runtime compiles it into the result (semantic_view: lists capped at 12, 24 rows)."""
    state = {"hypothesis_id": hid, "revision": 3, "status": "revised", "statement": f"synthetic statement for {hid}", "knowledge_support": [],
             "knowledge_gaps": gaps or []}
    obs = [{"observation_id": f"o{i}", "source_id": "s1", "claim": f"synthetic claim {i}", "paraphrase_or_excerpt": "synthetic quote"} for i in range(field_rows)]
    adm = [{"admitted_evidence_id": f"fev_{i:03d}", "observation_id": f"o{i}", "source_id": "s1", "evidence_role": "friction", "polarity": "supporting",
            "hypothesis_ids": [hid]} for i in range(field_rows)]
    steps = [{"step_id": "I_research", "sequence": 1, "output": {"action_id": "act_1", "observations": obs, "sources": [{"source_id": "s1", "url": "https://example.org/t"}]}},
             {"step_id": "J_admit", "sequence": 2, "output": {"evidence_admission": {"action_id": "act_1", "admitted": adm, "rejected": []}}}] if field_rows else []
    return SV.build({hid: state}, {}, step_outputs=steps)["hypotheses"][0]


# ─────────────────────────────────────────────────────────── B-12: a qualification shows its STATE, gates and gaps — both stages
MARKET = {"record_id": "qual-m-1", "stage": "market_delta", "state": "PROVISIONAL", "hypothesis_ids": [H1],
          "gate_results": [{"gate_id": "gate_c", "name": "competitor_review_analysis", "minimum": 2, "observed": 1, "passed": False},
                           {"gate_id": "gate_p", "name": "current_price_checks", "minimum": 1, "observed": 2, "passed": True}],
          "open_gaps": [{"gap_id": "gap_q1", "hypothesis_id": H1, "question": "which incumbent already fits gloves?", "evidence_role": "competition"}]}
SUPPLY = {"record_id": "qual-s-1", "stage": "supply", "state": "UNPROVEN", "hypothesis_ids": [H1],
          "gate_results": [{"gate_id": "gate_r", "name": "risk_review", "minimum": 1, "observed": 0, "passed": False}], "open_gaps": []}


def test_a_qualification_renders_its_state_gate_results_and_open_gaps(tmp_path):
    _, html = _dossier(_journal({"qualifications": [MARKET]}), tmp_path)
    assert "qualification market_delta: <strong>PROVISIONAL</strong>" in html
    assert "competitor_review_analysis 1/2 unmet" in html and "current_price_checks 2/1 passed" in html and "1 open gap" in html


def test_every_qualify_stage_the_result_collects_is_shown_once_market_delta_first(tmp_path):
    # a result compiled with `{"collect_all": "qualifications", "as": "qualifications_by_step"}` keeps R_qualify beside U_qualify; the
    # plain `qualifications` include (newest step wins) holds only the supply list
    model, html = _dossier(_journal({"qualifications_by_step": [[MARKET], [SUPPLY]], "qualifications": [SUPPLY]}), tmp_path)
    assert [q["record_id"] for q in model["governed"]["qualifications"]] == ["qual-m-1", "qual-s-1"]
    assert "qualification market_delta: <strong>PROVISIONAL</strong>" in html and "qualification supply: <strong>UNPROVEN</strong>" in html
    assert html.index("qualification market_delta") < html.index("qualification supply") and "risk_review 0/1 unmet" in html


# ─────────────────────────────────────────────────────────── B-13 + B-11: Field + / − as TrailSignal counts it; every open ledger gap
def test_field_counts_come_from_every_admitted_field_record_by_trailsignals_relation_to_the_hypothesis(tmp_path):
    field = [_admitted(i, polarity="contradicting" if i < 4 else "supporting") for i in range(30)]                  # 26 + / 4 −, the 4 − admitted first
    field.append(_admitted(30, relations=[{"hypothesis_id": H1, "relation": "CONTRADICTS"}]))                       # globally supporting, CONTRADICTS H1
    field.append(_admitted(31, polarity="contradicting", relations=[{"hypothesis_id": H1, "relation": "NEUTRAL"}]))  # neither, for H1
    other = [_admitted(40 + i, stage="product_reality") for i in range(5)] + [_admitted(50, duplicate_of="fev_005")]  # not field evidence / a duplicate
    output = {"evidence_admissions": [{"action_id": "act_1", "admitted": field + other, "rejected": []}], "hypothesis_semantics": [_view(H1, field_rows=30)]}
    model, html = _dossier(_journal(output), tmp_path)
    row = model["governed"]["hypotheses"][0]
    assert (row["field_evidence"], row["field_supporting"], row["field_contradicting"]) == (32, 26, 5)             # the view's 24-row tail said 24 / 0
    assert "<td class='num'>26 / 5 · " in html
    # the Field Observations table shows the per-hypothesis relation where it differs from the global polarity
    assert f"supporting<br>{H1}: contradicting" in html and f"contradicting<br>{H1}: neutral" in html


def test_every_open_ledger_gap_reaches_the_hypothesis_row_not_only_those_among_the_first_12(tmp_path):
    gaps = [{"gap_id": f"g{i}", "question": f"synthetic question {i}", "evidence_role": "friction", "status": "closed" if i < 12 else "open"} for i in range(14)]
    loop = [{"gap_id": f"g{i}", "hypothesis_id": H1, "question": f"synthetic question {i}", "evidence_role": "friction", "origin": "ledger"} for i in (12, 13)]
    loop += [{"gap_id": "gb1", "hypothesis_id": H1, "question": "a bridge question", "evidence_role": "friction", "origin": "bridge"}]
    model, html = _dossier(_journal({"hypothesis_semantics": [_view(H1, gaps=gaps)], "unresolved_research_gaps": loop}), tmp_path)
    assert model["governed"]["hypotheses"][0]["open_gaps"] == ["synthetic question 12", "synthetic question 13"]    # the view kept only the 12 closed ones
    many = [{"gap_id": f"g{i}", "question": f"synthetic question {i}", "evidence_role": "friction", "status": "open"} for i in range(6)]
    _, html = _dossier(_journal({"hypothesis_semantics": [_view(H1, gaps=many)]}), tmp_path)
    assert "open gaps (6): synthetic question 0; synthetic question 1; synthetic question 2; synthetic question 3 (+2 more)" in html


# ─────────────────────────────────────────────────────────── B-14: evidence a result does not carry is ABSENT, never zero
def test_a_run_that_ended_before_compiling_says_its_admitted_evidence_is_absent_not_zero(tmp_path):
    receipt = {"action_id": "act_1", "observations": [{"observation_id": "o1", "source_id": "s1", "claim": "synthetic claim", "paraphrase_or_excerpt": "synthetic quote"}],
               "sources": [{"source_id": "s1", "url": "https://example.org/t"}], "tool_trace": []}
    submission = {"seq": 1, "kind": "submission", "data": {"step_id": "I_research", "kind": "receipt", "accepted": True, "payload": receipt}}
    journal = _journal({}, status="terminal_gap", gap={"code": "PRODUCT_CONCEPTS_UNLAWFUL", "step_id": "Z_refuse_concepts", "message": "synthetic"},
                       lineage={"admitted_evidence_ids": ["fev_1", "fev_2", "fev_3"]}, events=(submission,))
    model, html = _dossier(journal, tmp_path)
    assert model["governed"]["evidence_absent"] == {"admitted_evidence_ids": 3, "terminal_status": "terminal_gap"}
    assert "admitted 0 · rejected 0" not in html and "Field Observations — 3 admitted evidence id(s) in the lineage; their records are not in this result" in html
    assert "the result carries no step outputs" in html and "Typed gap PRODUCT_CONCEPTS_UNLAWFUL" in html
    # a completed run whose result carries its admissions is unchanged
    done = _journal({"evidence_admissions": [{"action_id": "act_1", "admitted": [_admitted(1)], "rejected": []}]}, lineage={"admitted_evidence_ids": ["fev_001"]})
    model, html = _dossier(done, tmp_path)
    assert model["governed"]["evidence_absent"] is None and "Field Observations — admitted 1 · rejected 0" in html


# ─────────────────────────────────────────────────────────── B-16: the loop's open questions lead Unresolved; every cut is said
def test_unresolved_leads_with_the_loops_open_questions_and_no_list_is_cut_silently(tmp_path):
    loop = [{"gap_id": f"g{i}", "hypothesis_id": H1 if i % 2 else H2, "question": f"LOOPQ-{i:02d} synthetic open question", "evidence_role": "friction",
             "origin": "ledger" if i % 3 else "bridge"} for i in range(36)]
    clusters = [{"id": f"cl{i}", "community": f"community-{i:02d}", "friction_family": "dexterity_loss", "authority": "THIN", "record_count": 1, "thread_count": 1,
                 "independent_voices": 1, "unknowns": []} for i in range(13)]
    leads = [{"id": f"lead{i}", "name": f"synthetic lead {i:02d}", "source_lane": "CORPUS", "voi": 1.0 - i / 100} for i in range(15)]
    sits = [{"id": f"ls{i}", "authority": "RECONSTRUCTED", "community": f"community-{i:02d}", "unknowns": ["how often"], "frictions": []} for i in range(11)]
    output = {"unresolved_research_gaps": loop, "lived_clusters": clusters, "population_leads": leads, "lived_situations": sits,
              "product_opportunity": {"remaining_uncertainty": ["synthetic remaining doubt"]}}
    unknowns = [{"about": "no PURCHASE_INTENT recorded"}] * 5 + [{"about": "workaround unknown"}] * 3
    model, html = _dossier(_journal(output, unknowns=unknowns), tmp_path)
    assert all(f"LOOPQ-{i:02d} synthetic open question" in html for i in range(36))
    assert model["unresolved"][:36] == [f"LOOPQ-{i:02d} synthetic open question — {H1 if i % 2 else H2} ({'ledger' if i % 3 else 'bridge'})" for i in range(36)]
    assert model["unresolved"][36] == "synthetic remaining doubt" and not any("recorded" in u or "unknown" in u for u in model["unresolved"])
    assert model["governed"]["unknowns"] == {"distinct": ["no PURCHASE_INTENT recorded", "workaround unknown"], "recorded": 8}
    assert "2 distinct of 8 recorded" in html
    assert "showing 12 of 13 clusters" in html and "showing 14 of 15 leads" in html and "showing 10 of 11 situations" in html
