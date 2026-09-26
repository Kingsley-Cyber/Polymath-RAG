#!/usr/bin/env python3
"""HarnessActionV1 -> HarnessResearchReceiptV1 (GOVERNED-CONVERGENCE-V1 TG4, docs/27).

In GOVERNED mode the Polymath cognitive adapter (`trail.product_discovery`) issues a HARNESS_ACTION step: a typed
research assignment (hypotheses, evidence gaps, search intents, source roles, freshness, independence, budget). THIS
skill's existing acquisition tooling does the research — the same channel tools, the same observation / field_record /
supplier_candidate shapes — and this module turns what was harvested into the receipt the adapter accepts through
`adapter_submit kind=receipt`. TrailSignal then decides what is admitted as evidence. Nothing here decides anything:

  * it is NOT a second harness — it fetches nothing, searches nothing and ranks nothing;
  * it carries NO score: `evidence_score`, `qualify.py` and `evaluator.py` are standalone-mode only, and the receipt is
    built from a whitelist of fields, so a score / rank / weight key cannot ride along;
  * it never invents provenance: an item without a harvest-time `retrieved_at`, or without an explicit
    `published_at_if_known` (null = "the page shows no date"), is OMITTED and the omission is written into the
    receipt's `limitations` — a missing timestamp is never replaced by "now", and a known publish date is never dropped;
  * it never re-labels to pass: roles map through ONE static table; an item whose roles mean nothing to TrailSignal is
    omitted, never coerced; TrailSignal's rejections are findings.

    python3 python/adapter_receipt.py build --action action.json --observations obs.json \\
        --harness-id claude-code --started-at 2026-09-20T17:00:00Z --completed-at 2026-09-20T17:20:00Z \\
        --tool-trace trace.json --out receipt.json [--strict]
    python3 python/adapter_receipt.py validate --receipt receipt.json [--action action.json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schemas", "harness_receipt.schema.json")     # BYTE COPY of the polymath-v4 contract
#: the contract this copy was taken from, and its sha256 — tests/run_all.py fails on drift (copy != pin, or pin != the
#: authoritative file when polymath-v4 sits beside this repo). A contract change = re-copy + re-pin, in the same slice.
SCHEMA_SOURCE = "polymath-v4/contracts/adapter/v1/harness_receipt.schema.json"
SCHEMA_SHA256 = "c5a8e1ca1c3a28e18b1a0ae5a5b66c1d765793df507c6e9a76d8304c4e3cd7e8"   # ADR-069: + optional hypothesis_relations (four copies re-pinned 2026-09-22)

EXCERPT_MAX, CLAIM_MAX, CONTEXT_MAX, LIMITATION_MAX = 600, 2000, 2000, 1000
SCHEMA_MAX = {"sources": 100, "observations": 200, "tool_trace": 200, "limitations": 50}

#: skill evidence role (graph/policies.yaml `evidence_roles.valid`) -> TrailSignal evidence role. ONE static table.
#: None = the role is real in standalone mode but names nothing TrailSignal admits (vocabulary, corpus-side mechanism):
#: an item carrying only such roles is omitted, never coerced into a role it did not claim.
ROLE_MAP = {
    "FRICTION_EVIDENCE": "friction", "WORKAROUND_EVIDENCE": "workaround", "PRODUCT_MODIFICATION": "workaround",
    "BEHAVIOR_SUPPORT": "behavior", "PURCHASE_INTENT": "demand", "PRODUCT_REQUEST": "demand",
    "PRODUCT_COMPLAINT": "competition", "PRODUCT_COMPARISON": "competition", "CURRENT_PRODUCT_REFERENCE": "competition",
    "PRODUCT_DELTA_SUPPORT": "competition", "CONTRADICTION": "contradiction", "PRICE_EVIDENCE": "price",
    "SUPPLIER_AVAILABILITY": "supply", "MOQ_EVIDENCE": "supply", "CUSTOMIZATION_EVIDENCE": "operations",
    "FULFILLMENT_EVIDENCE": "operations", "MECHANISM_SUPPORT": None, "INSIDER_LANGUAGE": None,
}
TRAIL_ROLES = ("friction", "workaround", "behavior", "demand", "competition", "seasonality", "operations", "risk",
               "contradiction", "price", "supply")
#: registered domains -> TrailSignal source class (TrailSignal `data/source_capabilities.csv`, read 2026-09-20). A class is
#: a DESCRIPTION of the source, stated truthfully; whether the source may support the claimed role is TrailSignal's call.
DOMAIN_CLASS = {
    "reddit.com": "community_discussion", "redd.it": "community_discussion", "facebook.com": "community_discussion",
    "youtube.com": "video_platform", "youtu.be": "video_platform", "tiktok.com": "social_trend", "trends.pinterest.com": "social_trend",
    "amazon.com": "marketplace_listing", "amazon.co.uk": "marketplace_listing", "amazon.ca": "marketplace_listing",
    "amazon.de": "marketplace_listing", "walmart.com": "marketplace_listing", "etsy.com": "marketplace_listing",
    "ebay.com": "marketplace_listing", "homedepot.com": "retailer", "lowes.com": "retailer",
    "alibaba.com": "supplier_listing", "cjdropshipping.com": "supplier_listing", "1688.com": "supplier_listing",
}
#: URL patterns TrailSignal routes BEFORE its domain rows (data/source_capabilities.csv since HR7, ADR-070: the comment threads
#: under a short video, cited by the video's canonical link). Checked before DOMAIN_CLASS; a Creative Center link stays a trend.
PATTERN_CLASS = {"tiktok.com/@": "video_platform", "instagram.com/reel": "video_platform", "instagram.com/p/": "video_platform"}
#: fallback by the skill's own source family / platform when the domain is not a registered one (class-level wildcard rows)
FAMILY_CLASS = {"community": "community_discussion", "review": "retailer", "marketplace_listing": "marketplace_listing",
                "supplier": "supplier_listing"}
PLATFORM_CLASS = {"reddit": "community_discussion", "forum": "community_discussion", "twitter": "community_discussion",
                  "xiaohongshu": "community_discussion", "facebook": "community_discussion", "youtube": "video_platform",
                  "tiktok": "social_trend", "instagram": "video_platform", "amazon_reviews": "marketplace_listing",
                  "amazon": "marketplace_listing", "alibaba": "supplier_listing", "cjdropshipping": "supplier_listing",
                  "1688": "supplier_listing", "manufacturer": "supplier_listing", "retailer": "retailer"}
#: families that are NOT harness observations at all: corpus knowledge is Polymath's, never field evidence
NOT_FIELD_FAMILIES = {"corpus_evergreen"}
_FORBIDDEN_KEY = re.compile(r"score|rank|weight", re.I)
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


# ------------------------------------------------------------------ schema --
def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def schema_sha256() -> str:
    with open(SCHEMA_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _is_type(value, t: str) -> bool:
    return {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
            "boolean": isinstance(value, bool), "null": value is None,
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool)}.get(t, True)


def schema_errors(value, spec: dict, path: str = "$") -> list[str]:
    """The JSON-Schema subset the receipt contract uses, read from the byte-copied schema at runtime (so tightening the
    contract needs no code change here): type (incl. unions), required = KEY PRESENT (null is a value), properties,
    additionalProperties:false, items, min/maxItems, min/maxLength, pattern, format date-time, minimum, enum, const.
    models.validate is NOT used: its `required` means "present and non-empty", which would reject a lawful null."""
    errs: list[str] = []
    t = spec.get("type")
    if t is not None and not any(_is_type(value, x) for x in (t if isinstance(t, list) else [t])):
        return [f"{path}: expected {t}, got {type(value).__name__}"]
    if "const" in spec and value != spec["const"]:
        errs.append(f"{path}: must be {spec['const']!r}")
    if spec.get("enum") is not None and value not in spec["enum"]:
        errs.append(f"{path}: {value!r} not in {spec['enum']}")
    if isinstance(value, str):
        if spec.get("minLength") is not None and len(value) < spec["minLength"]:
            errs.append(f"{path}: shorter than {spec['minLength']}")
        if spec.get("maxLength") is not None and len(value) > spec["maxLength"]:
            errs.append(f"{path}: longer than {spec['maxLength']}")
        if spec.get("pattern") and not re.search(spec["pattern"], value):
            errs.append(f"{path}: does not match {spec['pattern']}")
        if spec.get("format") == "date-time" and not _ISO.match(value):
            errs.append(f"{path}: not an RFC 3339 date-time")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and spec.get("minimum") is not None and value < spec["minimum"]:
        errs.append(f"{path}: below minimum {spec['minimum']}")
    if isinstance(value, dict):
        for key in spec.get("required") or []:
            if key not in value:
                errs.append(f"{path}.{key}: required")
        props = spec.get("properties") or {}
        for key, sub in props.items():
            if key in value:
                errs += schema_errors(value[key], sub, f"{path}.{key}")
        if spec.get("additionalProperties") is False:
            extra = sorted(set(value) - set(props))
            if extra:
                errs.append(f"{path}: unexpected keys {extra}")
    if isinstance(value, list):
        if spec.get("minItems") is not None and len(value) < spec["minItems"]:
            errs.append(f"{path}: fewer than {spec['minItems']} items")
        if spec.get("maxItems") is not None and len(value) > spec["maxItems"]:
            errs.append(f"{path}: more than {spec['maxItems']} items")
        if isinstance(spec.get("items"), dict):
            for i, v in enumerate(value):
                errs += schema_errors(v, spec["items"], f"{path}[{i}]")
    return errs


# ----------------------------------------------------------------- helpers --
def _sid(prefix: str, *parts) -> str:
    return prefix + hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def _clip(text, n: int) -> str:
    return " ".join(str(text or "").split())[:n]


def _domain(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def source_class_for(url: str, source_identity: dict | None = None) -> str | None:
    """Registered domain first (a fact about the URL), then the skill's own platform / family (a fact about the channel the
    item came from). None = the builder does not know what kind of source this is and will not guess."""
    lowered = str(url or "").lower()
    for pattern, cls in PATTERN_CLASS.items():
        if pattern in lowered:
            return cls
    host = _domain(url)
    for dom, cls in DOMAIN_CLASS.items():
        if host == dom or host.endswith("." + dom):
            return cls
    ident = source_identity or {}
    return PLATFORM_CLASS.get(str(ident.get("platform") or "").lower()) or FAMILY_CLASS.get(str(ident.get("source_family") or "").lower())


def trail_role_for(item: dict) -> str | None:
    """ONE role per observation. A contradiction is a contradiction whatever else it carries (the falsifying signal is never
    hidden behind another label); otherwise the FIRST role the harvester listed that TrailSignal knows."""
    if item.get("contradicts") is True:
        return "contradiction"
    explicit = str(item.get("evidence_role_claimed") or "").strip()
    if explicit:
        return explicit if explicit in TRAIL_ROLES else None
    for role in item.get("evidence_roles") or []:
        mapped = ROLE_MAP.get(str(role))
        if mapped:
            return mapped
    return None


def _iso_ok(value) -> bool:
    return isinstance(value, str) and bool(_ISO.match(value))


def _harvest_problem(item: dict) -> str | None:
    """Why this item cannot become a receipt observation (None = it can). Provenance is captured at HARVEST time or not at all."""
    url = str(item.get("source") or item.get("url") or "")
    if not re.match(r"^https?://", url):
        return "no source URL (a receipt observation must be re-resolvable)"
    if not _iso_ok(item.get("retrieved_at")):
        return "no harvest-time retrieved_at (never replaced by 'now')"
    if "published_at_if_known" not in item:
        return "published_at_if_known not recorded (write null when the page shows no date — silence is not 'unknown')"
    if item["published_at_if_known"] is not None and not _iso_ok(item["published_at_if_known"]):
        return "published_at_if_known is not an RFC 3339 date-time"
    return None


def _metric(item: dict) -> dict | None:
    m = item.get("metric") or item.get("metric_if_present")
    if not isinstance(m, dict) or not m.get("name") or not m.get("unit") or not isinstance(m.get("value"), (int, float)) or isinstance(m.get("value"), bool):
        return None
    # TRAIL PARITY (2026-09-21): TrailSignal REQUIRES the `sample_n` key (nullable) and an identifier-shaped metric name; a metric
    # without the key passed Polymath's old schema and ended a real run as TRAIL_REFUSED. Always emit it; null = not stated.
    n = m.get("sample_n")
    name = re.sub(r"[^A-Za-z0-9._:/-]+", "_", str(m["name"]).strip()).strip("_") or "metric"
    return {"name": _clip(name, 100), "value": m["value"], "unit": _clip(m["unit"], 50),
            "sample_n": n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None}


def _context(item: dict) -> str:
    parts = [f"community: {item['community']}" if item.get("community") else "", f"activity: {item['activity']}" if item.get("activity") else "",
             f"moment: {item['moment']}" if item.get("moment") else "", str(item.get("context") or ""),
             f"workaround: {item['workaround']}" if item.get("workaround") else "",
             f"desired outcome: {item['desired_outcome']}" if item.get("desired_outcome") else "",
             "purchase language present" if item.get("purchase_language") is True else ""]
    return _clip(" · ".join(p for p in parts if p), CONTEXT_MAX) or "no further context recorded at harvest time"


def _supplier_items(candidates: list[dict]) -> list[dict]:
    """A supplier candidate (schemas/supplier_candidate.json) is up to TWO claims about one listing: a price and a minimum
    order. Numbers come from the skill's OWN parsers (executors._parse_price / _parse_moq) — no second parser, and a
    policy default MOQ is never presented as an observed number."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import executors as _ex
    out = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        lo, hi = _ex._parse_price(c.get("price_raw", ""))
        moq = _ex._parse_moq(c.get("moq_raw", ""))
        base = {"source": c.get("url"), "retrieved_at": c.get("retrieved_at"), "hypothesis_ids": c.get("hypothesis_ids") or [],
                "community": c.get("supplier_name"), "source_identity": {"source_family": "supplier", "platform": str(c.get("channel") or "").lower()},
                "context": f"listing: {c.get('product_name')} · supplier: {c.get('supplier_name')} · price as listed: {c.get('price_raw')} · MOQ as listed: {c.get('moq_raw')}"
                           + (" · customizable" if c.get("customizable") else "")}
        if "published_at_if_known" in c:
            base["published_at_if_known"] = c["published_at_if_known"]
        name = _clip(c.get("product_name"), 300)
        if lo is not None:
            out.append({**base, "id": f"{c.get('id')}:price", "evidence_roles": ["PRICE_EVIDENCE"], "problem": f"{name}: listed unit price from USD {lo}" + (f" to {hi}" if hi not in (None, lo) else ""),
                        "quote_ref": str(c.get("price_raw") or ""), "metric": {"name": "unit_price_low", "value": lo, "unit": "USD"}})
        if moq:
            out.append({**base, "id": f"{c.get('id')}:moq", "evidence_roles": ["MOQ_EVIDENCE"], "problem": f"{name}: listed minimum order {moq} units",
                        "quote_ref": str(c.get("moq_raw") or ""), "metric": {"name": "minimum_order_quantity", "value": moq, "unit": "units"}})
        if lo is None and not moq:
            out.append({**base, "id": f"{c.get('id')}:listing", "evidence_roles": ["SUPPLIER_AVAILABILITY"], "problem": f"{name}: listed by {c.get('supplier_name')} (no parseable price or MOQ)",
                        "quote_ref": _clip(f"{c.get('price_raw')} / {c.get('moq_raw')}", EXCERPT_MAX)})
    return out


