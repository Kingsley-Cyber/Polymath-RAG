"""I4 CANONICAL-IDENTITY SCORE v1 — supplements, never replaces.

The frozen I4 surface scorer matches endpoint STRINGS. After PHASE 3
resolves identity, two facts whose endpoints share canonical IDs are the
same assertion for the graph, while the surface scorer still reports
"different string -> wrong". That is an evaluation representation
mismatch, not an extraction error.

    SURFACE   depends_on(CareConnect portal -> CareChart EMR platform)
              != gold "CareChart EMR"

    IDENTITY  depends_on(ent_careconnect_portal -> ent_carechart_emr...)
              == gold canonical endpoint

This metric is SEPARATELY VERSIONED. `eval/i4/verify_i4.py` and its frozen
artifacts are untouched, and the historical surface number stays
comparable. Neither metric overrides the other; they answer different
questions.

Usage: .venv/bin/python eval/doc_audit/i4_identity_score.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.contraction_resolution import (  # noqa: E402
    build_memberships, canonical_id_for,
)

METRIC = "i4-canonical-identity-score-v1"
DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i4-fresh-acceptance-v1"


def _norm(s: str) -> str:
    return " ".join(str(s).lower().replace("-", " ").split())


def main() -> int:
    gold = json.loads((ROOT / "eval/i4/gold/fact_gold.json").read_text()
                      )["supported_positive"]["facts"]
    c = psycopg.connect(DSN)
    docs = {r[0]: r[1].split("/")[-1] for r in c.execute(
        "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s",
        (CORPUS,)).fetchall()}
    admitted = {d: [(r[0], r[1]) for r in c.execute(
        "SELECT DISTINCT surface, core_type FROM mentions "
        "WHERE doc_id=%s AND admission_class!='MENTION_ONLY'", (d,)).fetchall()]
        for d in docs}
    rows = c.execute("""
        SELECT f.predicate, s.normalized_surface, o.normalized_surface, ev.doc_id
          FROM facts f
          JOIN entities s ON s.entity_id=f.subject_id
          JOIN entities o ON o.entity_id=f.object_id
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN documents d ON d.doc_id=ev.doc_id
         WHERE d.corpus_id=%s""", (CORPUS,)).fetchall()
    c.close()

    # one canonical map per document, keyed by normalized surface
    cmap: dict[str, dict[str, str]] = {}
    for doc_id, name in docs.items():
        m = build_memberships(admitted[doc_id])
        cmap[name] = {_norm(s): v.canonical_id for s, v in m.items()}

    def canon(surface: str, doc: str) -> str:
        return cmap.get(doc, {}).get(_norm(surface)) or canonical_id_for(surface)

    surface_gold = {(g["predicate"], _norm(g["subject"]), _norm(g["object"]))
                    for g in gold}
    ident_gold = set()
    for g in gold:
        doc = next((n for n in docs.values() if n.endswith(g["doc"])), g["doc"])
        ident_gold.add((g["predicate"], canon(g["subject"], doc),
                        canon(g["object"], doc)))

    s_tp = s_fp = i_tp = i_fp = 0
    recovered = []
    for pred, subj, obj, doc_id in rows:
        doc = docs[doc_id]
        s_hit = (pred, _norm(subj), _norm(obj)) in surface_gold
        i_hit = (pred, canon(subj, doc), canon(obj, doc)) in ident_gold
        s_tp += s_hit; s_fp += not s_hit
        i_tp += i_hit; i_fp += not i_hit
        if i_hit and not s_hit:
            recovered.append(f"{pred}({subj} -> {obj})")

    print(f"metric: {METRIC}   (supplements the frozen surface score; "
          f"verify_i4.py untouched)\n")
    print(f"  SURFACE  TP {s_tp:<3} FP {s_fp:<3} P {s_tp/(s_tp+s_fp):.3f}   "
          f"R {s_tp/len(gold):.3f}   <- historical, frozen")
    print(f"  IDENTITY TP {i_tp:<3} FP {i_fp:<3} P {i_tp/(i_tp+i_fp):.3f}   "
          f"R {i_tp/len(gold):.3f}   <- graph-semantic")
    if recovered:
        print("\n  assertions the graph gets right but surface matching scores wrong:")
        for r in recovered:
            print(f"    {r}")
    merged = {}
    for name, m in cmap.items():
        for surf, cid in m.items():
            merged.setdefault((name, cid), []).append(surf)
    clusters = {k: v for k, v in merged.items() if len(v) > 1}
    print(f"\n  canonical clusters formed: {len(clusters)}")
    for (name, cid), members in sorted(clusters.items()):
        print(f"    {name:<32} {cid:<34} {sorted(members)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
