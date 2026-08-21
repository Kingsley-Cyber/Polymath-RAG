#!/usr/bin/env python3
"""V5 P9 — FULL DETERMINISTIC REPLAY: ledger -> settlement -> facts.

READ-ONLY. Extends shadow settlement through the fact compiler: evidence
anchors recomputed from the pinned rule pack (deterministic, lexical),
candidates built per slice with the settled identities, relations compiled
by the frozen compiler — and the resulting FACT ID SET compared with
production. Fact ids are content hashes, so set equality is the strongest
possible claim: same evidence in, same graph truth out, byte for byte.
"""
import argparse, importlib.util, json, os, sys
sys.path[:0] = ["shared", "workers", "eval/v5"]
os.environ.setdefault("POLYMATH_SYNTAX_PROVIDER", "spacy")

import psycopg

DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
_spec = importlib.util.spec_from_file_location(
    "shadow_settlement", os.path.join(os.path.dirname(__file__), "shadow_settlement.py"))
SH = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_spec and _spec.loader and _spec) if False else _spec.loader.exec_module(SH)


def replay_facts(conn, doc_id: str, corpus_id: str, profile: dict):
    from polymath_shared.contracts import DocumentProfile
    from polymath_shared.rulepack import compile_relation
    from workers.candidates import build_candidates
    from workers.extract_worker import (_evidence_spans, _fill_parse_entities,
                                        _pack, _persist_slice_manifest)  # noqa: F401
    from workers.evidence_proposer import propose_evidence
    from workers.summarizer import split_sentences  # noqa: F401
    from workers.extract_worker import parse_sentence

    pack = _pack()
    ids, ordered = SH.shadow_settle(conn, doc_id, corpus_id)
    # evidence anchors: deterministic lexical derivation from the pinned pack
    anchors_by_chunk = {}
    for cid, text in conn.execute(
            "SELECT chunk_id, text FROM chunks WHERE doc_id=%s AND tier='child'",
            (doc_id,)).fetchall():
        anchors_by_chunk[cid] = propose_evidence(text, cid, pack)

    # attach evidence + parse to the manifest slices; fill parse entity ids
    from workers.candidates import SentenceSlice
    enriched = []
    for row, sl in ordered:
        ev = [a for a in anchors_by_chunk.get(row["chunk_id"], [])
              if a.start >= sl.sentence_start and a.end <= sl.sentence_end]
        parse = parse_sentence(sl.text)
        if parse is not None:
            parse["_sentence_offsets"] = [sl.sentence_start, sl.sentence_end]
        nsl = SentenceSlice(text=sl.text, sentence_start=sl.sentence_start,
                            sentence_end=sl.sentence_end, entities=sl.entities,
                            evidence=ev, parse=parse,
                            sentence_index=sl.sentence_index, syntax=sl.syntax)
        if parse is not None:
            _fill_parse_entities(parse, nsl.entities, corpus_id, ids)
        enriched.append((row, nsl))

    profile_id = profile.get("profile_id", "core")
    from workers.extract_worker import EXTRACTOR_VERSION
    facts, hist = set(), []
    for row, sl in enriched:
        cands = build_candidates([sl], doc_id=doc_id, corpus_id=corpus_id,
                                 ontology_profile=profile_id,
                                 extractor_version=EXTRACTOR_VERSION,
                                 rule_pack=pack, doc_entities_history=hist,
                                 identities=ids)
        hist.extend(sorted(sl.entities, key=lambda e: (e.start, e.end)))
        for cand in cands:
            decision = compile_relation(cand, sl.parse, pack, syntax=sl.syntax)
            if decision.decision in ("ACCEPT", "QUALIFY") and decision.fact:
                facts.add(decision.fact.fact_id)
    return facts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    a = ap.parse_args()
    report = {"corpus": a.corpus, "docs": 0, "replayed_facts": 0,
              "production_facts": 0, "missing": [], "extra": []}
    with psycopg.connect(DSN) as conn:
        replayed: set = set()
        for doc_id, prof in conn.execute(
                "SELECT doc_id, profile FROM documents WHERE corpus_id=%s ORDER BY doc_id",
                (a.corpus,)).fetchall():
            report["docs"] += 1
            replayed |= replay_facts(conn, doc_id, a.corpus, prof)
        prod = {r[0] for r in conn.execute(
            """SELECT DISTINCT f.fact_id FROM facts f
                 JOIN evidence ev ON ev.fact_id=f.fact_id
                 JOIN documents d ON d.doc_id=ev.doc_id
                WHERE d.corpus_id=%s""", (a.corpus,)).fetchall()}
    report["replayed_facts"] = len(replayed)
    report["production_facts"] = len(prod)
    report["missing"] = sorted(prod - replayed)[:8]
    report["extra"] = sorted(replayed - prod)[:8]
    report["verdict"] = "IDENTICAL" if replayed == prod else "DIVERGENT"
    print(json.dumps(report, indent=1))
    return 0 if replayed == prod else 1


if __name__ == "__main__":
    raise SystemExit(main())
