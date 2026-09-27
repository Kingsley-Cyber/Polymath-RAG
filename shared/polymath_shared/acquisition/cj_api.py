"""CJ DROPSHIPPING'S OFFICIAL API (API 2.0), READ-ONLY (SUPPLIER-APIS, the owner's decision of 2026-09-27).

What CJ's own documentation (developers.cjdropshipping.com, read 2026-09-27) says, and what this client does with it:
  * sign-in: `POST /authentication/getAccessToken` with `{"apiKey": ...}` (the key from My CJ > Authorization > API; API 2.0 needs
    no e-mail) returns `accessToken` + `accessTokenExpiryDate` (about 180 days). The token is CACHED per key in this process until
    ten minutes before that date; CJ's refusal of a cached token (1600001 / 1600002 / 1600003 / 1601000, or HTTP 401 / 403) drops
    it and signs in once more. Later calls send it as the `CJ-Access-Token` header.
  * rate: 1 request a second for a free account (the sign-in too): calls are spaced 1.1 s apart per key, and CJ's "too much request"
    (1600200, or HTTP 429) is waited out twice (2 s, then 4 s) before the call gives up. A spent quota (1600201, 16900500) is not
    retried.
  * success = HTTP 200 and `code` 200 (or no code).
  * the routes: the product search `GET /product/listV2` (keyWord, page, size <= 100, features=enable_category: the category
    names), the product details `GET /product/query` (pid: the product and its variants with stock by country), the freight quote
    `POST /logistic/freightCalculate` (a calculation: it creates nothing) and the warehouse list `GET /product/globalWarehouseList`.
    `ENDPOINTS` is the complete set; `test_supplier_tools` pins it, so no order, cart, payment, dispute, store-listing or sourcing
    route can be added. CJ's own MCP server is not used: its token reaches orders, payments and disputes too.
  * no product page URL comes back: a listing's URL is built from the site's own pattern
    (`https://cjdropshipping.com/product/<slug>-p-<pid>.html`, as CJ's product pages are indexed).
Neither the key nor the token ever reaches a log, a result or an error text (`_scrub`)."""
from __future__ import annotations

import hashlib
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from polymath_shared.acquisition.listing_apis import ApiFailed
from polymath_shared.acquisition.service import Target, now_iso

BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"
SITE, LABEL = "cjdropshipping.com", "CJ Dropshipping API"
TOKEN, SEARCH, PRODUCT, FREIGHT, WAREHOUSES = ("/authentication/getAccessToken", "/product/listV2", "/product/query",
                                              "/logistic/freightCalculate", "/product/globalWarehouseList")
#: every CJ route this client may call: the sign-in and four READS (test_supplier_tools pins the set)
ENDPOINTS = (TOKEN, SEARCH, PRODUCT, FREIGHT, WAREHOUSES)
MIN_INTERVAL_S = 1.1
RATE_LIMIT_WAITS_S = (2.0, 4.0)
TIMEOUT_S = 20.0
TOKEN_MARGIN_S = 600
TOKEN_FALLBACK_TTL_S = 3600            # an expiry date CJ did not give or that does not parse: sign in again within the hour
SEARCH_SIZE_MAX = 100
AUTH_CODES = frozenset({1600001, 1600002, 1600003, 1601000})
RATE_CODES = frozenset({1600200})
QUOTA_CODES = frozenset({1600201, 16900500})
PARAM_CODES = frozenset({1600300, 16900403, 16900205})
#: the note every CJ answer carries into `limitations`: where the data came from
SOURCE_NOTE = ("listings from the CJ Dropshipping API: CJ's own catalogue data, no web page was opened; the price is CJ's sell price in "
               "US dollars, and a minimum order is shown only where the API states one")
_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{5,63}")


@dataclass
class _Account:
    """Per key, in this process: the cached token and the time of the last call (CJ's one-request-a-second limit)."""
    token: str | None = None
    expires_at: float = 0.0
    last_call: float = float("-inf")
    pace: threading.Lock = field(default_factory=threading.Lock)


_ACCOUNTS: dict[str, _Account] = {}
_ACCOUNTS_LOCK = threading.Lock()


def _account(key: str) -> _Account:
    kid = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    with _ACCOUNTS_LOCK:
        return _ACCOUNTS.setdefault(kid, _Account())


def _epoch(value: Any) -> float | None:
    """CJ's expiry date ("2021-08-18T09:16:33+08:00") -> epoch seconds; None when it does not parse."""
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def _clip(value: Any, n: int = 160) -> str:
    return " ".join(str(value or "").split())[:n]


