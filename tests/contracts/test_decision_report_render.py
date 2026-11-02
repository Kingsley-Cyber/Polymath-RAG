"""PRODUCT-DECISION-REPORT-V1 §4.5 (B4a) — the decision report's renderer.

`report.build_model_from_bundle(decision)` turns the decision model (§4.4: `unit_economics.compute`'s answer) into the ReportModel and
`report.render(model, "DECISION")` draws it: a summary row per product, then per product its links, demand (the Reddit summary and at
most five dated comments, Amazon's rank / bought / ratings), supply (offers, shipping options, the US-stock caution), market (Amazon /
eBay n, median, min, max, the reference price and the comparables), the margin per channel — dropship or inventory, every row adding up
(sell − unit − inbound − shipping / last mile − fees − returns = margin), an inventory line's US-stock requirement beside its chip —
with the TikTok 8 % what-if, the agent's
verdict (labelled as the agent's), the receipts, and the assumptions with their sources. A missing number reads UNKNOWN. http(s) links
are real anchors; every other scheme stays text, before and after the server's sanitizer. `dossier.render_decision(bundle)` runs it all
in ONE engine process. A governed dossier carries the same section, computed from the run's TrailSignal-admitted supplier leads and
product-reality prices.

Fixtures (tests/fixtures/product_report_render): `bundle_sample.json` is a HAND-WRITTEN bundle in the §4.1 / §4.3 record shapes (every
product, listing, comment and URL invented; hostile text and javascript: / data: URLs on purpose); `decision_sample.json` is
`unit_economics.compute` of that bundle, frozen, with two extra Reddit comments appended to the first product (the engine hands over
five; seven test the renderer's own cap). The engine always runs OUT OF PROCESS (its flat module names never enter this interpreter).
No database, no network, no model."""
from __future__ import annotations

import html
import json
from decimal import ROUND_HALF_UP, Decimal
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "adapters" / "ecommerce"
FIXTURES = ROOT / "tests" / "fixtures" / "product_report_render"
for _p in (ROOT / "shared", ROOT / "workers", ROOT / "tests" / "determinism"):
    sys.path.insert(0, str(_p))

import pytest  # noqa: E402
from polymath_shared.adapter import dossier  # noqa: E402

DECISION = json.loads((FIXTURES / "decision_sample.json").read_text(encoding="utf-8"))
BUNDLE = json.loads((FIXTURES / "bundle_sample.json").read_text(encoding="utf-8"))
VERDICTS = BUNDLE["verdicts"]
META = {"report_id": BUNDLE["report_id"], "title": BUNDLE["title"], "built_at": "2026-11-02"}
ANCHOR = re.compile(r'<a href="([^"]*)" rel="noopener noreferrer" target="_blank">')
HAS_COMPUTE = (ENGINE / "python" / "unit_economics.py").is_file()


def _env(tmp_path: pathlib.Path) -> dict:
    return {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "OPPORTUNITY_RESEARCH_DB": str(tmp_path / "loop.sqlite3")}


def _engine(code: str, payload, tmp_path: pathlib.Path, *, engine: pathlib.Path = ENGINE):
    """Run `code` in the engine's own directory, out of process: `payload` is json.load(open(sys.argv[1])); the code prints JSON."""
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload, ensure_ascii=False))
    proc = subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, 'python'); import report; " + code, str(path)],
                          cwd=engine, env=_env(tmp_path), capture_output=True, text=True, check=False, timeout=180)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout)


def _decision_page(tmp_path, decision=DECISION, *, verdicts=VERDICTS, meta=META) -> tuple[dict, str]:
    """(the ReportModel, the DECISION page) drawn by the engine; the page as the server sends it: sanitized, in a document."""
    out = _engine("p = json.load(open(sys.argv[1])); m = report.build_model_from_bundle(p['decision'], verdicts=p['verdicts'], meta=p['meta']); "
                  "print(json.dumps({'model': m, 'html': report.render(m, 'DECISION')}))",
                  {"decision": decision, "verdicts": verdicts, "meta": meta}, tmp_path)
    return out["model"], dossier.document(dossier.sanitize(out["html"]), "Decision report")


def _section(page: str, start: str, end: str | None) -> str:
    i = page.index(start)
    return page[i: page.index(end, i) if end else len(page)]


def _product(page: str, n: int) -> str:
    """Product `n`'s section, from its own heading to the next one (never the summary row that repeats its title)."""
    start = page.index(f'<h2 class="ptitle">{n}. ')
    nxt = page.find(f'<h2 class="ptitle">{n + 1}. ', start)
    return page[start: nxt if nxt > 0 else page.index("Assumptions and Sources", start)]


def _row(table: str, first_cell: str) -> str:
    return _section(table, first_cell, "</tr>")


def _cells(row: str) -> list[str]:
    return re.findall(r'<td class="n">(.*?)</td>', row)


def _urls(node) -> list[str]:
    if isinstance(node, dict):
        return [u for v in node.values() for u in _urls(v)]
    if isinstance(node, list):
        return [u for v in node for u in _urls(v)]
    return [node] if isinstance(node, str) and node.startswith(("https://", "http://")) else []


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    return _decision_page(tmp_path_factory.mktemp("decision"))


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(dossier.__file__).resolve().is_relative_to(ROOT), dossier.__file__
    assert dossier.DECISION_RENDERER == ENGINE / "python" / "report.py"


# ─────────────────────────────────────────────────────────── the page: every section, in order
def test_the_decision_page_has_every_section_in_order(sample):
    model, page = sample
    assert page.startswith("<!doctype html>") and '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
    assert "Product Decision Report · quick report — rows unadmitted" in page and "Pet grooming and walking — decision report" in page
    assert "as of 2026-11-02 · ship to US · 3 products" in page
    order = ["Decision Summary", '<h2 class="ptitle">1. Self-cleaning slicker brush', '<h2 class="ptitle">2. Collapsible silicone',
             '<h2 class="ptitle">3. Reflective no-pull dog harness', "Assumptions and Sources", "<footer>"]
    at = [page.index(x) for x in order]
    assert at == sorted(at), order
    inner = ["Links", "Demand", "Supply", "Shipping legs", "Market", "Amazon comparables", "eBay comparables", "Margin per channel",
             "The other offers on each channel", "What if TikTok Shop charges 8 %", "the agent's verdict — not computed by Polymath",
             f"How these numbers were computed — {len(DECISION['products'][0]['receipts'])} receipt(s)"]
    p1 = _product(page, 1)
    at = [p1.index(x) for x in inner]
    assert at == sorted(at), [x for x in inner if x not in p1]
    assert [p["candidate_id"] for p in model["decision"]["products"]] == ["cand_slicker", "cand_bowl", "cand_harness"]   # the model's order


def test_the_summary_names_the_best_channel_its_supply_model_margin_and_every_delivery_verdict(sample):
    model, page = sample
    rows = _section(page, "Decision Summary", "</tbody>").split("<tr>")[2:]
    assert len(rows) == 3
    # B3 review fixes R2 #1 and N2: handling counts on every order clock — on a calendar rule its 1 business day can be 3 calendar days — so no
    # option meets Shopify's 7 days (2-5 + 3, 8-15 + 3): Shopify takes its cheapest line, CJ from China, at WARN ($4.55), the highest margin of
    # all by the printed rule (PASS or WARN)
    assert ('<span class="best">Shopify</span><br><span class="why">Dropship</span></td><td class="n">$4.55</td><td class="n">$4.55</td>') in rows[0]
    assert re.findall(r'chip chip-(\w+)">([^<]+)<', rows[0]) == [("pass", "TikTok US PASS"), ("pass", "TikTok CB PASS"), ("warn", "Shopify WARN"),
                                                                  ("pass", "eBay PASS"), ("pass", "Amazon PASS")]
    for channel in ("TikTok US", "TikTok CB", "Amazon"):                                      # the inventory lines: they need your own US stock
        assert f'<span class="chip chip-pass">{channel} PASS</span><span class="why">(requires US stock)</span>' in rows[0]
    assert '<span class="unk">NONE</span>' in rows[1] and _cells(rows[1]) == ['<span class="unk">UNKNOWN</span>'] * 2
    assert rows[1].count("chip chip-unknown") == 5 and rows[1].count("(requires US stock)") == 5   # five UNKNOWN chips, none blank
    assert '<span class="best">Shopify</span><br><span class="why">Dropship</span></td><td class="n">$9.80</td>' in rows[2]
    assert rows[2].count("chip chip-pass") == 5
    assert {p["candidate_id"]: (p["best"] or {}).get("channel_id") for p in model["decision"]["products"]} == \
        {"cand_slicker": "shopify", "cand_bowl": None, "cand_harness": "shopify"}
    assert "best channel = the highest margin before ads among the channels whose delivery verdict is PASS or WARN" in page   # the rule is printed


