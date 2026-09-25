"""AUTORESEARCH-SOURCES-AND-HARNESS-V1 (register 11.489): the governed research directives are HARNESS-NEUTRAL (a plain search
string plus where to look and what to read — never a host tool command, ADR-063), short-video comment channels get research slots
under the budget (gap S-02), and CJ Dropshipping sits alongside Alibaba with TrailSignal's supply templates bound per concept
(gap S-06). Every domain operation runs through the REAL worker → binding subprocess path (the products / supply tests' `_exec`).
"""
from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402

#: fragments of the host tool chains the standalone engine keeps (`executors._CHANNEL_TEMPLATES`, `_SOURCING_TOOLS`)
TOOL_TOKENS = ("opencli", "mcporter", "python3", "curl ", "exa.", "numresults", "-f json", "camoufox", "--json", "sourcing_exa")
H = ["hyp_" + c * 12 for c in "1234"]


def _exec(operation: str, inputs: dict) -> dict:
    raw = {"adapter_id": "fixture.one_op", "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0", "input_schema_version": "1.0.0",
           "output_schema_version": "1.0.0", "description": "one domain operation", "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
           "budgets": {"max_steps": 4, "max_agent_reason": 0, "max_branch_loops": 0}, "entry_step_id": "op", "terminal_step_id": "end",
           "steps": [{"step_id": "op", "type": "DOMAIN_OPERATION", "title": "op", "next": "end",
                      "config": {"domain": "ecommerce", "operation": operation, "inputs": {k: f"outputs.given.{k}" for k in inputs}}},
                     {"step_id": "end", "type": "COMPILE_RESULT", "title": "end", "next": None, "config": {"include": ["lineage"]}}]}
    assert C.validate("adapter_manifest", raw) == [] and M.graph_integrity_errors(raw) == []
    m = M.Manifest(adapter_id=raw["adapter_id"], adapter_version="1.0.0", workflow_version="1.0.0", retrieval_policy_version="1.0.0", input_schema_version="1.0.0",
                   output_schema_version="1.0.0", entry_step_id="op", terminal_step_id="end", budgets=raw["budgets"], steps={s["step_id"]: s for s in raw["steps"]}, raw=raw)
    state = RunState(run_id="adr_" + "7" * 32, adapter_id=raw["adapter_id"], status="running", input={}, outputs={"given": inputs})
    out = W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)
    assert "output" in out, out
    return out["output"]


def _no_tool_command(intent: dict) -> None:
    text = f"{intent.get('template') or ''} {intent.get('intent') or ''}".lower()
    assert not any(t in text for t in TOOL_TOKENS), f"{intent['intent_id']} names a host tool: {text[:200]}"
    assert "{" not in (intent.get("template") or ""), f"{intent['intent_id']} still carries a slot"


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── field research: neutral intents, every channel and every subject
FIELD_DIRECTIVE = {
    "objective": "find first-person field evidence", "geography": "US", "language": "en",
    "evidence_gaps": [{"gap_id": f"gap_{k}", "hypothesis_id": H[k], "question": q, "evidence_role": "friction"} for k, q in enumerate((
        "do runners complain that keys bounce out of pockets mid stride", "do hikers lose their phone when climbing over rocks",
        "do cyclists drop snacks when reaching into a jersey pocket", "do dog walkers juggle bags leashes and keys in the rain"))],
    "search_intents": [{"intent_id": "q-complaint", "intent": "Find direct complaint language", "evidence_goal": "complaint", "evidence_roles": ["friction", "behavior"], "template": None},
                       {"intent_id": "q-workaround", "intent": "Find workaround discussions", "evidence_goal": "workaround", "evidence_roles": ["workaround"], "template": None}],
    "preferred_source_roles": ["community_discussion"], "disallowed_source_roles": ["supplier_listing"], "minimum_independent_sources": 3,
    "freshness_requirement": {"max_age_days": 14, "policy_ref": "strictest-routed-source"}, "budget": {"max_queries": 12, "max_sources": 20, "max_observations": 80},
    "success_condition": "10 independent complaints", "falsification_condition": "no recurring complaints"}


