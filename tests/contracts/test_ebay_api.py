"""PRODUCT-DECISION-REPORT-V1 §4.3 (slice B2): eBay's Browse API as the report's eBay comparables, READ-ONLY.
  * the owner's free developer keyset (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET, environment only): unset = EBAY_NOT_CONFIGURED, never
    an error; set = an application token (OAuth client credentials, cached until it nearly expires, renewed once on a 401);
  * one read: item_summary/search on EBAY_US with a ship-to end-user context, NEW fixed-price items that ship to the buyer;
    results in the report's listing shape (price_usd, shipping_usd, delivery_min / delivery_max dates, location, condition, url,
    title); untrusted text cleaned and capped, only eBay item URLs kept, answers read up to a byte cap;
  * paced one call at a time per keyset; a circuit breaker after an auth or a rate-limit failure; typed reason codes; the secret
    and tokens never reach an error; sold history (a restricted API) is never called.
Fake HTTP only (httpx.MockTransport) and a fake clock: no call reaches eBay. The search answer is SYNTHETIC (its file name and its
`_synthetic` key say so): hand-built to the documented response shape, because no eBay answer could be recorded."""
from __future__ import annotations

import ast
import base64
import hashlib
import itertools
import json
import pathlib
import re
import sys
import urllib.parse

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import ebay_api as EB
from polymath_shared.acquisition.listing_apis import ApiFailed

FX = ROOT / "tests" / "fixtures" / "product_report_host"
SYNTHETIC = FX / "SYNTHETIC_ebay_item_summary_search_slicker_brush.json"
_SEQ = itertools.count()
TOKEN_VALUE = "v^1.1#i^1#SYNTHETIC-APP-TOKEN#" + "t" * 40


def _keyset() -> tuple[str, str]:
    """A fresh fake keyset per client: the token cache, the pacing and the breaker are per keyset, in this process."""
    n = next(_SEQ)
    return f"SynthApp-Polymath-PRD-{n:04d}", "PRD-" + hashlib.sha256(f"ebay-secret-{n}".encode()).hexdigest()[:36]


def _search_doc() -> dict:
    return json.loads(SYNTHETIC.read_text())


def _token(ttl=7200, value=TOKEN_VALUE):
    return lambda req: httpx.Response(200, json={"access_token": value, "expires_in": ttl, "token_type": "Application Access Token"})


def _search(doc=None, status=200):
    return lambda req: httpx.Response(status, json=doc if doc is not None else _search_doc())


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def clock(self):
        return self.t


class FakeEbay:
    """eBay's API: `token` / `search` are reply factories (request -> Response), exceptions, or lists of them (one per call)."""

    def __init__(self, token=None, search=None, clock: Clock | None = None):
        self.calls: list[httpx.Request] = []
        self.stamps: list[float] = []
        self.token, self.search, self.clock = token or _token(), search or _search(), clock

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        self.stamps.append(self.clock.clock() if self.clock else 0.0)
        reply = self.token if request.url.path == EB.TOKEN else self.search if request.url.path == EB.SEARCH else None
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        if isinstance(reply, Exception):
            raise reply
        return reply(request) if reply is not None else httpx.Response(404, json={})

    def paths(self) -> list[str]:
        return [r.url.path for r in self.calls]


def _client(fake, clock=None, keyset=None, **kw) -> EB.EbayClient:
    clock = clock or Clock()
    fake.clock = fake.clock or clock
    cid, secret = keyset or _keyset()
    return EB.EbayClient(cid, secret, transport=httpx.MockTransport(fake), sleep=clock.sleep, clock=clock.clock, **kw)


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(EB.__file__).resolve().is_relative_to(ROOT), EB.__file__


def test_the_fixture_says_it_is_synthetic():
    doc = _search_doc()
    assert "SYNTHETIC" in SYNTHETIC.name and doc["_synthetic"].startswith("SYNTHETIC:") and "No eBay call was made" in doc["_synthetic"]


