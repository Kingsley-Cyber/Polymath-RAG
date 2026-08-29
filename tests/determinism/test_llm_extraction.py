"""LOCAL-LLM-EXTRACTION-V1 — contract, gate, boundary, and neighborhood tests.

Pure-determinism suite (no DB, no network). The boundary tests double as
the CI guard for the owner's 300 KB rule: a cloud dispatch for an
ineligible source must be impossible, not merely discouraged.
"""
from __future__ import annotations

import json
import sys
import pathlib

import pytest
from pydantic import ValidationError

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.llm_extraction.contract import (  # noqa: E402
    CONTRACT_ID,
    ExtractionPacket,
)
from polymath_shared.llm_extraction.gate import (  # noqa: E402
    ChunkView,
    map_core_type,
    sanitize,
    strip_thinking,
    validate_and_normalize,
)
from polymath_shared.llm_extraction.policy import (  # noqa: E402
    CLOUD_MIN_BYTES,
    CloudBoundaryViolation,
    require_cloud_eligible,
    select_lane,
)
from polymath_shared.llm_extraction.client import (  # noqa: E402
    LLMExtractionClient,
    build_user_prompt,
)
from workers.llm_provider import (  # noqa: E402
    build_neighborhoods,
    to_evidence_spans,
    to_precomputed_entities,
)

CHUNK_A = ("FortiGate firewalls reported VPN tunnel errors after the "
           "firmware update on January 15.")
CHUNK_B = ("The SOC playbook requires analysts to verify the jump host "
           "before re-keying any IPsec tunnel.")


def _packet_json(nid: str = "p1:0", *, contract: str = CONTRACT_ID,
                 entity_quote: str | None = None,
                 relation_quote: str | None = None) -> str:
    return json.dumps({
        "contract": contract, "profile": "volume",
        "items": [{
            "neighborhood_id": nid,
            "entities": [
                {"surface": "FortiGate", "type": "Product",
                 "quote": entity_quote or CHUNK_A},
                {"surface": "jump host", "type": "system",
                 "quote": CHUNK_B},
            ],
            "relations": [
                {"subject": "FortiGate", "predicate": "reported",
                 "object": "VPN tunnel errors",
                 "quote": relation_quote or CHUNK_A},
            ],
            "digest": {"central_claim": "A firewall error report.",
                       "main_mechanism": "Firmware update caused errors.",
                       "retrieval_uses": ["why do VPN 400s spike?"]},
        }],
    })


def _views(nid: str = "p1:0") -> dict[str, list[ChunkView]]:
    return {nid: [ChunkView("chunk_a", CHUNK_A), ChunkView("chunk_b", CHUNK_B)]}


# ---------------------------------------------------------------------------
# contract
# ---------------------------------------------------------------------------

def test_contract_round_trip() -> None:
    packet = ExtractionPacket.model_validate_json(_packet_json())
    assert packet.items[0].entities[0].surface == "FortiGate"
    assert packet.profile == "volume"


def test_contract_rejects_unknown_contract_id() -> None:
    with pytest.raises(ValidationError):
        ExtractionPacket.model_validate_json(
            _packet_json(contract="some-other-contract"))


def test_contract_rejects_unknown_profile() -> None:
    raw = json.loads(_packet_json())
    raw["profile"] = "deluxe"
    with pytest.raises(ValidationError):
        ExtractionPacket.model_validate(raw)


# ---------------------------------------------------------------------------
# sanitize
# ---------------------------------------------------------------------------

def test_strip_thinking_removes_blocks_and_fences() -> None:
    raw = "<think>reasoning here</think>```json\n{\"a\": 1}\n```"
    assert strip_thinking(raw) == '{"a": 1}'


def test_sanitize_salvages_truncated_stream() -> None:
    good = _packet_json()
    raw = json.loads(good)
    item = raw["items"][0]
    # realistic truncation: output budget cut the stream after the entity
    # array completed — the full packet no longer parses, the good prefix
    # must not be discarded
    stream = good[:good.index('"relations"')].rstrip().rstrip(",") + \
        "]}]}"
    res, packet = sanitize(stream, {"p1:0"})
    assert res.ok and res.salvaged
    assert packet is not None
    assert {e.surface for e in packet.items[0].entities} == {"FortiGate", "jump host"}
    assert item["neighborhood_id"] == packet.items[0].neighborhood_id