def test_field_research_intents_are_plain_queries_and_every_channel_and_every_gap_gets_a_slot():
    out = _exec("research.plan", {"research_directive": FIELD_DIRECTIVE,
                                  "hypotheses": [{"hypothesis_id": h, "revision": 0, "status": "proposed", "statement": g["question"]}
                                                 for h, g in zip(H, FIELD_DIRECTIVE["evidence_gaps"])]})
    intents = out["research_directive"]["search_intents"]
    assert intents[:2] == FIELD_DIRECTIVE["search_intents"] and out["governance_unchanged"] is True        # Trail's WHAT first, untouched
    added = intents[2:]
    assert len(intents) == 12 and out["planned"]["dropped_over_budget"] > 0                               # the budget binds ...
    channels = {i["intent_id"].split(":")[-2] for i in added}
    assert {"reddit", "amazon_reviews", "youtube", "tiktok", "instagram", "xiaohongshu", "twitter", "forum"} <= channels   # ... yet no channel starves (S-02)
    assert {i["intent_id"].split(":")[-1] for i in added} == {"gap_0", "gap_1", "gap_2", "gap_3"}          # ... and no gap does either
    for i in added:
        _no_tool_command(i)
        assert i["template"] and i["template"] in i["intent"]                                               # the plain search string, stated in the intent
    by_channel = {i["intent_id"].split(":")[-2]: i for i in added}
    assert "(tiktok.com)" in by_channel["tiktok"]["intent"] and "comment threads" in by_channel["tiktok"]["intent"]
    assert "tiktok.com/@creator/video/" in by_channel["tiktok"]["intent"]                                   # the canonical link Trail routes to comments
    assert "(instagram.com)" in by_channel["instagram"]["intent"] and "instagram.com/reel/" in by_channel["instagram"]["intent"]
    assert "comment threads" in by_channel["youtube"]["intent"]


# ─────────────────────────────────────────────────────────── supply: Trail's templates bound per concept, CJ alongside Alibaba
H1, H2 = "hyp_" + "a" * 12, "hyp_" + "b" * 12
LIVE = [{"hypothesis_id": H1, "revision": 2, "status": "strengthened", "statement": "pockets bounce"},
        {"hypothesis_id": H2, "revision": 1, "status": "weakened", "statement": "gloves block zips"}]
MECHS = [{"id": "m_clip", "name": "glove-operable magnetic clip", "hypothesis_id": H1}, {"id": "m_zip", "name": "oversized zip pull", "hypothesis_id": H2}]


def _concept(i, form, mech="m_clip"):
    return {"id": f"pc_{i}", "mechanism_id": mech, "name": f"stride {form}", "form_factor": form, "target_moment": "DURING",
            "variations": [{"name": "standard"}], "evidence_refs": ["fev_0001"]}


CONCEPTS = [_concept(1, "magnetic belt clip"), _concept(2, "wrist pouch"), _concept(3, "shoe-lace key holder")]
#: the shape TrailSignal's supply directive has: one slot-free intent, and stage templates with `{product_territory}` (gap_compiler)
SUPPLY_DIRECTIVE = {"objective": "find supply feasibility", "evidence_gaps": [], "geography": None, "language": "en",
                    "search_intents": [{"intent_id": "si_supply", "intent": "find supplier MOQ and unit economics", "evidence_goal": "supply", "evidence_roles": ["supply", "price"]},
                                       {"intent_id": "si_moq", "intent": "supplier MOQ", "evidence_goal": "supply", "evidence_roles": ["supply", "price"],
                                        "template": "{product_territory} supplier moq"},
                                       {"intent_id": "si_lead", "intent": "lead time", "evidence_goal": "operations", "evidence_roles": ["operations"],
                                        "template": "{product_territory} lead time"}],
                    "success_condition": "2 suppliers with price and MOQ", "falsification_condition": "no supplier under the target landed cost", "budget": {"max_queries": 24}}


