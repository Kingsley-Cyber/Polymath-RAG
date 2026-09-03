"""EXTRACTION-THROUGHPUT-V2 exit gate: rank slices are disjoint,
packing respects the slice budget, oversize neighborhoods route to
the big-budget lane, cached receipts replay without network, the 413
ladder splits then escapes cross-host, and unknown context degrades
to single-lane affinity."""
from __future__ import annotations

import pytest

import polymath_shared.llm_extraction.pool as pool_mod
import workers.llm_provider as llm
from polymath_shared.llm_extraction.client import (
    ExtractionTransportError,
    LLMCallResult,
)
from polymath_shared.llm_extraction.gate import SanitizeResult
from workers.llm_provider import Neighborhood


class FakeEp:
    def __init__(self, name, host, budget):
        self.name = name
        self.url = f"https://{host}"
        self.model = "m"
        self.api_key = "k"
        self.cloud_opts = {}
        self.limiter_key = name
        self.dedicated = False
        self.request_char_budget = budget


RING = ([FakeEp(f"g{i}", "groq.test", 1000) for i in range(4)]
        + [FakeEp(f"m{i}", "gemini.test", 5000) for i in range(4)]
        + [FakeEp("n0", "nvidia.test", 3000),
           FakeEp("p0", "local.test", 9000)])

CALLS: list[tuple[str, int]] = []          # (lane_name, batch_size)
FAIL_413: set = set()


from types import SimpleNamespace


def _result(parsed=True):
    return LLMCallResult(lane="cloud", model="m", raw_text="{}",
                         packet=(SimpleNamespace(entities=[], relations=[],
                                                 digests=[], items=[])
                                 if parsed else None),
                         sanitize=SanitizeResult(ok=False,
                                                 error_class="EMPTY"),
                         wall_ms=1)


class FakeClient:
    def __init__(self, lane, url="", model="", limiter_key="",
                 api_key=None, cloud_opts=None):
        self.lane = lane
        self.base_url = url
        self.endpoint_name = limiter_key

    def extract(self, payload, **_kw):
        CALLS.append((self.endpoint_name, len(payload)))
        if self.endpoint_name in FAIL_413:
            raise ExtractionTransportError(
                "cloud transport failed: HTTP 413")
        return _result()

    def extract_from_raw(self, payload, raw):
        CALLS.append((self.endpoint_name + ":cached", len(payload)))
        return _result()


@pytest.fixture(autouse=True)
def _wire(monkeypatch):
    CALLS.clear()
    FAIL_413.clear()
    monkeypatch.setattr(pool_mod, "cloud_ring", lambda: list(RING))
    monkeypatch.setattr(pool_mod, "select_cloud_endpoint_abs",
                        lambda i: RING[i % len(RING)])
    monkeypatch.setattr(pool_mod, "home_ring_index", lambda d: 0)
    monkeypatch.setattr(llm, "LLMExtractionClient", FakeClient)
    monkeypatch.setattr(llm, "contract_identity", lambda: {"t": "v2"})
    # EXTRACTION-COVERAGE-V1's reissue pass re-touches quarantined
    # fakes through the base client — its own tests own it; here it
    # only obscures the dispatch mechanics under test
    monkeypatch.setattr(llm, "_reissue", lambda *a, **k: [])


def _nb(i, chars=200):
    return Neighborhood(nid=f"n{i}", chunks=[(f"c{i}", "x" * chars)])


def _run(n=6, **kw):
    return llm.run_proposals([_nb(i) for i in range(n)], lane="cloud",
                             source_bytes=10**6, doc_id="doc_a", **kw)


def test_rank_slices_are_disjoint():
    lanes_by_rank = {}
    for rank in range(4):
        CALLS.clear()
        _run(active_rank=rank, active_docs=4)
        lanes_by_rank[rank] = {name for name, _ in CALLS}
    all_lanes = [ln for s in lanes_by_rank.values() for ln in s]
    assert len(all_lanes) == len(set(all_lanes)), lanes_by_rank
    # ring 10 // 4 active = 2 lanes per doc
    assert all(len(s) <= 2 for s in lanes_by_rank.values())


