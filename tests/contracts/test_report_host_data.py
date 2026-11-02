"""PRODUCT-DECISION-REPORT-V1 §4.3 (slice B2): the report's HOST DATA, `host_data.collect`, for every user.
  * CJ through the supplier tools AS THE CALLER'S PRINCIPAL (fair use applies to friends): one search per candidate, the relevance
    filter (a title must hold every head term; near misses kept in `relevance.dropped`), at most 3 products, the best match read in
    full, its cheapest variant quoted from CN and from US (CJ's "a-b" days parsed into ints), `us_stock_confirmed` only when CJ
    states US stock; at most 4 CJ calls a candidate;
  * eBay comparables through the Browse API when the keyset is set, EBAY_NOT_CONFIGURED otherwise (never an error), the breaker
    after an auth failure;
  * per-call receipts, typed statuses, CJ's own Agent Reach `fallback` carried through, one candidate's failure never stopping the
    others, a fair-use refusal waited out once.
The CJ answers in tests/fixtures/product_report_host/cj*.json are RECORDED: the supplier tools' real answers of 2026-11-02 (15:34-15:35
UTC; CJ re-enabled, "candle warmer" near misses, the slicker brush's details and its freight CN->US and US->US). The eBay answer is
SYNTHETIC (its file name and `_synthetic` key say so). Fake HTTP only (httpx.MockTransport), fake clocks: no call reaches CJ or eBay;
no browser, no database."""
from __future__ import annotations

import copy
import functools
import hashlib
import itertools
import json
import pathlib
import sys
from datetime import datetime

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import cj_api as CJ
from polymath_shared.acquisition import ebay_api as EB
from polymath_shared.acquisition import supplier as SUP
from polymath_shared.acquisition.service import AcquisitionRefused
from polymath_shared.product_search import host_data as HD

FX = ROOT / "tests" / "fixtures" / "product_report_host"
BRUSH_PID = "AEF754AF-2F7F-424E-897C-2BF7DF141B30"
GREEN, YELLOW = "6ACD9F80-DE0B-4A16-8292-392385BF19E6", "F44F78AC-0E35-47DB-8F25-B8C2CFA0F53A"
CANDIDATES = [{"candidate_id": "c1", "title": "Candle warmer lamp", "search_terms": ["candle warmer"]},
              {"candidate_id": "c2", "title": "Self-cleaning slicker brush", "search_terms": ["self cleaning slicker brush"]},
              {"candidate_id": "c3", "title": "Candle warmer lamp", "search_terms": ["candle warmer lamp"]}]
SEARCHES = {"candle warmer": "cj1_search_candle.json", "self cleaning slicker brush": "cj2_search_brush.json",
            "candle warmer lamp": "cj3_search_candle_lamp.json"}
_SEQ = itertools.count()


def _load(name: str) -> dict:
    return json.loads((FX / name).read_text())


class Recorded:
    """The supplier tools answering with the RECORDED answers; `override` replaces an answer (a dict, an exception, or a callable
    taking the call's keywords) per (tool, key) where key is the query / product id / origin country. Every call is kept."""

    def __init__(self, override=None):
        self.calls: list[tuple[str, dict]] = []
        self.override = override or {}

    def _answer(self, tool, key, default, kw):
        self.calls.append((tool, kw))
        got = self.override.get((tool, key), default)
        got = got(kw) if callable(got) and not isinstance(got, Exception) else got
        if isinstance(got, Exception):
            raise got
        return copy.deepcopy(got)

    def search(self, **kw):
        return self._answer("search", kw["query"], _load(SEARCHES[kw["query"]]) if kw["query"] in SEARCHES else
                            {"status": "EMPTY", "reason_code": "CJ_EMPTY", "items": [], "sources": [], "fallback": None}, kw)

    def product(self, **kw):
        return self._answer("product", kw["product_id"], _load("cj4_product_brush.json") if kw["product_id"] == BRUSH_PID else
                            {"status": "NOT_FOUND", "reason_code": None, "product": None, "variants": []}, kw)

    def freight(self, **kw):
        return self._answer("freight", kw["from_country"],
                            _load("cj5_freight_cn_us.json" if kw["from_country"] == "CN" else "cj7_freight_us_us.json"), kw)


class Clock:
    def __init__(self):
        self.t, self.wall_t = 0.0, 1_790_000_000.0
        self.sleeps: list[float] = []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s
        self.wall_t += s

    def clock(self):
        return self.t

    def wall(self):
        return self.wall_t


def _collect(fns=None, candidates=None, **kw):
    kw.setdefault("env", {})
    kw.setdefault("principal_id", "prn_fred")
    return HD.collect(CANDIDATES if candidates is None else candidates, supplier_fns=fns or Recorded(), **kw)


@pytest.fixture(autouse=True)
def _fresh_fair_use(monkeypatch):
    monkeypatch.setattr(SUP, "FAIR_USE", SUP.FairUse())


@pytest.fixture(autouse=True)
def _fresh_ebay_daily(monkeypatch):
    monkeypatch.setattr(HD, "EBAY_DAILY", HD.EbayDaily())


def test_the_code_under_test_is_this_checkout():
    for mod in (HD, EB, SUP, CJ):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── the CJ path on the recorded answers
