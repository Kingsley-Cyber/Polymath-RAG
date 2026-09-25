"""CLOUDFLARE-WORKERS-AI-V1 — provider-family regression tests.

Pins the MECHANISM (URL resolution, per-lane credentials, stage routing, quota-error
classification, promotion gate, secret hygiene), never a live account. The 12 assertions
map 1:1 to the owner's acceptance list.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config" / "cloud_providers.json"
CF_TEMPLATE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai"


def _cf_lane(name, tok_n, dedicated, structured="json", json_mode=True):
    return {
        "name": name, "enabled": True, "url_template": CF_TEMPLATE,
        "account_id_env": f"CLOUDFLARE_ACCOUNT_ID_{tok_n}",
        "api_key_env": f"CLOUDFLARE_API_TOKEN_{tok_n}",
        "model": "@cf/qwen/qwen3-30b-a3b-fp8", "reasoning_effort": None,
        "structured": structured, "json_mode": json_mode, "think_suffix": "/no_think",
        "dedicated": dedicated, "request_char_budget": 30000,
    }


@pytest.fixture
def cf_pool(monkeypatch, tmp_path):
    """Isolate pool + lane_registry from the machine's real config/.env/env."""
    from polymath_shared.llm_extraction import pool, lane_registry
    providers = tmp_path / "providers.json"
    dotenv = tmp_path / "dotenv"
    dotenv.write_text("")  # empty repo .env -> only process env resolves
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", providers)
    monkeypatch.setattr(pool, "_ENV_FILE", dotenv)
    monkeypatch.setattr(lane_registry, "_PROVIDERS_FILE", providers, raising=False)
    monkeypatch.setattr(lane_registry, "_ENV_FILE", dotenv, raising=False)
    # neutralize the machine's real Cloudflare env for a clean baseline
    for n in range(1, 7):
        monkeypatch.delenv(f"CLOUDFLARE_API_TOKEN_{n}", raising=False)
        monkeypatch.delenv(f"CLOUDFLARE_ACCOUNT_ID_{n}", raising=False)

    def write(providers_list, pins=None):
        providers.write_text(json.dumps({"stage_pins": pins or {}, "providers": providers_list}))
    return monkeypatch, write


def _names(pool):
    return {ep.name for ep in pool.cloud_endpoints()}


# 1 ─────────────────────────────────────────────────────────────────────────
def test_missing_token_parks_lane_cleanly(cf_pool):
    from polymath_shared.llm_extraction import pool
    mp, write = cf_pool
    write([_cf_lane("cloudflare1", 1, False)])
    mp.setenv("CLOUDFLARE_ACCOUNT_ID_1", "acct_abc")  # account present, token ABSENT
    assert "cloudflare1" not in _names(pool)  # parked, roster still builds (no crash)


# 2 ─────────────────────────────────────────────────────────────────────────
def test_missing_account_id_parks_lane_cleanly(cf_pool):
    from polymath_shared.llm_extraction import pool, lane_registry
    mp, write = cf_pool
    write([_cf_lane("cloudflare1", 1, False)])
    mp.setenv("CLOUDFLARE_API_TOKEN_1", "faketok_token")  # token present, account ABSENT
    assert "cloudflare1" not in _names(pool)  # parked (no URL without the account id)
    lane = next(l for l in lane_registry.build_lanes() if l.name == "cloudflare1")
    assert lane.reachability == lane_registry.CREDENTIAL_ABSENT  # actionable status


