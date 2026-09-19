#!/usr/bin/env python3
"""WLK2A stage tracer (READ-ONLY) — latent concept activation / candidate deepening.

For wc01/wc03/wc05/wc06/wc07/wc10 x {FAST,HYBRID,GRAPH,WILDCARD} trace an expert family through:
  q0 -> scout noms -> plan subqueries/bridges -> document candidate (rank) -> selected-for-deepening
  (top-6) -> chunk union -> rerank query used -> rerank outcome -> exact loss stage.

Decisive experiment (answers Q3/Q5): the reranker scores (result.context.query, chunk) where
result.context.query = retrieval_text_for(plan) = the PRIMARY (q0) query ONLY. So a chunk retrieved by
an aspect/PROFILE bridge subquery is judged against q0, not against the bridge that justified it. For
each expert chunk that reached the union sub-floor against q0, RE-SCORE it (same reranker sidecar,
_rerank_children) against (a) each subquery that retrieved it and (b) the PROFILE-expansion bridges. If
a bridge lifts it above the floor (logit>=0) while q0 did not, the query-representation fix is proven
viable; if not, the chunk is genuinely irrelevant (deepening/nomination or null).

Read-only. No repo/production change. Needs the live embed/rerank sidecars.
"""
from __future__ import annotations
import json, os, pathlib, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[1]
MODES = [("FAST", "VECTOR"), ("HYBRID", "HYBRID"), ("GRAPH", "GRAPH"), ("WILDCARD", "WILDCARD")]
CASES = {"wc01_fake_smile", "wc03_villain_won", "wc05_ordinary_fast",
         "wc06_unpredictable_fighter", "wc07_silent_authority", "wc10_suppressed_grief"}
FLOOR_LOGIT = 0.0  # aspect_weak_floor 0.5 on the sigmoid <=> logit >= 0


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


