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
def pool_env(monkeypatch):
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
