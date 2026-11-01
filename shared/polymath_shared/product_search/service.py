"""PRODUCT SEARCH (product-search-v1): the product turn's supplier lookups and the `product_research` block every product turn
carries (PRODUCT-SEARCH-E2E; the owner's decisions of 2026-11-01).

The default for a product question is Polymath's OWN answer: product hypotheses formed from the chosen corpus, CJ Dropshipping finds
per hypothesis, ending with an OFFER of the full governed research run (`ecommerce.product_research`) — never started here, and
always driven by the user's agent. Per hypothesis:
  * CJ: ONE `supplier.search` (CJ's official API, paced by the CJ client, at most MAX_LOOKUPS a turn, run one after another) as the
    turn's principal (`principal_context.current()`; None = the owner / a trusted local caller). Items are FLATTENED to the
    documented names (ITEM_FIELDS, from the shaped item's `listing` and its source's URL; a missing field is null, never invented),
    the same product is kept once across hypotheses, and S1's `fallback` (the user's own Agent Reach) is passed through UNCHANGED.
    A refusal (`AcquisitionRefused`: a fair-use limit, a principal not allowed) or any other failure degrades to a typed
    UNAVAILABLE entry with a fallback — it never fails the turn.
  * Alibaba: nothing is searched on this host ("alibaba is strictly agent reach"): AGENT_REACH_REQUIRED with the commands
    (`agent_reach.fallback`, built here without spending a supplier call).
The block also states its limitations (a listing proves supply, not demand), the offer of the full run (with the turn's
`corpus_ids`, which a friend's adapter start requires), the Agent Reach install facts and receipts (counts and statuses only).
`ProductTurn` is what the chat runtime (`orchestrator/api/ui.py`) and `POST /product/search` drive. Pure apart from the injected
`search` callable (default `polymath_shared.acquisition.supplier.search`)."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from polymath_shared.product_search import hypotheses as H
from polymath_shared.product_search.intent import ProductIntent, _geography, _norm

CONTRACT = "product-search-v1"
ADAPTER_ID = "ecommerce.product_research"
MAX_HYPOTHESES = H.MAX_HYPOTHESES
MAX_LOOKUPS = 5                    # CJ searches a turn: CJ allows about one call a second per key
MAX_TERM_LOOKUPS = 3               # turns without hypotheses search the request's own terms
DEFAULT_LIMIT, MAX_LIMIT = 6, 10   # CJ items per hypothesis
THIN_EVIDENCE = 3                  # fewer passages than this = thin evidence
MD_ITEMS = 3                       # finds shown per hypothesis in the answer text
EVIDENCE_TEXT, EVIDENCE_ROWS = 400, 16
CJ_SITE, ALIBABA_SITE = "cjdropshipping.com", "alibaba.com"
VERDICT, VERDICT_THIN, VERDICT_TERMS = "product_hypotheses", "product_hypotheses_thin", "product_terms_only"
AGENT_REACH_REPO = "https://github.com/Panniantong/Agent-Reach"
AGENT_REACH_VERIFY = "agent-reach doctor --json"
NO_TERMINAL_NOTE = ("web-link and claude.ai users get CJ API results only; the Agent Reach fallback needs an agent running on your "
                    "own device")
SUPPLY_NOT_DEMAND = "a listing proves supply, not demand: a CJ listing never shows that people want or buy the product"
HYPOTHESES_NOT_FACTS = ("the product hypotheses are inferences from the library's passages, labelled as hypotheses: they are not facts "
                        "the library states and not products it recommends")
ALIBABA_LOCAL = "alibaba.com is read only by your own Agent Reach on your own device, never by the Polymath host"
#: the documented item fields (product-search-v1) <- the shaped supplier item's `listing` (cj_api.listing_record via service.shape)
ITEM_FIELDS = ("title", "price", "discount_price", "moq", "image", "url", "product_id", "sku", "category", "stores_listing",
               "warehouse_stock", "supplier")
LISTING_FIELDS = {"title": "title", "price": "price_as_listed", "discount_price": "discount_price_as_listed",
                  "moq": "minimum_order_as_listed", "image": "image", "product_id": "product_id", "sku": "sku", "category": "category",
                  "stores_listing": "listed_by_stores", "warehouse_stock": "warehouse_inventory", "supplier": "supplier"}
LISTED_STATUSES = ("OK", "PARTIAL")
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+!|<>~])")


def agent_reach_block() -> dict[str, Any]:
    return {"local_only": True, "install": {"repo": AGENT_REACH_REPO, "verify": AGENT_REACH_VERIFY}, "no_terminal_note": NO_TERMINAL_NOTE}


# ------------------------------------------------------------------------------------------------------------- lookups --
def _default_search() -> Callable[..., dict]:
    from polymath_shared.acquisition import supplier
    return supplier.search


def fallback_for(site: str, query: str | None, reason_code: str, why: str) -> dict[str, Any]:
    """The user-side Agent Reach handoff, built by the acquisition layer's own `agent_reach.fallback` (its `commands` are objects
    {step, run, what, then, for_each?}); a typed placeholder with the same keys when that module cannot build one here."""
    build_error = "agent_reach.fallback returned no handoff"
    try:
        from polymath_shared.acquisition import agent_reach
        built = agent_reach.fallback(site, query, reason_code, why)
        if isinstance(built, dict):
            return built
    except Exception as exc:  # noqa: BLE001 — the handoff is advice; a build failure must never fail the turn
        build_error = f"{type(exc).__name__}: {str(exc)[:160]}"
    return {"kind": "AGENT_REACH", "reason_code": reason_code, "why": why, "site": site, "query": query, "run_on": "your machine",
            "never": "do not use your agent's built-in web search or web fetch for this",
            "install": {"repo": AGENT_REACH_REPO, "verify": AGENT_REACH_VERIFY}, "commands": [],
            "submit": {"tool": "supplier_parse", "route": "POST /supplier/parse"}, "placeholder": True,
            "build_error": build_error}


def item_view(raw: Mapping[str, Any], sources_by_id: Mapping[str, Any]) -> dict[str, Any]:
    """One supplier_search item in the documented names. The shaped item nests CJ's fields under `listing`
    (price_as_listed, minimum_order_as_listed, listed_by_stores, warehouse_inventory, ...) and keeps its URL on its source row; a
    flat item is read under the documented names. A missing field is null."""
    listing = raw.get("listing") if isinstance(raw.get("listing"), Mapping) else {}
    out: dict[str, Any] = {}
    for name in ITEM_FIELDS:
        value = listing.get(LISTING_FIELDS[name]) if name in LISTING_FIELDS else None
        if value in (None, "") and raw.get(name) not in (None, ""):
            value = raw.get(name)
        out[name] = value if value not in ("",) else None
    url = raw.get("url") or (sources_by_id.get(raw.get("source_id")) or {}).get("url")
    out["url"] = url if isinstance(url, str) and url.startswith(("https://", "http://")) else None
    return out


def _not_searched(term: str | None, why: str) -> dict[str, Any]:
    return {"status": "NOT_SEARCHED", "search_term": term, "items": [], "fallback": None, "reason_code": "NOT_SEARCHED", "note": why}


def cj_lookup(term: str, *, principal_id: str | None, limit: int, search: Callable[..., dict]) -> dict[str, Any]:
    """{status, search_term, items, fallback, reason_code, limitations}: one CJ search as the turn's principal."""
    from polymath_shared.acquisition.service import AcquisitionRefused
    try:
        res = search(principal_id=principal_id, query=term, source="cj", limit=limit)
    except AcquisitionRefused as exc:
        why = f"the supplier search refused this call ({exc.code}: {exc.message})"
        return {"status": "UNAVAILABLE", "search_term": term, "items": [], "reason_code": exc.code,
                "refused": {"code": exc.code, "status": exc.status, "message": exc.message},
                "fallback": fallback_for(CJ_SITE, term, exc.code, why + ". Your own Agent Reach can search cjdropshipping.com meanwhile"),
                "limitations": [why]}
    except Exception as exc:  # noqa: BLE001 — a lookup failure degrades the find, never the turn
        why = f"the CJ supplier search failed on this host ({type(exc).__name__})"
        return {"status": "UNAVAILABLE", "search_term": term, "items": [], "reason_code": "CJ_ERROR",
                "fallback": fallback_for(CJ_SITE, term, "CJ_ERROR", why), "limitations": [why]}
    res = res if isinstance(res, Mapping) else {}
    status = str(res.get("status") or "UNAVAILABLE").upper()
    sources = {s.get("source_id"): s for s in res.get("sources") or [] if isinstance(s, Mapping) and s.get("source_id")}
    items = [item_view(i, sources) for i in res.get("items") or [] if isinstance(i, Mapping)][:limit]
    fallback = res.get("fallback") if isinstance(res.get("fallback"), Mapping) else None
    code = res.get("reason_code")
    if fallback is None and status not in LISTED_STATUSES:
        code = code or ("CJ_EMPTY" if status == "EMPTY" else "CJ_UNAVAILABLE")
        why = next((str(x) for x in res.get("limitations") or [] if x), f"CJ answered {status}")
        fallback = fallback_for(CJ_SITE, term, str(code), why)
    return {"status": status, "search_term": term, "items": items, "fallback": fallback, "reason_code": code,
            "limitations": [str(x) for x in (res.get("limitations") or []) if x]}