def test_the_margin_table_shows_the_offer_type_every_cost_and_the_us_stock_an_inventory_line_requires(sample):
    _, page = sample
    head = _section(_section(_product(page, 1), "Margin per channel", "</thead>"), "<thead>", None)
    assert re.findall(r"<th[^>]*>([^<]+)</th>", head) == ["Channel", "Offer type", "Offer", "Sell", "− Unit", "− Inbound", "− Shipping / last mile",
                                                           "− Fees", "− Returns", "= Margin before ads", "Margin %", "Break-even ad cost", "Delivery"]
    margin = _section(_product(page, 1), "Margin per channel", "</tbody>")
    tiktok = _row(margin, '<td class="sticky">TikTok Shop · US account')                     # an INVENTORY line: Alibaba bulk, held in US stock
    # inbound 1.176 a unit = the MOQ order's 235.20 ÷ 200 (N4a: the per-unit figure and the total agree)
    assert _cells(tiktok) == ["$14.74", "$1.45", "$1.176", "$5.95", "$0.88", "$1.66", "$3.62", "24.6 %", "$3.62"]
    assert ("<td>Inventory<br><span class=\"why\">last mile: CJ US→US quote for Self-cleaning slicker brush pet grooming comb, 120 g</span></td>"
            '<td>ALIBABA <span class="url">alibaba:1601087654321</span></td>') in tiktok
    assert ('<span class="chip chip-pass">PASS</span> <span class="chip chip-req">REQUIRES US STOCK</span><br>'
            '<span class="req">requires holding US stock: first stock in 39 days, cash $525.20 before first stock (goods $290.00 + inbound $235.20)'
            '</span>') in tiktok                                                               # beside the verdict chip (contract C5)
    assert "+ 1 business day(s) handling" in tiktok and "with 1 business day of handling (setting handling_business_days)" in tiktok
    best = _row(margin, '<td class="sticky">Shopify')                                         # the best line: DROPSHIP, at WARN
    assert _cells(best) == ["$14.74", "$3.42", "$0.00", "$4.18", "$1.12", "$1.47", "$4.55", "30.9 %", "$4.55"] and "★ best" in best
    assert '<span class="chip chip-warn">WARN</span>' in best and "REQUIRES US STOCK" not in best
    assert "which can take up to 3 calendar days (an order on a Friday is scanned on Monday)" in best
    ebay = _row(margin, '<td class="sticky">eBay')                                             # a DROPSHIP line: CJ ships each order
    assert _cells(ebay) == ["$14.74", "$3.42", "$0.00", "$4.18", "$2.40", "$1.47", "$3.27", "22.2 %", "$3.27"]
    assert "<td>Dropship<br><span class=\"why\">the supplier ships each order: CJPacket Ordinary from CN</span></td>" in ebay
    assert "REQUIRES US STOCK" not in ebay
    others = _section(_product(page, 1), "The other offers on each channel — 5 line(s)", "</details>")
    tiktok_cj = _row(others, '<td class="sticky">TikTok Shop · US account')
    assert "<td>Dropship" in tiktok_cj and "did not confirm US stock" in tiktok_cj and "REQUIRES US STOCK" not in tiktok_cj
    harness_ebay = _row(_section(_product(page, 3), "Margin per channel", "</tbody>"), '<td class="sticky">eBay')
    # R2 #1: 2-4 days from the US + 1 business day of handling = 5 > the badge's 4 business days (it was "eligible" before handling counted)
    assert "free-shipping badge eligible" not in harness_ebay and "free-shipping badge not eligible" in harness_ebay and "(4 + 1 = 5 &gt; 4)" in harness_ebay


def _money(cell: str) -> Decimal | None:
    text = re.sub(r"<[^>]+>", "", cell)
    return None if text == "UNKNOWN" else Decimal(text.replace("−", "-").replace("$", "").replace(",", ""))


def test_every_margin_row_adds_up_on_the_page(sample):
    """sell − unit − inbound − shipping / last mile − fees − returns = margin before ads, from the numbers a reader sees (the engine
    rounds the margin to the cent, half up): every channel line, every other offer's line and every what-if, for every product."""
    _, page = sample
    checked = 0
    for n in (1, 2, 3):
        prod = _product(page, n)
        tables = [_section(prod, "Margin per channel", "</tbody>")]
        if "The other offers on each channel" in prod:
            tables.append(_section(prod, "The other offers on each channel", "</tbody>"))
        tables += [_section(prod[i:], "<tbody>", "</tbody>") for i in [m.start() for m in re.finditer("What if TikTok Shop charges 8 %", prod)]]
        for table in tables:
            for row in table.split("<tr>")[2 if "<thead>" in table else 1:]:
                cells = _cells(row)
                if cells and cells[0].endswith("%"):                                         # a what-if row starts with its fee rate
                    cells = cells[1:]
                values = [_money(c) for c in cells[:7]]
                if len(values) == 7 and None not in values:
                    sell, unit, inbound, shipping, fees, returns, margin = values
                    assert (sell - unit - inbound - shipping - fees - returns).quantize(Decimal("0.01"), ROUND_HALF_UP) == margin, row[:300]
                    checked += 1
                elif len(values) == 7:
                    assert values[6] is None, row[:300]                                      # a missing part leaves the margin UNKNOWN, never a guess
    assert checked == 5 + 5 + 2 + 5 + 2                                                       # slicker: 5 lines, 5 others, 2 what-ifs; harness: 5 + 2


def test_usd_keeps_the_precision_the_engine_kept(tmp_path):
    out = _engine("print(json.dumps([report._usd(x) for x in json.load(open(sys.argv[1]))]))", [0.035, 1.2, -3.5, 1234.5, 0.0, "UNKNOWN", None], tmp_path)
    assert out == ["$0.035", "$1.20", "−$3.50", "$1,234.50", "$0.00", "<span class='unk'>UNKNOWN</span>", "<span class='unk'>UNKNOWN</span>"]


def test_numbers_are_formatted_right_aligned_and_unknown_is_never_blank(sample):
    _, page = sample
    p1 = _product(page, 1)
    supply = _section(p1, "Supply", "Shipping legs")
    none = '<span class="why">none · dropship</span>'
    assert _cells(_row(supply, "<strong>CJ</strong>")) == ["$3.42", "1", "$3.42", none, none, none, '<span class="unk">UNKNOWN</span>', none]   # CJ: no lead time
    # MOQ capital 200 × 1.45 = 290.00, inbound 235.20 for the MOQ order = 1.176 / unit, cash before first stock 525.20, lead 15, first stock in 39 days
    assert _cells(_row(supply, "<strong>ALIBABA</strong>")) == ["$1.45", "200", "$290.00", "$1.176", "$235.20", "$525.20", "15", "39"]   # 1.176 × 200 = 235.20
    assert "best seller rank #1,243 in Pet Supplies" in p1 and "2,000" in p1 and "18,452" in p1
    p2 = _product(page, 2)
    margin = _section(p2, "Margin per channel", "</tbody>")
    assert margin.count('<td class="n"><span class="unk">UNKNOWN</span></td>') == 5 * 8     # every number but the unit cost, five channels
    assert "no last mile for shipping from your US stock" in margin and "NO LAST MILE" in p2
    assert "Reference sell price <strong><span class=\"unk\">UNKNOWN</span></strong> — basis: UNKNOWN: fewer than 3 matched listings" in p2
    assert not re.search(r'<td class="n">\s*</td>', page)                                    # no blank number cell anywhere
    assert page.count('class="n"') > 300 and "text-align:right" in page and "font-variant-numeric:tabular-nums" in page


