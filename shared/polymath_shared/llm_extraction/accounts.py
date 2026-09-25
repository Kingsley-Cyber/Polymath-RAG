"""LLM-BACKEND L1 — the provider account registry (register 11.465; gap L-01).

`config/llm_accounts.yaml` is the one place that says which ACCOUNTS exist (one API key = one account), which models
each account serves under which provider quota, and which lanes (account × model × stage use) are configured. The
runtime still reads `config/cloud_providers.json` and `config/extraction_models/limiter.yaml`; this module compiles the
registry into exactly those two structures and checks there is no drift, so the registry is the authoring surface and
the runtime files are its output (L3 writes them from here; L1 changes no behaviour).

Secrets never live here: the registry names the env variables, and every check reports only whether a variable is set.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_FILE = REPO_ROOT / "config" / "llm_accounts.yaml"
PROVIDERS_FILE = REPO_ROOT / "config" / "cloud_providers.json"
LIMITER_FILE = REPO_ROOT / "config" / "extraction_models" / "limiter.yaml"

#: lane fields that belong to the ACCOUNT, re-attached to every lane when compiling
ACCOUNT_FIELDS = ("api_key_env", "account_id_env")


@dataclass(frozen=True)
class Lane:
    name: str
    account: str
    model: str
    fields: dict[str, Any]              # the provider entry's own fields, verbatim (minus name / account fields)
    limiter: dict[str, Any] | None      # the lane's limiter.yaml entry, verbatim

    @property
    def enabled(self) -> bool:
        return self.fields.get("enabled", True) is not False

    @property
    def dedicated(self) -> bool:
        return bool(self.fields.get("dedicated", False))


@dataclass(frozen=True)
class Account:
    name: str
    provider: str
    key_env: str
    account_id_env: str | None
    quota: dict[str, dict[str, Any]]    # model -> the provider's own limits for this account (rpm, rpd, tpm, tpd, otpm)
    notes: str = ""
    lanes: tuple[Lane, ...] = ()


@dataclass(frozen=True)
class Registry:
    version: int
    docs: list[str]
    stage_pins: dict[str, list[str]]
    slots: dict[str, dict[str, Any]]
    local_limiters: dict[str, dict[str, Any]]
    accounts: dict[str, Account]
    lanes: dict[str, Lane] = field(default_factory=dict)


def load_registry(path: Path | str = REGISTRY_FILE) -> Registry:
    raw = yaml.safe_load(Path(path).read_text())
    accounts: dict[str, Account] = {}
    lanes: dict[str, Lane] = {}
    for aname, a in (raw.get("accounts") or {}).items():
        acct_lanes = []
        for lname, l in (a.get("lanes") or {}).items():
            if lname in lanes:
                raise ValueError(f"lane {lname!r} is declared under two accounts")
            body = dict(l or {})
            limiter = body.pop("limiter", None)
            model = str(body.get("model") or "")
            lane = Lane(lname, aname, model, body, limiter)
            lanes[lname] = lane
            acct_lanes.append(lane)
        accounts[aname] = Account(aname, str(a["provider"]), str(a["key_env"]), a.get("account_id_env"),
                                  dict(a.get("quota") or {}), str(a.get("notes") or ""), tuple(acct_lanes))
    return Registry(int(raw.get("version", 1)), list(raw.get("docs") or []), dict(raw.get("stage_pins") or {}),
                    dict(raw.get("slots") or {}), dict(raw.get("local_limiters") or {}), accounts, lanes)


def compile_runtime(reg: Registry) -> tuple[dict, dict]:
    """(cloud_providers.json, limiter.yaml) as data, exactly what the runtime reads."""
    providers = []
    limiter: dict[str, Any] = {}
    for acct in reg.accounts.values():
        for lane in acct.lanes:
            entry = {"name": lane.name, **lane.fields, "api_key_env": acct.key_env}
            if acct.account_id_env:
                entry["account_id_env"] = acct.account_id_env
            providers.append(entry)
            if lane.limiter is not None:
                limiter[lane.name] = dict(lane.limiter)
    limiter.update({k: dict(v) for k, v in reg.local_limiters.items()})
    return ({"_doc": list(reg.docs), "stage_pins": dict(reg.stage_pins), "providers": providers},
            {"providers": limiter})


def runtime_drift(reg: Registry, providers_path: Path = PROVIDERS_FILE, limiter_path: Path = LIMITER_FILE) -> list[str]:
    """Every difference between the compiled registry and the checked-in runtime files (empty = no drift).
    Provider order is ignored: the runtime sorts its roster by name and pins name their lanes explicitly."""
    want_p, want_l = compile_runtime(reg)
    have_p = json.loads(Path(providers_path).read_text())
    have_l = yaml.safe_load(Path(limiter_path).read_text())
    out: list[str] = []
    if want_p["_doc"] != have_p.get("_doc"):
        out.append("_doc differs")
    if want_p["stage_pins"] != have_p.get("stage_pins"):
        out.append("stage_pins differ")
    wp = {e["name"]: e for e in want_p["providers"]}
    hp = {e["name"]: e for e in have_p.get("providers") or []}
    for n in sorted(set(wp) | set(hp)):
        if n not in hp:
            out.append(f"provider {n}: only in the registry")
        elif n not in wp:
            out.append(f"provider {n}: only in cloud_providers.json")
        elif wp[n] != hp[n]:
            keys = sorted(k for k in set(wp[n]) | set(hp[n]) if wp[n].get(k) != hp[n].get(k))
            out.append(f"provider {n}: fields differ {keys}")
    wl, hl = want_l["providers"], (have_l or {}).get("providers") or {}
    for n in sorted(set(wl) | set(hl)):
        if wl.get(n) != hl.get(n):
            out.append(f"limiter {n}: differs")
    return out


@dataclass(frozen=True)
class Finding:
    level: str       # "error" | "warning"
    code: str
    message: str


def _pinned(reg: Registry) -> dict[str, list[str]]:
    by_lane: dict[str, list[str]] = {}
    for stage, lanes in reg.stage_pins.items():
        for n in lanes if isinstance(lanes, list) else [lanes]:
            by_lane.setdefault(n, []).append(stage)
    return by_lane


def lane_uses(reg: Registry) -> dict[str, list[str]]:
    """Which stages can call each enabled lane: its pins, plus the extraction pool for enabled non-dedicated lanes."""
    uses = {n: list(s) for n, s in _pinned(reg).items()}
    for n, lane in reg.lanes.items():
        if lane.enabled and not lane.dedicated:
            uses.setdefault(n, []).append("extract")
    return uses


def validate(reg: Registry, env: dict[str, str] | None = None) -> list[Finding]:
    env = os.environ if env is None else env
    f: list[Finding] = []
    for stage, lanes in reg.stage_pins.items():
        for n in lanes if isinstance(lanes, list) else [lanes]:
            if n not in reg.lanes:
                f.append(Finding("error", "PIN_UNKNOWN_LANE", f"stage {stage} pins unknown lane {n}"))
    # W1 — a limiter family must not span accounts (one account's 429 storm must never freeze another account)
    fam_accounts: dict[str, set[str]] = {}
    for lane in reg.lanes.values():
        fam = (lane.limiter or {}).get("family")
        if fam:
            fam_accounts.setdefault(fam, set()).add(lane.account)
    for fam, accts in sorted(fam_accounts.items()):
        if len(accts) > 1:
            f.append(Finding("warning", "FAMILY_SPANS_ACCOUNTS", f"limiter family {fam} spans {len(accts)} accounts: "
                                                                 f"{', '.join(sorted(accts))}"))
    # W2 — a dedicated (account, model) pair reached by more than one worker slot at once
    uses = lane_uses(reg)
    for (acct, model), lanes in sorted(_pairs(reg).items()):
        stages = {s for n in lanes if reg.lanes[n].enabled and reg.lanes[n].dedicated for s in uses.get(n, [])}
        slots = sum(int((reg.slots.get(s) or {}).get("count", 1)) for s in stages)
        if slots > 1 and any(reg.lanes[n].dedicated for n in lanes):
            f.append(Finding("warning", "PAIR_SHARED_BY_SLOTS", f"{acct} × {model}: up to {slots} worker slots "
                                                                f"({', '.join(sorted(stages))}) share one quota"))
    # W3 — a quota the owner pays for with no enabled, used lane
    for acct in reg.accounts.values():
        for model in acct.quota:
            active = [lane for lane in acct.lanes if lane.model == model and lane.enabled and uses.get(lane.name)]
            if not active:
                f.append(Finding("warning", "IDLE_PAIR", f"{acct.name} × {model}: quota declared, no enabled lane uses it"))
    # W6 (L2) — per-process budgets times the worker slots that can reach a pair must fit the pair's quota
    for acct in reg.accounts.values():
        for model, quota in acct.quota.items():
            lanes = [lane for lane in acct.lanes if lane.model == model and lane.enabled and uses.get(lane.name)]
            for metric in ("rpd", "tpd", "tpm", "otpm"):
                cap = quota.get(metric)
                if not cap:
                    continue
                total = 0
                for lane in lanes:
                    per_process = (lane.limiter or {}).get(metric)
                    if per_process:
                        slots = sum(int((reg.slots.get(s) or {}).get("count", 1)) for s in uses.get(lane.name, []))
                        total += int(per_process) * max(slots, 1)
                if total > int(cap):
                    f.append(Finding("warning", "BUDGET_EXCEEDS_QUOTA",
                                     f"{acct.name} × {model}: {metric} budgets reach {total:,} against a quota of {int(cap):,}"))
    # W4 — credentials the registry names but the environment lacks (booleans only)
    for acct in reg.accounts.values():
        if not (env.get(acct.key_env) or "").strip():
            f.append(Finding("warning", "KEY_UNSET", f"{acct.name}: {acct.key_env} is not set"))
        if acct.account_id_env and not (env.get(acct.account_id_env) or "").strip():
            f.append(Finding("warning", "ACCOUNT_ID_UNSET", f"{acct.name}: {acct.account_id_env} is not set"))
    # W5 — enabled lanes nothing can call
    for n, lane in sorted(reg.lanes.items()):
        if lane.enabled and not uses.get(n):
            f.append(Finding("warning", "LANE_UNUSED", f"lane {n} is enabled but no stage can call it"))
    return f


def _pairs(reg: Registry) -> dict[tuple[str, str], list[str]]:
    pairs: dict[tuple[str, str], list[str]] = {}
    for lane in reg.lanes.values():
        pairs.setdefault((lane.account, lane.model), []).append(lane.name)
    return pairs


def ownership_rows(reg: Registry, env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """One row per (account, model): who can call it, with what quota, and whether its credentials are set.
    Values of secrets are never read into the output, only whether they are set."""
    env = os.environ if env is None else env
    uses = lane_uses(reg)
    rows = []
    for acct in reg.accounts.values():
        models = list(dict.fromkeys([*acct.quota, *(lane.model for lane in acct.lanes)]))
        for model in models:
            lanes = [lane for lane in acct.lanes if lane.model == model]
            active = [lane for lane in lanes if lane.enabled and uses.get(lane.name)]
            stages = sorted({s for lane in active for s in uses.get(lane.name, [])})
            key_set = bool((env.get(acct.key_env) or "").strip())
            acct_id_set = bool((env.get(acct.account_id_env) or "").strip()) if acct.account_id_env else None
            # the runtime parks a lane whose key or account id is unset (pool._configured_providers)
            state = ("parked" if active and (not key_set or acct_id_set is False)
                     else "active" if active else "idle")
            rows.append({
                "account": acct.name, "provider": acct.provider, "model": model,
                "lanes": [f"{lane.name}{'' if lane.enabled else ' (off)'}" for lane in lanes],
                "stages": stages,
                "slots": sum(int((reg.slots.get(s) or {}).get("count", 1)) for s in stages),
                "quota": acct.quota.get(model) or {},
                "key_set": key_set,
                "account_id_set": acct_id_set,
                "state": state,
            })
    return rows
