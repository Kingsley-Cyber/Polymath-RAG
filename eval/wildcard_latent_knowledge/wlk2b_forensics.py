#!/usr/bin/env python3
"""WLK2B forensic investigation — WHY deep material dies post-candidate (READ-ONLY).

The WLK2B slice asked: is high-value *already-discovered* deep material being suppressed by the
generic reranker/portfolio (a survivable crowding artifact), so a redundancy-aware survival pass
could rescue it without touching the cross-encoder? This probe answers that with runtime evidence.

For wc01/wc05/wc07 x {FAST,HYBRID,GRAPH,WILDCARD} it wraps candidate_engine.select_evidence
(observe + delegate — behaviour is unchanged) to capture the full CandidateResult.union (the fused
chunk pool the reranker scores, which chat_retrieve_mode does not otherwise expose) and reports, for
each deep-family chunk: its fused rank, whether it reached the judged prefix, its cross-encoder logit,
whether it survived to final; plus the winners' logits, the lexical redundancy (4-gram Jaccard)
between winners and the best lost deep chunk, and the composition trace. Deep-family detection is by
doc_id -> cinema_docmap name (the SURVIVAL-2026-09-18 detector); union CandidateEvidence rows carry an
empty source_name (joined only for FINAL), so name detection must go through the docmap.

FINDING (WLK2B-RERANK-SURVIVAL-FINDINGS-V1, 2026-09-18): NULL. Every deep chunk that reaches the
judge scores far below the relevance floor (logit<0 i.e. sigmoid<0.5; best observed -1.20/sig 0.231),
winners are NOT redundant (pairwise J~0, matching EVIDENCE-UTILITY-V1's "J=0.072"), and deep chunks
frequently never enter the chunk union at all (routed as a *document*, never deepened). The loss is
sub-floor relevance + upstream candidate under-population, not a survivable portfolio-crowding artifact.

Read-only; makes no repository or production change. Run: `.venv/bin/python
eval/wildcard_latent_knowledge/wlk2b_forensics.py [out.json]` (needs the live embed/rerank sidecars).
"""
from __future__ import annotations
import json, os, pathlib, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODES = [("FAST", "VECTOR"), ("HYBRID", "HYBRID"), ("GRAPH", "GRAPH"), ("WILDCARD", "WILDCARD")]
CASES = {"wc01_fake_smile", "wc05_ordinary_fast", "wc07_silent_authority"}


def _env():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    for f in ("POLYMATH_PROFILE_SCOUT", "POLYMATH_CHAT_PROFILE_EXPANSION", "POLYMATH_CHAT_RESOLUTION",
              "POLYMATH_CHAT_CONSTRAINT_ALIGN", "POLYMATH_CHAT_EVIDENCE_ROLES"):
        os.environ[f] = "1"


def _dn(docmap, d):
    if not d:
        return ""
    for k, v in docmap.items():
        if k == d or k.startswith(d):
            return v
    return d[:14]


def _shingles(t, n=4):
    ws = re.findall(r"\w+", (t or "").lower())
    if len(ws) < n:
        return set(ws)
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def _jac(a, b):
    A, B = _shingles(a), _shingles(b)
    return round(len(A & B) / len(A | B), 3) if (A | B) else 0.0


