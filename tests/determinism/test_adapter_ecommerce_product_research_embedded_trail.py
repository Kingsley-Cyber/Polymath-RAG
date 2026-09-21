"""Consolidation migration Phases 6 + 11 — the complete `ecommerce.product_research` run against the REAL embedded TrailSignal core
(`POLYMATH_TRAIL_MODE=embedded`): the existing Polymath runtime, the imported ecommerce domain (out of process) and TrailSignal's own
registry, admission, judgement, qualification and scoring code — byte-identical to A41 @ de64d84 — in ONE checkout. No daemon, no
Postgres, no Temporal, no network. The agent, the harness and its sources are scripted; nothing here is real-world evidence.

The scripted harness cites sources TrailSignal's registry has never heard of. The honest outcome is therefore a DEFENSIBLE REJECTION
("A defensible rejection is success. A software / runtime failure is not." — MIGRATION_POLICY).

Needs `packageurl` (see test_trail_core_embedded.py): run with TrailSignal's interpreter until it is added to this repo's environment.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

pytest.importorskip("packageurl", reason="TrailSignal's platform contracts need `packageurl`; add it in the merge window (ADR-TRAIL-EMBEDDING) or run with TrailSignal's interpreter")

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", pathlib.Path(__file__).resolve().parent):
    sys.path.insert(0, str(_p))

from polymath_shared.adapter import service  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402
import test_adapter_ecommerce_product_research_e2e as SCRIPT  # noqa: E402  (the scripted agent + harness; its stub TrailSignal is NOT used here)


@pytest.fixture
def embedded(monkeypatch, tmp_path):
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setenv("POLYMATH_TRAIL_MODE", "embedded")
    monkeypatch.setenv("POLYMATH_TRAIL_STORE", str(tmp_path / "trail_audit.sqlite3"))
    monkeypatch.setattr(W, "_TRAIL", None)                                     # let the worker build its own client from the mode switch
    service.reset_registry()
    SCRIPT.NEEDS.clear()
    yield store
    monkeypatch.setattr(W, "_TRAIL", None)
    service.reset_registry()


def test_a_complete_run_against_the_real_trailsignal_core_ends_in_a_defensible_rejection(embedded):
    rid, st, _actions = SCRIPT._run(SCRIPT.Agent())
    assert st.status == "completed", (st.status, st.gap, st.failure)                                       # no software / runtime failure anywhere in the chain
    import trail_signal.contexts.workflow.application.research_operations as ro
    assert pathlib.Path(ro.__file__).resolve().is_relative_to(ROOT / "governance" / "trail")              # the EMBEDDED TrailSignal code ran
    rows = {}
    for r in embedded.list_steps(None, rid):
        rows.setdefault(r["step_id"], []).append(r)
    assert all(r["status"] == "executed" for rs in rows.values() for r in rs if r["step_type"] in ("EXTERNAL_OPERATION", "DOMAIN_OPERATION"))

    # TrailSignal ADMITTED the field evidence (registered community sources) on every research round, by its own rules …
    admissions = [r["output"]["evidence_admission"] for r in rows["J_admit"]]
    assert len(admissions) == 3 and all(len(a["admitted"]) == 5 and a["rejected"] == [] for a in admissions)
    cards = rows["J_cards"][-1]["output"]
    assert cards["round"] == 3 and len(cards["field_records"]) == 15 and cards["lived_clusters"][0]["authority"] == "ANCHOR"
    assert cards["lived_clusters"][0]["independent_voices"] == 5                                          # … and the domain counted TRAILSIGNAL'S independence groups
    # … and REFUSED the fabricated product-review and supplier sources
    assert [x["reason_code"] for x in rows["Q_admit"][0]["output"]["evidence_admission"]["rejected"]] == ["SOURCE_UNREGISTERED"]
    assert {x["reason_code"] for x in rows["T_admit"][0]["output"]["evidence_admission"]["rejected"]} == {"SOURCE_ROLE_UNSUITABLE"}
    assert rows["T_leads"][0]["output"]["leads"] == [] and {c["status"] for c in rows["T_leads"][0]["output"]["sourcing_coverage"]} == {"unsourced"}

    # the supply directive is compiled by TrailSignal from the qualification's open gaps — never borrowed from another stage (M1-07)
    assert rows["S_gaps"][0]["output"]["research_directive"]["search_intents"] and rows["S_plan"][0]["output"]["governance_unchanged"] is True

    out = service.result(None, rid)["output"]
    assert len(out["product_concepts"]) == 3 and all(len(c["variations"]) >= 2 for c in out["product_concepts"])
    assert out.get("trail_scores") in ([], None) and len(out["score_refusals"]) == 3                        # TrailSignal refused to score: the ONLY scoring authority said no
    assert all(r["reason_code"] == "HARD_GATE_UNMET" and "supply" in r["detail"] for r in out["score_refusals"])
    assert {q["state"] for q in out["qualifications"]} <= {"UNPROVEN", "NO_DEFENSIBLE_BRIDGE"}
    assert out["product_opportunity"]["supply"] is None                                                   # no lead -> no supply claim in the interpretation
