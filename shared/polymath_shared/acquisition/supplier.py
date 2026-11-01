"""SUPPLIER TOOLS (SUPPLIER-APIS, owner-approved 2026-09-27; PRODUCT-SEARCH-E2E, the owner's decisions of 2026-11-01): READ-ONLY
supplier lookups for EVERY Polymath user: the owner, a friend's connector key (an MCP principal) and a friend signed in on the web
app (the owner: "so im ensuring users of the connector and link works seamlessly as me").

  * `search`     (supplier_search):     CJ's catalogue through CJ's official API (source "cj"). source "alibaba" reads NOTHING on this
                                        host ("alibaba is strictly agent reach"): status AGENT_REACH_REQUIRED and a `fallback`. The
                                        SAME record shape as `research_acquire`'s listings: `service.shape` over the readers.
  * `product`    (supplier_product):    CJ's product details and its variants (SKU, options, weight, price, stock by country).
  * `freight`    (supplier_freight):    CJ's freight quote for one variant to one country (carrier, cost, delivery days).
  * `warehouses` (supplier_warehouses): CJ's warehouse list (the countries a freight quote can start from).
  * `parse`      (supplier_parse):      the output of the USER's own Agent Reach (an Exa search, one Jina Reader page) from alibaba.com
                                        or cjdropshipping.com -> the supplier_search shape (`agent_reach.parse`), so every user's
                                        results are read the same way; a verification page is refused (HUMAN_CHECK).
When CJ cannot answer (no key on this host, CJ_API_DISABLED = CJ's 1600014 that only the owner can lift, an auth refusal, another
refusal, CJ's rate limit after its waits, the network, a spent quota, a reply that cannot be read) or answers with no product,
supplier_search keeps its shape, names the failure (`reason_code`) and adds `fallback`: the user's own Agent Reach on the user's own
machine ("prompt users to install it on their end and use their agent reach setup if api fails"), never an agent's built-in web
search or fetch ("it should never use a users claude native web search due to bot detections"). Polymath itself never calls Exa or
Jina: it only builds the commands and parses what the user sends back. supplier_product's failure carries the same `fallback` (find
and read that product's page); freight and warehouses name their failure (`reason_code`) with `fallback` null: CJ's freight
calculator and warehouse list have no user-side equivalent. Every answer has both keys (null when not needed).
FAIR USE (they spend the owner's CJ account): a principal gets at most ONE CJ call in flight and at most
POLYMATH_SUPPLIER_RATE_PER_MINUTE supplier calls a minute (default 30), refused 429 with Retry-After; no daily cap. The owner (no
principal) is not limited. Counted in this process (the orchestrator is one process; a bounce resets it).
Built on the CJ REST client (`cj_api`, with its circuit breaker), never on CJ's own MCP server: its token also reaches orders,
payments, payment links, disputes and store listings. Nothing here creates, confirms, pays, deletes, lists or disputes, and nothing
falls back to the host browser (it holds the owner's sign-ins: research_acquire stays the owner's). Keys come from the environment
only and never reach a result, an error or a log."""
from __future__ import annotations

import collections
import contextlib
import logging
import math
import os
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any

from polymath_shared import principal_context
from polymath_shared.acquisition import agent_reach, cj_api
from polymath_shared.acquisition.listing_apis import ApiFailed
from polymath_shared.acquisition.service import (
    AcquisitionRefused,
    Target,
    _query,
    now_iso,
    shape,
)

log = logging.getLogger("polymath.acquisition")
CONTRACT = "supplier-tools-v1"
#: source -> (site, the acquisition reader that serves it)
SOURCES = {"cj": (cj_api.SITE, "cj_listings"), "alibaba": (agent_reach.ALIBABA, "alibaba_listings")}
TOOLS = ("supplier_search", "supplier_product", "supplier_freight", "supplier_warehouses", "supplier_parse")
SEARCH_LIMIT_DEFAULT, SEARCH_LIMIT_MAX, QUANTITY_MAX = 10, 50, 10000
RATE_ENV, RATE_DEFAULT = "POLYMATH_SUPPLIER_RATE_PER_MINUTE", 30
NO_CJ_KEY = "CJ_API_KEY is not set on this host: the CJ supplier tools are off (the owner sets it in .env; see .env.example)"
UNTRUSTED = agent_reach.UNTRUSTED
CJ_REACTIVATE = ("only the Polymath owner can lift it: sign in at cjdropshipping.com, open My CJ > Authorization > API, turn API access "
                 "back on or create a new API key (or ask CJ support), then set CJ_API_KEY on the Polymath host")
