#!/usr/bin/env python3
"""docs/21 step 3 — past field evidence re-enters a run as observations.

Polymath's field-evidence corpus holds one document per community thread
(frontmatter: platform, thread_key, community, source_url, exported_at) and
one paragraph per curated observation, each opening with a machine line:

    FIELD_OBS author=u/name roles=A|B purchase=no freshness=LIVE gap=<gap_id> obs=<obs_id>

The corpus lane returns those paragraphs as ordinary rows (tagged
`field_evidence` by the adapter). This module turns them back into
observation candidates for the CURRENT run's open gaps — same gap id when
the signal repeats, keyword overlap otherwise — carrying the ORIGINAL
author/thread identity (independence) and a freshness class recomputed from
the export date. Every candidate cites `corpus_row_id`, which is what the
utilization receipt counts as "gaps with corpus support".

    python3 python/field_evidence.py --state run.json --out payload.json [--min-overlap 3]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys

_HDR = re.compile(r"FIELD_OBS\s+(.*)")
_KV = re.compile(r"(\w+)=(\S+)")
_QUOTE = re.compile(r'^"(.*)"$', re.S)
_STOP = {"that", "this", "with", "from", "they", "their", "what", "when", "have", "which", "into", "than", "then", "there",
         "these", "those", "would", "could", "about", "where", "does", "being", "more", "most", "only", "people", "evidence",
         "missing", "intermediate", "report", "describe", "mention", "communities"}


def _toks(s: str) -> set:
    return {t for t in re.findall(r"[a-z]{4,}", (s or "").lower()) if t not in _STOP}


def parse_row(row: dict) -> dict | None:
    text = row.get("text") or row.get("summary") or ""
    m = _HDR.search(text)
    if not m:
        return None
    kv = dict(_KV.findall(m.group(1)))
    body = text[m.end():].strip()
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    quote = ""
    problem = workaround = ""
    for l in lines:
        q = _QUOTE.match(l)
        if q and not quote:
            quote = q.group(1).strip()
        elif l.lower().startswith("problem:"):
            problem = l.split(":", 1)[1].strip()
        elif l.lower().startswith("workaround:"):
            workaround = l.split(":", 1)[1].strip()
    if not quote:
        return None
    fm = ((row.get("document") or {}).get("frontmatter")) or {}
    return {"author_key": kv.get("author"), "roles": [r for r in (kv.get("roles") or "").split("|") if r],
            "purchase_language": (kv.get("purchase") or "no").lower() in ("yes", "true", "1"),
            "freshness_at_export": kv.get("freshness"), "gap_id": kv.get("gap"), "obs_id": kv.get("obs"),
            "quote": quote, "problem": problem, "workaround": workaround,
            "platform": fm.get("platform") or "reddit", "thread_key": fm.get("thread_key"), "community": fm.get("community"),
            "source_url": fm.get("source_url") or row.get("source"), "exported_at": fm.get("exported_at")}


def recompute_freshness(cls_at_export: str | None, exported_at: str | None, today: dt.date | None = None) -> str:
    """LIVE decays to FAST after 90 days from export; FAST decays to SLOW after
    two years. Conservative: the thread is at least as old as its export."""
    today = today or dt.date.today()
    try:
        age = (today - dt.date.fromisoformat((exported_at or "")[:10])).days
    except ValueError:
        return "SLOW"
    if cls_at_export == "LIVE":
        return "LIVE" if age <= 90 else ("FAST" if age <= 730 else "SLOW")
    if cls_at_export == "FAST":
        return "FAST" if age <= 730 else "SLOW"
    return "SLOW"


def candidates(state: dict, min_overlap: int = 3, today: dt.date | None = None) -> list[dict]:
    d = state.get("data") or {}
    live = {h.get("id") for h in d.get("hypotheses") or [] if h.get("status") not in ("REJECTED", "HOLD")}
    gaps = [g for g in d.get("gaps") or [] if g.get("status") == "open" and g.get("hypothesis_id") in live]
    gap_toks = {g["id"]: _toks(g.get("question", "")) for g in gaps}
    existing = {o.get("id") for o in d.get("observations") or []}
    out = []
    for row in d.get("corpus_evidence") or []:
        if "field_evidence" not in (row.get("tags") or []):
            continue
        p = parse_row(row)
        if not p:
            continue
        rt = _toks(" ".join([p["quote"], p["problem"], p["workaround"]]))
        targets = []
        if p.get("gap_id") and p["gap_id"] in gap_toks:
            targets.append((p["gap_id"], "same_gap"))
        for g in gaps:
            if g["id"] == p.get("gap_id"):
                continue
            ov = len(rt & gap_toks[g["id"]])
            if ov >= min_overlap:
                targets.append((g["id"], f"overlap:{ov}"))
        for gid, why in targets:
            oid = "fobs_" + hashlib.sha1(f"{row.get('id')}|{gid}".encode()).hexdigest()[:12]
            if oid in existing:
                continue
            out.append({"id": oid, "gap_id": gid, "source": p["source_url"], "quote_ref": p["quote"],
                        "community": f"r/{p['community']}" if p.get("community") else None,
                        "problem": p["problem"], "workaround": p["workaround"], "purchase_language": p["purchase_language"],
                        "evidence_roles": p["roles"] or ["BEHAVIOR_SUPPORT"],
                        "freshness": {"class": recompute_freshness(p["freshness_at_export"], p["exported_at"], today)},
                        "source_identity": {"source_family": "community", "platform": p["platform"],
                                            "author_key": p["author_key"], "thread_key": p["thread_key"]},
                        "corpus_row_id": row.get("id"), "query_id": None, "query_used": "field-evidence corpus",
                        "matched_by": why, "origin_observation_id": p.get("obs_id")})
    return out


def lead_candidates(state: dict, today: dt.date | None = None) -> list[dict]:
    """docs/25 §2: prior field rows re-enter as field_records for the leads
    whose community they came from (origin PRIOR_RUN) — real records, real
    authors, freshness recomputed; never a person invented."""
    import lived_world as _lw
    d = state.get("data") or {}
    leads = _lw.all_leads(state)
    by_comm = {}
    for l in leads:
        if l.get("community_key"):
            by_comm.setdefault(_lw._norm_community(l["community_key"]), l["id"])
    existing = {r.get("id") for r in d.get("field_records") or []}
    out = []
    for row in d.get("corpus_evidence") or []:
        if "field_evidence" not in (row.get("tags") or []):
            continue
        p = parse_row(row)
        if not p or not p.get("community"):
            continue
        lid = by_comm.get(_lw._norm_community(p["community"]))
        if not lid:
            continue
        rid = "frec_" + hashlib.sha1(f"{row.get('id')}|{lid}".encode()).hexdigest()[:12]
        if rid in existing:
            continue
        out.append({"id": rid, "lead_id": lid, "source": p["source_url"], "quote_ref": p["quote"],
                    "community": f"r/{p['community']}", "problem": p["problem"], "workaround": p["workaround"],
                    "purchase_language": p["purchase_language"], "evidence_roles": p["roles"] or ["BEHAVIOR_SUPPORT"],
                    "freshness": {"class": recompute_freshness(p["freshness_at_export"], p["exported_at"], today)},
                    "source_identity": {"source_family": "community", "platform": p["platform"],
                                        "author_key": p["author_key"], "thread_key": p["thread_key"]},
                    "origin": "PRIOR_RUN", "corpus_row_id": row.get("id"), "query_used": "field-evidence corpus"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True); ap.add_argument("--out", required=True); ap.add_argument("--min-overlap", type=int, default=3)
    ap.add_argument("--leads", action="store_true", help="docs/25: emit field_records for nominated leads instead of gap observations")
    a = ap.parse_args()
    with open(a.state, encoding="utf-8") as f:
        state = json.load(f)
    if a.leads:
        recs = lead_candidates(state)
        json.dump({"field_records": recs}, open(a.out, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({"field_records": len(recs), "leads_covered": len({r["lead_id"] for r in recs})}, indent=1))
        return 0
    cands = candidates(state, a.min_overlap)
    json.dump({"observations": cands}, open(a.out, "w"), ensure_ascii=False, indent=1)
    by_gap: dict = {}
    for c in cands:
        by_gap.setdefault(c["gap_id"], set()).add((c["source_identity"]["platform"], c["source_identity"]["thread_key"]))
    print(json.dumps({"candidates": len(cands), "gaps_covered": len(by_gap), "threads_per_gap": {k[:8]: len(v) for k, v in by_gap.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
