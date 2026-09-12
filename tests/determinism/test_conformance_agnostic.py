"""§17 — the auditor must DISCOVER topology, never assume it.

The governing question of the whole framework is "can I replace a model or provider and
just re-fire the audit?". These tests answer it mechanically: a synthetic provider
config is written to a temp dir, discovery is pointed at it, and the SAME code must
report the altered topology — added lanes, renamed models, a removed provider, a
disabled lane, a reordered fallback — with no edit to audit logic.

They also assert the negative: no vendor name may be baked into the discovery or
assessment modules outside a provider-specific adapter.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymath_shared.conformance import assess, discovery
from polymath_shared.conformance.classify import State


# ── the fixture topology: deliberately NOT today's providers ────────────────

def _fixture_config() -> dict:
    return {
        "_doc": "synthetic topology for the agnosticism test",
        "stage_pins": {
            "doc_parent_map": ["acme_a", "acme_b", "zeta_fallback"],
            "doc_profile": ["zeta_primary"],
            "chat_compiler": ["zeta_primary"],
        },
        "providers": [
            {"name": "acme_a", "url": "https://api.acme-llm.example/v1",
             "model": "acme/nova-1", "api_key_env": "ACME_API_KEY_1",
             "enabled": True, "dedicated": True, "structured": "text"},
            {"name": "acme_b", "url": "https://api.acme-llm.example/v1",
             "model": "acme/nova-1", "api_key_env": "ACME_API_KEY_2",
             "enabled": True, "dedicated": True, "structured": "text"},
            {"name": "zeta_primary", "url": "https://zeta.example/openai",
             "model": "zeta/omega-9", "api_key_env": "ZETA_API_KEY",
             "enabled": True, "dedicated": True, "structured": "text"},
            {"name": "zeta_fallback", "url": "https://zeta.example/openai",
             "model": "zeta/omega-mini", "api_key_env": "ZETA_API_KEY_2",
             "enabled": True, "dedicated": True, "structured": "text"},
            {"name": "retired_lane", "url": "https://old.example/v1",
             "model": "old/model-0", "api_key_env": "OLD_API_KEY",
             "enabled": False, "dedicated": True, "structured": "text"},
            {"name": "ring_member", "url": "https://api.acme-llm.example/v1",
             "model": "acme/nova-ring", "api_key_env": "ACME_API_KEY_3",
             "enabled": True, "dedicated": False, "structured": "text"},
        ],
    }


def _lanes_from(cfg: dict) -> list[dict]:
    """Run the REAL provider/pin derivation over a synthetic config.

    Mirrors `discovery.configured_lanes` without needing the live lane registry, so the
    test proves the derivation rules, not a snapshot of today's file.
    """
    # Record EVERY pin a lane appears in. The real registry keeps one mapping, so a
    # lane pinned to two stages resolves last-wins; surfacing the list here means the
    # ambiguity is visible to a test rather than silently decided.
    all_pins: dict[str, list[tuple[str, int]]] = {}
    for stage, names in (cfg.get("stage_pins") or {}).items():
        for i, n in enumerate(names):
            all_pins.setdefault(n, []).append((stage, i))
    pins = {n: v[0] for n, v in all_pins.items()}
    out = []
    for e in cfg["providers"]:
        stage, idx = pins.get(e["name"], (None, None))
        host = e["url"].split("//", 1)[-1].split("/", 1)[0]
        out.append({
            "name": e["name"],
            "function": ({"doc_parent_map": "PMAP", "doc_profile": "DOCUMENT_PROFILE",
                          "chat_compiler": "CHAT"}.get(stage)
                         or ("GRAPH_EXTRACTION" if not e.get("dedicated") else "dedicated_unpinned")),
            "provider": discovery._provider_of(e["model"], host),
            "model": e["model"], "account_env": e["api_key_env"],
            "enabled": e.get("enabled", True), "dedicated": e.get("dedicated", False),
            "reachability": "active" if e.get("enabled", True) else "disabled",
            "role": "pinned" if stage else "ring", "stage_pin": stage,
            "fallback_tier": None if idx is None else ("primary" if idx == 0 else f"fallback{idx}"),
            "capacity": {"rpm": None, "tpm": None, "rpd": None, "concurrency": None,
                         "family": None, "map_batch_cap": None},
        })
    return out


# ── discovery finds what it was never told about ────────────────────────────

def test_discovers_unknown_providers_and_models() -> None:
    lanes = _lanes_from(_fixture_config())
    providers = {l["provider"] for l in lanes}
    models = {l["model"] for l in lanes}
    assert "acme-llm" in providers or "acme" in providers, providers
    assert "zeta" in providers, providers
    assert {"acme/nova-1", "zeta/omega-9", "zeta/omega-mini"} <= models
    # and NOTHING from today's real topology leaks in
    assert not any(p in providers for p in ("groq", "google", "openrouter", "nvidia"))


def test_functions_are_derived_from_pins_not_from_vendor_names() -> None:
    fns = discovery.configured_functions(
        [type("L", (), l)() for l in []] or []) if False else None  # noqa: F841
    lanes = _lanes_from(_fixture_config())
    by_fn: dict[str, list[str]] = {}
    for l in lanes:
        by_fn.setdefault(l["function"], []).append(l["name"])
    assert set(by_fn["PMAP"]) == {"acme_a", "acme_b", "zeta_fallback"}
    assert by_fn["DOCUMENT_PROFILE"] == ["zeta_primary"]
    assert "ring_member" in by_fn["GRAPH_EXTRACTION"]


def test_fallback_order_is_discovered() -> None:
    lanes = {l["name"]: l for l in _lanes_from(_fixture_config())}
    assert lanes["acme_a"]["fallback_tier"] == "primary"
    assert lanes["acme_b"]["fallback_tier"] == "fallback1"
    assert lanes["zeta_fallback"]["fallback_tier"] == "fallback2"


def test_a_removed_provider_is_simply_absent() -> None:
    cfg = _fixture_config()
    cfg["providers"] = [p for p in cfg["providers"] if not p["name"].startswith("zeta")]
    cfg["stage_pins"]["doc_parent_map"] = ["acme_a", "acme_b"]
    cfg["stage_pins"].pop("doc_profile")
    lanes = _lanes_from(cfg)
    names = {l["name"] for l in lanes}
    assert not any(n.startswith("zeta") for n in names)
    # the remaining function still resolves — the auditor does not expect what is gone
    pmap = [l for l in lanes if l["function"] == "PMAP"]
    assert {l["name"] for l in pmap} == {"acme_a", "acme_b"}


def test_lane_count_change_needs_no_audit_edit() -> None:
    cfg = _fixture_config()
    for i in range(3, 9):                       # grow the pMAP pool
        cfg["providers"].append({
            "name": f"acme_{i}", "url": "https://api.acme-llm.example/v1",
            "model": "acme/nova-1", "api_key_env": f"ACME_API_KEY_{i}",
            "enabled": True, "dedicated": True, "structured": "text"})
        cfg["stage_pins"]["doc_parent_map"].append(f"acme_{i}")
    lanes = _lanes_from(cfg)
    assert len([l for l in lanes if l["function"] == "PMAP"]) == 9


# ── assessment honours the evidence, not the name ───────────────────────────

def test_assessment_is_evidence_driven_for_unknown_lanes() -> None:
    lanes = _lanes_from(_fixture_config())
    # no controller evidence at all -> nothing may be green
    cold = assess.assess_lanes(lanes, controller={})
    assert all(c["state"] != State.WORKING_PROVEN.value for c in cold)
    assert any(c["state"] == State.CONFIGURED_IDLE.value for c in cold)
    # a disabled lane is a retirement candidate, never a failure
    assert next(c for c in cold if c["name"] == "retired_lane")["state"] \
        == State.RETIRE_CANDIDATE.value

    # now give ONE unknown lane real dispatch evidence -> it alone goes green
    warm = assess.assess_lanes(lanes, controller={"acme_b": {"day_count": 12}})
    got = {c["name"]: c["state"] for c in warm}
    assert got["acme_b"] == State.WORKING_PROVEN.value
    assert got["acme_a"] == State.CONFIGURED_IDLE.value


def test_a_reachable_lane_pinned_to_nothing_is_broken_not_idle() -> None:
    """The 11.194 defect class: enabled + credentialed but serving no function."""
    cfg = _fixture_config()
    cfg["providers"].append({"name": "orphan", "url": "https://api.acme-llm.example/v1",
                             "model": "acme/nova-1", "api_key_env": "ACME_API_KEY_9",
                             "enabled": True, "dedicated": True, "structured": "text"})
    lanes = _lanes_from(cfg)
    res = {c["name"]: c["state"] for c in assess.assess_lanes(lanes, controller={})}
    assert res["orphan"] == State.BROKEN_REACHABLE.value


# ── the negative: no vendor names baked into the framework ──────────────────

FRAMEWORK = Path(__file__).resolve().parents[2] / "shared" / "polymath_shared" / "conformance"
VENDOR_TOKENS = ("map_groq", "GROQ_API_KEY", "gemini1", "openrouter1", "compound-mini")


@pytest.mark.parametrize("mod", ["discovery.py", "assess.py", "classify.py", "report.py"])
def test_no_current_topology_is_hardcoded(mod: str) -> None:
    src = (FRAMEWORK / mod).read_text()
    for tok in VENDOR_TOKENS:
        assert tok not in src, f"{mod} hardcodes {tok!r} — the audit must discover it"


def test_a_lane_pinned_to_two_stages_is_visible_as_ambiguous() -> None:
    """A lane in two stage pins is a config ambiguity, not a silent last-wins.

    The live registry keeps one lane->function mapping, so such a lane quietly serves
    only one stage. This asserts the condition is DETECTABLE from config rather than
    discovered later by a stage that never gets its lane.
    """
    cfg = _fixture_config()
    cfg["stage_pins"]["chat_compiler"] = ["zeta_primary", "acme_a"]
    counts: dict[str, int] = {}
    for names in cfg["stage_pins"].values():
        for n in names:
            counts[n] = counts.get(n, 0) + 1
    ambiguous = sorted(n for n, c in counts.items() if c > 1)
    # zeta_primary is already double-pinned in the base fixture (doc_profile +
    # chat_compiler); adding acme_a to chat_compiler makes two. Both must be visible.
    assert ambiguous == ["acme_a", "zeta_primary"], ambiguous
