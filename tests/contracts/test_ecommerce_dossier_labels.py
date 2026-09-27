"""TRAIL-EXT-BUGHUNT-V1 batch C (B-36 / B-37 / B-39 / B-40) — the dossier (`adapters/ecommerce/python/report.py`) labels what it shows
by what the record says: a hop is evidence-backed only BEFORE the boundary the bridge names, a substitute is shown under every
sibling it counts for, a supplier is who the listing names, and a field quote is labelled by the community that spoke, with the
records that contradict a hypothesis marked and never crowded out.

Each test builds a SYNTHETIC journal (or a standalone state) and builds + renders the ReportModel OUT OF PROCESS through the engine's
own `report` module (its flat module names never enter this interpreter). No database, no network; every text is invented.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "adapters" / "ecommerce"
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import semantic_view as SV

H1, H2 = "hyp_" + "a" * 12, "hyp_" + "b" * 12
HOPS = re.compile(r"<li[^>]*>([^<]*)<span class='tag'>([^<]*)</span></li>")


def _engine(code: str, payload: dict, tmp_path: pathlib.Path) -> dict:
    jpath = tmp_path / "input.json"
    jpath.write_text(json.dumps(payload))
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "OPPORTUNITY_RESEARCH_DB": str(tmp_path / "loop.sqlite3")}
    proc = subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, 'python'); import models, report; " + code, str(jpath)],
                          cwd=ENGINE, env=env, capture_output=True, text=True, check=False, timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


def _dossier(journal: dict, tmp_path: pathlib.Path) -> tuple[dict, str]:
    out = _engine("m = report.build_model_from_governed(json.load(open(sys.argv[1]))); print(json.dumps({'model': m, 'html': report.render(m)}))", journal, tmp_path)
    return out["model"], out["html"]


def _journal(output: dict, *, adapter_id: str = "ecommerce.product_research", events: tuple = ()) -> dict:
    result = {"run_id": "adr_" + "8" * 32, "status": "completed", "gap": None, "output": output, "lineage": {}, "unknowns": [], "contradictions": []}
    return {"run_id": "adr_" + "8" * 32, "adapter_id": adapter_id, "adapter_version": "0.7.0", "created_at": "2026-09-26T10:00:00Z",
            "input": {"seed": "synthetic seed: runners lose keys mid stride"}, "agent_identity": "test-agent", "harness_id": "test-harness",
            "events": [*events, {"seq": len(events) + 1, "kind": "result", "data": {"result": result}}], "built_at": "2026-09-26T12:00:00Z"}


def _receipt(action_id: str, observations: list[dict], sources: list[dict]) -> dict:
    return {"seq": 1, "kind": "submission", "data": {"step_id": "I_research", "kind": "receipt", "accepted": True,
                                                     "payload": {"action_id": action_id, "observations": observations, "sources": sources, "tool_trace": []}}}


def _view(hid: str) -> dict:
    state = {"hypothesis_id": hid, "revision": 1, "status": "revised", "statement": f"synthetic statement for {hid}", "knowledge_support": [], "knowledge_gaps": []}
    return SV.build({hid: state}, {}, step_outputs=[])["hypotheses"][0]


# ─────────────────────────────────────────────────────────── B-36: a hop is evidence-backed only BEFORE the boundary the bridge names
def _transduction_hops(boundary: str, tmp_path) -> list[tuple[str, str]]:
    bridge = {"hypothesis_id": H1, "source": "a synthetic passage", "path": ["A hop", "B hop", "C hop", "D hop"], "target_mechanism": "pocket anchor",
              "evidence_boundary": {"first_inference_at": boundary}, "status": "WORKING_HYPOTHESIS", "grounding": "CORPUS_ONLY"}
    _, html = _dossier(_journal({"bridges": [bridge], "hypothesis_semantics": [_view(H1)]}), tmp_path)
    return HOPS.findall(html)


def test_the_transduction_tags_hops_from_the_boundary_on_as_inferred_whatever_whitespace_it_carries(tmp_path):
    expected = [("A hop", "evidence-backed"), ("B hop", "evidence-backed"), ("C hop", "inferred"), ("D hop", "inferred")]
    assert _transduction_hops("C hop", tmp_path) == expected
    assert _transduction_hops("C hop\n", tmp_path) == expected                    # the bridge law strips the boundary; so does the dossier
    assert _transduction_hops(" C hop ", tmp_path) == expected


def test_a_boundary_that_names_no_hop_claims_no_hop_as_evidence_backed(tmp_path):
    assert _transduction_hops("a hop nobody wrote", tmp_path) == [(h, "inferred") for h in ("A hop", "B hop", "C hop", "D hop")]


def test_the_standalone_reasoning_bridge_reads_the_boundary_the_same_way(tmp_path):
    state_code = ("st = models.new_state('probe'); st['data']['hypotheses'] = [{'id': 'h1', 'status': 'SUPPORTED', 'target_mechanism': 'pocket_anchor', "
                  "'path': ['a_hop', 'b_hop', 'c_hop', 'd_hop'], 'evidence_boundary': {'first_inference_at': json.load(open(sys.argv[1]))['boundary']}}]; "
                  "print(json.dumps({'html': report.render(report.build_model(st))}))")
    html = _engine(state_code, {"boundary": "c_hop\n"}, tmp_path)["html"]
    assert HOPS.findall(html) == [("a hop", "evidence-backed"), ("b hop", "evidence-backed"), ("c hop", "inferred"), ("d hop", "inferred")]


# ─────────────────────────────────────────────────────────── B-37: a substitute is listed under every sibling concept it counts for
def test_a_substitute_is_shown_under_every_sibling_concept_it_contests(tmp_path):
    product = {"id": "fev_o1", "concept_id": "pc_1", "applies_to_concepts": ["pc_1", "pc_2"], "variation_id": None, "hypothesis_id": H1, "relation": "solves",
               "contests_concept": True, "product_name": "SYNTHETIC-CHEST-HARNESS", "price_raw": "$19.99", "url": "https://www.example.com/p/1", "claim": "already does it"}
    reality = [{"concept_id": c, "concept": f"concept {c}", "mechanism_id": "m_strap", "hypothesis_id": H1, "jobs_planned": 2, "existing_products": 1,
                "by_relation": {"solves": 1}, "contested_by": ["fev_o1"], "status": "EXISTING_PRODUCT_CONTESTS"} for c in ("pc_1", "pc_2")]
    _, html = _dossier(_journal({"concept_reality": reality, "existing_products": [product], "reality_plan": [{}, {}, {}]}), tmp_path)
    cards = {c: html[html.index(f"GENERATED CONCEPT {c}"):] for c in ("pc_1", "pc_2")}
    assert "SYNTHETIC-CHEST-HARNESS" in cards["pc_1"][:cards["pc_1"].index("GENERATED CONCEPT pc_2")]
    assert "SYNTHETIC-CHEST-HARNESS" in cards["pc_2"] and html.count("SYNTHETIC-CHEST-HARNESS") == 2


# ─────────────────────────────────────────────────────────── B-39: the supplier is who the listing names, never the platform
def test_the_legacy_dossier_names_the_listing_s_supplier_and_the_platform_only_as_channel(tmp_path):
    observations = [{"observation_id": "s1", "source_id": "src_1", "claim": "Foldable pocket clip, 2.8 USD per piece at 500 pieces",
                     "paraphrase_or_excerpt": "US$2.80 / piece", "metric_if_present": {"name": "unit_price_low", "value": 2.8, "unit": "USD"},
                     "context": "listing: Foldable pocket clip · supplier: None · price as listed: US$2.80 · MOQ as listed: 500 pieces"},
                    {"observation_id": "s2", "source_id": "src_2", "claim": "Zip key pouch listed by a named factory", "paraphrase_or_excerpt": "3.20 USD",
                     "metric_if_present": {"name": "unit_price", "value": 3.2, "unit": "USD"},
                     "context": "listing: Zip key pouch · supplier: Synthetic Hardware Factory Co. · price as listed: 3.20 USD"}]
    sources = [{"source_id": f"src_{i}", "url": f"https://www.alibaba.com/product-detail/synthetic_{i}.html", "source_class": "supplier_listing"} for i in (1, 2)]
    admitted = [{"admitted_evidence_id": f"fev_s{i}", "observation_id": f"s{i}", "source_id": f"src_{i}", "evidence_role": "price", "source_class": "supplier_listing",
                 "independence_group": "alibaba", "polarity": "supporting", "hypothesis_ids": [H1], "stage_relevance": "supply"} for i in (1, 2)]
    output = {"evidence_admissions": [{"action_id": "act_supply", "admitted": admitted, "rejected": []}],
              "product_opportunity": {"product_concept": {"title": "synthetic pocket anchor", "mechanism_explanation": "anchors keys"}}}
    model, html = _dossier(_journal(output, adapter_id="trail.product_discovery", events=(_receipt("act_supply", observations, sources),)), tmp_path)
    leads = {l["url"].rsplit("/", 1)[-1]: l for l in model["leads"]}
    assert leads["synthetic_1.html"]["supplier_name"] == "" and leads["synthetic_1.html"]["channel"] == "alibaba"       # `supplier: None` names nobody
    assert leads["synthetic_2.html"]["supplier_name"] == "Synthetic Hardware Factory Co." and leads["synthetic_2.html"]["channel"] == "alibaba"
    assert "supplier: alibaba" not in html and "supplier: not named on the listing" in html and "supplier: Synthetic Hardware Factory Co." in html
    assert leads["synthetic_1.html"]["price_usd_low"] == 2.8 and leads["synthetic_2.html"]["price_usd_low"] is None      # the declared metric name only
    assert leads["synthetic_2.html"]["listing_metrics"] == ["unit_price 3.2 USD"] and "price not parsed · MOQ not parsed · listing metric: unit_price 3.2 USD" in html


# ─────────────────────────────────────────────────────────── B-40: field quotes by community, contradictions marked and never crowded out
def test_field_quotes_are_labelled_by_community_and_contradicting_voices_are_marked_and_kept(tmp_path):
    def obs(i: int, context: str) -> dict:
        return {"observation_id": f"o{i}", "source_id": "s_forum" if i == 25 else "s_reddit", "claim": f"synthetic claim {i}", "paraphrase_or_excerpt": f"QUOTE-{i:02d}",
                "context": context}
    def adm(i: int, *, polarity: str = "supporting", stage: str = "field_evidence", duplicate_of=None, relations=None) -> dict:
        row = {"admitted_evidence_id": f"fev_{i:03d}", "observation_id": f"o{i}", "source_id": "s_reddit", "evidence_role": "friction", "source_class": "community_discussion",
               "independence_group": "reddit", "polarity": polarity, "hypothesis_ids": [H1], "stage_relevance": stage, "duplicate_of": duplicate_of}
        return {**row, "hypothesis_relations": relations} if relations else row
    observations = [obs(i, f"community: r/community{i:02d} · activity: running") for i in range(25)] + [obs(25, "activity: running")]
    rows = [adm(i) for i in range(18)]                                                                  # 18 supporting voices admitted first …
    rows += [adm(18, polarity="contradicting"), adm(19, polarity="contradicting")]                      # … then two that contradict H1
    rows += [adm(20, relations=[{"hypothesis_id": H1, "relation": "CONTRADICTS"}])]                     # globally supporting, CONTRADICTS H1 (ADR-069)
    rows += [adm(21, stage="product_reality"), adm(22, stage="supply"), adm(23, duplicate_of="fev_000"), adm(24), adm(25)]
    sources = [{"source_id": "s_reddit", "url": "https://www.reddit.com/r/running/comments/t1/"}, {"source_id": "s_forum", "url": "https://www.example-forum.org/t/2"}]
    output = {"evidence_admissions": [{"action_id": "act_1", "admitted": rows, "rejected": []}]}
    model, html = _dossier(_journal(output, events=(_receipt("act_1", observations, sources),)), tmp_path)
    quotes = model["quotes"]
    assert len(quotes) == 14 and not {q["community"] for q in quotes} & {"reddit"}                  # never the independence group (the platform)
    assert quotes[0]["community"] == "r/community00" and all(q["community"] == f"r/community{int(q['quote'][6:]):02d}" for q in quotes)
    shown = [q["quote"] for q in quotes]
    assert {"QUOTE-18", "QUOTE-19", "QUOTE-20"} <= set(shown)                                          # admitted[:14] held none of them
    assert not {"QUOTE-21", "QUOTE-22", "QUOTE-23"} & set(shown)                                       # product reality, supply, a duplicate
    assert [q["contradicts"] for q in quotes if q["quote"] in ("QUOTE-18", "QUOTE-20")] == [[H1], [H1]]
    assert f"QUOTE-18”<span class='src'>r/community18 — https://www.reddit.com/r/running/comments/t1/ · <strong style='color:#b00'>contradicts {H1}</strong>" in html
    assert "QUOTE-00”<span class='src'>r/community00 — https://www.reddit.com/r/running/comments/t1/</span>" in html


def test_a_quote_without_a_community_tag_is_labelled_by_its_source_host(tmp_path):
    observations = [{"observation_id": "o1", "source_id": "s_forum", "claim": "synthetic claim", "paraphrase_or_excerpt": "QUOTE-HOST", "context": "activity: running"}]
    rows = [{"admitted_evidence_id": "fev_001", "observation_id": "o1", "source_id": "s_forum", "evidence_role": "friction", "source_class": "community_discussion",
             "independence_group": "forum_group", "polarity": "supporting", "hypothesis_ids": [H1], "stage_relevance": "field_evidence"}]
    sources = [{"source_id": "s_forum", "url": "https://www.example-forum.org/t/2"}]
    model, _ = _dossier(_journal({"evidence_admissions": [{"action_id": "act_1", "admitted": rows, "rejected": []}]}, events=(_receipt("act_1", observations, sources),)), tmp_path)
    assert [q["community"] for q in model["quotes"]] == ["example-forum.org"]
