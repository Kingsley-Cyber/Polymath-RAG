"""LISTING APIS (SUPPLIER-APIS, the owner's decision of 2026-09-27): supplier listings WITHOUT the pages that show human checks.

The host browser reads a supplier's own search page, and those pages put a human check in front of an automated reader (the R7 run:
Alibaba on every call, CJ a verification redirect). The fix is to stop needing those pages, never to get past a check:
  * cjdropshipping.com: CJ's OFFICIAL API (`cj_api`), when `CJ_API_KEY` is set;
  * alibaba.com: search-engine RESULT SNIPPETS from the local SearXNG (`searxng`), unless `SEARXNG_URL=off`.
A site with such an API is read through it FIRST. When the API cannot answer (unreachable, network, auth, quota, rate limit, a reply
it cannot read), the host browser reads the site exactly as before, the result SAYS so (a `backend_notes` line that reaches
`limitations` in every state) and the fallback is COUNTED (`catalog` shows it under `host.listing_apis`; a warning log line). No
listing API configured = today's backend, untouched. Keys come from the environment only and never reach a log, a result or an
error."""
from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from typing import Any

from polymath_shared.acquisition.service import Backend, Target, now_iso

log = logging.getLogger("polymath.acquisition")


class ApiFailed(Exception):
    """A listing API could not answer. `reason` is one stable word (unreachable, network, auth, quota, rate_limit, bad_request,
    refused, bad_reply, server, error); `detail` says why in plain words and never holds a key or a token."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


_COUNTS: dict[str, dict[str, Any]] = {}
_COUNT_LOCK = threading.Lock()


def _count(reader: str, outcome: str, reason: str | None = None) -> dict[str, Any]:
    """Count one API read or one fallback for `reader` (in this process: a bounce resets it) -> the reader's counts now."""
    with _COUNT_LOCK:
        c = _COUNTS.setdefault(reader, {"api_reads": 0, "fallbacks": 0, "fallback_reasons": {}})
        c[outcome] += 1
        if reason:
            c["fallback_reasons"][reason] = c["fallback_reasons"].get(reason, 0) + 1
        return {"api_reads": c["api_reads"], "fallbacks": c["fallbacks"], "fallback_reasons": dict(c["fallback_reasons"])}


def counts() -> dict[str, dict[str, Any]]:
    with _COUNT_LOCK:
        return {r: {"api_reads": c["api_reads"], "fallbacks": c["fallbacks"], "fallback_reasons": dict(c["fallback_reasons"])}
                for r, c in _COUNTS.items()}


class ListingAPIs:
    """The host browser backend with listing APIs in front (see the module docstring)."""

    def __init__(self, browser: Backend, apis: Mapping[str, Any]):
        self.browser, self.apis = browser, dict(apis)

    def status(self) -> dict[str, Any]:
        out = dict(self.browser.status())
        now = counts()
        out["listing_apis"] = {reader: {"api": api.label, **now.get(reader, {"api_reads": 0, "fallbacks": 0, "fallback_reasons": {}})}
                               for reader, api in sorted(self.apis.items())}
        return out

    def read(self, target: Target, limit: int) -> dict[str, Any]:
        api = self.apis.get(target.reader)
        if api is None:
            return self.browser.read(target, limit)
        try:
            raw = api.read(target, limit)
        except ApiFailed as exc:
            return self._fall_back(target, limit, api.label, exc.reason, exc.detail)
        except Exception as exc:          # a reader's own bug: said and counted like any other failure, never a silent 500
            log.exception("listing API raised: reader=%s api=%s", target.reader, api.label)
            return self._fall_back(target, limit, api.label, "error", type(exc).__name__)
        _count(target.reader, "api_reads")
        return raw

    def _fall_back(self, target: Target, limit: int, label: str, reason: str, detail: str) -> dict[str, Any]:
        now = _count(target.reader, "fallbacks", reason)
        log.warning("listing API fell back to the host browser: reader=%s api=%s reason=%s fallbacks=%d api_reads=%d",
                    target.reader, label, reason, now["fallbacks"], now["api_reads"])
        note = f"the {label} could not answer ({reason}: {detail}); the host browser read {target.site} instead"
        try:
            raw = dict(self.browser.read(target, limit))
        except Exception as exc:  # noqa: BLE001 — the browser read failed too: nothing was read, and both reasons are said
            raw = {"state": "unavailable", "note": f"the read failed ({type(exc).__name__}: {str(exc)[:200]})", "retrieved_at": now_iso()}
        raw["backend_notes"] = [note, *(raw.get("backend_notes") or [])]
        return raw


def configured(env: Mapping[str, str]) -> dict[str, Any]:
    """reader -> the listing API this host is configured for, read from the environment only."""
    from polymath_shared.acquisition import cj_api, searxng
    apis: dict[str, Any] = {}
    client = cj_api.client_from_env(env)
    if client is not None:
        apis["cj_listings"] = cj_api.CJListings(client)
    url = searxng.base_url(env)
    if url:
        apis["alibaba_listings"] = searxng.SearXNGListings(url)
    return apis


def wrap(browser: Backend, env: Mapping[str, str]) -> Backend:
    """The browser backend itself when no listing API is configured (today's backend, untouched), else `ListingAPIs`."""
    apis = configured(env)
    return ListingAPIs(browser, apis) if apis else browser
