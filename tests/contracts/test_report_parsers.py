"""PRODUCT-DECISION-REPORT-V1 (B1, plan §4.1): `agent_reach.parse_report_source` reads ONE upload of the report's fetch script
(an Exa search output or ONE Jina Reader page) for reddit / amazon / ebay / alibaba, line by line, into the report's records.
  * the owner (2026-11-02): an HTML decision report any agent model can produce; raw pages never pass through the model: the
    user's machine runs the fetch script and Polymath parses the uploads deterministically;
  * Jina answers HTTP 200 even when the site refused it: block pages are BLOCKED, verification pages HUMAN_CHECK, nothing from
    either is a record; a number the page does not state stays None (never guessed);
  * the owner (2026-11-02): Reddit needs "comments with dates and summary": each comment keeps its date (ISO when it can be
    read, else the shown text with its precision), points and a short text; at most 5 per thread, highest points first.
Fixtures (tests/fixtures/product_report/) are the owner's REAL Agent Reach probe outputs of 2026-11-02, unedited, except that the
probe's own `curl -w` trailer line (`__CURLMETA__ http=… time=… size=…`) is dropped from the Jina reads (the byte count it
printed was checked against the body that remains):
  exa_reddit_brush.out / exa_reddit_candle_r2.out   `mcporter call exa.web_search_exa query=site:reddit.com …` (8 threads each)
  exa_reddit_candle.out                             the same search answered 429 (empty output)
  exa_amazon_brush.out / exa_amazon_candle.out      Exa restricted to amazon.com (the candle one holds an Amazon search page)
  jina_amazon_product.out                           `curl -s https://r.jina.ai/https://www.amazon.com/dp/B00ZGPI3OY`
  jina_amazon_search_links.out                      the search page read with `X-With-Links-Summary: true` (449 KB)
  jina_amazon_search.out                            the search page read without it (no product links)
  jina_amazon_search_plain.out                      live 2026-11-02: a search page in Jina's PLAIN-TEXT layout, its links only in
                                                    the "Links/Buttons:" summary (unedited: the fetch script's own output)
  jina_amazon_search_snapshot.out                   live 2026-11-02 (amz_feeder): Jina's cached snapshot of a search page that
                                                    had not loaded, 346 bytes, both warnings over an empty Markdown Content
                                                    (unedited: the fetch script's own output)
  exa_ebay_brush.out / exa_ebay_candle.out          Exa restricted to ebay.com (it dropped the restriction: mostly other sites)
  exa_alibaba_brush.out / exa_alibaba_candle.out    Exa restricted to alibaba.com
  jina_alibaba_A.out / jina_alibaba_B_retry.out     Jina on two alibaba.com product pages
  jina_alibaba_B.out / jina_alibaba_C.out           Jina on alibaba.com product pages answered "Access Denied" (Akamai)
  jina_reddit_*.out (7) / jina_ebay_*.out (5)       Jina on reddit threads and eBay pages: all blocked
No network, no browser, no database."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared",):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import agent_reach as AR
from polymath_shared.acquisition import challenge as CH

FIX = ROOT / "tests" / "fixtures" / "product_report"
BRUSH, CANDLE = ["self-cleaning slicker brush"], ["candle warmer lamp"]
ISO_MINUTE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z")
#: a supplier's own description: a synthetic product page is a real page's size (a Jina read under AR.READER_MIN_BYTES with no
#: block or check page in it is a failed read, never a page)
SUPPLIER_TEXT = "\n## Product descriptions from the supplier\n\n" + "A sturdy product for everyday use, packed with care. " * 10 + "\n"


def _fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _parse(source: str, name: str, kind: str = "search", terms: list[str] | None = None) -> dict:
    return AR.parse_report_source(source, _fx(name), kind=kind, candidate_terms=terms)


def _by(records: list[dict], key: str) -> dict:
    return {r[key]: r for r in records}


def test_the_code_under_test_is_this_checkout_and_the_fixtures_hold_no_secret():
    assert pathlib.Path(AR.__file__).resolve().is_relative_to(ROOT), AR.__file__
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "__CURLMETA__" not in text, path.name
        assert not re.search(r"exaApiKey=|Authorization: Bearer|EXA_API_KEY|JINA_API_KEY|CJ_API_KEY|api[_-]?key=", text, re.IGNORECASE), path.name


def test_the_result_shape_and_the_vocabulary():
    got = _parse("reddit", "exa_reddit_brush.out")
    assert set(got) == {"status", "source", "kind", "tool_class", "records", "next_targets", "refused", "notes"}
    assert (got["status"], got["source"], got["kind"], got["tool_class"]) == ("OK", "reddit", "search", "agent_reach.exa")
    assert got["notes"][0] == AR.REPORT_UNTRUSTED and "Polymath opened no page" in got["notes"][1]
    with pytest.raises(ValueError):
        AR.parse_report_source("tiktok", "x", kind="search")
    with pytest.raises(ValueError):
        AR.parse_report_source("reddit", "x", kind="thread")


# ─────────────────────────────────────────────────────────── reddit (Exa only: Jina is blocked)
def test_reddit_threads_with_dated_comments_highest_points_first():
    got = _parse("reddit", "exa_reddit_brush.out", terms=BRUSH)
    assert got["status"] == "OK" and len(got["records"]) == 8 and got["refused"] == [] and got["next_targets"] == []
    threads = _by(got["records"], "url")
    first = threads["https://www.reddit.com/r/StandardPoodles/comments/lyfl5i/slicker_brush_recommendations/"]
    assert (first["kind"], first["title"], first["subreddit"], first["published_at"]) == \
        ("thread", "Slicker Brush Recommendations?", "StandardPoodles", "2021-03-05T16:27:37Z")
    assert (first["score"], first["comments_count"]) == (None, None)             # Exa showed no "Posted by" line: unknown, not 0
    assert [(c["author"], c["points"], c["date"], c["date_precision"]) for c in first["comments"]] == [
        ("y2knole", 2, "2021-03-05T16:29:00Z", "minute"), ("lcollision", 2, "2021-03-05T16:43:00Z", "minute"),
        ("WuPacalypse", 2, "2021-03-05T17:22:00Z", "minute")]
    assert first["comments"][0]["text"] == ("people swear on the cris cristensen ones. i personally have something from amazon or chewy or "
                                            "something that was like $12 and i guess it does fine? Im not about to drop $80 on a dog brush.")
    assert first["excerpt"].startswith("What is your favourite brush for your spoo?") and first["relevant"] is True
    # Exa cut this title ("... The ..."): the post's own heading holds it whole; its "Posted by" line holds score and comments
    sam = threads["https://www.reddit.com/r/samoyeds/comments/1rq3u24/i_have_to_give_a_shoutout_to_this_cheap_slicker/"]
    assert sam["title"] == "I have to give a shout-out to this cheap slicker brush. The Nice Paws self clearing brush is definitely my go-to."
    assert (sam["score"], sam["comments_count"], sam["published_at"]) == (81, 6, "2026-03-10T17:46:45Z")
    assert [(c["author"], c["points"]) for c in sam["comments"]] == [("Basic_Commercial_241", 7), ("Kazaklyzm", 6)]
    # a comment header with no quoted text under it (cut by Exa) is no comment; the links a thread names are kept apart
    doodles = threads["https://www.reddit.com/r/Goldendoodles/comments/v35r27/slicker_brush_recommendations/"]
    assert [(c["author"], c["points"]) for c in doodles["comments"]] == [("ExtensionCamel8607", 5), ("kkc126", 2)]
    assert doodles["links"] == ["https://www.amazon.com/dp/B00KAJQJ74?ref=ppx_pop_mob_ap_share",
                                "https://www.amazon.com/dp/B09G981NXV/ref=cm_sw_r_cp_api_i_7Z397MJTYCSTS127F691?_encoding=UTF8&psc=1",
                                "https://www.amazon.com/dp/B00TYEMXQC/ref=cm_sw_r_cp_api_i_GSMV0RB9KQJ3YQ5W4Q67"]
    assert threads["https://www.reddit.com/r/Goldendoodles/comments/1bfocb7/is_the_chris_christensen_slicker_brush_worth_the/"]["comments"] == []
    for t in got["records"]:
        assert len(t["comments"]) <= AR.MAX_COMMENTS and all(len(c["text"]) <= AR.COMMENT_CHARS for c in t["comments"])
        assert [c["points"] for c in t["comments"]] == sorted((c["points"] for c in t["comments"]), reverse=True)


@pytest.mark.parametrize("name,kept", [("exa_reddit_brush.out", 16), ("exa_reddit_candle_r2.out", 14)])
def test_every_comment_date_on_the_real_exa_outputs_is_parsed(name, kept):
    got = _parse("reddit", name)
    comments = [c for t in got["records"] for c in t["comments"]]
    assert len(comments) == kept and all(c["text"] and c["author"] and c["points"] is not None for c in comments)
    assert all(ISO_MINUTE.fullmatch(c["date"]) and c["date_precision"] == "minute" for c in comments), comments
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", t["published_at"]) for t in got["records"])
    if name == "exa_reddit_candle_r2.out":
        best = _by(got["records"], "subreddit")["NeedProductHelp"]
        assert (best["comments"][0]["author"], best["comments"][0]["date"]) == ("IntrepidFishing1020", "2026-04-25T09:32:00Z")
        assert [c["points"] for c in _by(got["records"], "url")[
            "https://www.reddit.com/r/bathandbodyworks/comments/rynv7y/candle_warmer_vs_burning/"]["comments"]] == [25, 12, 1]


def test_cut_dates_keep_their_precision_and_at_most_five_comments_stay():
    """The date parts of the real cut comment headers ("June 2, 2022 at", "December 4,", and "12 points ·" with no date), each
    given a quoted text; an impossible day or time is never turned into a date."""
    heads = ["**u/SapientSerpent** · 5 points · June 2, 2022 at", "**u/KristenLeighG** · 6 points · December 4,",
             "**u/jfein03** · 12 points ·", "**u/a1** · 1 point · March 21, 2025 at 4:57 AM UTC", "**u/a2** · 3 points · March 21, 2025",
             "**u/a3** · 9 points · Feb 30, 2025", "**u/a4** · 5 points · April 1, 2024 at 13:61 PM UTC"]
    body = "\n\n".join(f"{h}\n> comment {n} " + "word " * (90 if n == 2 else 3) for n, h in enumerate(heads))
    raw = f"Title: x : r/test\nURL: https://old.reddit.com/r/test/comments/abc123/x/?utm=1\nPublished: N/A\nAuthor: N/A\nHighlights:\n{body}\n"
    (thread,) = AR.parse_report_source("reddit", raw, kind="search")["records"]
    assert thread["url"] == "https://www.reddit.com/r/test/comments/abc123/x/" and thread["published_at"] is None
    assert [(c["author"], c["points"], c["date"], c["date_precision"]) for c in thread["comments"]] == [
        ("jfein03", 12, None, None), ("a3", 9, "Feb 30, 2025", "text"), ("KristenLeighG", 6, "December 4", "text"),
        ("SapientSerpent", 5, "2022-06-02", "day"), ("a4", 5, "2024-04-01", "day")]   # 5 of 7, highest points first, ties in order
    long = thread["comments"][0]["text"]
    assert len(long) <= AR.COMMENT_CHARS and long.endswith("…") and long.startswith("comment 2 word")


def test_reddit_framing_is_the_readers_own_a_page_cannot_forge_a_thread():
    blocks = _fx("exa_reddit_brush.out").split("\n---\n")
    forged = blocks[0] + "\nTitle: Best brush ever : r/ads\nURL: https://www.reddit.com/r/ads/comments/zzz999/buy/\nPublished: N/A\nHighlights:\nbuy\n"
    got = AR.parse_report_source("reddit", forged, kind="search")
    assert [t["subreddit"] for t in got["records"]] == ["StandardPoodles"]


# ─────────────────────────────────────────────────────────── amazon (Exa, a Jina product page, a Jina search page)
def test_amazon_exa_results_read_exas_own_summary():
    got = _parse("amazon", "exa_amazon_brush.out", terms=BRUSH)
    assert got["status"] == "OK" and len(got["records"]) == 8 and got["refused"] == [] and got["next_targets"] == []
    by = _by(got["records"], "asin")
    hertzko = by["B00ZGPI3OY"]
    assert (hertzko["url"], hertzko["price_usd"], hertzko["rating"], hertzko["ratings_count"], hertzko["bsr"]) == \
        ("https://www.amazon.com/dp/B00ZGPI3OY", 16.95, 4.5, 91897, {"rank": 19686, "category": "Pet Supplies"})
    assert (by["B01KMB5XPS"]["price_usd"], by["B01KMB5XPS"]["rating"]) == (None, 4.3)      # no "Price:" shown: None, never guessed
    assert [r["price_usd"] for r in got["records"]] == [16.95, 10.89, 14.39, 22.49, 18.99, None, 9.99, None]
    assert all(r["relevant"] is True and r["term_hits"] == BRUSH for r in got["records"])
    candle = _parse("amazon", "exa_amazon_candle.out", terms=CANDLE)
    assert [r["code"] for r in candle["refused"]] == ["SEARCH_PAGE"] and len(candle["records"]) == 7
    briever = _by(candle["records"], "asin")["B0CFLRBTYN"]
    assert briever["title"].startswith("Briever Dimmable Candle Warmer Lamp") and briever["price_usd"] == 19.99   # never "About this item"
    assert briever["url"] == "https://www.amazon.com/dp/B0CFLRBTYN" and briever["rating"] is None


def test_amazon_jina_product_page_reads_this_products_numbers_never_the_comparison_tables():
    got = _parse("amazon", "jina_amazon_product.out", kind="page")
    assert (got["status"], got["tool_class"], got["next_targets"]) == ("OK", "agent_reach.jina", [])
    (rec,) = got["records"]
    assert rec["title"] == ("Hertzko Self Cleaning Slicker Brush for Dogs and Cats - Pet Hair Brush for Shedding Long and Short Hair - Easy "
                            "Clean Retractable Bristles - Cat and Dog Grooming Tool - Purple")
    assert {k: rec[k] for k in ("asin", "price_usd", "list_price_usd", "rating", "ratings_count", "bsr", "bought_past_month",
                                "delivery_text", "fulfilled_by", "prime")} == {
        "asin": "B00ZGPI3OY", "price_usd": 16.95, "list_price_usd": None, "rating": 4.5, "ratings_count": 91899,
        "bsr": {"rank": 19379, "category": "Pet Supplies"}, "bought_past_month": 200, "delivery_text": "FREE delivery",
        "fulfilled_by": "merchant", "prime": None}           # "This item: … Ships from and sold by BullzEyeDeals."


def test_amazon_search_page_with_links_lists_its_products_and_names_their_pages():
    raw = _fx("jina_amazon_search_links.out")
    assert AR.MAX_RAW_BYTES < len(raw.encode()) <= AR.MAX_REPORT_BYTES          # 449 KB: over supplier_parse's cap, within the report's
    got = AR.parse_report_source("amazon", raw, kind="search", candidate_terms=BRUSH)
    recs = got["records"]
    assert (got["status"], len(recs), got["refused"]) == ("OK", 48, [])
    first = recs[0]
    assert {k: first[k] for k in ("asin", "price_usd", "list_price_usd", "rating", "ratings_count", "bought_past_month", "prime",
                                  "fulfilled_by")} == {"asin": "B0CLLPVZRV", "price_usd": 14.99, "list_price_usd": 19.99, "rating": 4.6,
                                                       "ratings_count": 14600, "bought_past_month": 10000, "prime": True,
                                                       "fulfilled_by": "amazon"}
    assert first["delivery_text"] == ("Join Prime to get FREE delivery Thu, Nov 5 / Or Non-members get FREE delivery Sat, Nov 7 on $35 of "
                                       "items shipped by Amazon")
    by = _by(recs, "asin")
    assert (by["B00OIP3QEU"]["price_usd"], by["B00OIP3QEU"]["list_price_usd"]) == (30.59, None)    # "Typical price" is no list price
    assert (by["B000YJ0SR2"]["prime"], by["B00ZGPI3OY"]["fulfilled_by"]) == (None, None)            # not shown: None
    filled = {k: sum(r[k] is not None for r in recs) for k in ("price_usd", "rating", "ratings_count", "bought_past_month", "prime",
                                                                "fulfilled_by", "list_price_usd", "bsr")}
    assert filled == {"price_usd": 48, "rating": 48, "ratings_count": 48, "bought_past_month": 38, "prime": 45, "fulfilled_by": 45,
                      "list_price_usd": filled["list_price_usd"], "bsr": 0} and filled["list_price_usd"] >= 5
    targets = got["next_targets"]
    assert len(targets) == AR.MAX_NEXT_TARGETS and all(t["source"] == "amazon" and t["kind"] == "page" for t in targets)
    assert all(re.fullmatch(r"https://www\.amazon\.com/dp/[A-Z0-9]{10}", t["url"]) for t in targets)
    assert targets[0]["url"] == "https://www.amazon.com/dp/B0CLLPVZRV"
    relevant = [r["url"] for r in recs if r["relevant"]]
    assert [t["url"] for t in targets] == relevant[:AR.MAX_NEXT_TARGETS]          # relevant first, in the page's order


def test_amazon_search_page_without_links_names_no_product():
    got = _parse("amazon", "jina_amazon_search.out", terms=CANDLE)
    assert (got["status"], got["records"], got["next_targets"]) == ("EMPTY", [], [])
    assert [r["code"] for r in got["refused"]] == ["NO_PRODUCT_LINKS"] and "X-With-Links-Summary: true" in got["refused"][0]["why"]


# ─────────────────────────────────────────────────────────── ebay (Exa fallback only)
def test_ebay_exa_keeps_ebay_item_pages_and_refuses_every_other_site():
    got = _parse("ebay", "exa_ebay_brush.out", terms=BRUSH)
    assert got["status"] == "OK" and [r["code"] for r in got["refused"]] == ["OFF_SITE"] * 6
    assert any("without the site restriction" in n for n in got["notes"])
    uk, au = got["records"]
    assert uk == {"kind": "listing", "item_id": "355791010109", "title": "FRESHLY BAILEY SELF-CLEANING SLICKER BRUSH FOR CATS/DOGS NEW NO PACKAGE",
                  "url": "https://www.ebay.co.uk/itm/355791010109", "domain": "ebay.co.uk", "price": 20.39, "currency": "USD",
                  "shipping_text": "US $19.51 (approx £14.75) eBay International Shipping", "location": "Yukon, OK, United States",
                  "delivery_text": None, "sold_count": None, "condition": "New", "us_listing": False, "relevant": True, "term_hits": BRUSH}
    assert {k: au[k] for k in ("domain", "price", "currency", "sold_count", "condition", "location", "delivery_text", "us_listing")} == {
        "domain": "ebay.com.au", "price": 5.0, "currency": "USD", "sold_count": 118, "condition": "Brand New",
        "location": "Ashburn, Virginia, United States", "delivery_text": "Estimated between Mon, 2 Nov and Sat, 7 Nov to 94112",
        "us_listing": False}
    candle = _parse("ebay", "exa_ebay_candle.out")
    (lamp,) = candle["records"]
    assert (lamp["price"], lamp["currency"], lamp["sold_count"], lamp["delivery_text"], lamp["location"]) == \
        (58.99, "AUD", 1, "Varies", "Newtown, Australia")
    assert [r["code"] for r in candle["refused"]] == ["OFF_SITE"] * 7                 # amazon.com pages and two amzn.to short links


# ─────────────────────────────────────────────────────────── alibaba (Exa, Jina product pages)
def test_alibaba_exa_tiers_moq_lead_time_and_the_split_prices():
    got = _parse("alibaba", "exa_alibaba_brush.out", terms=BRUSH)
    assert (got["status"], len(got["records"]), got["refused"]) == ("OK", 8, [])
    by = _by(got["records"], "product_id")
    aiya = by["1600824724683"]                                                   # "$0.88 100-999 pieces" on one line
    assert aiya["price_tiers"] == [{"qty_min": 100, "qty_max": 999, "unit_price": 0.88}, {"qty_min": 1000, "qty_max": 2999, "unit_price": 0.8},
                                   {"qty_min": 3000, "qty_max": None, "unit_price": 0.75}]
    assert (aiya["moq"], aiya["moq_unit"], aiya["moq_basis"], aiya["unit_price_at_moq"], aiya["currency"]) == (100, "pieces", "first_tier", 0.88, "USD")
    assert (aiya["lead_time_days_min"], aiya["lead_time_days_max"]) == (31, 31)      # the lead-time table's smallest order
    assert aiya["lead_time_text"] == ("lead time 1-100 pieces: 31 days; >100 pieces: to be negotiated; for the minimum order (100 "
                                      "pieces): 31 days; delivery time (supplier attribute): 7-15 Days")
    assert aiya["lead_time_basis"] == "moq_row"
    assert aiya["lead_time_table"] == [{"qty_min": 1, "qty_max": 100, "days": 31}, {"qty_min": 101, "qty_max": None, "days": None}]
    assert (aiya["gross_weight_kg"], aiya["sample_price_usd"], aiya["sold_as_shown"]) == (0.17, 8.0, "601 sold")
    split = by["1601292437894"]                                                  # "$" / "2" / "59" over three lines
    assert split["price_as_listed"] == "$2.59 (10-99 pieces), $2.17 (100-999 pieces), $1.86 (≥1,000 pieces)"
    assert (split["moq"], split["unit_price_at_moq"], split["lead_time_days_min"]) == (10, 2.59, 10)
    assert (split["delivery_estimate_text"], split["shipping_fee_text"]) == \
        ("Guaranteed delivery: Aug 07 - Sep 01", "Shipping fee: $47.90 $67.90 for 10 pieces")
    rng = by["1600978228274"]                                                    # "$ 2 08- 2 18 Minimum order quantity: 1,000 pieces"
    assert (rng["price_min"], rng["price_max"], rng["unit_price_at_moq"], rng["unit_price_basis"], rng["moq"], rng["moq_basis"]) == \
        (2.08, 2.18, 2.18, "range_max", 1000, "stated")
    euro = by["1600901187399"]                                                   # "€ 2 30": kept in euros, never converted
    assert (euro["price_as_listed"], euro["currency"], euro["price_min"], euro["moq"]) == ("€2.30", "EUR", 2.3, 10)
    idepet = by["1601707877823"]
    assert (idepet["store_rating"], idepet["store_rating_count"]) == (4.6, 1226)
    assert [r["days"] for r in idepet["lead_time_table"]] == [9, 30, None]
    assert all(r["transit_days_min"] is None and r["on_time_dispatch_rate"] is None for r in got["records"])   # Exa shows neither
    assert [t["url"] for t in got["next_targets"]] == [r["url"] for r in got["records"]]                       # 8 product-detail pages
    assert all(t["source"] == "alibaba" and t["kind"] == "page" and "/product-detail/" in t["url"] for t in got["next_targets"])


def test_alibaba_exa_introduction_pages_and_reversed_tiers():
    got = _parse("alibaba", "exa_alibaba_candle.out", terms=CANDLE)
    assert [r["code"] for r in got["refused"]] == ["NOT_A_PRODUCT_PAGE"] * 3      # two electronics listing pages, a showroom
    by = _by(got["records"], "product_id")
    assert sorted((pid, r["page"]) for pid, r in by.items()) == [
        ("1600715897476", "detail"), ("1600909800522", "introduction"), ("1601032523521", "introduction"),
        ("1601723721615", "detail"), ("60821188177", "introduction")]
    gloway = by["1600909800522"]                                                 # "- 5 - 99 Pieces" then "$7.90"
    assert [(t["qty_min"], t["qty_max"], t["unit_price"]) for t in gloway["price_tiers"]] == [(5, 99, 7.9), (100, 499, 7.4), (500, 2999, 6.8), (3000, None, 6.4)]
    lantern = by["60821188177"]                                                  # "$8.35-$11.58/ Piece| 60 Piece/Pieces(Min. Order)"
    assert (lantern["price_min"], lantern["price_max"], lantern["moq"], lantern["minimum_order_as_listed"]) == (8.35, 11.58, 60, "60 pieces")
    nine = by["1601723721615"]                                                   # "$ 9 69" / "27-269 pieces"
    assert (nine["unit_price_at_moq"], nine["moq"], nine["price_min"]) == (9.69, 27, 7.09)
    assert [t["url"] for t in got["next_targets"]] == [by["1601723721615"]["url"], by["1600715897476"]["url"]]   # detail pages only


def test_alibaba_jina_pages_supplier_card_dispatch_transit_and_shipping():
    a = _parse("alibaba", "jina_alibaba_A.out", kind="page")
    (rec,) = a["records"]
    assert (rec["supplier"], rec["supplier_years_as_shown"], rec["moq"], rec["unit_price_at_moq"]) == \
        ("Yangzhou Aiya Pet Products Co., Ltd.", "12 yrs", 100, 0.88)
    assert (rec["transit_days_min"], rec["transit_days_max"], rec["shipping_per_kg_usd"]) == (17, 24, 0.84)
    # "Starts at US$0.84/kg with a 50kg minimum": the minimum is by weight; no money minimum is stated, so none is computed
    assert (rec["shipping_min_kg"], rec["shipping_min_charge_usd"], rec["shipping_quote_usd"], rec["shipping_quote_qty"]) == (50.0, None, None, None)
    # the card prints "≥85%" before its label and the reorder rate's "50%" after it; the overview's exact "85.7%" wins
    assert (rec["on_time_dispatch_rate"], rec["on_time_dispatch_text"]) == (0.857, "85.7%")
    assert (rec["store_rating"], rec["store_rating_count"], rec["ships_to"]) == (4.9, 213, "US")
    assert (rec["lead_time_days_min"], rec["gross_weight_kg"], rec["sample_price_usd"]) == (31, 0.17, 8.0)
    assert rec["shipping_fee_text"] == "Shipping fee: Starts at US$0.84/kg with a 50kg minimum. Final cost varies by destination."
    assert a["next_targets"] == []
    (b,) = _parse("alibaba", "jina_alibaba_B_retry.out", kind="page")["records"]
    assert (b["supplier"], b["on_time_dispatch_rate"], b["on_time_dispatch_text"], b["store_rating"]) == \
        ("Guangzhou Yanhui E-Commerce Co., Ltd.", 0.96, "≥96%", 4.5)
    assert [(r["qty_min"], r["qty_max"], r["days"]) for r in b["lead_time_table"]] == [(1, 100, 7), (101, 500, 10), (501, 1000, 15), (1001, None, None)]
    assert (b["delivery_estimate_text"], b["shipping_fee_text"], b["gross_weight_kg"]) == \
        ("Estimated delivery by Nov 23-Dec 03", "Shipping fee: $5,537 for 200 pieces", 1.2)
    assert (b["shipping_quote_usd"], b["shipping_quote_qty"], b["shipping_min_kg"]) == (5537.0, 200, None)
    # R2 #4: the MOQ is 200, so the row 101-500 (10 days) applies, never the smallest row (7 days)
    assert (b["moq"], b["lead_time_days_min"], b["lead_time_days_max"], b["lead_time_basis"]) == (200, 10, 10, "moq_row")
    assert b["lead_time_text"].endswith("; for the minimum order (200 pieces): 10 days")
    assert (b["transit_days_min"], b["shipping_per_kg_usd"], b["ships_to"]) == (None, None, None)   # not on this page: None


def test_alibaba_shipping_quote_and_minimum_as_the_pages_state_them():
    """The PRODUCT-SEARCH-E2E probe page (tests/fixtures/agent_reach/, a real Jina read of 2026-11-01) quotes shipping for the
    minimum order ("Shipping fee: **$83.15**~~$103.15~~ for 55 pieces": the struck-through old price is not the quote)."""
    page = (ROOT / "tests/fixtures/agent_reach/alibaba_jina_product_page.txt").read_text(encoding="utf-8")
    (rec,) = AR.parse_report_source("alibaba", page, kind="page")["records"]
    assert (rec["shipping_quote_usd"], rec["shipping_quote_qty"], rec["shipping_per_kg_usd"], rec["shipping_min_kg"]) == (83.15, 55, None, None)
    assert (rec["delivery_estimate_text"], rec["moq"], rec["unit_price_at_moq"]) == ("Guaranteed delivery: Nov 13 - Dec 08", 55, 0.18)
    split = _by(_parse("alibaba", "exa_alibaba_brush.out")["records"], "product_id")["1601292437894"]
    assert (split["shipping_quote_usd"], split["shipping_quote_qty"]) == (47.9, 10)          # "$47.90 $67.90 for 10 pieces": the first
    for line, kg, money in (("Shipping fee: Starts at US$1.20/kg (min. 21 kg)", 21.0, None),
                            ("Shipping fee: US$2.10/kg, minimum charge US$35", None, 35.0),
                            ("Shipping fee: $3/kg", None, None)):
        raw = ("Title: Lamp - Buy  Product on Alibaba.com\n\nURL Source: https://www.alibaba.com/product-detail/Lamp_1600000000001.html\n\n"
               f"Markdown Content:\n# Lamp\n\n**$5.00**\n\n10-99 pieces\n\n{line}\n\nMOQ: 10 pieces\n{SUPPLIER_TEXT}")
        (one,) = AR.parse_report_source("alibaba", raw, kind="page")["records"]
        assert (one["shipping_min_kg"], one["shipping_min_charge_usd"], one["moq"]) == (kg, money, 10), line


# ─────────────────────────────────────────────────────────── blocks, walls, bounds
BLOCKED = [("alibaba", "jina_alibaba_B.out"), ("alibaba", "jina_alibaba_C.out"),
           *[("reddit", f"jina_reddit_{n}.out") for n in ("A_json", "A_old", "A_old_browser", "A_www", "B_old", "B_oldjson", "B_www")],
           *[("ebay", f"jina_ebay_{n}.out") for n in ("item_A", "item_B", "search", "search_browser", "sold")]]


@pytest.mark.parametrize("source,name", BLOCKED)
def test_a_page_the_site_refused_is_blocked_and_admits_nothing(source, name):
    got = AR.parse_report_source(source, _fx(name), kind="page")
    assert (got["status"], got["records"], got["next_targets"]) == ("BLOCKED", [], [])
    assert [r["code"] for r in got["refused"]] == ["BLOCKED"] and "HTTP 403" in got["refused"][0]["why"]


def test_a_block_page_without_the_warning_line_is_still_blocked_and_a_check_page_is_human_check():
    for title, words in (("Blocked", "## whoa there, pardner!\n\nYour request has been blocked due to a network policy."),
                         ("", "You've been blocked by network security."), ("Access Denied", "You don't have permission to access this.")):
        raw = f"Title: {title}\n\nURL Source: https://www.amazon.com/dp/B00ZGPI3OY\n\nMarkdown Content:\n{words}\n"
        got = AR.parse_report_source("amazon", raw, kind="page")
        assert (got["status"], [r["code"] for r in got["refused"]]) == ("BLOCKED", ["BLOCKED"]), title
    check = ("Title: Amazon.com\n\nURL Source: https://www.amazon.com/dp/B00ZGPI3OY\n\nMarkdown Content:\nEnter the characters you see below\n\n"
             "Sorry, we just need to make sure you're not a robot.")
    got = AR.parse_report_source("amazon", check, kind="page")
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("HUMAN_CHECK", ["HUMAN_CHECK"])    # a check page (plan §4.1)
    slider = ("Title: Captcha Interception\n\nURL Source: https://www.alibaba.com/product-detail/Lamp_1600000000001.html\n\n"
              "Markdown Content:\nPlease slide to verify\n")
    got = AR.parse_report_source("alibaba", slider, kind="page")
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("HUMAN_CHECK", ["HUMAN_CHECK"])


def test_what_is_not_one_readers_output_is_refused_by_name_never_raised():
    assert _parse("reddit", "exa_reddit_candle.out")["status"] == "EMPTY"            # the 429 run printed nothing
    err = "[mcporter] exa.web_search_exa responded with HTTP 429 (Error POSTing to endpoint: rate limit)"
    got = AR.parse_report_source("reddit", err, kind="search")
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("UNRECOGNISED", ["UNRECOGNISED_OUTPUT"])
    got = AR.parse_report_source("amazon", "x" * (AR.MAX_REPORT_BYTES + 1), kind="search")
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("UNRECOGNISED", ["OUTPUT_TOO_LARGE"])
    got = AR.parse_report_source("reddit", _fx("exa_reddit_brush.out"), kind="page")      # an Exa search sent as a page read
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("UNRECOGNISED", ["KIND_MISMATCH"])
    got = AR.parse_report_source("alibaba", _fx("jina_alibaba_A.out"), kind="search")      # a product page sent as a search
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("UNRECOGNISED", ["KIND_MISMATCH"])
    off = AR.parse_report_source("reddit", _fx("exa_amazon_brush.out"), kind="search")     # another source's output
    assert (off["status"], {r["code"] for r in off["refused"]}) == ("EMPTY", {"OFF_SITE"})


# ─────────────────────────────────────────────────────────── review round R2 (2026-11-02): regressions
def test_r2_2_a_tier_priced_as_a_range_is_costed_at_its_high_end():
    """Contract C3: `unit_price` is a range's HIGH end, `unit_price_low` its low end (only for a range)."""
    raw = ("Title: Test Self Cleaning Slicker Brush\nURL: https://www.alibaba.com/product-detail/Test-Self-Cleaning-Slicker-Brush_1600000000001.html\n"
           "Published: N/A\nAuthor: N/A\nHighlights:\n# Test Self Cleaning Slicker Brush\n\n $1.20 - 1.50 \n\n 100-499 pieces \n\n $1.10 - 1.40 \n\n"
           " ≥500 pieces \n\nSingle gross weight\n\n0.200 kg\n")
    (rec,) = AR.parse_report_source("alibaba", raw, kind="search")["records"]
    assert rec["price_tiers"] == [{"qty_min": 100, "qty_max": 499, "unit_price": 1.5, "unit_price_low": 1.2},
                                  {"qty_min": 500, "qty_max": None, "unit_price": 1.4, "unit_price_low": 1.1}]
    assert (rec["moq"], rec["unit_price_at_moq"], rec["price_min"], rec["price_max"]) == (100, 1.5, 1.1, 1.5)
    single = _by(_parse("alibaba", "exa_alibaba_brush.out")["records"], "product_id")["1600824724683"]
    assert all("unit_price_low" not in t for t in single["price_tiers"])           # a single price has no low end


