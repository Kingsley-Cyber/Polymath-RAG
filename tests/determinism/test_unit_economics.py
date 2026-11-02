"""PRODUCT-DECISION-REPORT-V1 §4.4 (B3) — the decision model `adapters/ecommerce/python/unit_economics.py`, run OUT OF PROCESS the way the
dossier runs it (the engine never imports `polymath_shared`): a JSON bundle in, the decision JSON out.

Pins, each against numbers worked out by hand from the plan's formulas (the arithmetic is in the comments): every channel's line
for one product (TikTok Shop US local AND cross-border, Shopify, eBay, Amazon seller-fulfilled), the delivery verdicts of plan §2,
MOQ capital, the two supply models — CJ = dropship (CJ ships each order), Alibaba = inventory (buy the MOQ, inbound freight by the
listing's own terms — a quote for a stated quantity first, else max(MOQ weight, the stated minimum kg) × the per-kg rate, never below a
stated minimum charge, ÷ MOQ —, then every order ships from your US stock: the last mile is the candidate's cheapest CJ US→US quote,
else the owner's setting, else UNKNOWN) — on the recorded pages, through the real parsers —, a missing input staying UNKNOWN, the 19.3 % returns allowance, break-even ad cost = margin before ads, TikTok's unconfirmed 8 % as a
sensitivity, Reddit as comments with dates plus a counts-only summary (owner, 2026-11-02), a receipt for every number, the same bytes
for the same input, and no file, socket or process touched while computing. No database, no network.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))
ENGINE = ROOT / "adapters" / "ecommerce"
FIXTURES = ROOT / "tests" / "fixtures" / "product_report"
MODULE = ENGINE / "python" / "unit_economics.py"
CHANNELS = ["tiktok_us", "tiktok_cross_border", "shopify", "ebay", "amazon_fbm"]
MONEY = ("offer_id", "sell_price_usd", "unit_cost_usd", "inbound_usd", "shipping_usd", "fees_usd", "returns_usd", "margin_before_ads_usd",
         "margin_pct", "break_even_ad_cost_usd")
HOST_FIXTURES = ROOT / "tests" / "fixtures" / "product_report_host"


def _cj(pid, prices, freight, stock=False, weight=120):
    return {"product_id": pid, "title": f"CJ {pid}", "url": f"https://cjdropshipping.com/product/x-p-{pid}.html", "sell_price_usd": prices[0],
            "suggested_retail_usd": 12.99, "weight_g": weight, "variants": [{"variant_id": f"{pid}-v{i}", "price_usd": p} for i, p in enumerate(prices)],
            "freight": freight, "us_stock_confirmed": stock}


def _amazon(asin, price, **kw):
    return {"kind": "listing", "asin": asin, "title": f"Amazon {asin}", "url": f"https://www.amazon.com/dp/{asin}", "price_usd": price, "relevant": True, **kw}


US_3_7 = {"carrier": "USPS", "cost_usd": 5.20, "days_min": 3, "days_max": 7}
CN_4_9 = {"carrier": "CJPacket Ordinary", "cost_usd": 4.10, "days_min": 4, "days_max": 9}
BUNDLE = {
    "candidates": [{"candidate_id": "worked", "title": "Pet hair remover"}, {"candidate_id": "cn_only", "title": "Lint shaver"},
                   {"candidate_id": "no_comps", "title": "Dog brush"}],
    "host": {"cj": {"worked": {"status": "OK", "reason_code": None, "products": [_cj("P1", [3.27, 3.10], {"CN": [CN_4_9], "US": [US_3_7]}, weight=150)]},
                    "cn_only": {"status": "OK", "products": [_cj("P2", [2.00], {"CN": [dict(CN_4_9, cost_usd=3.00)], "US": []})]},
                    "no_comps": {"status": "OK", "products": [_cj("P3", [4.00], {"CN": [], "US": [dict(US_3_7, cost_usd=5.00)]})]}},
             "ebay": {"worked": {"status": "OK", "listings": [{"title": "E1", "url": "https://www.ebay.com/itm/123456789012", "price_usd": 14.50, "shipping_usd": 0.0},
                                                             {"title": "E2", "url": "https://www.ebay.com/itm/223456789012", "price_usd": 17.00, "shipping_usd": 3.99}]},
                      "no_comps": {"status": "EBAY_NOT_CONFIGURED", "reason_code": "EBAY_NOT_CONFIGURED", "listings": []}}},
    "parsed": {
        "worked": {
            "amazon": [_amazon("B0A", 15.99, bsr={"rank": 5120, "category": "Pet Supplies"}, bought_past_month=2000, ratings_count=1234),
                       _amazon("B0B", 19.99, bsr={"rank": 812, "category": "Pet Supplies"}, ratings_count=8765), _amazon("B0C", 22.49)],
            "alibaba": [{"kind": "listing", "url": "https://www.alibaba.com/product-detail/x_1601132652199.html", "product_id": "1601132652199",
                         "title": "Silicone lint remover", "currency": "USD", "relevant": True,
                         "price_tiers": [{"qty_min": 55, "qty_max": 99, "unit_price": 0.18}, {"qty_min": 100, "qty_max": 499, "unit_price": 0.17},
                                         {"qty_min": 500, "qty_max": None, "unit_price": 0.16}],
                         "moq": 100, "moq_basis": "stated", "shipping_per_kg_usd": 0.84, "shipping_min_kg": 50.0, "gross_weight_kg": 0.17,
                         "shipping_fee_text": "Shipping fee: Starts at US$0.84/kg with a 50kg minimum.", "transit_days_min": 17, "transit_days_max": 24,
                         "lead_time_days_min": 7, "lead_time_days_max": 15}],
            "reddit": [{"kind": "thread", "subreddit": "CatAdvice", "url": "https://www.reddit.com/r/CatAdvice/comments/aa1/hair/", "published_at": "2026-09-30",
                        "relevant": True, "comments": [{"author": "a", "points": 81, "date": "2026-10-01T16:29:00Z", "text": "The silicone one works on couches."},
                                                       {"author": "b", "points": 12, "date": "2026-10-12", "text": "Lint rollers waste money."}]},
                       {"kind": "thread", "subreddit": "dogs", "url": "https://www.reddit.com/r/dogs/comments/bb2/shedding/", "published_at": "2026-08-15",
                        "relevant": True, "comments": [{"author": "c", "points": 81, "date": "2026-10-05", "text": "Rubber gloves help too."},
                                                       {"author": "d", "points": 3, "date": "December 4,", "text": "x" * 420}]}]},
        "cn_only": {"amazon": [_amazon("B2A", 9.00), _amazon("B2B", 9.50), _amazon("B2C", 9.99)]}},
    "settings": {"as_of": "2026-11-02"}}


def _run(bundle: dict, tmp_path: pathlib.Path, name: str = "decision") -> tuple[subprocess.CompletedProcess, bytes | None]:
    """`python unit_economics.py --bundle b.json --out d.json` in a private directory with a minimal environment (no DSN, no key)."""
    bpath, out = tmp_path / f"{name}.bundle.json", tmp_path / f"{name}.json"
    bpath.write_text(json.dumps(bundle), encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "OPPORTUNITY_RESEARCH_DB": str(tmp_path / "loop.sqlite3")}
    proc = subprocess.run([sys.executable, str(MODULE), "--bundle", str(bpath), "--out", str(out)], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=120, check=False)
    return proc, (out.read_bytes() if out.exists() else None)


@pytest.fixture(scope="module")
def decision(tmp_path_factory) -> dict:
    proc, raw = _run(BUNDLE, tmp_path_factory.mktemp("ue"))
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(raw)


def _product(decision: dict, cid: str) -> dict:
    return next(p for p in decision["products"] if p["candidate_id"] == cid)


def _line(ch: dict, keys=MONEY) -> tuple:
    return tuple(ch[k] for k in keys)


def test_worked_example_every_channel(decision):
    """At the $19.99 Amazon median (15.99 / 19.99 / 22.49), CJ $3.10 (the cheaper variant) and Alibaba $0.17 at MOQ 100."""
    p = _product(decision, "worked")
    ch = p["channels"]
    assert decision["channels"] == CHANNELS and set(ch) == set(CHANNELS)     # the list carries the order; the JSON object is key-sorted
    assert p["market"]["reference_price_usd"] == 19.99 and p["market"]["basis"] == "AMAZON_MEDIAN"
    # INVENTORY (Alibaba): unit 0.17 + inbound max(100 × 0.17 kg, the 50 kg minimum) × 0.84 $/kg ÷ 100 = 0.42 + the last mile from US stock (the
    # candidate's cheapest CJ US→US quote: USPS 3-7 days, 5.20) = 5.79 landed; returns 19.3 % × 5.79 = 1.11747 -> 1.12
    # tiktok_us: 6 % × 19.99 = 1.1994 -> 1.20; margin 19.99 - 5.79 - 1.20 - 1.12 = 11.88 = break-even ad cost; 11.88 / 19.99 = 59.43 % -> 59.4
    assert _line(ch["tiktok_us"]) == ("alibaba:1601132652199", 19.99, 0.17, 0.42, 5.20, 1.20, 1.12, 11.88, 59.4, 11.88)
    assert _line(ch["tiktok_cross_border"]) == ("alibaba:1601132652199", 19.99, 0.17, 0.42, 5.20, 1.20, 1.12, 11.88, 59.4, 11.88)
    # shopify: 2.9 % × 19.99 + 0.30 + 39 / 100 = 1.26971 -> 1.27; margin 19.99 - 5.79 - 1.27 - 1.12 = 11.81 (59.1 %, not the 85-90 % of bulk freight alone);
    # WARN: the last mile's 3-7 days + 1 business day of handling = 8 > 7 (R2 #1: every clock that starts at the order counts handling)
    assert _line(ch["shopify"]) == ("alibaba:1601132652199", 19.99, 0.17, 0.42, 5.20, 1.27, 1.12, 11.81, 59.1, 11.81)
    assert ch["shopify"]["delivery"]["verdict"] == "WARN" and ch["shopify"]["delivery"]["handling_business_days"] == 1
    assert ("with 1 business day of handling (setting handling_business_days), which can take up to 3 calendar days (an order on a Friday is scanned "
            "on Monday): 7 calendar days + 3 = up to 10 days > 7") in ch["shopify"]["delivery"]["reason"]
    # ebay: 13.6 % × 19.99 + 0.40 (order above $10) = 3.11864 -> 3.12; margin 19.99 - 5.79 - 3.12 - 1.12 = 9.96
    assert _line(ch["ebay"]) == ("alibaba:1601132652199", 19.99, 0.17, 0.42, 5.20, 3.12, 1.12, 9.96, 49.8, 9.96)
    # amazon_fbm: max(15 % × 19.99, 0.30) + 0.99 = 3.9885 -> 3.99; margin 19.99 - 5.79 - 3.99 - 1.12 = 9.09
    assert _line(ch["amazon_fbm"]) == ("alibaba:1601132652199", 19.99, 0.17, 0.42, 5.20, 3.99, 1.12, 9.09, 45.5, 9.09)
    assert all(ch[c]["model"] == "inventory" and ch[c]["delivery"]["origin"] == "US" and ch[c]["delivery"]["cautions"] == ["REQUIRES_US_STOCK"]
               and "requires holding US stock: first stock in 39 days, cash $59.00 before first stock (goods $17.00 + inbound $42.00)"
               in ch[c]["delivery"]["reason"] for c in CHANNELS)
    # DROPSHIP (CJ $3.10) is kept on every channel: tiktok_us via the US option (China FAILS; 5 + 1 = 6 ≤ 6 business days): 19.99 - 8.30 - 1.20 - 1.60
    # = 8.89; cross-border via China 4-9 (9 + 1 ≤ 15, cheapest passing): 19.99 - 7.20 - 1.20 - 1.39 = 10.20; shopify: no option passes once handling
    # counts (4-9 + 3, 3-7 + 3 > 7: 1 business day of handling can be 3 calendar days), so the cheapest, China, WARN: 19.99 - 7.20 - 1.27 - 1.39 =
    # 10.13; ebay via China: 19.99 - 7.20 - 3.12 - 1.39 = 8.28; amazon: China 9 + 3 = 12 > 10, the US 7 + 3 = 10 ≤ 10 passes: 19.99 - 8.30 - 3.99 - 1.60 = 6.10
    assert _line(ch["tiktok_us"]["alternatives"][0]) == ("cj:P1", 19.99, 3.10, 0.0, 5.20, 1.20, 1.60, 8.89, 44.5, 8.89)
    assert {c: [(a["offer_id"], a["model"], a["margin_before_ads_usd"], a["delivery"]["verdict"]) for a in ch[c]["alternatives"]] for c in CHANNELS} == {
        "tiktok_us": [("cj:P1", "dropship", 8.89, "PASS")], "tiktok_cross_border": [("cj:P1", "dropship", 10.20, "PASS")],
        "shopify": [("cj:P1", "dropship", 10.13, "WARN")], "ebay": [("cj:P1", "dropship", 8.28, "PASS")], "amazon_fbm": [("cj:P1", "dropship", 6.10, "PASS")]}


def test_delivery_verdicts_of_plan_section_2(decision):
    """The brief's cases: CN->US 4-9 days, and a US warehouse 3-7 days with US stock unconfirmed."""
    cn = _product(decision, "cn_only")["channels"]
    # handling counts on every order clock: on a calendar rule 1 business day can be 3 calendar days, so China 4-9 is 9 + 3 = 12 > 10 for Amazon (WARN)
    assert {c: cn[c]["delivery"]["verdict"] for c in CHANNELS} == {"tiktok_us": "FAIL", "tiktok_cross_border": "PASS", "shopify": "WARN",
                                                                   "ebay": "PASS", "amazon_fbm": "WARN"}
    assert cn["tiktok_us"]["delivery"]["origin"] == "CN" and "China" in cn["tiktok_us"]["delivery"]["reason"]
    assert cn["ebay"]["delivery"]["badge_eligible"] is False and cn["ebay"]["delivery"]["business_days_max"] == 7   # 9 calendar days ≥ 7 business > 4
    assert cn["amazon_fbm"]["delivery"]["prime"] == "FAIL" and cn["shopify"]["delivery"]["days_max"] == 9
    us = _product(decision, "no_comps")["channels"]["tiktok_us"]["delivery"]
    assert us["verdict"] == "PASS" and us["origin"] == "US" and us["days_max"] == 7 and us["business_days_max"] == 5
    assert us["cautions"] == ["US_STOCK_UNCONFIRMED"] and "CAUTION" in us["reason"] and "business days" in us["reason"]
    # the only offer FAILS tiktok_us: it is still shown (its verdict says why), with no alternative
    assert cn["tiktok_us"]["offer_id"] == "cj:P2" and cn["tiktok_us"]["alternatives"] == []