# ─────────────────────────────────────────────────────────── what exists: the sign-in and one read
def test_only_the_sign_in_and_one_search_exist_and_sold_history_is_never_called():
    assert EB.ENDPOINTS == ("/identity/v1/oauth2/token", "/buy/browse/v1/item_summary/search")
    text = (ROOT / "shared/polymath_shared/acquisition/ebay_api.py").read_text()
    tree = ast.parse(text)
    in_fstrings = {id(v) for j in ast.walk(tree) if isinstance(j, ast.JoinedStr) for v in j.values}
    routes = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in in_fstrings
              and re.fullmatch(r"/[A-Za-z][\w/]*", n.value)}
    assert routes == set(EB.ENDPOINTS), routes                          # no other eBay route is named
    assert not re.search(r"item_sales|marketplace_insights|/order|/bidding|/checkout|/offer/", text)
    assert EB.SCOPE == "https://api.ebay.com/oauth/api_scope" and EB.MARKETPLACE == "EBAY_US"


# ─────────────────────────────────────────────────────────── not configured
def test_without_the_keyset_ebay_is_not_configured_and_that_is_never_an_error():
    assert EB.client_from_env({}) is None and EB.missing({}) == [EB.ID_ENV, EB.SECRET_ENV]
    assert EB.client_from_env({EB.ID_ENV: "SynthApp"}) is None and EB.missing({EB.ID_ENV: "SynthApp"}) == [EB.SECRET_ENV]
    assert EB.client_from_env({EB.ID_ENV: "  ", EB.SECRET_ENV: "x"}) is None and not EB.configured({EB.SECRET_ENV: "x"})
    why = EB.not_configured_why({EB.SECRET_ENV: "s3cr3t-value-never-shown"})
    assert EB.ID_ENV in why and EB.SECRET_ENV not in why and "s3cr3t" not in why and ".env.example" in why
    cid, secret = _keyset()
    client = EB.client_from_env({EB.ID_ENV: cid, EB.SECRET_ENV: secret})
    assert isinstance(client, EB.EbayClient) and EB.configured({EB.ID_ENV: cid, EB.SECRET_ENV: secret})
    with pytest.raises(ValueError):
        EB.EbayClient("", secret)


# ─────────────────────────────────────────────────────────── the search
def test_a_search_signs_in_with_client_credentials_and_asks_ebay_us_as_a_buyer_in_the_ship_to_country():
    fake, clock, (cid, secret) = FakeEbay(), Clock(), _keyset()
    got = _client(fake, clock, (cid, secret)).search("  self cleaning   slicker brush ", ship_to="us", limit=30)
    tok, srch = fake.calls
    assert (tok.method, tok.url.host, tok.url.path) == ("POST", "api.ebay.com", EB.TOKEN)
    assert tok.headers["authorization"] == "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode()
    assert urllib.parse.parse_qs(tok.content.decode()) == {"grant_type": ["client_credentials"], "scope": [EB.SCOPE]}
    assert (srch.method, srch.url.host, srch.url.path) == ("GET", "api.ebay.com", EB.SEARCH)
    assert dict(srch.url.params) == {"q": "self cleaning slicker brush", "limit": "30",
                                     "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW},deliveryCountry:US"}
    assert srch.headers["x-ebay-c-marketplace-id"] == "EBAY_US"
    assert srch.headers["x-ebay-c-enduserctx"] == "contextualLocation=country%3DUS"
    assert srch.headers["authorization"] == f"Bearer {TOKEN_VALUE}"
    assert got["request"] == {"q": "self cleaning slicker brush", "limit": 30, "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW},deliveryCountry:US",
                              "marketplace": "EBAY_US", "ship_to": "US", "ship_to_zip_given": False}
    assert got["total"] == 412 and got["unusable"] == 1 and len(got["listings"]) == 7
    assert got["listings"][0] == {"title": "Self Cleaning Slicker Brush for Dogs and Cats, Pet Grooming Brush",
                                  "url": "https://www.ebay.com/itm/100000000001", "price_usd": 12.99, "shipping_usd": 0.0,
                                  "delivery_min": "2026-11-05", "delivery_max": "2026-11-08", "location": "US", "condition": "New",
                                  "item_id": "v1|100000000001|0", "us_listing": True}
    zipped = FakeEbay()
    _client(zipped, ship_to_zip="66952").search("slicker brush", ship_to="GB")
    assert zipped.calls[1].headers["x-ebay-c-enduserctx"] == "contextualLocation=country%3DGB%2Czip%3D66952"
    assert zipped.calls[1].url.params["filter"].endswith("deliveryCountry:GB")


