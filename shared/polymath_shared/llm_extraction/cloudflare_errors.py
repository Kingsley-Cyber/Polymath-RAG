"""CLOUDFLARE-WORKERS-AI-V1 — classify Cloudflare Workers AI error responses.

Cloudflare's OpenAI-compatible endpoint reports provider faults in a `{"errors":
[{"code": N, "message": ...}]}` (or nested `error`) body, sometimes with HTTP 429 and
sometimes with a 2xx/4xx status. Two codes need DIFFERENT behaviour and MUST NOT be
conflated (owner contract):

  3036  account free allocation exhausted for the day  → DAILY_FREE_QUOTA_EXHAUSTED
        park the account/lane until the daily reset; do NOT retry-loop it; other
        providers continue; it resumes naturally after reset.

  3040  the provider is out of capacity right now       → OUT_OF_CAPACITY
        transient; bounded/backoff retry (the normal AIMD path), NOT a day-long park.

A plain HTTP 429 with no recognizable code is treated as OUT_OF_CAPACITY (bounded
backoff) — never as a day-long park, so a momentary rate blip cannot dark a lane for a day.

This module is pure (no I/O, no limiter) so it is unit-testable against synthetic bodies —
the codes cannot be triggered on demand against a live free account.
"""
from __future__ import annotations

import json
import time

DAILY_FREE_QUOTA_EXHAUSTED = "DAILY_FREE_QUOTA_EXHAUSTED"
OUT_OF_CAPACITY = "OUT_OF_CAPACITY"

#: Cloudflare error codes (documented). 3036 = daily allocation spent; 3040 = out of capacity.
_CODE_DAILY = 3036
_CODE_CAPACITY = 3040


def _codes(body_text: str) -> set[int]:
    """Every integer `code` under an `errors`/`error` object in the body. Defensive: a
    non-JSON or unexpected body yields no codes (the caller falls back to status)."""
    out: set[int] = set()
    try:
        b = json.loads(body_text) if isinstance(body_text, str) else (body_text or {})
    except (json.JSONDecodeError, TypeError):
        return out
    if not isinstance(b, dict):
        return out
    buckets = []
    for key in ("errors", "error"):
        v = b.get(key)
        if isinstance(v, list):
            buckets.extend(v)
        elif isinstance(v, dict):
            buckets.append(v)
    for item in buckets:
        if isinstance(item, dict):
            c = item.get("code")
            if isinstance(c, int):
                out.add(c)
            elif isinstance(c, str) and c.strip().isdigit():
                out.add(int(c))
    return out


def classify(status: int | None, body_text: str | None) -> str | None:
    """Return DAILY_FREE_QUOTA_EXHAUSTED / OUT_OF_CAPACITY / None for a Cloudflare response.

    Only call this for Cloudflare-host lanes — it is a no-op (None) for anything it does
    not positively recognize, so it can never reclassify another provider's error."""
    codes = _codes(body_text or "")
    if _CODE_DAILY in codes:
        return DAILY_FREE_QUOTA_EXHAUSTED
    if _CODE_CAPACITY in codes:
        return OUT_OF_CAPACITY
    text = (body_text or "").lower()
    # Belt-and-braces for the documented phrasing when the numeric code is absent.
    if _CODE_DAILY in codes or "daily" in text and ("allocation" in text or "quota" in text):
        return DAILY_FREE_QUOTA_EXHAUSTED
    if status == 429:
        # a rate 429 with no daily-exhaustion marker is transient capacity, not a day park
        return OUT_OF_CAPACITY
    return None


def is_cloudflare_host(url: str | None) -> bool:
    """True for the Cloudflare API host (netloc match — never a substring of a path)."""
    if not url:
        return False
    from urllib.parse import urlparse
    try:
        return urlparse(url).netloc.endswith("api.cloudflare.com")
    except Exception:  # noqa: BLE001 — classification must never break a dispatch
        return False


def seconds_to_daily_reset(now: float | None = None) -> int:
    """Seconds until the next UTC midnight — Cloudflare's free allocation resets daily at
    00:00 UTC. Used to park an exhausted account exactly until it replenishes."""
    now = time.time() if now is None else now
    day = 86400
    return int(day - (now % day)) or day