def test_the_cj_path_on_the_recorded_answers():
    fns = Recorded()
    out = _collect(fns)
    json.dumps(out)                                                         # storable as it is (jsonb)
    assert set(out) >= {"cj", "ebay", "receipts"} and out["contract"] == HD.CONTRACT and out["ship_to"] == "US"
    brush = out["cj"]["c2"]
    assert (brush["status"], brush["reason_code"], brush["calls"], brush["query"]) == ("OK", None, 4, "self cleaning slicker brush")
    assert brush["relevance"]["head_terms"] == ["self", "cleaning", "slicker", "brush"] and brush["relevance"]["dropped"] == []
    assert [k["product_id"] for k in brush["relevance"]["kept"]] == [BRUSH_PID, "1798640551353528320", "1695048285893316608"]
    top = brush["products"][0]
    assert {k: top[k] for k in ("product_id", "title", "url", "image", "sell_price_usd", "suggested_retail_usd", "weight_g",
                                "us_stock_confirmed", "cheapest_variant_id", "price_basis", "detail_status", "freight_status")} == {
        "product_id": BRUSH_PID, "title": "Pet Self Cleaning Slicker Brush",
        "url": f"https://cjdropshipping.com/product/pet-self-cleaning-slicker-brush-p-{BRUSH_PID}.html",
        "image": "https://cf.cjdropshipping.com/20200220/1540523199930.png", "sell_price_usd": 3.83, "suggested_retail_usd": 34.13,
        "weight_g": 250.0, "us_stock_confirmed": False, "cheapest_variant_id": GREEN, "price_basis": "cheapest_variant",
        "detail_status": "OK", "freight_status": {"CN": "OK", "US": "OK"}}
    assert top["variants"] == [{"variant_id": GREEN, "price_usd": 3.83, "weight_g": 250.0, "options": "Green", "us_stock_units": None},
                               {"variant_id": YELLOW, "price_usd": 3.83, "weight_g": 250.0, "options": "Yellow", "us_stock_units": None}]
    cn, us = top["freight"]["CN"], top["freight"]["US"]
    assert (len(cn), len(us)) == (29, 7)                                    # measured: 29 options CN->US, 7 options US->US
    assert cn[0] == {"carrier": "LuWei Ordinary US", "cost_usd": 7.53, "days_min": 5, "days_max": 11, "days_text": "5-11", "days_unit": None}
    by_carrier = {o["carrier"]: o for o in cn}
    assert by_carrier["CJPacket Ordinary"] == {"carrier": "CJPacket Ordinary", "cost_usd": 7.89, "days_min": 4, "days_max": 9, "days_text": "4-9",
                                               "days_unit": None}
    assert by_carrier["CJPacket Eub Special Line"]["cost_usd"] == 10.16    # CJ's total: postage 9.70 + clearance 0.46
    assert (by_carrier["CJPacket Liquid Line"]["days_min"], by_carrier["CJPacket Liquid Line"]["days_max"]) == (20, 60)
    assert us[0] == {"carrier": "UniUni+", "cost_usd": 7.22, "days_min": 3, "days_max": 8, "days_text": "3-8", "days_unit": None}
    assert all(o["days_unit"] is None for o in cn + us)                    # CJ's recorded text names no unit ("4-9"): C2 null
    for opts in (cn, us):
        assert [o["cost_usd"] for o in opts] == sorted(o["cost_usd"] for o in opts)       # cheapest first
        assert all(isinstance(o["days_min"], int) and isinstance(o["days_max"], int) and o["days_min"] <= o["days_max"] for o in opts)
    for other, price in zip(brush["products"][1:], (2.16, 18.98)):         # kept, not read in full (the 4-call budget)
        assert (other["detail_status"], other["freight_status"], other["variants"], other["sell_price_usd"], other["price_basis"],
                other["us_stock_confirmed"]) == ("NOT_FETCHED", {"CN": "NOT_FETCHED", "US": "NOT_FETCHED"}, [], price, "search_from_price", False)
    for cid, query in (("c1", "candle warmer"), ("c3", "candle warmer lamp")):  # measured near misses: LED candles, lamps
        miss = out["cj"][cid]
        assert (miss["status"], miss["reason_code"], miss["products"], miss["calls"], miss["query"]) == ("NO_MATCH", "CJ_NO_RELEVANT", [], 1, query)
        dropped = miss["relevance"]["dropped"]
        assert len(dropped) == 3 and all(d["why"] == "MISSING_HEAD_TERMS" and d["missing"] == ["warmer"] for d in dropped)
    assert [d["title"] for d in out["cj"]["c1"]["relevance"]["dropped"]][2] == "Solar LED candle light"
    assert [(t, kw["principal_id"]) for t, kw in fns.calls] == [("search", "prn_fred")] * 2 + [("product", "prn_fred")] + \
        [("freight", "prn_fred")] * 2 + [("search", "prn_fred")]            # the principal on every supplier call (fair use)
    assert [kw for t, kw in fns.calls if t == "freight"] == [
        {"principal_id": "prn_fred", "variant_id": GREEN, "country": "US", "quantity": 1, "from_country": "CN"},
        {"principal_id": "prn_fred", "variant_id": GREEN, "country": "US", "quantity": 1, "from_country": "US"}]
    assert [(r["n"], r["source"], r["call"], r["candidate_id"], r["status"], r["rows"]) for r in out["receipts"]] == [
        (1, "cj", "supplier_search", "c1", "PARTIAL", 3), (2, "cj", "supplier_search", "c2", "PARTIAL", 3),
        (3, "cj", "supplier_product", "c2", "OK", 2), (4, "cj", "supplier_freight", "c2", "OK", 29),
        (5, "cj", "supplier_freight", "c2", "OK", 7), (6, "cj", "supplier_search", "c3", "PARTIAL", 3)]
    assert out["receipts"][1]["request"] == {"query": "self cleaning slicker brush", "source": "cj", "limit": HD.CJ_SEARCH_LIMIT}
    assert out["receipts"][1]["retrieved_at"] == "2026-11-02T15:34:40Z"    # CJ's own answer time
    assert out["calls"] == {"cj": 6, "ebay": 0, "fair_use_waited_s": 0.0}
    assert out["reason_codes"] == {"cj": ["CJ_NO_RELEVANT"], "ebay": ["EBAY_NOT_CONFIGURED"]}   # C6: the entries' codes, distinct
    assert out["ebay_configured"] is False and all(e["status"] == "NOT_CONFIGURED" and e["reason_code"] == "EBAY_NOT_CONFIGURED"
                                                    and e["listings"] == [] for e in out["ebay"].values())
    assert any("EBAY_CLIENT_ID" in n for n in out["notes"]) and any("us_stock_confirmed" in n for n in out["notes"])


def test_head_terms_the_relevance_rule_and_the_parsers():
    assert HD.head_terms("self cleaning slicker brush") == ["self", "cleaning", "slicker", "brush"]
    assert HD.head_terms("Self-cleaning slicker brush for long-haired cats") == ["self", "cleaning", "slicker", "brush"]
    assert HD.head_terms("set of 2 LED strip lights with remote") == ["led", "strip", "lights"]
    assert HD.head_terms("candle warmer lamp") == ["candle", "warmer", "lamp"] and HD.head_terms("") == []
    assert HD.missing_terms("Touch Screen Winter Gloves", ["touchscreen", "winter", "gloves"]) == []   # joined spelling
    assert HD.missing_terms("Winter Glove", ["gloves"]) == [] and HD.missing_terms("Candle Warmers", ["candle", "warmer"]) == []
    assert HD.missing_terms("Phone Batteries Pack", ["battery"]) == [] and HD.missing_terms("2 Battery Set", ["batteries"]) == []
    assert HD.missing_terms("Sealed Glass Jar", ["led"]) == ["led"] and HD.missing_terms("12 LEDs strip", ["led"]) == []  # short = a word
    assert HD.missing_terms("Christmas Candle Lights LED", ["candle", "warmer"]) == ["warmer"]
    for text, want in (("4-9", (4, 9)), ("10-23", (10, 23)), ("3", (3, 3)), ("5–11 days", (5, 11)), ("9-4", (4, 9)),
                       ("3-7 business days", (3, 7)), (" 20 - 60 ", (20, 60)), ("", (None, None)), ("about a week", (None, None)),
                       ("0", (None, None)), ("400-500", (None, None)), (None, (None, None)), (True, (None, None)), ("4-9-12", (None, None))):
        assert HD.parse_days(text) == want, text
    assert HD.number_range("US$3.83-16.62") == (3.83, 16.62) and HD.number_range("226.00-1399.00") == (226.0, 1399.0)
    assert HD.number_range("US$1,234.50") == (1234.5, 1234.5) and HD.number_range(7.53) == (7.53, 7.53)
    assert HD.number_range(None) == (None, None) and HD.number_range("n/a") == (None, None) and HD.number_range("1-2-3") == (None, None)
    assert HD.search_term({"title": "Self-cleaning slicker brush for long-haired cats"}) == "self cleaning slicker brush"
    assert HD.search_term({"search_terms": ["x", "  pet hair   remover "], "title": "t"}) == "pet hair remover"
    assert HD.search_term({"search_terms": "lint roller"}) == "lint roller" and HD.search_term({"title": "!!"}) is None


