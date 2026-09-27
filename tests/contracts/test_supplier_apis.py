"""SUPPLIER-APIS (the owner's decision of 2026-09-27): supplier listings WITHOUT the pages that show human checks, never past a check.
  * cjdropshipping.com: CJ's OFFICIAL API 2.0 when `CJ_API_KEY` is set: the sign-in (`apiKey` only) and its token cached until it
    expires, the product search mapped onto the browser backend's listing shape, CJ's rate limit waited out, a refused token renewed
    once; an API that cannot answer (auth, quota, network) falls back to the host browser, SAID in `limitations` and COUNTED.
  * alibaba.com: the local SearXNG's search-engine results (`site:alibaba.com <query>`, format=json): only product-detail URLs,
    title / price / minimum order from the snippet as indexed, a verification page's text never a listing; SearXNG unreachable (or
    every engine failing) falls back the same way. `SEARXNG_URL=off` = not used.
  * no key (and SearXNG off) = today's backend itself; with SearXNG on, a CJ read without a key is still the browser's read, byte
    for byte.
  * keys never reach a result, an error or a log.
Fake HTTP only (httpx.MockTransport): no call reaches CJ, a search engine or a SearXNG. No browser, no database.
"""
import hashlib
import itertools
import json
import logging
import pathlib
import sys

import httpx
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import cj_api as CJ
from polymath_shared.acquisition import listing_apis as LA
from polymath_shared.acquisition import opencli as O
from polymath_shared.acquisition import searxng as SX
from polymath_shared.acquisition import service as S

ACTION = {"action_id": "hact_" + "c" * 24, "run_id": "adr_" + "d" * 32, "budget": {"max_queries": 5}, "disallowed_source_roles": [],
          "search_intents": [{"intent_id": "si_supply", "intent": "supplier listings", "evidence_goal": "supply", "evidence_roles": ["supply", "price"]}]}
_SEQ = itertools.count()


def _action(tag) -> dict:
    return {**ACTION, "action_id": "hact_" + hashlib.sha256(json.dumps(tag, sort_keys=True).encode()).hexdigest()[:24]}


def _key() -> str:
    """A fresh fake key per test: the token cache and the pacing are per key."""
    return f"CJ{next(_SEQ):04d}@api@{hashlib.sha256(str(next(_SEQ)).encode()).hexdigest()[:32]}"


class Clock:
    """Monotonic + wall clocks that only move when the client sleeps (pacing and rate-limit waits are recorded, never slept)."""

    def __init__(self, wall: float = 1_790_000_000.0):
        self.mono, self.wall_now, self.sleeps = 0.0, wall, []

    def sleep(self, s: float) -> None:
        self.sleeps.append(round(s, 3))
        self.mono += s
        self.wall_now += s

    def clock(self) -> float:
        return self.mono

    def wall(self) -> float:
        return self.wall_now


PRODUCT = {"id": "04A22450-67F0-4617-A132-E7AE7F8963B0", "nameEn": "Women's Waterproof Camera Rain Cover", "sku": "CJNSSYWY01847",
           "bigImage": "https://cc-west-usa.oss-us-west-1.aliyuncs.com/20210129/2167381084610.png", "sellPrice": "11.85", "nowPrice": "9.50",
           "listedNum": 100, "categoryId": "5E656DFB", "threeCategoryName": "Camera Covers", "supplierName": "", "warehouseInventoryNum": 0,
           "productType": "ORDINARY_PRODUCT"}


def _ok(data) -> httpx.Response:
    return httpx.Response(200, json={"code": 200, "result": True, "message": "Success", "data": data, "requestId": "r-1", "success": True})


def _err(code: int, message: str, http: int = 200) -> httpx.Response:
    return httpx.Response(http, json={"code": code, "result": False, "message": message, "data": None, "requestId": "r-2", "success": False})


