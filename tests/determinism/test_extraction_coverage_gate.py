"""EXTRACTION-COVERAGE-HARDENING-V1 — the mandatory checks, pinned.

Pure determinism: no DB, no network, no model. Each test names the
measured failure it guards (2026-08-30, corpus cysa-study-v1).
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.extraction_coverage import coverage_verdict  # noqa: E402
from polymath_shared.llm_extraction.client import (  # noqa: E402
    ExtractionTransportError,
    LLMCallResult,
)
from polymath_shared.llm_extraction.contract import SanitizeResult  # noqa: E402
from polymath_shared.llm_extraction.gate import (  # noqa: E402
    ChunkView,
    is_interrogative,
    sanitize,
    validate_and_normalize,
)
from polymath_shared.llm_extraction.limiter import AdaptiveLimiter, ProviderLimit  # noqa: E402
from polymath_shared.llm_extraction.policy import CLOUD_MIN_BYTES  # noqa: E402
from polymath_shared.region_role import (  # noqa: E402
    NOISE_ROLES,
    ROLE_BODY,
    ROLE_INDEX,
    ROLE_LEGAL,
    ROLE_NOISE_OCR,
    ROLE_OUTPUT,
    ROLE_QUESTION_BANK,
    ROLE_STUB,
    classify_region,
    is_noise,
    parent_role,
)
from workers import llm_provider  # noqa: E402

TEXTS = {
    "p1": "FortiGate firewalls require IPsec tunnels for site links.",
    "p2": "Splunk correlates with Elastic for detection pipelines.",
    "p3": "Nessus scans hosts for known vulnerabilities every night.",
    "p4": "Wireshark captures packets on the mirror port for analysis.",
}
RELS = {
    "p1": ("FortiGate firewalls", "REQUIRES", "IPsec tunnels", TEXTS["p1"]),
    "p2": ("Splunk", "CORRELATES_WITH", "Elastic", TEXTS["p2"]),
    "p3": ("Nessus", "ACTS_ON", "hosts", TEXTS["p3"]),
    "p4": ("Wireshark", "ACTS_ON", "packets", TEXTS["p4"]),
}


def _item(nid: str) -> dict:
    s, p, o, q = RELS[nid]
    return {"neighborhood_id": f"{nid}:0",
            "entities": [{"surface": s, "type": "Product", "quote": q}],
            "relations": [{"subject": s, "predicate": p, "object": o, "quote": q}],
            "digest": {}}


def _raw(nids: list[str]) -> str:
    return json.dumps({"contract": "polymath-extraction-v1", "profile": "volume",
                       "items": [_item(n) for n in nids]})


def _neighborhoods() -> list:
    return [llm_provider.Neighborhood(nid=f"{k}:0", chunks=[(f"c_{k}", v)])
            for k, v in TEXTS.items()]


class _Lane:
    """A cloud lane double: `script` maps the tuple of neighborhood ids in
    a call to the raw text it answers with (None = quarantine)."""
    lane = "cloud"
    model = "m"

    def __init__(self, script, *, finish=None, salvaged_for=()):
        self.script = script
        self.finish = finish
        self.salvaged_for = set(salvaged_for)
        self.calls: list[tuple[str, ...]] = []

    def _lane_limiter(self):
        return AdaptiveLimiter("t", ProviderLimit(kind="rate", rpm=100, conc_cap=4))

    def extract(self, neighborhoods, **kw):
        ids = tuple(nid for nid, _ in neighborhoods)
        self.calls.append(ids)
        raw = self.script(ids)
        if raw is None:
            return LLMCallResult(lane="cloud", model="m", raw_text="", packet=None,
                                 sanitize=SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE"),
                                 wall_ms=1, error_class="QUARANTINED_UNPARSEABLE",
                                 neighborhood_ids=list(ids))
        s_res, packet = sanitize(raw, set(ids))
        if ids in self.salvaged_for:
            s_res = SanitizeResult(ok=True, salvaged=True)
        return LLMCallResult(lane="cloud", model="m", raw_text=raw, packet=packet,
                             sanitize=s_res, wall_ms=1, neighborhood_ids=list(ids),
                             finish_reason=self.finish if len(ids) > 1 else "stop")


def _run(monkeypatch, lane):
    monkeypatch.setattr(llm_provider, "make_client", lambda _lane: lane)
    monkeypatch.setattr(llm_provider, "_ensure_controller_store", lambda: None)
    return llm_provider.run_proposals(_neighborhoods(), lane="cloud",
                                      source_bytes=CLOUD_MIN_BYTES + 1)


def _disp(merged) -> dict[str, str]:
    return {d["nid"]: d["disposition"] for d in merged.dispositions}


# ---------------------------------------------------------------- coverage

def test_first_neighborhood_only_is_reissued_and_recovered(monkeypatch) -> None:
    """The measured failure: a 4-neighborhood call answered for the first
    id only (pattern X...X...). Every silent id is re-issued singly."""
    lane = _Lane(lambda ids: _raw([ids[0].split(":")[0]]))
    results, merged = _run(monkeypatch, lane)
    st = merged.stats
    assert st["neighborhoods_sent"] == 4
    assert st["neighborhoods_reissued"] == 3 and st["neighborhoods_recovered"] == 3
    assert st["neighborhoods_dropped"] == 0 and st["neighborhoods_unaccounted"] == 0
    assert st["neighborhoods_returned"] == 4
    assert st["relations"] == 4 and st["parents_with_extraction"] == 4
    d = _disp(merged)
    assert d["p1:0"] == "returned"
    assert d["p2:0"] == d["p3:0"] == d["p4:0"] == "reissued_returned"
    assert lane.calls == [("p1:0", "p2:0", "p3:0", "p4:0"), ("p2:0",), ("p3:0",), ("p4:0",)]
    assert sum(1 for r in results if r.reissue) == 3


def test_permanent_loss_is_recorded_as_dropped_never_raised(monkeypatch) -> None:
    def script(ids):
        keep = [i.split(":")[0] for i in ids if i != "p3:0"]
        return _raw(keep) if keep else None
    lane = _Lane(script)
    _results, merged = _run(monkeypatch, lane)
    st = merged.stats
    assert st["neighborhoods_dropped"] == 1 and st["neighborhoods_unaccounted"] == 0
    assert _disp(merged)["p3:0"] == "dropped"
    assert st["relations"] == 3 and st["parents_with_extraction"] == 3
    assert not coverage_verdict(st)["ok"]
    assert coverage_verdict(st)["reasons"] == ["extraction_dropped_neighborhoods_1"]


def test_truncated_call_marks_last_item_incomplete_and_reissues(monkeypatch) -> None:
    lane = _Lane(lambda ids: _raw([i.split(":")[0] for i in ids]), finish="length")
    _results, merged = _run(monkeypatch, lane)
    st = merged.stats
    assert st["calls_truncated"] == 1
    assert st["neighborhoods_reissued"] == 1 and st["neighborhoods_recovered"] == 1
    assert _disp(merged)["p4:0"] == "reissued_returned"
    assert lane.calls[1] == ("p4:0",)


def test_salvaged_call_is_treated_like_a_truncated_one(monkeypatch) -> None:
    full = ("p1:0", "p2:0", "p3:0", "p4:0")
    lane = _Lane(lambda ids: _raw([i.split(":")[0] for i in ids]), salvaged_for=[full])
    _results, merged = _run(monkeypatch, lane)
    assert merged.stats["calls_salvaged"] == 1
    assert merged.stats["neighborhoods_reissued"] == 1
    assert _disp(merged)["p4:0"] == "reissued_returned"


def test_quarantined_call_reissues_every_id_it_carried(monkeypatch) -> None:
    lane = _Lane(lambda ids: None if len(ids) > 1 else _raw([ids[0].split(":")[0]]))
    _results, merged = _run(monkeypatch, lane)
    st = merged.stats
    assert st["calls_quarantined"] == 1
    assert st["neighborhoods_reissued"] == 4 and st["neighborhoods_recovered"] == 4
    assert st["neighborhoods_dropped"] == 0 and st["relations"] == 4


def test_incomplete_partial_is_kept_when_reissue_fails(monkeypatch) -> None:
    def script(ids):
        if len(ids) > 1:
            return _raw([i.split(":")[0] for i in ids])
        return None
    lane = _Lane(script, finish="length")
    _results, merged = _run(monkeypatch, lane)
    assert _disp(merged)["p4:0"] == "incomplete_kept"
    assert merged.stats["neighborhoods_incomplete_kept"] == 1
    assert merged.stats["neighborhoods_dropped"] == 0
    assert merged.stats["relations"] == 4          # the partial's relation survives


def test_limiter_refusal_on_reissue_still_fails_the_stage(monkeypatch) -> None:
    def script(ids):
        return _raw([ids[0].split(":")[0]]) if len(ids) > 1 else "REFUSE"
    class _Refusing(_Lane):
        def extract(self, neighborhoods, **kw):
            ids = tuple(nid for nid, _ in neighborhoods)
            if len(ids) == 1:
                return LLMCallResult(lane="cloud", model="m", raw_text="", packet=None,
                                     sanitize=SanitizeResult(ok=False, error_class="LIMITER_REFUSED"),
                                     wall_ms=0, error_class="LIMITER_REFUSED",
                                     neighborhood_ids=list(ids))
            return super().extract(neighborhoods, **kw)
    with pytest.raises(ExtractionTransportError):
        _run(monkeypatch, _Refusing(script))


def test_every_neighborhood_returned_means_no_reissue(monkeypatch) -> None:
    lane = _Lane(lambda ids: _raw([i.split(":")[0] for i in ids]))
    _results, merged = _run(monkeypatch, lane)
    st = merged.stats
    assert st["neighborhoods_reissued"] == 0 and st["calls_reissue"] == 0
    assert st["neighborhoods_returned"] == 4 and coverage_verdict(st)["ok"]
    assert len(lane.calls) == 1


# ----------------------------------------------------------------- verdict

def test_verdict_hard_soft_and_unknown() -> None:
    unknown = coverage_verdict(None)
    assert unknown["ok"] and not unknown["known"] and unknown["warnings"] == ["extraction_coverage_unknown"]
    legacy = coverage_verdict({"entities": 3})          # pre-hardening artifact
    assert legacy["ok"] and not legacy["known"]
    bad = coverage_verdict({"neighborhoods_sent": 4, "neighborhoods_unaccounted": 1,
                            "neighborhoods_dropped": 2, "parents_total": 4,
                            "parents_with_extraction": 1})
    assert not bad["ok"]
    assert bad["reasons"] == ["extraction_unaccounted_neighborhoods_1",
                              "extraction_dropped_neighborhoods_2"]
    soft = coverage_verdict({"neighborhoods_sent": 4, "parents_total": 4,
                             "parents_with_extraction": 1}, floor=0.5)
    assert soft["ok"] and soft["coverage"] == 0.25
    assert soft["warnings"] == ["extraction_coverage_0.25_below_floor_0.50"]
    assert coverage_verdict({"neighborhoods_sent": 4, "parents_total": 4,
                             "parents_with_extraction": 1})["warnings"] == []


# ------------------------------------------------------------- interrogative

QUIZ = ("Which one of the following is not a phase of the threat lifecycle "
        "addressed in the MITRE ATT&CK model? Domination Exfiltration Execution")


def test_interrogative_quote_is_rejected_at_the_gate() -> None:
    assert is_interrogative(QUIZ)
    assert is_interrogative("What tool can she use?")
    assert not is_interrogative("FOREIGN KEY is not a type of PRIMARY KEY.")
    assert is_interrogative("He asked what to do?")            # trailing '?' is enough
    assert not is_interrogative("Which is fine.")             # opener alone is not
    raw = json.dumps({"contract": "polymath-extraction-v1", "profile": "volume", "items": [{
        "neighborhood_id": "q:0", "entities": [],
        "relations": [{"subject": "Domination", "predicate": "OPPOSES",
                       "object": "MITRE ATT&CK model", "quote": QUIZ}],
        "digest": {}}]})
    _s, packet = sanitize(raw, {"q:0"})
    out = validate_and_normalize(packet, {"q:0": [ChunkView("c", QUIZ)]})
    assert out.stats["relations"] == 0 and out.stats["relations_rejected"] == 1
    assert out.rejections[0]["error_class"] == "INTERROGATIVE_ATTESTATION"


# ---------------------------------------------------------------- regions

GARBAGE = ("cucxtulaee ence ee oe ee ee eee ee i saeceve sere ee ee ee ee a a 7 ; "
           "ei ee = rokomee eae ue oe vom Se Se RE ee eS ee ee eR ee ee ee SRE RETESET "
           "ESS SD ee eee ee oe ee Pr Pe ert Te eee eee ed ee eee eee eee ee a ee ee "
           "ee ee Beasts he ake er ee er rr a ee er rr re or er oe er TiyirLee ee 2")
PACKETS = ("35 0,111428929 10,0,2.4 10,0.2.15 vOP 60 41015 = 10 Len=0 36 O,111446417 "
           "10,0,2.4 10,0,2.15 UDP 60 41015 + 1542 Len=0 37 0,111508808 10,0,2.4 "
           "10,0,2.15 VDP 60 41015 = 1349 Len=0 38 0,111524824 10.0.2. 10,0,2.15 VDP")
INDEX = "\n".join([
    "agent-based scanning, 81, 89, 90, 313, 316", "Agile software development, 139, 145, 330",
    "air gap, 16, 18, 286", "AbuseIPDB, 275, 388", "acceptable use policy (AUP), 160, 340",
    "accessing hosts, 4–5, 282", "account lockouts, 289", "attack vectors, 149, 169, 345",
    "authenticated vulnerability scan, 185, 352", "auth.log file, 27, 292"])
TRADEMARK = ("All trademarks and brands within this book are for clarifying purposes only "
             "and are the owned by the owners themselves, not affiliated with this document.")
QUIZ_PAGE = ("Which one of the following elements is least likely to be found in a data retention "
             "policy? Minimum retention period for data Maximum retention period for data "
             "Description of information to retain Classification of information elements "
             "Kevin leads the IT team at a small business and does not have a dedicated security "
             "team. Which of the following is the most appropriate tool for Kevin to use? "
             "Penetration testing tool Patch management tool Vulnerability scanning tool")
BODY = ("The MANUFACTURER_ID of the PRODUCT_MANUFACTURERS table has the same constraint. "
        "As you can see, the PRODUCT_NAMES table has a column called MANUFACTURER_ID. That "
        "column has the values of a column in the PRODUCT_MANUFACTURERS table. If you will "
        "remove a manufacturer, you also need to remove the entry from the MANUFACTURER_ID "
        "column of the PRODUCT_NAMES table. You can achieve this result using FOREIGN KEY.")


@pytest.mark.parametrize("text,role", [
    (GARBAGE, ROLE_NOISE_OCR), (PACKETS, ROLE_OUTPUT), (INDEX, ROLE_INDEX),
    (TRADEMARK, ROLE_LEGAL), (QUIZ_PAGE, ROLE_QUESTION_BANK), (BODY, ROLE_BODY),
    ("too short to matter", ROLE_STUB),
])
def test_region_classifier_on_measured_samples(text, role) -> None:
    got, reason = classify_region(text)
    assert got == role, (got, reason)
    assert classify_region(text) == classify_region(text)      # deterministic


def test_region_noise_membership_and_parent_rule() -> None:
    assert is_noise(ROLE_NOISE_OCR) and is_noise(ROLE_INDEX) and is_noise(ROLE_LEGAL)
    assert not is_noise(ROLE_BODY) and not is_noise(ROLE_QUESTION_BANK)
    assert not is_noise(ROLE_OUTPUT) and not is_noise(None)
    assert ROLE_STUB in NOISE_ROLES
    assert parent_role([ROLE_NOISE_OCR, ROLE_NOISE_OCR])[0] == ROLE_NOISE_OCR
    assert parent_role([ROLE_NOISE_OCR, ROLE_BODY])[0] == ROLE_BODY
    assert parent_role([ROLE_QUESTION_BANK, ROLE_QUESTION_BANK, ROLE_BODY])[0] == ROLE_QUESTION_BANK
    assert parent_role([])[0] == ROLE_STUB


def test_noise_regions_never_enter_a_neighborhood() -> None:
    rows = [
        {"chunk_id": "a", "parent_id": "p", "text": BODY, "char_start": 0, "region_role": ROLE_BODY},
        {"chunk_id": "b", "parent_id": "p", "text": BODY, "char_start": 500, "region_role": ROLE_NOISE_OCR},
        {"chunk_id": "c", "parent_id": "p", "text": BODY, "char_start": 900, "region_role": None},
    ]
    out = llm_provider.build_neighborhoods(rows, max_chars=60_000)
    assert [cid for n in out for cid, _ in n.chunks] == ["a", "c"]


def test_contract_identity_pins_coverage_and_region_rules() -> None:
    ident = llm_provider.contract_identity()
    assert ident["coverage"] == "extraction-coverage-v1"
    assert len(ident["region_role_sha256"]) == 64


def test_drop_tolerance_small_loss_promotes_large_loss_blocks() -> None:
    """COVERAGE-DROP-TOLERANCE-V1 (2026-09-02): 1 dropped neighborhood of
    106 (a 515 KB book, coverage 0.906) must not hold a document back
    forever; 8 dropped of 10 (the local-lane collapse) must."""
    small = coverage_verdict({"neighborhoods_sent": 106, "neighborhoods_dropped": 1,
                              "parents_total": 106, "parents_with_extraction": 96})
    assert small["ok"] and small["reasons"] == []
    assert small["warnings"] == ["extraction_dropped_neighborhoods_1"]
    large = coverage_verdict({"neighborhoods_sent": 10, "neighborhoods_dropped": 8,
                              "parents_total": 10, "parents_with_extraction": 2})
    assert not large["ok"]
    assert large["reasons"] == ["extraction_dropped_neighborhoods_8"]
    # exactly at the tolerance is still a warning; one over is a reason
    at = coverage_verdict({"neighborhoods_sent": 100, "neighborhoods_dropped": 10,
                           "parents_total": 100, "parents_with_extraction": 90})
    over = coverage_verdict({"neighborhoods_sent": 100, "neighborhoods_dropped": 11,
                             "parents_total": 100, "parents_with_extraction": 89})
    assert at["ok"] and not over["ok"]