def test_reddit_shows_the_summary_and_at_most_five_dated_comments_never_the_full_list(sample):
    model, page = sample
    demand = _section(_product(page, 1), "Demand", "Supply")
    assert html.escape(DECISION["products"][0]["demand"]["reddit"]["summary"], quote=False) in demand        # the engine's own sentence
    assert demand.count("<blockquote>") == 5 and "showing 5 of 7 comments" in demand
    assert "SIXTH-COMMENT-NEVER-SHOWN" not in page and "SEVENTH-COMMENT-NEVER-SHOWN" not in page
    first = _section(demand, "<blockquote>", "</blockquote>")
    assert ("2026-09-14 · 214 points · r/doggrooming · "
            '<a href="https://www.reddit.com/r/doggrooming/comments/sample1/best_brush_for_double_coat/" rel="noopener noreferrer" target="_blank">thread</a>') in first
    rd = model["decision"]["products"][0]["demand"]["reddit"]
    assert len(rd["comments"]) == 5 and rd["comments_total"] == 7                           # the model never carries the full list either
    assert "No Reddit threads were collected." in _product(page, 3)
    links = _section(_product(page, 1), "<strong>Reddit</strong>", "</li>")
    assert len(ANCHOR.findall(links)) == 2                                                     # two threads, each once


def test_reddit_shows_the_threads_the_parser_left_out_count_and_five_titles_with_dates(sample):
    """Contract C4 (R2 #7): the engine's `threads_excluded` — the threads the parser judged not about the product — are shown under the
    comments: how many, then at most five titles (newest first, each with its date and subreddit, a link to the thread), never counted."""
    model, page = sample
    demand = _section(_product(page, 1), "Demand", "Supply")
    left = _section(demand, "Left out as not about this product", "</p>")
    assert "Left out as not about this product: 6 threads</strong>" in left and "they are not in the counts above" in left
    assert "by the parser's relevance rule their titles do not name the product" in left      # N4d: worded for whatever rule the parser applies
    titles = re.findall(r'target="_blank">([^<]*)</a> <span class="why">\(([^)]*)\)</span>', left)
    assert titles == [("Candle warmer recommendations?", "2026-10-20 · r/Candles"), ("Off-topic &lt;b&gt;bold&lt;/b&gt; lamp thread", "2026-10-18 · r/lamps"),
                      ("Garden hose reel that does not kink", "2026-09-30 · r/gardening"), ("Phone case that survives a drop", "2026-08-01 · r/phones"),
                      ("Another off-topic thread", "2026-07-15 · r/misc")]                     # five, newest first; the undated sixth is counted, not shown
    assert '<span class="why">(+1 more)</span>' in left and "Desk lamp tips" not in page
    assert "OFF-TOPIC-COMMENT-NEVER-COUNTED" not in page                                       # their comments are never shown or counted
    assert html.escape(DECISION["products"][0]["demand"]["reddit"]["summary"], quote=False) in demand and "2 threads in 2 subreddits" in demand
    rd = model["decision"]["products"][0]["demand"]["reddit"]
    assert rd["threads_excluded_total"] == 6 and len(rd["threads_excluded"]) == 5               # the model carries five and the count
    assert "Left out as not about this product" not in _product(page, 2) + _product(page, 3)   # none left out: nothing shown


def test_the_appendix_states_the_handling_time_every_delivery_rule_counts(sample):
    _, page = sample
    appendix = _section(page, "Assumptions and Sources", "</footer>")
    assert "Handling time" in appendix and "1 business day(s) to the first carrier scan (setting handling_business_days, policies default 1)" in appendix
    # N4b / N4c: the owner's own last mile also stands in when every CJ quote's product is too light — the tolerance is the policy's
    assert "or when the offer is more than 25 % heavier than every CJ quote's product (policies report_settings last_mile_weight_tolerance)" in appendix


def test_an_inventory_offer_without_a_last_mile_shows_the_engines_reason(tmp_path):
    """The engine says why an inventory offer has no last mile (no CJ US→US quote, or the offer is over 25 % heavier than every quote's
    product — R2 #9c); the page shows that reason, not a fixed sentence."""
    decision = json.loads(json.dumps(DECISION))
    offer = next(o for o in decision["products"][1]["offers"] if o.get("model") == "inventory")
    offer["last_mile_note"] = ("the offer weighs 500 g a unit, more than 25 % above the weight of every CJ US→US quote (250 g): that price is not this "
                               "item's, and no owner setting (settings last_mile_usd / last_mile_days) stands in")
    _, page = _decision_page(tmp_path, decision)
    legs = _section(_product(page, 2), "Shipping legs", "</tbody>")
    assert "NO LAST MILE</span> — the offer weighs 500 g a unit, more than 25 % above the weight of every CJ US→US quote (250 g)" in legs


def test_supply_shows_both_supply_models_every_shipping_leg_and_the_right_us_stock_note(sample):
    _, page = sample
    p1 = _product(page, 1)
    legs = _section(p1, "Shipping legs", "</tbody>")
    assert ('<td>each order — the supplier ships to the buyer</td><td>CN</td><td>CJPacket Ordinary</td><td class="n">$4.18</td><td class="n">8–15</td>'
            "<td>CJ freight quote</td>") in legs
    assert ("<td>inbound — once, to your US stock</td><td>CN</td><td>the listing's stated shipping</td><td class=\"n\">$1.176</td>"
            '<td class="n">17–24</td><td>PER_KG · per-kg rate × unit weight<br><span class="why">destination: US</span></td>') in legs
    assert ('<td>last mile — each order, from your US stock</td><td>US</td><td>USPS Ground Advantage</td><td class="n">$5.95</td><td class="n">2–5</td>'
            "<td>CJ US→US quote for Self-cleaning slicker brush pet grooming comb, 120 g</td>") in legs
    supply = _section(p1, "Supply", "Shipping legs")
    assert "<td>Dropship</td>" in supply and "<td>Inventory</td>" in supply and "<td>PER_KG<br><span class=\"why\">per-kg rate × unit weight</span></td>" in supply
    # the US-stock caution is a DROPSHIP offer's (CJ quoted US freight without confirming stock); an inventory offer needs YOUR stock
    assert p1.count("a US→US freight quote does NOT prove US stock") == 1 and "CJ offer cj:2501163412000000001: a US→US freight quote" in p1
    assert ("ALIBABA offer alibaba:1601087654321: inventory — requires holding US stock: first stock in 39 days, cash $525.20 before first stock "
            "(goods $290.00 + inbound $235.20)") in p1
    assert "CJ suggested retail $13.68 (reference only, never used as a price)" in p1 and "supplier Ningbo Example Pet Products Co., Ltd." in p1
    assert "US stock confirmed by the supplier" in _product(page, 3)
    p2 = _product(page, 2)
    assert "host data: CJ NO_MATCH (CJ_NO_RELEVANT_PRODUCT) · eBay API NOT_CONFIGURED (EBAY_NOT_CONFIGURED)" in p2
    assert ("requires holding US stock: first stock time UNKNOWN, cash UNKNOWN before first stock (goods $310.00 + inbound UNKNOWN)"
            in p2)                                                                              # what is not known is said, not left out
    assert p1.count('<span class="pill">unadmitted</span>') == 2 + 4 + 4                       # every offer and comparable row says who stands behind it


