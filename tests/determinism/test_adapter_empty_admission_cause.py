"""DEFECT D1 (hit again by REAL input, 2026-09-21, run adr_47b7277c…): a research round whose receipt TrailSignal admitted
NOTHING from still produced an admission; Trail's next judgement cited that admission as the cause of its verdicts; the
runtime derived "allowed causes" from admitted rows only, refused the verdict (PHI_VERDICT_INVALID) and the run died at
L_judge. An empty admission is a governed event and must be citable. In-memory store double: no database."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _adapter_memory_store import MemoryStore
from polymath_shared.adapter import service, store as pg_store

RUN = "adr_0123456789abcdef0123"


def _store_with(admissions):
    s = MemoryStore()
    for n, admitted in enumerate(admissions):
        aid = f"hact_{n:08x}"
        s.actions[aid] = {"action_id": aid, "run_id": RUN, "status": "received"}
        s.record_admission(None, {"action_id": aid, "run_id": RUN, "admission_id": f"hadm_{n:08x}",
                                  "admitted": [{"admitted_evidence_id": f"fev_{n}_{i}", "evidence_role": "friction", "polarity": "supports"} for i in range(admitted)], "rejected": []})
    return s


def test_an_admission_that_admitted_nothing_is_still_an_allowed_cause(monkeypatch):
    assert pathlib.Path(service.__file__).is_relative_to(ROOT)
    s = _store_with([3, 0])                                   # round 1 admitted three observations, round 2 admitted none
    assert s.admission_ids(None, RUN) == ["hadm_00000000", "hadm_00000001"]
    assert s.actions["hact_00000001"]["status"] == "rejected"
    monkeypatch.setattr(service, "store", s)
    monkeypatch.setattr(s, "load_run", lambda conn, run_id: (type("S", (), {"outputs": {}})(), {}), raising=False)
    allowed = service._allowed_causes(None, RUN, {"context": {"evidence_refs": []}}, {})
    assert allowed["hadm_00000001"] == "evidence_admission" and allowed["hadm_00000000"] == "evidence_admission"


def test_another_runs_admission_is_not_this_runs_cause():
    s = _store_with([0])
    s.actions["hact_other"] = {"action_id": "hact_other", "run_id": "adr_ffffffffffffffffffff", "status": "rejected", "admission": {"admission_id": "hadm_other"}}
    assert s.admission_ids(None, RUN) == ["hadm_00000000"]


def test_the_postgres_store_reads_admissions_from_the_action_rows_too():
    import inspect
    sql = inspect.getsource(pg_store.admission_ids)
    assert "adapter_admitted_evidence" in sql and "adapter_harness_actions" in sql and "admission->>'admission_id'" in sql and "UNION" in sql
