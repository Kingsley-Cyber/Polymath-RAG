"""WIRE-CONTRACT PARITY: Polymath's `harness_receipt.schema.json` must never accept a receipt TrailSignal's
`HarnessResearchReceiptV1` refuses. Found by the first REAL ecommerce run (2026-09-21): a receipt that passed Polymath's
schema (a metric without `sample_n`; tool-trace intent ids containing `~`, which the ecommerce binding itself generated)
was refused by Trail's `evidence.admit`, and the run ended `terminal_gap: TRAIL_REFUSED` — a software failure, not a
governed outcome. Scripted receipts never carried a metric and never echoed the binding's intent ids, so nothing caught it.

Pinned here against the EMBEDDED, byte-pinned Trail contract: every identifier pattern, every key Trail requires, every
length bound; and, behaviourally, the receipt shapes that killed the run are now rejected at submit (the step stays open)."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "governance" / "trail" / "src"))

import pytest

from polymath_shared.adapter.contracts import ContractViolation, assert_valid
from trail_signal.contexts.evidence.public.contracts import HarnessResearchReceiptV1

POLYMATH = json.loads((ROOT / "contracts" / "adapter" / "v1" / "harness_receipt.schema.json").read_text())
TRAIL = HarnessResearchReceiptV1.model_json_schema()
STRICTER_BY_CONSTRUCTION = {"action_id": "hact_0123456789abcdef", "run_id": "adr_0123456789abcdef0123"}      # Polymath's own id formats: a subset of Trail's identifier


def _res(s):
    return TRAIL["$defs"][s["$ref"].split("/")[-1]] if "$ref" in s else s


def _flat(s, path=""):
    s, out = _res(s), {}
    for k, v in (s.get("properties") or {}).items():
        v, p = _res(v), f"{path}.{k}" if path else k
        cands = [_res(x) for x in v.get("anyOf", [v])]
        out[p] = {"pattern": next((c["pattern"] for c in cands if c.get("pattern")), None), "maxLength": next((c["maxLength"] for c in cands if c.get("maxLength")), None),
                  "required": k in (s.get("required") or [])}
        for c in cands:
            if c.get("type") == "array" and isinstance(c.get("items"), dict):
                out.update(_flat(c["items"], p + "[]"))
            elif c.get("properties") or "$ref" in c:
                out.update(_flat(c, p))
    return out


def test_polymath_is_at_least_as_strict_as_trail_on_every_field():
    assert pathlib.Path(sys.modules[HarnessResearchReceiptV1.__module__].__file__).is_relative_to(ROOT / "governance" / "trail")
    trail, mine, problems = _flat(TRAIL), _flat(POLYMATH), []
    for field, t in trail.items():
        m = mine.get(field)
        if m is None:
            problems.append(f"{field}: Trail has it, Polymath's schema does not")
            continue
        if t["required"] and not m["required"]:
            problems.append(f"{field}: required by Trail, optional here")
        if t["pattern"] and m["pattern"] != t["pattern"]:
            sample = STRICTER_BY_CONSTRUCTION.get(field)
            if not (sample and m["pattern"] and re.match(m["pattern"], sample) and re.match(t["pattern"], sample)):
                problems.append(f"{field}: Trail pattern {t['pattern']!r}, here {m['pattern']!r}")
        if t["maxLength"] and field not in STRICTER_BY_CONSTRUCTION and (m["maxLength"] or 10 ** 9) > t["maxLength"]:      # those two patterns bound their own length
            problems.append(f"{field}: Trail maxLength {t['maxLength']}, here {m['maxLength']}")
    assert not problems, "\n".join(problems)


def _receipt(**over):
    base = {"action_id": "hact_0123456789abcdef", "run_id": "adr_0123456789abcdef0123", "harness_id": "claude-code/agent-host", "started_at": "2026-09-21T06:15:00Z",
            "completed_at": "2026-09-21T06:20:00Z", "limitations": ["none"],
            "sources": [{"source_id": "src_01", "url": "https://www.reddit.com/r/photography/comments/x/y/", "source_class": "community_discussion",
                         "retrieved_at": "2026-09-21T06:20:00Z", "published_at_if_known": None}],
            "observations": [{"observation_id": "obs_01", "source_id": "src_01", "claim": "a first-person complaint", "paraphrase_or_excerpt": "paraphrase",
                              "metric_if_present": {"name": "stated_spend", "unit": "USD", "value": 160, "sample_n": None}, "context": "thread",
                              "evidence_role_claimed": "friction", "hypothesis_ids": ["hyp_0123456789abcdef"]}],
            "tool_trace": [{"search_intent_id": "q-complaint:reddit:hyp_0123456789abcdef", "tool_class": "opencli_reddit_search", "query_count": 1}]}
    return {**base, **over}


def test_a_conforming_receipt_passes_both_contracts():
    assert_valid("harness_receipt", _receipt())
    HarnessResearchReceiptV1.model_validate_json(json.dumps(_receipt()))


@pytest.mark.parametrize("mutate", [
    lambda r: r["observations"][0]["metric_if_present"].pop("sample_n"),                                     # killed the real run
    lambda r: r["tool_trace"][0].__setitem__("search_intent_id", "q-complaint~reddit~hyp_0123456789abcdef"),  # killed the real run
    lambda r: r["tool_trace"][0].pop("query_count"),
    lambda r: r["observations"][0].pop("hypothesis_ids"),
    lambda r: r["observations"][0].pop("evidence_role_claimed"),
    lambda r: r["sources"][0].__setitem__("source_class", "practitioner blog"),
    lambda r: r["observations"][0].__setitem__("observation_id", "obs 01"),
])
def test_what_trail_refuses_is_rejected_at_submit_not_at_admission(mutate):
    bad = _receipt()
    mutate(bad)
    with pytest.raises(Exception):
        HarnessResearchReceiptV1.model_validate_json(json.dumps(bad))                                         # Trail refuses it …
    with pytest.raises(ContractViolation):
        assert_valid("harness_receipt", bad)                                                                  # … so Polymath must, first


def test_the_ecommerce_binding_issues_trail_valid_intent_ids():
    src = (ROOT / "adapters" / "ecommerce" / "binding.py").read_text()
    made = re.findall(r'"intent_id": f"([^"]+)"', src)
    assert len(made) == 2 and all("~" not in m for m in made), made
    pattern = re.compile(_flat(TRAIL)["tool_trace[].search_intent_id"]["pattern"])
    assert pattern.match("q-complaint:reddit:hyp_0123456789abcdef") and pattern.match("si_supply:alibaba:pc_1")
    assert (ROOT / "adapters" / "ecommerce" / "schemas" / "harness_receipt.schema.json").read_bytes() == (ROOT / "contracts" / "adapter" / "v1" / "harness_receipt.schema.json").read_bytes()


@pytest.mark.parametrize("mutate", [
    lambda r: r.__setitem__("completed_at", "2026-09-21T06:00:00Z"),                       # before started_at — ended a real run (2026-09-21)
    lambda r: r["observations"][0].__setitem__("source_id", "src_not_listed"),
])
def test_trails_cross_field_rules_are_checked_at_submit(mutate):
    """Two rules of HarnessResearchReceiptV1 that no JSON schema can express. `validate_receipt` is what the submit path runs."""
    from polymath_shared.adapter.transitions import validate_receipt
    good, bad = _receipt(), _receipt()
    mutate(bad)
    step = {"run_id": good["run_id"], "harness_action": {"action_id": good["action_id"]}}
    assert validate_receipt(step, good) == []
    with pytest.raises(Exception):
        HarnessResearchReceiptV1.model_validate_json(json.dumps(bad))                       # Trail refuses it …
    assert validate_receipt(step, bad), "… so the submit path must refuse it first"

