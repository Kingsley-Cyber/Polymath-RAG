#!/usr/bin/env python3
"""Answer-level holdout grader (LLM-DIRECT-CANON P5). See README.md.

    .venv/bin/python eval/v5/holdout/grade_holdout.py --questions eval/v5/holdout/dev_questions.json
    .venv/bin/python eval/v5/holdout/grade_holdout.py --questions eval/v5/holdout/sealed/q.json --sealed --manifest-sha256 <sha>

Runs each question through POST /chat (HYBRID), reads citations from the
response, and grades deterministically. Dev runs never write release
evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

import psycopg

HERE = pathlib.Path(__file__).resolve().parent
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200").rstrip("/")
DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
EVIDENCE = HERE.parents[0] / "release_evidence" / "sealed_holdout.json"
ABSTAIN_MARKERS = ("i don't have enough grounded evidence", "i cannot answer", "insufficient evidence")


def chat(question: str, corpus_id: str) -> tuple[int, float, dict]:
    body = json.dumps({"message": question, "corpus_id": corpus_id, "mode": "HYBRID"}).encode()
    req = urllib.request.Request(ORCH + "/chat", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "holdout-grader/1.0"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, (time.perf_counter() - t0) * 1000, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000, json.loads(e.read() or b"{}")
    except Exception as e:  # noqa: BLE001
        return 0, (time.perf_counter() - t0) * 1000, {"error": str(e)}


def cited_docs(out: dict, doc_names: dict[str, str]) -> list[str]:
    names: set[str] = set()
    for c in out.get("citations") or []:
        if not isinstance(c, dict):
            continue
        for d in c.get("source_document_ids") or []:
            names.add(doc_names.get(str(d), str(d)))
        for loc in c.get("human_locators") or []:
            names.add(str(loc))
        if c.get("source_name"):
            names.add(str(c["source_name"]))
    return sorted(names)


def grade_one(q: dict, code: int, out: dict, cited: list[str], corpus_of_doc: dict[str, str]) -> dict:
    answer = (out.get("answer") or "") if isinstance(out, dict) else ""
    low = answer.lower()
    abstained = any(low.strip().startswith(m) for m in ABSTAIN_MARKERS)
    foreign = [c for c in cited if corpus_of_doc.get(c) not in (None, q["corpus_id"])]
    hit_doc = any(any(exp.lower() in c.lower() for c in cited) for exp in q.get("expected_docs") or [])
    phrase_ok = any(p.lower() in low for p in q.get("must_include_any") or []) if q.get("must_include_any") else True
    forbidden = [p for p in q.get("must_not_include") or [] if p.lower() in low]
    zero = {"foreign_corpus_citations": len(foreign), "answers_without_citations": 0, "errors": 0}
    if code != 200:
        verdict, why = "unexplained", f"http {code}"; zero["errors"] = 1
    elif q.get("expects_abstain"):
        verdict, why = ("supported", "abstained as expected") if abstained else ("wrong", "asserted on a nonce question")
    elif abstained:
        verdict, why = "unexplained", "abstained on an answerable question"
    elif forbidden:
        verdict, why = "wrong", f"forbidden phrase present: {forbidden}"
    elif not cited:
        verdict, why = "unexplained", "answer without citations"; zero["answers_without_citations"] = 1
    elif not hit_doc:
        verdict, why = "wrong", f"cited only unexpected documents: {cited[:3]}"
    elif not phrase_ok:
        verdict, why = "unexplained", "expected doc cited but no required phrase in the answer"
    else:
        verdict, why = "supported", "expected doc cited and required phrase present"
    return {"id": q["id"], "verdict": verdict, "why": why, "cited": cited[:6], "zero": zero,
            "answer_head": answer[:160]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--sealed", action="store_true")
    ap.add_argument("--manifest-sha256")
    a = ap.parse_args()
    qpath = pathlib.Path(a.questions); raw = qpath.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if a.sealed and (not a.manifest_sha256 or a.manifest_sha256 != sha or "sealed" not in qpath.parts):
        raise SystemExit("--sealed requires a question file under holdout/sealed/ and --manifest-sha256 matching its bytes")
    questions = json.loads(raw)
    with psycopg.connect(DSN) as conn:
        rows = conn.execute("SELECT doc_id, source_name, corpus_id FROM documents").fetchall()
    doc_names = {r[0]: r[1] for r in rows}
    corpus_of_doc = {r[1]: r[2] for r in rows}
    results = []
    for q in questions:
        code, ms, out = chat(q["question"], q["corpus_id"])
        cited = cited_docs(out, doc_names) if isinstance(out, dict) else []
        g = grade_one(q, code, out, cited, corpus_of_doc); g["wall_ms"] = round(ms)
        results.append(g)
        print(f"{q['id']:8} {g['verdict']:11} {g['wall_ms']:>6} ms  {g['why']}")
    n = len(results) or 1
    sup = round(100 * sum(r["verdict"] == "supported" for r in results) / n, 1)
    wrong = round(100 * sum(r["verdict"] == "wrong" for r in results) / n, 1)
    unexplained = sum(r["verdict"] == "unexplained" for r in results)
    zero = {k: sum(r["zero"][k] for r in results) for k in ("foreign_corpus_citations", "answers_without_citations", "errors")}
    walls = sorted(r["wall_ms"] for r in results)
    summary = {"questions": len(results), "supported_pct": sup, "wrong_pct": wrong, "unexplained": unexplained,
               "zero_tolerance": zero, "p50_ms": walls[len(walls) // 2] if walls else None,
               "p95_ms": walls[int(len(walls) * 0.95) - 1 if len(walls) > 1 else 0] if walls else None,
               "question_file": str(qpath), "manifest_sha256": sha, "sealed": bool(a.sealed),
               "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "producer": "eval/v5/holdout/grade_holdout.py", "results": results}
    print(f"supported {sup}% wrong {wrong}% unexplained {unexplained} zero_tolerance {zero} p50 {summary['p50_ms']} ms")
    if a.sealed:
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(summary, indent=1)); print(f"SEALED evidence written: {EVIDENCE}")
    else:
        # dev results are working files, never repository content (the repo
        # guard declares every tracked file; a dated result would churn it)
        out_dir = pathlib.Path(os.environ.get("POLYMATH_HOLDOUT_OUT", "/private/tmp/polymath_fleet/holdout"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"DEV-RESULTS-{dt.datetime.now().strftime('%Y-%m-%dT%H%M%S')}.json"
        out.write_text(json.dumps(summary, indent=1)); print(f"dev results (NOT evidence): {out}")
    return 0 if (sup >= 90 and wrong <= 5 and unexplained == 0 and all(v == 0 for v in zero.values())) else 1


if __name__ == "__main__":
    raise SystemExit(main())