class CJClient:
    """One CJ account's read-only client. `transport`, `sleep`, `clock` and `wall` are injected by tests (no network there)."""

    def __init__(self, api_key: str, *, base_url: str = BASE_URL, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], float] = time.time):
        if not str(api_key or "").strip():
            raise ValueError("a CJ API key is required")
        self._key = str(api_key).strip()
        self._base = base_url.rstrip("/")
        self._transport, self._sleep, self._clock, self._wall = transport, sleep, clock, wall
        self._acct = _account(self._key)

    # ------------------------------------------------------------------------------------------------------------ plumbing --
    def _scrub(self, text: str) -> str:
        for secret in (self._key, self._acct.token):
            if secret:
                text = text.replace(secret, "[redacted]")
        return text

    def _send(self, method: str, path: str, *, params: Mapping[str, Any] | None, body: Any, token: str | None) -> httpx.Response:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["CJ-Access-Token"] = token
        with self._acct.pace:                                     # one call at a time per account, spaced by MIN_INTERVAL_S
            wait = MIN_INTERVAL_S - (self._clock() - self._acct.last_call)
            if wait > 0:
                self._sleep(wait)
            try:
                with httpx.Client(transport=self._transport, timeout=TIMEOUT_S) as client:
                    return client.request(method, self._base + path, params=params, json=body, headers=headers)
            finally:
                self._acct.last_call = self._clock()

    def _token(self) -> str:
        acct = self._acct
        if acct.token and acct.expires_at - TOKEN_MARGIN_S > self._wall():
            return acct.token
        acct.token = None
        data = self._call("POST", TOKEN, body={"apiKey": self._key}, signed=False)
        token = data.get("accessToken") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise ApiFailed("bad_reply", "CJ's sign-in answer held no access token")
        acct.token = token.strip()
        acct.expires_at = _epoch(data.get("accessTokenExpiryDate")) or (self._wall() + TOKEN_FALLBACK_TTL_S)
        return acct.token

    def _call(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, body: Any = None, signed: bool = True) -> Any:
        """One CJ call -> its `data`, or ApiFailed. Waits out CJ's rate limit; renews a refused token once."""
        waits, renewed = list(RATE_LIMIT_WAITS_S), False
        while True:
            token = self._token() if signed else None
            try:
                r = self._send(method, path, params=params, body=body, token=token)
            except httpx.TimeoutException:
                raise ApiFailed("network", "CJ did not answer in time") from None
            except httpx.TransportError as exc:
                raise ApiFailed("network", f"CJ could not be reached ({type(exc).__name__})") from None
            try:
                payload = r.json()
            except ValueError:
                payload = None
            code = payload.get("code") if isinstance(payload, dict) else None
            said = self._scrub(_clip(payload.get("message") if isinstance(payload, dict) else ""))
            if r.status_code == 429 or code in RATE_CODES:
                if waits:
                    self._sleep(waits.pop(0))
                    continue
                raise ApiFailed("rate_limit", "CJ's rate limit still held after waiting 2 s and 4 s")
            if r.status_code in (401, 403) or code in AUTH_CODES:
                if signed and not renewed:                        # a cached token CJ no longer takes: sign in again, once
                    self._acct.token, renewed = None, True
                    continue
                raise ApiFailed("auth", f"CJ refused the {'token' if signed else 'API key'} ({code or r.status_code}: {said or 'no message'})")
            if code in QUOTA_CODES:
                raise ApiFailed("quota", f"CJ's quota is used up ({code}: {said or 'no message'})")
            if r.status_code >= 500:
                raise ApiFailed("server", f"CJ answered HTTP {r.status_code}")
            if not isinstance(payload, dict):
                raise ApiFailed("bad_reply", f"CJ's answer is not JSON (HTTP {r.status_code})")
            if r.status_code != 200 or (code is not None and code != 200):
                raise ApiFailed("bad_request" if code in PARAM_CODES else "refused",
                                f"CJ answered {code if code is not None else r.status_code}: {said or 'no message'}")
            return payload.get("data")

    # --------------------------------------------------------------------------------------------------------------- reads --
    def search(self, query: str, size: int) -> tuple[list[dict[str, Any]], int | None]:
        """CJ's product search (best match first) -> (products, CJ's total count for the query)."""
        data = self._call("GET", SEARCH, params={"keyWord": query, "page": 1, "size": max(1, min(int(size), SEARCH_SIZE_MAX)),
                                                 "features": "enable_category"})
        if not isinstance(data, dict):
            raise ApiFailed("bad_reply", "CJ's product search held no data")
        products: list[dict[str, Any]] = []
        for block in data.get("content") or []:
            if isinstance(block, dict) and isinstance(block.get("productList"), list):
                products += [p for p in block["productList"] if isinstance(p, dict)]
            elif isinstance(block, dict) and (block.get("id") or block.get("pid")):      # a flat list, as the older route answered
                products.append(block)
        total = data.get("totalRecords")
        return products, total if isinstance(total, int) and not isinstance(total, bool) else None

    def product(self, pid: str) -> dict[str, Any] | None:
        data = self._call("GET", PRODUCT, params={"pid": pid})
        return data if isinstance(data, dict) and data else None

    def freight(self, vid: str, to_country: str, quantity: int, from_country: str) -> list[dict[str, Any]]:
        data = self._call("POST", FREIGHT, body={"startCountryCode": from_country, "endCountryCode": to_country,
                                                 "products": [{"quantity": int(quantity), "vid": vid}]})
        if data is None:
            return []
        if not isinstance(data, list):
            raise ApiFailed("bad_reply", "CJ's freight answer is not a list of options")
        return [o for o in data if isinstance(o, dict)]

    def warehouses(self) -> list[dict[str, Any]]:
        data = self._call("GET", WAREHOUSES)
        if data is None:
            return []
        if not isinstance(data, list):
            raise ApiFailed("bad_reply", "CJ's warehouse answer is not a list")
        return [w for w in data if isinstance(w, dict)]