class FakeCJ:
    """CJ's API as its documentation shows it. `script` maps a route to the replies it gives in turn (the last one repeats)."""

    def __init__(self, token="tok-cached-7f3e", expiry="2027-03-01T09:16:33+08:00", products=(PRODUCT,), total=1, script=None):
        self.token, self.calls = token, []
        default = {CJ.TOKEN: [_ok({"openId": 1, "accessToken": token, "accessTokenExpiryDate": expiry, "refreshToken": "r",
                                   "refreshTokenExpiryDate": expiry, "createDate": "2026-09-27T00:00:00+08:00"})],
                   CJ.SEARCH: [_ok({"pageSize": 20, "pageNumber": 1, "totalRecords": total, "totalPages": 1,
                                    "content": [{"productList": list(products), "relatedCategoryList": [], "keyWord": "x"}]})]}
        self.script = {**default, **(script or {})}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api2.0/v1")
        body = json.loads(request.content) if request.content else None
        self.calls.append({"method": request.method, "path": path, "params": dict(request.url.params), "token": request.headers.get("CJ-Access-Token"),
                           "body": body})
        replies = self.script.get(path)
        if not replies:
            return httpx.Response(404, json={"code": 404, "message": "no such route"})
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def paths(self) -> list[str]:
        return [c["path"] for c in self.calls]


def _client(fake, key=None, clock=None) -> CJ.CJClient:
    clock = clock or Clock()
    return CJ.CJClient(key or _key(), transport=httpx.MockTransport(fake), sleep=clock.sleep, clock=clock.clock, wall=clock.wall)


class Browser:
    """The host browser backend, recorded (what OpenCLI's bridge returned for one read)."""

    def __init__(self, raw):
        self.raw, self.reads = raw, []

    def status(self):
        return {"backend": "opencli", "available": True, "note": "browser bridge connected"}

    def read(self, target, limit):
        self.reads.append((target.reader, limit))
        return dict(self.raw)


BROWSER_LISTING = O.OpenCLIBackend._listing("https://cjdropshipping.com/product/rain-cover-p-1A2B3C4D.html", "Rain cover",
                                            "Rain cover\n$3.20 - $4.10\nMin. order: 500 pieces\nNingbo Example Trading Co., Ltd.")


def _acquire(backend, site: str, tag, query="camera rain cover") -> dict:
    return S.acquire(principal_id=None, action=_action(tag), operation="listings", target=query, site=site, search_intent_id="si_supply",
                     backend=backend)


def test_the_code_under_test_is_this_checkout():
    for mod in (CJ, LA, O, SX, S):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── CJ: the sign-in and its token
def test_the_token_is_fetched_once_and_cached_until_it_expires():
    fake, clock = FakeCJ(), Clock()
    client = _client(fake, clock=clock)
    for _ in range(3):
        client.search("rain cover", 20)
    assert fake.paths() == [CJ.TOKEN, CJ.SEARCH, CJ.SEARCH, CJ.SEARCH]                  # one sign-in for three reads
    assert fake.calls[0]["method"] == "POST" and set(fake.calls[0]["body"]) == {"apiKey"}  # API 2.0: the key alone, no e-mail
    assert all(c["token"] == fake.token for c in fake.calls[1:]) and fake.calls[0]["token"] is None
    assert fake.calls[1]["params"] == {"keyWord": "rain cover", "page": "1", "size": "20", "features": "enable_category"}   # the client sends the size it is asked
    assert all(s <= CJ.MIN_INTERVAL_S for s in clock.sleeps) and len(clock.sleeps) == 3   # spaced 1.1 s apart: CJ's one a second
    clock.wall_now = CJ._epoch("2027-03-01T09:16:33+08:00") - 60                           # ten-minute margin before the expiry
    client.search("rain cover", 20)
    assert fake.paths()[-2:] == [CJ.TOKEN, CJ.SEARCH]


def test_a_token_cj_refuses_is_renewed_once_and_the_read_goes_on():
    fake = FakeCJ(script={CJ.SEARCH: [_err(1600001, "Invalid API key or access token"),
                                      _ok({"totalRecords": 1, "content": [{"productList": [PRODUCT]}]})]})
    products, total = _client(fake).search("rain cover", 5)
    assert fake.paths() == [CJ.TOKEN, CJ.SEARCH, CJ.TOKEN, CJ.SEARCH] and total == 1 and products[0]["id"] == PRODUCT["id"]


def test_cjs_rate_limit_is_waited_out_and_a_spent_quota_is_not_retried():
    clock = Clock()
    fake = FakeCJ(script={CJ.SEARCH: [_err(1600200, "Too much request"), httpx.Response(429, json={"message": "slow down"}),
                                      _ok({"totalRecords": 0, "content": []})]})
    assert _client(fake, clock=clock).search("rain cover", 5) == ([], 0)
    assert [s for s in clock.sleeps if s >= 2] == [2.0, 4.0] and fake.paths().count(CJ.SEARCH) == 3
    held = FakeCJ(script={CJ.SEARCH: [_err(1600200, "Too much request")]})
    with pytest.raises(LA.ApiFailed) as exc:
        _client(held).search("rain cover", 5)
    assert exc.value.reason == "rate_limit" and held.paths().count(CJ.SEARCH) == 3
    spent = FakeCJ(script={CJ.SEARCH: [_err(16900500, "Insufficient points, please check your daily points balance")]})
    with pytest.raises(LA.ApiFailed) as exc:
        _client(spent).search("rain cover", 5)
    assert exc.value.reason == "quota" and spent.paths().count(CJ.SEARCH) == 1


