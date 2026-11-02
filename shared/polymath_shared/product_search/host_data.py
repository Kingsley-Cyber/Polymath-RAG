"""PRODUCT DECISION REPORT: HOST DATA (PRODUCT-DECISION-REPORT-V1 §4.3, slice B2; the owner's plan of 2026-11-02): what the
Polymath HOST itself learns about each candidate product, for every user (the owner, a friend's connector key, a friend on the web
app), before any Agent Reach round runs on the user's machine.

`collect(candidates, *, principal_id, ship_to="US", supplier_fns=None, ebay=None) -> {cj, ebay, receipts, ...}`:
  * CJ, through the supplier tools (`supplier.search / product / freight`: CJ's official API, its pacing and circuit breaker) AS THE
    CALLER'S PRINCIPAL, so fair use applies to friends. Per candidate: ONE search for its first search term, then the RELEVANCE
    FILTER: a product is kept only when its title holds every HEAD TERM of that search (`head_terms`: the term's own words up to
    the first "for" / "with" / ..., stop words left out; measured 2026-11-02: "candle warmer" came back as LED candles) as a WHOLE
    word, its plural or singular, or two or three adjacent words joined ("touch screen" = "touchscreen"); a word inside another
    word never counts (R2 #6: "Desk Clamp Phone Holder" is not a "desk lamp"). The near
    misses stay in `relevance.dropped` with the terms they miss; at most MAX_PRODUCTS are kept. The best-matching kept product (the
    first in the search's order: CJ's best match, re-ranked by the query's rarest words) is read in full (its variants with name,
    price and weight) and costed at ONE variant (`choose_variant`, VARIANT_RULE; live 2026-11-02 a fountain was costed at its $2.94
    filter set): parts and accessories named as such are dropped, light parts and samples are dropped when the weights spread, then
    the cheapest of the rest; `variants` holds what the rule kept, `variants_dropped` the rest and why, `variant_rule` the rule as
    applied (also on the product's receipt); none left = `detail_status` NO_COSTED_VARIANT, no price. CJ's freight quote for that
    variant is asked from CN
    and from US to the ship-to country, CJ's "a-b" days parsed into ints with the unit its text names (`days_unit`: "business",
    "calendar" or None, contract C2). `us_stock_confirmed` is true only when CJ STATES stock in
    a US warehouse for that variant (measured: stock by country came back [] while a US->US quote answered: a quote is no proof).
    At most CJ_CALLS_PER_CANDIDATE (4) CJ calls a candidate: the search, the details, two freight quotes; the other kept products
    keep what the search gave (`detail_status` NOT_FETCHED).
  * eBay, through `ebay_api` (the Browse API on the owner's keyset): ONE search per candidate for the same term, the same relevance
    filter; EBAY_NOT_CONFIGURED (status NOT_CONFIGURED) when the keyset is unset, which is never an error. Every eBay search first
    spends the caller's fair use, the SAME per-key budget as its CJ calls (R1 #2; the owner passes untouched): a refusal is
    FAIR_USE_LIMITED for that candidate, nothing reaches eBay and the keyset's shared breaker is untouched. A friend also gets at
    most EBAY_DAILY_SEARCHES (300) eBay searches a UTC day (R1 verify round; the owner is exempt): past it EBAY_DAILY_LIMIT, the
    same way (no eBay call, the breaker untouched).
  * every call leaves a receipt (what was asked, the status, the reason code, the rows, when). A failure is a typed status with its
    `reason_code`; the supplier tools' own `fallback` (the user's own Agent Reach) is carried through unchanged; one candidate's
    failure never stops the others. A CJ fair-use refusal (SUPPLIER_RATE_LIMITED / SUPPLIER_BUSY: nothing reached CJ) is waited
    out once, for its Retry-After (at most FAIR_USE_WAIT_MAX_S, FAIR_USE_WAIT_TOTAL_S a collect), then answered as a typed failure;
    an eBay one is answered at once. Either is reported as FAIR_USE_LIMITED (the gate's own code in `fair_use_code`).
Statuses (cj and ebay): OK, PARTIAL (a later call failed: what was learned is kept), NO_MATCH (answers, none relevant), EMPTY,
UNAVAILABLE, NOT_SEARCHED (no usable term), NOT_CONFIGURED (eBay only). Every text field is the supplier's or the seller's own
untrusted text. Deterministic code only: no model, no web page, no key in any result."""
from __future__ import annotations

import functools
import logging
import math
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from polymath_shared.acquisition import agent_reach, cj_api, ebay_api, supplier
from polymath_shared.acquisition.agent_reach import head_terms, missing_terms
from polymath_shared.acquisition.listing_apis import ApiFailed
from polymath_shared.acquisition.service import AcquisitionRefused, now_iso

log = logging.getLogger("polymath.product_search")
CONTRACT = "product-report-host-v1"
#: where CJ's freight quote starts: China, and CJ's US warehouses
ORIGINS = ("CN", "US")
MAX_CANDIDATES = 8                     # the report's cap (PRODUCT-DECISION-REPORT-V1 §3: max_products default 5, cap 8)
MAX_PRODUCTS = 3                       # relevant CJ products kept per candidate
CJ_CALLS_PER_CANDIDATE = 4             # the search, the details, the freight from CN, the freight from US
CJ_SEARCH_LIMIT = 10                   # CJ listings read per search (one CJ call whatever the number)
EBAY_SEARCH_LIMIT, MAX_LISTINGS = 30, 20
MAX_VARIANTS, MAX_FREIGHT_OPTIONS, MAX_DROPPED, MAX_LIMITATIONS = 30, 40, 12, 8
TERM_MAX, TITLE_MAX = 100, 300
MAX_DAYS = 365
FAIR_USE_CODES = ("SUPPLIER_RATE_LIMITED", "SUPPLIER_BUSY")
#: the one reason code a fair-use refusal carries in host data, CJ or eBay (contract C6); the gate's own code is `fair_use_code`
FAIR_USE_LIMITED = "FAIR_USE_LIMITED"
FAIR_USE_WAIT_MAX_S, FAIR_USE_WAIT_TOTAL_S = 60.0, 120.0
#: R1 verify round: a friend's eBay searches per UTC day (policy). The keyset allows 5,000 eBay calls a day for EVERYONE; at the
#: 30-a-minute fair use one friend could spend them in 3-6 hours, after which every eBay 429 opens the keyset-wide breaker for
#: everyone for 300 s. The owner (principal None) is exempt. In process memory, like the fair use.
EBAY_DAILY_SEARCHES = 300
EBAY_DAILY_LIMIT = "EBAY_DAILY_LIMIT"
TOOLS = {"search": "supplier_search", "product": "supplier_product", "freight": "supplier_freight"}
EBAY_CALL = "ebay_browse_search"
RULE = ("a title must hold every head term of the search as a whole word (its plural or singular counts, and so does a joined "
        "spelling of two or three adjacent words: \"touch screen\" = \"touchscreen\"); a word inside another word never counts")