def test_sanitize_salvages_mid_object_cut() -> None:
    # cut right after the neighborhood_id pair completed (trailing comma
    # kept: it is the cut marker the repair searches for, mid-object, with
    # NO bracket closers)
    good = _packet_json()
    stream = good[:good.index('"entities"')].rstrip()
    res, packet = sanitize(stream, {"p1:0"})
    assert res.ok and res.salvaged
    assert packet is not None
    assert packet.items[0].neighborhood_id == "p1:0"
    assert {e.surface for e in packet.items[0].entities} <= {"FortiGate", "jump host"}


def test_sanitize_rejects_unknown_neighborhood() -> None:
    res, packet = sanitize(_packet_json(nid="bogus"), {"p1:0"})
    assert not res.ok
    assert res.error_class == "SANITIZE_UNKNOWN_NEIGHBORHOOD"
    assert packet is None


def test_sanitize_unparseable_is_a_durable_disposition() -> None:
    res, packet = sanitize("the model wrote prose instead of json", {"p1:0"})
    assert not res.ok
    assert res.error_class == "SANITIZE_UNPARSEABLE"
    assert packet is None


# ---------------------------------------------------------------------------
# gate: attestation + normalization
# ---------------------------------------------------------------------------

def test_gate_locates_and_normalizes() -> None:
    _, packet = sanitize(_packet_json(), {"p1:0"})
    out = validate_and_normalize(packet, _views())
    assert out.stats["entities"] >= 2
    assert out.stats["relations"] == 1
    assert not out.rejections
    a_spans = out.entities_by_chunk["chunk_a"]
    fortigate = [e for e in a_spans if e["text"] == "FortiGate"]
    assert fortigate and CHUNK_A[fortigate[0]["start"]:fortigate[0]["end"]] == "FortiGate"
    # open-vocabulary 'system' coerced via the documented fallback, raw preserved
    assert any(e["raw_type"] == "system" for e in out.entities_by_chunk["chunk_b"])
    assert all(e["label"] in ("Technology", "Concept", "Product")
               for e in out.entities_by_chunk["chunk_b"])
    ev = out.evidence_by_chunk["chunk_a"][0]
    assert CHUNK_A[ev["start"]:ev["end"]] == ev["text"]
    assert ev["predicate"] == "reported"


def test_gate_rejects_unattested_entity() -> None:
    raw = json.loads(_packet_json())
    raw["items"][0]["entities"].append(
        {"surface": "Palo Alto", "type": "Product", "quote": CHUNK_A})
    _, packet = sanitize(json.dumps(raw), {"p1:0"})
    out = validate_and_normalize(packet, _views())
    assert any(r["error_class"] == "UNATTESTED_ENTITY"
               and r["surface"] == "Palo Alto" for r in out.rejections)
    assert not any(e["text"] == "Palo Alto"
                   for spans in out.entities_by_chunk.values() for e in spans)


def test_gate_rejects_relation_with_missing_endpoint() -> None:
    raw = json.loads(_packet_json())
    raw["items"][0]["relations"][0]["object"] = "spanning tree"
    _, packet = sanitize(json.dumps(raw), {"p1:0"})
    out = validate_and_normalize(packet, _views())
    assert any(r["error_class"] == "UNATTESTED_RELATION_ENDPOINT"
               for r in out.rejections)


def test_gate_handles_whitespace_wrapped_quotes() -> None:
    wrapped = CHUNK_A.replace(" ", "\n", 1)
    _, packet = sanitize(_packet_json(entity_quote=wrapped,
                                      relation_quote=wrapped), {"p1:0"})
    out = validate_and_normalize(packet, _views())
    assert out.stats["relations"] == 1
    assert out.stats["entities"] >= 1


def test_gate_emits_endpoint_mentions_inside_relation_quote() -> None:
    _, packet = sanitize(_packet_json(), {"p1:0"})
    out = validate_and_normalize(packet, _views())
    a_spans = out.entities_by_chunk["chunk_a"]
    # object endpoint "VPN tunnel errors" must exist as a real mention
    obj = [e for e in a_spans if e["text"] == "VPN tunnel errors"]
    assert obj and CHUNK_A[obj[0]["start"]:obj[0]["end"]] == "VPN tunnel errors"