def test_fee_formulas_at_a_price_under_ten_dollars(decision):
    """$9.50 (median of 9.00 / 9.50 / 9.99): eBay's $0.30 per-order fee at ≤ $10; returns 19.3 % × (2.00 + 3.00) = 0.965 -> 0.97 (half up)."""
    cn = _product(decision, "cn_only")["channels"]
    # tiktok 0.57; shopify 0.2755 + 0.30 + 0.39 = 0.9655 -> 0.97; ebay 1.292 + 0.30 = 1.592 -> 1.59; amazon 1.425 + 0.99 = 2.415 -> 2.42
    assert [(cn[c]["fees_usd"], cn[c]["returns_usd"], cn[c]["margin_before_ads_usd"], cn[c]["margin_pct"]) for c in CHANNELS] == [
        (0.57, 0.97, 2.96, 31.2), (0.57, 0.97, 2.96, 31.2), (0.97, 0.97, 2.56, 26.9), (1.59, 0.97, 1.94, 20.4), (2.42, 0.97, 1.11, 11.7)]
    assert all(cn[c]["break_even_ad_cost_usd"] == cn[c]["margin_before_ads_usd"] for c in CHANNELS)


def test_the_two_supply_models(decision):
    offers = {o["offer_id"]: o for o in _product(decision, "worked")["offers"]}
    a = offers["alibaba:1601132652199"]
    assert (a["model"], a["unit_cost_usd"], a["moq"], a["moq_capital_usd"], a["lead_time_days"], a["time_to_stock_days"]) == (
        "inventory", 0.17, 100, 17.00, 15, 39)                                            # capital 100 × 0.17; first stock in 15 + 24 days
    assert a["inbound"] == {"origin": "CN", "carrier": "the listing's stated shipping", "cost_usd": 0.42, "days_min": 17, "days_max": 24, "rule": "MIN_KG",
                            "destination": "destination not stated; read as US"}
    assert (a["moq_inbound_usd"], a["cash_to_first_stock_usd"]) == (42.00, 59.00)          # C5: 50 kg × 0.84 for the MOQ order; 17.00 + 42.00
    assert a["shipping"] == [{"origin": "US", "carrier": "USPS", "cost_usd": 5.20, "days_min": 3, "days_max": 7, "source": "CJ US→US quote for CJ P1, 150 g"}]
    c = offers["cj:P1"]
    assert (c["model"], c["unit_cost_usd"], c["moq"], c["moq_capital_usd"], c["suggested_retail_usd"], c["us_stock_confirmed"]) == (
        "dropship", 3.10, 1, 3.10, 12.99, False)
    receipts = {r["id"]: r for r in _product(decision, "worked")["receipts"]}
    assert receipts["channels.tiktok_us.shipping_usd"]["rule"] == "LAST_MILE_CJ_US_QUOTE" and receipts["channels.tiktok_us.inbound_usd"]["result"] == 0.42
    assert receipts["channels.tiktok_us.returns_usd"]["inputs"] == {"returns_rate": 0.193, "landed_cost_usd": 5.79}     # unit + inbound + last mile


