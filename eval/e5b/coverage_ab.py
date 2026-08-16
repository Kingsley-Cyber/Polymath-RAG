"""E5B part 2 — R1A coverage A/B on the frozen coverage fixture.

A = retrieval-summary-v2 (qualified) doc + section summaries.
B = retrieval-summary-v2 + bounded concept-inventory-v1 serialization
under routing-concept-enriched-v1.

Same metrics as the frozen R1A coverage measure (concept / section
theme / late-content coverage, redundancy). No summary algorithm is
changed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from workers.summarizer import summarize, summarize_children  # noqa: E402
from polymath_shared.concept_inventory import (  # noqa: E402
    document_inventory,
    enriched_representation,
    section_inventory,
)
from polymath_shared.retrieval_summaries import (  # noqa: E402
    document_retrieval_summary,
    section_retrieval_summary,
)

FIXTURE = ROOT / "eval" / "r1a" / "coverage"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]


def concept_hits(text: str, concepts: list[str]) -> tuple[int, int]:
    lowered = text.lower()
    found = sum(1 for c in concepts if c.lower() in lowered)
    return found, len(concepts)


def redundancy_ratio(text: str) -> float:
    toks = [re.findall(r"[a-z0-9]+", s.lower()) for s in _sentences(text)]
    if len(toks) <= 1:
        return 0.0
    dup = 0
    for i, t in enumerate(toks):
        for p in toks[:i]:
            if p and len(set(t) & set(p)) / max(1, len(set(t) | set(p))) >= 0.8:
                dup += 1
                break
    return dup / len(toks)


def main() -> int:
    inventory = json.loads((FIXTURE / "inventory.json").read_text())["documents"]
    results = []
    for name, inv in sorted(inventory.items()):
        text = (FIXTURE / "docs" / name).read_text()
        sentences = _sentences(text)
        sections: list[list[str]] = []
        current: list[str] = []
        for s in sentences:
            if s.startswith("#") or len(s) < 60 and re.match(r"^[A-Z][^.]{5,55}$", s):
                if current:
                    sections.append(current)
                current = []
            else:
                current.append(s)
        if current:
            sections.append(current)
        parents = [{"chunk_id": f"p{i}", "summary": " ".join(sec), "text": " ".join(sec)}
                   for i, sec in enumerate(sections)]
        children_groups = [[{"chunk_id": f"c{i}j", "text": s} for s in sec]
                           for i, sec in enumerate(sections)]

        # A: qualified retrieval-summary-v2
        v2_doc, _ = document_retrieval_summary(parents, doc_id=name)
        v2_sections = " ".join(
            section_retrieval_summary(g, parent_id=f"p{i}")[0]
            for i, g in enumerate(children_groups)
        )

        # B: v2 + bounded concept inventory
        all_children = [c for g in children_groups for c in g]
        doc_concepts = document_inventory(all_children)
        b_doc = enriched_representation(v2_doc, doc_concepts)
        b_sections = " ".join(
            enriched_representation(
                section_retrieval_summary(g, parent_id=f"p{i}")[0],
                section_inventory(g),
            )
            for i, g in enumerate(children_groups)
        )

        def metrics(doc_summ, sec_summ):
            dc, dt = concept_hits(doc_summ + " " + sec_summ, inv["concepts"])
            sc, st = concept_hits(sec_summ, inv["section_themes"])
            lc, lt = concept_hits(doc_summ, inv["late_concepts"])
            return {
                "concept_coverage": round(dc / dt, 3),
                "section_theme_coverage": round(sc / st, 3),
                "late_content_coverage": round(lc / lt, 3),
                "redundancy": round(redundancy_ratio(sec_summ), 3),
                "size_chars": len(doc_summ) + len(sec_summ),
            }

        results.append({
            "document": name,
            "A": metrics(v2_doc, v2_sections),
            "B": metrics(b_doc, b_sections),
        })

    agg = {
        "documents": len(results),
        "A": {k: round(sum(r["A"][k] for r in results) / len(results), 3)
              for k in results[0]["A"]},
        "B": {k: round(sum(r["B"][k] for r in results) / len(results), 3)
              for k in results[0]["B"]},
    }
    out = {"aggregate": agg, "per_document": results}
    (ROOT / "eval" / "e5b" / "coverage_ab.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(agg, indent=1))
    print("wrote eval/e5b/coverage_ab.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