# ─────────────────────────────────────────────────────────── CJ: the record shape
def test_a_cj_product_maps_onto_the_browser_listing_shape_and_says_where_it_came_from():
    reader = CJ.CJListings(_client(FakeCJ(total=240)))
    raw = reader.read(S.resolve("listings", "camera rain cover", "cjdropshipping.com"), 20)
    (rec,) = raw["records"]
    assert set(BROWSER_LISTING) == set(rec) and set(BROWSER_LISTING["listing"]) - {"card"} <= set(rec["listing"])   # the browser's keys
    assert rec["url"] == "https://cjdropshipping.com/product/womens-waterproof-camera-rain-cover-p-04A22450-67F0-4617-A132-E7AE7F8963B0.html"
    lst = rec["listing"]
    assert (lst["title"], lst["price_as_listed"], lst["discount_price_as_listed"], lst["minimum_order_as_listed"], lst["supplier"]) == \
        ("Women's Waterproof Camera Rain Cover", "US$11.85", "US$9.50", None, None)
    assert (lst["product_id"], lst["sku"], lst["category"], lst["listed_by_stores"], lst["warehouse_inventory"]) == \
        (PRODUCT["id"], "CJNSSYWY01847", "Camera Covers", "100", "0")                       # a count of 0 stays "0"
    shaped = S.shape(S.resolve("listings", "camera rain cover", "cjdropshipping.com"), raw, action=_action("cj-shape-2"),
                     search_intent_id="si_supply", retrieved_at=raw["retrieved_at"], used=1, cap=5, limit=20)
    (item,), (src,) = shaped["items"], shaped["sources"]
    assert src["source_class"] == "supplier_listing" and src["url"] == rec["url"] and src["retrieved_at"] == raw["retrieved_at"]
    assert item["kind"] == "listing" and item["listing"]["price_as_listed"] == "US$11.85" and item["source_id"] == src["source_id"]
    assert any("CJ Dropshipping API" in x for x in shaped["limitations"])
    assert shaped["status"] == "PARTIAL" and any("read 1 of 240" in x for x in shaped["limitations"])   # CJ says how many exist


@pytest.mark.parametrize("value,expected", [("11.85", "US$11.85"), (58.09, "US$58.09"), ("0.97-4.08", "US$0.97-4.08"), ("2.83 -- 3.74", "US$2.83-3.74"),
                                            ("", None), (None, None), (True, None), ("0", None), ("n/a", None)])
def test_cj_prices_read_as_listed_in_us_dollars(value, expected):
    assert CJ.usd(value) == expected


def test_a_stated_minimum_order_is_kept_and_an_unusable_product_is_counted():
    rows = [dict(PRODUCT, directMinOrderNum="10"), dict(PRODUCT, id="1592402824729088001", directMinOrderNum=1), dict(PRODUCT, id="bad id!"),
            dict(PRODUCT, id="1592402824729088000", nameEn="")]
    raw = CJ.CJListings(_client(FakeCJ(products=rows, total=4))).read(S.resolve("listings", "rain cover", "cjdropshipping.com"), 20)
    assert [r["listing"]["minimum_order_as_listed"] for r in raw["records"]] == ["10 units", "1 unit"]
    assert any("2 product(s) in CJ's answer had no usable id or name" in n for n in raw["backend_notes"])


# ─────────────────────────────────────────────────────────── selection and the counted fallback
def _cj_backend(fake, browser_raw=None, clock=None):
    browser = Browser(browser_raw or {"state": "ok", "records": [BROWSER_LISTING]})
    return LA.ListingAPIs(browser, {"cj_listings": CJ.CJListings(_client(fake, clock=clock))}), browser