def test_r2_3_a_sponsored_ads_numbers_never_attach_to_the_result_above_it():
    raw = _fx("jina_amazon_search_links.out")
    whole = _by(AR.parse_report_source("amazon", raw, kind="search")["records"], "asin")["B0077JOOLI"]
    assert (whole["price_usd"], whole["rating"], whole["ratings_count"], whole["bought_past_month"]) == (12.59, 4.7, 386, 50)
    lines = raw.split("\n")                                     # as for a "See options" result: no price, rating or "bought" of its own
    k = next(i for i, line in enumerate(lines) if line.startswith("## [") and "/dp/B0077JOOLI/" in line)
    end = next(i for i in range(k + 1, len(lines)) if lines[i].startswith("Add to cart"))
    own = {i for i in range(k + 1, end) if re.search(r"out of 5 stars|^\[\(\d|bought in past month|^Price, product page", lines[i])}
    assert len(own) == 4 and any(lines[i].startswith("Sponsored## [Aumuca") for i in range(end, end + 12))
    cut = "\n".join(line for i, line in enumerate(lines) if i not in own)
    weaver = _by(AR.parse_report_source("amazon", cut, kind="search")["records"], "asin")["B0077JOOLI"]
    assert (weaver["price_usd"], weaver["rating"], weaver["ratings_count"], weaver["bought_past_month"]) == (None, None, None, None)
    assert weaver["delivery_text"].startswith("Join Prime to get FREE delivery Thu, Nov 5")          # its own lines stay


