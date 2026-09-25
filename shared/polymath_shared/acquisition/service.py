"""RESEARCH ACQUISITION — the contract and the policy (AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8; the owner's worker-pack prompt 06,
2026-09-25: "Polymath should run OpenCLI on its browser host and expose authorized research through its existing MCP connection, so a
connected Hermes or other client does not need OpenCLI installed locally").

What a call may do, and nothing else:
  * WHO: the owner only. The host browser carries the owner's sign-ins, so a registered principal (a friend's key) is refused: no remote
    client inherits another person's login. (The MCP gate also leaves this tool out of every principal's scope.)
  * WHEN: only while the run awaits a HARNESS_ACTION (the open research step) and inside its budget: each call is one query of the
    action's `budget.max_queries`, counted per action in this process (a restart forgets the count). A source class the action
    disallows is refused.
  * WHAT: a fixed, READ-ONLY catalog. Web search returns leads, never evidence. `comments` reads the comments under a CONTENT
    PERMALINK. `listings` runs a listing search on a supported site. Targets must match strict patterns in full, so an account page, a
    feed, a profile or a short link is never read. Nothing posts, likes, follows, buys or fills a form. No arbitrary URL, command or
    script is accepted.
  * WHAT IS TRUE: every item keeps its OWN date and says how precise it is:
    - `exact` comes from the site's own timestamp;
    - `relative` means the site shows only "3 weeks ago" (`published_at` stays null, `date_shown` keeps the text, and it is never turned
      into a date);
    - `none` means the page shows no date.
    `completeness` says what was read against what the page holds. A sign-in wall or a human check comes back as HUMAN_ACTION_REQUIRED:
    call again after a person acts. It is never worked around.
The result is receipt-ready: `sources` holds one row per (page, publish date), verbatim `items` point at them, and `tool_trace` holds
one row. It is NOT evidence. The harness still states each observation's claim, role and hypotheses and submits a
HarnessResearchReceiptV1 with adapter_submit. TrailSignal decides what is admitted."""
from __future__ import annotations

import hashlib
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

CONTRACT = "research-acquisition-v1"
OPERATIONS = ("catalog", "web_search", "comments", "listings")
EXCERPT_MAX, TITLE_MAX, QUERY_MAX = 600, 300, 300
LIMIT_DEFAULT, LIMIT_MAX = 20, 50

#: comments: the ONLY pages whose comments may be read — content permalinks matched in FULL.
#: (site, pattern, canonical form, class of the page as a source, reader)
COMMENT_PAGES = (
    ("tiktok.com", r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9._-]{1,64})/video/(\d{6,25})/?(?:\?[^#\s]*)?",
     "https://www.tiktok.com/@{0}/video/{1}", "video_platform", "tiktok_comments"),
    ("instagram.com", r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]{5,64})/?(?:\?[^#\s]*)?",
     "https://www.instagram.com/p/{0}/", "video_platform", "instagram_comments"),
    ("youtube.com", r"https?://(?:www\.|m\.)?youtube\.com/watch\?(?:[^#\s]*&)?v=([A-Za-z0-9_-]{6,20})(?:&[^#\s]*)?",
     "https://www.youtube.com/watch?v={0}", "video_platform", "youtube_comments"),
    ("youtube.com", r"https?://youtu\.be/([A-Za-z0-9_-]{6,20})(?:\?[^#\s]*)?",
     "https://www.youtube.com/watch?v={0}", "video_platform", "youtube_comments"),
    ("reddit.com", r"https?://(?:www\.|old\.)?reddit\.com/r/([A-Za-z0-9_]{2,40})/comments/([a-z0-9]{4,12})(?:/[A-Za-z0-9_%-]*)?/?(?:\?[^#\s]*)?",
     "https://www.reddit.com/r/{0}/comments/{1}/", "community_discussion", "reddit_comments"),
)
#: listings: search pages on these sites only; the page URL is built HERE from the query, never taken from the caller
LISTING_SITES = {"alibaba.com": ("supplier_listing", "alibaba_listings"), "cjdropshipping.com": ("supplier_listing", "cj_listings")}
_HOST = re.compile(r"^(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)$")