def main() -> int:
    _env(); sys.path.insert(0, str(ROOT / "shared"))
    import orchestrator.api.chat_retrieval as CR
    from orchestrator.api.ui import _profile_scout, _compile_chat_plan
    from polymath_shared.chat_plan import retrieval_text_for

    spec = json.loads((HERE / "WILDCARD-LATENT-KNOWLEDGE-10.json").read_text())
    docmap = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())

    real_select = CR.select_evidence
    captured: list = []

    def wrapped_select(result, budget, **kw):  # observe + delegate; behaviour unchanged
        final, trace = real_select(result, budget, **kw)
        captured.append((result, budget, list(final), trace))
        return final, trace
    CR.select_evidence = wrapped_select

    out = {}
    for spq in spec["queries"]:
        if spq["id"] not in CASES:
            continue
        q = spq["query"]; dkw = spq["deep_keywords"]
        plan = _compile_chat_plan(q, [], ["cinema"])
        try:
            _, sr, _ = _profile_scout(q, ["cinema"])
            scout = [_dn(docmap, getattr(n, "doc_id", "")) for n in (getattr(sr, "nominations", None) or [])]
        except Exception as e:
            scout = [f"<scout error {type(e).__name__}>"]
        nom_deep = sorted({k for k in dkw if any(k.lower() in (s or "").lower() for s in scout)})
        rtext = retrieval_text_for(plan)
        subs = tuple((x.id, x.type, x.query, x.weight) for x in plan.queries if x.type != "PRIMARY")
        exact = tuple(plan.exact_terms)
        case = {"query": q, "deep_keywords": dkw, "scout_docs": scout, "scout_deep_nominated": nom_deep,
                "retrieval_required": plan.retrieval_required, "modes": {}}
        if plan.retrieval_required:
            for label, mode in MODES:
                captured.clear()
                try:
                    CR.chat_retrieve_mode(mode, rtext, "cinema", exact_terms=exact, subqueries=subs)
                except Exception as e:
                    case["modes"][label] = {"error": f"{type(e).__name__}: {e}"}; continue
                if not captured:
                    case["modes"][label] = {"error": "no select_evidence call captured"}; continue
                result, budget, final, trace = max(captured, key=lambda t: len(t[0].union))
                urow = [c.to_row() for c in result.union]
                rank_of = {r["chunk_id"]: i for i, r in enumerate(urow)}
                udocs = {r["doc_id"] for r in urow}
                pre = set(trace.get("pre_g3_order") or [])
                post_rank = {cid: i for i, cid in enumerate(trace.get("post_g3_order") or [])}
                g3 = trace.get("g3_scores") or {}
                final_ids = trace.get("final") or [c.chunk_id for c in final]
                final_set = set(final_ids); final_obj = {c.chunk_id: c for c in final}

                def _rowname(r):  # union rows carry empty source_name -> resolve via docmap
                    return (r.get("source_name") or "") + " " + _dn(docmap, r.get("doc_id"))

                def _is_deep(name):
                    return sorted({k for k in dkw if k.lower() in (name or "").lower()})

                deep_rows = [r for r in urow if _is_deep(_rowname(r))]
                deep_lost = [r for r in deep_rows if r["chunk_id"] not in final_set]
                best_lost = deep_lost[0] if deep_lost else (deep_rows[0] if deep_rows else None)
                deep_detail = [{
                    "doc": _dn(docmap, r["doc_id"]), "families": _is_deep(_rowname(r)),
                    "fused_rank": rank_of.get(r["chunk_id"]), "fused_score": round(r.get("fused_score") or 0, 4),
                    "in_prefix": r["chunk_id"] in pre, "rerank_score": g3.get(r["chunk_id"], r.get("rerank_score")),
                    "post_rank": post_rank.get(r["chunk_id"]), "in_final": r["chunk_id"] in final_set,
                    "arrivals": r.get("arrivals"), "query_ids": r.get("query_ids"),
                    "text_head": (r.get("text") or "")[:110]} for r in deep_rows]
                fin_detail = []
                for cid in final_ids:
                    c = final_obj.get(cid); txt = c.text if c else ""
                    fin_detail.append({
                        "doc": _dn(docmap, c.doc_id if c else ""), "chunk_id": cid[:10],
                        "rerank_score": (g3.get(cid) if g3.get(cid) is not None else (c.rerank_score if c else None)),
                        "fused_rank": rank_of.get(cid),
                        "is_deep": bool(_is_deep((c.source_name if c else "") + " " + _dn(docmap, c.doc_id if c else ""))),
                        "redundancy_vs_best_lost_deep": (_jac(txt, best_lost.get("text")) if best_lost else None),
                        "same_doc_as_lost": bool(best_lost and c and c.doc_id == best_lost["doc_id"]),
                        "text_head": (txt or "")[:90]})
                fin_texts = [(fd["doc"], (final_obj[cid].text if cid in final_obj else "")) for cid, fd in zip(final_ids, fin_detail)]
                dup_pairs = [{"a": fin_texts[i][0], "b": fin_texts[j][0], "jac": _jac(fin_texts[i][1], fin_texts[j][1])}
                             for i in range(len(fin_texts)) for j in range(i + 1, len(fin_texts))
                             if _jac(fin_texts[i][1], fin_texts[j][1]) >= 0.12]
                comp = trace.get("composition") or {}
                case["modes"][label] = {
                    "union_size": len(urow), "union_docs": len(udocs), "prefix_size": trace.get("rerank_prefix"),
                    "synthesis_max": budget.synthesis_max, "final_size": len(final_ids), "judge": trace.get("judge"),
                    "deep_in_union": len(deep_rows), "deep_in_prefix": sum(1 for d in deep_detail if d["in_prefix"]),
                    "deep_in_final": sum(1 for d in deep_detail if d["in_final"]), "deep_detail": deep_detail,
                    "final_winners": fin_detail, "winner_dup_pairs": dup_pairs,
                    "composition": {"slots": comp.get("slots"), "doc_counts": comp.get("doc_counts"),
                                    "dominance": comp.get("dominance"), "doc_share_top": comp.get("doc_share_top"),
                                    "docs_within_gap": comp.get("docs_within_gap")},
                    "capped_out": trace.get("capped_out"), "prefix_docs": trace.get("prefix_docs")}
                dsum = " ".join(f"{d['families']}:fr{d['fused_rank']}/pre{int(d['in_prefix'])}/"
                                f"rs{d['rerank_score'] if d['rerank_score'] is None else round(d['rerank_score'],2)}/fin{int(d['in_final'])}"
                                for d in deep_detail[:3])
                print(f"  {spq['id']:22s} {label:8s} U={len(urow):3d}/{len(udocs):2d}d pre={trace.get('rerank_prefix')} "
                      f"fin={len(final_ids)} | deep u{len(deep_rows)} pre{sum(1 for d in deep_detail if d['in_prefix'])} "
                      f"fin{sum(1 for d in deep_detail if d['in_final'])} | {dsum}", flush=True)
        out[spq["id"]] = case

    CR.select_evidence = real_select
    dest = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "wlk2b_forensics.out.json")
    dest.write_text(json.dumps(out, indent=1, default=str))
    print(f"\nWROTE {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
