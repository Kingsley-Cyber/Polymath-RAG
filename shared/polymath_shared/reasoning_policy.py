"""REASONING-BOUNDARY-V1 RB2 — semantic role -> reasoning-BUDGET policy + provider adapter (pure).

The rest of Polymath stays provider-agnostic: a callsite says "this is a STRUCTURED_COMPILER call to model X
on API surface Y" and this module returns the concrete request params. Two budgets are kept SEPARATE so
reasoning can never truncate the structured contract:
  - reasoning budget: a CEILING (~≤300 for planners; simple calls use ~0), disabled or lowest-effort where a
    numeric budget isn't available.
  - output budget: set INDEPENDENTLY (≥250-350 for bridge/compiler JSON), never shared with reasoning.

Provider realities encoded (owner-authoritative intents; exact wire placement validated live):
  - Qwen 3.8 Chat Completions: `thinking_budget=N` + `preserve_thinking=false`; NEVER also `reasoning_effort`
    (invalid combo; `reasoning_effort=low`≈4096 = too big). Responses API: no `thinking_budget` -> disable/low.
  - Claude: `effort=low` (or disabled); no manual small budget (manual min 1024).
  - Gemini 3.x Flash: `thinking_level=low` (cannot fully disable).
  - DeepSeek v4: thinking disabled (returns empty otherwise).
  - Ollama (bridge): `think=false`.
EXTRACTION is intentionally absent here — it is contract-hash-locked and already off; do not route it through this.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# roles
BRIDGE = "BRIDGE"
STRUCTURED_COMPILER = "STRUCTURED_COMPILER"
REVIEWER = "REVIEWER"
CHAT_SYNTHESIS = "CHAT_SYNTHESIS"

# api surfaces
S_CHAT_COMPLETIONS = "chat_completions"   # the extraction httpx client (OpenAI-compat /v1/chat/completions)
S_LITELLM = "litellm"                      # litellm.completion (chat synthesis + reviewer)
S_RESPONSES = "responses"                  # OpenAI/Alibaba Responses API (no thinking_budget)
S_OLLAMA = "ollama"                        # native /api/chat|generate


@dataclass(frozen=True)
class RolePolicy:
    role: str
    preferred_max_reasoning_tokens: int | None   # numeric reasoning ceiling where supported; None = low/adaptive
    fallback_effort: str                          # when no numeric budget: "low" / "minimal"
    allow_reasoning_disable: bool                 # may we fully disable (planners/validators) vs only lower it
    target_output_tokens: int
    hard_output_tokens: int


ROLE_POLICIES: dict[str, RolePolicy] = {
    BRIDGE:              RolePolicy(BRIDGE, 200, "low", True, 300, 350),
    STRUCTURED_COMPILER: RolePolicy(STRUCTURED_COMPILER, 300, "low", True, 350, 500),
    REVIEWER:            RolePolicy(REVIEWER, 200, "low", True, 150, 200),
    CHAT_SYNTHESIS:      RolePolicy(CHAT_SYNTHESIS, None, "low", False, 2000, 6000),
}


def policy_enabled() -> bool:
    """The kill switch. When off (default), every callsite is a no-op -> pre-RB behaviour is byte-identical.
    Enabled only in the reasoning-qualification slice (Slice 2)."""
    return os.environ.get("POLYMATH_REASONING_POLICY", "0") == "1"


def _pol(role: str) -> RolePolicy:
    return ROLE_POLICIES.get(role) or ROLE_POLICIES[STRUCTURED_COMPILER]


def provider_family(model: str) -> str:
    m = (model or "").lower()
    if "deepseek" in m:
        return "deepseek"
    if "qwen" in m:
        return "qwen"
    if "gemini" in m:
        return "gemini"
    if "claude" in m or "anthropic" in m:
        return "claude"
    if "gpt" in m or "openai" in m:
        return "openai"
    return "other"


def _env_int(name: str, default: int | None) -> int | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def reasoning_params(role: str, model: str, api_surface: str = S_LITELLM) -> dict:
    """Concrete request params for (role, model, surface). Returns:
        {"top_level": {...}, "extra_body": {...}, "max_output_tokens": int}
    `top_level` merges into the request payload/kwargs; `extra_body` merges into the provider passthrough
    (litellm `extra_body` / OpenAI-compat `extra_body`); `max_output_tokens` is the SEPARATE output ceiling.
    Guarantees: never emits both `reasoning_effort` and `thinking_budget`; output budget is independent of
    the reasoning ceiling.
    """
    pol = _pol(role)
    fam = provider_family(model)
    budget = pol.preferred_max_reasoning_tokens
    # env override hook, e.g. POLYMATH_REASONING_MAX_STRUCTURED_COMPILER=300
    budget = _env_int(f"POLYMATH_REASONING_MAX_{role}", budget)
    out_cap = _env_int(f"POLYMATH_OUTPUT_MAX_{role}", pol.hard_output_tokens)

    top: dict = {}
    extra: dict = {}

    if fam == "qwen":
        if api_surface in (S_CHAT_COMPLETIONS, S_LITELLM) and budget is not None:
            # Chat Completions supports an explicit numeric reasoning budget. NOT reasoning_effort.
            params = {"thinking_budget": int(budget), "preserve_thinking": False}
            (top if api_surface == S_CHAT_COMPLETIONS else extra).update(params)
        else:
            # Responses API (no thinking_budget) or synthesis-low: disable thinking.
            params = {"enable_thinking": False, "preserve_thinking": False}
            (top if api_surface == S_CHAT_COMPLETIONS else extra).update(params)
    elif fam == "deepseek":
        extra["thinking"] = {"type": "disabled"}          # required or the model returns empty
    elif fam == "gemini":
        extra["thinking_level"] = "low"                   # cannot fully disable
    elif fam == "claude":
        extra["effort"] = pol.fallback_effort             # no manual small budget
    elif fam == "openai":
        top["reasoning_effort"] = pol.fallback_effort
    else:  # unknown provider: lowest-effort only if we cannot disable
        if not pol.allow_reasoning_disable:
            top["reasoning_effort"] = pol.fallback_effort

    if fam == "other" and api_surface == S_OLLAMA:
        top["think"] = False

    # INVARIANT: never both reasoning_effort and a numeric thinking budget.
    for bag in (top, extra):
        if "reasoning_effort" in bag and "thinking_budget" in bag:
            bag.pop("reasoning_effort")

    return {"top_level": top, "extra_body": extra, "max_output_tokens": int(out_cap) if out_cap else None}


def apply_litellm(kwargs: dict, role: str, model: str) -> dict:
    """Overlay the role's reasoning params onto a `litellm.completion` kwargs dict IN PLACE, ONLY when the
    policy is enabled (else a no-op -> byte-identical). Runtime overlay: nothing is written to any config or
    contract hash. Output budget stays with the caller's existing max_tokens logic. Returns the SANITIZED
    params applied (no secrets) for logging, or {} when disabled."""
    if not policy_enabled():
        return {}
    rp = reasoning_params(role, model, S_LITELLM)
    kwargs.update(rp["top_level"])
    if rp["extra_body"]:
        kwargs["extra_body"] = {**(kwargs.get("extra_body") or {}), **rp["extra_body"]}
    return {"role": role, "provider": provider_family(model), "surface": S_LITELLM,
            "top_level": dict(rp["top_level"]), "extra_body": dict(rp["extra_body"]),
            "max_output_tokens": rp["max_output_tokens"]}


def apply_chat_completions(payload: dict, role: str, model: str) -> dict:
    """Overlay reasoning params onto an OpenAI-compat /v1/chat/completions PAYLOAD in place, ONLY when the
    policy is enabled. For the chat-COMPILER stage only (never document extraction). Runtime overlay; no
    contract-hash change. Returns sanitized applied params (or {})."""
    if not policy_enabled():
        return {}
    rp = reasoning_params(role, model, S_CHAT_COMPLETIONS)
    payload.update(rp["top_level"])
    if rp["extra_body"]:
        payload["extra_body"] = {**(payload.get("extra_body") or {}), **rp["extra_body"]}
    return {"role": role, "provider": provider_family(model), "surface": S_CHAT_COMPLETIONS,
            "top_level": dict(rp["top_level"]), "extra_body": dict(rp["extra_body"]),
            "max_output_tokens": rp["max_output_tokens"]}