def test_us_stock_is_confirmed_only_when_cj_states_it_for_the_quoted_variant():
    def details(green_stock, yellow_stock, yellow_price="US$3.83"):
        d = _load("cj4_product_brush.json")
        d["variants"][0]["stock"], d["variants"][1]["stock"] = green_stock, yellow_stock
        d["variants"][1]["price_as_listed"] = yellow_price
        return d
    us = [{"country": "US", "total": "25", "cj_warehouse": "25", "factory": "0"}, {"country": "CN", "total": "900", "cj_warehouse": "0", "factory": "900"}]
    cases = [(details(us, []), True, 25), (details([], us, "US$3.95"), False, None),
             (details([{"country": "US", "total": "0", "cj_warehouse": "0", "factory": "0"}], []), False, 0),
             (details([{"country": "CN", "total": "51089", "cj_warehouse": "0", "factory": "51089"}], []), False, None)]
    for answer, confirmed, units in cases:
        out = _collect(Recorded({("product", BRUSH_PID): answer}), candidates=CANDIDATES[1:2])
        top = out["cj"]["c2"]["products"][0]
        assert (top["us_stock_confirmed"], top["variants"][0]["us_stock_units"], top["cheapest_variant_id"]) == (confirmed, units, GREEN)
        assert top["freight_status"] == {"CN": "OK", "US": "OK"}            # the US quote answered in every case: no proof alone
    cheaper_yellow = _collect(Recorded({("product", BRUSH_PID): details([], us, "US$3.10")}), candidates=CANDIDATES[1:2])
    top = cheaper_yellow["cj"]["c2"]["products"][0]
    assert (top["cheapest_variant_id"], top["sell_price_usd"], top["us_stock_confirmed"]) == (YELLOW, 3.10, True)
    assert [v["variant_id"] for v in top["variants"]] == [YELLOW, GREEN]   # cheapest first


# ─────────────────────────────────────────────────────────── failures: typed, carried through, contained
def test_a_cj_failure_is_typed_its_fallback_carried_through_and_the_other_candidates_go_on():
    handoff = {"kind": "AGENT_REACH", "reason_code": "CJ_API_DISABLED", "site": "cjdropshipping.com", "commands": [{"step": 1}]}
    disabled = {"contract": "supplier-tools-v1", "tool": "supplier_search", "status": "UNAVAILABLE", "items": [], "sources": [],
                "reason_code": "CJ_API_DISABLED", "fallback": handoff, "limitations": ["CJ has disabled API access (1600014)"]}
    out = _collect(Recorded({("search", "candle warmer"): RuntimeError("a reader bug"), ("search", "candle warmer lamp"): disabled}))
    assert (out["cj"]["c1"]["status"], out["cj"]["c1"]["reason_code"], out["cj"]["c1"]["calls"]) == ("UNAVAILABLE", "CJ_ERROR", 1)
    assert (out["cj"]["c1"]["fallback"]["kind"], out["cj"]["c1"]["fallback"]["reason_code"]) == ("AGENT_REACH", "CJ_ERROR")
    c3 = out["cj"]["c3"]
    assert (c3["status"], c3["reason_code"], c3["fallback"], c3["limitations"]) == ("UNAVAILABLE", "CJ_API_DISABLED", handoff,
                                                                                    ["CJ has disabled API access (1600014)"])
    assert out["cj"]["c2"]["status"] == "OK" and out["cj"]["c2"]["calls"] == 4              # the others went on
    prod_fb = {"kind": "AGENT_REACH", "reason_code": "CJ_RATE_LIMITED", "site": "cjdropshipping.com", "query": BRUSH_PID}
    slow = {"status": "UNAVAILABLE", "reason_code": "CJ_RATE_LIMITED", "fallback": prod_fb, "product_id": BRUSH_PID,
            "limitations": ["CJ's rate limit still held"]}
    fns = Recorded({("product", BRUSH_PID): slow})
    part = _collect(fns, candidates=CANDIDATES[1:2])["cj"]["c2"]
    assert (part["status"], part["reason_code"], part["fallback"], part["calls"]) == ("PARTIAL", "CJ_RATE_LIMITED", prod_fb, 2)
    assert len(part["products"]) == 3 and part["products"][0]["detail_status"] == "UNAVAILABLE"
    assert part["products"][0]["freight_status"] == {"CN": "NOT_FETCHED", "US": "NOT_FETCHED"} and [t for t, _ in fns.calls] == ["search", "product"]
    us_down = {"status": "UNAVAILABLE", "reason_code": "CJ_NETWORK", "fallback": None, "options": []}
    no_route = {"status": "EMPTY", "reason_code": None, "fallback": None, "options": []}
    p2 = _collect(Recorded({("freight", "US"): us_down}), candidates=CANDIDATES[1:2])["cj"]["c2"]
    assert (p2["status"], p2["reason_code"], p2["products"][0]["freight_status"]) == ("PARTIAL", "CJ_NETWORK", {"CN": "OK", "US": "UNAVAILABLE"})
    assert len(p2["products"][0]["freight"]["CN"]) == 29 and p2["products"][0]["freight"]["US"] == []
    p3 = _collect(Recorded({("freight", "US"): no_route}), candidates=CANDIDATES[1:2])["cj"]["c2"]
    assert (p3["status"], p3["products"][0]["freight_status"]["US"]) == ("OK", "EMPTY")     # CJ answered: no US route
    gone = _collect(Recorded({("product", BRUSH_PID): {"status": "NOT_FOUND", "reason_code": None, "product": None, "variants": []}}),
                    candidates=CANDIDATES[1:2])["cj"]["c2"]
    assert (gone["status"], gone["reason_code"], gone["products"][0]["detail_status"]) == ("PARTIAL", "CJ_PRODUCT_NOT_FOUND", "NOT_FOUND")
    empty = _collect(Recorded(), candidates=[{"candidate_id": "z", "title": "Nothing here", "search_terms": ["zzzz qqqq"]}])["cj"]["z"]
    assert (empty["status"], empty["reason_code"], empty["products"]) == ("EMPTY", "CJ_EMPTY", [])


def test_through_the_real_supplier_tools_a_disabled_cj_is_typed_handed_off_and_asked_once():
    clock, key = Clock(), _cj_key()
    fake = FakeCJ(token=lambda r: httpx.Response(200, json={"code": 1600014, "result": False, "message": "Your API access has been disabled", "data": None}),
                  clock=clock)
    client = CJ.CJClient(key, transport=httpx.MockTransport(fake), sleep=clock.sleep, clock=clock.clock, wall=clock.wall)
    out = HD.collect(CANDIDATES, principal_id="prn_fred", supplier_fns=_real_fns(client, SUP.FairUse(clock=clock.clock), {}), env={},
                     sleep=clock.sleep)
    for cid, query in (("c1", "candle warmer"), ("c2", "self cleaning slicker brush"), ("c3", "candle warmer lamp")):
        entry = out["cj"][cid]
        assert (entry["status"], entry["reason_code"]) == ("UNAVAILABLE", "CJ_API_DISABLED"), entry
        fb = entry["fallback"]                                              # the supplier tool's own handoff, unchanged
        assert (fb["kind"], fb["reason_code"], fb["site"], fb["query"], fb["run_on"]) == ("AGENT_REACH", "CJ_API_DISABLED",
                                                                                          "cjdropshipping.com", query, "your machine")
        assert fb["commands"][0]["run"].startswith(f"mcporter call exa.web_search_exa query='site:cjdropshipping.com {query}'")
    assert fake.paths() == [CJ.TOKEN]                                       # the breaker: CJ asked once for the whole report
    assert key not in json.dumps(out)