def test_alibaba_shipping_on_the_recorded_pages_through_the_real_parser(tmp_path):
    """The parser's own records of the recorded pages: page A says "Starts at US$0.84/kg with a 50kg minimum" (0.17 kg a unit, MOQ 100
    from its first price tier, $0.88); an Exa result says "Shipping fee: $47.90 $67.90 for 10 pieces" (MOQ 10). The engine charges
    page A max(100 × 0.17 = 17 kg, 50 kg) × 0.84 = 42.00 for the MOQ order, 0.42 a unit (0.14 without the minimum), and the quote
    47.90 ÷ 10 = 4.79 a unit — each receipt naming the rule."""
    from polymath_shared.acquisition import agent_reach as AR

    terms = ["slicker brush", "dog brush", "self cleaning slicker brush"]
    page = AR.parse_report_source("alibaba", (FIXTURES / "jina_alibaba_A.out").read_text(encoding="utf-8"), kind="page", candidate_terms=terms)
    search = AR.parse_report_source("alibaba", (FIXTURES / "exa_alibaba_brush.out").read_text(encoding="utf-8"), kind="search", candidate_terms=terms)
    a = next(x for x in page["records"] if x.get("product_id") == "1600824724683")
    assert (a["shipping_per_kg_usd"], a["shipping_min_kg"], a["gross_weight_kg"], a["moq"]) == (0.84, 50.0, 0.17, 100)
    proc, raw = _run({"candidates": [{"candidate_id": "brush", "title": "Self-cleaning slicker brush"}], "host": {},
                      "parsed": {"brush": {"alibaba": page["records"] + search["records"]}}, "settings": {"as_of": "2026-11-02"}}, tmp_path, "pages")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    at = {o["offer_id"]: i for i, o in enumerate(p["offers"])}
    receipts = {r["id"]: r for r in p["receipts"]}
    i = at["alibaba:1600824724683"]
    oa = p["offers"][i]
    assert (oa["unit_cost_usd"], oa["moq"], oa["moq_capital_usd"], oa["inbound"]["cost_usd"], oa["time_to_stock_days"]) == (0.88, 100, 88.00, 0.42, 55)
    ra = receipts[f"offers[{i}].inbound.cost_usd"]
    assert ra["rule"] == "MIN_KG" and (ra["inputs"]["order_kg"], ra["inputs"]["chargeable_kg"], ra["inputs"]["moq_order_total_usd"]) == (17.0, 50.0, 42.0)
    assert "50kg minimum" in ra["inputs"]["shipping_fee_text"]
    j = at["alibaba:1601292437894"]
    rq = receipts[f"offers[{j}].inbound.cost_usd"]
    assert p["offers"][j]["inbound"]["cost_usd"] == 4.79 and rq["rule"] == "QUOTE"
    assert (rq["inputs"]["shipping_quote_usd"], rq["inputs"]["shipping_quote_qty"], rq["inputs"]["moq"]) == (47.9, 10, 10)


def _page_a():
    from polymath_shared.acquisition import agent_reach as AR

    page = AR.parse_report_source("alibaba", (FIXTURES / "jina_alibaba_A.out").read_text(encoding="utf-8"), kind="page",
                                  candidate_terms=["slicker brush", "self cleaning slicker brush"])
    return [x for x in page["records"] if x.get("product_id") == "1600824724683"]


def _recorded_cj_reference() -> dict:
    """The candidate's CJ product as B2 reports it from the recorded answers: "Pet Self Cleaning Slicker Brush" (the cheapest variant, 250 g),
    its US→US options read by B2's own `freight_options` from the recorded quote (UniUni+ 3-8 days, $7.22 the cheapest)."""
    from polymath_shared.product_search import host_data as HD

    us = HD.freight_options(json.loads((HOST_FIXTURES / "cj7_freight_us_us.json").read_text(encoding="utf-8")))
    return {"status": "OK", "products": [{"product_id": "AEF754AF-2F7F-424E-897C-2BF7DF141B30", "title": "Pet Self Cleaning Slicker Brush",
                                           "url": "https://cjdropshipping.com/product/pet-self-cleaning-slicker-brush-p-AEF754AF-2F7F-424E-897C-2BF7DF141B30.html",
                                           "sell_price_usd": 3.83, "weight_g": 250.0, "variants": [{"variant_id": "6ACD9F80-DE0B-4A16-8292-392385BF19E6",
                                                                                                   "price_usd": 3.83, "weight_g": 250.0}],
                                           "freight": {"CN": [], "US": us}, "us_stock_confirmed": False}]}


def _page_a_bundle(host: dict | None = None, settings: dict | None = None) -> dict:
    return {"candidates": [{"candidate_id": "c1", "title": "Self-cleaning slicker brush"}], "host": {"cj": {"c1": host}} if host else {},
            "parsed": {"c1": {"alibaba": _page_a(), "amazon": [_amazon("A1", 15.99), _amazon("A2", 19.99), _amazon("A3", 22.49)]}},
            "settings": {"as_of": "2026-11-02", **(settings or {})}}


def _inventory_line(product: dict, channel: str) -> dict:
    ch = product["channels"][channel]
    return next(x for x in [ch, *ch["alternatives"]] if x["offer_id"] == "alibaba:1600824724683")


def test_page_a_as_inventory_with_the_recorded_cj_us_reference(tmp_path):
    """Page A (MOQ 100 at $0.88, inbound $0.42 a unit under its 50 kg minimum, first stock in 31 + 24 = 55 days, cash $130.00 before it) shipped
    from US stock at the recorded CJ US→US prices, the last mile chosen PER CHANNEL like a dropship offer's options, with 1 business day of
    handling before the first scan (R2 #1). TikTok US no longer takes UniUni+ 3-8 days (6 + 1 = 7 > 6 business days): it takes USPS+VIP 3-7
    days $7.78 (5 + 1 = 6); no option meets Shopify's 7 days once handling counts (3-7 + 1 = 8), so Shopify takes the cheapest at WARN."""
    proc, raw = _run(_page_a_bundle(_recorded_cj_reference()), tmp_path, "ref")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    a = next(o for o in p["offers"] if o["offer_id"] == "alibaba:1600824724683")
    assert [(s["carrier"], s["cost_usd"], s["days_min"], s["days_max"]) for s in a["shipping"]][:4] == [
        ("UniUni+", 7.22, 3, 8), ("GOFO GC parcel+", 7.37, 3, 8), ("GOFO+", 7.45, 3, 8), ("USPS+VIP", 7.78, 3, 7)]
    assert {s["source"] for s in a["shipping"]} == {"CJ US→US quote for Pet Self Cleaning Slicker Brush, 250 g"} and len(a["shipping"]) == 7
    # USPS+VIP 7.78 (both TikTok accounts; cross-border stock in a US warehouse is held to the US clock; and Amazon, where 1 business day of
    # handling can be 3 calendar days: UniUni+ 8 + 3 = 11 > 10, USPS+VIP 7 + 3 = 10 ≤ 10): landed 0.88 + 0.42 + 7.78 = 9.08, returns
    # 19.3 % × 9.08 = 1.75244 -> 1.75; tiktok 19.99 - 9.08 - 1.20 - 1.75 = 7.96, amazon 19.99 - 9.08 - 3.99 - 1.75 = 5.17. UniUni+ 7.22: landed 8.52,
    # returns 1.64436 -> 1.64; shopify (WARN) 19.99 - 8.52 - 1.27 - 1.64 = 8.56, ebay 19.99 - 8.52 - 3.12 - 1.64 = 6.71
    lines = {c: _inventory_line(p, c) for c in CHANNELS}
    assert {c: (lines[c]["shipping_usd"], lines[c]["landed_cost_usd"], lines[c]["returns_usd"], lines[c]["margin_before_ads_usd"], lines[c]["margin_pct"],
                lines[c]["delivery"]["verdict"]) for c in CHANNELS} == {
        "tiktok_us": (7.78, 9.08, 1.75, 7.96, 39.8, "PASS"), "tiktok_cross_border": (7.78, 9.08, 1.75, 7.96, 39.8, "PASS"),
        "shopify": (7.22, 8.52, 1.64, 8.56, 42.8, "WARN"), "ebay": (7.22, 8.52, 1.64, 6.71, 33.6, "PASS"), "amazon_fbm": (7.78, 9.08, 1.75, 5.17, 25.9, "PASS")}
    assert ("requires holding US stock: first stock in 55 days, cash $130.00 before first stock (goods $88.00 + inbound $42.00)"
            in lines["tiktok_us"]["delivery"]["reason"])
    receipts = {r["id"]: r for r in p["receipts"]}
    shop, tiktok = receipts["channels.shopify.shipping_usd"], receipts["channels.tiktok_us.shipping_usd"]
    assert shop["rule"] == tiktok["rule"] == "LAST_MILE_CJ_US_QUOTE"
    assert (shop["inputs"]["chosen"]["carrier"], shop["inputs"]["chosen"]["cost_usd"], shop["inputs"]["chosen"]["days_max"]) == ("UniUni+", 7.22, 8)
    assert (tiktok["inputs"]["chosen"]["carrier"], tiktok["inputs"]["chosen"]["cost_usd"], tiktok["inputs"]["chosen"]["days_max"]) == ("USPS+VIP", 7.78, 7)
    assert tiktok["inputs"]["why"] == "the cheapest last-mile option whose days pass this channel's delivery rule"
    assert shop["inputs"]["why"] == "no last-mile option passes this channel's delivery rule: the cheapest overall (WARN)"
    assert [(o["carrier"], o["verdict"]) for o in tiktok["inputs"]["options"]][:4] == [("UniUni+", "FAIL"), ("GOFO GC parcel+", "FAIL"), ("GOFO+", "FAIL"),
                                                                                      ("USPS+VIP", "PASS")]
    assert shop["inputs"]["chosen"]["source"] == "CJ US→US quote for Pet Self Cleaning Slicker Brush, 250 g"
    assert "with 1 business day of handling (setting handling_business_days)" in lines["tiktok_us"]["delivery"]["reason"]


