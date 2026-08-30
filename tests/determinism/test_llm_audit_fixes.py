"""LOCAL-LLM-EXTRACTION-V1 — regression suite for the 2026-08-29 audit.

One test per fixed finding (numbers reference the audit report). Pure
determinism: no DB, no network, no model.
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.llm_extraction.client import (
    ExtractionTransportError,
    LLMExtractionClient,
    _quarantine_class,
)
from polymath_shared.llm_extraction.contract import SanitizeResult
from polymath_shared.llm_extraction.gate import (
    ChunkView,
    _locate,
    _locate_all,
    _repair_truncated,
    sanitize,
    validate_and_normalize,
)
from polymath_shared.llm_extraction.limiter import (
    AdaptiveLimiter,
    ProviderLimit,
    _TokenBucket,
)
from polymath_shared.llm_extraction.policy import (
    CLOUD_MIN_BYTES,
    CloudBoundaryViolation,
    require_cloud_eligible,
    select_lane,
)

from workers import llm_provider

CH = "FortiGate firewalls reported VPN tunnel errors after the firmware update."


def _packet(entities=None, relations=None, nid="n") -> str:
    return json.dumps({
        "contract": "polymath-extraction-v1", "profile": "volume",
        "items": [{"neighborhood_id": nid,
                   "entities": entities if entities is not None else [
                       {"surface": "FortiGate", "type": "Product", "quote": CH}],
                   "relations": relations if relations is not None else [
                       {"subject": "FortiGate", "predicate": "reported",
                        "object": "VPN tunnel errors", "quote": CH}],
                   "digest": {}}]})


# ---------------------------------------------------------------------------
# gate (#1, #9, #19, #23, #24, #20)
# ---------------------------------------------------------------------------

def test_1_endpoint_mentions_carry_core_label_the_worker_accepts() -> None:
    from workers.extract_worker import _map_label, _pack
    _, p = sanitize(_packet(), {"n"})
    out = validate_and_normalize(p, {"n": [ChunkView("c", CH)]})
    obj = [e for e in out.entities_by_chunk["c"] if e["text"] == "VPN tunnel errors"]
    assert obj and obj[0]["label"] == "Concept" and obj[0]["raw_type"] == "VPN tunnel errors"
    for e in out.entities_by_chunk["c"]:
        assert _map_label(e["label"], _pack()) is not None, e


def test_9_attestation_is_token_boundary_aligned() -> None:
    v = ChunkView("c", "The hostname resolver failed; the host was fine.")
    hit = _locate("host", v)
    assert hit and v.text[hit[0]:hit[1]] == "host" and v.text[hit[0] - 1] == " "
    assert _locate("SOC", ChunkView("c", "a SOCKET here")) is None
    # ws-collapsed path is boundary-aligned too
    assert _locate("host name", ChunkView("c", "myhost  name here")) is None
    hit = _locate("host name", ChunkView("c", "my host  name here"))
    assert hit == (3, 13)


def test_19_truncated_entity_without_quote_is_dropped_not_synthesized() -> None:
    raw = ('{"contract":"polymath-extraction-v1","profile":"volume","items":[{'
           '"neighborhood_id":"n","entities":[{"surface":"FortiGate","type":"Product"},'
           '{"surface":"VPN","ty')
    assert _repair_truncated(raw) is not None
    res, p = sanitize(raw, {"n"})
    assert res.ok is False or p is None or all(
        e.quote != e.surface for e in p.items[0].entities)
    if p is not None:
        assert [e.surface for e in p.items[0].entities] == []


def test_23_multiple_boundary_aligned_mentions_up_to_cap() -> None:
    text = "Alpha uses Beta. Beta helps Alpha. Alpha again, and Alpha once more."
    _, p = sanitize(_packet(entities=[{"surface": "Alpha", "type": "Product",
                                       "quote": text}], relations=[]), {"n"})
    out = validate_and_normalize(p, {"n": [ChunkView("c", text)]})
    hits = [e for e in out.entities_by_chunk["c"] if e["text"] == "Alpha"]
    assert len(hits) == 2                       # MAX_MENTIONS_PER_SURFACE
    assert hits[0]["start"] < hits[1]["start"]
    assert len(_locate_all("Alpha", ChunkView("c", text), 10)) == 4


def test_24_predicate_fallbacks_are_counted_in_stats() -> None:
    _, p = sanitize(_packet(relations=[{"subject": "FortiGate", "predicate": "wibble",
                                        "object": "VPN tunnel errors", "quote": CH}]),
                    {"n"})
    out = validate_and_normalize(p, {"n": [ChunkView("c", CH)]})
    assert out.stats["predicate_fallbacks"] == 1


def test_20_unknown_neighborhood_drops_only_that_item() -> None:
    raw = json.loads(_packet(nid="good"))
    raw["items"].append({"neighborhood_id": "bogus", "entities": [], "relations": []})
    res, p = sanitize(json.dumps(raw), {"good"})
    assert res.ok and res.salvaged and p is not None
    assert [i.neighborhood_id for i in p.items] == ["good"]
    res, p = sanitize(_packet(nid="bogus"), {"good"})
    assert not res.ok and res.error_class == "SANITIZE_UNKNOWN_NEIGHBORHOOD"
    assert _quarantine_class(res) == "SANITIZE_UNKNOWN_NEIGHBORHOOD"
    assert _quarantine_class(SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE")) \
        == "QUARANTINED_UNPARSEABLE"


def test_25_alias_pass_is_token_bounded() -> None:
    from polymath_shared.llm_extraction.ontology import normalize_predicate
    # sub-word hits no longer fire: "part" in "counterpart", "acts" in
    # "contracts", "has" in "rehash"; whole-word aliases still do
    assert normalize_predicate("counterpart of") == ("RELATED_TO", "related_fallback")
    assert normalize_predicate("contracts with") == ("RELATED_TO", "related_fallback")
    assert normalize_predicate("rehash") == ("RELATED_TO", "related_fallback")
    assert normalize_predicate("is a kind of") == ("IS_A", "alias")
    assert normalize_predicate("depends on") == ("REQUIRES", "alias")
    assert normalize_predicate("comes before") == ("PRECEDES", "alias")


# ---------------------------------------------------------------------------
# boundary (#6)
# ---------------------------------------------------------------------------

def test_6_threshold_is_a_floor_at_both_boundaries() -> None:
    assert select_lane(10, threshold=0).lane == "local"
    assert select_lane(CLOUD_MIN_BYTES, threshold=0).lane == "local"
    assert select_lane(CLOUD_MIN_BYTES + 1, threshold=0).lane == "cloud"
    assert select_lane(CLOUD_MIN_BYTES + 1, threshold=500_000).lane == "local"  # raised
    with pytest.raises(CloudBoundaryViolation):
        require_cloud_eligible(10, threshold=0)
    with pytest.raises(ValueError):
        select_lane(10, threshold=-1)


def test_6_settings_refuse_non_loopback_endpoints_and_lowered_rule() -> None:
    from polymath_shared.settings import SidecarSettings, WorkerSettings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SidecarSettings(llm_local_extract_url="http://10.0.0.5:8755")
    with pytest.raises(ValidationError):
        SidecarSettings(llm_cloud_url="https://api.example.com")
    SidecarSettings(llm_local_extract_url="http://localhost:8755")
    with pytest.raises(ValidationError):
        WorkerSettings(cloud_min_bytes=0)
    WorkerSettings(cloud_min_bytes=500_000)


# ---------------------------------------------------------------------------
# llm_provider (#7, #2, #3)
# ---------------------------------------------------------------------------

def test_7_packing_never_exceeds_cap_unless_a_single_child_does() -> None:
    w = "word " * 20
    rows = [{"chunk_id": f"c{i}", "parent_id": "p", "text": w + "x" * n,
             "char_start": i} for i, n in enumerate([100, 50000, 50000, 50000])]
    ns = llm_provider.build_neighborhoods(rows, max_chars=60000)
    assert all(n.char_len <= 60000 or len(n.chunks) == 1 for n in ns)
    assert [[c for c, _ in n.chunks] for n in ns] == [["c0"], ["c1"], ["c2"], ["c3"]]
    assert all(n.chunks for n in ns)


def test_2_contract_identity_covers_semantic_inputs(monkeypatch) -> None:
    from polymath_shared.identity import content_hash
    base = llm_provider.contract_identity()
    for key in ("models", "prompt_sha256", "ontology_sha256", "type_fallbacks_sha256",
                "generation", "neighborhood", "chunk_kind_sha256", "limiter_seeds",
                "cloud_min_bytes"):
        assert key in base, key
    real = llm_provider.get_settings()
    changed = real.model_copy(deep=True)
    changed.sidecars.llm_cloud_model = "some-other-model"
    monkeypatch.setattr(llm_provider, "get_settings", lambda: changed)
    assert content_hash(llm_provider.contract_identity()) != content_hash(base)


def test_3_limiter_refusal_fails_the_stage_instead_of_completing(monkeypatch) -> None:
    from polymath_shared.llm_extraction.client import LLMCallResult

    class _Fake:
        lane = "cloud"
        model = "m"

        def _lane_limiter(self):
            return AdaptiveLimiter("t", ProviderLimit(kind="rate", rpm=10, conc_cap=2))

        def extract(self, neighborhoods, **kw):
            return LLMCallResult(
                lane="cloud", model="m", raw_text="", packet=None,
                sanitize=SanitizeResult(ok=False, error_class="LIMITER_REFUSED"),
                wall_ms=0, error_class="LIMITER_REFUSED")

    monkeypatch.setattr(llm_provider, "make_client", lambda lane: _Fake())
    # never attach the LIVE Postgres store from a unit test (it would
    # persist this test's limiter state into the fleet's controller row)
    monkeypatch.setattr(llm_provider, "_ensure_controller_store", lambda: None)
    n = llm_provider.Neighborhood(nid="p:0", chunks=[("c", CH)])
    with pytest.raises(ExtractionTransportError):
        llm_provider.run_proposals([n], lane="cloud", source_bytes=CLOUD_MIN_BYTES + 1)


# ---------------------------------------------------------------------------
# client (#14, #26 fallback shape)
# ---------------------------------------------------------------------------

def test_14_slot_released_on_malformed_body_shape(monkeypatch) -> None:
    client = LLMExtractionClient("local", url="http://127.0.0.1:1", model="m")
    lim = client._lane_limiter()
    held_before = lim._sem.held

    def _bad(*a, **k):
        raise ValueError("invalid literal for int(): 'n/a'")

    monkeypatch.setattr(client, "_chat", _bad)
    with pytest.raises(ExtractionTransportError):
        client.extract([("p", [("c", CH)])], source_bytes=10,
                       threshold_bytes=CLOUD_MIN_BYTES)
    assert lim._sem.held == held_before


# ---------------------------------------------------------------------------
# limiter (#11, #12, #13, #21, #22, #30)
# ---------------------------------------------------------------------------

def _rate(**kw) -> AdaptiveLimiter:
    spec = dict(kind="rate", rpm=1000, tpm=None, conc_cap=8, min=2, max=8, adaptive=False)
    spec.update(kw)
    return AdaptiveLimiter("t", ProviderLimit(**spec))


def test_11_half_open_admits_exactly_one_probe() -> None:
    lim = _rate()
    for _ in range(10):
        lim.record_failure()
    assert lim.breaker_open
    lim._breaker.cooldown_s = 0.0
    time.sleep(0.005)
    assert lim.acquire(block=False)            # the single probe
    assert not lim.acquire(block=False)        # nobody else while it flies
    lim.record_failure()                       # probe failed → open again
    lim.release()
    assert lim.breaker_open
    assert not lim.acquire(block=False) or lim._breaker.probe_in_flight
    lim.release() if lim._breaker.probe_in_flight else None
    lim.record_success()                       # probe succeeded → closed
    assert not lim.breaker_open
    assert lim.acquire(block=False) and lim.acquire(block=False)
    lim.release(); lim.release()


def test_12_bucket_clamps_oversized_requests_and_never_sleeps_under_lock() -> None:
    b = _TokenBucket(60)
    assert b.acquire(10_000, block=True)       # clamped to capacity, returns
    b2 = _TokenBucket(60)
    b2.tokens = 0.0
    t = threading.Thread(target=lambda: b2.acquire(1.0, block=True), daemon=True)
    t.start()
    time.sleep(0.05)
    t0 = time.perf_counter()
    b2.sync_remaining(0)                       # must not wait behind the sleeper
    assert time.perf_counter() - t0 < 0.2
    t.join(timeout=3)


def test_13_non_blocking_acquire_never_waits_when_saturated() -> None:
    lim = AdaptiveLimiter("t", ProviderLimit(kind="concurrency", init=1, min=1, max=1))
    assert lim.acquire(block=False)
    t0 = time.perf_counter()
    assert not lim.acquire(block=False)
    assert time.perf_counter() - t0 < 0.1
    assert lim._sem.held == 1
    lim.release()


def test_21_retry_after_holds_the_lane() -> None:
    lim = _rate()
    lim.record_failure(retry_after="2")
    assert lim.not_before > 0
    assert not lim.acquire(block=False)
    lim.record_failure(retry_after="not-a-number")   # ignored, no crash


def test_22_rpm_token_refunded_when_tpm_refuses() -> None:
    lim = _rate(rpm=2, tpm=10)
    assert lim.acquire(est_tokens=10, block=False)      # drains the TPM bucket
    lim.release()
    assert not lim.acquire(est_tokens=5, block=False)   # TPM refuses → RPM refunded
    assert lim._rpm.tokens == pytest.approx(1.0, abs=0.01)   # only the first call's token (refill drift)
    assert lim._sem.held == 0


def test_30_from_config_ignores_unknown_keys() -> None:
    base = ProviderLimit(kind="rate", rpm=1)
    got = ProviderLimit.from_config(base, {"rpm": 5, "typo_key": 1, "init": 3})
    assert got.rpm == 5 and got.init == 3


# ---------------------------------------------------------------------------
# extract_worker (#10)
# ---------------------------------------------------------------------------

def test_10_multi_sentence_quote_is_clipped_and_recorded() -> None:
    from polymath_shared.contracts import EvidenceSpan
    from workers.extract_worker import _clip_to_sentences, _sentences_of, _slices
    txt = "FortiGate reported errors. The SOC verified the host."
    sp = EvidenceSpan(chunk_id="c", start=0, end=len(txt), text=txt,
                      evidence_class="llm_relation", score=1.0, extractor_version="v")
    clipped, audit = _clip_to_sentences([sp], txt)
    assert [c.text for c in clipped] == ["FortiGate reported errors.",
                                         "The SOC verified the host."]
    assert all(txt[c.start:c.end] == c.text for c in clipped)
    assert audit and audit[0]["reason"] == "EVIDENCE_CROSSES_SENTENCE"
    assert sum(len(s.evidence) for s in _slices(_sentences_of(txt), [], clipped)) == 2
    single = sp.model_copy(update={"end": 26, "text": txt[:26]})
    assert _clip_to_sentences([single], txt) == ([single], [])


# ---------------------------------------------------------------------------
# batched_server (#4, #15, #27, #28)
# ---------------------------------------------------------------------------

class _FakeTok:
    def encode(self, text):
        return text.split()

    def decode(self, ids):
        return " ".join(ids)

    def apply_chat_template(self, messages, **kw):
        return " ".join(m["content"] for m in messages)


def _server():
    pytest.importorskip("flask")
    sys.path.insert(0, str(ROOT / "sidecars" / "local_extractor"))
    import importlib
    mod = importlib.import_module("batched_server")
    mod._state.clear()
    mod._state.update({"model": object(), "tok": _FakeTok(), "logits_processors": None,
                       "batch_generate": None})
    return mod


def test_15_per_item_budget_and_honest_finish_reason() -> None:
    srv = _server()
    srv._state["batch_generate"] = lambda model, tok, prompts, **kw: [
        "one two three four five", "one two"]
    res = srv._generate([[1], [2]], [3, 10])
    assert res[0] == {"content": "one two three", "finish_reason": "length",
                      "completion_tokens": 3}
    assert res[1] == {"content": "one two", "finish_reason": "stop",
                      "completion_tokens": 2}
    assert srv._clamp_tokens(10 ** 9) == srv.SERVER_MAX_TOKENS
    assert srv._clamp_tokens("junk") == srv.DEFAULT_MAX_TOKENS


def test_4_micro_batch_failure_answers_every_item_once() -> None:
    srv = _server()

    def _boom(*a, **k):
        raise RuntimeError("Metal OOM")

    srv._state["batch_generate"] = _boom
    items = [{"system": "", "user": "hi", "max_tokens": 5,
              "gate": threading.Event(), "out": None, "status": None} for _ in range(3)]
    with srv._MICRO_LOCK:
        srv._MICRO_QUEUE[:] = items
    srv._run_micro_batch()
    for it in items:
        assert it["gate"].is_set() and it["status"] == 500
        assert json.loads(it["out"])["error"]["type"] == "generation_failed"
    with pytest.raises(ValueError):
        srv._split_messages([])
    with pytest.raises(ValueError):
        srv._split_messages([{"role": "user"}])
    assert srv._split_messages([{"role": "system", "content": "s"},
                                {"role": "user", "content": "u"}]) == ("s", "u")