def test_listings_are_normalised_as_untrusted_text_capped_and_only_ebay_item_urls_kept():
    got = _client(FakeEbay()).search("self cleaning slicker brush")
    by_id = {row["item_id"]: row for row in got["listings"]}
    china = by_id["v1|100000000002|0"]
    assert (china["price_usd"], china["shipping_usd"], china["delivery_min"], china["delivery_max"], china["location"],
            china["us_listing"]) == (6.49, 1.99, "2026-11-12", "2026-11-26", "CN", False)
    two = by_id["v1|100000000003|0"]                                        # the cheaper of two shipping options
    assert (two["shipping_usd"], two["delivery_min"], two["delivery_max"]) == (3.49, "2026-11-06", "2026-11-10")
    hidden = by_id["v1|100000000004|0"]                                     # zero-width + right-to-left override removed
    assert hidden["title"] == "Self Cleaning Slicker Brush for Shedding Dogs" and hidden["shipping_usd"] is None
    assert (hidden["delivery_min"], hidden["delivery_max"]) == ("2026-11-06", "2026-11-11")       # CALCULATED: dates, no cost
    uk = by_id["v1|100000000008|0"]
    assert uk["price_usd"] is None and uk["shipping_usd"] == 8.5 and uk["location"] == "GB"      # not stated in USD: no number
    assert "v1|100000000007|0" not in by_id                                 # ebay.com.example.net is not eBay: unusable
    assert all(re.fullmatch(r"https://www\.ebay\.com/itm/\d{12}", row["url"]) for row in got["listings"])   # tracking query dropped
    long = {"title": "Slicker Brush " + "x" * 500, "itemWebUrl": "http://www.ebay.com/itm/1?hash=a#b",
            "shippingOptions": [{"shippingCost": {"value": "2.00", "currency": "USD"}, "minEstimatedDeliveryDate": "2026-11-09T00:00:00Z",
                                 "maxEstimatedDeliveryDate": "2026-11-03T00:00:00Z"}], "price": {"value": "abc", "currency": "USD"},
            "condition": "New\x00\x07", "itemLocation": {"country": "usa"}}
    row = EB.listing(long)
    assert len(row["title"]) == EB.TITLE_MAX and row["url"] == "https://www.ebay.com/itm/1" and row["price_usd"] is None
    assert (row["delivery_min"], row["delivery_max"]) == ("2026-11-03", "2026-11-09") and row["condition"] == "New"
    assert row["location"] is None and row["us_listing"] is None
    for bad in ("https://www.ebay.com@evil.example/itm/1", "javascript:alert(1)", "https://ebay.com.evil.example/itm/1",
                "https://www.ebay.com/itm/1<script>", "ftp://www.ebay.com/itm/1", None, 7):
        assert EB.item_url(bad) is None, bad
    assert EB.listing({"title": "x", "itemWebUrl": None}) is None and EB.listing("not an item") is None


def test_an_empty_answer_has_no_item_list_and_a_malformed_one_is_a_bad_reply():
    got = _client(FakeEbay(search=_search({"total": 0, "limit": 30, "offset": 0}))).search("candle warmer")
    assert got["listings"] == [] and got["total"] == 0 and got["unusable"] == 0
    with pytest.raises(ApiFailed) as exc:
        _client(FakeEbay(search=_search({"itemSummaries": "nope"}))).search("candle warmer")
    assert exc.value.reason == "bad_reply" and EB.REASON_CODES[exc.value.reason] == "EBAY_BAD_REPLY"
    with pytest.raises(ApiFailed) as exc:
        _client(FakeEbay()).search("x")
    assert exc.value.reason == "bad_request"
    with pytest.raises(ApiFailed) as exc:
        _client(FakeEbay()).search("slicker brush", ship_to="USA")
    assert exc.value.reason == "bad_request"