def test_page_a_as_inventory_without_a_last_mile_is_unknown(tmp_path):
    proc, raw = _run(_page_a_bundle(), tmp_path, "none")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    for c in CHANNELS:
        line = p["channels"][c]
        assert (line["offer_id"], line["inbound_usd"], line["shipping_usd"], line["margin_before_ads_usd"], line["delivery"]["verdict"]) == (
            "alibaba:1600824724683", 0.42, "UNKNOWN", "UNKNOWN", "UNKNOWN")
        assert "no last mile" in line["delivery"]["reason"]
        assert "first stock in 55 days, cash $130.00 before first stock (goods $88.00 + inbound $42.00)" in line["delivery"]["reason"]


def test_tiktok_us_passes_an_inventory_offer_with_a_short_last_mile(tmp_path):
    """The owner's own last mile (settings last_mile_usd 4.50, last_mile_days 5): 5 days from US stock ≤ 6 business days."""
    proc, raw = _run(_page_a_bundle(settings={"last_mile_usd": 4.50, "last_mile_days": 5}), tmp_path, "owner")
    assert proc.returncode == 0, proc.stderr[-1500:]
    t = json.loads(raw)["products"][0]["channels"]["tiktok_us"]
    # landed 0.88 + 0.42 + 4.50 = 5.80, returns 1.1194 -> 1.12, margin 19.99 - 5.80 - 1.20 - 1.12 = 11.87
    assert _line(t) == ("alibaba:1600824724683", 19.99, 0.88, 0.42, 4.50, 1.20, 1.12, 11.87, 59.4, 11.87)
    assert (t["delivery"]["verdict"], t["delivery"]["origin"], t["delivery"]["days_max"]) == ("PASS", "US", 5)


# ─────────────────────────────────────────────────────────── review-fix round (R2 #1, #5, #9a-d; contracts C2, C3, C5)
def test_handling_time_counts_before_the_carriers_days_on_every_order_clock(tmp_path):
    """R2 #1: TikTok counts "Delivered within 6 business days of Awaiting Shipment" — handling is inside the 6. With the default 1 day the
    recorded UniUni+ 3-8 days (6 business) is 7 > 6: FAIL; with 0 days it passes; with 3 days the first scan itself is late (3 > 2)."""
    def tiktok(handling):
        settings = {} if handling is None else {"handling_business_days": handling}
        proc, raw = _run(_page_a_bundle(_recorded_cj_reference(), settings=settings), tmp_path, f"h{handling}")
        assert proc.returncode == 0, proc.stderr[-1500:]
        line = _inventory_line(json.loads(raw)["products"][0], "tiktok_us")
        return line["shipping_usd"], line["margin_before_ads_usd"], line["delivery"]["verdict"], line["delivery"]["handling_business_days"], line["delivery"]["reason"]
    default, none, slow = tiktok(None), tiktok(0), tiktok(3)
    assert default[:4] == (7.78, 7.96, "PASS", 1) and "5 + 1 = up to 6" in default[4]                      # USPS+VIP 3-7
    assert none[:4] == (7.22, 8.63, "PASS", 0) and "6 + 0 = up to 6" in none[4]                            # UniUni+ 3-8 again
    assert slow[:4] == (7.22, 8.63, "FAIL", 3) and "first carrier scan after 3 business days > 2" in slow[4]   # nothing passes: the cheapest, FAIL


def test_ebays_free_shipping_badge_counts_handling(tmp_path):
    fast = {"status": "OK", "products": [_cj("FAST", [4.00], {"CN": [], "US": [{"carrier": "USPS", "cost_usd": 5.00, "days_min": 2, "days_max": 3}]}, stock=True)]}
    def badge(handling):
        bundle = {"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {"cj": {"c1": fast}},
                  "parsed": {"c1": {"amazon": [_amazon("A1", 15.99), _amazon("A2", 19.99), _amazon("A3", 22.49)]}},
                  "settings": {"as_of": "2026-11-02", "handling_business_days": handling}}
        proc, raw = _run(bundle, tmp_path, f"badge{handling}")
        assert proc.returncode == 0, proc.stderr[-1500:]
        return json.loads(raw)["products"][0]["channels"]["ebay"]["delivery"]["badge_eligible"]
    assert (badge(1), badge(2)) == (True, False)              # 3 + 1 = 4 ≤ 4 with handling 1 ≤ 1; handling 2 > 1 loses it


def test_cash_before_first_stock_on_the_recorded_b_retry_page(tmp_path):
    """C5 / R2 #5: the recorded page's own quote is $5,537 for the 200-piece MOQ at $11.00: goods $2,200.00 + inbound $5,537.00 = $7,737.00
    before the first unit can sell (the page names no destination: read as the US, and said so)."""
    from polymath_shared.acquisition import agent_reach as AR

    recs = AR.parse_report_source("alibaba", (FIXTURES / "jina_alibaba_B_retry.out").read_text(encoding="utf-8"), kind="page",
                                  candidate_terms=["candle warmer"])["records"]
    bundle = {"candidates": [{"candidate_id": "c1", "title": "Candle warmer lamp"}], "host": {}, "parsed": {"c1": {"alibaba": recs}},
              "settings": {"as_of": "2026-11-02", "last_mile_usd": 9.50, "last_mile_days": 5}}
    proc, raw = _run(bundle, tmp_path, "bretry")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    o = p["offers"][0]
    assert (o["moq"], o["unit_cost_usd"], o["moq_capital_usd"], o["moq_inbound_usd"], o["cash_to_first_stock_usd"]) == (200, 11.0, 2200.0, 5537.0, 7737.0)
    assert o["inbound"]["rule"] == "QUOTE" and o["inbound"]["cost_usd"] == 27.685 and o["inbound"]["destination"] == "destination not stated; read as US"
    assert o["inbound"]["cost_usd"] * o["moq"] == o["moq_inbound_usd"]                  # N4a: the per-unit figure is the total ÷ MOQ, so they agree
    assert "requires holding US stock: first stock time UNKNOWN, cash $7,737.00 before first stock (goods $2,200.00 + inbound $5,537.00)" in \
        p["channels"]["shopify"]["delivery"]["reason"]
    receipts = {r["id"]: r for r in p["receipts"]}
    assert receipts["offers[0].cash_to_first_stock_usd"]["inputs"] == {"moq_capital_usd": 2200.0, "moq_inbound_usd": 5537.0}