def test_a_fair_use_refusal_is_waited_out_once_then_typed_and_never_counted_as_a_cj_call():
    def refused(wait):
        return SUP.FairUseRefused("SUPPLIER_RATE_LIMITED", f"at most 30 supplier calls a minute per key: call again in {wait} s", wait)
    once = iter([refused(12)])

    def search_once(kw):
        exc = next(once, None)
        if exc is not None:
            raise exc
        return _load(SEARCHES[kw["query"]])
    clock = Clock()
    out = _collect(Recorded({("search", "self cleaning slicker brush"): search_once}), candidates=CANDIDATES[1:2], sleep=clock.sleep)
    assert out["cj"]["c2"]["status"] == "OK" and out["cj"]["c2"]["calls"] == 4 and clock.sleeps == [12.0]
    assert [(r["call"], r["status"], r["reason_code"]) for r in out["receipts"]][:2] == [("supplier_search", "REFUSED", "FAIR_USE_LIMITED"),
                                                                                         ("supplier_search", "PARTIAL", None)]
    assert out["receipts"][0]["fair_use_code"] == "SUPPLIER_RATE_LIMITED"
    assert out["calls"]["fair_use_waited_s"] == 12.0 and out["receipts"][0]["waited_s"] == 12.0

    def always(kw):
        raise refused(50)
    clock2 = Clock()
    terms = ["candle warmer", "self cleaning slicker brush", "candle warmer lamp"]
    out2 = _collect(Recorded({("search", t): always for t in terms}), sleep=clock2.sleep)
    assert clock2.sleeps == [50.0, 50.0]                                    # the third would pass FAIR_USE_WAIT_TOTAL_S: not waited
    for cid, term in zip(("c1", "c2", "c3"), terms):
        entry = out2["cj"][cid]
        assert (entry["status"], entry["reason_code"], entry["calls"], entry["retry_after_s"]) == ("UNAVAILABLE", "FAIR_USE_LIMITED", 0, 50)
        assert entry["fair_use_code"] == "SUPPLIER_RATE_LIMITED" and entry["fallback"]["reason_code"] == "FAIR_USE_LIMITED"
        assert entry["fallback"]["kind"] == "AGENT_REACH" and entry["fallback"]["query"] == term     # still handed to Agent Reach
    assert out2["calls"]["cj"] == 0                                         # a refusal never reached CJ
    busy = _collect(Recorded({("search", "self cleaning slicker brush"): SUP.FairUseRefused("SUPPLIER_BUSY", "one CJ call at a time", 1),
                              ("product", BRUSH_PID): AcquisitionRefused(422, "BAD_ID", "not a CJ id")}), candidates=CANDIDATES[1:2],
                    sleep=Clock().sleep)["cj"]["c2"]
    assert (busy["status"], busy["reason_code"], busy["fair_use_code"]) == ("UNAVAILABLE", "FAIR_USE_LIMITED", "SUPPLIER_BUSY")


# ─────────────────────────────────────────────────────────── the real supplier tools: paced, bounded, held to fair use
def _cj_key() -> str:
    return f"CJ{next(_SEQ):04d}@api@" + hashlib.sha256(f"hostdata-{next(_SEQ)}".encode()).hexdigest()[:32]


def _ok(data) -> httpx.Response:
    return httpx.Response(200, json={"code": 200, "result": True, "message": "Success", "data": data})


def _raw_products(query: str, n: int = 12) -> list[dict]:
    stem = hashlib.sha256(query.encode()).hexdigest()[:8].upper()
    return [{"id": f"{stem}-0000-4000-8000-{i:012d}", "nameEn": f"{query.title()} Model {i}", "sellPrice": f"{3 + i}.50",
             "threeCategoryName": "Pet Grooming", "listedNum": 10 + i} for i in range(n)]


def _raw_details(pid: str) -> dict:
    return {"pid": pid, "productNameEn": "Detailed product", "productWeight": "180.0-260.0", "sellPrice": "4.20-5.10",
            "suggestSellPrice": "19.99-24.99", "bigImage": "https://cf.cjdropshipping.com/x.jpg", "variants": [
                {"vid": pid[:-4] + "VAR1", "variantNameEn": "A", "variantKey": "Blue", "variantWeight": 260.0, "variantSellPrice": 5.10,
                 "variantSugSellPrice": 24.99, "inventories": [{"countryCode": "CN", "totalInventory": 400, "cjInventory": 0, "factoryInventory": 400}]},
                {"vid": pid[:-4] + "VAR2", "variantNameEn": "B", "variantKey": "Pink", "variantWeight": 180.0, "variantSellPrice": 4.20,
                 "variantSugSellPrice": 19.99, "inventories": [{"countryCode": "US", "totalInventory": 7, "cjInventory": 7, "factoryInventory": 0}]}]}


class FakeCJ:
    """CJ's raw API 2.0 (synthetic answers in CJ's documented shapes), stamping every call on the fake clock."""

    def __init__(self, token=None, clock: Clock | None = None):
        self.calls: list[tuple[str, dict | None]] = []
        self.stamps: list[float] = []
        self.clock = clock
        self.token = token or (lambda r: _ok({"accessToken": "tok-hostdata-1", "accessTokenExpiryDate": "2027-03-01T09:16:33+08:00"}))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api2.0/v1")
        body = json.loads(request.content) if request.content else None
        self.calls.append((path, body))
        self.stamps.append(self.clock.clock() if self.clock else 0.0)
        if path == CJ.TOKEN:
            return self.token(request)
        if path == CJ.SEARCH:
            q = request.url.params["keyWord"]
            return _ok({"totalRecords": 12, "content": [{"productList": _raw_products(q)}]})
        if path == CJ.PRODUCT:
            return _ok(_raw_details(request.url.params["pid"]))
        if path == CJ.FREIGHT:
            if body["startCountryCode"] == "US":
                return _ok([{"logisticName": "UniUni+", "logisticPrice": 7.22, "logisticAging": "3-8", "totalPostageFee": 7.22}])
            return _ok([{"logisticName": "CJPacket Ordinary", "logisticPrice": 7.89, "logisticAging": "4-9", "totalPostageFee": 7.89},
                        {"logisticName": "CJPacket Eub Special Line", "logisticPrice": 9.7, "logisticAging": "10-23",
                         "clearanceOperationFee": 0.46, "totalPostageFee": 10.16}])
        return httpx.Response(404, json={"code": 404})

    def paths(self) -> list[str]:
        return [p for p, _ in self.calls]


class RecordingFairUse(SUP.FairUse):
    """The real fair-use gate, also keeping when each supplier call was admitted."""

    def __init__(self, clock):
        super().__init__(clock=clock)
        self.admitted: list[float] = []

    def admit(self, principal_id, env=None):
        super().admit(principal_id, env)
        if principal_id is not None:
            self.admitted.append(self._clock())


def _real_fns(client, gate, env):
    return {name: functools.partial(getattr(SUP, name), cj=client, fair_use=gate, env=env) for name in ("search", "product", "freight")}


