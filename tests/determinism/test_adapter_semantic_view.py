"""Restoration Slice 1 — semantic continuity (SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE §8).

OpportunitySemanticViewV1 is a DERIVED read-only projection: §8.1 tests 1–8 · origin linkage §8.3 · revisions applied or refused
§8.4 · the later-pass readable-evidence reservation §8.5 (the run-5 shape: a targeted retrieval existed and not one of its rows was
readable) · §8.6 acceptance through the EXISTING runtime: rich state -> view -> a reasoning consumer and a domain consumer.

No database, no network: `service.store` is the in-memory double and `conn` is None. Executors here are test doubles ON PURPOSE —
under pytest in a worktree `workers` resolves to the MAIN checkout, so this file never imports it; what it proves is `shared/`."""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "tests" / "determinism"))
from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter import hypotheses as H  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter import semantic_view as SV  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "adapter_semantic_view"
ADAPTER_ID = "fixture.semantic_continuity"
RUN, NOW = "adr_" + "5" * 32, "2026-09-21T12:00:00Z"
H1, H2 = "hyp_" + "a" * 24, "hyp_" + "b" * 24


def test_the_code_under_test_is_this_checkout():
    for mod in (SV, H, EB, service, M):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── a rich, run-5-shaped state
def _ledger_state(hid, rev, **over):
    base = {"hypothesis_id": hid, "run_id": RUN, "parent_hypothesis_ids": [], "revision": rev, "status": "revised" if rev else "proposed",
            "statement": "Landscape photographers on the trail miss shots because spare batteries are buried in the pack",
            "mechanism": "consumables are stored away from the point of use", "population": "landscape photographers",
            "activity": "landscape photography", "task": "reach spare batteries and filters", "context": "on the trail, in cold or wet weather",
            "suspected_friction": "buried accessories",
            "knowledge_support": [{"chunk_id": "chunk_access", "document_id": None, "graph_fact_id": None, "retrieval_trace_id": None, "evidence_role": "analogy"}],
            "trail_priors": [], "field_evidence_ids": [], "assumptions": ["the population shoots alone"],
            "contradictions": [], "falsifiers": ["pack access is quick and never costs a shot"],
            "knowledge_gaps": [{"gap_id": "gap_h1_0", "question": "do lone photographers report missing a shot while digging for a battery?", "evidence_role": "behavior", "status": "open"}],
            "created_at": NOW, "updated_at": NOW, "lead_ids": ["lead_latent"], "latent_structure_ids": ["ls_access"]}
    return {**base, **over}


def _outputs():
    return {
        "C_primitives": {"primitives": {
            "drivers": ["a lone operator does every job a crew divides"], "workarounds": ["spares taped to the tripod leg"],
            "frictions": ["consumables live away from the point of use"], "latent_values": ["never miss the light"],
            "transferable_invariants": ["when ONE person must both operate and tend a precision tool, tending interrupts operating"],
            "shared_predicates": ["access", "carry"],
            "evidence_refs": {"drivers": ["chunk_other"], "workarounds": ["chunk_access"], "frictions": ["chunk_access"], "latent_values": ["chunk_unrelated"]}}},
        "C_lineage": {"latent_structures": [
            {"id": "ls_access", "kind": "ACCESS_PROBLEM", "text": "replenishing a consumable stored away from the point of use breaks the flow of work",
             "evidence_refs": ["chunk_access"], "possible_populations": ["landscape photographers", "anglers"],
             "applicability_outside_source": "any task where a precision tool consumes something and the operator works alone"},
            {"id": "ls_weather", "kind": "EXPOSURE", "text": "weather degrades dexterity", "evidence_refs": ["chunk_weather"], "possible_populations": ["anglers"]}]},
        "C_population": {"population_leads": [
            {"id": "lead_seed", "name": "camera assistants", "kind": "POPULATION", "source_lane": "CORPUS", "seed_population": True, "voi": 0.17},
            {"id": "lead_latent", "name": "who repeatedly experiences: a consumable stored away from the point of use", "kind": "POPULATION",
             "source_lane": "LATENT", "search_mode": "LATENT", "seed_population": False, "voi": 0.34, "latent_structure_id": "ls_access"}],
            "community_leads": []},
        "C_bridge": {"bridges": [{"hypothesis_id": H1, "source": "film-set practice", "path": ["a", "b", "c"], "target_mechanism": "point-of-use access",
                                  "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["do lone photographers stop work to reach spares?"],
                                  "alternatives": ["they carry spares in a jacket pocket"], "falsifiers": ["pocket access is quick"],
                                  "status": "WORKING_HYPOTHESIS", "grounding": "CORPUS_ONLY"}]},
        "N_jobs": {"physical_jobs": [{"hypothesis_id": H1, "job": "reach a consumable with one hand", "mechanism": "strap-mounted pouch"}]},
        "N_concepts": {"mechanisms": [{"id": "m_strap", "name": "strap-mounted quick access", "hypothesis_id": H1, "product_terms": ["backpack strap camera clip"]},
                                      {"id": "m_wrap", "name": "weather wrap", "hypothesis_id": H2, "product_terms": ["neoprene camera wrap"]}],
                       "product_concepts": [{"id": "pc_1", "mechanism_id": "m_strap", "name": "Universal-fit strap mount", "form_factor": "strap clamp", "buyer": "hikers",
                                             "variations": [{"name": "wide-jaw clamp", "twist": "adjustable jaw"}]},
                                            {"id": "pc_2", "mechanism_id": "m_strap", "name": "Battery sleeve on the strap", "form_factor": "elastic sleeve"},
                                            {"id": "pc_3", "mechanism_id": "m_wrap", "name": "Rain wrap", "form_factor": "neoprene wrap"}]},
    }