# 3 ─────────────────────────────────────────────────────────────────────────
def test_each_lane_resolves_its_own_token_account_pair(cf_pool):
    from polymath_shared.llm_extraction import pool
    mp, write = cf_pool
    write([_cf_lane("cloudflare1", 1, False), _cf_lane("cloudflare2", 2, False)])
    mp.setenv("CLOUDFLARE_API_TOKEN_1", "faketok_one"); mp.setenv("CLOUDFLARE_ACCOUNT_ID_1", "acct_ONE")
    mp.setenv("CLOUDFLARE_API_TOKEN_2", "faketok_two"); mp.setenv("CLOUDFLARE_ACCOUNT_ID_2", "acct_TWO")
    eps = {ep.name: ep for ep in pool.cloud_endpoints()}
    assert eps["cloudflare1"].api_key == "faketok_one" and "acct_ONE" in eps["cloudflare1"].url
    assert eps["cloudflare2"].api_key == "faketok_two" and "acct_TWO" in eps["cloudflare2"].url
    assert eps["cloudflare1"].limiter_key != eps["cloudflare2"].limiter_key  # own rate bucket


# 4 ─────────────────────────────────────────────────────────────────────────
def test_final_cloudflare_openai_url_is_correct(cf_pool):
    from polymath_shared.llm_extraction import pool
    mp, write = cf_pool
    write([_cf_lane("cloudflare1", 1, False)])
    mp.setenv("CLOUDFLARE_API_TOKEN_1", "faketok_x"); mp.setenv("CLOUDFLARE_ACCOUNT_ID_1", "ACC")
    ep = next(e for e in pool.cloud_endpoints() if e.name == "cloudflare1")
    final = f"{ep.url}/v1/chat/completions"  # what _chat posts to
    assert final == "https://api.cloudflare.com/client/v4/accounts/ACC/ai/v1/chat/completions"
    assert final.count("/v1/chat/completions") == 1
    assert "/ai/v1/v1/" not in final and "/completions/v1/" not in final


# 5 ─────────────────────────────────────────────────────────────────────────
def test_extraction_lanes_join_only_graph_extraction(cf_pool):
    from polymath_shared.llm_extraction import pool
    mp, write = cf_pool
    write([_cf_lane("cloudflare1", 1, False)],
          pins={"doc_profile": ["cloudflare_summary1"], "doc_parent_map": ["map_x"],
                "parent_enrichment": ["e"], "chat_compiler": ["c"]})
    for n in range(1, 3):
        mp.setenv(f"CLOUDFLARE_API_TOKEN_{n}", "faketok_x"); mp.setenv(f"CLOUDFLARE_ACCOUNT_ID_{n}", "ACC")
    # dedicated:false -> in the general (unpinned) ring; NOT in any pin group
    assert "cloudflare1" in {e.name for e in pool.cloud_endpoints() if not e.dedicated}
    for stage in ("doc_profile", "doc_parent_map", "parent_enrichment", "chat_compiler"):
        assert "cloudflare1" not in (pool.stage_pin(stage) or [])


# 6 ─────────────────────────────────────────────────────────────────────────
def test_summary_lanes_join_only_doc_profile(cf_pool):
    from polymath_shared.llm_extraction import pool
    mp, write = cf_pool
    write([_cf_lane("cloudflare_summary1", 5, True, structured="text", json_mode=False)],
          pins={"doc_profile": ["cloudflare_summary1"]})
    mp.setenv("CLOUDFLARE_API_TOKEN_5", "faketok_x"); mp.setenv("CLOUDFLARE_ACCOUNT_ID_5", "ACC")
    ep = next(e for e in pool.cloud_endpoints() if e.name == "cloudflare_summary1")
    assert ep.dedicated is True                       # never joins the general ring
    assert "cloudflare_summary1" not in {e.name for e in pool.cloud_endpoints() if not e.dedicated}
    assert "cloudflare_summary1" in pool.stage_pin("doc_profile")


# 7 ─────────────────────────────────────────────────────────────────────────
def test_quota_exhaustion_is_per_lane_not_global():
    from polymath_shared.llm_extraction.limiter import AdaptiveLimiter, ProviderLimit
    from polymath_shared.llm_extraction import cloudflare_errors as cf
    a = AdaptiveLimiter("cf_a", ProviderLimit(kind="rate", rpm=30))
    b = AdaptiveLimiter("cf_b", ProviderLimit(kind="rate", rpm=30))
    a.park_provider_day(cf.seconds_to_daily_reset())   # account A exhausted
    assert a.admit().admitted is False                 # A parked
    assert b.admit().admitted is True                  # B keeps serving — other providers continue


