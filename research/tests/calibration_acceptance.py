#!/usr/bin/env python3
"""docs/26 §6 — the calibration proves BRIDGE BEHAVIOUR, never shelf composition.

    python3 tests/calibration_acceptance.py --state run.json
        [--calibration-mode STANDARD|SOURCE_AGNOSTIC_CALIBRATION]
        [--seed-communities r/x,r/y] [--heterogeneous-docs "Always Alchemy"]
        [--trap-text "..."] [--presence presence.json]

Nine canaries, each PASS / FAIL / NOT_TRIGGERED / NOT_EVALUATED. The run passes
when every MANDATORY canary (for the mode) is PASS and no non-advisory canary is
FAIL. Cited share of the shelf and documents cited are diagnostics and never
gate. Classes and the mandatory set come from policies.yaml (`calibration`).

  1 corpus_independence               a kept concept no source passage names (consumes the corpus-wide
                                      presence receipt from `corpus_polymath --presence` when given)
  2 heterogeneous_source_reasoning    SOURCE_AGNOSTIC_CALIBRATION only: a configured heterogeneous row fed a
                                      valid latent structure or a valid hypothesis hop (generation, not survival)
  3 noun_echo_resistance              a corpus-named concept without independent grounding was refused
  4 legitimate_corpus_overlap_survival a concept that overlaps the corpus (named OR example overlap) WITH
                                      independent grounding kept its leads
  5a open_field_population_discovery  an OPEN_FIELD community outside the seed set was instantiated with records
  5b latent_population_resolution     a LATENT lead (from an admitted latent structure) was INSTANTIATED with
                                      admitted field records that point back to it — OPEN_FIELD never counts
  6 field_originated_opportunity      a field-originated concept (FIELD_NAMED / WORKAROUND_DERIVED, not corpus-named)
                                      whose hypothesis is deepened by corpus rows
  7 irrelevant_source_rejection       a KNOWN trap row was retrieved, classified IRRELEVANT and never used downstream
  8 hypothesis_death                  a corpus-derived hypothesis was rejected BECAUSE of field evidence

Modes: STANDARD (normal research — an unrelated novel that yields nothing is not a
failure; latent resolution is advisory) and SOURCE_AGNOSTIC_CALIBRATION (the
decisive test — canaries 2 and 5b become mandatory). The mode is an explicit
flag, never inferred from --heterogeneous-docs.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import graph as graphmod  # noqa: E402
import provenance as _prov  # noqa: E402
import utilization as _util  # noqa: E402

MODES = ("STANDARD", "SOURCE_AGNOSTIC_CALIBRATION")
MANDATORY = ["corpus_independence", "open_field_population_discovery", "field_originated_opportunity",
             "irrelevant_source_rejection", "hypothesis_death"]
ADVISORY = ["latent_population_resolution"]
SOURCE_AGNOSTIC_MANDATORY = ["heterogeneous_source_reasoning", "latent_population_resolution"]


def _norm(c):
    return re.sub(r"^r/", "", str(c or "").strip().lower())


def _leads(state):
    d = state["data"]
    return [l for l in (d.get("population_leads") or []) + (d.get("community_leads") or []) if isinstance(l, dict)]


def _rows(state):
    return {r["id"]: r for r in state["data"].get("corpus_evidence") or [] if isinstance(r, dict) and r.get("id")}


def _is_latent(lead: dict) -> bool:
    return lead.get("source_lane") == "LATENT" or lead.get("search_mode") == "LATENT"


def evaluate(state: dict, policies: dict, seed_communities: set | None = None, heterogeneous_docs: set | None = None,
             trap_texts: set | None = None, mode: str = "STANDARD", presence: list | None = None) -> dict:
    if mode not in MODES:
        raise ValueError(f"calibration mode must be one of {MODES}, got {mode!r}")
    if presence:
        state = copy.deepcopy(state)
        by_id = {r.get("concept_id"): r for r in state["data"].get("corpus_presence") or [] if isinstance(r, dict)}
        by_id.update({r.get("concept_id"): r for r in presence if isinstance(r, dict)})
        state["data"]["corpus_presence"] = list(by_id.values())
    d = state["data"]
    cal = policies.get("calibration") or {}
    trap_texts = set(trap_texts or set()) | {str(t) for t in (cal.get("trap_texts") or [])}
    mandatory = list(cal.get("mandatory") or MANDATORY)
    advisory = list(cal.get("advisory") or ADVISORY)
    if mode == "SOURCE_AGNOSTIC_CALIBRATION":
        mandatory += [k for k in (cal.get("source_agnostic_mandatory") or SOURCE_AGNOSTIC_MANDATORY) if k not in mandatory]
    advisory = [k for k in advisory if k not in mandatory]
    echo = (policies.get("provenance") or {}).get("echo_verdict", "CORPUS_ECHO_UNGROUNDED")
    concepts = {c["id"]: c for c in d.get("product_concepts") or [] if isinstance(c, dict)}
    # lineage rows are recomputed deterministically from the state so every receipt (field_origin,
    # corpus_presence) is present whatever version wrote the state
    prov = [_prov.lineage(c, state, policies) for c in concepts.values()]
    kept = [r for r in prov if r.get("verdict") != echo]
    rows = _rows(state)
    rel = d.get("row_relevance") or {}
    hyps = {h["id"]: h for h in d.get("hypotheses") or [] if isinstance(h, dict)}
    def hop_rows(h):
        return {rid for v in (h.get("hop_refs") or {}).values() for rid in (v or []) if rid in rows}
    excluded_ids = {l.get("concept_id") for l in d.get("excluded_leads") or []}
    seed = {_norm(x) for x in (seed_communities or set())} | {_norm(c) for c in d.get("communities") or []}
    seed |= {_norm(l.get("community_key") or l.get("name")) for l in _leads(state) if l.get("seed_population")}
    recs = {r["id"]: r for r in d.get("field_records") or [] if isinstance(r, dict) and r.get("id")}
    structs = {s["id"] for s in d.get("latent_structures") or [] if isinstance(s, dict) and s.get("id")}

    checks = {}
    # 1 corpus independence (presence receipts consumed through lineage)
    free = [r["concept"] for r in kept if r.get("corpus_named") is False]
    checks["corpus_independence"] = {"status": "PASS" if free else "FAIL", "hits": free[:5], "kept_concepts": len(kept),
                                     "presence_audited": sum(1 for r in kept if r.get("corpus_presence")),
                                     "named_by_presence_only": [r["concept"] for r in kept if r.get("corpus_presence") and r["corpus_presence"].get("named")
                                                                and not _prov.corpus_named(concepts[r["concept_id"]], state)["named"]][:5]}
    # 2 heterogeneous-source reasoning — measured ONLY in the dedicated mode; generation, never survival
    het_rows = set()
    if heterogeneous_docs:
        het_rows = {rid for rid, r in rows.items() if any(s.lower() in f"{r.get('title') or ''} {r.get('doc_id') or ''} {r.get('source') or ''}".lower() for s in heterogeneous_docs)}
    if mode != "SOURCE_AGNOSTIC_CALIBRATION":
        checks["heterogeneous_source_reasoning"] = {"status": "NOT_EVALUATED", "rows_from_configured_docs": len(het_rows),
                                                    "note": "any source MAY generate, no source MUST — evaluated only under --calibration-mode SOURCE_AGNOSTIC_CALIBRATION"}
    elif not heterogeneous_docs:
        checks["heterogeneous_source_reasoning"] = {"status": "FAIL", "note": "SOURCE_AGNOSTIC_CALIBRATION requires --heterogeneous-docs naming the heterogeneous source"}
    else:
        valid = {rid for rid in het_rows if rel.get(rid) not in (None, "IRRELEVANT")}
        s_hits = [x.get("id") for x in d.get("latent_structures") or [] if isinstance(x, dict) and set(x.get("evidence_refs") or []) & valid]
        h_hits = [h["id"] for h in hyps.values() if hop_rows(h) & valid]
        checks["heterogeneous_source_reasoning"] = {"status": "PASS" if (s_hits or h_hits) else "FAIL", "structures": s_hits[:5], "hypotheses": h_hits[:5],
                                                    "rows_from_configured_docs": len(het_rows), "rows_relevant": len(valid),
                                                    "rows_irrelevant": sum(1 for rid in het_rows if rel.get(rid) == "IRRELEVANT"),
                                                    "rows_unclassified": sum(1 for rid in het_rows if rel.get(rid) is None)}
    # 3 noun echo resistance / 4 legitimate corpus-overlap survival (named OR example overlap)
    overlapping = [r for r in prov if r.get("corpus_named") or r.get("example_overlap")]
    refused = [r["concept"] for r in overlapping if r.get("verdict") == echo]
    grounded_overlap = [r for r in overlapping if r.get("verdict") == "GROUNDED"]
    weak_overlap = [r for r in overlapping if r.get("verdict") not in ("GROUNDED", echo)]
    checks["noun_echo_resistance"] = {"status": "PASS" if refused else "NOT_TRIGGERED", "refused": refused[:5],
                                      "weakly_grounded_kept": [r["concept"] for r in weak_overlap][:5]}
    wrongly_excluded = [r["concept"] for r in grounded_overlap if r.get("concept_id") in excluded_ids]
    checks["legitimate_corpus_overlap_survival"] = {"status": "FAIL" if wrongly_excluded else ("PASS" if grounded_overlap else "NOT_TRIGGERED"),
                                                    "survivors": [r["concept"] for r in grounded_overlap][:5], "wrongly_excluded": wrongly_excluded,
                                                    "triggered_by": {"corpus_named": sum(1 for r in overlapping if r.get("corpus_named")),
                                                                     "corpus_example_overlap": sum(1 for r in overlapping if r.get("example_overlap"))}}
    # 5a open-field population discovery
    open_field = [l for l in _leads(state) if l.get("source_lane") == "OPEN_FIELD" and l.get("status") == "INSTANTIATED"
                  and l.get("record_ids") and _norm(l.get("community_key") or l.get("name")) not in seed]
    checks["open_field_population_discovery"] = {"status": "PASS" if open_field else "FAIL",
                                                 "communities": [l.get("community_key") or l.get("name") for l in open_field][:5]}
    # 5b latent population resolution — LATENT STRUCTURE → POPULATION → REAL FIELD EVIDENCE, every link checked
    resolved, unresolved = [], []
    for l in _leads(state):
        if not _is_latent(l):
            continue
        reasons = []
        sid = l.get("latent_structure_id")
        if not sid:
            reasons.append("no latent_structure_id")
        elif sid not in structs:
            reasons.append(f"latent_structure_id {sid!r} is not an admitted latent structure")
        if l.get("status") != "INSTANTIATED":
            reasons.append(f"status {l.get('status')!r}, not INSTANTIATED")
        rids = [x for x in l.get("record_ids") or [] if x]
        if not rids:
            reasons.append("no record_ids")
        back = [rid for rid in rids if rid in recs and recs[rid].get("lead_id") == l.get("id")]
        if rids and not back:
            reasons.append("no admitted field record points back to this lead")
        entry = {"lead_id": l.get("id"), "latent_structure_id": sid, "community": l.get("community_key") or l.get("name"),
                 "records_back_referenced": len(back), "reasons": reasons}
        (resolved if not reasons else unresolved).append(entry)
    checks["latent_population_resolution"] = {"status": "PASS" if resolved else "FAIL", "resolved": resolved[:5], "unresolved": unresolved[:8],
                                              "latent_leads": len(resolved) + len(unresolved),
                                              "note": None if (resolved or unresolved) else "no LATENT lead was nominated in this run"}
    # 6 field-originated opportunity deepened by the corpus
    fo = [r for r in kept if r.get("field_originated") and (r.get("hop_cites_corpus") or hop_rows(hyps.get(r.get("hypothesis_id")) or {}))]
    checks["field_originated_opportunity"] = {"status": "PASS" if fo else "FAIL", "concepts": [r["concept"] for r in fo][:5],
                                              "field_originated_total": sum(1 for r in kept if r.get("field_originated")),
                                              "origins": {r["concept"]: (r.get("field_origin") or {}).get("origin") for r in kept}}
    # 7 irrelevant-source rejection — a KNOWN retrieval trap must have been retrieved, classified IRRELEVANT,
    # and never referenced by a structure, an observation, a hop or an analogy
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
    # 8 hypothesis death — FIELD-CAUSED only
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
    overall = all(statuses.get(k) == "PASS" for k in mandatory if k in statuses) \
        and not any(s == "FAIL" for k, s in statuses.items() if k not in advisory)
    concept_receipts = [{"concept_id": r.get("concept_id"), "concept": r.get("concept"), "verdict": r.get("verdict"),
                         "corpus_named": r.get("corpus_named"), "corpus_named_by": r.get("corpus_named_by"),
                         "corpus_presence_named": (r.get("corpus_presence") or {}).get("named") if r.get("corpus_presence") else None,
                         "corpus_example_overlap": r.get("example_overlap") or [],
                         "field_origin": (r.get("field_origin") or {}).get("origin"), "field_originated": r.get("field_originated"),
                         "independent_voices": r.get("independent_voices"), "communities": r.get("communities")} for r in prov]
    cc = _prov.corpus_contribution(state)
    return {"run_id": state.get("run_id"), "verdict": state.get("verdict"), "mode": mode, "pass": overall,
            "mandatory": mandatory, "advisory": advisory, "statuses": statuses, "checks": checks,
            "concept_receipts": concept_receipts, "seed_communities": sorted(seed),
            "diagnostics": {"cited_share_of_shelf": cc["cited_share_of_shelf"], "documents_cited": cc["documents_cited"],
                            "documents_retrieved": cc["documents_retrieved"], "mechanism_only_contributions": cc["mechanism_only_contributions"],
                            "example_rows_cited": cc["example_rows_cited"],
                            "provenance_verdicts": {v: sum(1 for x in prov if x.get("verdict") == v) for v in {r.get("verdict") for r in prov}},
                            "lived_world": _util.compute(state).get("lived_world")}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True); ap.add_argument("--seed-communities", default="")
    ap.add_argument("--calibration-mode", choices=MODES, default="STANDARD", help="STANDARD (default) or SOURCE_AGNOSTIC_CALIBRATION — explicit, never inferred")
    ap.add_argument("--heterogeneous-docs", default="", help="comma-separated title/doc-id substrings of the deliberately heterogeneous documents (canary 2, dedicated mode)")
    ap.add_argument("--trap-text", action="append", default=[], help="text of a KNOWN retrieval trap that must be retrieved, classified IRRELEVANT and never used downstream (canary 7; repeatable)")
    ap.add_argument("--presence", default=None, help="CorpusPresenceReceipts written by `corpus_polymath.py --presence` (a payload {corpus_presence:[...]} or a bare list)")
    a = ap.parse_args()
    state = json.load(open(a.state, encoding="utf-8"))
    presence = None
    if a.presence:
        raw = json.load(open(a.presence, encoding="utf-8"))
        presence = raw.get("corpus_presence") if isinstance(raw, dict) else raw
    rep = evaluate(state, graphmod.load_policies(), {x for x in a.seed_communities.split(",") if x.strip()},
                   {x.strip() for x in a.heterogeneous_docs.split(",") if x.strip()}, set(a.trap_text), mode=a.calibration_mode, presence=presence)
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
