#!/usr/bin/env python3
"""WLK2A ceiling test (READ-ONLY, DIAGNOSTIC): is the deep-chunk survival ceiling set by BRIDGE
QUALITY (fixable) or CHUNK QUALITY (unfixable)? For wc01/wc05/wc07 grab the best-fused DEEP chunk
from the union and re-score it (same reranker) against: q0, the existing best PROFILE bridge, and an
IDEAL hand-written concept bridge derived from the query's latent need. The ideal bridges are a
DIAGNOSTIC instrument (like the benchmark's detection keywords), NEVER production concepts. If an
ideal bridge lifts the chunk above the floor (logit>=0) while q0/existing-bridge do not, the ceiling
is bridge quality -> owner = profile-expansion/bridge generation. If not, the chunks can't support it.
"""
from __future__ import annotations
import json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# DIAGNOSTIC concept bridges (query latent-need paraphrases; not book titles / not production)
IDEAL = {
 "wc01_fake_smile": "what observable facial muscle actions distinguish a genuine spontaneous smile from a deliberately performed or faked smile, around the eyes and mouth",
 "wc05_ordinary_fast": "principles of movement timing, spacing and cadence that make an ordinary-speed action read as fast and urgent on screen",
 "wc07_silent_authority": "how posture, spatial occupation and the effort quality of body movement communicate status, dominance and authority without speech",
}
DEEPKW = {"wc01_fake_smile": ["Ekman", "Facial Action", "Face Reveals", "Classifying Facial"],
          "wc05_ordinary_fast": ["Laban", "Timing for Animation"],
          "wc07_silent_authority": ["Laban", "Bartenieff", "Making Connections"]}


def _env():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    for f in ("POLYMATH_PROFILE_SCOUT", "POLYMATH_CHAT_PROFILE_EXPANSION", "POLYMATH_CHAT_RESOLUTION"):
        os.environ[f] = "1"


def _dn(docmap, d):
    for k, v in docmap.items():
        if k == d or (d and k.startswith(d)):
            return v
    return (d or "")[:14]


def main():
    _env(); sys.path.insert(0, str(ROOT / "shared"))
    import orchestrator.api.chat_retrieval as CR
    from orchestrator.api.ui import _compile_chat_plan
    from polymath_shared.chat_plan import retrieval_text_for
    spec = json.loads((ROOT / "eval/wildcard_latent_knowledge/WILDCARD-LATENT-KNOWLEDGE-10.json").read_text())
    docmap = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())
    real = CR.select_evidence; cap = []
    CR.select_evidence = lambda result, budget, **kw: (lambda f, t: (cap.append((result, f, t)) or (f, t)))(*real(result, budget, **kw))

    def rescore(qt, row):
        try:
            o = CR._rerank_children(qt, [dict(row)]); return round(o[0].get("rerank_score"), 2) if o and o[0].get("rerank_score") is not None else None
        except Exception as e:
            return f"<{type(e).__name__}>"

    out = []
    for spq in spec["queries"]:
        cid = spq["id"]
        if cid not in IDEAL:
            continue
        q = spq["query"]; dkw = DEEPKW[cid]
        plan = _compile_chat_plan(q, [], ["cinema"])
        rtext = retrieval_text_for(plan)
        subs = tuple((x.id, x.type, x.query, x.weight) for x in plan.queries if x.type != "PRIMARY")
        prof = [x.query for x in plan.queries if getattr(x, "origin", "USER") == "PROFILE"]
        cap.clear()
        CR.chat_retrieve_mode("HYBRID", rtext, "cinema", exact_terms=tuple(plan.exact_terms), subqueries=subs)
        result, final, trace = max(cap, key=lambda t: len(t[0].union))
        urow = [c.to_row() for c in result.union]
        deep = [r for r in urow if any(k.lower() in _dn(docmap, r.get("doc_id")).lower() for k in dkw)]
        if not deep:
            out.append({"case": cid, "note": "no deep chunk in union"}); continue
        # best deep chunk = lowest fused rank (best fused)
        best = deep[0]
        row = {"chunk_id": best["chunk_id"], "text": best.get("text") or ""}
        q0s = rescore(rtext, row)
        prof_s = max([s for s in (rescore(p, row) for p in prof) if isinstance(s, (int, float))], default=None)
        ideal_s = rescore(IDEAL[cid], row)
        rec = {"case": cid, "deep_doc": _dn(docmap, best["doc_id"]),
               "q0_score": q0s, "best_profile_bridge_score": prof_s, "ideal_bridge_score": ideal_s,
               "ideal_bridge_text": IDEAL[cid],
               "ceiling_is_bridge_quality": isinstance(ideal_s, (int, float)) and ideal_s >= 0 and (not isinstance(q0s, (int, float)) or q0s < 0)}
        out.append(rec)
        print(f"{cid:22s} {rec['deep_doc'][:30]:30s} q0={q0s} profile_bridge={prof_s} IDEAL={ideal_s} "
              f"{'<< GOOD BRIDGE RESCUES (ceiling=bridge quality)' if rec['ceiling_is_bridge_quality'] else '(no rescue even w/ ideal bridge)'}")
    CR.select_evidence = real
    (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (pathlib.Path(__file__).resolve().parent / "wlk2a_ceiling.out.json")).write_text(json.dumps(out, indent=1, default=str))
    print("\nWROTE ceiling json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