def test_lone_doc_spreads_across_the_fleet():
    _run(n=40, active_rank=0, active_docs=1)       # 10 batches of 4
    assert len({name for name, _ in CALLS}) >= 8   # fleet engaged


def test_unknown_context_degrades_to_single_lane():
    _run(n=6)
    assert len({name for name, _ in CALLS}) == 1   # affinity fallback


def test_packing_respects_slice_budget():
    # rank 0 with 4 active -> lanes g0,g1 (budget 1000) -> max 4
    # neighborhoods of 200 chars per batch, but budget forces <=5;
    # NEIGHBORHOODS_PER_CALL caps at 4 anyway — verify NO batch ever
    # exceeded the budget in chars
    _run(n=10, active_rank=0, active_docs=4)
    assert all(size * 200 <= 1000 for _, size in CALLS)


def test_oversize_neighborhood_routes_to_big_budget_lane():
    nbs = [_nb(0), Neighborhood(nid="huge", chunks=[("cH", "x" * 4000)])]
    llm.run_proposals(nbs, lane="cloud", source_bytes=10**6,
                      doc_id="doc_a", active_rank=0, active_docs=4)
    # slice budget (groq 1000) can't take 4000 chars -> big lane (p0 9000)
    assert any(name == "p0" for name, _ in CALLS)


def test_cache_replays_without_network():
    got = {}
    cache = (lambda key: "{}", lambda *a: got.setdefault("put", True))
    _run(n=6, active_rank=0, active_docs=4, call_cache=cache)
    assert CALLS and all(name.endswith(":cached") for name, _ in CALLS)


def test_413_splits_then_escapes_cross_host():
    FAIL_413.update({"g0", "g1", "g2", "g3"})    # whole groq family 413s
    _run(n=4, active_rank=0, active_docs=4)
    # halves retried on groq, singles escaped to a non-groq host
    assert any(name.startswith("m") or name in ("n0", "p0")
               for name, _ in CALLS)
    escaped = [s for n_, s in CALLS if not n_.startswith("g")]
    assert escaped and all(s == 1 for s in escaped)


def test_output_truncation_splits_like_payload(monkeypatch):
    class TruncClient(FakeClient):
        def extract(self, payload, **_kw):
            CALLS.append((self.endpoint_name, len(payload)))
            r = _result()
            if len(payload) > 1:
                r.finish_reason = "length"
            return r
    monkeypatch.setattr(llm, "LLMExtractionClient", TruncClient)
    _run(n=4, active_rank=0, active_docs=4)
    sizes = [s for _, s in CALLS]
    assert any(s > 1 for s in sizes)            # the truncated batch
    assert sum(1 for s in sizes if s == 1) >= 4  # split down to singles


def test_quarantine_semantic_escape_once_cross_host(monkeypatch):
    class QuarantineOnGroq(FakeClient):
        def extract(self, payload, **_kw):
            CALLS.append((self.endpoint_name, len(payload)))
            return _result(parsed=not self.endpoint_name.startswith("g"))
    monkeypatch.setattr(llm, "LLMExtractionClient", QuarantineOnGroq)
    _run(n=4, active_rank=0, active_docs=4)   # slice = g0/g1 (quarantine)
    lanes = [name for name, _ in CALLS]
    # exactly one cross-host escape per quarantined batch, non-groq
    assert any(not ln.startswith("g") for ln in lanes)
    assert sum(1 for ln in lanes if not ln.startswith("g")) <= 2


def test_deterministic_dispatch():
    _run(n=8, active_rank=1, active_docs=2)
    first = sorted(CALLS)
    CALLS.clear()
    _run(n=8, active_rank=1, active_docs=2)
    assert sorted(CALLS) == first


