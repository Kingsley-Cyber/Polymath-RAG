"""ALIBABA.COM PRODUCT-PAGE URLS (what is left of the SearXNG reader, SUPPLIER-APIS 2026-09-27).

PRODUCT-SEARCH-E2E (the owner, 2026-11-01: "alibaba is strictly agent reach"; "it should never use a users claude native web search
due to bot detections"): alibaba.com listings are found by the USER's own Agent Reach on the user's machine (`agent_reach`), never on
this host. The SearXNG reader that asked the host's search engines (`SearXNGListings`, its paging and pacing, `base_url`) and its
snippet parser (`parse_snippet`, which took a free-shipping cap for the price, glued title words onto the supplier and missed the
minimum order a price tier states) were removed; `agent_reach.parse` reads the user's output line by line instead. The compose
service and its settings (`compose.yaml` service `searxng`, `deployment/searxng/settings.yml`, `SEARXNG_URL` / `SEARXNG_SECRET` in
`.env.example`) are now unused by the code; removing them is a separate owner decision.

What stays is the alibaba.com product-page URL check the parser uses: `/product-detail/<name>_<number>.html` on alibaba.com or one
of its subdomains, parsed strictly and kept without its query or fragment."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

SITE = "alibaba.com"
_PRODUCT_PATH = re.compile(r"/product-detail/([^/?#]+?)_(\d{8,})\.html", re.IGNORECASE)


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


def product_slug(url: str) -> str | None:
    """The product page's name part (`Waterproof-Camera-Rain-Cover` of `/product-detail/Waterproof-Camera-Rain-Cover_1600….html`)."""
    found = listing_url(url)
    if found is None:
        return None
    m = _PRODUCT_PATH.fullmatch(urlsplit(found[0]).path)
    return m.group(1) if m else None