ORDER = ("C_primitives", "C_lineage", "C_population", "C_bridge", "N_jobs", "N_concepts")


def _admission_steps():
    """One observation linked to BOTH hypotheses with different meaning for each, one linked to H2 only — all loop passes are stored steps."""
    receipt = {"action_id": "hact_1", "observations": [
        {"observation_id": "obs_1", "source_id": "s1", "claim": "I dig through my pack for a battery and miss the light", "paraphrase_or_excerpt": "every dawn shoot"},
        {"observation_id": "obs_2", "source_id": "s1", "claim": "I own two strap clips and never go back", "paraphrase_or_excerpt": ""}],
        "sources": [{"source_id": "s1", "url": "https://forum.example/t/1", "source_class": "forum"}]}
    admission = {"evidence_admission": {"action_id": "hact_1", "admitted": [
        {"admitted_evidence_id": "fev_1", "observation_id": "obs_1", "source_id": "s1", "evidence_role": "friction", "polarity": "supporting", "hypothesis_ids": [H1, H2]},
        {"admitted_evidence_id": "fev_2", "observation_id": "obs_2", "source_id": "s1", "evidence_role": "behavior", "polarity": "contradicting", "hypothesis_ids": [H2]}]}}
    return [{"step_id": "I_research", "sequence": 23, "output": receipt}, {"step_id": "J_admit", "sequence": 24, "output": admission}]


def _current():
    h2 = _ledger_state(H2, 0, statement="Hikers keep the camera packed away in rain and lose the shot", mechanism=None, population="hikers",
                       suspected_friction=None, lead_ids=[], latent_structure_ids=[], knowledge_gaps=[],
                       knowledge_support=[{"chunk_id": "chunk_weather", "document_id": None, "graph_fact_id": None, "retrieval_trace_id": None, "evidence_role": "background"}])
    return {H1: _ledger_state(H1, 2, mechanism="the person who shoots is also the person who fetches"), H2: h2}


def _view():
    return SV.build(_current(), _outputs(), order=ORDER, step_outputs=_admission_steps(), run_id=RUN)


# ─────────────────────────────────────────────────────────── §8.1 tests 1–8
def test_1_latest_revision_wins():
    v = _view()["hypotheses"][0]
    assert v["hypothesis"]["revision"] == 2 and v["semantics"]["mechanism"] == "the person who shoots is also the person who fetches"