def test_r2_4_the_lead_time_is_the_row_that_holds_the_moq_and_words_there_are_unknown():
    def page(table: str, moq: str = "MOQ: 200 pieces") -> dict:
        raw = ("Title: Lamp - Buy  Product on Alibaba.com\n\nURL Source: https://www.alibaba.com/product-detail/Lamp_1600000000001.html\n\n"
               f"Markdown Content:\n# Lamp\n\n**$5.00**\n\n{moq}\n\nDelivery Time\n\n7-15 Days\n\n## Lead time\n\n{table}\n{SUPPLIER_TEXT}")
        (rec,) = AR.parse_report_source("alibaba", raw, kind="page")["records"]
        return rec
    rec = page("Quantity (pieces)1 - 100 101 - 500> 500\nLead time (days)7 To be negotiated 30")
    assert (rec["lead_time_days_min"], rec["lead_time_days_max"], rec["lead_time_basis"]) == (None, None, None)   # never the 7 of 1-100
    assert rec["lead_time_text"].startswith("lead time 1-100 pieces: 7 days; 101-500 pieces: to be negotiated; >500 pieces: 30 days")
    assert "for the minimum order (200 pieces): unknown" in rec["lead_time_text"]
    rec = page("| Quantity (pieces) | 1 - 100 | 101 - 500 | > 500 |\n| --- | --- | --- | --- |\n| Lead time (days) | Negotiable | 12 | 20 |")
    assert (rec["lead_time_days_min"], [r["days"] for r in rec["lead_time_table"]]) == (12, [None, 12, 20])     # a word keeps its column
    rec = page("Quantity (pieces)1 - 100> 100\nLead time (days)7 15", moq="Minimum order: see seller")
    assert (rec["moq"], rec["lead_time_days_min"]) == (None, None) and "the minimum order is not stated" in rec["lead_time_text"]
    rec = page("", moq="MOQ: 200 pieces")                                   # no table: the "Delivery Time" attribute
    assert (rec["lead_time_days_min"], rec["lead_time_days_max"], rec["lead_time_basis"]) == (7, 15, "supplier_attribute")