def test_with_a_key_cj_listings_come_from_the_api_and_the_browser_is_not_opened():
    backend, browser = _cj_backend(FakeCJ())
    out = _acquire(backend, "cjdropshipping.com", "api-first")
    assert out["status"] == "OK" and browser.reads == [] and out["items"][0]["listing"]["product_id"] == PRODUCT["id"]
    assert any(x.startswith("listings from the CJ Dropshipping API") for x in out["limitations"])
    assert backend.status()["listing_apis"]["cj_listings"]["api"] == "CJ Dropshipping API"


@pytest.mark.parametrize("script,reason", [
    ({CJ.TOKEN: [_err(1600001, "Invalid API key or access token")]}, "auth"),
    ({CJ.SEARCH: [_err(1600201, "Quota has been used up")]}, "quota"),
    ({CJ.SEARCH: [httpx.ConnectError("connection refused")]}, "network"),
    ({CJ.SEARCH: [httpx.Response(502, text="bad gateway")]}, "server")])
def test_an_api_that_cannot_answer_falls_back_to_the_browser_said_and_counted(script, reason, caplog):
    key = _key()
    fake = FakeCJ(script=script)
    browser = Browser({"state": "ok", "records": [BROWSER_LISTING]})
    backend = LA.ListingAPIs(browser, {"cj_listings": CJ.CJListings(_client(fake, key=key))})
    before = LA.counts().get("cj_listings", {}).get("fallbacks", 0)
    with caplog.at_level(logging.DEBUG):
        out = _acquire(backend, "cjdropshipping.com", ["fallback", reason])
    assert browser.reads == [("cj_listings", 20)] and out["status"] == "OK"                  # the browser read, as before
    assert out["items"][0]["listing"]["price_as_listed"] == "$3.20 - $4.10"
    said = [x for x in out["limitations"] if x.startswith("the CJ Dropshipping API could not answer")]
    assert len(said) == 1 and f"({reason}:" in said[0] and "the host browser read cjdropshipping.com instead" in said[0]
    now = backend.status()["listing_apis"]["cj_listings"]
    assert now["fallbacks"] == before + 1 and now["fallback_reasons"][reason] >= 1
    assert any("fell back to the host browser" in r.getMessage() for r in caplog.records)
    wire = json.dumps(out) + json.dumps(backend.status()) + "\n".join(r.getMessage() for r in caplog.records)
    assert key not in wire and fake.token not in wire                                     # never a key or a token


def test_a_fallback_that_meets_a_human_check_still_says_the_api_failed():
    backend, _ = _cj_backend(FakeCJ(script={CJ.TOKEN: [_err(1600001, "Invalid API key or access token")]}),
                             browser_raw={"state": "human_check", "page_url": "https://cjdropshipping.com/search/rain+cover.html"})
    out = _acquire(backend, "cjdropshipping.com", "fallback-wall")
    assert out["status"] == "HUMAN_ACTION_REQUIRED" and out["human_action"]["site"] == "cjdropshipping.com"
    assert any("could not answer (auth:" in x for x in out["limitations"]) and out["budget"]["refunded"] is True


def test_no_key_is_todays_backend_and_a_cj_read_is_the_browsers_byte_for_byte(monkeypatch):
    monkeypatch.delenv("CJ_API_KEY", raising=False)
    monkeypatch.setenv("SEARXNG_URL", "off")
    monkeypatch.delenv("POLYMATH_ACQUISITION", raising=False)
    assert type(S.default_backend()) is O.OpenCLIBackend                                  # nothing configured: the backend itself
    browser = Browser({"state": "ok", "records": [BROWSER_LISTING]})
    assert LA.wrap(browser, {"SEARXNG_URL": "off"}) is browser
    monkeypatch.delenv("SEARXNG_URL")
    assert isinstance(S.default_backend(), LA.ListingAPIs)                                # SearXNG is on by default (alibaba only)
    routed = LA.wrap(browser, {})
    assert set(routed.apis) == {"alibaba_listings"}
    t = S.resolve("listings", "camera rain cover", "cjdropshipping.com")
    assert routed.read(t, 20) == browser.read(t, 20)                                      # no CJ key: the browser's own read
    shaped = [S.shape(t, b.read(t, 20), action=_action("same"), search_intent_id="si_supply", retrieved_at="2026-09-27T10:00:00Z", used=1,
                      cap=5, limit=20) for b in (browser, routed)]
    assert json.dumps(shaped[0], sort_keys=True) == json.dumps(shaped[1], sort_keys=True)


