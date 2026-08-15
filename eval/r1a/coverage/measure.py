"""R1A coverage qualification: v1 (current) vs v2 (candidate) summaries.

Measures concept coverage, section-theme coverage, late-document
coverage, redundancy, and size against the frozen authored inventory.
Deterministic; no stores.

v1 document summary = current profile semantic_summary algorithm
   (extractive centroid, max 5 sentences / 1100 chars over parent
   texts — the same summarize() call the profile builder uses).
v1 section summary  = current parent summarize_children centroid.
v2 = polymath_shared.retrieval_summaries (R1A contract).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from workers.summarizer import summarize, summarize_children  # noqa: E402
from polymath_shared.retrieval_summaries import (  # noqa: E402
    document_retrieval_summary,
    section_retrieval_summary,
)

FIXTURE = ROOT / "eval" / "r1a" / "coverage"


def _sentences(text: str) -> list[str]:
    import re
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]


def concept_hits(text: str, concepts: list[str]) -> tuple[int, int]:
    lowered = text.lower()
    found = sum(1 for c in concepts if c.lower() in lowered)
    return found, len(concepts)


def redundancy_ratio(text: str) -> float:
    """Fraction of sentences that are near-duplicates of an earlier one."""
    import re as _re
    toks = [_re.findall(r"[a-z0-9]+", s.lower()) for s in _sentences(text)]
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
        # section split: heading lines mark sections; single-section docs
        # have one pseudo-parent over the whole doc
        import re
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
        children_groups = [[{"chunk_id": f"c{i}j", "text": s} for s in sec] for i, sec in enumerate(sections)]

        # v1
        v1_doc = summarize(" ".join(p["summary"] for p in parents), max_sentences=5, max_chars=1100)
        v1_sections = [summarize_children([c["text"] for c in g]) for g in children_groups]
        v1_all_sections = " ".join(v1_sections)

        # v2
        v2_doc, _ = document_retrieval_summary(parents, doc_id=name)
        v2_sections = " ".join(
            section_retrieval_summary(g, parent_id=f"p{i}")[0]
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
            "v1": metrics(v1_doc, v1_all_sections),
            "v2": metrics(v2_doc, v2_sections),
        })

    agg = {"documents": len(results),
           "v1": {k: round(sum(r["v1"][k] for r in results) / len(results), 3)
                  for k in results[0]["v1"]},
           "v2": {k: round(sum(r["v2"][k] for r in results) / len(results), 3)
                  for k in results[0]["v2"]}}
    out = {"aggregate": agg, "per_document": results}
    (ROOT / "eval" / "r1a" / "coverage_result.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(agg, indent=1))
    for r in results:
        print(f"  {r['document']:28} v1={r['v1']}  v2={r['v2']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