#: ApiFailed.reason -> the typed failure (`reason_code`)
REASON_CODES = {"disabled": "CJ_API_DISABLED", "auth": "CJ_AUTH", "refused": "CJ_REFUSED", "rate_limit": "CJ_RATE_LIMITED",
                "network": "CJ_NETWORK", "unreachable": "CJ_NETWORK", "quota": "CJ_QUOTA", "server": "CJ_SERVER_ERROR",
                "bad_reply": "CJ_BAD_REPLY", "bad_request": "CJ_BAD_REQUEST", "error": "CJ_ERROR"}
WHY = {
    "CJ_NO_KEY": "this Polymath host has no CJ API key (CJ_API_KEY), so it cannot search CJ's catalogue",
    "CJ_API_DISABLED": f"CJ has disabled API access for the Polymath owner's CJ account (CJ code 1600014); {CJ_REACTIVATE}",
    "CJ_AUTH": "CJ refused the owner's API key or token; the owner checks the key at My CJ > Authorization > API on cjdropshipping.com",
    "CJ_REFUSED": "CJ refused the request",
    "CJ_RATE_LIMITED": "CJ's rate limit (one request a second) still held after waiting 2 s and 4 s",
    "CJ_NETWORK": "CJ's API could not be reached from the Polymath host",
    "CJ_QUOTA": "CJ's quota for the owner's account is used up",
    "CJ_SERVER_ERROR": "CJ's API failed on its side",
    "CJ_BAD_REPLY": "CJ's API answered with something Polymath cannot read",
    "CJ_BAD_REQUEST": "CJ's API refused the request's parameters",
    "CJ_ERROR": "the CJ API reader failed on this host",
    "CJ_EMPTY": "CJ's API found no product for this query",
}
HANDOFF = ("this host could not answer: `fallback` is the user-side handoff. Run fallback.commands on your own machine with your own "
           "Agent Reach (install it if it is missing) and send each command's output to supplier_parse; never your agent's built-in web "
           "search or web fetch")
_COUNTRY = re.compile(r"[A-Za-z]{2}")


def authorize(principal_id: str | None) -> None:
    """Every Polymath user may use the supplier tools (PRODUCT-SEARCH-E2E): the owner (no principal context) and any principal the
    MCP gate or the web boundary let through. A malformed principal id never reaches here (principal_context refuses it); one that
    is not a principal id at all is refused again (defence in depth). research_acquire stays owner-only (`service.authorize`)."""
    if principal_id is not None and not principal_context.PRINCIPAL_ID_RE.match(str(principal_id)):
        raise AcquisitionRefused(403, "BAD_PRINCIPAL", "the supplier tools answer the owner or a registered principal")


# ---------------------------------------------------------------------------------------------------------------- fair use --
class FairUseRefused(AcquisitionRefused):
    """A fair-use refusal (429): `retry_after_s` is the Retry-After the route sends."""

    def __init__(self, code: str, message: str, retry_after_s: int):
        super().__init__(429, code, message)
        self.retry_after_s = max(1, int(retry_after_s))


def rate_per_minute(env: Mapping[str, str] | None = None) -> int:
    """POLYMATH_SUPPLIER_RATE_PER_MINUTE (a whole number >= 1), else 30."""
    raw = str((_env(env)).get(RATE_ENV) or "").strip()
    return int(raw) if raw.isdigit() and int(raw) >= 1 else RATE_DEFAULT