VARIANT_FIELDS = ("variant_id", "name", "price_usd", "weight_g", "options", "us_stock_units")
#: THE COSTED VARIANT (live 2026-11-02, rpt_164ed807ad94e63ef002458e: a pet water fountain was costed at its "Filter cotton set"
#: variant, $2.94 / 120 g, and the report printed a TikTok US margin of 70.5 %). A variant whose OWN name holds one of these words
#: (or its plural) names a part or an accessory, not the product, unless the search term holds that word too:
ACCESSORY_WORDS = ("filter", "replacement", "cartridge", "refill", "spare", "pump", "sponge", "part", "accessory")
#: and when the heaviest variant left weighs at least VARIANT_SPREAD x the lightest, the ones under VARIANT_LIGHT_SHARE of the
#: heaviest's weight are parts or samples (they ship light); then the cheapest of the rest (ties: the lower variant id)
VARIANT_SPREAD, VARIANT_LIGHT_SHARE = 2.5, 0.40
VARIANT_RULE = ("the costed variant is the cheapest left after dropping (1) variants whose own name (CJ's variant name after the "
                "product's title, and its variant key) holds a part or accessory word (filter, replacement, cartridge, refill, spare, pump, "
                "sponge, part, accessory, or a plural) the search term does not hold, and (2) when the heaviest variant left weighs at "
                "least 2.5 x the lightest, variants under 40 % of the heaviest's weight (parts and samples ship light); ties: the lower "
                "variant id")
LISTING_FIELDS = ("title", "url", "price_usd", "shipping_usd", "delivery_min", "delivery_max", "location", "condition", "item_id",
                  "us_listing")
NOTES = [
    ("CJ: one search per candidate (its first search term); a product is kept only when its title holds every head term of that "
     "search; at most 3 are kept, and only the best-matching one is read in full and quoted: CJ allows about one call a second, so "
     "the host spends at most 4 CJ calls a candidate (search, details, freight from CN, freight from US)"),
    ("CJ freight: cost_usd is CJ's total postage for one unit of the cheapest variant (postage, taxes and clearance as CJ states "
     "them); days_min / days_max are CJ's own delivery days (\"4-9\") as CJ states them, days_unit the unit its text names "
     "(business / calendar; null: neither); no handling time is added"),
    ("us_stock_confirmed is true only when CJ states stock in a US warehouse for the quoted variant: a US-to-US freight quote alone "
     "does not prove US stock (measured 2026-11-02: stock by country came back empty while the US quote answered)"),
    ("CJ variant: a product is costed at the cheapest variant left after dropping parts and accessories named as such and, when "
     "the variants' weights spread 2.5 x or more, the ones under 40 % of the heaviest (variant_rule and variants_dropped say "
     "what was dropped and why)"),
    supplier.UNTRUSTED,
]

# ------------------------------------------------------------------------------------------------- terms and relevance --
# `head_terms` and the whole-word matcher `missing_terms` live in acquisition.agent_reach (R2 verify round): CJ and eBay here and
# Amazon, Alibaba and Reddit in the report's parsers read a candidate's term the same way.