def test_market_shows_n_median_min_max_the_reference_and_the_comparables_with_links(sample):
    _, page = sample
    market = _section(_product(page, 1), "Market</h3>", "Margin per channel")
    assert _cells(_row(market, '<td class="sticky">Amazon')) == ["4", "$14.74", "$9.99", "$24.95"]
    assert _cells(_row(market, '<td class="sticky">eBay')) == ["4", "$12.49", "$10.99", "$16.50"]
    assert "Reference sell price <strong>$14.74</strong> — basis: the Amazon median (Amazon n = 4 ≥ 3)" in market
    assert ('<a href="https://www.amazon.com/dp/B0SAMPLE001" rel="noopener noreferrer" target="_blank">Self Cleaning Slicker Brush for Dogs &amp; Cats, '
            "Grooming Comb</a>") in market
    comp = _row(_section(market, "eBay comparables", "</tbody>"), "Dog Grooming Brush Self-Cleaning NEW")
    assert _cells(comp) == ["$8.99", "$3.50", "$12.49"]                                         # price, shipping, total
    assert _cells(_row(_section(_product(page, 2), "Market</h3>", "</tbody>"), '<td class="sticky">eBay')) == ["0"] + ['<span class="unk">UNKNOWN</span>'] * 3


def test_the_tiktok_8_percent_what_if_and_the_agents_verdict_are_labelled(sample):
    _, page = sample
    p1 = _product(page, 1)
    what_if = _section(p1, "What if TikTok Shop charges 8 %", "</tbody>")
    assert "<strong>UNCONFIRMED</strong>" in what_if and "only the fee changed" in what_if
    us = _row(what_if, "TikTok Shop · US account")
    assert "<td>Inventory</td>" in us and _cells(us) == ["8 %", "$14.74", "$1.45", "$1.176", "$5.95", "$1.18", "$1.66", "$3.32", "22.5 %", "$3.32"]
    cb = _row(what_if, "TikTok Shop · cross-border")
    assert "<td>Inventory</td>" in cb and _cells(cb) == ["8 %", "$14.74", "$1.45", "$1.176", "$5.95", "$1.18", "$1.66", "$3.32", "22.5 %", "$3.32"]
    verdict = _section(p1, '<div class="agent">', "</p></div>")
    assert "the agent's verdict — not computed by Polymath" in verdict and "Go on Shopify first &lt;b&gt;now&lt;/b&gt;" in verdict
    assert '<div class="agent">' not in _product(page, 2)                                       # no verdict given: none shown
    assert page.count('<div class="agent">') == 2


def test_the_receipts_show_every_number_with_its_formula_inputs_and_result(sample):
    _, page = sample
    receipts = _section(_product(page, 1), "How these numbers were computed", "</details>")
    shopify = _row(receipts, "channels.shopify.margin_before_ads_usd")
    assert "round2(sell price − (unit cost + inbound + shipping) − fees − returns allowance)" in shopify and '<td class="n">4.55</td>' in shopify
    last_mile = _row(receipts, "channels.tiktok_us.shipping_usd")
    assert "last mile" in last_mile and "CJ US→US quote for Self-cleaning slicker brush pet grooming comb, 120 g" in last_mile and last_mile.endswith('<td class="n">5.95</td>')
    assert receipts.count("<tr>") == len(DECISION["products"][0]["receipts"]) + 1
    assert '<span class="unk">MISSING</span> lead time' in receipts                             # what a missing number lacked


def test_the_appendix_lists_every_fee_and_rule_with_its_source_link_and_date(sample):
    model, page = sample
    appendix = _section(page, "Assumptions and Sources", "</footer>")
    assert "As of <strong>2026-11-02</strong> · channel rules read on <strong>2026-11-02</strong> · ship to <strong>US</strong>" in appendix
    wanted = set(_urls(DECISION["assumptions"]))
    assert len(wanted) == 21 and all(f'<a href="{html.escape(u)}" rel="noopener noreferrer" target="_blank">' in appendix for u in wanted)
    assert f"19.3 % of sales — {DECISION['assumptions']['returns']['text']}" in appendix and "published 2025-10-15" in appendix
    assert "13.6% × (price + shipping) + $0.30 per order ≤ $10.00 / $0.40 above" in appendix
    unconfirmed = _section(appendix, '<p class="minihead">UNCONFIRMED</p>', "</ul>")
    assert "8 % fee (tiktok_8pct) — TikTok Shop · US account, TikTok Shop · cross-border" in unconfirmed and len(ANCHOR.findall(unconfirmed)) == 3
    assert [u["item"] for u in model["decision"]["unconfirmed"]] == ["8 % fee (tiktok_8pct)"]


# ─────────────────────────────────────────────────────────── links and active content
def test_https_links_are_anchors_and_every_other_scheme_stays_text(sample):
    _, page = sample
    hrefs = ANCHOR.findall(page)
    assert hrefs and all(h.startswith(("https://", "http://")) for h in hrefs)
    assert len(re.findall(r"<a\b", page)) == len(hrefs)                                       # every anchor carries rel + target
    assert 'Silicone travel bowl <span class="url">javascript:alert(1)</span>' in page and "href=\"javascript" not in page.lower()
    assert '<span class="url">data:text/html,&lt;b&gt;not a link&lt;/b&gt;</span>' in page and 'href="data:' not in page
    assert not re.search(r"<\s*(script|img|iframe|object|embed|svg)\b", page, re.IGNORECASE) and not re.search(r"<[^>]*\son[a-z]+\s*=", page, re.IGNORECASE)
    assert "&lt;script&gt;alert('title')&lt;/script&gt;" in page and "&lt;img src=x onerror=alert(2)&gt;" in page   # hostile text stays text


def test_the_engine_draws_the_anchors_and_the_sanitizer_keeps_exactly_them(tmp_path):
    raw = _engine("p = json.load(open(sys.argv[1])); print(json.dumps(report.render(report.build_model_from_bundle(p), 'DECISION')))", DECISION, tmp_path)
    assert '<a href="https://www.amazon.com/dp/B0SAMPLE001" rel="noopener noreferrer" target="_blank">' in raw
    assert 'href="javascript' not in raw and 'href="data:' not in raw
    assert ANCHOR.findall(dossier.sanitize(raw)) == ANCHOR.findall(raw)                       # the same links survive, no more


SANITIZER_CASES = [
    ('<a href="https://shop.example/p?a=1&amp;b=2" onclick="steal()" class="x" title="t">ok</a>',
     '<a href="https://shop.example/p?a=1&amp;b=2" rel="noopener noreferrer" target="_blank">ok</a>'),
    ('<a href="HTTP://SHOP.EXAMPLE/P">caps</a>', '<a href="HTTP://SHOP.EXAMPLE/P" rel="noopener noreferrer" target="_blank">caps</a>'),
    ('<a href="javascript:alert(1)">js</a>', "js"),
    ('<a href="&#106;avascript:alert(1)">entity</a>', "entity"),
    ('<a href="java\tscript:alert(1)">tab</a>', "tab"),
    ('<a href=" https://shop.example/">space</a>', "space"),
    ('<a href="https://shop.example/a b">inner space</a>', "inner space"),
    ('<a href="data:text/html,x">data</a>', "data"),
    ('<a href="//shop.example/">protocol-relative</a>', "protocol-relative"),
    ('<a href="/relative">relative</a>', "relative"),
    ('<a href="http://">no host</a>', "no host"),
    ('<a href="https://shop.example/" href="javascript:y">two</a>', "two"),
    ("<a>bare</a>", "bare"),
    ('<a href="https://shop.example/x" rel="opener" target="_self">forced</a>', '<a href="https://shop.example/x" rel="noopener noreferrer" target="_blank">forced</a>'),
    ('<p><a href="https://shop.example/">open', '<p><a href="https://shop.example/" rel="noopener noreferrer" target="_blank">open</a>'),
    ('<script><a href="https://shop.example/">in a script</a></script>after', "after"),
    ('<details><summary>s</summary><section><table><thead><tr><th>h</th></tr></thead><tbody></tbody></table></section></details>',
     '<details><summary>s</summary><section><table><thead><tr><th>h</th></tr></thead><tbody></tbody></table></section></details>'),
]


