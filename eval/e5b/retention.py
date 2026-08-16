"""E5B part 2 — concept retention + budget diagnostics (observational).

Reports the deterministic pre-budget rank of every psychology gold
concept under the committed concept-inventory-v1 policy (generate ->
pre-filter -> overlap -> rank), plus the budget-cutoff grid. No
policy is changed. This is diagnostic only.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.concept_inventory import (  # noqa: E402
    DOC_BUDGET_GRID,
    _pre_filter,
    admit,
    apply_overlap_policy,
    generate_candidates,
    normalize_concept_v1,
)

PSYCH_GOLD = [
    "metacognitive monitoring", "metacognitive control",
    "judgments of learning", "processing fluency", "familiarity effect",
    "illusion of competence", "working memory", "cognitive load",
    "retrieval practice", "corrective feedback",
    "self-regulated learning", "local regulation", "global regulation",
]


def chunkify(text: str) -> list[dict]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 20]
    return [{"chunk_id": "chunk_" + hashlib.sha256(s.encode()).hexdigest()[:16],
             "text": s, "summary": ""} for s in sents]


def main() -> int:
    text = (ROOT / "eval" / "e3" / "corpus" / "docs" / "metacognition.md").read_text()
    chunks = chunkify(text)
    cands = []
    for ch in chunks:
        cands.extend(generate_candidates(ch["chunk_id"], ch["text"]))
    pre = _pre_filter(cands)
    kept = apply_overlap_policy(pre)
    ranked = admit(kept, budget=10**9)  # pre-budget deterministic order

    ranks = {}
    pre_norms = {c.normalized for c in pre}
    kept_norms = {c.normalized for c in kept}
    for g in PSYCH_GOLD:
        n = normalize_concept_v1(g)
        pos = next((i + 1 for i, c in enumerate(ranked) if c.normalized == n), None)
        if pos is not None and pos <= 8:
            status = "GENERATED_AND_ADMITTED"
        elif pos is not None:
            status = "GENERATED_BUT_BUDGETED_OUT"
        elif n in kept_norms:
            status = "FILTERED_AT_ADMISSION"
        elif n in pre_norms:
            status = "OVERLAP_DROPPED"
        else:
            status = "NOT_GENERATED"
        ranks[g] = {"rank": pos, "status": status}

    cutoff = {}
    for b in DOC_BUDGET_GRID:
        admitted = [c.normalized for c in ranked[:b]]
        cutoff[f"budget_{b}"] = {
            "admitted": admitted,
            "gold_hits": [g for g in PSYCH_GOLD if normalize_concept_v1(g) in admitted],
        }

    out = {
        "gold_ranks": ranks,
        "budget_cutoff_view": cutoff,
        "pipeline_counts": {"candidates": len(cands), "pre_filtered": len(pre),
                            "post_overlap": len(kept)},
    }
    (ROOT / "eval" / "e5b" / "retention.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"gold_ranks": ranks}, indent=1))
    print("wrote eval/e5b/retention.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