def _filter(rows: list[dict[str, Any]], head: list[str], cap: int, ident: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(the relevant rows, at most `cap`; every other row with why it was left out: MISSING_HEAD_TERMS + the terms, or OVER_LIMIT)."""
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for row in rows:
        miss = missing_terms(row.get("title"), head)
        why = "MISSING_HEAD_TERMS" if miss else "OVER_LIMIT" if len(kept) >= cap else None
        if why is None:
            kept.append(row)
        else:
            dropped.append({ident: row.get(ident), "title": row.get("title"), "url": row.get("url"), "why": why, "missing": miss})
    return kept, dropped


def _relevance(head: list[str], kept: list[dict[str, Any]], dropped: list[dict[str, Any]], ident: str) -> dict[str, Any]:
    return {"head_terms": head, "rule": RULE, "kept": [{ident: r.get(ident), "title": r.get("title")} for r in kept],
            "dropped": dropped[:MAX_DROPPED], "dropped_count": len(dropped)}


# ------------------------------------------------------------------------------------------------------ small parsers --
_NUM = re.compile(r"\d+(?:\.\d+)?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_DAYS_UNIT = r"(?:\s*(?:business|working|work|calendar))?(?:\s*(?:days?|d))?"
_DAYS = re.compile(r"(\d{1,3})\s*(?:-|–|—|~|to)\s*(\d{1,3})" + _DAYS_UNIT, re.IGNORECASE)
_DAY = re.compile(r"(\d{1,3})" + _DAYS_UNIT, re.IGNORECASE)
_BUSINESS_DAYS = re.compile(r"\b(?:business|working|work\s*days?|workdays?)\b", re.IGNORECASE)
_CALENDAR_DAYS = re.compile(r"\bcalendar\b", re.IGNORECASE)
_COUNTRY = re.compile(r"[A-Za-z]{2}")
_CANDIDATE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")


def parse_days(text: Any) -> tuple[int | None, int | None]:
    """CJ's delivery days as it states them ("4-9", "3", "10 - 23 days", "2-5 business days") -> (days_min, days_max); (None, None)
    for anything else. The unit the text names is read by `days_unit`, never dropped."""
    raw = " ".join(str(text or "").split()) if isinstance(text, (str, int)) and not isinstance(text, bool) else ""
    m = _DAYS.fullmatch(raw)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = min(a, b), max(a, b)
    else:
        m = _DAY.fullmatch(raw)
        if not m:
            return None, None
        lo = hi = int(m.group(1))
    return (lo, hi) if 1 <= hi <= MAX_DAYS else (None, None)


def days_unit(text: Any) -> str | None:
    """The unit CJ's delivery text states (contract C2): "business" when it says business / working days, "calendar" when it says
    calendar days, None when it says neither (or both). B3 reads None by its policy (`supplier_days_read_as`)."""
    raw = text if isinstance(text, str) else ""
    business, calendar = bool(_BUSINESS_DAYS.search(raw)), bool(_CALENDAR_DAYS.search(raw))
    return "business" if business and not calendar else "calendar" if calendar and not business else None


def number_range(text: Any) -> tuple[float | None, float | None]:
    """A number or a range as CJ lists it ("US$3.83", "US$3.83-16.62", "226.00-1399.00", 7.53) -> (low, high)."""
    if isinstance(text, bool) or text is None:
        return None, None
    nums = [float(x) for x in _NUM.findall(_THOUSANDS.sub("", str(text)))]
    if not nums or len(nums) > 2:
        return None, None
    lo, hi = min(nums), max(nums)
    return (lo, hi) if lo >= 0 and hi < 10_000_000 else (None, None)


def _money(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return round(n, 2) if 0 <= n < 1_000_000 else None


def _whole(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _text(value: Any, n: int) -> str:
    return ebay_api.clean_text(value, n)


def _url(value: Any) -> str | None:
    text = _text(value, 600)
    return text if text.startswith(("https://", "http://")) else None


def _ship_to(value: Any) -> str:
    text = str(value or "").strip()
    if not _COUNTRY.fullmatch(text):
        raise AcquisitionRefused(422, "BAD_COUNTRY", "ship_to is a two-letter country code (ISO 3166-1 alpha-2), e.g. US")
    return text.upper()


# --------------------------------------------------------------------------------------------------------- candidates --
def _term(raw: Any) -> str | None:
    text = " ".join(raw.split())[:TERM_MAX].strip() if isinstance(raw, str) else ""
    return text if len(text) >= 2 and head_terms(text) else None


def search_term(candidate: Mapping[str, Any]) -> str | None:
    """The term searched for a candidate: its first usable search term, else its title's own words up to the first
    "for" / "with" / ... (at most five), else None."""
    terms = candidate.get("search_terms")
    terms = [terms] if isinstance(terms, str) else terms if isinstance(terms, (list, tuple)) else []
    for raw in terms:
        term = _term(raw)
        if term:
            return term
    words = head_terms(candidate.get("title"))[:5]
    return _term(" ".join(words)) if words else None


def _candidates(candidates: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(candidates, (list, tuple)):
        raise AcquisitionRefused(422, "BAD_CANDIDATES", "candidates is a list of {candidate_id, title, search_terms}")
    out: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, raw in enumerate(candidates, 1):
        if not isinstance(raw, Mapping):
            skipped.append({"index": i, "candidate_id": None, "why": "NOT_AN_OBJECT"})
            continue
        cid = str(raw.get("candidate_id") or raw.get("id") or "").strip()
        cid = cid if _CANDIDATE_ID.fullmatch(cid) else f"c{i}"
        while cid in seen:
            cid = f"{cid}_{i}"
        seen.add(cid)
        if len(out) >= MAX_CANDIDATES:
            skipped.append({"index": i, "candidate_id": cid, "why": "OVER_LIMIT"})
            continue
        term = search_term(raw)
        out.append({"candidate_id": cid, "title": _text(raw.get("title"), TITLE_MAX) or None, "term": term,
                    "head_terms": head_terms(term) if term else []})
    return out, skipped


# ------------------------------------------------------------------------------------------------------------ the run --
def _fns(supplier_fns: Any, env: Mapping[str, str] | None, fair_use: Any = None) -> dict[str, Callable[..., Any]]:
    """supplier_fns: None (the supplier tools themselves, on `fair_use` when one is given), a mapping or an object with
    search / product / freight."""
    if supplier_fns is None:
        extra = {k: v for k, v in (("env", env), ("fair_use", fair_use)) if v is not None}
        return {name: functools.partial(getattr(supplier, name), **extra) for name in TOOLS}
    got = ({name: supplier_fns.get(name) for name in TOOLS} if isinstance(supplier_fns, Mapping)
           else {name: getattr(supplier_fns, name, None) for name in TOOLS})
    gone = [name for name, fn in got.items() if not callable(fn)]
    if gone:
        raise TypeError(f"supplier_fns lacks {', '.join(gone)}")
    return got


def _fallback(site: str, query: str | None, code: str, why: str) -> dict[str, Any] | None:
    """The user-side Agent Reach handoff for a call the supplier tools refused before answering (they build their own otherwise)."""
    try:
        built = agent_reach.fallback(site, query, code, why)
    except Exception:  # the handoff is advice: failing to build it must never fail the report
        log.exception("host data: the Agent Reach handoff could not be built")
        return None
    return built if isinstance(built, dict) else None


#: answers worth reusing within one collect (the same call for two candidates asks CJ / eBay once); failures are asked again
_REUSABLE = ("OK", "PARTIAL", "EMPTY", "NOT_FOUND")


def _refusal_code(exc: AcquisitionRefused) -> tuple[str, dict[str, Any]]:
    """(the reason code host data reports for a refusal, its extra fields): a fair-use refusal (SUPPLIER_RATE_LIMITED /
    SUPPLIER_BUSY) is FAIR_USE_LIMITED with the gate's own code and its Retry-After; any other refusal keeps its own code."""
    if exc.code not in FAIR_USE_CODES:
        return exc.code, {}
    extra: dict[str, Any] = {"fair_use_code": exc.code}
    if getattr(exc, "retry_after_s", None):
        extra["retry_after_s"] = exc.retry_after_s
    return FAIR_USE_LIMITED, extra


class EbayDaily:
    """Per principal, in this process: the eBay searches admitted in the current UTC day, at most `limit` (EBAY_DAILY_SEARCHES).
    The owner (principal None) passes untouched; a new UTC day starts every count again. `now` is injected by tests."""

    def __init__(self, now: Callable[[], datetime] | None = None, limit: int = EBAY_DAILY_SEARCHES):
        self._now = now or (lambda: datetime.now(UTC))
        self.limit = limit
        self._day: str | None = None
        self._used: dict[str, int] = {}
        self._lock = threading.Lock()

    def admit(self, principal_id: str | None) -> int | None:
        """Count one eBay search (None), or refuse it: the whole seconds until the next UTC day, when the principal already made
        `limit` of them today."""
        if principal_id is None:
            return None
        now = self._now().astimezone(UTC)
        with self._lock:
            if now.date().isoformat() != self._day:
                self._day, self._used = now.date().isoformat(), {}
            used = self._used.get(principal_id, 0)
            if used >= self.limit:
                midnight = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
                return max(1, math.ceil((midnight - now).total_seconds()))
            self._used[principal_id] = used + 1
        return None

    def refund(self, principal_id: str | None) -> None:
        """Give back one search admitted today that never reached eBay (the fair use refused it right after)."""
        if principal_id is None:
            return
        with self._lock:
            if self._used.get(principal_id, 0) > 0:
                self._used[principal_id] -= 1

    def used(self, principal_id: str) -> int:
        with self._lock:
            return self._used.get(principal_id, 0)


EBAY_DAILY = EbayDaily()


class _Run:
    """One collect(): the principal, the supplier functions, the receipts, the CJ calls per candidate, the fair-use waits and the
    answers already given in this run (two candidates with the same term ask CJ and eBay once)."""

    def __init__(self, principal_id: str | None, fns: dict[str, Callable[..., Any]], sleep: Callable[[float], None], gate: Any,
                 env: Mapping[str, str] | None, daily: EbayDaily | None = None):
        self.principal_id, self.fns, self.sleep, self.gate, self.env = principal_id, fns, sleep, gate, env
        self.daily = daily if daily is not None else EBAY_DAILY
        self.receipts: list[dict[str, Any]] = []
        self.cj_calls: dict[str, int] = {}
        self.ebay_calls = 0
        self.waited_s = 0.0
        self.memo: dict[tuple, Any] = {}

    def ebay_admit(self, cid: str, request: dict[str, Any], client: Any) -> dict[str, Any] | None:
        """R1 #2: an eBay search spends the principal's fair use, the SAME per-key budget its CJ calls spend (`supplier.FairUse`;
        the owner passes untouched), and (R1 verify round) one of the principal's EBAY_DAILY_SEARCHES a UTC day (`EbayDaily`; the
        owner is exempt). None = admitted, or eBay's own breaker is open (then the search answers at once with no network call
        and nothing is spent). Otherwise the entry fields of the refusal: EBAY_DAILY_LIMIT (with the seconds to the next UTC
        day) or FAIR_USE_LIMITED, nothing sent to eBay, so the keyset's shared breaker is never tripped by one friend's refusals."""
        held = client.breaker() if callable(getattr(client, "breaker", None)) else None
        if held:
            return None
        wait = self.daily.admit(self.principal_id)
        if wait is not None:
            why = (f"this eBay search was refused before it reached eBay ({EBAY_DAILY_LIMIT}: at most {self.daily.limit} eBay searches "
                   "per key a UTC day, so that one key never spends the eBay calls every user shares; the owner is exempt): ask "
                   "again after midnight UTC")
            self.receipt(source="ebay", call=EBAY_CALL, candidate_id=cid, request=request, status="REFUSED", reason_code=EBAY_DAILY_LIMIT,
                         rows=0, retry_after_s=wait)
            return {"status": "UNAVAILABLE", "reason_code": EBAY_DAILY_LIMIT, "why": why, "limitations": [why], "calls": 0,
                    "retry_after_s": wait}
        try:
            self.gate.admit(self.principal_id, self.env)
        except AcquisitionRefused as exc:
            self.daily.refund(self.principal_id)                 # the fair use refused it: no eBay search was made
            code, extra = _refusal_code(exc)
            why = (f"this eBay search was refused before it reached eBay ({exc.code}: {exc.message}); eBay searches spend the same "
                   "per-key fair use as CJ calls")
            self.receipt(source="ebay", call=EBAY_CALL, candidate_id=cid, request=request, status="REFUSED", reason_code=code, rows=0,
                         **extra)
            return {"status": "UNAVAILABLE", "reason_code": code, "why": why, "limitations": [why], "calls": 0, **extra}
        return None

    def receipt(self, *, source: str, call: str, candidate_id: str, request: dict[str, Any], status: str, reason_code: str | None,
                rows: int, retrieved_at: Any = None, **extra: Any) -> None:
        self.receipts.append({"n": len(self.receipts) + 1, "source": source, "call": call, "candidate_id": candidate_id,
                              "request": request, "status": status, "reason_code": reason_code, "rows": rows,
                              "retrieved_at": str(retrieved_at or now_iso()), **extra})

    def cj(self, cid: str, name: str, request: dict[str, Any], rows_of: Callable[[Mapping[str, Any]], int]) -> dict[str, Any]:
        """One supplier tool call as the run's principal -> its answer; a refusal or an exception becomes an UNAVAILABLE answer
        with a typed `reason_code`. At most CJ_CALLS_PER_CANDIDATE calls that may reach CJ per candidate (a refusal never does)."""
        key = ("cj", name, tuple(sorted(request.items())))
        if key in self.memo:
            answer = self.memo[key]
            status = str(answer.get("status") or "UNAVAILABLE").upper()
            self.receipt(source="cj", call=TOOLS[name], candidate_id=cid, request=request, status=status,
                         reason_code=answer.get("reason_code"), rows=rows_of(answer) if status in ("OK", "PARTIAL") else 0,
                         retrieved_at=answer.get("retrieved_at"), from_run_memo=True)
            return answer
        if self.cj_calls.get(cid, 0) >= CJ_CALLS_PER_CANDIDATE:
            return {"status": "NOT_FETCHED", "reason_code": "CJ_CALL_BUDGET", "fallback": None,
                    "limitations": [f"not asked: at most {CJ_CALLS_PER_CANDIDATE} CJ calls a candidate"]}
        waited = False
        while True:
            try:
                answer = self.fns[name](principal_id=self.principal_id, **request)
            except AcquisitionRefused as exc:
                code, extra = _refusal_code(exc)
                wait = float(getattr(exc, "retry_after_s", 0) or 0)
                if (exc.code in FAIR_USE_CODES and not waited and 0 < wait <= FAIR_USE_WAIT_MAX_S
                        and self.waited_s + wait <= FAIR_USE_WAIT_TOTAL_S):
                    self.receipt(source="cj", call=TOOLS[name], candidate_id=cid, request=request, status="REFUSED",
                                 reason_code=code, rows=0, waited_s=wait, **extra,
                                 note="refused before any CJ call (fair use); waited its Retry-After and asked once more")
                    self.sleep(wait)
                    self.waited_s += wait
                    waited = True
                    continue
                answer = {**self._failed(name, request, code, f"the {TOOLS[name]} call was refused before it reached CJ "
                                                              f"({exc.code}: {exc.message})"), **extra}
                self.receipt(source="cj", call=TOOLS[name], candidate_id=cid, request=request, status="REFUSED",
                             reason_code=code, rows=0, **extra)
                return answer
            except Exception as exc:  # a supplier tool's own bug is a failure like any other: typed, never raised
                log.exception("host data: %s raised for candidate %s", TOOLS[name], cid)
                answer = self._failed(name, request, "CJ_ERROR", f"the {TOOLS[name]} call failed on this host ({type(exc).__name__})")
            break
        self.cj_calls[cid] = self.cj_calls.get(cid, 0) + 1
        if not isinstance(answer, Mapping):
            answer = {"status": "UNAVAILABLE", "reason_code": "CJ_BAD_REPLY", "fallback": None,
                      "limitations": [f"the {TOOLS[name]} call answered something that is not a result"]}
        status = str(answer.get("status") or "UNAVAILABLE").upper()
        self.receipt(source="cj", call=TOOLS[name], candidate_id=cid, request=request, status=status,
                     reason_code=answer.get("reason_code"), rows=rows_of(answer) if status in ("OK", "PARTIAL") else 0,
                     retrieved_at=answer.get("retrieved_at"))
        if status in _REUSABLE:
            self.memo[key] = answer
        return answer

    @staticmethod
    def _failed(name: str, request: Mapping[str, Any], code: str, why: str) -> dict[str, Any]:
        """A supplier call that gave no answer (refused, or raised) as the UNAVAILABLE answer the tool itself would give: the typed
        code, why, and the same user-side handoff for a search or a product (CJ's freight calculator has none)."""
        fallback = None
        if name == "search":
            fallback = _fallback(cj_api.SITE, request.get("query"), code,
                                 why + ". Your own Agent Reach can search cjdropshipping.com meanwhile")
        elif name == "product":
            fallback = _fallback(cj_api.SITE, request.get("product_id"), code,
                                 why + ". Your own Agent Reach can find this product's page on cjdropshipping.com meanwhile")
        return {"status": "UNAVAILABLE", "reason_code": code, "fallback": fallback, "limitations": [why]}


def _limitations(answer: Mapping[str, Any]) -> list[str]:
    return list(dict.fromkeys(_text(x, 400) for x in answer.get("limitations") or [] if _text(x, 400)))[:MAX_LIMITATIONS]


def _failure_code(answer: Mapping[str, Any], status: str) -> str:
    code = answer.get("reason_code")
    return str(code) if code else {"EMPTY": "CJ_EMPTY", "NOT_FOUND": "CJ_PRODUCT_NOT_FOUND"}.get(status, "CJ_UNAVAILABLE")


def _rows(key: str) -> Callable[[Mapping[str, Any]], int]:
    """How many rows an answer holds under `key` (for its receipt); 0 when that is not a list."""
    return lambda answer: len(answer[key]) if isinstance(answer.get(key), list) else 0


# ------------------------------------------------------------------------------------------------------------------ CJ --
def _search_rows(answer: Mapping[str, Any]) -> list[dict[str, Any]]:
    """supplier_search's items -> {product_id, title, url, image, price_as_listed}, each product once, in the answer's order."""
    sources = {s.get("source_id"): s for s in answer.get("sources") or [] if isinstance(s, Mapping) and s.get("source_id")}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in answer.get("items") or []:
        if not isinstance(item, Mapping):
            continue
        listing = item.get("listing") if isinstance(item.get("listing"), Mapping) else {}
        pid = cj_api.valid_id(listing.get("product_id"))
        title = _text(listing.get("title"), TITLE_MAX)
        if not pid or not title or pid in seen:
            continue
        seen.add(pid)
        rows.append({"product_id": pid, "title": title,
                     "url": _url(item.get("url") or (sources.get(item.get("source_id")) or {}).get("url")),
                     "image": _url(listing.get("image")), "price_as_listed": _text(listing.get("price_as_listed"), 40) or None})
    return rows


def _product(row: Mapping[str, Any]) -> dict[str, Any]:
    """A kept product with what CJ's search gave: its "from" price (the low end of CJ's range, `price_basis` search_from_price);
    details, the variant rule and freight not fetched."""
    low, _ = number_range(row.get("price_as_listed"))
    return {"product_id": row["product_id"], "title": row["title"], "url": row.get("url"), "image": row.get("image"),
            "sell_price_usd": low, "suggested_retail_usd": None, "weight_g": None, "variants": [], "variants_dropped": [],
            "variant_rule": None, "freight": {origin: [] for origin in ORIGINS}, "us_stock_confirmed": False,
            "cheapest_variant_id": None, "price_basis": "search_from_price" if low is not None else None,
            "price_as_listed": row.get("price_as_listed"), "detail_status": "NOT_FETCHED",
            "freight_status": {origin: "NOT_FETCHED" for origin in ORIGINS}}


def _us_units(stock: Any) -> int | None:
    """The units CJ states in US warehouses for a variant; None when CJ states nothing for the US."""
    units = None
    for row in stock if isinstance(stock, list) else []:
        if isinstance(row, Mapping) and str(row.get("country") or "").strip().upper() == "US":
            n = _whole(row.get("total"))
            n = n if n is not None else _whole(row.get("cj_warehouse"))
            if n is not None:
                units = (units or 0) + n
    return units


_VARIANT_WORD = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    """A word without its plain plural ending ("filters" -> "filter", "accessories" -> "accessory")."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _own_words(name: Any, options: Any, title_words: list[str]) -> set[str]:
    """A variant's OWN words: its CJ variant name without the product's title in front (CJ names a variant "<product title>
    <variant key>", so every variant of "... Pets Accessories" would otherwise hold "accessories"), plus its variant key."""
    words = _VARIANT_WORD.findall(str(name or "").lower())
    shared = 0
    while shared < min(len(words), len(title_words)) and words[shared] == title_words[shared]:
        shared += 1
    if shared and shared >= min(3, len(title_words)):
        words = words[shared:]
    return set(words) | set(_VARIANT_WORD.findall(str(options or "").lower()))


def _dropped_variant(v: Mapping[str, Any], why: str, **extra: Any) -> dict[str, Any]:
    return {"variant_id": v.get("variant_id"), "name": v.get("name"), "price_usd": v.get("price_usd"), "weight_g": v.get("weight_g"),
            "why": why, **extra}


def choose_variant(variants: list[dict[str, Any]], *, title: Any, term: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]],
                                                                                   list[dict[str, Any]], dict[str, Any]]:
    """The variant a report costs (VARIANT_RULE) -> (that variant or None, the variants kept (cheapest first; ties: the lower id),
    the variants dropped (each with why: ACCESSORY_NAME + the words, or LIGHT_WEIGHT + the cutoff), the rule as applied). Every
    variant CJ gave is judged, before any display cap. Variants: [{variant_id, name, options, price_usd, weight_g, ...}]."""
    term_stems = {_stem(w) for w in _VARIANT_WORD.findall(str(term or "").lower())}
    title_words = _VARIANT_WORD.findall(str(title or "").lower())
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for v in variants:
        hits = sorted(w for w in _own_words(v.get("name"), v.get("options"), title_words)
                      if _stem(w) in ACCESSORY_WORDS and _stem(w) not in term_stems)
        if hits:
            dropped.append(_dropped_variant(v, "ACCESSORY_NAME", words=hits))
        else:
            kept.append(v)
    weights = [v["weight_g"] for v in kept if isinstance(v.get("weight_g"), (int, float)) and v["weight_g"] > 0]
    heaviest, lightest = (max(weights), min(weights)) if weights else (None, None)
    cutoff = None
    if heaviest is not None and lightest is not None and heaviest >= VARIANT_SPREAD * lightest:
        cutoff = VARIANT_LIGHT_SHARE * heaviest
        light = [v for v in kept if isinstance(v.get("weight_g"), (int, float)) and 0 < v["weight_g"] < cutoff]
        dropped += [_dropped_variant(v, "LIGHT_WEIGHT", cutoff_g=round(cutoff, 1)) for v in light]
        kept = [v for v in kept if not any(v is x for x in light)]
    kept.sort(key=lambda v: (v.get("price_usd") is None, v.get("price_usd") or 0.0, str(v.get("variant_id") or "")))
    chosen = next((v for v in kept if v.get("price_usd") is not None), None)
    rule = {"rule": VARIANT_RULE, "exempt_by_search": [w for w in ACCESSORY_WORDS if w in term_stems],
            "heaviest_g": heaviest, "lightest_g": lightest, "light_cutoff_g": round(cutoff, 1) if cutoff is not None else None,
            "variants": len(variants), "kept": len(kept), "dropped": len(dropped),
            "chosen_variant_id": chosen.get("variant_id") if chosen else None}
    return chosen, kept, dropped, rule