@pytest.mark.parametrize("raw,clean", SANITIZER_CASES)
def test_the_sanitizer_keeps_an_anchor_only_for_an_http_url(raw, clean):
    assert dossier.sanitize(raw) == clean


def test_the_engine_and_the_server_agree_on_which_urls_become_links(tmp_path):
    urls = ["https://www.amazon.com/dp/B0X", "http://shop.example/p?a=1&b=2", "HTTPS://X.EXAMPLE", "https://xn--bcher-kva.example/ü",
            "javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,x", "vbscript:x", "//shop.example", "/rel", "https://", "http:///p",
            " https://x.example", "https://x.example/a b", "https://x.example/\"onmouseover=y", "https://x.example/<b>", "https://x.example/\\x",
            "ftp://x.example/f", "mailto:a@b.example", "https://[::1]/p", "https://" + "a" * 2050 + ".example", 42, None, ""]
    engine = _engine("print(json.dumps([report.safe_url(u) for u in json.load(open(sys.argv[1]))]))", urls, tmp_path)
    assert engine == [dossier.safe_href(u) for u in urls]
    assert [u for u, ok in zip(urls, engine) if ok] == urls[:4] + ["https://[::1]/p"]


# ─────────────────────────────────────────────────────────── the layout: phone, light and dark, nothing else changed
def test_the_page_is_readable_on_a_phone_in_light_and_dark(sample):
    _, page = sample
    style = _section(page, "<style>", "</style>")
    assert "@media (prefers-color-scheme: dark)" in style and ':root[data-theme="dark"]' in style and "body{background:var(--bg)" in style
    assert "@media (max-width:640px)" in style and "div.scroll{overflow-x:auto}" in style and "position:sticky" in style
    assert page.count('<div class="scroll">') >= 20                                          # every table scrolls inside its own box
    assert "@import" not in style and "url(" not in style                                     # nothing external: the CSP allows none


def test_pages_without_a_decision_are_unchanged(tmp_path):
    code = ("import models; s = models.new_state('probe'); "
            "s['data']['hypotheses'] = [{'id': 'h1', 'status': 'SUPPORTED', 'target_mechanism': 'pocket_anchor', 'path': ['a', 'b'], 'evidence_boundary': {'first_inference_at': 'b'}}]; "
            "m = report.build_model(s); print(json.dumps({'html': report.render(m), 'has': 'decision' in m}))")
    out = _engine(code, {}, tmp_path)
    assert out["has"] is False and ".dec .chip" not in out["html"] and "Decision Summary" not in out["html"]


def test_the_decision_page_is_deterministic(tmp_path):
    assert _decision_page(tmp_path) == _decision_page(tmp_path)


# ─────────────────────────────────────────────────────────── contract C11: what was read through the user's Agent Reach
C11_NOTE = ("Needs a local agent: nothing from {} was uploaded for this report. Run the report's fetch script on a computer with Agent Reach "
            "(product_report_status gives it), then compile again.")
C11_TEXTS = ("Read through your Agent Reach", "Needs a local agent", "could not be read", "NOT READ")


def _plain_text(fragment: str) -> str:
    """A page fragment as a reader sees it: no tags, entities decoded."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def _no_uploads(sources=None, *, ebay_api: bool = True) -> dict:
    """BUNDLE as a compile with nothing uploaded hands it (product_report.build_bundle): every parsed list empty, the host's CJ data in;
    `ebay_api` False = a host without eBay keys (its eBay entries NOT_CONFIGURED, so eBay is planned through Agent Reach); `sources`
    beside it when given."""
    bundle = json.loads(json.dumps(BUNDLE))
    bundle["parsed"] = {c["candidate_id"]: {s: [] for s in ("reddit", "amazon", "ebay", "alibaba")} for c in bundle["candidates"]}
    if not ebay_api:
        bundle["host"]["ebay"] = {c["candidate_id"]: {"status": "NOT_CONFIGURED", "reason_code": "EBAY_NOT_CONFIGURED", "listings": []}
                                  for c in bundle["candidates"]}
    return bundle if sources is None else {**bundle, "sources": sources}


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_a_source_nothing_was_uploaded_from_says_it_needs_a_local_agent_in_its_own_section():
    """Contract C11 (plan §3.6, users without a terminal): a compile with nothing uploaded — the host's CJ data in, no Agent Reach
    packet — says in each Agent Reach source's own section (Reddit and Amazon under Demand, Alibaba under Supply, eBay under Market) that
    it needs a local agent and where the script is, in place of a finding read from nothing; its Links and Market rows say NOT READ.
    The engine's numbers are the same with or without `sources` (UNKNOWN stays UNKNOWN); without `sources` the page reads as before."""
    nothing = {s: {"planned": 3, "received": 0, "statuses": {}} for s in ("reddit", "amazon", "alibaba", "ebay")}
    out = dossier.render_decision(_no_uploads(nothing, ebay_api=False))
    before = dossier.render_decision(_no_uploads(ebay_api=False))
    page = out["html"]
    assert out["decision"] == before["decision"]                                               # compute never reads `sources`
    assert out["decision"]["products"][0]["demand"]["reddit"]["summary"] == "No Reddit threads were collected."   # the engine's own words
    assert "No Reddit threads were collected." in before["html"] and not any(x in before["html"] for x in C11_TEXTS)
    for n in (1, 2, 3):
        p = _product(page, n)
        assert "No Reddit threads were collected." not in _section(p, "Demand", "Supply")        # not read as a finding; its receipt stays
        assert "No Reddit threads were collected." in _section(p, "How these numbers were computed", "</details>")
        sections = {"Reddit": _section(p, "Demand", "Supply"), "Amazon": _section(p, "Demand", "Supply"),
                    "Alibaba": _section(p, "Supply", "Market"), "eBay": _section(p, "Market", "Margin per channel")}
        for label, part in sections.items():
            assert f'<p class="caution"><strong>{label}.</strong> Needs a local agent: nothing from {label}' in part, (n, label)
            assert C11_NOTE.format(label) in _plain_text(part) and _plain_text(p).count(C11_NOTE.format(label)) == 1, (n, label)
        links = _section(p, "Links", "Demand")
        for label in ("Alibaba", "Amazon", "eBay", "Reddit"):
            assert "NOT READ (needs a local agent)" in _plain_text(_section(links, f"<strong>{label}</strong>", "</li>")), (n, label)
        market = _section(p, "Marketplace (US)", "</tbody>")
        for label in ("Amazon", "eBay"):
            row = _row(market, f'<td class="sticky">{label}')
            assert "NOT READ (needs a local agent)" in _plain_text(row) and _cells(row)[1] == '<span class="unk">UNKNOWN</span>', (n, label)
    assert "Read through your Agent Reach: Reddit 0/3, Amazon 0/3, Alibaba 0/3, eBay 0/3" in _plain_text(page)


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_a_source_whose_every_upload_was_refused_could_not_be_read(tmp_path):
    """Contract C11: a source with uploads none of which is OK says '<Source> could not be read (BLOCKED n, HUMAN_CHECK m, EMPTY k): no
    data admitted.' in its section — the refused statuses counted, BLOCKED, HUMAN_CHECK, EMPTY first, then any other by name; a source
    with at least one OK upload is drawn from its data as before, with no note."""
    bundle = json.loads(json.dumps(BUNDLE))
    for parsed in bundle["parsed"].values():
        parsed["amazon"] = []                                                                  # every Amazon packet refused: no record
    sources = {"reddit": {"planned": 3, "received": 3, "statuses": {"EMPTY": 1, "OK": 2}},
               "amazon": {"planned": 6, "received": 5, "statuses": {"EMPTY": 1, "HUMAN_CHECK": 1, "BLOCKED": 3}},
               "alibaba": {"planned": 3, "received": 2, "statuses": {"OK": 2}}}
    out = dossier.render_decision({**bundle, "sources": sources})
    page = out["html"]
    assert out["decision"] == dossier.render_decision(bundle)["decision"]
    for n in (1, 2, 3):
        p = _product(page, n)
        demand = _section(p, "Demand", "Supply")
        assert ('<p class="caution"><strong>Amazon.</strong> Amazon could not be read (BLOCKED 3, HUMAN_CHECK 1, EMPTY 1): no data admitted.</p>'
                in demand), n
        assert "best seller rank" not in demand and "Needs a local agent" not in p
        assert "NOT READ (could not be read)" in _plain_text(_row(_section(p, "Marketplace (US)", "</tbody>"), '<td class="sticky">Amazon'))
        assert "<strong>Alibaba.</strong>" not in p                                            # read: no note
    demand = _section(_product(page, 1), "Demand", "Supply")
    assert html.escape(out["decision"]["products"][0]["demand"]["reddit"]["summary"], quote=False) in demand   # Reddit read: its summary
    assert "Read through your Agent Reach: Reddit 3/3, Amazon 5/6, Alibaba 2/3" in _plain_text(page)
    # statuses outside the three named ones follow them, by name
    odd = {"alibaba": {"planned": 3, "received": 3, "statuses": {"UNRECOGNISED": 1, "OUTPUT_TOO_LARGE": 1, "BLOCKED": 1}}}
    _, odd_page = _decision_page(tmp_path, out["decision"], meta={**META, "sources": odd})
    assert "Alibaba could not be read (BLOCKED 1, OUTPUT_TOO_LARGE 1, UNRECOGNISED 1): no data admitted." in _plain_text(_section(
        _product(odd_page, 1), "Supply", "Market"))


