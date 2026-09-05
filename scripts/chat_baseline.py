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


RETRIEVAL_OVERRIDE: str | None = None      # --retrieval v1|v2 (P1.a A/B)


LEXICAL_FIXTURE = ROOT / "eval" / "fixtures" / "chat_lexical_L.json"
_IDENT_SQL = r"""
WITH toks AS (
  SELECT ch.chunk_id, ch.doc_id, d.source_name, m[1] AS tok, length(ch.text) AS n
    FROM chunks ch JOIN documents d ON d.doc_id = ch.doc_id,
         LATERAL regexp_matches(ch.text, '\m([A-Z][A-Z0-9]{2,}(?:-[A-Z0-9]+)*)\M', 'g') AS m
   WHERE d.corpus_id = %s AND ch.tier = 'child' AND coalesce(ch.region_role, 'body') = 'body'
), df AS (
  SELECT tok, count(DISTINCT chunk_id) AS df, array_agg(DISTINCT chunk_id) AS chunk_ids,
         min(doc_id) AS doc_id, min(source_name) AS source_name, min(n) AS min_len
    FROM toks GROUP BY tok
)
SELECT tok, df, chunk_ids, doc_id, source_name FROM df
 WHERE df BETWEEN 1 AND 2 AND length(tok) BETWEEN 3 AND 12 AND min_len >= 300
 ORDER BY tok"""


