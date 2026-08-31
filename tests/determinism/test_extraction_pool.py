"""EXTRACTION-POOL-V1 determinism + boundary tests.

The pool must (1) degenerate to today's single-endpoint behavior when no
extras are configured, (2) assign endpoints deterministically per doc so
replay re-selects the same provider, (3) fail LOUDLY on malformed
rosters, and (4) never widen cloud ELIGIBILITY — the 300 KB owner
boundary is policy.py's alone.
"""
from __future__ import annotations

import json

import pytest

from polymath_shared.llm_extraction.policy import CLOUD_MIN_BYTES, select_lane
from polymath_shared.settings import get_settings


EXTRAS = json.dumps([
    {"name": "prov-b", "url": "http://127.0.0.1:11500", "model": "m-b"},
    {"name": "prov-c", "url": "http://127.0.0.1:11501", "model": "m-c"},
])


@pytest.fixture
def pool_env(monkeypatch, tmp_path):
    # isolate from the machine's real providers file, .env keys, and
    # process env — these tests pin the MECHANISM, not this machine
    from polymath_shared.llm_extraction import pool
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", tmp_path / "providers.json")
    monkeypatch.setattr(pool, "_ENV_FILE", tmp_path / "dotenv")

    def set_extras(value: str | None):
        if value is None:
            monkeypatch.delenv("POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS",
                               raising=False)
        else:
            monkeypatch.setenv("POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS", value)
        get_settings.cache_clear()
    yield set_extras
    get_settings.cache_clear()


def test_single_endpoint_degenerates_to_settings(pool_env):
    from polymath_shared.llm_extraction.pool import (
        cloud_endpoints,
        select_cloud_endpoint,
    )
    pool_env(None)
    roster = cloud_endpoints()
    s = get_settings().sidecars
    assert [ep.name for ep in roster] == ["primary"]
    assert roster[0].url == s.llm_cloud_url
    assert roster[0].model == s.llm_cloud_model
    assert roster[0].limiter_key == "default"   # AIMD state carries over
    assert select_cloud_endpoint("any-doc").name == "primary"


def test_assignment_is_deterministic_and_spreads(pool_env):
    from polymath_shared.llm_extraction.pool import select_cloud_endpoint
    pool_env(EXTRAS)
    docs = [f"doc_{i:04d}" for i in range(60)]
    first = {d: select_cloud_endpoint(d).name for d in docs}
    again = {d: select_cloud_endpoint(d).name for d in docs}
    assert first == again                       # replay-stable
    used = set(first.values())
    assert used == {"primary", "prov-b", "prov-c"}  # all providers assist


def test_extra_endpoints_get_their_own_limiter_lane(pool_env):
    from polymath_shared.llm_extraction.pool import cloud_endpoints
    pool_env(EXTRAS)
    keys = {ep.name: ep.limiter_key for ep in cloud_endpoints()}
    assert keys["primary"] == "default"
    assert keys["prov-b"] == "prov-b"
    assert keys["prov-c"] == "prov-c"


def test_malformed_roster_fails_loudly(pool_env):
    from polymath_shared.llm_extraction.pool import cloud_endpoints
    for bad in ("not json", '{"a": 1}',
                '[{"name": "x", "url": ""}]',
                '[{"name": "primary", "url": "http://x", "model": "m"}]'):
        pool_env(bad)
        with pytest.raises(ValueError):
            cloud_endpoints()


def test_lane_matrix_cloud_assist_v2(pool_env):
    # Owner rule v2 (2026-08-30): the threshold is a THROUGHPUT router.
    # Big -> cloud always; small -> local unless a cloud-affinity worker
    # holds it (assist). The pool never changes the matrix.
    pool_env(EXTRAS)
    big, small = CLOUD_MIN_BYTES + 1, CLOUD_MIN_BYTES
    assert select_lane(big).lane == "cloud"
    assert select_lane(big, affinity="local").lane == "cloud"   # no exceptions
    assert select_lane(small).lane == "local"
    assert select_lane(small, affinity="local").lane == "local"
    d = select_lane(small, affinity="cloud")
    assert d.lane == "cloud" and d.assist                        # the assist
    assert not select_lane(big).assist


def test_dispatch_guard_verifies_assist_intent(pool_env):
    # A sub-threshold cloud call passes ONLY with the explicit assist
    # flag; anything else is a caller bug and still fails loudly.
    from polymath_shared.llm_extraction.policy import (
        CloudBoundaryViolation,
        require_cloud_eligible,
    )
    pool_env(None)
    require_cloud_eligible(CLOUD_MIN_BYTES + 1)                  # big: fine
    require_cloud_eligible(CLOUD_MIN_BYTES, assist=True)         # assist: fine
    with pytest.raises(CloudBoundaryViolation):
        require_cloud_eligible(CLOUD_MIN_BYTES)                  # no intent


