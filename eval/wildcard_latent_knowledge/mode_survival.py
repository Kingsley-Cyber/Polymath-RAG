#!/usr/bin/env python3
"""LATENT-KNOWLEDGE-10 — concept-family SURVIVAL by stage across all four modes (40 retrieval cases).

Tests the hypothesis: the discovery layers are richer than the final evidence portfolio reveals — a
shared downstream (rerank) survival problem that erases each mode's distinct contribution. For every
query × {FAST, HYBRID, GRAPH, WILDCARD} it records whether each concept family is present at:
  NOMINATION (Scout, shared) → CANDIDATE (pre-rerank fused pool) → FINAL (post-rerank evidence).
Then computes Rerank Survival (final ∩ candidate / candidate) per mode, and per-mode DISCOVERY
(a family a mode's candidate pool has that FAST's does not). Retrieval-only (no synthesis) so it is
fast and isolates the survival question. Read-only. See WILDCARD-LATENT-KNOWLEDGE-10.json.
"""
from __future__ import annotations
import json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODES = [("FAST", "VECTOR"), ("HYBRID", "HYBRID"), ("GRAPH", "GRAPH"), ("WILDCARD", "WILDCARD")]


def _env():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    for f in ("POLYMATH_PROFILE_SCOUT", "POLYMATH_CHAT_PROFILE_EXPANSION", "POLYMATH_CHAT_RESOLUTION",
              "POLYMATH_CHAT_CONSTRAINT_ALIGN", "POLYMATH_CHAT_EVIDENCE_ROLES"):
        os.environ[f] = "1"


def _dn(docmap, d):
    if not d: return ""
    for k, v in docmap.items():
        if k == d or k.startswith(d): return v
    return d[:14]


def _fams(names, kws):
    return sorted({kw for kw in kws if any(kw.lower() in (n or "").lower() for n in names)})