class AcquisitionRefused(Exception):
    """A call the policy refuses. `status` is the HTTP status the route answers with; `code` is stable for clients."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class Target:
    operation: str
    reader: str
    site: str | None = None
    url: str | None = None                  # the content permalink to read (comments)
    query: str | None = None                # the query (web_search, listings)
    ident: tuple[str, ...] = ()             # ids parsed from the permalink
    source_class: str | None = None         # None = search results: leads, not sources


class Backend(Protocol):
    def status(self) -> dict[str, Any]: ...
    def read(self, target: Target, limit: int) -> dict[str, Any]: ...


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clip(text: Any, n: int) -> str:
    return " ".join(str(text or "").split())[:n]


# ------------------------------------------------------------------------------------------------------------------- policy --
def authorize(principal_id: str | None) -> None:
    """Owner only: no principal context = the owner key or a trusted local caller."""
    if principal_id is not None:
        raise AcquisitionRefused(403, "OWNER_ONLY", "research acquisition uses the host browser, which holds the owner's sign-ins; "
                                                    "a principal key may not use it")


def _query(text: str) -> str:
    q = " ".join(str(text or "").split())
    if not 2 <= len(q) <= QUERY_MAX:
        raise AcquisitionRefused(422, "BAD_QUERY", f"a query is 2 to {QUERY_MAX} characters")
    return q


def _site(site: str | None) -> str | None:
    if site is None or not str(site).strip():
        return None
    host = str(site).strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    m = _HOST.match(host)
    if not m:
        raise AcquisitionRefused(422, "BAD_SITE", "a site is a bare host name, e.g. example.com")
    return m.group(1)


def resolve(operation: str, target: str, site: str | None = None) -> Target:
    """The caller's request -> ONE catalog entry, or a refusal naming what is accepted."""
    if operation not in OPERATIONS:
        raise AcquisitionRefused(422, "UNKNOWN_OPERATION", f"operation must be one of {', '.join(OPERATIONS)}")
    if operation == "catalog":
        return Target(operation="catalog", reader="catalog")
    if operation == "web_search":
        host = _site(site)
        q = _query(target)
        return Target(operation="web_search", reader="web_search", site=host, query=f"site:{host} {q}" if host else q)
    if operation == "comments":
        url = str(target or "").strip()
        for host, pattern, canonical, cls, reader in COMMENT_PAGES:
            m = re.fullmatch(pattern, url)
            if m:
                return Target(operation="comments", reader=reader, site=host, url=canonical.format(*m.groups()), ident=m.groups(),
                              source_class=cls)
        raise AcquisitionRefused(422, "TARGET_NOT_PERMITTED", "comments are read only under a content permalink: "
                                 + "; ".join(sorted({c.format(*(["<id>"] * c.count("{"))) for _, _, c, _, _ in COMMENT_PAGES})))
    host = _site(site)
    if host not in LISTING_SITES:
        raise AcquisitionRefused(422, "SITE_NOT_SUPPORTED", f"listings are searched on {', '.join(sorted(LISTING_SITES))}")
    cls, reader = LISTING_SITES[host]
    return Target(operation="listings", reader=reader, site=host, query=_query(target), source_class=cls)


def bind(action: dict[str, Any] | None, target: Target, search_intent_id: str | None) -> None:
    """The read belongs to the run's OPEN research step, inside what that step allows."""
    if not isinstance(action, dict) or not action.get("action_id"):
        raise AcquisitionRefused(409, "NO_OPEN_RESEARCH_STEP", "the run is not awaiting a HARNESS_ACTION: call adapter_next")
    if target.source_class and target.source_class in (action.get("disallowed_source_roles") or []):
        raise AcquisitionRefused(403, "SOURCE_DISALLOWED", f"this research step disallows {target.source_class} sources")
    intents = {str(i.get("intent_id")) for i in action.get("search_intents") or [] if isinstance(i, dict)}
    if search_intent_id is not None and str(search_intent_id) not in intents:
        raise AcquisitionRefused(422, "UNKNOWN_SEARCH_INTENT", "search_intent_id must be one of the step's search intents")