# ------------------------------------------------------------------- build --
def build_receipt(action: dict, *, observations: list | None = None, field_records: list | None = None,
                  supplier_candidates: list | None = None, harness_id: str, started_at: str, completed_at: str,
                  tool_trace: list | None = None, limitations: list | None = None) -> tuple[dict, dict]:
    """(receipt, report). Deterministic: same inputs -> same bytes. `report` says what was included, omitted (with the reason)
    and clamped; every omission and clamp is ALSO written into the receipt's `limitations`, so TrailSignal and the dossier
    see the same account the harness saw."""
    budget = action.get("budget") or {}
    max_sources = min(int(budget.get("max_sources") or SCHEMA_MAX["sources"]), SCHEMA_MAX["sources"])
    max_obs = min(int(budget.get("max_observations") or SCHEMA_MAX["observations"]), SCHEMA_MAX["observations"])
    action_hyps = [str(h) for h in action.get("hypothesis_ids") or []]
    intents = {str(i.get("intent_id")) for i in action.get("search_intents") or [] if isinstance(i, dict)}
    items = [dict(x, _lane="observation") for x in observations or [] if isinstance(x, dict)] \
        + [dict(x, _lane="field_record") for x in field_records or [] if isinstance(x, dict)] \
        + [dict(x, _lane="supplier_candidate") for x in _supplier_items(supplier_candidates or [])]
    sources: dict[str, dict] = {}
    pages: set[str] = set()
    page_dated_ids: set[str] = set()
    obs_out: list[dict] = []
    omitted: list[dict] = []
    notes: list[str] = []
    seen_ids: set[str] = set()
    for it in items:
        oid = str(it.get("id") or _sid("obs_", it.get("source"), it.get("quote_ref"), it.get("problem")))
        family = str((it.get("source_identity") or {}).get("source_family") or "").lower()
        why = ("corpus knowledge is not a harness observation" if family in NOT_FIELD_FAMILIES or it.get("corpus_row_id")
               else "a prior-run / field-corpus record carries no harvest provenance of THIS action" if it.get("origin") in ("PRIOR_RUN", "FIELD_CORPUS")
               else _harvest_problem(it))
        role = trail_role_for(it)
        url = str(it.get("source") or it.get("url") or "")
        cls = source_class_for(url, it.get("source_identity"))
        claim = _clip(it.get("claim") or it.get("problem"), CLAIM_MAX)
        excerpt = _clip(it.get("quote_ref") or it.get("paraphrase_or_excerpt"), EXCERPT_MAX)
        why = why or (None if role else f"no role TrailSignal admits in {sorted(map(str, it.get('evidence_roles') or []))}") \
            or (None if cls else "unknown source class (unregistered domain and no platform / family recorded)") \
            or (None if claim else "no claim") or (None if excerpt else "no verbatim quote or excerpt") \
            or ("duplicate observation id" if oid in seen_ids else None)
        if why:
            omitted.append({"id": oid, "lane": it["_lane"], "reason": why}); continue
        # ONE source row per (page, publish date): comments under one video each keep their OWN date (TrailSignal anchors
        # freshness on the source's date), and no item's date is lent to another. The budget counts pages, not rows. An item whose
        # own date is not shown (null; e.g. only "3 weeks ago") may carry its PAGE's publish date (`page_published_at`): the
        # earliest it can be, so TrailSignal never sees it fresher than it is (it dates an undated source at the moment of reading).
        page_date = it.get("page_published_at") if not it["published_at_if_known"] and _iso_ok(it.get("page_published_at")) else None
        source_date = it["published_at_if_known"] or page_date
        if page_date:
            page_dated_ids.add(oid[:200])
        sid = _sid("src_", url, source_date or "")
        if sid not in sources:
            if url not in pages and len(pages) >= max_sources:
                omitted.append({"id": oid, "lane": it["_lane"], "reason": f"source budget reached ({max_sources})"}); continue
            if len(sources) >= SCHEMA_MAX["sources"]:
                omitted.append({"id": oid, "lane": it["_lane"], "reason": f"source rows at the contract maximum ({SCHEMA_MAX['sources']})"}); continue
            pages.add(url)
            sources[sid] = {"source_id": sid, "url": url[:2000], "source_class": cls, "retrieved_at": it["retrieved_at"],
                            "published_at_if_known": source_date}
        if len(obs_out) >= max_obs:
            omitted.append({"id": oid, "lane": it["_lane"], "reason": f"observation budget reached ({max_obs})"}); continue
        tagged = [str(h) for h in it.get("hypothesis_ids") or []]
        foreign = [h for h in tagged if h not in action_hyps]
        if foreign:
            notes.append(f"{oid}: dropped hypothesis ids that are not in the action: {foreign[:4]}")
        seen_ids.add(oid)
        linked = [h for h in tagged if h in action_hyps][:64]
        relations = [{"hypothesis_id": str(r.get("hypothesis_id")), "relation": str(r.get("relation")).upper()} for r in (it.get("hypothesis_relations") or []) if isinstance(r, dict)]
        kept = [r for r in relations if r["hypothesis_id"] in linked and r["relation"] in ("SUPPORTS", "CONTRADICTS", "NEUTRAL")]
        if len(kept) != len(relations):
            notes.append(f"{oid}: dropped {len(relations) - len(kept)} relation(s) naming an unlinked hypothesis or an unknown relation")
        obs_out.append({"observation_id": oid[:200], "source_id": sid, "claim": claim, "paraphrase_or_excerpt": excerpt,
                        "metric_if_present": _metric(it), "context": _context(it), "evidence_role_claimed": role,
                        "hypothesis_ids": linked, **({"hypothesis_relations": kept} if kept else {})})       # ADR-069: stated, never inferred
    used = {o["source_id"] for o in obs_out}
    trace_acc: dict[tuple[str, str], int] = {}
    for row in tool_trace or []:
        if not isinstance(row, dict):
            continue
        iid, tool = str(row.get("search_intent_id") or ""), _clip(row.get("tool_class"), 100)
        if iid not in intents:
            notes.append(f"tool trace row for unknown search intent {iid!r} dropped (the action issued: {sorted(intents)[:6]})"); continue
        if not tool:
            notes.append(f"tool trace row for intent {iid!r} names no tool_class: dropped"); continue
        n = row.get("query_count")
        trace_acc[(iid, tool)] = trace_acc.get((iid, tool), 0) + (int(n) if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else 0)
    trace = [{"search_intent_id": i, "tool_class": t, "query_count": n} for (i, t), n in sorted(trace_acc.items())][:SCHEMA_MAX["tool_trace"]]
    queries = sum(r["query_count"] for r in trace)
    if budget.get("max_queries") is not None and queries > int(budget["max_queries"]):
        notes.append(f"BUDGET EXCEEDED: {queries} queries were run, the action allowed {int(budget['max_queries'])} (recorded as run, not rewritten)")
    by_reason: dict[str, int] = {}
    for o in omitted:
        by_reason[o["reason"]] = by_reason.get(o["reason"], 0) + 1
    lim = [_clip(x, LIMITATION_MAX) for x in limitations or [] if str(x or "").strip()]
    lim += [_clip(f"{n} harvested item(s) omitted from this receipt: {reason}", LIMITATION_MAX) for reason, n in sorted(by_reason.items())]
    lim += [_clip(n, LIMITATION_MAX) for n in notes]
    page_dated = sum(1 for o in obs_out if o["observation_id"] in page_dated_ids)
    if page_dated:
        lim.append(_clip(f"{page_dated} item(s) without a date of their own are dated by their page's publish date (page_published_at): "
                         "the earliest they can be", LIMITATION_MAX))
    if not obs_out:
        lim.append("no observation in this receipt: nothing harvested met the provenance contract (a finding, not a failure to hide)")
    receipt = {"action_id": action.get("action_id"), "run_id": action.get("run_id"), "harness_id": _clip(harness_id, 100),
               "started_at": started_at, "completed_at": completed_at,
               "sources": [s for sid, s in sources.items() if sid in used], "observations": obs_out,
               "tool_trace": trace, "limitations": lim[:SCHEMA_MAX["limitations"]]}
    report = {"action_id": action.get("action_id"), "action_kind": action.get("action_kind"), "items_in": len(items), "observations": len(obs_out),
              "sources": len(receipt["sources"]), "omitted": omitted, "omitted_by_reason": by_reason, "notes": notes, "queries_recorded": queries,
              "roles": {r: sum(1 for o in obs_out if o["evidence_role_claimed"] == r) for r in sorted({o["evidence_role_claimed"] for o in obs_out})},
              "source_classes": {c: sum(1 for s in receipt["sources"] if s["source_class"] == c) for c in sorted({s["source_class"] for s in receipt["sources"]})},
              "errors": validate_receipt(receipt, action)}
    return receipt, report