def _apply_details(product: dict[str, Any], answer: Mapping[str, Any], term: Any = None) -> None:
    """supplier_product's answer -> the product's variants and the ONE it is costed at (`choose_variant`: never a part or an
    accessory), with the product's price, suggested retail, weight and US stock from that variant (CJ's product-level figures are
    often a range). `variants` lists the variants the rule kept (cheapest first), `variants_dropped` the others and why,
    `variant_rule` the rule as applied. When the rule drops every variant the product says so (`detail_status`
    NO_COSTED_VARIANT) and carries no price: it never falls back to a dropped variant's price."""
    view = answer.get("product") if isinstance(answer.get("product"), Mapping) else {}
    product["title"] = _text(view.get("title"), TITLE_MAX) or product["title"]
    product["url"] = _url(view.get("url")) or product["url"]
    product["image"] = _url(view.get("image")) or product["image"]
    variants: list[dict[str, Any]] = []
    for v in answer.get("variants") or []:
        if not isinstance(v, Mapping):
            continue
        vid = cj_api.valid_id(v.get("variant_id"))
        if not vid:
            continue
        price, _ = number_range(v.get("price_as_listed"))
        weight, _ = number_range(v.get("weight_g"))
        retail, _ = number_range(v.get("suggested_retail_as_listed"))
        variants.append({"variant_id": vid, "name": _text(v.get("name"), 200) or _text(v.get("options"), 200) or None,
                         "price_usd": price, "weight_g": weight, "options": _text(v.get("options"), 120) or None,
                         "us_stock_units": _us_units(v.get("stock")), "_retail": retail})
    chosen, kept, dropped, rule = choose_variant(variants, title=product["title"], term=term)
    product["variants"] = [{k: v[k] for k in VARIANT_FIELDS} for v in kept[:MAX_VARIANTS]]
    product["variants_dropped"] = dropped[:MAX_VARIANTS]
    product["variant_rule"] = rule
    product["detail_status"] = "OK"
    p_lo, _ = number_range(view.get("price_as_listed"))
    r_lo, r_hi = number_range(view.get("suggested_retail_as_listed"))
    w_lo, w_hi = number_range(view.get("weight_g"))
    single_retail = r_lo if r_lo == r_hi else None
    single_weight = w_lo if w_lo == w_hi else None
    if chosen is not None:
        product["cheapest_variant_id"] = chosen["variant_id"]
        product["sell_price_usd"], product["price_basis"] = chosen["price_usd"], "cheapest_variant"
        product["suggested_retail_usd"] = chosen["_retail"] if chosen["_retail"] is not None else single_retail
        product["weight_g"] = chosen["weight_g"] if chosen["weight_g"] is not None else single_weight
        product["us_stock_confirmed"] = (chosen["us_stock_units"] or 0) > 0
    elif variants and not kept:                                   # every variant was a part, an accessory or a light sample
        product["detail_status"] = "NO_COSTED_VARIANT"
        product["cheapest_variant_id"], product["sell_price_usd"], product["price_basis"] = None, None, None
        product["suggested_retail_usd"], product["weight_g"], product["us_stock_confirmed"] = single_retail, None, False
    else:                                                         # no variant left states a price
        if dropped:                                               # CJ's price range starts at its cheapest variant: maybe a dropped one
            product["sell_price_usd"], product["price_basis"] = None, None
        elif p_lo is not None:
            product["sell_price_usd"], product["price_basis"] = p_lo, "product_from_price"
        product["suggested_retail_usd"], product["weight_g"] = single_retail, single_weight


