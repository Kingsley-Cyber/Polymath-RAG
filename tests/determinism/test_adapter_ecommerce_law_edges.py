"""TRAIL-EXT-BUGHUNT-V1 batch C (B-36 / B-61 / B-62 / B-37) — the edges of the ecommerce domain's laws and joins.

B-36  the bridge law reads the evidence boundary one way: a stray newline no longer skips the hop-ref check, and a boundary that
      names no hop fails that check closed.
B-61  a FIELD_ANCHORED situation cites the records of ITS ANCHOR cluster — never a record of another (THIN) cluster, nor a
      contradicting one.
B-62  a record TrailSignal marks `duplicate_of` does not count toward a cluster's records, threads or voices.
B-37  what the ONE substitute job of a hypothesis finds counts for every sibling concept the job was planned for.
And the other batch-C helper's notes on these files: B-31 (the lineage law itself names a word written as an object — the
standalone controller calls it too), B-55 (the lived world reads words in any script; a lead with no keyword never searches for
nothing), B-34 (the reality join reads an annotated or re-cased concept tag as the concept it names).

One operation at a time through the REAL executor (`exec_domain`, the binding out of process), or the engine's own module out of
process. No database, no network. Text is synthetic.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import workers.adapter_step_worker as W
from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import manifest as M
from polymath_shared.adapter.transitions import RunState

H1, H2, H3 = "hyp_" + "a" * 12, "hyp_" + "b" * 12, "hyp_" + "c" * 12


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


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── B-36: C_bridge_law (hypotheses.validate_bridge)
ROWS = [{"id": f"ch_{i}", "text": f"synthetic passage {i} about cold hands and small dials", "kind": "chunk"} for i in range(3)]


def _bridge(hid: str, mech: str, *, boundary: str | None = None, hop_refs: dict | None = None) -> dict:
    return {"hypothesis_id": hid, "source": "a synthetic passage", "path": ["cold hands", "dials too small", mech, "product"], "target_mechanism": mech,
            "evidence_boundary": {"first_inference_at": mech if boundary is None else boundary},
            "hop_refs": {"0": ["ch_0"], "1": ["ch_1"]} if hop_refs is None else hop_refs,
            "gaps": ["do gloved users skip settings?"], "alternatives": ["cold batteries, not dials"], "falsifiers": ["gloved users change settings easily"],
            "status": "WORKING_HYPOTHESIS"}


def _bridge_law(first: dict) -> dict:
    return _exec("hypotheses.validate_bridge", {"hypotheses": [first, _bridge(H2, "battery keeper"), _bridge(H3, "fingertip flap")], "corpus_evidence": ROWS})


def test_a_boundary_with_a_stray_newline_is_still_checked_for_hop_refs():
    clean = _bridge_law(_bridge(H1, "dial grip", hop_refs={}))
    assert clean["admissible"] is False and sum(e.startswith(H1) and "cites no corpus/observation id" in e for e in clean["bridge_errors"]) == 2
    for boundary in ("dial grip\n", " dial grip "):          # validate_bridge strips the boundary; the hop-ref law read it raw and skipped
        out = _bridge_law(_bridge(H1, "dial grip", boundary=boundary, hop_refs={}))
        assert out["admissible"] is False and out["bridge_errors"] == clean["bridge_errors"], (boundary, out["bridge_errors"])
    cited = _bridge_law(_bridge(H1, "dial grip", boundary="dial grip\n"))                         # the same boundary WITH hop refs is lawful
    assert cited["admissible"] is True and cited["bridge_errors"] == []


def test_a_boundary_that_names_no_hop_fails_the_hop_ref_check_closed():
    out = _bridge_law(_bridge(H1, "dial grip", boundary="a hop nobody wrote"))
    assert out["admissible"] is False
    assert any(e.startswith(H1) and "hop_refs cannot be checked" in e for e in out["bridge_errors"]), out["bridge_errors"]
    assert any(e.startswith(H1) and "is not a hop in path" in e for e in out["bridge_errors"])          # validate_bridge's own error stays


# ─────────────────────────────────────────────────────────── the lived world (B-61 / B-62)
HYP = H1
HYPOTHESES = [{"hypothesis_id": HYP, "statement": "runners lose small items because pockets bounce", "suspected_friction": "access_interruption"}]


def _world(n: int, *, groups: int, threads: int, other_community: tuple = ()) -> dict:
    """`n` admitted observations over `threads` sources and `groups` TrailSignal independence groups; the observations whose index is
    in `other_community` name r/hiking instead of r/running (another cluster: community × friction family)."""
    sources = [{"source_id": f"src_{t}", "url": f"https://www.reddit.com/r/running/comments/t{t}/", "source_class": "community_discussion",
                "retrieved_at": "2026-09-20T10:00:00Z", "published_at_if_known": "2026-09-10T00:00:00Z"} for t in range(threads)]
    obs = [{"observation_id": f"obs_{i}", "source_id": f"src_{i % threads}", "claim": f"keys bounce out of the pocket mid stride ({i})",
            "paraphrase_or_excerpt": f"my keys fell out again on the trail {i}", "metric_if_present": None,
            "context": f"community: {'r/hiking' if i in other_community else 'r/running'} · activity: running · moment: during",
            "evidence_role_claimed": "friction", "hypothesis_ids": [HYP]} for i in range(n)]
    admitted = [{"admitted_evidence_id": f"fev_{i:04d}", "observation_id": f"obs_{i}", "source_id": f"src_{i % threads}", "evidence_role": "friction" if i else "workaround",
                 "source_class": "community_discussion", "freshness": "fresh", "independence_group": f"grp_{i % groups}", "polarity": "supporting", "hypothesis_ids": [HYP]}
                for i in range(n)]
    return {"receipts": [{"sources": sources, "observations": obs}], "admissions": [{"admission_id": "hadm_1", "admitted": admitted, "rejected": []}], "hypotheses": HYPOTHESES}


def _situation(cluster_id: str, authority: str, *friction_refs: list) -> dict:
    return {"id": "ls_1", "cluster_id": cluster_id, "authority": authority, "participants": "trail runners", "activity": "running", "moment": "DURING",
            "frictions": [{"text": f"keys bounce out ({i})", "authority": "FIELD_OBSERVATION", "refs": refs} for i, refs in enumerate(friction_refs)],
            "unknowns": ["how often per run"]}


def _two_clusters() -> dict:
    """r/running: 5 supporting records + 1 that CONTRADICTS the hypothesis (kept out of every cluster) -> ANCHOR; r/hiking: 2 -> THIN."""
    world = _world(8, groups=3, threads=2, other_community=(6, 7))
    world["admissions"][0]["admitted"][1]["hypothesis_relations"] = [{"hypothesis_id": HYP, "relation": "CONTRADICTS"}]
    cards = _exec("population.evidence_cards", world)
    by_community = {c["community"]: c for c in cards["lived_clusters"]}
    assert by_community["running"]["authority"] == "ANCHOR" and by_community["running"]["record_ids"] == ["fev_0000", "fev_0002", "fev_0003", "fev_0004", "fev_0005"]
    assert by_community["hiking"]["authority"] == "THIN" and by_community["hiking"]["record_ids"] == ["fev_0006", "fev_0007"]
    return {**cards, "anchor": by_community["running"]["id"], "thin": by_community["hiking"]["id"]}


def _situations_law(world: dict, situation: dict) -> dict:
    return _exec("population.validate_situations", {"lived_situations": [situation], "lived_clusters": world["lived_clusters"], "field_records": world["field_records"]})


def test_a_field_anchored_situation_cites_only_the_records_of_its_own_anchor_cluster():
    world = _two_clusters()
    own = _situations_law(world, _situation(world["anchor"], "FIELD_ANCHORED", ["fev_0000", "fev_0002"]))
    assert own["valid"] is True and own["errors"] == []
    other = _situations_law(world, _situation(world["anchor"], "FIELD_ANCHORED", ["fev_0006"]))            # a record of the THIN r/hiking cluster
    assert other["valid"] is False and any("outside that cluster" in e and "fev_0006" in e for e in other["errors"]), other["errors"]
    mixed = _situations_law(world, _situation(world["anchor"], "FIELD_ANCHORED", ["fev_0000"], ["fev_0007"]))
    assert mixed["valid"] is False and any("outside that cluster" in e and "fev_0007" in e for e in mixed["errors"]), mixed["errors"]


def test_a_field_anchored_situation_never_cites_a_contradicting_record():
    world = _two_clusters()
    against = _situations_law(world, _situation(world["anchor"], "FIELD_ANCHORED", ["fev_0001"]))         # known, but it CONTRADICTS the hypothesis
    assert against["valid"] is False and any("outside that cluster" in e and "fev_0001" in e for e in against["errors"]), against["errors"]


def test_a_reconstruction_on_a_thin_cluster_may_still_cite_its_records():
    world = _two_clusters()
    out = _situations_law(world, _situation(world["thin"], "RECONSTRUCTED", ["fev_0006"]))
    assert out["valid"] is True and out["errors"] == []


def test_trailsignal_duplicates_never_count_toward_an_anchor():
    """TrailSignal marks a record `duplicate_of` when the same independence group states the same claim again; it leaves the duplicate
    out of qualification and scoring. Three records plus two such duplicates are three records: THIN, not ANCHOR."""
    world = _world(3, groups=3, threads=2)
    dupes = [{"id": f"fev_dup_{i}", "duplicate_of": f"fev_000{i}", "community": "r/running", "friction_family": "access_interruption", "evidence_roles": ["FRICTION_EVIDENCE"],
              "independence_group": f"grp_{i}", "source": f"https://www.reddit.com/r/running/comments/d{i}/", "quote_ref": f"my keys fell out again on the trail {i}",
              "source_identity": {"platform": "reddit", "thread_key": f"https://www.reddit.com/r/running/comments/d{i}/"}} for i in range(2)]
    out = _exec("population.evidence_cards", {**world, "prior_field_records": dupes, "prior_round": 1})
    cluster = out["lived_clusters"][0]
    assert cluster["record_ids"] == ["fev_0000", "fev_0001", "fev_0002"] and cluster["record_count"] == 3 and cluster["authority"] == "THIN", cluster
    assert [r["id"] for r in out["field_records"]] == ["fev_dup_0", "fev_dup_1", "fev_0000", "fev_0001", "fev_0002"]    # kept as records, never counted twice
    distinct = _exec("population.evidence_cards", {**world, "prior_field_records": [{k: v for k, v in d.items() if k != "duplicate_of"} for d in dupes], "prior_round": 1})
    assert distinct["lived_clusters"][0]["record_count"] == 5 and distinct["lived_clusters"][0]["authority"] == "ANCHOR"   # the same five, not duplicates: ANCHOR


# ─────────────────────────────────────────────────────────── B-37: Q_join (product_reality.join) — the substitute job's siblings
DIRECTIVE = {"objective": "map current products", "hypothesis_ids": [H1, H2], "evidence_gaps": [], "geography": None, "language": None,
             "search_intents": [{"intent_id": "q-review", "intent": "Find incumbent deficiencies", "evidence_goal": "competition", "evidence_roles": ["competition"],
                                 "template": "{activity} {product_territory} review problem"}],
             "preferred_source_roles": ["marketplace_listing"], "disallowed_source_roles": ["supplier_listing"], "minimum_independent_sources": 2,
             "freshness_requirement": {"max_age_days": 90}, "budget": {"max_queries": 24, "max_sources": 40, "max_observations": 80},
             "success_condition": "3 products compared", "falsification_condition": "an incumbent already removes the friction"}
MECHANISMS = [{"id": "m_strap", "name": "strap-mounted camera carry", "hypothesis_id": H1, "product_terms": ["backpack strap camera clip"]},
              {"id": "m_wrap", "name": "fast weather wrap", "hypothesis_id": H2, "product_terms": ["camera rain cover"]}]
CONCEPTS = [{"id": "pc_1", "mechanism_id": "m_strap", "name": "Universal strap mount", "form_factor": "strap clamp mount"},
            {"id": "pc_2", "mechanism_id": "m_strap", "name": "Strap sleeve holster", "form_factor": "elastic strap sleeve"},
            {"id": "pc_3", "mechanism_id": "m_wrap", "name": "One-hand rain wrap", "form_factor": "neoprene wrap"}]
LIVE = [{"hypothesis_id": H1, "revision": 2, "status": "revised", "statement": "hikers cannot reach the camera with one hand"},
        {"hypothesis_id": H2, "revision": 1, "status": "revised", "statement": "photographers stop shooting in rain"}]
SEMANTICS = [{"hypothesis_id": H1, "population": "hiking photographers", "activity": "hiking photography", "task": "get the camera ready with one hand",
              "jobs": [{"job": "access: get the camera from carried to shooting with one hand"}]},
             {"hypothesis_id": H2, "population": "landscape photographers", "activity": "landscape photography", "task": "keep shooting in rain", "jobs": []}]


def _join(context: str) -> tuple[dict, dict]:
    plan = _exec("product_reality.plan", {"research_directive": DIRECTIVE, "product_concepts": CONCEPTS, "mechanisms": MECHANISMS, "live_hypotheses": LIVE, "semantics": SEMANTICS})
    receipt = {"action_id": "hact_pr", "observations": [{"observation_id": "o1", "source_id": "s1", "claim": "A chest harness already holds the camera ready for one-hand use.",
                                                         "context": context, "paraphrase_or_excerpt": ""}],
               "sources": [{"source_id": "s1", "url": "https://www.amazon.com/s?k=camera+chest+harness", "source_class": "marketplace_listing"}]}
    admission = {"admitted": [{"admitted_evidence_id": "fev_o1", "observation_id": "o1", "evidence_role": "competition", "polarity": "supporting", "hypothesis_ids": [H1]}]}
    out = _exec("product_reality.join", {"admissions": [admission], "receipts": [receipt], "product_concepts": CONCEPTS, "mechanisms": MECHANISMS,
                                         "live_hypotheses": LIVE, "reality_plan": plan["reality_plan"]})
    return plan, out


def test_what_the_substitute_job_finds_counts_for_every_sibling_it_was_planned_for():
    plan, _ = _join("")
    sub = next(j for j in plan["reality_plan"] if j["job_class"] == "substitute" and j["hypothesis_id"] == H1)
    assert sub["concept_id"] == "pc_1" and sub["applies_to_concepts"] == ["pc_1", "pc_2"]           # ONE search for the job both concepts share
    _, out = _join(f"concept: pc_1 · relation: solves · product: camera chest harness · intent: {sub['job_id']}")
    reality = {c["concept_id"]: c for c in out["concept_reality"]}
    assert reality["pc_1"]["status"] == reality["pc_2"]["status"] == "EXISTING_PRODUCT_CONTESTS", reality
    assert reality["pc_1"]["contested_by"] == reality["pc_2"]["contested_by"] == ["fev_o1"] and reality["pc_2"]["by_relation"] == {"solves": 1}
    assert reality["pc_3"]["status"] == "NO_EXISTING_PRODUCT_JOINED" and reality["pc_3"]["contested_by"] == []    # another hypothesis: untouched
    product = out["existing_products"][0]
    assert product["concept_id"] == "pc_1" and product["applies_to_concepts"] == ["pc_1", "pc_2"] and product["job_id"] == sub["job_id"]
    assert out["joined"]["joined"] == 1                                                              # one product, counted for two concepts


def test_a_product_its_own_concept_job_found_still_contests_that_concept_only():
    plan, _ = _join("")
    direct = next(j["job_id"] for j in plan["reality_plan"] if j["job_class"] == "direct_competitor" and j["concept_id"] == "pc_1" and not j.get("variation_id"))
    for context in (f"concept: pc_1 · relation: solves · product: camera chest harness · intent: {direct}", "concept: pc_1 · relation: solves · product: camera chest harness"):
        _, out = _join(context)
        reality = {c["concept_id"]: c for c in out["concept_reality"]}
        assert reality["pc_1"]["status"] == "EXISTING_PRODUCT_CONTESTS" and reality["pc_2"]["status"] == "NO_EXISTING_PRODUCT_JOINED", (context, reality)
        assert out["existing_products"][0]["applies_to_concepts"] == ["pc_1"]


# ─────────────────────────────────────────────────────────── notes from the other batch-C helper (B-31 / B-55 / B-34, these files' half)
ENGINE = ROOT / "adapters" / "ecommerce"
LAWFUL_PRIMITIVES = {"generative_signal": True, "row_relevance": {"ch_0": "SEMANTIC_MATCH", "ch_1": "LEXICAL_MATCH"},
                     "evidence_refs": {"frictions": ["ch_0"]}, "frictions": ["access_interruption"], "shared_predicates": ["access"]}


def _engine(code: str) -> object:
    """The engine's own modules, out of process — the standalone controller's path (its flat module names never enter this interpreter)."""
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, 'python'); import graph, lived_world; " + code],
                          cwd=ENGINE, env=env, capture_output=True, text=True, check=False, timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


def test_the_lineage_law_itself_names_a_word_written_as_an_object():
    """B-31: the standalone controller's submit path calls `lived_world.validate_primitives` — the law, not the binding, names it."""
    cases = [({"frictions": [{"text": "gloves block fine dial control"}]}, "primitives.frictions[0]: expected a string"),
             ({"shared_predicates": [["access", "retain"]]}, "primitives.shared_predicates[0]: expected a string"),
             ({"communities": [{"name": "r/photography"}]}, "primitives.communities[0]: expected a string"),
             ({"frictions": "gloves block fine dial control"}, "primitives.frictions: expected a list of strings")]
    state = {"data": {"corpus_evidence": ROWS, "row_relevance": {}}}
    for change, needle in cases:
        errors = _engine(f"print(json.dumps(lived_world.validate_primitives({dict(LAWFUL_PRIMITIVES, **change)!r}, {state!r}, graph.load_policies())))")
        assert any(e.startswith(needle) for e in errors), (needle, errors)
        out = _exec("understanding.validate_primitives", {"primitives": dict(LAWFUL_PRIMITIVES, **change), "corpus_evidence": ROWS})
        assert out["valid"] is False and any(e.startswith(needle) for e in out["errors"]), (needle, out["errors"])
    lawful = _exec("understanding.validate_primitives", {"primitives": LAWFUL_PRIMITIVES, "corpus_evidence": ROWS})
    assert lawful["valid"] is True and lawful["errors"] == []