def test_r2_7_reddit_threads_are_judged_by_their_titles_key_product_words():
    threads = _parse("reddit", "exa_reddit_brush.out", terms=["self cleaning slicker brush"])["records"]
    brush = _by(threads, "title")                                   # (two threads share the title "Slicker Brush Recommendations?")
    shout = brush["I have to give a shout-out to this cheap slicker brush. The Nice Paws self clearing brush is definitely my go-to."]
    assert (shout["score"], shout["published_at"][:10], shout["relevant"]) == (81, "2026-03-10", True)    # "self clearing": still the product
    assert {t for t, r in brush.items() if r["relevant"] is False} == {"Best deshedding tool for double coat?",
                                                                      "Thoughts on this vacuum brush thing I saw"}
    assert sum(t["relevant"] for t in threads) == 6 and len(threads) == 8
    candle = _by(_parse("reddit", "exa_reddit_candle_r2.out", terms=CANDLE)["records"], "title")
    assert {t for t, r in candle.items() if r["relevant"] is False} == {"Which type of candle lasts longer? Jar candles or wax melts?"}
    for title, relevant in (("Self Cleaning Oven tips : r/test", False), ("Slicker brush or rake? : r/test", True), ("Help me choose : r/test", False)):
        raw = f"Title: {title}\nURL: https://www.reddit.com/r/test/comments/abc123/t/\nPublished: N/A\nAuthor: N/A\nHighlights:\n**u/a** · 3 points · " \
              "March 5, 2021 at 4:29 PM UTC\n> I love my self cleaning slicker brush\n"
        (thread,) = AR.parse_report_source("reddit", raw, kind="search", candidate_terms=["self cleaning slicker brush"])["records"]
        assert thread["relevant"] is relevant, title                   # a comment's mention never makes the thread about it


