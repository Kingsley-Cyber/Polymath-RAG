"""QUICK-MODEL-GRADE-V1 — a five-minute, answer-keyed grade of a model's
extraction + enrichment ability. OUTSIDE the pipeline: no DB, no tickets,
no shared limiter row. Two fixed chunks with a hand-authored answer key
(eval/v5/fleet/quick_grade_answer_key.json), every model run concurrently
through the PRODUCTION client + gate + enrichment compiler, graded on:

  extraction   entity recall / precision vs the key, relation recall
               (pair + predicate), grounding (share of proposals the gate
               rejected as unattested), JSON validity, attempts, wall
  enrichment   envelope READY?, must-cover term coverage, gist_coverage,
               wall
  production   per-model wall budget (QUICK_BUDGET_S, default 120 s)

    QUICK_MODELS="a/b,c/d" [QUICK_URL=https://openrouter.ai/api]
    [QUICK_KEY_ENV=OPENROUTER_API_KEY] [QUICK_BUDGET_S=120] [QUICK_REASONING=none|low]
    model specs may carry a per-model reasoning effort: "vendor/model@none"
        .venv/bin/python eval/v5/fleet/quick_model_grade.py

Rubric (pre-registered, transparent):
  extraction = 0.40*ent_recall + 0.20*ent_precision + 0.30*rel_recall
               + 0.10*(1 - hallucination)
  enrichment = 0.50*envelope_ready + 0.35*term_coverage + 0.15*gist_coverage
  overall    = mean of the two; A>=0.80 B>=0.65 C>=0.50 else F.
  Any model over budget, or with an invalid packet on either chunk, is F.
Exit 0 always; the table is the result.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import threading
import time
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[3]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

KEY_FILE = pathlib.Path(os.environ.get(
    "QUICK_KEY_FILE", ROOT / "eval" / "v5" / "fleet" / "quick_grade_answer_key.json"))
# Owner 2026-09-02 "REMOVE ALL FAILURES": the F-graded slugs of pass 1
# (llama-3.1-8b, granite-4.1-8b, ling-3.0-flash, inkling-small:free) are
# out. A "model@effort" spec pins a reasoning effort for that model only
# (reasoning models must run with thinking off: "qwen/qwen3.7-flash@none").
DEFAULT_MODELS = [
    "qwen/qwen3.7-flash@none",
    "ibm-granite/granite-4.0-h-micro",
    "liquid/lfm-2.5-2.6b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "mistralai/mistral-small-2603",        # reference row (known-good lane)
]

_STOP = {"the", "a", "an", "of", "and", "to", "in", "for", "on", "s"}


def norm(s: str) -> str:
    s = (s or "").lower().replace("’", "'")
    s = re.sub(r"'s\b", "", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or (len(a) >= 4 and a in b) or (len(b) >= 4 and b in a):
        return True
    ta = {t for t in a.split() if t not in _STOP}
    tb = {t for t in b.split() if t not in _STOP}
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def any_match(x: str, golds: list[str]) -> bool:
    return any(match(x, g) for g in golds)


def grade_extraction(kept_entities: list[str], kept_relations: list[tuple],
                     n_proposals: int, n_unattested: int, key: dict) -> dict:
    gold_ents = key["entities"]                     # [{"names": [...], "type": ...}]
    gold_rels = key["relations"]                    # [{"subject": [...], "object": [...], "predicates": [...]}]
    hit_e = sum(1 for g in gold_ents if any(any_match(k, g["names"]) for k in kept_entities))
    all_gold_names = [n for g in gold_ents for n in g["names"]] + key.get("also_acceptable", [])
    rel_e = sum(1 for k in kept_entities if any_match(k, all_gold_names))
    hit_r = 0.0
    for g in gold_rels:
        best = 0.0
        for (s, p, o) in kept_relations:
            if any_match(s, g["subject"]) and any_match(o, g["object"]):
                best = max(best, 1.0 if (p or "").upper() in [x.upper() for x in g["predicates"]] else 0.5)
            elif any_match(s, g["object"]) and any_match(o, g["subject"]):
                best = max(best, 0.5)
        hit_r += best
    ent_recall = hit_e / max(len(gold_ents), 1)
    ent_precision = rel_e / max(len(kept_entities), 1) if kept_entities else 0.0
    rel_recall = hit_r / max(len(gold_rels), 1)
    halluc = n_unattested / max(n_proposals, 1)
    score = 0.40 * ent_recall + 0.20 * ent_precision + 0.30 * rel_recall + 0.10 * (1 - halluc)
    return {"ent_recall": round(ent_recall, 2), "ent_precision": round(ent_precision, 2),
            "rel_recall": round(rel_recall, 2), "hallucination": round(halluc, 2),
            "kept_entities": len(kept_entities), "kept_relations": len(kept_relations),
            "score": round(score, 3)}


def grade_enrichment(cp, key: dict) -> dict:
    ready = cp is not None and cp.status == "READY" and cp.output is not None
    text = ""
    if ready:
        o = cp.output
        text = " ".join([o.summary or "", o.abstraction or "", *(o.mechanisms or []),
                         *(o.affordances or []), *(c.gist for c in (o.children or []))])
    terms = key["must_cover"]
    covered = sum(1 for t in terms if any(match(t, w) for w in [text]) or norm(t) in norm(text))
    cov = covered / max(len(terms), 1)
    gist = float(getattr(cp, "gist_coverage", 0.0) or 0.0) if cp is not None else 0.0
    score = 0.50 * (1.0 if ready else 0.0) + 0.35 * cov + 0.15 * gist
    return {"envelope": "READY" if ready else f"{getattr(cp, 'status', 'none')}:{getattr(cp, 'error_class', None)}",
            "term_coverage": round(cov, 2), "covered": f"{covered}/{len(terms)}",
            "gist_coverage": round(gist, 2), "score": round(score, 3)}


def run_model(spec: str, url: str, api_key: str, key: dict, budget_s: float, out: dict) -> None:
    from polymath_shared.latent.compiler import ParentInput, compile_parents_microbatched
    from polymath_shared.latent.contract import PRODUCTION_BOUNDS
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.gate import ChunkView, validate_and_normalize

    t0 = time.perf_counter()
    model, _, effort = spec.partition("@")
    effort = effort or os.environ.get("QUICK_REASONING", "")
    res = {"model": spec, "chunks": {}, "enrich": {}, "errors": []}
    opts = {"structured": "json"}
    if effort:
        opts["reasoning_effort"] = effort      # reasoning models: turn thinking off/down
    ex = LLMExtractionClient("cloud", url=url, model=model, api_key=api_key,
                             limiter_key=f"quick:{model}", cloud_opts=opts)
    invalid = False
    for tag, ch in key["chunks"].items():
        cid, text = ch["chunk_id"], ch["text"]
        t = time.perf_counter()
        try:
            r = ex.extract([(cid, [(cid, text)])], source_bytes=10**9, threshold_bytes=0)
        except Exception as exc:  # noqa: BLE001
            res["chunks"][tag] = {"error": f"{type(exc).__name__}: {str(exc)[:80]}", "wall_s": round(time.perf_counter() - t, 1)}
            res["errors"].append(f"extract {tag}: {type(exc).__name__}"); invalid = True
            continue
        wall = time.perf_counter() - t
        if r.packet is None:
            res["chunks"][tag] = {"error": f"quarantined:{r.error_class}", "attempts": r.attempts, "wall_s": round(wall, 1)}
            res["errors"].append(f"extract {tag}: {r.error_class}"); invalid = True
            continue
        n_prop = sum(len(getattr(it, "entities", []) or []) + len(getattr(it, "relations", []) or [])
                     for it in r.packet.items)
        norm_ = validate_and_normalize(r.packet, {cid: [ChunkView(cid, text)]})
        unatt = sum(1 for x in norm_.rejections if "UNATTESTED" in str(x.get("error_class")))
        kept_e = [m.get("text") or "" for rr in norm_.entities_by_chunk.values() for m in rr]
        kept_r = [(ev.get("subject") or "", ev.get("predicate") or "", ev.get("object") or "")
                  for rr in norm_.evidence_by_chunk.values() for ev in rr
                  if ev.get("evidence_class") == "llm_relation"]
        g = grade_extraction(kept_e, kept_r, max(n_prop, len(kept_e) + len(kept_r) + len(norm_.rejections)),
                             unatt, ch["key"])
        g.update({"attempts": r.attempts, "finish": r.finish_reason, "wall_s": round(wall, 1),
                  "tokens_out": r.tokens_out})
        res["chunks"][tag] = g

    # enrichment: the parent of chunk A, via the production compiler
    ec = LLMExtractionClient("cloud", url=url, model=model, api_key=api_key,
                             limiter_key=f"quick:{model}", cloud_opts=dict(opts))
    ecap: Counter = Counter()

    def transport(items):
        outl = []
        for item_id, system, user, max_tokens in items:
            if time.perf_counter() - t0 > budget_s:
                outl.append((item_id, "", "BUDGET")); ecap["BUDGET"] += 1; continue
            raw, err = ec.complete_one(user, system_prompt=system, max_tokens=max_tokens)
            if err:
                ecap[err] += 1
            outl.append((item_id, raw, err))
        return outl

    par = key["enrichment"]
    parent = ParentInput(par["parent_id"], [(c["chunk_id"], i, c["text"]) for i, c in enumerate(par["children"])])
    t = time.perf_counter()
    try:
        compiled = compile_parents_microbatched(transport, [parent], PRODUCTION_BOUNDS, 6000, max_concurrency=1)
        cp = compiled[0] if compiled else None
    except Exception as exc:  # noqa: BLE001
        cp = None; res["errors"].append(f"enrich: {type(exc).__name__}: {str(exc)[:80]}")
    ge = grade_enrichment(cp, par)
    ge.update({"wall_s": round(time.perf_counter() - t, 1), "capacity": dict(ecap)})
    res["enrich"] = ge

    total = time.perf_counter() - t0
    ex_scores = [c["score"] for c in res["chunks"].values() if "score" in c]
    ex_score = sum(ex_scores) / len(key["chunks"]) if ex_scores else 0.0   # missing chunk = 0
    overall = (ex_score + ge["score"]) / 2
    over_budget = total > budget_s
    if invalid or over_budget:
        letter = "F"
    else:
        letter = "A" if overall >= 0.80 else "B" if overall >= 0.65 else "C" if overall >= 0.50 else "F"
    res.update({"extraction_score": round(ex_score, 3), "enrichment_score": ge["score"],
                "overall": round(overall, 3), "grade": letter, "total_s": round(total, 1),
                "over_budget": over_budget})
    out[spec] = res


def main() -> int:
    key = json.loads(KEY_FILE.read_text())
    import hashlib
    for tag, ch in key["chunks"].items():
        got = hashlib.sha256(ch["text"].encode()).hexdigest()
        assert got == ch.get("text_sha256", got), f"answer key chunk {tag} text drifted from its sha256 pin"
    models = [m.strip() for m in os.environ.get("QUICK_MODELS", ",".join(DEFAULT_MODELS)).split(",") if m.strip()]
    url = os.environ.get("QUICK_URL", "https://openrouter.ai/api")
    api_key = os.environ[os.environ.get("QUICK_KEY_ENV", "OPENROUTER_API_KEY")]
    budget_s = float(os.environ.get("QUICK_BUDGET_S", "120"))
    out: dict = {}
    threads = [threading.Thread(target=run_model, args=(m, url, api_key, key, budget_s, out), daemon=True)
               for m in models]
    t0 = time.perf_counter()
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=budget_s * 2.5)
    print(f"\nQUICK-MODEL-GRADE  key={KEY_FILE.name}  chunks={list(key['chunks'])}  "
          f"budget={budget_s:.0f}s/model  wall={time.perf_counter() - t0:.0f}s\n")
    hdr = ("| model | grade | overall | extract | enrich | ent recall A/B | ent prec A/B | rel recall A/B | "
           "halluc A/B | envelope | terms | gist | attempts | total s |")
    print(hdr); print("|" + "---|" * (hdr.count("|") - 1))
    for m in models:
        r = out.get(m)
        if not r:
            print(f"| {m} | F | – | – | – | did not finish within {budget_s * 2.5:.0f}s | | | | | | | | |"); continue
        A, B = r["chunks"].get("A", {}), r["chunks"].get("B", {})
        f = lambda d, k: (str(d.get(k)) if k in d else ("ERR" if d.get("error") else "–"))
        e = r["enrich"]
        print(f"| {m} | **{r['grade']}** | {r['overall']} | {r['extraction_score']} | {r['enrichment_score']} | "
              f"{f(A,'ent_recall')}/{f(B,'ent_recall')} | {f(A,'ent_precision')}/{f(B,'ent_precision')} | "
              f"{f(A,'rel_recall')}/{f(B,'rel_recall')} | {f(A,'hallucination')}/{f(B,'hallucination')} | "
              f"{e.get('envelope')} | {e.get('covered')} | {e.get('gist_coverage')} | "
              f"{f(A,'attempts')}/{f(B,'attempts')} | {r['total_s']}{' OVER' if r['over_budget'] else ''} |")
    print()
    for m in models:
        r = out.get(m)
        if r and (r["errors"] or r["grade"] == "F"):
            print(f"  {m}: errors={r['errors']} chunks={{ {', '.join(f'{k}: ' + (v.get('error') or 'ok') for k, v in r['chunks'].items())} }} "
                  f"enrich={r['enrich'].get('envelope')} capacity={r['enrich'].get('capacity')}")
    out_path = pathlib.Path(os.environ.get("QUICK_OUT", "/tmp/quick_model_grade.json"))
    out_path.write_text(json.dumps(out, indent=1, default=str))
    print(f"\nraw results: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
