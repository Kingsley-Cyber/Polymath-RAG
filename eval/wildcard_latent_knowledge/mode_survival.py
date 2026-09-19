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
        # per-mode DISCOVERY DELTA: specialized families a mode's CANDIDATE pool has that FAST's lacks
        fast_cand = set((per_mode.get("FAST") or {}).get("candidate_spec") or [])
        discovery_delta = {lab: sorted(set((per_mode.get(lab) or {}).get("candidate_spec") or []) - fast_cand)
                           for lab, _ in MODES if lab != "FAST"}
        # did each mode's own discovery survive into its FINAL evidence?
        delta_survival = {lab: sorted(set(discovery_delta.get(lab, [])) &
                                      set((per_mode.get(lab) or {}).get("final_spec") or []))
                          for lab in discovery_delta}
        # ORIGIN PROVENANCE per specialized family: which modes carry it at candidate / final + nominated
        origin = {}
        allf = sorted(set().union(*[set((per_mode.get(l) or {}).get("candidate_spec") or []) for l, _ in MODES])) if per_mode else []
        for fam in allf:
            origin[fam] = {"nominated": fam in nom_spec,
                           "candidate_modes": [l for l, _ in MODES if fam in ((per_mode.get(l) or {}).get("candidate_spec") or [])],
                           "final_modes": [l for l, _ in MODES if fam in ((per_mode.get(l) or {}).get("final_spec") or [])]}
        cases.append({"id": spq["id"], "retrieval_required": plan.retrieval_required,
                      "scout_spec": nom_spec, "scout_deep": nom_deep, "per_mode": per_mode,
                      "candidate_family_union": cand_union, "final_family_union": final_union,
                      "candidate_vs_final_shrink": len(cand_union) - len(final_union),
                      "discovery_delta": discovery_delta, "delta_survival": delta_survival,
                      "origin_provenance": origin,
                      "deep_family_survival": deep_survival, "expected_weakness": spq.get("baseline_weakness")})
        # print a compact survival line for the deep family
        dl = []
        for fam in dkw[:2]:
            r = deep_survival[fam]
            dl.append(f"{fam}: nom={int(r['nominated'])} " + " ".join(
                f"{lab[0]}[c{int(r[lab]['candidate'])}/f{int(r[lab]['final'])}]" for lab, _ in MODES))
        print(f"  {spq['id']:24s} route={plan.retrieval_required!s:5} | " + " ; ".join(dl), flush=True)

    # ---- clean funnel metrics (owner definitions): DISCOVERED -> CANDIDATE -> SURVIVED -> FINAL ----
    routed = [c for c in cases if c["retrieval_required"]]
    n = len(cases)

    def _any_deep(c, stage):
        return any(any(r[l][stage] for l, _ in MODES) for r in c["deep_family_survival"].values())
    funnel = {
        "routing_success": round(len(routed) / n, 3),
        "specialized_discovery_at_candidate": round(sum(1 for c in routed if c["candidate_family_union"]) / n, 3),
        "deep_target_reach_at_candidate": round(sum(1 for c in routed if _any_deep(c, "candidate")) / n, 3),
        "deep_survival_at_final": round(sum(1 for c in routed if _any_deep(c, "final")) / n, 3),
        "wildcard_value_add": round(sum(1 for c in routed if c["discovery_delta"].get("WILDCARD")) / n, 3),
    }
    # per-mode: rerank survival (spec + deep) + discovery-delta survival
    per_mode_agg = {}
    for label, _ in MODES:
        cs_tot = fs_tot = dcand = dsurv = dd = dds = 0
        for c in routed:
            m = c["per_mode"].get(label, {})
            cs, fs = set(m.get("candidate_spec") or []), set(m.get("final_spec") or [])
            cs_tot += len(cs); fs_tot += len(cs & fs)
            dcand += len(set(m.get("candidate_deep") or []))
            dsurv += len(set(m.get("candidate_deep") or []) & set(m.get("final_deep") or []))
            if label != "FAST":
                delta = set(c["discovery_delta"].get(label, []))
                dd += len(delta); dds += len(delta & fs)
        per_mode_agg[label] = {
            "rerank_survival_spec": round(fs_tot / cs_tot, 3) if cs_tot else None,
            "deep_candidate_families": dcand, "deep_survived_rerank": dsurv,
            "discovery_delta_families": (dd if label != "FAST" else None),
            "discovery_delta_survived_rerank": (dds if label != "FAST" else None)}
    cand_fams = len({f for c in routed for f in c["candidate_family_union"]})
    final_fams = len({f for c in routed for f in c["final_family_union"]})
    return {"benchmark": "LATENT-KNOWLEDGE-10", "modes": [m[0] for m in MODES],
            "wall_s": round(time.time() - t0, 1),
            "funnel_metrics": funnel, "per_mode": per_mode_agg,
            "candidate_family_diversity": cand_fams, "final_family_diversity": final_fams,
            "candidate_to_final_shrink": cand_fams - final_fams,
            "note": "source-family detection (title/author). content-family (concept aliases in chunk text) deferred to v2.",
            "cases": cases}


def main() -> int:
    out = run()
    stamp = time.strftime("%Y-%m-%d")
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / f"survival-{stamp}.json")
    path.write_text(json.dumps(out, indent=1))
    print("\n== FUNNEL METRICS ==")
    for k, v in out["funnel_metrics"].items():
        print(f"  {k:36s} {v}")
    print("== PER-MODE (rerank survival / deep cand->survived / discovery-delta survived) ==")
    for lab, v in out["per_mode"].items():
        print(f"  {lab:9s} rerank_survival={v['rerank_survival_spec']}  "
              f"deep={v['deep_survived_rerank']}/{v['deep_candidate_families']}  "
              f"delta_surv={v['discovery_delta_survived_rerank']}/{v['discovery_delta_families']}")
    print(f"  candidate family diversity={out['candidate_family_diversity']} -> final={out['final_family_diversity']}"
          f"  (shrink {out['candidate_to_final_shrink']})")
    print(f"\nWROTE {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