def client_from_env(env: Mapping[str, str], **kw: Any) -> CJClient | None:
    """The owner's CJ client when `CJ_API_KEY` is set, else None (the key is read from the environment only)."""
    key = str(env.get("CJ_API_KEY") or "").strip()
    return CJClient(key, **kw) if key else None


# ------------------------------------------------------------------------------------------------------------------ mapping --
def valid_id(value: Any) -> str | None:
    """A CJ product / variant id (a UUID or a long number) as given, or None."""
    text = str(value or "").strip()
    return text if _ID.fullmatch(text) else None


def product_url(pid: str, name: str) -> str:
    """The product's page on CJ's site, built from the site's own pattern (the API returns no URL)."""
    slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", str(name).lower())).strip("-")[:120].strip("-") or "product"
    return f"https://{SITE}/product/{slug}-p-{pid}.html"


def usd(value: Any) -> str | None:
    """CJ's US-dollar price as listed (a number, "11.85", a range "0.97-4.08" or "2.83 -- 3.74") -> "US$11.85" / "US$0.97-4.08"."""
    if value is None or isinstance(value, bool):
        return None
    nums = re.findall(r"\d+(?:\.\d+)?", str(value))
    if not nums or len(nums) > 2 or float(nums[0]) <= 0:
        return None
    lo, hi = nums[0], nums[-1]
    return f"US${lo}" if lo == hi else f"US${lo}-{hi}"


