#!/usr/bin/env python3
"""Report layer: views over canonical state. Facts frozen, prose optional.

  build   deterministic ReportModel JSON straight from the work state + SQLite
          (no LLM anywhere in this path — everything reproducible)
  render  ReportModel -> self-contained HTML (no external assets; light+dark)

Laws (docs/05 §13-22): reports never affect the research verdict; θ may write
an executive summary but ONLY from the ReportModel (pass --summary FILE.md);
no new facts may appear during presentation; product cards preserve discovery
origin; failures and holds are shown — a report is not sales copy.

  report.py build  --state candidates/run.json [--out model.json]
  report.py render --model model.json --out report.html
                   [--layout FULL_RESEARCH|SOURCING|EXECUTIVE] [--summary sum.md]

GOVERNED runs (docs/27): `build_model_from_governed(journal)` builds the SAME ReportModel from a governed run journal
(python/governed_run.py) and the SAME `render` draws it — there is no second report system. In a governed dossier the
verdict and every number next to a hypothesis are TrailSignal's record, shown VERBATIM (score, confidence, coverage
gaps, refusal reason); nothing is re-ranked and the standalone `evidence_score` never appears. Field observations are
shown as TrailSignal left them: admitted, or rejected WITH the reason code.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph as graphmod  # noqa: E402
import models  # noqa: E402


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


def _seed_of(inp: dict) -> str:
    for k in ("seed", "seed_idea", "question", "signal", "topic", "problem"):
        if isinstance(inp.get(k), str) and inp[k].strip():
            return inp[k].strip()
    return next((v.strip() for v in inp.values() if isinstance(v, str) and v.strip()), "")


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
    quals = [x for x in out.get("qualifications") or [] if isinstance(x, dict)]
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
                "reason_code": x.get("reason_code"), "detail": x.get("detail")}
    admitted = [_row(a, x) for a in adms for x in a.get("admitted") or [] if isinstance(x, dict)]
    rejected = [_row(a, x) for a in adms for x in a.get("rejected") or [] if isinstance(x, dict)]
    hyps: dict = {}
    for s in steps:                                           # the newest view of each hypothesis the adapter showed the agent
        for h in (s["step"].get("context") or {}).get("hypotheses") or []:
            if isinstance(h, dict) and h.get("hypothesis_id"):
                hyps[h["hypothesis_id"]] = h
    score_by = {x.get("hypothesis_id"): x for x in scores}
    refusal_by = {x.get("hypothesis_id"): x for x in refusals}
    hyp_rows = [{"hypothesis_id": hid, "statement": h.get("statement"), "mechanism": h.get("mechanism"), "population": h.get("population"),
                 "activity": h.get("activity"), "suspected_friction": h.get("suspected_friction"), "status": h.get("status"),
                 "field_evidence": len(h.get("field_evidence_ids") or []), "knowledge_support": len(h.get("knowledge_support") or []),
                 "contradictions": len(h.get("contradictions") or []), "trail_score": score_by.get(hid), "trail_refusal": refusal_by.get(hid)}
                for hid, h in hyps.items()]
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
        leads.append({"governed": True, "concept_id": "governed_concept", "product_name": (rows[0].get("claim") or url)[:160], "url": url,
                      "channel": rows[0].get("independence_group") or rows[0].get("source_class"), "price_usd_low": m.get("unit_price_low"),
                      "moq_units": m.get("minimum_order_quantity"), "mechanism": pc.get("mechanism_explanation") or "",
                      "trail_admission": sorted({str(r.get("role")) for r in rows}), "supplier_name": rows[0].get("independence_group") or ""})
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
    limitations = [l for r in receipts for l in (r.get("payload") or {}).get("limitations") or []]
    unresolved = [str(u.get("about") if isinstance(u, dict) else u) for u in (result or {}).get("unknowns") or []] \
        + [str(x) for x in po.get("remaining_uncertainty") or []] + [f"harness limitation: {l}" for l in limitations]
    dead = ("killed", "contradicted", "merged", "weakened")
    return {
        "run": {"run_id": journal.get("run_id"), "created_at": journal.get("created_at"), "status": terminal or "running", "verdict": verdict,
                "signal": _seed_of(journal.get("input") or {})[:600], "corpus": "polymath:" + ",".join(journal.get("corpus_ids") or []) if journal.get("corpus_ids") else None,
                "rounds": {"research": len(receipts)}},
        "coverage": {}, "independence": None, "bridges": [], "l4_receipts": [],
        "quotes": [{"quote": r.get("quote"), "source": r.get("url"), "community": r.get("independence_group") or r.get("source_class"), "roles": [r.get("role")]} for r in admitted][:14],
        "mechanisms": [], "leads": leads,
        "product_concepts": ([{"id": "governed_concept", "name": pc.get("title"), "form_factor": pc.get("problem"), "target_moment": pc.get("context"), "buyer": pc.get("population"),
                               "differentiator": pc.get("mechanism_explanation"), "mechanism_id": "governed", "variations": [], "evidence_refs": po.get("field_evidence_ids") or []}] if pc.get("title") else []),
        "sourcing_coverage": [], "utilization": {}, "provenance": [], "excluded_leads": [], "corpus_packets": packets, "corpus_answers": [],
        "held_rejected": [{"id": h["hypothesis_id"], "mechanism": h.get("mechanism") or h.get("statement"), "status": h.get("status")} for h in hyp_rows if h.get("status") in dead],
        "unresolved": list(dict.fromkeys(unresolved))[:12], "intelligence": None, "market_discovery": None, "product_anchored": None,
        "capability_failures": [], "settings": None,
        "governed": {"adapter": f"{journal.get('adapter_id')} {journal.get('adapter_version')}", "agent_identity": journal.get("agent_identity"), "harness_ids": lineage.get("harness_ids") or [journal.get("harness_id")],
                     "terminal_status": terminal, "gap": gap, "hypotheses": hyp_rows, "trail_scores": scores, "score_refusals": refusals, "qualifications": quals,
                     "admitted": admitted, "rejected": rejected,
                     "rejected_by_reason": {c: sum(1 for r in rejected if r.get("reason_code") == c) for c in sorted({str(r.get("reason_code")) for r in rejected})},
                     "receipt_omissions": [{"action_kind": (r.get("receipt_report") or {}).get("action_kind"), "omitted_by_reason": (r.get("receipt_report") or {}).get("omitted_by_reason") or {}}
                                           for r in receipts if (r.get("receipt_report") or {}).get("omitted_by_reason")],
                     "rejected_submissions": [{"step_id": s.get("step_id"), "kind": s.get("kind"), "errors": (s.get("response") or {}).get("error")} for s in subs if not s.get("accepted")],
                     "falsification_experiment": po.get("cheapest_falsification_experiment"), "contradictions": (result or {}).get("contradictions") or [],
                     "lineage": {k: (len(v) if isinstance(v, list) else v) for k, v in lineage.items()},
                     "steps": {"issued": len(steps), "agent_reason": sum(1 for s in steps if s["step"].get("step_type") == "AGENT_REASON"),
                               "harness_actions": sum(1 for s in steps if s["step"].get("step_type") == "HARNESS_ACTION"),
                               "with_readable_evidence": sum(1 for s in steps if (s.get("evidence") or {}).get("rows"))}},
        "audit": {"observations": len(obs_index), "unique_sources": len(src_count - {None}), "queries_compiled": queries, "research_rounds": len(receipts),
                  "events": len(ev), "hypotheses_total": len(hyp_rows)},
        "built_at": journal.get("built_at") or models.now(),
    }


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
    out.append("<h2>TrailSignal's Record</h2>")
    if not (g.get("trail_scores") or g.get("score_refusals") or g.get("qualifications")):
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
        out.append(f"<p class='why'>qualification {_e(q.get('stage') or q.get('qualification_stage'))}: <strong>{_e(q.get('verdict') or q.get('status'))}</strong> · {_e(', '.join(map(str, q.get('hypothesis_ids') or [])))}</p>")
    out.append("<h2>Reasoning Bridge (governed hypotheses)</h2><div class='scroll'><table><tr><th>Hypothesis</th><th>Statement</th><th>Mechanism</th><th>Ledger status</th><th>Field / corpus / contra</th><th>TrailSignal</th></tr>")
    for h in g.get("hypotheses") or []:
        ts = (f"score {h['trail_score'].get('score')}" if h.get("trail_score") else f"refused: {_e((h.get('trail_refusal') or {}).get('reason_code'))}" if h.get("trail_refusal") else "—")
        out.append(f"<tr><td class='num'>{_e(h.get('hypothesis_id'))}</td><td>{_e(h.get('statement'))}</td><td>{_e(h.get('mechanism') or '—')}</td><td class='num'>{_e(h.get('status'))}</td>"
                   f"<td class='num'>{h.get('field_evidence', 0)} / {h.get('knowledge_support', 0)} / {h.get('contradictions', 0)}</td><td class='num'>{ts}</td></tr>")
    out.append("</table></div>")
    adm, rej = g.get("admitted") or [], g.get("rejected") or []
    out.append(f"<h2>Field Observations — admitted {len(adm)} · rejected {len(rej)}</h2>")
    if g.get("rejected_by_reason"):
        out.append("<p class='why'>Rejections by TrailSignal reason code: " + _e(", ".join(f"{k} × {v}" for k, v in g["rejected_by_reason"].items())) + " — rejections are findings, shown as recorded.</p>")
    for ro in g.get("receipt_omissions") or []:
        out.append("<p class='why'>Never submitted (" + _e(ro.get("action_kind")) + "): " + _e("; ".join(f"{v} × {k}" for k, v in (ro.get("omitted_by_reason") or {}).items())) + "</p>")
    if adm:
        out.append("<div class='scroll'><table><tr><th>Stage</th><th>Role</th><th>Polarity</th><th>Freshness</th><th>Independence group</th><th>Quote</th><th>Source</th></tr>")
        for r in adm[:40]:
            out.append(f"<tr><td class='num'>{_e(r.get('stage'))}</td><td class='num'>{_e(r.get('role'))}</td><td class='num'>{_e(r.get('polarity'))}</td><td class='num'>{_e(r.get('freshness'))}</td>"
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


def render(model: dict, layout: str = "FULL_RESEARCH", summary_md: str | None = None) -> str:
    r, out = model["run"], []
    ok_v = r["verdict"] in ("QUALIFIED_LEADS", "PROVISIONAL_LEADS", "LOADOUT_READY",
                            "MARKET_SCOPES_READY", "PRODUCT_MARKETS_READY",
                            "PRODUCT_REFRAMED", "GOVERNED — TRAIL SCORED")
    verdict_label = r["verdict"] or "IN PROGRESS — partial report"
    out.append(f"""<style>{_CSS}</style><div class="page"><header>
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
            crossed = False
            for hop in b["path"] or []:
                if hop == b["boundary"]:
                    crossed = True
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
            out.append(f"<blockquote>“{_e(q['quote'])}”<span class='src'>{_e(q['community'])} — "
                       f"{_e(q['source'])}</span></blockquote>")

    if model.get("product_concepts"):
        out.append("<h2>Product Directions</h2>")
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
        out.append("<h2>Corpus evidence packets</h2>")
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
    out.append("<h2>Qualified Leads</h2>")
    if not model["leads"]:
        out.append("<p>No leads qualified — see verdict and unresolved items.</p>")
    for i, l in enumerate(model["leads"], 1):
        if l.get("governed"):
            # governed mode: a lead is a supplier observation TrailSignal ADMITTED. Price / MOQ are what the listing said (from
            # the receipt). There is NO evidence score here — the only score in a governed dossier is TrailSignal's, shown above.
            _price = f"${l['price_usd_low']} / unit" if l.get("price_usd_low") is not None else "price not parsed"
            _moq = f"MOQ {l['moq_units']:,}" if isinstance(l.get("moq_units"), (int, float)) else "MOQ not parsed"
            out.append(f"""<div class="card"><h3>{i}. {_e(l.get('product_name'))}</h3>
<div class="econ">{_e(_price)} · {_e(_moq)}</div>
<div class="why">{_e(l.get('channel') or '')} · admitted by TrailSignal as {_e(', '.join(l.get('trail_admission') or []))}<br>{_e(l.get('url') or '')}</div></div>""")
            continue
        hi = f" – {l['price_usd_high']}" if l.get("price_usd_high") not in (None, l.get("price_usd_low")) else ""
        out.append(f"""<div class="card"><h3>{i}. {_e(l['product_name'])}</h3>
<div class="econ">${l['price_usd_low']}{hi} / unit · MOQ {l['moq_units']:,}</div>
<div class="why">Mechanism: {_e(l['mechanism'].replace('_', ' '))} · {_e(l.get('channel') or 'alibaba')} · Supplier: {_e(l['supplier_name'])}
· evidence score {l['evidence_score']}<br>{_e(l.get('url') or '')}</div></div>""")

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
            for u in model["unresolved"]:
                out.append(f"<li>{_e(u)}</li>")
            out.append("</ul>")

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


def main():
    p = argparse.ArgumentParser(prog="report")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--state", required=True)
    b.add_argument("--out")
    rn = sub.add_parser("render")
    rn.add_argument("--model", required=True)
    rn.add_argument("--out", required=True)
    rn.add_argument("--layout", default="FULL_RESEARCH",
                    choices=["FULL_RESEARCH", "SOURCING", "EXECUTIVE", "COMMERCIAL"])
    rn.add_argument("--summary")
    args = p.parse_args()
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