def test_the_lived_world_reads_words_in_any_script_and_ascii_exactly_as_before():
    """B-55: `_toks` (lead VOI, seed matching, corpus-question words) was `[a-z][a-z\\-]{3,}`: `fotógrafos` became `grafos` and a
    Chinese run no word at all. ASCII text is pinned to the old rule."""
    ascii_samples = ["Runners lose KEYS mid-stride", "state-of-the-art e-bike x4s mp3 don't", "access_interruption / well- --abcd a---",
                     "The community's members, users & people: 1234 abc abcd", "Cold-hands; small dials (gloved) 'quoted' tl;dr"]
    got = _engine(f"print(json.dumps([sorted(lived_world._toks(x)) for x in {ascii_samples!r}] + [sorted(lived_world._STOP)]))")
    stop = set(got.pop())
    assert got == [sorted({t for t in re.findall(r"[a-z][a-z\-]{3,}", x.lower()) if t not in stop}) for x in ascii_samples]
    assert _engine("print(json.dumps(sorted(lived_world._toks('Los fotógrafos pierden la tapa'))))") == ["fotógrafos", "pierden", "tapa"]
    assert _engine("print(json.dumps(sorted(lived_world._toks('徒步摄影师 镜头盖'))))") == ["徒步摄影师", "镜头盖"]


