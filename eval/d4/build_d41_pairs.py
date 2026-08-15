"""D4.1 frozen pair set builder.

Builds (query, passage, text_kind, gold_label) pairs from:
  - the frozen D4 measurement records (real post-G3 retrieval candidates),
  - summary candidates (document semantic summaries + parent summaries),
  - a small frozen CONTRADICTS subset (3 proposition queries whose
    answers the corpus states in the opposite direction — natural
    semantics, no invented content).

Gold labels: SUPPORTS / TOPIC_ONLY / IRRELEVANT / CONTRADICTS.
Domain-group rule for negatives + hand-verified exceptions.

Deterministic; frozen output sha256 recorded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"

CONTRADICTION_QUERIES = [
    {
        "query_id": "c1_contradiction",
        "query": "Does high cognitive load improve metacognitive monitoring accuracy?",
        "contradicts": ["psych/cognitive_load.md", "psych/metacognitive_monitoring.md",
                        "psych/working_memory.txt"],
    },
    {
        "query_id": "c2_contradiction",
        "query": "Is rereading more effective than retrieval practice for long-term memory?",
        "contradicts": ["psych/retrieval_practice.md"],
    },
    {
        "query_id": "c3_contradiction",
        "query": "Does encryption alone prevent data misuse by authorized users?",
        "contradicts": ["cyber/encryption_basics.md"],
    },
]

DOMAIN_GROUP = {
    "psych": "psych", "systems": "systems", "cyber": "cyber", "knowledge": "knowledge",
}

# D4 frozen query answers live in these docs (gold from /tmp/d4/gold.json keys)
SUPPORTING_DOCS = {
    "q1_direct_lexical": ["cyber/zero_trust.docx"],
    "q2_paraphrased": ["psych/retrieval_practice.md", "psych/metacognitive_monitoring.md"],
    "q3_cross_section": ["psych/cognitive_load.md", "psych/metacognitive_monitoring.md",
                         "psych/working_memory.txt"],
    "q4_terminology_mismatch": ["psych/metacognitive_monitoring.md",
                                "psych/judgment_of_learning.epub"],
    "q5_summary_level": ["psych/metacognitive_monitoring.md", "psych/metacognitive_control.md"],
    "q6_child_text": ["cyber/incident_response.pdf"],
    "q7_graph_independent": ["psych/judgment_of_learning.epub"],
}

SAME_DOMAIN_UNSUPPORTED = {
    "u5_same_domain": {"psych"},
    "u6_keyword_trap": {"systems", "psych"},
}


def group_of(source_name: str) -> str | None:
    for g in DOMAIN_GROUP:
        if source_name.startswith(g + "/"):
            return g
    return None


def main() -> int:
    conn = psycopg.connect(DSN)
    source_of_doc = {r[0]: r[1] for r in conn.execute(
        "SELECT doc_id, source_name FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunk_text = {r[0]: r[1] for r in conn.execute(
        """SELECT ch.chunk_id, ch.text FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s""",
        (CORPUS,)).fetchall()}
    parent_text = {r[0]: r[1] for r in conn.execute(
        """SELECT ch.chunk_id, ch.summary FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s AND ch.tier='parent'""",
        (CORPUS,)).fetchall()}
    doc_summary = {r[0]: (r[1] or {}).get("semantic_summary") or "" for r in conn.execute(
        "SELECT doc_id, retrieval_profile FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    conn.close()

    measure = json.load(open(ROOT / "eval" / "d4" / "artifacts" / "measure.json"))
    gold_map = json.load(open(ROOT / "eval" / "d4" / "artifacts" / "gold.json"))["gold"]

    pairs = []
    seen = set()

    def add(query_id, query, kind, doc_id, chunk_id, passage, gold):
        cid = chunk_id or ("doc:" + doc_id)
        key = (query_id, kind, cid)
        if key in seen:
            return
        seen.add(key)
        pairs.append({
            "query_id": query_id, "query": query, "text_kind": kind,
            "doc_id": doc_id, "chunk_id": chunk_id, "passage": passage,
            "gold_label": gold,
        })

    query_text = {e["query_id"]: e["query"] for e in json.load(
        open(ROOT / "eval" / "d4" / "queries.json"))["queries"]}

    for r in measure["records"]:
        qid = r["query_id"]
        if qid not in query_text:
            continue
        doc_id = r["doc_id"] or ""
        src = source_of_doc.get(doc_id, "")
        if r["text_kind"] == "child_chunk" and r["chunk_id"] in chunk_text:
            passage = chunk_text[r["chunk_id"]]
        elif r["text_kind"] == "section_summary" and r["chunk_id"] in parent_text:
            passage = parent_text[r["chunk_id"]]
        elif r["text_kind"] == "document_summary" and doc_id in doc_summary:
            passage = doc_summary[doc_id]
        else:
            continue
        gkey = f"{qid}::__doc__:{src}" if r["text_kind"] == "document_summary" else f"{qid}::{r['chunk_id']}"
        if gold_map.get(gkey) == "SUPPORTED":
            gold = "SUPPORTS"
        elif qid in SAME_DOMAIN_UNSUPPORTED and group_of(src) in SAME_DOMAIN_UNSUPPORTED[qid]:
            gold = "TOPIC_ONLY"
        elif qid.startswith("u"):
            gold = "IRRELEVANT"
        elif group_of(src) == (group_of(SUPPORTING_DOCS[qid][0]) if qid in SUPPORTING_DOCS else None):
            gold = "TOPIC_ONLY"
        else:
            gold = "IRRELEVANT"
        add(qid, query_text[qid], r["text_kind"], doc_id, r["chunk_id"], passage, gold)

    # contradiction subset: pairs authored from corpus content (natural semantics)
    conn = psycopg.connect(DSN)
    for c in CONTRADICTION_QUERIES:
        for src in c["contradicts"]:
            rows = conn.execute(
                """SELECT ch.chunk_id, ch.tier, ch.text, ch.summary, d.doc_id
                   FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
                   WHERE d.corpus_id=%s AND d.source_name=%s""", (CORPUS, src)).fetchall()
            for chunk_id, tier, text, summary, doc_id in rows:
                if tier == "child":
                    add(c["query_id"], c["query"], "child_chunk", doc_id, chunk_id, text, "CONTRADICTS")
                else:
                    add(c["query_id"], c["query"], "section_summary", doc_id, chunk_id, summary or "", "CONTRADICTS")
            add(c["query_id"], c["query"], "document_summary", doc_id, None,
                doc_summary.get(doc_id, ""), "CONTRADICTS")
    conn.close()

    out = ROOT / "eval" / "d4" / "artifacts" / "d41_pairs.jsonl"
    out.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n")
    labels = {}
    for p in pairs:
        labels.setdefault(p["gold_label"], 0)
        labels[p["gold_label"]] += 1
    print(f"pairs: {len(pairs)} | labels: {labels}")
    import hashlib
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"sha256: {digest}")
    (out.parent / "d41_pairs.sha256").write_text(f"{digest}  d41_pairs.jsonl\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