class FairUse:
    """Per principal, in this process: supplier calls in the last 60 s (a sliding window) and the CJ call in flight. The owner
    (principal None) passes untouched. `clock` is injected by tests."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._calls: dict[str, collections.deque[float]] = {}
        self._busy: set[str] = set()
        self._lock = threading.Lock()

    def admit(self, principal_id: str | None, env: Mapping[str, str] | None = None) -> None:
        """Count one supplier call, or refuse it (SUPPLIER_RATE_LIMITED) when the principal already made `rate_per_minute` of them."""
        if principal_id is None:
            return
        rate, now = rate_per_minute(env), self._clock()
        with self._lock:
            calls = self._calls.setdefault(principal_id, collections.deque())
            while calls and now - calls[0] >= 60.0:
                calls.popleft()
            if len(calls) >= rate:
                wait = math.ceil(60.0 - (now - calls[0]))
                raise FairUseRefused("SUPPLIER_RATE_LIMITED", f"at most {rate} supplier calls a minute per key (fair use of the owner's CJ "
                                                              f"account; no daily cap): call again in {max(1, wait)} s", wait)
            calls.append(now)

    @contextlib.contextmanager
    def cj_call(self, principal_id: str | None) -> Iterator[None]:
        """Hold the principal's one CJ call in flight; a second one meanwhile is refused (SUPPLIER_BUSY), never queued."""
        if principal_id is None:
            yield
            return
        with self._lock:
            if principal_id in self._busy:
                raise FairUseRefused("SUPPLIER_BUSY", "one CJ call at a time per key (fair use of the owner's CJ account): wait for your "
                                                      "previous supplier call to finish, then call again", 1)
            self._busy.add(principal_id)
        try:
            yield
        finally:
            with self._lock:
                self._busy.discard(principal_id)


FAIR_USE = FairUse()


# ----------------------------------------------------------------------------------------------------------------- helpers --
def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _id(value: Any, what: str) -> str:
    got = cj_api.valid_id(value)
    if got is None:
        raise AcquisitionRefused(422, "BAD_ID", f"{what} is a CJ id: 6 to 64 letters, digits and hyphens (from supplier_search / supplier_product)")
    return got


def _country(value: Any, what: str) -> str:
    text = str(value or "").strip()
    if not _COUNTRY.fullmatch(text):
        raise AcquisitionRefused(422, "BAD_COUNTRY", f"{what} is a two-letter country code (ISO 3166-1 alpha-2), e.g. US")
    return text.upper()


def _head(tool: str, **extra: Any) -> dict[str, Any]:
    return {"contract": CONTRACT, "tool": tool, "source": "cj", **extra}


def _failed(exc: ApiFailed) -> tuple[str, str]:
    """(the typed reason code, the limitation that says why) for a CJ call that could not answer."""
    return REASON_CODES.get(exc.reason, "CJ_ERROR"), f"the {cj_api.LABEL} could not answer ({exc.reason}: {exc.detail})"


