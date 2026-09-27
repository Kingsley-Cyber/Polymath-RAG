"""ALIBABA LISTINGS FROM SEARCH-ENGINE RESULTS (SUPPLIER-APIS, the owner's decision of 2026-09-27): the local SearXNG, never
alibaba.com's own pages.

alibaba.com puts a human check in front of an automated reader of its search page (the R7 run: every call). This reader asks the
owner's LOCAL SearXNG (compose service `searxng`, loopback only; engines bing, duckduckgo and brave; `deployment/searxng/
settings.yml`): `GET {SEARXNG_URL}/search?q=site:alibaba.com <query>&format=json`, and reads only what the search engines
returned: a result's URL, title and snippet. It keeps a result only when its URL is an alibaba.com PRODUCT page
(`/product-detail/<name>_<number>.html`, the pattern of `adapters/ecommerce/python/sourcing_exa.py`, parsed strictly and kept
without its query), and reads the title, the price and the minimum order from the snippet where it shows them, verbatim; a result
whose text is a verification page is left out (`challenge.looks_like_challenge`). It never opens an alibaba.com page. SearXNG not
reachable, answering with something else than its JSON, or every engine failing = `ApiFailed`: the host browser reads the site
as before, said and counted (`listing_apis`). `SEARXNG_URL` unset or empty = http://127.0.0.1:8888; `off` = not used."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from polymath_shared.acquisition.challenge import looks_like_challenge
from polymath_shared.acquisition.listing_apis import ApiFailed
from polymath_shared.acquisition.service import Target, now_iso

DEFAULT_URL = "http://127.0.0.1:8888"
LABEL = "SearXNG search"
SITE = "alibaba.com"
TIMEOUT_S = 20.0
#: SUPPLIER-PAGES (the owner, 2026-09-27: "with alibaba it should be multiple products"): the engines answer mostly with Alibaba's
#: category and showroom pages (live: 1 product page in 40 results on page 1, 5 more on page 2), so a search reads up to MAX_PAGES
#: result pages while the listings are still short of the limit; a page with fewer than FULL_PAGE results is the engines' last
MAX_PAGES = 3
FULL_PAGE = 10
#: the notes every SearXNG answer carries into `limitations` (the first is the owner's wording)
SOURCE_NOTE = "found through search-engine results (SearXNG); snippet-level data"
INDEX_NOTE = ("each listing's title, price and minimum order are the search engines' snippet as indexed: the listing page itself was not "
              "opened, and it may have changed since")
OFF = frozenset({"off", "0", "false", "no", "none"})
_PRODUCT_PATH = re.compile(r"/product-detail/([^/?#]+?)_(\d{8,})\.html", re.IGNORECASE)
_PRICE = re.compile(r"(?:US\s?\$|USD\s?\$?|\$)\s?\d[\d,]*(?:\.\d+)?(?:\s*[-–~]\s*(?:US\s?\$|USD\s?\$?|\$)?\s?\d[\d,]*(?:\.\d+)?)?", re.IGNORECASE)
_MIN_ORDER = re.compile(r"(?:MOQ|Min(?:imum)?\.?\s*order(?:\s*quantity)?)\s*[:：]?\s*(\d[\d,]*)\s*(pieces?|pcs?|units?|sets?|pairs?|packs?|boxes|box|bags?"
                        r"|meters?|kilograms?|kgs?|tons?|rolls?|dozens?|cartons?)(?![a-z])", re.IGNORECASE)
#: a product page's indexed description names its seller as "... Supplier or Manufacturer-<company>"; else a company name as a card shows it
_MAKER = re.compile(r"Supplier\s+or\s+Manufacturer\s*-\s*([^.;|]{2,120}?(?:Co\.,?\s?Ltd\.?|Co\.,?\s?Limited|Company\s+Limited|Corporation|Inc\.|Factory"
                    r"|Limited|Ltd\.?))", re.IGNORECASE)
_COMPANY = re.compile(r"([A-Z][A-Za-z]+(?:[ &,.'-]+[A-Za-z&]+)*?\s(?:Co\.,?\s?Ltd\.?|Co\.,?\s?Limited|Company\s+Limited|Corporation|Inc\.|Factory))")
_TITLE_TAIL = re.compile(r"\s*(?:[-|–]\s*)?(?:Buy\s.+?\son\s+Alibaba\.com|Alibaba\.com)\s*$", re.IGNORECASE)


def base_url(env: Mapping[str, str]) -> str | None:
    """The SearXNG to ask: `SEARXNG_URL` (unset or empty = the local default), None when it is `off` or not an http(s) URL."""
    raw = str(env.get("SEARXNG_URL") or "").strip()
    if raw.lower() in OFF:
        return None
    url = (raw or DEFAULT_URL).rstrip("/")
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    return url if parts.scheme in ("http", "https") and parts.hostname else None


def listing_url(url: Any) -> tuple[str, str] | None:
    """(the product page's URL without its query or fragment, its product number) when `url` is an alibaba.com product page."""
    try:
        parts = urlsplit(str(url or "").strip())
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not (host == SITE or host.endswith("." + SITE)):
        return None
    m = _PRODUCT_PATH.fullmatch(parts.path)
    return (f"https://{host}{parts.path}", m.group(2)) if m else None


def parse_snippet(title: str, snippet: str, slug: str) -> dict[str, Any]:
    """The listing as the search result shows it: the title (the site's tail cut off), the price as listed (the last one before the
    minimum order, as on a listing card, where one stands before it; else the first), the minimum order as listed and the supplier;
    the snippet itself is kept (`card`) so every parsed field can be checked against it. Nothing is guessed: what the snippet does
    not show stays None."""
    title = _TITLE_TAIL.sub("", " ".join(str(title or "").split())).strip(" -|") or slug.replace("-", " ").strip()
    text = " ".join(str(snippet or "").split())
    moq = _MIN_ORDER.search(text)
    before = _PRICE.findall(text[: moq.start()]) if moq else []
    anywhere = _PRICE.findall(text)
    price = (before[-1] if before else anywhere[0]).strip() if (before or anywhere) else None
    supplier = _MAKER.search(text) or _COMPANY.search(text)
    return {"title": title[:300], "price_as_listed": price, "minimum_order_as_listed": f"{moq.group(1)} {moq.group(2)}" if moq else None,
            "supplier": supplier.group(1).strip() if supplier else None, "card": text[:300]}


class SearXNGListings:
    """The `alibaba_listings` reader over a SearXNG instance (see the module docstring)."""

    reader, label = "alibaba_listings", LABEL

    def __init__(self, base: str, *, transport: httpx.BaseTransport | None = None):
        self.base, self.transport = base.rstrip("/"), transport

    def _page(self, query: str, pageno: int) -> tuple[list[Any], list[str]]:
        """One result page: (results, the engines that did not answer). Raises ApiFailed."""
        params: dict[str, Any] = {"q": f"site:{SITE} {query}", "format": "json"}
        if pageno > 1:
            params["pageno"] = pageno
        try:
            with httpx.Client(transport=self.transport, timeout=TIMEOUT_S) as client:
                r = client.get(f"{self.base}/search", params=params, headers={"Accept": "application/json"})
        except httpx.TimeoutException:
            raise ApiFailed("unreachable", f"SearXNG at {self.base} did not answer in time") from None
        except httpx.TransportError as exc:
            raise ApiFailed("unreachable", f"SearXNG is not reachable at {self.base} ({type(exc).__name__}; start it: docker compose up -d searxng)") from None
        if r.status_code == 403:
            raise ApiFailed("refused", "SearXNG refused the JSON format (HTTP 403): search.formats must list json")
        if r.status_code != 200:
            raise ApiFailed("server" if r.status_code >= 500 else "refused", f"SearXNG answered HTTP {r.status_code}")
        try:
            data = r.json()
        except ValueError:
            raise ApiFailed("bad_reply", "SearXNG's answer is not JSON (is SEARXNG_URL another service?)") from None
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise ApiFailed("bad_reply", "SearXNG's answer holds no result list")
        failed = [f"{e[0]} ({e[1]})" for e in data.get("unresponsive_engines") or [] if isinstance(e, (list, tuple)) and len(e) >= 2]
        if not results and failed:
            raise ApiFailed("unreachable", "every search engine failed: " + "; ".join(failed)[:300])
        return results, failed

    def read(self, target: Target, limit: int) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        failed: dict[str, None] = {}
        other, walls, pages = 0, 0, 0
        page_error: str | None = None
        for pageno in range(1, MAX_PAGES + 1):
            try:
                results, page_failed = self._page(target.query or "", pageno)
            except ApiFailed as exc:
                if pageno == 1:
                    raise
                page_error = f"result page {pageno} was not read ({exc})"      # what the earlier pages gave is kept
                break
            pages += 1
            failed.update(dict.fromkeys(page_failed))
            added = 0
            for res in results:
                found = listing_url(res.get("url")) if isinstance(res, dict) else None
                if found is None:
                    other += 1
                    continue
                url, number = found
                if number in seen:                                       # the same product on a later page, or twice on one
                    continue
                title, snippet = str(res.get("title") or ""), str(res.get("content") or "")
                if looks_like_challenge(f"{title}\n{snippet}"):         # the engine indexed a verification page: never a listing
                    walls += 1
                    continue
                seen.add(number)
                slug = _PRODUCT_PATH.fullmatch(urlsplit(url).path).group(1)
                listing = parse_snippet(title, snippet, slug)
                text = (f"{listing['title']} · price as listed: {listing['price_as_listed'] or 'not shown'} · minimum order as listed: "
                        f"{listing['minimum_order_as_listed'] or 'not shown'} · supplier: {listing['supplier'] or 'unresolved'}")
                records.append({"kind": "listing", "ref": number, "url": url, "text": text, "published_at": None, "precision": "none",
                                "listing": listing})
                added += 1
                if len(records) >= limit:
                    break
            if len(records) >= limit or len(results) < FULL_PAGE or not added:
                break                                                    # enough, the engines' last page, or a page of nothing new
        notes = [SOURCE_NOTE, INDEX_NOTE]
        if pages > 1:
            notes.append(f"{pages} result pages read")
        if page_error:
            notes.append(page_error)
        if other:
            notes.append(f"{other} search result(s) were not alibaba.com product pages: left out")
        if walls:
            notes.append(f"{walls} search result(s) carried a verification page's text instead of a listing: left out, never a record")
        if failed:
            notes.append("search engines that did not answer: " + "; ".join(failed)[:300])
        return {"state": "ok", "retrieved_at": now_iso(), "records": records, "total": None, "complete": None,
                "order": "the search engines' own order, merged by SearXNG", "backend_notes": notes}