def test_fingerprint_tracks_roster(pool_env):
    from polymath_shared.llm_extraction.pool import pool_fingerprint
    pool_env(None)
    solo = pool_fingerprint()
    pool_env(EXTRAS)
    trio = pool_fingerprint()
    assert len(solo) == 1 and len(trio) == 3
    assert solo != trio


def test_make_client_carries_endpoint_identity(pool_env):
    from workers.llm_provider import make_client
    pool_env(EXTRAS)
    seen = set()
    for i in range(40):
        c = make_client("cloud", f"doc_{i}")
        assert c.lane == "cloud"
        seen.add((c.endpoint_name, c.model, c.limiter_key))
    assert len(seen) == 3


def test_providers_file_auto_gate(pool_env, monkeypatch, tmp_path):
    # MULTI-PROVIDER-AUTH-V1: a configured provider joins ONLY when its
    # key resolves; enabled:false parks it even with a key.
    import json as _json

    from polymath_shared.llm_extraction import pool
    pf = tmp_path / "providers.json"
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", pf)
    pf.write_text(_json.dumps({"providers": [
        {"name": "groq", "enabled": True, "url": "http://g", "model": "m1",
         "api_key_env": "T_GROQ_KEY", "reasoning_effort": "low"},
        {"name": "nvidia", "enabled": True, "url": "http://n", "model": "m2",
         "api_key_env": "T_NVIDIA_KEY"},
        {"name": "parked", "enabled": False, "url": "http://p", "model": "m3",
         "api_key_env": "T_GROQ_KEY"},
    ]}))
    pool_env(None)
    monkeypatch.delenv("T_NVIDIA_KEY", raising=False)
    monkeypatch.setenv("T_GROQ_KEY", "sk-test")
    names = [ep.name for ep in pool.cloud_endpoints()]
    assert names == ["groq", "primary"]          # nvidia keyless, parked off
    groq = pool.cloud_endpoints()[0]
    assert groq.api_key == "sk-test"
    assert groq.reasoning_effort == "low"
    monkeypatch.setenv("T_NVIDIA_KEY", "nvapi-test")
    assert [ep.name for ep in pool.cloud_endpoints()] == [
        "groq", "nvidia", "primary"]             # key drop = activation


def test_key_resolves_from_dotenv_file(pool_env, monkeypatch, tmp_path):
    from polymath_shared.llm_extraction import pool
    dotenv = tmp_path / "dotenv"
    monkeypatch.setattr(pool, "_ENV_FILE", dotenv)
    monkeypatch.delenv("T_DOTENV_KEY", raising=False)
    dotenv.write_text("# comment\nT_DOTENV_KEY=file-value\n")
    assert pool._resolve_key("T_DOTENV_KEY") == "file-value"
    monkeypatch.setenv("T_DOTENV_KEY", "env-wins")
    assert pool._resolve_key("T_DOTENV_KEY") == "env-wins"


def test_keys_never_leak_into_fingerprint_or_repr(pool_env, monkeypatch,
                                                  tmp_path):
    import json as _json

    from polymath_shared.llm_extraction import pool
    pf = tmp_path / "providers.json"
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", pf)
    pf.write_text(_json.dumps({"providers": [
        {"name": "groq", "url": "http://g", "model": "m1",
         "api_key_env": "T_GROQ_KEY"}]}))
    pool_env(None)
    monkeypatch.setenv("T_GROQ_KEY", "sk-SECRET")
    fp = _json.dumps(pool.pool_fingerprint())
    assert "sk-SECRET" not in fp
    assert "sk-SECRET" not in repr(pool.cloud_endpoints())


def test_structured_capability_negotiation(pool_env, monkeypatch, tmp_path):
    # STRUCTURED-CAPABILITY-V1: explicit level wins; legacy json_mode
    # maps to json/text; "schema" is accepted but DISPATCHES as json
    # (json_mode True) until a strict-schema canary passes; bad levels
    # fail loudly.
    import json as _json

    from polymath_shared.llm_extraction import pool
    pf = tmp_path / "providers.json"
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", pf)
    monkeypatch.setenv("T_CAP_KEY", "k")
    pf.write_text(_json.dumps({"providers": [
        {"name": "a-schema", "url": "http://a", "model": "m",
         "api_key_env": "T_CAP_KEY", "structured": "schema"},
        {"name": "b-json", "url": "http://b", "model": "m",
         "api_key_env": "T_CAP_KEY"},
        {"name": "c-text", "url": "http://c", "model": "m",
         "api_key_env": "T_CAP_KEY", "json_mode": False},
    ]}))
    pool_env(None)
    by = {ep.name: ep for ep in pool.cloud_endpoints()}
    assert by["a-schema"].structured == "schema"
    assert by["a-schema"].cloud_opts["json_mode"] is True   # downgraded dispatch
    assert by["b-json"].structured == "json"
    assert by["c-text"].structured == "text"
    assert by["c-text"].cloud_opts["json_mode"] is False
    fp = {e["name"]: e for e in pool.pool_fingerprint()}
    assert fp["a-schema"]["structured"] == "schema"          # contract input

    pf.write_text(_json.dumps({"providers": [
        {"name": "bad", "url": "http://x", "model": "m",
         "api_key_env": "T_CAP_KEY", "structured": "yaml"}]}))
    with pytest.raises(ValueError):
        pool.cloud_endpoints()