_USED: dict[str, int] = {}
_USED_LOCK = threading.Lock()


def take_query(action: dict[str, Any]) -> tuple[int, int]:
    """One query of the action's budget (per action, in this process)."""
    cap = int((action.get("budget") or {}).get("max_queries") or 20)
    key = str(action.get("action_id"))
    with _USED_LOCK:
        used = _USED.get(key, 0)
        if used >= cap:
            raise AcquisitionRefused(429, "QUERY_BUDGET_SPENT", f"this research step allows {cap} queries and all were used")
        _USED[key] = used + 1
        return used + 1, cap


def _limit(limit: int | None) -> int:
    try:
        n = int(limit) if limit is not None else LIMIT_DEFAULT
    except (TypeError, ValueError):
        raise AcquisitionRefused(422, "BAD_LIMIT", f"limit is a number from 1 to {LIMIT_MAX}")
    return max(1, min(n, LIMIT_MAX))


def catalog(host: dict[str, Any] | None = None) -> dict[str, Any]:
    forms = sorted({c.format(*(["<id>"] * c.count("{"))) for _, _, c, _, _ in COMMENT_PAGES})
    return {"contract": CONTRACT, "read_only": True, "owner_only": True, "limit": {"default": LIMIT_DEFAULT, "max": LIMIT_MAX},
            "operations": {
                "web_search": {"target": "a search query", "site": "optional: one host name to search within",
                               "yields": "leads (url, title, snippet): never evidence; read a lead's page with `comments`"},
                "comments": {"target": "a content permalink", "accepted": forms,
                             "yields": "one source per (page, publish date) + verbatim comments, each with its own date and its precision"},
                "listings": {"target": "a search query", "site": sorted(LISTING_SITES),
                             "yields": "one source per listing + the listing as shown (title, price as listed, minimum order as listed, supplier)"}},
            "host": host or {}}


# -------------------------------------------------------------------------------------------------------------------- shape --
_HUMAN = {"sign_in": ("a sign-in", "Sign in to {site} in the host's browser, then call again."),
          "human_check": ("a human check", "Open {site} in the host's browser and pass its human check, then call again.")}