def main() -> int:
    _env(); sys.path.insert(0, str(ROOT / "shared"))
    import orchestrator.api.chat_retrieval as CR
    from orchestrator.api.ui import _profile_scout, _compile_chat_plan
    from polymath_shared.chat_plan import retrieval_text_for

    spec = json.loads((ROOT / "eval/wildcard_latent_knowledge/WILDCARD-LATENT-KNOWLEDGE-10.json").read_text())
    docmap = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())

    real_select = CR.select_evidence
    captured: list = []

    def wrapped_select(result, budget, **kw):
        final, trace = real_select(result, budget, **kw)
        captured.append((result, budget, list(final), trace))
        return final, trace
    CR.select_evidence = wrapped_select

    def rescore(query_text, row):
        try:
            out = CR._rerank_children(query_text, [dict(row)])
            return out[0].get("rerank_score") if out else None
        except Exception as e:
            return f"<err {type(e).__name__}>"

    out = {}
    for spq in spec["queries"]:
        if spq["id"] not in CASES:
            continue
        q = spq["query"]
        expert_kw = sorted(set(spq["specialized_keywords"]) | set(spq["deep_keywords"]))
        deep_kw = set(spq["deep_keywords"])

        def _fam(name):
            return sorted({k for k in expert_kw if k.lower() in (name or "").lower()})

        plan = _compile_chat_plan(q, [], ["cinema"])
        try:
            _, sr, _ = _profile_scout(q, ["cinema"])
            scout = [(_dn(docmap, getattr(n, "doc_id", "")), getattr(n, "doc_id", "")) for n in (getattr(sr, "nominations", None) or [])]
        except Exception as e:
            scout = []
        scout_names = [s[0] for s in scout]
        # plan subqueries / bridges (mode-independent)
        qmap = {}
        subq_dump = []
        for x in plan.queries:
            qmap[x.id] = x
            subq_dump.append({"id": x.id, "type": x.type, "origin": getattr(x, "origin", "USER"),
                              "role": getattr(x, "role", ""), "query": x.query,
                              "inspired_by_profile": [_dn(docmap, d) for d in (getattr(x, "inspired_by_profile", None) or [])],
                              "target": getattr(x, "target", None)})
        profile_bridges = [(x.id, x.query) for x in plan.queries if getattr(x, "origin", "USER") == "PROFILE"]
        rtext = retrieval_text_for(plan)
        subs = tuple((x.id, x.type, x.query, x.weight) for x in plan.queries if x.type != "PRIMARY")
        exact = tuple(plan.exact_terms)
        scout_expert = sorted({k for k in expert_kw if any(k.lower() in (s or "").lower() for s in scout_names)})
        case = {"query": q, "expert_kw": expert_kw, "rerank_query_is_primary_only": rtext,
                "scout_expert_families": scout_expert, "n_subqueries": len(subs),
                "profile_bridges": [b[1] for b in profile_bridges], "subqueries": subq_dump, "modes": {}}
        expert_union_chunks = {}   # chunk_id -> {row, q0_score, retr_subq_ids, families, doc}
        if plan.retrieval_required:
            for label, mode in MODES:
                captured.clear()
                try:
                    CR.chat_retrieve_mode(mode, rtext, "cinema", exact_terms=exact, subqueries=subs)
                except Exception as e:
                    case["modes"][label] = {"error": f"{type(e).__name__}: {e}"}; continue
                if not captured:
                    case["modes"][label] = {"error": "no capture"}; continue
                result, budget, final, trace = max(captured, key=lambda t: len(t[0].union))
                urow = [c.to_row() for c in result.union]
                rank_of = {r["chunk_id"]: i for i, r in enumerate(urow)}
                g3 = trace.get("g3_scores") or {}
                final_set = set(trace.get("final") or [])
                # document candidates (all) + selected-for-deepening (top-6)
                docs_all = [(d.doc_id, getattr(d, "aggregate_rank", None)) for d in result.documents]
                sel_ids = {d.doc_id for d in result.selected_documents}
                expert_docs = [{"doc": _dn(docmap, did), "families": _fam(_dn(docmap, did)),
                                "doc_rank": ar, "selected_for_deepening": did in sel_ids}
                               for did, ar in docs_all if _fam(_dn(docmap, did))]
                # expert chunks in union
                deep_rows = [r for r in urow if _fam(_dn(docmap, r.get("doc_id")))]
                eu = []
                for r in deep_rows:
                    cid = r["chunk_id"]
                    retr = [qid for qid in (r.get("query_ids") or [])]
                    fam = _fam(_dn(docmap, r["doc_id"]))
                    eu.append({"doc": _dn(docmap, r["doc_id"]), "families": fam, "fused_rank": rank_of.get(cid),
                               "q0_rerank_score": g3.get(cid, r.get("rerank_score")),
                               "retrieving_subqueries": retr, "in_final": cid in final_set,
                               "is_deep": any(f in deep_kw for f in fam)})
                    if cid not in expert_union_chunks:
                        expert_union_chunks[cid] = {"row": r, "q0_score": g3.get(cid, r.get("rerank_score")),
                                                    "retr": retr, "families": fam, "doc": _dn(docmap, r["doc_id"])}
                case["modes"][label] = {
                    "union_size": len(urow), "expert_docs_nominated": expert_docs,
                    "expert_docs_selected_for_deepening": sum(1 for e in expert_docs if e["selected_for_deepening"]),
                    "expert_chunks_in_union": len(deep_rows), "expert_chunk_detail": eu}
                print(f"  {spq['id']:24s} {label:8s} exp_docs={len(expert_docs)}(sel {sum(1 for e in expert_docs if e['selected_for_deepening'])}) "
                      f"exp_chunks_union={len(deep_rows)}", flush=True)
        # ---- RE-SCORE EXPERIMENT (mode-independent; dedup by chunk_id) ----
        rescore_rows = []
        for cid, info in list(expert_union_chunks.items())[:8]:
            row = info["row"]; q0s = info["q0_score"]
            # bridges = the subqueries that retrieved it (non-PRIMARY) + all PROFILE bridges
            bridge_texts = {}
            for qid in info["retr"]:
                xq = qmap.get(qid)
                if xq and xq.type != "PRIMARY":
                    bridge_texts[f"retr:{qid}:{getattr(xq,'origin','?')}"] = xq.query
            for bid, bq in profile_bridges:
                bridge_texts[f"profile:{bid}"] = bq
            scored = {tag: rescore(txt, row) for tag, txt in list(bridge_texts.items())[:5]}
            numeric = [s for s in scored.values() if isinstance(s, (int, float))]
            best = max(numeric) if numeric else None
            rescore_rows.append({"doc": info["doc"], "families": info["families"], "chunk": cid[:10],
                                 "q0_score": q0s, "bridge_scores": scored,
                                 "best_bridge_score": best,
                                 "q0_below_floor": isinstance(q0s, (int, float)) and q0s < FLOOR_LOGIT,
                                 "bridge_clears_floor": isinstance(best, (int, float)) and best >= FLOOR_LOGIT})
            bstr = f"q0={q0s if q0s is None else round(q0s,2)} best_bridge={best if best is None else round(best,2)}"
            print(f"      RESCORE {info['doc'][:34]:34s} {info['families']} {bstr} "
                  f"{'<< BRIDGE CLEARS FLOOR' if (isinstance(best,(int,float)) and best>=FLOOR_LOGIT) else ''}", flush=True)
        case["rescore_experiment"] = rescore_rows
        out[spq["id"]] = case

    CR.select_evidence = real_select
    dest = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "wlk2a_forensics.json")
    dest.write_text(json.dumps(out, indent=1, default=str))
    print(f"\nWROTE {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