def test_map_core_type_policy_fallback_default() -> None:
    assert map_core_type("Product")[1] == "policy"
    assert map_core_type("system") == ("Technology", "fallback")
    assert map_core_type("flibble")[1] == "concept_default"


# ---------------------------------------------------------------------------
# 300 KB boundary (fail closed, both boundaries)
# ---------------------------------------------------------------------------

def test_select_lane_boundary() -> None:
    assert select_lane(CLOUD_MIN_BYTES).lane == "local"      # at: local only
    assert select_lane(CLOUD_MIN_BYTES - 1).lane == "local"
    assert select_lane(CLOUD_MIN_BYTES + 1).lane == "cloud"
    with pytest.raises(ValueError):
        select_lane(-1)


def test_dispatch_boundary_refuses_small_source() -> None:
    require_cloud_eligible(CLOUD_MIN_BYTES + 1)              # passes
    with pytest.raises(CloudBoundaryViolation):
        require_cloud_eligible(CLOUD_MIN_BYTES)              # at threshold: refused
    with pytest.raises(CloudBoundaryViolation):
        require_cloud_eligible(1)


def test_cloud_client_dispatch_guard_blocks_network() -> None:
    client = LLMExtractionClient(
        "cloud", url="http://127.0.0.1:1", model="qwen3.5:397b-cloud")
    # Dispatch boundary fires BEFORE any I/O: a violation must raise even
    # though the endpoint is unroutable — prove no request is attempted.
    with pytest.raises(CloudBoundaryViolation):
        client.extract([("p1:0", [("c1", CHUNK_A)])],
                       source_bytes=10, threshold_bytes=CLOUD_MIN_BYTES)


# ---------------------------------------------------------------------------
# neighborhoods + worker shapes
# ---------------------------------------------------------------------------

def _chunks() -> list[dict]:
    return [
        {"chunk_id": "c1", "parent_id": "p1", "text": "a" * 50, "char_start": 0},
        {"chunk_id": "c2", "parent_id": "p1", "text": "b" * 50, "char_start": 50},
        {"chunk_id": "c3", "parent_id": "p2", "text": "c" * 7000, "char_start": 100},
        {"chunk_id": "c4", "parent_id": None, "text": "d" * 10, "char_start": 7500},
    ]


def test_neighborhoods_group_split_and_orphans() -> None:
    ns = build_neighborhoods(_chunks(), max_chars=100)
    p1 = [n for n in ns if n.nid.startswith("p1")]
    assert len(p1) == 1 and {cid for cid, _ in p1[0].chunks} == {"c1", "c2"}
    assert any(n.nid.startswith("p2:") for n in ns)          # oversized split
    assert any(n.nid.startswith("__orphan__") for n in ns)   # no parent: still read


def test_precomputed_covers_every_chunk_and_composition() -> None:
    from polymath_shared.llm_extraction.gate import sanitize as _s
    _, packet = _s(_packet_json(), {"p1:0"})
    merged = validate_and_normalize(packet, _views())
    pre = to_precomputed_entities(merged, [("Product",), ("Product", "Concept")],
                                  all_chunk_ids=["chunk_a", "chunk_b", "chunk_z"])
    for cid in ("chunk_a", "chunk_b", "chunk_z"):
        assert set(pre[cid].keys()) == {("Product",), ("Product", "Concept")}
    assert pre["chunk_a"][("Product",)]["spans"]


def test_evidence_spans_are_chunk_ordered() -> None:
    _, packet = sanitize(_packet_json(), {"p1:0"})
    merged = validate_and_normalize(packet, _views())
    spans = to_evidence_spans(merged)["chunk_a"]
    assert spans and spans[0].evidence_class == "llm_relation"
    assert spans[0].extractor_version == "polymath-extraction-v1-evidence"


def test_user_prompt_carries_chunk_markers() -> None:
    prompt = build_user_prompt([("p1:0", [("c1", "hello"), ("c2", "world")])])
    assert "[chunk:c1]" in prompt and "[chunk:c2]" in prompt