def test_through_the_real_supplier_tools_cj_is_paced_bounded_and_a_friend_held_to_fair_use():
    clock, key = Clock(), _cj_key()
    fake = FakeCJ(clock=clock)
    client = CJ.CJClient(key, transport=httpx.MockTransport(fake), sleep=clock.sleep, clock=clock.clock, wall=clock.wall)
    gate = RecordingFairUse(clock.clock)
    env = {SUP.RATE_ENV: "10"}                                              # a friend's fair use: 10 supplier calls a minute
    cands = [{"candidate_id": f"k{i}", "title": t, "search_terms": [t]} for i, t in enumerate(("slicker brush", "lint roller", "pet hair remover"))]
    out = HD.collect(cands, principal_id="prn_fred", supplier_fns=_real_fns(client, gate, env), env={}, sleep=clock.sleep)
    for cand in cands:
        entry = out["cj"][cand["candidate_id"]]
        assert (entry["status"], entry["calls"], len(entry["products"])) == ("OK", 4, 3), entry
        assert entry["relevance"]["dropped_count"] == HD.CJ_SEARCH_LIMIT - HD.MAX_PRODUCTS   # CJ had 12; the search reads 10
        assert {d["why"] for d in entry["relevance"]["dropped"]} == {"OVER_LIMIT"}
        top = entry["products"][0]
        assert (top["sell_price_usd"], top["weight_g"], top["suggested_retail_usd"], top["us_stock_confirmed"]) == (4.2, 180.0, 19.99, True)
        assert top["cheapest_variant_id"].endswith("VAR2") and [v["options"] for v in top["variants"]] == ["Pink", "Blue"]
        assert top["freight"]["CN"][1] == {"carrier": "CJPacket Eub Special Line", "cost_usd": 10.16, "days_min": 10, "days_max": 23,
                                           "days_text": "10-23", "days_unit": None}
    reads = [p for p in fake.paths() if p != CJ.TOKEN]
    assert fake.paths().count(CJ.TOKEN) == 1 and len(reads) == 12          # bounded: 4 CJ reads a candidate, one sign-in
    assert reads == [CJ.SEARCH, CJ.PRODUCT, CJ.FREIGHT, CJ.FREIGHT] * 3
    gaps = [b - a for a, b in zip(fake.stamps, fake.stamps[1:])]
    assert all(g >= CJ.MIN_INTERVAL_S - 1e-9 for g in gaps), gaps          # CJ's pacing held on the clock
    refused = [r for r in out["receipts"] if r["status"] == "REFUSED"]
    assert refused and all((r["reason_code"], r["fair_use_code"]) == ("FAIR_USE_LIMITED", "SUPPLIER_RATE_LIMITED") for r in refused)
    assert out["calls"]["fair_use_waited_s"] > 0 and out["calls"]["cj"] == 12
    times = gate.admitted
    assert len(times) == 12 and all(sum(1 for t in times if a <= t < a + 60.0) <= 10 for a in times)   # never over 10 a minute
    owner = HD.collect(cands[:1], principal_id=None, supplier_fns=_real_fns(client, RecordingFairUse(clock.clock), env), env={},
                       sleep=clock.sleep)
    assert owner["cj"]["k0"]["status"] == "OK" and not [r for r in owner["receipts"] if r["status"] == "REFUSED"]   # the owner: no limit
    assert key not in json.dumps(out) and "tok-hostdata-1" not in json.dumps(out)


# ─────────────────────────────────────────────────────────── eBay through collect
def _ebay(fake, clock=None, **kw):
    clock = clock or Clock()
    fake.clock = fake.clock or clock
    n = next(_SEQ)
    return EB.EbayClient(f"SynthApp-HostData-{n:04d}", "PRD-" + hashlib.sha256(f"hd-{n}".encode()).hexdigest()[:36],
                         transport=httpx.MockTransport(fake), sleep=clock.sleep, clock=clock.clock, **kw)


class FakeEbay:
    def __init__(self, token=None, search=None):
        self.calls: list[httpx.Request] = []
        self.clock = None
        self.token = token or (lambda r: httpx.Response(200, json={"access_token": "v^1.1#SYNTHETIC-HD-TOKEN-0001", "expires_in": 7200}))
        self.search = search or (lambda r: httpx.Response(200, json=_load("SYNTHETIC_ebay_item_summary_search_slicker_brush.json")))

    def __call__(self, request):
        self.calls.append(request)
        return (self.token if request.url.path == EB.TOKEN else self.search)(request)

    def paths(self):
        return [r.url.path for r in self.calls]


def test_ebay_comparables_configured_not_configured_and_an_auth_failure_with_its_breaker():
    fake = FakeEbay()
    out = _collect(ebay=_ebay(fake))
    brush = out["ebay"]["c2"]
    assert (brush["status"], brush["reason_code"], brush["calls"], brush["query"]) == ("OK", None, 1, "self cleaning slicker brush")
    assert len(brush["listings"]) == 5 and all(set(row) == set(HD.LISTING_FIELDS) for row in brush["listings"])
    assert brush["listings"][0] == {"title": "Self Cleaning Slicker Brush for Dogs and Cats, Pet Grooming Brush",
                                    "url": "https://www.ebay.com/itm/100000000001", "price_usd": 12.99, "shipping_usd": 0.0,
                                    "delivery_min": "2026-11-05", "delivery_max": "2026-11-08", "location": "US", "condition": "New",
                                    "item_id": "v1|100000000001|0", "us_listing": True}
    dropped = {d["title"]: d["missing"] for d in brush["relevance"]["dropped"]}
    assert dropped == {"Dog Grooming Glove Pet Hair Remover Mitt": ["self", "cleaning", "slicker", "brush"],
                       "Slicker Brush for Dogs": ["self", "cleaning"]} and brush["relevance"]["unusable"] == 1
    for cid in ("c1", "c3"):                                                # every eBay answer is a near miss for "candle warmer"
        assert (out["ebay"][cid]["status"], out["ebay"][cid]["reason_code"], out["ebay"][cid]["listings"]) == ("NO_MATCH", "EBAY_NO_RELEVANT", [])
    ebay_rows = [r for r in out["receipts"] if r["source"] == "ebay"]
    assert [(r["call"], r["candidate_id"], r["status"], r["rows"]) for r in ebay_rows] == [
        ("ebay_browse_search", "c1", "NO_MATCH", 7), ("ebay_browse_search", "c2", "OK", 7), ("ebay_browse_search", "c3", "NO_MATCH", 7)]
    assert ebay_rows[1]["request"]["filter"] == "buyingOptions:{FIXED_PRICE},conditions:{NEW},deliveryCountry:US"
    assert fake.paths() == [EB.TOKEN, EB.SEARCH, EB.SEARCH, EB.SEARCH] and out["ebay_configured"] is True
    assert out["cj"]["c2"]["status"] == "OK" and out["calls"]["ebay"] == 3
    assert any("not sales" in n for n in out["notes"])
    off = _collect(env={"CJ_API_KEY": "", EB.ID_ENV: "SynthApp-only-id"})  # half a keyset is no keyset
    assert all((e["status"], e["reason_code"]) == ("NOT_CONFIGURED", "EBAY_NOT_CONFIGURED") for e in off["ebay"].values())
    assert "EBAY_CLIENT_SECRET is not set" in off["ebay"]["c1"]["why"] and "SynthApp-only-id" not in json.dumps(off)
    assert not [r for r in off["receipts"] if r["source"] == "ebay"] and off["cj"]["c2"]["status"] == "OK"
    clock = Clock()
    dead = FakeEbay(token=lambda r: httpx.Response(401, json={"error": "invalid_client", "error_description": "client authentication failed"}))
    bad = _collect(ebay=_ebay(dead, clock))
    first, later = bad["ebay"]["c1"], [bad["ebay"]["c2"], bad["ebay"]["c3"]]
    assert (first["status"], first["reason_code"], first["calls"]) == ("UNAVAILABLE", "EBAY_AUTH", 1) and "retry_after_s" not in first
    for entry in later:                                                     # the breaker: answered at once, eBay not called
        assert (entry["status"], entry["reason_code"], entry["calls"]) == ("UNAVAILABLE", "EBAY_AUTH", 0)
        assert entry["retry_after_s"] > 590 and "eBay was not called again" in entry["why"]
    assert dead.paths() == [EB.TOKEN] and bad["calls"]["ebay"] == 1 and bad["cj"]["c2"]["status"] == "OK"   # CJ unaffected


