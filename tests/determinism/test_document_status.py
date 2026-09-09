"""CANONICAL-DOCUMENT-STATUS-V1 (RAG-PIPELINE-FINISH Phase 12) — blocker logic.

Provider-free, DB-free: a scripted fake connection drives document_status (and the
vnext_readiness it calls) through a COMPLETE document and a pMAP-STALLED document, and
asserts the canonical aggregate + the ordered blocker list a failed canary reads.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_status import document_status  # noqa: E402


class _Cur:
    def __init__(self, one=None, all_=None):
        self._one, self._all = one, all_

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all or []


class _FakeConn:
    """Dispatches by distinctive SQL fragments. `scn` selects the scenario."""
    def __init__(self, scn):
        self.scn = scn

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        scn = self.scn
        if "FROM documents WHERE doc_id" in s:
            return _Cur(one=("docA", "corpA", "a.txt", "text/plain"))
        if "FROM runs WHERE corpus_id" in s:
            return _Cur(all_=[("runA", "query_ready")])
        if "tier='child'" in s:
            return _Cur(one=(8,))
        if "COUNT(*) FROM chunks WHERE doc_id=%s AND tier='parent'" in s and "region_role" not in s:
            return _Cur(one=(3,))
        if "FROM stage_tickets WHERE run_id" in s:
            return _Cur(all_=scn["stages"])
        if "a.payload->'doc_profile' FROM artifacts" in s:
            return _Cur(one=(scn["profile"],))
        if "to_regclass('public.document_parent_maps')" in s:
            return _Cur(one=("document_parent_maps",))
        # document_status eligible (no JOIN documents)
        if "FROM chunks WHERE doc_id=%s AND tier='parent' AND COALESCE(region_role" in s:
            return _Cur(one=(3,))
        if "COUNT(DISTINCT parent_id) FROM document_parent_maps WHERE doc_id" in s:
            return _Cur(one=(scn["mapped"],))
        if "FROM document_parent_exclusions WHERE doc_id" in s:
            return _Cur(one=(0,))
        if "FROM document_parent_map_batches WHERE doc_id" in s:
            return _Cur(one=(1, scn["b_done"], scn["b_partial"]))
        # vnext_readiness queries (JOIN documents)
        if "FROM chunks c JOIN documents d" in s:
            return _Cur(one=(3,))          # eligible
        if "FROM document_parent_maps m JOIN documents d" in s:
            return _Cur(one=(scn["mapped"],))   # mapped
        if "FROM document_parent_exclusions e JOIN documents d" in s:
            return _Cur(one=(0,))
        if "a.payload->'doc_profile'->>'vnext'='true'" in s:
            return _Cur(one=(scn["vnext_profiles"],))
        if "COUNT(*) FROM documents WHERE corpus_id" in s:
            return _Cur(one=(1,))
        raise AssertionError(f"unscripted SQL: {s[:90]}")


_DONE_STAGES = [("intake", "done", 0, None), ("extract", "done", 0, None),
                ("doc_profile", "done", 0, None), ("doc_parent_map", "done", 0, None)]

_COMPLETE = {"stages": _DONE_STAGES, "profile": {"doc_id": "docA", "valid": True, "vnext": "true", "quality": 0.9},
             "mapped": 3, "b_done": 1, "b_partial": 0, "vnext_profiles": 1}

_PMAP_STALLED = {"stages": _DONE_STAGES[:3] + [("doc_parent_map", "ready", 0, None)],
                 "profile": {"doc_id": "docA", "valid": True, "vnext": "true", "quality": 0.9},
                 "mapped": 1, "b_done": 0, "b_partial": 1, "vnext_profiles": 1}


def test_complete_document_has_no_blockers():
    st = document_status(_FakeConn(_COMPLETE), doc_id="docA")
    assert st["found"] and st["complete"] is True
    assert st["blockers"] == []
    assert st["state"]["vnext_verdict"] == "VNEXT_COMPLETE"
    assert st["pmap"]["mapped_active"] == 3 and st["pmap"]["unresolved"] == 0
    assert st["profile"]["present"] and st["profile"]["valid"] and st["profile"]["vnext"]
    assert st["chunks"] == {"children_total": 8, "parents_total": 3}
    # the functional-pool health rides along (config truth)
    assert "PMAP" in st["functional_pools"]


def test_pmap_stalled_document_names_the_blocker_first():
    st = document_status(_FakeConn(_PMAP_STALLED), doc_id="docA")
    assert st["complete"] is False
    # the pMAP shortfall is surfaced with exact counts, and vNext is INCOMPLETE
    assert any(b.startswith("pmap_unresolved:2_of_3") for b in st["blockers"])
    assert any(b.startswith("vnext_vnext_incomplete") for b in st["blockers"])
    assert st["pmap"]["unresolved"] == 2 and st["pmap"]["batches_partial"] == 1
    # a non-blocking doc_parent_map ticket that is merely 'ready' is NOT reported as a
    # generic stage_incomplete blocker (its shortfall shows as pmap_unresolved instead).
    assert not any(b == "stage_incomplete:doc_parent_map:ready" for b in st["blockers"])


def test_missing_document():
    class _Empty:
        def execute(self, *a, **k):
            return _Cur(one=None)
    st = document_status(_Empty(), doc_id="ghost")
    assert st["found"] is False and st["blockers"] == ["no_document"]
