"""The OpenCLI backend of research acquisition (AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8).

OpenCLI runs on the host that holds the owner's browser: its bridge extension in that browser and its daemon on this machine. It is a
SEPARATELY installed tool, not part of this repository: `POLYMATH_ACQUISITION_OPENCLI` names the binary, else the PATH, else
Homebrew's path. What this module does with it, and nothing else:
  * site commands that only READ (web search; marketplace search), called with fixed arguments and never through a shell;
  * for other pages, a browser session of its OWN (a fresh background tab, always closed afterwards) that opens a validated URL and
    evaluates a fixed, read-only script: the site's own comment list (YouTube too: OpenCLI's YouTube command reads one page and cuts
    each comment at 300 characters), the page's timestamps, the listing cards;
  * every comment reader also returns the PAGE's own publish date (`page_published_at`): an item whose own date is not shown is dated
    by it (the earliest it can be), never by the moment it was read;
  * at most POLYMATH_ACQUISITION_CONCURRENCY reads at a time (default 2), so the owner's browser is never flooded.
A sign-in wall or a human-verification page is DETECTED and reported (`state`), never worked around. The comment, like, follow,
post and purchase commands OpenCLI also has are never called."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from polymath_shared.acquisition.service import Target, now_iso

READ_TIMEOUT_S = 75
_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get("POLYMATH_ACQUISITION_CONCURRENCY", "2") or 2)))
_NOISE = ("Update available", "npm install")


def _iso(epoch: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(float(epoch)), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    m = re.fullmatch(r"\s*(\d+)\s*", str(v or ""))
    return int(m.group(1)) if m else None


def blocked(state: dict[str, Any]) -> str | None:
    """`human_check` / `sign_in` when the page is a wall rather than the content (pure; tested on recorded page states)."""
    text = f"{state.get('title', '')} {state.get('text', '')}".lower()
    url = str(state.get("url") or "").lower()
    if "human verification" in text or "not a robot" in text or "captcha" in text or "/validation" in url or "/captcha" in url:
        return "human_check"
    if "/accounts/login" in url or "/login" in url.split("?")[0] or state.get("login_prompt") or (state.get("wall") and not state.get("content")):
        return "sign_in"
    return None


#: a sign-in prompt shown OVER the content (TikTok's modal: its comment list still answers a signed-out visitor, the owner's rule
#: says a login wall is never read through). Matched in the page's whole visible text; hidden templates are not visible text.
LOGIN_PROMPT = r"log in to tiktok|log in to continue|sign in to continue"


def _iso_text(value: Any) -> str | None:
    """An ISO-8601 date-time with an offset -> UTC `...Z` (a page's own publish date); anything else -> None."""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


class Disabled:
    def __init__(self, note: str):
        self.note = note

    def status(self) -> dict[str, Any]:
        return {"backend": "opencli", "available": False, "note": self.note}

    def read(self, target: Target, limit: int) -> dict[str, Any]:
        return {"state": "unavailable", "note": self.note, "retrieved_at": now_iso()}


class OpenCLIBackend:
    def __init__(self, binary: str | None = None):
        self.binary = binary or os.environ.get("POLYMATH_ACQUISITION_OPENCLI") or shutil.which("opencli") or "/opt/homebrew/bin/opencli"

    # ----------------------------------------------------------------------------------------------------------- plumbing --
    def _run(self, args: list[str], timeout: int = READ_TIMEOUT_S) -> str:
        # reviewed (ruff S603): no shell; the binary is the host's OpenCLI; every argument is a fixed command word, a validated
        # permalink / id, a query passed as ONE argv item, or a fixed read-only script (test_the_backend_calls_only_read_commands)
        # OpenCLI is a Node program (`#!/usr/bin/env node`): its own directory goes first on PATH, so a fleet started with a thin PATH
        # still finds the `node` installed beside it
        env = {**os.environ, "PATH": os.pathsep.join([os.path.dirname(os.path.realpath(shutil.which(self.binary) or self.binary)),
                                                     os.path.dirname(self.binary), os.environ.get("PATH", "")])}
        proc = subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=timeout, env=env)  # noqa: S603
        return "\n".join(ln for ln in (proc.stdout or "").splitlines() if not any(n in ln for n in _NOISE)).strip()

    def _json(self, args: list[str], timeout: int = READ_TIMEOUT_S) -> Any:
        raw = self._run(args, timeout)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _open(self, session: str, url: str, settle: float) -> None:
        self._run(["browser", session, "open", url, "--window", "background"])
        time.sleep(settle)

    def _eval(self, session: str, js: str) -> Any:
        raw = self._run(["browser", session, "eval", js])
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(value, str):                     # the scripts below return JSON text
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def _page(self, session: str) -> dict[str, Any]:
        got = self._eval(session, "JSON.stringify({url: location.href, title: document.title, text: document.body ? document.body.innerText.slice(0, 600) : '',"
                                  " login_prompt: document.body ? /%s/i.test(document.body.innerText) : false})" % LOGIN_PROMPT)
        return got if isinstance(got, dict) else {}

    def _session(self) -> str:
        return "pm-acq-" + uuid.uuid4().hex[:10]

    def _close(self, session: str) -> None:
        try:
            self._run(["browser", session, "close"], timeout=20)
        except (subprocess.SubprocessError, OSError):
            pass

    def status(self) -> dict[str, Any]:
        if not (os.path.exists(self.binary) or shutil.which(self.binary)):
            return {"backend": "opencli", "available": False, "note": "OpenCLI is not installed on this host"}
        try:
            out = self._run(["doctor"], timeout=25)
        except (subprocess.SubprocessError, OSError) as exc:
            return {"backend": "opencli", "available": False, "note": f"doctor failed: {str(exc)[:120]}"}
        ok = bool(re.search(r"Daemon: running", out)) and bool(re.search(r"Extension: connected", out))
        return {"backend": "opencli", "available": ok, "note": "browser bridge connected" if ok else "the browser bridge is not connected (is the host's browser running?)"}

    def read(self, target: Target, limit: int) -> dict[str, Any]:
        reader = getattr(self, "_" + target.reader, None)
        if reader is None:
            return {"state": "unavailable", "note": f"no reader for {target.reader}", "retrieved_at": now_iso()}
        with _SLOTS:
            try:
                return reader(target, limit)
            except subprocess.TimeoutExpired:
                return {"state": "unavailable", "note": "the host browser did not answer in time", "retrieved_at": now_iso()}
            except (subprocess.SubprocessError, OSError) as exc:
                return {"state": "unavailable", "note": f"the browser bridge failed: {str(exc)[:160]}", "retrieved_at": now_iso()}

    def _in_tab(self, url: str, settle: float, js: str) -> tuple[dict[str, Any], Any, str]:
        session = self._session()
        try:
            self._open(session, url, settle)
            retrieved = now_iso()
            page = self._page(session)
            if blocked(page):
                return page, None, retrieved
            return page, self._eval(session, js), retrieved
        finally:
            self._close(session)

    # ------------------------------------------------------------------------------------------------------------ readers --
    def _web_search(self, t: Target, limit: int) -> dict[str, Any]:
        rows = self._json(["duckduckgo", "search", t.query or "", "--limit", str(min(limit, 10)), "-f", "json"])
        if not isinstance(rows, list):
            return {"state": "unavailable", "note": "the web search returned nothing readable", "retrieved_at": now_iso()}
        return {"state": "ok", "retrieved_at": now_iso(),
                "records": [{"url": r.get("url"), "title": r.get("title"), "snippet": r.get("snippet")} for r in rows if isinstance(r, dict)]}

    def _tiktok_comments(self, t: Target, limit: int) -> dict[str, Any]:
        video_id = t.ident[1]
        js = ("(async () => { const r = await fetch('/api/comment/list/?aid=1988&aweme_id=%s&count=%d&cursor=0', {credentials: 'include'});"
              " const d = await r.json().catch(() => null); let v = null; try { const u = JSON.parse(document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__').textContent);"
              " const s = u.__DEFAULT_SCOPE__['webapp.video-detail'].itemInfo.itemStruct; v = {desc: s.desc, created: s.createTime}; } catch (e) {}"
              " return JSON.stringify({status: r.status, code: d ? d.status_code : null, total: d ? d.total : null, has_more: d ? d.has_more : null, video: v,"
              " comments: ((d && d.comments) || []).map(c => ({cid: c.cid, text: c.text, created: c.create_time, likes: c.digg_count, author: (c.user || {}).unique_id}))}); })()"
              % (video_id, limit))
        page, data, retrieved = self._in_tab(t.url or "", 4.0, js)
        if (why := blocked(page)):
            return {"state": why, "page_url": t.url, "retrieved_at": retrieved}
        if not isinstance(data, dict) or data.get("code") not in (0, None) or data.get("status") != 200:
            return {"state": "unavailable", "page_url": t.url, "retrieved_at": retrieved,
                    "note": f"the page's comment list did not answer (status {data.get('status') if isinstance(data, dict) else '?'})"}
        records = []
        video = data.get("video") or {}
        if video.get("desc"):
            records.append({"kind": "caption", "ref": "caption", "text": video["desc"], "published_at": _iso(video.get("created")),
                            "precision": "exact" if _iso(video.get("created")) else "none"})
        for c in data.get("comments") or []:
            records.append({"kind": "comment", "ref": c.get("cid"), "text": c.get("text"), "published_at": _iso(c.get("created")),
                            "precision": "exact" if _iso(c.get("created")) else "none", "author": c.get("author"), "likes": _int(c.get("likes"))})
        return {"state": "ok", "page_url": t.url, "retrieved_at": retrieved, "records": records, "total": _int(data.get("total")),
                "complete": (not data.get("has_more")) if data.get("has_more") is not None else None, "page_published_at": _iso(video.get("created"))}

    #: the post's own date row under a post ("November 15, 2025"); comment rows show a short age ("44w", "2d")
    _FULL_DATE = re.compile(r"[A-Z][a-z]+ \d{1,2}(?:, \d{4})?|\d{1,2} [A-Z][a-z]+(?: \d{4})?")

    def _instagram_comments(self, t: Target, limit: int) -> dict[str, Any]:
        js = ("JSON.stringify({blocks: Array.from(document.querySelectorAll('time[datetime]')).map(t => { let n = t;"
              " while (n.parentElement && n.parentElement.querySelectorAll('time[datetime]').length === 1) n = n.parentElement;"
              " return {datetime: t.getAttribute('datetime'), shown: t.textContent, block: n.innerText.slice(0, 900)}; })})")
        page, data, retrieved = self._in_tab(t.url or "", 5.0, js)
        if (why := blocked(page)):
            return {"state": why, "page_url": t.url, "retrieved_at": retrieved}
        blocks = [b for b in ((data or {}).get("blocks") if isinstance(data, dict) else None) or [] if isinstance(b, dict)]
        # the post's own date row is the PAGE's date, never an item (its block is the likes / shares line)
        footer = [b for b in blocks if self._FULL_DATE.fullmatch(str(b.get("shown") or "").strip())]
        page_date = _iso_text(footer[-1].get("datetime")) if footer else None
        rows = [b for b in blocks if b not in footer]
        records = []
        for i, b in enumerate(rows[: limit + 1]):
            lines = [ln.strip() for ln in str(b.get("block") or "").split("\n") if ln.strip()]
            shown = str(b.get("shown") or "").strip()
            author = lines[0] if lines else None
            body = [ln for ln in lines[1:] if ln != shown and ln not in ("Reply", "Edited", "•", "Follow")
                    and not re.fullmatch(r"(?:\d[\d,.]*[km]?\s+likes?|View all \d+ repl(?:y|ies)|See translation|Original audio)", ln, re.I)]
            if not author or not re.search(r"[A-Za-z]", author) or not re.search(r"[A-Za-z]", " ".join(body)):
                continue                                              # a counts line, never a comment
            published = _iso_text(b.get("datetime"))
            records.append({"kind": "caption" if i == 0 else "comment", "ref": f"{b.get('datetime')}|{author}", "text": " ".join(body),
                            "published_at": published, "precision": "exact" if published else "none", "author": author})
        if not records:
            text = str(page.get("text") or "").lower()
            signed_out = "log in" in text and "sign up" in text           # the signed-out post view shows no comment rows at all
            return {"state": "sign_in" if signed_out else "unavailable", "page_url": t.url, "retrieved_at": retrieved,
                    "note": "the post view shows no dated comment", "page_published_at": page_date}
        return {"state": "ok", "page_url": t.url, "retrieved_at": retrieved, "records": records, "total": None, "complete": None,
                "page_published_at": page_date,
                "notes": ["the comments the post view shows without paging (usually the first few); the caption is the post's own text"]}

    def _youtube_comments(self, t: Target, limit: int) -> dict[str, Any]:
        """The watch page's OWN comment request, in a tab of our own: OpenCLI's YouTube command reads one page, cuts each comment at
        300 characters and never says whether more exist. YouTube shows a comment's age only as relative text."""
        js = ("(async () => { const find = (o, k) => { if (!o || typeof o !== 'object') return null; if (k in o) return o[k];"
              " for (const v of Object.values(o)) { const r = find(v, k); if (r) return r; } return null; };"
              " const sections = []; const walk = (o) => { if (!o || typeof o !== 'object') return;"
              " if (o.itemSectionRenderer && o.itemSectionRenderer.sectionIdentifier === 'comment-item-section') sections.push(o.itemSectionRenderer);"
              " for (const v of Object.values(o)) walk(v); }; walk(window.ytInitialData || {});"
              " const published = (document.querySelector('meta[itemprop=\"datePublished\"], meta[itemprop=\"uploadDate\"]') || {}).content || null;"
              " const token = sections.length ? find(sections[0], 'token') : null;"
              " if (!token) return JSON.stringify({status: 0, published, comments: [], has_more: false});"
              " const r = await fetch('/youtubei/v1/next?prettyPrint=false', {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'},"
              " body: JSON.stringify({context: ytcfg.get('INNERTUBE_CONTEXT'), continuation: token})}); const d = await r.json().catch(() => ({}));"
              " const items = (d.onResponseReceivedEndpoints || []).flatMap(e => ((e.reloadContinuationItemsCommand || e.appendContinuationItemsAction || {}).continuationItems) || []);"
              " const out = []; for (const mu of ((d.frameworkUpdates || {}).entityBatchUpdate || {}).mutations || []) { const p = (mu.payload || {}).commentEntityPayload;"
              " if (p) out.push({id: (p.properties || {}).commentId || null, text: ((p.properties || {}).content || {}).content || '', age: (p.properties || {}).publishedTime || null,"
              " author: (p.author || {}).displayName || null, likes: (p.toolbar || {}).likeCountNotliked || null}); }"
              " return JSON.stringify({status: r.status, published, comments: out.slice(0, %d), has_more: items.some(i => i.continuationItemRenderer) || out.length > %d}); })()"
              % (limit, limit))
        page, data, retrieved = self._in_tab(t.url or "", 5.0, js)
        if (why := blocked(page)):
            return {"state": why, "page_url": t.url, "retrieved_at": retrieved}
        if not isinstance(data, dict):
            return {"state": "unavailable", "page_url": t.url, "retrieved_at": retrieved, "note": "the watch page did not answer"}
        page_date = _iso_text(data.get("published"))
        if data.get("status") not in (0, 200) or (data.get("status") == 0 and not data.get("comments")):
            return {"state": "unavailable", "page_url": t.url, "retrieved_at": retrieved, "page_published_at": page_date,
                    "note": "no comment list (comments off, or the page did not load)"}
        records = [{"kind": "comment", "ref": c.get("id"), "text": c.get("text"), "published_at": None, "precision": "relative",
                    "date_shown": c.get("age"), "author": c.get("author"), "likes": _int(c.get("likes"))} for c in data.get("comments") or []]
        return {"state": "ok", "page_url": t.url, "retrieved_at": retrieved, "records": records, "total": None,
                "complete": not data.get("has_more"), "page_published_at": page_date}

    def _reddit_comments(self, t: Target, limit: int) -> dict[str, Any]:
        js = ("(async () => { const r = await fetch(location.pathname.replace(/\\/$/, '') + '.json?limit=%d&depth=1&raw_json=1', {credentials: 'include'});"
              " const d = await r.json().catch(() => null); if (!Array.isArray(d)) return JSON.stringify({status: r.status});"
              " const p = d[0].data.children[0].data; return JSON.stringify({status: r.status, post: {title: p.title, text: p.selftext, created: p.created_utc,"
              " author: p.author, comments: p.num_comments}, comments: d[1].data.children.filter(c => c.kind === 't1').map(c => ({id: c.data.id,"
              " text: c.data.body, created: c.data.created_utc, author: c.data.author, score: c.data.score}))}); })()" % limit)
        page, data, retrieved = self._in_tab(t.url or "", 3.0, js)
        if (why := blocked(page)):
            return {"state": why, "page_url": t.url, "retrieved_at": retrieved}
        if not isinstance(data, dict) or not data.get("post"):
            return {"state": "unavailable", "page_url": t.url, "retrieved_at": retrieved, "note": "the thread did not answer"}
        post = data["post"]
        records = [{"kind": "post", "ref": "post", "text": f"{post.get('title') or ''}\n{post.get('text') or ''}".strip(),
                    "published_at": _iso(post.get("created")), "precision": "exact" if _iso(post.get("created")) else "none", "author": post.get("author")}]
        records += [{"kind": "comment", "ref": c.get("id"), "text": c.get("text"), "published_at": _iso(c.get("created")),
                     "precision": "exact" if _iso(c.get("created")) else "none", "author": c.get("author"), "likes": _int(c.get("score"))}
                    for c in data.get("comments") or []]
        total = _int(post.get("comments"))
        return {"state": "ok", "page_url": t.url, "retrieved_at": retrieved, "records": records, "total": total,
                "complete": (total is not None and len(records) - 1 >= total), "page_published_at": _iso(post.get("created"))}

    def _listing_cards(self, url: str, settle: float, link_selector: str, stop: str) -> tuple[dict[str, Any], Any, str]:
        js = ("JSON.stringify(Array.from(document.querySelectorAll('%s')).map(a => { let c = a; for (let i = 0; i < 8 && c && !(%s).test(c.innerText || ''); i++) c = c.parentElement;"
              " return {href: a.href.split('?')[0], title: (a.innerText || a.title || '').trim().slice(0, 300), card: c ? c.innerText.slice(0, 600) : ''}; }).filter(x => x.title))"
              % (link_selector, stop))
        return self._in_tab(url, settle, js)

    @staticmethod
    def _listing(href: str, title: str, card: str) -> dict[str, Any]:
        """One listing as the card shows it. The price is the last one BEFORE the minimum order (a card may also show a coupon
        threshold); the unit of a minimum order is a lowercase unit word (card text can glue the next line on)."""
        lines = [ln.strip() for ln in title.splitlines() if ln.strip()]
        ui = re.compile(r"^(?:List|Added Products|QTY|Free|Lists?:?\s*\d+|\$[\d.,\s$-]+)$", re.I)
        title = max((ln for ln in lines if not ui.match(ln)), key=len, default=" ".join(lines))
        cut = re.search(r"Min\.?\s*order", card)
        prices = re.findall(r"(?:US\s?\$|\$)\s?\d[\d.,]*(?:\s?-\s?\$?\d[\d.,]*)?", card[: cut.start()] if cut else card)
        moq = re.search(r"Min\.?\s*order:?\s*(\d[\d.,]*\s*(?:pieces?|pcs|units?|sets?|pairs?|packs?|boxes|box|bags?|meters?|kilograms?|kg"
                        r"|tons?|rolls?|dozens?|cartons?)(?![a-z]))", card)
        supplier = next((m.group(1) for ln in card.splitlines() for m in [re.search(
            r"([A-Z][A-Za-z]+(?:[ &,.'-]+[A-Za-z&]+)*?\s(?:Co\.,?\s?Ltd\.?|Co\.,?\s?Limited|Company Limited|Limited|Corporation|Inc\.|Factory))", ln)] if m), None)
        listing = {"title": title, "price_as_listed": prices[-1].strip() if prices else None,
                   "minimum_order_as_listed": moq.group(1).strip() if moq else None, "supplier": supplier,
                   "card": " ".join(card.split())[:300]}          # the card as shown: the parsed fields are checkable
        text = f"{title} · price as listed: {listing['price_as_listed'] or 'not shown'} · minimum order as listed: {listing['minimum_order_as_listed'] or 'not shown'}" \
               f" · supplier: {supplier or 'unresolved'}"
        return {"kind": "listing", "ref": href, "url": href, "text": text, "published_at": None, "precision": "none", "listing": listing}

    def _alibaba_listings(self, t: Target, limit: int) -> dict[str, Any]:
        url = f"https://www.alibaba.com/trade/search?SearchText={quote_plus(t.query or '')}"
        page, rows, retrieved = self._listing_cards(url, 5.0, 'a[href*=\\"/product-detail/\\"]', "/Min\\.? ?order/")
        if (why := blocked(page)):
            return {"state": why, "page_url": url, "retrieved_at": retrieved}
        seen, records = set(), []
        for r in rows if isinstance(rows, list) else []:
            if r.get("href") in seen or not r.get("href", "").startswith("https://"):
                continue
            seen.add(r["href"])
            records.append(self._listing(r["href"], r.get("title") or "", r.get("card") or ""))
            if len(records) >= limit:
                break
        return {"state": "ok" if records else "unavailable", "page_url": url, "retrieved_at": retrieved, "records": records, "total": None,
                "complete": None, **({} if records else {"note": "no listing card was read on the search page"})}

    def _cj_listings(self, t: Target, limit: int) -> dict[str, Any]:
        url = f"https://cjdropshipping.com/search/{quote_plus(t.query or '')}.html"
        page, rows, retrieved = self._listing_cards(url, 6.0, 'a[href*=\\"/product/\\"]', "/\\$/")
        if (why := blocked(page)):
            return {"state": why, "page_url": url, "retrieved_at": retrieved}
        seen, records = set(), []
        for r in rows if isinstance(rows, list) else []:
            if r.get("href") in seen or not r.get("href", "").startswith("https://"):
                continue
            seen.add(r["href"])
            records.append(self._listing(r["href"], r.get("title") or "", r.get("card") or ""))
            if len(records) >= limit:
                break
        return {"state": "ok" if records else "unavailable", "page_url": url, "retrieved_at": retrieved, "records": records, "total": None,
                "complete": None, **({} if records else {"note": "no listing card was read on the search page"})}

    def _amazon_listings(self, t: Target, limit: int) -> dict[str, Any]:
        retrieved = now_iso()
        rows = self._json(["amazon", "search", t.query or "", "--limit", str(limit), "-f", "json"], timeout=READ_TIMEOUT_S)
        if not isinstance(rows, list):
            return {"state": "unavailable", "retrieved_at": retrieved, "note": "the marketplace search returned nothing readable"}
        records, seen = [], set()
        for r in rows:
            asin = str((r or {}).get("asin") or "")
            if not re.fullmatch(r"[A-Z0-9]{10}", asin) or asin in seen:  # a sponsored slot can repeat an organic one
                continue
            seen.add(asin)
            url = f"https://www.amazon.com/dp/{asin}"                    # the canonical listing permalink
            r = dict(r, rating_text=re.sub(r",\s*rating details$", "", str(r.get("rating_text") or "")) or None)
            listing = {"title": r.get("title"), "price_as_listed": r.get("price_text"), "rating_as_shown": r.get("rating_text"),
                       "ratings_count_as_shown": r.get("review_count_text"), "sponsored": "yes" if r.get("is_sponsored") else "no",
                       "supplier": None}
            text = (f"{r.get('title') or ''} · price as listed: {r.get('price_text') or 'not shown'} · rating as shown: "
                    f"{r.get('rating_text') or 'not shown'} · ratings as shown: {r.get('review_count_text') or 'not shown'}"
                    + (" · sponsored listing" if r.get("is_sponsored") else ""))
            records.append({"kind": "listing", "ref": asin, "url": url, "text": text, "published_at": None, "precision": "none", "listing": listing})
        return {"state": "ok" if records else "unavailable", "retrieved_at": retrieved, "records": records[:limit], "total": None,
                "complete": None, **({} if records else {"note": "no listing was read on the marketplace search"})}