# ─────────────────────────────────────────────────────────── inputs
def test_the_inputs_are_bounded_checked_and_a_repeated_term_asked_once():
    many = [{"candidate_id": f"c{i}", "title": "Self-cleaning slicker brush", "search_terms": ["self cleaning slicker brush"]} for i in range(10)]
    fns = Recorded()
    out = _collect(fns, candidates=many + ["not an object"])
    assert list(out["cj"]) == [f"c{i}" for i in range(8)]
    assert out["skipped"] == [{"index": 9, "candidate_id": "c8", "why": "OVER_LIMIT"}, {"index": 10, "candidate_id": "c9", "why": "OVER_LIMIT"},
                              {"index": 11, "candidate_id": None, "why": "NOT_AN_OBJECT"}]
    assert [t for t, _ in fns.calls] == ["search", "product", "freight", "freight"]   # the same term: CJ asked once for all eight
    assert all(e["status"] == "OK" and len(e["products"][0]["freight"]["CN"]) == 29 for e in out["cj"].values())
    assert sum(1 for r in out["receipts"] if r.get("from_run_memo")) == 7 * 4 and out["calls"]["cj"] == 4
    named = _collect(Recorded(), candidates=[{"title": "Self-cleaning slicker brush for long-haired cats"},
                                             {"candidate_id": "dup", "title": "Candle warmer lamp", "search_terms": ["candle warmer"]},
                                             {"candidate_id": "dup", "title": "Candle warmer lamp", "search_terms": ["candle warmer lamp"]},
                                             {"candidate_id": "bad id!", "title": "!!"}])
    assert list(named["cj"]) == ["c1", "dup", "dup_3", "c4"]
    assert named["cj"]["c1"]["query"] == "self cleaning slicker brush" and named["cj"]["c1"]["status"] == "OK"   # the title's own words
    assert (named["cj"]["c4"]["status"], named["cj"]["c4"]["reason_code"], named["cj"]["c4"]["calls"]) == ("NOT_SEARCHED", "NO_SEARCH_TERM", 0)
    assert named["ebay"]["c4"]["status"] == "NOT_CONFIGURED"
    for kwargs, code in (({"ship_to": "USA"}, "BAD_COUNTRY"), ({"principal_id": "not a principal"}, "BAD_PRINCIPAL")):
        with pytest.raises(AcquisitionRefused) as exc:
            _collect(**kwargs)
        assert exc.value.code == code
    with pytest.raises(AcquisitionRefused) as exc:
        _collect(candidates="self cleaning slicker brush")
    assert (exc.value.status, exc.value.code) == (422, "BAD_CANDIDATES")
    with pytest.raises(TypeError):
        HD.collect(CANDIDATES, principal_id=None, supplier_fns={"search": print}, env={})
    gb = _collect(Recorded(), candidates=CANDIDATES[1:2], ship_to="gb")
    assert gb["ship_to"] == "GB" and gb["receipts"][2]["request"]["country"] == "GB"     # freight to the ship-to country


def test_a_host_bug_in_one_candidate_never_stops_the_others(monkeypatch):
    real = HD._apply_details

    def broken(product, answer):
        if product["product_id"] == BRUSH_PID:
            raise KeyError("a host bug")
        return real(product, answer)
    monkeypatch.setattr(HD, "_apply_details", broken)
    out = _collect(Recorded(), candidates=CANDIDATES)
    assert (out["cj"]["c2"]["status"], out["cj"]["c2"]["reason_code"]) == ("UNAVAILABLE", "HOST_DATA_ERROR")
    assert out["cj"]["c1"]["status"] == out["cj"]["c3"]["status"] == "NO_MATCH" and out["ebay"]["c2"]["status"] == "NOT_CONFIGURED"


# ─────────────────────────────────────────────────────────── review-fix round (R1 #2, R2 #6, R2 #9 / C2, C6)
def _cj_item(n: int, pid: str, title: str, price: str) -> tuple[dict, dict]:
    url = f"https://cjdropshipping.com/product/{title.lower().replace(' ', '-')}-p-{pid}.html"
    return ({"item_id": f"itm_{n}", "kind": "listing", "source_id": f"src_{n}", "excerpt": title,
             "listing": {"title": title, "price_as_listed": price, "product_id": pid}},
            {"source_id": f"src_{n}", "url": url, "source_class": "supplier_listing"})


def _ebay_doc(*titles: str) -> dict:
    template = _load("SYNTHETIC_ebay_item_summary_search_slicker_brush.json")["itemSummaries"][0]
    items = [{**template, "itemId": f"v1|3000000000{i:02d}|0", "title": t, "itemWebUrl": f"https://www.ebay.com/itm/3000000000{i:02d}"}
             for i, t in enumerate(titles)]
    return {"_synthetic": "SYNTHETIC (built in the test)", "total": len(items), "itemSummaries": items}


