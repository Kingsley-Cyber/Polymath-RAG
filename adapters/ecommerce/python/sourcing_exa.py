#!/usr/bin/env python3
"""docs/24 §2 — per-concept, per-channel sourcing through Exa (Alibaba + CJdropshipping).

  python3 python/sourcing_exa.py --state run.json --out cands.json [--channels alibaba,cjdropshipping] [--per 4] [--terms 3]

Reads `data.sourcing_plan`, runs one Exa search per (concept, channel, term)
scoped to the channel's site, keeps listing URLs, extracts price / MOQ text
VERBATIM from the highlight when visible (never invents — a listing with no
visible price keeps 'not shown in listing snippet' so normalize marks it
unparsed), and writes supplier_candidates stamped with concept_id,
mechanism_id and channel. Submit the output at supplier_search.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

SITES = {"alibaba": ["alibaba.com", "alibaba.co.uk"], "cjdropshipping": ["cjdropshipping.com"]}
LISTING = {"alibaba": re.compile(r"alibaba\.(?:com|co\.uk|[a-z]{2})/product-detail/([^/?#]+?)_(\d{8,})\.html", re.I),
           "cjdropshipping": re.compile(r"cjdropshipping\.com/product/([^/?#]+?)-p-([0-9A-Za-z-]{6,})\.html", re.I)}
PRICE = re.compile(r"(?:US\s?\$|\$|USD\s?)\s?\d[\d,]*(?:\.\d+)?(?:\s*[-–~]\s*(?:US\s?\$|\$)?\s?\d[\d,]*(?:\.\d+)?)?(?:\s*/\s*(?:piece|pc|set|pair|unit|bag|box))?", re.I)
MOQ = re.compile(r"(?:MOQ|Min(?:\.|imum)?\s*Order(?:\s*Quantity)?)\s*:?\s*\d[\d,]*\s*(?:pcs?|pieces?|sets?|pairs?|units?|bags?|boxes?)?|\d[\d,]*\s*(?:pcs?|pieces?|sets?|pairs?)\s*\(?\s*(?:MOQ|Min\.?\s*Order)", re.I)
NOT_SHOWN = "not shown in listing snippet"


def exa(query: str, n: int) -> list[dict]:
    r = subprocess.run(["mcporter", "call", "exa.web_search_exa", f"query={query}", f"numResults={n}"], capture_output=True, text=True, timeout=120)
    res = []
    for b in re.split(r"\n(?=Title: )", r.stdout):
        t = re.search(r"Title: (.*)", b); u = re.search(r"URL: (\S+)", b)
        if t and u:
            hl = b.split("Highlights:", 1)[1] if "Highlights:" in b else b
            res.append({"title": t.group(1).strip(), "url": u.group(1).strip(), "text": " ".join(hl.split())})
    return res


def parse_listing(channel: str, hit: dict) -> dict | None:
    m = LISTING[channel].search(hit["url"])
    if not m:
        return None
    price = PRICE.search(hit["text"]); moq = MOQ.search(hit["text"])
    p = price.group(0).strip() if price else ""
    n = re.search(r"\d[\d,]*(?:\.\d+)?", p)
    if n and float(n.group(0).replace(",", "")) > 100:      # a highlight number, not a unit price
        p = ""
    return {"id": f"sup_{channel[:2]}_{m.group(2)}", "product_name": hit["title"].split("|")[0].strip()[:120], "supplier_name": f"unresolved ({channel} listing)",
            "price_raw": p or NOT_SHOWN, "moq_raw": (moq.group(0).strip() if moq else "") or NOT_SHOWN, "url": hit["url"], "channel": channel,
            "snippet": hit["text"][:300]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--channels", default="alibaba,cjdropshipping"); ap.add_argument("--per", type=int, default=4); ap.add_argument("--terms", type=int, default=3)
    a = ap.parse_args()
    plan = (json.load(open(a.state)).get("data") or {}).get("sourcing_plan") or []
    wanted = [c.strip() for c in a.channels.split(",") if c.strip()]
    cands, seen = [], set()
    for job in plan:
        ch = job.get("channel") or "alibaba"
        if ch not in wanted or ch not in SITES:
            continue
        found = 0
        for term in (job.get("search_terms") or [])[: a.terms]:
            for site in SITES[ch]:
                for hit in exa(f"{term} site:{site}" + (" wholesale MOQ price" if ch == "alibaba" else ""), a.per):
                    row = parse_listing(ch, hit)
                    if not row or row["id"] in seen:
                        continue
                    seen.add(row["id"]); row.update({"concept_id": job["concept_id"], "mechanism_id": job.get("mechanism_id"), "search_term": term})
                    cands.append(row); found += 1
        print(f"{job['concept_id']:32s} {ch:14s} {found} listings")
    json.dump({"supplier_candidates": cands}, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"-- {len(cands)} candidates ({sum(1 for c in cands if c['price_raw'] != NOT_SHOWN and c['moq_raw'] != NOT_SHOWN)} with visible price+MOQ) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
