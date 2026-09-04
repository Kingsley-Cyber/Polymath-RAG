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
        "corpus_answers": d.get("corpus_answers") or [],
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


def render(model: dict, layout: str = "FULL_RESEARCH", summary_md: str | None = None) -> str:
    r, out = model["run"], []
    ok_v = r["verdict"] in ("QUALIFIED_LEADS", "PROVISIONAL_LEADS", "LOADOUT_READY",
                            "MARKET_SCOPES_READY", "PRODUCT_MARKETS_READY",
                            "PRODUCT_REFRAMED")
    verdict_label = r["verdict"] or "IN PROGRESS — partial report"
    out.append(f"""<style>{_CSS}</style><div class="page"><header>
<div class="eyebrow">Opportunity Report · {_e(layout.replace('_', ' ').title())}</div>
<h1>{_e((model['leads'][0]['mechanism'].replace('_', ' ').title()) if model['leads'] else (r['signal'][:60] + '…'))}</h1>
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

    if layout != "SOURCING":
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
    if model.get("corpus_answers"):
        out.append("<h2>What the corpus said</h2>")
        for a in model["corpus_answers"][:10]:
            _tag = "abstained" if a.get("abstained") else f"{len(a.get('citations') or [])} citation(s)"
            out.append(f"""<div class="card"><h3>{_e(a.get('question') or '')}</h3><div class="why">{_e((a.get('answer') or '')[:1200])}</div>
<div class="econ">{_e(a.get('mode') or '')} · {_tag} · {_e(a.get('corpus') or '')}</div></div>""")
    if model.get("utilization"):
        import utilization as _util
        out.append("<h2>Evidence utilization</h2>")
        out.append("<table class=\"util\">" + "".join(
            f"<tr><td>{_e(row.split('|')[1].strip())}</td><td>{_e(row.split('|')[2].strip())}</td></tr>"
            for row in _util.to_markdown(model["utilization"]).splitlines()[2:]) + "</table>")
    out.append("<h2>Qualified Leads</h2>")
    if not model["leads"]:
        out.append("<p>No leads qualified — see verdict and unresolved items.</p>")
    for i, l in enumerate(model["leads"], 1):
        hi = f" – {l['price_usd_high']}" if l.get("price_usd_high") not in (None, l.get("price_usd_low")) else ""
        out.append(f"""<div class="card"><h3>{i}. {_e(l['product_name'])}</h3>
<div class="econ">${l['price_usd_low']}{hi} / unit · MOQ {l['moq_units']:,}</div>
<div class="why">Mechanism: {_e(l['mechanism'].replace('_', ' '))} · Supplier: {_e(l['supplier_name'])}
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
<footer>Generated deterministically from run state {_e(r['run_id'])} — facts are frozen;
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
