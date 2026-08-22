"""Explain FactAdmission's decision for specific candidates.

Development tool. Prints, for each matching fact: the evidence window,
the parse, the syntactic roles the gates saw, and every gate verdict —
so a wrong admission is diagnosed from evidence rather than guessed at.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(ROOT, "shared"), os.path.join(ROOT, "workers"),
                os.path.dirname(os.path.abspath(__file__))]

import psycopg  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--match", action="append", required=True,
                    help="substring of 'predicate(subject, object)'")
    a = ap.parse_args()

    import fact_admission_shadow as SH
    from polymath_shared.fact_admission import GATES, FactContext, admit
    from polymath_shared.rulepack.compiler import load_rule_pack
    from polymath_shared.source_region import region_at

    pack = load_rule_pack()
    conn = psycopg.connect(SH.DSN)
    rows = SH.load_candidates(conn, a.corpus)
    layout = SH.load_layout(conn, a.corpus)

    for r in rows:
        off = r["offsets"] if isinstance(r["offsets"], dict) else {}
        s_start, s_end = off.get("subject_start"), off.get("subject_end")
        o_start, o_end = off.get("object_start"), off.get("object_end")
        r["region"] = "BODY_PROSE"
        r["sentence_text"], r["sentence_start"] = None, 0
        if s_start is not None and o_start is not None:
            lo, hi = min(s_start, o_start), max(s_end or s_start, o_end or o_start)
            r["region"] = region_at(r["chunk_text"], lo, hi, layout.get(r["doc_id"]))
            r["sentence_text"], r["sentence_start"] = SH.sentence_window(
                r["chunk_text"], lo, hi)

    wanted = []
    for r in rows:
        label = (f"{r['predicate']}({(r['subject_surface'] or '').lower()}, "
                 f"{(r['object_surface'] or '').lower()})")
        if any(m.lower() in label for m in a.match):
            wanted.append(r)
    print(f"matched {len(wanted)} candidates")
    SH.attach_parses(wanted)

    for r in wanted:
        off = r["offsets"] if isinstance(r["offsets"], dict) else {}
        prov = r["provenance"] if isinstance(r["provenance"], dict) else {}
        ctx = FactContext(
            doc_id=r["doc_id"], chunk_id=r["chunk_id"], predicate=r["predicate"],
            subject_entity_id=r["subject_id"], object_entity_id=r["object_id"],
            subject_type=r["subject_type"], object_type=r["object_type"],
            subject_admission_class=r["subject_class"],
            object_admission_class=r["object_class"],
            subject_surface=r["subject_surface"], object_surface=r["object_surface"],
            trigger_surface=r["trigger_surface"],
            trigger_lemma=(off.get("trigger_lemma") or prov.get("trigger_lemma")),
            evidence_class=r["evidence_class"],
            subject_start=off.get("subject_start"), subject_end=off.get("subject_end"),
            object_start=off.get("object_start"), object_end=off.get("object_end"),
            evidence_start=off.get("evidence_start"), evidence_end=off.get("evidence_end"),
            chunk_text=r["chunk_text"], region=r["region"], parse=r.get("parse"),
            scope=(prov.get("scope") or {}), sentence_start=r["sentence_start"])

        print("=" * 78)
        print(f"{r['predicate']}({r['subject_surface']}, {r['object_surface']})")
        print(f"  region={r['region']} trigger_lemma={ctx.trigger_lemma!r} "
              f"trigger_surface={ctx.trigger_surface!r} class={r['evidence_class']}")
        print(f"  types: {r['subject_type']} -> {r['object_type']}   "
              f"scope={ctx.scope}")
        print(f"  sentence: {(r['sentence_text'] or '')[:200]!r}")
        if ctx.parse:
            toks = ctx.parse.get("tokens") or []
            print(f"  parse ({len(toks)} tokens):")
            for t in toks[:40]:
                mark = ""
                cs = t.get("char_start")
                if cs is not None:
                    absolute = cs + ctx.sentence_start
                    if ctx.subject_start is not None and ctx.subject_start <= absolute < (ctx.subject_end or 0):
                        mark = " <SUBJ>"
                    elif ctx.object_start is not None and ctx.object_start <= absolute < (ctx.object_end or 0):
                        mark = " <OBJ>"
                    elif ctx.evidence_start is not None and ctx.evidence_start <= absolute < (ctx.evidence_end or 0):
                        mark = " <TRIG>"
                print(f"     i={t.get('i'):<3} {str(t.get('text'))[:16]:16s} "
                      f"{str(t.get('pos')):6s} {str(t.get('dep')):10s} "
                      f"head={t.get('head_i')}{mark}")
        else:
            print("  parse: NONE")
        for name, gate in GATES:
            v = gate(ctx, pack)
            print(f"  {name:14s} {v.outcome:8s} {v.reason or ''} {v.detail or ''}")
        d = admit(ctx, pack)
        print(f"  => {d.outcome} {d.reason or ''} (gate {d.gate}) flipped={d.flipped}")


if __name__ == "__main__":
    main()
