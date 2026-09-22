"""ADR-069 re-pin — the Polymath side of the extended Trail wire and the hypothesis-relative receipt relation.

`semantic_view.trail_wire` is the CLOSED wire a Trail step sends after the re-pin: the four fields + the caller's STATED knowledge support +
structured candidates the ledger already holds as facts. A friction family is named only when the ledger's `suspected_friction` IS a registry
family id the run's registry projection returned; free text is never guessed into a family. `transitions.validate_receipt` refuses a stated
relation to a hypothesis the observation does not link (the submit-time half of the four-copy contract). DB-free: the run-5-shaped fixture of
`test_adapter_semantic_view.py`, pure functions only."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import semantic_view as SV  # noqa: E402
from polymath_shared.adapter import transitions as T  # noqa: E402
import test_adapter_semantic_view as F  # noqa: E402  — the fixture builders (H1 / H2, _current, _outputs, _view)

MANIFEST = json.loads((ROOT / "config" / "adapters" / "ecommerce.product_research.json").read_text())
FAMILY = "buried_accessories"


def test_the_code_under_test_is_this_checkout():
    for mod in (SV, T):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


def _views():
    return {v["hypothesis"]["hypothesis_id"]: v for v in F._view()["hypotheses"]}


def test_the_wire_is_closed_and_additive_over_the_four_fields():
    w = SV.trail_wire(_views()[F.H1], friction_family_ids=[FAMILY])
    assert set(w) <= set(SV.TRAIL_WIRE_EXTENDED_FIELDS) and tuple(SV.TRAIL_WIRE_EXTENDED_FIELDS[:4]) == SV.TRAIL_WIRE_FIELDS
    assert {k: w[k] for k in SV.TRAIL_WIRE_FIELDS} == SV.trail_projection(F._current()[F.H1])   # the four-field view is unchanged inside it
    assert w["knowledge_support_count"] == 1                                                   # STATED: the ledger's knowledge_support, counted
    assert w["candidate_activity"] == "landscape photography" and w["candidate_task"] == "reach spare batteries and filters"
    assert w["candidate_context"] == "on the trail, in cold or wet weather"
    assert w["candidate_predicates"] == ["access", "carry"]                                     # the run's shared predicates, identifiers only
    assert w["candidate_friction_families"] == [FAMILY]                                         # "buried accessories" IS a returned family id
    assert "candidate_product_territories" not in w                                             # empty lists are absent: Trail's lexical path decides


def test_a_friction_family_is_never_guessed_from_prose():
    w = SV.trail_wire(_views()[F.H1], friction_family_ids=["some_other_family"])
    assert "candidate_friction_families" not in w
    w2 = SV.trail_wire(_views()[F.H2])                          # H2 has no suspected_friction and no registry families at all
    assert "candidate_friction_families" not in w2 and w2["knowledge_support_count"] == 1 and "candidate_task" in w2


def test_scope_carries_the_wire_beside_the_other_projections_and_by_id_stays_full():
    s = SV.scope(F._view(), friction_family_ids=[FAMILY])
    assert [w["hypothesis_id"] for w in s["trail"]] == [h["hypothesis"]["hypothesis_id"] for h in s["hypotheses"]]
    assert s["trail"][0]["candidate_friction_families"] == [FAMILY] and "candidate_activity" not in json.dumps(s["hypotheses"][0])
    assert "knowledge" in s["by_id"][F.H1]


def test_the_wire_is_deterministic_and_never_mutates_the_view():
    v = _views()[F.H1]
    before = json.dumps(v, sort_keys=True)
    a, b = SV.trail_wire(v, friction_family_ids=[FAMILY]), SV.trail_wire(v, friction_family_ids=[FAMILY])
    assert a == b and json.dumps(v, sort_keys=True) == before


def test_every_trail_step_of_the_production_manifest_opts_in():
    trail_steps = [s for s in MANIFEST["steps"] if s["type"] == "EXTERNAL_OPERATION"]
    assert trail_steps and all(s["config"].get("hypotheses_from") == "context.semantics.trail" for s in trail_steps)
    assert MANIFEST["adapter_version"] == "0.6.0"


# ─────────────────────────────────────────────────────────── the receipt relation, submit-time half
def _receipt(relations):
    obs = {"observation_id": "obs_1", "source_id": "src_1", "claim": "the shot was missed while digging for a battery", "paraphrase_or_excerpt": "…",
           "metric_if_present": None, "context": "forum thread, lone landscape photographer", "evidence_role_claimed": "behavior", "hypothesis_ids": [F.H1]}
    if relations is not None:
        obs["hypothesis_relations"] = relations
    return {"action_id": ACTION, "run_id": F.RUN, "harness_id": "fixture.harness", "started_at": "2026-09-21T12:00:00Z", "completed_at": "2026-09-21T12:00:05Z",
            "sources": [{"source_id": "src_1", "url": "https://example.invalid/t/1", "source_class": "forum", "retrieved_at": "2026-09-21T12:00:01Z", "published_at_if_known": None}],
            "observations": [obs], "tool_trace": [], "limitations": []}


ACTION = "hact_" + "c" * 16
STEP = {"run_id": F.RUN, "step_id": "F_receipt", "sequence": 3, "harness_action": {"action_id": ACTION}}


def _relation_errors(payload):
    return [e for e in T.validate_receipt(STEP, payload) if "relation" in e]


def test_a_relation_to_a_linked_hypothesis_is_admitted_and_an_unlinked_one_is_refused():
    assert _relation_errors(_receipt([{"hypothesis_id": F.H1, "relation": "CONTRADICTS"}])) == []
    assert _relation_errors(_receipt(None)) == []                                                # absent = Trail's global polarity rule, as before
    errors = _relation_errors(_receipt([{"hypothesis_id": F.H1, "relation": "SUPPORTS"}, {"hypothesis_id": F.H2, "relation": "CONTRADICTS"}]))
    assert len(errors) == 1 and "obs_1" in errors[0] and F.H2 in errors[0] and F.H1 not in errors[0].split(":")[-1]


@pytest.mark.parametrize("bad", [{"hypothesis_id": F.H1, "relation": "MAYBE"}, {"hypothesis_id": F.H1}, {"relation": "SUPPORTS"}])
def test_the_schema_refuses_a_malformed_relation(bad):
    assert any(e.startswith("payload:") for e in T.validate_receipt(STEP, _receipt([bad])))


def test_the_four_copies_of_the_receipt_contract_agree():
    contract = (ROOT / "contracts" / "adapter" / "v1" / "harness_receipt.schema.json").read_bytes()
    assert contract == (ROOT / "adapters" / "ecommerce" / "schemas" / "harness_receipt.schema.json").read_bytes()
    obs = json.loads(contract)["properties"]["observations"]["items"]["properties"]
    adm = json.loads((ROOT / "contracts" / "adapter" / "v1" / "evidence_admission.schema.json").read_text())["properties"]["admitted"]["items"]["properties"]
    assert obs["hypothesis_relations"]["items"] == adm["hypothesis_relations"]["items"]
    assert obs["hypothesis_relations"]["items"]["properties"]["relation"]["enum"] == ["SUPPORTS", "CONTRADICTS", "NEUTRAL"]