def test_auth_failure_quarantines_lane_never_the_document(monkeypatch):
    """LANE-AUTH-QUARANTINE-V1: a lane answering 401 (rotated key,
    stale env snapshot) is dead for the run; its batches escape
    cross-host and the document still completes. Live 2026-09-01: one
    openrouter 401 struck a whole extract stage to failed."""
    from polymath_shared.llm_extraction.client import ExtractionTransportError

    class AuthDeadOnGroq(FakeClient):
        def extract(self, payload, **_kw):
            CALLS.append((self.endpoint_name, len(payload)))
            if self.endpoint_name.startswith("g"):
                raise ExtractionTransportError(
                    "cloud transport failed: HTTP 401 <- Client error "
                    "'401 Unauthorized'")
            return _result()

    monkeypatch.setattr(llm, "LLMExtractionClient", AuthDeadOnGroq)
    _run(n=4, active_rank=0, active_docs=4)      # slice = the g family
    lanes = [name for name, _ in CALLS]
    assert any(not ln.startswith("g") for ln in lanes), "no cross-host escape"
    # every batch that hit a dead lane was carried by a live host
    assert sum(1 for ln in lanes if not ln.startswith("g")) >= \
        len({ln for ln in lanes if ln.startswith("g")})


def test_lone_doc_transport_failure_fails_over_cross_host(monkeypatch):
    """A lone document owns the whole ring (n_lanes == ring), so the old
    lane_i + n_lanes failover wrapped onto the SAME lane and one
    transient 503 failed the attempt (live 2026-09-01). Failover must
    reach a different host."""
    from polymath_shared.llm_extraction.client import ExtractionTransportError

    class FiveOhThreeOnGroq(FakeClient):
        def extract(self, payload, **_kw):
            CALLS.append((self.endpoint_name, len(payload)))
            if self.endpoint_name.startswith("g"):
                raise ExtractionTransportError(
                    "cloud transport failed: HTTP 503 <- Server error")
            return _result()

    monkeypatch.setattr(llm, "LLMExtractionClient", FiveOhThreeOnGroq)
    _run(n=4, active_rank=0, active_docs=1)      # lone doc: whole ring
    lanes = [name for name, _ in CALLS]
    assert any(not ln.startswith("g") for ln in lanes), \
        "503 on the home family never reached another host"


def test_receipt_accepted_count_counts_packet_items(monkeypatch):
    """RECEIPT-ACCEPTED-COUNT-FIX: receipts must record the proposal count
    of the REAL packet shape (items[].entities/relations); the old flat
    field names recorded 0 on every receipt (495/495 on 2026-09-02)."""
    from polymath_shared.llm_extraction.contract import (
        EntityProposal,
        ExtractionItem,
        ExtractionPacket,
    )

    class ItemsClient(FakeClient):
        def extract(self, payload, **_kw):
            CALLS.append((self.endpoint_name, len(payload)))
            r = _result()
            r.packet = ExtractionPacket(items=[
                ExtractionItem(
                    neighborhood_id=nid,
                    entities=[EntityProposal(surface="Acme", type="ORG",
                                             quote="Acme")])
                for nid, _chunks in payload])
            return r

    puts = []
    cache = (lambda key: None, lambda *a: puts.append(a))
    monkeypatch.setattr(llm, "LLMExtractionClient", ItemsClient)
    _run(n=4, active_rank=0, active_docs=4, call_cache=cache)
    assert puts, "cache_put never called"
    # RECEIPT-COMPLETENESS-V1 (2026-09-03): the ledger also carries finish_reason
    # as a 7th argument (older 6-arg cache doubles still accepted by the provider)
    assert all(len(a) in (6, 7) and a[5] >= 1 for a in puts), puts
    assert all(len(a) == 7 for a in puts), "finish_reason must be offered to the ledger"