def test_r2_8_an_amazon_robot_check_is_a_human_check_not_a_listing_titled_amazon_com():
    robot = ("Title: Amazon.com\n\nURL Source: https://www.amazon.com/dp/B00ZGPI3OY\n\nMarkdown Content:\nEnter the characters you see below\n"
             "----------------------------------\n\nSorry, we just need to make sure you're not a robot. For best results, please make sure "
             "your browser is accepting cookies.\n\n#### Type the characters you see in this image:\n\n![Image 1](https://images-na.ssl-images-amazon"
             ".com/captcha/x/Captcha_abc.jpg)\n\n[Try different image](https://www.amazon.com/errors/validateCaptcha)\n\nContinue shopping\n\n"
             "[Conditions of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=508088)[Privacy Policy](https://www.amazon.com/gp/"
             "help/customer/display.html?nodeId=468496)\n\n© 1996-2025, Amazon.com, Inc. or its affiliates\n")
    assert CH.looks_like_challenge(robot) is None                        # the footer outweighs the detector's budget: the bug
    got = AR.parse_report_source("amazon", robot, kind="page")
    assert (got["status"], got["records"], [r["code"] for r in got["refused"]]) == ("HUMAN_CHECK", [], ["HUMAN_CHECK"])
    assert "robot check" in got["refused"][0]["why"] and "Never solve, skip or work around it" in got["refused"][0]["why"]
    behind = robot.replace("\n\nMarkdown Content:", "\n\nWarning: Target URL returned error 503: Service Unavailable\n\nMarkdown Content:")
    got = AR.parse_report_source("amazon", behind, kind="page")                      # served with a 503: still a check page
    assert (got["status"], [r["code"] for r in got["refused"]]) == ("HUMAN_CHECK", ["HUMAN_CHECK"])