# ─────────────────────────────────────────────────────────── the token
def test_the_token_is_cached_until_it_nearly_expires_and_a_401_renews_it_once():
    clock, keyset = Clock(), _keyset()
    fake = FakeEbay(clock=clock)
    client = _client(fake, clock, keyset)
    client.search("slicker brush"), client.search("slicker brush")
    assert fake.paths() == [EB.TOKEN, EB.SEARCH, EB.SEARCH]
    _client(fake, clock, keyset).search("slicker brush")                   # another client, same keyset: same cached token
    assert fake.paths().count(EB.TOKEN) == 1
    clock.sleep(7200 - EB.TOKEN_MARGIN_S + 1)                               # within the margin of its expiry: signed in again
    client.search("slicker brush")
    assert fake.paths().count(EB.TOKEN) == 2
    stale = FakeEbay(search=[lambda r: httpx.Response(401, json={"errors": [{"errorId": 1001, "message": "Invalid access token"}]}),
                             _search()])
    assert len(_client(stale).search("slicker brush")["listings"]) == 7
    assert stale.paths() == [EB.TOKEN, EB.SEARCH, EB.TOKEN, EB.SEARCH]     # dropped, signed in once more, asked again
    dead = FakeEbay(search=lambda r: httpx.Response(401, json={"errors": [{"errorId": 1001, "message": "Invalid access token"}]}))
    with pytest.raises(ApiFailed) as exc:
        _client(dead).search("slicker brush")
    assert exc.value.reason == "auth" and dead.paths() == [EB.TOKEN, EB.SEARCH, EB.TOKEN, EB.SEARCH]   # renewed once, never more
    bad = FakeEbay(token=lambda r: httpx.Response(200, json={"token_type": "Application Access Token"}))
    with pytest.raises(ApiFailed) as exc:
        _client(bad).search("slicker brush")
    assert exc.value.reason == "bad_reply"


# ─────────────────────────────────────────────────────────── the circuit breaker
def test_an_auth_failure_opens_the_breaker_no_call_reaches_ebay_until_the_window_passes():
    clock, keyset = Clock(), _keyset()
    fake = FakeEbay(token=lambda r: httpx.Response(401, json={"error": "invalid_client", "error_description": "client authentication failed"}),
                    clock=clock)
    with pytest.raises(ApiFailed) as exc:
        _client(fake, clock, keyset).search("slicker brush")
    assert exc.value.reason == "auth" and EB.REASON_CODES["auth"] == "EBAY_AUTH" and exc.value.retry_after_s is None
    assert "invalid_client" in exc.value.detail and fake.paths() == [EB.TOKEN]
    t_before = clock.t
    for _ in range(3):                                                      # any client of this keyset: answered at once
        with pytest.raises(ApiFailed) as exc:
            _client(fake, clock, keyset).search("candle warmer")
        assert exc.value.reason == "auth" and "eBay was not called again" in exc.value.detail and exc.value.retry_after_s > 590
    assert fake.paths() == [EB.TOKEN] and clock.t == t_before               # no network call, no pacing wait
    held = _client(fake, clock, keyset).breaker()
    assert held["reason"] == "auth" and 590 < held["retry_after_s"] <= 600
    clock.sleep(EB.BREAKER_S + 1)
    assert _client(fake, clock, keyset).breaker() is None
    with pytest.raises(ApiFailed):
        _client(fake, clock, keyset).search("slicker brush")
    assert fake.paths() == [EB.TOKEN, EB.TOKEN]                             # the window passed: eBay is asked again
    scope = FakeEbay(token=lambda r: httpx.Response(400, json={"error": "invalid_scope", "error_description": "scope not granted"}))
    with pytest.raises(ApiFailed) as exc:
        _client(scope).search("slicker brush")
    assert exc.value.reason == "auth"                                       # a keyset that cannot sign in is a keyset problem


def test_a_rate_limit_opens_the_short_window_and_other_failures_none():
    clock, keyset = Clock(), _keyset()
    fake = FakeEbay(search=lambda r: httpx.Response(429, json={"errors": [{"errorId": 2001, "message": "Too many requests."}]}), clock=clock)
    with pytest.raises(ApiFailed) as exc:
        _client(fake, clock, keyset).search("slicker brush")
    assert exc.value.reason == "rate_limit" and "2001" in exc.value.detail and EB.REASON_CODES["rate_limit"] == "EBAY_RATE_LIMITED"
    assert fake.paths().count(EB.SEARCH) == 1                               # not retried: it is usually the day's quota
    assert EB.RATE_BREAKER_S - 10 < _client(fake, clock, keyset).breaker()["retry_after_s"] <= EB.RATE_BREAKER_S
    cases = [(lambda r: httpx.Response(503, text="busy"), "server"),
             (lambda r: httpx.Response(400, json={"errors": [{"errorId": 12001, "message": "Invalid filter"}]}), "bad_request"),
             (lambda r: httpx.Response(404, json={"errors": [{"errorId": 11001, "message": "Not found"}]}), "refused"),
             (lambda r: httpx.Response(200, text="<html>not json</html>"), "bad_reply"),
             (httpx.ConnectError("connection refused"), "network"), (httpx.ReadTimeout("slow"), "network")]
    for reply, reason in cases:
        clock2, keyset2 = Clock(), _keyset()
        fake2 = FakeEbay(search=reply, clock=clock2)
        with pytest.raises(ApiFailed) as exc:
            _client(fake2, clock2, keyset2).search("slicker brush")
        assert exc.value.reason == reason, (reason, exc.value)
        assert _client(fake2, clock2, keyset2).breaker() is None, reason   # no window for these
    assert set(EB.REASON_CODES.values()) == {"EBAY_AUTH", "EBAY_RATE_LIMITED", "EBAY_NETWORK", "EBAY_SERVER_ERROR", "EBAY_BAD_REPLY",
                                             "EBAY_BAD_REQUEST", "EBAY_REFUSED", "EBAY_ERROR"}