def alibaba_handoff(term: str | None) -> dict[str, Any]:
    if not term:
        return {"status": "NOT_SEARCHED", "search_term": None, "reason_code": "NOT_SEARCHED", "fallback": None}
    return {"status": "AGENT_REACH_REQUIRED", "search_term": term, "reason_code": "ALIBABA_AGENT_REACH_ONLY",
            "fallback": fallback_for(ALIBABA_SITE, term, "ALIBABA_AGENT_REACH_ONLY", ALIBABA_LOCAL)}


class _Lookups:
    """One turn's CJ searches: each term at most once, at most `cap` searches, every product kept once across the turn."""

    def __init__(self, *, principal_id: str | None, limit: int, search: Callable[..., dict], cap: int):
        self.principal_id, self.limit, self.search, self.cap = principal_id, limit, search, cap
        self.results: dict[str, dict[str, Any]] = {}
        self.seen: set[str] = set()
        self.deduped = 0
        self.skipped_cap = 0
        self.notes: list[str] = []

    def find(self, terms: list[str]) -> dict[str, Any]:
        """The CJ entry for a hypothesis: its first term not yet searched this turn, else the earlier result for its first term."""
        if not terms:
            return _not_searched(None, "no search term")
        term = next((t for t in terms if t not in self.results), None)
        if term is None:
            cj = dict(self.results[terms[0]])
        elif len(self.results) >= self.cap:
            self.skipped_cap += 1
            return _not_searched(term, f"only {self.cap} CJ searches run a turn (CJ allows about one call a second): search it "
                                       "with supplier_search or product_search")
        else:
            cj = cj_lookup(term, principal_id=self.principal_id, limit=self.limit, search=self.search)
            self.results[term] = cj
            self.notes += cj.pop("limitations", [])
            cj = dict(cj)
        kept = []
        for item in cj.get("items") or []:
            key = str(item.get("product_id") or item.get("url") or item.get("title") or "")
            if key and key in self.seen:
                self.deduped += 1
                continue
            if key:
                self.seen.add(key)
            kept.append(item)
        cj["items"] = kept
        cj.pop("limitations", None)
        return cj