def test_cross_border_stock_in_a_us_warehouse_is_judged_by_the_us_clock(tmp_path):
    """R2 #9a: a cross-border seller's stock in a US warehouse is held to ≤ 2 business days to the first scan and ≤ 6 to delivery — a verdict,
    not a note: CJ's US→US 3-10 days (at most 8 business days) + 1 = 9 > 6 FAILS, though 10 + 1 = 11 calendar days is under the 15 of direct mail."""
    slow = {"status": "OK", "products": [_cj("SLOW", [4.00], {"CN": [], "US": [{"carrier": "Ground", "cost_usd": 5.00, "days_min": 3, "days_max": 10}]})]}
    bundle = {"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {"cj": {"c1": slow}},
              "parsed": {"c1": {"amazon": [_amazon("A1", 15.99), _amazon("A2", 19.99), _amazon("A3", 22.49)]}}, "settings": {"as_of": "2026-11-02"}}
    proc, raw = _run(bundle, tmp_path, "cbus")
    assert proc.returncode == 0, proc.stderr[-1500:]
    d = json.loads(raw)["products"][0]["channels"]["tiktok_cross_border"]["delivery"]
    assert d["verdict"] == "FAIL" and "stock in a US (overseas) warehouse" in d["reason"] and "8 + 1 = up to 9 > 6" in d["reason"]