def freight_options(answer: Mapping[str, Any]) -> list[dict[str, Any]]:
    """supplier_freight's options -> [{carrier, cost_usd, days_min, days_max, days_text, days_unit}], cheapest first (then the
    shortest). cost_usd is CJ's total postage (postage, taxes and clearance) when CJ states it, else its postage; days_unit is
    what CJ's text says the days are (contract C2: "business", "calendar", or None when it says neither)."""
    out: list[dict[str, Any]] = []
    for o in answer.get("options") or []:
        if not isinstance(o, Mapping):
            continue
        total, cost = _money(o.get("total_usd")), _money(o.get("cost_usd"))
        days_min, days_max = parse_days(o.get("delivery_days"))
        out.append({"carrier": _text(o.get("carrier"), 120) or None, "cost_usd": total if total is not None else cost,
                    "days_min": days_min, "days_max": days_max, "days_text": _text(o.get("delivery_days"), 40) or None,
                    "days_unit": days_unit(o.get("delivery_days"))})
    out.sort(key=lambda o: (o["cost_usd"] is None, o["cost_usd"] or 0.0, o["days_max"] is None, o["days_max"] or 0, o["carrier"] or ""))
    return out[:MAX_FREIGHT_OPTIONS]


def _cj_entry(run: _Run, cand: Mapping[str, Any], ship_to: str) -> dict[str, Any]:
    cid, term, head = cand["candidate_id"], cand["term"], cand["head_terms"]
    entry: dict[str, Any] = {"status": None, "reason_code": None, "query": term, "products": [],
                             "relevance": _relevance(head, [], [], "product_id"), "fallback": None, "calls": 0,
                             "retrieved_at": None, "limitations": []}
    if not term:
        entry.update(status="NOT_SEARCHED", reason_code="NO_SEARCH_TERM",
                     limitations=["the candidate has no usable search term (2 or more characters naming the product)"])
        return entry
    found = run.cj(cid, "search", {"query": term, "source": "cj", "limit": CJ_SEARCH_LIMIT}, _rows("items"))
    status = str(found.get("status") or "UNAVAILABLE").upper()
    entry["retrieved_at"], entry["limitations"] = found.get("retrieved_at"), _limitations(found)
    entry["fallback"] = found.get("fallback") if isinstance(found.get("fallback"), Mapping) else None
    for carried in ("retry_after_s", "fair_use_code"):
        if found.get(carried):
            entry[carried] = found[carried]
    rows = _search_rows(found) if status in ("OK", "PARTIAL") else []
    if not rows:
        empty = status in ("OK", "PARTIAL", "EMPTY")
        entry.update(status="EMPTY" if empty else "UNAVAILABLE", reason_code="CJ_EMPTY" if empty else _failure_code(found, status),
                     calls=run.cj_calls.get(cid, 0))
        return entry
    kept, dropped = _filter(rows, head, MAX_PRODUCTS, "product_id")
    entry["relevance"] = _relevance(head, kept, dropped, "product_id")
    if not kept:
        entry.update(status="NO_MATCH", reason_code="CJ_NO_RELEVANT", calls=run.cj_calls.get(cid, 0))
        return entry
    products = [_product(row) for row in kept]
    entry["products"] = products
    failures: list[str] = []
    top = products[0]
    receipts_before = len(run.receipts)
    detail = run.cj(cid, "product", {"product_id": top["product_id"]}, _rows("variants"))
    d_status = str(detail.get("status") or "UNAVAILABLE").upper()
    if d_status == "OK":
        _apply_details(top, detail, term)
        if top["detail_status"] == "NO_COSTED_VARIANT":
            failures.append("CJ_NO_COSTED_VARIANT")
        elif top["cheapest_variant_id"] is None:
            failures.append("CJ_NO_PRICED_VARIANT")
        for row in run.receipts[receipts_before:]:                # the product's receipt carries the rule and what it dropped
            if row["call"] == TOOLS["product"]:
                row.update(chosen_variant_id=top["cheapest_variant_id"], variant_rule=top["variant_rule"],
                           variants_dropped=[{"variant_id": d["variant_id"], "why": d["why"]} for d in top["variants_dropped"]])
    else:
        top["detail_status"] = d_status if d_status in ("NOT_FOUND", "NOT_FETCHED") else "UNAVAILABLE"
        failures.append(_failure_code(detail, d_status))
        if entry["fallback"] is None and isinstance(detail.get("fallback"), Mapping):
            entry["fallback"] = detail["fallback"]
        entry["limitations"] = list(dict.fromkeys(entry["limitations"] + _limitations(detail)))[:MAX_LIMITATIONS]
    vid = top["cheapest_variant_id"]
    for origin in ORIGINS if vid else ():
        quote = run.cj(cid, "freight", {"variant_id": vid, "country": ship_to, "quantity": 1, "from_country": origin},
                       _rows("options"))
        q_status = str(quote.get("status") or "UNAVAILABLE").upper()
        if q_status == "OK":
            top["freight"][origin], top["freight_status"][origin] = freight_options(quote), "OK"
        elif q_status == "EMPTY":                                 # CJ answered: no shipping option from this origin
            top["freight_status"][origin] = "EMPTY"
        else:
            top["freight_status"][origin] = "NOT_FETCHED" if q_status == "NOT_FETCHED" else "UNAVAILABLE"
            failures.append(_failure_code(quote, q_status))
    entry.update(status="PARTIAL" if failures else "OK", reason_code=failures[0] if failures else None, calls=run.cj_calls.get(cid, 0))
    return entry


