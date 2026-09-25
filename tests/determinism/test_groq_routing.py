"""DOCUMENT-SEMANTIC-INDEX-V1 slice S7b — live Groq lane routing.

Pins that `route` maps a shared-budget decision back to the correct pin lane, that the
config `map_groq*` compound-mini lanes carry the account keys, and that the router
flag is off by default. Pure — a fake registry, no network.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import groq_routing as RT  # noqa: E402
from polymath_shared.document_profile import groq_router as GR  # noqa: E402
from polymath_shared.llm_extraction.limiter import AdaptiveLimiter, ProviderLimit  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_reservations():
    """CONCURRENCY-SPREAD-V1 reservations are module-level; isolate every test."""
    RT.reset_reservations()
    yield
    RT.reset_reservations()

MAP_PIN = [f"map_groq{i}" for i in range(1, 7)]
PROVIDERS = [{"name": f"map_groq{i}", "api_key_env": f"GROQ_API_KEY_{i}", "model": "groq/compound-mini"}
             for i in range(1, 7)]


def _lim(day_count=0):
    lim = AdaptiveLimiter("cloud[x]", ProviderLimit(kind="rate", rpm=30, tpm=70000, rpd=230, max=6, min=1))
    lim._day_count = day_count
    return lim


def test_router_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("POLYMATH_GROQ_ROUTER", raising=False)
    assert RT.router_enabled() is False
    monkeypatch.setenv("POLYMATH_GROQ_ROUTER", "1")
    assert RT.router_enabled() is True


def test_account_maps_from_config():
    account_of, model_of = RT.account_maps(MAP_PIN, PROVIDERS)
    assert account_of["map_groq3"] == "GROQ_API_KEY_3"
    assert model_of["map_groq3"] == "groq/compound-mini"


def test_select_lane_maps_decision_back():
    account_of, model_of = RT.account_maps(MAP_PIN, PROVIDERS)
    d = GR.RouteDecision(account="GROQ_API_KEY_4", model="groq/compound-mini", reason="selected")
    assert RT.select_lane(MAP_PIN, d, account_of, model_of) == "map_groq4"
    assert RT.select_lane(MAP_PIN, GR.RouteDecision(None, None, "no_capacity"), account_of, model_of) is None


def test_route_picks_least_loaded_account_lane():
    # key 3 is nearly spent (220/230); the rest are fresh → route to a fresh account's lane.
    day = {"map_groq3": 220}
    lims = {lane: _lim(day.get(lane, 0)) for lane in MAP_PIN}
    lane, decision = RT.route(MAP_PIN, "PARENT_ROUTING_MAP", est_total_tokens=4000.0,
                              providers=PROVIDERS, get_lane=lims.get, now=0.0)
    assert decision.routed and decision.model == "groq/compound-mini"
    assert lane in MAP_PIN and lane != "map_groq3"


def test_route_spreads_when_only_one_lane_is_registered():
    # regression for the 8-doc backfill bug: only map_groq1 has live state (used); the
    # rest are unregistered (get_lane -> None). The router MUST still consider the fresh
    # accounts and route AWAY from the used one — not pin every call to map_groq1.
    used = _lim(day_count=5)
    lane, decision = RT.route(MAP_PIN, "PARENT_ROUTING_MAP", est_total_tokens=4000.0, providers=PROVIDERS,
                              get_lane=lambda n: used if n == "map_groq1" else None, now=0.0)
    assert decision.routed and lane != "map_groq1"


def test_route_fresh_pool_still_spreads_deterministically():
    # no live lanes yet (get_lane -> None): route falls back to full-budget placeholders.
    lane, decision = RT.route(MAP_PIN, "PARENT_ROUTING_MAP", est_total_tokens=4000.0,
                              providers=PROVIDERS, get_lane=lambda n: None, now=0.0)
    assert decision.routed and lane in MAP_PIN


def test_route_spreads_a_concurrent_burst_across_accounts():
    # CONCURRENCY-SPREAD-V1 regression: N callers firing at ONCE read the same fresh snapshot and,
    # without the reservation, every one picks the lexicographically-smallest account (measured: a
    # 3-way parent-map backfill put 633/640 map calls on map_groq1). The in-process reservation
    # injects pending picks as in_flight so the burst rotates across all six accounts.
    def one(_):
        _lane, d = RT.route(MAP_PIN, "PARENT_ROUTING_MAP", est_total_tokens=250.0,
                            providers=PROVIDERS, get_lane=lambda n: None)
        return d.account

    with ThreadPoolExecutor(max_workers=6) as ex:
        got = Counter(a for a in ex.map(one, range(60)) if a)
    assert len(got) == 6, f"a concurrent burst pinned to {dict(got)} — expected all six accounts"
    assert max(got.values()) <= 18, f"one account took {max(got.values())}/60 — not spread: {dict(got)}"


def test_reservation_decays_so_sequential_is_not_starved():
    # A pick recorded now must NOT still steer a call one TTL later (sequential map calls are ~8 s
    # apart, past RESERVATION_TTL_S) — otherwise the reservation would permanently avoid accounts.
    RT.reset_reservations()
    RT.route(MAP_PIN, "PARENT_ROUTING_MAP", est_total_tokens=250.0, providers=PROVIDERS,
             get_lane=lambda n: None, now=0.0)
    # a fresh pool one TTL later: the earlier reservation has decayed, so account 1 is eligible again
    lane, d = RT.route(MAP_PIN, "PARENT_ROUTING_MAP", est_total_tokens=250.0, providers=PROVIDERS,
                       get_lane=lambda n: None, now=RT.RESERVATION_TTL_S + 1.0)
    assert d.routed and d.account == "GROQ_API_KEY_1"   # back to the deterministic first pick


def test_config_map_lanes_never_share_a_pair_with_the_profile():
    """PROVIDER-LANE-REASSIGNMENT-V1 (11.193) split each Groq KEY between doc_profile and pMAP so a pMAP burst could
    not starve doc_profile through a shared budget. Since GROQ-MODEL-SWAP-2026-09-23 the budgets are per (key, model),
    and LLM-BACKEND L3 (11.467; the owner 2026-09-24: 3 models per key, all used) puts pMAP back on every key on the
    two OTHER models: the profile's pair (key x gpt-oss-120b) is never on the pMAP pin, so the protection holds per
    pair. pMAP slot N owns map_groqN (gpt-oss-20b) + map_groqNq (qwen3.8-27b).
    """
    d = json.loads((ROOT / "config/cloud_providers.json").read_text())
    eps = {e["name"]: e for e in d["providers"]}
    pin = d["stage_pins"]["doc_parent_map"]
    # each pMAP key carries one lane per model (independent per-model budgets)
    groq_ring = [f"map_groq{i}" for i in range(1, 7)] + [f"map_groq{i}q" for i in range(1, 7)] + ["map_fallback_openrouter"]
    assert pin[: len(groq_ring)] == groq_ring
    # CLOUDFLARE-PMAP-V1 (11.255): the owner added two DEDICATED Cloudflare map lanes to the pool;
    # they are the ONLY admissible additions and never touch a Groq account key.
    extra = pin[len(groq_ring):]
    assert all(n.startswith("cloudflare_map") and eps[n]["dedicated"] is True for n in extra), extra
    assert all(not eps[n]["api_key_env"].startswith("GROQ_") for n in extra)
    for i in range(1, 7):
        assert eps[f"map_groq{i}"]["model"] == "openai/gpt-oss-20b" and eps[f"map_groq{i}"]["reasoning_effort"] == "low"
        assert eps[f"map_groq{i}q"]["model"] == "qwen/qwen3.8-27b" and eps[f"map_groq{i}q"]["reasoning_effort"] == "none"
        for n in (f"map_groq{i}", f"map_groq{i}q"):
            assert eps[n]["api_key_env"] == f"GROQ_API_KEY_{i}"
            assert eps[n]["dedicated"] is True and eps[n]["map_batch_cap"] == 15 and eps[n]["enabled"] is True
    assert d["stage_owners"]["doc_parent_map"] == [[f"map_groq{i}", f"map_groq{i}q"] for i in range(1, 7)]
    # DE-SHARED per pair: no pMAP lane uses a doc_profile (key, model) pair
    profile_pairs = {(eps[n]["api_key_env"], eps[n]["model"]) for n in d["stage_pins"]["doc_profile"]}
    assert not ({(eps[n]["api_key_env"], eps[n]["model"]) for n in pin} & profile_pairs)
