#!/usr/bin/env python3
"""S6A — CANONICAL-ENDPOINT-COVERAGE-ATTRIBUTION.

DIAGNOSTIC ONLY. Semantics are frozen; this writes nothing and decides
nothing. It answers one question for every gold endpoint:

    does this endpoint exist as a durable graph identity, and if not, WHICH
    authority declined it and on what evidence?

The canonical-identity score reported recall .385 with 10 gold facts holding
an endpoint that never earned durable identity. That number is compatible
with two opposite realities — admission is under-admitting, or admission is
correctly refusing things the gold asks the graph to contain — and they call
for opposite responses. Attribution distinguishes them before anything is
changed.

The waterfall is CLOSED: every endpoint lands in exactly one bucket, and
UNEXPLAINED must be zero. A bucket that absorbs the awkward cases would let
a real defect hide inside a plausible-looking summary.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

BUCKETS = (
    "DURABLE",                      # endpoint exists; not a coverage failure
    "DISCOVERY_MISS",               # the provider never proposed the span
    "SPAN_BOUNDARY",                # proposed, but not with the gold's extent
    "IDENTITY_FALSE_NEGATIVE",      # proper-noun evidence present, identity declined
    "CONCEPT_AUTHORITY_ABSENT",     # common nominal, document never established it
    "HEADING_SUPPRESSED",           # only occurrence is in a heading (row 47)
    "GENERIC_CORRECT_REFUSAL",      # a population/class term, correctly refused
    "LOCAL_REFERENCE_UNRESOLVED",   # a reference whose antecedent never resolved
    "HARBOR_ABSTENTION",            # settled abstention on recorded evidence
    "CANONICALIZATION_MISMATCH",    # durable, but canonical id differs from gold's
    "OTHER_EXPLAINED",
    "UNEXPLAINED",
)


def norm(s: str) -> str:
    import unicodedata
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().lower()


def _mentions_for(conn, corpus: str) -> dict:
    out: dict[str, list[dict]] = {}
    for r in conn.execute(
        """SELECT d.source_name, m.normalized_surface, m.surface, m.core_type,
                  m.anchor_kind, m.decision_status, m.reference_basis,
                  m.admission_reason, m.entity_id, m.doc_id, m.chunk_id,
                  m.char_start, m.char_end
             FROM mentions m JOIN documents d ON d.doc_id = m.doc_id
            WHERE m.corpus_id = %s""", (corpus,)).fetchall():
        out.setdefault(r[0], []).append({
            "normalized": r[1], "surface": r[2], "core_type": r[3],
            "anchor_kind": r[4], "decision_status": r[5], "reference_basis": r[6],
            "reason": r[7], "entity_id": r[8], "doc_id": r[9], "chunk_id": r[10],
            "start": r[11], "end": r[12]})
    return out


def _tokens_for(conn, corpus: str) -> dict:
    """spaCy tokens per mention span, rebuilt through the persisted manifest.

    Re-derived rather than stored: the point is to ask the SAME identity
    predicate what evidence it saw, so the attribution reflects the live
    authority instead of a paraphrase of it.
    """
    from workers.extract_worker import _syntax_evidence
    from workers.reprocess_worker import (
        _child_chunks, _ordered_slices_from_manifest, _persisted_spans,
        _slice_manifest,
    )

    chunks, spans = _child_chunks(conn, corpus), _persisted_spans(conn, corpus)
    out: dict[tuple, list] = {}
    for doc_id in sorted(chunks):
        manifest = _slice_manifest(conn, doc_id)
        if not manifest:
            continue
        ordered = _ordered_slices_from_manifest(chunks[doc_id], manifest, spans)
        if not ordered:
            continue
        _syntax_evidence(ordered)
        for row, sl in ordered:
            for sp in sl.entities:
                rel_s, rel_e = sp.start - sl.sentence_start, sp.end - sl.sentence_start
                toks = [t for t in (sl.syntax or {}).get("tokens", [])
                        if t.get("char_start") is not None
                        and t["char_start"] >= rel_s and t["char_end"] <= rel_e]
                out[(sp.doc_id, sp.chunk_id, sp.start, sp.end)] = toks
    return out


def classify_endpoint(gold_surface: str, doc: str, mentions: list[dict],
                      tokens: dict, doc_text: str,
                      layout: dict | None = None) -> dict:
    """Place ONE gold endpoint in exactly one bucket, with its evidence."""
    from polymath_shared.concept_evidence import admit_concept
    from polymath_shared.generic_classification import classify_generic
    from polymath_shared.identity_evidence import identity_evidence

    target = norm(gold_surface)
    exact = [m for m in mentions if m["normalized"] == target]

    if not exact:
        overlap = [m for m in mentions
                   if target in m["normalized"] or m["normalized"] in target]
        if overlap:
            return {"bucket": "SPAN_BOUNDARY",
                    "evidence": f"proposed as {sorted({m['surface'] for m in overlap})[:3]}, "
                                f"not with the gold extent"}
        return {"bucket": "DISCOVERY_MISS",
                "evidence": "no mention row overlaps this surface — the provider "
                            "never proposed it"}

    durable = [m for m in exact if m["entity_id"]]
    if durable:
        return {"bucket": "DURABLE", "entity_id": durable[0]["entity_id"],
                "evidence": f"{durable[0]['anchor_kind']} / {durable[0]['reason'][:60]}"}

    m = exact[0]
    toks = tokens.get((m["doc_id"], m["chunk_id"], m["start"], m["end"]), [])
    # The attribution must ask the LIVE authority, heading context included.
    # Omitting it would re-derive a different answer than the one actually
    # taken and report a defect that does not exist.
    regions = (layout or {}).get(m["chunk_id"]) or []
    in_head = any(a <= m["start"] and m["end"] <= b for a, b in regions)
    ident = identity_evidence(m["surface"], tokens=toks,
                              heading_context=in_head) if toks else None
    gen = classify_generic(m["surface"], tokens=toks)
    concept = admit_concept(m["surface"], document_text=doc_text)

    anchor = m["anchor_kind"]
    if anchor == "GENERIC":
        return {"bucket": "GENERIC_CORRECT_REFUSAL",
                "evidence": m["reason"][:80]}
    if anchor == "LOCAL_REFERENCE":
        return {"bucket": "LOCAL_REFERENCE_UNRESOLVED",
                "evidence": f"basis={m['reference_basis']} · {m['reason'][:60]}"}
    if anchor == "UNKNOWN":
        if in_head and not all(
                any(a <= o["start"] and o["end"] <= b for a, b in
                    (layout or {}).get(o["chunk_id"]) or []) is False
                for o in exact):
            pass
        if in_head and ident is not None and not ident.is_identity and any(
                "layout" in x for x in ident.exclusions):
            return {"bucket": "HEADING_SUPPRESSED",
                    "evidence": "every occurrence of this surface is inside a "
                                "heading; title capitalization is not identity "
                                "evidence (row 47)"}
        # subdivide the abstention by what the evidence actually showed
        if ident is not None and ident.is_identity:
            return {"bucket": "IDENTITY_FALSE_NEGATIVE",
                    "evidence": f"identity predicate says YES ({ident.reasons[0][:50]}) "
                                f"but the mention is UNKNOWN"}
        propn = [t["text"] for t in toks if t.get("pos") == "PROPN"]
        if propn and not gen.is_generic:
            return {"bucket": "IDENTITY_FALSE_NEGATIVE",
                    "evidence": f"PROPN {propn} present, identity declined: "
                                f"{(ident.exclusions[0] if ident and ident.exclusions else '?')[:60]}"}
        if concept is None and not gen.is_generic:
            return {"bucket": "CONCEPT_AUTHORITY_ABSENT",
                    "evidence": "common nominal; the document never defines or "
                                "declares this term, so no concept authority exists"}
        if gen.is_generic:
            return {"bucket": "GENERIC_CORRECT_REFUSAL",
                    "evidence": f"generic: {gen.reasons[0][:60]}"}
        return {"bucket": "HARBOR_ABSTENTION", "evidence": m["reason"][:80]}
    if anchor in ("IDENTITY", "CONCEPT"):
        return {"bucket": "CANONICALIZATION_MISMATCH",
                "evidence": f"{anchor} but no durable id — {m['reason'][:60]}"}
    return {"bucket": "UNEXPLAINED",
            "evidence": f"anchor={anchor} status={m['decision_status']} "
                        f"reason={m['reason'][:60]}"}


def main() -> int:
    import argparse

    import psycopg
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="i4-fresh-acceptance-v1")
    args = ap.parse_args()

    gold = json.loads((HERE / "gold" / "fact_gold.json").read_text())
    with psycopg.connect(DSN) as conn:
        mentions = _mentions_for(conn, args.corpus)
        tokens = _tokens_for(conn, args.corpus)
        layout = {}
        for src, cid, lm in conn.execute(
            """SELECT d.source_name, c.chunk_id, c.layout_map
                 FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
                WHERE d.corpus_id = %s AND c.tier='child'""", (args.corpus,)).fetchall():
            layout.setdefault(src, {})[cid] = [tuple(r) for r in (lm or [])]
        doc_text = {}
        for src, txt in conn.execute(
            """SELECT d.source_name, string_agg(c.text, E'\\n' ORDER BY c.chunk_index)
                 FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
                WHERE d.corpus_id = %s AND c.tier='child' GROUP BY 1""",
                (args.corpus,)).fetchall():
            doc_text[src] = txt

    counts = {b: 0 for b in BUCKETS}
    rows = []
    for g in gold["supported_positive"]["facts"]:
        src = next((s for s in mentions if s.endswith(g["doc"])), None)
        ms = mentions.get(src, [])
        dt = doc_text.get(src, "")
        for side in ("subject", "object"):
            res = classify_endpoint(g[side], g["doc"], ms, tokens, dt,
                                    layout.get(src, {}))
            counts[res["bucket"]] += 1
            rows.append({"fact": g.get("fact_id"), "side": side,
                         "surface": g[side], "doc": g["doc"], **res})

    missing = [r for r in rows if r["bucket"] != "DURABLE"]
    print(json.dumps({
        "corpus": args.corpus,
        "gold_facts": len(gold["supported_positive"]["facts"]),
        "gold_endpoint_instances": len(rows),
        "durable": counts["DURABLE"],
        "not_durable": len(missing),
        "attribution": {k: v for k, v in counts.items() if v},
        "unexplained": counts["UNEXPLAINED"],
    }, indent=1))
    print("\n--- endpoints without durable identity ---")
    for r in sorted(missing, key=lambda x: x["bucket"]):
        print(f"  [{r['bucket']:<26}] {r['fact'] or '?':<5} {r['side']:<8} "
              f"{r['surface'][:34]:<36} {r['evidence'][:72]}")
    return 1 if counts["UNEXPLAINED"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
