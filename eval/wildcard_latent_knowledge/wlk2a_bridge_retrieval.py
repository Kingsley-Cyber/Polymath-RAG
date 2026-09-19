#!/usr/bin/env python3
"""WLK2A end-to-end bridge test (READ-ONLY, DIAGNOSTIC): does running the FULL pipeline with the
bridge as the primary query (bridge-driven deepening + bridge-driven rerank, the owner's
'Retrieval Lineage' architecture) surface a floor-clearing expert chunk that reaches FINAL — which
q0 never achieves? For wc01/wc05/wc07 run chat_retrieve_mode twice: (1) q0 primary (baseline),
(2) ideal concept bridge as primary. Report expert-doc chunks in union/final and their rerank scores
(now against the bridge). The ideal bridge is a DIAGNOSTIC instrument, not a production concept.
If bridge-primary surfaces expert chunks that clear the floor and reach final, the lineage
architecture is validated end-to-end; if not, the corpus chunks can't support it.
"""
from __future__ import annotations
import json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
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


def run_one(CR, _compile, retrieval_text_for, docmap, qtext, dkw):
    plan = _compile(qtext, [], ["cinema"])
    rtext = retrieval_text_for(plan)
    subs = tuple((x.id, x.type, x.query, x.weight) for x in plan.queries if x.type != "PRIMARY")
    cap = []
    real = CR.select_evidence
    CR.select_evidence = lambda result, budget, **kw: (lambda f, t: (cap.append((result, f, t)) or (f, t)))(*real(result, budget, **kw))
    try:
        CR.chat_retrieve_mode("HYBRID", rtext, "cinema", exact_terms=tuple(plan.exact_terms), subqueries=subs)
    finally:
        CR.select_evidence = real
    result, final, trace = max(cap, key=lambda t: len(t[0].union))
    g3 = trace.get("g3_scores") or {}
    final_ids = set(trace.get("final") or [])

    def _is(name):
        return any(k.lower() in (name or "").lower() for k in dkw)
    urow = [c.to_row() for c in result.union]
    exp = [r for r in urow if _is(_dn(docmap, r.get("doc_id")))]
    exp_scored = [(g3.get(r["chunk_id"]), r["chunk_id"] in final_ids, _dn(docmap, r["doc_id"]), (r.get("text") or "")[:80])
                  for r in exp]
    judged = [s for s, *_ in exp_scored if isinstance(s, (int, float))]
    in_final = [x for x in exp_scored if x[1]]
    best = max(judged) if judged else None
    best_row = max(exp_scored, key=lambda x: (x[0] if isinstance(x[0], (int, float)) else -99)) if exp_scored else None
    return {"rerank_query": rtext[:80], "expert_in_union": len(exp), "expert_judged": len(judged),
            "best_expert_rerank": best, "expert_in_final": len(in_final),
            "best_expert_doc": best_row[2] if best_row else None,
            "best_expert_text_head": best_row[3] if best_row else None}


def main():
    _env(); sys.path.insert(0, str(ROOT / "shared"))
    import orchestrator.api.chat_retrieval as CR
    from orchestrator.api.ui import _compile_chat_plan
    from polymath_shared.chat_plan import retrieval_text_for
    spec = json.loads((ROOT / "eval/wildcard_latent_knowledge/WILDCARD-LATENT-KNOWLEDGE-10.json").read_text())
    docmap = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())
    out = []
    for spq in spec["queries"]:
        cid = spq["id"]
        if cid not in IDEAL:
            continue
        dkw = DEEPKW[cid]
        base = run_one(CR, _compile_chat_plan, retrieval_text_for, docmap, spq["query"], dkw)
        brid = run_one(CR, _compile_chat_plan, retrieval_text_for, docmap, IDEAL[cid], dkw)
        rec = {"case": cid, "q0_primary": base, "bridge_primary": brid,
               "bridge_surfaces_floor_clearing_expert": isinstance(brid["best_expert_rerank"], (int, float)) and brid["best_expert_rerank"] >= 0,
               "bridge_expert_reaches_final": brid["expert_in_final"] > 0}
        out.append(rec)
        print(f"\n=== {cid} ===")
        print(f"  q0-primary   : expert_union={base['expert_in_union']} best_rerank={base['best_expert_rerank']} in_final={base['expert_in_final']}")
        print(f"  bridge-primary: expert_union={brid['expert_in_union']} best_rerank={brid['best_expert_rerank']} in_final={brid['expert_in_final']}")
        print(f"    best expert chunk (bridge): {brid['best_expert_doc']} :: {brid['best_expert_text_head']}")
        print(f"    >>> bridge surfaces floor-clearing expert in FINAL: {rec['bridge_expert_reaches_final']} "
              f"(best rerank {brid['best_expert_rerank']})")
    (ROOT / "eval/wildcard_latent_knowledge" / "WLK2A-BRIDGE-2026-09-18.json").write_text(json.dumps(out, indent=1, default=str))
    print("\nWROTE WLK2A-BRIDGE-2026-09-18.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