# ----------------------------------------------------------------------------------------------------------- the block --
def seed_for(intent: ProductIntent, message: str) -> str:
    """The full research run's seed: the request's own seed (with its audience), else "products for <audience>", else the
    user's words as written (the adapter wants 3 to 2000 characters)."""
    if intent.seed and intent.audience and intent.audience not in intent.seed:
        seed = f"{intent.seed} for {intent.audience}"
    elif intent.seed:
        seed = intent.seed
    elif intent.audience:
        seed = f"products for {intent.audience}"
    else:
        seed = " ".join(str(message or "").split())
    seed = seed[:2000]
    return seed if len(seed) >= 3 else "product opportunities from this library"


def next_block(intent: ProductIntent, corpus_ids: list[str], message: str, *, hypotheses_from: str | None = None) -> dict[str, Any]:
    """`next`: the OFFER of the full governed run (never started here; the user's agent drives it), plus — on a turn that formed no
    hypotheses — how to get them (`model`: ask again with a model or call product_search; `agent`: form them from the evidence)."""
    run_input: dict[str, Any] = {"seed": seed_for(intent, message), "corpus_ids": list(corpus_ids)}
    if intent.geography:
        run_input["geography"] = intent.geography
    out: dict[str, Any] = {"full_research": {
        "tool": "adapter_start", "adapter_id": ADAPTER_ID, "input": run_input, "request_options": {"corpus_ids": list(corpus_ids)},
        "who_drives": "your agent", "auto_start": False,
        "note": ("An offer, never started automatically. If the user wants it, your agent starts the governed research run "
                 "(adapter_start), then answers every step itself (adapter_next / adapter_submit, until adapter_result); Polymath "
                 "never answers its reasoning steps. Its research steps use the user's local Agent Reach.")}}
    if hypotheses_from == "model":
        out["hypotheses"] = {
            "how": "ask_with_model_or_product_search",
            "why": "this answer was written without a language model, so no product hypotheses were formed from the library",
            "product_search": {"tool": "product_search", "route": "POST /product/search",
                               "input": {"message": message, "corpus_id": corpus_ids[0] if len(corpus_ids) == 1 else None}},
            "chat": {"route": "POST /chat", "set": {"synthesizer": "<a model id from polymath_models / GET /synthesizers>"}}}
    elif hypotheses_from == "agent":
        out["hypotheses"] = {
            "how": "agent_forms_then_product_search",
            "why": "an evidence-only turn returns evidence, not an answer: you form the hypotheses (see agent_steps)",
            "product_search": {"tool": "product_search", "route": "POST /product/search",
                               "input": {"message": message, "corpus_id": corpus_ids[0] if len(corpus_ids) == 1 else None,
                                         "hypotheses": [{"title": "<product name>", "search_terms": ["<2-4 word search>"]}]}}}
    return out