# ─────────────────────────────────────────────────────────── review round R2 verify (2026-11-02): head terms, one definition
OFF_TOPIC = {"brush": ["Cleaning my paint brush", "Brush cleaning tips for makeup brushes"],
             "candle": ["Warmer lamp for my reptile tank", "Best desk lamp for a warmer light?"]}


def _thread(title: str, comment: str = "I love it") -> str:
    return (f"Title: {title} : r/test\nURL: https://www.reddit.com/r/test/comments/abc123/t/\nPublished: N/A\nAuthor: N/A\nHighlights:\n"
            f"**u/a** · 3 points · March 5, 2021 at 4:29 PM UTC\n> {comment}\n")


@pytest.mark.parametrize("term,fixture,kept,family", [
    ("slicker brush for long hair dogs", "exa_reddit_brush.out", 5, "brush"),          # head: slicker brush (was 0 of 8)
    ("self-cleaning slicker brush dogs cats", "exa_reddit_brush.out", 6, "brush"),     # a title-derived term (was 1 of 8)
    ("self cleaning slicker brush", "exa_reddit_brush.out", 6, "brush"),
    ("candle warmer lamp with timer", "exa_reddit_candle_r2.out", 7, "candle"),       # head: candle warmer lamp (was 2 of 8)
    ("candle warmer lamp timer jar", "exa_reddit_candle_r2.out", 7, "candle"),        # hypotheses' title-derived term
])
def test_r2v_reddit_threads_are_judged_on_the_terms_head_words(term, fixture, kept, family):
    threads = _parse("reddit", fixture, terms=[term])["records"]
    assert sum(t["relevant"] for t in threads) == kept and all(t["term_hits"] == [term] for t in threads if t["relevant"])
    if family == "brush":
        shout = next(t for t in threads if t["score"] == 81)
        assert (shout["published_at"][:10], shout["relevant"]) == ("2026-03-10", True)
        assert {t["title"] for t in threads if not t["relevant"]} >= {"Best deshedding tool for double coat?",
                                                                       "Thoughts on this vacuum brush thing I saw"}
    else:
        assert {t["title"] for t in threads if not t["relevant"]} == {"Which type of candle lasts longer? Jar candles or wax melts?"}
    for title in OFF_TOPIC[family]:                                         # the reviewer's off-topic titles
        (thread,) = AR.parse_report_source("reddit", _thread(title, f"is a {term} better?"), kind="search", candidate_terms=[term])["records"]
        assert thread["relevant"] is False, (term, title)                   # a comment naming the product never makes it relevant


def test_r2v_one_head_term_definition_and_listings_hold_every_head_word_as_a_whole_word():
    from polymath_shared.product_search import host_data as HD
    assert (HD.head_terms, HD.missing_terms) == (AR.head_terms, AR.missing_terms)             # ONE definition: CJ, eBay and the parsers
    assert AR.head_terms("candle warmer lamp with timer") == ["candle", "warmer", "lamp"]
    assert AR.head_terms("slicker brush for long hair dogs") == ["slicker", "brush"]
    lamps = _parse("amazon", "exa_amazon_candle.out", terms=["candle warmer lamp with timer"])["records"]
    assert sum(r["relevant"] for r in lamps) == 7                                              # every listing names a candle warmer lamp
    raw = "".join(f"Title: {title}\nURL: https://www.amazon.com/dp/{asin}\nPublished: N/A\nAuthor: N/A\nHighlights:\n# {title}\n"
                  "Price: 9.99 USD.\n\n---\n\n" for title, asin in (("Desk Clamp Phone Holder", "B000000001"),
                                                                     ("LED Desk Lamp with Clamp", "B000000002"),
                                                                     ("Touchscreen Desk Lamps", "B000000003")))
    got = {r["asin"]: r["relevant"] for r in AR.parse_report_source("amazon", raw, kind="search", candidate_terms=["desk lamp"])["records"]}
    assert got == {"B000000001": False, "B000000002": True, "B000000003": True}               # "Clamp" never holds "lamp"
    joined = AR.parse_report_source("amazon", raw, kind="search", candidate_terms=["touch screen desk lamp"])["records"]
    assert [r["asin"] for r in joined if r["relevant"]] == ["B000000003"]                     # "touch screen" = "Touchscreen"


