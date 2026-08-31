"""EXTRACTION-POOL-V1 — the multi-provider cloud endpoint pool.

Owner directive (2026-08-30): lanes work their own backlog hard, steal
the other lane's when idle, and future cloud providers "assist" by
joining a router pool. This module is the POOL half; the stealing half
is lane-affinity claiming in worker_runtime.claim_ticket_events.

Design laws:

  - The 300 KB owner boundary (policy.py) is UNTOUCHED: pool selection
    only ever runs for documents the policy already routed to the cloud
    lane, and `require_cloud_eligible` still guards every dispatch. More
    providers widen cloud THROUGHPUT, never cloud ELIGIBILITY.
  - Endpoint choice is DETERMINISTIC per document (blake2b(doc_id) over
    the enabled roster, sorted by name): a crash/replay re-selects the
    same endpoint, receipts stay attributable, and N providers shard the
    cloud backlog evenly without any coordination state.
  - One endpoint (today's config) degenerates to exactly the old
    behavior — same url, same model, same limiter key.

Registering a new provider = one JSON entry in
POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS:

  [{"name": "deepseek-a", "url": "https://…/v1", "model": "deepseek-chat-x"}]

Each extra endpoint gets its own AIMD limiter lane (keyed by name), so a
slow provider throttles itself without dragging the others down.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from polymath_shared.settings import get_settings


@dataclass(frozen=True)
class CloudEndpoint:
    name: str
    url: str
    model: str

    @property
    def limiter_key(self) -> str:
        # the primary keeps the historical limiter lane ("default") so
        # its AIMD state and seeds carry over; extras get their own.
        return "default" if self.name == "primary" else self.name


def cloud_endpoints() -> list[CloudEndpoint]:
    """The enabled roster, sorted by name. Always >= 1 (the primary from
    settings). Extras come from POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS
    (JSON list of {name, url, model}); malformed JSON fails LOUDLY —
    a silently-dropped provider would look like a half-speed pool."""
    s = get_settings().sidecars
    roster = [CloudEndpoint("primary", s.llm_cloud_url, s.llm_cloud_model)]
    raw = (getattr(s, "llm_cloud_extra_endpoints", "") or "").strip()
    if raw:
        try:
            extras = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS is not valid JSON: {exc}")
        if not isinstance(extras, list):
            raise ValueError(
                "POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS must be a JSON list")
        for i, e in enumerate(extras):
            name = str(e.get("name") or "").strip()
            url = str(e.get("url") or "").strip()
            model = str(e.get("model") or "").strip()
            if not (name and url and model):
                raise ValueError(
                    f"cloud endpoint #{i} needs name+url+model: {e!r}")
            if name == "primary":
                raise ValueError("'primary' is reserved for the settings "
                                 "endpoint; pick another name")
            roster.append(CloudEndpoint(name, url, model))
    roster.sort(key=lambda ep: ep.name)
    names = [ep.name for ep in roster]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate cloud endpoint names: {names}")
    return roster


def select_cloud_endpoint(doc_id: str) -> CloudEndpoint:
    """Deterministic doc -> endpoint assignment over the enabled roster."""
    roster = cloud_endpoints()
    if len(roster) == 1:
        return roster[0]
    digest = hashlib.blake2b((doc_id or "").encode(), digest_size=8).digest()
    return roster[int.from_bytes(digest, "big") % len(roster)]


def pool_fingerprint() -> list[dict]:
    """Roster identity for contract_identity(): a provider added/removed/
    re-modeled must show up in the extraction contract."""
    return [{"name": ep.name, "url": ep.url, "model": ep.model}
            for ep in cloud_endpoints()]
