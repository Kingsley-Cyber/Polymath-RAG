#!/usr/bin/env python
"""CHAT-QUERY-COMPILER plan §4 — baseline set B and its runner (phase P0.0).

--build   derive a deterministic question set with GOLD chunk ids from the
          live corpora: definition-style child chunks (glossary entries,
          "X is ..." sentences) become questions; gold = that chunk id.
          Writes eval/fixtures/chat_baseline_B.json (committed).
--run     replay every question through /chat/stream (HYBRID, deterministic
          synthesizer unless --llm) and record, from the receipt's funnel:
          gold in union, gold in selected (hit@k), gold cited, wall, phase_ms.
          Writes docs/wiki/experiments/chat-baseline-<tag>.json + .md.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
FIXTURE = ROOT / "eval" / "fixtures" / "chat_baseline_B.json"
OUT_DIR = ROOT / "docs" / "wiki" / "experiments"
ORCH = os.environ.get("POLYMATH_ORCHESTRATOR_URL", "http://127.0.0.1:7200")

_DEF_RE = re.compile(r"^(?P<term>[A-Z][A-Za-z0-9 \-–/'’]{2,48}?)\s*(?:—|–|:|\bis\b|\bare\b|\brefers to\b|\bmeans\b)\s+(?P<rest>[a-z][^.]{30,200}\.)", re.M)


def _connect():
    import psycopg
    return psycopg.connect(os.environ["POLYMATH_PG_DSN"])


_STOP_HEADINGS = {"introduction", "summary", "notes", "index", "contents", "references", "glossary", "exercises",
                  "acknowledgments", "acknowledgements", "preface", "foreword", "appendix", "bibliography", "conclusion",
                  "key terms", "review questions", "further reading", "about the author", "credits", "copyright"}


def _clean_heading(h: str) -> str | None:
    h = (h or "").strip()
    h = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", h)               # markdown links → text
    h = h.replace("**", "").replace("*", "").replace("_", " ").replace("\\.", "").strip()
    h = re.sub(r"^[\d.\s:–—-]+", "", h)                          # drop numbering
    h = re.sub(r"[?!.:;,]+$", "", h)                                # trailing punctuation
    h = re.sub(r"\s+", " ", h).strip(" :–—-")
    if not h or len(h) > 60 or len(h.split()) > 7 or len(h.split()) < 2:
        return None
    if h.lower() in _STOP_HEADINGS or re.search(r"\b(chapter|part|section|figure|table|page)\b", h, re.I):
        return None
    if not re.search(r"[A-Za-z]{3}", h):
        return None
    return h


def build(per_corpus: int, corpora: list[str], seed: int) -> dict:
    """Known-answer questions from SECTION HEADINGS: the section's own children
    that contain a content word of the heading are the gold set (cap 6).
    Deterministic for a fixed corpus state and seed."""
    rng = random.Random(seed)
    items = []
    with _connect() as c:
        for corpus in corpora:
            rows = c.execute(
                """SELECT p.chunk_id, p.doc_id, d.source_name, p.heading_path,
                          array_agg(ch.chunk_id ORDER BY ch.chunk_index) AS kids,
                          array_agg(ch.text ORDER BY ch.chunk_index) AS texts
                     FROM chunks p JOIN documents d ON d.doc_id = p.doc_id
                     JOIN chunks ch ON ch.parent_id = p.chunk_id AND ch.tier = 'child'
                          AND coalesce(ch.region_role,'body') = 'body'
                    WHERE d.corpus_id = %s AND p.tier = 'parent'
                      AND jsonb_array_length(coalesce(p.heading_path,'[]'::jsonb)) >= 2
                    GROUP BY p.chunk_id, p.doc_id, d.source_name, p.heading_path
                   HAVING count(ch.chunk_id) BETWEEN 2 AND 12
                    ORDER BY p.chunk_id""", (corpus,)).fetchall()
            cands = []
            for parent_id, doc_id, source, hp, kids, texts in rows:
                hp = hp if isinstance(hp, list) else json.loads(hp or "[]")
                term = _clean_heading(str(hp[-1]))
                if not term:
                    continue
                words = [w for w in re.findall(r"[A-Za-z]{4,}", term.lower()) if w not in ("with", "from", "that", "this", "your", "their", "into", "about")]
                if not words:
                    continue
                gold = [cid for cid, t in zip(kids, texts) if sum(1 for w in words if w in (t or "").lower()) >= max(1, len(words) // 2)]
                if not gold:
                    continue
                cands.append({"corpus_id": corpus, "doc_id": doc_id, "source_name": source, "parent_id": parent_id,
                              "term": term, "heading_path": hp, "gold_chunk_ids": gold[:6], "gold_chunk_id": gold[0],
                              "question": f"What does the book say about {term.lower() if not term.isupper() else term}?"})
            rng.shuffle(cands)
            picked, seen_docs = [], set()
            for x in cands:                                   # one per document first
                if x["doc_id"] in seen_docs:
                    continue
                seen_docs.add(x["doc_id"]); picked.append(x)
                if len(picked) >= per_corpus:
                    break
            for x in cands:
                if len(picked) >= per_corpus:
                    break
                if x not in picked:
                    picked.append(x)
            items.extend(picked)
    return {"version": "chat-baseline-B-v3", "seed": seed, "corpora": corpora, "per_corpus": per_corpus,
            "gold_rule": "children of the heading's own section containing >= half the heading's content words (cap 6)",
            "questions": items}


def _stream(question: str, corpus: str, synthesizer: str | None) -> tuple[dict, float]:
    body = {"message": question, "corpus_id": corpus, "mode": "HYBRID"}
    if synthesizer:
        body["synthesizer"] = synthesizer
    req = urllib.request.Request(f"{ORCH}/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    t0 = time.time(); answer = {}
    with urllib.request.urlopen(req, timeout=400) as r:
        cur = None
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "answer":
                try:
                    answer = json.loads(line[5:].strip())
                except Exception:
                    pass
    return answer, time.time() - t0


def _receipt_for(question: str) -> dict | None:
    with _connect() as c:
        row = c.execute("""SELECT meta, wall_ms FROM query_receipts WHERE kind='chat_stream' AND question_head=%s
                           ORDER BY received_at DESC LIMIT 1""", (question[:200],)).fetchone()
    return {"meta": row[0], "wall_ms": row[1]} if row else None


def run(tag: str, synthesizer: str | None, limit: int | None) -> dict:
    from polymath_shared.funnel import where_did_it_die
    fx = json.loads(FIXTURE.read_text())
    results = []
    for i, q in enumerate(fx["questions"][: limit or None]):
        try:
            ans, wall = _stream(q["question"], q["corpus_id"], synthesizer)
        except Exception as exc:  # noqa: BLE001
            results.append({**q, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}); continue
        rec = _receipt_for(q["question"]) or {}
        fun = ((rec.get("meta") or {}).get("funnel")) or {}
        st = fun.get("stages") or {}
        golds = q.get("gold_chunk_ids") or [q["gold_chunk_id"]]
        def _in(stage):
            return any(g in (st.get(stage) or []) for g in golds)
        sel = st.get("selected") or []
        ranks = [sel.index(g) + 1 for g in golds if g in sel]
        best = min(ranks) if ranks else None
        deaths = [where_did_it_die(fun, g) for g in golds] if fun else ["NO_FUNNEL"]
        order = ["CITED", "IGNORED_BY_LLM", "LOST_AT_SELECTION", "LOST_AT_RERANK", "LOST_AT_UNION_TRUNCATION", "NEVER_RETRIEVED", "NO_FUNNEL"]
        results.append({**q, "wall_s": round(wall, 2), "phase_ms": (rec.get("meta") or {}).get("phase_ms"),
                        "gold_in_retrieved": _in("retrieved"),
                        "gold_in_union": _in("union"),
                        "gold_in_pre_rerank": _in("pre_rerank"),
                        "gold_selected_rank": best,
                        "gold_cited": _in("cited"),
                        "death": sorted(deaths, key=order.index)[0],
                        "counts": fun.get("counts"), "lane_counts": fun.get("lane_counts"),
                        "verdict": (ans.get("result") or {}).get("meta", {}).get("verdict") if isinstance(ans.get("result"), dict) else None})
        print(f"[{i+1}/{len(fx['questions'])}] {q['corpus_id']:14s} {results[-1].get('death','?'):26s} rank={results[-1].get('gold_selected_rank')} {wall:5.1f}s  {q['question'][:60]}", flush=True)
    ok = [r for r in results if "error" not in r]
    def rate(key):
        return round(sum(1 for r in ok if r.get(key)) / max(1, len(ok)), 3)
    summary = {
        "n": len(results), "errors": len(results) - len(ok),
        "gold_in_retrieved": rate("gold_in_retrieved"), "gold_in_union": rate("gold_in_union"),
        "gold_in_pre_rerank": rate("gold_in_pre_rerank"),
        "hit@10_selected": round(sum(1 for r in ok if r.get("gold_selected_rank") and r["gold_selected_rank"] <= 10) / max(1, len(ok)), 3),
        "mrr_selected": round(sum(1.0 / r["gold_selected_rank"] for r in ok if r.get("gold_selected_rank")) / max(1, len(ok)), 3),
        "gold_cited": rate("gold_cited"),
        "wall_p50_s": round(statistics.median([r["wall_s"] for r in ok]), 2) if ok else None,
        "wall_p90_s": round(sorted(r["wall_s"] for r in ok)[int(len(ok) * 0.9) - 1], 2) if len(ok) >= 10 else None,
        "deaths": dict(sorted(__import__("collections").Counter(r.get("death") for r in ok).items())),
        "synthesizer": synthesizer or "default", "tag": tag,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chat-baseline-{tag}.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, default=str))
    md = [f"# Chat baseline — {tag}", "", f"Fixture `{FIXTURE.relative_to(ROOT)}` ({fx['version']}, seed {fx['seed']}); synthesizer {summary['synthesizer']}; HYBRID via /chat/stream.", "",
          "| metric | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items() if k not in ("tag", "synthesizer")] + ["", "| corpus | question | death | selected rank | wall s |", "|---|---|---|---|---|"]
    md += [f"| {r['corpus_id']} | {r['question'][:60]} | {r.get('death', r.get('error'))} | {r.get('gold_selected_rank')} | {r.get('wall_s')} |" for r in results]
    (OUT_DIR / f"chat-baseline-{tag}.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary, indent=1))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--corpora", default="cinema,ecom-meta-v1")
    ap.add_argument("--per-corpus", type=int, default=15)
    ap.add_argument("--seed", type=int, default=20260905)
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--synthesizer", default="deterministic-template-v3")
    ap.add_argument("--llm", action="store_true", help="use the default LLM synthesizer instead of the deterministic one")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.build:
        fx = build(a.per_corpus, [c.strip() for c in a.corpora.split(",") if c.strip()], a.seed)
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(fx, indent=1))
        print(f"wrote {FIXTURE} with {len(fx['questions'])} questions")
    if a.run:
        run(a.tag, None if a.llm else a.synthesizer, a.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