def _english_words() -> set[str]:
    try:
        return {w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8", errors="ignore") if w.strip()}
    except OSError:
        return set()


def build_lexical(per_corpus: int, corpora: list[str], seed: int) -> dict:
    """LEXICAL FIXTURE SET L (plan §4 P1.a / §5b #1): acronyms and identifiers
    that occur in at most two child chunks of the corpus (document frequency
    1–2). The question names the token verbatim in quotes; the gold set is
    exactly the chunks that contain it. An exact-match lane must find these;
    a dense lane may not. Deterministic for a fixed corpus state and seed."""
    rng = random.Random(seed)
    words = _english_words()
    items = []
    with _connect() as c:
        for corpus in corpora:
            rows = c.execute(_IDENT_SQL, (corpus,)).fetchall()
            # CASE-INSENSITIVE document frequency: "WATTS" with df 1 in caps but 40 chunks of
            # "watts" is not an exact-match test (BM25 lowercases). Keep tokens whose whole-word,
            # case-insensitive frequency in the corpus's child chunks is also ≤ 2.
            pool = [r for r in rows if r[0].lower() not in words and not (re.fullmatch(r"[A-Z]+", r[0]) and len(r[0]) > 6)]
            rng.shuffle(pool)
            pool = pool[:160]
            ci = dict(c.execute(
                """SELECT t.tok, count(*) FROM unnest(%s::text[]) AS t(tok)
                     JOIN chunks ch ON ch.tier = 'child' AND ch.text ~* ('\\m' || regexp_replace(t.tok, '([.\\-])', '\\\\\\1', 'g') || '\\M')
                     JOIN documents d ON d.doc_id = ch.doc_id AND d.corpus_id = %s
                    GROUP BY t.tok""", ([r[0] for r in pool], corpus)).fetchall())
            cands = []
            for tok, df, chunk_ids, doc_id, source in pool:
                if ci.get(tok, 0) > 2:
                    continue
                low = tok.lower()
                if low in words:
                    continue
                # a hyphenated compound of dictionary words ("THREE-TIME") is not an identifier: the
                # shared BM25 tokenizer splits it into common words and no exact-match lane can
                # single it out (measured 2026-09-05: the only L miss under v2). Identifiers carry a
                # digit or a non-word hyphen part.
                # the shared BM25 tokenizer splits on hyphens, so a hyphenated token is retrievable only
                # through its parts ("ADRG-021" → adrg works, "COM-1" → com/1 does not): hyphenated tokens
                # test the projection's tokenizer (§3.23, frozen), not the lane — excluded from L.
                if "-" in tok:
                    continue
                if re.search(r"\d|-", tok):
                    kind = "identifier"
                elif 3 <= len(tok) <= 6:
                    kind = "acronym"
                else:
                    continue
                cands.append({"corpus_id": corpus, "doc_id": doc_id, "source_name": source, "term": tok, "kind": kind,
                              "df": int(df), "df_ci": int(ci.get(tok, 0)), "gold_chunk_ids": list(chunk_ids)[:2], "gold_chunk_id": list(chunk_ids)[0],
                              "question": f'What does the book say about "{tok}"?', "exact_terms": [tok]})
            rng.shuffle(cands)
            picked, seen_docs, kinds = [], set(), {"identifier": 0, "acronym": 0}
            for x in sorted(cands, key=lambda x: (x["kind"] != "identifier", 0)):   # identifiers first, one per document first
                if len(picked) >= per_corpus:
                    break
                if x["doc_id"] in seen_docs and len(seen_docs) < 6:
                    continue
                if kinds[x["kind"]] >= (per_corpus + 1) // 2 and any(v < (per_corpus + 1) // 2 for v in kinds.values()) and len(cands) > per_corpus * 2:
                    continue
                seen_docs.add(x["doc_id"]); kinds[x["kind"]] += 1; picked.append(x)
            for x in cands:
                if len(picked) >= per_corpus:
                    break
                if x not in picked:
                    picked.append(x)
            items.extend(picked)
    return {"version": "chat-lexical-L-v1", "seed": seed, "corpora": corpora, "per_corpus": per_corpus,
            "gold_rule": "child chunks (body region) containing the token; token df 1-2 in caps AND whole-word case-insensitive df <= 2 in the corpus; not an English word; hyphenated tokens excluded (the shared BM25 tokenizer splits on hyphens)",
            "questions": items}


def _stream(question: str, corpus: str, synthesizer: str | None, history: list | None = None,
            compiler: str | None = None) -> tuple[dict, float]:
    body = {"message": question, "corpus_id": corpus, "mode": "HYBRID"}
    if synthesizer:
        body["synthesizer"] = synthesizer
    if history:
        body["history"] = history
    if compiler:
        body["compiler"] = compiler
    if RETRIEVAL_OVERRIDE:
        body["retrieval"] = RETRIEVAL_OVERRIDE
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


FOLLOWUP_TEMPLATES = ("How does that work in practice?", "Can you say more about that?", "Why does that matter?")


def followup_conversations(fx: dict) -> list[dict]:
    """FOLLOW-UP FIXTURES (plan §4 P0.c): each B question becomes a 2-turn
    conversation whose last user turn is a PRONOUN-ONLY follow-up; the gold
    set is unchanged. Deterministic: template = index mod 3."""
    out = []
    for i, q in enumerate(fx["questions"]):
        term = q["term"]
        out.append({**q, "history": [
            {"role": "user", "content": f"Tell me about {term.lower() if not term.isupper() else term}."},
            {"role": "assistant", "content": f"Here is what the book says about {term}: it is covered in the section of the same name, "
                                              f"with the key points and examples the author gives there [S1]."}],
            "question": FOLLOWUP_TEMPLATES[i % len(FOLLOWUP_TEMPLATES)],
            "original_question": q["question"]})
    return out


_S_TAG = re.compile(r"\[S(\d+)\]")
_ABSTAIN = re.compile(r"(not|n't|never)\s+(in|within|part of|contained in|covered by|mentioned in|present in|found in)\s+the\s+(provided\s+)?(evidence|sources|corpus|material)"
                      r"|evidence (does not|doesn't|did not|didn't) (contain|include|mention|cover|address|provide)"
                      r"|(no|without) (direct |specific |relevant )?(evidence|information|material) (on|about|for|regarding)"
                      r"|missing (premise|from the evidence)|cannot (be )?(answer|determine|confirm)", re.I)


def citation_stats(ans: dict, rec: dict) -> dict:
    """CITATION-PRECISION-V1 (P0.d gate): emitted [S#] tags vs the legend
    of the turn. precision = tags that resolve to a legend entry / tags
    emitted (None when no tag was emitted). Also the answer head and an
    abstention-marker flag for the artifact-task gate."""
    text = str(((ans.get("result") or {}).get("answer")) or "")
    legend = (ans.get("retrieval") or {}).get("legend") or ((rec.get("meta") or {}).get("legend")) or []
    valid = {str(e.get("tag")) for e in legend}
    tags = [f"S{m.group(1)}" for m in _S_TAG.finditer(text)]
    good = [t for t in tags if t in valid]
    ret = ans.get("retrieval") or {}
    arrivals = ret.get("arrivals") or {}
    selected = [e.get("chunk_id") for e in legend if e.get("chunk_id") and not e.get("carried")]
    return {"engine": ret.get("engine"), "arrivals_n": len(arrivals),
            "arrivals_missing": sum(1 for cid in selected if not arrivals.get(cid)),      # P1.a gate: 0 on every turn
            "lane_sizes": ret.get("lane_sizes"),
            "degraded_components": [d.get("component") for d in (ret.get("degraded") or []) if isinstance(d, dict)],
            "answer_chars": len(text), "answer_head": text[:160], "tags_total": len(tags), "tags_valid": len(good),
            "tags_distinct": len(set(tags)), "citation_precision": (round(len(good) / len(tags), 3) if tags else None),
            "used_evidence_n": len((ans.get("retrieval") or {}).get("used_evidence") or []),
            "abstain_marker": bool(_ABSTAIN.search(text)),
            "task_type": ((ans.get("retrieval") or {}).get("chat_plan") or {}).get("task_type")}


def _hit10(r: dict) -> bool:
    return bool(r.get("gold_selected_rank")) and r["gold_selected_rank"] <= 10


def recovery_against(results: list[dict], reference_tag: str) -> dict:
    """RECOVERY (P0.c): pair this run with a reference run of the same fixture
    (same order) and report hit@10 on the subset the reference retrieved.
    The follow-up form of a question can never beat its single-turn form, so
    the gate reads the follow-up hit@10 on the single-turn-retrievable subset;
    the all-item number is reported beside it."""
    ref = json.loads((OUT_DIR / f"chat-baseline-{reference_tag}.json").read_text())["results"]
    pairs = [(a, b) for a, b in zip(ref, results) if not a.get("error") and not b.get("error")]
    both = sum(1 for a, b in pairs if _hit10(a) and _hit10(b))
    only_ref = sum(1 for a, b in pairs if _hit10(a) and not _hit10(b))
    only_this = sum(1 for a, b in pairs if _hit10(b) and not _hit10(a))
    neither = sum(1 for a, b in pairs if not _hit10(a) and not _hit10(b))
    return {"reference": reference_tag, "paired": len(pairs), "both": both, "only_reference": only_ref, "only_this": only_this,
            "neither": neither, "reference_hit@10": round((both + only_ref) / max(1, len(pairs)), 3),
            "subset_hit@10": round(both / max(1, both + only_ref), 3)}


def run(tag: str, synthesizer: str | None, limit: int | None, compiler: str | None = None, followups: bool = False,
        reference: str | None = None, fixture: Path | None = None) -> dict:
    from polymath_shared.funnel import where_did_it_die
    fixture = fixture or FIXTURE
    fx = json.loads(fixture.read_text())
    questions = followup_conversations(fx) if followups else fx["questions"]
    results = []
    for i, q in enumerate(questions[: limit or None]):
        try:
            ans, wall = _stream(q["question"], q["corpus_id"], synthesizer, history=q.get("history"), compiler=compiler)
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
        cite = citation_stats(ans, rec)
        results.append({**q, "wall_s": round(wall, 2), "phase_ms": (rec.get("meta") or {}).get("phase_ms"), **cite,
                        "gold_in_retrieved": _in("retrieved"),
                        "gold_in_union": _in("union"),
                        "gold_in_pre_rerank": _in("pre_rerank"),
                        "gold_selected_rank": best,
                        "gold_cited": _in("cited"),
                        "death": sorted(deaths, key=order.index)[0],
                        "counts": fun.get("counts"), "lane_counts": fun.get("lane_counts"),
                        "verdict": (ans.get("result") or {}).get("meta", {}).get("verdict") if isinstance(ans.get("result"), dict) else None})
        plan = ((rec.get("meta") or {}).get("chat_plan")) or {}
        results[-1]["chat_plan"] = {k: plan.get(k) for k in ("task_type", "retrieval_required", "retrieval_skipped", "retrieval_query", "compiler")}
        print(f"[{i+1}/{len(questions)}] {q['corpus_id']:14s} {results[-1].get('death','?'):26s} rank={results[-1].get('gold_selected_rank')} {wall:5.1f}s  {q['question'][:40]} | {(plan.get('retrieval_query') or '')[:50]}", flush=True)
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
        "synthesizer": synthesizer or "default", "tag": tag, "compiler": compiler or "server-default",
        "retrieval": RETRIEVAL_OVERRIDE or "server-default",
        "fixture": (str(fixture.relative_to(ROOT)) if str(fixture).startswith(str(ROOT)) else str(fixture)), "fixture_version": fx.get("version"),
        "followups": followups, "recovery": (recovery_against(results, reference) if reference else None),
        "compiler_fallbacks": sum(1 for r in ok if ((r.get("chat_plan") or {}).get("compiler") or {}).get("fallback")),
        "citation_precision_mean": (round(sum(r["citation_precision"] for r in ok if r.get("citation_precision") is not None)
                                          / max(1, sum(1 for r in ok if r.get("citation_precision") is not None)), 3)),
        "answers_with_tags": sum(1 for r in ok if r.get("tags_total")),
        "tags_total": sum(r.get("tags_total") or 0 for r in ok), "tags_valid": sum(r.get("tags_valid") or 0 for r in ok),
        "abstain_markers": sum(1 for r in ok if r.get("abstain_marker")),
        "engines": dict(__import__("collections").Counter(r.get("engine") for r in ok)),
        "arrivals_missing_total": sum(r.get("arrivals_missing") or 0 for r in ok),
        "turns_with_arrivals": sum(1 for r in ok if r.get("arrivals_n")),
        "degraded_turns": sum(1 for r in ok if r.get("degraded_components")),
        "answer_chars_p50": (sorted(r.get("answer_chars") or 0 for r in ok)[len(ok) // 2] if ok else 0),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chat-baseline-{tag}.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, default=str))
    _write_md(tag, summary, results)
    print(json.dumps(summary, indent=1))
    return summary


def _write_md(tag: str, summary: dict, results: list) -> None:
    fx = json.loads(FIXTURE.read_text())
    import datetime as _dt
    today = _dt.date.today().isoformat()
    md = ["---", f"title: \"Chat baseline — {tag}\"", "owner: governance", f"last_reviewed: {today}", f"last_touched: {today}",
          "status: measured", "---", "", f"# Chat baseline — {tag}", "",
          f"Fixture `{summary.get('fixture') or FIXTURE.relative_to(ROOT)}` ({summary.get('fixture_version') or fx.get('version')}, seed {fx.get('seed')}); synthesizer {summary['synthesizer']}; compiler {summary.get('compiler')}; retrieval {summary.get('retrieval')}; follow-ups {summary.get('followups')}; HYBRID via /chat/stream.", "",
          *([f"Recovery vs `{summary['recovery']['reference']}`: paired {summary['recovery']['paired']}, both {summary['recovery']['both']}, "
             f"only reference {summary['recovery']['only_reference']}, only this {summary['recovery']['only_this']}, neither {summary['recovery']['neither']}; "
             f"reference hit@10 {summary['recovery']['reference_hit@10']}; **hit@10 on the reference-retrievable subset {summary['recovery']['subset_hit@10']}**.", ""]
            if summary.get("recovery") else []),
          "| metric | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items() if k not in ("tag", "synthesizer")] + ["", "| corpus | question | death | selected rank | wall s |", "|---|---|---|---|---|"]
    md += [f"| {r['corpus_id']} | {r['question'][:60]} | {r.get('death', r.get('error'))} | {r.get('gold_selected_rank')} | {r.get('wall_s')} |" for r in results]
    (OUT_DIR / f"chat-baseline-{tag}.md").write_text("\n".join(md) + "\n")


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
    ap.add_argument("--render", action="store_true", help="rewrite the .md from an existing chat-baseline-<tag>.json")
    ap.add_argument("--compiler", default=None, help="per-request POLYMATH_CHAT_COMPILER override: off | shadow | on")
    ap.add_argument("--followups", action="store_true", help="run the derived 2-turn follow-up conversations instead of the plain questions")
    ap.add_argument("--fixture", default=None, help="fixture file to run (default eval/fixtures/chat_baseline_B.json; L = eval/fixtures/chat_lexical_L.json)")
    ap.add_argument("--retrieval", default=None, help="per-request POLYMATH_CHAT_RETRIEVAL override: v1 | v2")
    ap.add_argument("--build-lexical", action="store_true", help="build eval/fixtures/chat_lexical_L.json (acronyms/identifiers with df 1-2)")
    ap.add_argument("--reference", default=None, help="tag of a same-fixture run to pair with (recovery: hit@10 on the subset the reference retrieved)")
    a = ap.parse_args()
    if a.render:
        d = json.loads((OUT_DIR / f"chat-baseline-{a.tag}.json").read_text())
        _write_md(a.tag, d["summary"], d["results"])
        print(f"rendered {OUT_DIR / f'chat-baseline-{a.tag}.md'}")
        return 0
    if a.build:
        fx = build(a.per_corpus, [c.strip() for c in a.corpora.split(",") if c.strip()], a.seed)
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(fx, indent=1))
        print(f"wrote {FIXTURE} with {len(fx['questions'])} questions")
    global RETRIEVAL_OVERRIDE
    RETRIEVAL_OVERRIDE = a.retrieval
    if a.build_lexical:
        fx = build_lexical(a.per_corpus, [c for c in a.corpora.split(",") if c], a.seed)
        LEXICAL_FIXTURE.write_text(json.dumps(fx, indent=1, ensure_ascii=False))
        kinds = __import__("collections").Counter(q["kind"] for q in fx["questions"])
        print(f"wrote {LEXICAL_FIXTURE.relative_to(ROOT)}: {len(fx['questions'])} questions {dict(kinds)}")
        for q in fx["questions"]:
            print(f"  {q['corpus_id']:14s} {q['kind']:10s} df={q['df']} df_ci={q.get('df_ci')} {q['term']}")
    if a.run:
        fixture = Path(a.fixture) if a.fixture else None
        if fixture is not None:
            fixture = (fixture if fixture.is_absolute() else (ROOT / fixture) if (ROOT / fixture).exists() else fixture).resolve()
        run(a.tag, None if a.llm else a.synthesizer, a.limit, compiler=a.compiler, followups=a.followups, reference=a.reference, fixture=fixture)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