def _whole(value: Any) -> str | None:
    """A count as text (a whole number >= 0, or its digits), else None: 0 stays "0", never "unknown"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return str(value)
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return str(int(value))
    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{1,12}", text) else None


def _first(p: Mapping[str, Any], *keys: str) -> str | None:
    return next((_clip(p.get(k), 300) for k in keys if _clip(p.get(k), 300)), None)


def listing_record(p: Mapping[str, Any]) -> dict[str, Any] | None:
    """One product of CJ's search -> one listing record in the browser backend's shape (`opencli.OpenCLIBackend._listing`): the
    title, the price as listed, the minimum order as listed, the supplier, plus what only the API gives (the product id, SKU, image,
    category, the discount price, how many stores list it, the stock in CJ's warehouses). None without a usable id and name."""
    pid = valid_id(p.get("id") or p.get("pid"))
    name = _clip(p.get("nameEn") or p.get("productNameEn"), 300)
    if not pid or not name:
        return None
    price = usd(p.get("sellPrice"))
    discount = usd(p.get("nowPrice") or p.get("discountPrice"))
    moq = _whole(p.get("directMinOrderNum"))
    moq_text = (f"{moq} unit" + ("" if moq == "1" else "s")) if moq and moq != "0" else None
    supplier = _clip(p.get("supplierName"), 200) or None
    listing = {"title": name, "price_as_listed": price, "minimum_order_as_listed": moq_text, "supplier": supplier,
               "discount_price_as_listed": discount if discount and discount != price else None,
               "category": _first(p, "threeCategoryName", "categoryName", "twoCategoryName", "oneCategoryName"),
               "image": _first(p, "bigImage", "productImage"), "product_id": pid, "sku": _first(p, "sku", "productSku", "spu"),
               "listed_by_stores": _whole(p.get("listedNum")), "warehouse_inventory": _whole(p.get("warehouseInventoryNum"))}
    text = (f"{name} · price as listed: {price or 'not shown'} · minimum order as listed: {moq_text or 'not shown'}"
            f" · supplier: {supplier or 'unresolved'}")
    return {"kind": "listing", "ref": pid, "url": product_url(pid, name), "text": text, "published_at": None, "precision": "none",
            "listing": listing}


class CJListings:
    """The `cj_listings` reader over CJ's API: raw reads in the browser backend's shape, for `service.shape`."""

    reader, label = "cj_listings", LABEL

    def __init__(self, client: CJClient):
        self.client = client

    def read(self, target: Target, limit: int) -> dict[str, Any]:
        products, total = self.client.search(target.query or "", limit)
        retrieved = now_iso()
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        unusable = 0
        for p in products:
            rec = listing_record(p)
            if rec is None:
                unusable += 1
                continue
            if rec["ref"] in seen:
                continue
            seen.add(rec["ref"])
            records.append(rec)
            if len(records) >= limit:
                break
        notes = [SOURCE_NOTE]
        if unusable:
            notes.append(f"{unusable} product(s) in CJ's answer had no usable id or name: left out")
        return {"state": "ok", "retrieved_at": retrieved, "records": records, "total": total,
                "complete": (len(records) >= total) if total is not None else None, "order": "CJ's own best-match order",
                "backend_notes": notes}


def product_view(d: Mapping[str, Any]) -> dict[str, Any]:
    """CJ's product details -> {product, variants}: every field as CJ lists it (weights in grams, prices in US dollars)."""
    pid = valid_id(d.get("pid")) or _clip(d.get("pid"), 64)
    name = _clip(d.get("productNameEn"), 300)
    images = [_clip(u, 500) for u in (d.get("productImageSet") or []) if isinstance(u, str) and u.startswith("http")][:10]
    product = {"product_id": pid, "title": name or None, "sku": _clip(d.get("productSku"), 100) or None,
               "url": product_url(pid, name) if pid and name else None, "image": _clip(d.get("bigImage"), 500) or None, "images": images,
               "weight_g": _clip(d.get("productWeight"), 40) or None, "unit": _clip(d.get("productUnit"), 40) or None,
               "category": _clip(d.get("categoryName"), 300) or None, "price_as_listed": usd(d.get("sellPrice")),
               "suggested_retail_as_listed": usd(d.get("suggestSellPrice")), "listed_by_stores": _whole(d.get("listedNum")),
               "supplier": _clip(d.get("supplierName"), 200) or None}
    variants = []
    for v in d.get("variants") or []:
        if not isinstance(v, dict):
            continue
        stock = [{"country": _clip(i.get("countryCode"), 8) or None, "total": _whole(i.get("totalInventory")),
                  "cj_warehouse": _whole(i.get("cjInventory")), "factory": _whole(i.get("factoryInventory"))}
                 for i in v.get("inventories") or [] if isinstance(i, dict)]
        variants.append({"variant_id": valid_id(v.get("vid")) or _clip(v.get("vid"), 64), "sku": _clip(v.get("variantSku"), 100) or None,
                         "name": _clip(v.get("variantNameEn"), 300) or None, "options": _clip(v.get("variantKey"), 200) or None,
                         "weight_g": _clip(v.get("variantWeight"), 40) or None, "price_as_listed": usd(v.get("variantSellPrice")),
                         "suggested_retail_as_listed": usd(v.get("variantSugSellPrice")), "stock": stock})
    return {"product": product, "variants": variants}


def _money(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def freight_view(o: Mapping[str, Any]) -> dict[str, Any]:
    """One of CJ's freight options: the carrier, the cost in US dollars, the delivery time in days as CJ states it."""
    return {"carrier": _clip(o.get("logisticName"), 120) or None, "cost_usd": _money(o.get("logisticPrice")),
            "delivery_days": _clip(o.get("logisticAging"), 40) or None, "taxes_usd": _money(o.get("taxesFee")),
            "clearance_usd": _money(o.get("clearanceOperationFee")), "total_usd": _money(o.get("totalPostageFee"))}


def warehouse_view(w: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": _clip(w.get("id") if w.get("id") is not None else w.get("areaId"), 64) or None, "name": _clip(w.get("areaEn"), 120) or None,
            "country_code": _clip(w.get("countryCode"), 8) or None, "country": _clip(w.get("nameEn"), 120) or None,
            "code": _clip(w.get("valueEn"), 64) or None, "available": not bool(w.get("disabled"))}