# ─────────────────────────────────────────────────────────── pacing, size, secrets
def test_calls_are_paced_one_at_a_time_per_keyset_on_the_clock():
    clock, keyset = Clock(), _keyset()
    fake = FakeEbay(clock=clock)
    client = _client(fake, clock, keyset)
    for term in ("slicker brush", "candle warmer", "pet hair remover"):
        client.search(term)
    assert fake.paths() == [EB.TOKEN, EB.SEARCH, EB.SEARCH, EB.SEARCH]
    gaps = [b - a for a, b in zip(fake.stamps, fake.stamps[1:])]
    assert all(g >= EB.MIN_INTERVAL_S - 1e-9 for g in gaps), gaps
    assert clock.sleeps and all(s <= EB.MIN_INTERVAL_S for s in clock.sleeps)
    slow = FakeEbay(clock=clock)
    _client(slow, clock, keyset, min_interval_s=3.0).search("slicker brush")   # the spacing is per keyset, not per client
    assert slow.stamps[0] - fake.stamps[-1] >= 3.0 - 1e-9


class _Endless(httpx.SyncByteStream):
    def __init__(self):
        self.chunks = 0

    def __iter__(self):
        while self.chunks < 10_000:
            self.chunks += 1
            yield b'{"itemSummaries": [' if self.chunks == 1 else b" " * 1024


def test_an_oversized_answer_is_refused_without_reading_it_all():
    declared = FakeEbay(search=lambda r: httpx.Response(200, headers={"content-length": str(10**9)}, stream=_Endless()))
    with pytest.raises(ApiFailed) as exc:
        _client(declared, max_bytes=4096).search("slicker brush")
    assert exc.value.reason == "bad_reply" and "larger than 4096 bytes" in exc.value.detail
    stream = _Endless()
    chunked = FakeEbay(search=lambda r: httpx.Response(200, stream=stream))
    with pytest.raises(ApiFailed) as exc:
        _client(chunked, max_bytes=4096).search("slicker brush")
    assert exc.value.reason == "bad_reply" and stream.chunks <= 6           # stopped reading at the cap


def test_the_secret_and_the_token_never_reach_an_error():
    keyset = _keyset()
    cid, secret = keyset
    echo = FakeEbay(token=lambda r: httpx.Response(401, json={"error": "invalid_client",
                                                               "error_description": f"bad {secret} for {cid}"}))
    with pytest.raises(ApiFailed) as exc:
        _client(echo, keyset=keyset).search("slicker brush")
    assert secret not in str(exc.value) and cid not in str(exc.value) and "[redacted]" in str(exc.value)
    echo2 = FakeEbay(search=lambda r: httpx.Response(400, json={"errors": [{"errorId": 12001, "message": f"token {TOKEN_VALUE} odd"}]}))
    with pytest.raises(ApiFailed) as exc:
        _client(echo2).search("slicker brush")
    assert TOKEN_VALUE not in str(exc.value) and "[redacted]" in str(exc.value)
    got = _client(FakeEbay(), keyset=_keyset()).search("slicker brush")
    assert TOKEN_VALUE not in json.dumps(got)


def test_the_env_template_names_the_two_keys_with_empty_values():
    lines = (ROOT / ".env.example").read_text().splitlines()
    for name in (EB.ID_ENV, EB.SECRET_ENV):
        (line,) = [ln for ln in lines if ln.startswith(name + "=")]
        assert line == name + "=", line
        assert lines[lines.index(line) - 1].startswith("# "), name          # one comment line each