def test_an_inbound_estimate_for_another_country_is_not_used(tmp_path):
    """R2 #9b: the page's shipping estimate is for the country it names ("Deliver to"): Germany is not US inbound freight (UNKNOWN, said why);
    the US is used; an unstated destination is used and the row says so."""
    base = {"kind": "listing", "title": "slicker brush", "relevant": True, "price_tiers": [{"qty_min": 100, "qty_max": None, "unit_price": 1.00}], "moq": 100,
            "shipping_quote_usd": 50.0, "shipping_quote_qty": 100, "transit_days_min": 10, "transit_days_max": 14, "lead_time_days_max": 7}
    recs = [dict(base, url=f"https://www.alibaba.com/product-detail/x_160000000009{i}.html", product_id=f"160000000009{i}", ships_to=dest)
            for i, dest in enumerate(["Germany", "United States", None])]
    proc, raw = _run({"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {}, "parsed": {"c1": {"alibaba": recs}}, "settings": {"as_of": "2026-11-02"}},
                     tmp_path, "shipsto")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    got = [(o["inbound"]["cost_usd"], o["inbound"]["days_max"], o["inbound"]["destination"], o["moq_inbound_usd"], o["time_to_stock_days"]) for o in p["offers"]]
    assert got == [("UNKNOWN", "UNKNOWN", "Germany — not the US: not used", "UNKNOWN", "UNKNOWN"),
                   (0.5, 14, "US", 50.0, 21), (0.5, 14, "destination not stated; read as US", 50.0, 21)]
    receipts = {r["id"]: r for r in p["receipts"]}
    assert receipts["offers[0].inbound.cost_usd"]["formula"] == "not used: the listing's shipping estimate is for Germany, not the US"


def test_a_cj_last_mile_stands_in_only_for_an_item_of_about_its_weight(tmp_path):
    """R2 #9c: CJ's US→US quote was for a 250 g brush. A 300 g offer (20 % heavier) and an offer of unknown weight may use it; a 500 g one may not —
    its last mile is UNKNOWN, with the reason — unless the owner set their own last mile."""
    def lm(weight, settings=None):
        rec = {"kind": "listing", "url": "https://www.alibaba.com/product-detail/x_1600000000081.html", "product_id": "1600000000081", "title": "slicker brush",
               "relevant": True, "price_tiers": [{"qty_min": 100, "qty_max": None, "unit_price": 1.00}], "moq": 100, **({"gross_weight_kg": weight} if weight else {})}
        bundle = {"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {"cj": {"c1": _recorded_cj_reference()}}, "parsed": {"c1": {"alibaba": [rec]}},
                  "settings": {"as_of": "2026-11-02", **(settings or {})}}
        proc, raw = _run(bundle, tmp_path, f"w{weight}")
        assert proc.returncode == 0, proc.stderr[-1500:]
        o = next(x for x in json.loads(raw)["products"][0]["offers"] if x["model"] == "inventory")
        return len(o["shipping"]), o.get("last_mile_note")
    assert lm(0.3) == (7, None) and lm(None) == (7, None)
    n, why = lm(0.5)
    assert n == 0 and why.startswith("the offer weighs 500 g a unit, more than 25 % above the weight of every CJ US→US quote (250 g)")
    assert lm(0.5, {"last_mile_usd": 9.0, "last_mile_days": 4}) == (1, None)                # the owner's own last mile stands in


def test_a_quote_in_business_days_is_read_as_business_days(tmp_path):
    """C2 / R2 #9d: CJ's "2-6 business days" is 6 business days (+ 1 handling = 7 > 6: TikTok US FAILS) and up to 10 calendar days for Shopify;
    the same quote with no unit is read as calendar days (6 days hold at most 5 business + 1 = 6: TikTok US PASSES). Shopify WARNS either way
    once handling's worst week counts (10 + 3, 6 + 3 > 7)."""
    def verdicts(unit):
        opt = {"carrier": "USPS", "cost_usd": 5.00, "days_min": 2, "days_max": 6, **({"days_unit": unit} if unit else {})}
        host = {"status": "OK", "products": [_cj("U", [4.00], {"CN": [], "US": [opt]}, stock=True)]}
        bundle = {"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {"cj": {"c1": host}},
                  "parsed": {"c1": {"amazon": [_amazon("A1", 15.99), _amazon("A2", 19.99), _amazon("A3", 22.49)]}}, "settings": {"as_of": "2026-11-02"}}
        proc, raw = _run(bundle, tmp_path, f"unit{unit}")
        assert proc.returncode == 0, proc.stderr[-1500:]
        ch = json.loads(raw)["products"][0]["channels"]
        return ch["tiktok_us"]["delivery"]["verdict"], ch["shopify"]["delivery"]["verdict"], ch["tiktok_us"]["delivery"]["business_days_max"]
    assert verdicts("business") == ("FAIL", "WARN", 6)
    assert verdicts(None) == verdicts("calendar") == ("PASS", "WARN", 5)


def test_a_tier_priced_as_a_range_is_costed_at_its_high_end(tmp_path):
    """C3: the parser's tier `unit_price` is the HIGH end of a range and `unit_price_low` the low end: $1.20 - 1.50 at 100-499 pieces costs $1.50
    a unit, $150.00 for the MOQ — and the receipt says it took the high end."""
    rec = {"kind": "listing", "url": "https://www.alibaba.com/product-detail/x_1600000000001.html", "product_id": "1600000000001", "title": "slicker brush",
           "relevant": True, "moq": 100, "price_tiers": [{"qty_min": 100, "qty_max": 499, "unit_price": 1.50, "unit_price_low": 1.20},
                                                         {"qty_min": 500, "qty_max": None, "unit_price": 1.40, "unit_price_low": 1.10}]}
    proc, raw = _run({"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {}, "parsed": {"c1": {"alibaba": [rec]}}, "settings": {"as_of": "2026-11-02"}},
                     tmp_path, "c3")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    assert (p["offers"][0]["unit_cost_usd"], p["offers"][0]["moq_capital_usd"]) == (1.5, 150.0)
    assert "the tier is priced as a range: its high end" in {r["id"]: r for r in p["receipts"]}["offers[0].unit_cost_usd"]["formula"]


def test_handling_on_a_calendar_rule_counts_its_worst_week(tmp_path):
    """N2: on a calendar-day rule the 1 business day of handling counts as up to 3 calendar days (an order on a Friday is scanned on Monday).
    Cross-border: China 7-14 days is 14 + 3 = 17 > 15 (FAIL), China 5-11 is 14 ≤ 15 (PASS, taken). Amazon: 8 days + 3 = 11 > 10 (WARN),
    7 + 3 = 10 (PASS, taken though dearer)."""
    host = {"status": "OK", "products": [_cj("N2", [4.00], {"CN": [{"carrier": "Pure Electricity", "cost_usd": 3.00, "days_min": 7, "days_max": 14},
                                                                   {"carrier": "Ordinary", "cost_usd": 3.50, "days_min": 5, "days_max": 11}],
                                                            "US": [{"carrier": "Eight", "cost_usd": 7.22, "days_min": 3, "days_max": 8},
                                                                   {"carrier": "Seven", "cost_usd": 7.78, "days_min": 3, "days_max": 7}]}, stock=True)]}
    bundle = {"candidates": [{"candidate_id": "c1", "title": "x"}], "host": {"cj": {"c1": host}}, "settings": {"as_of": "2026-11-02"},
              "parsed": {"c1": {"amazon": [_amazon("A1", 15.99), _amazon("A2", 19.99), _amazon("A3", 22.49)]}}}
    proc, raw = _run(bundle, tmp_path, "n2")
    assert proc.returncode == 0, proc.stderr[-1500:]
    p = json.loads(raw)["products"][0]
    receipts = {r["id"]: r for r in p["receipts"]}
    cb, amz = p["channels"]["tiktok_cross_border"], p["channels"]["amazon_fbm"]
    assert (cb["delivery"]["carrier"], cb["delivery"]["verdict"]) == ("Ordinary", "PASS")
    assert {o["carrier"]: o["verdict"] for o in receipts["channels.tiktok_cross_border.shipping_usd"]["inputs"]["options"]}["Pure Electricity"] == "FAIL"
    assert (amz["delivery"]["carrier"], amz["delivery"]["verdict"]) == ("Seven", "PASS")
    assert {o["carrier"]: o["verdict"] for o in receipts["channels.amazon_fbm.shipping_usd"]["inputs"]["options"]}["Eight"] == "WARN"
    assert "which can take up to 3 calendar days (an order on a Friday is scanned on Monday)" in amz["delivery"]["reason"]
    assert "in transit (first carrier scan) after up to 3 calendar days ≤ 3" in cb["delivery"]["reason"]


def test_the_assumptions_say_when_the_owners_last_mile_stands_in(decision):
    """N4b / N4c: the owner's own last mile stands in when there is no CJ US→US quote OR every quote's product is too light — the tolerance read
    from the policy (25 %), never written into the words."""
    a = decision["assumptions"]
    assert a["last_mile"]["weight_tolerance"] == 0.25
    assert "or when the offer is more than 25 % heavier than every CJ quote's product" in a["last_mile"]["text"]
    assert "at most 25 % above that product's" in a["alibaba"]


def test_missing_comps_make_every_margin_unknown(decision):
    p = _product(decision, "no_comps")
    assert p["market"]["reference_price_usd"] == "UNKNOWN" and p["market"]["basis"] == "UNKNOWN"
    assert p["sources_status"]["ebay_api"]["status"] == "EBAY_NOT_CONFIGURED"
    for c in CHANNELS:
        line = p["channels"][c]
        assert _line(line, ("sell_price_usd", "fees_usd", "margin_before_ads_usd", "margin_pct", "break_even_ad_cost_usd")) == ("UNKNOWN",) * 5
        assert _line(line, ("unit_cost_usd", "landed_cost_usd", "returns_usd")) == (4.00, 9.00, 1.74)   # 19.3 % × 9.00 = 1.737 -> 1.74
    assert p["sensitivity"]["tiktok_8pct"]["channels"]["tiktok_us"]["margin_before_ads_usd"] == "UNKNOWN"
    rc = next(r for r in p["receipts"] if r["id"] == "market.reference_price_usd")
    assert rc["result"] == "UNKNOWN" and rc["missing"]


def test_tiktok_8pct_is_a_sensitivity(decision):
    s = _product(decision, "worked")["sensitivity"]["tiktok_8pct"]
    assert s["rate_pct"] == 8.0 and s["status"] == "UNCONFIRMED"
    # 8 % × 19.99 = 1.5992 -> 1.60 on the best (inventory) line: 19.99 - 5.79 - 1.60 - 1.12 = 11.48 on both TikTok accounts
    assert _line(s["channels"]["tiktok_us"], ("offer_id", "fees_usd", "margin_before_ads_usd", "margin_pct", "break_even_ad_cost_usd")) == (
        "alibaba:1601132652199", 1.60, 11.48, 57.4, 11.48)
    assert _line(s["channels"]["tiktok_cross_border"], ("fees_usd", "margin_before_ads_usd", "margin_pct")) == (1.60, 11.48, 57.4)


def test_reddit_is_comments_with_dates_and_a_counts_only_summary(decision):
    r = _product(decision, "worked")["demand"]["reddit"]
    assert r["summary"] == "2 threads in 2 subreddits, 4 comments read, newest 2026-10-12; the most-upvoted comment has 81 points."
    assert (r["threads"], r["subreddits"], r["newest"], r["comments_total"]) == (2, ["r/CatAdvice", "r/dogs"], "2026-10-12", 4)
    # by points, then the newer date first; a date the page shows only as text is no date; text ≤ 300 characters
    assert [(c["points"], c["date"], c["subreddit"]) for c in r["comments"]] == [(81, "2026-10-05", "r/dogs"), (81, "2026-10-01", "r/CatAdvice"),
                                                                                (12, "2026-10-12", "r/CatAdvice"), (3, None, "r/dogs")]
    assert len(r["comments"][3]["text"]) == 300 and all(set(c) == {"date", "points", "subreddit", "text", "url"} for c in r["comments"])
    a = _product(decision, "worked")["demand"]["amazon"]
    assert (a["bsr_best"], a["bsr_best_category"], a["bought_past_month_max"], a["ratings_count_max"]) == (812, "Pet Supplies", 2000, 8765)


def _leaves(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if not (path == "" and k == "receipts"):
                yield from _leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, node


def test_every_number_has_a_receipt(decision):
    """Every number (and every UNKNOWN in place of one) has exactly one receipt whose id is its path and whose result is the value;
    every receipt points at a value that exists."""
    for p in decision["products"]:
        leaves = dict(_leaves(p))
        ids = [r["id"] for r in p["receipts"]]
        assert len(ids) == len(set(ids)), "duplicate receipt ids"
        by_id = {r["id"]: r for r in p["receipts"]}
        assert all({"id", "formula", "inputs", "result"} <= set(r) for r in p["receipts"])
        numbers = {k: v for k, v in leaves.items() if (isinstance(v, (int, float)) and not isinstance(v, bool))
                   or (v == "UNKNOWN" and k.rsplit(".", 1)[-1] not in ("verdict", "basis", "status", "origin", "rule"))}
        assert numbers, p["candidate_id"]
        assert [k for k, v in numbers.items() if k not in by_id or by_id[k]["result"] != v] == [], p["candidate_id"]
        assert [i for i in by_id if i not in leaves or leaves[i] != by_id[i]["result"]] == [], p["candidate_id"]


def _reversed(node):
    if isinstance(node, dict):
        return {k: _reversed(node[k]) for k in reversed(list(node))}
    return [_reversed(x) for x in node] if isinstance(node, list) else node


def test_same_input_same_bytes(tmp_path):
    first, a = _run(BUNDLE, tmp_path, "a")
    second, b = _run(BUNDLE, tmp_path, "b")
    third, c = _run(_reversed(BUNDLE), tmp_path, "c")
    assert first.returncode == second.returncode == third.returncode == 0
    assert a == b == c and a


def test_compute_touches_no_file_socket_or_process(tmp_path):
    """Pure: once the engine is imported, computing opens no file, resolves no host, starts no process (audit hooks see everything)."""
    bpath = tmp_path / "bundle.json"
    bpath.write_text(json.dumps(BUNDLE), encoding="utf-8")
    code = ("import json, sys; sys.path.insert(0, 'python'); import graph, unit_economics as U, executors\n"
            "policy = graph.load_policies(); bundle = json.load(open(sys.argv[1])); seen = []\n"
            "watch = ('open', 'socket.', 'subprocess.', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn', 'urllib.', 'http.')\n"
            "sys.addaudithook(lambda ev, args: seen.append(ev) if ev.startswith(watch) else None)\n"
            "decision = U.compute(bundle, policy); print(json.dumps({'events': seen, 'products': len(decision['products'])}))")
    proc = subprocess.run([sys.executable, "-c", code, str(bpath)], cwd=ENGINE, capture_output=True, text=True, timeout=120, check=False,
                          env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "OPPORTUNITY_RESEARCH_DB": str(tmp_path / "x.sqlite3")})
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == {"events": [], "products": 3}
    src = MODULE.read_text(encoding="utf-8")
    assert not [ln for ln in src.splitlines() if ln.lstrip().startswith(("import polymath_shared", "from polymath_shared"))]


def test_owner_settings_and_refusals(tmp_path):
    proc, raw = _run({**BUNDLE, "settings": {"as_of": "2026-11-02", "shopify_monthly_orders": 50, "returns_rate": 0.10, "channels": ["shopify"]}}, tmp_path)
    assert proc.returncode == 0, proc.stderr[-800:]
    d = json.loads(raw)
    shop = _product(d, "worked")["channels"]["shopify"]
    # 2.9 % × 19.99 + 0.30 + 39 / 50 = 1.65971 -> 1.66; CJ via China (no option meets 7 days once handling counts: the cheapest) at 10 % returns:
    # 0.10 × 7.20 = 0.72, margin 19.99 - 7.20 - 1.66 - 0.72 = 10.41
    assert d["channels"] == ["shopify"] and shop["fees_usd"] == 1.66 and _product(d, "worked")["sensitivity"] == {}
    assert _line(shop["alternatives"][0], ("offer_id", "returns_usd", "margin_before_ads_usd")) == ("cj:P1", 0.72, 10.41)
    for bad in ({"returns_rate": 1.5}, {"shopify_monthly_orders": 0}, {"ship_to": "GB"}, {"channels": ["myspace"]}):
        proc, raw = _run({**BUNDLE, "settings": bad}, tmp_path, "bad")
        assert proc.returncode == 2 and json.loads(proc.stderr.strip().splitlines()[-1])["error"] == "DECISION_INPUT_INVALID", bad


def test_policy_holds_plan_section_2_with_dated_sources(decision):
    pol = yaml.safe_load((ENGINE / "graph" / "policies.yaml").read_text(encoding="utf-8"))
    sc, rs = pol["sales_channels"], pol["report_settings"]
    ch = sc["channels"]
    assert sc["order"] == CHANNELS
    assert [ch[c]["fee"]["rate_pct"] for c in CHANNELS] == [6.0, 6.0, 2.9, 13.6, 15.0]
    assert (ch["shopify"]["fee"]["fixed_usd"], ch["shopify"]["fee"]["plan_monthly_usd"]) == (0.30, 39.00)
    assert ch["ebay"]["fee"]["per_order"] == [{"max_order_usd": 10.00, "fee_usd": 0.30}, {"fee_usd": 0.40}]
    assert (ch["amazon_fbm"]["fee"]["min_referral_usd"], ch["amazon_fbm"]["fee"]["per_item_usd"]) == (0.30, 0.99)
    assert (ch["tiktok_us"]["sensitivity"]["rate_pct"], ch["tiktok_us"]["sensitivity"]["status"]) == (8.0, "UNCONFIRMED")
    d = {c: ch[c]["delivery"] for c in CHANNELS}
    assert (d["tiktok_us"]["origins"], d["tiktok_us"]["max_handling_business_days"], d["tiktok_us"]["max_delivery_business_days"]) == (["US"], 2, 6)
    assert (d["tiktok_cross_border"]["max_in_transit_calendar_days"], d["tiktok_cross_border"]["max_delivery_days"], d["tiktok_cross_border"]["over"]) == (3, 15, "FAIL")
    assert (d["shopify"]["max_delivery_days"], d["shopify"]["over"], d["shopify"]["ftc_ship_within_days"]) == (7, "WARN", 30)
    assert (d["ebay"]["badge_max_handling_business_days"], d["ebay"]["badge_max_delivery_business_days"]) == (1, 4)
    assert (d["amazon_fbm"]["max_delivery_days"], d["amazon_fbm"]["over"], d["amazon_fbm"]["prime_fail_origins"]) == (10, "WARN", ["CN"])
    assert rs["defaults"] == {"shopify_monthly_orders": 100, "returns_rate": 0.193, "ship_to": "US", "last_mile_usd": None, "last_mile_days": None,
                              "handling_business_days": 1}
    assert rs["last_mile_weight_tolerance"] == 0.25
    assert sc["sources"][rs["returns_rate_source"]]["published"] == "2025-10-15"
    cited = {s for c in CHANNELS for s in ch[c]["sources"] + ch[c].get("sensitivity", {}).get("sources", [])}
    assert all(sc["sources"][s]["url"].startswith("https://") and sc["sources"][s]["read"] == "2026-11-02" for s in cited)
    # every report prints each rule with its URL and date
    a = decision["assumptions"]
    assert a["returns"]["rate"] == 0.193 and a["returns"]["source"]["url"].startswith("https://nrf.com/")
    assert all(a["channels"][c]["fee"]["text"] and a["channels"][c]["delivery"]["text"] and a["channels"][c]["sources"]
               and all(s["url"] and s["read"] for s in a["channels"][c]["sources"]) for c in CHANNELS)


# ───────────────────────────────────────── live run 2026-11-02 (rpt_164ed807ad94e63ef002458e): CJ search prices and the costed variant
LIVE_CJ = json.loads((ROOT / "tests" / "fixtures" / "product_report_render" / "cj_live_pet_fountain.json").read_text(encoding="utf-8"))
UNCHECKED = ("cj:1366573785234411520", "cj:2501260812541627900")          # never detail-fetched: $4.39 and $1.74 are CJ's search "from" prices


def _fountain(products: list, amazon: list | None = None) -> dict:
    """The live fountain candidate: its recorded CJ products, an Amazon market at $19.99 so that margins are known."""
    return {"candidates": [{"candidate_id": "c1", "title": "Pet water fountain", "search_terms": ["pet water fountain"]}],
            "host": {"cj": {"c1": {"status": "OK", "products": products}}, "ebay": {}},
            "parsed": {"c1": {"amazon": amazon if amazon is not None else
                              [_amazon(a, p, title=f"Pet water fountain {a}") for a, p in (("B1F", 17.99), ("B2F", 19.99), ("B3F", 24.99))]}},
            "settings": {"as_of": "2026-11-02"}}


def _lines(product: dict) -> list[dict]:
    return [line for ch in product["channels"].values() for line in [ch, *ch["alternatives"]]]


def _decide(bundle: dict, tmp_path: pathlib.Path, name: str) -> dict:
    proc, raw = _run(bundle, tmp_path, name)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(raw)


def test_a_cj_product_known_only_by_its_search_price_is_shown_never_costed(tmp_path):
    """Live: two CJ products were never detail-fetched (detail_status NOT_FETCHED, price_basis search_from_price) and the page read
    "Dropship $4.39" / "Dropship $1.74" — CJ's search "from" price, its lowest variant, often a part. The engine leaves their unit cost
    UNKNOWN, hands the search price beside it (with its receipt) and keeps them out of every margin line: the channels are exactly
    those of the read product alone."""
    d = _decide(_fountain(LIVE_CJ["products"]), tmp_path, "live")
    p = d["products"][0]
    offers = {o["offer_id"]: o for o in p["offers"]}
    for oid, price, listed in ((UNCHECKED[0], 4.39, "US$4.39-32.21"), (UNCHECKED[1], 1.74, "US$1.74-3.42")):
        o = offers[oid]
        assert (o["unit_cost_usd"], o["from_price_usd"], o["price_basis"], o["detail_status"], o["moq_capital_usd"]) == (
            "UNKNOWN", price, "search_from_price", "NOT_FETCHED", "UNKNOWN"), oid
        assert o["not_costed"].startswith("not in the margin lines: CJ's details for this product") and "variant_note" not in o
        i = p["offers"].index(o)
        unit = next(r for r in p["receipts"] if r["id"] == f"offers[{i}].unit_cost_usd")
        assert unit["result"] == "UNKNOWN" and unit["missing"] == ["a checked unit cost (CJ's product details: its variants)"]
        assert unit["formula"].startswith("not known: CJ's details for this product were not read") and unit["inputs"]["from_price_usd"] == price
        assert next(r for r in p["receipts"] if r["id"] == f"offers[{i}].from_price_usd")["inputs"]["price_as_listed"] == listed
    read = offers["cj:1651788214971146240"]
    assert read["unit_cost_usd"] == 2.94 and "from_price_usd" not in read and "not_costed" not in read   # read in full: costed (no rule yet)
    assert not [line for line in _lines(p) if line["offer_id"] in UNCHECKED]                                # no margin line carries them
    alone = _decide(_fountain(LIVE_CJ["products"][:1]), tmp_path, "alone")
    assert p["channels"] == alone["products"][0]["channels"]                                               # the lines are the read product's
    assert "has no margin line" in d["assumptions"]["cj"] and "search \"from\" price" in d["assumptions"]["cj"]
    leaves = dict(_leaves(p))
    assert {r["id"]: r["result"] for r in p["receipts"] if r["id"].endswith("from_price_usd")} == {
        k: v for k, v in leaves.items() if k.endswith("from_price_usd")} and len([k for k in leaves if k.endswith("from_price_usd")]) == 2


def test_when_every_offer_is_known_only_by_its_search_price_no_channel_has_a_margin(tmp_path):
    p = _decide(_fountain(LIVE_CJ["products"][1:]), tmp_path, "unchecked")["products"][0]
    assert [o["unit_cost_usd"] for o in p["offers"]] == ["UNKNOWN", "UNKNOWN"]
    for cid, ch in p["channels"].items():
        assert (ch["offer_id"], ch["unit_cost_usd"], ch["margin_before_ads_usd"], ch["delivery"]["verdict"], ch["alternatives"]) == (
            None, "UNKNOWN", "UNKNOWN", "UNKNOWN", []), cid
        assert ch["delivery"]["reason"] == ("UNKNOWN: no offer with a known unit cost — CJ's details were not read (a search \"from\" price is "
                                            "not a unit cost): cannot check the delivery rule."), cid


B2_RULE = {"rule": "the costed variant is the cheapest left after dropping parts and accessories, and light variants when the weights spread",
           "variants": 30, "kept": 24, "dropped": 6, "chosen_variant_id": "1651788215109558272"}


def _with_rule(product: dict) -> dict:
    """The live read product as the host's variant rule (B2, host_data `choose_variant`) hands it: `variants` = the kept ones, the six
    lighter or part variants in `variants_dropped` with why, `variant_rule` the rule as applied, the costed variant's id, price and weight."""
    top = json.loads(json.dumps(product))
    light = [v for v in top["variants"] if v["weight_g"] < 300]
    assert len(light) == 6 and {v["price_usd"] for v in light} == {2.94, 5.38}
    top["variants"] = [v for v in top["variants"] if v["weight_g"] >= 300]
    assert (len(top["variants"]), len(top["variants"]) + len(light)) == (B2_RULE["kept"], B2_RULE["variants"])
    top["variants_dropped"] = [{"variant_id": v["variant_id"], "price_usd": v["price_usd"], "weight_g": v["weight_g"],
                                "why": "ACCESSORY_NAME" if "Filter" in v["options"] else "LIGHT_WEIGHT"} for v in light]
    top.update(variant_rule=dict(B2_RULE), cheapest_variant_id=B2_RULE["chosen_variant_id"], sell_price_usd=10.22, weight_g=770.0)
    return top


def test_the_offer_is_costed_at_the_variant_the_hosts_rule_names_and_says_so_in_one_line(tmp_path):
    """Once the host chooses the costed variant (B2: `variant_rule`, `variants_dropped`), the engine costs THAT variant — $10.22 / 770 g, not
    the $2.94 filter set — and the offer says so in one line; its unit-cost receipt carries the rule as applied."""
    top = _with_rule(LIVE_CJ["products"][0])
    p = _decide(_fountain([top, *LIVE_CJ["products"][1:]]), tmp_path, "rule")["products"][0]
    o = p["offers"][0]
    assert (o["offer_id"], o["unit_cost_usd"], o["variant_note"]) == (
        "cj:1651788214971146240", 10.22, "costed variant: $10.22 / 770 g; 6 lighter or part variants left out")
    unit = next(r for r in p["receipts"] if r["id"] == "offers[0].unit_cost_usd")
    assert unit["formula"] == "the variant the host's variant rule costs: " + B2_RULE["rule"]
    assert (unit["inputs"]["variant_id"], unit["inputs"]["variant_weight_g"], unit["inputs"]["variants_dropped"], unit["inputs"]["variant_rule"]) == (
        "1651788215109558272", 770.0, 6, B2_RULE)
    assert all(line["unit_cost_usd"] == 10.22 for line in _lines(p))                     # every margin line costs the named variant
    # a dropped variant still listed among the variants is never costed, and with no variant named the cheapest variant kept is
    kept_cheap = dict(top, variants=[*top["variants"], {"variant_id": "1651788215663206400", "price_usd": 2.94, "weight_g": 120.0}],
                      variant_rule={k: v for k, v in B2_RULE.items() if k != "chosen_variant_id"}, cheapest_variant_id=None)
    q = _decide(_fountain([kept_cheap]), tmp_path, "unnamed")["products"][0]
    assert q["offers"][0]["unit_cost_usd"] == 10.22 and q["offers"][0]["variant_note"].startswith("costed variant: $10.22 / 770 g;")
    # without a rule (the recorded data, before B2) nothing changes: the cheapest variant, no note
    r = _decide(_fountain(LIVE_CJ["products"][:1]), tmp_path, "norule")["products"][0]
    assert r["offers"][0]["unit_cost_usd"] == 2.94 and "variant_note" not in r["offers"][0]


def test_a_product_whose_every_variant_the_rule_drops_is_never_costed(tmp_path):
    """B2: when the rule drops every variant the host says so (detail_status NO_COSTED_VARIANT) and carries no price; the engine never
    costs it and keeps it out of the margin lines, saying why."""
    top = dict(_with_rule(LIVE_CJ["products"][0]), variants=[], detail_status="NO_COSTED_VARIANT", cheapest_variant_id=None,
               sell_price_usd=None, price_basis=None, weight_g=None, variant_rule=dict(B2_RULE, kept=0, dropped=30, chosen_variant_id=None))
    p = _decide(_fountain([top]), tmp_path, "nocost")["products"][0]
    o = p["offers"][0]
    assert (o["unit_cost_usd"], o["detail_status"], o["not_costed"]) == (
        "UNKNOWN", "NO_COSTED_VARIANT", "not in the margin lines: the host's variant rule left no variant to cost (30 lighter or part variants left out)")
    assert "from_price_usd" not in o and not [line for line in _lines(p) if line["offer_id"]]
    assert p["channels"]["shopify"]["delivery"]["reason"].startswith("UNKNOWN: no offer with a known unit cost — the host's variant rule left no "
                                                                     "variant to cost")
    # a rule whose every priced variant is among those it dropped (the status not set) is read the same way: never a dropped variant's price
    rule = _with_rule(LIVE_CJ["products"][0])
    every = dict(rule, variants=rule["variants_dropped"], cheapest_variant_id=None)
    q = _decide(_fountain([every]), tmp_path, "alldropped")["products"][0]
    assert q["offers"][0]["unit_cost_usd"] == "UNKNOWN" and q["offers"][0]["not_costed"].startswith("not in the margin lines: the host's variant rule")


def test_the_engine_costs_the_variant_b2s_own_rule_chose_on_the_recorded_live_variants(tmp_path):
    """The engine and the host agree: B2's `choose_variant` run on the recorded live variants, the product shaped the way `_apply_details`
    shapes it, and the engine costs exactly the variant it chose, counting what it dropped."""
    from polymath_shared.product_search import host_data
    if not hasattr(host_data, "choose_variant"):
        pytest.skip("B2's variant rule (host_data.choose_variant) is not in this checkout")
    top = json.loads(json.dumps(LIVE_CJ["products"][0]))
    chosen, kept, dropped, rule = host_data.choose_variant([dict(v, name=None) for v in top["variants"]], title=top["title"], term="pet water fountain")
    assert chosen is not None and chosen["price_usd"] > 2.94 and dropped
    top.update(variants=[{k: v.get(k) for k in host_data.VARIANT_FIELDS} for v in kept], variants_dropped=dropped, variant_rule=rule,
               cheapest_variant_id=chosen["variant_id"], sell_price_usd=chosen["price_usd"], weight_g=chosen["weight_g"])
    o = _decide(_fountain([top]), tmp_path, "b2")["products"][0]["offers"][0]
    w = int(chosen["weight_g"]) if float(chosen["weight_g"]).is_integer() else chosen["weight_g"]
    assert o["unit_cost_usd"] == chosen["price_usd"] and o["variant_note"] == (
        f"costed variant: ${chosen['price_usd']:,.2f} / {w} g; {rule['dropped']} lighter or part variant{'' if rule['dropped'] == 1 else 's'} left out")


def test_every_number_has_a_receipt_with_search_prices_and_the_costed_variant(tmp_path):
    """The receipt invariant (test_every_number_has_a_receipt) on the live fountain: search prices beside an UNKNOWN unit cost, the costed
    variant, and a product the rule left with no variant."""
    top = _with_rule(LIVE_CJ["products"][0])
    none = dict(top, variants=[], detail_status="NO_COSTED_VARIANT", cheapest_variant_id=None, sell_price_usd=None, price_basis=None,
                weight_g=None, product_id="1651788214971146999")
    for name, products in (("live", LIVE_CJ["products"]), ("rule", [top, *LIVE_CJ["products"][1:], none])):
        test_every_number_has_a_receipt(_decide(_fountain(products), tmp_path, f"receipts-{name}"))
