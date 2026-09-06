"""B12 LATENT-COMPOSITION-V1 — WILDCARD finish under load: skipped frontier reported, bridges carry `verified`,
unverified bridges built without the judge and never from evidence chunks."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))


def test_divergent_finish_reports_the_skipped_frontier_and_bridges_carry_verified():
    """B12: when the deadline stops validation, the skipped parents are returned in frontier order so the caller can
    ship them UNVERIFIED; validated bridges carry verified=True."""
    from polymath_shared.divergent import DivergentPlan, divergent_finish
    parents = {f"p{i}": {"parent_id": f"p{i}", "doc_id": f"d{i}", "source_name": f"S{i}.md", "hop1": 0.9 - 0.1 * i,
                         "channels": ["abstraction"], "abstraction": f"principle {i}", "transfer": ""} for i in range(4)}
    clock = {"t": 0.0}

    def tick():
        return clock["t"]

    def children_of(pid):
        clock["t"] += 0.5                       # each validation costs 0.5 s of the fake clock
        return [{"payload": {"chunk_id": f"{pid}-k", "text": f"child of {pid} about force", "source_name": "S.md"}}]

    w = divergent_finish("force and intent", parents, children_of=children_of, baseline={"parent_ids": set(), "doc_ids": set(), "chunk_ids": set()},
                         rerank_pairs=lambda a, texts: [0.9 for _ in texts], plan=DivergentPlan(max_bridges=3), deadline=1.0, clock=tick)
    d = w["diagnostics"]
    assert d["partial"] is True and d["parents_validated"] >= 1 and d["parents_skipped"] == len(d["skipped_parents"]) > 0
    assert [s["parent_id"] for s in d["skipped_parents"]] == [f"p{i}" for i in range(d["parents_validated"], 4)]
    assert all(b["verified"] is True for b in w["wildcard"])


def test_unverified_bridges_are_built_from_skipped_parents_without_the_judge_and_never_from_evidence_chunks():
    import time
    from polymath_shared.divergent import DivergentPlan
    from orchestrator.api.chat_retrieval import _unverified_bridges
    slots = [{"parent_id": "pA", "doc_id": "dA", "source_name": "A.md", "hop1": 0.8, "channels": ["abstraction"], "abstraction": "principle A", "transfer": "why A"},
             {"parent_id": "pB", "doc_id": "dB", "source_name": "B.md", "hop1": 0.9, "channels": ["transfer"], "abstraction": "", "transfer": "principle B"},
             {"parent_id": "pOBV", "doc_id": "dO", "source_name": "O.md", "hop1": 0.95, "channels": ["abstraction"], "abstraction": "obvious", "transfer": ""}]

    def children_of(pid):
        if pid == "pA":
            return [{"payload": {"chunk_id": "ev1", "text": "already in evidence"}}, {"payload": {"chunk_id": "a-k", "text": "the body reads force", "source_name": "A.md"}}]
        return [{"payload": {"chunk_id": f"{pid}-k", "text": f"child of {pid}", "source_name": f"{pid}.md"}}]

    out = _unverified_bridges(slots, children_of=children_of, baseline={"parent_ids": {"pOBV"}, "doc_ids": set(), "chunk_ids": {"ev1"}},
                              quota=3, fill_deadline=time.perf_counter() + 5, plan=DivergentPlan(), qtoks={"force"})
    assert [b["parent_id"] for b in out] == ["pB", "pA"]                                  # obvious parent excluded, hop1 order
    assert all(b["verified"] is False and b["scores"]["source_support"] is None for b in out)
    assert out[1]["source_evidence"]["chunk_id"] == "a-k"                                    # the evidence chunk was skipped
    assert out[0]["principle"] == "principle B" and out[1]["why_it_may_transfer"] == "why A"
    assert _unverified_bridges(slots, children_of=children_of, baseline={}, quota=0, fill_deadline=time.perf_counter() + 5, plan=DivergentPlan(), qtoks=set()) == []