def test_the_agent_reach_counts_are_shown_once_near_the_top(tmp_path):
    """Contract C11: 'Read through your Agent Reach: Reddit 4/4, Amazon 0/4, ...' — packets uploaded / planned per source, once, under the
    Decision Summary heading before the summary table, in the order Reddit, Amazon, Alibaba, eBay (any other source after them, as
    text); the model carries the rows."""
    sources = {"ebay": {"planned": 2, "received": 2, "statuses": {"OK": 2}}, "alibaba": {"planned": 4, "received": 3, "statuses": {"OK": 3}},
               "amazon": {"planned": 4, "received": 0, "statuses": {}}, "reddit": {"planned": 4, "received": 4, "statuses": {"OK": 4}},
               "tiktok<img src=x onerror=alert(1)>": {"planned": 1, "received": 0, "statuses": {}}}
    model, page = _decision_page(tmp_path, meta={**META, "sources": sources})
    line = "Read through your Agent Reach: Reddit 4/4, Amazon 0/4, Alibaba 3/4, eBay 2/2, tiktok<img src=x onerror=alert(1)> 0/1"
    text = _plain_text(page)
    assert line in text and text.count("Read through your Agent Reach") == 1
    assert page.index("Decision Summary") < page.index("Read through your Agent Reach") < page.index("<th>Best channel</th>")
    assert "<img" not in page                                                                  # a source name is text
    rows = model["decision"]["sources"]
    assert [(r["source"], r["received"], r["planned"], r["state"]) for r in rows] == [
        ("reddit", 4, 4, "READ"), ("amazon", 0, 4, "NEEDS_LOCAL_AGENT"), ("alibaba", 3, 4, "READ"), ("ebay", 2, 2, "READ"),
        ("tiktok<img src=x onerror=alert(1)>", 0, 1, "NEEDS_LOCAL_AGENT")]
    assert rows[1]["note"] == C11_NOTE.format("Amazon") and C11_NOTE.format("Amazon") in _plain_text(_section(_product(page, 1), "Demand", "Supply"))


def test_a_bundle_without_sources_renders_exactly_as_before(tmp_path, sample):
    """Contract C11: an older caller's bundle (no `sources`), None, an empty mapping or sources neither planned nor received draw the same
    page and model as before — no counts line, no note, no NOT READ."""
    model, page = sample                                                                       # META carries no `sources`
    assert "sources" not in META and "sources" not in model["decision"]
    assert not any(x in page for x in C11_TEXTS)
    for sources in (None, {}, {"reddit": {"planned": 0, "received": 0, "statuses": {}}}, ["not", "a", "mapping"]):
        assert _decision_page(tmp_path, meta={**META, "sources": sources}) == (model, page), sources


# ─────────────────────────────────────────────────────────── live run 2026-11-02: CJ search prices and the costed variant
LIVE_CJ = json.loads((FIXTURES / "cj_live_pet_fountain.json").read_text(encoding="utf-8"))


def _with_cj(cid: str, products: list) -> dict:
    """BUNDLE with candidate `cid`'s CJ products replaced."""
    bundle = json.loads(json.dumps(BUNDLE))
    bundle["host"]["cj"][cid]["products"] = products
    return bundle


def _supply_row(page: str, n: int, offer_url_part: str) -> str:
    supply = _section(_product(page, n), "Supply", "Shipping legs")
    return next(row for row in supply.split("<tr>") if offer_url_part in row)


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_a_cj_offer_known_only_by_its_search_price_reads_from_and_has_no_margin_line():
    """Live (rpt_164ed807ad94e63ef002458e): a CJ product the host never detail-fetched read "Dropship $1.74" — CJ's search "from" price,
    its lowest variant, often a part. The page now says "from $1.74 (CJ search price: the lowest variant, not checked)" with why it has
    no margin line, and no margin line carries it: the channels are those of the same bundle without it."""
    unchecked = LIVE_CJ["products"][2]
    assert (unchecked["detail_status"], unchecked["price_basis"], unchecked["sell_price_usd"]) == ("NOT_FETCHED", "search_from_price", 1.74)
    slicker = BUNDLE["host"]["cj"]["cand_slicker"]["products"]
    out = dossier.render_decision(_with_cj("cand_slicker", [*slicker, unchecked]))
    page = out["html"]
    raw = _supply_row(page, 1, unchecked["product_id"])
    unit, moq, capital = (_plain_text(c) for c in _cells(raw)[:3])
    assert (unit, moq, capital) == ("from $1.74 (CJ search price: the lowest variant, not checked)", "1", "UNKNOWN")
    assert ("not in the margin lines: CJ's details for this product (its variants, weight and freight) were not read, so only its search "
            "\"from\" price is known") in _plain_text(raw)
    margins = _section(_product(page, 1), "Margin per channel", "How these numbers were computed")
    assert f"cj:{unchecked['product_id']}" not in margins and "cj:2501163412000000001" in margins
    assert out["decision"]["products"][0]["channels"] == dossier.render_decision(BUNDLE)["decision"]["products"][0]["channels"]
    assert _cells(_supply_row(page, 1, "2501163412000000001"))[0] == "$3.42"                            # a read product: its unit cost


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_the_costed_variant_is_said_in_one_line_on_its_offer():
    """B2's variant rule: the host names the variant it costs (`variant_rule`, `variants_dropped`); the offer's row says it in one line —
    "costed variant: $3.88 / 120 g; 1 lighter or part variant left out" — and its unit cost is that variant's."""
    cj = json.loads(json.dumps(BUNDLE["host"]["cj"]["cand_slicker"]["products"][0]))
    blue = cj["variants"].pop(0)                                                          # the rule left the $3.42 variant out
    cj.update(variants_dropped=[{**blue, "why": "LIGHT_WEIGHT"}], cheapest_variant_id="v-pink", sell_price_usd=3.88,
              variant_rule={"rule": "the cheapest variant left after dropping parts and light samples", "dropped": 1, "chosen_variant_id": "v-pink"})
    out = dossier.render_decision(_with_cj("cand_slicker", [cj]))
    raw = _supply_row(out["html"], 1, cj["product_id"])
    assert "supplier CJdropshipping · costed variant: $3.88 / 120 g; 1 lighter or part variant left out · CJ suggested retail" in _plain_text(raw)
    assert _cells(raw)[:3] == ["$3.88", "1", "$3.88"]                                      # unit cost, MOQ, MOQ capital: the named variant's
    unit = next(r for r in out["decision"]["products"][0]["receipts"] if r["id"] == "offers[0].unit_cost_usd")
    assert unit["formula"] == "the variant the host's variant rule costs: the cheapest variant left after dropping parts and light samples"


