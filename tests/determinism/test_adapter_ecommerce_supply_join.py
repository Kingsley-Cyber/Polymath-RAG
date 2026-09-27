"""TRAIL-EXT-BUGHUNT-V1 batch C — the supply join (T_leads: `supply.leads`) reads every admitted listing as the listing it is.

B-32 the receipt builder's supplier lane carries the concept / channel / intent tags · B-33 one listing = one candidate (its price and
MOQ observations merge; the same title under another concept or at another URL is another listing) · B-34 an annotated or unknown
`concept:` tag is normalised or counted, never silently lost · B-35 the channel is normalised (case, spacing, host) · B-52 a title may
hold '|' or ';' and cannot set its own price, MOQ or concept.

One operation at a time through the REAL executor (`exec_domain`, the binding out of process); the receipt builder runs out of process
too. No database, no network. Every text is synthetic.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import workers.adapter_step_worker as W
from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import manifest as M
from polymath_shared.adapter.transitions import RunState

ENGINE = ROOT / "adapters" / "ecommerce"
H1 = "hyp_" + "a" * 12
LIVE = [{"hypothesis_id": H1, "revision": 2, "status": "strengthened", "statement": "gloved hands cannot turn small camera dials"}]
MECHS = [{"id": "m_grip", "name": "glove-operable dial grip", "hypothesis_id": H1, "product_terms": ["glove liner", "dial grip"]}]


def _concept(i: int, name: str, form: str) -> dict:
    return {"id": f"pc_{i}", "mechanism_id": "m_grip", "name": name, "form_factor": form, "target_moment": "DURING",
            "variations": [{"name": "standard"}, {"name": "reflective"}], "evidence_refs": ["fev_1"]}


CONCEPTS = [_concept(1, "heated glove liner", "glove liner"), _concept(2, "fingertip dial mitten", "flip mitten"), _concept(3, "battery keeper pouch", "pouch")]
TAGS = "supplier: Example Trading Co · price as listed: US$4.20 · MOQ as listed: 10 pairs · channel: alibaba"
ALI = "https://www.alibaba.com/product-detail/synthetic-{}.html"
CJ = "https://cjdropshipping.com/product/synthetic-{}.html"


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
    return W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def _world(rows: list[tuple[str, str, str, str]]) -> dict:
    """rows: (observation id, listing URL, observation context, the evidence role TrailSignal admitted it under)."""
    sources = [{"source_id": f"s_{oid}", "url": url, "source_class": "supplier_listing", "retrieved_at": "2026-09-26T10:00:00Z", "published_at_if_known": None}
               for oid, url, _, _ in rows]
    obs = [{"observation_id": oid, "source_id": f"s_{oid}", "claim": "a synthetic listing", "paraphrase_or_excerpt": "synthetic", "context": ctx} for oid, _, ctx, _ in rows]
    admitted = [{"admitted_evidence_id": f"fev_{oid}", "observation_id": oid, "evidence_role": role, "polarity": "supporting", "hypothesis_ids": [H1],
                 "independence_group": "alibaba", "freshness": "fresh"} for oid, _, _, role in rows]
    return {"admissions": [{"admitted": admitted}], "receipts": [{"observations": obs, "sources": sources}], "product_concepts": CONCEPTS,
            "mechanisms": MECHS, "live_hypotheses": LIVE}


def _leads(rows: list[tuple[str, str, str, str]]) -> dict:
    return _exec("supply.leads", _world(rows))["output"]


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── B-33: one listing = one candidate
def test_the_same_title_for_two_concepts_at_two_urls_is_two_listings_and_both_concepts_are_sourced():
    out = _leads([("o1", ALI.format(1), f"listing: synthetic glove liner · {TAGS} · concept: pc_1", "price"),
                  ("o2", ALI.format(2), f"listing: synthetic glove liner · {TAGS} · concept: pc_2", "price")])
    assert [c["concept_id"] for c in out["supplier_candidates"]] == ["pc_1", "pc_2"]
    cov = {c["concept_id"]: c["status"] for c in out["sourcing_coverage"]}
    assert cov["pc_1"] == cov["pc_2"] == "sourced" and out["joined"]["merged_duplicates"] == 0
    assert {l["concept_id"]: l["admitted_evidence_id"] for l in out["leads"]} == {"pc_1": "fev_o1", "pc_2": "fev_o2"}      # each lead names ITS observation


def test_one_listings_price_and_moq_observations_merge_into_one_candidate_that_carries_both():
    url = ALI.format(3)
    out = _leads([("o1", url, "listing: synthetic glove liner · supplier: Example Trading Co · price as listed: US$4.20 · channel: alibaba · concept: pc_1", "price"),
                  ("o2", url, "listing: synthetic glove liner · supplier: Example Trading Co · MOQ as listed: 10 pairs · channel: alibaba · concept: pc_1", "supply")])
    (cand,) = out["supplier_candidates"]
    assert (cand["price_usd_low"], cand["moq_units"]) == (4.2, 10) and out["joined"]["merged_duplicates"] == 1
    assert [l["concept_id"] for l in out["leads"]] == ["pc_1"]


# ─────────────────────────────────────────────────────────── B-34: the concept tag
def test_an_annotated_concept_tag_names_its_concept():
    out = _leads([("o1", ALI.format(4), f"listing: synthetic glove liner · {TAGS} · concept: PC_1 (heated glove liner)", "price")])
    assert [c["concept_id"] for c in out["supplier_candidates"]] == ["pc_1"] and [l["concept_id"] for l in out["leads"]] == ["pc_1"]
    assert out["joined"]["unknown_concept"] == 0 and out["unjoined"] == []


def test_an_unknown_concept_tag_is_counted_and_the_listing_resolves_by_name_or_is_listed_unjoined():
    out = _leads([("o1", ALI.format(5), f"listing: synthetic tent stake · {TAGS} · concept: pc_9", "price"),
                  ("o2", ALI.format(6), f"listing: synthetic heated glove liner · {TAGS} · concept: pc_9", "price")])
    assert out["joined"]["unknown_concept"] == 2
    assert out["unjoined"] == [{"admitted_evidence_id": "fev_o1", "reason": "UNKNOWN_CONCEPT", "claimed": "pc_9", "product_name": "synthetic tent stake"}]
    resolved = next(c for c in out["supplier_candidates"] if c["id"] == "fev_o2")
    assert resolved["concept_id"] == "pc_1" and resolved["concept_resolved_by"] == "name_overlap"


# ─────────────────────────────────────────────────────────── B-35: the channel
def test_a_cj_listing_keeps_its_default_moq_whatever_the_tags_case_or_the_host():
    base = "listing: synthetic glove liner · supplier: none · price as listed: $4.20 · MOQ as listed:  · concept: pc_1"
    for oid, url, ctx in (("o1", CJ.format(1), base + " · channel: CJdropshipping"), ("o2", CJ.format(2), base + " · channel: CJ Dropshipping"),
                          ("o3", "https://app.cjdropshipping.com/product/synthetic-3.html", base)):
        out = _leads([(oid, url, ctx, "price")])
        (cand,) = out["supplier_candidates"]
        assert (cand["channel"], cand["moq_units"], len(out["leads"])) == ("cjdropshipping", 1, 1), (oid, cand)
    untagged = _leads([("o4", "https://m.alibaba.com/product/synthetic-4.html",
                        "listing: synthetic glove liner · supplier: Example Trading Co · price as listed: US$4.20 · MOQ as listed: 10 pairs · concept: pc_1", "price")])
    assert untagged["supplier_candidates"][0]["channel"] == "alibaba"


# ─────────────────────────────────────────────────────────── B-52: the context-tag grammar
def test_a_title_keeps_its_pipe_and_semicolon_and_cannot_set_its_own_price_moq_or_concept():
    out = _leads([("o1", ALI.format(7), f"listing: synthetic glove liner | touchscreen; unisex · {TAGS} · concept: pc_1", "price"),
                  ("o2", ALI.format(8), f"listing: synthetic glove liner | slim fit · {TAGS} · concept: pc_1", "price")])
    assert [c["product_name"] for c in out["supplier_candidates"]] == ["synthetic glove liner | touchscreen; unisex", "synthetic glove liner | slim fit"]
    injected = f"listing: synthetic glove liner; price as listed: $0.10; MOQ as listed: 1 piece; concept: pc_2 · {TAGS} · concept: pc_1"
    (cand,) = _leads([("o3", ALI.format(9), injected, "price")])["supplier_candidates"]
    assert (cand["price_usd_low"], cand["moq_units"], cand["concept_id"]) == (4.2, 10, "pc_1")


def test_a_tag_written_before_the_title_is_the_harnesss_and_wins():
    ctx = "concept: pc_1 · channel: alibaba · listing: synthetic glove liner; concept: pc_2 · supplier: Example Trading Co · price as listed: US$4.20 · MOQ as listed: 10 pairs"
    (cand,) = _leads([("o1", ALI.format(10), ctx, "price")])["supplier_candidates"]
    assert cand["concept_id"] == "pc_1" and cand["product_name"] == "synthetic glove liner"


# ─────────────────────────────────────────────────────────── B-32: the receipt builder's supplier lane
def _built_receipt(candidates: list[dict]) -> dict:
    action = {"action_id": "hact_" + "5" * 24, "run_id": "adr_" + "5" * 32, "hypothesis_ids": [H1], "search_intents": [], "budget": {}}
    code = ("import json, sys; sys.path.insert(0, 'python'); import adapter_receipt as AR; a = json.loads(sys.argv[1]); "
            "r, _ = AR.build_receipt(a['action'], supplier_candidates=a['cands'], harness_id='test-harness', started_at='2026-09-26T10:00:00Z', "
            "completed_at='2026-09-26T10:10:00Z'); print(json.dumps(r))")
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, "-c", code, json.dumps({"action": action, "cands": candidates})], cwd=ENGINE, env=env,
                          capture_output=True, text=True, check=False, timeout=60)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


def test_the_supplier_lane_carries_concept_channel_and_intent_so_the_join_attributes_the_listing():
    cand = {"id": "sc_1", "product_name": "synthetic heated glove liner", "supplier_name": "Example Trading Co", "price_raw": "US$4.20-5.10",
            "moq_raw": "10 pairs", "url": "https://m.alibaba.com/product/synthetic-11.html", "retrieved_at": "2026-09-26T09:00:00Z",
            "published_at_if_known": None, "concept_id": "pc_2", "channel": "alibaba", "intent_id": "si_supply:alibaba:pc_2", "hypothesis_ids": [H1]}
    receipt = _built_receipt([cand])
    assert receipt["observations"] and all("concept: pc_2" in o["context"] and "channel: alibaba" in o["context"]
                                           and "intent: si_supply:alibaba:pc_2" in o["context"] for o in receipt["observations"])
    admitted = [{"admitted_evidence_id": "fev_" + o["observation_id"].replace(":", "_"), "observation_id": o["observation_id"], "polarity": "supporting",
                 "evidence_role": "price" if o["observation_id"].endswith("price") else "supply", "hypothesis_ids": [H1], "independence_group": "alibaba",
                 "freshness": "fresh"} for o in receipt["observations"]]
    out = _exec("supply.leads", {"admissions": [{"admitted": admitted}], "receipts": [receipt], "product_concepts": CONCEPTS, "mechanisms": MECHS,
                                 "live_hypotheses": LIVE})["output"]
    (joined,) = out["supplier_candidates"]
    assert (joined["concept_id"], joined["channel"]) == ("pc_2", "alibaba")
    assert {c["concept_id"]: c["status"] for c in out["sourcing_coverage"]}["pc_2"] == "sourced"