def _statuses(entries: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str((e.get(key) or {}).get("status") or "NONE") for e in entries).items()))


def build_block(intent: ProductIntent, *, corpus_ids: list[str], message: str, hypotheses: list[dict[str, Any]],
                term_finds: list[dict[str, Any]] | None = None, lookups: _Lookups | None = None, parse=None,
                verdict: str | None = None, steer: Mapping[str, Any] | None = None, hypotheses_from: str | None = None,
                routing: Mapping[str, Any] | None = None,
                extra_limitations: Iterable[str] = ()) -> dict[str, Any]:
    """The product_research block (product-search-v1)."""
    term_finds = list(term_finds) if term_finds is not None else None
    entries = list(hypotheses) + list(term_finds or [])
    limitations = [SUPPLY_NOT_DEMAND]
    if hypotheses:
        limitations.append(HYPOTHESES_NOT_FACTS)
    if intent.geography:
        limitations.append(f"CJ listings are not filtered by country: check stock and shipping to {intent.geography} with "
                           "supplier_product and supplier_freight before relying on a find")
    limitations.append("Alibaba is never searched from the Polymath host: each entry carries the Agent Reach commands to run on "
                       "your own device")
    failed = sum(1 for e in entries if (e.get("cj") or {}).get("status") not in (*LISTED_STATUSES, "EMPTY", "NOT_SEARCHED"))
    if failed:
        limitations.append(f"CJ could not be searched for {failed} of {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}: each "
                           "has a `fallback` with the reason and the Agent Reach commands")
    if lookups is not None and lookups.skipped_cap:
        limitations.append(f"only {lookups.cap} CJ searches run a turn: {lookups.skipped_cap} entr"
                           f"{'y was' if lookups.skipped_cap == 1 else 'ies were'} not searched (status NOT_SEARCHED)")
    limitations += [str(x) for x in extra_limitations if x]
    if lookups is not None:
        limitations += list(dict.fromkeys(lookups.notes))[:4]
    block: dict[str, Any] = {
        "contract": CONTRACT,
        "intent": {"kind": intent.kind, "seed": intent.seed, "audience": intent.audience, "geography": intent.geography,
                   "rule": intent.rule},
        "corpus_ids": list(corpus_ids),
        "hypotheses": list(hypotheses),
        **({"term_finds": term_finds} if term_finds is not None else {}),
        "limitations": list(dict.fromkeys(limitations)),
        "next": next_block(intent, corpus_ids, message, hypotheses_from=hypotheses_from),
        "agent_reach": agent_reach_block(),
        "receipts": {"lookups": len(lookups.results) if lookups is not None else 0,
                     "statuses": {"cj": _statuses(entries, "cj"), "alibaba": _statuses(entries, "alibaba")},
                     "deduped": lookups.deduped if lookups is not None else 0,
                     "parse": parse.receipt() if parse is not None else {"status": "not_run"},
                     **({"steer": dict(steer)} if steer else {}),
                     **({"routing": dict(routing)} if routing else {})},
    }
    if verdict:
        block["verdict"] = verdict
    return block


def verdict_for(hypotheses: list[dict[str, Any]], *, evidence_count: int, parse_status: str | None) -> str:
    """product_hypotheses, or product_hypotheses_thin when the evidence is thin: fewer than THIN_EVIDENCE passages, a block that
    could not be read, or fewer than half of the hypotheses citing a passage."""
    cited = sum(1 for h in hypotheses if h.get("evidence_tags"))
    if not hypotheses or parse_status == "fallback" or evidence_count < THIN_EVIDENCE or cited * 2 < len(hypotheses):
        return VERDICT_THIN
    return VERDICT


