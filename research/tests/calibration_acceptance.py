#!/usr/bin/env python3
"""docs/26 §6 — the calibration proves BRIDGE BEHAVIOUR, never shelf composition.

    python3 tests/calibration_acceptance.py --state run.json
        [--seed-communities r/x,r/y] [--heterogeneous-docs "Alchemy,Gambling"]

Eight canaries, each PASS / FAIL / NOT_TRIGGERED / NOT_EVALUATED. The run
passes when every MANDATORY canary is PASS and no canary is FAIL. Cited share
of the shelf and documents cited are printed as diagnostics and never gate.
Thresholds and the mandatory set come from policies.yaml (`calibration`).

  1 corpus_independence          a kept concept no source passage names
  2 heterogeneous_source_reasoning  a hypothesis / structure built on a configured non-business document
  3 noun_echo_resistance         a corpus-named concept without independent grounding was refused
  4 legitimate_echo_survival     a corpus-named concept WITH independent grounding kept its leads
  5 latent_population_discovery an open-field or latent-derived community outside the seed set was instantiated
  6 field_originated_opportunity a field-originated concept whose hypothesis is deepened by corpus rows
  7 irrelevant_source_rejection a KNOWN trap row (--trap-text) was retrieved, classified IRRELEVANT and never used downstream
  8 hypothesis_death             a corpus-derived hypothesis was rejected BECAUSE of field evidence (contradiction / cited refs)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import graph as graphmod  # noqa: E402
import provenance as _prov  # noqa: E402
import utilization as _util  # noqa: E402

MANDATORY = ["corpus_independence", "latent_population_discovery", "field_originated_opportunity",
             "irrelevant_source_rejection", "hypothesis_death"]


def _norm(c):
    return re.sub(r"^r/", "", str(c or "").strip().lower())


def _leads(state):
    d = state["data"]
    return [l for l in (d.get("population_leads") or []) + (d.get("community_leads") or []) if isinstance(l, dict)]


def _rows(state):
    return {r["id"]: r for r in state["data"].get("corpus_evidence") or [] if isinstance(r, dict) and r.get("id")}


def evaluate(state: dict, policies: dict, seed_communities: set | None = None, heterogeneous_docs: set | None = None,
             trap_texts: set | None = None) -> dict:
    d = state["data"]
    cal = policies.get("calibration") or {}
    trap_texts = set(trap_texts or set()) | {str(t) for t in (cal.get("trap_texts") or [])}
    mandatory = list(cal.get("mandatory") or MANDATORY)
    echo = (policies.get("provenance") or {}).get("echo_verdict", "CORPUS_ECHO_UNGROUNDED")
    concepts = {c["id"]: c for c in d.get("product_concepts") or [] if isinstance(c, dict)}
    prov = d.get("provenance") or [_prov.lineage(c, state, policies) for c in concepts.values()]
    for r in prov:                                             # older states: fill the receipts the canaries need
        if "corpus_named" not in r and r.get("concept_id") in concepts:
            r.update({"corpus_named": _prov.corpus_named(concepts[r["concept_id"]], state)["named"]})
    kept = [r for r in prov if r.get("verdict") != echo]
    rows = _rows(state)
    hyps = {h["id"]: h for h in d.get("hypotheses") or [] if isinstance(h, dict)}
    def hop_rows(h):
        return {rid for v in (h.get("hop_refs") or {}).values() for rid in (v or []) if rid in rows}
    excluded_ids = {l.get("concept_id") for l in d.get("excluded_leads") or []}
    seed = {_norm(x) for x in (seed_communities or set())} | {_norm(c) for c in d.get("communities") or []}
    seed |= {_norm(l.get("community_key") or l.get("name")) for l in _leads(state) if l.get("seed_population")}

    checks = {}
    # 1 corpus independence
    free = [r["concept"] for r in kept if r.get("corpus_named") is False]
    checks["corpus_independence"] = {"status": "PASS" if free else "FAIL", "hits": free[:5], "kept_concepts": len(kept)}
    # 2 heterogeneous-source reasoning (evaluated when configured)
    if heterogeneous_docs:
        het_rows = {rid for rid, r in rows.items() if any(s.lower() in f"{r.get('title') or ''} {r.get('doc_id') or ''} {r.get('source') or ''}".lower() for s in heterogeneous_docs)}
        h_hits = [h["id"] for h in hyps.values() if hop_rows(h) & het_rows]
        s_hits = [x.get("id") for x in d.get("latent_structures") or [] if isinstance(x, dict) and set(x.get("evidence_refs") or []) & het_rows]
        checks["heterogeneous_source_reasoning"] = {"status": "PASS" if (h_hits or s_hits) else "FAIL", "hypotheses": h_hits[:5], "structures": s_hits[:5],
                                                    "rows_from_configured_docs": len(het_rows)}
    else:
        checks["heterogeneous_source_reasoning"] = {"status": "NOT_EVALUATED", "note": "pass --heterogeneous-docs to evaluate"}
    # 3 noun echo resistance / 4 legitimate echo survival
    named = [r for r in prov if r.get("corpus_named") or r.get("example_overlap")]
    refused = [r["concept"] for r in named if r.get("verdict") == echo]
    grounded_named = [r for r in named if r.get("verdict") == "GROUNDED"]
    ungrounded_named = [r for r in named if r.get("verdict") not in ("GROUNDED", echo)]
    checks["noun_echo_resistance"] = {"status": "PASS" if refused else "NOT_TRIGGERED", "refused": refused[:5],
                                      "weakly_grounded_kept": [r["concept"] for r in ungrounded_named][:5]}
    wrongly_excluded = [r["concept"] for r in grounded_named if r.get("concept_id") in excluded_ids]
    checks["legitimate_echo_survival"] = {"status": "FAIL" if wrongly_excluded else ("PASS" if grounded_named else "NOT_TRIGGERED"),
                                          "survivors": [r["concept"] for r in grounded_named][:5], "wrongly_excluded": wrongly_excluded}
    # 5 latent population discovery
    discovered = [l for l in _leads(state)
                  if (l.get("source_lane") in ("OPEN_FIELD", "LATENT") or l.get("search_mode") == "LATENT" or l.get("latent_structure_id"))
                  and l.get("record_ids") and _norm(l.get("community_key") or l.get("name")) not in seed]
    checks["latent_population_discovery"] = {"status": "PASS" if discovered else "FAIL",
                                             "communities": [l.get("community_key") or l.get("name") for l in discovered][:5]}
    # 6 field-originated opportunity deepened by the corpus
    fo = [r for r in kept if r.get("field_originated") and (r.get("hop_cites_corpus") or hop_rows(hyps.get(r.get("hypothesis_id")) or {}))]
    checks["field_originated_opportunity"] = {"status": "PASS" if fo else "FAIL", "concepts": [r["concept"] for r in fo][:5],
                                              "field_originated_total": sum(1 for r in kept if r.get("field_originated"))}
    # 7 irrelevant-source rejection — a KNOWN retrieval trap (configured text) must have been retrieved,
    # classified IRRELEVANT, and never referenced by a structure, an observation, a hop or an analogy
    rel = d.get("row_relevance") or {}
    traps = {t.lower() for t in (trap_texts or set()) if t}
    if traps:
        trap_rows = {rid for rid, r in rows.items() if any(t in f"{r.get('text') or ''} {r.get('summary') or ''}".lower() for t in traps)}
        referenced = set()
        for x in d.get("latent_structures") or []:
            referenced |= set((x or {}).get("evidence_refs") or [])
        for x in d.get("corpus_observations") or []:
            referenced |= set((x or {}).get("evidence_refs") or [])
        for h in hyps.values():
            referenced |= hop_rows(h)
        referenced |= {a.get("seed_id") for a in d.get("cross_domain_analogies") or [] if isinstance(a, dict)}
        for refs in ((d.get("primitives") or {}).get("evidence_refs") or {}).values():
            referenced |= set(refs or [])
        unclassified = sorted(rid for rid in trap_rows if rel.get(rid) is None)
        misclassified = sorted(rid for rid in trap_rows if rel.get(rid) not in (None, "IRRELEVANT"))
        leaked = sorted(trap_rows & referenced)
        status = "PASS" if trap_rows and not unclassified and not misclassified and not leaked else "FAIL"
        checks["irrelevant_source_rejection"] = {"status": status, "trap_rows_retrieved": len(trap_rows), "unclassified": unclassified[:5],
                                                 "misclassified": misclassified[:5], "leaked_downstream": leaked[:5],
                                                 "note": None if trap_rows else "configured trap text was never retrieved — configure a trap the retrieval actually returns"}
    else:
        checks["irrelevant_source_rejection"] = {"status": "NOT_EVALUATED", "irrelevant_rows_any": sum(1 for c in rel.values() if c == "IRRELEVANT"),
                                                 "note": "pass --trap-text (or set calibration.trap_texts) — a weak 'some row was marked IRRELEVANT' never proves resistance"}
    # 8 hypothesis death — FIELD-CAUSED only: a corpus-derived hypothesis is dead for this canary
    # when an admitted contradicting observation sits on one of its gaps, or a challenge / evaluation
    # that rejected or revised it cites admitted field evidence. "Rejected after a round" proves nothing.
    field_ids = {x.get("id") for x in (d.get("observations") or []) + (d.get("field_records") or []) if isinstance(x, dict)}
    contra_gaps = {o.get("gap_id") for o in d.get("observations") or [] if o.get("contradicts")}
    def _cited_field(rec):
        refs = set((rec.get("evidence_refs") or []) + (rec.get("observation_ids") or []) + (rec.get("supporting_observation_ids") or []))
        return bool(refs & field_ids)
    dead, dead_without_cause = [], []
    for h in hyps.values():
        if h.get("status") != "REJECTED" or not hop_rows(h):
            continue
        gaps = {g["id"] for g in d.get("gaps") or [] if g.get("hypothesis_id") == h.get("id")}
        by_contra = bool(gaps & contra_gaps)
        by_challenge = any(c.get("hypothesis_id") == h.get("id") and c.get("verdict") in ("REJECTED", "REVISE") and _cited_field(c)
                           for c in d.get("challenges") or [] if isinstance(c, dict))
        by_eval = any(e.get("hypothesis_id") == h.get("id") and e.get("verdict") in ("REJECT", "REVISE") and _cited_field(e)
                      for e in d.get("evaluations") or [] if isinstance(e, dict))
        (dead if (by_contra or by_challenge or by_eval) else dead_without_cause).append(h["id"])
    checks["hypothesis_death"] = {"status": "PASS" if dead else "FAIL", "field_caused": dead[:5],
                                  "rejected_without_field_cause": dead_without_cause[:5]}

    statuses = {k: v["status"] for k, v in checks.items()}
    overall = all(statuses[k] == "PASS" for k in mandatory if k in statuses) and not any(s == "FAIL" for s in statuses.values())
    cc = _prov.corpus_contribution(state)
    return {"run_id": state.get("run_id"), "verdict": state.get("verdict"), "pass": overall, "mandatory": mandatory,
            "statuses": statuses, "checks": checks, "seed_communities": sorted(seed),
            "diagnostics": {"cited_share_of_shelf": cc["cited_share_of_shelf"], "documents_cited": cc["documents_cited"],
                            "documents_retrieved": cc["documents_retrieved"], "mechanism_only_contributions": cc["mechanism_only_contributions"],
                            "example_rows_cited": cc["example_rows_cited"], "provenance_verdicts": {r.get("verdict"): sum(1 for x in prov if x.get("verdict") == r.get("verdict")) for r in prov},
                            "lived_world": _util.compute(state).get("lived_world")}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True); ap.add_argument("--seed-communities", default="")
    ap.add_argument("--heterogeneous-docs", default="", help="comma-separated title/doc-id substrings of deliberately non-business documents (canary 2)")
    ap.add_argument("--trap-text", action="append", default=[], help="text of a KNOWN retrieval trap that must be retrieved, classified IRRELEVANT and never used downstream (canary 7; repeatable)")
    a = ap.parse_args()
    state = json.load(open(a.state, encoding="utf-8"))
    rep = evaluate(state, graphmod.load_policies(), {x for x in a.seed_communities.split(",") if x.strip()},
                   {x.strip() for x in a.heterogeneous_docs.split(",") if x.strip()}, set(a.trap_text))
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