def test_2_origin_ids_remain_linked_by_id_never_by_name():
    v = _view()["hypotheses"][0]
    assert v["origin"]["lead_ids"] == ["lead_latent"] and v["origin"]["latent_structure_ids"] == ["ls_access"] and v["origin"]["unresolved_ids"] == []
    assert [l["id"] for l in v["origin"]["leads"]] == ["lead_latent"] and v["origin"]["seed_population"] is False
    declared = [s for s in v["transduction"]["latent_structures"] if s["basis"] == "DECLARED"]
    assert [s["id"] for s in declared] == ["ls_access"] and "applicability_outside_source" in declared[0]
    # a lineage claim is never inferred: H2 declared nothing, so its origin is EMPTY and said to be missing —
    # the structure that shares its evidence is offered under a different, honest basis
    h2 = _view()["hypotheses"][1]
    assert h2["origin"]["lead_ids"] == [] and h2["origin"]["leads"] == [] and "origin" in h2["missing"]
    assert [(s["id"], s["basis"]) for s in h2["transduction"]["latent_structures"]] == [("ls_weather", "SHARED_EVIDENCE")]


def test_3_rich_fields_survive():
    v = _view()["hypotheses"][0]
    s = v["semantics"]
    assert (s["population"], s["activity"], s["task"], s["context"], s["suspected_friction"]) == \
        ("landscape photographers", "landscape photography", "reach spare batteries and filters", "on the trail, in cold or wet weather", "buried accessories")
    assert s["assumptions"] == ["the population shoots alone"] and s["falsifiers"] == ["pack access is quick and never costs a shot"]
    assert v["knowledge"]["knowledge_support_count"] == 1 and v["knowledge"]["supporting_evidence_ids"] == ["chunk_access"]
    assert v["knowledge"]["knowledge_gaps"][0]["gap_id"] == "gap_h1_0"
    # primitives reach the hypothesis through SHARED CITED EVIDENCE (ids), never through word overlap
    assert set(v["transduction"]["primitives_sharing_evidence"]) == {"workarounds", "frictions"}
    assert v["transduction"]["run_level"]["transferable_invariants"][0].startswith("when ONE person")
    assert v["jobs"] == [{"job": "reach a consumable with one hand", "mechanism": "strap-mounted pouch"}]
    assert v["mechanisms"][0]["product_terms"] == ["backpack strap camera clip"]


def test_4_a_missing_bridge_is_reported_missing_never_fabricated():
    h1, h2 = _view()["hypotheses"]
    assert h1["bridge"]["target_mechanism"] == "point-of-use access" and h1["bridge"]["evidence_boundary"] == {"first_inference_at": "b"}
    assert h2["bridge"] is None and "bridge" in h2["missing"] and {"mechanism", "suspected_friction"} <= set(h2["missing"])
    assert h2["semantics"]["mechanism"] is None


def test_5_multiple_concepts_remain_separate_and_join_through_their_mechanism():
    h1, h2 = _view()["hypotheses"]
    assert [c["id"] for c in h1["concepts"]] == ["pc_1", "pc_2"] and [c["id"] for c in h2["concepts"]] == ["pc_3"]
    assert h1["concepts"][0]["variations"] == [{"name": "wide-jaw clamp", "twist": "adjustable jaw"}]


def test_6_multiple_evidence_relations_remain_separate():
    h1, h2 = _view()["hypotheses"]
    assert [(e["evidence_id"], e["polarity"]) for e in h1["field_evidence"]] == [("fev_1", "supporting")]
    assert [(e["evidence_id"], e["polarity"]) for e in h2["field_evidence"]] == [("fev_1", "supporting"), ("fev_2", "contradicting")]
    assert h1["field_evidence"][0]["text"].startswith("I dig through my pack") and h1["field_evidence"][0]["source"] == "https://forum.example/t/1"


def test_7_building_the_view_never_mutates_the_underlying_state():
    current, outputs, steps = _current(), _outputs(), _admission_steps()
    before = copy.deepcopy((current, outputs, steps))
    view = SV.build(current, outputs, order=ORDER, step_outputs=steps, run_id=RUN)
    SV.scope(view)["by_id"][H1]["semantics"]["population"] = "MUTATED"          # nor does a consumer's copy reach back
    view["hypotheses"][0]["semantics"]["assumptions"].append("MUTATED")
    assert (current, outputs, steps) == before


def test_8_identical_state_gives_an_identical_view():
    a, b = _view(), SV.build(_current(), _outputs(), order=ORDER, step_outputs=_admission_steps(), run_id=RUN)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    jsonb = lambda v: json.loads(json.dumps(v, sort_keys=True))                   # JSONB keeps neither key order nor tuples   # noqa: E731
    c = SV.build(jsonb(_current()) | {}, jsonb(_outputs()), order=list(ORDER), step_outputs=jsonb(_admission_steps()), run_id=RUN)
    assert json.dumps({**c, "hypotheses": sorted(c["hypotheses"], key=lambda v: v["hypothesis"]["hypothesis_id"])}, sort_keys=True) == \
        json.dumps({**a, "hypotheses": sorted(a["hypotheses"], key=lambda v: v["hypothesis"]["hypothesis_id"])}, sort_keys=True)