def _md(text: Any) -> str:
    """Supplier and model text made inert in Markdown: no link, image, emphasis, HTML or [S#] tag can be smuggled in."""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(str(text or "").split()))


def _md_url(url: Any) -> str | None:
    u = str(url or "").strip()
    if not u.startswith(("https://", "http://")):
        return None
    return u.replace(" ", "%20").replace("(", "%28").replace(")", "%29").replace("<", "%3C").replace(">", "%3E")


_STATUS_WORDS = {"EMPTY": "no CJ listing matched", "UNAVAILABLE": "CJ could not be searched from here",
                 "AGENT_REACH_REQUIRED": "this search runs through Agent Reach on your own device",
                 "NOT_SEARCHED": "not searched this turn", "HUMAN_ACTION_REQUIRED": "CJ asked for a human check"}


def _item_line(item: Mapping[str, Any]) -> str:
    title = _md(item.get("title") or "untitled listing")
    url = _md_url(item.get("url"))
    head = f"[{title}]({url})" if url else title
    facts = [x for x in (
        _md(item.get("price")) if item.get("price") else None,
        f"discount {_md(item.get('discount_price'))}" if item.get("discount_price") else None,
        f"min. order {_md(item.get('moq'))}" if item.get("moq") else None,
        f"listed by {_md(item.get('stores_listing'))} stores" if item.get("stores_listing") else None,
        f"CJ stock {_md(item.get('warehouse_stock'))}" if item.get("warehouse_stock") else None) if x]
    return f"   - {head}" + (f" — {' · '.join(facts)}" if facts else "")


def _entry_lines(n: int, label: str, tags: list[str], cj: Mapping[str, Any]) -> list[str]:
    head = f"{n}. **{_md(label)}**"
    if tags:
        head += " — from " + ", ".join(f"[{t}]" for t in tags)
    term = cj.get("search_term")
    items = list(cj.get("items") or [])
    status = str(cj.get("status") or "")
    if items:
        lines = [head + (f" — CJ search “{_md(term)}”:" if term else ":")]
        lines += [_item_line(i) for i in items[:MD_ITEMS]]
        if len(items) > MD_ITEMS:
            lines.append(f"   - and {len(items) - MD_ITEMS} more in the answer data")
        return lines
    words = _STATUS_WORDS.get(status, f"CJ answered {_md(status) or 'nothing'}")
    tail = "; the Agent Reach fallback in the answer data runs it on your own device" if cj.get("fallback") else ""
    return [head + (f" — CJ search “{_md(term)}”: " if term else " — ") + words + tail]


def finds_markdown(block: Mapping[str, Any], legend_tags: Iterable[str] | None = None) -> str:
    """The short Markdown section appended to a product turn's answer text: each hypothesis (or search term) with its top CJ
    finds, then the offer of the full run — so a UI or agent that ignores `product_research` still sees the finds."""
    legend = set(legend_tags) if legend_tags is not None else None
    hyps = list(block.get("hypotheses") or [])
    terms = list(block.get("term_finds") or [])
    lines = ["### Supplier finds (CJ Dropshipping)", ""]
    if hyps:
        lines += ["Each product hypothesis above, searched on CJ Dropshipping. A listing proves supply, not demand.", ""]
        for n, h in enumerate(hyps, 1):
            tags = [t for t in h.get("evidence_tags") or [] if legend is None or t in legend]
            lines += _entry_lines(n, str(h.get("title") or f"hypothesis {n}"), tags, h.get("cj") or {})
    elif terms:
        unread = ((block.get("receipts") or {}).get("parse") or {}).get("status") == "fallback"
        lines += [("The hypotheses above could not be read back as data, so CJ Dropshipping was searched with the request's own "
                   "terms. A listing proves supply, not demand." if unread else
                   "No product hypotheses were formed on this turn; CJ Dropshipping was searched with the request's own terms. A "
                   "listing proves supply, not demand."), ""]
        for n, t in enumerate(terms, 1):
            lines += _entry_lines(n, f"Search: {t.get('search_term') or ''}", [], t.get("cj") or {})
    else:
        lines += ["Nothing was searched on CJ Dropshipping this turn: no product hypothesis and no search term came out of it.", ""]
    lines += ["", "*The full governed research run (`ecommerce.product_research`) is offered, not started: if you want it, your agent "
                  "starts it with `adapter_start` and drives every step.*"]
    return "\n".join(lines)