def test_the_key_is_read_from_the_environment_only():
    assert CJ.client_from_env({}) is None and CJ.client_from_env({"CJ_API_KEY": "  "}) is None
    assert isinstance(CJ.client_from_env({"CJ_API_KEY": _key()}), CJ.CJClient)
    src = (ROOT / "shared/polymath_shared/acquisition/cj_api.py").read_text()
    assert "print(" not in src and "log." not in src                                     # the client never logs or prints


# ─────────────────────────────────────────────────────────── alibaba.com through SearXNG
ALI = "https://www.alibaba.com/product-detail/Waterproof-Camera-Rain-Cover_1600123456789.html"
SNIPPET = ("Waterproof camera rain cover for DSLR. US$2.06-3.49. Min. order: 200 pieces. Find Complete Details about Waterproof Camera "
           "Rain Cover from Camera Bags Supplier or Manufacturer-Shenzhen Wjm Silicone & Plastic Electronic Co., Ltd.")
RESULTS = [
    {"url": ALI + "?spm=a2700.galleryofferlist", "title": "Waterproof Camera Rain Cover - Buy Rain Cover,Camera Cover Product on Alibaba.com",
     "content": SNIPPET, "engine": "bing"},
    {"url": ALI, "title": "Waterproof Camera Rain Cover", "content": "a duplicate of the first", "engine": "duckduckgo"},
    {"url": "https://www.alibaba.com/showroom/camera-rain-cover.html", "title": "Camera Rain Cover - Alibaba", "content": "a showroom"},
    {"url": "https://m.alibaba.com/product/1600123456789/Waterproof-Camera-Rain-Cover.html", "title": "mobile", "content": "mobile page"},
    {"url": "https://evil.example/www.alibaba.com/product-detail/Rain-Cover_1600999999999.html", "title": "spoof", "content": "x"},
    {"url": "https://www.aliexpress.com/item/1005001234567890.html", "title": "another site", "content": "US$1.00"},
    {"url": "https://www.alibaba.com/product-detail/Rain-Sleeve_1600555555555.html", "title": "Captcha Interception",
     "content": "Sorry, we have detected unusual traffic from your network. Please slide to verify."},
    {"url": "https://spanish.alibaba.com/product-detail/Lens-Hood_1600777777777.html", "title": "Lens Hood | Alibaba.com",
     "content": "MOQ: 50 pcs, $0.80 / piece"},
]


