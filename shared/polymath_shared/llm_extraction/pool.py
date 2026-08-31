"""EXTRACTION-POOL-V1 — the multi-provider cloud endpoint pool.

Owner directive (2026-08-30): lanes work their own backlog hard, steal
the other lane's when idle, and future cloud providers "assist" by
joining a router pool. This module is the POOL half; the stealing half
is lane-affinity claiming in worker_runtime.claim_ticket_events.

Design laws:

  - Lane policy is policy.py's alone (owner rule v2: throughput router +
    explicit assist); the pool only decides WHICH cloud endpoint serves
    a cloud dispatch, never whether a document may go cloud.
  - Endpoint choice is DETERMINISTIC per document (blake2b(doc_id) over
    the enabled roster, sorted by name): a crash/replay re-selects the
    same endpoint, receipts stay attributable, and N providers shard the
    cloud backlog evenly without any coordination state.
  - One endpoint (today's config) degenerates to exactly the old
    behavior — same url, same model, same limiter key.

Registering a new provider (MULTI-PROVIDER-AUTH-V1): the durable way is
config/cloud_providers.json — Groq and NVIDIA ship pre-configured there,
and a provider ACTIVATES the moment its api_key_env resolves (process
env, then the repo .env). POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS remains as
an env-only override lane for ad-hoc endpoints. Each endpoint gets its
own AIMD limiter lane (keyed by name), so a slow provider throttles
itself without dragging the others down. Keys are runtime auth material:
never in this file, never in fingerprints, never in logs.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from polymath_shared.settings import get_settings

log = logging.getLogger("extraction-pool")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROVIDERS_FILE = _REPO_ROOT / "config" / "cloud_providers.json"
_ENV_FILE = _REPO_ROOT / ".env"


@dataclass(frozen=True)
class CloudEndpoint:
    name: str
    url: str
    model: str
    # MULTI-PROVIDER-AUTH-V1: the key is runtime auth material — excluded
    # from repr and NEVER part of pool_fingerprint()/contract identity.
    api_key: str | None = field(default=None, repr=False)
    # per-endpoint payload quirks (see config/cloud_providers.json _doc)
    reasoning_effort: str | None = None
    json_mode: bool = True
    # STRUCTURED-CAPABILITY-V1: the strongest output method this endpoint
    # supports — "schema" (native strict JSON Schema), "json" (object
    # mode), "text" (prompt-only). Local parse→validate→sanitize ALWAYS
    # runs regardless of level: provider structured output is an
    # optimization, our validator is the contract. "schema" is accepted
    # in config but currently DOWNGRADED to "json" at dispatch (measured:
    # the primary daemon silently ignores json_schema strict:true) until
    # a provider passes a strict-schema canary; the field exists so that
    # upgrade is a config flip, not a code change.
    structured: str = "json"
    # DEDICATED-V1: a dedicated endpoint serves ONLY stages pinned to it
    # (stage_pins); it never joins the general extraction sharding — its
    # rate budget is reserved for its stage.
    dedicated: bool = False

    @property
    def limiter_key(self) -> str:
        # the primary keeps the historical limiter lane ("default") so
        # its AIMD state and seeds carry over; extras get their own.
        return "default" if self.name == "primary" else self.name

    @property
    def cloud_opts(self) -> dict:
        # "schema" now DISPATCHES level-1 (client sends the packet
        # json_schema) — declare it only after a live canary on that
        # provider+model (STRICT-SCHEMA-V1; verified Groq qwen3.8-27b).
        return {"reasoning_effort": self.reasoning_effort,
                "structured": self.structured,
                "json_mode": self.structured in ("schema", "json")}


def _resolve_key(env_name: str) -> str | None:
    """Process env first, then the repo .env (gitignored) — the fleet's
    workers inherit the supervisor's env, which may predate a key drop,
    so the .env file is the durable source."""
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    try:
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{env_name}="):
                v = line.split("=", 1)[1].strip().strip("'\"")
                if v:
                    return v
    except OSError:
        pass
    return None


_ROSTER_LOGGED: set[tuple] = set()


def _structured_level(e: dict) -> str:
    """Capability negotiation input: explicit `structured` wins; legacy
    `json_mode: false` means "text"; default "json"."""
    level = str(e.get("structured") or "").strip().lower()
    if level:
        if level not in ("schema", "json", "text"):
            raise ValueError(
                f"structured must be schema|json|text, got {level!r} "
                f"for {e.get('name')!r}")
        return level
    return "json" if e.get("json_mode", True) else "text"


def _configured_providers() -> list[CloudEndpoint]:
    """Providers from config/cloud_providers.json. AUTO-GATE: a provider
    joins iff enabled is not false AND its key resolves — setup for a
    new provider is pasting the key into .env. The gate is surfaced,
    never silent: every roster composition is logged once."""
    try:
        raw = json.loads(_PROVIDERS_FILE.read_text())
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{_PROVIDERS_FILE} is not valid JSON: {exc}")
    out: list[CloudEndpoint] = []
    for e in raw.get("providers") or []:
        name = str(e.get("name") or "").strip()
        if not name or name == "primary":
            raise ValueError(f"provider needs a non-reserved name: {e!r}")
        if e.get("enabled") is False:
            continue
        key_env = str(e.get("api_key_env") or "").strip()
        key = _resolve_key(key_env) if key_env else None
        if key_env and not key:
            _log_once(("parked", name),
                      "cloud provider %r parked: %s not set (drop the key "
                      "in .env to activate)", name, key_env)
            continue
        url = str(e.get("url") or "").strip()
        model = str(e.get("model") or "").strip()
        if not (url and model):
            raise ValueError(f"provider {name!r} needs url+model: {e!r}")
        out.append(CloudEndpoint(
            name=name, url=url, model=model, api_key=key,
            reasoning_effort=e.get("reasoning_effort"),
            json_mode=bool(e.get("json_mode", True)),
            structured=_structured_level(e),
            dedicated=bool(e.get("dedicated", False))))
    return out


def _log_once(token: tuple, msg: str, *args) -> None:
    if token not in _ROSTER_LOGGED:
        _ROSTER_LOGGED.add(token)
        log.info(msg, *args)


def cloud_endpoints() -> list[CloudEndpoint]:
    """The enabled roster, sorted by name. Always >= 1 (the primary from
    settings). Extras come from POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS
    (JSON list of {name, url, model}); malformed JSON fails LOUDLY —
    a silently-dropped provider would look like a half-speed pool."""
    s = get_settings().sidecars
    roster = [CloudEndpoint("primary", s.llm_cloud_url, s.llm_cloud_model)]
    roster.extend(_configured_providers())
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
            key_env = str(e.get("api_key_env") or "").strip()
            roster.append(CloudEndpoint(
                name=name, url=url, model=model,
                api_key=_resolve_key(key_env) if key_env else None,
                reasoning_effort=e.get("reasoning_effort"),
                json_mode=bool(e.get("json_mode", True)),
                structured=_structured_level(e)))
    roster.sort(key=lambda ep: ep.name)
    names = [ep.name for ep in roster]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate cloud endpoint names: {names}")
    _log_once(("roster", tuple(names)),
              "cloud extraction pool: %s", ", ".join(names))
    return roster


class PinnedProviderUnavailable(RuntimeError):
    """A stage is DEDICATED to a provider that is not active (no key /
    enabled:false / missing from the registry). Loud by design — a
    dedicated stage must never silently spend another provider."""


def stage_pin(stage: str) -> list[str] | None:
    """The pin for a stage as a GROUP (a single name is a group of one).
    DUAL-LANE (owner 2026-08-30): unlinked accounts with separate rate
    buckets pin as a list and shard the stage's docs between them."""
    try:
        raw = json.loads(_PROVIDERS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    pin = (raw.get("stage_pins") or {}).get(stage)
    if not pin:
        return None
    if isinstance(pin, str):
        return [pin.strip()]
    return [str(x).strip() for x in pin if str(x).strip()]


def select_endpoint_for_stage(stage: str, doc_id: str) -> CloudEndpoint:
    """STAGE-PIN-V1: a pinned stage dispatches ONLY within its pin group
    — deterministic doc-hash sharding across the group's ACTIVE members
    (each unlinked account is its own rate bucket and AIMD lane). A
    partially-dark group runs on the remaining members (logged once);
    an entirely-dark group fails loudly — a dedicated stage never
    silently spends an unpinned provider. Unpinned stages shard the
    whole roster."""
    pin = stage_pin(stage)
    if pin is None:
        return select_cloud_endpoint(doc_id)
    active = [ep for ep in cloud_endpoints() if ep.name in pin]
    if not active:
        raise PinnedProviderUnavailable(
            f"stage {stage!r} is dedicated to {pin!r}, none of which are "
            f"active (no key in .env, enabled:false, or absent from "
            f"config/cloud_providers.json) — activate one or remove the pin")
    if len(active) < len(pin):
        dark = sorted(set(pin) - {ep.name for ep in active})
        _log_once(("pin-partial", stage, tuple(dark)),
                  "stage %r pin group running at reduced capacity: %s "
                  "inactive", stage, ", ".join(dark))
    if len(active) == 1:
        return active[0]
    digest = hashlib.blake2b((doc_id or "").encode(), digest_size=8).digest()
    return active[int.from_bytes(digest, "big") % len(active)]


def select_cloud_endpoint(doc_id: str) -> CloudEndpoint:
    """Deterministic doc -> endpoint assignment over the enabled,
    NON-DEDICATED roster (dedicated endpoints serve only their pinned
    stages — DEDICATED-V1)."""
    roster = [ep for ep in cloud_endpoints() if not ep.dedicated]
    if not roster:
        roster = cloud_endpoints()   # everything dedicated: fail open, loudly
        _log_once(("all-dedicated",),
                  "every cloud endpoint is dedicated; general dispatch "
                  "falling back to the full roster")
    if len(roster) == 1:
        return roster[0]
    digest = hashlib.blake2b((doc_id or "").encode(), digest_size=8).digest()
    return roster[int.from_bytes(digest, "big") % len(roster)]


def pool_fingerprint() -> list[dict]:
    """Roster identity for contract_identity(): a provider added/removed/
    re-modeled must show up in the extraction contract."""
    return [{"name": ep.name, "url": ep.url, "model": ep.model,
             "reasoning_effort": ep.reasoning_effort,
             "structured": ep.structured, "dedicated": ep.dedicated}
            for ep in cloud_endpoints()]