def test_supply_binds_trails_templates_per_concept_and_cj_sits_alongside_alibaba_as_plain_queries():
    out = _exec("supply.plan", {"product_concepts": CONCEPTS, "mechanisms": MECHS, "live_hypotheses": LIVE, "research_directive": SUPPLY_DIRECTIVE})
    intents = out["research_directive"]["search_intents"]
    assert intents[0] == SUPPLY_DIRECTIVE["search_intents"][0] and out["governance_unchanged"] is True    # the slot-free intent, untouched
    assert not [i for i in intents if i["intent_id"] in ("si_moq", "si_lead")]                            # never sent with a `{slot}` (S-06)
    bound = [i for i in intents if i["intent_id"].startswith(("si_moq:", "si_lead:"))]
    assert {i["intent_id"].split(":")[1] for i in bound} == {"pc_1", "pc_2", "pc_3"} and out["planned"]["trail_templates_bound"] == 6
    assert all(i["template"].endswith((" supplier moq", " lead time")) and not i["template"].startswith(" ") for i in bound)
    assert all(f"concept: {i['intent_id'].split(':')[1]}" in i["intent"] for i in bound)
    sourcing = [i for i in intents if i["intent_id"].count(":") == 2]
    assert {i["intent_id"].split(":")[1] for i in sourcing} == {"alibaba", "cjdropshipping"}
    assert {i["intent_id"].split(":")[2] for i in sourcing} == {"pc_1", "pc_2", "pc_3"}                    # both channels, every concept
    cj = next(i for i in sourcing if ":cjdropshipping:" in i["intent_id"])
    assert "(cjdropshipping.com)" in cj["intent"] and all(t in cj["intent"] for t in ("listing:", "supplier:", "price as listed:", "MOQ as listed:", "concept:"))
    for i in intents:
        _no_tool_command(i)
    assert all("tools" not in j and j["where"] in ("alibaba.com", "cjdropshipping.com") for j in out["sourcing_plan"])   # the materials too


def _supply_world(rows):
    sources = [{"source_id": f"s{i}", "url": url, "source_class": "supplier_listing", "retrieved_at": "2026-09-20T10:00:00Z", "published_at_if_known": None} for i, (url, _) in enumerate(rows)]
    obs = [{"observation_id": f"o{i}", "source_id": f"s{i}", "claim": "listing", "paraphrase_or_excerpt": "listing", "metric_if_present": None, "context": ctx,
            "evidence_role_claimed": "supply", "hypothesis_ids": [H1]} for i, (_, ctx) in enumerate(rows)]
    admitted = [{"admitted_evidence_id": f"fev_s{i}", "observation_id": f"o{i}", "evidence_role": "supply", "freshness": "fresh", "independence_group": f"g{i}",
                 "polarity": "supporting", "hypothesis_ids": [H1]} for i in range(len(rows))]
    return {"receipts": [{"sources": sources, "observations": obs}], "admissions": [{"admission_id": "hadm_s", "admitted": admitted}],
            "product_concepts": CONCEPTS, "mechanisms": MECHS, "live_hypotheses": LIVE}


def test_an_unresolved_supplier_with_a_channel_note_is_not_a_name():
    rows = [("https://cjdropshipping.com/product/x.html", "listing: running wrist pouch · supplier: unresolved (cjdropshipping listing) · price as listed: $4.35 · MOQ as listed: 1 · concept: pc_2"),
            ("https://www.alibaba.com/product-detail/y.html", "listing: magnetic belt clip · supplier: Shenzhen Example Co · price as listed: US$1.20 · MOQ as listed: 500 pieces · concept: pc_1")]
    out = _exec("supply.leads", _supply_world(rows))
    by = {c["id"]: c for c in out["supplier_candidates"]}
    assert by["fev_s0"]["supplier_name"] is None and by["fev_s1"]["supplier_name"] == "Shenzhen Example Co"
    assert out["joined"]["without_supplier_name"] == 1


# ─────────────────────────────────────────────────────────── manifests ask only for source classes Trail can route
def test_every_source_class_a_manifest_names_exists_in_the_pinned_trail_registry():
    rows = list(csv.DictReader((ROOT / "governance/trail/data/source_capabilities.csv").open(newline="", encoding="utf-8")))
    known = {r["source_class"] for r in rows}
    for m in M.list_manifests(M.ADAPTER_DIR):
        for sid, spec in m.steps.items():
            harness = spec.get("harness") or {}
            for key in ("preferred_source_roles", "disallowed_source_roles"):
                unknown = set(harness.get(key) or []) - known
                assert not unknown, f"{m.adapter_id}:{sid}.{key} names classes Trail does not route: {sorted(unknown)} (gap S-07)"


