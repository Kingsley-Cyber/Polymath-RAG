"""Single-document quality audit harness (see PLAN.md).

Captures per-arm, per-document extraction output to its OWN path so arms
can be diffed at the fact level. `verify_i4.py` overwrites one shared
evidence.json; this does not.

Usage:
  .venv/bin/python eval/doc_audit/harness.py --arm CONTROL
  .venv/bin/python eval/doc_audit/harness.py --compare CONTROL VAR-BIND VAR-CHUNK
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
OUT = ROOT / "eval" / "doc_audit" / "arms"
CORPUS = "i4-fresh-acceptance-v1"
DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _norm(s: str) -> str:
    return " ".join(str(s).lower().replace("-", " ").split())


def _fragment_pairs(surfaces: list[str]) -> list[list[str]]:
    """Admitted entities where one surface is a strict word-prefix of
    another — i.e. the same referent split across two graph nodes."""
    pairs = []
    for a in surfaces:
        for b in surfaces:
            if a == b:
                continue
            wa, wb = _norm(a).split(), _norm(b).split()
            if len(wa) < len(wb) and wb[:len(wa)] == wa:
                pairs.append([a, b])
    return sorted(pairs)


def collect(arm: str) -> dict:
    import psycopg
    key = json.loads((ROOT / "eval/doc_audit/KEY_B.json").read_text())["documents"]
    gold = json.loads((ROOT / "eval/i4/gold/fact_gold.json").read_text())
    gold_facts = gold["supported_positive"]["facts"]

    c = psycopg.connect(DSN)
    docs = c.execute(
        "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s ORDER BY source_name",
        (CORPUS,)).fetchall()
    result = {"arm": arm, "config": {
        "relation_pipeline": os.environ.get("POLYMATH_RELATION_PIPELINE", "legacy_v1"),
        "chunker": os.environ.get("POLYMATH_CHUNKER", "legacy_v1"),
        "rescue": os.environ.get("POLYMATH_RESCUE", "off"),
        "rule_pack": os.environ.get("POLYMATH_WORKER_RULE_PACK_VERSION", "1.2.0"),
        "syntax": os.environ.get("POLYMATH_SYNTAX_PROVIDER", "disabled"),
    }, "documents": {}}

    for doc_id, source in docs:
        name = source.split("/")[-1]
        facts = c.execute("""
            SELECT f.predicate, s.normalized_surface, s.core_type, s.admission_class,
                   o.normalized_surface, o.core_type, o.admission_class, f.decision
              FROM facts f
              JOIN entities s ON s.entity_id=f.subject_id
              JOIN entities o ON o.entity_id=f.object_id
              JOIN evidence ev ON ev.fact_id=f.fact_id
             WHERE ev.doc_id=%s ORDER BY f.predicate, 2, 5""", (doc_id,)).fetchall()
        mentions = c.execute("""
            SELECT normalized_surface, core_type, admission_class, gliner_score
              FROM mentions WHERE doc_id=%s ORDER BY gliner_score DESC""", (doc_id,)).fetchall()

        emitted = [{"predicate": f[0], "subject": f[1], "subject_type": f[2],
                    "subject_admission": f[3], "object": f[4], "object_type": f[5],
                    "object_admission": f[6], "decision": f[7]} for f in facts]

        # Key A: gold rows scoped to this document
        dgold = [g for g in gold_facts if name.endswith(g["doc"])]
        tp = [g for g in dgold if any(
            e["predicate"] == g["predicate"] and _norm(e["subject"]) == _norm(g["subject"])
            and _norm(e["object"]) == _norm(g["object"]) for e in emitted)]
        matched = {(g["predicate"], _norm(g["subject"]), _norm(g["object"])) for g in tp}
        fp = [e for e in emitted
              if (e["predicate"], _norm(e["subject"]), _norm(e["object"])) not in matched]

        # Key B: which wanted facts appeared (predicate + both endpoints, order-free
        # on the endpoints so a direction flip still counts as "found")
        want = key.get(name, {}).get("wanted", [])
        found = []
        for w in want:
            hit = any(e["predicate"] == w["predicate"] and
                      {_norm(e["subject"]), _norm(e["object"])} ==
                      {_norm(w["subject"]), _norm(w["object"])} for e in emitted)
            found.append({**w, "found": hit})

        admitted = [m[0] for m in mentions if m[2] != "MENTION_ONLY"]
        result["documents"][name] = {
            "emitted": emitted,
            "emitted_count": len(emitted),
            "gold_scoped": {"gold": len(dgold), "tp": len(tp), "fp": len(fp),
                            "fn": len(dgold) - len(tp)},
            "key_b": {"wanted": len(want), "found": sum(1 for f in found if f["found"]),
                      "detail": found},
            "mentions": [{"surface": m[0], "type": m[1], "admission": m[2],
                          "score": float(m[3])} for m in mentions],
            "fragment_pairs": _fragment_pairs(admitted),
        }

    ents = c.execute(
        "SELECT COUNT(*) FROM canonical_memberships WHERE corpus_id=%s", (CORPUS,)).fetchone()[0]
    clus = c.execute(
        "SELECT COUNT(*) FROM canonical_entities WHERE corpus_id=%s", (CORPUS,)).fetchone()[0]
    result["canonicalization"] = {"entities": ents, "clusters": clus,
                                  "merged": ents - clus}
    c.close()
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm")
    ap.add_argument("--compare", nargs="*")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.arm:
        r = collect(a.arm)
        p = OUT / f"{a.arm}.json"
        p.write_text(json.dumps(r, indent=1))
        tot = sum(d["emitted_count"] for d in r["documents"].values())
        print(f"{a.arm}: {tot} facts across {len(r['documents'])} docs -> {p}")
        print(f"  config: {r['config']}")
        print(f"  canonicalization merged: {r['canonicalization']['merged']}")
        return 0
    if a.compare:
        arms = {n: json.loads((OUT / f"{n}.json").read_text()) for n in a.compare}
        names = sorted(next(iter(arms.values()))["documents"])
        print(f"{'document':<32} " + " ".join(f"{n:>26}" for n in a.compare))
        for d in names:
            cells = []
            for n in a.compare:
                x = arms[n]["documents"][d]
                g = x["gold_scoped"]
                cells.append(f"{x['emitted_count']:>2}f {g['tp']}tp/{g['fp']}fp "
                             f"KB{x['key_b']['found']}/{x['key_b']['wanted']}")
            print(f"{d:<32} " + " ".join(f"{c:>26}" for c in cells))
        print()
        for n in a.compare:
            r = arms[n]
            tot = sum(x["emitted_count"] for x in r["documents"].values())
            tp = sum(x["gold_scoped"]["tp"] for x in r["documents"].values())
            fp = sum(x["gold_scoped"]["fp"] for x in r["documents"].values())
            kb = sum(x["key_b"]["found"] for x in r["documents"].values())
            kbw = sum(x["key_b"]["wanted"] for x in r["documents"].values())
            frag = sum(len(x["fragment_pairs"]) for x in r["documents"].values())
            print(f"{n:<12} facts={tot:<4} gold TP={tp:<3} FP={fp:<3} "
                  f"KeyB={kb}/{kbw}  fragments={frag}  merged={r['canonicalization']['merged']}")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