def test_the_view_is_bounded_and_absorbed_hypotheses_leave_it():
    big = _current()
    big[H1]["assumptions"] = ["x" * 5000] * 40
    big[H2]["status"] = "killed"
    v = SV.build(big, _outputs(), order=ORDER, run_id=RUN)
    assert [h["hypothesis"]["hypothesis_id"] for h in v["hypotheses"]] == [H1]
    assert len(v["hypotheses"][0]["semantics"]["assumptions"]) == SV.MAX_ITEMS and len(v["hypotheses"][0]["semantics"]["assumptions"][0]) == SV.TEXT_CHARS
    assert len(json.dumps(v)) < 20_000


def test_consumer_projections_are_distinct_and_the_trail_projection_is_closed_at_four_fields():
    v = _view()["hypotheses"][0]
    q = SV.query_projection(v)
    assert q["population"] == "landscape photographers" and q["task"] == "reach spare batteries and filters" and q["workarounds"] == ["spares taped to the tripod leg"]
    assert q["bridge_gaps"] == ["do lone photographers stop work to reach spares?"] and "concepts" not in q and "field_evidence" not in q
    pr = SV.product_reality_projection(v)
    assert [c["id"] for c in pr["concepts"]] == ["pc_1", "pc_2"] and pr["mechanisms"][0]["product_terms"] == ["backpack strap camera clip"]
    assert "trail" not in SV.agent_projection(v)
    for source in (v, v["hypothesis"], _current()[H1], {"hypothesis_id": H1, "revision": 2, "status": "revised", "statement": "s" * 9}):
        assert tuple(SV.trail_projection(source)) == SV.TRAIL_WIRE_FIELDS          # Trail's wire models are extra="forbid"


# ─────────────────────────────────────────────────────────── §8.3 origin linkage in the ledger
REFS = [{"kind": "chunk", "id": "chunk_access"}, {"kind": "chunk", "id": "chunk_weather"}, {"kind": "field_evidence", "id": "fev_1"}]
KNOWN = {"lead_ids": {"lead_seed", "lead_latent"}, "latent_structure_ids": {"ls_access", "ls_weather"}}


def _step(step_id="C_hypotheses", seq=11):
    return {"run_id": RUN, "step_id": step_id, "sequence": seq, "context": {"evidence_refs": REFS}, "harness_action": None}


def _generated():
    props = [{"statement": "photographers miss shots digging for batteries", "supporting_evidence_ids": ["chunk_access"], "lead_ids": ["lead_latent"],
              "latent_structure_ids": ["ls_access"], "knowledge_gaps": [{"question": "how often does it cost a shot?", "evidence_role": "behavior"}]},
             {"statement": "hikers keep the camera packed away in rain", "supporting_evidence_ids": ["chunk_weather"]}]
    return H.generate(RUN, _step(), props, registry_snapshot_id=None, recorded_at=NOW, known_origin_ids=KNOWN)


def test_origin_ids_are_stored_as_ids_only_and_a_state_without_them_stays_valid():
    states, _ = _generated()
    assert states[0]["lead_ids"] == ["lead_latent"] and states[0]["latent_structure_ids"] == ["ls_access"]
    assert "lead_ids" not in states[1] and "latent_structure_ids" not in states[1]           # pre-existing shape, still valid (assert_valid ran)
    assert all(isinstance(i, str) for i in states[0]["lead_ids"])                              # never a copy of the lead


def test_an_origin_id_this_run_did_not_produce_is_refused():
    with pytest.raises(H.HypothesisRejected) as exc:
        H.generate(RUN, _step(), [{"statement": "a fabricated lineage claim", "supporting_evidence_ids": ["chunk_access"], "lead_ids": ["lead_invented"]}],
                   registry_snapshot_id=None, recorded_at=NOW, known_origin_ids=KNOWN)
    assert "lead_invented" in str(exc.value) and "has not produced" in str(exc.value)