def summary(block: Mapping[str, Any] | None, verdict: str | None = None) -> dict[str, Any] | None:
    """The receipt's `product_search` meta: counts and statuses only, never item text."""
    if not block:
        return None
    rec = block.get("receipts") or {}
    entries = list(block.get("hypotheses") or []) + list(block.get("term_finds") or [])
    intent = block.get("intent") or {}
    return {"contract": CONTRACT, "kind": intent.get("kind"), "rule": intent.get("rule"), "verdict": verdict or block.get("verdict"),
            "hypotheses": len(block.get("hypotheses") or []), "term_finds": len(block.get("term_finds") or []),
            "lookups": rec.get("lookups", 0), "items": sum(len((e.get("cj") or {}).get("items") or []) for e in entries),
            "statuses": rec.get("statuses"), "deduped": rec.get("deduped", 0), "parse": (rec.get("parse") or {}).get("status"),
            "steer": (rec.get("steer") or {}).get("mode"), "corpora": len(block.get("corpus_ids") or []),
            **({"routing": {"method": rec["routing"].get("method"), "candidates": len(rec["routing"].get("candidates") or [])}}
               if isinstance(rec.get("routing"), Mapping) else {})}


def agent_steps(block: Mapping[str, Any]) -> list[str]:
    """Plain instructions for an agent on an evidence-only product turn (MCP polymath_search / polymath_explore)."""
    corpora = list(block.get("corpus_ids") or [])
    cid = corpora[0] if len(corpora) == 1 else "<one corpus_id>"
    return [
        "Form 3 to 5 product hypotheses from this packet's evidence: for each, a short product name, the problem it solves and for "
        "whom, and the evidence it rests on (cite the packet's chunk_id values). The library need not name products: read it for "
        "frictions, workarounds, unmet jobs, audiences, recurring complaints and use situations. Label them as hypotheses, never as "
        "facts or as products the library recommends.",
        f"Call product_search with message = the user's words, corpus_id = {cid} and hypotheses = [{{title, search_terms}}] (1 to 3 "
        "short catalogue searches each, 2 to 4 plain words): Polymath searches CJ Dropshipping for each and returns the finds, with "
        "an Agent Reach fallback wherever CJ cannot answer.",
        "Relay the hypotheses with their finds and product_research.limitations: a listing proves supply, not demand.",
        "End by offering the full governed research run (product_research.next.full_research): never start it unasked; if the user "
        "accepts, you drive every step yourself (adapter_next / adapter_submit until adapter_result).",
        "Live web reads (Alibaba always, CJ when its API fails) go only through the user's local Agent Reach on their own device, "
        "never your built-in web search or web fetch; a user without a terminal gets the CJ API results only.",
    ]


def compact_evidence(legend: Iterable[Mapping[str, Any]], text_of: Callable[[str], str | None] | None = None,
                     previews: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """/product/search's `evidence`: per [S#] passage its tag, chunk id, source and at most EVIDENCE_TEXT characters of its text
    (`text_of(chunk_id)`, else the inventory preview by locator)."""
    rows = []
    for e in list(legend or [])[:EVIDENCE_ROWS]:
        cid = e.get("chunk_id")
        text = None
        if text_of is not None and cid:
            try:
                text = text_of(str(cid))
            except Exception:  # noqa: BLE001 — a text the resolver cannot give falls back to the preview
                text = None
        text = text or (previews or {}).get(str(e.get("locator") or "")) or ""
        rows.append({"tag": e.get("tag"), "chunk_id": cid, "source": e.get("breadcrumb") or e.get("doc_id") or None,
                     "text": " ".join(str(text).split())[:EVIDENCE_TEXT]})
    return rows


def normalize_geography(value: Any) -> str | None:
    """A request's geography: a two-letter code (upper-cased), EU, or a place name read like the intent reads one; else the
    trimmed text itself (the adapter takes any string). None when empty."""
    text = " ".join(str(value or "").split())[:60]
    if not text:
        return None
    if re.fullmatch(r"[A-Za-z]{2}", text):
        return "GB" if text.upper() == "UK" else text.upper()
    return _geography(text, _norm(text)) or text


def _limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(n, MAX_LIMIT))