def test_r2v_n1_the_robot_check_wording_counts_only_as_a_whole_line_of_a_jina_page():
    """N1: an Exa Reddit comment that QUOTES the wording is content; so is a Jina page that uses it inside a sentence."""
    exa = _thread("Slicker Brush Recommendations?", "the seller page made me type the characters you see in this image twice")
    got = AR.parse_report_source("reddit", exa, kind="search", candidate_terms=["slicker brush"])
    assert (got["status"], got["refused"], len(got["records"])) == ("OK", [], 1)
    page = _fx("jina_amazon_product.out").replace("200+ bought in past month",
                                                  "200+ bought in past month\n\nIt asked me to enter the characters you see below, then it worked.")
    got = AR.parse_report_source("amazon", page, kind="page")
    assert (got["status"], got["records"][0]["price_usd"]) == ("OK", 16.95)
    line = page.replace("It asked me to enter the characters you see below, then it worked.", "Enter the characters you see below")
    assert AR.parse_report_source("amazon", line, kind="page")["status"] == "OK"               # a 40 KB product page is no check page
    short = ("Title: Amazon.com\n\nURL Source: https://www.amazon.com/dp/B00ZGPI3OY\n\nMarkdown Content:\nEnter the characters you see "
             "below\n\nContinue shopping\n")
    assert AR.parse_report_source("amazon", short, kind="page")["status"] == "HUMAN_CHECK"


# ─────────────────────────────────────────────────────────── live run 2026-11-02 (rpt_00c434852e89c27f80de987e)
def test_live_amazon_search_page_in_the_plain_text_layout_lists_its_products():
    """jina_amazon_search_plain.out: a fresh read of packet r1-c2-amazon-2's URL with the fetch script's exact command (143 KB).
    Jina printed the PLAIN-TEXT layout: plain lines per result, the products' links only in the "Links/Buttons:" summary, whose
    text is each result's ratings count ("(44.5K)"). The markdown layout (jina_amazon_search_links.out) keeps its 48 listings."""
    raw = _fx("jina_amazon_search_plain.out")
    got = AR.parse_report_source("amazon", raw, kind="search", candidate_terms=["pet water fountain"])
    recs = got["records"]
    assert (got["status"], len(recs), got["refused"]) == ("OK", 43, [])                # was EMPTY / NO_PRODUCT_LINKS
    by = _by(recs, "asin")
    veken = by["B0G34DKXPL"]                                       # "- [(6K)](https://www.amazon.com/Veken-Innovation-…/dp/B0G34DKXPL/ref=sr_1_40…)"
    assert {k: veken[k] for k in ("url", "price_usd", "list_price_usd", "rating", "ratings_count", "bought_past_month", "prime")} == {
        "url": "https://www.amazon.com/dp/B0G34DKXPL", "price_usd": 27.99, "list_price_usd": 29.99, "rating": 4.3, "ratings_count": 6000,
        "bought_past_month": 30000, "prime": True}
    assert veken["title"].startswith("Veken Innovation Award Winner Stainless Steel Cat Water Fountain, 108oz, C1 Automatic Pet Fountain")
    twin = by["B0F9FC7JYD"]                                        # two results show "(1.6K)": its URL's name words pick its own
    assert "Wastewater Separation" in twin["title"] and (twin["price_usd"], twin["ratings_count"]) == (49.99, 1600)
    assert {"B0GX5X4BNF", "B0H9GVML2X", "B0F2T6CXKT", "B0GHQBCFVN", "B0H38KJ35D"} <= set(by)  # sponsored /sspa/click: url= names the ASIN
    assert "B0DVBL912R" not in by and "B0GY91BQCP" not in by       # the footer's store card and a click-tracking link are no results
    filled = {k: sum(r[k] is not None for r in recs) for k in ("price_usd", "rating", "ratings_count", "bought_past_month", "delivery_text")}
    assert filled == {"price_usd": 42, "rating": 43, "ratings_count": 43, "bought_past_month": 41, "delivery_text": 42}
    assert sum(r["relevant"] for r in recs) == 41                  # "pet" is held by "Cat" / "Dog" (AUDIENCE); live: n = 1
    assert [t["url"] for t in got["next_targets"]] == [r["url"] for r in recs if r["relevant"]][:AR.MAX_NEXT_TARGETS]
    assert all(t["kind"] == "page" and t["source"] == "amazon" for t in got["next_targets"])
    lines = raw.split("\n")                                         # the Sponsored / next-title boundary: without its own lines the
    k = lines.index("Veken Innovation Award Winner Stainless Steel Cat Water Fountain, 108oz, C1")    # result keeps no number of
    cut = lines[:k + 5] + lines[k + 8:]                             # the next result's (drops "30K+ bought…", "Price, product page", "$27.99")
    assert [x.strip() for x in lines[k + 5:k + 8]] == ["30K+ bought in past month", "Price, product page", "$27.99"]
    alone = _by(AR.parse_report_source("amazon", "\n".join(cut), kind="search")["records"], "asin")["B0G34DKXPL"]
    assert (alone["price_usd"], alone["bought_past_month"], alone["rating"]) == (None, None, 4.3)


def test_live_alibaba_captcha_interception_pages_are_a_human_check():
    """Five 1 KB round-2 reads titled "Captcha Interception" were stored as listings: the challenge detector alone lets such a
    page through once its other lines outweigh its budget. A short Jina page with that whole title is HUMAN_CHECK."""
    page = ("Title: Captcha Interception\n\nURL Source: https://www.alibaba.com/product-detail/Wholesale-Custom-Logo-Self-Cleaning-Slicker_"
            "1601292437894.html\n\nMarkdown Content:\nAlibaba.com\n\nWe could not show this page to you right now because of the way your "
            "request reached us.\n\nIf you keep seeing this page, contact customer service with the reference below.\n\n"
            "Reference: 0b1c2d3e4f5a6b7c8d9e\n\nHelp Center | Privacy Policy | Terms of Use\n")
    assert CH.looks_like_challenge(page) is None                   # the live bug: the detector alone admits it
    got = AR.parse_report_source("alibaba", page, kind="page")
    assert (got["status"], got["records"], [r["code"] for r in got["refused"]]) == ("HUMAN_CHECK", [], ["HUMAN_CHECK"])
    assert "Captcha Interception" in got["refused"][0]["why"]
    behind = page.replace("\n\nMarkdown Content:", "\n\nWarning: Target URL returned error 403: Forbidden\n\nMarkdown Content:")
    assert AR.parse_report_source("alibaba", behind, kind="page")["status"] == "HUMAN_CHECK"
    listing = ("Title: Captcha Interception Practice Kit - Buy  Product on Alibaba.com\n\nURL Source: https://www.alibaba.com/product-detail/"
               "Kit_1600000000009.html\n\nMarkdown Content:\n# Captcha Interception Practice Kit\n\n**$5.00**\n\n10-99 pieces\n\n"
               "Our kit teaches how a captcha interception page works.\n" + SUPPLIER_TEXT)
    kit = AR.parse_report_source("alibaba", listing, kind="page")   # a listing that merely mentions it is content
    assert (kit["status"], kit["records"][0]["unit_price_at_moq"]) == ("OK", 5.0)