def test_a_split_child_inherits_its_parents_origin():
    states, _ = _generated()
    current = {s["hypothesis_id"]: s for s in states}
    hid = states[0]["hypothesis_id"]
    allowed = {"chunk_access": "chunk", "chunk_weather": "chunk"}
    new, _ = H.apply(RUN, _step("G_mechanisms", 20), current, [{"hypothesis_id": hid, "kind": "SPLIT", "cause_refs": [{"kind": "chunk", "id": "chunk_access"}],
                     "children": [{"statement": "a narrower child hypothesis", "supporting_evidence_ids": ["chunk_access"]}]}],
                     actor="theta", allowed_causes=allowed, recorded_at=NOW, known_origin_ids=KNOWN)
    child = next(s for s in new if s["hypothesis_id"] != hid)
    assert child["lead_ids"] == ["lead_latent"] and child["latent_structure_ids"] == ["ls_access"] and child["parent_hypothesis_ids"] == [hid]


# ─────────────────────────────────────────────────────────── §8.4 a revision is applied or refused, never dropped
def _revise(changes):
    states, _ = _generated()
    current = {s["hypothesis_id"]: s for s in states}
    hid = states[0]["hypothesis_id"]
    allowed = {"chunk_access": "chunk", "fev_1": "field_evidence", "pri_1": "trail_prior"}
    new, trs = H.apply(RUN, _step("K_revise", 31), current, [{"hypothesis_id": hid, "kind": "REVISE", "cause_refs": [{"kind": "chunk", "id": "chunk_access"}],
                       "changes": changes}], actor="theta", allowed_causes=allowed, recorded_at=NOW, known_origin_ids=KNOWN)
    return states[0], new[0], trs


def test_revise_applies_gaps_assumptions_falsifiers_and_contradictions():
    before, after, trs = _revise({"mechanism": "the shooter is also the fetcher", "assumptions": ["they shoot alone", "spares are needed mid-shoot"],
                                  "falsifiers": ["a chest pouch already solves it"],
                                  "knowledge_gaps": [{"question": "How often does it cost a shot?", "status": "researched"},
                                                     {"question": "which spares are reached for most?", "evidence_role": "behavior"}],
                                  "contradictions": [{"statement": "owners of strap clips report no problem", "evidence_ids": ["fev_1"]}]})
    assert after["revision"] == before["revision"] + 1 and after["status"] == "revised" and after["mechanism"] == "the shooter is also the fetcher"
    assert after["assumptions"] == ["they shoot alone", "spares are needed mid-shoot"] and after["falsifiers"] == ["a chest pouch already solves it"]
    gaps = after["knowledge_gaps"]
    assert len(gaps) == 2 and gaps[0]["gap_id"] == before["knowledge_gaps"][0]["gap_id"] and gaps[0]["status"] == "researched"    # identity survives the round
    assert gaps[1]["status"] == "open" and gaps[1]["gap_id"] != gaps[0]["gap_id"]
    assert after["contradictions"] == [{"statement": "owners of strap clips report no problem", "evidence_ids": ["fev_1"]}]
    assert before["knowledge_gaps"][0]["status"] == "open" and len(trs) == 1                  # the earlier revision is untouched


@pytest.mark.parametrize("changes, needle", [
    ({"mechanism": "fine", "market_size": "huge"}, "changes.market_size cannot be revised"),
    ({"status": "promoted"}, "changes.status cannot be revised"),
    ({"assumptions": "not a list"}, "changes.assumptions must be a list"),
    ({"knowledge_gaps": [{"evidence_role": "behavior"}]}, "needs a question"),
    ({"knowledge_gaps": [{"question": "q?", "status": "answered"}]}, "gap status"),
    ({"contradictions": [{"statement": "no ids"}]}, "need evidence_ids"),
    ({"contradictions": [{"statement": "a prior is not evidence", "evidence_ids": ["pri_1"]}]}, "not citable: pri_1"),
    ({"lead_ids": ["lead_invented"]}, "has not produced"),
])
def test_revise_refuses_loudly_what_it_cannot_apply(changes, needle):
    with pytest.raises(H.HypothesisRejected) as exc:
        _revise(changes)
    assert needle in "; ".join(exc.value.errors)