class ProductTurn:
    """One turn in product mode: the intent, the retrieval steering, the synthesis contract, the read-back of the hypothesis block,
    the CJ / Alibaba lookups and the product_research block. The chat runtime and POST /product/search drive it."""

    def __init__(self, intent: ProductIntent, *, message: str, corpus_ids: Iterable[str] = (), principal_id: str | None = None,
                 options: Mapping[str, Any] | None = None, search: Callable[..., dict] | None = None):
        opts = dict(options or {})
        geo = normalize_geography(opts.get("geography"))
        if geo:
            from dataclasses import replace
            intent = replace(intent, geography=geo)
        self.intent = intent
        self.message = message or ""
        self.corpus_ids = list(corpus_ids or [])
        self.principal_id = principal_id
        self.limit = _limit(opts.get("limit_per_hypothesis")) if opts.get("limit_per_hypothesis") is not None else DEFAULT_LIMIT
        self._search = search
        self.steer: dict[str, Any] | None = None
        self.parse: H.HypothesisParse | None = None
        self.block: dict[str, Any] | None = None
        self.verdict: str | None = None
        self.routing: dict[str, Any] | None = None

    # -- retrieval and synthesis
    def steer_plan(self, plan):
        """The plan with the product aspects (on a copy: a steering failure leaves the compiled plan exactly as it was, and the
        receipt says so)."""
        import copy
        try:
            steered, self.steer = H.steer_plan(copy.deepcopy(plan), self.intent)
            return steered
        except Exception as exc:  # noqa: BLE001 — steering is additive; the turn keeps its compiled plan
            self.steer = {"mode": "failed", "error": type(exc).__name__}
            return plan

    def steer_text(self, query: str) -> str:
        try:
            text, self.steer = H.steer_text(query, self.intent)
            return text
        except Exception as exc:  # noqa: BLE001
            self.steer = {"mode": "failed", "error": type(exc).__name__}
            return query

    def contract(self) -> str:
        return H.contract_block(self.intent)

    def route(self, candidates: Iterable[str], *, embed=None, role_scope=None, **deps: Any) -> str | None:
        """Several libraries in scope: pick the best one for this request (product-library-routing-v1) and keep it as the turn's
        library; the receipt rides `product_research.receipts.routing`. Returns the chosen library (None with no candidate)."""
        from polymath_shared.product_search import routing as R
        try:
            self.routing = R.route_library(self.message, candidates, embed=embed, role_scope=role_scope, **deps)
        except Exception as exc:  # noqa: BLE001 — routing never fails the turn: the first candidate by id, receipted
            ranked = sorted(dict.fromkeys(str(c) for c in candidates if c))
            self.routing = {"contract": R.CONTRACT, "candidates": ranked, "chosen": ranked[0] if ranked else None,
                            "runner_up": ranked[1] if len(ranked) > 1 else None, "scores": {}, "method": "first_candidate",
                            "notes": [f"routing failed ({type(exc).__name__})"]}
        chosen = self.routing.get("chosen")
        if chosen:
            self.corpus_ids = [chosen]
        return chosen


    def read_answer(self, answer_text: str, legend: Iterable[Mapping[str, Any]]) -> str:
        """Parse the answer's hypothesis block; returns the answer text without it."""
        self.parse = H.parse_block(answer_text, [e.get("tag") for e in legend or [] if e.get("tag")])
        return self.parse.clean_text

    def planned_lookups(self) -> int:
        hyps = self.parse.hypotheses if self.parse is not None and self.parse.hypotheses else None
        n = len(hyps) if hyps else len(self.intent.search_terms)
        return min(n, MAX_LOOKUPS if hyps else MAX_TERM_LOOKUPS)

    # -- lookups
    def _lookups(self, cap: int) -> _Lookups:
        return _Lookups(principal_id=self.principal_id, limit=self.limit, search=self._search or _default_search(), cap=cap)

    def _with_finds(self, hypotheses: list[dict[str, Any]], look: _Lookups) -> list[dict[str, Any]]:
        out = []
        for h in hypotheses[:MAX_HYPOTHESES]:
            cj = look.find(list(h.get("search_terms") or []))
            out.append({**h, "cj": cj, "alibaba": alibaba_handoff(cj.get("search_term") or (h.get("search_terms") or [None])[0])})
        return out

    def _term_finds(self, look: _Lookups) -> list[dict[str, Any]]:
        out = []
        for term in list(self.intent.search_terms)[:MAX_TERM_LOOKUPS]:
            cj = look.find([term])
            out.append({"search_term": term, "cj": cj, "alibaba": alibaba_handoff(term)})
        return out

    # -- the three runtime ends and the agent-hypotheses route
    def finish_llm(self, *, legend: list[Mapping[str, Any]]) -> tuple[dict[str, Any], str, str]:
        """(block, verdict, Markdown) for an LLM-synthesised product turn."""
        parse = self.parse or H.parse_block("", None)
        tags = [e.get("tag") for e in legend if e.get("tag")]
        look = self._lookups(MAX_LOOKUPS)
        extra: list[str] = []
        if parse.hypotheses:
            verdict = verdict_for(parse.hypotheses, evidence_count=len(legend), parse_status=parse.status)
            hyps = [dict(h) for h in parse.hypotheses]
            if verdict == VERDICT_THIN:
                for h in hyps:
                    if len(legend) < THIN_EVIDENCE or not h.get("evidence_tags"):
                        h["confidence"] = "low"
                extra.append("the library's evidence for these hypotheses is thin: treat them as low-confidence")
            hyps = self._with_finds(hyps, look)
            terms: list[dict[str, Any]] | None = None
        else:
            verdict = VERDICT_THIN
            hyps = []
            extra.append(f"the answer's machine-readable hypothesis block could not be read ({parse.reason}): CJ was searched with "
                         "the request's own terms instead; the hypotheses are in the answer text")
            terms = self._term_finds(look)
        self.verdict = verdict
        self.block = build_block(self.intent, corpus_ids=self.corpus_ids, message=self.message, hypotheses=hyps, term_finds=terms,
                                 lookups=look, parse=parse, verdict=verdict, steer=self.steer, extra_limitations=extra,
                                 routing=self.routing)
        return self.block, verdict, finds_markdown(self.block, tags)

    def finish_deterministic(self, answer: Mapping[str, Any]) -> dict[str, Any]:
        """The deterministic synthesizer's answer (/chat without a model, MCP `ask`) with the product block: its claims and
        citations unchanged, CJ searched with the request's own terms, `next` saying how to get hypotheses."""
        look = self._lookups(MAX_TERM_LOOKUPS)
        terms = self._term_finds(look)
        self.verdict = VERDICT_TERMS
        self.block = build_block(self.intent, corpus_ids=self.corpus_ids, message=self.message, hypotheses=[], term_finds=terms,
                                 lookups=look, verdict=VERDICT_TERMS, steer=self.steer, hypotheses_from="model",
                                 routing=self.routing)
        meta = dict(answer.get("meta") or {})
        grounded = meta.get("verdict")
        meta.update({"grounded_verdict": grounded, "verdict": VERDICT_TERMS, "product_search": summary(self.block)})
        note = ("This is a product search. This answer was written without a language model, so no product hypotheses were formed "
                "from the library: ask again with a model, or call product_search, for hypotheses with CJ Dropshipping finds.")
        text = str(answer.get("answer") or "")
        body = note if (grounded != "supported" or not text.strip()) else f"{text}\n\n{note}"
        return {**dict(answer), "answer": f"{body}\n\n{finds_markdown(self.block)}", "meta": meta, "product_research": self.block}

    def finish_evidence(self) -> tuple[dict[str, Any], list[str]]:
        """(block, agent_steps) for an evidence-only product turn: no hypotheses (the agent forms them), CJ for the request's terms."""
        look = self._lookups(MAX_TERM_LOOKUPS)
        terms = self._term_finds(look)
        self.verdict = None
        self.block = build_block(self.intent, corpus_ids=self.corpus_ids, message=self.message, hypotheses=[], term_finds=terms,
                                 lookups=look, steer=self.steer, hypotheses_from="agent", routing=self.routing)
        return self.block, agent_steps(self.block)

    def finish_agent(self, supplied: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], str, str]:
        """(block, verdict, Markdown) for hypotheses the caller's agent formed itself (POST /product/search with `hypotheses`)."""
        hyps = []
        for raw in supplied:
            title = H._text(raw.get("title"), H.TITLE_MAX)
            if not title:
                continue
            hyps.append({"id": f"h{len(hyps) + 1}", "title": title, "problem": H._text(raw.get("problem"), H.PROBLEM_MAX),
                         "audience": H._text(raw.get("audience"), H.AUDIENCE_MAX), "evidence_tags": [],
                         "search_terms": H._terms(raw.get("search_terms"), title), "confidence": None, "source": "agent"})
            if len(hyps) >= MAX_HYPOTHESES:
                break
        look = self._lookups(MAX_LOOKUPS)
        hyps = self._with_finds(hyps, look)
        self.verdict = VERDICT
        self.block = build_block(self.intent, corpus_ids=self.corpus_ids, message=self.message, hypotheses=hyps, lookups=look,
                                 verdict=VERDICT, extra_limitations=["these hypotheses were formed by the caller's agent: Polymath "
                                                                     "searched suppliers for them and did not check them against the library"])
        return self.block, VERDICT, finds_markdown(self.block)

    def receipt(self) -> dict[str, Any] | None:
        return summary(self.block, self.verdict)