def _searx(results=RESULTS, unresponsive=(), status=200, seen=None, body=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if isinstance(body, Exception):
            raise body
        if body is not None:
            return httpx.Response(status, text=body)
        return httpx.Response(status, json={"query": request.url.params.get("q"), "results": list(results),
                                            "answers": [], "corrections": [], "infoboxes": [], "suggestions": [],
                                            "unresponsive_engines": [list(u) for u in unresponsive]})
    return httpx.MockTransport(handler)


def test_only_alibaba_product_pages_are_kept_and_read_from_the_snippet():
    seen = []
    raw = SX.SearXNGListings("http://127.0.0.1:8888", transport=_searx(seen=seen)).read(S.resolve("listings", "camera rain cover", "alibaba.com"), 20)
    (req,) = seen
    assert (req.url.path, req.url.params["q"], req.url.params["format"]) == ("/search", "site:alibaba.com camera rain cover", "json")
    assert [r["url"] for r in raw["records"]] == [ALI, "https://spanish.alibaba.com/product-detail/Lens-Hood_1600777777777.html"]
    first = raw["records"][0]["listing"]
    assert (first["title"], first["price_as_listed"], first["minimum_order_as_listed"], first["supplier"]) == \
        ("Waterproof Camera Rain Cover", "US$2.06-3.49", "200 pieces", "Shenzhen Wjm Silicone & Plastic Electronic Co., Ltd.")
    assert first["card"].startswith("Waterproof camera rain cover for DSLR")                         # the snippet, to check against
    second = raw["records"][1]["listing"]
    assert (second["title"], second["price_as_listed"], second["minimum_order_as_listed"], second["supplier"]) == ("Lens Hood", "$0.80", "50 pcs", None)
    notes = raw["backend_notes"]
    assert notes[0] == "found through search-engine results (SearXNG); snippet-level data" and any("as indexed" in n for n in notes)
    assert any(n.startswith("4 search result(s) were not alibaba.com product pages") for n in notes)
    assert any(n.startswith("1 search result(s) carried a verification page's text") for n in notes)


@pytest.mark.parametrize("url,expected", [
    (ALI, (ALI, "1600123456789")), (ALI + "#reviews", (ALI, "1600123456789")),
    ("http://alibaba.com/product-detail/x_12345678.html", ("https://alibaba.com/product-detail/x_12345678.html", "12345678")),
    ("https://www.alibaba.com/product-detail/x_1234567.html", None),                     # too short to be a product number
    ("https://www.alibaba.com/trade/search?SearchText=rain+cover", None), ("https://alibaba.com.evil.example/product-detail/x_12345678.html", None),
    ("javascript:alert(1)", None), ("", None), (None, None)])
def test_a_listing_url_is_an_alibaba_product_page_parsed_in_full(url, expected):
    assert SX.listing_url(url) == expected


@pytest.mark.parametrize("snippet,expected", [
    ("5% off $2,000 US$2.06-3.49 Min. order: 200 pieces", ("US$2.06-3.49", "200 pieces")),     # the price before the minimum order
    ("Price: $1.20 - $1.50 / piece; MOQ: 1,000 pcs", ("$1.20 - $1.50", "1,000 pcs")),
    ("Minimum order quantity: 2 sets. USD 35.50", ("USD 35.50", "2 sets")),
    ("High quality rain cover for travel cameras", (None, None)),                              # nothing shown, nothing guessed
    ("¥18.50 per piece, 1-10 pieces", (None, None))])
def test_price_and_minimum_order_come_from_the_snippet_verbatim(snippet, expected):
    got = SX.parse_snippet("Rain Cover | Alibaba.com", snippet, "Rain-Cover")
    assert (got["price_as_listed"], got["minimum_order_as_listed"]) == expected and got["title"] == "Rain Cover"


def _sx_backend(transport, browser_raw=None):
    browser = Browser(browser_raw or {"state": "ok", "records": [O.OpenCLIBackend._listing(ALI, "Rain cover", "Rain cover\n$3.20\nMin. order: 10 pieces")]})
    return LA.ListingAPIs(browser, {"alibaba_listings": SX.SearXNGListings("http://127.0.0.1:8888", transport=transport)}), browser


# ── SUPPLIER-PAGES (the owner, 2026-09-27: "with alibaba it should be multiple products"): the engines answer mostly with category
# pages, so a search reads more result pages while the listings are short of the limit
@pytest.fixture(autouse=True)
def _no_real_pacing(monkeypatch):
    """SUPPLIER-PACING: every test runs unpaced (a fake or zero pace); the pacing test sets its own interval."""
    monkeypatch.setattr(SX, "MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(SX, "_last_call", 0.0)


def _product(n: int, title: str = "Gloves") -> dict:
    return {"url": f"https://www.alibaba.com/product-detail/{title}_16000000000{n:02d}.html", "title": f"{title} {n} | Alibaba.com",
            "content": "US$1.00 MOQ: 10 pcs"}


def _category(n: int) -> dict:
    return {"url": f"https://www.alibaba.com/showroom/thing-{n}.html", "title": "showroom", "content": "many suppliers"}


def _pages(pages: dict[int, list[dict]], seen: list, fail_at: int | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        pageno = int(request.url.params.get("pageno") or 1)
        if fail_at == pageno:
            raise httpx.ConnectError("gone")
        return httpx.Response(200, json={"results": pages.get(pageno, []), "unresponsive_engines": []})
    return httpx.MockTransport(handler)


def _read(pages, limit, seen, **kw):
    return SX.SearXNGListings("http://127.0.0.1:8888", transport=_pages(pages, seen, **kw)).read(S.resolve("listings", "gloves", "alibaba.com"), limit)


def test_more_result_pages_are_read_until_the_limit_with_no_product_twice():
    seen: list = []
    pages = {1: [_category(i) for i in range(9)] + [_product(1)],
             2: [_category(i) for i in range(5)] + [_product(n) for n in (1, 2, 3, 4, 5)],          # product 1 again
             3: [_category(i) for i in range(5)] + [_product(n) for n in (6, 7, 8, 9, 10)]}
    raw = _read(pages, 8, seen)
    assert [r.url.params.get("pageno") for r in seen] == [None, "2", "3"]                   # page 1 is asked exactly as before
    refs = [r["ref"] for r in raw["records"]]
    assert len(refs) == 8 and len(set(refs)) == 8 and refs[:5] == [f"16000000000{n:02d}" for n in (1, 2, 3, 4, 5)]
    assert "3 result pages read" in raw["backend_notes"]


def test_a_short_page_is_the_engines_last_and_a_page_of_nothing_new_ends_the_search():
    seen: list = []
    raw = _read({1: [_category(i) for i in range(7)] + [_product(1)]}, 20, seen)                # 8 results: not a full page
    assert len(seen) == 1 and [r["ref"] for r in raw["records"]] == ["1600000000001"]
    seen = []
    raw = _read({1: [_category(i) for i in range(9)] + [_product(1)], 2: [_category(i) for i in range(9)] + [_product(1)]}, 20, seen)
    assert len(seen) == 2 and len(raw["records"]) == 1                                          # page 2 repeated page 1: stop


def test_a_later_page_that_fails_keeps_what_the_earlier_pages_gave():
    seen: list = []
    raw = _read({1: [_category(i) for i in range(7)] + [_product(n) for n in (1, 2, 3)]}, 20, seen, fail_at=2)
    assert len(seen) == 2 and [r["ref"] for r in raw["records"]] == [f"16000000000{n:02d}" for n in (1, 2, 3)]
    assert any(n.startswith("result page 2 was not read") for n in raw["backend_notes"])


def test_searches_are_paced_two_seconds_apart_across_pages_and_calls(monkeypatch):
    """SUPPLIER-PACING: the engines are asked no faster than one search every 2 s from this process."""
    monkeypatch.setattr(SX, "MIN_INTERVAL_S", 2.0)
    now, slept = [1000.0], []

    def clock():
        return now[0]

    def sleep(s):
        slept.append(round(s, 3))
        now[0] += s
    pages = {p: [_product(p * 10 + i) for i in range(10)] for p in range(1, 4)}
    backend = SX.SearXNGListings("http://127.0.0.1:8888", transport=_pages(pages, []), sleep=sleep, clock=clock)
    backend.read(S.resolve("listings", "gloves", "alibaba.com"), 100)
    assert slept == [2.0, 2.0]                                              # page 1 at once (the last call was long ago), then 2 s gaps
    now[0] += 0.5
    backend.read(S.resolve("listings", "hats", "alibaba.com"), 5)          # a new search 0.5 s later waits the rest of the 2 s
    assert slept[2] == 1.5


def test_at_most_three_result_pages_are_read():
    seen: list = []
    pages = {p: [_product(p * 10 + i) for i in range(10)] for p in range(1, 6)}
    raw = _read(pages, 100, seen)
    assert len(seen) == 3 and len(raw["records"]) == 30


def test_cj_results_are_ranked_by_the_querys_words_and_cjs_order_breaks_ties():
    """SUPPLIER-RANK: CJ led with keyboard and welder's gloves for "touchscreen winter gloves"."""
    name = lambda p: p.get("nameEn")
    ps = [{"nameEn": "Keyboard gloves"}, {"nameEn": "Arthritis pressure gloves"}, {"nameEn": "Velvet Gloves Flip Touch Screen Half"},
          {"nameEn": "Winter gloves touchscreen warm"}, {"nameEn": "Winter knitted gloves"}]
    # "gloves" is on every name and decides nothing; "touchscreen" (rare, and "Touch Screen" holds it) outweighs "winter"
    assert [p["nameEn"] for p in CJ.rank_by_query(ps, "touchscreen winter gloves", name)] == [
        "Winter gloves touchscreen warm", "Velvet Gloves Flip Touch Screen Half", "Winter knitted gloves", "Keyboard gloves",
        "Arthritis pressure gloves"]
    assert CJ.rank_by_query(ps, "", name) == ps and CJ.rank_by_query([], "gloves", name) == []
    assert CJ.query_words("Touch-screen WINTER gloves, a 2nd time") == ("touch", "screen", "winter", "gloves", "2nd", "time")


def test_alibaba_listings_through_searxng_say_so_and_never_open_the_site():
    backend, browser = _sx_backend(_searx())
    out = _acquire(backend, "alibaba.com", "searx-ok")
    assert out["status"] == "OK" and browser.reads == [] and len(out["items"]) == 2
    assert {s["source_class"] for s in out["sources"]} == {"supplier_listing"}
    assert "found through search-engine results (SearXNG); snippet-level data" in out["limitations"]


@pytest.mark.parametrize("transport,reason", [
    (_searx(body=httpx.ConnectError("connection refused")), "unreachable"),
    (_searx(results=[], unresponsive=[("bing", "timeout"), ("duckduckgo", "CAPTCHA"), ("brave", "too many requests")]), "unreachable"),
    (_searx(status=403, body="<html>forbidden</html>"), "refused"),
    (_searx(body="<html>not searxng</html>"), "bad_reply")])
def test_searxng_that_cannot_answer_falls_back_to_the_browser_said_and_counted(transport, reason):
    backend, browser = _sx_backend(transport)
    before = LA.counts().get("alibaba_listings", {}).get("fallbacks", 0)
    out = _acquire(backend, "alibaba.com", ["searx-fallback", reason, id(transport)])
    assert browser.reads == [("alibaba_listings", 20)] and out["status"] == "OK"
    said = [x for x in out["limitations"] if x.startswith("the SearXNG search could not answer")]
    assert len(said) == 1 and f"({reason}:" in said[0] and "the host browser read alibaba.com instead" in said[0]
    assert backend.status()["listing_apis"]["alibaba_listings"]["fallbacks"] == before + 1


def test_every_engine_failing_is_named_and_a_partial_answer_is_kept():
    raw = SX.SearXNGListings("http://127.0.0.1:8888", transport=_searx(results=RESULTS[:1], unresponsive=[("brave", "too many requests")])).read(
        S.resolve("listings", "rain cover", "alibaba.com"), 20)
    assert len(raw["records"]) == 1 and any("search engines that did not answer: brave (too many requests)" in n for n in raw["backend_notes"])


@pytest.mark.parametrize("env,expected", [({}, "http://127.0.0.1:8888"), ({"SEARXNG_URL": ""}, "http://127.0.0.1:8888"),
                                          ({"SEARXNG_URL": "http://127.0.0.1:9999/"}, "http://127.0.0.1:9999"), ({"SEARXNG_URL": "off"}, None),
                                          ({"SEARXNG_URL": "OFF"}, None), ({"SEARXNG_URL": "ftp://127.0.0.1"}, None), ({"SEARXNG_URL": "not a url"}, None)])
def test_searxng_is_on_by_default_and_off_says_off(env, expected):
    assert SX.base_url(env) == expected


# ─────────────────────────────────────────────────────────── the compose service and its settings
def test_the_searxng_service_is_local_capped_pinned_and_opt_in():
    services = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]
    assert set(services) == {"postgres", "qdrant", "neo4j", "redis", "searxng"}
    sx = services["searxng"]
    image, _, tag = sx["image"].partition(":")
    assert image == "searxng/searxng" and tag and tag != "latest" and tag[0].isdigit()          # a pinned tag
    assert sx["ports"] == ["127.0.0.1:8888:8080"]                                                # loopback only
    assert sx["deploy"]["resources"]["limits"] == {"cpus": "0.5", "memory": "256M"}
    assert sx["volumes"] == ["./deployment/searxng/settings.yml:/etc/searxng/settings.yml:ro"]
    assert "SEARXNG_SECRET" in sx["environment"] and "FORCE_OWNERSHIP=false" in sx["environment"]  # the secret passes through, unwritten
    assert sx["profiles"] == ["search"]                                                          # `docker compose up` stays the stores
    for name in ("postgres", "qdrant", "neo4j", "redis"):
        assert "profiles" not in services[name]


def test_the_searxng_settings_serve_json_from_five_engines_with_no_limiter_and_no_secret():
    text = (ROOT / "deployment/searxng/settings.yml").read_text()
    s = yaml.safe_load(text)
    assert s["use_default_settings"]["engines"]["keep_only"] == ["bing", "duckduckgo", "brave", "qwant", "yahoo"]
    assert "json" in s["search"]["formats"] and s["server"]["limiter"] is False and s["server"]["public_instance"] is False
    assert "secret_key" not in s["server"] and "ultrasecretkey" not in text
    assert "outgoing" not in s and "proxies" not in text.replace("No proxies", "") and "using_tor_proxy" not in text
    assert [e for e in s["engines"] if e["name"] == "bing"] == [{"name": "bing", "disabled": False}]


def test_the_env_template_names_the_keys_with_empty_values():
    lines = (ROOT / ".env.example").read_text().splitlines()
    for name in ("CJ_API_KEY", "SEARXNG_URL", "SEARXNG_SECRET"):
        (line,) = [ln for ln in lines if ln.startswith(name + "=")]
        assert line == name + "=", line
        assert lines[lines.index(line) - 1].startswith("# "), name                                # one comment line each
    assert not any(ln.startswith(("EXA_API_KEY", "CJ_ACCOUNT_EMAIL")) for ln in lines)
