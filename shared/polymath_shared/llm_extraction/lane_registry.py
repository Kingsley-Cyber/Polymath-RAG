"""LANE-REGISTRY-V1 (RAG-PIPELINE-FINISH Phase 2) — the explicit, sanitized
account/model lane registry + query views over the provider control plane.

The pool (`pool.py`) decides WHICH endpoint serves a dispatch and the limiter
(`limiter.py`) owns per-lane admission; neither exposes a queryable inventory of
"which functional pool does each account/model lane serve, is its credential
present, is it reachable, what is its declared capacity". This module builds that
view from the SAME configuration those layers read:

    config/cloud_providers.json          endpoints + stage_pins
    config/extraction_models/limiter.yaml per-lane family + capacity seeds

and resolves credential PRESENCE — never the value. No secret ever enters the
registry: `api_key_env` names the variable, `credential_present` is a bool, and
the key string is never read into a field, rendered, or logged. This is the
Phase-2 deliverable (one-key-one-account made explicit) and the Phase-3 effective
-capacity table's substrate; it is pure policy (reads config + env presence, no
network, no provider call), so the offline acceptance gate can print it.

Functional-pool mapping (plan §1.1 — purposes, not providers):

    CHAT              stage_pins.chat_compiler
    GRAPH_EXTRACTION  the unpinned/non-dedicated cloud ring + the settings primary
    DOCUMENT_PROFILE  stage_pins.doc_profile
    PMAP              stage_pins.doc_parent_map

`parent_enrichment` is reported as a legacy BRIDGE surface (plan §1.12), not a
fifth permanent pool. A lane name is 1:1 with a function; cross-function credential
sharing (the six Groq accounts serving DOCUMENT_PROFILE via compound and PMAP via
compound-mini) is visible in the by-account view, exactly as the plan requires.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROVIDERS_FILE = _REPO_ROOT / "config" / "cloud_providers.json"
_LIMITER_FILE = _REPO_ROOT / "config" / "extraction_models" / "limiter.yaml"
_ENV_FILE = _REPO_ROOT / ".env"

LANE_REGISTRY_VERSION = "lane-registry-v1"

# Functional pools (plan §1.1) keyed by the stage pin that dedicates lanes to them.
CHAT = "CHAT"
GRAPH_EXTRACTION = "GRAPH_EXTRACTION"
DOCUMENT_PROFILE = "DOCUMENT_PROFILE"
PMAP = "PMAP"
PARENT_ENRICHMENT = "parent_enrichment"  # legacy bridge, not a permanent pool

#: stage pin name -> functional pool
_PIN_FUNCTION = {
    "chat_compiler": CHAT,
    "doc_profile": DOCUMENT_PROFILE,
    "doc_parent_map": PMAP,
    "parent_enrichment": PARENT_ENRICHMENT,
}

#: DAG stage name -> functional pool (the ingestion mapping the pool-metrics view
#: joins against stage_tickets). `extract` is the unpinned GRAPH_EXTRACTION ring;
#: the pinned stages map through their pin. Stages absent here have no LLM pool.
STAGE_TO_FUNCTION = {
    "extract": GRAPH_EXTRACTION,
    "doc_profile": DOCUMENT_PROFILE,
    "doc_parent_map": PMAP,
    "parent_enrichment": PARENT_ENRICHMENT,
    "chat_compiler": CHAT,
}


def functional_pool_of(stage: str) -> str | None:
    """The functional pool that drains a DAG stage's LLM work, or None if the stage
    uses no provider pool (intake/projection/summary stages)."""
    return STAGE_TO_FUNCTION.get(stage)


#: the measured compound-mini structured-output reliability cap — the pMAP batch-size
#: default when a lane declares no `map_batch_cap` (11.178 / MAP_RELIABILITY_CAP).
PMAP_DEFAULT_BATCH_CAP = 15


def pmap_pool_batch_cap(registry: "LaneRegistry | None" = None,
                        default: int = PMAP_DEFAULT_BATCH_CAP) -> int:
    """The pMAP pool's qualified batch cap = the MIN `map_batch_cap` over its ACTIVE
    lanes (so every planned batch is drainable by every lane — the pool-drain
    invariant). A lane without a declared cap uses ``default``. A homogeneous pool that
    qualifies at 60 returns 60 (architectural target honored); today's compound-mini
    pool returns 15. No active PMAP lane => the default."""
    reg = registry or build_registry()
    active = [l for l in reg.by_function().get(PMAP, []) if l.reachability == ACTIVE]
    if not active:
        return default
    return min((l.map_batch_cap or default) for l in active)

# reachability states (static; runtime cooldown/breaker is NOT config and is
# excluded so the offline gate is deterministic — see `runtime_note`).
ACTIVE = "active"                              # enabled and credential present
CREDENTIAL_ABSENT = "configured_credential_absent"  # enabled, key not in env/.env (parked)
DISABLED = "disabled"                          # enabled: false


def _credential_present(env_name: str) -> bool:
    """True iff the api_key_env resolves (process env, then repo .env). Mirrors
    pool._resolve_key but returns ONLY a boolean — the value is never retained."""
    if not env_name:
        return True  # a lane with no api_key_env (e.g. the local primary) needs no key
    if os.environ.get(env_name, "").strip():
        return True
    try:
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{env_name}=") and line.split("=", 1)[1].strip().strip("'\""):
                return True
    except OSError:
        pass
    return False


def _load_providers() -> dict:
    try:
        return json.loads(_PROVIDERS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_limiter() -> dict:
    try:
        import yaml
        return (yaml.safe_load(_LIMITER_FILE.read_text()) or {}).get("providers", {}) or {}
    except Exception:  # noqa: BLE001 — availability-neutral; a missing/broken limiter.yaml yields no seeds
        return {}


@dataclass(frozen=True)
class LaneCapacity:
    """The DECLARED (config-seed) capacity of a lane — a seed/ceiling, not runtime
    truth. Runtime provider headers and measured envelopes are higher authority
    (plan §1.7); this is what the scheduler starts from."""
    kind: str | None = None            # rate | concurrency
    rpm: int | None = None
    tpm: int | None = None
    rpd: int | None = None             # per-account daily requests (Groq); UNVERIFIED vs headers
    conc_cap: int | None = None
    family: str | None = None          # limiter isolation/damp family (e.g. groq_acct_1)
    request_char_budget: int | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class LaneInfo:
    name: str
    function: str
    api_key_env: str                   # NAME only, never the value
    account_id: str                    # = api_key_env (one key = one account lane, plan §1.5)
    model: str
    provider_host: str                 # URL netloc = pool._family_of interleave family
    dedicated: bool
    role: str                          # primary | fallback | ring | pinned
    reachability: str
    credential_present: bool
    enabled: bool
    capacity: LaneCapacity = field(default_factory=LaneCapacity)
    #: LANE-QUALIFIED pMAP batch cap (RAG-PIPELINE-FINISH Phase 7): max aliases/request
    #: this lane's model reliably maps. None => the global MAP_RELIABILITY_CAP default.
    #: Distinct from provider RPM/TPM — a WORKLOAD capability, not a rate limit.
    map_batch_cap: int | None = None

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "capacity"}
        d["capacity"] = self.capacity.to_dict()
        return d


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url or "").netloc or ""


def _role_for(name: str, dedicated: bool, in_pin: bool) -> str:
    low = name.lower()
    if "fallback" in low:
        return "fallback"
    if in_pin:
        return "pinned"
    if dedicated:
        return "dedicated"
    return "ring"


def build_lanes() -> list[LaneInfo]:
    """Every CONFIGURED lane (active AND parked), with its function, account,
    reachability and declared capacity. Deterministic order (function, name)."""
    providers_raw = _load_providers()
    limiter = _load_limiter()
    stage_pins = providers_raw.get("stage_pins") or {}
    # name -> function, from the pins (a name absent from every pin is ring/GRAPH_EXTRACTION)
    pinned_function: dict[str, str] = {}
    for stage, names in stage_pins.items():
        fn = _PIN_FUNCTION.get(stage)
        if fn is None:
            continue
        for n in (names if isinstance(names, list) else [names]):
            pinned_function[str(n).strip()] = fn

    lanes: list[LaneInfo] = []

    # 1) the settings primary (local Ollama) — always in the roster, GRAPH_EXTRACTION.
    try:
        from polymath_shared.settings import get_settings
        s = get_settings().sidecars
        prim = limiter.get("ollama_cloud", {}) if isinstance(limiter, dict) else {}
        lanes.append(LaneInfo(
            name="primary", function=GRAPH_EXTRACTION, api_key_env="", account_id="local:primary",
            model=str(getattr(s, "llm_cloud_model", "") or ""), provider_host=_host(getattr(s, "llm_cloud_url", "")),
            dedicated=False, role="primary", reachability=ACTIVE, credential_present=True, enabled=True,
            capacity=LaneCapacity(kind=prim.get("kind"), rpm=prim.get("rpm"), tpm=prim.get("tpm"),
                                  conc_cap=prim.get("conc_cap"), family=prim.get("family"))))
    except Exception:  # noqa: BLE001 — settings unavailable in a bare test env; the config lanes still build
        pass

    # 2) every configured cloud provider.
    for e in providers_raw.get("providers") or []:
        name = str(e.get("name") or "").strip()
        if not name:
            continue
        api_key_env = str(e.get("api_key_env") or "").strip()
        enabled = e.get("enabled") is not False
        present = _credential_present(api_key_env)
        dedicated = bool(e.get("dedicated", False))
        in_pin = name in pinned_function
        function = pinned_function.get(name, GRAPH_EXTRACTION if not dedicated else "dedicated_unpinned")
        if not enabled:
            reach = DISABLED
        elif present:
            reach = ACTIVE
        else:
            reach = CREDENTIAL_ABSENT
        seed = limiter.get(name, {}) if isinstance(limiter, dict) else {}
        lanes.append(LaneInfo(
            name=name, function=function, api_key_env=api_key_env,
            account_id=api_key_env or f"anon:{name}", model=str(e.get("model") or ""),
            provider_host=_host(e.get("url") or ""), dedicated=dedicated,
            role=_role_for(name, dedicated, in_pin), reachability=reach,
            credential_present=present, enabled=enabled,
            capacity=LaneCapacity(
                kind=seed.get("kind"), rpm=seed.get("rpm"), tpm=seed.get("tpm"),
                rpd=seed.get("rpd"), conc_cap=seed.get("conc_cap"), family=seed.get("family"),
                request_char_budget=e.get("request_char_budget")),
            map_batch_cap=e.get("map_batch_cap")))

    lanes.sort(key=lambda l: (l.function, l.name))
    return lanes


@dataclass(frozen=True)
class LaneRegistry:
    version: str
    lanes: tuple[LaneInfo, ...]

    # ----- query views (plan §2) ---------------------------------------------
    def by_function(self) -> dict[str, list[LaneInfo]]:
        out: dict[str, list[LaneInfo]] = {}
        for l in self.lanes:
            out.setdefault(l.function, []).append(l)
        return out

    def by_account(self) -> dict[str, list[LaneInfo]]:
        """account/key -> the lanes (functions × models) consuming it. This is
        where cross-function credential sharing (Groq compound + compound-mini on
        one key) becomes visible."""
        out: dict[str, list[LaneInfo]] = {}
        for l in self.lanes:
            out.setdefault(l.account_id, []).append(l)
        return out

    def by_model(self) -> dict[str, list[LaneInfo]]:
        out: dict[str, list[LaneInfo]] = {}
        for l in self.lanes:
            out.setdefault(l.model or "(unset)", []).append(l)
        return out

    def shared_accounts(self) -> dict[str, set[str]]:
        """account_id -> {functions} where more than one function shares it — the
        explicit-Groq-exception audit (plan §1.5 rule 7)."""
        acc_fns: dict[str, set[str]] = {}
        for l in self.lanes:
            acc_fns.setdefault(l.account_id, set()).add(l.function)
        return {a: fns for a, fns in acc_fns.items() if len(fns) > 1}

    def pool_lane_health(self) -> dict[str, dict]:
        """Per functional pool: total / active / credential-absent / disabled lane
        counts — the 'healthy qualified lanes' signal the pool-drain invariant and
        the canonical status (Phase 12) report. Provider-free (config truth)."""
        out: dict[str, dict] = {}
        for fn, lanes in self.by_function().items():
            active = [l for l in lanes if l.reachability == ACTIVE]
            out[fn] = {
                "total": len(lanes),
                "active": len(active),
                "credential_absent": sum(1 for l in lanes if l.reachability == CREDENTIAL_ABSENT),
                "disabled": sum(1 for l in lanes if l.reachability == DISABLED),
                "active_lanes": sorted(l.name for l in active),
            }
        return out

    def reachability(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {ACTIVE: [], CREDENTIAL_ABSENT: [], DISABLED: []}
        for l in self.lanes:
            out.setdefault(l.reachability, []).append(l.name)
        return out

    def unreachable_pins(self) -> dict[str, list[str]]:
        """A functional pool whose lanes are ALL non-active is a loud defect — the
        stage would raise PinnedProviderUnavailable. Returns function -> dark lanes
        only when the WHOLE pool is dark."""
        out: dict[str, list[str]] = {}
        for fn, lanes in self.by_function().items():
            if fn in ("dedicated_unpinned",):
                continue
            active = [l for l in lanes if l.reachability == ACTIVE]
            if lanes and not active:
                out[fn] = [l.name for l in lanes]
        return out

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "lanes": [l.to_dict() for l in self.lanes],
            "by_function": {fn: [l.name for l in ls] for fn, ls in self.by_function().items()},
            "shared_accounts": {a: sorted(f) for a, f in self.shared_accounts().items()},
            "reachability": self.reachability(),
            "unreachable_pins": self.unreachable_pins(),
        }


def build_registry() -> LaneRegistry:
    return LaneRegistry(version=LANE_REGISTRY_VERSION, lanes=tuple(build_lanes()))


def sanitized_inventory(reg: LaneRegistry | None = None) -> str:
    """A human-readable, SECRET-FREE inventory table (Phase-2/Phase-3 gate: the
    system can print effective capacity without a provider call). Never renders a
    key value — only its variable NAME and a present/absent flag."""
    reg = reg or build_registry()
    lines = [f"# LANE INVENTORY ({reg.version}) — no secrets; api_key_env is a NAME",
             f"{'function':<17} {'lane':<22} {'model':<26} {'account_env':<20} "
             f"{'reach':<26} {'cap(rpm/tpm/rpd/conc)':<22} family"]
    for l in reg.lanes:
        c = l.capacity
        cap = f"{c.rpm or '-'}/{c.tpm or '-'}/{c.rpd or '-'}/{c.conc_cap or '-'}"
        present = "yes" if l.credential_present else "NO"
        reach = f"{l.reachability}({present})"
        lines.append(f"{l.function:<17} {l.name:<22} {(l.model or '-'):<26} "
                     f"{(l.api_key_env or '-'):<20} {reach:<26} {cap:<22} {c.family or '-'}")
    shared = reg.shared_accounts()
    if shared:
        lines.append("")
        lines.append("# CROSS-FUNCTION CREDENTIAL SHARING (accounts serving >1 function):")
        for acc, fns in sorted(shared.items()):
            lines.append(f"  {acc}: {', '.join(sorted(fns))}")
    dark = reg.unreachable_pins()
    if dark:
        lines.append("")
        lines.append("# FULLY-DARK FUNCTIONAL POOLS (would raise PinnedProviderUnavailable):")
        for fn, lanes in sorted(dark.items()):
            lines.append(f"  {fn}: {', '.join(lanes)}")
    return "\n".join(lines)