def test_a_corpus_question_carries_the_problem_words_whatever_their_script():
    def questions(problems: list[str], community: str) -> list[str]:
        records = [{"id": f"fr_{i}", "problem": p, "community": community, "friction_family": "unassigned", "evidence_roles": ["FRICTION_EVIDENCE"]}
                   for i, p in enumerate(problems)]
        cluster = {"id": "cl_1", "community": community, "friction_family": "unassigned", "authority": "THIN", "record_ids": [r["id"] for r in records],
                   "independent_voices": 1}
        return [q["question"] for q in _exec("knowledge.corpus_questions", {"lived_clusters": [cluster], "field_records": records})["corpus_questions"]]
    spanish = questions(["fotógrafos pierden tapa", "fotógrafos pierden tapa en el viento", "fotógrafos pierden tapa otra vez"], "fotografía de paisaje")
    # the three words tie on count; their order follows set iteration (string hashing is per process), so only the words are pinned
    assert spanish and all(re.search(r"(?<!\w)grafos", q) is None for q in spanish), spanish         # was: `fotógrafos` cut to `grafos`
    assert any({"fotógrafos", "pierden", "tapa"} <= set(q.split()) for q in spanish), spanish
    chinese = questions(["镜头盖被风吹走", "镜头盖被风吹走"], "风光摄影")
    assert chinese and any("镜头盖被风吹走" in q for q in chinese), chinese                    # was: no word, no question at all