# ─────────────────────────────────────────────────────────── render_decision: ONE engine process
@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_render_decision_runs_the_real_unit_economics_and_draws_its_answer(tmp_path):
    out = dossier.render_decision(BUNDLE)
    decision, page = out["decision"], out["html"]
    # the decision is unit_economics' own answer for this bundle with the engine's policies: its CLI says the same
    proc = subprocess.run([sys.executable, "python/unit_economics.py", "--bundle", str(FIXTURES / "bundle_sample.json")], cwd=ENGINE, env=_env(tmp_path),
                          capture_output=True, text=True, check=True, timeout=120)
    assert json.dumps(decision, sort_keys=True) == json.dumps(json.loads(proc.stdout), sort_keys=True)
    assert decision["model"] == "unit_economics.v1" and [p["candidate_id"] for p in decision["products"]] == ["cand_slicker", "cand_bowl", "cand_harness"]
    # the page is that decision drawn by the engine's renderer, sanitized, with the bundle's verdicts and header
    expected = _engine("p = json.load(open(sys.argv[1])); m = report.build_model_from_bundle(p['d'], verdicts=p['v'], meta=p['m']); "
                       "print(json.dumps(report.render(m, 'DECISION')))",
                       {"d": decision, "v": VERDICTS, "m": {**META, "ship_to": None}}, tmp_path)
    assert page == dossier.document(dossier.sanitize(expected), "Decision report · Pet grooming and walking — decision report")
    assert all(x in page for x in ("Decision Summary", "Margin per channel", "What if TikTok Shop charges 8 %", "Assumptions and Sources",
                                   "the agent's verdict — not computed by Polymath"))
    assert not re.search(r"<\s*script", page, re.IGNORECASE) and ANCHOR.findall(page)
    assert not [m for m in ("report", "models", "graph", "unit_economics") if str(ENGINE) in str(getattr(sys.modules.get(m), "__file__", ""))]


STUB = '''"""tests only: a stand-in for unit_economics that answers the frozen decision fixture after checking what it was handed"""
import json, time
def compute(bundle, policy):
    if bundle.get("behave") == "raise":
        raise ValueError("a bundle the model cannot read")
    if bundle.get("behave") == "sleep":
        time.sleep(30)
    decision = json.load(open(%r, encoding="utf-8"))
    decision["handed"] = {"candidates": [c["candidate_id"] for c in bundle["candidates"]],
                          "policy": sorted(k for k in ("sales_channels", "report_settings", "supplier") if k in policy)}
    return decision
''' % str(FIXTURES / "decision_sample.json")


def _engine_copy(tmp_path: pathlib.Path, unit_economics: str | None) -> pathlib.Path:
    """A private copy of the engine (python/ + graph/) with `unit_economics` as its unit_economics.py — or none."""
    dst = tmp_path / "engine"
    shutil.copytree(ENGINE / "python", dst / "python", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ENGINE / "graph", dst / "graph")
    (dst / "python" / "unit_economics.py").unlink(missing_ok=True)
    if unit_economics is not None:
        (dst / "python" / "unit_economics.py").write_text(unit_economics, encoding="utf-8")
    return dst


@pytest.fixture
def stub_engine(tmp_path, monkeypatch):
    dst = _engine_copy(tmp_path, STUB)
    monkeypatch.setattr(dossier, "DECISION_RENDERER", dst / "python" / "report.py")
    return dst


def test_render_decision_hands_compute_the_bundle_and_the_engines_policies_and_draws_what_it_answers(stub_engine, tmp_path):
    out = dossier.render_decision(BUNDLE, title="Pet report")
    assert out["decision"]["handed"] == {"candidates": ["cand_slicker", "cand_bowl", "cand_harness"], "policy": ["report_settings", "sales_channels", "supplier"]}
    assert {k: v for k, v in out["decision"].items() if k != "handed"} == DECISION
    expected = _engine("p = json.load(open(sys.argv[1])); m = report.build_model_from_bundle(p['d'], verdicts=p['v'], meta=p['m']); "
                       "print(json.dumps(report.render(m, 'DECISION')))", {"d": out["decision"], "v": VERDICTS, "m": {**META, "ship_to": None}}, tmp_path)
    assert out["html"] == dossier.document(dossier.sanitize(expected), "Pet report") and "SIXTH-COMMENT-NEVER-SHOWN" not in out["html"]


def test_render_decision_failures_are_typed(stub_engine, tmp_path, monkeypatch):
    def code(bundle, **kw) -> str:
        with pytest.raises(dossier.DossierError) as err:
            dossier.render_decision(bundle, **kw)
        assert err.value.code in dossier.DECISION_ERRORS
        return err.value.code
    assert code(["not", "a", "bundle"]) == "DECISION_BUNDLE_INVALID"
    assert code({**BUNDLE, "behave": "raise"}) == "UNIT_ECONOMICS_FAILED"
    assert code({**BUNDLE, "behave": "sleep"}, timeout_s=3) == "DECISION_TIMEOUT"
    monkeypatch.setattr(dossier, "MAX_BUNDLE_BYTES", 1000)
    assert code(BUNDLE) == "DECISION_BUNDLE_TOO_LARGE"
    monkeypatch.setattr(dossier, "MAX_BUNDLE_BYTES", 20_000_000)
    monkeypatch.setattr(dossier, "MAX_HTML_BYTES", 1000)
    assert code(BUNDLE) == "DECISION_TOO_LARGE"
    monkeypatch.setattr(dossier, "MAX_HTML_BYTES", 5_000_000)
    bare = _engine_copy(tmp_path / "bare", None)                      # an engine without unit_economics.py
    monkeypatch.setattr(dossier, "DECISION_RENDERER", bare / "python" / "report.py")
    assert code(BUNDLE) == "UNIT_ECONOMICS_UNAVAILABLE"
    (bare / "python" / "report.py").write_text("import sys\nsys.exit(3)\n")                   # a renderer that dies without a word
    assert code(BUNDLE) == "DECISION_RENDER_FAILED"


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_a_bundle_the_real_model_refuses_is_a_typed_failure():
    with pytest.raises(dossier.DossierError) as err:
        dossier.render_decision({**BUNDLE, "settings": {"ship_to": "DE"}})
    assert err.value.code == "UNIT_ECONOMICS_FAILED" and "ship_to" in str(err.value)


# ─────────────────────────────────────────────────────────── a governed dossier carries the same section
H1 = "hyp_" + "a" * 12


def _journal(output: dict) -> dict:
    result = {"run_id": "adr_" + "7" * 32, "status": "completed", "gap": None, "output": output, "lineage": {}, "unknowns": [], "contradictions": []}
    return {"run_id": "adr_" + "7" * 32, "adapter_id": "ecommerce.product_research", "adapter_version": "0.7.0", "created_at": "2026-10-30T10:00:00Z",
            "input": {"seed": "synthetic seed: runners lose keys mid stride"}, "agent_identity": "test-agent", "harness_id": "test-harness",
            "events": [{"seq": 1, "kind": "result", "data": {"result": result}}], "built_at": "2026-10-30T12:00:00Z"}


