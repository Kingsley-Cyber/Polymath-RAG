"""PRODUCT-DECISION-REPORT-V1 §4.4 (B3): the decision report's money and delivery model. Pure: no I/O, no network, no clock.

    compute(bundle, policy) -> decision
      bundle = {candidates, host (plan §4.3), parsed: {candidate_id: {reddit, amazon, ebay, alibaba}}, settings}
      policy = the engine's policies (graph.load_policies()): `sales_channels` + `report_settings` (graph/policies.yaml)

Per candidate it lays out the supplier OFFERS in two models. DROPSHIP (each CJ product): the cheapest variant, MOQ 1, CJ ships each
order — its freight quotes from China and from a US warehouse. INVENTORY (each Alibaba listing): buy the MOQ in bulk at the tier price
that holds it (MOQ capital), bring it to your US stock (inbound freight per unit by the listing's own terms, once: lead time + transit
to first stock), then ship each order from US stock (the last mile: per channel, the cheapest of the candidate's CJ US→US quotes whose
days pass the channel's rule, as labelled proxies, else the owner's settings, else UNKNOWN) — so its customer delivery is the last
mile from the US. Then the MARKET (matched Amazon and eBay listings: n / median / min / max of price + shipping where
stated, and the reference price), the DEMAND counts (Reddit threads and their top comments, Amazon's best seller rank, "bought in past
month" and ratings) and, per sales channel, every offer's line: sell price, unit cost, shipping, fees, returns allowance, margin
before ads, margin %, break-even ad cost per sale and the delivery verdict — the best offer first, the rest kept.

The owner's decisions (2026-11-02): TikTok Shop is shown as a US local account AND as a cross-border account; returns are 19.3 % of
sales (NRF, 2025-10-15) costed at unit cost + shipping; no ad cost is assumed — the break-even ad cost per sale IS the margin before
ads; TikTok's 8 % rate (unconfirmed, trade blogs) is a sensitivity, never the base case.

Laws:
  * deterministic code does every number; every number in a product carries a receipt {id, formula, inputs, result} whose `id` is
    the number's path inside the product (`channels.tiktok_us.fees_usd`, `offers[0].shipping[1].cost_usd`) and whose `result` is
    the number itself;
  * a missing input yields "UNKNOWN" (its receipt names what is missing), never a guess; CJ's suggested retail is never a price;
  * money is Decimal: every computed amount is rounded half-up to cents, margin % to one decimal; a stated price keeps its
    precision (an Alibaba tier of $0.035 stays $0.035);
  * every rate and threshold comes from `policy` (each printed in `assumptions` with its source URL and the date it was read);
  * the engine never imports `polymath_shared`: the dossier runs this out of process with a JSON bundle, and
    `python unit_economics.py --bundle bundle.json [--out decision.json]` does the same by hand.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

MODEL = "unit_economics.v1"
UNKNOWN = "UNKNOWN"
PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
CENT, TENTH, HUNDRED, THOUSAND = Decimal("0.01"), Decimal("0.1"), Decimal(100), Decimal(1000)
FEE_KINDS = ("percent", "percent_fixed_plan", "percent_per_order", "referral_min_per_item")
DELIVERY_KINDS = ("us_local_only", "max_days", "honest_handling")
US_STOCK_UNCONFIRMED = "US_STOCK_UNCONFIRMED"
REQUIRES_US_STOCK = "REQUIRES_US_STOCK"
DROPSHIP, INVENTORY = "dropship", "inventory"


class DecisionInputError(ValueError):
    """The bundle, a setting or the policy cannot be modelled as given: nothing is computed (fail closed, never a guess)."""


_ORIGIN_NAMES = {"US": "a US warehouse", "CN": "China"}
_ORIGIN_CODES = {"us": "US", "usa": "US", "united states": "US", "united states of america": "US", "cn": "CN", "china": "CN",
                 "mainland china": "CN"}
_BARE_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_DAYS = re.compile(r"(\d{1,3})(?:\s*(?:-|–|~|to)\s*(\d{1,3}))?")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_COUNT = re.compile(r"(\d+(?:\.\d+)?)\s*([KkMm])?")
_POINTS = re.compile(r"[-−]?\d+")
#: one Alibaba price tier as the listing parse prints them: "$0.18 (55-99 pieces)", "US $1.20 - 1.50 (≥500 pieces)"
_TIER = re.compile(r"((?:US\s?\$|USD\s?\$?|\$)\s?\d[\d,]*(?:\.\d+)?(?:\s*[-–~]\s*(?:US\s?\$|USD\s?\$?|\$)?\s?\d[\d,]*(?:\.\d+)?)?)\s*\(([^)]*)\)",
                   re.IGNORECASE)
_TIER_QTY = re.compile(r"(≥|>=|>)?\s*(\d[\d,]*)(?:\s*[-–~]\s*(\d[\d,]*))?")
_WEIGHT = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|kgs|kilograms?|g|grams?)\b", re.IGNORECASE)
_EBAY_ITEM = re.compile(r"/itm/(?:[^/?#]+/)?(\d{6,})")
_FREE = re.compile(r"\bfree\s+(?:shipping|delivery|postage)\b", re.IGNORECASE)


# ------------------------------------------------------------------------------------------------------------- numbers --
def _dec(value: Any) -> Decimal | None:
    """A finite, non-negative number (int, float, Decimal or a bare numeric string such as "3.27" / "1,234") -> Decimal, else None.
    A float goes through its shortest repr, so 0.1 is Decimal("0.1"), never the binary expansion."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, (int, float)):
        d = Decimal(str(value))
    elif isinstance(value, str):
        s = value.strip().replace(",", "")
        if not _BARE_NUMBER.fullmatch(s):
            return None
        d = Decimal(s)
    else:
        return None
    return d if d.is_finite() and d >= 0 else None


def _usd(value: Any) -> Decimal | None:
    """A US-dollar amount: a number, or text the engine's own price parser reads as dollars (executors._parse_price: a currency other
    than US$ / USD / a bare $ is "not parsed", never 25 dollars). A range reads as its low end here; callers that need the
    conservative end use _usd_range."""
    lo, _ = _usd_range(value)
    return lo


def _usd_range(value: Any) -> tuple[Decimal | None, Decimal | None]:
    d = _dec(value)
    if d is not None:
        return d, d
    if not isinstance(value, str) or not value.strip():
        return None, None
    import executors as _ex  # the engine's one price parser (adapter_receipt does the same); imported lazily: it is not small
    lo, hi = _ex._parse_price(value)
    return _dec(lo), _dec(hi)