# ─────────────────────────────────────────────────────────── short-video comments: harvest → receipt → TrailSignal admission
def test_comments_under_one_video_keep_their_own_dates_through_trail_admission():
    """The Hermes skill's receipt builder lists the VIDEO (its canonical link) as the source and gives each comment its own row by
    publish date; the pinned TrailSignal core routes those rows to its comment sources (ADR-070) and anchors each comment's
    freshness on THAT comment's date. One platform = one independence group."""
    from datetime import datetime, timezone
    sys.path.insert(0, str(ROOT / "adapters" / "ecommerce" / "python"))
    sys.path.insert(0, str(ROOT / "governance" / "trail"))
    import adapter_receipt as AR
    import embedded as E
    for mod in (AR, E):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    snap = E.compile_registry_snapshot(E.ROOT / "data", E.ROOT / "config", E.ROOT / "data" / "source_capabilities.csv", compiled_at=now)
    hyp, run = "hyp_" + "ab" * 12, "adr_" + "c0" * 16
    action = {"action_id": "hact_c0ffee000001", "run_id": run, "hypothesis_ids": [hyp], "budget": {"max_queries": 10, "max_sources": 4, "max_observations": 10},
              "search_intents": [{"intent_id": "si_comments", "intent": "tiktok (tiktok.com): comment threads — ankle weights"}]}
    video, reel = "https://www.tiktok.com/@creator/video/7400000000000000001", "https://www.instagram.com/reel/C0ABCDEFGHI/"

    def comment(i, url, published, role, platform):
        return {"id": f"c{i}", "source": url, "quote_ref": f"verbatim comment {i}", "problem": f"comment claim {i}", "evidence_roles": [role],
                "retrieved_at": "2026-09-25T11:00:00Z", "published_at_if_known": published, "hypothesis_ids": [hyp],
                "source_identity": {"source_family": "community", "platform": platform}}
    receipt, report = AR.build_receipt(action, observations=[comment(1, video, "2026-09-02T10:00:00Z", "FRICTION_EVIDENCE", "tiktok"),
                                                             comment(2, video, "2026-09-20T08:30:00Z", "WORKAROUND_EVIDENCE", "tiktok"),
                                                             comment(3, reel, "2026-09-12T12:00:00Z", "FRICTION_EVIDENCE", "instagram")],
                                       harness_id="claude-code", started_at="2026-09-25T10:50:00Z", completed_at="2026-09-25T11:10:00Z",
                                       tool_trace=[{"search_intent_id": "si_comments", "tool_class": "browser", "query_count": 2}])
    assert report["errors"] == [] and len(receipt["sources"]) == 3 and {s["url"] for s in receipt["sources"]} == {video, reel}
    ident = "adr-" + "c0" * 16
    request = {"idempotency_key": f"idempotency:{ident}:admit:1", "operation_kind": "evidence.admit", "purpose_ref": "purpose:product-discovery",
               "registry_snapshot_id": snap.snapshot_id, "request_id": f"request:{ident}:admit:1", "run_ref": f"run:{ident}",
               "payload": {"action_id": action["action_id"], "admitted_evidence_ids": [], "stage": "field_evidence", "receipt": receipt,
                           "hypotheses": [{"hypothesis_id": hyp, "revision": 0, "statement": "Walkers wearing ankle weights get chafed skin", "status": "proposed"}]}}
    out = E.operate(E.build_service(clock=lambda: now), "evidence.admit", request)["result"]["evidence_admission"]
    assert out["rejected"] == [], out["rejected"]
    by = {a["observation_id"]: a for a in out["admitted"]}
    assert [by[k]["anchored_at"] for k in ("c1", "c2", "c3")] == ["2026-09-02T10:00:00Z", "2026-09-20T08:30:00Z", "2026-09-12T12:00:00Z"]
    assert {a["source_class"] for a in by.values()} == {"video_platform"} and [by[k]["evidence_role"] for k in ("c1", "c2", "c3")] == ["friction", "workaround", "friction"]
    assert by["c1"]["independence_group"] == by["c2"]["independence_group"] == "tiktok" and by["c3"]["independence_group"] == "instagram"