def test_relevance_takes_whole_words_only_on_cj_and_ebay_alike():
    """R2 #6: a head term counts only as a whole word of the title (its plural or singular, or two or three adjacent words joined
    either way), never inside another word: the first kept product is the one priced and freight-quoted."""
    for title, term, missing in (("Desk Clamp Phone Holder", "desk lamp", ["lamp"]), ("LED Light Up Earrings", "ring light", ["ring"]),
                                 ("Office Chair Brush", "hair brush", ["hair"]), ("Phone Holder Showcase", "phone case", ["case"]),
                                 ("Sealed Glass Jar", "led jar", ["led"]), ("Candlestick Holder", "candle holder", ["candle"]),
                                 ("LED Desk Lamp with Clamp", "desk lamp", []), ("Ring Light with Tripod", "ring light", []),
                                 ("Hairbrush for Women", "hair brush", []), ("Touchscreen Winter Gloves", "touch screen winter gloves", []),
                                 ("Touch Screen Winter Glove", "touchscreen winter gloves", []), ("Phone Cases 2 Pack", "phone case", []),
                                 ("Candle Warmers Electric", "candle warmer", []), ("Phone Batteries", "phone battery", []),
                                 ("Self-Cleaning Slicker Brush", "self cleaning slicker brush", [])):
        assert HD.missing_terms(title, HD.head_terms(term)) == missing, (title, term)
    clamp, lamp = "2000000000000000001", "2000000000000000002"
    (i1, s1), (i2, s2) = _cj_item(1, clamp, "Desk Clamp Phone Holder", "US$2.10"), _cj_item(2, lamp, "LED Desk Lamp with Clamp", "US$6.40")
    found = {"status": "PARTIAL", "retrieved_at": "2026-11-02T16:00:00Z", "items": [i1, i2], "sources": [s1, s2], "fallback": None}
    details = {"status": "OK", "product": {"product_id": lamp, "title": "LED Desk Lamp with Clamp"},
               "variants": [{"variant_id": "LAMP-VARIANT-01", "price_as_listed": "US$6.40", "weight_g": "640.0", "stock": []}]}
    fns = Recorded({("search", "desk lamp"): found, ("product", lamp): details})
    desk = [{"candidate_id": "d1", "title": "Desk lamp", "search_terms": ["desk lamp"]}]
    entry = _collect(fns, candidates=desk)["cj"]["d1"]
    assert [k["product_id"] for k in entry["relevance"]["kept"]] == [lamp]
    assert [(d["product_id"], d["why"], d["missing"]) for d in entry["relevance"]["dropped"]] == [(clamp, "MISSING_HEAD_TERMS", ["lamp"])]
    assert [kw["product_id"] for t, kw in fns.calls if t == "product"] == [lamp]          # the clamp is never the priced product
    assert (entry["status"], entry["products"][0]["sell_price_usd"]) == ("OK", 6.40)
    fake = FakeEbay(search=lambda r: httpx.Response(200, json=_ebay_doc("Phone Holder Showcase Stand", "Phone Case for iPhone 15")))
    eb = _collect(Recorded(), candidates=[{"candidate_id": "p1", "title": "Phone case", "search_terms": ["phone case"]}],
                  ebay=_ebay(fake))["ebay"]["p1"]
    assert [row["title"] for row in eb["listings"]] == ["Phone Case for iPhone 15"]          # the same rule for eBay
    assert [(d["title"], d["missing"]) for d in eb["relevance"]["dropped"]] == [("Phone Holder Showcase Stand", ["case"])]


def test_every_freight_option_names_the_unit_cjs_text_states():
    """C2 / R2 #9: "2-5 business days" keeps its unit; every freight option gains days_unit ("business" / "calendar" / None) and
    keeps every key it had."""
    for text, days, unit in (("2-5 business days", (2, 5), "business"), ("3-7 Working Days", (3, 7), "business"),
                             ("4-6 workdays", (4, 6), "business"), ("2-5 business", (2, 5), "business"),
                             ("5-10 calendar days", (5, 10), "calendar"), ("4-9", (4, 9), None), ("12-20 days", (12, 20), None),
                             ("", (None, None), None), (None, (None, None), None)):
        assert (HD.parse_days(text), HD.days_unit(text)) == (days, unit), text
    assert HD.days_unit("2-5 business or calendar days") is None                 # both named: neither is claimed
    us = {"status": "OK", "options": [
        {"carrier": "USPS+", "cost_usd": 4.71, "delivery_days": "2-5 business days", "taxes_usd": 0.0, "clearance_usd": 0.0, "total_usd": 4.71},
        {"carrier": "Slow Post", "cost_usd": 3.10, "delivery_days": "7-12 calendar days", "total_usd": 3.10}]}
    top = _collect(Recorded({("freight", "US"): us}), candidates=CANDIDATES[1:2])["cj"]["c2"]["products"][0]
    assert top["freight"]["US"] == [
        {"carrier": "Slow Post", "cost_usd": 3.1, "days_min": 7, "days_max": 12, "days_text": "7-12 calendar days", "days_unit": "calendar"},
        {"carrier": "USPS+", "cost_usd": 4.71, "days_min": 2, "days_max": 5, "days_text": "2-5 business days", "days_unit": "business"}]
    keys = {"carrier", "cost_usd", "days_min", "days_max", "days_text", "days_unit"}
    assert all(set(o) == keys for opts in top["freight"].values() for o in opts) and len(top["freight"]["CN"]) == 29


def test_ebay_spends_the_friends_fair_use_and_a_refusal_never_reaches_ebay_or_its_breaker():
    """R1 #2: every eBay search first spends the caller's fair use (the same per-key budget as its CJ calls). A friend whose
    minute is used up makes ZERO eBay calls (FAIR_USE_LIMITED per candidate), the keyset's shared breaker stays shut, and the
    owner's next collection is not limited by it."""
    clock = Clock()
    gate = RecordingFairUse(clock.clock)
    for _ in range(SUP.RATE_DEFAULT):                                      # the friend's minute is used up
        gate.admit("prn_fred")
    fake = FakeEbay()
    client = _ebay(fake, clock)
    out = _collect(Recorded(), ebay=client, fair_use=gate, sleep=clock.sleep)
    for cid in ("c1", "c2", "c3"):
        e = out["ebay"][cid]
        assert (e["status"], e["reason_code"], e["fair_use_code"], e["calls"], e["listings"]) == (
            "UNAVAILABLE", "FAIR_USE_LIMITED", "SUPPLIER_RATE_LIMITED", 0, []), e
        assert e["retry_after_s"] >= 1 and "fair use" in e["why"]
    assert fake.calls == [] and out["calls"]["ebay"] == 0                  # zero eBay calls: not even the sign-in
    assert client.breaker() is None                                        # the shared breaker never tripped
    assert [(r["call"], r["status"], r["reason_code"]) for r in out["receipts"] if r["source"] == "ebay"] == [
        ("ebay_browse_search", "REFUSED", "FAIR_USE_LIMITED")] * 3
    assert out["reason_codes"]["ebay"] == ["FAIR_USE_LIMITED"] and out["cj"]["c2"]["status"] == "OK"
    owner = _collect(Recorded(), principal_id=None, ebay=client, fair_use=gate, sleep=clock.sleep)
    assert [owner["ebay"][c]["status"] for c in ("c1", "c2", "c3")] == ["NO_MATCH", "OK", "NO_MATCH"]     # the owner: served at once
    assert fake.paths() == [EB.TOKEN, EB.SEARCH, EB.SEARCH, EB.SEARCH] and owner["reason_codes"]["ebay"] == ["EBAY_NO_RELEVANT"]
    clock.sleep(61)                                                        # a minute on, the friend is served again
    assert _collect(Recorded(), ebay=client, fair_use=gate, sleep=clock.sleep)["ebay"]["c2"]["status"] == "OK"
    fresh = RecordingFairUse(clock.clock)                                  # one admission per eBay search; the run's memo spends none
    same = [{"candidate_id": c, "title": "Slicker brush", "search_terms": ["self cleaning slicker brush"]} for c in ("a", "b")]
    _collect(Recorded(), candidates=same, ebay=_ebay(FakeEbay(), clock), fair_use=fresh)
    assert len(fresh.admitted) == 1
    dead = FakeEbay(token=lambda r: httpx.Response(401, json={"error": "invalid_client", "error_description": "client authentication failed"}))
    fresh2 = RecordingFairUse(clock.clock)
    bad = _collect(Recorded(), ebay=_ebay(dead, clock), fair_use=fresh2)
    assert [bad["ebay"][c]["reason_code"] for c in ("c1", "c2", "c3")] == ["EBAY_AUTH"] * 3
    assert len(fresh2.admitted) == 1 and dead.paths() == [EB.TOKEN]        # an open breaker spends no fair use