def _cents(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def _unit4(d: Decimal) -> Decimal:
    """A per-unit share of a total (inbound freight ÷ MOQ): half-up to 4 decimals, so the share × MOQ gives the total back to the cent."""
    return d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _out(value: Any) -> Any:
    """The JSON form of a number: Decimal -> float (shortest repr), int stays int, None -> "UNKNOWN"."""
    if value is None:
        return UNKNOWN
    if isinstance(value, Decimal):
        return float(value)
    return value


def _int(value: Any) -> int | None:
    """A non-negative whole number (int, integral float, "12", "1,234") -> int, else None."""
    d = _dec(value)
    return int(d) if d is not None and d == d.to_integral_value() else None


def _count(value: Any) -> int | None:
    """A count as a listing shows it: 2000, "2,000", "2K+ bought in past month", "1.5K" -> int; anything else -> None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        d = _dec(value)
        return int(d) if d is not None else None
    m = _COUNT.search(str(value).replace(",", ""))
    if not m:
        return None
    n = Decimal(m.group(1)) * {"k": THOUSAND, "m": THOUSAND * THOUSAND}.get((m.group(2) or "").lower(), Decimal(1))
    return int(n)


def _points(value: Any) -> int | None:
    """Reddit points (may be negative): 81, "81", "81 points", "-3" -> int."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value == int(value) else None
    m = _POINTS.search(str(value))
    return int(m.group(0).replace("−", "-")) if m else None


def _days(lo: Any, hi: Any = None, text: Any = None) -> tuple[int | None, int | None]:
    """(days_min, days_max) from numbers, or from text such as "4-9", "7 to 15 days", "12"."""
    a, b = _int(lo), _int(hi)
    if a is None and b is None and isinstance(text, str):
        m = _DAYS.search(text)
        if m:
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
    if a is not None and b is None:
        b = a
    if a is not None and b is not None and a > b:
        a, b = b, a
    return a, b


def _iso_date(value: Any) -> str | None:
    """"2026-10-12", "2026-10-12T08:00:00Z" -> "2026-10-12"; anything else (relative text such as "3 weeks ago") -> None."""
    if not isinstance(value, str):
        return None
    m = _ISO_DATE.match(value.strip())
    if not m or not (1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31):
        return None
    return m.group(0)


def _business_days_max(days: int, read_as: str) -> int:
    """The most business days `days` supplier days can be. Read as calendar days, the worst case is the run of days holding the
    fewest weekend days (7 calendar days hold 5 business days, 8 hold at most 6, 9 at most 7); read as business days, they are."""
    if read_as == "business":
        return days
    weeks, rest = divmod(days, 7)
    return days - (2 * weeks + max(0, rest - 5))


def _clip(value: Any, n: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _plain(d: Decimal) -> str:
    """A quantity as people write it: Decimal("50.0") -> "50", Decimal("17.00") -> "17", Decimal("0.170") -> "0.17"."""
    return format(d.normalize(), "f")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ------------------------------------------------------------------------------------------------------------ receipts --
class _Book:
    """The receipts of one product. Every row: {id: the value's path in the product, formula, inputs, result: the value}."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, rid: str, formula: str, inputs: dict[str, Any], result: Any, **extra: Any) -> Any:
        row = {"id": rid, "formula": formula, "inputs": inputs, "result": result}
        row.update({k: v for k, v in extra.items() if v is not None})
        self.rows.append(row)
        return result

    def observed(self, rid: str, value: Any, source: str, field: str) -> Any:
        """A number read from an input as it stands (a quote, a listing, a comment)."""
        out = _out(value)
        return self.add(rid, "observed" if value is not None else "observed: not stated", {"source": source, "field": field}, out,
                        missing=[field] if value is None else None)


class _Pending:
    """Receipts whose final path is known only later (a channel line's position is decided after every offer is priced)."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, dict[str, Any], Any, dict[str, Any]]] = []

    def add(self, rel: str, formula: str, inputs: dict[str, Any], result: Any, **extra: Any) -> Any:
        self.rows.append((rel, formula, inputs, result, extra))
        return result

    def emit(self, book: _Book, prefix: str) -> None:
        for rel, formula, inputs, result, extra in self.rows:
            book.add(f"{prefix}.{rel}", formula, inputs, result, **extra)


# -------------------------------------------------------------------------------------------------------------- policy --
def _policy(policy: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """`sales_channels` and `report_settings`, checked: fail closed on a missing section, an unknown formula kind or a source id
    that resolves to nothing."""
    if not isinstance(policy, dict) or not isinstance(policy.get("sales_channels"), dict) or not isinstance(policy.get("report_settings"), dict):
        raise DecisionInputError("policy must be the engine's policies (graph.load_policies()) holding `sales_channels` and `report_settings`")
    sc, rs = policy["sales_channels"], policy["report_settings"]
    channels, sources = sc.get("channels") or {}, sc.get("sources") or {}
    for cid in sc.get("order") or []:
        ch = channels.get(cid)
        if not isinstance(ch, dict):
            raise DecisionInputError(f"sales_channels.order names {cid!r}, which sales_channels.channels does not define")
        if (ch.get("fee") or {}).get("kind") not in FEE_KINDS:
            raise DecisionInputError(f"sales_channels.channels.{cid}.fee.kind must be one of {FEE_KINDS}")
        fee = ch["fee"]
        if fee["kind"] == "percent_per_order" and (not fee.get("per_order") or fee["per_order"][-1].get("max_order_usd") is not None):
            raise DecisionInputError(f"sales_channels.channels.{cid}.fee.per_order must end with a tier without max_order_usd")
        if (ch.get("delivery") or {}).get("kind") not in DELIVERY_KINDS:
            raise DecisionInputError(f"sales_channels.channels.{cid}.delivery.kind must be one of {DELIVERY_KINDS}")
        sens = ch.get("sensitivity")
        if sens is not None and (not isinstance(sens, dict) or not sens.get("id") or _dec(sens.get("rate_pct")) is None):
            raise DecisionInputError(f"sales_channels.channels.{cid}.sensitivity needs an id and a rate_pct")
        for sid in list(ch.get("sources") or []) + list((sens or {}).get("sources") or []):
            if sid not in sources:
                raise DecisionInputError(f"sales_channels.channels.{cid} cites source {sid!r}, which sales_channels.sources does not define")
    if not isinstance(rs.get("defaults"), dict):
        raise DecisionInputError("report_settings.defaults is missing")
    if rs.get("returns_rate_source") not in sources:
        raise DecisionInputError("report_settings.returns_rate_source must name a sales_channels source")
    return sc, rs


def _settings(raw: Any, sc: dict[str, Any], rs: dict[str, Any]) -> dict[str, Any]:
    """The report's settings over `report_settings.defaults`: shopify_monthly_orders (a whole number ≥ 1), returns_rate (0 ≤ r < 1),
    ship_to ("US": the only market the channel rules describe), channels (a subset of sales_channels.order, kept in that order),
    as_of (the only date the model knows)."""
    if raw is not None and not isinstance(raw, dict):
        raise DecisionInputError("settings must be an object")
    raw = raw or {}
    d = dict(rs["defaults"])
    for key in ("shopify_monthly_orders", "returns_rate", "ship_to", "last_mile_usd", "last_mile_days", "handling_business_days"):
        if raw.get(key) is not None:
            d[key] = raw[key]
    orders = d.get("shopify_monthly_orders")
    if isinstance(orders, bool) or _int(orders) is None or _int(orders) < 1:
        raise DecisionInputError("settings.shopify_monthly_orders must be a whole number of at least 1")
    rate = _dec(d.get("returns_rate")) if not isinstance(d.get("returns_rate"), str) else None
    if rate is None or rate >= 1:
        raise DecisionInputError("settings.returns_rate must be a number from 0 to below 1 (0.193 = 19.3 %)")
    if d.get("ship_to") != "US":
        raise DecisionInputError("settings.ship_to must be \"US\": the channel rules describe the US market only")
    order = list(sc.get("order") or [])
    wanted = raw.get("channels")
    if wanted is None:
        channels = order
    else:
        if not isinstance(wanted, list) or not wanted or any(c not in order for c in wanted):
            raise DecisionInputError(f"settings.channels must be a non-empty list drawn from {order}")
        channels = [c for c in order if c in wanted]
    as_of = raw.get("as_of")
    if as_of is not None and not isinstance(as_of, str):
        raise DecisionInputError("settings.as_of must be a date string")
    handling = d.get("handling_business_days")
    if isinstance(handling, (bool, str)) or _int(handling) is None:
        raise DecisionInputError("settings.handling_business_days must be a whole number of at least 0 (business days to the first carrier scan)")
    lm_usd, lm_days = d.get("last_mile_usd"), d.get("last_mile_days")
    if lm_usd is not None and (isinstance(lm_usd, (bool, str)) or _dec(lm_usd) is None):
        raise DecisionInputError("settings.last_mile_usd must be a number of at least 0, or null")
    if lm_days is not None and (isinstance(lm_days, (bool, str)) or _int(lm_days) is None):
        raise DecisionInputError("settings.last_mile_days must be a whole number of at least 0, or null")
    return {"shopify_monthly_orders": _int(orders), "returns_rate": rate, "ship_to": "US", "channels": channels, "as_of": as_of,
            "last_mile_usd": _dec(lm_usd) if lm_usd is not None else None, "last_mile_days": _int(lm_days) if lm_days is not None else None,
            "handling_business_days": _int(handling)}


def _policy_hash(sc: dict[str, Any], rs: dict[str, Any]) -> str:
    blob = json.dumps({"sales_channels": sc, "report_settings": rs}, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------------------------------------------------- records --
def _records(items: Any) -> list[dict[str, Any]]:
    """Records as handed over: a list of records, or of parse results ({status, records: [...]}) whose records are taken."""
    out: list[dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict) and isinstance(item.get("records"), list):
            out.extend(r for r in item["records"] if isinstance(r, dict))
        elif isinstance(item, dict):
            out.append(item)
    return out


def _flat(record: dict[str, Any]) -> dict[str, Any]:
    """The listing parse nests its fields under `listing`; the report parse may not. Either way: one flat dict."""
    inner = record.get("listing")
    return {**record, **inner} if isinstance(inner, dict) else dict(record)


def _filled(record: dict[str, Any]) -> int:
    return sum(1 for v in record.values() if v not in (None, "", [], {}))


def _merge(records: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    """Records that name the same thing (an Exa result in round 1 and its product page in round 2) become one: field by field, the
    first non-empty value of the richer record wins. First-seen order is kept."""
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    order: list[str] = []
    for i, rec in enumerate(records):
        k = key(rec, i)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append((i, rec))
    merged = []
    for k in order:
        ranked = [r for _, r in sorted(groups[k], key=lambda ir: (-_filled(ir[1]), ir[0]))]
        out: dict[str, Any] = {}
        for rec in ranked:
            for f, v in rec.items():
                if out.get(f) in (None, "", [], {}) and v not in (None, "", [], {}):
                    out[f] = v
        merged.append(out)
    return merged


def _norm_url(url: Any) -> str:
    text = str(url or "").strip()
    m = re.match(r"(?i)^(https?)://([^/?#]+)([^?#]*)", text)
    if not m:
        return text
    host = m.group(2).lower()
    host = re.sub(r"^(?:www|old|new|np)\.(reddit\.com)$", r"\1", host)
    return f"https://{host}{m.group(3).rstrip('/')}"


def _origin(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return _ORIGIN_CODES.get(text.lower(), text.upper()[:40] or None)


# -------------------------------------------------------------------------------------------------------------- offers --
def _cj_offers(block: dict[str, Any], cj_moq: int) -> list[dict[str, Any]]:
    offers = []
    for p in block.get("products") or []:
        if not isinstance(p, dict):
            continue
        priced = []
        for v in p.get("variants") or []:
            if isinstance(v, dict):
                price = _usd(v.get("price_usd"))
                if price is not None and price > 0:
                    priced.append((price, str(v.get("variant_id") or ""), v))
        if priced:
            price, vid, _variant = min(priced, key=lambda t: (t[0], t[1]))
            unit, basis = price, {"formula": "the cheapest variant's price", "inputs": {"variant_id": vid or None, "variants_priced": len(priced),
                                                                                       "variant_prices": sorted(float(t[0]) for t in priced)}}
        else:
            lo, _ = _usd_range(p.get("sell_price_usd"))
            unit = lo if lo is not None and lo > 0 else None
            basis = ({"formula": "the product's CJ price (no variant states a price; a range reads as its low end, the cheapest variant)",
                      "inputs": {"sell_price_usd": p.get("sell_price_usd")}} if unit is not None else
                     {"formula": "no variant and no product price stated", "inputs": {"sell_price_usd": p.get("sell_price_usd")}, "missing": ["variant price"]})
        shipping = []
        freight = p.get("freight") if isinstance(p.get("freight"), dict) else {}
        for origin_key in sorted(freight):
            for o in freight.get(origin_key) or []:
                if not isinstance(o, dict):
                    continue
                dmin, dmax = _days(o.get("days_min"), o.get("days_max"), o.get("delivery_days"))
                days_unit = o.get("days_unit") if o.get("days_unit") in ("business", "calendar") else None   # C2: a missing key is null
                shipping.append({"origin": _origin(origin_key), "carrier": _clip(o.get("carrier"), 120) or None, "cost": _usd(o.get("cost_usd")),
                                 "days_min": dmin, "days_max": dmax, "days_unit": days_unit, "lead": None, "basis": "cj_quote"})
        pid = str(p.get("product_id") or "").strip()
        offers.append({"offer_id": f"cj:{pid}" if pid else None, "source": "cj", "model": DROPSHIP, "title": _clip(p.get("title"), 300) or None,
                       "url": p.get("url") or None, "image": p.get("image") or None, "supplier": "CJdropshipping",
                       "unit_cost": unit, "unit_basis": basis, "moq": cj_moq, "lead_time": None, "shipping": shipping,
                       "us_stock_confirmed": p.get("us_stock_confirmed") if isinstance(p.get("us_stock_confirmed"), bool) else None,
                       "suggested_retail": _usd(p.get("suggested_retail_usd")), "weight_g": _cj_weight(p)})
    return offers


def _cj_weight(p: dict[str, Any]) -> Decimal | None:
    """The CJ product's weight in grams (a range such as "120-150" reads as its heavier end); the cheapest variant's weight when the
    product states none."""
    def grams(v: Any) -> Decimal | None:
        d = _dec(v)
        if d is not None:
            return d
        nums = re.findall(r"\d+(?:\.\d+)?", str(v or ""))
        return max(Decimal(n) for n in nums) if nums else None
    w = grams(p.get("weight_g"))
    if w is None:
        ws = [grams(v.get("weight_g")) for v in p.get("variants") or [] if isinstance(v, dict)]
        ws = [x for x in ws if x is not None]
        w = max(ws) if ws else None
    return w if w is not None and w > 0 else None


def _tiers(rec: dict[str, Any]) -> list[tuple[Decimal, int | None, int | None, bool]]:
    """[(price, min qty, max qty, price was a range)] from structured tiers, or from the listing parse's `price_as_listed`
    ("$0.18 (55-99 pieces), $0.17 (100-499 pieces), $0.16 (≥500 pieces)"). A tier priced as a range keeps its HIGH end."""
    out = []
    structured = rec.get("tiers") or rec.get("price_tiers")
    if isinstance(structured, list) and structured:
        for t in structured:
            if isinstance(t, dict):
                lo, hi = _usd_range(next((t[k] for k in ("unit_price", "price_usd", "price") if t.get(k) is not None), None))
                if t.get("unit_price_low") is not None and hi is not None:          # C3: unit_price is the HIGH end, unit_price_low the low end
                    low = _usd(t.get("unit_price_low"))
                    lo = low if low is not None and low <= hi else lo
                qmin = _int(t.get("min_qty", t.get("qty_min", t.get("min"))))
                qmax = _int(t.get("max_qty", t.get("qty_max", t.get("max"))))
                qty_text = t.get("quantity") or t.get("qty")
                if qmin is None and isinstance(qty_text, str):
                    qmin, qmax = _qty_range(qty_text)
            elif isinstance(t, (list, tuple)) and len(t) == 2:
                lo, hi = _usd_range(t[0])
                qmin, qmax = _qty_range(str(t[1]))
            else:
                continue
            if hi is not None and hi > 0:
                out.append((hi, qmin, qmax, lo != hi))
        return out
    text = rec.get("price_as_listed")
    if isinstance(text, str):
        for m in _TIER.finditer(text):
            lo, hi = _usd_range(m.group(1))
            qmin, qmax = _qty_range(m.group(2))
            if hi is not None and hi > 0 and qmin is not None:
                out.append((hi, qmin, qmax, lo != hi))
    return out


def _qty_range(text: str) -> tuple[int | None, int | None]:
    m = _TIER_QTY.search(text or "")
    if not m:
        return None, None
    lo = int(m.group(2).replace(",", ""))
    if m.group(1) == ">":
        lo += 1
    hi = int(m.group(3).replace(",", "")) if m.group(3) else (None if m.group(1) else lo)
    return lo, hi


def _alibaba_moq(rec: dict[str, Any], tiers: list) -> tuple[int | None, str]:
    for key in ("moq", "moq_units", "minimum_order"):
        n = _int(rec.get(key))
        if n:
            return n, f"the parser's {key}" + (f" ({rec['moq_basis']})" if rec.get("moq_basis") else "")
    for key in ("minimum_order_as_listed", "moq_raw", "moq_text"):
        if isinstance(rec.get(key), str) and rec[key].strip():
            import executors as _ex  # the engine's one MOQ parser
            n = _ex._parse_moq(rec[key])
            if n:
                return n, f"parsed from {key} {rec[key]!r} (executors._parse_moq)"
    mins = [t[1] for t in tiers if t[1] is not None]
    if mins:
        return min(mins), "the first price tier's lower bound"
    return None, "not stated"


def _alibaba_weight_g(rec: dict[str, Any]) -> tuple[Decimal | None, str]:
    for key, factor in (("weight_kg", THOUSAND), ("gross_weight_kg", THOUSAND), ("unit_weight_kg", THOUSAND), ("weight_g", Decimal(1))):
        d = _dec(rec.get(key))
        if d is not None and d > 0:
            return d * factor, f"stated by the listing ({key})"
    for key in ("weight_text", "gross_weight_text"):
        m = _WEIGHT.search(str(rec.get(key) or ""))
        if m:
            d = Decimal(m.group(1)) * (THOUSAND if m.group(2).lower().startswith("k") else Decimal(1))
            if d > 0:
                return d, f"stated by the listing ({key} {rec[key]!r})"
    return None, "not stated"


def _off_topic(terms: list[str]) -> str:
    """Why a record the parser judged off-topic is left out — in words that hold for whatever relevance rule the parser applies."""
    searched = "; ".join(f"'{t}'" for t in terms[:3])
    return "not about this product: its title does not name the product" + (f" searched for ({searched})" if searched else "") + " (the parser's relevance rule)"


def _relevant(rec: dict[str, Any], source: str, excluded: list[dict[str, Any]], ref: Any, terms: list[str] | None = None) -> bool:
    """A record the parser judged NOT to be about the candidate (`relevant: false`) is left out and listed with why — the host side
    drops its own near misses the same way. Unjudged records stay."""
    if rec.get("relevant") is False:
        excluded.append({"source": source, "ref": ref, "why": _off_topic(terms or [])})
        return False
    return True


def _alibaba_shipping(moq: int | None, weight_g: Decimal | None, weight_from: str, per_kg: Decimal | None, min_kg: Decimal | None,
                      min_charge: Decimal | None, quote: Decimal | None, quote_qty: int | None) -> dict[str, Any]:
    """Per-unit shipping of an Alibaba offer and the rule that set it -> {cost, rule, formula, inputs, missing}.
      QUOTE       the listing's own quote for a stated quantity ("Shipping fee: $83.15 for 55 pieces"), preferred: quote ÷ quantity;
      PER_KG      the MOQ order's weight × the per-kg rate (no stated minimum reached): total ÷ MOQ = rate × unit weight;
      MIN_KG      the stated minimum chargeable weight ("with a 50kg minimum") is above the MOQ order's weight: the minimum × the rate;
      MIN_CHARGE  the total would fall below the stated minimum charge: that charge;
      per unit = the MOQ order's total ÷ MOQ (round2). A minimum cannot be spread without an MOQ: then UNKNOWN, never a guess."""
    if quote is not None and quote > 0 and quote_qty:
        inputs: dict[str, Any] = {"shipping_quote_usd": float(quote), "shipping_quote_qty": quote_qty, "moq": moq}
        total = _cents(quote * moq / quote_qty) if moq is not None else None
        if total is not None:
            inputs["moq_order_total_usd"] = float(total)
        scaled = "" if moq is None or moq == quote_qty else f" (the quote is for {quote_qty} pieces, the MOQ is {moq}: scaled to the MOQ order)"
        per = _unit4(total / moq) if total is not None else _unit4(quote / quote_qty)
        return {"cost": per, "rule": "QUOTE", "inputs": inputs, "missing": None, "moq_total": total,
                "formula": (f"the listing's own quote for {quote_qty} pieces, preferred{scaled}: "
                            + ("the MOQ order's total ÷ MOQ, to 4 decimals (× MOQ = that total)" if total is not None else
                               "shipping_quote_usd ÷ shipping_quote_qty, to 4 decimals"))}
    base: dict[str, Any] = {"shipping_per_kg_usd": _out(per_kg), "unit_weight_kg": _out(weight_g / THOUSAND if weight_g is not None else None),
                            "weight_from": weight_from, "shipping_min_kg": _out(min_kg) if min_kg else None,
                            "shipping_min_charge_usd": _out(min_charge) if min_charge is not None else None, "moq": moq}
    if per_kg is None or weight_g is None:
        return {"cost": None, "rule": UNKNOWN, "inputs": base, "formula": "no shipping quote; per-kg shipping needs the rate and the unit weight",
                "missing": [k for k, v in (("a shipping quote or a per-kg rate", per_kg), ("unit weight", weight_g)) if v is None], "moq_total": None}
    unit_kg = weight_g / THOUSAND
    if moq is None:
        if min_kg or min_charge is not None:
            return {"cost": None, "rule": UNKNOWN, "inputs": base, "missing": ["MOQ"], "moq_total": None,
                    "formula": "a minimum (weight or charge) is stated but the MOQ is not: the minimum cannot be spread per unit"}
        return {"cost": _unit4(per_kg * unit_kg), "rule": "PER_KG", "inputs": base, "missing": None, "moq_total": None,
                "formula": "shipping_per_kg_usd × unit weight kg, to 4 decimals: no minimum stated (and no MOQ to total)"}
    order_kg = unit_kg * moq
    chargeable = max(order_kg, min_kg) if min_kg else order_kg
    total = chargeable * per_kg
    rule = "MIN_KG" if min_kg and min_kg > order_kg else "PER_KG"
    if min_charge is not None and total < min_charge:
        total, rule = min_charge, "MIN_CHARGE"
    if rule == "MIN_CHARGE":
        why = f"the ${min_charge} minimum charge applies (the MOQ order's {_plain(chargeable)} kg would cost ${_cents(chargeable * per_kg)})"
    elif rule == "MIN_KG":
        why = f"the {_plain(min_kg)} kg minimum applies (the MOQ order weighs {_plain(order_kg)} kg)"
    else:
        why = f"the MOQ order's own weight, {_plain(order_kg)} kg" + (f" (≥ the {_plain(min_kg)} kg minimum)" if min_kg else "")
    return {"cost": _unit4(_cents(total) / moq), "rule": rule, "missing": None, "moq_total": _cents(total),
            "inputs": {**base, "order_kg": float(order_kg), "chargeable_kg": float(chargeable), "moq_order_total_usd": float(_cents(total))},
            "formula": ("round2(max(MOQ × unit weight kg, shipping_min_kg) × shipping_per_kg_usd, never below shipping_min_charge_usd) for the MOQ "
                        "order, ÷ MOQ to 4 decimals (× MOQ = that total): " + why)}


def _alibaba_offers(records: list[dict[str, Any]], cj_weight_g: Decimal | None, cj_weight_from: str | None,
                    rs: dict[str, Any], excluded: list[dict[str, Any]], terms: list[str] | None = None) -> list[dict[str, Any]]:
    flat = [f for f in (_flat(r) for r in records if (r.get("kind") in (None, "listing")))
            if _relevant(f, "alibaba", excluded, f.get("url") or f.get("product_id"), terms)]

    def key(rec: dict[str, Any], i: int) -> str:
        pid = str(rec.get("product_id") or rec.get("ref") or "").strip()
        return f"id:{pid}" if pid else (f"url:{_norm_url(rec.get('url'))}" if rec.get("url") else f"row:{i}")

    offers = []
    for rec in _merge(flat, key):
        currency = str(rec.get("currency") or "").strip().upper()
        tiers = _tiers(rec) if currency in ("", "USD") else []
        moq, moq_from = _alibaba_moq(rec, tiers)
        unit = basis = None
        if currency not in ("", "USD"):
            basis = {"formula": f"priced in {currency}: a price is never converted", "inputs": {"price_as_listed": rec.get("price_as_listed"),
                                                                                               "currency": currency}, "missing": ["US-dollar price"]}
        elif tiers:
            ordered = sorted(tiers, key=lambda t: (t[1] if t[1] is not None else 0))
            fits = [t for t in ordered if moq is not None and t[1] is not None and t[1] <= moq]
            tier = fits[-1] if fits else ordered[0]
            unit = tier[0]
            basis = {"formula": "the price of the tier that holds the MOQ" + (" (no tier holds the MOQ: the first tier)" if not fits else "")
                     + (" — the tier is priced as a range: its high end" if tier[3] else ""),
                     "inputs": {"moq": moq, "moq_from": moq_from, "tiers": [{"price_usd": float(t[0]), "min_qty": t[1], "max_qty": t[2]} for t in ordered]}}
        else:
            stated = next((rec[k] for k in ("price_usd", "price_max") if rec.get(k) is not None), None)
            lo, hi = _usd_range(stated if stated is not None else rec.get("price_as_listed") or rec.get("price_raw"))
            if hi is not None and hi > 0:
                unit = hi
                basis = {"formula": "the stated price (no price tiers)" + (" — a range: its high end, the price nearest the MOQ" if lo != hi else ""),
                         "inputs": {"price_as_listed": rec.get("price_as_listed") or rec.get("price_raw") or rec.get("price_usd")}}
        if unit is None and basis is None:
            basis = {"formula": "no US-dollar price stated", "inputs": {"price_as_listed": rec.get("price_as_listed")}, "missing": ["price"]}
        origin = _origin(rec.get("ships_from") or rec.get("origin")) or rs.get("alibaba_origin_default") or "CN"
        tmin, tmax = _days(rec.get("transit_days_min"), rec.get("transit_days_max"))
        _lead_min, lmax = _days(rec.get("lead_time_days_min"), rec.get("lead_time_days_max"))
        per_kg = _usd(rec.get("shipping_per_kg_usd"))
        quote, quote_qty = _usd(rec.get("shipping_quote_usd")), _int(rec.get("shipping_quote_qty"))
        weight_g, weight_from = _alibaba_weight_g(rec)
        stated_weight_g = weight_g
        if weight_g is None and cj_weight_g is not None:
            weight_g, weight_from = cj_weight_g, cj_weight_from
        # R2 #9b: the page's shipping estimate is for the country it names ("Deliver to"); a stated non-US destination is not US inbound freight
        dest = _origin(rec.get("ships_to")) if str(rec.get("ships_to") or "").strip() else None
        if dest is not None and dest != "US":
            rule = {"cost": None, "rule": UNKNOWN, "missing": ["a US inbound quote"], "moq_total": None,
                    "inputs": {"ships_to": rec.get("ships_to"), "shipping_quote_usd": _out(quote) if quote is not None else None,
                               "shipping_per_kg_usd": _out(per_kg) if per_kg is not None else None},
                    "formula": f"not used: the listing's shipping estimate is for {_clip(rec.get('ships_to'), 60)}, not the US"}
            tmin = tmax = None                                   # its transit days are for that destination too
            destination = f"{_clip(rec.get('ships_to'), 60)} — not the US: not used"
        else:
            rule = _alibaba_shipping(moq, weight_g, weight_from, per_kg, _dec(rec.get("shipping_min_kg")), _usd(rec.get("shipping_min_charge_usd")),
                                     quote, quote_qty)
            destination = "US" if dest == "US" else "destination not stated; read as US"
            rule["formula"] += f" — destination: {destination}"
        rule["inputs"]["shipping_fee_text"] = _clip(rec.get("shipping_fee_text"), 200) or None
        rule["inputs"]["destination"] = destination
        inbound = {"origin": origin, "carrier": _clip(rec.get("shipping_method"), 120) or "the listing's stated shipping", "cost": rule["cost"],
                   "days_min": tmin, "days_max": tmax, "cost_rule": rule, "destination": destination}
        capital = _cents(moq * unit) if moq is not None and unit is not None else None
        moq_inbound = rule.get("moq_total")
        pid = str(rec.get("product_id") or rec.get("ref") or "").strip()
        oid = f"alibaba:{pid}" if pid else f"alibaba:{hashlib.sha256(_norm_url(rec.get('url')).encode()).hexdigest()[:12]}"
        offers.append({"offer_id": oid, "source": "alibaba", "model": INVENTORY, "title": _clip(rec.get("title"), 300) or None,
                       "url": rec.get("url") or None, "image": None, "supplier": _clip(rec.get("supplier"), 200) or None, "unit_cost": unit,
                       "unit_basis": basis, "moq": moq, "moq_from": moq_from, "lead_time": lmax,
                       "lead_time_text": _clip(rec.get("lead_time_text"), 200) or None,
                       "shipping_fee_text": _clip(rec.get("shipping_fee_text"), 200) or None, "inbound": inbound,
                       "time_to_stock": lmax + tmax if lmax is not None and tmax is not None else None,
                       "moq_inbound": moq_inbound,
                       "cash_to_first_stock": capital + moq_inbound if capital is not None and moq_inbound is not None else None,
                       "shipping": [], "us_stock_confirmed": None, "suggested_retail": None, "weight_g": weight_g,
                       "stated_weight_g": stated_weight_g, "origin_stated": bool(rec.get("ships_from") or rec.get("origin"))})
    return offers


def _last_miles(cj: list[dict[str, Any]], settings: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """The ways to ship ONE order from the seller's own US stock: (every CJ US→US quote of the candidate's CJ products — a proxy, each
    labelled with its CJ product and weight; each channel takes the cheapest whose days pass its rule, else the cheapest overall, exactly as
    a dropship offer picks among its options —, the owner's settings last_mile_usd / last_mile_days or None)."""
    out = []
    for o in cj:
        weight = f"{_plain(o['weight_g'])} g" if o["weight_g"] is not None else "weight not stated"
        for s in o["shipping"]:
            if s["origin"] == "US":
                out.append({"origin": "US", "carrier": s["carrier"], "cost": s["cost"], "days_min": s["days_min"], "days_max": s["days_max"],
                            "days_unit": s.get("days_unit"), "basis": "last_mile", "source": f"CJ US→US quote for {o['title'] or o['offer_id']}, {weight}",
                            "source_rule": "LAST_MILE_CJ_US_QUOTE", "ref": o["offer_id"], "ref_weight_g": o["weight_g"]})
    owner = None
    if settings["last_mile_usd"] is not None or settings["last_mile_days"] is not None:
        days = settings["last_mile_days"]
        owner = {"origin": "US", "carrier": "your own shipping", "cost": settings["last_mile_usd"], "days_min": days, "days_max": days,
                 "days_unit": None, "basis": "last_mile", "source": "the owner's settings last_mile_usd / last_mile_days",
                 "source_rule": "LAST_MILE_OWNER_SETTING", "ref": None, "ref_weight_g": None}
    return out, owner


def _last_mile_for(offer: dict[str, Any], cj_options: list[dict[str, Any]], owner: dict[str, Any] | None,
                   tolerance: Decimal) -> tuple[list[dict[str, Any]], str | None]:
    """An inventory offer's last-mile options and, when it has none, why. A CJ US→US quote stands in for shipping THIS item only when the
    offer's own unit weight is unknown or at most `tolerance` heavier than the CJ product the quote was for (R2 #9c); the owner's own
    last mile is the fallback; else none — UNKNOWN, never guessed."""
    w = offer.get("stated_weight_g")
    fits = [o for o in cj_options if w is None or (o["ref_weight_g"] is not None and w <= o["ref_weight_g"] * (1 + tolerance))]
    if fits:
        return [dict(o) for o in fits], None
    if owner is not None:
        return [dict(owner)], None
    if not cj_options:
        return [], "no CJ US→US quote for this product and no owner setting (settings last_mile_usd / last_mile_days)"
    refs = sorted({(o["ref_weight_g"], o["source"]) for o in cj_options}, key=lambda t: (t[0] is None, t[0] or 0, t[1]))
    said = "; ".join(f"{_plain(rw)} g" if rw is not None else "weight not stated" for rw, _ in refs)
    return [], (f"the offer weighs {_plain(w)} g a unit, more than {_plain(tolerance * 100)} % above the weight of every CJ US→US quote ({said}): "
                "that price is not this item's, and no owner setting (settings last_mile_usd / last_mile_days) stands in")


def _offers(cj_block: dict[str, Any], alibaba: list[dict[str, Any]], rs: dict[str, Any], cj_moq: int, book: _Book,
            excluded: list[dict[str, Any]], settings: dict[str, Any], terms: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """(internal offers, their JSON form) — receipts for every number of the JSON form."""
    cj = _cj_offers(cj_block, cj_moq)
    weights = [(o["weight_g"], o["offer_id"]) for o in cj if o["weight_g"] is not None]
    cj_w, cj_from = (max(weights, key=lambda t: (t[0], str(t[1]))) if weights else (None, None))
    cj_last, owner_last = _last_miles(cj, settings)
    tolerance = _dec(rs.get("last_mile_weight_tolerance"))
    tolerance = tolerance if tolerance is not None else Decimal("0.25")
    internal = cj + _alibaba_offers(alibaba, cj_w, f"CJ-known weight (the heaviest matched CJ product, {cj_from}: conservative)" if cj_w else None, rs,
                                    excluded, terms)
    for o in internal:
        if o["model"] == INVENTORY:
            o["shipping"], o["last_mile_note"] = _last_mile_for(o, cj_last, owner_last, tolerance)
    seen: set[str] = set()
    kept = []
    for i, o in enumerate(internal):
        oid = o["offer_id"] or f"{o['source']}:row{i}"
        if oid in seen:
            continue
        seen.add(oid)
        o["offer_id"] = oid
        kept.append(o)
    out = []
    for i, o in enumerate(kept):
        p = f"offers[{i}]"
        ub = o["unit_basis"]
        book.add(f"{p}.unit_cost_usd", ub["formula"], ub["inputs"], _out(o["unit_cost"]), missing=ub.get("missing"))
        if o["source"] == "cj":
            book.add(f"{p}.moq", "CJ dropships single units: the engine's policy supplier.moq_default_by_channel.cjdropshipping",
                     {"policy": "supplier.moq_default_by_channel.cjdropshipping"}, o["moq"])
        else:
            book.add(f"{p}.moq", "the listing's minimum order", {"from": o["moq_from"]}, _out(o["moq"]),
                     missing=["minimum order"] if o["moq"] is None else None)
        cap = o["moq"] * o["unit_cost"] if o["moq"] is not None and o["unit_cost"] is not None else None
        o["moq_capital"] = _cents(cap) if cap is not None else None
        book.add(f"{p}.moq_capital_usd", "round2(MOQ × unit cost)", {"moq": _out(o["moq"]), "unit_cost_usd": _out(o["unit_cost"])},
                 _out(o["moq_capital"]), missing=[k for k, v in (("moq", o["moq"]), ("unit cost", o["unit_cost"])) if v is None] or None)
        lead_src = "lead_time_days_max (the listing's lead-time table)" if o["source"] == "alibaba" else "CJ states no lead time"
        book.add(f"{p}.lead_time_days", "observed" if o["lead_time"] is not None else "observed: not stated", {"source": o["source"], "field": lead_src},
                 _out(o["lead_time"]), missing=["lead time"] if o["lead_time"] is None else None)
        ship_out = []
        for j, s in enumerate(o["shipping"]):
            q = f"{p}.shipping[{j}]"
            if s["basis"] == "cj_quote":
                book.add(f"{q}.cost_usd", "observed: CJ's freight quote for one unit" if s["cost"] is not None else "observed: not stated",
                         {"source": "CJ freight quote", "field": "cost_usd"}, _out(s["cost"]), rule="CJ_QUOTE",
                         missing=["cost_usd"] if s["cost"] is None else None)
                src = "CJ freight quote"
            else:                           # an inventory offer's last mile from the seller's US stock
                book.add(f"{q}.cost_usd", f"the last mile per order from your US stock: {s['source']}", {"source": s["source"], "ref_offer_id": s["ref"],
                         "carrier": s["carrier"]}, _out(s["cost"]), rule=s["source_rule"], missing=["last-mile cost"] if s["cost"] is None else None)
                src = s["source"]
            book.observed(f"{q}.days_min", s["days_min"], src, "days_min")
            book.observed(f"{q}.days_max", s["days_max"], src, "days_max")
            row = {"origin": s["origin"], "carrier": s["carrier"], "cost_usd": _out(s["cost"]), "days_min": _out(s["days_min"]),
                   "days_max": _out(s["days_max"])}
            if s["basis"] == "last_mile":
                row["source"] = s["source"]
            ship_out.append(row)
        item = {"offer_id": o["offer_id"], "source": o["source"], "model": o["model"], "title": o["title"], "url": o["url"], "supplier": o["supplier"],
                "unit_cost_usd": _out(o["unit_cost"]), "moq": _out(o["moq"]), "moq_capital_usd": _out(o["moq_capital"]), "shipping": ship_out,
                "lead_time_days": _out(o["lead_time"])}
        if o["model"] == INVENTORY:
            ib, r = o["inbound"], o["inbound"]["cost_rule"]
            book.add(f"{p}.inbound.cost_usd", r["formula"], r["inputs"], _out(ib["cost"]), rule=r["rule"], missing=r["missing"])
            book.observed(f"{p}.inbound.days_min", ib["days_min"], "the listing's transit estimate", "transit_days_min")
            book.observed(f"{p}.inbound.days_max", ib["days_max"], "the listing's transit estimate", "transit_days_max")
            item["inbound"] = {"origin": ib["origin"], "carrier": ib["carrier"], "cost_usd": _out(ib["cost"]), "days_min": _out(ib["days_min"]),
                               "days_max": _out(ib["days_max"]), "rule": r["rule"], "destination": ib["destination"]}
            item["moq_inbound_usd"] = book.add(f"{p}.moq_inbound_usd", "the inbound freight for the MOQ order: " + r["formula"],
                                               {"rule": r["rule"], "moq": _out(o["moq"]), **{k: v for k, v in r["inputs"].items() if k in (
                                                   "moq_order_total_usd", "shipping_quote_usd", "shipping_quote_qty", "chargeable_kg", "shipping_per_kg_usd",
                                                   "shipping_min_charge_usd", "destination")}},
                                               _out(o["moq_inbound"]), missing=(["inbound freight for the MOQ order"] if o["moq_inbound"] is None else None))
            item["cash_to_first_stock_usd"] = book.add(f"{p}.cash_to_first_stock_usd", "MOQ capital (goods) + the inbound freight for the MOQ order: "
                                                       "the cash out before the first stock can sell",
                                                       {"moq_capital_usd": _out(o["moq_capital"]), "moq_inbound_usd": _out(o["moq_inbound"])},
                                                       _out(o["cash_to_first_stock"]),
                                                       missing=[k for k, v in (("MOQ capital", o["moq_capital"]), ("inbound for the MOQ order", o["moq_inbound"]))
                                                                if v is None] or None)
            if o.get("last_mile_note"):
                item["last_mile_note"] = o["last_mile_note"]
            item["time_to_stock_days"] = book.add(f"{p}.time_to_stock_days", "lead time + transit, once: the days until the first stock reaches you",
                                                  {"lead_time_days": _out(o["lead_time"]), "transit_days_max": _out(ib["days_max"])}, _out(o["time_to_stock"]),
                                                  missing=[k for k, v in (("lead time", o["lead_time"]), ("transit days", ib["days_max"])) if v is None] or None)
        if o["source"] == "cj":
            item["image"] = o["image"]
            item["us_stock_confirmed"] = o["us_stock_confirmed"]
            item["suggested_retail_usd"] = book.observed(f"{p}.suggested_retail_usd", o["suggested_retail"], "CJ product (reference only, never used as a price)",
                                                          "suggested_retail_usd")
        else:
            item["lead_time_text"] = o["lead_time_text"]
            item["shipping_fee_text"] = o["shipping_fee_text"]
        out.append(item)
    return kept, out


# -------------------------------------------------------------------------------------------------------------- market --
def _stats(values: list[Decimal]) -> dict[str, Any]:
    vals = sorted(values)
    n = len(vals)
    if not n:
        return {"n": 0, "median": None, "min": None, "max": None}
    mid = n // 2
    median = vals[mid] if n % 2 else _cents((vals[mid - 1] + vals[mid]) / 2)
    return {"n": n, "median": median, "min": vals[0], "max": vals[-1]}


def _shipping_text(text: Any) -> Decimal | None:
    """A listing's shipping line: "Free shipping" / "Free delivery" = 0, "+$4.99 shipping" = 4.99, anything else = not stated."""
    if not isinstance(text, str) or not text.strip():
        return None
    if _FREE.search(text):
        return Decimal(0)
    return _usd(text) if re.search(r"\$|USD", text) else None


def _comps(amazon: list[dict[str, Any]], ebay_api: dict[str, Any], ebay_reach: list[dict[str, Any]],
           terms: list[str] | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """(amazon comps, ebay comps, excluded): each comp {title, url, price, shipping (None = not stated), total, source}."""
    excluded: list[dict[str, Any]] = []
    amz = []
    recs = [f for f in (_flat(r) for r in amazon if r.get("kind") in (None, "listing")) if _relevant(f, "amazon", excluded, f.get("asin") or f.get("url"), terms)]
    for rec in _merge(recs, lambda r, i: f"asin:{r['asin']}" if r.get("asin") else (f"url:{_norm_url(r.get('url'))}" if r.get("url") else f"row:{i}")):
        price = _usd(rec.get("price_usd"))
        if price is None or price <= 0:
            excluded.append({"source": "amazon", "ref": rec.get("asin") or rec.get("url"), "why": "no US-dollar price"})
            continue
        ship = _usd(rec.get("shipping_usd"))
        amz.append({"title": _clip(rec.get("title"), 200) or None, "url": rec.get("url"), "price": price, "shipping": ship,
                    "total": price + (ship or 0), "source": "amazon", "ref": rec.get("asin") or rec.get("url")})
    eb = []
    seen: set[str] = set()

    def ebay_key(url: Any) -> str:
        m = _EBAY_ITEM.search(str(url or ""))
        return f"item:{m.group(1)}" if m else f"url:{_norm_url(url)}"

    for rec in (ebay_api.get("listings") or []):
        if not isinstance(rec, dict):
            continue
        price = _usd(rec.get("price_usd"))
        k = ebay_key(rec.get("url"))
        if price is None or price <= 0:
            excluded.append({"source": "ebay_api", "ref": rec.get("url"), "why": "no US-dollar price"})
            continue
        if k in seen:
            continue
        seen.add(k)
        ship = _usd(rec.get("shipping_usd"))
        eb.append({"title": _clip(rec.get("title"), 200) or None, "url": rec.get("url"), "price": price, "shipping": ship,
                   "total": price + (ship or 0), "source": "ebay_api", "ref": k})
    for rec in [_flat(r) for r in ebay_reach if r.get("kind") in (None, "listing")]:
        if not _relevant(rec, "ebay_reach", excluded, rec.get("url"), terms):
            continue
        k = ebay_key(rec.get("url"))
        cur = str(rec.get("currency") or "").strip().upper()
        if rec.get("us_listing") is False:
            excluded.append({"source": "ebay_reach", "ref": rec.get("url"), "why": "not a US eBay listing"})
            continue
        raw = rec.get("price_usd") if rec.get("price_usd") is not None else rec.get("price")
        if cur and cur != "USD":
            excluded.append({"source": "ebay_reach", "ref": rec.get("url"), "why": f"priced in {cur}, not US dollars"})
            continue
        if not cur and not isinstance(raw, str) and rec.get("price_usd") is None and rec.get("us_listing") is not True:
            excluded.append({"source": "ebay_reach", "ref": rec.get("url"), "why": "currency not stated"})
            continue
        price = _usd(raw)
        if price is None or price <= 0:
            excluded.append({"source": "ebay_reach", "ref": rec.get("url"), "why": "no US-dollar price"})
            continue
        if k in seen:
            continue
        seen.add(k)
        ship = _usd(rec.get("shipping_usd")) if rec.get("shipping_usd") is not None else _shipping_text(rec.get("shipping_text"))
        eb.append({"title": _clip(rec.get("title"), 200) or None, "url": rec.get("url"), "price": price, "shipping": ship,
                   "total": price + (ship or 0), "source": "ebay_reach", "ref": k})
    return amz, eb, excluded


def _market(amazon: list[dict[str, Any]], ebay_api: dict[str, Any], ebay_reach: list[dict[str, Any]], rs: dict[str, Any],
            book: _Book, terms: list[str] | None = None) -> tuple[dict[str, Any], Decimal | None]:
    amz, eb, excluded = _comps(amazon, ebay_api, ebay_reach, terms)
    out: dict[str, Any] = {}
    for name, comps in (("amazon", amz), ("ebay", eb)):
        comps = sorted(comps, key=lambda c: (c["total"], str(c["url"] or "")))
        st = _stats([c["total"] for c in comps])
        values = [float(c["total"]) for c in comps]
        block: dict[str, Any] = {"n": book.add(f"market.{name}.n", "count of matched listings with a US-dollar price (one per listing)",
                                               {"listings": [c["ref"] for c in comps]}, st["n"])}
        for stat, formula in (("median", "median of price + shipping where stated (an even count: the mean of the middle two, round2)"),
                              ("min", "lowest price + shipping where stated"), ("max", "highest price + shipping where stated")):
            block[stat] = book.add(f"market.{name}.{stat}", formula, {"values": values}, _out(st[stat]), missing=["matched listings"] if not comps else None)
        rows = []
        for k, c in enumerate(comps):
            q = f"market.{name}.comps[{k}]"
            book.observed(f"{q}.price_usd", c["price"], c["source"], "price_usd")
            book.observed(f"{q}.shipping_usd", c["shipping"], c["source"], "shipping (not stated = price only)")
            book.add(f"{q}.total_usd", "price + shipping where stated", {"price_usd": float(c["price"]), "shipping_usd": _out(c["shipping"])}, _out(c["total"]))
            rows.append({"title": c["title"], "url": c["url"], "source": c["source"], "price_usd": _out(c["price"]), "shipping_usd": _out(c["shipping"]),
                         "total_usd": _out(c["total"])})
        block["comps"] = rows
        out[name] = block
    floor = int(rs.get("min_comps_for_reference") or 3)
    a = _stats([c["total"] for c in amz])
    pooled = _stats([c["total"] for c in amz + eb])
    if a["n"] >= floor:
        ref, basis = a["median"], "AMAZON_MEDIAN"
        formula = f"the Amazon median (Amazon n = {a['n']} ≥ {floor})"
    elif pooled["n"] >= floor:
        ref, basis = pooled["median"], "POOLED_MEDIAN"
        formula = f"the pooled Amazon + eBay median (Amazon n = {a['n']} < {floor}; pooled n = {pooled['n']} ≥ {floor})"
    else:
        ref, basis = None, UNKNOWN
        formula = f"UNKNOWN: fewer than {floor} matched listings (Amazon n = {a['n']}, pooled n = {pooled['n']})"
    out["reference_price_usd"] = book.add("market.reference_price_usd", formula,
                                          {"amazon_values": [float(c["total"]) for c in sorted(amz, key=lambda c: c["total"])],
                                           "ebay_values": [float(c["total"]) for c in sorted(eb, key=lambda c: c["total"])],
                                           "min_comps_for_reference": floor}, _out(ref),
                                          missing=[f"at least {floor} matched listings"] if ref is None else None)
    out["basis"] = basis
    out["basis_note"] = "CJ's suggested retail is shown on CJ offers as reference only and never used as a price"
    out["excluded"] = excluded
    return out, ref


# -------------------------------------------------------------------------------------------------------------- demand --
def _subreddit(rec: dict[str, Any]) -> str | None:
    name = str(rec.get("subreddit") or "").strip()
    if not name:
        m = re.search(r"reddit\.com/r/([A-Za-z0-9_]+)", str(rec.get("url") or ""))
        name = m.group(1) if m else ""
    name = re.sub(r"^/?r/", "", name).strip("/ ")
    return f"r/{name}" if name else None


def _reddit(records: list[dict[str, Any]], rs: dict[str, Any], book: _Book, terms: list[str] | None = None) -> dict[str, Any]:
    terms = terms or []
    threads, left_out = [], {}
    for r in records:
        if r.get("kind") not in (None, "thread"):
            continue
        if r.get("relevant") is False:              # C4: the parser's own per-record judgement; shown with its title and date, never silently
            k = _norm_url(r.get("url")) if r.get("url") else f"row:{len(left_out)}"
            if k not in left_out:
                left_out[k] = {"source": "reddit", "ref": r.get("url"), "title": _clip(r.get("title"), 200) or None,
                               "date": _iso_date(r.get("published_at")), "subreddit": _subreddit(r),
                               "why": _off_topic(terms)}
            continue
        threads.append(r)
    threads_excluded = sorted(left_out.values(), key=lambda x: (x["date"] is None, -int((x["date"] or "0").replace("-", "")), str(x["title"] or ""),
                                                                str(x["ref"] or "")))
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for i, t in enumerate(threads):
        k = _norm_url(t.get("url")) if t.get("url") else f"row:{i}"
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(t)
    subs: dict[str, str] = {}
    dates: list[str] = []
    comments: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for k in order:
        group = groups[k]
        sub = next((s for s in (_subreddit(t) for t in group) if s), None)
        if sub:
            subs.setdefault(sub.lower(), sub)
        url = next((t.get("url") for t in group if t.get("url")), None)
        for t in group:
            d = _iso_date(t.get("published_at"))
            if d:
                dates.append(d)
            for c in t.get("comments") or []:
                if not isinstance(c, dict):
                    continue
                text = _clip(c.get("text"), int(rs.get("reddit_comment_chars") or 300))
                cd, pts = _iso_date(c.get("date")), _points(c.get("points"))
                key = (k, cd, pts, text)
                if key in seen or not text:
                    continue
                seen.add(key)
                if cd:
                    dates.append(cd)
                comments.append({"date": cd, "points": pts, "subreddit": sub, "text": text, "url": url})
    comments.sort(key=lambda c: (c["points"] is None, -(c["points"] or 0), c["date"] is None, -int((c["date"] or "0").replace("-", "")),
                                 str(c["url"] or ""), c["text"]))
    top = comments[: int(rs.get("reddit_comments_max") or 5)]
    n_threads, n_comments = len(order), len(comments)
    newest = max(dates) if dates else None
    subreddits = sorted(subs.values(), key=str.lower)
    out: dict[str, Any] = {}
    out["threads"] = book.add("demand.reddit.threads", "count of distinct thread URLs", {"urls": [k for k in order]}, n_threads)
    out["subreddits"] = subreddits
    out["newest"] = book.add("demand.reddit.newest", "the newest date among the threads and their comments", {"dates": sorted(set(dates))},
                             newest if newest else UNKNOWN, missing=["a dated thread or comment"] if not newest else None)
    out["comments_total"] = book.add("demand.reddit.comments_total", "count of distinct comments read across the threads",
                                     {"threads": n_threads}, n_comments)
    rows = []
    for i, c in enumerate(top):
        book.add(f"demand.reddit.comments[{i}].points", "observed" if c["points"] is not None else "observed: not stated",
                 {"source": "reddit", "url": c["url"], "date": c["date"]}, _out(c["points"]), missing=["points"] if c["points"] is None else None)
        rows.append({"date": c["date"], "points": _out(c["points"]), "subreddit": c["subreddit"], "text": c["text"], "url": c["url"]})
    out["comments"] = rows
    if not n_threads:
        summary = "No Reddit threads were collected."
    else:
        summary = _plural(n_threads, "thread")
        if subreddits:
            summary += f" in {_plural(len(subreddits), 'subreddit')}"
        summary += f", {_plural(n_comments, 'comment')} read"
        if newest:
            summary += f", newest {newest}"
        best = next((c["points"] for c in comments if c["points"] is not None), None)
        summary += (f"; the most-upvoted comment has {_plural(best, 'point')}." if best is not None else
                    "; no comment shows its points." if n_comments else ".")
    out["summary"] = book.add("demand.reddit.summary", "counts only, no judgment: threads, subreddits, comments, newest date, top comment points",
                              {"threads": n_threads, "subreddits": len(subreddits), "comments": n_comments, "newest": newest,
                               "top_points": next((c["points"] for c in comments if c["points"] is not None), None)}, summary)
    return {"summary": out["summary"], "threads": out["threads"], "subreddits": out["subreddits"], "newest": out["newest"],
            "comments_total": out["comments_total"], "comments": out["comments"], "threads_excluded": threads_excluded}


def _amazon_demand(records: list[dict[str, Any]], book: _Book) -> dict[str, Any]:
    recs = _merge([_flat(r) for r in records if r.get("kind") in (None, "listing") and r.get("relevant") is not False],
                  lambda r, i: f"asin:{r['asin']}" if r.get("asin") else (f"url:{_norm_url(r.get('url'))}" if r.get("url") else f"row:{i}"))
    bsr, bought, ratings = [], [], []
    for r in recs:
        ref = r.get("asin") or r.get("url")
        b = r.get("bsr")
        rank = _count(b.get("rank")) if isinstance(b, dict) else _count(b)
        if rank:
            bsr.append((rank, str((b or {}).get("category") or "") if isinstance(b, dict) else "", str(ref or "")))
        n = _count(r.get("bought_past_month"))
        if n is not None:
            bought.append((n, str(ref or "")))
        n = _count(r.get("ratings_count"))
        if n is not None:
            ratings.append((n, str(ref or "")))
    best = min(bsr, key=lambda t: (t[0], t[1], t[2])) if bsr else None
    top_b = max(bought, key=lambda t: (t[0], t[1])) if bought else None
    top_r = max(ratings, key=lambda t: (t[0], t[1])) if ratings else None
    out = {"listings": book.add("demand.amazon.listings", "count of distinct matched Amazon listings", {"refs": [r.get("asin") or r.get("url") for r in recs]}, len(recs))}
    out["bsr_best"] = book.add("demand.amazon.bsr_best", "the best (lowest) best-sellers rank among the matched listings",
                               {"ranks": [{"rank": t[0], "category": t[1] or None, "ref": t[2]} for t in sorted(bsr)]}, best[0] if best else UNKNOWN,
                               missing=["a best-sellers rank"] if not best else None)
    out["bsr_best_category"] = (best[1] or None) if best else None
    out["bsr_best_ref"] = best[2] if best else None
    out["bought_past_month_max"] = book.add("demand.amazon.bought_past_month_max", "the highest \"bought in past month\" among the matched listings",
                                            {"values": [{"value": t[0], "ref": t[1]} for t in sorted(bought)]}, top_b[0] if top_b else UNKNOWN,
                                            missing=["bought in past month"] if not top_b else None)
    out["ratings_count_max"] = book.add("demand.amazon.ratings_count_max", "the highest ratings count among the matched listings",
                                        {"values": [{"value": t[0], "ref": t[1]} for t in sorted(ratings)]}, top_r[0] if top_r else UNKNOWN,
                                        missing=["ratings count"] if not top_r else None)
    return out


# ------------------------------------------------------------------------------------------------------------ delivery --
def _option_days(opt: dict[str, Any]) -> tuple[int | None, str]:
    """(the quote's max days — the carrier's days, handling comes on top —, how they read)."""
    if opt["days_max"] is None:
        return None, ("ships from your US stock, but the last mile states no days" if opt["basis"] == "last_mile" else "the quote states no delivery days")
    span = f"{opt['days_min']}-{opt['days_max']}" if opt["days_min"] is not None and opt["days_min"] != opt["days_max"] else f"{opt['days_max']}"
    unit = f" {opt['days_unit']}" if opt.get("days_unit") in ("business", "calendar") else ""
    if opt["basis"] == "last_mile":
        return opt["days_max"], f"ships from your US stock: the last mile is {span}{unit} days by {opt['carrier']} ({opt['source']})"
    return opt["days_max"], f"{opt['carrier'] or 'CJ'} quotes {span}{unit} days from {opt['origin']}"


def _calendar_days_max(days: int) -> int:
    """The most calendar days `days` business days can span: a run that starts on a weekend (5 -> 7, 6 -> 10)."""
    return days + 2 * -(-days // 5) if days > 0 else 0


def _day_counts(opt: dict[str, Any], n: int, read_as: str) -> tuple[int, int, str]:
    """(the most business days, the most calendar days) the quote's `n` days can be, and the unit they were read in: a quote that says
    "business" (C2 `days_unit`) is compared to business-day rules directly and spans its worst week for calendar rules; one that says
    "calendar" — or neither, read as policies `supplier_days_read_as` — holds at most its worst week's business days."""
    unit = opt.get("days_unit") if opt.get("days_unit") in ("business", "calendar") else read_as
    if unit == "business":
        return n, _calendar_days_max(n), "business"
    return _business_days_max(n, "calendar"), n, "calendar"


def _stock_note(offer: dict[str, Any]) -> str:
    """An inventory offer's precondition (contract C5), in the words the report prints: "requires holding US stock: first stock in N days,
    cash $7,737.00 before first stock (goods $2,200.00 + inbound $5,537.00)"."""
    tts, cap, inb, cash = offer.get("time_to_stock"), offer.get("moq_capital"), offer.get("moq_inbound"), offer.get("cash_to_first_stock")
    first = f"first stock in {tts} days" if tts is not None else "first stock time UNKNOWN"
    money = (lambda d: f"${d:,.2f}" if d is not None else "UNKNOWN")
    return (f"requires holding US stock: {first}, cash {money(cash)} before first stock (goods {money(cap)} + inbound {money(inb)})")


def _price_text(d: Decimal) -> str:
    """A stated price as people write it: cents when it has no more ($11.00, $0.17), its own precision when it has ($0.035)."""
    return f"${d:,.2f}" if d == _cents(d) else f"${format(d.normalize(), 'f')}"


def _stock_detail(offer: dict[str, Any]) -> str:
    ib = offer["inbound"]
    unit = _price_text(offer["unit_cost"]) if offer["unit_cost"] is not None else "an UNKNOWN unit cost"
    lead = f"lead time {offer['lead_time']} days" if offer["lead_time"] is not None else "lead time not stated"
    transit = f"transit {ib['days_max']} days" if ib["days_max"] is not None else "transit not stated"
    return (f"MOQ {offer['moq'] if offer['moq'] is not None else 'UNKNOWN'} × {unit}; {lead} + {transit} from "
            f"{_ORIGIN_NAMES.get(ib['origin'], ib['origin'])}, once")


def _days_word(n: int) -> str:
    return f"{n} business day{'' if n == 1 else 's'}"


def _evaluate(cid: str, ch: dict[str, Any], opt: dict[str, Any], offer: dict[str, Any], rs: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """One shipping option against one channel's delivery rule. Every clock that starts at the order counts the seller's handling
    first: H = settings handling_business_days (policies default 1) business days to the first carrier scan, then the carrier's days."""
    rule = ch["delivery"]
    read_as = str(rs.get("supplier_days_read_as") or "calendar")
    h = settings["handling_business_days"]
    origin = opt["origin"] or UNKNOWN
    n, how = _option_days(opt)
    b, cal, unit = _day_counts(opt, n, read_as) if n is not None else (None, None, None)
    where = _ORIGIN_NAMES.get(origin, origin)
    handling = f"with {_days_word(h)} of handling (setting handling_business_days)"
    notes: list[str] = []
    cautions: list[str] = []
    extra: dict[str, Any] = {}
    kind = rule["kind"]
    if kind == "us_local_only":
        hmax, dmax = rule["max_handling_business_days"], rule["max_delivery_business_days"]
        if origin not in (rule.get("origins") or ["US"]):
            verdict = FAIL
            notes.append(f"ships from {where}: a TikTok Shop US local account ships US domestic orders only (local to local); "
                         f"the rule is first carrier scan ≤ {hmax} and delivered ≤ {dmax} business days from the order, from a US warehouse")
        elif n is None:
            verdict = UNKNOWN
            notes.append(f"ships from {where} but {how}: cannot check delivered ≤ {dmax} business days")
        else:
            verdict = PASS if h <= hmax and b + h <= dmax else FAIL
            notes.append(f"{how}; {handling}: {_business_sum(n, b, h, dmax, unit)}; first carrier scan after {_days_word(h)} "
                         f"{'≤' if h <= hmax else '>'} {hmax}")
            notes.append(f"custom handling ({rule['custom_handling_business_days'][0]}-{rule['custom_handling_business_days'][1]} business days) "
                         f"would instead allow delivered ≤ handling + {rule['custom_handling_extra_delivery_business_days']}")
    elif kind == "max_days":
        limit = rule["max_delivery_days"]
        wh = rule.get("overseas_warehouse") or {}
        if n is None:
            verdict = UNKNOWN
            notes.append(f"{how}: cannot check delivered ≤ {limit} days")
        elif cid == "tiktok_cross_border" and origin == "US" and wh:
            # stock in a US (overseas) warehouse: the cross-border rules hold it to the US clock — a verdict, not a note
            whh, whd = wh["max_handling_business_days"], wh["max_delivery_business_days"]
            verdict = PASS if h <= whh and b + h <= whd else FAIL
            notes.append(f"{how}; stock in a US (overseas) warehouse: TikTok's cross-border rules ask first carrier scan ≤ {whh} and delivered ≤ "
                         f"{whd} business days; {handling}: {_business_sum(n, b, h, whd, unit)}; first scan after {_days_word(h)} {'≤' if h <= whh else '>'} {whh}")
        else:
            h_cal = _calendar_days_max(h)            # the handling's business days on the calendar: worst week (an order on a Friday is scanned on Monday)
            total = cal + h_cal
            ok_scan = True
            if cid == "tiktok_cross_border":
                ok_scan = h_cal <= rule["max_in_transit_calendar_days"]
            verdict = rule["over"] if total > limit or not ok_scan else PASS
            span = f"{n} {unit} days" + (f" (at most {cal} calendar days)" if unit == "business" else "")
            notes.append(f"{how}; {handling}, which can take up to {h_cal} calendar day{'' if h_cal == 1 else 's'} (an order on a Friday is scanned "
                         f"on Monday): {span} + {h_cal} = up to {total} days {'>' if total > limit else '≤'} {limit}")
            if cid == "tiktok_cross_border":
                notes.append(f"in transit (first carrier scan) after up to {h_cal} calendar days {'≤' if ok_scan else '>'} "
                             f"{rule['max_in_transit_calendar_days']}")
            if rule.get("ftc_ship_within_days"):
                notes.append(f"state the delivery window honestly (FTC: ship within the stated time, or within {rule['ftc_ship_within_days']} days "
                             "when none is stated)")
            if rule.get("basis"):
                notes.append(f"threshold: {rule['basis']}")
        if origin in (rule.get("prime_fail_origins") or []):
            notes.append(f"Prime: FAIL — Seller Fulfilled Prime cannot be met shipping from {where}")
            extra["prime"] = FAIL
    else:  # honest_handling (eBay)
        if n is None:
            verdict = UNKNOWN
            notes.append(f"{how}: set the handling time and delivery estimate from a real quote before listing")
            extra["badge_eligible"] = None
        else:
            verdict = PASS
            hb, db = rule["badge_max_handling_business_days"], rule["badge_max_delivery_business_days"]
            badge = h <= hb and b + h <= db
            extra["badge_eligible"] = badge
            notes.append(f"allowed with an honest handling time ({_days_word(h)}, setting handling_business_days); {how}; free-shipping badge "
                         + ("possible" if badge else "not eligible") + f": it needs handling ≤ {hb} ({h} {'≤' if h <= hb else '>'} {hb}) and delivered ≤ "
                         f"{db} business days ({b} + {h} = {b + h} {'≤' if b + h <= db else '>'} {db})")
        if origin not in ("US", UNKNOWN):
            notes.append(f"state the item location as {where} (eBay item location policy)")
    if offer["source"] == "cj" and origin == "US" and offer.get("us_stock_confirmed") is not True:
        cautions.append(US_STOCK_UNCONFIRMED)
        notes.append("CAUTION: CJ quoted freight from a US warehouse but did not confirm US stock (a US quote does not prove US stock): "
                     "confirm the US warehouse holds it before listing")
    if offer["model"] == INVENTORY:
        cautions.append(REQUIRES_US_STOCK)
        notes.append(f"{_stock_note(offer)} — {_stock_detail(offer)}")
    reason = f"{verdict}: " + "; ".join(notes) + "."
    return {"verdict": verdict, "reason": reason, "origin": origin, "carrier": opt["carrier"], "days": n, "business_days": b,
            "handling": h, "cautions": cautions, **extra}


def _business_sum(n: int, b: int, h: int, limit: int, unit: str) -> str:
    """The business-day sum a rule checks, said plainly: handling + the carrier's days (read as calendar days: the most business days
    they can hold; the business-day reading too when it differs)."""
    ok = b + h <= limit
    if unit == "business" or b == n:
        return f"{b} + {h} = up to {b + h} business days {'≤' if ok else '>'} {limit}"
    alt = n + h
    return (f"read as calendar days {n} days hold at most {b} business days: {b} + {h} = up to {b + h} {'≤' if ok else '>'} {limit}"
            + (f" (if the supplier means business days, {n} + {h} = {alt} > {limit} fails)" if ok and alt > limit else ""))


# ------------------------------------------------------------------------------------------------------------- channels --
def _fees(ch: dict[str, Any], price: Decimal, settings: dict[str, Any], rate_pct: Any = None) -> tuple[Decimal, str, dict[str, Any]]:
    fee = ch["fee"]
    kind = fee["kind"]
    rate = Decimal(str(rate_pct if rate_pct is not None else fee["rate_pct"]))
    pct = price * rate / HUNDRED
    base = {"price_usd": float(price), "shipping_charged_usd": 0.0, "rate_pct": float(rate)}
    if kind == "percent":
        return _cents(pct), f"round2({rate}% × (price + shipping charged)); free shipping to the buyer: shipping charged = 0", base
    if kind == "percent_fixed_plan":
        orders = settings["shopify_monthly_orders"]
        plan = Decimal(str(fee["plan_monthly_usd"]))
        fixed = Decimal(str(fee["fixed_usd"]))
        total = pct + fixed + plan / Decimal(orders)
        return (_cents(total), f"round2({rate}% × (price + shipping charged) + ${fixed} + ${plan} {fee.get('plan', '')} plan ÷ {orders} orders a month)",
                {**base, "fixed_usd": float(fixed), "plan_monthly_usd": float(plan), "monthly_orders": orders})
    if kind == "percent_per_order":
        per = None
        for tier in fee["per_order"]:
            cap = tier.get("max_order_usd")
            if cap is None or price <= Decimal(str(cap)):
                per = Decimal(str(tier["fee_usd"]))
                break
        tiers_txt = " / ".join((f"${Decimal(str(t['fee_usd'])):.2f} when the order is ≤ ${Decimal(str(t['max_order_usd'])):.2f}" if t.get("max_order_usd") is not None
                                else f"${Decimal(str(t['fee_usd'])):.2f} above") for t in fee["per_order"])
        return (_cents(pct + per), f"round2({rate}% × (price + shipping charged) + per-order fee ({tiers_txt}))",
                {**base, "per_order_fee_usd": float(per)})
    minimum = Decimal(str(fee["min_referral_usd"]))
    per_item = Decimal(str(fee["per_item_usd"]))
    return (_cents(max(pct, minimum) + per_item), f"round2(max({rate}% × (price + shipping charged), ${minimum}) + ${per_item} per item)",
            {**base, "min_referral_usd": float(minimum), "per_item_usd": float(per_item)})


def _choose(evals: list[tuple[dict[str, Any], dict[str, Any]]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The cheapest option that PASSES the channel's rule; when none passes, the cheapest overall (its verdict says why)."""
    if not evals:
        return None
    passing = [e for e in evals if e[1]["verdict"] == PASS]
    pool = passing or evals
    return min(pool, key=lambda e: (e[0]["cost"] is None, e[0]["cost"] or 0, e[1]["days"] is None, e[1]["days"] or 0,
                                    str(e[0]["origin"]), str(e[0]["carrier"] or "")))


def _line(cid: str, ch: dict[str, Any], offer: dict[str, Any] | None, price: Decimal | None, settings: dict[str, Any],
          rs: dict[str, Any]) -> tuple[dict[str, Any], _Pending, dict[str, Any]]:
    """One offer on one channel -> (line, its pending receipts, internal numbers)."""
    rec = _Pending()
    evals = [(opt, _evaluate(cid, ch, opt, offer, rs, settings)) for opt in offer["shipping"]] if offer else []
    chosen = _choose(evals)
    unit = offer["unit_cost"] if offer else None
    inventory = bool(offer) and offer["model"] == INVENTORY
    inbound = offer["inbound"]["cost"] if inventory else (Decimal(0) if offer else None)
    ship = chosen[0]["cost"] if chosen else None
    rate = settings["returns_rate"]
    oid = offer["offer_id"] if offer else None
    if chosen:
        dv = chosen[1]
        options = [{"origin": o["origin"], "carrier": o["carrier"], "cost_usd": _out(o["cost"]), "verdict": e["verdict"]} for o, e in evals]
    else:
        if not offer:
            why, origin, cautions = "no supplier offer: cannot check the delivery rule", UNKNOWN, []
        elif inventory:
            why = (f"no last mile for shipping from your US stock — {offer.get('last_mile_note') or 'no CJ US→US quote and no owner setting'}: "
                   f"cannot check the delivery rule; {_stock_note(offer)} — {_stock_detail(offer)}")
            origin, cautions = "US", [REQUIRES_US_STOCK]
        else:
            why, origin, cautions = "no shipping data in the offer: cannot check the delivery rule", UNKNOWN, []
        dv = {"verdict": UNKNOWN, "reason": f"UNKNOWN: {why}.", "origin": origin, "carrier": None, "days": None, "business_days": None,
              "handling": settings["handling_business_days"], "cautions": cautions}
        options = []
    rec.add("sell_price_usd", "the market reference price (market.reference_price_usd): the price the buyer pays, shipping included",
            {"reference_price_usd": _out(price)}, _out(price), missing=["reference price"] if price is None else None)
    rec.add("unit_cost_usd", "the offer's unit cost (offers[].unit_cost_usd)", {"offer_id": oid}, _out(unit),
            missing=["unit cost"] if unit is None else None)
    if inventory:
        rec.add("inbound_usd", f"the offer's inbound freight per unit to your US stock (offers[].inbound.cost_usd, rule {offer['inbound']['cost_rule']['rule']})",
                {"offer_id": oid, "rule": offer["inbound"]["cost_rule"]["rule"]}, _out(inbound), missing=["inbound freight"] if inbound is None else None)
        last = chosen[0] if chosen else None
        if last:
            span = f"{last['days_min']}-{last['days_max']}" if last["days_min"] is not None and last["days_min"] != last["days_max"] else f"{last['days_max']}"
            why = ("the cheapest last-mile option whose days pass this channel's delivery rule" if dv["verdict"] == PASS else
                   f"no last-mile option passes this channel's delivery rule: the cheapest overall ({dv['verdict']})")
            formula = (f"the last mile per order from your US stock: {last['carrier']} ${_out(last['cost'])} {span} days ({last['source']}) — {why}"
                       if last["cost"] is not None else f"the last mile per order from your US stock: {last['carrier']} ({last['source']}) — {why}")
        else:
            why, formula = None, "the last mile per order from your US stock: none known"
        rec.add("shipping_usd", formula,
                {"offer_id": oid, "chosen": {"carrier": last["carrier"], "cost_usd": _out(last["cost"]), "days_min": _out(last["days_min"]),
                                             "days_max": _out(last["days_max"]), "source": last["source"], "ref_offer_id": last["ref"]} if last else None,
                 "why": why, "options": [{"carrier": o["carrier"], "cost_usd": _out(o["cost"]), "days_max": _out(o["days_max"]), "verdict": e["verdict"],
                                          "source": o["source"]} for o, e in evals]},
                _out(ship), rule=last["source_rule"] if last else UNKNOWN,
                missing=["last-mile cost (a CJ US→US quote or the owner's settings last_mile_usd)"] if ship is None else None)
    else:
        rec.add("inbound_usd", "dropship: the supplier ships each order to the buyer — no inbound freight" if offer else "no supplier offer",
                {"offer_id": oid}, _out(inbound), missing=["supplier offer"] if inbound is None else None)
        rec.add("shipping_usd", "the cheapest shipping option that passes this channel's delivery rule, else the cheapest overall",
                {"offer_id": oid, "options": options, "chosen": {"origin": dv["origin"], "carrier": dv.get("carrier")} if chosen else None},
                _out(ship), missing=["shipping cost"] if ship is None else None)
    landed = unit + inbound + ship if unit is not None and inbound is not None and ship is not None else None
    rec.add("landed_cost_usd", "unit cost + inbound freight per unit + shipping", {"unit_cost_usd": _out(unit), "inbound_usd": _out(inbound),
            "shipping_usd": _out(ship)}, _out(landed), missing=[k for k, v in (("unit cost", unit), ("inbound freight", inbound), ("shipping", ship))
                                                              if v is None] or None)
    fees = None
    if price is not None:
        fees, formula, inputs = _fees(ch, price, settings)
        rec.add("fees_usd", formula, inputs, _out(fees), policy=f"sales_channels.channels.{cid}.fee")
    else:
        rec.add("fees_usd", "channel fee formula on the sell price", {"price_usd": UNKNOWN}, UNKNOWN, missing=["sell price"],
                policy=f"sales_channels.channels.{cid}.fee")
    returns = _cents(rate * landed) if landed is not None else None
    rec.add("returns_usd", "round2(returns_rate × (unit cost + inbound + shipping))", {"returns_rate": float(rate), "landed_cost_usd": _out(landed)},
            _out(returns), missing=["unit cost + inbound + shipping"] if returns is None else None, policy="report_settings.defaults.returns_rate")
    parts = (price, landed, fees, returns)
    margin = _cents(price - landed - fees - returns) if all(v is not None for v in parts) else None
    missing = [k for k, v in zip(("sell price", "unit cost + inbound + shipping", "fees", "returns"), parts) if v is None] or None
    rec.add("margin_before_ads_usd", "round2(sell price − (unit cost + inbound + shipping) − fees − returns allowance)",
            {"sell_price_usd": _out(price), "landed_cost_usd": _out(landed), "fees_usd": _out(fees), "returns_usd": _out(returns)},
            _out(margin), missing=missing)
    pct = (margin / price * HUNDRED).quantize(TENTH, rounding=ROUND_HALF_UP) if margin is not None and price else None
    rec.add("margin_pct", "round1(margin before ads ÷ sell price × 100)", {"margin_before_ads_usd": _out(margin), "sell_price_usd": _out(price)},
            _out(pct), missing=missing)
    rec.add("break_even_ad_cost_usd", "= margin before ads: the most a sale can spend on ads and break even (no ad cost is assumed)",
            {"margin_before_ads_usd": _out(margin)}, _out(margin), missing=missing)
    rec.add("delivery.days_max", "the delivery days the rule checks: " + (_option_days(chosen[0])[1] if chosen else "no shipping data"),
            {"offer_id": oid, "carrier": dv.get("carrier"), "origin": dv["origin"]}, _out(dv["days"]), missing=["delivery days"] if dv["days"] is None else None)
    rec.add("delivery.business_days_max", f"the most business days those days can hold (supplier days read as {rs.get('supplier_days_read_as') or 'calendar'} days: "
            "the run of days with the fewest weekend days)", {"days_max": _out(dv["days"])}, _out(dv["business_days"]),
            missing=["delivery days"] if dv["business_days"] is None else None)
    rec.add("delivery.handling_business_days", "the seller's handling before the first carrier scan: settings handling_business_days "
            "(policies report_settings default) — every rule whose clock starts at the order counts it before the carrier's days",
            {"setting": "handling_business_days"}, dv["handling"], policy="report_settings.defaults.handling_business_days")
    delivery = {"verdict": dv["verdict"], "reason": dv["reason"], "origin": dv["origin"], "days_max": _out(dv["days"]),
                "business_days_max": _out(dv["business_days"]), "handling_business_days": dv["handling"], "carrier": dv.get("carrier"),
                "cautions": dv["cautions"]}
    for k in ("badge_eligible", "prime"):
        if k in dv:
            delivery[k] = dv[k]
    line = {"offer_id": oid, "source": offer["source"] if offer else None, "model": offer["model"] if offer else None, "sell_price_usd": _out(price),
            "unit_cost_usd": _out(unit), "inbound_usd": _out(inbound), "shipping_usd": _out(ship), "landed_cost_usd": _out(landed),
            "fees_usd": _out(fees), "returns_usd": _out(returns),
            "margin_before_ads_usd": _out(margin), "margin_pct": _out(pct), "break_even_ad_cost_usd": _out(margin), "delivery": delivery}
    return line, rec, {"margin": margin, "landed": landed, "verdict": dv["verdict"], "price": price, "unit": unit, "ship": ship}


def _channels(offers: list[dict[str, Any]], price: Decimal | None, settings: dict[str, Any], sc: dict[str, Any], rs: dict[str, Any],
              book: _Book) -> tuple[dict[str, Any], dict[str, Any]]:
    channels: dict[str, Any] = {}
    sens: dict[str, Any] = {}
    for cid in settings["channels"]:
        ch = sc["channels"][cid]
        priced = [(i, *_line(cid, ch, o, price, settings, rs)) for i, o in enumerate(offers)] or [(0, *_line(cid, ch, None, price, settings, rs))]
        # best first: non-FAIL delivery, then the highest margin (at one sell price that is the lowest landed cost; with shipping
        # unknown, the lowest unit cost), then offer order
        priced.sort(key=lambda t: (t[3]["verdict"] == FAIL, t[3]["margin"] is None, -(t[3]["margin"] or 0), t[3]["landed"] is None,
                                   t[3]["landed"] or 0, t[3]["unit"] is None, t[3]["unit"] or 0, t[0]))
        (_, best, best_rec, best_num), rest = priced[0], priced[1:]
        best_rec.emit(book, f"channels.{cid}")
        entry = dict(best)
        alts = []
        for k, (_, line, rec, _num) in enumerate(rest):
            rec.emit(book, f"channels.{cid}.alternatives[{k}]")
            alts.append(line)
        entry["alternatives"] = alts
        channels[cid] = entry
        if ch.get("sensitivity"):
            _sensitivity(book, sens, cid, ch, best["offer_id"], best_num, settings)
    return channels, sens


def _sensitivity(book: _Book, sens: dict[str, Any], cid: str, ch: dict[str, Any], offer_id: str | None, num: dict[str, Any],
                 settings: dict[str, Any]) -> None:
    """The channel's best line again at the sensitivity rate (TikTok's unconfirmed 8 %): same offer, same price, same returns."""
    spec = ch["sensitivity"]
    sid = spec["id"]
    if sid not in sens:
        sens[sid] = {"rate_pct": book.add(f"sensitivity.{sid}.rate_pct", f"policy value: {spec.get('status')} (trade blogs), never the base case",
                                          {"policy": f"sales_channels.channels.{cid}.sensitivity.rate_pct"}, float(spec["rate_pct"])),
                     "status": spec.get("status"), "channels": {}}
    p = f"sensitivity.{sid}.channels.{cid}"
    price, landed = num["price"], num["landed"]
    fees = returns = margin = pct = None
    if price is not None:
        fees, formula, inputs = _fees(ch, price, settings, rate_pct=spec["rate_pct"])
    else:
        formula, inputs = "the channel's fee formula at the sensitivity rate", {"price_usd": UNKNOWN, "rate_pct": float(spec["rate_pct"])}
    if price is not None and landed is not None:
        returns = _cents(settings["returns_rate"] * landed)
        margin = _cents(price - landed - fees - returns)
        pct = (margin / price * HUNDRED).quantize(TENTH, rounding=ROUND_HALF_UP)
    missing = None if margin is not None else [k for k, v in (("sell price", price), ("unit cost + inbound + shipping", landed)) if v is None]
    book.add(f"{p}.fees_usd", formula, inputs, _out(fees), policy=f"sales_channels.channels.{cid}.sensitivity",
             missing=["sell price"] if price is None else None)
    book.add(f"{p}.margin_before_ads_usd", "round2(sell price − (unit cost + inbound + shipping) − fees − returns allowance)",
             {"sell_price_usd": _out(price), "landed_cost_usd": _out(landed), "fees_usd": _out(fees), "returns_usd": _out(returns)},
             _out(margin), missing=missing)
    book.add(f"{p}.margin_pct", "round1(margin before ads ÷ sell price × 100)", {"margin_before_ads_usd": _out(margin), "sell_price_usd": _out(price)},
             _out(pct), missing=missing)
    book.add(f"{p}.break_even_ad_cost_usd", "= margin before ads", {"margin_before_ads_usd": _out(margin)}, _out(margin), missing=missing)
    sens[sid]["channels"][cid] = {"offer_id": offer_id, "fees_usd": _out(fees), "margin_before_ads_usd": _out(margin), "margin_pct": _out(pct),
                                  "break_even_ad_cost_usd": _out(margin)}


# --------------------------------------------------------------------------------------------------------- assumptions --
def _fee_text(fee: dict[str, Any], settings: dict[str, Any]) -> str:
    kind, rate = fee["kind"], fee["rate_pct"]
    if kind == "percent":
        return f"{rate}% × (price + shipping)"
    if kind == "percent_fixed_plan":
        return (f"{rate}% × (price + shipping) + ${Decimal(str(fee['fixed_usd'])):.2f} + the {fee.get('plan', '')} plan "
                f"${Decimal(str(fee['plan_monthly_usd'])):.2f}/month ÷ {settings['shopify_monthly_orders']} orders")
    if kind == "percent_per_order":
        parts = [(f"${Decimal(str(t['fee_usd'])):.2f} per order ≤ ${Decimal(str(t['max_order_usd'])):.2f}" if t.get("max_order_usd") is not None
                  else f"${Decimal(str(t['fee_usd'])):.2f} above") for t in fee["per_order"]]
        return f"{rate}% × (price + shipping) + " + " / ".join(parts)
    return (f"max({rate}% × (price + shipping), ${Decimal(str(fee['min_referral_usd'])):.2f}) + "
            f"${Decimal(str(fee['per_item_usd'])):.2f} per item")


def _delivery_text(cid: str, rule: dict[str, Any]) -> str:
    kind = rule["kind"]
    if kind == "us_local_only":
        lo, hi = rule["custom_handling_business_days"]
        return (f"FAIL when shipped from outside the US (domestic shipping only); from a US warehouse PASS only when in transit ≤ "
                f"{rule['max_handling_business_days']} and delivered ≤ {rule['max_delivery_business_days']} business days (custom handling "
                f"{lo}-{hi}: delivered ≤ handling + {rule['custom_handling_extra_delivery_business_days']}), else FAIL")
    if kind == "honest_handling":
        return (f"PASS with an honest handling time; the free-shipping badge needs handling ≤ {rule['badge_max_handling_business_days']} and "
                f"delivery ≤ {rule['badge_max_delivery_business_days']} business days")
    text = f"PASS when delivered ≤ {rule['max_delivery_days']} {'business ' if rule.get('days') == 'business' else ''}days, else {rule['over']}"
    if rule.get("max_in_transit_calendar_days"):
        text = (f"PASS when in transit ≤ {rule['max_in_transit_calendar_days']} and delivered ≤ {rule['max_delivery_days']} calendar days, "
                f"else {rule['over']}")
    if rule.get("ftc_ship_within_days"):
        text += f"; ship within the stated time, or {rule['ftc_ship_within_days']} days when none is stated (FTC)"
    if rule.get("prime_fail_origins"):
        text += f"; Prime FAIL from {', '.join(_ORIGIN_NAMES.get(o, o) for o in rule['prime_fail_origins'])}"
    if rule.get("basis"):
        text += f" ({rule['basis']})"
    return text


def _assumptions(sc: dict[str, Any], rs: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    sources = sc["sources"]
    tol = _dec(rs.get("last_mile_weight_tolerance"))
    tol = tol if tol is not None else Decimal("0.25")

    def src(sid: str) -> dict[str, Any]:
        s = sources[sid]
        return {"id": sid, "url": s.get("url"), "title": s.get("title"), "published": s.get("published"), "read": s.get("read"), "backs": s.get("backs")}

    channels = {}
    for cid in settings["channels"]:
        ch = sc["channels"][cid]
        channels[cid] = {"label": ch.get("label"), "fee": {**ch["fee"], "text": _fee_text(ch["fee"], settings)},
                         "delivery": {**ch["delivery"], "text": _delivery_text(cid, ch["delivery"])},
                         "sources": [src(s) for s in ch.get("sources") or []]}
        if ch.get("sensitivity"):
            channels[cid]["sensitivity"] = {**{k: v for k, v in ch["sensitivity"].items() if k != "sources"},
                                            "sources": [src(s) for s in ch["sensitivity"].get("sources") or []]}
    shopify = sc["channels"].get("shopify", {}).get("fee") or {}
    floor = int(rs.get("min_comps_for_reference") or 3)
    out = {
        "rules_read_on": sc.get("read_on"),
        "as_of": settings["as_of"],
        "sell_price": (f"the reference price: the median of matched Amazon listings (price + shipping where stated) when there are at least {floor}, "
                       f"else the median of matched Amazon and eBay listings together when there are at least {floor}, else UNKNOWN; "
                       "CJ's suggested retail is shown as reference only and never used"),
        "fee_base": sc.get("fee_base"),
        "returns": {"rate": float(settings["returns_rate"]), "text": "returns allowance per sale = returns rate × (unit cost + inbound freight + shipping)",
                    "source": src(rs["returns_rate_source"])},
        "ad_cost": ("no ad cost is assumed (owner decision 2026-11-02): every line shows the break-even ad cost per sale, which equals the "
                    "margin before ads"),
        "chargebacks": "not modelled per unit",
        "handling": (f"every delivery rule whose clock starts at the order counts the seller's handling first: {settings['handling_business_days']} "
                     "business day(s) to the first carrier scan (setting handling_business_days, policies default 1), then the carrier's days — "
                     "TikTok US: first scan ≤ 2 and handling + carrier ≤ 6 business days; TikTok cross-border: first scan ≤ 3 days and "
                     "handling + carrier ≤ 15 calendar days (stock in a US warehouse: first scan ≤ 2, ≤ 6 business days); eBay's free-shipping "
                     "badge: handling ≤ 1 and ≤ 4 business days; Shopify (7) and Amazon (10): handling + carrier days"),
        "delivery_days": (f"a quote's max days are the carrier's days (the seller's handling comes on top) and are read as "
                          f"{rs.get('supplier_days_read_as') or 'calendar'} days unless the quote says business or calendar days; a rule counted "
                          "in business days takes the most business days calendar days can hold, a rule counted in calendar days the most calendar "
                          "days business days can span; an inventory offer is checked on its last mile from US stock"),
        "cj": ("dropship model: unit cost = the cheapest variant; MOQ 1; CJ ships each order — its freight quotes from China (CN) and from a "
               "US warehouse (US); a US quote does not prove US stock"),
        "alibaba": ("inventory model — buy the MOQ in bulk and hold US stock: unit cost = the price of the tier that holds the MOQ (a price range: "
                    "its high end); MOQ capital = MOQ × unit cost; inbound freight per unit = the listing's own quote for a stated quantity "
                    "(quote ÷ quantity), else max(MOQ × unit weight, the stated minimum kg) × the per-kg rate, never below a stated minimum charge, "
                    "÷ MOQ (the unit weight: stated, else the heaviest matched CJ product's; UNKNOWN without a quote or a rate and a weight, or "
                    "with a minimum but no MOQ, or when the listing's shipping estimate is for a country other than the US — an unstated "
                    "destination is read as the US and said so); cash before first stock = MOQ capital (goods) + the inbound freight for the "
                    "MOQ order; each order then ships from your US stock: the last mile = per channel, the cheapest of the "
                    "candidate's CJ US→US quotes whose days pass that channel's rule, else the cheapest overall (a proxy, each labelled with its "
                    f"CJ product and weight, used only when the offer's own unit weight is unknown or at most {_plain(tol * 100)} % above that "
                    "product's), else the "
                    "owner's settings last_mile_usd / last_mile_days, else UNKNOWN; customer delivery = the last-mile days from the US; time to first stock = lead time + transit, once; the inbound leg "
                    f"ships from {_ORIGIN_NAMES.get(rs.get('alibaba_origin_default') or 'CN', 'China')} unless the listing states another origin"),
        "last_mile": {"usd": float(settings["last_mile_usd"]) if settings["last_mile_usd"] is not None else None, "days": settings["last_mile_days"],
                      "weight_tolerance": float(tol),
                      "text": ("the owner's own last mile (settings last_mile_usd / last_mile_days), used for an inventory offer when the candidate "
                               f"has no CJ US→US quote, or when the offer is more than {_plain(tol * 100)} % heavier than every CJ quote's product "
                               "(policies report_settings last_mile_weight_tolerance)")},
        "best_offer": "per channel the best offer is the highest margin among offers whose delivery verdict is not FAIL; every other offer is kept",
        "shopify_plan": {"plan": shopify.get("plan"), "monthly_usd": shopify.get("plan_monthly_usd"),
                         "monthly_orders": settings["shopify_monthly_orders"],
                         "per_order_usd": float(_cents(Decimal(str(shopify.get("plan_monthly_usd") or 0)) / Decimal(settings["shopify_monthly_orders"])))},
        "channels": channels,
    }
    return out


# ------------------------------------------------------------------------------------------------------------- compute --
def compute(bundle: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """The decision model for every candidate (plan §4.4). Raises DecisionInputError (a ValueError) on a malformed bundle, setting or
    policy."""
    if not isinstance(bundle, dict):
        raise DecisionInputError("bundle must be an object {candidates, host, parsed, settings}")
    sc, rs = _policy(policy)
    settings = _settings(bundle.get("settings"), sc, rs)
    host = bundle.get("host") if isinstance(bundle.get("host"), dict) else {}
    parsed = bundle.get("parsed") if isinstance(bundle.get("parsed"), dict) else {}
    cj_moq = _int(((policy.get("supplier") or {}).get("moq_default_by_channel") or {}).get("cjdropshipping"))
    if not cj_moq:
        raise DecisionInputError("policy supplier.moq_default_by_channel.cjdropshipping (CJ's single-unit MOQ) is missing")
    products = []
    for i, cand in enumerate(bundle.get("candidates") or []):
        if not isinstance(cand, dict) or not str(cand.get("candidate_id") or cand.get("id") or "").strip():
            raise DecisionInputError(f"candidates[{i}] needs a candidate_id")
        cid = str(cand.get("candidate_id") or cand.get("id")).strip()
        products.append(_product(cand, cid, host, parsed.get(cid) if isinstance(parsed.get(cid), dict) else {}, settings, sc, rs, cj_moq))
    return {"model": MODEL, "as_of": settings["as_of"], "policy_hash": _policy_hash(sc, rs),
            "settings": {**settings, "returns_rate": float(settings["returns_rate"]),
                         "last_mile_usd": float(settings["last_mile_usd"]) if settings["last_mile_usd"] is not None else None},
            "channels": list(settings["channels"]),
            "products": products, "assumptions": _assumptions(sc, rs, settings)}


def _product(cand: dict[str, Any], cid: str, host: dict[str, Any], parsed: dict[str, Any], settings: dict[str, Any],
             sc: dict[str, Any], rs: dict[str, Any], cj_moq: int) -> dict[str, Any]:
    book = _Book()
    cj_block = ((host.get("cj") or {}).get(cid)) or {}
    ebay_block = ((host.get("ebay") or {}).get(cid)) or {}
    cj_block = cj_block if isinstance(cj_block, dict) else {}
    ebay_block = ebay_block if isinstance(ebay_block, dict) else {}
    terms = [str(t).strip() for t in (cand.get("search_terms") if isinstance(cand.get("search_terms"), list) else [cand.get("term")]) if t and str(t).strip()]
    offers_excluded: list[dict[str, Any]] = []
    internal, offers = _offers(cj_block, _records(parsed.get("alibaba")), rs, cj_moq, book, offers_excluded, settings, terms)
    market, price = _market(_records(parsed.get("amazon")), ebay_block, _records(parsed.get("ebay")), rs, book, terms)
    demand = {"reddit": _reddit(_records(parsed.get("reddit")), rs, book, terms), "amazon": _amazon_demand(_records(parsed.get("amazon")), book)}
    channels, sensitivity = _channels(internal, price, settings, sc, rs, book)
    status = {"cj": {"status": cj_block.get("status") or UNKNOWN, "reason_code": cj_block.get("reason_code")},
              "ebay_api": {"status": ebay_block.get("status") or UNKNOWN, "reason_code": ebay_block.get("reason_code")}}
    return {"candidate_id": cid, "title": _clip(cand.get("title"), 300) or None, "offers": offers, "market": market, "demand": demand,
            "channels": channels, "sensitivity": sensitivity, "sources_status": status, "offers_excluded": offers_excluded, "receipts": book.rows}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os
    import sys

    ap = argparse.ArgumentParser(description="PRODUCT-DECISION-REPORT-V1 §4.4: the decision model of a report bundle (pure, no network)")
    ap.add_argument("--bundle", required=True, help="the report bundle as JSON {candidates, host, parsed, settings}")
    ap.add_argument("--out", help="write the decision JSON here (default: stdout)")
    args = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import graph

    with open(args.bundle, encoding="utf-8") as f:
        bundle = json.load(f)
    try:
        decision = compute(bundle, graph.load_policies())
    except DecisionInputError as exc:
        print(json.dumps({"error": "DECISION_INPUT_INVALID", "detail": str(exc)}), file=sys.stderr)
        return 2
    text = json.dumps(decision, sort_keys=True, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
