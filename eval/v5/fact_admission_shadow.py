"""POLYMATH-FACT-ADMISSION-V1 — shadow pass over the existing L4 ledger.

Read-only. Replays FactAdmission against every relation candidate that
already produced a fact, WITHOUT touching production canonical facts.
This is the payoff of the evidence-first architecture: semantic
iteration costs minutes over persisted evidence instead of hours of
re-ingestion.

Outputs a census: pass/qualify/reject counts, per-gate rejection
reasons, predicate and document distribution before/after, and the
per-candidate decisions for precision sampling.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(ROOT, "shared"), os.path.join(ROOT, "workers")]

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

SYNTAX_BATCH = 512


def load_candidates(conn, corpus: str) -> list[dict]:
    """Every candidate that produced a fact, with settled endpoint state,
    persisted spans, and its chunk text. One query, no per-row lookups."""
    rows = conn.execute("""
        SELECT DISTINCT ON (rc.candidate_id)
               rc.candidate_id, rc.doc_id, rc.chunk_id, rc.predicate,
               rc.evidence_class, rc.trigger_surface,
               rc.subject_surface, rc.object_surface,
               f.fact_id, f.subject_id, f.object_id, f.decision, f.provenance,
               ev.span_offsets, ch.text, ch.layout_map,
               es.core_type, es.admission_class,
               eo.core_type, eo.admission_class
          FROM relation_candidates rc
          JOIN documents d ON d.doc_id = rc.doc_id
          JOIN facts f ON f.fact_id = rc.fact_id
          LEFT JOIN evidence ev ON ev.fact_id = f.fact_id AND ev.chunk_id = rc.chunk_id
          JOIN chunks ch ON ch.chunk_id = rc.chunk_id
          LEFT JOIN entities es ON es.entity_id = f.subject_id
          LEFT JOIN entities eo ON eo.entity_id = f.object_id
         WHERE d.corpus_id = %s AND rc.fact_id IS NOT NULL
         ORDER BY rc.candidate_id
    """, (corpus,)).fetchall()
    out = []
    for r in rows:
        (cid, doc_id, chunk_id, predicate, ev_class, trigger,
         subj_surf, obj_surf, fact_id, subj_id, obj_id, decision, prov,
         offsets, text, layout_map, s_type, s_class, o_type, o_class) = r
        out.append({
            "candidate_id": cid, "doc_id": doc_id, "chunk_id": chunk_id,
            "predicate": predicate, "evidence_class": ev_class,
            "trigger_surface": trigger, "subject_surface": subj_surf,
            "object_surface": obj_surf, "fact_id": fact_id,
            "subject_id": subj_id, "object_id": obj_id,
            "prod_decision": decision, "provenance": prov or {},
            "offsets": offsets or {}, "chunk_text": text,
            "layout_map": layout_map or [],
            "subject_type": s_type, "subject_class": s_class,
            "object_type": o_type, "object_class": o_class,
        })
    return out


def load_layout(conn, corpus: str) -> dict[str, list[tuple[str, int, int]]]:
    rows = conn.execute("""
        SELECT dl.doc_id, dl.kind, dl.char_start, dl.char_end
          FROM document_layout dl JOIN documents d ON d.doc_id = dl.doc_id
         WHERE d.corpus_id = %s""", (corpus,)).fetchall()
    by_doc: dict[str, list] = defaultdict(list)
    for doc_id, kind, lo, hi in rows:
        by_doc[doc_id].append((kind, lo, hi))
    return by_doc


def sentence_window(text: str, start: int, end: int) -> tuple[str, int]:
    """The sentence containing [start, end), via the production splitter."""
    from workers.extract_worker import _sentences_of
    sentences = _sentences_of(text)
    for s_text, (s0, s1) in zip(sentences.texts, sentences.offsets):
        if s0 <= start and end <= s1:
            return s_text, s0
    lo = text.rfind("\n", 0, start) + 1
    hi = text.find("\n", end)
    hi = len(text) if hi == -1 else hi
    return text[lo:hi], lo


def attach_parses(rows: list[dict]) -> dict:
    """Batch-parse the unique sentences the candidates sit in."""
    from polymath_shared.clients import SpacySyntaxClient

    uniq: dict[str, str] = {}
    for r in rows:
        if r.get("sentence_text") and r["sentence_text"] not in uniq:
            uniq[r["sentence_text"]] = f"s{len(uniq)}"
    sentences = [{"sentence_id": sid, "text": txt} for txt, sid in uniq.items()]
    if not sentences:
        return {"sentences": 0}
    client = SpacySyntaxClient()
    results: list[dict] = []
    try:
        client.verify_pin()
        for i in range(0, len(sentences), SYNTAX_BATCH):
            batch = sentences[i:i + SYNTAX_BATCH]
            resp = client.syntax(batch)
            if [x["sentence_id"] for x in resp["results"]] != [s["sentence_id"] for s in batch]:
                raise RuntimeError("syntax sidecar returned mismatched identity/order")
            results.extend(resp["results"])
    finally:
        client.close()
    by_id = {r["sentence_id"]: r for r in results}
    for r in rows:
        sid = uniq.get(r.get("sentence_text") or "")
        r["parse"] = by_id.get(sid) if sid else None
    return {"sentences": len(sentences)}


def run(corpus: str, out_path: str | None, persist: bool = False) -> dict:
    from polymath_shared.fact_admission import FactContext, admit, policy
    from polymath_shared.rulepack.compiler import load_rule_pack
    from polymath_shared.source_region import REGION_POLICY_VERSION, region_at

    pack = load_rule_pack()
    conn = psycopg.connect(DSN)
    rows = load_candidates(conn, corpus)
    layout = load_layout(conn, corpus)

    # region + sentence window: computed once per row, never per gate
    for r in rows:
        off = r["offsets"] if isinstance(r["offsets"], dict) else {}
        s_start, s_end = off.get("subject_start"), off.get("subject_end")
        o_start, o_end = off.get("object_start"), off.get("object_end")
        e_start, e_end = off.get("evidence_start"), off.get("evidence_end")
        r["region"] = "BODY_PROSE"
        r["sentence_text"], r["sentence_start"] = None, 0
        if s_start is not None and o_start is not None:
            lo, hi = min(s_start, o_start), max(s_end or s_start, o_end or o_start)
            r["region"] = region_at(r["chunk_text"], lo, hi, layout.get(r["doc_id"]))
            r["sentence_text"], r["sentence_start"] = sentence_window(
                r["chunk_text"], lo, hi)

    stats = attach_parses(rows)

    decisions, gate_census, reason_census = [], Counter(), Counter()
    pred_before, pred_after = Counter(), Counter()
    doc_before, doc_after = Counter(), Counter()
    flips = 0
    for r in rows:
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
            chunk_text=r["chunk_text"], region=r["region"],
            parse=r.get("parse"), scope=(prov.get("scope") or {}),
            sentence_start=r["sentence_start"],
        )
        d = admit(ctx, pack)
        pred_before[r["predicate"]] += 1
        doc_before[r["doc_id"]] += 1
        if d.outcome == "PASS":
            pred_after[r["predicate"]] += 1
            doc_after[r["doc_id"]] += 1
        if d.flipped:
            flips += 1
        gate_census[f"{d.gate or 'ADMITTED'}"] += 1
        reason_census[f"{d.gate or 'ADMITTED'}:{d.reason or 'PASS'}"] += 1
        decisions.append({
            "candidate_id": r["candidate_id"], "fact_id": r["fact_id"],
            "doc_id": r["doc_id"], "chunk_id": r["chunk_id"],
            "predicate": r["predicate"], "prod_decision": r["prod_decision"],
            "subject_id": r["subject_id"], "object_id": r["object_id"],
            "subject_surface": r["subject_surface"], "object_surface": r["object_surface"],
            "region": r["region"], "outcome": d.outcome, "reason": d.reason,
            "gate": d.gate, "flipped": d.flipped,
        })

    outcomes = Counter(d["outcome"] for d in decisions)
    report = {
        "corpus": corpus,
        "contract": "fact-admission-v1",
        "policy_version": policy()["policy_version"],
        "region_policy_version": REGION_POLICY_VERSION,
        "candidates_examined": len(rows),
        "sentences_parsed": stats.get("sentences", 0),
        "outcomes": dict(outcomes),
        "orientation_flips": flips,
        "gate_census": dict(gate_census.most_common()),
        "reason_census": dict(reason_census.most_common()),
        "predicate_before": dict(pred_before.most_common()),
        "predicate_after": dict(pred_after.most_common()),
        "documents_with_facts_before": len(doc_before),
        "documents_with_facts_after": len(doc_after),
        "unique_facts_before": len({d["fact_id"] for d in decisions}),
        "unique_facts_after": len({d["fact_id"] for d in decisions
                                   if d["outcome"] == "PASS"}),
    }
    if out_path:
        with open(out_path, "w") as f:
            json.dump({"report": report, "decisions": decisions}, f, indent=1)
    if persist:
        persist_decisions(conn, corpus, decisions, report)
        report["persisted"] = len(decisions)
    return report


def persist_decisions(conn, corpus: str, decisions: list[dict],
                      report: dict, shadow: bool = True) -> None:
    """Record every gate decision in fact_admission_decisions.

    shadow=True by default: the rows document what admission WOULD do
    without governing the projected graph. Cutover flips the flag; it
    does not rewrite history.
    """
    from polymath_shared.source_region import REGION_POLICY_VERSION
    rows = [(d["fact_id"], d["candidate_id"], corpus, d["doc_id"],
             d["outcome"], d["gate"], d["reason"], bool(d["flipped"]), shadow,
             report["contract"], report["policy_version"],
             REGION_POLICY_VERSION)
            for d in decisions if d.get("fact_id")]
    with conn.cursor() as cur:
        cur.execute("""DELETE FROM fact_admission_decisions
                        WHERE corpus_id = %s AND contract_version = %s
                          AND policy_version = %s""",
                    (corpus, report["contract"], report["policy_version"]))
        cur.executemany(
            """INSERT INTO fact_admission_decisions
                 (fact_id, candidate_id, corpus_id, doc_id, outcome, gate,
                  reason, flipped, shadow, contract_version, policy_version,
                  region_policy_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT DO NOTHING""", rows)
    conn.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out")
    ap.add_argument("--persist", action="store_true",
                    help="record decisions in fact_admission_decisions (shadow)")
    a = ap.parse_args()
    print(json.dumps(run(a.corpus, a.out, a.persist), indent=1))