# ─────────────────────────────────────────────────────────── §8.5 later retrieval must be READABLE (the run-5 failure)
def _rows(prefix, n, kind="chunk"):
    return [{"id": f"{prefix}_{i:03d}", "kind": kind, "text": f"{prefix} row {i}", "ca4_grade": "DIRECT" if i < 5 else None} for i in range(n)]


def _run5_shaped_steps():
    """B pass: plan 121 rows + an empty boundary call + graph facts · F pass (hypothesis-targeted): 107 rows · K pass (loop): 9 rows."""
    return [{"step_id": "B_plan", "sequence": 2, "output": {"rows": _rows("b", 121)}},
            {"step_id": "B_retrieve", "sequence": 3, "output": {"rows": [], "surface": "evidence"}},
            {"step_id": "B_graph", "sequence": 4, "output": {"rows": [], "graph_rows": _rows("bg", 30, "graph_fact")}},
            {"step_id": "C_primitives", "sequence": 7, "output": {"primitives": {}}},
            {"step_id": "F_plan", "sequence": 17, "output": {"rows": _rows("f", 107)}},
            {"step_id": "F_retrieve", "sequence": 18, "output": {"rows": []}},
            {"step_id": "G_mechanisms", "sequence": 20, "output": {"transitions": []}},
            {"step_id": "K_retrieve", "sequence": 30, "output": {"rows": _rows("k", 9)}}]


def _refs(steps):
    return [{"kind": r["kind"], "id": r["id"]} for s in steps for key in ("rows", "graph_rows") for r in s["output"].get(key) or []]


def test_passes_are_runs_of_adjacent_knowledge_outputs_and_a_row_belongs_to_the_newest_pass_that_returned_it():
    steps = _run5_shaped_steps()
    steps[-1]["output"]["rows"].append({"id": "b_000", "kind": "chunk", "text": "returned again by the loop retrieval"})
    passes = EB.knowledge_passes(s["output"] for s in steps)
    assert passes["b_001"] == 0 and passes["bg_000"] == 0 and passes["f_000"] == 1 and passes["k_000"] == 2 and passes["b_000"] == 2