def test_stage_pin_dedicates_and_fails_loudly(pool_env, monkeypatch, tmp_path):
    # STAGE-PIN-V1: pinned stage -> exactly that provider; pinned but
    # inactive -> loud PinnedProviderUnavailable (never silent reroute);
    # unpinned stages shard as normal.
    import json as _json

    from polymath_shared.llm_extraction import pool
    pf = tmp_path / "providers.json"
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", pf)
    pf.write_text(_json.dumps({
        "stage_pins": {"parent_enrichment": "nvidia"},
        "providers": [
            {"name": "nvidia", "url": "http://n", "model": "m",
             "api_key_env": "T_PIN_KEY"}]}))
    pool_env(None)

    monkeypatch.delenv("T_PIN_KEY", raising=False)   # parked: no key
    with pytest.raises(pool.PinnedProviderUnavailable):
        pool.select_endpoint_for_stage("parent_enrichment", "doc_x")

    monkeypatch.setenv("T_PIN_KEY", "nvapi-test")    # key drop = dedicated
    ep = pool.select_endpoint_for_stage("parent_enrichment", "doc_x")
    assert ep.name == "nvidia"
    # every doc goes to the pin — no sharding on a dedicated stage
    assert {pool.select_endpoint_for_stage("parent_enrichment", f"d{i}").name
            for i in range(8)} == {"nvidia"}
    # unpinned stage still shards over the whole roster
    assert pool.select_endpoint_for_stage("extract", "doc_x").name in {
        "nvidia", "primary"}


def test_stage_pin_group_shards_and_degrades_loudly(pool_env, monkeypatch,
                                                    tmp_path):
    # DUAL-LANE pin groups: docs shard deterministically across ACTIVE
    # members; a partially-dark group runs on the rest; all-dark raises.
    import json as _json

    from polymath_shared.llm_extraction import pool
    pf = tmp_path / "providers.json"
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", pf)
    pf.write_text(_json.dumps({
        "stage_pins": {"parent_enrichment": ["nvidia", "nvidia2"]},
        "providers": [
            {"name": "nvidia", "url": "http://n1", "model": "m",
             "api_key_env": "T_NV1"},
            {"name": "nvidia2", "url": "http://n2", "model": "m",
             "api_key_env": "T_NV2"}]}))
    pool_env(None)
    monkeypatch.setenv("T_NV1", "k1")
    monkeypatch.setenv("T_NV2", "k2")
    names = {pool.select_endpoint_for_stage("parent_enrichment", f"d{i}").name
             for i in range(40)}
    assert names == {"nvidia", "nvidia2"}       # both lanes churn
    first = pool.select_endpoint_for_stage("parent_enrichment", "d7").name
    assert all(pool.select_endpoint_for_stage("parent_enrichment", "d7").name
               == first for _ in range(5))      # replay-stable

    monkeypatch.delenv("T_NV2", raising=False)  # one account dark
    assert {pool.select_endpoint_for_stage("parent_enrichment", f"d{i}").name
            for i in range(10)} == {"nvidia"}   # reduced, not rerouted

    monkeypatch.delenv("T_NV1", raising=False)  # all dark
    with pytest.raises(pool.PinnedProviderUnavailable):
        pool.select_endpoint_for_stage("parent_enrichment", "d0")


def test_dedicated_endpoints_excluded_from_general_sharding(pool_env,
                                                            monkeypatch,
                                                            tmp_path):
    # DEDICATED-V1: dedicated endpoints serve only their pinned stages;
    # general extraction sharding never touches them.
    import json as _json

    from polymath_shared.llm_extraction import pool
    pf = tmp_path / "providers.json"
    monkeypatch.setattr(pool, "_PROVIDERS_FILE", pf)
    monkeypatch.setenv("T_DK", "k")
    pf.write_text(_json.dumps({
        "stage_pins": {"parent_enrichment": ["nv"]},
        "providers": [
            {"name": "g1", "url": "http://g1", "model": "m",
             "api_key_env": "T_DK", "structured": "schema"},
            {"name": "nv", "url": "http://n", "model": "m",
             "api_key_env": "T_DK", "dedicated": True}]}))
    pool_env(None)
    general = {pool.select_cloud_endpoint(f"d{i}").name for i in range(30)}
    assert "nv" not in general               # reserved for its stage
    assert pool.select_endpoint_for_stage(
        "parent_enrichment", "d0").name == "nv"
    # level-1 endpoints carry the structured level into dispatch opts
    g1 = [ep for ep in pool.cloud_endpoints() if ep.name == "g1"][0]
    assert g1.cloud_opts["structured"] == "schema"
