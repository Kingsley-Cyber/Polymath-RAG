#!/usr/bin/env python3
"""Report layer: views over canonical state. Facts frozen, prose optional.

  build   deterministic ReportModel JSON straight from the work state + SQLite
          (no LLM anywhere in this path — everything reproducible)
  render  ReportModel -> self-contained HTML (no external assets; light+dark)

Laws (docs/05 §13-22): reports never affect the research verdict; θ may write
an executive summary but ONLY from the ReportModel (pass --summary FILE.md);
no new facts may appear during presentation; product cards preserve discovery
origin; failures and holds are shown — a report is not sales copy.

  report.py build    --state candidates/run.json [--out model.json]
  report.py render   --model model.json --out report.html
                     [--layout FULL_RESEARCH|SOURCING|EXECUTIVE|COMMERCIAL|DECISION] [--summary sum.md]
  report.py decision --bundle bundle.json --out report.html --decision-out decision.json

GOVERNED runs (docs/27): `build_model_from_governed(journal)` builds the SAME ReportModel from a governed run journal
(python/governed_run.py) and the SAME `render` draws it — there is no second report system. In a governed dossier the
verdict and every number next to a hypothesis are TrailSignal's record, shown VERBATIM (score, confidence, coverage
gaps, refusal reason); nothing is re-ranked and the standalone `evidence_score` never appears. Field observations are
shown as TrailSignal left them: admitted, or rejected WITH the reason code.

DECISION reports (PRODUCT-DECISION-REPORT-V1 §4.5): `build_model_from_bundle(decision)` builds the SAME ReportModel from the
decision model `unit_economics.compute(bundle, policy)` returns (§4.4) and `render(model, "DECISION")` draws it. Every number
on that page is the unit-economics engine's (each with its receipt); this layer orders, formats and links, and a missing
number is shown as UNKNOWN — never blank, never guessed. A governed dossier carries the same decision section, computed from
the run's TrailSignal-admitted supplier leads and product-reality prices.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph as graphmod  # noqa: E402
import models  # noqa: E402
from adapter_receipt import polarity_for


# ------------------------------------------------------------------ build --
def build_model(state: dict) -> dict:
    d = state["data"]
    cov = state.get("satisfaction") or {}
    events = []
    try:
        import memory
        with memory.connect() as conn:
            events = [dict(r) for r in conn.execute(
                "SELECT sequence, event_type, created_at FROM events WHERE run_id=? "
                "ORDER BY sequence", (state["run_id"],)).fetchall()]
    except Exception:
        pass
    live = [h for h in d["hypotheses"] if h.get("status") == "SUPPORTED"]
    other = [h for h in d["hypotheses"] if h.get("status") != "SUPPORTED"]
    obs_by_id = {o["id"]: o for o in d["observations"]}
    return {
        "run": {"run_id": state["run_id"], "created_at": state.get("created_at"),
                "status": state["status"], "verdict": state.get("verdict"),
                "signal": (d.get("signal") or "")[:600],
                "corpus": state.get("corpus"),
                "rounds": state["rounds"]},
        "coverage": {name: {"satisfied": spec["satisfied"],
                            "roles_present": spec["roles_present"]}
                     for name, spec in (cov.get("requirements") or {}).items()},
        "independence": cov.get("independence"),
        "bridges": [{"id": h["id"], "path": h.get("path"),
                     "boundary": (h.get("evidence_boundary") or {}).get("first_inference_at"),
                     "mechanism": h.get("target_mechanism"), "status": h.get("status"),
                     "invariant": h.get("invariant"),
                     "exploratory": bool(h.get("exploratory"))}
                    for h in live + other],
        "l4_receipts": state.get("l4_receipts") or [],
        "quotes": [{"quote": o.get("quote_ref"), "source": o.get("source"),
                    "community": o.get("community"), "roles": o.get("evidence_roles")}
                   for o in d["observations"]][:14],
        "mechanisms": [{"name": m.get("name"), "status": m.get("status"),
                        "notes": m.get("notes"),
                        "support_count": len(m.get("supporting_observation_ids") or [])}
                       for m in d["mechanisms"]],
        "leads": d.get("leads") or [],
        "product_concepts": d.get("product_concepts") or [],
        "sourcing_coverage": d.get("sourcing_coverage") or [],
        "utilization": d.get("utilization") or {},
        "provenance": d.get("provenance") or [],
        "excluded_leads": d.get("excluded_leads") or [],
        "corpus_packets": d.get("corpus_packets") or [],          # docs/22 (v2.2.0): evidence, never an answer
        "corpus_answers": d.get("corpus_answers") or [],          # LEGACY (< v2.2.0) runs only: a synthesis, not evidence
        "held_rejected": [{"id": h["id"], "mechanism": h.get("target_mechanism"),
                           "status": h.get("status")} for h in other],
        "unresolved": [g.get("question") for g in d["gaps"] if g.get("status") == "open"][:8],
        "intelligence": _intel_block(state),
        "market_discovery": _market_block(state),
        "product_anchored": _product_block(state),
        "capability_failures": state.get("capability_failures") or [],
        "settings": {"hash": (state.get("settings") or {}).get("hash"),
                     "preset": (state.get("settings") or {}).get("preset"),
                     "revisions": [{"revision": r.get("revision"),
                                    "patch": r.get("patch"),
                                    "requested_by": r.get("requested_by"),
                                    "effective_from_node": r.get("effective_from_node")}
                                   for r in (state.get("settings") or {}).get("revisions") or []]}
                    if state.get("settings") else None,
        "audit": {"observations": len(d["observations"]),
                  "unique_sources": len({o.get("source") for o in d["observations"]}),
                  "queries_compiled": len(d.get("queries") or []),
                  "research_rounds": state["rounds"]["research"],
                  "events": len(events),
                  "hypotheses_total": len(d["hypotheses"])},
        "built_at": models.now(),
    }


def _qualifications(out: dict) -> list[dict]:
    """TrailSignal's qualification records, EVERY qualify stage the result carries (gap B-12): a manifest that collects each qualify
    step (`{"collect_all": "qualifications", "as": "qualifications_by_step"}`) keeps market delta beside supply, where the plain include
    keeps only the newest step's list. One record once; market delta before supply."""
    rows = [q for step in out.get("qualifications_by_step") or [] if isinstance(step, list) for q in step] + list(out.get("qualifications") or [])
    seen: set = set()
    quals = []
    for q in rows:
        if isinstance(q, dict):
            key = q.get("record_id") or json.dumps(q, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                quals.append(q)
    stage_order = {"market_delta": 0, "supply": 1}
    return sorted(quals, key=lambda q: stage_order.get(str(q.get("stage") or q.get("qualification_stage")), 2))


def _distinct_questions(questions: list) -> list[str]:
    """Questions once each; the derived view clips long texts, so two copies of one question can differ only past the clip."""
    seen: set = set()
    out = []
    for q in questions:
        key = " ".join(str(q).split())[:380].lower()
        if key not in seen:
            seen.add(key)
            out.append(str(q))
    return out


def _seed_of(inp: dict) -> str:
    for k in ("seed", "seed_idea", "question", "signal", "topic", "problem"):
        if isinstance(inp.get(k), str) and inp[k].strip():
            return inp[k].strip()
    return next((v.strip() for v in inp.values() if isinstance(v, str) and v.strip()), "")


def _context_field(context, key: str) -> str | None:
    """`key: value · key: value` from an observation's free-text context — the binding's tolerant reader (`binding._context_field`).
    Absent stays absent."""
    m = re.search(r"(?:^|·|\||;|\n)\s*" + re.escape(key) + r"\s*:\s*([^·|;\n]+)", str(context or ""), re.IGNORECASE)
    return m.group(1).strip() or None if m else None


def _named_supplier(value) -> str | None:
    """A supplier the listing NAMES — the builder's `supplier: None` and an `unknown` / `unresolved (…)` placeholder name nobody (the
    binding's `supply.leads` rule, gap S-06)."""
    return value if value and not re.match(r"(?:none|unknown|unresolved)\b", value.strip().lower()) else None


def _host(url) -> str:
    return (urlparse(str(url or "")).hostname or "").removeprefix("www.")


def _alternate(rows: list[dict], key, cap: int) -> list[dict]:
    """Up to `cap` rows taken in turn from each `key` group (groups in order of first appearance, rows in their own order)."""
    groups: dict = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    queues, out = list(groups.values()), []
    while len(out) < cap and any(queues):
        for q in queues:
            if q and len(out) < cap:
                out.append(q.pop(0))
    return out


def build_model_from_governed(journal: dict) -> dict:
    """ReportModel from a governed run journal (docs/27). Deterministic given the journal; reads nothing else. The
    adapter's AdapterResultV1 is the authority for everything TrailSignal decided; the journal's receipts supply what the
    result does not carry (the verbatim quote, the URL, the price / MOQ metric) — joined by (action_id, observation_id)."""
    ev = journal.get("events") or []
    steps = [e["data"] for e in ev if e.get("kind") == "step"]
    subs = [e["data"] for e in ev if e.get("kind") == "submission"]
    result = next((e["data"]["result"] for e in reversed(ev) if e.get("kind") == "result"), None)
    out = (result or {}).get("output") or {}
    lineage = (result or {}).get("lineage") or {}
    adms = [a for a in out.get("evidence_admissions") or [] if isinstance(a, dict)]
    scores = [x for x in out.get("trail_scores") or [] if isinstance(x, dict)]
    refusals = [x for x in out.get("score_refusals") or [] if isinstance(x, dict)]
    quals = _qualifications(out)
    kind_of = {(s["step"].get("harness_action") or {}).get("action_id"): (s["step"].get("harness_action") or {}).get("action_kind")
               for s in steps if s["step"].get("step_type") == "HARNESS_ACTION"}
    receipts = [s for s in subs if s.get("kind") == "receipt" and s.get("accepted")]
    obs_index, src_count, queries = {}, set(), 0
    for r in receipts:
        pay = r.get("payload") or {}
        srcs = {x.get("source_id"): x for x in pay.get("sources") or [] if isinstance(x, dict)}
        queries += sum(int(t.get("query_count") or 0) for t in pay.get("tool_trace") or [] if isinstance(t, dict))
        for o in pay.get("observations") or []:
            if isinstance(o, dict):
                obs_index[(pay.get("action_id"), o.get("observation_id"))] = (o, srcs.get(o.get("source_id")) or {})
                src_count.add((srcs.get(o.get("source_id")) or {}).get("url"))

    def _row(adm: dict, x: dict) -> dict:
        o, src = obs_index.get((adm.get("action_id"), x.get("observation_id")), ({}, {}))
        return {"observation_id": x.get("observation_id"), "action_kind": kind_of.get(adm.get("action_id")), "claim": o.get("claim"),
                "quote": o.get("paraphrase_or_excerpt"), "url": src.get("url"), "source_class": x.get("source_class") or src.get("source_class"),
                "retrieved_at": src.get("retrieved_at"), "published_at_if_known": src.get("published_at_if_known"), "metric": o.get("metric_if_present"),
                "role": x.get("evidence_role") or o.get("evidence_role_claimed"), "polarity": x.get("polarity"), "freshness": x.get("freshness"),
                "independence_group": x.get("independence_group"), "stage": x.get("stage_relevance"), "suitability": x.get("source_suitability"),
                "hypothesis_ids": x.get("hypothesis_ids") or o.get("hypothesis_ids") or [], "admitted_evidence_id": x.get("admitted_evidence_id"),
                "reason_code": x.get("reason_code"), "detail": x.get("detail"), "duplicate_of": x.get("duplicate_of"),
                # WHO spoke and WHO sells, as the observation names them (gaps B-39 / B-40) — the independence group is the platform
                "community": _context_field(o.get("context"), "community"), "supplier": _context_field(o.get("context"), "supplier"),
                "hypothesis_relations": [r for r in x.get("hypothesis_relations") or [] if isinstance(r, dict)]}
    admitted = [_row(a, x) for a in adms for x in a.get("admitted") or [] if isinstance(x, dict)]
    rejected = [_row(a, x) for a in adms for x in a.get("rejected") or [] if isinstance(x, dict)]
    # Field + / − beside a hypothesis, counted as TrailSignal counts it (gaps B-13 / B-11): every admitted FIELD-stage record linked to
    # the hypothesis, duplicates excluded, by TrailSignal's relation to THAT hypothesis — never the derived view's 24-row sample (all
    # stages) or the global polarity. The view's sample is used only when the result carries no admission at all.
    field_records = [x for a in adms for x in a.get("admitted") or [] if isinstance(x, dict) and not x.get("duplicate_of")
                     and x.get("stage_relevance", "field_evidence") == "field_evidence"]

    def _field_counts(hid: str) -> dict:
        if not adms:
            return {}
        pols = [polarity_for(x, hid) for x in field_records if hid in (x.get("hypothesis_ids") or [])]
        return {"field_evidence": len(pols), "field_supporting": pols.count("supporting"), "field_contradicting": pols.count("contradicting"),
                "field_counts_from": "ADMISSIONS"}
    # the research loop's record of what it left open (M_unresolved: every hypothesis, every origin, uncapped)
    loop_gaps = [g for g in out.get("unresolved_research_gaps") or [] if isinstance(g, dict) and g.get("question")]
    hyps: dict = {}
    for s in steps:                                           # the newest view of each hypothesis the adapter showed the agent
        for h in (s["step"].get("context") or {}).get("hypotheses") or []:
            if isinstance(h, dict) and h.get("hypothesis_id"):
                hyps[h["hypothesis_id"]] = h
    score_by = {x.get("hypothesis_id"): x for x in scores}
    refusal_by = {x.get("hypothesis_id"): x for x in refusals}
    # AUTHORITATIVE hypothesis state (restoration reference §13.1): the result's DERIVED semantic view (ledger + outputs + admissions at
    # the end of the run); else the newest view the journal shows the agent was given; ONLY then the four-field step context, whose
    # mechanism / population / friction / support columns are empty by construction.
    views = [v for v in out.get("hypothesis_semantics") or [] if isinstance(v, dict) and isinstance(v.get("hypothesis"), dict)]
    views_from = "RESULT" if views else None
    if not views:
        for s in reversed(steps):
            shown = ((s.get("materials") or {}).get("values") or {}).get("hypothesis_semantics")
            if isinstance(shown, list) and shown:
                views, views_from = [v for v in shown if isinstance(v, dict) and isinstance(v.get("hypothesis"), dict)], f"MATERIALS@{s['step'].get('step_id')}"
                break
    view_by = {v["hypothesis"]["hypothesis_id"]: v for v in views}

    def _hyp_row(hid: str, h: dict) -> dict:
        v = view_by.get(hid)
        if not v:
            return {"hypothesis_id": hid, "statement": h.get("statement"), "mechanism": h.get("mechanism"), "population": h.get("population"),
                    "activity": h.get("activity"), "suspected_friction": h.get("suspected_friction"), "status": h.get("status"), "state_from": "STEP_CONTEXT_4_FIELDS",
                    "field_evidence": len(h.get("field_evidence_ids") or []), "knowledge_support": len(h.get("knowledge_support") or []),
                    "contradictions": len(h.get("contradictions") or []), "trail_score": score_by.get(hid), "trail_refusal": refusal_by.get(hid),
                    **(_field_counts(hid) or {"field_counts_from": "STEP_CONTEXT"})}
        hy, se, kn, fe = v["hypothesis"], v.get("semantics") or {}, v.get("knowledge") or {}, [e for e in v.get("field_evidence") or [] if isinstance(e, dict)]
        # the view carries the FIRST 12 ledger gaps, open or closed; the loop's record carries every open ledger gap (gap B-13)
        view_open = [g_.get("question") for g_ in kn.get("knowledge_gaps") or [] if isinstance(g_, dict) and g_.get("status", "open") == "open"]
        loop_open = [g_["question"] for g_ in loop_gaps if g_.get("hypothesis_id") == hid and g_.get("origin") == "ledger"]
        return {"hypothesis_id": hid, "statement": hy.get("statement"), "revision": hy.get("revision"), "status": hy.get("status"), "state_from": views_from,
                "mechanism": se.get("mechanism"), "population": se.get("population"), "activity": se.get("activity"), "task": se.get("task"), "context": se.get("context"),
                "suspected_friction": se.get("suspected_friction"), "assumptions": se.get("assumptions") or [], "falsifiers": se.get("falsifiers") or [],
                "open_gaps": _distinct_questions(view_open + loop_open),
                "field_evidence": len(fe), "field_supporting": sum(1 for e in fe if e.get("polarity") == "supporting"),
                "field_contradicting": sum(1 for e in fe if e.get("polarity") == "contradicting"), "knowledge_support": kn.get("knowledge_support_count") or 0,
                "contradictions": len(se.get("contradictions") or []), "trail_score": score_by.get(hid), "trail_refusal": refusal_by.get(hid),
                **(_field_counts(hid) or {"field_counts_from": "VIEW_SAMPLE"})}
    hyp_rows = [_hyp_row(hid, hyps.get(hid) or {}) for hid in dict.fromkeys(list(view_by) + list(hyps))]
    transduction = _transduction_block(out, views)
    reality = _product_reality_block(out)
    terminal = (result or {}).get("status")
    gap = (result or {}).get("gap")
    verdict = (None if result is None else f"GOVERNED GAP — {(gap or {}).get('code')}" if terminal == "terminal_gap"
               else f"GOVERNED RUN {str(terminal).upper()}" if terminal in ("cancelled", "failed")
               else "GOVERNED — TRAIL SCORED" if scores else "GOVERNED — TRAIL REFUSED TO SCORE" if refusals else "GOVERNED — COMPLETED WITHOUT A SCORE")
    po = out.get("product_opportunity") if isinstance(out.get("product_opportunity"), dict) else {}
    pc = po.get("product_concept") if isinstance(po.get("product_concept"), dict) else {}
    supply = [r for r in admitted if r.get("stage") == "supply" or r.get("source_class") == "supplier_listing"]
    leads = []
    for url in dict.fromkeys(r.get("url") for r in supply if r.get("url")):
        rows = [r for r in supply if r.get("url") == url]
        m = {(r.get("metric") or {}).get("name"): (r.get("metric") or {}).get("value") for r in rows if isinstance(r.get("metric"), dict)}
        # the supplier is who the LISTING names (`supplier:` in the observation context), never TrailSignal's independence group — that
        # is the platform, shown as the channel; a metric under another name than the receipt builder's two is shown raw (gap B-39)
        raw = [" ".join(str(v) for v in (x.get("name"), x.get("value"), x.get("unit")) if v not in (None, ""))
               for x in (r.get("metric") for r in rows) if isinstance(x, dict) and x.get("name") not in ("unit_price_low", "minimum_order_quantity")]
        leads.append({"governed": True, "concept_id": "governed_concept", "product_name": (rows[0].get("claim") or url)[:160], "url": url,
                      "channel": rows[0].get("independence_group") or rows[0].get("source_class"), "price_usd_low": m.get("unit_price_low"),
                      "moq_units": m.get("minimum_order_quantity"), "listing_metrics": raw, "mechanism": pc.get("mechanism_explanation") or "",
                      "trail_admission": sorted({str(r.get("role")) for r in rows}), "supplier_name": next((r["supplier"] for r in rows if _named_supplier(r.get("supplier"))), "")})
    packets = []
    for s in steps:
        for rc in (s.get("evidence") or {}).get("receipts") or []:
            if isinstance(rc, dict) and rc.get("surface") == "evidence_boundary" and not any(p["id"] == f"{rc.get('step_id')}#{rc.get('sequence')}" for p in packets):
                calls = [c for c in rc.get("calls") or [] if isinstance(c, dict)]
                grades: dict = {}
                for c in calls:
                    for g, n in (c.get("grades") or {}).items():
                        grades[g] = grades.get(g, 0) + n
                packets.append({"id": f"{rc.get('step_id')}#{rc.get('sequence')}", "need": " · ".join(rc.get("needs") or []) or rc.get("step_id"), "corpus": ",".join(rc.get("corpus_ids") or []),
                                "mode": rc.get("mode"), "n_evidence": rc.get("n_rows") or 0, "ca4_grades": grades, "utility_roles": {}, "origins": {},
                                "compiled_queries": sum(int(c.get("compiled_queries") or 0) for c in calls),
                                "corpus_explorer": {"requested": any(c.get("corpus_explorer_requested") for c in calls), "used": any(c.get("corpus_explorer_used") for c in calls),
                                                    "firing": next((c.get("firing") for c in calls if isinstance(c.get("firing"), dict) and c["firing"].get("cause")), None)}})
    # ecommerce.product_research (consolidation migration): the result carries the domain's OWN typed product set, supplier join and
    # lived world. They replace the single concept / metric-derived leads synthesized above for the older adapter's result.
    real_concepts = [c for c in out.get("product_concepts") or [] if isinstance(c, dict)]
    domain_supply = isinstance(out.get("sourcing_coverage"), list)
    if domain_supply:
        admitted_role = {r.get("admitted_evidence_id"): r.get("role") for r in admitted}
        leads = [{"governed": True, "concept_id": l.get("concept_id"), "concept": l.get("concept"), "product_name": l.get("product_name"), "url": l.get("url"),
                  "channel": l.get("channel"), "price_usd_low": l.get("price_usd_low"), "price_usd_high": l.get("price_usd_high"), "moq_units": l.get("moq_units"),
                  "mechanism": l.get("mechanism") or "", "mechanism_id": l.get("mechanism_id"), "supplier_name": l.get("supplier_name") or "supplier not named on the listing",
                  "trail_admission": [str(admitted_role.get(l.get("admitted_evidence_id")) or "supply")]} for l in out.get("leads") or [] if isinstance(l, dict)]
    limitations = [l for r in receipts for l in (r.get("payload") or {}).get("limitations") or []]
    # Unresolved = what the research left OPEN, the loop's own questions first (gap B-16); the steps' `unknowns` (mostly per-cluster
    # templates) are a separate, counted list — neither is cut here: the renderer says how much it shows
    unresolved = [f"{g['question']} — {g.get('hypothesis_id')} ({g.get('origin')})" for g in loop_gaps] \
        + [str(x) for x in po.get("remaining_uncertainty") or []] + [f"harness limitation: {l}" for l in limitations]
    unknowns = [str(u.get("about") if isinstance(u, dict) else u) for u in (result or {}).get("unknowns") or []]
    # a run that ended before COMPILE_RESULT: its result carries no step outputs while its lineage still lists the admitted ids — the
    # evidence is ABSENT from this result, never zero (gap B-14)
    admitted_ids = lineage.get("admitted_evidence_ids") if isinstance(lineage.get("admitted_evidence_ids"), list) else []
    evidence_absent = {"admitted_evidence_ids": len(admitted_ids), "terminal_status": terminal} if result is not None and not adms and admitted_ids else None
    # What the Field Actually Said (gap B-40): FIELD-stage records only (never a product-reality or supplier row), a TrailSignal
    # duplicate once, labelled by the community the observation names (else the source host) — the independence group is the
    # platform, not who spoke — and taken in turn with the records that CONTRADICT a hypothesis (TrailSignal's relation to it), which
    # are marked and never crowded out by admission order
    quotes = _alternate([{"quote": r.get("quote"), "source": r.get("url"), "community": r.get("community") or _host(r.get("url")) or r.get("source_class"),
                          "roles": [r.get("role")], "polarity": r.get("polarity"), "stage": r.get("stage"),
                          "contradicts": [h for h in r.get("hypothesis_ids") or [] if polarity_for(r, h) == "contradicting"]}
                         for r in admitted if (r.get("stage") or "field_evidence") == "field_evidence" and not r.get("duplicate_of")],
                        lambda q: bool(q["contradicts"]), 14)
    dead = ("killed", "contradicted", "merged", "weakened")
    concepts = real_concepts or ([{"id": "governed_concept", "name": pc.get("title"), "form_factor": pc.get("problem"), "target_moment": pc.get("context"), "buyer": pc.get("population"),
                                   "differentiator": pc.get("mechanism_explanation"), "mechanism_id": "governed", "variations": [], "evidence_refs": po.get("field_evidence_ids") or []}]
                                 if pc.get("title") else [])
    return {
        "run": {"run_id": journal.get("run_id"), "created_at": journal.get("created_at"), "status": terminal or "running", "verdict": verdict,
                "signal": _seed_of(journal.get("input") or {})[:600], "corpus": "polymath:" + ",".join(journal.get("corpus_ids") or []) if journal.get("corpus_ids") else None,
                "rounds": {"research": len(receipts)}},
        "coverage": {}, "independence": None, "l4_receipts": [],
        "bridges": [{"id": b.get("hypothesis_id"), "path": b.get("path"), "boundary": (b.get("evidence_boundary") or {}).get("first_inference_at"), "mechanism": b.get("target_mechanism"),
                     "status": b.get("status"), "invariant": None, "exploratory": False} for b in out.get("bridges") or [] if isinstance(b, dict)],
        "quotes": quotes,
        "mechanisms": [], "leads": leads,
        "product_concepts": concepts,
        "sourcing_coverage": [c for c in out.get("sourcing_coverage") or [] if isinstance(c, dict)], "utilization": {}, "provenance": [], "excluded_leads": [], "corpus_packets": packets, "corpus_answers": [],
        "held_rejected": [{"id": h["hypothesis_id"], "mechanism": h.get("mechanism") or h.get("statement"), "status": h.get("status")} for h in hyp_rows if h.get("status") in dead],
        "unresolved": list(dict.fromkeys(unresolved)), "intelligence": None, "market_discovery": None, "product_anchored": None,
        "capability_failures": [], "settings": None,
        "governed": {"adapter": f"{journal.get('adapter_id')} {journal.get('adapter_version')}", "agent_identity": journal.get("agent_identity"), "harness_ids": lineage.get("harness_ids") or [journal.get("harness_id")],
                     "terminal_status": terminal, "gap": gap, "hypotheses": hyp_rows, "trail_scores": scores, "score_refusals": refusals, "qualifications": quals,
                     "admitted": admitted, "rejected": rejected, "evidence_absent": evidence_absent,
                     "result_without_outputs": result is not None and not out and terminal in ("terminal_gap", "failed", "cancelled"),
                     "unresolved_research_gaps": loop_gaps, "unknowns": {"distinct": list(dict.fromkeys(unknowns)), "recorded": len(unknowns)},
                     "rejected_by_reason": {c: sum(1 for r in rejected if r.get("reason_code") == c) for c in sorted({str(r.get("reason_code")) for r in rejected})},
                     "receipt_omissions": [{"action_kind": (r.get("receipt_report") or {}).get("action_kind"), "omitted_by_reason": (r.get("receipt_report") or {}).get("omitted_by_reason") or {}}
                                           for r in receipts if (r.get("receipt_report") or {}).get("omitted_by_reason")],
                     "rejected_submissions": [{"step_id": s.get("step_id"), "kind": s.get("kind"), "errors": (s.get("response") or {}).get("error")} for s in subs if not s.get("accepted")],
                     "falsification_experiment": po.get("cheapest_falsification_experiment"), "contradictions": (result or {}).get("contradictions") or [],
                     "mechanisms": [m for m in out.get("mechanisms") or [] if isinstance(m, dict)],
                     "transduction": transduction, "product_reality": reality, "hypothesis_state_from": views_from or "STEP_CONTEXT_4_FIELDS",
                     "coordinates": {"priors": [p for p in out.get("priors") or [] if isinstance(p, dict)], "territories": [t for t in out.get("territories") or [] if isinstance(t, dict)]},
                     "materials_recorded": sum(1 for s in steps if s.get("materials")),
                     "lived_situations": [x for x in out.get("lived_situations") or [] if isinstance(x, dict)],
                     "lived_clusters": [x for x in out.get("lived_clusters") or [] if isinstance(x, dict)],
                     "population_leads": [x for key in ("population_leads", "community_leads") for x in out.get(key) or [] if isinstance(x, dict)],
                     "lenses": [x for x in out.get("lenses") or [] if isinstance(x, dict)], "corpus_questions": [x for x in out.get("corpus_questions") or [] if isinstance(x, dict)],
                     "registry_snapshot": next((x.get("registry_snapshot") for x in adms if isinstance(x.get("registry_snapshot"), dict)), None),
                     "lineage": {k: (len(v) if isinstance(v, list) else v) for k, v in lineage.items()},
                     "steps": {"issued": len(steps), "agent_reason": sum(1 for s in steps if s["step"].get("step_type") == "AGENT_REASON"),
                               "harness_actions": sum(1 for s in steps if s["step"].get("step_type") == "HARNESS_ACTION"),
                               "with_readable_evidence": sum(1 for s in steps if (s.get("evidence") or {}).get("rows"))}},
        "audit": {"observations": len(obs_index), "unique_sources": len(src_count - {None}), "queries_compiled": queries, "research_rounds": len(receipts),
                  "events": len(ev), "hypotheses_total": len(hyp_rows)},
        "built_at": journal.get("built_at") or models.now(),
        # PRODUCT-DECISION-REPORT-V1 §4.5: the unit economics of the admitted supplier leads against the admitted product-reality prices
        "decision": _governed_decision(journal, leads, concepts, reality),
    }


# ------------------------------------------------- governed: the decision --
#: a price as a product-reality listing showed it, read only when it is ONE US-dollar amount ("$19.99", "US$ 1,299.00", "19.99 USD");
#: a range, another currency or any other text stays unread (the comparable then has no price: UNKNOWN, never a guess)
_ONE_USD = re.compile(r"(?:US\s?\$|\$|USD\s?)\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?|(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?\s?USD", re.IGNORECASE)


def _one_usd(text) -> float | None:
    m = _ONE_USD.fullmatch(str(text or "").strip())
    if not m:
        return None
    whole, cents = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    return float(whole.replace(",", "") + (cents or ""))


def _listing_id(url) -> str | None:
    """The product number a CJ (`…-p-<digits>.html`) or alibaba.com (`…_<digits>.html`) listing URL carries, else None."""
    m = re.search(r"(?:-p-|_)(\d{6,})\.html?(?:$|[?#])", str(url or ""))
    return m.group(1) if m else None


def _listed_price(lead: dict) -> str | None:
    """A supplier lead's parsed price written back the way a listing shows it ("US$1.2-1.8"), beside the numbers themselves."""
    lo, hi = lead.get("price_usd_low"), lead.get("price_usd_high")
    return None if lo is None else f"US${lo}" + (f"-{hi}" if hi not in (None, lo) else "")


def _governed_bundle(journal: dict, leads: list[dict], concepts: list[dict], reality: dict | None) -> tuple[dict, list[dict]] | None:
    """The §4.4 bundle of a governed run, from what TrailSignal ADMITTED: one candidate per product concept that has an admitted supplier
    lead; a cjdropshipping lead as a CJ product (host.cj), any other as a supplier listing (parsed.alibaba — the sourcing channels are
    alibaba and cjdropshipping); the concept's product-reality prices on amazon.com / ebay.com as Amazon / eBay comparables. What the run
    did not research (freight, Reddit, an eBay API search) is absent, so its numbers come out UNKNOWN. Also returns the product-reality
    prices from other retailers, which the Amazon / eBay market model does not take (listed beside it)."""
    by_concept: dict = {}
    for lead in leads:
        if isinstance(lead, dict) and lead.get("url"):
            by_concept.setdefault(str(lead.get("concept_id") or "governed_concept"), []).append(lead)
    if not by_concept:
        return None
    names = {str(c.get("id")): c.get("name") for c in concepts if isinstance(c, dict)}
    existing = [p for p in (reality or {}).get("existing_products") or [] if isinstance(p, dict)]
    candidates, cj, ebay, parsed, others = [], {}, {}, {}, []
    for cid, rows in by_concept.items():
        title = str(names.get(cid) or rows[0].get("product_name") or cid)
        candidates.append({"candidate_id": cid, "title": title, "search_terms": [title]})
        mine = [p for p in existing if cid in (p.get("applies_to_concepts") or [p.get("concept_id")])]
        cj_rows = [r for r in rows if str(r.get("channel") or "").lower().startswith("cj") or _host(r.get("url")).endswith("cjdropshipping.com")]
        cj[cid] = {"status": "TRAILSIGNAL_ADMITTED" if cj_rows else "NOT_SEARCHED", "reason_code": None if cj_rows else "GOVERNED_RUN_NO_CJ_LEAD",
                   "relevance": {"kept": [], "dropped": []},
                   "products": [{"product_id": _listing_id(r.get("url")), "title": r.get("product_name"), "url": r.get("url"), "image": None, "sell_price_usd": r.get("price_usd_low"),
                                 "suggested_retail_usd": None, "weight_g": None, "variants": [], "freight": {"CN": [], "US": []}, "us_stock_confirmed": False,
                                 "admission": ADMITTED} for r in cj_rows]}
        alibaba = [{"kind": "listing", "ref": _listing_id(r.get("url")), "url": r.get("url"), "published_at": None, "precision": "none",
                    "listing": {"title": r.get("product_name"), "price_as_listed": _listed_price(r), "minimum_order_as_listed": None if r.get("moq_units") is None else f"{r['moq_units']} pieces",
                                "supplier": r.get("supplier_name"), "product_id": None},
                    "price_usd_low": r.get("price_usd_low"), "price_usd_high": r.get("price_usd_high"), "moq_units": r.get("moq_units"), "admission": ADMITTED}
                   for r in rows if r not in cj_rows]
        amazon, ebay_rows = [], []
        for p in mine:
            row = {"kind": "listing", "title": p.get("product_name") or p.get("claim"), "url": p.get("url"), "price_usd": _one_usd(p.get("price_raw")),
                   "price_as_listed": p.get("price_raw"), "admission": ADMITTED}
            host = _host(p.get("url"))
            if re.search(r"(?:^|\.)amazon\.com$", host):
                amazon.append(row)
            elif re.search(r"(?:^|\.)ebay\.com$", host):
                ebay_rows.append({**row, "shipping_usd": None, "us_listing": True})
            elif p.get("price_raw") or p.get("url"):
                others.append({"candidate_id": cid, "title": row["title"], "url": p.get("url"), "price_as_listed": p.get("price_raw"), "admission": ADMITTED})
        ebay[cid] = {"status": "TRAILSIGNAL_ADMITTED" if ebay_rows else "NOT_SEARCHED", "reason_code": None if ebay_rows else "GOVERNED_RUN_NO_EBAY_PRICE",
                     "listings": ebay_rows}
        parsed[cid] = {"reddit": [], "amazon": amazon, "ebay": [], "alibaba": alibaba}
    built = str(journal.get("built_at") or "")[:10] or None
    return ({"candidates": candidates, "host": {"cj": cj, "ebay": ebay, "receipts": []}, "parsed": parsed,
             "settings": {"ship_to": "US", **({"as_of": built} if built else {})}, "report_id": journal.get("run_id")}, others)


def _governed_decision(journal: dict, leads: list[dict], concepts: list[dict], reality: dict | None) -> dict | None:
    """The decision section of a governed dossier — None when the run admitted no supplier lead. `unit_economics.compute` runs here, in
    the engine process that draws the dossier; when it cannot (absent, or it fails), the section says so with a typed code instead of
    numbers, and the rest of the dossier is drawn as before."""
    built = _governed_bundle(journal, leads, concepts, reality)
    if built is None:
        return None
    bundle, others = built
    try:
        import unit_economics
        decision = unit_economics.compute(bundle, graphmod.load_policies())
        if not isinstance(decision, dict):
            raise TypeError(f"compute returned {type(decision).__name__}, not the decision model")
    except Exception as exc:  # noqa: BLE001 — a dossier never loses its other sections to the decision block
        code = "UNIT_ECONOMICS_UNAVAILABLE" if isinstance(exc, ImportError) else "UNIT_ECONOMICS_FAILED"
        decision = {"error": {"code": code, "message": f"{type(exc).__name__}: {exc}"[:300]}, "products": []}
    block = _decision_block(decision, admission=ADMITTED, ship_to="US")
    block["other_prices"] = others
    return block


def _transduction_block(out: dict, views: list) -> dict | None:
    """Where each hypothesis CAME FROM (restoration reference §13.2): what was abstracted from the corpus, which population lead /
    latent structure it declares as its origin, and the bridge it earned. Four authorities are kept apart: corpus evidence (cited
    ids), inferred semantic structure (the agent's abstraction), live-world evidence, TrailSignal's determination."""
    prim = out.get("primitives") if isinstance(out.get("primitives"), dict) else {}
    structures = [x for x in out.get("latent_structures") or [] if isinstance(x, dict)]
    bridges = {b.get("hypothesis_id"): b for b in out.get("bridges") or [] if isinstance(b, dict)}
    if not (prim or structures or bridges or views):
        return None
    per_h = []
    for v in views:
        hid = v["hypothesis"]["hypothesis_id"]
        b = v.get("bridge") or bridges.get(hid) or {}
        origin = v.get("origin") or {}
        per_h.append({"hypothesis_id": hid, "statement": v["hypothesis"].get("statement"),
                      "origin_leads": [{"id": l.get("id"), "name": l.get("name"), "lane": l.get("source_lane"), "seed_population": l.get("seed_population")} for l in origin.get("leads") or []],
                      "origin_declared": bool(origin.get("lead_ids") or origin.get("latent_structure_ids")),
                      "latent_structures": [{"id": x.get("id"), "kind": x.get("kind"), "text": x.get("text"), "basis": x.get("basis"),
                                             "applicability_outside_source": x.get("applicability_outside_source")} for x in (v.get("transduction") or {}).get("latent_structures") or []],
                      "primitives_sharing_evidence": (v.get("transduction") or {}).get("primitives_sharing_evidence") or {},
                      "bridge": ({"source": b.get("source"), "path": b.get("path") or [], "first_inference_at": (b.get("evidence_boundary") or {}).get("first_inference_at"),
                                  "target_mechanism": b.get("target_mechanism"), "gaps": b.get("gaps") or [], "alternatives": b.get("alternatives") or [],
                                  "falsifiers": b.get("falsifiers") or [], "status": b.get("status"), "grounding": b.get("grounding")} if b else None)})
    return {"transferable_invariants": [str(x) for x in prim.get("transferable_invariants") or []], "shared_predicates": [str(x) for x in prim.get("shared_predicates") or []],
            "families": {k: [str(x) for x in prim.get(k) or []][:8] for k in ("drivers", "behaviors", "adaptations", "constraints", "workarounds", "frictions", "latent_values", "physical_jobs") if prim.get(k)},
            "latent_structures": structures, "hypotheses": per_h}


def _product_reality_block(out: dict) -> dict | None:
    """Generated concepts and EXISTING products, kept apart and joined by concept id (restoration reference §13.3)."""
    reality = [c for c in out.get("concept_reality") or [] if isinstance(c, dict)]
    products = [p for p in out.get("existing_products") or [] if isinstance(p, dict)]
    if not reality and not products:
        return None
    return {"concepts": reality, "existing_products": products, "jobs": len(out.get("reality_plan") or [])}


def _intel_block(state: dict) -> dict | None:
    """Commercial-intelligence projection (docs/11) — present only when the
    intelligence layer ran; reports never invent it."""
    import intelligence
    d = state["data"]
    if not any(d.get(k) for k in intelligence.INTEL_KEYS):
        return None
    angles = [dict(a, _key=k) for k in intelligence.ANGLE_KEYS for a in d.get(k) or []]
    return {
        "market_analysis": d.get("market_analysis") or [],
        "angles": [{"id": a.get("id"), "angle_type": a.get("angle_type"),
                    "hook_type": a.get("hook_type"), "thesis": a.get("thesis"),
                    "evidence_state": a.get("evidence_state"),
                    "disposition": a.get("disposition"),
                    "featured_product": a.get("featured_product")}
                   for a in angles],
        "angle_portfolio": state.get("angle_portfolio"),
        "briefs": d.get("creative_briefs") or [],
        "style": d.get("style_intelligence") or [],
        "storefront": d.get("storefront_strategies") or [],
        "chains": d.get("analysis_chains") or [],
    }


def _market_block(state: dict) -> dict | None:
    d = state["data"]
    if not d.get("market_scopes") and not d.get("promoted_scopes"):
        return None
    return {
        "promoted": d.get("promoted_scopes") or [],
        "scopes": [{"id": s.get("id"), "market": s.get("market"),
                    "niche": s.get("niche"), "subniche": s.get("subniche"),
                    "status": s.get("status")} for s in d.get("market_scopes") or []],
        "divergences": d.get("signal_divergences") or [],
        "whitespace": [{"id": w.get("id"), "type": w.get("type"),
                        "scope": w.get("market_scope_id"), "state": w.get("state"),
                        "mismatch": w.get("observed_mismatch")}
                       for w in d.get("whitespace_hypotheses") or []],
        "frontier_stability": d.get("market_frontier_stability"),
        "provenance": d.get("signal_provenance"),
    }


def _product_block(state: dict) -> dict | None:
    d = state["data"]
    if not d.get("product_identity") and not d.get("market_bridges"):
        return None
    return {
        "identity": d.get("product_identity") or {},
        "claims": d.get("product_claims") or [],
        "meanings": [{"id": m.get("id"), "type": m.get("type"), "job": m.get("job"),
                      "state": m.get("state")} for m in d.get("product_meanings") or []],
        "bridges": [{"id": b.get("id"), "market_scope": b.get("market_scope"),
                     "meaning_id": b.get("meaning_id"), "state": b.get("state"),
                     "supporting": len(b.get("supporting_evidence") or [])}
                    for b in d.get("market_bridges") or []],
        "reframes": d.get("market_reframes") or [],
        "stability": d.get("reverse_fit_stability"),
    }


# --------------------------------------------------------------- decision --
# PRODUCT-DECISION-REPORT-V1 §4.5 (B4a). The decision model is `unit_economics.compute(bundle, policy)`'s answer (§4.4): every number
# in it is the engine's, with its receipt. This layer keeps, orders, links and formats — it computes no number. The one choice it makes
# is which channel to name "best" (BEST_CHANNEL_RULE, printed on the page) when the model names none.
DECISION_LAYOUT = "DECISION"
LAYOUTS = ("FULL_RESEARCH", "SOURCING", "EXECUTIVE", "COMMERCIAL", DECISION_LAYOUT)
CHANNELS = (("tiktok_us", "TikTok Shop · US account", "TikTok US"), ("tiktok_cross_border", "TikTok Shop · cross-border", "TikTok CB"),
            ("shopify", "Shopify", "Shopify"), ("ebay", "eBay", "eBay"), ("amazon_fbm", "Amazon · FBM", "Amazon"))
CHANNEL_LABEL = {c: label for c, label, _ in CHANNELS}
CHANNEL_SHORT = {c: short for c, _, short in CHANNELS}
DELIVERY_VERDICTS = ("PASS", "WARN", "FAIL", "UNKNOWN")
#: who stands behind a decision row: a governed run's rows were admitted by TrailSignal; a quick report's were read, never admitted
ADMITTED, UNADMITTED = "TrailSignal-admitted", "unadmitted"
AGENT_VERDICT_LABEL = "the agent's verdict — not computed by Polymath"
AGENT_VERDICT_MAX_CHARS = 1200                      # == POST /product/report/{id}/compile's bound (plan §4.6)
REDDIT_COMMENTS_SHOWN = 5                           # owner, 2026-11-02: the summary sentence, then at most five comments — never the full list
REDDIT_EXCLUDED_SHOWN = 5                           # contract C4: the threads the parser judged off-topic — their count, then at most five titles with dates
#: an inventory offer's precondition (contract C5): unit_economics carries these four numbers on the offer and on every inventory line
STOCK_FIELDS = ("time_to_stock_days", "moq_capital_usd", "moq_inbound_usd", "cash_to_first_stock_usd")
COMMENT_MAX_CHARS, COMPS_SHOWN, LINKS_SHOWN, RECEIPTS_SHOWN = 700, 8, 5, 400
LINK_SOURCES = (("cj", "CJ"), ("alibaba", "Alibaba"), ("amazon", "Amazon"), ("ebay", "eBay"), ("reddit", "Reddit"))
MARKETS = (("amazon", "Amazon"), ("ebay", "eBay"))
#: contract C11 (plan §3.6, users without a terminal): the sources a report reads through the user's own Agent Reach, in the order the
#: counts line names them (eBay only when the host has no eBay API: the fetch plan holds no eBay packet otherwise), and what a
#: source's sections say when nothing from it was uploaded, or when every upload of it was refused
AGENT_REACH_SOURCES = (("reddit", "Reddit"), ("amazon", "Amazon"), ("alibaba", "Alibaba"), ("ebay", "eBay"))
NEEDS_LOCAL_AGENT = ("Needs a local agent: nothing from {source} was uploaded for this report. Run the report's fetch script on a computer "
                     "with Agent Reach (product_report_status gives it), then compile again.")
NOT_READ = "{source} could not be read ({counts}): no data admitted."
NOT_READ_ORDER = ("BLOCKED", "HUMAN_CHECK", "EMPTY")
MONEY_FIELDS = ("sell_price_usd", "unit_cost_usd", "inbound_usd", "shipping_usd", "fees_usd", "returns_usd", "margin_before_ads_usd",
                "break_even_ad_cost_usd")
#: the two supply models (unit_economics): DROPSHIP — the supplier ships each order; INVENTORY — buy the MOQ, bring it to your own US
#: stock once (inbound freight per unit, time to first stock), then ship each order from that stock (the last mile)
OFFER_MODELS = {"dropship": "Dropship", "inventory": "Inventory"}
REQUIRES_US_STOCK = "REQUIRES_US_STOCK"
#: how an inventory offer's inbound freight per unit was set (unit_economics `_alibaba_shipping`)
INBOUND_RULES = {"QUOTE": "the listing's own shipping quote ÷ its quantity", "PER_KG": "per-kg rate × unit weight",
                 "MIN_KG": "the stated minimum chargeable weight × the per-kg rate, ÷ MOQ", "MIN_CHARGE": "the stated minimum charge, ÷ MOQ",
                 "UNKNOWN": "no quote, or no per-kg rate and unit weight"}
BEST_CHANNEL_RULE = ("best channel = the highest margin before ads among the channels whose delivery verdict is PASS or WARN; a channel that "
                     "FAILS delivery, or whose delivery or margin is UNKNOWN, is never the best")
#: an http(s) URL with a host and no character that could leave an attribute — the ONLY kind of URL that becomes an anchor; any other
#: scheme (javascript:, data:, …) stays text. The server's sanitizer applies the same rule again (polymath_shared.adapter.dossier.safe_href;
#: the engine never imports `shared`, so the rule is written twice and a contract test holds the two equal).
_HTTP_URL = re.compile(r"https?://[^\s\"'<>\\^`{|}\x00-\x1f\x7f]+", re.IGNORECASE)
MAX_URL_CHARS = 2048


def safe_url(value) -> str | None:
    """`value` when it may be an anchor's href (an http(s) URL with a host), else None — it is then shown as text."""
    if not isinstance(value, str) or len(value) > MAX_URL_CHARS or not _HTTP_URL.fullmatch(value):
        return None
    try:
        host = urlparse(value).hostname
    except ValueError:
        return None
    return value if host else None


def _unknown(v) -> bool:
    """None, NaN, an empty string or the word UNKNOWN: a value the engine could not compute (shown as UNKNOWN, never blank)."""
    return v is None or (isinstance(v, float) and not math.isfinite(v)) or (isinstance(v, str) and v.strip().upper() in ("", "UNKNOWN"))


def _number(v):
    """A finite int / float, else None. A bool is not a number."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _dicts(v) -> list[dict]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _verdict(v) -> str:
    """The delivery verdict as the engine wrote it (upper-cased); a missing one is UNKNOWN."""
    return v.strip().upper() if isinstance(v, str) and v.strip() else "UNKNOWN"


def _line_row(cid: str, c: dict, offers: dict, receipts: dict, path: str) -> dict:
    """One channel line as the model wrote it (unit_economics `_line`): the offer it prices and its supply model, the money fields
    (sell − unit − inbound − shipping or last mile − fees − returns = margin before ads), where its shipping figure comes from, the
    delivery verdict, and — for an inventory line — the US stock it requires (the offer's time to first stock and the cash before it:
    MOQ capital + the inbound freight for the MOQ order, contract C5)."""
    d = _dict(c.get("delivery"))
    offer = _dict(offers.get(c.get("offer_id")))
    model = c.get("model") or offer.get("model")
    shipping = _dict(receipts.get(f"{path}.shipping_usd"))          # the line's own receipt names its last-mile source and rule
    last_mile = _dict(c.get("last_mile"))
    source = (c.get("last_mile_source") or last_mile.get("source") or _dict(shipping.get("inputs")).get("source")
              or (next((x.get("source") for x in _dicts(offer.get("shipping")) if x.get("source")), None) if model == "inventory" else None))
    cautions = [str(x) for x in d.get("cautions") or []] if isinstance(d.get("cautions"), list) else []
    return {"channel_id": cid, "label": CHANNEL_LABEL.get(cid, cid), "offer_id": c.get("offer_id"), "source": c.get("source"), "model": model,
            **{k: c.get(k) for k in MONEY_FIELDS + ("landed_cost_usd",)}, "margin_pct": c.get("margin_pct"),
            "shipping_source": source, "shipping_rule": c.get("last_mile_rule") or last_mile.get("rule") or shipping.get("rule"),
            "requires_us_stock": ({k: offer.get(k) for k in STOCK_FIELDS} if REQUIRES_US_STOCK in cautions else None),
            "delivery": {**d, "verdict": _verdict(d.get("verdict"))}}


def _channel_rows(channels, offers: list[dict] | None = None, receipts: list[dict] | None = None) -> list[dict]:
    """One row per channel — its best offer's line, the other offers' lines under `alternatives` — the plan's channels first in their
    fixed order, then any other the model carries (in its order)."""
    channels = _dict(channels)
    by_offer = {o.get("offer_id"): o for o in offers or []}
    by_id = {r.get("id"): r for r in receipts or []}
    order = [c for c, _, _ in CHANNELS if c in channels] + [c for c in channels if c not in CHANNEL_LABEL]
    return [{**_line_row(cid, _dict(channels[cid]), by_offer, by_id, f"channels.{cid}"),
             "alternatives": [_line_row(cid, a, by_offer, by_id, f"channels.{cid}.alternatives[{k}]")
                              for k, a in enumerate(_dicts(_dict(channels[cid]).get("alternatives")))]}
            for cid in order]


def _best_channel(product: dict, rows: list[dict]) -> dict | None:
    """The model's own `best_channel` when it names one; else BEST_CHANNEL_RULE over the rows (the first in channel order on a tie)."""
    named = product.get("best_channel")
    named = named.get("channel_id") or named.get("channel") if isinstance(named, dict) else named
    if isinstance(named, str) and named:
        row = next((r for r in rows if r["channel_id"] == named), None)
        return {"channel_id": named, "label": CHANNEL_LABEL.get(named, named), "from": "MODEL",
                **({k: row.get(k) for k in ("margin_before_ads_usd", "break_even_ad_cost_usd", "margin_pct", "model", "offer_id", "requires_us_stock")}
                   if row else {})}
    ok = [r for r in rows if r["delivery"]["verdict"] in ("PASS", "WARN") and _number(r.get("margin_before_ads_usd")) is not None]
    if not ok:
        return None
    best = max(ok, key=lambda r: r["margin_before_ads_usd"])
    return {"channel_id": best["channel_id"], "label": best["label"], "from": "RULE",
            **{k: best.get(k) for k in ("margin_before_ads_usd", "break_even_ad_cost_usd", "margin_pct", "model", "offer_id", "requires_us_stock")}}


def _market_row(m, admission: str) -> dict:
    m = _dict(m)
    comps = [dict(c, admission=c.get("admission") or admission) for c in _dicts(m.get("comps"))]
    return {"n": m.get("n"), "median": m.get("median"), "min": m.get("min"), "max": m.get("max"), "comps": comps[:COMPS_SHOWN], "comps_total": len(comps),
            **{k: m.get(k) for k in ("status", "reason_code", "reason") if m.get(k) is not None}}


def _link_entry(url, text=None) -> dict | None:
    if _unknown(url) or not isinstance(url, str):
        return None
    return {"url": url, "href": safe_url(url), "text": str(text) if text not in (None, "") else None}


def _product_links(product: dict, offers: list[dict], markets: dict, comments: list[dict]) -> dict:
    """Links per source (CJ, Alibaba, Amazon, eBay, Reddit): the model's own `links` when it carries them, else the offers' and
    comparables' URLs and the threads of the Reddit comments — each URL once, at most LINKS_SHOWN per source."""
    given = _dict(product.get("links"))
    out = {}
    for src, _ in LINK_SOURCES:
        if src in given:
            raw = given[src] if isinstance(given[src], list) else [given[src]]
            entries = [_link_entry(x.get("url"), x.get("title") or x.get("text")) if isinstance(x, dict) else _link_entry(x) for x in raw]
        elif src in ("cj", "alibaba"):
            entries = [_link_entry(o.get("url"), o.get("title")) for o in offers if str(o.get("source") or "").lower() == src]
        elif src in ("amazon", "ebay"):
            entries = [_link_entry(c.get("url"), c.get("title")) for c in markets[src]["comps"]]
        else:
            entries = [_link_entry(c.get("url") or c.get("thread_url")) for c in comments]
        seen, kept = set(), []
        for e in entries:
            key = _link_key(e["url"]) if e else None
            if e and key not in seen:
                seen.add(key)
                kept.append(e)
        out[src] = {"shown": kept[:LINKS_SHOWN], "total": len(kept)}
    return out


def _link_key(url: str) -> str:
    """One page once: the scheme, a `www.` and a trailing slash do not make another link."""
    m = re.match(r"(?i)^https?://(?:www\.)?([^/?#]+)([^#]*)", url)
    return f"{m.group(1).lower()}{m.group(2).rstrip('/')}" if m else url


def _stock_words(req) -> str:
    """unit_economics' own words for an inventory offer's precondition (contract C5): "requires holding US stock: first stock in N days,
    cash $7,737.00 before first stock (goods $2,200.00 + inbound $5,537.00)" — from an offer or a line's `requires_us_stock`."""
    req = _dict(req)
    n = _number(req.get("time_to_stock_days"))

    def money(v) -> str:
        x = _number(v)
        return f"${x:,.2f}" if x is not None else "UNKNOWN"
    return ("requires holding US stock: " + (f"first stock in {n:g} days" if n is not None else "first stock time UNKNOWN")
            + f", cash {money(req.get('cash_to_first_stock_usd'))} before first stock (goods {money(req.get('moq_capital_usd'))} + "
            f"inbound {money(req.get('moq_inbound_usd'))})")


def _us_stock_notes(offers: list[dict]) -> list[str]:
    """The US-stock caution (plan §1: a US→US freight quote does NOT prove US stock), per offer that quotes a US origin."""
    notes = []
    for o in offers:
        who = f"{str(o.get('source') or 'offer').upper()} offer {o.get('offer_id') or ''}".strip()
        if o.get("model") == "inventory":
            notes.append(f"{who}: inventory — {_stock_words(o)}; each order then ships from your "
                         "own US stock (the last mile), so the supplier's US stock does not matter here.")
        elif any(str(s.get("origin") or "").upper() == "US" for s in _dicts(o.get("shipping"))):
            if o.get("us_stock_confirmed") is True:
                notes.append(f"{who}: US stock confirmed by the supplier — the US-warehouse delivery times apply.")
            else:
                notes.append(f"{who}: a US→US freight quote does NOT prove US stock — the supplier did not confirm stock in a US warehouse. "
                             "Until it does, plan on the China-origin delivery times.")
        notes += [f"{who}: {c}" for c in (o.get("cautions") if isinstance(o.get("cautions"), list) else []) if isinstance(c, str) and c.strip()]
    return notes


def _base_line(lines: list[dict], cid: str, what_if: dict) -> dict:
    """The parts a what-if keeps from the channel's line for the same offer (unit_economics `_sensitivity`: same offer, same price, same
    landed cost and returns — only the fee changes), so its row adds up on the page as well."""
    row = next((r for r in lines if r["channel_id"] == cid), None)
    for line in ([row] + list(row.get("alternatives") or [])) if row else []:
        if line.get("offer_id") == what_if.get("offer_id"):
            return {"base": {k: line.get(k) for k in ("model", "sell_price_usd", "unit_cost_usd", "inbound_usd", "shipping_usd", "returns_usd")}}
    return {"base": None}


def _sensitivity_blocks(sens, lines: list[dict] | None = None) -> list[dict]:
    """Each what-if the model carries (the TikTok 8 % fee first) — unit_economics writes {rate_pct, status, channels: {channel: line}} —
    as its rows per channel, its status and its rate (in percent)."""
    lines = lines or []
    blocks = []
    sens = _dict(sens)
    for key in sorted(sens, key=lambda k: (k != "tiktok_8pct", k)):
        s = _dict(sens[key])
        per = _dict(s.get("channels")) if isinstance(s.get("channels"), dict) else {k: v for k, v in s.items() if isinstance(v, dict)}
        order = [c for c, _, _ in CHANNELS if c in per] + [c for c in per if c not in CHANNEL_LABEL]
        blocks.append({"key": key, "rows": [{"channel_id": ch, "label": CHANNEL_LABEL.get(ch, ch), **_dict(per[ch]), **_base_line(lines, ch, _dict(per[ch]))}
                                            for ch in order],
                       "status": s.get("status") or ("UNCONFIRMED" if key == "tiktok_8pct" else None), "rate_pct": s.get("rate_pct"),
                       "basis": s.get("basis") or s.get("note")})
    return blocks


def _receipt_formula(receipts: list[dict], rid: str) -> str | None:
    """The formula of the receipt whose id is `rid` (unit_economics: a receipt's id is the number's path in the product)."""
    return next((str(r.get("formula")) for r in receipts if r.get("id") == rid and r.get("formula")), None)


def _decision_product(p: dict, verdicts: dict, admission: str) -> dict:
    cid = str(p.get("candidate_id") or "")
    offers = [dict(o, admission=o.get("admission") or admission) for o in _dicts(p.get("offers"))]
    market, demand = _dict(p.get("market")), _dict(p.get("demand"))
    reddit = _dict(demand.get("reddit"))
    comments = _dicts(reddit.get("comments")) if "comments" in reddit else _dicts(reddit.get("signals"))
    markets = {mk: _market_row(market.get(mk), admission) for mk, _ in MARKETS}
    receipts = _dicts(p.get("receipts"))
    channels = _channel_rows(p.get("channels"), offers, receipts)
    verdict = verdicts.get(cid) if cid in verdicts else p.get("agent_verdict")
    counted = _number(reddit.get("comments_total"))           # unit_economics counts every comment it read and hands over the top five
    status = {k: _dict(v) for k, v in _dict(p.get("sources_status")).items()}
    return {
        "candidate_id": cid, "title": str(p.get("title") or cid or "untitled product"), "admission": admission,
        # what the HOST's CJ / eBay calls answered — a governed run makes none (its rows are what TrailSignal admitted), so it shows none
        "sources_status": {} if admission == ADMITTED else {k: {"status": v.get("status"), "reason_code": v.get("reason_code")} for k, v in status.items()},
        "offers": offers, "us_stock_notes": _us_stock_notes(offers), "offers_excluded": _dicts(p.get("offers_excluded")),
        "market": {**markets, "reference_price_usd": market.get("reference_price_usd"), "basis": market.get("basis"),
                   "basis_text": _receipt_formula(receipts, "market.reference_price_usd"), "basis_note": market.get("basis_note"),
                   "excluded": _dicts(market.get("excluded"))},
        "demand": {"reddit": {"summary": reddit.get("summary"), "threads": reddit.get("threads"), "newest": reddit.get("newest"),
                              "subreddits": [str(s) for s in reddit.get("subreddits") or [] if s] if isinstance(reddit.get("subreddits"), list) else [],
                              # never the full list: the model keeps at most REDDIT_COMMENTS_SHOWN and the count
                              "comments": [{**c, "text": str(c.get("text") or "")[:COMMENT_MAX_CHARS]} for c in comments[:REDDIT_COMMENTS_SHOWN]],
                              "comments_total": max(int(counted) if counted is not None else 0, len(comments)),
                              # C4: the threads the parser judged not about the product — their count and at most five, newest first
                              "threads_excluded": _dicts(reddit.get("threads_excluded"))[:REDDIT_EXCLUDED_SHOWN],
                              "threads_excluded_total": len(_dicts(reddit.get("threads_excluded")))},
                   "amazon": _dict(demand.get("amazon"))},
        "channels": channels, "best": _best_channel(p, channels), "sensitivity": _sensitivity_blocks(p.get("sensitivity"), channels),
        "receipts": receipts[:RECEIPTS_SHOWN], "receipts_total": len(receipts),
        "links": _product_links(p, offers, markets, comments),
        "agent_verdict": str(verdict).strip()[:AGENT_VERDICT_MAX_CHARS] if isinstance(verdict, str) and verdict.strip() else None,
    }


#: unit_economics `_assumptions`: the model's own rules, in the order the appendix lists them
ASSUMPTION_RULES = (("sell_price", "Sell price"), ("fee_base", "Fee base"), ("returns", "Returns allowance"), ("ad_cost", "Ad cost"),
                    ("chargebacks", "Chargebacks"), ("handling", "Handling time"), ("delivery_days", "Delivery days"), ("cj", "CJ offers"),
                    ("alibaba", "Alibaba offers"),
                    ("best_offer", "Best offer per channel"), ("shopify_plan", "Shopify plan"))
_ASSUMPTION_KNOWN = {k for k, _ in ASSUMPTION_RULES} | {"as_of", "rules_read_on", "ship_to", "channels"}


def _source(s) -> dict | None:
    """One source of a rule: its title, URL, the date it was read and (when known) published, and what it backs."""
    if isinstance(s, str) and s.strip():
        return {"title": None if safe_url(s) else s, "url": s if safe_url(s) else None}
    if not isinstance(s, dict):
        return None
    return {"id": s.get("id"), "title": s.get("title"), "url": s.get("url"), "read": s.get("read") or s.get("date") or s.get("read_at"),
            "published": s.get("published"), "backs": s.get("backs")}


def _assumptions_block(a: dict) -> dict:
    """The appendix: the model's rules (each with its source), every channel's fee and delivery rule with the pages they were read from,
    and every UNCONFIRMED item (a sensitivity the channel itself never published). Keys this layer does not know are flattened, not lost."""
    rules = []
    for key, label in ASSUMPTION_RULES:
        if key not in a:
            continue
        v, sources = a[key], []
        if isinstance(v, dict) and key == "returns":
            rate = _number(v.get("rate"))
            text = " — ".join(x for x in (f"{rate * 100:g} % of sales" if rate is not None else None, v.get("text")) if x)
            sources = [s for s in [_source(v.get("source"))] if s]
        elif isinstance(v, dict) and key == "shopify_plan":
            text = (f"{_plain(v.get('plan'))} plan {_plain(v.get('monthly_usd'))} USD a month ÷ {_plain(v.get('monthly_orders'))} orders a month = "
                    f"{_plain(v.get('per_order_usd'))} USD an order")
        else:
            text = v if isinstance(v, str) else _plain(v)
        rules.append({"item": label, "value": text, "sources": sources})
    channels, unconfirmed, seen = [], [], set()
    chs = _dict(a.get("channels"))
    for cid in [c for c, _, _ in CHANNELS if c in chs] + [c for c in chs if c not in CHANNEL_LABEL]:
        ch = _dict(chs[cid])
        fee, delivery, sens = ch.get("fee"), ch.get("delivery"), _dict(ch.get("sensitivity"))
        channels.append({"channel_id": cid, "label": ch.get("label") or CHANNEL_LABEL.get(cid, cid),
                         "fee": _dict(fee).get("text") if isinstance(fee, dict) else fee,
                         "delivery": _dict(delivery).get("text") if isinstance(delivery, dict) else delivery,
                         "sources": [s for s in (_source(x) for x in (ch.get("sources") if isinstance(ch.get("sources"), list) else [])) if s],
                         "sensitivity": ({"id": sens.get("id"), "rate_pct": sens.get("rate_pct"), "status": sens.get("status")} if sens else None)})
        sid = sens.get("id") or f"{cid}.sensitivity"
        if sens and str(sens.get("status") or "").upper() == "UNCONFIRMED" and sid not in seen:
            seen.add(sid)
            unconfirmed.append({"item": f"{_plain(sens.get('rate_pct'))} % fee ({sid})", "applies_to": [CHANNEL_LABEL.get(cid, cid)],
                                "sources": [s for s in (_source(x) for x in sens.get("sources") or []) if s]})
        elif sens and sid in seen:
            next(u for u in unconfirmed if u["item"].endswith(f"({sid})"))["applies_to"].append(CHANNEL_LABEL.get(cid, cid))
    other = [r for k, v in a.items() if k not in _ASSUMPTION_KNOWN for r in _assumption_rows(v, (k,))]
    unconfirmed += [{"item": f"{r['item']} — {_plain(r.get('value'))}", "applies_to": [], "sources": [{"title": r.get("source"), "url": u} for u in r["urls"]]
                     or ([{"title": r["source"], "url": None}] if r.get("source") else [])} for r in other if r["status"] == "UNCONFIRMED"]
    return {"rules": rules, "channels": channels, "other": other, "unconfirmed": unconfirmed,
            "rules_read_on": a.get("rules_read_on"), "as_of": a.get("as_of")}


_ASSUMPTION_META = ("url", "urls", "source_url", "source", "date", "as_of", "read", "read_at", "published", "status", "unconfirmed", "confirmed")


def _assumption_label(path: tuple) -> str:
    return " · ".join(CHANNEL_LABEL.get(str(p), str(p).replace("_", " ")) for p in path) or "assumption"


def _assumption_row(path: tuple, item, *, unconfirmed: bool = False) -> dict:
    """One fee / rule / setting: what it says, its source, the URL(s) it was read from, the date, and whether it is UNCONFIRMED."""
    if not isinstance(item, dict):
        return {"item": _assumption_label(path), "value": item, "source": None, "urls": [], "date": None, "status": "UNCONFIRMED" if unconfirmed else None}
    urls = [u for u in ([item.get("url"), item.get("source_url")] + (item.get("urls") if isinstance(item.get("urls"), list) else [])) if isinstance(u, str) and u]
    status = item.get("status") if isinstance(item.get("status"), str) else None
    if unconfirmed or item.get("unconfirmed") is True or item.get("confirmed") is False or (status or "").upper() == "UNCONFIRMED":
        status = "UNCONFIRMED"
    name = item.get("name") or item.get("id") or item.get("item")
    values = {k: v for k, v in item.items() if k not in _ASSUMPTION_META and k not in ("name", "id", "item")}
    return {"item": _assumption_label(path + ((name,) if isinstance(name, str) and name else ())), "value": values,
            "source": item.get("source") if isinstance(item.get("source"), str) else None, "urls": list(dict.fromkeys(urls)),
            "date": item.get("date") or item.get("as_of") or item.get("read") or item.get("read_at") or item.get("published"), "status": status}


def _assumption_rows(node, path: tuple = (), *, unconfirmed: bool = False) -> list[dict]:
    """Every assumption the model lists, flattened: a mapping whose values are all plain (no nested mapping) is ONE item; a list under
    `unconfirmed` makes each of its entries an UNCONFIRMED item."""
    unconfirmed = unconfirmed or (bool(path) and str(path[-1]).lower() == "unconfirmed")
    if isinstance(node, dict):
        if node and not any(isinstance(v, dict) or (isinstance(v, list) and any(isinstance(x, dict) for x in v)) for v in node.values()):
            return [_assumption_row(path, node, unconfirmed=unconfirmed)] if path else \
                [r for k, v in node.items() for r in _assumption_rows(v, (k,), unconfirmed=unconfirmed)]
        return [r for k, v in node.items() for r in _assumption_rows(v, path + (k,), unconfirmed=unconfirmed)]
    if isinstance(node, list):
        if unconfirmed or any(isinstance(x, dict) for x in node):
            return [r for i, x in enumerate(node) for r in _assumption_rows(x, path if isinstance(x, dict) else path + (str(i + 1),), unconfirmed=unconfirmed)]
        return [_assumption_row(path, "; ".join(map(str, node)))]
    return [_assumption_row(path, node, unconfirmed=unconfirmed)]


def _whole(v) -> int:
    """A count from the bundle: a whole number ≥ 0, anything else 0."""
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def _agent_reach(sources) -> list[dict]:
    """Contract C11: the bundle's `sources` ({source: {planned, received, statuses: {STATUS: n}}}, product_report.build_bundle) as rows
    in AGENT_REACH_SOURCES order (any other source after them, by name), each with its label, its counts and the note its sections
    show: nothing received = NEEDS_LOCAL_AGENT; uploads but none OK = NOT_READ, the statuses counted (BLOCKED, HUMAN_CHECK, EMPTY,
    then any other by name); otherwise no note. A source neither planned nor received is left out. No `sources` (an older caller) = no
    rows: the page reads exactly as it did before C11."""
    if not isinstance(sources, dict):
        return []
    labels = dict(AGENT_REACH_SOURCES)
    rows = []
    for src in [s for s, _ in AGENT_REACH_SOURCES] + sorted(str(k) for k in sources if k not in labels):
        v = sources.get(src)
        if not isinstance(v, dict):
            continue
        planned, received = _whole(v.get("planned")), _whole(v.get("received"))
        statuses = {str(k): _whole(n) for k, n in _dict(v.get("statuses")).items() if _whole(n)}
        if not planned and not received:
            continue
        label = labels.get(src, src)
        if not received:
            state, note = "NEEDS_LOCAL_AGENT", NEEDS_LOCAL_AGENT.format(source=label)
        elif not statuses.get("OK"):
            counts = ", ".join(f"{s} {statuses[s]}" for s in [s for s in NOT_READ_ORDER if s in statuses]
                               + sorted(s for s in statuses if s not in NOT_READ_ORDER))
            state, note = "NOT_READ", (NOT_READ.format(source=label, counts=counts) if counts else f"{label} could not be read: no data admitted.")
        else:
            state, note = "READ", None
        rows.append({"source": src, "label": label, "planned": planned, "received": received, "statuses": dict(sorted(statuses.items())),
                     "state": state, "note": note})
    return rows


def _decision_block(decision, *, verdicts=None, admission: str = UNADMITTED, ship_to=None, sources=None) -> dict:
    """The decision section of a ReportModel: the products in the model's order, then the assumptions appendix — and, when the bundle
    says what was read through the user's Agent Reach (contract C11), those sources (`_agent_reach`)."""
    decision = _dict(decision)
    assumptions = _dict(decision.get("assumptions"))
    as_of = assumptions.get("as_of") or decision.get("as_of")
    appendix = _assumptions_block(assumptions)
    reach = _agent_reach(sources)
    return {"admission": admission, "as_of": as_of if isinstance(as_of, str) else (None if as_of is None else str(as_of)),
            "ship_to": ship_to or assumptions.get("ship_to") or _dict(decision.get("settings")).get("ship_to") or decision.get("ship_to"),
            "model": decision.get("model"), "policy_hash": decision.get("policy_hash"),
            "products": [_decision_product(p, _dict(verdicts), admission) for p in _dicts(decision.get("products"))],
            "assumptions": appendix, "unconfirmed": appendix["unconfirmed"], "best_channel_rule": BEST_CHANNEL_RULE,
            "error": decision.get("error") if isinstance(decision.get("error"), dict) else None, **({"sources": reach} if reach else {})}


def build_model_from_bundle(decision: dict, *, verdicts: dict | None = None, admission: str = UNADMITTED, meta: dict | None = None) -> dict:
    """ReportModel for the DECISION layout from the decision model `unit_economics.compute(bundle, policy)` returns (plan §4.4).
    `verdicts`: {candidate_id: the connected agent's verdict text} — shown labelled AGENT_VERDICT_LABEL, never computed here.
    `admission`: the label of every row (a quick report's rows are UNADMITTED). `meta`: report_id, title, ship_to, built_at, and the
    bundle's `sources` (contract C11: what was read through the user's Agent Reach; absent = the page as before C11).
    Deterministic given its inputs; reads nothing else. The standard ReportModel keys are present (empty) so every layout draws it."""
    meta = _dict(meta)
    block = _decision_block(decision, verdicts=verdicts, admission=admission, ship_to=meta.get("ship_to"), sources=meta.get("sources"))
    n = len(block["products"])
    title = str(meta.get("title") or "").strip() or f"Product decision report — {n} product{'s' if n != 1 else ''}"
    hrefs = {e["url"] for p in block["products"] for grp in p["links"].values() for e in grp["shown"] if e.get("href")}
    return {
        "run": {"run_id": str(meta.get("report_id") or "product-decision-report"), "created_at": block["as_of"], "status": "compiled",
                "verdict": "PRODUCT DECISION REPORT", "signal": title[:600], "corpus": None, "rounds": {"research": 0}},
        "coverage": {}, "independence": None, "bridges": [], "l4_receipts": [], "quotes": [], "mechanisms": [], "leads": [], "product_concepts": [],
        "sourcing_coverage": [], "utilization": {}, "provenance": [], "excluded_leads": [], "corpus_packets": [], "corpus_answers": [], "held_rejected": [],
        "unresolved": [], "intelligence": None, "market_discovery": None, "product_anchored": None, "capability_failures": [], "settings": None,
        "decision": block,
        "audit": {"observations": 0, "unique_sources": len(hrefs), "queries_compiled": 0, "research_rounds": 0, "events": 0, "hypotheses_total": 0},
        "built_at": str(meta.get("built_at") or block["as_of"] or models.now()),
    }


# ----------------------------------------------------------------- render --
_CSS = """
:root{--bg:#f4f0e9;--surface:#fbf8f3;--ink:#2b2724;--muted:#7a716a;
--accent:#c15f3c;--ok:#4a7a54;--bad:#a4432e;--hair:#d8d0c3}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
--bg:#211e1b;--surface:#2a2622;--ink:#ece5db;--muted:#9a8f85;
--accent:#d47a55;--ok:#7fae88;--bad:#c76a52;--hair:#3d3831}}
:root[data-theme="dark"]{--bg:#211e1b;--surface:#2a2622;--ink:#ece5db;
--muted:#9a8f85;--accent:#d47a55;--ok:#7fae88;--bad:#c76a52;--hair:#3d3831}
body{background:var(--bg);color:var(--ink);margin:0;
font:17px/1.65 "Iowan Old Style",Palatino,Georgia,serif}
.page{max-width:720px;margin:0 auto;padding:56px 24px 96px}
header{border-bottom:1px solid var(--hair);padding-bottom:32px;margin-bottom:40px}
.eyebrow{font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;
text-transform:uppercase;color:var(--accent)}
h1{font-size:34px;line-height:1.15;margin:14px 0 10px;text-wrap:balance;font-weight:600}
.meta{color:var(--muted);font-size:14px}
.verdict{display:inline-block;margin-top:16px;padding:6px 14px;border:1px solid;
border-radius:2px;font:600 13px/1 ui-monospace,Menlo,monospace;letter-spacing:.06em}
.v-ok{color:var(--ok);border-color:var(--ok)} .v-bad{color:var(--bad);border-color:var(--bad)}
h2{font-size:15px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;
color:var(--muted);border-bottom:1px solid var(--hair);padding-bottom:8px;margin:44px 0 18px}
.bridge{list-style:none;padding:0;margin:0}
.bridge li{padding:5px 0 5px 18px;border-left:2px solid var(--ok);position:relative}
.bridge li.inferred{border-left-style:dashed;border-left-color:var(--accent)}
.bridge li .tag{font:500 10px/1 ui-monospace,monospace;letter-spacing:.08em;
text-transform:uppercase;color:var(--muted);margin-left:8px}
table{width:100%;border-collapse:collapse;font-size:15px}
td,th{padding:8px 10px;border-bottom:1px solid var(--hair);text-align:left;vertical-align:top}
th{font:600 11px/1.4 ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.num{font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.sat{color:var(--ok);font-weight:600}.unsat{color:var(--bad);font-weight:600}
blockquote{margin:0 0 14px;padding:10px 16px;background:var(--surface);
border-left:3px solid var(--accent);font-style:italic}
blockquote .src{display:block;margin-top:6px;font:12px/1.4 ui-monospace,monospace;
font-style:normal;color:var(--muted);word-break:break-all}
.card{background:var(--surface);border:1px solid var(--hair);padding:18px 20px;margin:0 0 16px}
.card h3{margin:0 0 4px;font-size:18px;font-weight:600}
.card .econ{font:600 16px/1.4 ui-monospace,Menlo,monospace;color:var(--accent);margin:6px 0}
.card .why{font-size:14px;color:var(--muted)}
.pill{font:600 10px/1 ui-monospace,monospace;letter-spacing:.08em;padding:3px 8px;
border:1px solid var(--hair);border-radius:2px;color:var(--muted);text-transform:uppercase}
.summary{background:var(--surface);border:1px solid var(--hair);padding:20px 24px;margin:0 0 8px}
.mk{font-family:ui-monospace,Menlo,monospace;margin-right:6px}
.mk-ok{color:var(--ok)}.mk-mid{color:var(--accent)}.mk-lo{color:var(--muted)}.mk-x{color:var(--bad)}
.claims{list-style:none;padding:0;margin:0 0 10px}
.claims li{padding:4px 0;border-bottom:1px dotted var(--hair)}
.subhead{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
font-weight:600;margin:18px 0 8px}
.slides{margin:8px 0 0;padding-left:22px;font-size:14px}
footer{margin-top:56px;border-top:1px solid var(--hair);padding-top:16px;
color:var(--muted);font-size:13px}
div.scroll{overflow-x:auto}
"""


def _e(x):
    return html.escape(str(x if x is not None else ""))


# authority markers (docs/11): observation, interpretation and creative
# implication are three different authority levels — never render them as
# one equally-factual paragraph
_MARKS = {"GROUNDED": "●", "OBSERVED": "●",
          "PARTIAL": "◐", "INFERRED": "◐", "CURRENT_SIGNAL": "◐",
          "WORKING_HYPOTHESIS": "○", "SPECULATIVE": "○", "SIMULATED": "○",
          "CREATIVE_RECOMMENDATION": "○",
          # discovery-mode object states (docs/12-13)
          "SUPPORTED": "●", "CONFIRMED": "●",
          "REFINED": "◐", "WEAKENED": "◐", "WEAK": "◐",
          "PROPOSED": "○", "UNVERIFIED": "○", "UNTESTED": "○", "RETAINED": "○"}


def _state_mark(st):
    return _mark(st, contradicted=st in ("CONTRADICTED", "UNSUPPORTED"))


def _mark(cls, contradicted=False):
    if contradicted:
        return '<span class="mk mk-x" title="contradicted">×</span>'
    m = _MARKS.get(cls or "", "○")
    kind = "ok" if m == "●" else ("mid" if m == "◐" else "lo")
    return f'<span class="mk mk-{kind}" title="{_e(cls)}">{m}</span>'


def _render_intelligence(intel: dict, layout: str) -> list[str]:
    out = []
    _SECTIONS = {"market_structure": "Market structure",
                 "customer_community": "Customer & community",
                 "current_signals": "Current signals",
                 "opportunity": "Opportunity", "risks": "Risks"}
    if intel["market_analysis"]:
        out.append("<h2>Market Analysis</h2>")
        for sec, label in _SECTIONS.items():
            claims = [c for c in intel["market_analysis"] if c.get("section") == sec]
            if not claims:
                continue
            out.append(f"<h3 class='subhead'>{label}</h3><ul class='claims'>")
            for c in claims:
                out.append(f"<li>{_mark(c.get('classification'), bool(c.get('contradicting')))} "
                           f"{_e(c.get('statement'))}</li>")
            out.append("</ul>")
    if intel["angles"]:
        out.append("<h2>Angle Portfolio</h2>")
        pf = intel.get("angle_portfolio") or {}
        if pf:
            out.append(f"<p class='why' style='color:var(--muted)'>Selected set: "
                       f"{_e(', '.join(pf.get('covered_hooks') or []))}</p>")
        out.append("<div class='scroll'><table><tr><th></th><th>Type</th><th>Hook</th>"
                   "<th>Thesis</th><th>Disposition</th></tr>")
        sel = set((intel.get("angle_portfolio") or {}).get("selected") or [])
        for a in intel["angles"]:
            if a.get("disposition") == "REJECT" and layout != "FULL_RESEARCH":
                continue
            star = "★ " if a.get("id") in sel else ""
            out.append(f"<tr><td>{_mark(a.get('evidence_state'))}</td>"
                       f"<td class='num'>{_e(a.get('angle_type'))}</td>"
                       f"<td class='num'>{_e(a.get('hook_type') or '—')}</td>"
                       f"<td>{star}{_e(a.get('thesis'))}</td>"
                       f"<td class='num'>{_e(a.get('disposition'))}</td></tr>")
        out.append("</table></div>")
    for b in intel["briefs"]:
        out.append(f"""<div class="card"><h3>Ad brief · {_e(b.get('hook'))}</h3>
<div class="why">tension: {_e(b.get('tension'))}<br>reveal: {_e(b.get('reveal'))}
<br>proof: {_e(b.get('proof') or '—')} · CTA: {_e(b.get('cta') or '—')}</div>""")
        if b.get("slides"):
            out.append("<ol class='slides'>")
            for s in b["slides"]:
                fn = s.get("function") if isinstance(s, dict) else s
                msg = s.get("message", "") if isinstance(s, dict) else ""
                out.append(f"<li><strong>{_e(fn)}</strong> {_e(msg)}</li>")
            out.append("</ol>")
        out.append("</div>")
    if intel["style"]:
        out.append("<h2>Style World</h2><ul class='claims'>")
        for s in intel["style"]:
            desc = s.get("pattern") or s.get("direction") or s.get("id")
            out.append(f"<li>{_mark(s.get('authority'))} {_e(desc)}</li>")
        out.append("</ul>")
    for s in intel["storefront"]:
        out.append(f"""<h2>Storefront Thesis</h2><div class="summary">
<p>{_mark(s.get('authority'))} {_e(s.get('positioning'))}</p>
<p class="why">pillars: {_e(', '.join(s.get('content_pillars') or []))}</p></div>""")
    if intel["chains"] and layout != "EXECUTIVE":
        out.append("<h2>Analysis Chains</h2>")
        for ch in intel["chains"]:
            out.append("<ul class='bridge'>")
            for label, key in [("evidence", "evidence"), ("observation", "observation"),
                               ("interpretation", "interpretation"),
                               ("market", "market_implication"),
                               ("product", "product_implication"),
                               ("ad", "ad_implication")]:
                val = ch.get(key)
                val = ", ".join(val) if isinstance(val, list) else val
                cls = "" if key in ("evidence", "observation") else ' class="inferred"'
                out.append(f"<li{cls}>{_e(val)}<span class='tag'>{label}</span></li>")
            out.append("</ul>")
    if out:
        out.insert(0, "<p class='why' style='color:var(--muted)'>"
                      "● evidence-backed · ◐ partial / inferred · ○ exploratory · × contradicted"
                      "</p>")
    return out


#: who stands behind a block of the governed dossier (consolidation migration, EXECUTION_PLAN Phase 8). A reader must never have to guess
#: whether a line is knowledge, something a person said in the world, the agent's inference, or TrailSignal's decision.
AUTHORITY = {"POLYMATH": "POLYMATH KNOWLEDGE", "FIELD": "LIVE-WORLD OBSERVATION", "AGENT": "AGENT INFERENCE", "TRAIL": "TRAIL DETERMINATION", "REGISTRY": "TRAIL REGISTRY"}


def _auth(*keys: str) -> str:
    return " ".join(f"<span class='auth' style='font:600 10px/1 ui-monospace,monospace;letter-spacing:.06em;border:1px solid currentColor;border-radius:3px;padding:2px 5px;opacity:.75'>{AUTHORITY[k]}</span>" for k in keys)


#: how many unresolved items / distinct step unknowns a page lists before it says "showing N of M"
UNRESOLVED_SHOWN, UNKNOWNS_SHOWN = 100, 60


def _showing(shown: int, total: int, what: str) -> str:
    """A list cut for the page says so (gap B-16); the ReportModel keeps every item."""
    return f"<p class='why'>showing {shown} of {total} {what}</p>" if total > shown else ""


def _first_inferred_hop(path: list, boundary) -> int:
    """Index of the first INFERRED hop: the hop `first_inference_at` names, compared stripped as the bridge law compares it. A
    boundary that names no hop marks every hop inferred — the dossier never calls a hop evidence-backed it cannot place (gap B-36)."""
    hops, b = [str(h).strip() for h in path or []], str(boundary or "").strip()
    return hops.index(b) if b in hops else 0


def _render_lived_world(g: dict) -> list[str]:
    """Population leads, lived clusters and lived situations — the engine's lived world, computed in governed mode from what TrailSignal ADMITTED."""
    out: list[str] = []
    leads, clusters, sits = g.get("population_leads") or [], g.get("lived_clusters") or [], g.get("lived_situations") or []
    if leads:
        out.append(f"<h2>Populations Worth Looking At {_auth('AGENT', 'REGISTRY')}</h2><p class='why'>Leads are places to look, never demand. Lanes: the seed, the knowledge base, a latent problem nobody named a population for, "
                   "and registry situations. Ranked by value of information.</p><div class='scroll'><table><tr><th>Lead</th><th>Lane</th><th>VOI</th><th>Restates the seed?</th><th>Why</th></tr>")
        for l in sorted(leads, key=lambda x: -(x.get("voi") or 0))[:14]:
            out.append(f"<tr><td>{_e(l.get('name'))}</td><td class='num'>{_e(l.get('source_lane'))}</td><td class='num'>{l.get('voi')}</td><td class='num'>{'yes' if l.get('seed_population') else 'no'}</td><td>{_e(l.get('why') or '')}</td></tr>")
        out.append("</table></div>" + _showing(14, len(leads), "leads (highest value of information first)"))
    if clusters:
        out.append(f"<h2>Lived Clusters {_auth('FIELD', 'TRAIL')}</h2><p class='why'>Built only from observations TrailSignal admitted; the voice count is TrailSignal's independence groups. "
                   "ANCHOR = enough records, threads and independent voices to anchor reasoning; THIN = not yet.</p><div class='scroll'><table><tr><th>Community</th><th>Friction</th><th>Authority</th><th>Records / threads / voices</th><th>Unknowns</th></tr>")
        for c in clusters[:12]:
            out.append(f"<tr><td>{_e(c.get('community'))}</td><td>{_e(c.get('friction_family'))}</td><td class='num'><strong>{_e(c.get('authority'))}</strong></td>"
                       f"<td class='num'>{c.get('record_count')} / {c.get('thread_count')} / {c.get('independent_voices')}</td><td>{_e('; '.join(c.get('unknowns') or []))}</td></tr>")
        out.append("</table></div>" + _showing(12, len(clusters), "clusters"))
    if sits:
        out.append(f"<h2>Lived Situations {_auth('AGENT')}</h2><p class='why'>One moment in one real world, reconstructed from admitted records — never a persona. FIELD_ANCHORED sits on an ANCHOR cluster and cites its records; "
                   "RECONSTRUCTED lists what the records do not say; SIMULATED is never evidence.</p>")
        for x in sits[:10]:
            fr = "; ".join(f"{_e(f.get('text'))} [{_e(f.get('authority'))}: {_e(', '.join(map(str, f.get('refs') or [])))}]" for f in x.get("frictions") or [] if isinstance(f, dict))
            out.append(f"<div class='card'><h3>{_e(x.get('participants') or x.get('community') or x.get('id'))} — {_e(x.get('activity') or '')} · {_e(x.get('moment') or '')} · <span class='num'>{_e(x.get('authority'))}</span></h3>"
                       f"<div class='why'>{fr or '—'}</div><div class='econ'>unknowns: {_e('; '.join(map(str, x.get('unknowns') or [])) or 'none listed')}</div></div>")
        out.append(_showing(10, len(sits), "situations"))
    return out


def _render_transduction(t: dict | None) -> list[str]:
    """§13.2: what was abstracted, what each hypothesis declares as its origin, the bridge it earned — authorities kept apart."""
    if not t:
        return []
    out = [f"<h2>Transduction — from the corpus to the hypothesis {_auth('POLYMATH', 'AGENT')}</h2><p class='why'>Corpus evidence is cited by id; the structure below is the agent's "
           "ABSTRACTION of it (inferred, not evidence); the live world and TrailSignal's determination come later and are shown in their own sections.</p>"]
    if t.get("transferable_invariants"):
        out.append("<p><strong>Transferable invariants</strong> (source-independent): " + _e(" · ".join(t["transferable_invariants"][:6])) + "</p>")
    if t.get("families"):
        out.append("<p class='why'>" + " · ".join(f"<strong>{_e(k.replace('_', ' '))}</strong>: {_e('; '.join(v[:4]))}" for k, v in t["families"].items()) + "</p>")
    if t.get("latent_structures"):
        out.append("<div class='scroll'><table><tr><th>Latent structure</th><th>Kind</th><th>Text</th><th>Possible populations</th><th>Applies outside the source</th></tr>")
        for x in t["latent_structures"][:12]:
            out.append(f"<tr><td class='num'>{_e(x.get('id'))}</td><td class='num'>{_e(x.get('kind'))}</td><td>{_e(x.get('text'))}</td>"
                       f"<td>{_e(', '.join(map(str, x.get('possible_populations') or [])))}</td><td>{_e(x.get('applicability_outside_source') or '—')}</td></tr>")
        out.append("</table></div>")
    for h in t.get("hypotheses") or []:
        leads = ", ".join(f"{l.get('name')} [{l.get('lane')}{', seed population' if l.get('seed_population') else ''}]" for l in h.get("origin_leads") or [])
        structs = ", ".join(f"{x.get('id')} ({str(x.get('basis') or '').lower().replace('_', ' ')})" for x in h.get("latent_structures") or [])
        out.append(f"<div class='card'><h3>{_e(h.get('hypothesis_id'))}</h3><div class='why'>{_e(h.get('statement'))}<br><strong>Origin</strong>: "
                   + (_e(leads or "no lead resolved") if h.get("origin_declared") else "<em>not declared by the hypothesis</em>")
                   + (f" · structures: {_e(structs)}" if structs else "") + "</div>")
        b = h.get("bridge")
        if b:
            out.append(f"<p style='margin:6px 0 2px'><strong>{_e(b.get('target_mechanism'))}</strong> <span class='pill'>{_e(b.get('status'))} · {_e(b.get('grounding'))}</span></p><ul class='bridge'>")
            first_inferred = _first_inferred_hop(b.get("path") or [], b.get("first_inference_at"))
            for i, hop in enumerate(b.get("path") or []):
                cls, tag = (" class='inferred'", "inferred") if i >= first_inferred else ("", "evidence-backed")
                out.append(f"<li{cls}>{_e(hop)}<span class='tag'>{tag}</span></li>")
            out.append("</ul>")
            for label, key in (("speculative gaps", "gaps"), ("alternatives", "alternatives"), ("falsifiers", "falsifiers")):
                if b.get(key):
                    out.append(f"<p class='why'>{label}: {_e('; '.join(map(str, b[key][:4])))}</p>")
        else:
            out.append("<p class='why'><em>No bridge recorded for this hypothesis.</em></p>")
        out.append("</div>")
    return out


def _render_product_reality(pr: dict | None) -> list[str]:
    """§13.3: GENERATED concepts on the left of every row, EXISTING products under them — never one list."""
    if not pr:
        return []
    out = [f"<h2>Product Reality — generated concepts vs. existing products {_auth('AGENT', 'FIELD', 'TRAIL')}</h2><p class='why'>{pr.get('jobs', 0)} per-concept research job(s). "
           "A concept is the run's own idea; an existing product is something a real seller lists today. They are joined only by the concept tag the research job asked for.</p>"]
    by_concept: dict = {}
    for p in pr.get("existing_products") or []:
        for cid in p.get("applies_to_concepts") or [p.get("concept_id")]:     # a substitute counts for every sibling its job served (gap B-37)
            by_concept.setdefault(cid, []).append(p)
    for c in pr.get("concepts") or []:
        contested = c.get("status") == "EXISTING_PRODUCT_CONTESTS"
        out.append(f"<div class='card'><h3>GENERATED CONCEPT {_e(c.get('concept_id'))} — {_e(c.get('concept'))} "
                   f"<span class='pill' style='{'color:#b00' if contested else ''}'>{_e(str(c.get('status') or '').replace('_', ' ').lower())}</span></h3>"
                   f"<div class='why'>hypothesis {_e(c.get('hypothesis_id'))} · mechanism {_e(c.get('mechanism_id'))} · {c.get('jobs_planned', 0)} job(s) · {c.get('existing_products', 0)} existing product(s)</div>")
        rows = by_concept.get(c.get("concept_id")) or []
        if rows:
            out.append("<div class='scroll'><table><tr><th>EXISTING product</th><th>Relation</th><th>Price as listed</th><th>What was observed</th><th>Source</th></tr>")
            for p in rows[:12]:
                rel = f"<strong style='color:#b00'>{_e(p.get('relation'))} — contests this concept</strong>" if p.get("contests_concept") else _e(p.get("relation"))
                out.append(f"<tr><td>{_e(p.get('product_name') or '—')}{(' · ' + _e(p.get('variation_id'))) if p.get('variation_id') else ''}</td><td class='num'>{rel}</td>"
                           f"<td class='num'>{_e(p.get('price_raw') or '—')}</td><td>{_e(p.get('claim'))}</td><td class='num'>{_e(p.get('url') or '')}</td></tr>")
            out.append("</table></div>")
        out.append("</div>")
    return out


def _polarity_cell(r: dict) -> str:
    """The record's global polarity and, for every hypothesis where TrailSignal's stated relation differs from it (ADR-069), what the
    record counts as FOR that hypothesis (gap B-11)."""
    differs = [f"{rel.get('hypothesis_id')}: {polarity_for(r, rel.get('hypothesis_id')) or 'neutral'}" for rel in r.get("hypothesis_relations") or []
               if polarity_for(r, rel.get("hypothesis_id")) != r.get("polarity")]
    return _e(r.get("polarity")) + "".join(f"<br>{_e(d)}" for d in differs)


def _render_governed(g: dict) -> list[str]:
    """The governed block (docs/27): TrailSignal's record VERBATIM, the hypotheses as the adapter's ledger holds them, and
    every field observation as TrailSignal left it — admitted, or rejected with its reason code. Nothing here is computed."""
    out = [f"<h2>Governed Run</h2><p class='why'>Adapter <strong>{_e(g.get('adapter'))}</strong> · reasoning by {_e(g.get('agent_identity'))} · "
           f"harness {_e(', '.join(map(str, g.get('harness_ids') or [])))} · {(g.get('steps') or {}).get('issued', 0)} steps issued "
           f"({(g.get('steps') or {}).get('agent_reason', 0)} reasoning, {(g.get('steps') or {}).get('harness_actions', 0)} harness actions; "
           f"{(g.get('steps') or {}).get('with_readable_evidence', 0)} carried readable evidence). TrailSignal decided what counts as evidence and computed the only score.</p>"]
    if g.get("gap"):
        out.append(f"<p>{_mark(None, True)} <strong>Typed gap {_e((g['gap'] or {}).get('code'))}</strong> at {_e((g['gap'] or {}).get('step_id'))} — {_e((g['gap'] or {}).get('message'))}. "
                   "A gap is a finding: the run stopped where the contract said it must.</p>")
    snap = g.get("registry_snapshot") or {}
    if snap:
        out.append(f"<p class='why'>{_auth('REGISTRY')} registry snapshot <span class='num'>{_e(snap.get('snapshot_id'))}</span> — source roles, freshness windows, independence groups and hard gates are registry data, never code.</p>")
    out.append(f"<h2>TrailSignal's Record {_auth('TRAIL')}</h2>")
    if g.get("result_without_outputs"):
        out.append(f"<p class='why'>The run ended {_e(g.get('terminal_status'))} before compiling its result: the result carries no step outputs, so TrailSignal's "
                   "records, the admitted evidence, the lived world and the product set are ABSENT from it below — absent, not zero.</p>")
    elif not (g.get("trail_scores") or g.get("score_refusals") or g.get("qualifications")):
        out.append("<p>No score, refusal or qualification record reached the result.</p>")
    for sc in g.get("trail_scores") or []:
        subs = ", ".join(f"{_e(x.get('axis'))} {x.get('value')}" for x in sc.get("subscores") or [] if isinstance(x, dict))
        gaps = "; ".join(f"{_e(x.get('signal_type'))} ({_e(x.get('source_tier'))}): {_e(x.get('reason'))}" for x in sc.get("coverage_gaps") or [] if isinstance(x, dict))
        out.append(f"""<div class="card"><h3>{_e(sc.get('hypothesis_id'))} — score {sc.get('score')} · confidence {sc.get('confidence')}</h3>
<div class="why">subscores: {subs or '—'}<br>coverage gaps: {gaps or 'none recorded'}</div>
<div class="econ">{_e(sc.get('record_id'))} · {_e(sc.get('scoring_version'))} · weights {_e(sc.get('weights_version'))} · {len(sc.get('admitted_evidence_ids') or [])} admitted observation(s) · as of {_e(sc.get('as_of'))} · shown verbatim, never re-ranked</div></div>""")
    for rf in g.get("score_refusals") or []:
        out.append(f"""<div class="card"><h3>{_e(rf.get('hypothesis_id'))} — <span style="color:#b00">REFUSED: {_e(rf.get('reason_code'))}</span></h3>
<div class="why">{_e(rf.get('detail') or '')}</div><div class="econ">{_e(rf.get('record_id'))} · as of {_e(rf.get('as_of'))}</div></div>""")
    for q in g.get("qualifications") or []:
        # QualificationV1 carries `state` (gap B-12); `verdict` / `status` are older records' words
        gates = "; ".join(f"{_e(r.get('name') or r.get('gate_id'))} {_e(r.get('observed'))}/{_e(r.get('minimum'))} {'passed' if r.get('passed') else 'unmet'}"
                          for r in q.get("gate_results") or [] if isinstance(r, dict))
        out.append(f"<p class='why'>qualification {_e(q.get('stage') or q.get('qualification_stage'))}: <strong>{_e(q.get('state') or q.get('verdict') or q.get('status'))}</strong> · "
                   f"{_e(', '.join(map(str, q.get('hypothesis_ids') or [])))}" + (f" · gates: {gates}" if gates else "")
                   + f" · {len(q.get('open_gaps') or [])} open gap(s)</p>")
    out += _render_lived_world(g)
    out += _render_transduction(g.get("transduction"))
    out.append(f"<h2>Reasoning Bridge (governed hypotheses) {_auth('AGENT', 'TRAIL')}</h2><p class='why'>Hypothesis state read from: <strong>{_e(g.get('hypothesis_state_from'))}</strong>"
               + (" — the four-field step view carries no mechanism, population, friction or support; those columns are empty by construction, not by finding." if g.get("hypothesis_state_from") == "STEP_CONTEXT_4_FIELDS" else " (the ledger's newest revision, joined to the run's own outputs).")
               + "</p><div class='scroll'><table><tr><th>Hypothesis</th><th>Statement</th><th>Population · activity · task · context</th><th>Mechanism</th><th>Friction</th>"
                 "<th>Ledger status (rev)</th><th>Field + / − · corpus · contra</th><th>TrailSignal</th></tr>")
    for h in g.get("hypotheses") or []:
        ts = (f"score {h['trail_score'].get('score')}" if h.get("trail_score") else f"refused: {_e((h.get('trail_refusal') or {}).get('reason_code'))}" if h.get("trail_refusal") else "—")
        who = " · ".join(str(x) for x in (h.get("population"), h.get("activity"), h.get("task"), h.get("context")) if x) or "—"
        out.append(f"<tr><td class='num'>{_e(h.get('hypothesis_id'))}</td><td>{_e(h.get('statement'))}</td><td>{_e(who)}</td><td>{_e(h.get('mechanism') or '—')}</td><td>{_e(h.get('suspected_friction') or '—')}</td>"
                   f"<td class='num'>{_e(h.get('status'))} ({_e(h.get('revision') if h.get('revision') is not None else '—')})</td>"
                   f"<td class='num'>{h.get('field_supporting', h.get('field_evidence', 0))} / {h.get('field_contradicting', 0)} · {h.get('knowledge_support', 0)} · {h.get('contradictions', 0)}</td><td class='num'>{ts}</td></tr>")
        if h.get("open_gaps") or h.get("falsifiers"):
            n_open = len(h.get("open_gaps") or [])
            out.append("<tr><td></td><td colspan='7' class='why'>" + (f"open gaps ({n_open}): {_e('; '.join(map(str, h['open_gaps'][:4])))}"
                                                                       + (f" (+{n_open - 4} more)" if n_open > 4 else "") if n_open else "")
                       + (" · " if h.get("open_gaps") and h.get("falsifiers") else "") + (f"falsifiers: {_e('; '.join(map(str, h['falsifiers'][:3])))}" if h.get("falsifiers") else "") + "</td></tr>")
    out.append("</table></div>")
    out += _render_product_reality(g.get("product_reality"))
    coords = g.get("coordinates") or {}
    if coords.get("priors") or coords.get("territories"):
        out.append(f"<h2>Registry Coordinates {_auth('REGISTRY', 'TRAIL')}</h2><p class='why'>Coordinates TrailSignal projected the hypotheses onto — never evidence. "
                   + _e("; ".join(f"{p.get('registry_record_id') or p.get('record_id')} ({p.get('label') or p.get('prior_role')})" for p in (coords.get('priors') or [])[:16]))
                   + (" · territories: " + _e("; ".join(f"{t.get('territory_id')} ({t.get('territory_name') or t.get('territory')})" for t in (coords.get('territories') or [])[:12])) if coords.get("territories") else "") + "</p>")
    adm, rej = g.get("admitted") or [], g.get("rejected") or []
    if g.get("evidence_absent"):
        out.append(f"<h2>Field Observations — {g['evidence_absent'].get('admitted_evidence_ids')} admitted evidence id(s) in the lineage; their records are not in this result "
                   f"{_auth('FIELD', 'TRAIL')}</h2><p class='why'>The run ended {_e(g['evidence_absent'].get('terminal_status'))} before compiling its result, so the "
                   "admitted observations are not shown here — they were admitted, not zero.</p>")
    else:
        out.append(f"<h2>Field Observations — admitted {len(adm)} · rejected {len(rej)} {_auth('FIELD', 'TRAIL')}</h2>")
    if g.get("rejected_by_reason"):
        out.append("<p class='why'>Rejections by TrailSignal reason code: " + _e(", ".join(f"{k} × {v}" for k, v in g["rejected_by_reason"].items())) + " — rejections are findings, shown as recorded.</p>")
    for ro in g.get("receipt_omissions") or []:
        out.append("<p class='why'>Never submitted (" + _e(ro.get("action_kind")) + "): " + _e("; ".join(f"{v} × {k}" for k, v in (ro.get("omitted_by_reason") or {}).items())) + "</p>")
    if adm:
        out.append("<div class='scroll'><table><tr><th>Stage</th><th>Role</th><th>Polarity</th><th>Freshness</th><th>Independence group</th><th>Quote</th><th>Source</th></tr>")
        for r in adm[:40]:
            out.append(f"<tr><td class='num'>{_e(r.get('stage'))}</td><td class='num'>{_e(r.get('role'))}</td><td class='num'>{_polarity_cell(r)}</td><td class='num'>{_e(r.get('freshness'))}</td>"
                       f"<td class='num'>{_e(r.get('independence_group'))}</td><td>“{_e(r.get('quote') or r.get('claim') or '')}”</td><td class='num'>{_e(r.get('url') or '')}</td></tr>")
        out.append("</table></div>")
    if rej:
        out.append("<div class='scroll'><table><tr><th>Reason code</th><th>Detail</th><th>Quote</th><th>Source</th></tr>")
        for r in rej[:40]:
            out.append(f"<tr><td class='num'>{_e(r.get('reason_code'))}</td><td>{_e(r.get('detail') or '')}</td><td>“{_e(r.get('quote') or r.get('claim') or '')}”</td><td class='num'>{_e(r.get('url') or '')}</td></tr>")
        out.append("</table></div>")
    if g.get("rejected_submissions"):
        out.append("<p class='why'>Submissions the adapter refused (the step stayed open and was answered again): "
                   + _e("; ".join(f"{x.get('step_id')} ({x.get('kind')})" for x in g["rejected_submissions"])) + "</p>")
    if g.get("falsification_experiment"):
        out.append(f"<p class='why'><strong>Cheapest falsification experiment:</strong> {_e(g['falsification_experiment'])}</p>")
    ln = g.get("lineage") or {}
    if ln:
        out.append("<p class='why' style='color:var(--muted)'>Lineage: " + _e(" · ".join(f"{k.replace('_', ' ')} {v}" for k, v in ln.items())) + "</p>")
    return out


# ------------------------------------------------------- render: decision --
#: added to the stylesheet only when a page carries a decision section, so every other page stays byte for byte what it was. Numbers are
#: right-aligned with tabular figures; tables scroll sideways inside their box on a phone (the channel column stays put); light + dark
#: come from the same tokens as the rest of the report.
_DECISION_CSS = """
.page.decision{max-width:980px}
.dec table.dt{font-size:14px}
.dec .dt td,.dec .dt th{padding:7px 9px}
.dec td.n,.dec th.n{text-align:right;font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;white-space:nowrap}
.dec .chip{display:inline-block;font:600 10.5px/1.25 ui-monospace,Menlo,monospace;letter-spacing:.05em;padding:3px 6px;margin:1px 4px 3px 0;
border:1px solid currentColor;border-radius:3px;white-space:nowrap}
.dec .chip-pass{color:var(--ok)}.dec .chip-warn{color:var(--accent)}.dec .chip-fail{color:var(--bad)}
.dec .chip-unknown{color:var(--muted);border-style:dashed}
.dec .chip-req{color:var(--ink);background:var(--surface);border-style:double;border-width:3px}
.dec .req{font-size:13px;font-weight:600;color:var(--ink)}
.dec th.op{white-space:nowrap}
.dec .unk{font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.06em;color:var(--muted)}
.dec a{color:var(--accent);text-underline-offset:2px;overflow-wrap:anywhere}
.dec .url{font:12px/1.4 ui-monospace,Menlo,monospace;color:var(--muted);overflow-wrap:anywhere}
.dec h2.ptitle{font-size:22px;line-height:1.25;letter-spacing:0;text-transform:none;color:var(--ink);border-bottom:2px solid var(--ink);margin-top:60px}
.dec .minihead{font:600 12px/1.4 ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:16px 0 6px}
.dec .caution{border-left:3px solid var(--bad);background:var(--surface);padding:8px 12px;font-size:14px;margin:10px 0}
.dec .agent{border:1px dashed var(--accent);background:var(--surface);padding:12px 16px;margin:18px 0}
.dec .agent .label{font:600 11px/1.4 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.dec ul.links{list-style:none;padding:0;margin:0}
.dec ul.links li{padding:4px 0;border-bottom:1px dotted var(--hair);font-size:15px}
.dec details{margin:14px 0}
.dec summary{cursor:pointer;color:var(--muted);font-size:14px}
.dec .sticky{position:sticky;left:0;background:var(--bg);z-index:1}
.dec .best{color:var(--ok);font-weight:600;white-space:nowrap}
@media (max-width:640px){.page{padding:28px 16px 64px}h1{font-size:26px}.dec table.dt{font-size:13px}
.dec .dt td,.dec .dt th{padding:6px 6px}blockquote{padding:8px 12px}}
"""
_UNK = "<span class='unk'>UNKNOWN</span>"


def _usd(v) -> str:
    """Dollars to the cent — or to the precision the engine kept (a stated Alibaba tier of $0.035 stays $0.035), so that a margin row
    adds up on the page exactly as the engine added it."""
    n = _number(v)
    if n is None:
        return _UNK if _unknown(v) else _e(v)
    text = f"{abs(n):,.2f}" if abs(round(n, 2) - n) < 1e-9 else f"{abs(n):,.4f}".rstrip("0")
    return ("−" if n < 0 else "") + f"${text}"


def _pct(v) -> str:
    """A percentage as the engine wrote it (margin_pct is in percent: 24.1 is 24.1 %)."""
    n = _number(v)
    if n is None:
        return _UNK if _unknown(v) else _e(v)
    return ("−" if n < 0 else "") + f"{abs(n):,.1f} %"


def _rate(v) -> str:
    """A fee rate as unit_economics writes it: in percent (rate_pct 8.0 is 8 %)."""
    n = _number(v)
    return _UNK if n is None else f"{n:g} %"


def _count(v) -> str:
    n = _number(v)
    if n is None:
        return _UNK if _unknown(v) else _e(v)
    return f"{n:,.0f}" if float(n).is_integer() else f"{n:,}"


def _days(lo, hi) -> str:
    lo, hi = _number(lo), _number(hi)
    if lo is None and hi is None:
        return _UNK
    if lo is None or hi is None:
        return f"≤ {hi:g}" if lo is None else f"≥ {lo:g}"
    return f"{lo:g}" if lo == hi else f"{lo:g}–{hi:g}"


def _text(v, *, empty: str = _UNK) -> str:
    return empty if _unknown(v) else _e(v)


def _plain(v) -> str:
    """A receipt's or an assumption's value as text (escaped): numbers as the engine wrote them, structures flattened."""
    if _unknown(v):
        return "UNKNOWN"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return f"{v:,}" if isinstance(v, int) else f"{v:,.6f}".rstrip("0").rstrip(".")
    if isinstance(v, list):
        return ", ".join(_plain(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{str(k).replace('_', ' ')}: {_plain(x)}" for k, x in v.items())
    return str(v)


def _chip(verdict: str, prefix: str | None = None) -> str:
    v = str(verdict or "UNKNOWN")
    cls = v.lower() if v in DELIVERY_VERDICTS else "unknown"
    return f"<span class='chip chip-{cls}'>{_e(prefix + ' ' if prefix else '')}{_e(v)}</span>"


def _short_url(url: str, cap: int = 64) -> str:
    p = urlparse(url)
    text = ((p.hostname or "").removeprefix("www.") + p.path).rstrip("/") or url
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _link(url, text=None) -> str:
    """An http(s) URL becomes a real anchor (a new tab, no opener, no referrer); any other scheme stays text, shown so a reader sees it."""
    label = text if text not in (None, "") else None
    href = safe_url(url)
    if href:
        return f'<a href="{_e(href)}" rel="noopener noreferrer" target="_blank">{_e(label or _short_url(href))}</a>'
    if _unknown(url):
        return _e(label) if label else _UNK
    return (f"{_e(label)} " if label else "") + f"<span class='url'>{_e(url)}</span>"


def _pill(admission: str) -> str:
    return f" <span class='pill'>{_e(admission)}</span>"


def _model_label(model) -> str:
    return _e(OFFER_MODELS.get(str(model), model)) if not _unknown(model) else _UNK


def _requirement(req: dict | None) -> str:
    """The US stock an inventory line requires, beside its verdict chip: unit_economics' REQUIRES_US_STOCK and its words."""
    if not req:
        return ""
    return (f" <span class='chip chip-req'>REQUIRES US STOCK</span><br><span class='req'>"
            f"{_e(_stock_words(req))}</span>")


#: what a delivery caution code says beside its verdict chip (unit_economics: a US freight quote without confirmed US stock)
CAUTION_TEXT = {"US_STOCK_UNCONFIRMED": "US stock unconfirmed", REQUIRES_US_STOCK: "requires US stock"}


def _cautions(delivery: dict) -> str:
    codes = [str(c) for c in delivery.get("cautions") or [] if c] if isinstance(delivery.get("cautions"), list) else []
    return "".join(f"<span class='why'>({_e(CAUTION_TEXT.get(c, c))})</span> " for c in codes)


def _render_decision(dec: dict, *, governed: bool = False) -> list[str]:
    """The decision section (plan §4.5): the summary table, then per product links · demand · supply · market · margin per channel
    (+ the what-ifs) · the agent's verdict · receipts, then the assumptions and their sources. Drawn the same way in a DECISION page
    and inside a governed dossier."""
    products = dec.get("products") or []
    who = (f"Rows are <strong>{_e(ADMITTED)}</strong>: supplier listings and product-reality prices TrailSignal admitted in this governed run."
           if dec.get("admission") == ADMITTED else
           f"Rows are <strong>{_e(dec.get('admission') or UNADMITTED)}</strong>: read through the user's own Agent Reach and the host's CJ / eBay "
           "APIs — TrailSignal did not admit them.")
    out = ["<div class='dec'>",
           f"<h2>Decision Summary{(' ' + _auth('FIELD', 'TRAIL')) if governed else ''}</h2>",
           "<p class='why'>Every number is computed by Polymath's unit-economics engine from the inputs listed under each product (its receipts "
           "close each product). <strong>UNKNOWN</strong> means an input was missing — the engine never guesses. Ad cost is not assumed: the "
           f"break-even ad cost per sale is the margin before ads. {who}</p>"]
    reach = dec.get("sources") or []
    if reach:                                      # contract C11: once, near the top — the packets read through the user's Agent Reach
        out.append("<p><strong>Read through your Agent Reach:</strong> " + ", ".join(f"{_e(s['label'])} {s['received']}/{s['planned']}" for s in reach)
                   + " <span class='why'>— packets uploaded / packets the report's fetch script plans</span></p>")
    err = dec.get("error")
    if err:
        out.append(f"<p class='caution'>The unit economics could not be computed ({_e(err.get('code'))}): {_e(err.get('message') or '')} — "
                   "the margins and delivery verdicts below are absent, not zero.</p>")
    if not products:
        out.append("" if err else "<p>No product reached the decision model.</p>")
    else:
        out.append("<div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Product</th><th>Best channel</th><th class='n'>Margin before ads</th>"
                   "<th class='n'>Break-even ad cost</th><th>Delivery verdict per channel</th></tr></thead><tbody>")
        for i, p in enumerate(products, 1):
            b = p.get("best")
            best = (f"<span class='best'>{_e(b['label'])}</span><br><span class='why'>{_model_label(b.get('model'))}"
                    + (f" — {_e(_stock_words(b.get('requires_us_stock')))}" if b.get("requires_us_stock") else "") + "</span>"
                    if b else "<span class='unk'>NONE</span> <span class='why'>no channel passes delivery with a known margin</span>")
            chips = "".join(_chip(c["delivery"]["verdict"], CHANNEL_SHORT.get(c["channel_id"], c["channel_id"])) + _cautions(c["delivery"])
                            for c in p["channels"]) or _UNK
            out.append(f"<tr><td class='sticky'>{i}. {_e(p['title'])}</td><td>{best}</td><td class='n'>{_usd((b or {}).get('margin_before_ads_usd'))}</td>"
                       f"<td class='n'>{_usd((b or {}).get('break_even_ad_cost_usd'))}</td><td>{chips}</td></tr>")
        out.append(f"</tbody></table></div><p class='why'>{_e(dec.get('best_channel_rule') or BEST_CHANNEL_RULE)}.</p>")
    for i, p in enumerate(products, 1):
        out += _render_decision_product(i, p, reach)
    others = dec.get("other_prices") or []
    if others:
        out.append("<h3 class='subhead'>Product-reality prices from other retailers</h3><p class='why'>Admitted by TrailSignal, shown as listed; the Amazon / "
                   "eBay market model above does not take them.</p><ul class='links'>"
                   + "".join(f"<li>{_e(o.get('candidate_id'))} — {_link(o.get('url'), o.get('title'))} · price as listed {_text(o.get('price_as_listed'))}"
                             f"{_pill(o.get('admission') or ADMITTED)}</li>" for o in others[:COMPS_SHOWN]) + "</ul>"
                   + _showing(min(len(others), COMPS_SHOWN), len(others), "prices"))
    out += _render_assumptions(dec)
    out.append("</div>")
    return out


def _source_links(sources: list[dict]) -> str:
    """Each source as its link (or its title when it has no http(s) URL) with the date it was read and, when known, published."""
    cells = []
    for s in sources or []:
        dates = " · ".join(x for x in (f"read {_e(s['read'])}" if s.get("read") else "", f"published {_e(s['published'])}" if s.get("published") else "") if x)
        cells.append(_link(s.get("url"), s.get("title")) + (f" <span class='why'>({dates})</span>" if dates else ""))
    return "<br>".join(cells) or "—"


def _offer_name(o: dict) -> str:
    return f"{_e(str(o.get('source') or 'offer').upper())} <span class='url'>{_e(o.get('offer_id') or '')}</span>"


def _render_decision_product(i: int, p: dict, reach: list[dict] | None = None) -> list[str]:
    """One product's sections. `reach` (contract C11, `_agent_reach`): an Agent Reach source with a note says it plainly in its own
    section — Reddit and Amazon under Demand, Alibaba under Supply, eBay under Market — in place of a finding read from nothing; its
    Links row and Market row say NOT READ / why. The engine's numbers are drawn as they are."""
    gaps = {s["source"]: s for s in reach or [] if s.get("note")}
    why_not = {"NEEDS_LOCAL_AGENT": "needs a local agent", "NOT_READ": "could not be read"}

    def gap(src: str, label: str) -> str:
        return f"<p class='caution'><strong>{label}.</strong> {_e(gaps[src]['note'])}</p>"
    status = " · ".join(f"{_e({'cj': 'CJ', 'ebay_api': 'eBay API'}.get(k, k))} {_e(v.get('status') or 'UNKNOWN')}"
                        + (f" ({_e(v['reason_code'])})" if v.get("reason_code") else "") for k, v in (p.get("sources_status") or {}).items())
    out = [f"<section><h2 class='ptitle'>{i}. {_e(p['title'])}</h2><p class='meta'>candidate {_e(p.get('candidate_id') or '—')} · rows "
           f"{_e(p.get('admission'))}{(' · host data: ' + status) if status else ''}</p>"]
    # links
    out.append("<h3 class='subhead'>Links</h3><ul class='links'>")
    for src, label in LINK_SOURCES:
        grp = p["links"].get(src) or {"shown": [], "total": 0}
        cells = " · ".join(_link(e["url"], e.get("text")) for e in grp["shown"]) or (
            f"<span class='unk'>NOT READ</span> <span class='why'>({why_not[gaps[src]['state']]})</span>" if src in gaps else
            "<span class='unk'>NONE FOUND</span>")
        more = f" <span class='why'>(+{grp['total'] - len(grp['shown'])} more)</span>" if grp["total"] > len(grp["shown"]) else ""
        out.append(f"<li><strong>{label}</strong> — {cells}{more}</li>")
    out.append("</ul>")
    # demand: the Reddit summary, then at most five comments (date, points, subreddit, text, the thread); Amazon's rank / bought / ratings
    rd, am = p["demand"]["reddit"], p["demand"]["amazon"]
    subs = ", ".join(rd.get("subreddits") or [])
    out.append("<h3 class='subhead'>Demand</h3>"
               + (gap("reddit", "Reddit") if "reddit" in gaps else
                  f"<p><strong>Reddit.</strong> {_text(rd.get('summary'))} <span class='why'>· threads {_count(rd.get('threads'))} · "
                  f"{_e(subs) if subs else 'no subreddit'} · newest {_text(rd.get('newest'))}</span></p>"))
    for c in rd.get("comments") or []:
        out.append(f"<blockquote>“{_e(c.get('text')) or '(no text)'}”<span class='src'>{_text(c.get('date'), empty='date UNKNOWN')} · "
                   f"{_count(c.get('points'))} points · {_text(c.get('subreddit'), empty='subreddit UNKNOWN')} · "
                   f"{_link(c.get('url') or c.get('thread_url'), 'thread')}</span></blockquote>")
    total = rd.get("comments_total") or 0
    if total > len(rd.get("comments") or []):
        out.append(f"<p class='why'>showing {len(rd.get('comments') or [])} of {total} comments — the summary above counts them all</p>")
    left = rd.get("threads_excluded") or []
    left_total = rd.get("threads_excluded_total") or len(left)
    if left_total:
        shown = "; ".join(f"{_link(x.get('ref'), x.get('title') or x.get('ref') or 'untitled thread')} "
                          f"<span class='why'>({_text(x.get('date'), empty='date UNKNOWN')}{(' · ' + _e(x['subreddit'])) if x.get('subreddit') else ''})</span>"
                          for x in left)
        more = f" <span class='why'>(+{left_total - len(left)} more)</span>" if left_total > len(left) else ""
        out.append(f"<p class='why'><strong>Left out as not about this product: {left_total} thread{'' if left_total == 1 else 's'}</strong> — "
                   f"by the parser's relevance rule their titles do not name the product; they are not in the counts above: {shown}{more}</p>")
    bsr, cat = am.get("bsr_best"), am.get("bsr_best_category")
    if isinstance(bsr, dict):
        bsr, cat = bsr.get("rank"), cat or bsr.get("category")
    bsr_text = (f"#{_count(bsr)}" + (f" in {_e(cat)}" if cat else "")) if _number(bsr) is not None else _text(bsr)
    out.append(gap("amazon", "Amazon") if "amazon" in gaps else
               f"<p><strong>Amazon.</strong> best seller rank {bsr_text} · bought in the past month (highest listing) "
               f"{_count(am.get('bought_past_month_max'))} · ratings (most-rated listing) {_count(am.get('ratings_count_max'))}"
               + (f" · {_count(am['listings'])} matched listing(s)" if "listings" in am else "") + "</p>")
    # supply: the offers, their shipping options, the US-stock caution
    out.append("<h3 class='subhead'>Supply</h3>")
    if "alibaba" in gaps:
        out.append(gap("alibaba", "Alibaba"))
    offers = p.get("offers") or []
    if not offers:
        out.append("<p><span class='unk'>NO OFFER</span> — no CJ or Alibaba offer reached the model; the unit cost is UNKNOWN.</p>")
    else:
        out.append("<div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Offer</th><th>Type</th><th class='n'>Unit cost</th><th class='n'>MOQ</th>"
                   "<th class='n'>MOQ capital</th><th class='n'>Inbound / unit</th><th>Inbound rule</th><th class='n'>Inbound for MOQ</th>"
                   "<th class='n'>Cash before first stock</th><th class='n'>Lead time (days)</th><th class='n'>Time to first stock (days)</th></tr></thead><tbody>")
        none = "<td class='n'><span class='why'>none · dropship</span></td>"
        for o in offers:
            notes = " · ".join(x for x in (f"supplier {_e(o['supplier'])}" if o.get("supplier") else "",
                                           f"lead time as listed: {_e(o['lead_time_text'])}" if o.get("lead_time_text") else "",
                                           f"shipping as listed: {_e(o['shipping_fee_text'])}" if o.get("shipping_fee_text") else "",
                                           f"CJ suggested retail {_usd(o['suggested_retail_usd'])} (reference only, never used as a price)"
                                           if _number(o.get("suggested_retail_usd")) is not None else "") if x)
            note = f"<br><span class='why'>{notes}</span>" if notes else ""
            inventory = o.get("model") == "inventory"
            ib = _dict(o.get("inbound"))
            rule = ib.get("rule") or ("UNKNOWN" if inventory else None)
            out.append(f"<tr><td class='sticky'><strong>{_e(str(o.get('source') or 'offer').upper())}</strong> {_link(o.get('url'), o.get('title') or o.get('offer_id'))}"
                       f"{_pill(o.get('admission'))}{note}</td><td>{_model_label(o.get('model'))}</td>"
                       f"<td class='n'>{_usd(o.get('unit_cost_usd'))}</td><td class='n'>{_count(o.get('moq'))}</td><td class='n'>{_usd(o.get('moq_capital_usd'))}</td>"
                       + (f"<td class='n'>{_usd(ib.get('cost_usd'))}</td><td>{_e(rule)}<br><span class='why'>{_e(INBOUND_RULES.get(rule, ''))}</span></td>"
                          f"<td class='n'>{_usd(o.get('moq_inbound_usd'))}</td><td class='n'>{_usd(o.get('cash_to_first_stock_usd'))}</td>"
                          if inventory else none + "<td>—</td>" + none + none)
                       + f"<td class='n'>{_count(o.get('lead_time_days'))}</td>"
                       + (f"<td class='n'>{_count(o.get('time_to_stock_days'))}</td>" if inventory else none) + "</tr>")
        out.append("</tbody></table></div><p class='minihead'>Shipping legs</p><div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Offer</th>"
                   "<th>Leg</th><th>Origin</th><th>Carrier</th><th class='n'>Cost / unit</th><th class='n'>Days</th><th>Source</th></tr></thead><tbody>")
        for o in offers:
            ships, name = _dicts(o.get("shipping")), _offer_name(o)
            if o.get("model") == "inventory":
                ib = _dict(o.get("inbound"))
                out.append(f"<tr><td class='sticky'>{name}</td><td>inbound — once, to your US stock</td><td>{_text(ib.get('origin'))}</td><td>{_text(ib.get('carrier'))}</td>"
                           f"<td class='n'>{_usd(ib.get('cost_usd'))}</td><td class='n'>{_days(ib.get('days_min'), ib.get('days_max'))}</td>"
                           f"<td>{_e(ib.get('rule') or 'UNKNOWN')} · {_e(INBOUND_RULES.get(ib.get('rule') or 'UNKNOWN', ''))}"
                           + (f"<br><span class='why'>destination: {_e(ib['destination'])}</span>" if ib.get("destination") else "") + "</td></tr>")
                leg = "last mile — each order, from your US stock"
                if not ships:
                    why = o.get("last_mile_note") or "no CJ US→US quote for this product and no owner setting (settings last_mile_usd / last_mile_days)"
                    out.append(f"<tr><td class='sticky'>{name}</td><td>{leg}</td><td colspan='5'><span class='unk'>NO LAST MILE</span> — {_e(why)}: "
                               "cost and days UNKNOWN</td></tr>")
            else:
                leg = "each order — the supplier ships to the buyer"
                if not ships:
                    out.append(f"<tr><td class='sticky'>{name}</td><td>{leg}</td><td colspan='5'><span class='unk'>NO SHIPPING QUOTE</span> — cost and days UNKNOWN</td></tr>")
            for x in ships:
                src = x.get("source") or ("CJ freight quote" if o.get("source") == "cj" else "the offer's quote")
                out.append(f"<tr><td class='sticky'>{name}</td><td>{leg}</td><td>{_text(x.get('origin'))}</td><td>{_text(x.get('carrier'))}</td>"
                           f"<td class='n'>{_usd(x.get('cost_usd'))}</td><td class='n'>{_days(x.get('days_min'), x.get('days_max'))}</td><td>{_e(src)}</td></tr>")
        out.append("</tbody></table></div>")
    if p.get("offers_excluded"):
        out.append("<p class='why'>Left out of the offers: " + _e("; ".join(f"{x.get('source')} {x.get('ref') or ''} — {x.get('why')}" for x in p["offers_excluded"][:COMPS_SHOWN]))
                   + "</p>")
    for note in p.get("us_stock_notes") or []:
        out.append(f"<p class='caution'>{_e(note)}</p>")
    # market: Amazon / eBay n, median, min, max; the reference price and how it was chosen; the comparables with their links
    m = p["market"]
    out.append("<h3 class='subhead'>Market</h3><div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Marketplace (US)</th><th class='n'>n</th>"
               "<th class='n'>Median</th><th class='n'>Min</th><th class='n'>Max</th></tr></thead><tbody>")
    for mk, label in MARKETS:
        row = m[mk]
        why = f" <span class='why'>{_e(row.get('reason_code') or row.get('status'))}</span>" if row.get("reason_code") or row.get("status") else ""
        if mk in gaps:
            why += f" <span class='unk'>NOT READ</span> <span class='why'>({why_not[gaps[mk]['state']]})</span>"
        out.append(f"<tr><td class='sticky'>{label}{why}</td><td class='n'>{_count(row.get('n'))}</td><td class='n'>{_usd(row.get('median'))}</td>"
                   f"<td class='n'>{_usd(row.get('min'))}</td><td class='n'>{_usd(row.get('max'))}</td></tr>")
    basis = m.get("basis_text") or m.get("basis")
    out.append(f"</tbody></table></div><p>Reference sell price <strong>{_usd(m.get('reference_price_usd'))}</strong> — basis: {_text(basis)}"
               + (f" <span class='why'>({_e(m['basis'])})</span>" if m.get("basis_text") and m.get("basis") else "") + "</p>"
               + (f"<p class='why'>{_e(m['basis_note'])}</p>" if m.get("basis_note") else ""))
    if "ebay" in gaps:
        out.append(gap("ebay", "eBay"))
    for mk, label in MARKETS:
        comps = m[mk]["comps"]
        if not comps:
            continue
        rated = any("rating" in c or "ratings_count" in c for c in comps)
        out.append(f"<p class='minihead'>{label} comparables</p><div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Listing</th>"
                   "<th class='n'>Price</th><th class='n'>Shipping</th><th class='n'>Total</th>"
                   + ("<th class='n'>Rating</th><th class='n'>Ratings</th>" if rated else "") + "</tr></thead><tbody>")
        for c in comps:
            total_cell = _usd(c.get("total_usd")) if "total_usd" in c else "—"
            out.append(f"<tr><td class='sticky'>{_link(c.get('url'), c.get('title'))}{_pill(c.get('admission'))}</td><td class='n'>{_usd(c.get('price_usd'))}</td>"
                       f"<td class='n'>{_usd(c.get('shipping_usd')) if 'shipping_usd' in c else '—'}</td><td class='n'>{total_cell}</td>"
                       + (f"<td class='n'>{_e(c['rating']) if _number(c.get('rating')) is not None else '—'}</td>"
                          f"<td class='n'>{_count(c['ratings_count']) if 'ratings_count' in c else '—'}</td>" if rated else "") + "</tr>")
        out.append("</tbody></table></div>" + _showing(len(comps), m[mk].get("comps_total") or 0, f"{label} comparables"))
    if m.get("excluded"):
        out.append("<p class='why'>Left out of the market: " + _e("; ".join(f"{x.get('source')} {x.get('ref') or ''} — {x.get('why')}" for x in m["excluded"][:COMPS_SHOWN]))
                   + (f" (+{len(m['excluded']) - COMPS_SHOWN} more)" if len(m["excluded"]) > COMPS_SHOWN else "") + "</p>")
    # margin per channel (+ the other offers' lines, the what-ifs): every row reads as the subtraction it is
    best = (p.get("best") or {}).get("channel_id")
    head = ("<th class='n'>Sell</th><th class='n op'>− Unit</th><th class='n op'>− Inbound</th><th class='n op'>− Shipping / last mile</th>"
            "<th class='n op'>− Fees</th><th class='n op'>− Returns</th><th class='n op'>= Margin before ads</th><th class='n'>Margin %</th><th class='n'>Break-even ad cost</th>")
    out.append("<h3 class='subhead'>Margin per channel</h3><p class='why'>Each row adds up: sell − unit − inbound − shipping (or the last mile) − fees − returns "
               "= margin before ads, rounded to the cent. A <strong>Dropship</strong> line has no inbound: the supplier ships each order. An "
               "<strong>Inventory</strong> line pays inbound freight once per unit to your own US stock, then the last mile for each order — and "
               "requires holding that stock first.</p>"
               f"<div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Channel</th><th>Offer type</th><th>Offer</th>{head}"
               "<th>Delivery</th></tr></thead><tbody>")
    for c in p["channels"]:
        star = " <span class='best'>★ best</span>" if c["channel_id"] == best else ""
        out.append(f"<tr><td class='sticky'>{_e(c['label'])}{star}</td>" + _line_cells(c) + "</tr>")
    if not p["channels"]:
        out.append(f"<tr><td colspan='13'>{_UNK} — the model carries no channel</td></tr>")
    out.append("</tbody></table></div>")
    alts = [(c, a) for c in p["channels"] for a in c.get("alternatives") or []]
    if alts:
        out.append(f"<details><summary>The other offers on each channel — {len(alts)} line(s)</summary><div class='scroll'><table class='dt'><thead><tr>"
                   f"<th class='sticky'>Channel</th><th>Offer type</th><th>Offer</th>{head}<th>Delivery</th></tr></thead><tbody>"
                   + "".join(f"<tr><td class='sticky'>{_e(c['label'])}</td>{_line_cells(a)}</tr>" for c, a in alts) + "</tbody></table></div></details>")
    for s in p.get("sensitivity") or []:
        title = "What if TikTok Shop charges 8 %" if s["key"] == "tiktok_8pct" else f"What if — {s['key'].replace('_', ' ')}"
        status = f" — <strong>{_e(s['status'])}</strong>" if s.get("status") else ""
        out.append(f"<p class='minihead'>{_e(title)}{status}</p><p class='why'>The channel's line again with only the fee changed: the same offer, sell price, "
                   "unit, inbound, shipping and returns.</p>" + (f"<p class='why'>{_e(s['basis'])}</p>" if s.get("basis") else ""))
        out.append("<div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Channel</th><th>Offer type</th><th class='n'>Fee rate</th>"
                   "<th class='n'>Sell</th><th class='n op'>− Unit</th><th class='n op'>− Inbound</th><th class='n op'>− Shipping / last mile</th>"
                   "<th class='n op'>− Fees</th><th class='n op'>− Returns</th><th class='n op'>= Margin before ads</th><th class='n'>Margin %</th>"
                   "<th class='n'>Break-even ad cost</th></tr></thead><tbody>")
        for r in s["rows"]:
            base = r.get("base") or {}
            out.append(f"<tr><td class='sticky'>{_e(r['label'])}</td><td>{_model_label(base.get('model'))}</td>"
                       f"<td class='n'>{_rate(r.get('rate_pct', s.get('rate_pct')))}</td>"
                       + "".join(f"<td class='n'>{_usd(base.get(k))}</td>" for k in ("sell_price_usd", "unit_cost_usd", "inbound_usd", "shipping_usd"))
                       + f"<td class='n'>{_usd(r.get('fees_usd'))}</td><td class='n'>{_usd(base.get('returns_usd'))}</td>"
                       f"<td class='n'>{_usd(r.get('margin_before_ads_usd'))}</td><td class='n'>{_pct(r.get('margin_pct'))}</td>"
                       f"<td class='n'>{_usd(r.get('break_even_ad_cost_usd'))}</td></tr>")
        if not s["rows"]:
            out.append(f"<tr><td colspan='12'>{_UNK} — no sell price, so no what-if line</td></tr>")
        out.append("</tbody></table></div>")
    # the agent's verdict — the agent's words, never Polymath's
    if p.get("agent_verdict"):
        out.append(f"<div class='agent'><div class='label'>{_e(AGENT_VERDICT_LABEL)}</div><p>{_e(p['agent_verdict'])}</p></div>")
    # receipts: inputs → formula → result, for every number above
    receipts = p.get("receipts") or []
    if receipts:
        out.append(f"<details><summary>How these numbers were computed — {p.get('receipts_total') or len(receipts)} receipt(s)</summary><div class='scroll'><table class='dt'>"
                   "<thead><tr><th>Number</th><th>Formula</th><th>Inputs</th><th class='n'>Result</th></tr></thead><tbody>")
        for rc in receipts:
            what = rc.get("id") or rc.get("field") or rc.get("name") or rc.get("what")
            missing = f"<br><span class='unk'>MISSING</span> {_e(_plain(rc['missing']))}" if rc.get("missing") else ""
            out.append(f"<tr><td class='num'>{_text(what, empty='—')}</td><td>{_text(rc.get('formula'), empty='—')}{missing}</td>"
                       f"<td>{_e(_plain(rc.get('inputs'))) if rc.get('inputs') is not None else '—'}</td><td class='n'>{_e(_plain(rc.get('result')))}</td></tr>")
        out.append("</tbody></table></div>" + _showing(len(receipts), p.get("receipts_total") or 0, "receipts") + "</details>")
    out.append("</section>")
    return out


def _line_cells(c: dict) -> str:
    """One channel line's cells: its supply model (and where its shipping figure comes from), the offer it prices, the money as the
    subtraction it is, the delivery verdict — with the US stock an inventory line requires beside the chip — and the verdict's reason."""
    d = c["delivery"]
    where = " · ".join(x for x in (f"from {_e(d['origin'])}" if not _unknown(d.get("origin")) else "",
                                   f"up to {_count(d['days_max'])} days" if _number(d.get("days_max")) is not None else "",
                                   f"+ {_count(d['handling_business_days'])} business day(s) handling" if _number(d.get("handling_business_days")) is not None else "",
                                   "free-shipping badge eligible" if d.get("badge_eligible") is True else "") if x)
    if c.get("model") == "inventory":
        how = f"last mile: {_e(c['shipping_source'])}" if c.get("shipping_source") else "last mile: NONE known"
    elif c.get("model") == "dropship":
        how = ("the supplier ships each order" + (f": {_e(d['carrier'])} from {_e(d['origin'])}" if d.get("carrier") and not _unknown(d.get("origin")) else ""))
    else:
        how = ""
    offer = f"{_e(str(c.get('source') or '').upper())} <span class='url'>{_e(c.get('offer_id') or '')}</span>" if c.get("offer_id") else _UNK
    how_html = f"<br><span class='why'>{how}</span>" if how else ""
    return (f"<td>{_model_label(c.get('model'))}{how_html}</td><td>{offer}</td>"
            + "".join(f"<td class='n'>{_usd(c.get(k))}</td>" for k in ("sell_price_usd", "unit_cost_usd", "inbound_usd", "shipping_usd", "fees_usd",
                                                                    "returns_usd", "margin_before_ads_usd"))
            + f"<td class='n'>{_pct(c.get('margin_pct'))}</td><td class='n'>{_usd(c.get('break_even_ad_cost_usd'))}</td>"
            f"<td>{_chip(d['verdict'])}{_requirement(c.get('requires_us_stock'))}<br>"
            f"<span class='why'>{_text(d.get('reason'), empty='no reason recorded')}{(' · ' + where) if where else ''}</span></td>")


def _render_assumptions(dec: dict) -> list[str]:
    a = dec.get("assumptions") or {}
    read_on = f" · channel rules read on <strong>{_e(a['rules_read_on'])}</strong>" if a.get("rules_read_on") else ""
    out = ["<h2>Assumptions and Sources</h2>",
           f"<p class='why'>As of <strong>{_text(dec.get('as_of'))}</strong>{read_on} · ship to <strong>{_text(dec.get('ship_to'))}</strong>. Each fee and "
           "delivery rule was read from the page linked beside it, on the date shown. An <strong>UNCONFIRMED</strong> item does not come from the channel itself."
           + (f" Model {_e(dec['model'])} · policy {_e(dec['policy_hash'])}." if dec.get("model") or dec.get("policy_hash") else "") + "</p>"]
    if not (a.get("rules") or a.get("channels") or a.get("other")):
        out.append(f"<p>{_UNK} — the decision model lists no assumption.</p>")
        return out
    if a.get("rules"):
        out.append("<p class='minihead'>How the numbers are made</p><div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Rule</th>"
                   "<th>What the engine does</th><th>Source</th></tr></thead><tbody>"
                   + "".join(f"<tr><td class='sticky'>{_e(r['item'])}</td><td>{_e(r['value'])}</td><td>{_source_links(r.get('sources'))}</td></tr>" for r in a["rules"])
                   + "</tbody></table></div>")
    if a.get("channels"):
        out.append("<p class='minihead'>Channels: fee and delivery rule</p><div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Channel</th>"
                   "<th>Fee per order</th><th>Delivery rule</th><th>Sources</th></tr></thead><tbody>")
        for c in a["channels"]:
            sens = c.get("sensitivity")
            extra = (f"<br><span class='why'>what-if: {_rate(sens.get('rate_pct'))}"
                     + (f" — {_chip(str(sens['status']).upper())}" if sens.get("status") else "") + "</span>") if sens else ""
            out.append(f"<tr><td class='sticky'>{_e(c['label'])}</td><td>{_text(c.get('fee'))}{extra}</td><td>{_text(c.get('delivery'))}</td>"
                       f"<td>{_source_links(c.get('sources'))}</td></tr>")
        out.append("</tbody></table></div>")
    if a.get("other"):
        out.append("<p class='minihead'>Other assumptions</p><div class='scroll'><table class='dt'><thead><tr><th class='sticky'>Item</th><th>Value / rule</th>"
                   "<th>Source</th><th>Date</th><th>Status</th></tr></thead><tbody>")
        for r in a["other"]:
            src = " · ".join(x for x in ([_e(r["source"])] if r.get("source") else []) + [_link(u) for u in r.get("urls") or []]) or "—"
            status = _chip("UNCONFIRMED") if r.get("status") == "UNCONFIRMED" else _e(r.get("status") or "")
            out.append(f"<tr><td class='sticky'>{_e(r['item'])}</td><td>{_e(_plain(r.get('value')))}</td><td>{src}</td><td class='num'>{_text(r.get('date'), empty='—')}</td>"
                       f"<td>{status}</td></tr>")
        out.append("</tbody></table></div>")
    if dec.get("unconfirmed"):
        out.append("<p class='minihead'>UNCONFIRMED</p><ul class='links'>"
                   + "".join(f"<li>{_chip('UNCONFIRMED')} {_e(u['item'])}" + (f" — {_e(', '.join(u['applies_to']))}" if u.get("applies_to") else "")
                             + (f"<br>{_source_links(u.get('sources'))}" if u.get("sources") else "") + "</li>" for u in dec["unconfirmed"]) + "</ul>")
    return out


def _render_decision_page(model: dict, summary_md: str | None = None) -> str:
    """The DECISION layout: the report header, the decision section, the footer."""
    r, dec = model["run"], model.get("decision") or {}
    n = len(dec.get("products") or [])
    admitted = dec.get("admission") == ADMITTED
    out = [f"<style>{_CSS}{_DECISION_CSS}</style><div class='page decision'><header>"
           f"<div class='eyebrow'>Product Decision Report · {'TrailSignal-admitted rows' if admitted else 'quick report — rows unadmitted'}</div>"
           f"<h1>{_e(r.get('signal') or 'Product decision report')}</h1>"
           f"<div class='meta'>{_e(r.get('run_id'))} · as of {_text(dec.get('as_of'))} · ship to {_text(dec.get('ship_to'))} · {n} product{'s' if n != 1 else ''}"
           f" · built {_e(str(model.get('built_at') or '')[:10])}</div>"
           f"<span class='verdict'>{_e(str(ADMITTED if admitted else dec.get('admission') or UNADMITTED).upper())}</span></header>"]
    if summary_md:
        out.append(f'<h2>Executive Summary</h2><div class="summary">{summary_md}</div>')
    if model.get("governed") and not dec:
        out.append("<p>This governed run admitted no supplier listing, so it has no decision section.</p>")
    out += _render_decision(dec, governed=bool(model.get("governed")))
    out.append(f"<footer>Generated deterministically from the decision model of {_e(r.get('run_id'))}: the numbers are the unit-economics engine's (each with "
               "its receipt), the agent's verdicts are the agent's, and this page computes nothing. opportunity-research skill.</footer></div>")
    return "".join(out)


def render(model: dict, layout: str = "FULL_RESEARCH", summary_md: str | None = None) -> str:
    if layout == DECISION_LAYOUT:
        return _render_decision_page(model, summary_md)
    r, out = model["run"], []
    ok_v = r["verdict"] in ("QUALIFIED_LEADS", "PROVISIONAL_LEADS", "LOADOUT_READY",
                            "MARKET_SCOPES_READY", "PRODUCT_MARKETS_READY",
                            "PRODUCT_REFRAMED", "GOVERNED — TRAIL SCORED")
    verdict_label = r["verdict"] or "IN PROGRESS — partial report"
    out.append(f"""<style>{_CSS}{_DECISION_CSS if model.get('decision') else ''}</style><div class="page"><header>
<div class="eyebrow">{'Governed Opportunity Dossier' if model.get('governed') else 'Opportunity Report'} · {_e(layout.replace('_', ' ').title())}</div>
<h1>{_e(((model.get('product_concepts') or [{}])[0].get('name') or r['signal'][:60] + '…') if model.get('governed') else ((model['leads'][0]['mechanism'].replace('_', ' ').title()) if model['leads'] else (r['signal'][:60] + '…')))}</h1>
<div class="meta">{_e(r['run_id'])}{(' · corpus ' + _e(r['corpus'])) if r.get('corpus') else ''} · built {_e(model['built_at'][:10])} · {model['audit']['research_rounds']} research rounds</div>
<span class="verdict {'v-ok' if ok_v else 'v-bad'}">{_e(verdict_label)}</span></header>""")
    if model.get("capability_failures"):
        out.append("<h2>Capability Deficits</h2><ul class='claims'>")
        for cf in model["capability_failures"]:
            out.append(f"<li>{_mark(None, True)} <strong>{_e(cf.get('capability'))}</strong> "
                       f"unavailable at node {_e(cf.get('node'))} — {_e(cf.get('detail') or '')} "
                       f"(coverage deficit, not failure of the research)</li>")
        out.append("</ul>")

    if summary_md:
        out.append(f'<h2>Executive Summary</h2><div class="summary">{summary_md}</div>')

    out.append(f"<h2>Opportunity Thesis</h2><p>{_e(r['signal'])}</p>")

    if model.get("governed"):
        out += _render_governed(model["governed"])
    if layout != "SOURCING" and not model.get("governed"):
        out.append("<h2>Reasoning Bridge</h2>")
        for b in model["bridges"]:
            if b["status"] != "SUPPORTED":
                continue
            out.append(f'<p style="margin:0 0 6px"><strong>{_e(b["mechanism"])}</strong>'
                       + (' <span class="pill">exploratory transfer</span>' if b["exploratory"] else "")
                       + "</p><ul class='bridge'>")
            first_inferred = _first_inferred_hop(b["path"] or [], b["boundary"])
            for i, hop in enumerate(b["path"] or []):
                crossed = i >= first_inferred
                cls = ' class="inferred"' if crossed else ""
                tag = "inferred" if crossed else "evidence-backed"
                out.append(f"<li{cls}>{_e(hop.replace('_', ' '))}<span class='tag'>{tag}</span></li>")
            out.append("</ul>")
            if b.get("invariant"):
                out.append(f'<p class="why" style="color:var(--muted);font-size:14px">Transfer invariant: {_e(b["invariant"])}</p>')

    if not model.get("governed"):            # a governed dossier's coverage is TrailSignal's own (coverage gaps, gates) — shown above, verbatim
        out.append("<h2>Evidence Coverage</h2><div class='scroll'><table><tr><th>Requirement</th><th>Status</th><th>Roles present</th></tr>")
        for name, spec in model["coverage"].items():
            cls = "sat" if spec["satisfied"] else "unsat"
            word = "SATISFIED" if spec["satisfied"] else "UNSATISFIED"
            out.append(f"<tr><td>{_e(name.replace('_', ' '))}</td><td class='{cls}'>{word}</td>"
                       f"<td class='num'>{_e(', '.join(spec['roles_present']) or '—')}</td></tr>")
        out.append("</table></div>")
    if model.get("independence"):
        ind = model["independence"]
        out.append(f"<p class='why' style='color:var(--muted)'>{ind['independent_groups']} independent "
                   f"source groups · {ind['source_families']} source families</p>")

    if layout != "SOURCING" and model["quotes"]:
        out.append("<h2>What the Field Actually Said</h2>")
        for q in model["quotes"][:8 if layout == "EXECUTIVE" else 14]:
            against = f" · <strong style='color:#b00'>contradicts {_e(', '.join(q['contradicts']))}</strong>" if q.get("contradicts") else ""
            out.append(f"<blockquote>“{_e(q['quote'])}”<span class='src'>{_e(q['community'])} — "
                       f"{_e(q['source'])}{against}</span></blockquote>")

    if model.get("product_concepts"):
        out.append("<h2>Product Directions" + (f" {_auth('AGENT')}" if model.get("governed") else "") + "</h2>")
        if model.get("governed"):
            out.append("<p class='why'>The agent proposed these; the domain's portfolio law held them to several DISTINCT directions, each with variations, each citing admitted field evidence. "
                       "No direction is ranked or scored here.</p>")
        leads_by_concept = {}
        for l in model["leads"]:
            leads_by_concept.setdefault(l.get("concept_id"), []).append(l)
        _cov = {c.get("concept_id"): c for c in model.get("sourcing_coverage") or []}
        _n_mech = len({c.get("mechanism_id") for c in model["product_concepts"]})
        _sourced = sum(1 for c in model["product_concepts"] if leads_by_concept.get(c.get("id")))
        out.append(f"<div class=\"why\">{_sourced} of {len(model['product_concepts'])} concepts have supplier leads · "
                   f"{_n_mech} mechanism{'s' if _n_mech != 1 else ''} behind the set"
                   + (" · <b>single-mechanism portfolio</b>: these are one product territory in several forms" if _n_mech == 1 else "") + "</div>")
        for i, c in enumerate(model["product_concepts"], 1):
            vs = "".join(f"<li><b>{_e(v.get('name') if isinstance(v, dict) else str(v))}</b>"
                         + (f" — {_e(v.get('twist'))}" if isinstance(v, dict) and v.get("twist") else "") + "</li>"
                         for v in c.get("variations") or [])
            n_leads = len(leads_by_concept.get(c.get("id"), []))
            _cc = _cov.get(c.get("id")) or {}
            if not n_leads:
                out.append(f"""<div class="card"><h3>{i}. {_e(c.get('name'))} — <span style="color:#b00">UNSOURCED</span></h3>
<div class="econ">{_e(c.get('form_factor') or '')} · moment: {_e(c.get('target_moment') or '')}</div>
<div class="why">{_e(c.get('differentiator') or '')}</div><ul>{vs}</ul>
<div class="why">no supplier lead for this concept ({_cc.get('candidates', 0)} candidate(s) submitted, {_cc.get('parsed', 0)} with parsed price+MOQ) — a finding, not a gap to paper over</div></div>""")
                continue
            out.append(f"""<div class="card"><h3>{i}. {_e(c.get('name'))}</h3>
<div class="econ">{_e(c.get('form_factor') or '')} · moment: {_e(c.get('target_moment') or '')} · buyer: {_e(c.get('buyer') or '')}</div>
<div class="why">{_e(c.get('differentiator') or '')}</div><ul>{vs}</ul>
<div class="why">{n_leads} supplier lead(s) · grounded in {len(c.get('evidence_refs') or [])} observation(s)</div></div>""")
    if model.get("corpus_packets"):
        # docs/22 (v2.2.0): the corpus is asked for EVIDENCE. A packet is what Polymath retrieved, graded and seated for a
        # need — there is no corpus-written answer to show; the reasoning over these rows is θ's and appears above.
        out.append("<h2>Corpus evidence packets" + (f" {_auth('POLYMATH')}" if model.get("governed") else "") + "</h2>")
        for pk in model["corpus_packets"][:12]:
            _ce = pk.get("corpus_explorer") or {}
            _fire = ("Corpus Explore fired" if _ce.get("used") else
                     ("Corpus Explore requested, did not fire" + (f" ({_e((_ce.get('firing') or {}).get('cause'))})" if (_ce.get("firing") or {}).get("cause") else "")
                      if _ce.get("requested") else "Corpus Explore not requested"))
            _n = int(pk.get("n_evidence") or 0)
            _body = (f"{_n} evidence row(s) · CA4 grades {_e(pk.get('ca4_grades') or {})} · utility roles {_e(pk.get('utility_roles') or {})} · origins {_e(pk.get('origins') or {})}"
                     if _n else "no evidence: the corpus does not support this need (a finding, not an abstention to paper over)")
            out.append(f"""<div class="card"><h3>{_e((pk.get('need') or '')[:300])}</h3><div class="why">{_body}</div>
<div class="econ">{_e(pk.get('mode') or '')} · {_e(pk.get('corpus') or '')} · {_e(pk.get('compiled_queries') or 0)} compiled quer(ies) · {_fire} · evidence only — no synthesis</div></div>""")
    if model.get("corpus_answers"):
        out.append("<h2>What the corpus said — legacy synthesis, not evidence</h2>")
        for a in model["corpus_answers"][:10]:
            _tag = "abstained" if a.get("abstained") else f"{len(a.get('citations') or [])} citation(s)"
            out.append(f"""<div class="card"><h3>{_e(a.get('question') or '')}</h3><div class="why">{_e((a.get('answer') or '')[:1200])}</div>
<div class="econ">{_e(a.get('mode') or '')} · {_tag} · {_e(a.get('corpus') or '')} · recorded by a pre-2.2.0 run</div></div>""")
    if model.get("utilization"):
        import utilization as _util
        out.append("<h2>Evidence utilization</h2>")
        out.append("<table class=\"util\">" + "".join(
            f"<tr><td>{_e(row.split('|')[1].strip())}</td><td>{_e(row.split('|')[2].strip())}</td></tr>"
            for row in _util.to_markdown(model["utilization"]).splitlines()[2:]) + "</table>")
    _pv = (model.get("utilization") or {}).get("provenance") or {}
    _prov_rows = (model.get("provenance") or [])
    if _prov_rows:
        out.append("<h2>Provenance</h2><div class='scroll'><table><tr><th>concept</th><th>verdict</th><th>voices</th><th>communities</th><th>lived anchors</th><th>corpus named</th><th>corpus example overlap</th><th>field origin</th><th>field-originated</th></tr>"
                   + "".join(f"<tr><td>{_e(r.get('concept'))}</td><td>{_e(r.get('verdict'))}</td><td class='num'>{r.get('independent_voices')}</td>"
                             f"<td>{_e(', '.join(r.get('communities') or []))}</td><td class='num'>{len(r.get('lived_anchor_ids') or [])}</td>"
                             f"<td>{'yes' + (' (presence)' if (r.get('corpus_presence') or {}).get('named') else '') if r.get('corpus_named') else 'no'}</td>"
                             f"<td>{_e(', '.join(r.get('example_overlap') or []) or '—')}</td><td>{_e((r.get('field_origin') or {}).get('origin') or '—')}</td><td>{'yes' if r.get('field_originated') else 'no'}</td></tr>" for r in _prov_rows)
                   + "</table></div>")
    if model.get("excluded_leads"):
        out.append("<p class='why'>Excluded as CORPUS_ECHO_UNGROUNDED (lineage was corpus example → same noun → same-noun search only): "
                   + _e("; ".join(str(l.get("product_name")) for l in model["excluded_leads"])) + "</p>")
    if model.get("governed"):
        out.append(f"<h2>Supplier Leads {_auth('FIELD', 'TRAIL')}</h2><p class='why'>A lead here is a supplier listing TrailSignal ADMITTED, joined to the mechanism it embodies and the concept it realises. "
                   "Price and MOQ are what the listing said. Whether the opportunity qualifies is TrailSignal's record above — a lead is not a qualification.</p>")
    else:
        out.append("<h2>Qualified Leads</h2>")
    if not model["leads"]:
        out.append("<p>No supplier listing was admitted for any concept — see TrailSignal's record and the unsourced concepts above.</p>" if model.get("governed")
                   else "<p>No leads qualified — see verdict and unresolved items.</p>")
    for i, l in enumerate(model["leads"], 1):
        if l.get("governed"):
            # governed mode: a lead is a supplier observation TrailSignal ADMITTED. Price / MOQ are what the listing said (from
            # the receipt). There is NO evidence score here — the only score in a governed dossier is TrailSignal's, shown above.
            _price = f"${l['price_usd_low']} / unit" if l.get("price_usd_low") is not None else "price not parsed"
            _moq = f"MOQ {l['moq_units']:,}" if isinstance(l.get("moq_units"), (int, float)) else "MOQ not parsed"
            _raw = f" · listing metric: {'; '.join(map(str, l['listing_metrics']))}" if l.get("listing_metrics") else ""
            out.append(f"""<div class="card"><h3>{i}. {_e(l.get('product_name'))}</h3>
<div class="econ">{_e(_price)} · {_e(_moq)}{_e(_raw)}</div>
<div class="why">{_e(l.get('concept') or l.get('concept_id') or '')} · mechanism: {_e(l.get('mechanism') or '—')} · supplier: {_e(l.get('supplier_name') or 'not named on the listing')}<br>
{_e(l.get('channel') or '')} · admitted by TrailSignal as {_e(', '.join(l.get('trail_admission') or []))}<br>{_e(l.get('url') or '')}</div></div>""")
            continue
        hi = f" – {l['price_usd_high']}" if l.get("price_usd_high") not in (None, l.get("price_usd_low")) else ""
        out.append(f"""<div class="card"><h3>{i}. {_e(l['product_name'])}</h3>
<div class="econ">${l['price_usd_low']}{hi} / unit · MOQ {l['moq_units']:,}</div>
<div class="why">Mechanism: {_e(l['mechanism'].replace('_', ' '))} · {_e(l.get('channel') or 'alibaba')} · Supplier: {_e(l['supplier_name'])}
· evidence score {l['evidence_score']}<br>{_e(l.get('url') or '')}</div></div>""")
    if model.get("decision"):
        # PRODUCT-DECISION-REPORT-V1 §4.5: the unit economics of these leads, the SAME section a DECISION page draws
        out += _render_decision(model["decision"], governed=bool(model.get("governed")))

    if layout == "FULL_RESEARCH":
        if model["held_rejected"]:
            out.append("<h2>Held & Rejected Paths</h2><div class='scroll'><table><tr><th>Hypothesis</th><th>Mechanism</th><th>Status</th></tr>")
            for h in model["held_rejected"]:
                out.append(f"<tr><td>{_e(h['id'])}</td><td>{_e(h['mechanism'])}</td><td class='num'>{_e(h['status'])}</td></tr>")
            out.append("</table></div>")
        if model["l4_receipts"]:
            out.append("<h2>Independent Review (L4)</h2><div class='scroll'><table><tr><th>Bridge</th><th>Verdict</th><th>Decisive falsifier</th></tr>")
            for rec in model["l4_receipts"]:
                out.append(f"<tr><td>{_e(rec.get('subject_id'))}</td><td class='num'>{_e(rec.get('status'))}</td>"
                           f"<td>{_e(rec.get('decisive_falsifier') or '—')}</td></tr>")
            out.append("</table></div>")
        if model["unresolved"]:
            out.append("<h2>Unresolved</h2><ul>")
            for u in model["unresolved"][:UNRESOLVED_SHOWN]:
                out.append(f"<li>{_e(u)}</li>")
            out.append("</ul>" + _showing(UNRESOLVED_SHOWN, len(model["unresolved"]), "unresolved items"))
        unknowns = (model.get("governed") or {}).get("unknowns") or {}
        if unknowns.get("distinct"):
            # the steps' own `unknowns` (gap B-16): kept apart from what the research left open, and counted
            out.append(f"<h3 class='subhead'>Unknowns the run's steps recorded — {len(unknowns['distinct'])} distinct of {unknowns.get('recorded')} recorded</h3><ul class='claims'>"
                       + "".join(f"<li>{_e(u)}</li>" for u in unknowns["distinct"][:UNKNOWNS_SHOWN]) + "</ul>"
                       + _showing(UNKNOWNS_SHOWN, len(unknowns["distinct"]), "distinct unknowns"))

    md = model.get("market_discovery")
    if md:
        out.append("<h2>Market Map</h2>")
        if md["promoted"]:
            out.append("<div class='scroll'><table><tr><th>Scope</th><th>Whitespace</th>"
                       "<th>Divergence</th><th>Next mode</th></tr>")
            for p in md["promoted"]:
                scope_label = " / ".join(x for x in (p.get("market"), p.get("niche"),
                                                     p.get("subniche")) if x)
                out.append(f"<tr><td>{_e(scope_label)}</td>"
                           f"<td class='num'>{len(p.get('whitespace_ids') or [])}</td>"
                           f"<td class='num'>{_e(', '.join(p.get('divergence_patterns') or []) or '—')}</td>"
                           f"<td class='num'>{_e(p.get('recommended_mode'))}</td></tr>")
            out.append("</table></div>")
        if md["whitespace"]:
            out.append("<h3 class='subhead'>Whitespace hypotheses</h3><ul class='claims'>")
            for w in md["whitespace"]:
                out.append(f"<li>{_state_mark(w.get('state') or 'PROPOSED')} "
                           f"<strong>{_e((w.get('type') or '').replace('_', ' ').lower())}</strong> — "
                           f"{_e(w.get('mismatch'))}</li>")
            out.append("</ul>")
        if md.get("frontier_stability"):
            fs = md["frontier_stability"]
            out.append(f"<p class='why' style='color:var(--muted)'>Frontier ranking "
                       f"{_e(fs.get('status'))} under ±{fs.get('perturbation', 0)} weight perturbation "
                       f"({fs.get('flips', 0)}/{fs.get('trials', 0)} flips)</p>")

    pa = model.get("product_anchored")
    if pa:
        ident = pa["identity"]
        out.append(f"<h2>Product Identity</h2><p><strong>{_e(ident.get('canonical_name'))}</strong> "
                   f"({_e(ident.get('identity_state'))}) — aliases: "
                   f"{_e(', '.join(ident.get('aliases') or []) or '—')}</p>")
        if pa["claims"]:
            out.append("<h3 class='subhead'>Claim audit</h3><ul class='claims'>")
            for c in pa["claims"]:
                out.append(f"<li>{_state_mark(c.get('state'))} [{_e(c.get('origin'))}] "
                           f"{_e(c.get('claim'))}</li>")
            out.append("</ul>")
        if pa["bridges"]:
            out.append("<h2>Market Bridges</h2><div class='scroll'><table>"
                       "<tr><th></th><th>Market</th><th>Meaning</th><th>State</th><th>Evidence</th></tr>")
            for b in pa["bridges"]:
                out.append(f"<tr><td>{_state_mark(b.get('state'))}</td>"
                           f"<td>{_e(b.get('market_scope'))}</td>"
                           f"<td class='num'>{_e(b.get('meaning_id'))}</td>"
                           f"<td class='num'>{_e(b.get('state'))}</td>"
                           f"<td class='num'>{b.get('supporting', 0)}</td></tr>")
            out.append("</table></div>")
        for rf in pa["reframes"]:
            out.append(f"""<h2>Market Reframe</h2><div class="summary">
<p>{_state_mark(rf.get('user_frame_state'))} User frame “{_e(rf.get('initial_user_frame'))}”
is <strong>{_e(rf.get('user_frame_state'))}</strong>
→ evidence supports “{_e(rf.get('evidence_supported_frame') or '—')}”</p>
<p class="why">{_e(rf.get('why') or '')}</p></div>""")
            adj = (rf.get("adjacent_products") or []) + (rf.get("adjacent_markets") or [])
            if adj:
                out.append(f"<p class='why' style='color:var(--muted)'>Adjacent: {_e(', '.join(map(str, adj)))}</p>")

    intel = model.get("intelligence")
    if intel and layout in ("FULL_RESEARCH", "COMMERCIAL", "EXECUTIVE"):
        out += _render_intelligence(intel, layout)

    st = model.get("settings")
    if st and (st.get("preset") or st.get("revisions")):
        out.append("<h2>Preference History</h2><ul class='claims'>")
        out.append(f"<li>Run started: <strong>{_e(st.get('preset') or 'custom settings')}</strong> "
                   f"(hash {_e(st.get('hash'))})</li>")
        for rv in st["revisions"]:
            changes = ", ".join(f"{k}: {v.get('from')} → {v.get('to')}"
                                for k, v in (rv.get("patch") or {}).items())
            out.append(f"<li>Revision {rv.get('revision')} by {_e(rv.get('requested_by'))} "
                       f"from node {_e(rv.get('effective_from_node'))}: {_e(changes)}</li>")
        out.append("</ul>")

    a = model["audit"]
    out.append(f"""<h2>Research Audit</h2><p class="num" style="font-size:14px">
{a['hypotheses_total']} hypotheses · {a['queries_compiled']} queries compiled ·
{a['observations']} observations from {a['unique_sources']} sources ·
{a['research_rounds']} rounds · {a['events']} durable events</p>
<footer>Generated deterministically from {'the governed run journal of' if model.get('governed') else 'run state'} {_e(r['run_id'])} — facts are frozen;
this report cannot alter verdicts or evidence. opportunity-research skill.</footer></div>""")
    return "".join(out)


#: what `report.py decision` answers on stdout when it cannot draw the page (exit 2): one JSON line {ok: false, code, message}
DECISION_CLI_ERRORS = ("DECISION_BUNDLE_UNREADABLE", "DECISION_BUNDLE_INVALID", "UNIT_ECONOMICS_UNAVAILABLE", "POLICY_UNAVAILABLE",
                       "UNIT_ECONOMICS_FAILED")


def _bundle_meta(bundle: dict) -> dict:
    """What the page shows from the bundle itself — compute never reads these: report_id, title, ship_to, the as-of date, and `sources`
    (contract C11: per Agent Reach source the packets planned / received and their statuses)."""
    settings = _dict(bundle.get("settings"))
    return {"report_id": bundle.get("report_id"), "title": bundle.get("title"), "ship_to": bundle.get("ship_to") or settings.get("ship_to"),
            "built_at": settings.get("as_of") or bundle.get("as_of"), "sources": bundle.get("sources")}


def decision_page(bundle_path: str, out: str, decision_out: str) -> int:
    """`report.py decision`: ONE engine process loads the policy, calls `unit_economics.compute(bundle, policy)` (plan §4.4), builds the
    ReportModel (`build_model_from_bundle`, the bundle's `verdicts` beside it) and draws the DECISION page. Writes the page to `out` and the
    decision model to `decision_out`; prints {ok: true, ...}. A failure prints {ok: false, code (DECISION_CLI_ERRORS), message} and exits 2."""
    def fail(code: str, exc) -> int:
        print(json.dumps({"ok": False, "code": code, "message": (f"{type(exc).__name__}: {exc}" if isinstance(exc, BaseException) else str(exc))[-600:]}))
        return 2
    try:
        with open(bundle_path, encoding="utf-8") as f:
            bundle = json.load(f)
    except (OSError, ValueError) as exc:
        return fail("DECISION_BUNDLE_UNREADABLE", exc)
    if not isinstance(bundle, dict):
        return fail("DECISION_BUNDLE_INVALID", "the bundle is one JSON object: {candidates, host, parsed, settings}")
    try:
        import unit_economics
    except ImportError as exc:
        return fail("UNIT_ECONOMICS_UNAVAILABLE", exc)
    try:
        policy = graphmod.load_policies()
    except Exception as exc:  # noqa: BLE001 — a policy that cannot be read is a typed failure, never a page without its fees
        return fail("POLICY_UNAVAILABLE", exc)
    try:
        decision = unit_economics.compute(bundle, policy)
    except Exception as exc:  # noqa: BLE001
        return fail("UNIT_ECONOMICS_FAILED", exc)
    if not isinstance(decision, dict):
        return fail("UNIT_ECONOMICS_FAILED", f"compute returned {type(decision).__name__}, not the decision model")
    model = build_model_from_bundle(decision, verdicts=bundle.get("verdicts"), meta=_bundle_meta(bundle))
    page = render(model, DECISION_LAYOUT)
    with open(decision_out, "w", encoding="utf-8") as f:
        json.dump(decision, f, ensure_ascii=False, default=str)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(json.dumps({"ok": True, "report": out, "decision": decision_out, "products": len(model["decision"]["products"])}))
    return 0


def main():
    p = argparse.ArgumentParser(prog="report")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--state", required=True)
    b.add_argument("--out")
    rn = sub.add_parser("render")
    rn.add_argument("--model", required=True)
    rn.add_argument("--out", required=True)
    rn.add_argument("--layout", default="FULL_RESEARCH", choices=list(LAYOUTS))
    rn.add_argument("--summary")
    dc = sub.add_parser("decision", help="PRODUCT-DECISION-REPORT-V1: bundle -> unit_economics.compute -> the DECISION page")
    dc.add_argument("--bundle", required=True)
    dc.add_argument("--out", required=True)
    dc.add_argument("--decision-out", dest="decision_out", required=True)
    args = p.parse_args()
    if args.cmd == "decision":
        return decision_page(args.bundle, args.out, args.decision_out)
    if args.cmd == "build":
        model = build_model(models.load_state(args.state))
        text = json.dumps(model, indent=1, ensure_ascii=False)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
            print(json.dumps({"ok": True, "model": args.out}))
        else:
            print(text)
        return 0
    if args.cmd == "render":
        with open(args.model, encoding="utf-8") as f:
            model = json.load(f)
        summary = None
        if args.summary:
            with open(args.summary, encoding="utf-8") as f:
                summary = f.read()
        html_out = render(model, args.layout, summary)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(json.dumps({"ok": True, "report": args.out, "layout": args.layout}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