# ---------------------------------------------------------------------------------------------------------------- eBay --
def _ebay_entry(run: _Run, cand: Mapping[str, Any], ship_to: str, client: Any, not_configured: str | None) -> dict[str, Any]:
    cid, term, head = cand["candidate_id"], cand["term"], cand["head_terms"]
    entry: dict[str, Any] = {"status": None, "reason_code": None, "query": term, "listings": [],
                             "relevance": _relevance(head, [], [], "item_id"), "calls": 0, "retrieved_at": None, "limitations": []}
    if client is None:
        entry.update(status="NOT_CONFIGURED", reason_code=ebay_api.NOT_CONFIGURED, why=not_configured,
                     limitations=[not_configured or "the eBay Browse API is not configured on this host"])
        return entry
    if not term:
        entry.update(status="NOT_SEARCHED", reason_code="NO_SEARCH_TERM")
        return entry
    request = {"q": term, "ship_to": ship_to, "limit": EBAY_SEARCH_LIMIT}
    key = ("ebay", term, ship_to)
    reused = key in run.memo
    if not reused:
        refused = run.ebay_admit(cid, request, client)            # the principal's fair use, before anything reaches eBay
        if refused is not None:
            entry.update(refused)
            return entry
    try:
        got = run.memo[key] if reused else client.search(term, ship_to=ship_to, limit=EBAY_SEARCH_LIMIT)
    except ApiFailed as exc:
        code = ebay_api.REASON_CODES.get(exc.reason, "EBAY_ERROR")
        why = f"the {ebay_api.LABEL} could not answer ({exc.reason}: {exc.detail})"
        entry.update(status="UNAVAILABLE", reason_code=code, why=why, limitations=[why])
        if exc.retry_after_s is not None:                         # the breaker answered: eBay was not called
            entry["retry_after_s"] = exc.retry_after_s
        else:
            entry["calls"] = 1
            run.ebay_calls += 1
        run.receipt(source="ebay", call=EBAY_CALL, candidate_id=cid, request=request, status="UNAVAILABLE", reason_code=code, rows=0,
                    **({"retry_after_s": exc.retry_after_s} if exc.retry_after_s is not None else {}))
        return entry
    except Exception as exc:  # the eBay reader's own bug is a failure like any other
        log.exception("host data: the eBay search raised for candidate %s", cid)
        why = f"the {ebay_api.LABEL} reader failed on this host ({type(exc).__name__})"
        entry.update(status="UNAVAILABLE", reason_code="EBAY_ERROR", why=why, limitations=[why], calls=1)
        run.ebay_calls += 1
        run.receipt(source="ebay", call=EBAY_CALL, candidate_id=cid, request=request, status="UNAVAILABLE", reason_code="EBAY_ERROR",
                    rows=0)
        return entry
    if not reused:
        run.ebay_calls += 1
        run.memo[key] = got
    listings = [row for row in got.get("listings") or [] if isinstance(row, Mapping)]
    kept, dropped = _filter(listings, head, MAX_LISTINGS, "item_id")
    entry["relevance"] = {**_relevance(head, kept, dropped, "item_id"), "unusable": int(got.get("unusable") or 0)}
    entry["listings"] = [{k: row.get(k) for k in LISTING_FIELDS} for row in kept]
    entry.update(status="OK" if kept else "NO_MATCH" if listings else "EMPTY",
                 reason_code=None if kept else "EBAY_NO_RELEVANT" if listings else "EBAY_EMPTY", calls=0 if reused else 1,
                 retrieved_at=got.get("retrieved_at"), total=got.get("total"), request=got.get("request"),
                 limitations=[ebay_api.SOURCE_NOTE, ebay_api.UNTRUSTED])
    run.receipt(source="ebay", call=EBAY_CALL, candidate_id=cid, request=dict(got.get("request") or request), status=entry["status"],
                reason_code=entry["reason_code"], rows=len(listings), retrieved_at=got.get("retrieved_at"),
                **({"from_run_memo": True} if reused else {}))
    return entry