# 8 ─────────────────────────────────────────────────────────────────────────
def test_3036_daily_exhaustion_parks_without_immediate_retry():
    from polymath_shared.llm_extraction.limiter import AdaptiveLimiter, ProviderLimit, REFUSE_PROVIDER_RPD
    from polymath_shared.llm_extraction import cloudflare_errors as cf
    body = json.dumps({"success": False, "errors": [{"code": 3036, "message": "daily allocation exhausted"}]})
    assert cf.classify(429, body) == cf.DAILY_FREE_QUOTA_EXHAUSTED
    lim = AdaptiveLimiter("cf", ProviderLimit(kind="rate", rpm=30))
    lim.park_provider_day(cf.seconds_to_daily_reset())
    d = lim.admit()
    assert d.admitted is False and d.reason == REFUSE_PROVIDER_RPD  # refused BEFORE dispatch = no retry-loop


# 9 ─────────────────────────────────────────────────────────────────────────
def test_3040_capacity_failure_is_transient_backoff():
    from polymath_shared.llm_extraction import cloudflare_errors as cf
    body = json.dumps({"errors": [{"code": 3040, "message": "out of capacity"}]})
    assert cf.classify(200, body) == cf.OUT_OF_CAPACITY          # NOT a day-long park
    assert cf.classify(429, "{}") == cf.OUT_OF_CAPACITY          # bare 429 = transient, bounded retry
    assert cf.classify(200, "{}") is None                        # a clean 200 is never a fault


# 10 ────────────────────────────────────────────────────────────────────────
def test_fingerprint_changes_when_cloudflare_model_or_config_changes(cf_pool):
    from polymath_shared.llm_extraction import pool
    mp, write = cf_pool
    mp.setenv("CLOUDFLARE_API_TOKEN_1", "faketok_x"); mp.setenv("CLOUDFLARE_ACCOUNT_ID_1", "ACC")
    write([_cf_lane("cloudflare1", 1, False)])
    fp_a = pool.pool_fingerprint()
    lane = _cf_lane("cloudflare1", 1, False); lane["model"] = "@cf/qwen/qwen3-8b-fp8"
    write([lane])
    fp_b = pool.pool_fingerprint()
    assert fp_a != fp_b  # a re-model shows up in the extraction contract identity


# 11 ────────────────────────────────────────────────────────────────────────
def test_no_credential_value_in_committed_files():
    # every version-controlled file names ONLY env variables, never a resolved secret.
    # Matches a REAL Workers-AI token shape (prefix + a long alnum body) so the prose in
    # this very file does not self-trip; also refuses the one supplied account id literal.
    import re
    token_re = re.compile(r"cf" r"ut_[A-Za-z0-9]{16,}")
    account_literal = "ef533dd8" "e5dc6748692f083d97421efb"
    targets = [CONFIG, REPO / ".env.example", Path(__file__),
               REPO / "docs" / "wiki" / "plans" / "CLOUDFLARE-WORKERS-AI-QUALIFICATION.md"]
    for f in targets:
        if not f.exists():
            continue
        text = f.read_text()
        assert not token_re.search(text), f"a Workers-AI token literal leaked into {f}"
        assert account_literal not in text, f"an account id leaked into {f}"