def test_by_default_cj_and_ebay_spend_one_fair_use_budget(monkeypatch):
    """R1 #2 through the default wiring: the supplier tools and the eBay search admit on the SAME gate (`supplier.FAIR_USE`)."""
    clock, key = Clock(), _cj_key()
    cj_client = CJ.CJClient(key, transport=httpx.MockTransport(FakeCJ(clock=clock)), sleep=clock.sleep, clock=clock.clock, wall=clock.wall)
    monkeypatch.setattr(CJ, "client_from_env", lambda env, **kw: cj_client)
    gate = RecordingFairUse(clock.clock)
    monkeypatch.setattr(SUP, "FAIR_USE", gate)
    ebay_fake = FakeEbay()
    cands = [{"candidate_id": "k0", "title": "Slicker brush", "search_terms": ["slicker brush"]}]
    env = {SUP.RATE_ENV: "5"}                                              # a friend's fair use: 5 calls a minute
    first = HD.collect(cands, principal_id="prn_fred", ebay=_ebay(ebay_fake, clock), env=env, sleep=clock.sleep)
    assert (first["cj"]["k0"]["status"], first["cj"]["k0"]["calls"], first["ebay"]["k0"]["status"]) == ("OK", 4, "OK")
    assert len(gate.admitted) == 5                                         # 4 CJ calls + 1 eBay search: one budget
    searched = ebay_fake.paths().count(EB.SEARCH)
    second = HD.collect(cands, principal_id="prn_fred", ebay=_ebay(ebay_fake, clock), env=env, sleep=lambda s: None)
    assert (second["cj"]["k0"]["reason_code"], second["ebay"]["k0"]["reason_code"]) == ("FAIR_USE_LIMITED", "FAIR_USE_LIMITED")
    assert ebay_fake.paths().count(EB.SEARCH) == searched and len(gate.admitted) == 5
    assert second["reason_codes"] == {"cj": ["FAIR_USE_LIMITED"], "ebay": ["FAIR_USE_LIMITED"]}


# ─────────────────────────────────────────────────────────── review round R2 / R1 verify (2026-11-02)
def test_one_term_reading_for_cj_ebay_and_the_report_parsers():
    """R2 verify: `head_terms` and the whole-word matcher live in acquisition.agent_reach; host data uses the same functions."""
    from polymath_shared.acquisition import agent_reach as AR
    assert HD.head_terms is AR.head_terms and HD.missing_terms is AR.missing_terms
    assert HD.head_terms("candle warmer lamp with timer") == ["candle", "warmer", "lamp"]
    assert HD.missing_terms("Desk Clamp Phone Holder", HD.head_terms("desk lamp")) == ["lamp"]
    # live 2026-11-02: an AUDIENCE word is held by its group on CJ and eBay too ("pet" by "Cat" / "Dog"), nothing else is
    assert HD.missing_terms("Automatic Cat Feeder", HD.head_terms("automatic pet feeder")) == []
    assert HD.missing_terms("Pet Hair Remover", HD.head_terms("dog bed")) == ["dog", "bed"]


class FixedNow:
    def __init__(self, iso):
        self.t = datetime.fromisoformat(iso)

    def __call__(self):
        return self.t


def test_a_friends_ebay_searches_stop_at_the_daily_budget_before_reaching_ebay_or_its_breaker(monkeypatch):
    """R1 verify: one friend could spend the keyset's 5,000 eBay calls a day in 3-6 hours at the 30-a-minute fair use, then every
    eBay 429 opens the keyset-wide breaker for everyone for 300 s. So a friend gets at most EBAY_DAILY_SEARCHES (300) eBay
    searches a UTC day: past it EBAY_DAILY_LIMIT, zero eBay calls, no fair use spent, the breaker untouched; the owner is exempt,
    another friend keeps their own budget, and a new UTC day starts again."""
    assert HD.EBAY_DAILY_SEARCHES == 300 and HD.EBAY_DAILY_LIMIT == "EBAY_DAILY_LIMIT"
    now = FixedNow("2026-11-02T23:59:00+00:00")
    daily = HD.EbayDaily(now=now)
    for _ in range(HD.EBAY_DAILY_SEARCHES):
        assert daily.admit("prn_fred") is None
    clock = Clock()
    gate = RecordingFairUse(clock.clock)
    fake = FakeEbay()
    client = _ebay(fake, clock)
    out = _collect(Recorded(), ebay=client, fair_use=gate, sleep=clock.sleep, ebay_daily=daily)
    for cid in ("c1", "c2", "c3"):
        e = out["ebay"][cid]
        assert (e["status"], e["reason_code"], e["calls"], e["listings"], e["retry_after_s"]) == (
            "UNAVAILABLE", "EBAY_DAILY_LIMIT", 0, [], 60), e                  # 60 s to midnight UTC
        assert "300 eBay searches per key a UTC day" in e["why"]
    assert fake.calls == [] and out["calls"]["ebay"] == 0 and client.breaker() is None and gate.admitted == []
    assert [(r["call"], r["status"], r["reason_code"], r["retry_after_s"]) for r in out["receipts"] if r["source"] == "ebay"] == [
        ("ebay_browse_search", "REFUSED", "EBAY_DAILY_LIMIT", 60)] * 3
    assert out["reason_codes"]["ebay"] == ["EBAY_DAILY_LIMIT"] and out["cj"]["c2"]["status"] == "OK"      # CJ is not affected
    ann = _collect(Recorded(), principal_id="prn_ann", ebay=client, fair_use=gate, sleep=clock.sleep, ebay_daily=daily)
    assert ann["ebay"]["c2"]["status"] == "OK" and daily.used("prn_ann") == 3                              # another friend's budget
    owner = _collect(Recorded(), principal_id=None, ebay=client, fair_use=gate, sleep=clock.sleep, ebay_daily=daily)
    assert owner["ebay"]["c2"]["status"] == "OK" and daily.used("prn_fred") == 300                        # the owner is exempt
    now.t = datetime.fromisoformat("2026-11-03T00:00:01+00:00")                                            # a new UTC day
    again = _collect(Recorded(), ebay=client, fair_use=gate, sleep=clock.sleep, ebay_daily=daily)
    assert again["ebay"]["c2"]["status"] == "OK" and daily.used("prn_fred") == 3
    # a search the fair use refuses never reached eBay: its daily search is given back
    tight, full = HD.EbayDaily(now=now, limit=5), RecordingFairUse(clock.clock)
    for _ in range(SUP.RATE_DEFAULT):
        full.admit("prn_kim")
    kim = _collect(Recorded(), principal_id="prn_kim", ebay=_ebay(FakeEbay(), clock), fair_use=full, ebay_daily=tight)
    assert [kim["ebay"][c]["reason_code"] for c in ("c1", "c2", "c3")] == ["FAIR_USE_LIMITED"] * 3 and tight.used("prn_kim") == 0
    # by default every collect spends the process's one budget (`EBAY_DAILY`)
    monkeypatch.setattr(HD, "EBAY_DAILY", HD.EbayDaily(now=now, limit=1))
    first = _collect(Recorded(), principal_id="prn_lee", ebay=_ebay(FakeEbay(), clock), fair_use=RecordingFairUse(clock.clock))
    assert [first["ebay"][c]["reason_code"] for c in ("c1", "c2", "c3")] == ["EBAY_NO_RELEVANT", "EBAY_DAILY_LIMIT", "EBAY_DAILY_LIMIT"]