def _codes(entries: Mapping[str, Any]) -> list[str]:
    return sorted({str(e["reason_code"]) for e in entries.values() if isinstance(e, Mapping) and e.get("reason_code")})


def _crashed(cand: Mapping[str, Any], source: str, exc: Exception) -> dict[str, Any]:
    why = f"collecting {source} data for this candidate failed on this host ({type(exc).__name__})"
    entry: dict[str, Any] = {"status": "UNAVAILABLE", "reason_code": "HOST_DATA_ERROR", "query": cand.get("term"), "calls": 0,
                             "relevance": _relevance(cand.get("head_terms") or [], [], [], "product_id" if source == "cj" else "item_id"),
                             "retrieved_at": None, "limitations": [why]}
    entry.update({"products": [], "fallback": None} if source == "cj" else {"listings": []})
    return entry


# ------------------------------------------------------------------------------------------------------------- collect --
def collect(candidates: list[dict[str, Any]], *, principal_id: str | None, ship_to: str = "US", supplier_fns: Any = None,
            ebay: Any = None, env: Mapping[str, str] | None = None, sleep: Callable[[float], None] | None = None,
            fair_use: Any = None, ebay_daily: EbayDaily | None = None) -> dict[str, Any]:
    """The host data of a product decision report (PRODUCT-DECISION-REPORT-V1 §4.3) -> {cj: {candidate_id: {status, reason_code,
    products, relevance, ...}}, ebay: {candidate_id: {status, reason_code, listings, ...}}, receipts: [...], plus contract,
    ship_to, retrieved_at, ebay_configured, reason_codes, skipped (candidates over MAX_CANDIDATES or not objects), calls, limits,
    notes}.

    Reason codes (contract C6) live at cj.<candidate_id>.reason_code and ebay.<candidate_id>.reason_code (null when that source
    answered OK), per call at receipts[].reason_code (with receipts[].source); `reason_codes` = {cj: [...], ebay: [...]}, the
    distinct non-null codes of the entries, sorted.

    candidates: [{candidate_id (or id), title, search_terms}]; principal_id: the caller (None = the owner), passed to every
    supplier tool so fair use applies, and held to the same fair use before every eBay search (R1 #2); supplier_fns: the
    supplier tools (default) or test doubles with the same keywords; ebay: an `ebay_api.EbayClient`, else one from the
    environment (none = EBAY_NOT_CONFIGURED); env: the environment to read (default os.environ); sleep: how a fair-use wait
    waits (tests inject a fake clock); fair_use: the fair-use gate (default `supplier.FAIR_USE`, the one the supplier tools use);
    ebay_daily: the friends' daily eBay budget (default `EBAY_DAILY`, EBAY_DAILY_SEARCHES a UTC day per principal)."""
    supplier.authorize(principal_id)
    ship = _ship_to(ship_to)
    source_env = os.environ if env is None else env
    gate = fair_use if fair_use is not None else supplier.FAIR_USE
    run = _Run(principal_id, _fns(supplier_fns, env, fair_use), sleep or time.sleep, gate, env, ebay_daily)
    client = ebay if ebay is not None else ebay_api.client_from_env(source_env)
    not_configured = None if client is not None else ebay_api.not_configured_why(source_env)
    cands, skipped = _candidates(candidates)
    cj: dict[str, Any] = {}
    eb: dict[str, Any] = {}
    for cand in cands:
        cid = cand["candidate_id"]
        try:
            cj[cid] = _cj_entry(run, cand, ship)
        except Exception as exc:  # one candidate's failure never stops the others
            log.exception("host data: CJ for candidate %s raised", cid)
            cj[cid] = {**_crashed(cand, "cj", exc), "calls": run.cj_calls.get(cid, 0)}
        try:
            eb[cid] = _ebay_entry(run, cand, ship, client, not_configured)
        except Exception as exc:  # one candidate's failure never stops the others
            log.exception("host data: eBay for candidate %s raised", cid)
            eb[cid] = _crashed(cand, "ebay", exc)
    return {"contract": CONTRACT, "ship_to": ship, "retrieved_at": now_iso(), "cj": cj, "ebay": eb, "receipts": run.receipts,
            "ebay_configured": client is not None, "reason_codes": {"cj": _codes(cj), "ebay": _codes(eb)}, "skipped": skipped,
            "calls": {"cj": sum(run.cj_calls.values()), "ebay": run.ebay_calls, "fair_use_waited_s": run.waited_s},
            "limits": {"max_candidates": MAX_CANDIDATES, "cj_products_per_candidate": MAX_PRODUCTS,
                       "cj_calls_per_candidate": CJ_CALLS_PER_CANDIDATE, "ebay_listings_per_candidate": MAX_LISTINGS},
            "notes": NOTES[:-1] + [ebay_api.SOURCE_NOTE if client is not None else not_configured, NOTES[-1]]}