def test_audience_words_are_held_by_their_group_and_nothing_else():
    assert AR.AUDIENCE == {"pet": ("pet", "cat", "kitten", "dog", "puppy")}
    assert AR.missing_terms("Automatic Cat Feeder", AR.head_terms("automatic pet feeder")) == []
    assert AR.missing_terms("Puppies Slow Feeder Bowl", AR.head_terms("pets slow feeder bowl")) == []
    assert AR.missing_terms("Desk Clamp Phone Holder", AR.head_terms("desk lamp")) == ["lamp"]
    assert AR.missing_terms("Pet Hair Remover", AR.head_terms("dog bed")) == ["dog", "bed"]
    assert AR.missing_terms("Dog Water Fountain", AR.head_terms("cat water fountain")) == ["cat"]   # one direction only
    assert AR.missing_terms("Petal Desk Lamp", AR.head_terms("pet lamp")) == ["pet"]               # whole words: "Petal" is no pet
    (thread,) = AR.parse_report_source("reddit", _thread("Best cat water fountain?"), kind="search",
                                       candidate_terms=["pet water fountain"])["records"]
    assert thread["relevant"] is True                              # the Reddit title rule reads "pet" the same way


def test_a_failed_reader_read_is_empty_reader_failed_never_no_product_links():
    """Live 2026-11-02 (rpt_64ad6f4a34dccc5d915547ab, r1-c3-amazon-2): a 252-byte Jina read of an Amazon search page was stored
    EMPTY / NO_PRODUCT_LINKS with the hint to add the links header the fetch plan already sends. Jina's own error JSON, or a Jina
    read with no page in it (under READER_MIN_BYTES, or no content), is EMPTY / READER_FAILED with a plain reason."""
    error = ('{"data":null,"code":422,"name":"AssertionFailureError","status":42206,"message":"Failed to goto https://www.amazon.com/s'
             '?k=automatic+pet+feeder: net::ERR_ABORTED","readableMessage":"AssertionFailureError: Failed to goto"}')
    bare = "Title: Amazon.com : automatic pet feeder\n\nURL Source: https://www.amazon.com/s?k=automatic+pet+feeder\n\nMarkdown Content:\n"
    tiny = bare + "Loading...\n"
    for raw, detail in ((error, "its own error 422 AssertionFailureError"), (bare, "a title and a URL, no page"),
                        (tiny, "a title and a URL, no page")):
        got = AR.parse_report_source("amazon", raw, kind="search")
        assert (got["status"], got["records"], [r["code"] for r in got["refused"]]) == ("EMPTY", [], ["READER_FAILED"])
        assert got["refused"][0]["why"] == (f"the reader returned only {len(raw.encode())} bytes ({detail}): a failed read, not a page; "
                                            "run the round's script once more")
        assert "X-With-Links-Summary" not in got["refused"][0]["why"]
    page = AR.parse_report_source("alibaba", tiny.replace("amazon.com/s?k=automatic+pet+feeder",
                                                          "alibaba.com/product-detail/Feeder_1600000000001.html"), kind="page")
    assert [r["code"] for r in page["refused"]] == ["READER_FAILED"]                    # any source's Jina page read
    assert AR.parse_report_source("amazon", error.replace('"code":422', '"code":200'), kind="search")["status"] == "UNRECOGNISED"
    # the recorded pages are unaffected: block and check pages keep their codes, real pages their records, an empty Exa upload
    # EMPTY_OUTPUT; the one recorded failed read is Jina's cached snapshot (test below)
    failed = set()
    for path in FIX.iterdir():
        source = next(s for s in AR.REPORT_SOURCES if s in path.name)
        for kind in AR.REPORT_KINDS:
            got = AR.parse_report_source(source, path.read_text(encoding="utf-8"), kind=kind)
            if "READER_FAILED" in {r["code"] for r in got["refused"]}:
                failed.add((path.name, kind))
    assert failed == {("jina_amazon_search_snapshot.out", "search"), ("jina_amazon_search_snapshot.out", "page")}
    assert [r["code"] for r in _parse("reddit", "exa_reddit_candle.out")["refused"]] == ["EMPTY_OUTPUT"]
    assert [r["code"] for r in _parse("ebay", "jina_ebay_item_A.out", kind="page")["refused"]] == ["BLOCKED"]   # 261 bytes, still BLOCKED
    assert _parse("amazon", "jina_amazon_search.out")["refused"][0]["code"] == "NO_PRODUCT_LINKS"                # a real page without links


def test_jinas_cached_snapshot_of_a_page_that_had_not_loaded_is_reader_failed_at_any_size():
    """Live 2026-11-02 (amz_feeder): Jina answered an Amazon search read with its cached snapshot of a page that had not loaded,
    "This page maybe not yet fully loaded" and "This is a cached snapshot" over an empty Markdown Content. That is a failed read
    whatever its byte count (READER_FAILED, never NO_PRODUCT_LINKS and its links-header hint); the same two warnings over a real
    page change nothing."""
    raw = _fx("jina_amazon_search_snapshot.out")
    warnings = [line for line in raw.splitlines() if line.startswith("Warning: ")]
    assert len(raw.encode()) == 346 and [w.split(",")[0] for w in warnings] == [
        "Warning: This page maybe not yet fully loaded", "Warning: This is a cached snapshot of the original page"]
    padded = raw.replace("This page does not seem to contain any buttons/links.\n",
                         "".join(f"- [Sign in](https://www.amazon.com/ap/signin?n={n})\n" for n in range(12)))
    assert len(padded.encode()) > AR.READER_MIN_BYTES
    for text, kind in ((raw, "search"), (padded, "search"), (raw, "page")):
        got = AR.parse_report_source("amazon", text, kind=kind, candidate_terms=["automatic pet feeder"])
        assert (got["status"], got["records"], got["next_targets"]) == ("EMPTY", [], [])
        assert got["refused"] == [{"url": "https://www.amazon.com/s?k=automatic+pet+feeder", "code": "READER_FAILED", "why": (
            f"the reader returned its cached snapshot of a page that had not loaded ({len(text.encode())} bytes, an empty Markdown "
            "Content): a failed read, not a page; run the round's script once more")}]
    page = padded.replace("https://www.amazon.com/s?k=automatic+pet+feeder", "https://www.alibaba.com/product-detail/Feeder_1600000000001.html")
    assert [r["code"] for r in AR.parse_report_source("alibaba", page, kind="page")["refused"]] == ["READER_FAILED"]   # any Jina page
    # the same two warnings over a real page (the plain-text search page): parsed exactly as without them
    plain = _fx("jina_amazon_search_plain.out")
    head, rest = plain.split("\nMarkdown Content:\n", 1)
    warned = head + "\n" + "\n".join(warnings) + "\n\nMarkdown Content:\n" + rest
    before = AR.parse_report_source("amazon", plain, kind="search", candidate_terms=["pet water fountain"])
    after = AR.parse_report_source("amazon", warned, kind="search", candidate_terms=["pet water fountain"])
    assert after["status"] == "OK" and len(after["records"]) > 10 and "READER_FAILED" not in {r["code"] for r in after["refused"]}
    assert (after["records"], after["next_targets"], after["refused"]) == (before["records"], before["next_targets"], before["refused"])


def test_relevance_is_judged_only_against_the_candidates_terms():
    plain = _parse("amazon", "exa_amazon_candle.out")
    assert all(r["relevant"] is None and r["term_hits"] == [] for r in plain["records"])
    wrong = _parse("amazon", "exa_amazon_candle.out", terms=BRUSH)
    assert all(r["relevant"] is False for r in wrong["records"])
    both = _parse("amazon", "exa_amazon_candle.out", terms=[*BRUSH, "candle lamp"])
    assert all(r["term_hits"] == ["candle lamp"] for r in both["records"])


def test_the_parser_is_deterministic():
    for source, name, kind in (("reddit", "exa_reddit_brush.out", "search"), ("amazon", "jina_amazon_search_links.out", "search"),
                               ("alibaba", "jina_alibaba_A.out", "page"), ("ebay", "exa_ebay_brush.out", "search")):
        assert _parse(source, name, kind, BRUSH) == _parse(source, name, kind, BRUSH)
