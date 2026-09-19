#!/usr/bin/env python3
"""WILDCARD-LATENT-KNOWLEDGE-10 harness. Runs each query under FAST + WILDCARD, captures the full
retrieval trace (routing/nomination/candidate/rerank/portfolio) via the deployed engine, runs the
WILDCARD synthesis (gemma) for the synthesis-spend check, scores CONCEPT FAMILIES (never exact book
identity), locates the stage-of-loss, and emits the six benchmark metrics. Read-only. See the spec
`WILDCARD-LATENT-KNOWLEDGE-10.json`. Run: `.venv/bin/python eval/wildcard_latent_knowledge/harness.py`.
"""
from __future__ import annotations
import json, os, pathlib, sys, time, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "http://127.0.0.1:7200"


def _load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    for f in ("POLYMATH_PROFILE_SCOUT", "POLYMATH_CHAT_PROFILE_EXPANSION", "POLYMATH_CHAT_RESOLUTION",
              "POLYMATH_CHAT_CONSTRAINT_ALIGN", "POLYMATH_CHAT_EVIDENCE_ROLES"):
        os.environ[f] = "1"


def _docname(docmap, d):
    if not d:
        return ""
    for k, v in docmap.items():
        if k == d or k.startswith(d):
            return v
    return d[:14]


def _families(docnames, keywords):
    """Which specialized/deep keyword families appear among these source names."""
    return sorted({kw for kw in keywords if any(kw.lower() in (n or "").lower() for n in docnames)})