def test_run5_shape_a_later_retrieval_is_readable_inside_the_unchanged_caps():
    steps = _run5_shaped_steps()
    out = EB.hydrate(_refs(steps), steps)
    rows = out["rows"]
    assert len(rows) == EB.HYDRATE_MAX_ROWS == 60                                         # the cap did not move
    later = [r for r in rows if r.get("retrieval_pass")]
    assert later and {r["retrieval_pass"] for r in later} == {1, 2}                      # before: zero later rows, at every step of run 5
    assert sum(1 for r in later if r["id"].startswith("k_")) == 9                        # the NEWEST pass is served first
    chunk_rows = [r for r in rows if r["kind"] == "chunk"]
    assert len([r for r in chunk_rows if r.get("retrieval_pass")]) <= -(-len(chunk_rows) * 4 // 10)     # at most the reserved share
    assert [r["id"] for r in chunk_rows if not r.get("retrieval_pass")][:5] == [f"b_{i:03d}" for i in range(5)]   # graded first-pass rows keep their place
    assert out["allocation"] == {"passes": 3, "recent_share": EB.RECENT_SHARE, "later_pass_rows": len(later)}
    assert EB.hydrate(_refs(steps), steps) == out                                        # deterministic


def test_a_single_pass_run_reads_exactly_what_it_read_before():
    steps = _run5_shaped_steps()[:4]
    rows = EB.hydrate(_refs(steps), steps)["rows"]
    assert [r["id"] for r in rows if r["kind"] == "chunk"][:3] == ["b_000", "b_001", "b_002"] and not any(r.get("retrieval_pass") for r in rows)
    bucket = _rows("b", 50)
    assert EB.reserve_recent(bucket, 20, {}) == bucket[:20]


def test_admitted_field_evidence_keeps_its_floor():
    steps = _run5_shaped_steps() + _admission_steps()
    refs = [{"kind": "field_evidence", "id": "fev_1"}, {"kind": "field_evidence", "id": "fev_2"}] + _refs(_run5_shaped_steps())
    rows = EB.hydrate(refs, steps)["rows"]
    assert [r["id"] for r in rows[:2]] == ["fev_1", "fev_2"] and len(rows) == 60 and any(r.get("retrieval_pass") == 2 for r in rows)


# ─────────────────────────────────────────────────────────── §8.6 acceptance: rich state -> view -> consumers, through the runtime
@pytest.fixture
def runtime(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    service.reset_registry()
    yield store
    service.reset_registry()


def _knowledge_executor(step, state, m):
    n, prefix = (150, "first") if step["step_id"] == "first_pass" else (12, "targeted")
    rows = [{"id": f"chunk_{prefix}_{i:03d}", "kind": "chunk", "text": f"{prefix} evidence {i}", "corpus_id": "cinema"} for i in range(n)]
    return {"output": {"rows": rows}, "evidence_refs": [{"kind": "chunk", "id": r["id"], "corpus_id": "cinema"} for r in rows]}


def _drive(store):
    seen: dict[str, dict] = {}

    def domain(step, state, m):
        seen["domain_step"] = step
        return {"output": {"planned": len(((step.get("context") or {}).get("semantics") or {}).get("query") or [])}}

    executors = {"POLYMATH_RETRIEVE": _knowledge_executor, "DOMAIN_OPERATION": domain}
    rid = service.start(None, adapter_id=ADAPTER_ID, input_payload={"seed": "how a camera crew keeps equipment working"}, directory=FIXTURES)["run_id"]
    answers = {
        "abstract": lambda nxt: {"primitives": {"workarounds": ["spares taped to the tripod leg"], "transferable_invariants": ["tending interrupts operating"],
                                                "evidence_refs": {"workarounds": ["chunk_first_000"]}},
                                 "latent_structures": [{"id": "ls_access", "kind": "ACCESS_PROBLEM", "text": "a consumable stored away from the point of use",
                                                        "evidence_refs": ["chunk_first_000"], "applicability_outside_source": "any lone operator"}],
                                 "population_leads": [{"id": "lead_latent", "name": "lone operators of precision tools", "source_lane": "LATENT",
                                                       "seed_population": False, "latent_structure_id": "ls_access"}]},
        "hypothesize": lambda nxt: {"hypotheses": [{"statement": "lone photographers miss shots digging for spare batteries", "population": "landscape photographers",
                                                    "activity": "landscape photography", "task": "reach spare batteries", "context": "on the trail",
                                                    "mechanism": "spares are stored away from the point of use", "suspected_friction": "buried accessories",
                                                    "supporting_evidence_ids": ["chunk_first_000"], "lead_ids": ["lead_latent"], "latent_structure_ids": ["ls_access"],
                                                    "knowledge_gaps": [{"question": "does digging for a battery cost them a shot?", "evidence_role": "behavior"}]}]},
        "bridge": lambda nxt: {"bridges": [{"hypothesis_id": nxt["step"]["context"]["hypotheses"][0]["hypothesis_id"], "source": "film-set practice",
                                            "path": ["a", "b", "c"], "target_mechanism": "point-of-use access", "evidence_boundary": {"first_inference_at": "b"},
                                            "gaps": ["do lone photographers stop work to reach spares?"], "status": "WORKING_HYPOTHESIS"}]},
        "revise": lambda nxt: {"transitions": [{"hypothesis_id": nxt["step"]["context"]["hypotheses"][0]["hypothesis_id"], "kind": "REVISE",
                                                "cause_refs": [{"kind": "chunk", "id": "chunk_targeted_000"}],
                                                "changes": {"mechanism": "the shooter is also the fetcher",
                                                            "knowledge_gaps": [{"question": "which spares are reached for most?", "evidence_role": "behavior"}]}}]},
    }
    for _ in range(40):
        st = service.advance(None, rid, executors, max_steps=1, directory=FIXTURES)
        if st.terminal:
            return rid, st, seen
        if st.status == "awaiting_agent":
            nxt = service.next_step(None, rid, directory=FIXTURES)
            seen[nxt["step"]["step_id"]] = nxt
            service.submit(None, rid, {"step_id": nxt["step"]["step_id"], "payload": answers[nxt["step"]["step_id"]](nxt),
                                       "submitted_by": {"agent_identity": "test-agent"}}, directory=FIXTURES)
    raise AssertionError("run did not terminate")


def test_acceptance_rich_state_reaches_a_reasoning_consumer_without_collapse(runtime):
    rid, st, seen = _drive(runtime)
    assert st.status == "completed"
    nxt = seen["revise"]
    # the AdapterStepV1 is UNCHANGED: the four-field hypothesis view, schema-closed
    assert [sorted(h) for h in nxt["step"]["context"]["hypotheses"]] == [sorted(SV.TRAIL_WIRE_FIELDS)]
    view = nxt["materials"]["values"]["hypothesis_semantics"][0]
    s = view["semantics"]
    assert view["hypothesis"]["statement"].startswith("lone photographers") and (s["population"], s["task"], s["context"]) == \
        ("landscape photographers", "reach spare batteries", "on the trail")
    assert s["mechanism"] == "spares are stored away from the point of use" and s["suspected_friction"] == "buried accessories"
    assert [g["question"] for g in view["knowledge"]["knowledge_gaps"]] == ["does digging for a battery cost them a shot?"]
    assert view["transduction"]["run_level"]["transferable_invariants"] == ["tending interrupts operating"]
    assert view["origin"]["leads"][0]["id"] == "lead_latent" and view["transduction"]["latent_structures"][0]["basis"] == "DECLARED"
    assert view["bridge"]["target_mechanism"] == "point-of-use access" and view["bridge"]["gaps"] == ["do lone photographers stop work to reach spares?"]
    # newer TARGETED evidence is readable although the first pass alone overfills every cap (150 rows > 60 readable)
    targeted = [r for r in nxt["evidence"]["rows"] if r["id"].startswith("chunk_targeted_")]
    assert targeted and all(r["retrieval_pass"] == 1 for r in targeted) and len(nxt["evidence"]["rows"]) == 60
    assert any(r["id"].startswith("chunk_targeted_") for r in nxt["step"]["context"]["evidence_refs"])        # and citable
    # a step that did not ask for the view gets none
    assert "hypothesis_semantics" not in (seen["hypothesize"].get("materials") or {}).get("values", {})


def test_acceptance_a_domain_consumer_sees_the_revised_state_and_the_stored_step_stays_closed(runtime):
    rid, _, seen = _drive(runtime)
    step = seen["domain_step"]
    q = step["context"]["semantics"]["query"][0]
    assert q["mechanism"] == "the shooter is also the fetcher" and q["revision"] == 1                          # the LATEST revision, not the proposal
    assert [g["question"] for g in q["knowledge_gaps"]] == ["does digging for a battery cost them a shot?", "which spares are reached for most?"]
    assert q["population_aliases"] == ["lone operators of precision tools"] and q["bridge_gaps"] == ["do lone photographers stop work to reach spares?"]
    # what Trail would be sent is still exactly four fields; nothing of the view was persisted
    assert [sorted(h) for h in step["context"]["hypotheses"]] == [sorted(SV.TRAIL_WIRE_FIELDS)]
    assert [SV.trail_projection(h) for h in step["context"]["hypotheses"]] == step["context"]["hypotheses"]
    stored = next(r for r in runtime.list_steps(None, rid) if r["step_id"] == "plan")
    assert "semantics" not in stored["step"]["context"] and stored["output"]["planned"] == 1
    assert "semantics" not in json.dumps(runtime.runs[rid]["state"])


def test_the_production_manifest_gives_every_restored_input_a_consumer():
    m = M.load_manifest(ROOT / "config" / "adapters" / "ecommerce.product_research.json")
    show = {sid: (s.get("config") or {}).get("show") or {} for sid, s in m.steps.items()}
    for sid in ("C_bridge", "G_mechanisms", "K_revise", "N_jobs", "N_concepts"):
        assert show[sid].get("hypothesis_semantics") == "semantics.hypotheses", sid
    assert show["C_hypotheses"]["primitives"] == "outputs.C_primitives.primitives" and "latent_structures" in show["C_hypotheses"]
    assert sum(1 for s in show.values() if any(str(v).startswith("semantics.") for v in s.values())) == 5        # not "show everything everywhere"
    item = m.steps["C_hypotheses"]["output_schema"]["properties"]["hypotheses"]["items"]["properties"]
    assert {"lead_ids", "latent_structure_ids"} <= set(item)
    for sid in ("G_mechanisms", "K_revise", "N_jobs"):
        changes = m.steps[sid]["output_schema"]["properties"]["transitions"]["items"]["properties"]["changes"]
        assert changes["additionalProperties"] is False and set(changes["properties"]) == set(H.REVISABLE_FIELDS + H.REVISABLE_LIST_FIELDS)