def _unavailable(tool: str, code: str, why: str, fallback: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    limits = [why] + ([WHY[code]] if code in WHY and WHY[code] not in why else [])
    if fallback is not None:
        limits.append(HANDOFF)
    else:
        limits.append("no user-side equivalent exists for this CJ tool: it needs CJ's API; call again once CJ answers")
    return {**_head(tool, **extra), "retrieved_at": now_iso(), "status": "UNAVAILABLE", "reason_code": code, "fallback": fallback,
            "limitations": limits}


def _product_fallback(pid: str, code: str) -> dict[str, Any]:
    """supplier_product's handoff: the user's own Agent Reach finds this product's page on cjdropshipping.com and reads it."""
    return agent_reach.fallback(cj_api.SITE, pid, code, WHY[code] + ". Until it answers, your own Agent Reach can find this product's page "
                                f"on cjdropshipping.com (its id {pid} is in the page's URL) and read it")


def _client(env: Mapping[str, str] | None, cj: cj_api.CJClient | None) -> cj_api.CJClient | None:
    return cj or cj_api.client_from_env(_env(env))


# ----------------------------------------------------------------------------------------------------------------- search --
def search(*, principal_id: str | None, query: str, source: str = "cj", limit: int | None = SEARCH_LIMIT_DEFAULT,
           env: Mapping[str, str] | None = None, cj: cj_api.CJClient | None = None, fair_use: FairUse | None = None) -> dict[str, Any]:
    """supplier_search -> {contract, tool, source, site, query, retrieved_at, status, sources, items, completeness, limitations,
    reason_code, fallback}. status: OK / PARTIAL / EMPTY / UNAVAILABLE (CJ) or AGENT_REACH_REQUIRED (alibaba); `fallback` is set
    whenever this host could not give CJ listings (every CJ failure and an empty answer) and always for alibaba, else None."""
    authorize(principal_id)
    if source not in SOURCES:
        raise AcquisitionRefused(422, "UNKNOWN_SOURCE", f"source is one of {', '.join(sorted(SOURCES))}")
    q = _query(query)
    try:
        n = max(1, min(int(limit if limit is not None else SEARCH_LIMIT_DEFAULT), SEARCH_LIMIT_MAX))
    except (TypeError, ValueError):
        raise AcquisitionRefused(422, "BAD_LIMIT", f"limit is a number from 1 to {SEARCH_LIMIT_MAX}") from None
    gate = fair_use or FAIR_USE
    gate.admit(principal_id, env)
    site, reader_name = SOURCES[source]
    t = Target(operation="listings", reader=reader_name, site=site, query=q, source_class="supplier_listing")
    if source == "alibaba":
        why = ("alibaba.com is read only by your own Agent Reach on your machine, never by this host (the owner's decision of "
               "2026-11-01: no search engine and no host browser here, and never an agent's built-in web search or fetch, which meet "
               "bot checks)")
        return {"contract": CONTRACT, "tool": "supplier_search", "source": source, "site": site, "query": q, "retrieved_at": now_iso(),
                "status": "AGENT_REACH_REQUIRED", "sources": [], "items": [], "completeness": {"read": 0, "available": None, "complete": None},
                "limitations": [f"{site}: nothing was read on this host; {why}", HANDOFF],
                "reason_code": "ALIBABA_AGENT_REACH_ONLY", "fallback": agent_reach.fallback(site, q, "ALIBABA_AGENT_REACH_ONLY", why)}
    client = _client(env, cj)
    code: str | None = None
    if client is None:
        raw: dict[str, Any] = {"state": "unavailable", "note": NO_CJ_KEY}
        code = "CJ_NO_KEY"
    else:
        with gate.cj_call(principal_id):
            try:
                raw = cj_api.CJListings(client).read(t, n)
            except ApiFailed as exc:
                code, note = _failed(exc)
                raw = {"state": "unavailable", "note": note}
            except Exception as exc:          # a reader's own bug is a failure like any other: said, typed, handed off
                log.exception("supplier search: the CJ reader raised")
                code, raw = "CJ_ERROR", {"state": "unavailable", "note": f"the {cj_api.LABEL} reader failed ({type(exc).__name__})"}
    out = shape(t, raw, action={}, search_intent_id=None, retrieved_at=str(raw.get("retrieved_at") or now_iso()), used=0, cap=0, limit=n)
    if code is None and out["status"] == "EMPTY":
        code = "CJ_EMPTY"
    fallback = None
    if code is not None:
        why = WHY[code] + (". Your own Agent Reach may still find CJ product pages through Exa" if code == "CJ_EMPTY" else
                           ". Until it answers, search cjdropshipping.com with your own Agent Reach on your machine")
        fallback = agent_reach.fallback(site, q, code, why)
    limitations = out["limitations"] + ([WHY[code], HANDOFF] if code is not None else [])
    return {"contract": CONTRACT, "tool": "supplier_search", "source": source, "site": site, "query": q, "retrieved_at": out["retrieved_at"],
            "status": out["status"], "sources": out["sources"], "items": out["items"], "completeness": out["completeness"],
            "limitations": limitations, "reason_code": code, "fallback": fallback}


# ------------------------------------------------------------------------------------------------------- product / freight --
def product(*, principal_id: str | None, product_id: str, env: Mapping[str, str] | None = None,
            cj: cj_api.CJClient | None = None, fair_use: FairUse | None = None) -> dict[str, Any]:
    """supplier_product -> {contract, tool, source, product_id, retrieved_at, status, reason_code, product, variants, limitations}."""
    authorize(principal_id)
    pid = _id(product_id, "product_id")
    gate = fair_use or FAIR_USE
    gate.admit(principal_id, env)
    client = _client(env, cj)
    if client is None:
        return _unavailable("supplier_product", "CJ_NO_KEY", NO_CJ_KEY, _product_fallback(pid, "CJ_NO_KEY"), product_id=pid)
    with gate.cj_call(principal_id):
        try:
            data = client.product(pid)
        except ApiFailed as exc:
            code, why = _failed(exc)
            return _unavailable("supplier_product", code, why, _product_fallback(pid, code), product_id=pid)
    if data is None:
        return {**_head("supplier_product", product_id=pid), "retrieved_at": now_iso(), "status": "NOT_FOUND", "reason_code": None,
                "fallback": None, "product": None, "variants": [], "limitations": [f"CJ's API returned no product for {pid}"]}
    view = cj_api.product_view(data)
    return {**_head("supplier_product", product_id=pid), "retrieved_at": now_iso(), "status": "OK", "reason_code": None, "fallback": None, **view,
            "limitations": [("from the CJ Dropshipping API: CJ's own catalogue data, no web page was opened; prices in US dollars, weights "
                             "in grams, stock as CJ reports it now"), UNTRUSTED]}


def freight(*, principal_id: str | None, variant_id: str, country: str, quantity: int = 1, from_country: str = "CN",
            env: Mapping[str, str] | None = None, cj: cj_api.CJClient | None = None, fair_use: FairUse | None = None) -> dict[str, Any]:
    """supplier_freight -> {contract, tool, source, request, retrieved_at, status, reason_code, options, limitations}."""
    authorize(principal_id)
    vid = _id(variant_id, "variant_id")
    to, start = _country(country, "country"), _country(from_country, "from_country")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= QUANTITY_MAX:
        raise AcquisitionRefused(422, "BAD_QUANTITY", f"quantity is a whole number from 1 to {QUANTITY_MAX}")
    request = {"variant_id": vid, "from_country": start, "to_country": to, "quantity": quantity}
    gate = fair_use or FAIR_USE
    gate.admit(principal_id, env)
    client = _client(env, cj)
    if client is None:
        return _unavailable("supplier_freight", "CJ_NO_KEY", NO_CJ_KEY, request=request)
    with gate.cj_call(principal_id):
        try:
            options = [cj_api.freight_view(o) for o in client.freight(vid, to, quantity, start)]
        except ApiFailed as exc:
            return _unavailable("supplier_freight", *_failed(exc), request=request)
    return {**_head("supplier_freight", request=request), "retrieved_at": now_iso(), "status": "OK" if options else "EMPTY",
            "reason_code": None, "fallback": None, "options": options,
            "limitations": [("CJ's own freight estimate from the CJ Dropshipping API (a calculation: nothing was ordered); costs in US dollars, "
                             "delivery time in days as CJ states it")]
            + ([] if options else [f"CJ offers no shipping option for this variant from {start} to {to}"])}


def warehouses(*, principal_id: str | None, env: Mapping[str, str] | None = None, cj: cj_api.CJClient | None = None,
               fair_use: FairUse | None = None) -> dict[str, Any]:
    """supplier_warehouses -> {contract, tool, source, retrieved_at, status, reason_code, warehouses, limitations}."""
    authorize(principal_id)
    gate = fair_use or FAIR_USE
    gate.admit(principal_id, env)
    client = _client(env, cj)
    if client is None:
        return _unavailable("supplier_warehouses", "CJ_NO_KEY", NO_CJ_KEY)
    with gate.cj_call(principal_id):
        try:
            rows = [cj_api.warehouse_view(w) for w in client.warehouses()]
        except ApiFailed as exc:
            return _unavailable("supplier_warehouses", *_failed(exc))
    return {**_head("supplier_warehouses"), "retrieved_at": now_iso(), "status": "OK" if rows else "EMPTY", "reason_code": None,
            "fallback": None, "warehouses": rows, "limitations": ["CJ's warehouse list from the CJ Dropshipping API"]}


# ------------------------------------------------------------------------------------------------------------------ parse --
def parse(*, principal_id: str | None, site: str, raw_text: str, env: Mapping[str, str] | None = None,
          fair_use: FairUse | None = None) -> dict[str, Any]:
    """supplier_parse: ONE command's output of the user's own Agent Reach (an Exa search or one Jina Reader page) from `site`
    (alibaba.com / cjdropshipping.com, or the source name alibaba / cj) -> the supplier_search shape, plus `tool_class`
    (agent_reach.exa / agent_reach.jina, for the receipt's tool trace), `refused` (every page that became no item, and why:
    HUMAN_CHECK, OFF_SITE, NOT_A_PRODUCT_PAGE, DUPLICATE, OVER_LIMIT) and `next` (after an Exa search: the exact Jina command for
    each product found). status: OK / EMPTY, or HUMAN_CHECK when every page was a verification page. Polymath opens no page."""
    authorize(principal_id)
    host = agent_reach.site_of(site)
    if host is None:
        raise AcquisitionRefused(422, "UNKNOWN_SITE", f"site is one of {', '.join(agent_reach.SITES)} (or the source name cj / alibaba)")
    try:
        text = agent_reach.clean_text(raw_text)
    except agent_reach.BadOutput as exc:
        raise AcquisitionRefused(exc.status, exc.code, exc.message) from None
    (fair_use or FAIR_USE).admit(principal_id, env)
    try:
        got = agent_reach.parse(host, text)
    except agent_reach.BadOutput as exc:
        raise AcquisitionRefused(exc.status, exc.code, exc.message) from None
    source = agent_reach.SOURCE_OF[host]
    retrieved = now_iso()
    t = Target(operation="listings", reader=f"agent_reach_{source}", site=host, query=None, source_class="supplier_listing")
    raw = {"state": "ok", "retrieved_at": retrieved, "records": got["records"], "total": None, "complete": None,
           "order": "the order of the submitted output", "backend_notes": got["notes"]}
    out = shape(t, raw, action={}, search_intent_id=None, retrieved_at=retrieved, used=0, cap=0, limit=max(1, len(got["records"])))
    walls = [r for r in got["refused"] if r["code"] == "HUMAN_CHECK"]
    status = "HUMAN_CHECK" if walls and not out["items"] else out["status"]
    exa = got["tool_class"] == agent_reach.TOOL_EXA
    nxt = None
    if exa and got["records"]:
        nxt = {"commands": [agent_reach.jina_command(r["url"]) for r in got["records"]],
               "what": "each reads one product page in full through Jina Reader on your machine (price tiers, minimum order, supplier)",
               "then": f"send each page's output as its own supplier_parse call with site \"{host}\"", "walls": agent_reach.WALLS[host]}
    limitations = out["limitations"] + [
        "retrieved_at is when Polymath received this output; the page was read on the user's own machine just before"]
    if walls:
        limitations.append(agent_reach.WALLS[host])
    return {"contract": CONTRACT, "tool": "supplier_parse", "source": source, "site": host, "query": None, "retrieved_at": out["retrieved_at"],
            "status": status, "sources": out["sources"], "items": out["items"], "completeness": out["completeness"],
            "limitations": limitations, "tool_class": got["tool_class"],
            "tool_trace": {"tool_class": got["tool_class"], "query_count": 1 if exa else got["documents"]},
            "refused": got["refused"], "next": nxt, "reason_code": "HUMAN_CHECK" if status == "HUMAN_CHECK" else None, "fallback": None}