def _forbidden_keys(node, path="$") -> list[str]:
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if _FORBIDDEN_KEY.search(str(k)):
                out.append(f"{path}.{k}")
            out += _forbidden_keys(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _forbidden_keys(v, f"{path}[{i}]")
    return out


def validate_receipt(receipt: dict, action: dict | None = None) -> list[str]:
    """Contract violations (empty = the adapter's `adapter_submit kind=receipt` provenance check will accept it):
    the byte-copied JSON Schema, the action binding the adapter enforces (action_id, run_id), and this skill's own laws
    (every observation's source is listed; hypothesis ids are a subset of the action's; intents are the action's;
    no score / rank / weight key anywhere)."""
    errs = schema_errors(receipt, load_schema())
    if not isinstance(receipt, dict):
        return errs
    srcs = {s.get("source_id") for s in receipt.get("sources") or [] if isinstance(s, dict)}
    for o in receipt.get("observations") or []:
        if isinstance(o, dict) and o.get("source_id") not in srcs:
            errs.append(f"observation {o.get('observation_id')!r}: source {o.get('source_id')!r} is not listed in sources")
    errs += [f"forbidden key {k} (a receipt carries no score, rank or weight)" for k in _forbidden_keys(receipt)]
    if action:
        if receipt.get("action_id") != action.get("action_id"):
            errs.append(f"action_id {receipt.get('action_id')!r} is not the issued action {action.get('action_id')!r}")
        if receipt.get("run_id") != action.get("run_id"):
            errs.append("run_id does not match the action's run")
        hyps = set(map(str, action.get("hypothesis_ids") or []))
        intents = {str(i.get("intent_id")) for i in action.get("search_intents") or [] if isinstance(i, dict)}
        for o in receipt.get("observations") or []:
            bad = [h for h in (o.get("hypothesis_ids") or []) if h not in hyps] if isinstance(o, dict) else []
            if bad:
                errs.append(f"observation {o.get('observation_id')!r}: hypothesis ids outside the action {bad[:3]}")
        for t in receipt.get("tool_trace") or []:
            if isinstance(t, dict) and t.get("search_intent_id") not in intents:
                errs.append(f"tool trace intent {t.get('search_intent_id')!r} is not one the action issued")
    return errs


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------- cli --
def _load(path: str | None, key: str | None = None):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and key and key in data:
        return data[key]
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="adapter_receipt")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="HarnessActionV1 + what this skill harvested -> HarnessResearchReceiptV1")
    b.add_argument("--action", required=True, help="the step's `harness_action` (HarnessActionV1) as issued by adapter_next — or the whole adapter_next payload")
    b.add_argument("--observations", help="JSON list (or {observations:[…]}) of schemas/observation.json items + harvest provenance")
    b.add_argument("--field-records", dest="field_records", help="JSON list (or {field_records:[…]}) of schemas/field_record.json items + harvest provenance")
    b.add_argument("--supplier-candidates", dest="supplier_candidates", help="JSON list (or {supplier_candidates:[…]}) of schemas/supplier_candidate.json items + harvest provenance")
    b.add_argument("--tool-trace", dest="tool_trace", help="JSON list of {search_intent_id, tool_class, query_count}")
    b.add_argument("--harness-id", required=True, dest="harness_id")
    b.add_argument("--started-at", required=True, dest="started_at")
    b.add_argument("--completed-at", dest="completed_at", default=None, help="default: now (the moment the receipt is built)")
    b.add_argument("--limitation", action="append", default=[], help="repeatable: a limitation the harness wants on the record")
    b.add_argument("--out", required=True)
    b.add_argument("--strict", action="store_true", help="exit 2 when anything was omitted, clamped or dropped")
    v = sub.add_parser("validate")
    v.add_argument("--receipt", required=True)
    v.add_argument("--action")
    args = ap.parse_args(argv)
    if args.cmd == "validate":
        action = _load(args.action)
        action = (((action or {}).get("step") or {}).get("harness_action") or (action or {}).get("harness_action") or action) if action else None
        errs = validate_receipt(_load(args.receipt), action)
        print(json.dumps({"ok": not errs, "errors": errs, "schema_sha256": schema_sha256()}, indent=1))
        return 0 if not errs else 1
    action = _load(args.action)
    action = ((action.get("step") or {}).get("harness_action") or action.get("harness_action") or action)
    receipt, report = build_receipt(action, observations=_load(args.observations, "observations"), field_records=_load(args.field_records, "field_records"),
                                    supplier_candidates=_load(args.supplier_candidates, "supplier_candidates"), harness_id=args.harness_id,
                                    started_at=args.started_at, completed_at=args.completed_at or now_iso(), tool_trace=_load(args.tool_trace, "tool_trace"),
                                    limitations=args.limitation)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: report[k] for k in ("action_id", "action_kind", "items_in", "observations", "sources", "omitted_by_reason", "roles", "source_classes", "queries_recorded", "notes", "errors")}, ensure_ascii=False), file=sys.stderr)
    if report["errors"]:
        return 1
    return 2 if args.strict and (report["omitted"] or report["notes"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