GOVERNED_OUTPUT = {
    "product_concepts": [{"id": "pc_1", "name": "Magnetic belt key clip", "mechanism_id": "m_anchor", "variations": [{"name": "slim"}, {"name": "reflective"}]}],
    "sourcing_coverage": [{"concept_id": "pc_1", "concept": "Magnetic belt key clip", "candidates": 2, "parsed": 2, "leads": 2, "status": "sourced"}],
    "leads": [{"concept_id": "pc_1", "concept": "Magnetic belt key clip", "product_name": "magnetic belt clip key holder", "channel": "alibaba",
               "url": "https://www.alibaba.com/product-detail/Magnetic-Belt-Clip_1600000000001.html", "price_usd_low": 1.2, "price_usd_high": 1.8, "moq_units": 500,
               "supplier_name": "Example Hardware Co", "mechanism": "pocket anchor", "admitted_evidence_id": "fev_s1"},
              {"concept_id": "pc_1", "concept": "Magnetic belt key clip", "product_name": "running key clip", "channel": "cjdropshipping",
               "url": "https://cjdropshipping.com/product/running-key-clip-p-2500000000000000009.html", "price_usd_low": 4.35, "price_usd_high": 4.35, "moq_units": 1,
               "supplier_name": "", "mechanism": "pocket anchor", "admitted_evidence_id": "fev_s2"}],
    "concept_reality": [{"concept_id": "pc_1", "concept": "Magnetic belt key clip", "mechanism_id": "m_anchor", "hypothesis_id": H1, "jobs_planned": 2,
                         "existing_products": 5, "by_relation": {"competitor": 5}, "contested_by": [], "status": "EXISTING_PRODUCTS_FOUND"}],
    "existing_products": [
        {"id": f"fev_r{i}", "concept_id": "pc_1", "applies_to_concepts": ["pc_1"], "relation": "competitor", "contests_concept": False, "product_name": name,
         "price_raw": price, "url": url, "claim": "listed today"}
        for i, (name, price, url) in enumerate([("Belt key clip A", "$19.99", "https://www.amazon.com/dp/B0GOV00001"),
                                                ("Belt key clip B", "$24.99", "https://www.amazon.com/dp/B0GOV00002"),
                                                ("Belt key clip C", "$14.99", "https://www.amazon.com/dp/B0GOV00003"),
                                                ("Belt key clip D", "$12.50", "https://www.ebay.com/itm/100000000077"),
                                                ("Belt key clip E", "$9.99 - $15.99", "https://shop.example/p/clip-e")])],
    "reality_plan": [{}, {}],
}


def _governed(output: dict, tmp_path, *, engine: pathlib.Path = ENGINE) -> tuple[dict, str]:
    out = _engine("m = report.build_model_from_governed(json.load(open(sys.argv[1]))); print(json.dumps({'model': m, 'html': report.render(m)}))",
                  _journal(output), tmp_path, engine=engine)
    return out["model"], dossier.sanitize(out["html"])


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_a_governed_dossier_computes_the_decision_from_admitted_supply_leads_and_product_reality_prices(tmp_path):
    model, page = _governed(GOVERNED_OUTPUT, tmp_path)
    dec = model["decision"]
    assert dec["admission"] == "TrailSignal-admitted" and dec["error"] is None and [p["candidate_id"] for p in dec["products"]] == ["pc_1"]
    p = dec["products"][0]
    assert p["title"] == "Magnetic belt key clip"
    offers = {o["source"]: o for o in p["offers"]}
    assert (offers["alibaba"]["unit_cost_usd"], offers["alibaba"]["moq"], offers["alibaba"]["moq_capital_usd"]) == (1.8, 500, 900.0)   # a range: its high end
    assert (offers["cj"]["unit_cost_usd"], offers["cj"]["moq"]) == (4.35, 1) and all(o["admission"] == "TrailSignal-admitted" for o in p["offers"])
    amazon = p["market"]["amazon"]
    assert (amazon["n"], amazon["median"], amazon["min"], amazon["max"], p["market"]["reference_price_usd"]) == (3, 19.99, 14.99, 24.99, 19.99)
    assert p["market"]["ebay"]["n"] == 1 and all(c["admission"] == "TrailSignal-admitted" for c in amazon["comps"])
    assert [o["title"] for o in dec["other_prices"]] == ["Belt key clip E"]                  # another retailer: listed, not in the market model
    assert all(c["margin_before_ads_usd"] == "UNKNOWN" for c in p["channels"]) and all(c["sell_price_usd"] == 19.99 for c in p["channels"])
    # the page: the same section, every row labelled TrailSignal-admitted, beside everything the dossier showed before
    assert "LIVE-WORLD OBSERVATION" in _section(page, "Decision Summary", "</h2>")
    assert "Rows are <strong>TrailSignal-admitted</strong>" in page and page.count('<span class="pill">TrailSignal-admitted</span>') == 2 + 4 + 1
    assert "unadmitted" not in page and "host data:" not in page                               # a governed run made no host CJ / eBay call
    assert "Supplier Leads" in page and "$1.2 / unit · MOQ 500" in page and "Product Reality — generated concepts vs. existing products" in page
    assert page.index("Supplier Leads") < page.index("Decision Summary")
    assert ('<a href="https://www.amazon.com/dp/B0GOV00001" rel="noopener noreferrer" target="_blank">Belt key clip A</a>' in page
            and "https://www.amazon.com/dp/B0GOV00001</td>" in page)                          # an anchor in the decision; the old block keeps its text


def test_a_governed_run_without_a_supply_lead_has_no_decision_section(tmp_path):
    output = {k: v for k, v in GOVERNED_OUTPUT.items() if k != "leads"}
    model, page = _governed(output, tmp_path)
    assert model["decision"] is None and "Decision Summary" not in page and ".dec .chip" not in page and "<a " not in page


def test_a_governed_dossier_keeps_every_other_section_when_unit_economics_is_missing(tmp_path):
    bare = _engine_copy(tmp_path, None)
    model, page = _governed(GOVERNED_OUTPUT, tmp_path, engine=bare)
    assert model["decision"]["error"]["code"] == "UNIT_ECONOMICS_UNAVAILABLE" and model["decision"]["products"] == []
    assert "The unit economics could not be computed (UNIT_ECONOMICS_UNAVAILABLE)" in page
    assert "Supplier Leads" in page and "$1.2 / unit · MOQ 500" in page and "Product Reality — generated concepts vs. existing products" in page


# the scripted, complete ecommerce.product_research run (stub TrailSignal, in-memory store): the closest thing in this repository to a
# recorded R7 governed journal — no recorded R7 journal is kept as a fixture
from test_adapter_ecommerce_dossier import runtime  # noqa: E402,F401  (the in-memory store + stub TrailSignal fixture)


@pytest.mark.skipif(not HAS_COMPUTE, reason="unit_economics.py (B3) is not in this checkout")
def test_the_scripted_governed_run_gains_the_decision_section_and_loses_nothing(runtime, tmp_path):  # noqa: F811
    import test_adapter_ecommerce_dossier as DOSSIER
    import test_adapter_ecommerce_product_research_e2e as SCRIPT
    page, model = DOSSIER._dossier(DOSSIER._journaled_run(SCRIPT.Agent()), tmp_path)
    dec = model["decision"]
    assert dec and dec["admission"] == "TrailSignal-admitted" and dec["error"] is None
    assert [p["candidate_id"] for p in dec["products"]] == ["pc_1", "pc_2"]                     # the two sourced concepts; pc_3 is unsourced
    units = {p["candidate_id"]: [o["unit_cost_usd"] for o in p["offers"]] for p in dec["products"]}
    assert units == {"pc_1": [1.8], "pc_2": [4.35]}                                               # US$1.20-1.80 at MOQ 500: the high end
    assert all(label in page for label in DOSSIER.LABELS) and "UNSOURCED" in page and "$1.2 / unit" in page and "Example Hardware Co" in page
    assert "Decision Summary" in page and "Assumptions and Sources" in page and "evidence score" not in page