def shape(t: Target, raw: dict[str, Any], *, action: dict[str, Any], search_intent_id: str | None, retrieved_at: str,
          used: int, cap: int, limit: int) -> dict[str, Any]:
    """The backend's raw read -> the acquisition result (pure)."""
    state = str(raw.get("state") or "unavailable")
    page_url = raw.get("page_url") or t.url
    out: dict[str, Any] = {
        "contract": CONTRACT, "run_id": action.get("run_id"), "action_id": action.get("action_id"), "operation": t.operation,
        "site": t.site, "target": t.url or t.query, "retrieved_at": retrieved_at, "status": "", "sources": [], "items": [],
        "completeness": {"read": 0, "available": None, "complete": None}, "limitations": [], "human_action": None,
        "tool_trace": {"search_intent_id": search_intent_id, "tool_class": f"polymath.acquire/{t.operation}", "query_count": 1},
        "budget": {"queries_used_here": used, "max_queries": cap}}
    out["acquisition_id"] = "acq_" + _sha(f"{action.get('action_id')}|{t.operation}|{out['target']}|{t.site}|{retrieved_at}")[:24]
    where = t.site or "the page"
    if state in _HUMAN:
        need, how = _HUMAN[state]
        out["status"] = "HUMAN_ACTION_REQUIRED"
        out["human_action"] = {"kind": state, "site": where, "instruction": how.format(site=where), "retry": True}
        out["limitations"].append(f"{where}: {need} is required in the host browser; nothing was read (not bypassed)")
        return out
    if state != "ok":
        out["status"] = "UNAVAILABLE"
        out["limitations"].append(f"{where}: {_clip(raw.get('note') or 'the host browser could not read it', 300)}")
        return out
    records = [r for r in raw.get("records") or [] if isinstance(r, dict)][: limit + 1]      # + the page's own post / caption
    if t.operation == "web_search":
        out["items"] = [{"item_id": "itm_" + _sha(str(r.get("url")))[:12], "kind": "result", "url": str(r.get("url") or ""),
                         "title": _clip(r.get("title"), TITLE_MAX), "excerpt": _clip(r.get("snippet"), EXCERPT_MAX)}
                        for r in records if str(r.get("url") or "").startswith("http")]
        out["completeness"] = {"read": len(out["items"]), "available": None, "complete": None}
        out["limitations"].append("search results are leads, not evidence: read a lead's page before citing it")
        out["status"] = "OK" if out["items"] else "EMPTY"
        return out
    sources: dict[str, dict[str, Any]] = {}
    relative = 0
    for r in records:
        url = str(r.get("url") or page_url or "")
        precision = r.get("precision") if r.get("precision") in ("exact", "relative", "none") else "none"
        published = r.get("published_at") if precision == "exact" else None
        relative += precision == "relative"
        sid = "src_" + _sha(f"{url}|{published or ''}")[:12]       # one source per (page, publish date): no item lends its date to another
        sources.setdefault(sid, {"source_id": sid, "url": url[:2000], "source_class": t.source_class, "retrieved_at": retrieved_at,
                                 "published_at_if_known": published})
        item: dict[str, Any] = {"item_id": "itm_" + _sha(f"{url}|{r.get('ref') or ''}|{r.get('text') or ''}")[:12],
                                "kind": str(r.get("kind") or ("comment" if t.operation == "comments" else "listing")), "source_id": sid,
                                "excerpt": _clip(r.get("text"), EXCERPT_MAX), "published_at": published, "date_precision": precision,
                                "date_shown": _clip(r.get("date_shown"), 40) or None}
        if r.get("author"):                                          # a stable pseudonym for independence checks, never the handle
            item["author_key"] = "a_" + _sha(f"{t.site}|{str(r['author']).lower()}")[:10]
        if isinstance(r.get("likes"), int) and not isinstance(r.get("likes"), bool):
            item["likes"] = r["likes"]
        if r.get("listing"):
            item["listing"] = {k: _clip(v, TITLE_MAX) or None for k, v in r["listing"].items()}
        out["items"].append(item)
    out["sources"] = list(sources.values())
    total, complete = raw.get("total"), raw.get("complete")
    out["completeness"] = {"read": len(out["items"]), "available": total if isinstance(total, int) else None,
                           "complete": complete if isinstance(complete, bool) else None, "order": raw.get("order") or "the site's own order"}
    if relative:
        out["limitations"].append(f"{relative} item(s) show only a relative age: published_at is null and date_shown keeps the site's text")
    if complete is False or (isinstance(total, int) and total > len(out["items"])):
        out["limitations"].append(f"read {len(out['items'])} of {total if isinstance(total, int) else 'more'} (the first page in the site's own order)")
    for note in raw.get("notes") or []:
        out["limitations"].append(_clip(note, 300))
    out["status"] = "EMPTY" if not out["items"] else ("PARTIAL" if complete is False or (isinstance(total, int) and total > len(out["items"])) else "OK")
    return out


# ------------------------------------------------------------------------------------------------------------------ entry --
def default_backend() -> Backend:
    from polymath_shared.acquisition import opencli
    if os.environ.get("POLYMATH_ACQUISITION", "1").strip() in ("0", "false", "off"):
        return opencli.Disabled("research acquisition is switched off on this host (POLYMATH_ACQUISITION=0)")
    return opencli.OpenCLIBackend()


def acquire(*, principal_id: str | None, action: dict[str, Any] | None, operation: str, target: str, site: str | None = None,
            search_intent_id: str | None = None, limit: int | None = None, backend: Backend | None = None) -> dict[str, Any]:
    authorize(principal_id)
    t = resolve(operation, target, site)
    backend = backend or default_backend()
    if t.operation == "catalog":
        return catalog(backend.status())
    bind(action, t, search_intent_id)
    n = _limit(limit)
    used, cap = take_query(action)
    started = now_iso()
    raw = backend.read(t, n)
    return shape(t, raw, action=action, search_intent_id=search_intent_id, retrieved_at=str(raw.get("retrieved_at") or started),
                 used=used, cap=cap, limit=n)