def test_a_lead_with_no_keyword_searches_for_its_own_words_never_for_nothing():
    prim = {**LAWFUL_PRIMITIVES, "population_leads": [{"name": "VR users", "why": "named in the passage"},
                                                      {"name": "trail runners", "why": "named", "frictions": ["keys bounce"]}]}
    out = _exec("population.nominate", {"signal": "synthetic seed about headsets", "primitives": prim, "corpus_evidence": ROWS})
    leads = {l["name"]: l for l in out["population_leads"]}
    vr = {q["channel"]: q["query"] for q in leads["VR users"]["channel_queries"]}
    assert vr["reddit"] == "VR users" and vr["forum"] == "VR users forum" and all(q.startswith("VR users") for q in vr.values()), vr   # was: "" and " forum"
    runners = {q["channel"]: q["query"] for q in leads["trail runners"]["channel_queries"]}
    assert runners["reddit"] == "trail runners keys bounce" and runners["forum"] == "trail runners keys bounce forum"   # a lead with keywords: unchanged


def test_the_reality_join_reads_an_annotated_or_recased_concept_tag_as_its_concept():
    plan = _exec("product_reality.plan", {"research_directive": DIRECTIVE, "product_concepts": CONCEPTS, "mechanisms": MECHANISMS, "live_hypotheses": LIVE, "semantics": SEMANTICS})
    tags = {"o1": "concept: PC_2 · relation: competitor · product: strap holster A", "o2": "concept: pc_1 (universal strap mount) · relation: solves · product: clamp B",
            "o3": "concept: pc_9 · relation: competitor · product: C"}
    receipt = {"action_id": "hact_pr", "observations": [{"observation_id": o, "source_id": "s1", "claim": f"synthetic claim {o}", "context": ctx, "paraphrase_or_excerpt": ""}
                                                        for o, ctx in tags.items()],
               "sources": [{"source_id": "s1", "url": "https://www.amazon.com/s?k=strap", "source_class": "marketplace_listing"}]}
    admission = {"admitted": [{"admitted_evidence_id": f"fev_{o}", "observation_id": o, "evidence_role": "competition", "polarity": "supporting", "hypothesis_ids": [H1]}
                              for o in tags]}
    out = _exec("product_reality.join", {"admissions": [admission], "receipts": [receipt], "product_concepts": CONCEPTS, "mechanisms": MECHANISMS,
                                         "live_hypotheses": LIVE, "reality_plan": plan["reality_plan"]})
    assert {p["id"]: p["concept_id"] for p in out["existing_products"]} == {"fev_o1": "pc_2", "fev_o2": "pc_1"}
    assert out["unjoined"] == [{"admitted_evidence_id": "fev_o3", "reason": "UNKNOWN_CONCEPT", "claimed": "pc_9", "claim": "synthetic claim o3"}]
    assert out["joined"]["unknown_concept"] == 1 and out["joined"]["joined"] == 2
    assert {c["concept_id"]: c["status"] for c in out["concept_reality"]}["pc_1"] == "EXISTING_PRODUCT_CONTESTS"