def run():
    _env(); sys.path.insert(0, str(ROOT / "shared"))
    from orchestrator.api.chat_retrieval import chat_retrieve_mode
    from orchestrator.api.ui import _profile_scout, _compile_chat_plan
    from polymath_shared.chat_plan import retrieval_text_for
    from polymath_shared.query_constraints import grade_evidence
    spec = json.loads((HERE / "WILDCARD-LATENT-KNOWLEDGE-10.json").read_text())
    docmap = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())
    cases, t0 = [], time.time()

    for spq in spec["queries"]:
        q = spq["query"]; kw = spq["specialized_keywords"]; dkw = spq["deep_keywords"]
        plan = _compile_chat_plan(q, [], ["cinema"])
        try:
            _, sr, _ = _profile_scout(q, ["cinema"])
            scout = [_dn(docmap, getattr(n, "doc_id", "")) for n in (getattr(sr, "nominations", None) or [])]
        except Exception:
            scout = []
        nom_spec, nom_deep = _fams(scout, kw), _fams(scout, dkw)
        rtext = retrieval_text_for(plan)
        subs = tuple((x.id, x.type, x.query, x.weight) for x in plan.queries if x.type != "PRIMARY")
        exact = tuple(plan.exact_terms)
        per_mode = {}
        if plan.retrieval_required:
            for label, mode in MODES:
                try:
                    fast = chat_retrieve_mode(mode, rtext, "cinema", exact_terms=exact, subqueries=subs)
                except Exception as e:
                    per_mode[label] = {"error": f"{type(e).__name__}: {e}"}; continue
                ev = fast.get("evidence") or []
                tr = fast.get("meta") or {}; trace = fast.get("trace") or {}
                final_docs = sorted({_dn(docmap, c.get("doc_id")) for c in ev})
                # CANDIDATE pool (pre-rerank): fused union chunk ids -> docs, else document_candidates
                cand_ids = trace.get("funnel_union") or []
                cand_map = {c.get("chunk_id"): c.get("doc_id") for c in ev}
                cand_docs = {_dn(docmap, cand_map.get(cid)) for cid in cand_ids if cand_map.get(cid)}
                for dc in (trace.get("document_candidates") or []):
                    did = dc.get("doc_id") if isinstance(dc, dict) else None
                    if did: cand_docs.add(_dn(docmap, did))
                cand_docs |= set(final_docs)  # final are a subset of candidates by definition
                cand_docs = sorted(d for d in cand_docs if d)
                gb, _ = grade_evidence(ev, plan); gc = {"DIRECT": 0, "PARTIAL": 0, "RELATED": 0}
                for r in gb.values(): gc[r] = gc.get(r, 0) + 1
                per_mode[label] = {
                    "candidate_spec": _fams(cand_docs, kw), "candidate_deep": _fams(cand_docs, dkw),
                    "final_spec": _fams(final_docs, kw), "final_deep": _fams(final_docs, dkw),
                    "grades": gc, "n_candidate_docs": len(cand_docs), "n_final_docs": len(final_docs)}
        # cross-mode: candidate diversity vs final diversity (the convergence test)
        cand_union = sorted(set().union(*[set(m.get("candidate_spec", [])) for m in per_mode.values()])) if per_mode else []
        final_union = sorted(set().union(*[set(m.get("final_spec", [])) for m in per_mode.values()])) if per_mode else []
        # deep-family survival row: nominated / per-mode candidate / per-mode final
        deep_survival = {}
        for fam in dkw:
            row = {"nominated": fam in nom_deep}
            for label, _ in MODES:
                m = per_mode.get(label, {})
                row[label] = {"candidate": fam in (m.get("candidate_deep") or []),
                              "final": fam in (m.get("final_deep") or [])}
            deep_survival[fam] = row
        cases.append({"id": spq["id"], "retrieval_required": plan.retrieval_required,
                      "scout_spec": nom_spec, "scout_deep": nom_deep, "per_mode": per_mode,
                      "candidate_family_union": cand_union, "final_family_union": final_union,
                      "candidate_vs_final_shrink": len(cand_union) - len(final_union),
                      "deep_family_survival": deep_survival, "expected_weakness": spq.get("baseline_weakness")})
        # print a compact survival line for the deep family
        dl = []
        for fam in dkw[:2]:
            r = deep_survival[fam]
            dl.append(f"{fam}: nom={int(r['nominated'])} " + " ".join(
                f"{lab[0]}[c{int(r[lab]['candidate'])}/f{int(r[lab]['final'])}]" for lab, _ in MODES))
        print(f"  {spq['id']:24s} route={plan.retrieval_required!s:5} | " + " ; ".join(dl), flush=True)

    # aggregate: rerank survival per mode (final_spec / candidate_spec), candidate>final shrink
    agg = {}
    for label, _ in MODES:
        surv, tot = 0, 0
        for c in cases:
            m = c["per_mode"].get(label, {})
            cs, fs = set(m.get("candidate_spec") or []), set(m.get("final_spec") or [])
            tot += len(cs); surv += len(cs & fs)
        agg[label] = {"rerank_survival_spec": round(surv / tot, 3) if tot else None,
                      "candidate_spec_families": tot, "survived_families": surv}
    return {"benchmark": "LATENT-KNOWLEDGE-10", "modes": [m[0] for m in MODES],
            "wall_s": round(time.time() - t0, 1), "rerank_survival_by_mode": agg, "cases": cases}


def main() -> int:
    out = run()
    stamp = time.strftime("%Y-%m-%d")
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / f"survival-{stamp}.json")
    path.write_text(json.dumps(out, indent=1))
    print("\n== RERANK SURVIVAL (final specialized families / candidate specialized families) ==")
    for lab, v in out["rerank_survival_by_mode"].items():
        print(f"  {lab:9s} survival={v['rerank_survival_spec']}  ({v['survived_families']}/{v['candidate_spec_families']})")
    shrink = sum(c["candidate_vs_final_shrink"] for c in out["cases"])
    print(f"  candidate→final family shrink (sum across cases): {shrink}")
    print(f"\nWROTE {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