def _synth_wildcard(query, synth):
    """One WILDCARD /chat/stream turn (real synthesis) -> answer + legend(S#->doc) + cited ids."""
    body = json.dumps({"message": query, "corpus_id": "cinema", "mode": "WILDCARD", "synthesizer": synth}).encode()
    req = urllib.request.Request(f"{BASE}/chat/stream", data=body,
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    ans, cur = {}, None
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "answer":
                try: ans = json.loads(line[5:].strip())
                except Exception: pass
    retr = ans.get("retrieval") or {}
    res = ans.get("result") or {}
    answer = (res.get("answer") if isinstance(res, dict) else res) or ""
    legend = {e.get("tag"): e.get("doc_id") for e in (retr.get("legend") or []) if e.get("tag")}
    import re
    cited_tags = set(re.findall(r"\[([SA]\d+)\]", answer))
    cited_docs = [legend.get(t) for t in cited_tags if legend.get(t)]
    return answer, legend, cited_docs, retr.get("epistemic")


def run():
    _load_env()
    sys.path.insert(0, str(ROOT / "shared"))
    from orchestrator.api.chat_retrieval import chat_retrieve_mode
    from orchestrator.api.ui import _profile_scout, _compile_chat_plan
    from polymath_shared.chat_plan import retrieval_text_for
    from polymath_shared.query_constraints import grade_evidence

    spec = json.loads((HERE / "WILDCARD-LATENT-KNOWLEDGE-10.json").read_text())
    docmap = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())
    synth_wc = spec["synthesizer_wildcard"]
    cases, t0 = [], time.time()

    for spq in spec["queries"]:
        q = spq["query"]
        spec_kw, deep_kw = spq["specialized_keywords"], spq["deep_keywords"]
        plan = _compile_chat_plan(q, [], ["cinema"])
        try:
            _, sr, _ = _profile_scout(q, ["cinema"])
            scout_docs = [_docname(docmap, getattr(n, "doc_id", "")) for n in (getattr(sr, "nominations", None) or [])]
        except Exception:
            scout_docs = []
        rtext = retrieval_text_for(plan)
        subs = tuple((x.id, x.type, x.query, x.weight) for x in plan.queries if x.type != "PRIMARY")
        exact = tuple(plan.exact_terms)

        modes = {}
        for label, mode in (("FAST", "VECTOR"), ("WILDCARD", "WILDCARD")):
            docs, cand, grades_ct = [], [], {"DIRECT": 0, "PARTIAL": 0, "RELATED": 0}
            if plan.retrieval_required:
                fast = chat_retrieve_mode(mode, rtext, "cinema", exact_terms=exact, subqueries=subs)
                ev = fast.get("evidence") or []
                seen = set()
                for c in ev:
                    dn = _docname(docmap, c.get("doc_id"))
                    if dn and dn not in seen: seen.add(dn); docs.append(dn)
                # candidate (pre-rerank) doc set from the fused union trace
                tr = fast.get("trace") or {}
                cand = sorted({_docname(docmap, c.get("doc_id")) for c in ev} |
                              {_docname(docmap, (fast.get("meta") or {}).get("_", "")) })
                gb, _ = grade_evidence(ev, plan)
                for r in gb.values(): grades_ct[r] = grades_ct.get(r, 0) + 1
            modes[label] = {"final_docs": docs, "specialized": _families(docs, spec_kw),
                            "deep": _families(docs, deep_kw), "grades": grades_ct}

        # synthesis (WILDCARD gemma) — real answer + which cited docs are specialized
        answer, legend, cited_docs, epi = _synth_wildcard(q, synth_wc) if plan.retrieval_required else ("", {}, [], None)
        cited_names = [_docname(docmap, d) for d in cited_docs]
        synth_spend = bool(_families(cited_names, spec_kw))

        # concept deltas + family reach
        wc_spec, fa_spec = set(modes["WILDCARD"]["specialized"]), set(modes["FAST"]["specialized"])
        wildcard_only = sorted(wc_spec - fa_spec)
        fast_only = sorted(fa_spec - wc_spec)
        scout_deep = _families(scout_docs, deep_kw)
        final_deep = sorted(set(modes["FAST"]["deep"]) | set(modes["WILDCARD"]["deep"]))
        specialized_discovery = bool(wc_spec or fa_spec)
        deep_target_reached = bool(final_deep)
        transformative = bool(final_deep)  # a deeper-family source that reached final evidence
        # stage-of-loss for the deeper family (last stage it survived)
        if not plan.retrieval_required:
            stage = "ROUTING"
        elif not (scout_deep or _families(modes["FAST"]["final_docs"] + modes["WILDCARD"]["final_docs"], deep_kw)):
            stage = "NOMINATION"
        elif scout_deep and not final_deep:
            stage = "RERANK"
        elif final_deep and not synth_spend and _families(cited_names, deep_kw) == []:
            stage = "SYNTHESIS"
        else:
            stage = "NONE"

        cases.append({
            "id": spq["id"], "query": q, "task_type": plan.task_type,
            "retrieval_required": plan.retrieval_required,
            "scout_nominations": scout_docs[:8], "scout_deep_family": scout_deep,
            "final_evidence_fast": modes["FAST"]["final_docs"][:8],
            "final_evidence_wildcard": modes["WILDCARD"]["final_docs"][:8],
            "grades_fast": modes["FAST"]["grades"], "grades_wildcard": modes["WILDCARD"]["grades"],
            "fast_specialized": sorted(fa_spec), "wildcard_specialized": sorted(wc_spec),
            "wildcard_only": wildcard_only, "fast_only": fast_only,
            "deep_target_reached": deep_target_reached, "final_deep_family": final_deep,
            "specialized_discovery": specialized_discovery, "transformative_discovery": transformative,
            "synthesis_spend": synth_spend, "cited_docs": sorted(set(cited_names)),
            "epistemic": epi, "stage_of_loss": stage,
            "expected_weakness": spq.get("baseline_weakness")})
        print(f"  {spq['id']:24s} route={plan.retrieval_required!s:5} stage_loss={stage:10s} "
              f"spec={specialized_discovery} deep={deep_target_reached} synth={synth_spend} wc_only={wildcard_only}",
              flush=True)

    n = len(cases)
    known_deep = [c for c in cases if c["retrieval_required"]]  # deep family expected everywhere retrieval runs
    metrics = {
        "routing_success": round(sum(c["retrieval_required"] for c in cases) / n, 3),
        "specialized_discovery_rate": round(sum(c["specialized_discovery"] for c in cases) / n, 3),
        "transformative_discovery_rate": round(sum(c["transformative_discovery"] for c in cases) / n, 3),
        "deep_target_reach": round(sum(c["deep_target_reached"] for c in known_deep) / len(known_deep), 3) if known_deep else None,
        "wildcard_value_add": round(sum(1 for c in cases if c["wildcard_only"]) / n, 3),
        "synthesis_spend_rate": round(sum(c["synthesis_spend"] for c in cases if c["specialized_discovery"]) /
                                      max(1, sum(c["specialized_discovery"] for c in cases)), 3),
    }
    stage_hist = {}
    for c in cases:
        stage_hist[c["stage_of_loss"]] = stage_hist.get(c["stage_of_loss"], 0) + 1
    return {"benchmark": spec["benchmark"], "version": spec["version"],
            "wall_s": round(time.time() - t0, 1), "metrics": metrics,
            "stage_of_loss_histogram": stage_hist, "cases": cases}


def main() -> int:
    out = run()
    stamp = time.strftime("%Y-%m-%d")
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / f"results-{stamp}.json")
    path.write_text(json.dumps(out, indent=1))
    print("\n== METRICS ==")
    for k, v in out["metrics"].items():
        print(f"  {k:30s} {v}")
    print(f"  stage_of_loss {out['stage_of_loss_histogram']}")
    print(f"\nWROTE {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