# 12 ────────────────────────────────────────────────────────────────────────
def test_extraction_lanes_not_promoted_without_passing_canary():
    # PROMOTION GATE: cloudflare1..4 may be enabled in the committed config ONLY if the
    # qualification report records a graph-extraction PROMOTE. Parked (enabled:false) needs
    # no report. This binds the config to the measured verdict.
    raw = json.loads(CONFIG.read_text())
    ext = [e for e in raw["providers"] if e["name"] in {"cloudflare3", "cloudflare4", "cloudflare5", "cloudflare6"}]
    assert len(ext) == 4                      # owner split 2026-09-13: accounts 3-6 = extraction helpers
    enabled = [e for e in ext if e.get("enabled") is True]
    if enabled:
        doc = REPO / "docs" / "wiki" / "plans" / "CLOUDFLARE-WORKERS-AI-QUALIFICATION.md"
        assert doc.exists(), "extraction lanes enabled but no qualification report"
        low = doc.read_text().lower()
        assert "graph extraction" in low and "promote" in low and "do not promote" not in low


# 13 ────────────────────────────────────────────────────────────────────────
def test_owner_split_two_map_lanes_four_extraction_lanes():
    """CLOUDFLARE-PMAP-V1 (owner 2026-09-13): 2 keys on Parent-MAP, 4 on graph extraction, 0 on
    doc_profile. Map lanes are DEDICATED (never join the extraction ring), pinned ONLY to
    doc_parent_map, TEXT mode (the MAP DSL is lines, not JSON), and carry the pool's cap."""
    raw = json.loads(CONFIG.read_text())
    cf = {e["name"]: e for e in raw["providers"] if e["name"].startswith("cloudflare")}
    assert set(cf) == {"cloudflare_map1", "cloudflare_map2", "cloudflare3", "cloudflare4", "cloudflare5", "cloudflare6"}
    maps = [cf["cloudflare_map1"], cf["cloudflare_map2"]]
    assert [m["api_key_env"] for m in maps] == ["CLOUDFLARE_API_TOKEN_1", "CLOUDFLARE_API_TOKEN_2"]
    for m in maps:
        assert m["dedicated"] is True and m["structured"] == "text" and m["json_mode"] is False
        assert m["map_batch_cap"] == 15                      # never raises the pool cap (MIN over lanes)
    for n in ("cloudflare3", "cloudflare4", "cloudflare5", "cloudflare6"):
        assert cf[n]["dedicated"] is False and cf[n]["structured"] == "json"
    pins = raw["stage_pins"]
    assert pins["doc_parent_map"][-1:] == ["cloudflare_map2"]
    # account 1 was RETIRED by the owner (2026-09-24, register 11.469; its account id was never found): the lane stays
    # defined as the record, disabled and off the pin
    assert "cloudflare_map1" not in pins["doc_parent_map"] and cf["cloudflare_map1"]["enabled"] is False
    assert not any(n.startswith("cloudflare") for n in pins["doc_profile"])           # 0 on profile
    for stage in ("parent_enrichment", "chat_compiler", "doc_profile"):
        assert not ({"cloudflare_map1", "cloudflare_map2"} & set(pins.get(stage) or []))
    # every lane has its own limiter family, keyed by the NEW lane names
    import yaml
    lim = yaml.safe_load((REPO / "config" / "extraction_models" / "limiter.yaml").read_text())
    lanes = lim.get("providers") or lim.get("lanes") or lim   # limiter.yaml top-level key is `providers`
    fams = {n: lanes[n]["family"] for n in cf}
    assert len(set(fams.values())) == 6, fams


# 14 ────────────────────────────────────────────────────────────────────────
def test_map_lanes_not_promoted_without_a_parent_map_verdict():
    """PROMOTION GATE for pMAP: cloudflare_map1..2 may be enabled ONLY if the qualification
    report records a PARENT-MAP PROMOTE measured with the production prompt + compiler."""
    raw = json.loads(CONFIG.read_text())
    maps = [e for e in raw["providers"] if e["name"] in {"cloudflare_map1", "cloudflare_map2"}]
    assert len(maps) == 2
    if any(e.get("enabled") is True for e in maps):
        doc = REPO / "docs" / "wiki" / "plans" / "CLOUDFLARE-WORKERS-AI-QUALIFICATION.md"
        low = doc.read_text().lower()
        assert "parent-map" in low and "promote" in low
        assert "parent-map: do not promote" not in low
