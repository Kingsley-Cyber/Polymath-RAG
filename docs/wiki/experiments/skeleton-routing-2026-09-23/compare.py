"""SKELETON-ROUTING-V1 live comparison ($0): this morning's five live turns (flags off, RETRIEVAL-PATHWAYS-5Q results.json)
against the same five questions after the flags were switched on (live_results.json). Reuses the pathway analyzer."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE.parent / "retrieval-pathways-2026-09-23"
spec = importlib.util.spec_from_file_location("pathways_analyze", BASE / "analyze.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)                                   # type: ignore[union-attr]
SKELETON = ("latent_rescue", "dualread", "seealso_fanout", "graph_dest")


def _row(t: dict) -> dict:
    s = A.summarize(t)
    f = s["funnel"]
    rt = ((t.get("receipt") or {}).get("meta") or {}).get("retrieval_trace") or {}
    return {"mode": s["mode"], "wall_s": s["wall_s"], "status": (s["receipt"] or {}).get("status"),
            "lane_counts": {k: (f["lane_counts"] or {}).get(k) for k in SKELETON},
            "skeleton_final": sum((f["lane_in_final"] or {}).get(k, 0) for k in SKELETON),
            "skeleton_cited": sum((f["lane_in_cited"] or {}).get(k, 0) for k in SKELETON),
            "cited": (f["counts"] or {}).get("cited"), "final_docs": len(s["final_docs"]), "cited_docs": len(s["cited_docs"]),
            "route_aspects": sorted(k for k in (rt.get("aspects") or {}) if str(k).startswith("rt:")),
            "latent_selection": (s["latent_selection"] or {}).get("counts"),
            "latent_labels": (s["prompt"] or {}).get("latent_labels"),
            "atom_frontier": ((s["wildcard"] or {}).get("atom_frontier")),
            "answer_head": s["answer_head"][:300]}


def main() -> int:
    before = [_row(t) for t in json.loads((BASE / "results.json").read_text())]
    after = [_row(t) for t in json.loads((HERE / "live_results.json").read_text())]
    out = []
    for b, a in zip(before, after):
        out.append({"before": b, "after": a})
        print(f"\n=== {a['mode']}  wall {b['wall_s']}s → {a['wall_s']}s  status {a['status']}")
        for k in ("lane_counts", "skeleton_final", "skeleton_cited", "cited", "final_docs", "cited_docs"):
            print(f"  {k:15s} {b[k]}  →  {a[k]}")
        print(f"  route aspects: {a['route_aspects']} | latent seats: {a['latent_selection']} | latent labels: {a['latent_labels']}"
              f" | atom frontier: {a['atom_frontier']}")
        print(f"  answer: {a['answer_head'][:220]}")
    (HERE / "live_compare.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
