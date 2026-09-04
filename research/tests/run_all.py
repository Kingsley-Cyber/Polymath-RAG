#!/usr/bin/env python3
"""Dependency-free test suite (no pytest in the Hermes venv — deliberate).

Run:  ~/.hermes/hermes-agent/venv/bin/python tests/run_all.py
Covers: graph structure, illegal-transition rejection, supplier parsing,
the abstention path (negative control), and a full positive E2E walk of the
control graph through the CLI — the same interface the agent uses.
"""
import json
import os
import subprocess
import sys
import tempfile

os.environ["OPPORTUNITY_RESEARCH_DB"] = os.path.join(tempfile.mkdtemp(), "test-loop.sqlite3")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CTL = os.path.join(ROOT, "python", "controller.py")
sys.path.insert(0, os.path.join(ROOT, "python"))

import executors  # noqa: E402
import graph as graphmod  # noqa: E402

PASS = 0
FAILS: list = []


def ok(cond, label):
    """Fail-fast by default (CI). RUN_ALL_CONTINUE=1 collects every failure
    and exits non-zero at the end — so one broken check no longer hides the
    rest during local triage."""
    global PASS
    if not cond:
        print(f"FAIL  {label}")
        if os.environ.get("RUN_ALL_CONTINUE") == "1":
            FAILS.append(label)
            return
        sys.exit(1)
    PASS += 1
    print(f"pass  {label}")


def ctl(*args):
    r = subprocess.run([PY, CTL, *args], capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.returncode, {"raw": r.stdout, "err": r.stderr}


def submit(state, node, payload):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        p = f.name
    rc, out = ctl("submit", "--state", state, "--node", node, "--file", p)
    os.unlink(p)
    return rc, out


# ---- 1. graph structure -----------------------------------------------------
g = graphmod.load_graph()
ok(graphmod.validate_graph(g) == [], "control_graph.yaml structurally valid")
ok(g["graph"]["entry"] == "understand", "entry is understand (never Alibaba)")
supplier_preds = {e["from"] for e in g["edges"] if e["to"] == "supplier_search"}
ok(supplier_preds == {"product_ideation"}, "Alibaba reachable ONLY through product_ideation (docs/19)")
ideation_preds = {e["from"] for e in g["edges"] if e["to"] == "product_ideation"}
ok(ideation_preds == {"mechanism"}, "product_ideation reachable ONLY through a supported mechanism")
ok((g["nodes"]["corpus"].get("on_enter") == "python.corpus_query_compiler"), "corpus node compiles its reformulations on entry (docs/19)")

# ---- 2. supplier normalization ---------------------------------------------
st = {"data": {"supplier_candidates": [
    {"id": "s1", "product_name": "Clip Mic", "supplier_name": "Shenzhen A",
     "price_raw": "US $12.50 - 18.00", "moq_raw": "100 pcs", "url": "u1"},
    {"id": "s2", "product_name": "Clip Mic", "supplier_name": "Shenzhen A",
     "price_raw": "dup", "moq_raw": "dup", "url": "u1"},
    {"id": "s3", "product_name": "Windshield", "supplier_name": "B Co",
     "price_raw": "$0.80", "moq_raw": "2,000 pieces", "url": "u2"}]}}
note = executors.supplier(st, graphmod.load_policies())
s = st["data"]["supplier_candidates"]
ok(len(s) == 2, "supplier dedupe by (product,supplier)")
ok(s[0]["price_usd_low"] == 12.5 and s[0]["price_usd_high"] == 18.0, "price range parsed")
ok(s[0]["moq_units"] == 100 and s[1]["moq_units"] == 2000, "MOQ parsed incl. thousands")

# ---- 2b. bridge admissibility (φ constraining θ) ---------------------------
import bridge  # noqa: E402
pol = graphmod.load_policies()
BASE = {"alternatives": ["alt explanation"], "falsifiers": ["killer observation"]}
valid3 = {"id": "bv", "source": "s", "path": ["a", "b", "c"], "target_mechanism": "m",
          "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["?"],
          "status": "WORKING_HYPOTHESIS", **BASE}
direct = {"id": "bx", "source": "storytelling", "path": ["storytelling", "microphone"],
          "target_mechanism": "microphone", "evidence_boundary": {"first_inference_at": "storytelling"},
          "gaps": ["?"], "status": "WORKING_HYPOTHESIS", **BASE}
long_leap = {"id": "by", "source": "s", "path": ["a", "b", "c", "d", "e"],
             "target_mechanism": "m", "evidence_boundary": {"first_inference_at": "b"},
             "gaps": ["?"], "status": "WORKING_HYPOTHESIS", **BASE}
no_gap = {"id": "bz", "source": "s", "path": ["a", "b", "c"], "target_mechanism": "m",
          "evidence_boundary": {"first_inference_at": "b"}, "gaps": [],
          "status": "WORKING_HYPOTHESIS", **BASE}
ghost = {"id": "bg", "source": "s", "path": ["a", "b", "c"], "target_mechanism": "m",
         "evidence_boundary": {"first_inference_at": "zz"}, "gaps": ["?"],
         "status": "WORKING_HYPOTHESIS", **BASE}
bare = {"id": "bn", "source": "s", "path": ["a", "b", "c"], "target_mechanism": "m",
        "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["?"],
        "status": "WORKING_HYPOTHESIS"}
ok(bridge.validate_bridge(valid3, pol) == [], "well-formed 3-hop bridge admissible")
ok(any("intermediate mechanism" in e for e in bridge.validate_bridge(direct, pol)),
   "direct source->product jump rejected")
ok(any("alternatives" in e for e in bridge.validate_bridge(bare, pol)) and
   any("falsifiers" in e for e in bridge.validate_bridge(bare, pol)),
   "bridge without alternatives+falsifiers rejected")
ok(any("researchable gaps" in e for e in bridge.validate_bridge(long_leap, pol)),
   "long speculation without covering gaps rejected")
long_leap_covered = dict(long_leap, gaps=["hop c real?", "hop d real?"])
ok(bridge.validate_bridge(long_leap_covered, pol) == [],
   "same bridge admissible once gaps cover the speculation")
ok(any("unfalsifiable" in e for e in bridge.validate_bridge(no_gap, pol)),
   "gapless working hypothesis rejected as unfalsifiable")
ok(any("not a hop in path" in e for e in bridge.validate_bridge(ghost, pol)),
   "evidence boundary must exist in the path")

# ---- 2b2. portfolio diversity law -------------------------------------------
def _hyp(i, mech, **kw):
    d = {"id": f"p{i}", "source": "s", "path": ["a", "b", "c"], "target_mechanism": mech,
         "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["?"],
         "status": "WORKING_HYPOTHESIS", **BASE}
    d.update(kw); return d
dup_port = [_hyp(1, "magnet"), _hyp(2, "magnet"), _hyp(3, "clamp")]
ok(any("duplicate mechanism families" in e for e in bridge.validate_portfolio(dup_port, pol)),
   "portfolio rejects mechanism-family duplicates")
ok(any("need 3-6" in e for e in bridge.validate_portfolio([_hyp(1, "magnet")], pol)),
   "portfolio requires 3-6 diverse hypotheses")
wild_bad = [_hyp(1, "magnet"), _hyp(2, "clamp"), _hyp(3, "badge_reel", exploratory=True)]
ok(any("WORKING_ANALOGY" in e for e in bridge.validate_portfolio(wild_bad, pol)),
   "exploratory transfer must be WORKING_ANALOGY — no evidentiary privilege")
wild_ok = [_hyp(1, "magnet"), _hyp(2, "clamp"),
           _hyp(3, "badge_reel", exploratory=True, status="WORKING_ANALOGY")]
ok(bridge.validate_portfolio(wild_ok, pol) == [], "diverse portfolio with one wildcard admissible")

# ---- 2c. evidence authority (relevance != authority) ------------------------
import verifiers  # noqa: E402
import satisfaction  # noqa: E402
good_obs = {"id": "ea1", "gap_id": "g", "source": "reddit.com/r/a/1", "quote_ref": "q",
            "community": "creators", "problem": "p", "evidence_roles": ["FRICTION_EVIDENCE"],
            "freshness": {"class": "LIVE"},
            "source_identity": {"source_family": "community", "platform": "reddit", "author_key": "a1"}}
ok(verifiers.evidence_admissibility(good_obs, pol) == [], "community friction evidence admissible")
bad_role = dict(good_obs, id="ea2", evidence_roles=["FRICTION_EVIDENCE"],
                source_identity={"source_family": "supplier", "platform": "alibaba", "author_key": "s1"})
ok(any("may not establish" in e for e in verifiers.evidence_admissibility(bad_role, pol)),
   "supplier listing cannot establish human friction")
stale = dict(good_obs, id="ea3", evidence_roles=["SUPPLIER_AVAILABILITY"],
             source_identity={"source_family": "supplier", "platform": "alibaba", "author_key": "s1"},
             freshness={"class": "EVERGREEN"})
ok(any("freshness" in e for e in verifiers.evidence_admissibility(stale, pol)),
   "evergreen source cannot establish live supplier availability")
ind = verifiers.independence_groups([
    dict(good_obs, id=f"x{i}", source_identity={"source_family": "community",
         "platform": "reddit", "author_key": "same_author"}) for i in range(5)])
ok(ind["independent_groups"] == 1, "five comments from one author = one independent group")

# ---- 2d. registry compiler ---------------------------------------------------
import registry as regmod  # noqa: E402
snap, cerrs = regmod.compile_registry()
ok(cerrs == [] and snap is not None, "registry compiles VALID from real trailsignal CSVs")
ok(snap["counts"]["seeds"] == 1386 and snap["counts"]["activities"] > 400,
   "full seed registry compiled (1386 seeds, 400+ atomic activities)")
ok(len(snap["index_by_predicate_friction"].get("access|occupied_hand", [])) > 0,
   "(predicate, friction) structural index resolves cross-domain analogies")
ok(all(t.get("expected_roles") is not None for t in snap["query_templates"]),
   "every query grammar mapped to evidence roles (or explicit non-evidence purpose)")
ok(all(c["score_basis"] == "SEED_PRIOR" and not c["evidence_validated"]
       for c in snap["candidate_priors"]),
   "candidate numbers compiled as SEED_PRIOR, never validated evidence")
ok(all(sd["weight"] for sd in snap["scoring_dimensions"].values()),
   "scoring dimensions sourced solely from rubric")

# ---- 3. E2E: negative control -> NO_GENERATIVE_SIGNAL -----------------------
tmp = tempfile.mkdtemp()
neg = os.path.join(tmp, "neg.json")
rc, out = ctl("init", "--state", neg, "--signal", "medieval monastery brewing schedules")
ok(rc == 0 and out["node"] == "understand", "init at entry")
rc, out = submit(neg, "hypothesize", {"hypotheses": []})
ok(rc == 1, "out-of-order submission rejected")
submit(neg, "understand", {"signal": "monastery brewing; no living community tension identified"})
ctl("step", "--state", neg)
submit(neg, "corpus", {"corpus_evidence": [{"id": "e1", "summary": "barrel cooperage economics"}]})
ctl("step", "--state", neg)      # -> primitives
submit(neg, "primitives", {"primitives": {"generative_signal": False}})
ctl("step", "--state", neg)      # -> signal_gate
rc, out = ctl("step", "--state", neg)  # gate -> stop
nstate = json.load(open(neg))
ok(nstate["status"] == "stopped" and nstate["verdict"] == "NO_GENERATIVE_SIGNAL",
   "knowledge without generative signal abstains cleanly (a SUCCESS outcome)")

# ---- 4. E2E: positive storytelling walk ------------------------------------
pos = os.path.join(tmp, "pos.json")
ctl("init", "--state", pos, "--signal", "storytelling performance movement gesture friction")
submit(pos, "understand", {"signal": "storytelling performance movement gesture friction; creators move while recording"})
ctl("step", "--state", pos)
submit(pos, "corpus", {"corpus_evidence": [{"id": "e1", "summary": "creator differentiation via physical delivery and movement"},
                                             {"id": "e0", "summary": "he put a pillow under her and held it all in", "title": "Some Novel"}]})
ctl("step", "--state", pos)            # -> primitives
_prim = {"generative_signal": True,
    "behaviors": ["performer physically expresses while speaking"],
    "constraints": ["capture system must preserve movement"],
    "frictions": ["occupied_hand"],
    "physical_jobs": ["capture clean audio without constraining expression"],
    "shared_predicates": ["access", "attach"],
    "transferable_invariants": ["tool should interfere as little as possible with the activity it enables"],
    # docs/26: source-agnostic interpretation objects
    "latent_structures": [{"id": "st1", "kind": "TRANSFERABLE_INVARIANT", "text": "frequent access to a small object while hands stay occupied and the body moves",
                           "evidence_refs": ["e1"], "applicability_outside_source": "anyone who performs while handling gear", "authority": "LATENT_HYPOTHESIS"},
                          {"id": "st2", "kind": "ROUTINE", "text": "sets up the same kit in a new room every day", "evidence_refs": ["e1"],
                           "possible_populations": ["touring musicians"], "authority": "LATENT_HYPOTHESIS"}],
    "corpus_observations": [{"id": "co1", "kind": "OBSERVED_PRODUCT", "name": "lavalier microphone", "evidence_refs": ["e1"], "job_served": "hands-free capture",
                             "evidentiary_authority": "NONE_FOR_CURRENT_DEMAND"}],
    "row_relevance": {"e1": "STRUCTURAL_ANALOGY", "e0": "IRRELEVANT"}}
rc, out = submit(pos, "primitives", {"primitives": dict(_prim, row_relevance={"e1": "MAYBE"})})
ok(rc == 1 and any("row_relevance" in e for e in out.get("schema_errors", [])), "an unknown relevance class is rejected (docs/26 axis 1)")
rc, out = submit(pos, "primitives", {"primitives": _prim})
ok(rc == 0, f"primitives with latent structures, corpus observations and row relevance admitted ({out.get('schema_errors', '')[:1]})")
_ps0 = json.load(open(pos))
ok(len(_ps0["data"]["latent_structures"]) == 2 and _ps0["data"]["corpus_observations"][0]["kind"] == "OBSERVED_PRODUCT"
   and next(r for r in _ps0["data"]["corpus_evidence"] if r["id"] == "e0").get("relevance") == "IRRELEVANT",
   "interpretation objects are mirrored into their own data keys and relevance is stamped on rows")
ctl("step", "--state", pos)            # -> signal_gate
ctl("step", "--state", pos)            # gate -> lenses
ctl("step", "--state", pos)            # lens gate -> structural_lookup
rc, out = ctl("step", "--state", pos)  # structural -> population_nominate (docs/25)
ok(out["ok"] and out["advanced_to"] == "population_nominate", "signal+lens+structural gates advanced into population discovery")
pstate = json.load(open(pos))
ok(len(pstate["data"]["cross_domain_analogies"]) > 0,
   "invariant-bounded cross-domain analogies attached from registry")
rc, out = ctl("step", "--state", pos)  # nominate -> population_scout
pstate = json.load(open(pos))
ok(out.get("advanced_to") == "population_scout" and pstate["data"]["population_leads"]
   and all(l["authority"] == "LEAD" and l["status"] == "NOMINATED" for l in pstate["data"]["population_leads"]),
   f"registry situations nominated as PopulationLeads (authority LEAD, never demand): {len(pstate['data']['population_leads'])}")
ok(all(l.get("channel_queries") and all(q.get("tools") for q in l["channel_queries"]) for l in pstate["data"]["population_leads"]),
   "every lead carries compiled channel queries with tool chains (docs/24)")
_latent = [l for l in pstate["data"]["population_leads"] if l.get("search_mode") == "LATENT"]
_named_from_structure = [l for l in pstate["data"]["population_leads"] if l.get("latent_structure_id") == "st2"]
ok(_latent and all(l["source_lane"] == "LATENT" for l in _latent) and "hands" in _latent[0]["channel_queries"][0]["query"] and "who repeatedly" not in _latent[0]["channel_queries"][0]["query"]
   and _named_from_structure and _named_from_structure[0]["name"] == "touring musicians",
   "LATENT PROBLEM → population: a structure with no population becomes a LATENT lead searched by its own language; a named one becomes a NAMED lead (docs/26 §4)")
rc, out = submit(pos, "population_scout", {"community_leads": [
    {"id": "cl_creators", "kind": "COMMUNITY", "name": "r/NewTubers", "source_lane": "OPEN_FIELD", "platform": "reddit",
     "community_key": "NewTubers", "nominated_by": ["reddit search 'mic cable movement' → 9 posts in r/NewTubers"],
     "authority": "LEAD", "status": "NOMINATED", "why": "creators complain about tethered audio", "expected_frictions": ["occupied_hand"]},
    {"id": "cl_dance", "kind": "COMMUNITY", "name": "r/Dance", "source_lane": "OPEN_FIELD", "platform": "reddit",
     "community_key": "Dance", "nominated_by": ["reddit search 'teaching class mic' → 5 posts in r/Dance"],
     "authority": "LEAD", "status": "NOMINATED", "why": "instructors teach while moving, nobody nominated them", "expected_frictions": ["movement_restriction"]}]})
ok(rc == 0, f"open-field CommunityLeads admitted ({out.get('schema_errors', '')[:1]})")
_cl_state = json.load(open(pos))
_cl_dance = next(l for l in _cl_state["data"]["community_leads"] if l["id"] == "cl_dance")
ok(_cl_dance.get("channel_queries") and any(q["channel"] == "reddit" and q.get("subreddit_hints") == ["Dance"] and q.get("tools") for q in _cl_dance["channel_queries"]),
   "an agent-submitted community lead gets its channel tool chains compiled at submit, scoped to its community (live defect 2026-09-04: '4 leads, 0 channel queries')")
rc, out = submit(pos, "population_scout", {"community_leads": [dict(pstate["data"]["population_leads"][0], id="bad_lead", kind="COMMUNITY", authority="DEMAND")]})
ok(rc == 1, "a lead claiming DEMAND authority is rejected — a lead never establishes demand")
ctl("step", "--state", pos)            # scout -> population_queue
rc, out = ctl("step", "--state", pos)  # queue -> community_instantiate
pq = json.load(open(pos))["population_queue"]
ok(out.get("advanced_to") == "community_instantiate" and pq["round"] == 1 and 1 <= len(pq["batch"]) <= 4
   and pq["batch"][0] in ("cl_creators", "cl_dance") and pq["batch_queries"] > 0,
   f"VOI queue hands ONE batch, open-field non-seed leads first, never with zero channel queries ({pq['batch'][:2]}, {pq['batch_queries']} queries)")
def _rec(i, lead, comm, fam, author, thread, roles, moment=None, products=None, workaround=""):
    return {"id": f"fr_{lead}_{i}", "lead_id": lead, "source": f"reddit.com/r/{comm}/{thread}", "quote_ref": f"real quote {lead} {i}",
            "community": f"r/{comm}", "problem": f"{fam} while filming {i}", "workaround": workaround, "friction_family": fam,
            "evidence_roles": roles, "freshness": {"class": "LIVE"}, "origin": "CHANNEL", **({"moment": moment} if moment else {}),
            **({"products_named": products} if products else {}),
            "source_identity": {"source_family": "community", "platform": "reddit", "author_key": author, "thread_key": thread}}
# independence law: 5 authors across 2 threads = 2 voices (THIN); across 3 threads = 3 voices (ANCHOR)
recs = ([_rec(i, "cl_creators", "NewTubers", "occupied_hand", f"nt_a{i}", f"nt_t{i % 3}", ["FRICTION_EVIDENCE"], "DURING", ["collar clip"], "tapes transmitter to belt") for i in range(5)]
        + [_rec(i, "cl_dance", "Dance", "movement_restriction", f"dn_a{i}", f"dn_t{i % 3}", ["WORKAROUND_EVIDENCE"], None, ["sweatband pouch"], "stuffs mic in sweatband") for i in range(6)]
        + [_rec(0, pstate["data"]["population_leads"][0]["id"], "hiking", "carry_load", "hk_a0", "hk_t0", ["BEHAVIOR_SUPPORT"])])
rc, out = submit(pos, "community_instantiate", {"field_records": [dict(recs[0], id="bad_rec", lead_id="nope")]})
ok(rc == 1 and any("not a nominated lead" in e for e in out.get("schema_errors", [])), "a field record must belong to a nominated lead")
rc, out = submit(pos, "community_instantiate", {"field_records": recs})
ok(rc == 0, f"field records admitted through the evidence contract ({out.get('schema_errors', '')[:1]})")
rc_dup, out_dup = submit(pos, "community_instantiate", {"field_records": [dict(recs[0], id="fr_late_add", quote_ref="a record that arrived in a second payload")]})
ok(rc_dup == 1 and out_dup.get("error") == "IDEMPOTENCY_CONFLICT", "a second, different payload in the same visit is refused as IDEMPOTENCY_CONFLICT — one payload per visit (live 2026-09-04)")
ctl("step", "--state", pos)            # instantiate -> evidence_cards
rc, out = ctl("step", "--state", pos)  # cards -> population_gate
pstate = json.load(open(pos))
cl = {c["community"]: c for c in pstate["data"]["lived_clusters"]}
ok(len(pstate["data"]["participant_cards"]) == 12 and cl["newtubers"]["authority"] == "ANCHOR" and cl["dance"]["authority"] == "ANCHOR"
   and cl["hiking"]["authority"] == "THIN" and cl["hiking"]["unknowns"],
   f"cards + clusters: 5 records/3 threads/3 voices = ANCHOR, one record = THIN with unknowns ({ {k: v['authority'] for k, v in cl.items()} })")
rc, out = ctl("step", "--state", pos)  # gate -> lived_situations (2 anchors satisfy the minimum)
ok(out.get("advanced_to") == "lived_situations", f"population gate proceeds once enough ANCHOR clusters exist ({out.get('note')})")
_anchor, _thin = cl["newtubers"]["id"], cl["hiking"]["id"]
rc, out = submit(pos, "lived_situations", {"lived_situations": [
    {"id": "bad_ls", "authority": "FIELD_ANCHORED", "cluster_id": _thin, "unknowns": [], "frictions": [{"text": "x", "authority": "FIELD_OBSERVATION", "refs": ["fr_cl_creators_0"]}]}]})
ok(rc == 1 and any("THIN" in e for e in out.get("schema_errors", [])), "FIELD_ANCHORED on a THIN cluster is rejected — thin cards may only feed reconstruction")
rc, out = submit(pos, "lived_situations", {"lived_situations": [
    {"id": "ls_nt", "authority": "FIELD_ANCHORED", "cluster_id": _anchor, "community": "newtubers", "activity": "filming a talking-head video", "moment": "DURING",
     "body_hand_state": "one hand on the camera, torso turning", "frictions": [{"text": "cable restricts turning", "authority": "FIELD_OBSERVATION", "refs": ["fr_cl_creators_0", "fr_cl_creators_1"]}],
     "unknowns": ["how often they film standing", "whether they edit the same day"]},
    {"id": "ls_hk", "authority": "RECONSTRUCTED", "cluster_id": _thin, "situation": "packing at the trailhead", "unknowns": ["what they carry", "whether hands are free"]},
    {"id": "bad_bio", "authority": "RECONSTRUCTED", "cluster_id": _thin, "situation": "a complete life story", "unknowns": []}]})
ok(rc == 1 and any("biography" in e for e in out.get("schema_errors", [])), "a reconstruction without unknowns is rejected as a biography")
rc, out = submit(pos, "lived_situations", {"lived_situations": [
    {"id": "ls_nt", "authority": "FIELD_ANCHORED", "cluster_id": _anchor, "community": "newtubers", "activity": "filming a talking-head video", "moment": "DURING",
     "frictions": [{"text": "cable restricts turning", "authority": "FIELD_OBSERVATION", "refs": ["fr_cl_creators_0", "fr_cl_creators_1"]}],
     "unknowns": ["how often they film standing"]},
    {"id": "ls_hk", "authority": "RECONSTRUCTED", "cluster_id": _thin, "situation": "packing at the trailhead", "unknowns": ["what they carry"]}]})
ok(rc == 0, f"anchored + reconstructed situations admitted ({out.get('schema_errors', '')[:1]})")
rc, out = ctl("step", "--state", pos)  # lived_situations -> corpus_mechanisms (on_enter compiles questions)
pstate = json.load(open(pos))
ok(out.get("advanced_to") == "corpus_mechanisms" and pstate["data"]["corpus_questions"]
   and all(q["question"] and q["cluster_id"] for q in pstate["data"]["corpus_questions"])
   and any("workaround" in q["question"].lower() for q in pstate["data"]["corpus_questions"]),
   f"corpus questions compiled at friction/mechanism level from clusters ({len(pstate['data']['corpus_questions'])})")
submit(pos, "corpus_mechanisms", {"corpus_evidence": [{"id": "e2", "summary": "habit cues survive when the tool interferes least with the movement",
                                                        "question_id": pstate["data"]["corpus_questions"][0]["id"], "tags": ["chunk", "question_level"], "doc_id": "bookA"}]})
rc, out = ctl("step", "--state", pos)  # corpus_mechanisms -> hypothesize
ok(out.get("advanced_to") == "hypothesize", "question-level corpus pass feeds the bridge")
_c_nt, _c_dn = cl["newtubers"]["id"], cl["dance"]["id"]
h = {"id": "h1", "source": "storytelling_importance",
     "path": ["creator_differentiation", "physical_delivery", "movement", "low_interference_audio"],
     "target_mechanism": "wearable_wireless_audio",
     "evidence_boundary": {"first_inference_at": "creator_differentiation"},
     "gaps": ["creators complain equipment interferes with movement",
              "creators actually move while recording"],
     "status": "WORKING_HYPOTHESIS",
     "alternatives": ["static creators dominate; audio friction is niche"],
     "falsifiers": ["creators report never moving while recording"]}
h2 = dict(h, id="h2", target_mechanism="mechanical_clamp_mount",
          gaps=["creators want stronger clips", "clip failures reported in the wild"],
          falsifiers=["clips already satisfy"])
h3 = dict(h, id="h3", target_mechanism="garment_integrated_pocket",
          gaps=["creators would buy audio-ready garments", "garment mods observed"],
          falsifiers=["nobody modifies clothing for audio"])
rc, out = submit(pos, "hypothesize", {"hypotheses": [h, h2, h3]})
ok(rc == 1 and any("lived_anchor_ids" in e or "CORPUS_ONLY" in e for e in out.get("schema_errors", [])),
   "a hypothesis must name its lane: ANCHOR clusters or grounding CORPUS_ONLY (docs/25 §5)")
rc, out = submit(pos, "hypothesize", {"hypotheses": [dict(h, lived_anchor_ids=[_thin]), dict(h2, grounding="CORPUS_ONLY"), dict(h3, grounding="CORPUS_ONLY")]})
ok(rc == 1 and any("THIN" in e for e in out.get("schema_errors", [])), "a THIN cluster cannot anchor a hypothesis")
rc, out = submit(pos, "hypothesize", {"hypotheses": [dict(h, lived_anchor_ids=[_c_nt], hop_refs={"1": ["e0"]}), dict(h2, lived_anchor_ids=[_c_dn]), dict(h3, grounding="CORPUS_ONLY")]})
ok(rc == 1 and any("IRRELEVANT" in e for e in out.get("schema_errors", [])), "a hop citing a row classified IRRELEVANT is refused (docs/26 §2)")
h = dict(h, lived_anchor_ids=[_c_nt], hop_refs={"1": ["e1"]}); h2 = dict(h2, lived_anchor_ids=[_c_dn], hop_refs={"1": ["e1"]}); h3 = dict(h3, grounding="CORPUS_ONLY")
rc, out = submit(pos, "hypothesize", {"hypotheses": [h, h2, h3]})
ok(rc == 0, f"diverse 3-hypothesis portfolio admitted with lived anchors ({out.get('schema_errors', '')[:1]})")
rc, out = ctl("step", "--state", pos)  # -> semantic_review
ok(out.get("advanced_to") == "semantic_review" and "dossier" in str(out.get("needs", {})),
   "L4 review node reached with dossier directive")
import evaluator as evmod  # noqa: E402
dossier = evmod.build_dossier(json.load(open(pos)))
ok(all("notes" not in b and "research_priority" not in b for b in dossier["bridges"])
   and dossier["bridges"], "dossier is sanitized structure, no generator narrative")
evals = {"evaluations": [
    {"id": "ev1", "hypothesis_id": "h1", "verdict": "PASS", "reasons": ["mechanistic chain plausible"]},
    {"id": "ev2", "hypothesis_id": "h2", "verdict": "REVISE", "reasons": ["missing middle"],
     "missing_intermediates": ["evidence clips fail under movement"]},
    {"id": "ev3", "hypothesis_id": "h3", "verdict": "PASS", "reasons": ["distinct family, falsifiable"]}]}
submit(pos, "semantic_review", evals)
rc, out = ctl("step", "--state", pos)  # semantic_review -> apply_review
rc, out = ctl("step", "--state", pos)  # apply L4 -> challenge
ok("L4 verdicts applied" in str(out.get("note", "")), "L4 verdicts applied deterministically")
pstate2 = json.load(open(pos))
h2_now = next(x for x in pstate2["data"]["hypotheses"] if x["id"] == "h2")
ok(h2_now["status"] == "CHALLENGED" and any("missing intermediate" in g for g in h2_now["gaps"]),
   "REVISE downgrades to CHALLENGED and missing intermediates become gaps")
ok(len(pstate2.get("l4_receipts", [])) == 3, "L4 receipts recorded (model judgment, never fact)")
submit(pos, "challenge", {"challenges": [{"id": "c1", "hypothesis_id": "h1",
       "argument": "maybe static creators dominate", "verdict": "WORKING_HYPOTHESIS"}]})
ctl("step", "--state", pos)            # -> triage
rc, out = ctl("step", "--state", pos)  # triage -> gaps
ok("research-ready" in str(out.get("note", "")), "triage assigns research priority")
rc, out = ctl("step", "--state", pos)  # gap compiler -> web_research
ok(out["advanced_to"] == "web_research", "open gap routes to web_research")
state = json.load(open(pos))
gids = [gp["id"] for gp in state["data"]["gaps"] if gp["hypothesis_id"] == "h1"]
ok(len(gids) == 2 and len(state["data"]["queries"]) >= 6, "gaps + queries compiled (h1 pair tracked)")
ok(all(q.get("why_this_source") and q.get("expected_evidence_roles") for q in state["data"]["queries"]),
   "every query declares why_this_source + expected roles")
obs = [{"id": f"o{g}{i}", "gap_id": gid, "source": f"reddit.com/r/x/{g}{i}",
        "quote_ref": f"my mic cable kills my movement {g}{i}", "community": "creators",
        "problem": "tethered audio", "workaround": "tapes transmitter to belt",
        "purchase_language": i == 0,
        "evidence_roles": ["FRICTION_EVIDENCE"] if i != 1 else ["WORKAROUND_EVIDENCE"],
        "freshness": {"class": "LIVE"},
        "source_identity": {"source_family": "community", "platform": "reddit",
                            "author_key": f"author_{g}{i}", "thread_key": f"t{g}{i}"}}
       for g, gid in enumerate(gids) for i in range(3)]
# docs/20 §1: the clamp and garment paths are REJECTED at the next challenge, so the
# evidence must actually speak against them — one contradicting voice per path
_gids23 = [next(gp["id"] for gp in state["data"]["gaps"] if gp["hypothesis_id"] == hid) for hid in ("h2", "h3")]
obs += [{"id": f"oc{k}", "gap_id": gid, "source": f"reddit.com/r/x/contra{k}", "contradicts": True,
         "quote_ref": f"tried that path, it does not hold up {k}", "community": "creators", "problem": "n/a",
         "evidence_roles": ["FRICTION_EVIDENCE"], "freshness": {"class": "LIVE"},
         "source_identity": {"source_family": "community", "platform": "reddit", "author_key": f"contra_{k}", "thread_key": f"tc{k}"}}
        for k, gid in enumerate(_gids23)]
bad_sub = dict(obs[0], id="zbad", evidence_roles=["SUPPLIER_AVAILABILITY"])
rc_b, out_b = submit(pos, "web_research", {"observations": [bad_sub]})
ok(rc_b == 1 and any("may not establish" in e for e in out_b.get("schema_errors", [])),
   "controller rejects evidence claiming roles its source cannot establish")
submit(pos, "web_research", {"observations": obs})
ctl("step", "--state", pos)            # -> curate
ctl("step", "--state", pos)            # curate -> challenge
submit(pos, "challenge", {"challenges": [{"id": "c2", "hypothesis_id": "h1",
       "argument": "6 independent complaints support the bridge; clamp and garment paths contradicted",
       "verdict": "SUPPORTED"}],
       "hypotheses": [dict(h, status="SUPPORTED"),
                      dict(h2, status="REJECTED"), dict(h3, status="REJECTED")]})
ctl("step", "--state", pos)            # -> triage
ctl("step", "--state", pos)            # triage -> gaps
rc, out = ctl("step", "--state", pos)
ok(out["advanced_to"] == "mechanism",
   "evidence_sufficient: rejected hypotheses' gaps are moot, supported path advances")
submit(pos, "mechanism", {
    "mechanisms": [{"id": "m1", "name": "wearable-wireless-audio", "hypothesis_id": "h1",
                    "supporting_observation_ids": [o["id"] for o in obs], "status": "SUPPORTED"}],
    "product_candidates": [{"id": "p1", "mechanism_id": "m1", "name": "DJI Mic class"}]})
rc, out = ctl("step", "--state", pos)
ok(out["advanced_to"] == "product_ideation", "supported mechanism unlocks product ideation (docs/19)")
_obs_ids = [o["id"] for o in obs]
_concepts = [{"id": f"pc{i}", "mechanism_id": "m1", "name": n, "form_factor": ff, "target_moment": "recording on the move",
              "variations": [{"name": f"{n} lite"}, {"name": f"{n} pro", "twist": "dual channel"}],
              "evidence_refs": _obs_ids[:2]}
             for i, (n, ff) in enumerate([("Clip mic", "wearable"), ("Collar loop", "garment-integrated"), ("Desk puck", "tabletop")], 1)]
# docs/25 §7: one concept grounded across communities (observations + field records from two clusters),
# one field-originated noun (the sweatband pouch the dancers named — absent from every corpus row)
_concepts[0]["evidence_refs"] = _obs_ids[:3] + ["fr_cl_creators_0", "fr_cl_dance_0", "fr_cl_dance_1"]
_concepts[1] = dict(_concepts[1], name="Sweatband pouch", form_factor="wearable band", origin="FIELD",
                    evidence_refs=["fr_cl_dance_0", "fr_cl_dance_1", "fr_cl_dance_2", "fr_cl_dance_3"])
submit(pos, "product_ideation", {"product_concepts": _concepts})
rc, out = ctl("step", "--state", pos)
ok(out.get("advanced_to") == "supplier_search", f"3 distinct concepts x 2 variations unlock Alibaba ({out if out.get('advanced_to') != 'supplier_search' else ''})")
submit(pos, "supplier_search", {"supplier_candidates": [
    {"id": "s1", "product_name": "Wireless Lav Kit", "supplier_name": "Shenzhen Audio", "mechanism_id": "m1", "concept_id": "pc1",
     "price_raw": "US $9.90 - 14.50", "moq_raw": "50 pcs", "url": "alibaba.com/x"}]})
ctl("step", "--state", pos)            # -> normalize
ctl("step", "--state", pos)            # normalize -> qualify
rc, out = ctl("step", "--state", pos)  # qualify gate -> stop
state = json.load(open(pos))
ok(state["status"] == "stopped" and state["verdict"] == "QUALIFIED_LEADS",
   "positive walk terminates with QUALIFIED_LEADS")
gaps_now = state["data"]["gaps"]
ok(any(g.get("registry_query_grammars") for g in gaps_now),
   "gaps carry registry query grammars for role-matched research")
cov = state.get("satisfaction") or {}
ok(cov.get("core_satisfied") is True and not cov.get("missing"),
   "role coverage receipt: all core requirements satisfied")
ok(len(state.get("satisfaction_history", [])) >= 2,
   "satisfaction receipts are append-only history (causally frozen cycles)")
ok(len(state["data"]["leads"]) == 1 and state["data"]["leads"][0]["moq_units"] == 50,
   "lead carries normalized supplier economics")
_prov = {r["concept_id"]: r for r in state["data"]["provenance"]}
ok(_prov["pc1"]["verdict"] == "GROUNDED" and _prov["pc1"]["independent_voices"] >= 3 and len(_prov["pc1"]["communities"]) >= 2,
   f"provenance: a concept cited by independent voices across communities is GROUNDED ({_prov['pc1']['verdict']})")
ok(_prov["pc2"]["field_originated"] is True, "a noun that lives only in the field records is field-originated")
_u = state["data"]["utilization"]
ok(_u["lived_world"]["clusters_by_authority"].get("ANCHOR") == 2 and _u["corpus_contribution"]["rows_cited"] >= 0
   and "cited_share_of_shelf" in _u["corpus_contribution"] and _u["provenance"]["verdicts"],
   "utilization receipt carries lived-world, corpus-contribution and provenance sections")

# ---- 5. SQLite durability ---------------------------------------------------
import memory  # noqa: E402
run = memory.get_run(json.load(open(pos))["run_id"])
ok(run is not None and run["status"] == "stopped" and run["verdict"] == "QUALIFIED_LEADS",
   "run row persisted with terminal verdict")
with memory.connect() as _c:
    n_nodes = _c.execute("SELECT COUNT(*) c FROM work_nodes WHERE run_id=?", (run["run_id"],)).fetchone()["c"]
    n_events = _c.execute("SELECT COUNT(*) c FROM events WHERE run_id=?", (run["run_id"],)).fetchone()["c"]
    n_checks = _c.execute("SELECT COUNT(*) c FROM checks WHERE run_id=?", (run["run_id"],)).fetchone()["c"]
ok(n_nodes >= 15 and n_events >= 5 and n_checks >= 1,
   f"work graph mirrored ({n_nodes} nodes), audit events ({n_events}), receipts ({n_checks})")

# crash durability: a fresh run stepped past its outputs creates ONE pending action
dur = os.path.join(tmp, "dur.json")
ctl("init", "--state", dur)  # no signal: understand must park a pending action
rc1, o1 = ctl("step", "--state", dur)   # understand outputs missing -> pending action
rc2, o2 = ctl("step", "--state", dur)   # crash/retry -> SAME action
ok(rc1 == 1 and rc2 == 1 and o1.get("action_id") and o1["action_id"] == o2.get("action_id"),
   "crash-resume: re-step returns the SAME pending action, never a duplicate")
ok(o2.get("attempt") == 2, "attempt count increments on redelivery")

# idempotent submit: identical payload twice -> ALREADY_APPLIED, no dup mutation
pay = {"signal": "durability probe interpreted"}
submit(dur, "understand", pay)
rc3, o3 = submit(dur, "understand", pay)
ok(rc3 == 0 and o3.get("idempotent") == "ALREADY_APPLIED",
   "identical re-submit returns ALREADY_APPLIED")
d_state = json.load(open(dur))
ok(d_state["data"]["signal"] == "durability probe interpreted",
   "no duplicate mutation from idempotent retry")

# conflicting divergent submit for the same answered node -> hard conflict
rc4, o4 = submit(dur, "understand", {"signal": "a DIFFERENT interpretation"})
ok(rc4 == 1 and o4.get("error") == "IDEMPOTENCY_CONFLICT",
   "divergent duplicate for an answered node is a hard conflict")

# config drift blocks resume
dr = memory.get_run(d_state["run_id"])
with memory.connect() as _c:
    _c.execute("UPDATE runs SET policy_hash='deadbeef' WHERE run_id=?", (d_state["run_id"],))
rc5, o5 = ctl("step", "--state", dur)
ok(rc5 == 1 and o5.get("error") == "BLOCKED_CONFIG_DRIFT" and "policy_hash" in o5.get("drifted", []),
   "config drift -> BLOCKED_CONFIG_DRIFT, never silent resume")
with memory.connect() as _c:
    _c.execute("UPDATE runs SET policy_hash=? WHERE run_id=?", (dr["policy_hash"], d_state["run_id"]))

# terminal immutability
rc6, o6 = ctl("step", "--state", pos)
ok(rc6 == 0 and o6.get("verdict") == "QUALIFIED_LEADS" and "immutable" in str(o6.get("terminal", "")),
   "terminal run returns the same immutable result on re-step")

# ---- 5b. NICHE_LOADOUT math + graph -----------------------------------------
import loadout_math as lm  # noqa: E402
lp = graphmod.load_policies()
branches = [
 {"name": "trail_runners", "new_jobs": .8, "new_frictions": .9, "new_slots": .8,
  "insider_specificity": .7, "transfer_strength": .5, "commerce_reachability": .8,
  "redundancy": .1, "inference_distance": .2, "research_cost": .3},
 {"name": "runners_aged_31_32", "new_jobs": 0, "new_frictions": 0, "new_slots": 0,
  "insider_specificity": .1, "transfer_strength": 0, "commerce_reachability": .5,
  "redundancy": .9, "inference_distance": .1, "research_cost": .2}]
rk = lm.rank_frontier(branches, lp)
ok(rk[0]["branch"] == "trail_runners" and rk[0]["disposition"] == "EXPLORE"
   and rk[1]["disposition"] == "PRUNE",
   "frontier utility explores trail runners, prunes adjective-only split")
sg = lm.surface_gain("recreational_runners", "recreational_runners_age_31_32",
                     {"new_activities": 0, "new_frictions": 0}, lp)
ok(sg["disposition"] == "COLLAPSE_TO_PARENT", "zero-delta split collapses to parent")
sg2 = lm.surface_gain("runners", "runner_x_soldier",
                      {"new_activities": 3, "new_frictions": 5, "new_physical_jobs": 4,
                       "new_product_slots": 6}, lp)
ok(sg2["disposition"] == "KEEP_BRANCH", "high-gain intersection keeps its branch")
shorts = lambda i: {"id": f"s{i}", "quality": .9, "physical_jobs": ["stride_freedom"],
                    "moments": ["during"], "collection_roles": ["UTILITY"],
                    "mechanism_family": "shorts"}
diverse = [
 {"id": "gem", "quality": .8, "physical_jobs": ["stride_freedom"], "moments": ["during"],
  "collection_roles": ["INSIDER_GEM"], "mechanism_family": "shorts"},
 {"id": "belt", "quality": .75, "physical_jobs": ["retain_access"], "moments": ["during"],
  "collection_roles": ["UTILITY"], "mechanism_family": "belt"},
 {"id": "antichafe", "quality": .7, "physical_jobs": ["skin_protection"], "moments": ["during", "after"],
  "collection_roles": ["DISCOVERY"], "mechanism_family": "topical"},
 {"id": "wetbag", "quality": .65, "physical_jobs": ["post_run_transition"], "moments": ["after"],
  "collection_roles": ["COMPLEMENT"], "mechanism_family": "bag"}]
sel = lm.select_portfolio([shorts(i) for i in range(6)] + diverse, lp)
ok(len(set(sel["selected"]) & {"gem", "belt", "antichafe", "wetbag"}) >= 3,
   "portfolio F(S) picks the diverse set over six near-identical shorts")
ok(len(sel["covered_jobs"]) >= 3, "selected set covers multiple physical jobs")
fid_bad = lm.insider_fidelity({"situation_specificity": .2, "task_coverage": .2,
    "workaround_realism": 0, "constraint_fidelity": .2, "insider_language": .1,
    "experience_differentiation": 0, "traceability": .2, "genericness": .9}, lp)
ok(fid_bad["status"] == "FAIL_INSIDER_FIDELITY", "generic loadout fails insider fidelity")
lg = graphmod.load_graph("loadout_graph.yaml")
ok(graphmod.validate_graph(lg) == [], "loadout graph structurally valid")
lo = os.path.join(tmp, "lo.json")
rc, out = ctl("init", "--state", lo, "--graph", "loadout_graph.yaml")
ok(rc == 0 and out["node"] == "scope_intake", "controller runs the loadout graph")
submit(lo, "scope_intake", {"scope_request": {"scope_id": "runners_trail",
       "experience_level": "ADVANCED", "contexts": ["hot_weather"],
       "life_intersections": [], "rationale": "test"}})
rc, out = ctl("step", "--state", lo)
ok(out.get("advanced_to") == "frontier", "graph-generic submit specs work for new modes")

# ---- 6. report layer: views over frozen state -------------------------------
import report as repmod  # noqa: E402
model = repmod.build_model(json.load(open(pos)))
ok(model["run"]["verdict"] == "QUALIFIED_LEADS" and model["leads"] and model["coverage"],
   "ReportModel built deterministically from terminal state")
page = repmod.render(model, "FULL_RESEARCH")
ok("http" not in page.split("src=")[0][:0] and "<script src" not in page and "@import" not in page,
   "report HTML is self-contained (no external assets)")
ok(model["leads"][0]["product_name"] in page and str(model["leads"][0]["moq_units"]) in page,
   "lead economics rendered from frozen facts")
ok("Held" in page or not model["held_rejected"], "held/rejected paths shown — not sales copy")
exec_page = repmod.render(model, "EXECUTIVE")
ok(len(exec_page) < len(page), "layout modes subset the same frozen model")

# ---- 7. context engineering (docs/10) ---------------------------------------
import copy  # noqa: E402
import context as ctxmod  # noqa: E402

# 7a. envelope frozen with the pending action (reasoning replay stability)
cx = os.path.join(tmp, "cx.json")
ctl("init", "--state", cx, "--signal", "context probe signal")
ctl("step", "--state", cx)                    # understand already has signal -> corpus
rc, o1 = ctl("step", "--state", cx)           # corpus outputs missing -> pending + envelope
env1 = o1.get("context_envelope") or {}
ok(rc == 1 and env1.get("status") == "READY"
   and env1["manifest"]["required_contract_complete"] is True,
   "pending action ships a READY ContextEnvelope")
ok("hypotheses" not in env1["action_context"]["working_set"]
   and "hypotheses" in env1["action_context"]["prohibited"],
   "contract exclusions are enforced, not hoped for")
cx_state = json.load(open(cx))
cx_state["data"]["signal"] = "TAMPERED between steps"
json.dump(cx_state, open(cx, "w"))
rc, o2 = ctl("step", "--state", cx)
env2 = o2.get("context_envelope") or {}
ok(env2["manifest"]["context_hash"] == env1["manifest"]["context_hash"],
   "crash-resume returns the SAME frozen envelope, not a fresh recompile")
rc, so = ctl("status", "--state", cx)
ok((so.get("context") or {}).get("status") == "READY",
   "status reports context readiness for model-executed nodes")

# 7b. required object genuinely missing -> BLOCKED_CONTEXT_INCOMPLETE
bl = os.path.join(tmp, "bl.json")
ctl("init", "--state", bl, "--graph", "loadout_graph.yaml")
bl_state = json.load(open(bl))
bl_state["node"] = "field"
bl_state["data"]["scope_request"] = {"scope_id": "x", "scope": "trail_runners"}
json.dump(bl_state, open(bl, "w"))
rc, o = ctl("step", "--state", bl)
ok(rc == 1 and o.get("error") == "BLOCKED_CONTEXT_INCOMPLETE"
   and any(d["key"] == "research_plan" for d in o.get("deficits", [])),
   "missing required context blocks the action instead of under-specifying θ")

# 7c. deterministic backfill from the Work Graph mirror (recovery, not research)
g_ctl = graphmod.load_graph()
pol_ctx = graphmod.load_policies()
pos_state = json.load(open(pos))
lost = copy.deepcopy(pos_state)
lost["data"]["observations"] = []
lost["node"] = "mechanism"
env = ctxmod.compile_envelope(lost, g_ctl, pol_ctx)
ok(env["status"] == "READY" and "observations" in env["manifest"]["backfilled"]
   and len(env["action_context"]["working_set"]["observations"]) >= 5,
   "context backfill recovers observations from SQLite via memory.py")
ok(all(h.get("status") != "REJECTED"
       for h in env["action_context"]["working_set"]["hypotheses"]),
   "rejected branches stay out of the working set by default")

# 7d. evaluator isolation: sanitized hypotheses, no generator narrative
sst = copy.deepcopy(pos_state)
sst["node"] = "semantic_review"
sst["data"]["hypotheses"] = [dict(h, notes="PERSUASIVE NARRATIVE", research_priority=3)]
senv = ctxmod.compile_envelope(sst, g_ctl, pol_ctx)
ok(all("notes" not in x and "research_priority" not in x
       for x in senv["action_context"]["working_set"]["hypotheses"]),
   "L4 evaluator envelope is sanitized — receipts, never narrative")

# 7e. deterministic budget trim: P2 drops, P0/P1 never
pol_tight = copy.deepcopy(pol_ctx)
pol_tight.setdefault("context", {}).setdefault("budgets", {})["max_chars"] = 50
tenv = ctxmod.compile_envelope(copy.deepcopy(pos_state) | {"node": "mechanism"},
                               g_ctl, pol_tight, "mechanism")
ok("observations" in tenv["manifest"]["excluded_due_to_budget"]
   and "hypotheses" in tenv["action_context"]["working_set"],
   "budget pressure drops P2 evidence, never P1 decision-critical state")

# 7f. checkpoints + working_context.md projection
cp = memory.latest_checkpoint(pos_state["run_id"])
ok(cp is not None and cp["phase"] == "QUALIFICATION_COMPLETE"
   and cp.get("progress_signature"),
   "phase checkpoints recorded — recovery is checkpoint + deltas, not replay")
rc, o = ctl("context-export", "--state", pos)
wc = open(o["working_context"]).read()
ok(rc == 0 and "GENERATED FROM SQLITE" in wc and "DO NOT EDIT AS CANONICAL" in wc
   and pos_state["run_id"] in wc,
   "working_context.md is a one-way, reproducible projection")

# ---- 8. commercial intelligence (docs/11) -----------------------------------
import intelligence as intmod  # noqa: E402
INT = os.path.join(ROOT, "python", "intelligence.py")


def intel(*args):
    r = subprocess.run([PY, INT, *args], capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.returncode, {"raw": r.stdout, "err": r.stderr}


packet = intmod.build_packet(pos_state)
ok(packet["products"] and packet["observations"]
   and all("notes" not in b for b in packet["bridges"]),
   "generation packet is sanitized canonical receipts, no narrative")

ci = os.path.join(tmp, "ci.json")
json.dump(pos_state, open(ci, "w"))
obs_ids = [o_["id"] for o_ in pos_state["data"]["observations"]]

# 8a. research state is untouchable from this layer
with open(os.path.join(tmp, "bad_intel.json"), "w") as f:
    json.dump({"hypotheses": [{"id": "hx"}]}, f)
rc, o = intel("admit", "--state", ci, "--file", os.path.join(tmp, "bad_intel.json"))
ok(rc == 1 and "cannot mutate research state" in str(o.get("error", "")),
   "intelligence admission refuses research keys — verdict != marketing")

# 8b. fabricated lineage / weak objects rejected
bad = {"ad_angles": [{"id": "ax", "angle_type": "AD", "hook_type": "DISCOVERY",
                      "thesis": "totally real angle", "evidence_refs": ["ghost_ref"]}],
       "analysis_chains": [{"id": "chx", "evidence": [obs_ids[0]],
                            "observation": "x", "market_implication": "y",
                            "product_implication": "z", "ad_implication": "w"}],
       "style_intelligence": [{"id": "sx", "kind": "observed", "pattern": "neon"}]}
with open(os.path.join(tmp, "bad2.json"), "w") as f:
    json.dump(bad, f)
rc, o = intel("admit", "--state", ci, "--file", os.path.join(tmp, "bad2.json"))
errs = str(o.get("schema_errors", []))
ok(rc == 1 and "do not resolve" in errs, "fabricated evidence lineage fails admission")
ok("interpretation" in errs, "analysis chain with a missing link is rejected")
ok("observed style signals require" in errs,
   "observed style claims require receipts — no arbitrary branding advice")

# 8c. the real admission: grading, dedupe, genericness, portfolio
good = {
    "market_analysis": [
        {"id": "mc1", "section": "customer_community", "classification": "OBSERVED",
         "statement": "Creators tape transmitters to belts to keep moving",
         "evidence_refs": obs_ids[:3]},
        {"id": "mc2", "section": "opportunity", "classification": "OBSERVED",
         "statement": "Movement-first creators are underserved"}],
    "ad_angles": [
        {"id": "a1", "angle_type": "AD", "hook_type": "INSIDER_PROBLEM",
         "thesis": "cable tether kills expressive movement during recording",
         "tension": "you need the mic but it anchors you",
         "reveal": "wearable wireless kit", "featured_product": "p1",
         "evidence_refs": obs_ids[:2]},
        {"id": "a2", "angle_type": "AD", "hook_type": "INSIDER_PROBLEM",
         "thesis": "cable tether kills expressive movement while recording sessions",
         "evidence_refs": obs_ids[:2]},
        {"id": "a3", "angle_type": "AD", "hook_type": "PERFORMANCE",
         "thesis": "helps creators make better quality content",
         "evidence_refs": obs_ids[:2]},
        {"id": "a4", "angle_type": "AD", "hook_type": "SEASONAL",
         "thesis": "outdoor festival season forces untethered capture setups",
         "evidence_refs": []},
        {"id": "a5", "angle_type": "AD", "hook_type": "DISCOVERY",
         "thesis": "most storytellers never learn wearable capture kits exist",
         "evidence_refs": obs_ids[2:3]}],
    "analysis_chains": [
        {"id": "ch1", "evidence": obs_ids[:2],
         "observation": "creators improvise belt-taped transmitters",
         "interpretation": "movement outranks audio convenience",
         "market_implication": "movement-first creators are a distinct segment",
         "product_implication": "prioritize wearable, cable-free capture",
         "ad_implication": "lead with the moment the cable snaps taut"}],
    "creative_briefs": [
        {"id": "b1", "angle_id": "a1", "objective": "DISCOVERY",
         "target": {"niche": "storytelling_creators"},
         "hook": "Your mic is choreographing you",
         "tension": "the cable decides where you stand",
         "reveal": "clip-on wireless kit", "evidence_refs": obs_ids[:2],
         "claim_boundaries": ["no audio-quality superiority claims"],
         "slides": [{"function": "HOOK", "message": "Who is really directing?"},
                    {"function": "PRODUCT_REVEAL"}]}],
    "storefront_strategies": [
        {"id": "sf1", "scope": "storytelling_creators",
         "positioning": "gear that disappears while you perform",
         "content_pillars": ["movement_first", "capture_without_choreography"]}],
    "style_intelligence": [
        {"id": "st1", "kind": "inferred",
         "direction": "documentary stage-light minimalism"}],
}
with open(os.path.join(tmp, "good_intel.json"), "w") as f:
    json.dump(good, f)
rc, o = intel("admit", "--state", ci, "--file", os.path.join(tmp, "good_intel.json"))
ok(rc == 0 and o["ok"], f"evidence-grounded intelligence admitted ({str(o)[:120]})")
ci_state = json.load(open(ci))
angles = {a["id"]: a for a in ci_state["data"]["ad_angles"]}
ok(angles["a1"]["evidence_state"] == "GROUNDED" and angles["a1"]["disposition"] == "ADVANCE",
   "2+ resolving refs -> GROUNDED ADVANCE (authority computed, not claimed)")
ok(angles["a2"]["disposition"] == "REJECT", "near-duplicate thesis rejected — one angle, once")
ok(angles["a3"]["disposition"] == "REJECT", "generic 'helps make better content' angle rejected")
ok(angles["a4"]["disposition"] == "HOLD" and angles["a4"]["evidence_state"] == "SPECULATIVE",
   "unreferenced angle is SPECULATIVE and held, never advanced")
claims = {c["id"]: c for c in ci_state["data"]["market_analysis"]}
ok(claims["mc2"]["classification"] == "INFERRED"
   and any(r["check"] == "OBSERVED_DOWNGRADED" for r in o["receipts"]),
   "OBSERVED without receipts is downgraded to INFERRED with a receipt")
ok(len(set((o["angle_portfolio"] or {}).get("covered_hooks", []))) >= 2,
   "angle portfolio optimizes hook-type coverage as a SET")
ok(ci_state["verdict"] == "QUALIFIED_LEADS" and ci_state["status"] == "stopped",
   "admission never touches the research verdict")
ok(ci_state["data"]["storefront_strategies"][0]["authority"] == "CREATIVE_RECOMMENDATION",
   "unreferenced storefront thesis is a CREATIVE_RECOMMENDATION, not analysis")
with memory.connect() as _c:
    n_ang = _c.execute("SELECT COUNT(*) c FROM work_nodes WHERE run_id=? AND node_type='AD_ANGLE'",
                       (ci_state["run_id"],)).fetchone()["c"]
ok(n_ang >= 5, "angles mirrored as first-class Work Graph objects")

# 8d. report projection with authority markers
imodel = repmod.build_model(ci_state)
ok(imodel["intelligence"] and imodel["intelligence"]["angles"], "ReportModel carries intelligence")
ipage = repmod.render(imodel, "FULL_RESEARCH")
ok("Angle Portfolio" in ipage and "evidence-backed" in ipage and "●" in ipage,
   "report renders angle matrix with authority markers")
cpage = repmod.render(imodel, "COMMERCIAL")
ok("Analysis Chains" in cpage and "Storefront Thesis" in cpage,
   "COMMERCIAL layout projects chains and storefront strategy")
ok("QUALIFIED_LEADS" in cpage, "creative layer surfaces but never rewrites the verdict")

# ---- 9. MARKET_DISCOVERY + PRODUCT_ANCHORED (docs/12-14) --------------------
import market_math as mmath  # noqa: E402
import product_market_math as pmm  # noqa: E402
from models import stable_id  # noqa: E402

polx = graphmod.load_policies()

# 9a. deterministic math receipts
rc_strong = mmath.market_frontier_utility(
    {"id": "s1", "features": {"attention": .5, "community": .9, "whitespace": .8,
                              "job_richness": .7, "currentness": .8, "sourceability": .6,
                              "transfer": .3, "redundancy": .1, "saturation": .2}}, polx)
ok(rc_strong["disposition"] == "EXPLORE" and rc_strong["config_hash"]
   and rc_strong["formula"] == "market_frontier_v1" and rc_strong["weights"],
   "M(s) ships a full receipt (formula, inputs, weights, config hash) — never a bare score")
div = mmath.detect_divergence({"search_interest": .2, "community_activity": .8,
                               "commerce_supply": .2, "product_saturation": .1,
                               "workaround_density": .7}, polx)
ok("EARLY_EMERGENCE" in div["patterns"] and "PRE_CATEGORY" in div["patterns"]
   and "COMMUNITY_COMMERCE_GAP" in div["patterns"],
   "channel disagreement detected as named patterns — divergence IS information")
div2 = mmath.detect_divergence({"search_interest": .9, "community_activity": .2,
                                "commerce_supply": .8, "product_saturation": .9,
                                "workaround_density": .1}, polx)
ok(div2["patterns"] == ["MATURE_COMMODITY"], "high search + huge supply + quiet community = commodity")
stab = mmath.rank_stability(
    [{"id": "a", "features": {"attention": .9, "community": .9}},
     {"id": "b", "features": {"attention": .1, "community": .1}}],
    polx["market_discovery"]["frontier"]["weights"], 0.2)
ok(stab["status"] == "STABLE", "dominant ranking is STABLE under weight perturbation")
weak_bridge = pmm.reverse_fit_utility(
    {"id": "bx", "features": {"mechanism_fit": .3, "job_fit": .2, "community_richness": .1,
                              "language_coherence": .2, "currentness": .3, "differentiation": .1,
                              "ecommerce_compatibility": .5, "assumption_distance": .9,
                              "saturation": .9, "redundancy": .5}}, polx)
ok(weak_bridge["disposition"] == "PRUNE",
   "assumption-heavy saturated bridge gets PRUNED by R(n|p)")

# 9b. graphs validate
for gname in ("market_discovery_graph.yaml", "product_anchored_graph.yaml"):
    gg = graphmod.load_graph(gname)
    ok(graphmod.validate_graph(gg) == [], f"{gname} structurally valid incl. ContextContracts")

# 9c. MARKET_DISCOVERY E2E walk
md = os.path.join(tmp, "md.json")
ctl("init", "--state", md, "--graph", "market_discovery_graph.yaml", "--signal", "running")
submit(md, "market_intake", {"market_seed": {
    "market": "running", "canonical_identity": "recreational and competitive running as lived activity",
    "aliases": ["run", "jogging"]}})
ctl("step", "--state", md)   # -> field_lane
submit(md, "field_lane", {"field_signals": [
    {"id": "f1", "origin": "FIELD", "kind": "STYLE_SIGNAL",
     "summary": "run clubs converging on retro high-split shorts", "source": "reddit.com/r/running"},
    {"id": "f2", "origin": "FIELD", "kind": "COMMUNITY",
     "summary": "urban run-club culture with distinct vocabulary", "source": "instagram"},
    {"id": "f3", "origin": "FIELD", "kind": "CURRENT_FRICTION",
     "summary": "phone bounce complaints on long runs", "source": "reddit.com/r/AdvancedRunning"}]})
ctl("step", "--state", md)   # -> trend_lane
submit(md, "trend_lane", {"trend_signals": [
    {"id": "t1", "origin": "TRENDS", "kind": "QUERY_CLUSTER",
     "summary": "high split running shorts rising; jogging shorts migrating to split shorts"}]})
rc, out = ctl("step", "--state", md)   # -> corpus_lane
md_state = json.load(open(md))
cenv = ctxmod.compile_envelope(md_state, graphmod.load_graph("market_discovery_graph.yaml"), polx)
ok("field_signals" not in cenv["action_context"]["working_set"]
   and "trend_signals" not in cenv["action_context"]["working_set"],
   "corpus lane envelope is BLIND to field/trend lanes — no anchoring before merge")
submit(md, "corpus_lane", {"corpus_signals": [
    {"id": "c1", "origin": "CORPUS", "kind": "TRANSFERABLE_INVARIANT",
     "summary": "interruption cost: people hate stopping a primary activity to access an object"}]})
ctl("step", "--state", md)   # -> supply_lane
submit(md, "supply_lane", {"supply_signals": [
    {"id": "sp1", "origin": "SUPPLY", "kind": "PRODUCT_FAMILY",
     "summary": "no-bounce belt and split-short manufacturing families reachable"}]})
ctl("step", "--state", md)   # supply -> merge_signals
rc, out = ctl("step", "--state", md)   # merge -> query_graph
md_state = json.load(open(md))
ok(len(md_state["data"].get("signal_provenance", {})) >= 4,
   "lanes merged with per-origin provenance preserved")
submit(md, "query_graph", {"query_nodes": [
    {"id": "q1", "query": "high split running shorts", "origin": "TREND_RELATED",
     "parent_ids": [], "semantic_cluster": "minimal_high_mobility_shorts"},
    {"id": "q2", "query": "run club gear", "origin": "COMMUNITY_LANGUAGE",
     "semantic_cluster": "run_club_culture"}]})
ctl("step", "--state", md)   # -> lattice
_F = lambda **kw: {**{"attention": .3, "community": .3, "whitespace": .3, "job_richness": .4,
                      "currentness": .4, "sourceability": .5, "transfer": .2,
                      "redundancy": .1, "saturation": .3}, **kw}
submit(md, "lattice", {"market_scopes": [
    {"id": "sc_club", "market": "running", "niche": "run club runners",
     "subniche": "style-forward urban run clubs", "origin": "FIELD",
     "dimensions": {"social": "run_club", "context": "urban"},
     "features": _F(attention=.5, community=.9, whitespace=.8, currentness=.8, sourceability=.35)},
    {"id": "sc_hot", "market": "running", "niche": "distance running",
     "subniche": "high mileage hot weather", "origin": "TRENDS",
     "dimensions": {"experience": "high_mileage", "context": "hot_weather"},
     "features": _F(attention=.3, community=.7, whitespace=.7, job_richness=.8, sourceability=.3)},
    {"id": "sc_dog", "market": "running", "niche": "dog running",
     "origin": "CORPUS", "dimensions": {"life_intersection": "runner_x_dog_owner"},
     "features": _F(community=.5, whitespace=.5)},
    {"id": "sc_club_dup", "market": "running", "niche": "run club runners",
     "subniche": "urban run clubs", "origin": "THETA",
     "dimensions": {"social": "run_club", "context": "urban"},
     "features": _F(community=.5, whitespace=.4)}]})
ctl("step", "--state", md)             # lattice -> market_frontier
rc, out = ctl("step", "--state", md)   # frontier executes -> community_sampling
md_state = json.load(open(md))
scopes = {s["id"]: s for s in md_state["data"]["market_scopes"]}
ok(scopes["sc_club"]["status"] == "RETAINED" and scopes["sc_club_dup"]["status"] == "COLLAPSED",
   "diversity-aware frontier keeps the diverse set, collapses the near-duplicate scope")
ok(md_state["data"]["market_frontier_receipts"][0]["config_hash"]
   and md_state["data"]["market_frontier_stability"]["status"] in ("STABLE", "SENSITIVE", "HIGHLY_SENSITIVE"),
   "frontier decision persisted with receipts + robustness status")
_SRC = lambda i: {"source_family": "community", "platform": "reddit",
                  "author_key": f"md_a{i}", "thread_key": f"md_t{i}"}
submit(md, "community_sampling", {"observations": [
    {"id": f"mo{i}", "gap_id": "sampling:sc_club", "scope_id": "sc_club",
     "source": f"reddit.com/r/running/club{i}", "quote_ref": f"our club kits beat shop gear {i}", "query_used": "run club kit vs shop gear",
     "community": "run clubs", "problem": "generic retail assortments",
     "workaround": "clubs make their own kit",
     "evidence_roles": ["WORKAROUND_EVIDENCE" if i else "FRICTION_EVIDENCE"],
     "freshness": {"class": "LIVE"}, "source_identity": _SRC(i)} for i in range(3)]})
ctl("step", "--state", md)   # -> curate
ctl("step", "--state", md)   # curate -> divergence
ctl("step", "--state", md)             # divergence -> gap_analysis
rc, out = ctl("step", "--state", md)   # gap_analysis -> whitespace
md_state = json.load(open(md))
divs = {d_["scope_id"]: d_ for d_ in md_state["data"]["signal_divergences"]}
ok("COMMUNITY_COMMERCE_GAP" in divs["sc_club"]["patterns"]
   and "EARLY_EMERGENCE" in divs["sc_hot"]["patterns"],
   "per-scope SignalDivergence computed from channel features + workaround density")
submit(md, "whitespace", {"whitespace_hypotheses": [
    {"id": "wh1", "market_scope_id": "sc_club", "type": "CURATION_WHITESPACE",
     "genesis": "COMMUNITY_LED",
     "observed_mismatch": "distinct club culture and vocabulary vs generic running retail",
     "supporting_signals": ["f1", "f2"], "physical_jobs": ["club_identity_display"],
     "next_validation": ["club members complain shops sell generic gear"]},
    {"id": "wh2", "market_scope_id": "sc_hot", "type": "PRODUCT_WHITESPACE",
     "genesis": "PROBLEM_LED",
     "observed_mismatch": "hot-weather high-mileage carry complaints vs unchanged products",
     "next_validation": ["repeated complaints about hot-weather carry"]}],
    "demand_reroutes": [
    {"id": "rr1", "existing_demand": "running shorts everyone already buys",
     "incumbent_solution": "generic performance shorts", "reroute_dimension": "IDENTITY",
     "target_scope": "sc_club", "new_positioning": "club-culture editorial shorts",
     "why_existing_demand_transfers": "same product, community identity route",
     "evidence_refs": ["f1"]}]})
ctl("step", "--state", md)             # whitespace -> market_gaps
rc, out = ctl("step", "--state", md)   # gaps compile -> targeted_research (round open)
ok(out.get("advanced_to") == "targeted_research", "open whitespace gaps route to targeted research")
md_state = json.load(open(md))
wh1_gap = next(g["id"] for g in md_state["data"]["gaps"] if g.get("whitespace_id") == "wh1")
submit(md, "targeted_research", {"observations": [
    {"id": f"mv{i}", "gap_id": wh1_gap,
     "source": f"reddit.com/r/RunClubs/v{i}", "quote_ref": f"shops only stock generic marathon stuff {i}", "query_used": "club kit complaints generic retail",
     "community": "run clubs", "problem": "no curated club-culture gear",
     "evidence_roles": ["FRICTION_EVIDENCE"], "freshness": {"class": "LIVE"},
     "source_identity": {"source_family": "community", "platform": "reddit",
                         "author_key": f"mv_a{i}", "thread_key": f"mv_t{i}"}} for i in range(3)]})
ctl("step", "--state", md)   # targeted -> revise
rc, out = ctl("step", "--state", md)   # revise -> market_gaps -> (done) skeptic
md_state = json.load(open(md))
wh = {w["id"]: w for w in md_state["data"]["whitespace_hypotheses"]}
ok(wh["wh1"]["state"] == "SUPPORTED", "field evidence moves whitespace to SUPPORTED — θ never does")
rc, out = ctl("step", "--state", md)
ok(out.get("advanced_to") == "entry_surface",
   "bounded research loop exits to capture-feasibility assessment")
_CD = lambda **kw: {**{"competitor_fragmentation": .6, "incumbent_lock_in": .2,
                       "differentiation_clarity": .6, "switching_friction": .2,
                       "niche_specificity": .6, "organic_contentability": .6,
                       "visual_demonstrability": .6, "creator_channel_fit": .6,
                       "supplier_flexibility": .5, "margin_room": .5,
                       "trust_barrier": .2, "regulatory_burden": .1}, **kw}
submit(md, "entry_surface", {"capture_assessments": [
    {"id": "ca1", "scope_id": "sc_club", "dimensions": _CD(niche_specificity=.9),
     "evidence_refs": ["f1", "f2"]},
    {"id": "ca2", "scope_id": "sc_hot", "dimensions": _CD(), "evidence_refs": ["mo0"]}]})
ctl("step", "--state", md)             # entry_surface -> capture_gate
rc, out = ctl("step", "--state", md)   # capture_gate -> market_skeptic
md_state = json.load(open(md))
ok(all(a.get("result") in ("EASY_ENTRY", "PLAUSIBLE") for a in md_state["data"]["capture_assessments"])
   and md_state["data"]["capture_receipts"][0]["config_hash"],
   "capture feasibility judged categorically with receipts — never a share probability")
ok(any(g["gap_type"] == "CHANNEL_GAP" for g in md_state["data"]["demand_gaps"])
   and any(g["gap_type"] == "CURATION_GAP" for g in md_state["data"]["demand_gaps"]),
   "demand gap analysis typed the mismatches (channel + curation, not just unmet need)")
submit(md, "market_skeptic", {"evaluations": [
    {"id": "mev1", "hypothesis_id": "wh1", "verdict": "PASS",
     "reasons": ["culture-commerce mismatch has receipts from 6 independent authors"]},
    {"id": "mev2", "hypothesis_id": "wh2", "verdict": "REJECT",
     "reasons": ["complaints unvalidated this run; divergence alone can carry the scope"]}]})
ctl("step", "--state", md)   # skeptic -> apply
ctl("step", "--state", md)   # apply -> promotion
rc, out = ctl("step", "--state", md)   # promotion -> stop
md_state = json.load(open(md))
ok(md_state["status"] == "stopped" and md_state["verdict"] == "MARKET_SCOPES_READY",
   "market discovery terminates MARKET_SCOPES_READY")
promoted = {p["scope_id"]: p for p in md_state["data"]["promoted_scopes"]}
ok("sc_club" in promoted and promoted["sc_club"]["recommended_mode"] == "NICHE_LOADOUT",
   "curation whitespace promotes with NICHE_LOADOUT recommendation")
ok("sc_hot" in promoted and "EARLY_EMERGENCE" in promoted["sc_hot"]["divergence_patterns"],
   "a scope can promote on divergence patterns even after its whitespace was L4-rejected")
ok("sc_dog" not in promoted, "quiet scope without whitespace or divergence stays unpromoted")

# 9d. handoff creates a child run with an explicit packet, never mutates parent
child = os.path.join(tmp, "child_nl.json")
rc, out = ctl("handoff", "--state", md, "--to-mode", "niche_loadout",
              "--scope", "sc_club", "--out", child)
ok(rc == 0 and out["mode"] == "niche_loadout" and out["entry"] == "scope_intake",
   "handoff spawns a NICHE_LOADOUT child at its entry node")
ch_state = json.load(open(child))
pkt = ch_state["data"]["handoff_packet"]
ok(pkt["source_run"] == md_state["run_id"] and pkt["promoted_scope"]["scope_id"] == "sc_club"
   and pkt["authority_boundaries"] and "sc_club_dup" in pkt["prior_rejections"],
   "HandoffPacket carries promoted scope, authority laws and prior rejections — not the whole context")
ok(json.load(open(md))["verdict"] == "MARKET_SCOPES_READY",
   "parent run type/verdict untouched by handoff")
with memory.connect() as _c:
    n_h = _c.execute("SELECT COUNT(*) c FROM events WHERE run_id=? AND event_type='HANDOFF'",
                     (md_state["run_id"],)).fetchone()["c"]
ok(n_h == 1, "handoff recorded as a durable parent event")

# 9e. PRODUCT_ANCHORED: unresolved identity refuses to proceed
pab = os.path.join(tmp, "pa_bad.json")
ctl("init", "--state", pab, "--graph", "product_anchored_graph.yaml", "--signal", "mystery object")
submit(pab, "product_intake", {"product_seed": {"user_name": "mystery walnuts",
                                                "description": "unknown paired nuts"}})
ctl("step", "--state", pab)
submit(pab, "identity_resolution", {"product_identity": {
    "id": "pid_bad", "canonical_name": "unknown", "identity_state": "AMBIGUOUS"}})
ctl("step", "--state", pab)            # -> identity_gate
rc, out = ctl("step", "--state", pab)  # gate -> stop
pab_state = json.load(open(pab))
ok(pab_state["status"] == "stopped" and pab_state["verdict"] == "PRODUCT_IDENTITY_UNRESOLVED",
   "ambiguous product identity terminates instead of researching a guess")

# 9f. PRODUCT_ANCHORED E2E: wenwan walnuts (the docs/14 canary)
pa = os.path.join(tmp, "pa.json")
ctl("init", "--state", pa, "--graph", "product_anchored_graph.yaml",
    "--signal", "sell chinese jade walnuts as stress relief")
submit(pa, "product_intake", {"product_seed": {
    "user_name": "chinese jade walnuts",
    "description": "matched pair of large textured walnuts, polished with handling",
    "user_hypotheses": ["stress relief gadget for men 30-55"],
    "seller_claims": ["relieves stress and improves health", "rare aged walnuts"]}})
ctl("step", "--state", pa)
submit(pa, "identity_resolution", {"product_identity": {
    "id": "pid1", "user_name": "chinese jade walnuts", "canonical_name": "wenwan walnuts",
    "aliases": ["play walnuts", "chinese hand walnuts", "baoding-style walnuts"],
    "identity_state": "PROBABLE"}})
ctl("step", "--state", pa)             # -> identity_gate
ctl("step", "--state", pa)             # gate -> claim_quarantine
rc, out = ctl("step", "--state", pa)   # quarantine -> pa_query_graph
pa_state = json.load(open(pa))
claims = pa_state["data"]["product_claims"]
ok(len(claims) == 3 and all(c["state"] == "UNVERIFIED" for c in claims),
   "user + seller claims quarantined UNVERIFIED — seller copy is not evidence")
health_claim_id = stable_id("claim", "SELLER", "relieves stress and improves health")
submit(pa, "pa_query_graph", {"query_nodes": [
    {"id": "pq1", "query": "wenwan walnuts", "origin": "USER"},
    {"id": "pq2", "query": "play walnuts pair", "origin": "COMMUNITY_LANGUAGE"}]})
rc, out = ctl("step", "--state", pa)   # -> blind_field
benv = out.get("context_envelope") or ctxmod.compile_envelope(
    json.load(open(pa)), graphmod.load_graph("product_anchored_graph.yaml"), polx)
ws = benv["action_context"]["working_set"]
ok("product_seed" not in ws and "product_claims" not in ws and "product_identity" in ws,
   "blind field lane sees identity + aliases ONLY — never the seller's story")
submit(pa, "blind_field", {"field_signals": [
    {"id": "pf1", "origin": "FIELD", "kind": "COMMUNITY",
     "summary": "collector forums trade matched pairs, discuss patina development",
     "source": "reddit.com/r/wenwan"},
    {"id": "pf2", "origin": "FIELD", "kind": "CURRENT_TOPIC",
     "summary": "buyers compare pairing, size, skin texture — never health effects",
     "source": "etsy reviews"}]})
ctl("step", "--state", pa)             # -> corpus_lane
submit(pa, "corpus_lane", {"corpus_signals": [
    {"id": "pc1", "origin": "CORPUS", "kind": "BEHAVIORAL_MECHANISM",
     "summary": "collecting behavior: progression, grading, display, care rituals"}]})
ctl("step", "--state", pa)             # -> commerce_scan
submit(pa, "commerce_scan", {"commerce_signals": [
    {"id": "pm1", "origin": "COMMERCE", "kind": "POSITIONING",
     "summary": "etsy listings split between hand-exercise framing and collector framing"}]})
ctl("step", "--state", pa)             # -> merge
ctl("step", "--state", pa)             # merge -> meanings
submit(pa, "meanings", {"product_meanings": [
    {"id": "m_collect", "type": "COLLECTOR", "interaction": "repeated handling and pair evaluation",
     "lived_situation": "desk and display collecting", "job": "collection_progression",
     "inference_distance": 1, "evidence_refs": ["pf1", "pc1"]},
    {"id": "m_wellness", "type": "FUNCTIONAL", "interaction": "hand rolling",
     "lived_situation": "stress relief at desk", "job": "stress_reduction",
     "inference_distance": 3},
    {"id": "m_gift", "type": "GIFT", "interaction": "gifting",
     "lived_situation": "cultural gift occasions", "job": "meaningful_gift",
     "inference_distance": 2}]})
ctl("step", "--state", pa)             # -> bridges
_BF = lambda **kw: {**{"mechanism_fit": .5, "job_fit": .5, "community_richness": .3,
                       "language_coherence": .4, "currentness": .4, "differentiation": .4,
                       "ecommerce_compatibility": .6, "assumption_distance": .4,
                       "saturation": .4, "redundancy": .1}, **kw}
submit(pa, "bridges", {"market_bridges": [
    {"id": "b_collect", "meaning_id": "m_collect", "market_scope": "wenwan collectors",
     "jobs": ["tactile_hobby", "collection_progression"],
     "features": _BF(mechanism_fit=.8, job_fit=.8, community_richness=.9,
                     language_coherence=.8, assumption_distance=.2, saturation=.3)},
    {"id": "b_wellness", "meaning_id": "m_wellness", "market_scope": "stress relief gadget buyers",
     "jobs": ["stress_reduction"],
     "features": _BF(community_richness=.2, assumption_distance=.7, saturation=.7)},
    {"id": "b_gift", "meaning_id": "m_gift", "market_scope": "cultural gift shoppers",
     "jobs": ["meaningful_gift"], "features": _BF()}]})
ctl("step", "--state", pa)             # bridges -> reverse_fit
rc, out = ctl("step", "--state", pa)   # reverse_fit executes -> community_research
pa_state = json.load(open(pa))
bst = {b["id"]: b["state"] for b in pa_state["data"]["market_bridges"]}
ok(bst["b_collect"] == "RETAINED" and bst["b_gift"] == "RETAINED" and bst["b_wellness"] == "PRUNED",
   "R(n|p) funds real communities and PRUNES the invented stress-relief persona pre-research")
ok(pa_state["data"]["reverse_fit_receipts"][0]["formula"] == "reverse_fit_v1"
   and pa_state["data"]["reverse_fit_stability"]["status"] in ("STABLE", "SENSITIVE", "HIGHLY_SENSITIVE"),
   "reverse-fit decision persisted with receipts + robustness status")
_PSRC = lambda i: {"source_family": "community", "platform": "reddit",
                   "author_key": f"pa_a{i}", "thread_key": f"pa_t{i}"}
submit(pa, "community_research", {"observations": [
    *[{"id": f"po{i}", "gap_id": "sampling:b_collect", "bridge_id": "b_collect",
       "source": f"reddit.com/r/wenwan/{i}", "quote_ref": f"took 2 years to match this pair {i}",
       "community": "wenwan collectors", "problem": "finding matched pairs",
       "workaround": "trade within collector groups",
       "evidence_roles": ["BEHAVIOR_SUPPORT" if i else "PURCHASE_INTENT"],
       "freshness": {"class": "LIVE"}, "source_identity": _PSRC(i)} for i in range(3)],
    {"id": "po_con", "gap_id": "sampling:b_wellness", "bridge_id": "b_wellness",
     "contradicts": True, "contradicts_claims": [health_claim_id],
     "source": "reddit.com/r/wenwan/health", "quote_ref": "the health claims are marketing nonsense",
     "community": "wenwan collectors", "problem": "sellers pushing health framing",
     "evidence_roles": ["CONTRADICTION"], "freshness": {"class": "LIVE"},
     "source_identity": _PSRC(9)}]})
ctl("step", "--state", pa)             # community -> revise_bridges
rc, out = ctl("step", "--state", pa)   # revise -> bridge_gaps
pa_state = json.load(open(pa))
bstates = {b["id"]: b["state"] for b in pa_state["data"]["market_bridges"]}
ok(bstates["b_collect"] == "SUPPORTED" and bstates["b_wellness"] == "PRUNED",
   "field evidence supports the collector bridge; the pruned persona stays dead")
cstates = {c["id"]: c["state"] for c in pa_state["data"]["product_claims"]}
ok(cstates[health_claim_id] == "CONTRADICTED",
   "quarantined health claim audited CONTRADICTED by community evidence")
rc, out = ctl("step", "--state", pa)   # bridge_gaps -> targeted_research (b_gift open)
ok(out.get("advanced_to") == "targeted_research", "under-evidenced retained bridge gets a targeted round")
pa_state = json.load(open(pa))
gift_gap = next(g["id"] for g in pa_state["data"]["gaps"] if g.get("bridge_id") == "b_gift")
submit(pa, "targeted_research", {"observations": [
    {"id": "pg1", "gap_id": gift_gap, "bridge_id": "b_gift",
     "source": "etsy.com/gift-reviews", "quote_ref": "bought as a retirement gift, he loved it",
     "community": "gift buyers", "problem": "meaningful gifts for older men",
     "evidence_roles": ["PURCHASE_INTENT"], "freshness": {"class": "LIVE"},
     "source_identity": {"source_family": "review", "platform": "etsy",
                         "author_key": "pg_a1", "thread_key": "pg_t1"}}]})
ctl("step", "--state", pa)             # targeted -> revise (round 2)
ctl("step", "--state", pa)             # revise executes -> bridge_gaps
rc, out = ctl("step", "--state", pa)   # gaps done -> reframe
submit(pa, "reframe", {"market_reframes": [
    {"id": "rf1", "initial_user_frame": "stress relief gadget",
     "user_frame_state": "CONTRADICTED",
     "evidence_supported_frame": "collectible hobby object (wenwan practice)",
     "why": "owner communities discuss pairing, patina and progression; they mock health framing",
     "proposed_repositioning": "collector-grade matched pairs with provenance and care guidance",
     "adjacent_products": ["walnut care brush", "display stands", "rotation cases"],
     "adjacent_markets": ["desk fidget collectors"],
     "evidence_refs": ["po0", "po_con"]}]})
ctl("step", "--state", pa)             # reframe -> skeptic
submit(pa, "skeptic", {"evaluations": [
    {"id": "pev1", "hypothesis_id": "b_collect", "verdict": "PASS",
     "reasons": ["owner voices, insider terminology, purchase language all present"]},
    {"id": "pev2", "hypothesis_id": "b_gift", "verdict": "REJECT",
     "reasons": ["single review; gift frame projected, no community"]}]})
ctl("step", "--state", pa)             # skeptic -> apply
ctl("step", "--state", pa)             # apply -> bridge_gate
rc, out = ctl("step", "--state", pa)   # gate -> stop
pa_state = json.load(open(pa))
ok(pa_state["status"] == "stopped" and pa_state["verdict"] == "PRODUCT_REFRAMED",
   "canary outcome: evidence REFRAMES the user's stress-relief thesis to the collector market")
ok(pa_state["data"]["top_bridges"] and pa_state["data"]["top_bridges"][0]["id"] == "b_collect",
   "strongest defensible bridge survives L4 and lands in top_bridges")

# 9g. reports project both modes with authority marks
md_model = repmod.build_model(md_state)
md_page = repmod.render(md_model, "FULL_RESEARCH")
ok("Market Map" in md_page and "NICHE_LOADOUT" in md_page and "Whitespace" in md_page,
   "market discovery report renders the market map + promoted scopes")
pa_model = repmod.build_model(pa_state)
pa_page = repmod.render(pa_model, "FULL_RESEARCH")
ok("wenwan walnuts" in pa_page and "Claim audit" in pa_page
   and "Market Reframe" in pa_page and "CONTRADICTED" in pa_page,
   "product-anchored report shows identity, claim audit and the reframe")

# ---- 10. v1 qualification: config, settings, ops, traps (docs/15) -----------
import doctor  # noqa: E402
import settings as setmod  # noqa: E402
import verifiers as vermod  # noqa: E402
import yaml as _yaml  # noqa: E402

# 10a. fail-closed configuration
res = doctor.run()
ok(res["ok"] and res["errors"] == [], f"doctor: full config lint is clean ({res['errors'][:2]})")
try:
    graphmod.loads("a: 1\nb: 2\na: 3")
    ok(False, "duplicate YAML keys rejected")
except _yaml.YAMLError:
    ok(True, "duplicate YAML keys rejected at the loader — fail closed, never last-wins")
bad_graph = os.path.join(ROOT, "graph", "zz_doctor_trap.yaml")
with open(bad_graph, "w") as f:
    f.write("""graph: {id: trap, version: 0.0.1, entry: a}
nodes:
  a: {type: wizard, outputs: [nonsense_key]}
  b: {type: reason, prompt: does_not_exist, outputs: [signal],
      context: {require: [signal], evidence_roles: [FAKE_ROLE]}}
  c: {type: agent, executor: some_agent, outputs: [observations]}
  stop: {type: terminal}
edges:
  - {from: a, to: b, when: imaginary_condition}
  - {from: b, to: c}
  - {from: c, to: stop}
""")
try:
    errs = doctor.check_graph_file("zz_doctor_trap.yaml")
finally:
    os.unlink(bad_graph)
joined = " | ".join(errs)
ok("unknown node type" in joined and "imaginary_condition" in joined
   and "nonsense_key" in joined and "FAKE_ROLE" in joined
   and "does_not_exist" in joined and "missing ContextContract" in joined,
   "doctor catches unknown types, conditions, keys, roles, prompts and missing contracts")

# 10b. settings: user can tighten, never weaken
r1 = setmod.resolve({"community_strength": "VERY_STRONG"})
ok(r1["resolved"]["community_strength"] == "VERY_STRONG" and r1["hash"],
   "USER_SAFE override resolves into a hashed snapshot")
for bad_ov, why in ((({"evidence.min_independent_sources": 1}), "SYSTEM_LOCKED refused"),
                    (({"market_discovery.breadth": "EXTREME"}), "value outside allowed[] refused"),
                    (({"made.up.setting": 1}), "unknown setting refused")):
    try:
        setmod.resolve(bad_ov)
        ok(False, why)
    except ValueError:
        ok(True, why)
try:
    setmod.apply_overrides_mid_run({"settings": r1},
                                   {"market_discovery.max_research_rounds": 1})
    ok(False, "immutable setting refused mid-run")
except ValueError:
    ok(True, "immutable setting refused mid-run — resolved once, pinned by hash")
sfile = os.path.join(tmp, "settings.json")
json.dump({"market_discovery.max_research_rounds": 1}, open(sfile, "w"))
sst_run = os.path.join(tmp, "settings_run.json")
rc, out = ctl("init", "--state", sst_run, "--graph", "market_discovery_graph.yaml",
              "--signal", "probe", "--settings", sfile)
ok(rc == 0 and out.get("settings_hash"), "init pins the resolved settings hash to the run")
sst_state = json.load(open(sst_run))
sst_state["rounds"]["research"] = 1
sst_state["data"]["gaps"] = [{"id": "g1", "status": "open"}]
import transitions as trmod  # noqa: E402
ok(trmod.market_research_needed(sst_state, polx) is False,
   "ADVANCED_SAFE round cap actually bounds the research loop")
sst_state["settings"] = None
ok(trmod.market_research_needed(sst_state, polx) is True,
   "without the override, the policy default (2 rounds) governs")
json.dump({"evidence.min_independent_sources": 1}, open(sfile, "w"))
rc, out = ctl("init", "--state", os.path.join(tmp, "locked.json"),
              "--graph", "market_discovery_graph.yaml", "--settings", sfile)
ok(rc == 1 and out.get("error") == "SETTINGS_REJECTED",
   "init refuses a run whose settings try to weaken evidence laws")

# 10c. operational lifecycle controls
opsr = os.path.join(tmp, "ops.json")
ctl("init", "--state", opsr, "--signal", "ops probe")
rc, out = ctl("pause", "--state", opsr)
ok(rc == 0 and out["status"] == "paused", "pause is a first-class user control")
rc, out = ctl("step", "--state", opsr)
ok(rc == 1 and out.get("error") == "RUN_PAUSED", "step refuses while paused")
rc, out = submit(opsr, "understand", {"signal": "should not land"})
ok(rc == 1 and out.get("error") == "RUN_PAUSED", "submit refuses while paused")
partial = repmod.render(repmod.build_model(json.load(open(opsr))), "EXECUTIVE")
ok("IN PROGRESS" in partial, "a paused run still yields an honest partial report")
rc, out = ctl("resume", "--state", opsr)
ok(rc == 0 and out["status"] == "running", "resume continues exactly where it paused")
rc, out = ctl("abandon", "--state", opsr, "--reason", "operator changed priorities")
ok(rc == 0 and out["verdict"] == "ABANDONED", "abandon terminates cleanly with a reason")
rc, out = ctl("step", "--state", opsr)
ok(rc == 0 and "immutable" in str(out.get("terminal", "")), "an abandoned run is immutable")
rc, out = ctl("abandon", "--state", opsr)
ok(rc == 1, "double-abandon refused — terminal runs never change")

# 10d. capability failures degrade honestly, never fake success
mdc = os.path.join(tmp, "mdc.json")
ctl("init", "--state", mdc, "--graph", "market_discovery_graph.yaml", "--signal", "pets")
submit(mdc, "market_intake", {"market_seed": {"market": "pets", "canonical_identity": "pet ownership"}})
ctl("step", "--state", mdc)
submit(mdc, "field_lane", {"field_signals": [
    {"id": "pf_1", "origin": "FIELD", "summary": "cat owners improvise furniture protection"}]})
ctl("step", "--state", mdc)            # -> trend_lane
rc, out = submit(mdc, "trend_lane", {"capability_failure": {
    "capability": "google_trends", "detail": "provider unreachable"}})
ok(rc == 0 and out.get("recorded") == "CAPABILITY_FAILURE",
   "unavailable capability recorded as a typed deficit, not a stall")
rc, out = ctl("step", "--state", mdc)
ok(rc == 0 and out.get("advanced_to") == "corpus_lane"
   and "CAPABILITY_FAILURE" in str(out.get("note", "")),
   "the graph proceeds past the dead optional lane with the deficit on record")
capf = os.path.join(tmp, "capfail.json")
cf_state = json.load(open(pos))
cf_state.update({"run_id": "capfail", "node": "supplier_search", "status": "running",
                 "verdict": None, "capability_failures": []})
cf_state["data"]["supplier_candidates"] = []
cf_state["data"]["leads"] = []
json.dump(cf_state, open(capf, "w"))
submit(capf, "supplier_search", {"capability_failure": {
    "capability": "alibaba", "detail": "sourcing lane blocked"}})
ctl("step", "--state", capf)           # supplier_search -> normalize (with deficit)
ctl("step", "--state", capf)           # normalize -> qualify
rc, out = ctl("step", "--state", capf)  # qualify -> stop
cf_final = json.load(open(capf))
ok(cf_final["verdict"] == "MECHANISM_WITHOUT_SUPPLY" and cf_final["status"] == "stopped",
   "Alibaba blocked -> honest MECHANISM_WITHOUT_SUPPLY, never fake QUALIFIED_LEADS")
cf_page = repmod.render(repmod.build_model(cf_final), "FULL_RESEARCH")
ok("Capability Deficits" in cf_page and "alibaba" in cf_page,
   "the report surfaces the capability deficit explicitly")

# 10e. claim-authority regression suite (constitutional rules as tests)
def _adm(obs):
    return vermod.evidence_admissibility(obs, polx)

sup_as_demand = {"id": "t1", "evidence_roles": ["PURCHASE_INTENT"],
                 "source_identity": {"source_family": "supplier"},
                 "freshness": {"class": "LIVE"}}
ok(any("may not establish" in e for e in _adm(sup_as_demand)),
   "TRAP: supplier listing masquerading as demand — rejected (Alibaba ≠ demand)")
corpus_as_field = {"id": "t2", "evidence_roles": ["FRICTION_EVIDENCE"],
                   "source_identity": {"source_family": "corpus_evergreen"},
                   "freshness": {"class": "EVERGREEN"}}
ok(any("may not establish" in e for e in _adm(corpus_as_field)),
   "TRAP: corpus knowledge claiming current-market friction — rejected (corpus ≠ market proof)")
stale = {"id": "t3", "evidence_roles": ["CURRENT_PRODUCT_REFERENCE"],
         "source_identity": {"source_family": "review"},
         "freshness": {"class": "SLOW"}}
ok(any("claim-relative" in e for e in _adm(stale)),
   "TRAP: stale evidence claiming a current product reference — rejected")
fake_family = {"id": "t4", "evidence_roles": ["BEHAVIOR_SUPPORT"],
               "source_identity": {"source_family": "trends"},
               "freshness": {"class": "LIVE"}}
ok(any("unknown source_family" in e for e in _adm(fake_family)),
   "TRAP: trends dressed up as an evidence source family — rejected (Trends ≠ sales)")

import models as modmod  # noqa: E402
vstate = modmod.new_state("viral")
vstate["data"]["gaps"] = [{"id": "vg", "status": "open",
                           "required_evidence_roles": ["FRICTION_EVIDENCE"]}]
vstate["data"]["observations"] = [
    {"id": f"v{i}", "gap_id": "vg", "source": "reddit.com/r/x/one_viral_thread",
     "quote_ref": f"same thread voice {i}", "evidence_roles": ["FRICTION_EVIDENCE"],
     "source_identity": {"source_family": "community", "platform": "reddit",
                         "author_key": f"a{i}", "thread_key": "one_thread"}}
    for i in range(3)]
executors.comments(vstate, polx)
ok(vstate["data"]["gaps"][0]["status"] == "open",
   "TRAP: one viral thread as three sources — gap stays open (comments ≠ prevalence)")

nstate = modmod.new_state("noev")
nstate["data"]["whitespace_hypotheses"] = [
    {"id": "nw", "market_scope_id": "s", "type": "PRODUCT_WHITESPACE",
     "observed_mismatch": "x", "state": "PROPOSED"}]
nstate["data"]["gaps"] = [{"id": "ng", "whitespace_id": "nw", "status": "open",
                           "required_evidence_roles": ["FRICTION_EVIDENCE"]}]
import market_discovery as mdmod  # noqa: E402
mdmod.revise_whitespace(nstate, polx)
ok(nstate["data"]["whitespace_hypotheses"][0]["state"] == "PROPOSED"
   and nstate["data"]["gaps"][0]["status"] == "open",
   "TRAP: no evidence found — whitespace stays PROPOSED, never CONTRADICTED")

same_mech = [dict(h, id=f"sm{i}") for i in range(3)]
perrs = bridge.validate_portfolio(same_mech, polx)
ok(any("duplicate mechanism" in e for e in perrs),
   "TRAP: six variants of one product — same-mechanism portfolio rejected")

# 10f. cross-mode handoff matrix
for src_state, to_mode, scope, entry in (
        (md, "opportunity_research", "sc_hot", "understand"),
        (pa, "niche_loadout", "b_collect", "scope_intake"),
        (pa, "opportunity_research", "b_collect", "understand")):
    dst = os.path.join(tmp, f"h_{to_mode}_{scope}.json")
    rc, out = ctl("handoff", "--state", src_state, "--to-mode", to_mode,
                  "--scope", scope, "--out", dst)
    ch = json.load(open(dst))
    ok(rc == 0 and ch["node"] == entry and ch["data"]["handoff_packet"]
       and ch["data"]["observations"] == [],
       f"handoff {os.path.basename(src_state)} -> {to_mode}: frozen packet only, no parent context")

# 10g. replay: projections deterministic and rebuildable
w1, w2 = os.path.join(tmp, "w1.md"), os.path.join(tmp, "w2.md")
ctl("context-export", "--state", md, "--out", w1)
os.unlink(w1)
ctl("context-export", "--state", md, "--out", w1)
ctl("context-export", "--state", md, "--out", w2)
ok(open(w1).read() == open(w2).read(),
   "working_context.md deleted -> rebuilt byte-identical from canonical state")

# 10h. Architecture Qualification Report — the stopping condition
import qualify  # noqa: E402
q_states = [pos, md, pa, child, capf, opsr]
q_report = qualify.build_report(q_states)
for run_q in q_report["runs"]:
    if run_q["invariant_violations"]:
        print("VIOLATIONS", run_q["run_id"], run_q["invariant_violations"])
ok(q_report["total_invariant_violations"] == 0 and q_report["stopping_condition_met"],
   "ZERO invariant violations across adversarial fixtures — v1 stopping condition met")
ok(set(q_report["modes_covered"]) >= {"opportunity_research", "niche_loadout",
                                      "market_discovery", "product_anchored"},
   "qualification covers all four modes")
q_out = os.environ.get("QUALIFY_OUT") or os.path.join(tmp, "qualification.json")
with open(q_out, "w", encoding="utf-8") as f:
    json.dump(q_report, f, indent=1, ensure_ascii=False)
print(f"qualification report -> {q_out}")

# ---- 11. Preference Control Plane (docs/16) ---------------------------------
# 11a. self-describing surface
desc = setmod.describe("niche_loadout")
ids = {d_["id"] for d_ in desc["adjustable"]}
ok("niche_loadout.discovery_product_target" in ids and "community_strength" in ids
   and "product_anchored.market_bridges_target" not in ids,
   "describe(mode) exposes shared + mode controls, hides other modes")
ok(all(d_.get("label") and d_.get("mutability") for d_ in desc["adjustable"])
   and {"FAST_SCAN", "DEEP_INSIDER", "BLUE_OCEAN"} <= set(desc["presets"]),
   "every adjustable control is labeled with mutability; presets discoverable")
exp = setmod.explain("community_strength")
ok(exp["ok"] and exp["cannot_affect"] and exp["cost_effect"],
   "explain() carries affects/cannot_affect/cost so Hermes can teach the lever")
lockd = setmod.explain("loadout.final_collection_contract")
ok(lockd["level"] == "SYSTEM_LOCKED" and lockd["reason"],
   "constitutional contract is visible + explainable, never settable")
try:
    setmod.resolve({"niche_loadout.discovery_product_target": 50})
    ok(False, "integer ceiling enforced")
except ValueError:
    ok(True, "integer ceiling enforced — 50 products exceeds the schema range")
pr = setmod.resolve({"community_strength": "VERY_STRONG"}, preset="BLUE_OCEAN")
ok(pr["resolved"]["open_discovery"] == "HIGH"
   and pr["resolved"]["community_strength"] == "VERY_STRONG"
   and pr["preset"] == "BLUE_OCEAN",
   "preset + natural-language override compose (preset first, override wins)")

# 11b. desired stopping conditions vs φ ceilings (units)
stag = {"data": {"slot_candidates": [{"id": f"s{i}"} for i in range(3)]},
        "settings": setmod.resolve({"niche_loadout.discovery_product_target": 30}),
        "discovery_loop": {"rounds": 1, "last_count": 3}}
executors.discovery_loop_gate(stag, polx)
ok(stag["discovery_loop"]["continue"] is False,
   "stagnation beats the user's target — no new candidates means stop")
ceil = {"data": {"slot_candidates": [{"id": f"s{i}"} for i in range(3)]},
        "settings": setmod.resolve({"niche_loadout.discovery_product_target": 30}),
        "discovery_loop": {"rounds": 3, "last_count": 1}}
executors.discovery_loop_gate(ceil, polx)
ok(ceil["discovery_loop"]["continue"] is False,
   "the system round ceiling beats the user's target — never loop forever")
oc = modmod.new_state("oc")
oc["data"]["hypotheses"] = [{"id": "h1", "status": "WORKING_HYPOTHESIS"}]
oc["data"]["gaps"] = [{"id": "g1", "hypothesis_id": "h1", "status": "open"}]
oc["rounds"]["research"] = 1
ok(trmod.material_gap_exists(oc, polx) is True, "opportunity default: round 1 of 3 continues")
oc["settings"] = setmod.resolve({"opportunity_research.max_research_rounds": 1})
ok(trmod.material_gap_exists(oc, polx) is False,
   "user-tightened opportunity round cap actually governs the loop")

# 11c. preference-consuming gates (units)
pm = modmod.new_state("pm")
pm["data"]["market_scopes"] = [{"id": f"ps{i}", "market": "m", "status": "RETAINED"}
                               for i in range(4)]
pm["data"]["whitespace_hypotheses"] = [
    {"id": f"pw{i}", "market_scope_id": f"ps{i}", "type": "PRODUCT_WHITESPACE",
     "observed_mismatch": "x", "state": "SUPPORTED"} for i in range(4)]
pm["settings"] = setmod.resolve({"market_discovery.retained_markets": 3})
mdmod.market_promotion(pm, polx)
ok(len(pm["data"]["promoted_scopes"]) == 3,
   "retained_markets preference caps promotion within the 3-8 contract")
import product_anchored as pamod  # noqa: E402
pb = modmod.new_state("pb")
pb["data"]["market_bridges"] = [
    {"id": f"pb{i}", "meaning_id": f"m{i}", "market_scope": f"scope {i} {'alpha beta gamma delta'.split()[i]}",
     "jobs": [f"job{i}"],
     "features": {"mechanism_fit": .8, "job_fit": .8, "community_richness": .8,
                  "language_coherence": .7, "currentness": .5, "differentiation": .6,
                  "ecommerce_compatibility": .7, "assumption_distance": .2,
                  "saturation": .2, "redundancy": .1}} for i in range(4)]
pb["settings"] = setmod.resolve({"product_anchored.market_bridges_target": 2})
pamod.reverse_fit_gate(pb, polx)
ok(len([b for b in pb["data"]["market_bridges"] if b["state"] == "RETAINED"]) == 2,
   "market_bridges_target preference bounds reverse-fit retention")
import intelligence as intmod2  # noqa: E402
five_angles = [{"id": f"an{i}", "angle_type": "AD", "hook_type": h, "thesis": f"unique thesis {h} {i}",
                "disposition": "ADVANCE"}
               for i, h in enumerate(["INSIDER_PROBLEM", "DISCOVERY", "SEASONAL",
                                      "COMPARISON", "VALUE"])]
ap = intmod2.select_angle_portfolio(
    five_angles, polx, {"settings": setmod.resolve({"report_angle_count": 3})})
ok(ap["size"] <= 3, "report_angle_count preference caps the angle portfolio")

# 11d. E2E: "keep digging until 5, then give me 3" (loadout discovery loop)
lo2 = os.path.join(tmp, "lo2.json")
lo2_settings = os.path.join(tmp, "lo2_settings.json")
json.dump({"niche_loadout.discovery_product_target": 5,
           "niche_loadout.final_product_target": 3}, open(lo2_settings, "w"))
rc, out = ctl("init", "--state", lo2, "--graph", "loadout_graph.yaml",
              "--signal", "trail runners", "--settings", lo2_settings)
ok(rc == 0 and out["settings_hash"], "loadout run pinned to dig-until-5/final-3 preferences")
submit(lo2, "scope_intake", {"scope_request": {"scope_id": "trail", "scope": "trail_runners",
       "experience_level": "ADVANCED", "contexts": ["hot"], "rationale": "t"}})
ctl("step", "--state", lo2)            # -> frontier
submit(lo2, "frontier", {"frontier_branches": [{"name": "trail_runners", "new_jobs": .8,
       "new_frictions": .8, "new_slots": .8, "insider_specificity": .7,
       "transfer_strength": .4, "commerce_reachability": .7, "redundancy": .1,
       "inference_distance": .2, "research_cost": .3}]})
ctl("step", "--state", lo2)            # -> frontier_gate
ctl("step", "--state", lo2)            # -> world_model
rc, out = submit(lo2, "world_model", {"world_model": {"activities": ["long trail runs"],
       "constraints": ["heat", "carry"], "insider_language": ["vert", "FKT"]}})
ok(rc == 1 and any("moments" in e for e in out.get("schema_errors", [])), "world model without moments/open_questions is rejected (schema, not prompt text)")
submit(lo2, "world_model", {"world_model": {"activities": ["long trail runs"], "moments": ["mid-run", "post-run"],
       "constraints": ["heat", "carry"], "insider_language": ["vert", "FKT"], "open_questions": ["how they carry water"]}})
ctl("step", "--state", lo2)            # -> lived_r1
rc, out = submit(lo2, "lived_r1", {"lived_situations": [{"id": "ls1", "situation": "mid-run water access",
       "inferred_frictions": ["occupied_hand"]}]})
ok(rc == 1 and any("authority" in e or "unknowns" in e for e in out.get("schema_errors", [])), "a lived situation must declare authority + unknowns")
submit(lo2, "lived_r1", {"lived_situations": [{"id": "ls1", "situation": "mid-run water access",
       "inferred_frictions": ["occupied_hand"], "authority": "SIMULATED", "unknowns": ["how far between refills"]}]})
ctl("step", "--state", lo2)            # -> voi_gate
ctl("step", "--state", lo2)            # voi -> field
_LSRC = lambda i: {"source_family": "community", "platform": "reddit",
                   "author_key": f"lo_a{i}", "thread_key": f"lo_t{i}"}
submit(lo2, "field", {"observations": [
    {"id": f"lf{i}", "gap_id": "sampling:trail", "source": f"reddit.com/r/trailrunning/{i}",
     "quote_ref": f"soft flasks slosh and chafe {i}", "community": "trail runners",
     "problem": "hydration carry", "evidence_roles": ["FRICTION_EVIDENCE"],
     "freshness": {"class": "LIVE"}, "source_identity": _LSRC(i)} for i in range(3)]})
ctl("step", "--state", lo2)            # -> culture_curate
ctl("step", "--state", lo2)            # curate -> lived_r2
submit(lo2, "lived_r2", {"lived_situations": [{"id": "ls2", "situation": "post-run transition",
       "inferred_frictions": ["wet_gear"], "authority": "RECONSTRUCTED", "evidence_refs": ["lf0"], "unknowns": ["where they change"]}]})
ctl("step", "--state", lo2)            # -> product_slots
_SLOT = lambda i, job, fam: {"id": f"slot{i}", "name": f"item {i}", "quality": .7 + i * .02,
                             "physical_jobs": [job], "moments": ["during"],
                             "collection_roles": ["INSIDER_GEM" if i == 0 else "UTILITY"],
                             "mechanism_family": fam, "why_this": "ls1"}
submit(lo2, "product_slots", {"slot_candidates": [
    _SLOT(0, "hydration_carry", "vest"), _SLOT(1, "skin_protection", "topical"),
    _SLOT(2, "heat_management", "apparel")]})
ctl("step", "--state", lo2)            # product_slots -> discovery_gate
rc, out = ctl("step", "--state", lo2)  # gate: 3/5 -> loop back to voi_gate
ok(out.get("advanced_to") == "voi_gate" and "one more discovery round" in str(out.get("note", "")),
   "3/5 candidates: the discovery loop digs again — the user's target drives it")
ctl("step", "--state", lo2)            # voi -> field (outputs exist)
ctl("step", "--state", lo2)            # field -> culture_curate
ctl("step", "--state", lo2)            # curate -> lived_r2
ctl("step", "--state", lo2)            # lived_r2 -> product_slots
submit(lo2, "product_slots", {"slot_candidates": [
    _SLOT(3, "post_run_transition", "bag"), _SLOT(4, "night_visibility", "light")]})
ctl("step", "--state", lo2)            # -> discovery_gate
rc, out = ctl("step", "--state", lo2)  # gate: 5/5 -> sellability
ok(out.get("advanced_to") == "sellability" and "satisfy" in str(out.get("note", "")),
   "target reached: the loop exits to sellability — dig-until-N, deterministically")
# mid-run revision: allowed lever now, portfolio lever after the fact refused
rev_file = os.path.join(tmp, "rev.json")
json.dump({"community_strength": "VERY_STRONG"}, open(rev_file, "w"))
r = subprocess.run([PY, os.path.join(ROOT, "python", "settings.py"), "apply",
                    "--state", lo2, "--file", rev_file], capture_output=True, text=True)
rev_out = json.loads(r.stdout)
ok(r.returncode == 0 and rev_out["revision"]["revision"] == 1
   and rev_out["revision"]["retroactive"] is False,
   "mid-run revision recorded as versioned, non-retroactive SettingsRevision")
ctl("step", "--state", lo2)            # sellability -> portfolio
json.dump({"niche_loadout.final_product_target": 4}, open(rev_file, "w"))
r = subprocess.run([PY, os.path.join(ROOT, "python", "settings.py"), "apply",
                    "--state", lo2, "--file", rev_file], capture_output=True, text=True)
ok(r.returncode == 1 and "before portfolio" in r.stdout,
   "final-size lever freezes once the run reaches portfolio selection")
rc, out = ctl("step", "--state", lo2)  # portfolio executes -> community_skeptic
lo2_state = json.load(open(lo2))
ok(len(lo2_state["data"]["loadout"]) == 3,
   "final_product_target=3 honored inside the constitutional 3-6 contract")
lg2 = graphmod.load_graph("loadout_graph.yaml")
env2 = ctxmod.compile_envelope(lo2_state, lg2, graphmod.load_policies())
ok(env2["action_context"]["user_preferences"].get("community_strength") == "VERY_STRONG",
   "workers see the revised preference in the frozen envelope, not chat history")
lo2_page = repmod.render(repmod.build_model(lo2_state), "FULL_RESEARCH")
ok("Preference History" in lo2_page and "Revision 1" in lo2_page,
   "report shows the preference history — no silent setting changes")

# 11e. doctor validates the whole declared surface (incl. presets)
res2 = doctor.run()
ok(res2["ok"], f"doctor green over the settings surface ({res2['errors'][:2]})")
ok(os.path.isfile(os.path.join(ROOT, "prompts", "preference_compiler.md")),
   "preference compiler contract exists for Hermes")

# ---- 12. registry flywheel + gap analysis + genesis (docs/17) ---------------
import candidates as candmod  # noqa: E402
import gap_analysis as gamod  # noqa: E402
import maintenance_triggers as mtmod  # noqa: E402

# 12a. terminal gates auto-emitted candidates — the user never asked
md_state = json.load(open(md))
md_kinds = {c["kind"] for c in md_state["data"].get("registry_candidates") or []}
ok({"QUERY_PATTERN_CANDIDATE", "SOURCE_CANDIDATE", "WHITESPACE_MOTIF_CANDIDATE",
    "DEMAND_REROUTE_MOTIF_CANDIDATE"} <= md_kinds,
   f"market run auto-emitted reusable candidates ({sorted(md_kinds)})")
pa_state = json.load(open(pa))
pa_kinds = {c["kind"] for c in pa_state["data"].get("registry_candidates") or []}
ok("MARKET_BRIDGE_PATTERN_CANDIDATE" in pa_kinds,
   "product-anchored run auto-emitted its supported bridge pattern")
ok(all(c.get("authority") == "CANDIDATE"
       for c in md_state["data"]["registry_candidates"]),
   "candidates carry CANDIDATE authority — seed rows never become evidence")
ok(md_state["verdict"] == "MARKET_SCOPES_READY",
   "auto-emission never touched the verdict")

# 12b. maintenance triggers: recurrence across DISTINCT runs opens the lifecycle
for fake_run in ("recur_x", "recur_y"):
    fstate = modmod.new_state(fake_run)
    fstate["data"]["registry_candidates"] = [
        {"id": f"rc_{fake_run}", "kind": "SOURCE_CANDIDATE", "name": "reddit:community",
         "payload": {}, "authority": "CANDIDATE", "status": "PROPOSED"}]
    memory.create_run(fake_run, "trigger probe", "collect")
    memory.sync_work_nodes(fake_run, fstate)
trig = mtmod.evaluate(polx)
ok(trig["maintenance_due"] and any(
    f["trigger"] == "SOURCE_TRIGGER" and f["name"] == "reddit:community"
    for f in trig["fired"]),
   "cross-run source recurrence fires the maintenance trigger deterministically")
maint_state_path = os.path.join(tmp, "maint_auto.json")
created = mtmod.create_maintenance_run(trig, maint_state_path)
ok(created["ok"] and created["candidates_loaded"] >= 1
   and json.load(open(maint_state_path))["node"] == "collect",
   "trigger opens a Registry Maintenance run — promotion still needs L5 approval")
with memory.connect() as _c:
    n_t = _c.execute("SELECT COUNT(*) c FROM events WHERE event_type='MAINTENANCE_TRIGGERED'"
                     ).fetchone()["c"]
ok(n_t >= 1, "MAINTENANCE_TRIGGERED recorded durably")

# 12c. genesis: emphasis, never authority
bad_gen = dict(h, id="hg1", genesis="VIBES_LED")
ok(any("genesis" in e for e in modmod.validate(bad_gen, "hypothesis")),
   "unknown genesis rejected by schema")
gstate = modmod.new_state("gen_probe")
gstate["data"]["hypotheses"] = [dict(h, id="hg2", genesis="TREND_LED",
                                     gaps=["does the trend change behavior?"])]
executors.gap_compiler(gstate, polx)
ok(gstate["data"]["gaps"][0]["required_freshness"] == ["LIVE"],
   "TREND_LED genesis tightens gap freshness to LIVE — popularity is never the product")

# 12d. capture feasibility: HOSTILE entry excluded from promotion
hstate = modmod.new_state("hostile_probe")
hstate["data"]["market_scopes"] = [{"id": "hs1", "market": "m", "status": "RETAINED"}]
hstate["data"]["whitespace_hypotheses"] = [
    {"id": "hw1", "market_scope_id": "hs1", "type": "PRODUCT_WHITESPACE",
     "observed_mismatch": "x", "state": "SUPPORTED"}]
hstate["data"]["capture_assessments"] = [
    {"id": "hc1", "scope_id": "hs1",
     "dimensions": {"competitor_fragmentation": .1, "incumbent_lock_in": .9,
                    "differentiation_clarity": .1, "switching_friction": .9,
                    "trust_barrier": .9, "regulatory_burden": .9}}]
mdmod.capture_gate(hstate, polx)
mdmod.market_promotion(hstate, polx)
ok(hstate["data"]["capture_assessments"][0]["result"] == "HOSTILE"
   and hstate["data"]["promoted_scopes"] == [],
   "great demand + hostile entry -> judged HOSTILE and NOT promoted")

# 12e. demand reroutes were optional: accepted in md walk, absent in pa walk
ok(any(r["id"] == "rr1" for r in md_state["data"].get("demand_reroutes") or []),
   "optional demand_reroutes accepted at the whitespace node")
with memory.connect() as _c:
    n_rr = _c.execute("SELECT COUNT(*) c FROM work_nodes WHERE node_type='DEMAND_REROUTE'"
                      ).fetchone()["c"]
ok(n_rr >= 1, "DemandReroute mirrored as a first-class Work Graph object")

# 12f. gap analysis runs standalone for other modes (shared operator, not a mode)
ga_probe = modmod.new_state("ga_probe")
ga_probe["data"]["market_reframes"] = [
    {"id": "gr1", "initial_user_frame": "stress relief",
     "user_frame_state": "CONTRADICTED",
     "evidence_supported_frame": "collector hobby", "evidence_refs": []}]
gamod.demand_gap_analysis(ga_probe, polx)
ok(any(g["gap_type"] == "POSITIONING_GAP" for g in ga_probe["data"]["demand_gaps"]),
   "a contradicted user frame surfaces as a POSITIONING_GAP — shared operator works cross-mode")

# 12g. doctor still green over the flywheel surface
res3 = doctor.run()
ok(res3["ok"], f"doctor green over flywheel additions ({res3['errors'][:2]})")

# ---- 13. fresh-clone bootstrap: compiled registry is a self-healing cache ---
import registry as regmod  # noqa: E402

snap_before = regmod.load_snapshot()
ok(bool(snap_before and snap_before.get("build_id")), "registry snapshot loads")
os.remove(regmod.OUT)
snap_auto = regmod.load_snapshot()
ok(bool(snap_auto) and snap_auto.get("build_id") == snap_before.get("build_id"),
   "missing snapshot self-compiles deterministically (fresh clone works)")
ok(os.path.exists(regmod.OUT), "auto-build persisted the snapshot to disk")
os.remove(regmod.OUT)
rc, out = ctl("doctor")
ok(rc == 0 and out.get("ok") is True, "doctor green on a fresh-clone tree (no compiled/)")

# ---- 14. corpus contract (docs/18): legacy migration + provenance ----------
import models as modelsmod  # noqa: E402

leg = os.path.join(tempfile.mkdtemp(), "legacy.json")
rc, _ = ctl("init", "--state", leg, "--signal", "legacy-era run")
ok(rc == 0, "init for legacy-migration fixture")
with open(leg, encoding="utf-8") as f:
    _ls = json.load(f)
_ls["node"] = "polymath"  # a pre-rename run parked at the retrieve node
_ls["data"]["polymath_evidence"] = _ls["data"].pop("corpus_evidence")
_ls["data"]["polymath_evidence"].append({"id": "old1", "summary": "legacy row"})
_ls["data"]["observations"].append(
    {"id": "obs_leg", "source_identity": {"source_family": "polymath_evergreen"}})
with open(leg, "w", encoding="utf-8") as f:
    json.dump(_ls, f)
mig = modelsmod.load_state(leg)
ok(mig["node"] == "corpus" and "polymath_evidence" not in mig["data"]
   and mig["data"]["corpus_evidence"][0]["id"] == "old1",
   "legacy state migrates on load: node + evidence key")
ok(mig["data"]["observations"][-1]["source_identity"]["source_family"] == "corpus_evergreen",
   "legacy source_family normalized to corpus_evergreen")
rc, st = ctl("status", "--state", leg)
ok(rc == 0 and st.get("node") == "corpus", "CLI resumes a legacy run at the renamed node")

prov = os.path.join(tempfile.mkdtemp(), "prov.json")
ctl("init", "--state", prov, "--signal", "prov run", "--corpus", "qdrant:test_notes")
with open(prov, encoding="utf-8") as f:
    ok(json.load(f).get("corpus") == "qdrant:test_notes", "init --corpus recorded in state")
ctl("step", "--state", prov)              # signal pre-filled -> advances to corpus node
rc, pend = ctl("step", "--state", prov)   # outputs missing -> pending + frozen envelope
ok('"corpus": "qdrant:test_notes"' in json.dumps(pend),
   "corpus provenance rides the RunBrief into every frozen envelope")


# ---- 12. 2026-09-03 review fixes: validator, receipts, independence, parsing, math, triage ----
import models as _m12  # noqa: E402
import evaluator as _ev12  # noqa: E402
import memory as _mem12  # noqa: E402
import verifiers as _ver12  # noqa: E402

# 12a. schema validation is real: types, nested objects, array items
_e = _m12.validate({"id": 5, "product_name": "x", "supplier_name": "y"}, "supplier_candidate")
ok(any("expected string" in x and ".id" in x for x in _e), "validator rejects a wrong-typed scalar")
_e = _m12.validate({"id": "h1", "source": "s", "path": "a>b>c", "target_mechanism": "m",
                    "evidence_boundary": "b", "gaps": ["?"], "status": "WORKING_HYPOTHESIS",
                    "alternatives": ["a"], "falsifiers": ["f"]}, "hypothesis")
ok(any("path" in x and "expected array" in x for x in _e), "validator rejects a string where an array is declared")
ok(any("evidence_boundary" in x and "expected object" in x for x in _e), "validator rejects a scalar where an object is declared")
_e = _m12.validate({"id": "h1", "source": "s", "path": ["a", "b", "c"], "target_mechanism": "m",
                    "evidence_boundary": {"first_inference_at": "b"}, "gaps": ["?"],
                    "status": "NOT_A_STATUS", "alternatives": ["a"], "falsifiers": ["f"]}, "hypothesis")
ok(any("not in" in x for x in _e), "validator still enforces enums")
ok(_m12.validate(valid3, "hypothesis") == [], "a well-formed hypothesis passes the full validator")

# 12b. L4 receipts: only THIS call's receipts persist; failures are recorded, not swallowed
_st = _m12.new_state("r12", "sig")
_st["data"]["hypotheses"] = [{"id": "h1", "status": "WORKING_HYPOTHESIS"}, {"id": "h2", "status": "WORKING_HYPOTHESIS"}]
_st["l4_receipts"] = [{"check_type": "SEMANTIC_BRIDGE_REVIEW", "subject_id": "old", "status": "PASS"}]
_calls = []
_orig_wc = _mem12.write_check
_mem12.write_check = lambda *a, **k: _calls.append(a)
_ev12.apply_evaluations(_st, pol)                     # no evaluations at all
ok(_calls == [], "no evaluations -> no receipts re-written (the receipts[-0:] bug)")
_st["data"]["evaluations"] = [{"hypothesis_id": "h1", "verdict": "PASS"}, {"hypothesis_id": "h2", "verdict": "REVISE", "missing_intermediates": ["x"]}]
_ev12.apply_evaluations(_st, pol)
ok(len(_calls) == 2 and {c[3] for c in _calls} == {"PASS", "REVISE"}, "exactly the two new receipts persisted")
ok(_st["data"]["hypotheses"][1]["status"] == "CHALLENGED" and "evidence for missing intermediate: x" in _st["data"]["hypotheses"][1]["gaps"],
   "REVISE still challenges the bridge and appends the intermediate as a gap")
def _boom(*a, **k): raise RuntimeError("disk full")
_mem12.write_check = _boom
_ev12.apply_evaluations(_st, pol)
ok(_st.get("warnings") and _st["warnings"][-1]["where"] == "l4_receipt_persist" and "disk full" in _st["warnings"][-1]["error"],
   "receipt persistence failure is recorded in state.warnings, not swallowed")
_mem12.write_check = _orig_wc

# 12c. ONE definition of independence: gap closure uses (platform, author) groups
def _obs12(i, author, gap="g1"):
    return {"id": f"o{i}", "gap_id": gap, "quote_ref": f"quote {i}", "source": f"https://reddit.com/r/x/{i}",
            "evidence_roles": ["FRICTION_EVIDENCE"], "freshness": {"class": "LIVE"},
            "source_identity": {"platform": "reddit", "author_key": author, "source_family": "community"}}
_st = _m12.new_state("r12c", "sig")
_st["data"]["gaps"] = [{"id": "g1", "status": "open", "required_evidence_roles": []}]
_st["data"]["observations"] = [_obs12(1, "alice"), _obs12(2, "alice"), _obs12(3, "alice")]
executors.comments(_st, pol)
ok(_st["data"]["gaps"][0]["status"] == "open", "three URLs from ONE author do not close a gap")
_st["data"]["gaps"][0]["status"] = "open"
_st["data"]["observations"] = [_obs12(1, "alice"), _obs12(2, "bob"), _obs12(3, "carol")]
executors.comments(_st, pol)
ok(_st["data"]["gaps"][0]["status"] == "supported", "three independent voices close it")
ok(_ver12.independence_groups(_st["data"]["observations"])["independent_groups"] == 3,
   "the same grouping coverage reports")

# 12d. supplier parsing: units win, currencies guard, price strings are never quantities
_sst = {"data": {"supplier_candidates": [
    {"id": "a", "product_name": "A", "supplier_name": "s1", "price_raw": "US $3.20", "moq_raw": "1-10 pieces"},
    {"id": "b", "product_name": "B", "supplier_name": "s2", "price_raw": "¥25", "moq_raw": "≥ 500 sets"},
    {"id": "c", "product_name": "C", "supplier_name": "s3", "price_raw": "€ 4,00 - 6,00", "moq_raw": "MOQ: 50"},
    {"id": "d", "product_name": "D", "supplier_name": "s4", "price_raw": "$12", "moq_raw": "$12"},
    {"id": "e", "product_name": "E", "supplier_name": "s5", "price_raw": "USD 1,200.50", "moq_raw": "1-10"},
]}}
executors.supplier(_sst, pol)
_by = {s["id"]: s for s in _sst["data"]["supplier_candidates"]}
ok(_by["a"]["price_usd_low"] == 3.2 and _by["a"]["moq_units"] == 10, "'1-10 pieces' is MOQ 10, not 1")
ok(_by["b"]["price_usd_low"] is None and _by["b"]["moq_units"] == 500, "¥25 is not 25 dollars; '≥ 500 sets' parses")
ok(_by["c"]["price_usd_low"] is None and _by["c"]["moq_units"] == 50, "euro prices refuse to parse; 'MOQ: 50' parses")
ok(_by["d"]["price_usd_low"] == 12 and _by["d"]["moq_units"] is None, "a price string in the MOQ field is not a quantity")
ok(_by["e"]["price_usd_low"] == 1200.5 and _by["e"]["moq_units"] is None, "'1-10' without a unit is ambiguous -> None")

# 12e. lens gate: whole words with bounded morphology
_orig_ll = executors.load_lenses
executors.load_lenses = lambda: {"woodwork": {"keywords": ["saw"], "question": "q"},
                                 "mobility": {"keywords": ["move"], "question": "q2"},
                                 "minimal-interference": {"keywords": [], "question": "q0"}}
def _lens_names(signal):
    st_ = {"data": {"signal": signal, "corpus_evidence": []}}
    executors.lens_gate(st_, pol)
    return [l["name"] for l in st_["data"]["lenses"]]
ok(_lens_names("sawdust everywhere in the shop") == ["minimal-interference"], "'sawdust' does not select the 'saw' lens")
ok(_lens_names("the saw binds on wet oak") == ["woodwork"], "whole-word keyword still selects")
ok(_lens_names("hard to keep moving; movement hurts") == ["mobility"], "bounded morphology: moving/movement hit 'move'")
executors.load_lenses = _orig_ll

# 12f. memory: schema verified once per process; submissions take the write lock
_mem12._SCHEMA_READY.clear()
_ens_calls = []
_orig_ens = _mem12._ensure_schema
_mem12._ensure_schema = lambda c: (_ens_calls.append(1), _orig_ens(c))
_mem12.connect().close(); _mem12.connect().close(); _mem12.connect().close()
ok(len(_ens_calls) == 1, "connect() verifies the schema once per process, not per call")
_mem12._ensure_schema = _orig_ens
import inspect as _insp12  # noqa: E402
ok('conn.execute("BEGIN IMMEDIATE")' in _insp12.getsource(_mem12.apply_submission),
   "apply_submission holds the write lock across its read-then-write")

# 12g. loadout math properties (frontier / VoI / surface gain / portfolio / fidelity)
_fu = lm.frontier_utility({"name": "b", "new_jobs": 1, "new_frictions": 1, "new_slots": 1, "insider_specificity": 1,
                           "transfer_strength": 1, "commerce_reachability": 1}, lp)
ok(_fu["utility"] == 1.0 and _fu["disposition"] == "EXPLORE", "frontier utility saturates at 1.0 -> EXPLORE")
_fu0 = lm.frontier_utility({"name": "z", "redundancy": 1, "inference_distance": 1, "research_cost": 1}, lp)
ok(_fu0["utility"] == 0.0 and _fu0["disposition"] == "PRUNE", "all-negative branch floors at 0.0 -> PRUNE")
_rf = lm.rank_frontier(branches, lp)
ok([b["utility"] for b in _rf] == sorted([b["utility"] for b in _rf], reverse=True), "rank_frontier is descending")
_q_hi = lm.voi_priority({"id": "q", "missing_role_importance": 1, "decision_impact": 1, "expected_cost": 1}, lp)
_q_lo = lm.voi_priority({"id": "q", "missing_role_importance": 1, "decision_impact": 0.2, "expected_cost": 1}, lp)
_q_cheap = lm.voi_priority({"id": "q", "missing_role_importance": 1, "decision_impact": 1, "expected_cost": 0.0}, lp)
ok(_q_hi["priority"] > _q_lo["priority"], "VoI rises with decision impact")
ok(_q_cheap["priority"] == lm.voi_priority({"id": "q", "missing_role_importance": 1, "decision_impact": 1, "expected_cost": 0.1}, lp)["priority"],
   "VoI cost is floored at 0.1 (no division blow-up)")
_rq = lm.rank_questions([{"id": "a", "decision_impact": 0.1}, {"id": "b", "decision_impact": 0.9}], lp)
ok([q["question"] for q in _rq] == ["b", "a"], "rank_questions is descending by priority")
_sg = lm.surface_gain("p", "c", {k: 1 for k in lp["surface_gain"]["weights"]}, lp)
ok(_sg["disposition"] == "KEEP_BRANCH" and lm.surface_gain("p", "c", {}, lp)["disposition"] == "COLLAPSE_TO_PARENT",
   "surface gain keeps a revealing split and collapses an empty one")
def _cand(i, jobs, roles=("core",), fam="f", q=0.8):
    return {"id": f"c{i}", "name": f"c{i}", "quality": q, "physical_jobs": list(jobs), "moments": ["m"],
            "collection_roles": list(roles), "mechanism_family": fam}
_pool = [_cand(i, [f"job{i}"], fam=f"fam{i}") for i in range(10)]
_sel = lm.select_portfolio(_pool, lp)
ok(lp["portfolio"]["size_min"] <= _sel["size"] <= lp["portfolio"]["size_max"], "portfolio size respects size_min..size_max")
ok(len(set(_sel["selected"])) == len(_sel["selected"]) and set(_sel["selected"]) <= {c["id"] for c in _pool},
   "portfolio has no duplicates and only input ids")
ok(lm.select_portfolio(_pool, lp) == _sel, "portfolio selection is deterministic")
ok(lm.select_portfolio([], lp)["size"] == 0, "empty candidate pool -> empty portfolio, no crash")
_clones = [_cand(i, ["same"], fam="same") for i in range(6)] + [_cand(99, ["other"], fam="other")]
ok("c99" in lm.select_portfolio(_clones, lp)["selected"], "a diverse candidate beats a redundant clone")
_two = lm.select_portfolio(_pool[:2], lp)
ok(_two["size"] == 2, "fewer candidates than size_min -> takes what exists, never invents")
_fid = lm.insider_fidelity({k: 1.0 for k in lp["insider_fidelity"]["weights"] if k != "genericness_penalty"}, lp)
ok(_fid["status"] == "PASS" and lm.insider_fidelity({"genericness": 1.0}, lp)["status"] == "FAIL_INSIDER_FIDELITY",
   "insider fidelity passes on full dimensions and fails a generic loadout")

# 12h. market math properties
_mf = mmath.market_frontier_utility({"id": "s1", "features": {k: 1 for k in pol["market_discovery"]["frontier"]["weights"]}}, pol)
ok(0.0 <= _mf["total"] <= 1.0 and _mf["formula"] == "market_frontier_v1" and len(_mf["config_hash"]) == 12,
   "market frontier is a bounded receipt with a config hash")
ok(mmath.market_frontier_utility({"id": "s0"}, pol)["disposition"] == "PRUNE", "featureless scope prunes")
_scopes = [{"id": f"s{i}", "market": f"market{i}", "niche": f"n{i}"} for i in range(12)]
_recs = [{"scope_id": f"s{i}", "total": 0.9 - i * 0.01, "disposition": "EXPLORE"} for i in range(12)]
_recs[3]["disposition"] = "PRUNE"
_recs.append({"scope_id": "ghost", "total": 0.99, "disposition": "EXPLORE"})
_ds = mmath.diversity_select(_scopes, _recs, pol)
ok(len(_ds) == len(set(_ds)) and len(_ds) <= int(pol["market_discovery"]["frontier"].get("retain_max", 8)),
   "diversity_select: no duplicates, bounded by retain_max")
ok("s3" not in _ds and "ghost" not in _ds, "diversity_select ignores PRUNE and unknown scope ids")
_dv = mmath.detect_divergence({"community_activity": 0.9, "search_interest": 0.1, "commerce_supply": 0.1}, pol)
ok("EARLY_EMERGENCE" in _dv["patterns"] and "COMMUNITY_COMMERCE_GAP" in _dv["patterns"], "divergence names early emergence")
ok(mmath.detect_divergence({}, pol)["spread"] == 0.0, "divergence spread is 0 for empty channels")
_w = dict(pol["market_discovery"]["frontier"]["weights"])
_items = [{"id": "a", "features": {k: 0.9 for k in _w}}, {"id": "b", "features": {k: 0.1 for k in _w}}]
ok(mmath.rank_stability(_items, _w, 0.2)["status"] == "STABLE", "a dominant leader is STABLE under perturbation")
ok(mmath.rank_stability(_items[:1], _w, 0.2)["trials"] == 0, "rank_stability with one item runs no trials")
_k = list(_w)[0]
_tie = [{"id": "a", "features": {_k: 1.0}}, {"id": "b", "features": {kk: (1.0 if kk != _k else 0.0) for kk in _w}}]
ok(mmath.rank_stability(_tie, _w, 0.5)["trials"] == 2 * len(_w), "rank_stability trials = 2 per weight")

# 12i. product-anchored math properties
_rf1 = pmm.reverse_fit_utility({"id": "b1", "features": {k: 1 for k in pol["product_anchored"]["reverse_fit"]["weights"]}}, pol)
ok(0.0 <= _rf1["total"] <= 1.0 and _rf1["formula"] == "reverse_fit_v1", "reverse fit is a bounded receipt")
_bridges = [{"id": f"b{i}", "market_scope": f"m{i}", "jobs": [f"j{i}"]} for i in range(6)]
_brec = [{"bridge_id": f"b{i}", "total": 0.8 - i * 0.05, "disposition": "EXPLORE"} for i in range(6)]
_sb = pmm.diversity_select_bridges(_bridges, _brec, pol)
ok(len(_sb) == len(set(_sb)) and len(_sb) <= int(pol["product_anchored"]["reverse_fit"].get("bridge_target", 3)),
   "bridge diversity selection: no duplicates, bounded by bridge_target")
ok(pmm.bridge_rank_stability(_bridges[:1], pol)["status"] == "STABLE", "bridge rank stability delegates to market_math")

# 12j. corpus adapter mapping (pure; the network path is the agent's)
import corpus_polymath as _cp  # noqa: E402
_resp = {"selected_documents": [{"doc_id": "doc_A", "semantic_summary": 'title: "Hooked"\nsource_file: "x"\n\nHabit loops: variable rewards make users return without external triggers, forming behavior over four steps.'}],
         "child_evidence": [{"chunk_id": "chunk_1", "doc_id": "doc_A", "text": "variable rewards drive return visits"},
                            {"chunk_id": "chunk_1", "doc_id": "doc_A", "text": "dup"},
                            {"chunk_id": "chunk_2", "doc_id": "doc_B", "text": ""}],
         "graph_facts": [{"fact_id": "f1", "subject": "hook", "predicate": "CAUSES", "object": "habit"}]}
_rows = _cp.rows_from_response(_resp, "ecom-meta-v1")
ok([r["id"] for r in _rows] == ["polymath:doc:doc_A", "polymath:chunk:chunk_1"], "adapter dedupes by id and drops empty rows")
ok(all(r["id"] and r["summary"] and r["source"] for r in _rows), "every adapter row satisfies the docs/18 contract")
ok("Hooked" in _rows[0]["source"] and "Hooked" in _rows[1]["source"], "document title becomes the auditable source")
ok(len(_cp.rows_from_response(_resp, "c", include_facts=True)) == 3, "graph facts only when asked")
_resp2 = {"selected_documents": [
              {"doc_id": "t1", "semantic_summary": 'title: "1 product. 3 AI tools"\nvideo_id: x\nurl: https://youtube.com/w\n\n## Description\n\nApply for my mentorship: https://a.b/c\n\n## Transcript\n\n**[0:00]** Hey guys, Mark here. In this video I show how three AI tools helped me find a product and scale to twenty thousand a day.'},
              {"doc_id": "t2", "semantic_summary": 'title: "Meta only"\nvideo_id: y\nurl: https://youtube.com/y\n## Description\nhttps://link'}],
          "child_evidence": [{"chunk_id": "tc1", "doc_id": "t1", "text": "**[9:25]** find that this is a **[9:27]** fantastic structure"}]}
_rows2 = _cp.rows_from_response(_resp2, "mbb", titles={"t1": "/Users/x/1 product. 3 ai tools.md", "t2": "/Users/y/Meta only.md"})
ok([r["id"] for r in _rows2] == ["polymath:doc:t1", "polymath:chunk:tc1"], "frontmatter-only profiles are dropped; real profiles kept")
ok(_rows2[0]["summary"].startswith("Hey guys") and "mentorship" not in _rows2[0]["summary"], "profile summary is what the document says, not its links")
ok("1 product. 3 AI tools" in _rows2[0]["source"] and "/Users" not in _rows2[1]["source"], "a filesystem path never becomes the auditable source title")
ok("[9:25]" not in _rows2[1]["summary"] and "[9:25]" in _rows2[1]["text"], "transcript timestamps leave the summary, verbatim text keeps them")

# 12l. forced verdict: an exhausted research budget with no supported gap must still route to mechanism
import transitions as _tr12  # noqa: E402
_x = _m12.new_state("r12l", "sig")
_x["data"]["hypotheses"] = [{"id": "hx", "status": "CHALLENGED", "gaps": ["q1"]}]
_x["data"]["gaps"] = [{"id": "gx", "hypothesis_id": "hx", "status": "open", "question": "q1"}]
_x["data"]["observations"] = [{"id": f"o{i}", "gap_id": "gx"} for i in range(6)]
_x["rounds"]["research"] = pol["evidence"]["max_research_rounds"]
ok(_tr12.evaluate("material_gap_exists", _x, pol) is False, "budget spent: gaps stop being researchable")
ok(_tr12.evaluate("evidence_sufficient", _x, pol) is True, "budget spent + nothing supported -> mechanism must pronounce (no silent stall)")
_x["rounds"]["research"] = 1
ok(_tr12.evaluate("evidence_sufficient", _x, pol) is False, "with budget left and open gaps, research continues")
_x["data"]["gaps"][0]["status"] = "supported"
_x["data"]["hypotheses"][0]["status"] = "REJECTED"
ok(_tr12.evaluate("evidence_sufficient", _x, pol) is False, "a supported gap of a REJECTED bridge does not count as sufficiency")
_x["data"]["hypotheses"][0]["status"] = "CHALLENGED"
ok(_tr12.evaluate("evidence_sufficient", _x, pol) is True, "a supported gap of a LIVE bridge with enough observations is sufficiency")

# 12m. per-visit submission: outputs left over from an earlier visit never satisfy a re-entered node
_pv = os.path.join(tempfile.mkdtemp(), "pv.json")
ctl("init", "--state", _pv, "--signal", "per-visit guard seed", "--corpus", "polymath:test")
ctl("step", "--state", _pv)                                   # entry pre-filled -> corpus (an advance INTO corpus exists)
with open(_pv, encoding="utf-8") as f:
    _pvs = json.load(f)
_pvs["data"]["corpus_evidence"] = [{"id": "stale1", "summary": "left over from a previous visit", "source": "test"}]
with open(_pv, "w", encoding="utf-8") as f:
    json.dump(_pvs, f)
rc, _out = ctl("step", "--state", _pv)
ok(rc != 0 and "not submitted" in json.dumps(_out), "stale outputs in state do not advance a re-entered node without a submission")
rc, _out = submit(_pv, "corpus", {"corpus_evidence": [{"id": "fresh1", "summary": "this visit", "source": "test"}]})
rc2, _out2 = ctl("step", "--state", _pv)
ok(rc == 0 and rc2 == 0 and _out2.get("node") in (None, "primitives") and not _out2.get("error"),
   "a submission in this visit advances it")

# 12k. run triage lays out the run's bugs
import run_triage as _rt  # noqa: E402
tri = os.path.join(tempfile.mkdtemp(), "tri.json")
ctl("init", "--state", tri, "--signal", "clip-on microphones for storytelling creators", "--corpus", "polymath:test")
ctl("step", "--state", tri)                       # -> corpus node, run row created
_res = _rt.triage(tri, pol)
ok(_res["ok"] and _res["counts"]["BLOCKER"] == 0 and _res["counts"]["DEFECT"] == 0, "a fresh run triages clean")
rc, _out = ctl("triage-run", "--state", tri)
ok(rc == 0 and _out.get("ok") is True and "bugs" in _out, "controller triage-run exits 0 on a clean run")
with open(tri, encoding="utf-8") as f:
    _ts = json.load(f)
_good_node = _ts["node"]
_ts["node"] = "hypothesize"
with open(tri, "w", encoding="utf-8") as f:
    json.dump(_ts, f)
_res = _rt.triage(tri, pol)
ok(any(b["code"] == "NODE_DISAGREE" and b["severity"] == "BLOCKER" for b in _res["bugs"]) and not _res["ok"],
   "JSON/SQLite node disagreement is a BLOCKER")
_ts["node"] = _good_node
_ts["data"]["corpus_evidence"] = [{"id": "x1", "summary": "a note with no origin"}]
_ts["data"]["gaps"] = [{"id": "g1", "status": "supported", "required_evidence_roles": []}]
_ts["data"]["observations"] = [_obs12(1, "alice"), _obs12(2, "alice"),
                               dict(_obs12(3, "zed"), source_identity={"platform": "book", "author_key": "z", "source_family": "corpus_evergreen"},
                                    evidence_roles=["PURCHASE_INTENT"], freshness={"class": "EVERGREEN"})]
_ts["data"]["supplier_candidates"] = [{"id": "s1", "product_name": "P", "supplier_name": "S", "price_raw": "¥25",
                                        "moq_raw": "100 pcs", "url": "u", "price_usd_low": 25.0, "price_usd_high": 25.0, "moq_units": 100}]
with open(tri, "w", encoding="utf-8") as f:
    json.dump(_ts, f)
_res = _rt.triage(tri, pol)
_codes = {b["code"] for b in _res["bugs"]}
ok({"CORPUS_ROW_NOT_EVIDENCE", "GAP_SUPPORT_INCONSISTENT", "OBS_INADMISSIBLE", "SUPPLIER_CURRENCY"} <= _codes,
   "triage lays out: notes-as-evidence, single-voice closure, authority violation, currency-blind price")
ok(all(b["fix"] and b["where"] for b in _res["bugs"]), "every finding names where it is and the fix")
rc, _md = subprocess.run([PY, CTL, "triage-run", "--state", tri, "--markdown"], capture_output=True, text=True).returncode, None
_md = subprocess.run([PY, CTL, "triage-run", "--state", tri, "--markdown"], capture_output=True, text=True).stdout
ok(rc == 1 and "| severity |" in _md and "GAP_SUPPORT_INCONSISTENT" in _md, "markdown triage table; exit 1 when defects exist")

# ---------------------------------------------------------------------------
# 13. docs/19 — corpus-first ideation: compiled reformulations, contract rows,
#     hop provenance, portfolio law, supplier fit, registry growth
# ---------------------------------------------------------------------------
import corpus_queries as _cq
import ideation as _ide
import bridge as _br
import corpus_polymath as _cp
_sig13 = """SEED: Purple Ocean — sell a boring product to a market with no expert brand.
LATENT INTERPRETATION: the buyer is an anxious first-time caregiver in r/AgingParents
and r/CaregiverSupport; the tension is dignity vs. safety; invariant: nobody wants to
look like a patient in their own home; contrast: medical-supply catalogs vs. lifestyle brands."""
_st13 = {"data": {"signal": _sig13, "communities": ["r/AgingParents"]}}
_q1 = _cq.compile_queries(_st13, pol)
_q2 = _cq.compile_queries(_st13, pol)
ok(3 <= len(_q1) <= 5 and _q1 == _q2, f"corpus_plan compiles 3-5 reformulations deterministically ({len(_q1)})")
ok(len({q["query"] for q in _q1}) == len(_q1) and all(q.get("id") and q.get("kind") and q.get("why") for q in _q1),
   "every compiled query is distinct and says why it exists")
ok(len({q["kind"] for q in _q1}) >= 3, "reformulations span kinds (seed/tension/communities/invariant/contrast), not paraphrases")
_st13b = {"data": {"signal": _sig13}}
_note13 = executors.EXECUTORS["python.corpus_query_compiler"](_st13b, pol)
ok(_st13b["data"].get("corpus_queries") == _q1 and "reformulation" in str(_note13).lower(), f"on_enter executor writes data.corpus_queries ({_note13})")

# contract rows from RETRIEVE-EVIDENCE-ROWS-V1
_resp13 = {"evidence_rows": [
    {"id": "chunk:c1", "kind": "chunk", "doc_id": "d1", "title": "T1", "source": "T1 · Ch · 20250709 · 3:15–3:47",
     "text": "[3:15 - 3:47] people hide the grab bar", "text_clean": "people hide the grab bar", "lanes": ["vector"], "score": 0.9,
     "timecode": {"start": "3:15", "end": "3:47", "start_s": 195, "end_s": 227}},
    {"id": "doc:d2", "kind": "document", "doc_id": "d2", "title": "T2", "source": "T2 · summary", "text": "sum", "text_clean": "sum",
     "lanes": ["summary"], "score": 0.5, "summary": {"summary": "sum"}},
    {"id": "fact:f1", "kind": "graph_fact", "doc_id": "d3", "title": "T3", "source": "T3 · fact", "text": "A causes B", "text_clean": "A causes B",
     "lanes": ["graph"], "score": 0.4, "fact": {"subject": "A", "predicate": "causes", "object": "B"}, "evidence": [{"doc_id": "d3", "chunk_id": "c9"}]},
    {"id": "fact:f2", "kind": "graph_fact", "doc_id": "d4", "title": "T4", "source": "T4", "text": "C causes D", "text_clean": "C causes D",
     "lanes": ["graph"], "score": 0.3, "fact": {}},
]}
_rows13 = _cp.rows_from_evidence_rows(_resp13, "mbb")
ok([r["id"] for r in _rows13] == ["polymath:chunk:c1", "polymath:document:d2", "polymath:graph_fact:f1"],
   "adapter maps chunk/document/attested fact rows and DROPS an unattested fact")
ok(all(r["can_establish"] == ["behavioral_mechanism", "conceptual_pattern"] and "current_demand" in r["cannot_establish"] for r in _rows13),
   "every corpus row carries can_establish / cannot_establish (docs/04 authority)")
ok(_rows13[0]["timecode"]["start_s"] == 195 and _rows13[0]["summary"] == "people hide the grab bar" and "3:15" in _rows13[0]["source"],
   "transcript rows keep timecode + clean text + human source")
ok("graph_fact" in _rows13[2]["tags"] and _rows13[2]["fact"]["predicate"] == "causes", "graph rows are tagged and keep the fact")

# portfolio law (product_ideation)
_st13c = {"data": {"mechanisms": [{"id": "m1", "status": "SUPPORTED"}, {"id": "m2", "status": "REJECTED"}],
                   "observations": [{"id": "o1"}, {"id": "o2"}]}}
def _pc(i, ff, mech="m1", nvar=2, refs=("o1",)):
    return {"id": f"pc{i}", "mechanism_id": mech, "name": f"Concept {i}", "form_factor": ff, "target_moment": "m",
            "variations": [{"name": f"v{j}"} for j in range(nvar)], "evidence_refs": list(refs)}
ok(not _ide.validate_concepts([_pc(1, "wearable"), _pc(2, "tabletop"), _pc(3, "garment")], _st13c, pol), "3 distinct concepts x 2 variations pass")
ok(_ide.validate_concepts([_pc(1, "wearable"), _pc(2, "tabletop")], _st13c, pol), "2 concepts violate the portfolio floor")
ok(_ide.validate_concepts([_pc(1, "wearable"), _pc(2, "wearable"), _pc(3, "garment")], _st13c, pol), "duplicate form factors rejected")
ok(_ide.validate_concepts([_pc(1, "wearable", nvar=1), _pc(2, "tabletop"), _pc(3, "garment")], _st13c, pol), "a concept with one variation rejected")
ok(_ide.validate_concepts([_pc(1, "wearable", mech="m2"), _pc(2, "tabletop"), _pc(3, "garment")], _st13c, pol), "concept on a REJECTED mechanism rejected")
ok(_ide.validate_concepts([_pc(1, "wearable", refs=("zz",)), _pc(2, "tabletop"), _pc(3, "garment")], _st13c, pol), "evidence_refs must be observation ids")

# hop provenance
_pol_hops = copy.deepcopy(pol); _pol_hops.setdefault("bridge", {})["require_hop_refs"] = True
_hyp13 = {"id": "h9", "path": ["creators_move", "cables_snag", "wearable_audio"], "evidence_boundary": {"first_inference_at": "wearable_audio"},
          "hop_refs": {"0": ["polymath:chunk:c1"], "1": ["polymath:chunk:c1"]}}
ok(not _br.validate_hop_refs(_hyp13, _pol_hops, {"polymath:chunk:c1"}), "evidence-side hops citing known rows pass")
ok(_br.validate_hop_refs(dict(_hyp13, hop_refs={"0": ["polymath:chunk:c1"]}), _pol_hops, {"polymath:chunk:c1"}), "missing ref on an evidence-side hop rejected")
ok(_br.validate_hop_refs(dict(_hyp13, hop_refs={"0": ["nope"], "1": ["polymath:chunk:c1"]}), _pol_hops, {"polymath:chunk:c1"}), "unknown row id rejected")
_pol_nohops = copy.deepcopy(pol); _pol_nohops.setdefault("bridge", {})["require_hop_refs"] = False
ok(not _br.validate_hop_refs(dict(_hyp13, hop_refs={}), _pol_nohops, set()), "policy off: hop refs optional")
ok((graphmod.load_policies().get("bridge") or {}).get("require_hop_refs") is True, "shipped policy: hop provenance is REQUIRED (owner 2026-09-03)")

ok(len(_cq.compile_queries({"data": {"signal": "context probe signal"}}, pol)) >= 1, "a plain signal still gets a corpus plan (never an empty lane)")

# supplier <-> mechanism fit (docs/19 item 7)
_mech13 = {"id": "m1", "name": "wearable-wireless-audio", "status": "SUPPORTED"}
_d13 = {"product_concepts": [{"id": "pc1", "mechanism_id": "m1", "name": "Clip mic", "form_factor": "wearable"}],
        "product_candidates": [{"id": "p1", "mechanism_id": "m1", "name": "DJI Mic class"}]}
ok(executors._supplier_fits({"id": "s1", "product_name": "Garden Hose 50ft", "mechanism_id": "m1"}, _mech13, _d13), "declared mechanism_id = fit")
ok(executors._supplier_fits({"id": "s2", "product_name": "Wireless Lavalier Mic Kit"}, _mech13, _d13), "token overlap with the mechanism's product territory = fit")
ok(not executors._supplier_fits({"id": "s3", "product_name": "Garden Hose 50ft"}, _mech13, _d13), "unrelated listing does NOT fit the mechanism")
ok((executors._concept_for({"id": "s1", "concept_id": "pc1"}, _mech13, _d13) or {}).get("id") == "pc1", "lead resolves its product concept")

# corpus-supplied analogies (docs/19 item 3): graph rows become CORPUS_FACT_HYPOTHESIS analogies
_st13d = {"data": {"corpus_evidence": [
    {"id": "polymath:graph_fact:f1", "kind": "graph_fact", "tags": ["graph_fact", "corpus_evergreen"], "title": "Dog hiking guide",
     "summary": "hikers attach the leash to a hip belt to keep both hands free", "source": "polymath/x · Dog hiking guide",
     "fact": {"subject": "leash", "predicate": "attach", "object": "hip belt"}},
    {"id": "polymath:chunk:c1", "kind": "chunk", "tags": ["chunk", "corpus_evergreen"], "summary": "attach the leash to a belt", "source": "s"}],
    # docs/26 §2 (fail-closed): only CLASSIFIED rows may become analogies — the graph row is classified, the chunk is not
    "row_relevance": {"polymath:graph_fact:f1": "STRUCTURAL_ANALOGY"}}}
_prim13 = {"shared_predicates": ["attach", "access"], "frictions": ["occupied_hand"], "behaviors": ["performer keeps both hands free while speaking"],
           "physical_jobs": ["capture audio hands free"]}
_an13 = executors._corpus_analogies(_st13d, _prim13, 5)
ok(_an13 and all(a.get("authority") == "CORPUS_FACT_HYPOTHESIS" for a in _an13) and all("graph" in str(a.get("evidence_refs") or a.get("row_id") or a) for a in _an13),
   "graph-lane rows yield analogies labelled CORPUS_FACT_HYPOTHESIS citing the row; chunk rows do not")

# status shows per-gap independent-thread counts (docs/19 item 6)
_gs = os.path.join(tmp, "gapstatus.json")
ctl("init", "--state", _gs, "--signal", "status probe signal")
with open(_gs, encoding="utf-8") as f:
    _gst = json.load(f)
_gst["node"] = "web_research"
_gst["data"]["hypotheses"] = [{"id": "h1", "status": "CHALLENGED"}]
_gst["data"]["gaps"] = [{"id": "gA", "hypothesis_id": "h1", "question": "do creators tape transmitters?", "status": "open", "required_evidence_roles": ["FRICTION_EVIDENCE"]}]
def _o13(i, author, thread):
    return {"id": f"ob{i}", "gap_id": "gA", "source": f"reddit.com/r/x/{thread}", "quote_ref": f"quote {i}", "evidence_roles": ["FRICTION_EVIDENCE"],
            "freshness": {"class": "LIVE"}, "source_identity": {"source_family": "community", "platform": "reddit", "author_key": author, "thread_key": thread}}
_gst["data"]["observations"] = [_o13(1, "a", "t1"), _o13(2, "a", "t2"), _o13(3, "b", "t2"), _o13(4, "c", "t3")]
with open(_gs, "w", encoding="utf-8") as f:
    json.dump(_gst, f)
rc, _so = ctl("status", "--state", _gs)
_gv = {g["gap_id"]: g for g in (_so.get("gaps") or [])}
ok("gA" in _gv and _gv["gA"]["independent_threads"] == 2 and _gv["gA"]["need_more"] >= 1,
   f"status shows independent threads per gap (a/t1,a/t2,b/t2 = one voice; c/t3 second) -> 2, need 1 more ({_gv.get('gA')})")

# registry growth from a SUPPORTED bridge (docs/19 item 5)
import candidates as _cand
def _st13e(mech_status="SUPPORTED", with_query=True):
    o = {"id": "o1", "gap_id": "g1", "quote_ref": "I tape the transmitter to my belt", "source": "reddit.com/r/x/1",
         "evidence_roles": ["WORKAROUND_EVIDENCE"], "freshness": {"class": "LIVE"},
         "source_identity": {"source_family": "community", "platform": "reddit", "author_key": "a", "thread_key": "t1"}}
    if with_query:
        o["query_id"] = "q1"; o["query_used"] = "transmitter belt tape"
    return {"run_id": "r13", "data": {
        "mechanisms": [{"id": "m1", "name": "wearable-wireless-audio", "status": mech_status, "hypothesis_id": "h1", "supporting_observation_ids": ["o1"]}],
        "hypotheses": [{"id": "h1", "status": mech_status, "target_mechanism": "wearable_wireless_audio"}],
        "primitives": {"frictions": ["occupied_hand"], "physical_jobs": ["capture audio hands free"], "behaviors": ["moves while recording"]},
        "observations": [o], "gaps": [{"id": "g1", "status": "supported", "question": "do creators tape transmitters?"}],
        "queries": [{"id": "q1", "gap_id": "g1", "query": "transmitter belt tape", "channel": "reddit"}],
        "registry_candidates": []}}
_s13 = _st13e(); _cand.auto_emit(_s13, pol)
_kinds13 = {c["kind"] for c in _s13["data"]["registry_candidates"]}
ok({"MECHANISM_CANDIDATE", "FRICTION_CANDIDATE", "ACTIVITY_CANDIDATE", "QUERY_PATTERN_CANDIDATE"} <= _kinds13,
   f"supported bridge emits mechanism + friction + activity + query-pattern candidates ({sorted(_kinds13)})")
ok(all(c["authority"] == "CANDIDATE" and c["status"] == "PROPOSED" and c["evidence_refs"] for c in _s13["data"]["registry_candidates"]),
   "candidates are PROPOSED, never evidence, and cite their observations")
_s13r = _st13e("REJECTED"); _cand.auto_emit(_s13r, pol)
ok(not ({"MECHANISM_CANDIDATE", "FRICTION_CANDIDATE", "ACTIVITY_CANDIDATE"} & {c["kind"] for c in _s13r["data"]["registry_candidates"]}),
   "a rejected bridge grows nothing in the registry")
_s13q = _st13e(with_query=False); _cand.auto_emit(_s13q, pol)
ok("QUERY_PATTERN_CANDIDATE" not in {c["kind"] for c in _s13q["data"]["registry_candidates"]},
   "query patterns come only from queries that actually yielded admitted observations")

# curate: dedupe per (quote, gap); required_freshness enforced (docs/19 item 6)
def _ob13(i, gap, quote, author, cls="LIVE"):
    return {"id": f"z{i}", "gap_id": gap, "quote_ref": quote, "source": f"reddit.com/r/x/{i}", "problem": "p",
            "evidence_roles": ["FRICTION_EVIDENCE"], "freshness": {"class": cls},
            "source_identity": {"source_family": "community", "platform": "reddit", "author_key": author, "thread_key": f"t{i}"}}
import models as _models
_cs = _models.new_state("cur13", "curate probe"); _cs["node"] = "curate"
_cs["data"].update({"hypotheses": [{"id": "h1", "status": "CHALLENGED"}],
       "gaps": [{"id": "gA", "hypothesis_id": "h1", "question": "?", "status": "open", "required_evidence_roles": ["FRICTION_EVIDENCE"]},
                {"id": "gB", "hypothesis_id": "h1", "question": "??", "status": "open", "required_evidence_roles": ["FRICTION_EVIDENCE"], "required_freshness": ["LIVE"]}],
       "observations": [_ob13(1, "gA", "same quote", "a"), _ob13(2, "gA", "same quote", "b"), _ob13(3, "gB", "same quote", "c"),
                        _ob13(4, "gA", "q4", "d"), _ob13(5, "gA", "q5", "e"),
                        _ob13(6, "gB", "old 1", "f", "EVERGREEN"), _ob13(7, "gB", "old 2", "g", "EVERGREEN"), _ob13(8, "gB", "old 3", "h", "EVERGREEN")]})
executors.comments(_cs, pol)
_ids13 = {o["id"] for o in _cs["data"]["observations"]}
ok("z2" not in _ids13 and "z3" in _ids13, "same quote on the same gap collapses; the same quote answering another gap survives")
_gaps13 = {g["id"]: g["status"] for g in _cs["data"]["gaps"]}
ok(_gaps13["gA"] == "supported", f"gA: three independent voices -> supported ({_gaps13['gA']})")
ok(_gaps13["gB"] != "supported", f"gB requires LIVE evidence: three evergreen voices do NOT close it ({_gaps13['gB']})")

# gap queries are short keyword forms with community scope (docs/19 item 4)
_gq = {"run_id": "gq13", "data": {"communities": ["r/videography", "r/NewTubers"],
       "hypotheses": [{"id": "h1", "status": "CHALLENGED", "gaps": ["do creators tape transmitters to their belts while filming?"]}],
       "gaps": [{"id": "gX", "hypothesis_id": "h1", "question": "do creators tape transmitters to their belts while filming?", "status": "open",
                 "required_evidence_roles": ["WORKAROUND_EVIDENCE"]}], "queries": []}}
executors.gap_compiler(_gq, pol)
_rq = [q for q in _gq["data"]["queries"] if q.get("channel") == "reddit"]
ok(_rq and all("site:" not in q["query"] and len(q["query"].split()) <= 8 and q.get("keywords") and q.get("question") for q in _rq),
   f"reddit queries are short keyword forms carrying the question + keywords ({_rq[0]['query'] if _rq else None})")
ok(_rq and _rq[0].get("subreddit_hints") == ["r/videography", "r/NewTubers"], "named communities become subreddit scope hints")

# report: Product Directions (concepts x variations, leads grouped by concept) — on the real terminal state
import report as _rep
with open(pos, encoding="utf-8") as f:
    _rs = json.load(f)
_rs_obs = [o["id"] for o in _rs["data"].get("observations") or []][:2] or ["o00"]
_rs["data"]["product_concepts"] = [{"id": "pc1", "mechanism_id": "m1", "name": "Clip mic", "form_factor": "wearable", "target_moment": "walking talk",
                                    "variations": [{"name": "Clip mic lite"}, {"name": "Clip mic pro", "twist": "dual channel"}], "evidence_refs": _rs_obs}]
for _l in _rs["data"].get("leads") or []:
    _l["concept_id"] = "pc1"
_html13 = _rep.render(_rep.build_model(_rs))
ok("Product Directions" in _html13 and "Clip mic pro" in _html13 and "dual channel" in _html13
   and f"{len(_rs['data'].get('leads') or [])} supplier lead" in _html13,
   "report renders Product Directions with variations and per-concept lead counts")

# ---------------------------------------------------------------------------
# 14. docs/20 — evidence allocation (starvation is not refutation) and
#     sourcing per concept (no borrowing)
# ---------------------------------------------------------------------------
import allocation as _al
def _o14(i, gap, author, thread, contradicts=False):
    return {"id": f"a{i}", "gap_id": gap, "source": f"reddit.com/r/x/{thread}", "quote_ref": f"q{i}", "evidence_roles": ["FRICTION_EVIDENCE"],
            "freshness": {"class": "LIVE"}, "contradicts": contradicts,
            "source_identity": {"source_family": "community", "platform": "reddit", "author_key": author, "thread_key": thread}}
_s14 = _models.new_state("alloc14", "allocation probe")
_s14["data"].update({
    "hypotheses": [{"id": "hA", "status": "CHALLENGED"}, {"id": "hB", "status": "CHALLENGED"}, {"id": "hC", "status": "CHALLENGED"}, {"id": "hD", "status": "REJECTED"}],
    "gaps": [{"id": "gA1", "hypothesis_id": "hA", "question": "a1", "status": "supported", "required_evidence_roles": []},
             {"id": "gA2", "hypothesis_id": "hA", "question": "a2", "status": "supported", "required_evidence_roles": []},
             {"id": "gB1", "hypothesis_id": "hB", "question": "b1", "status": "open", "required_evidence_roles": []},
             {"id": "gB2", "hypothesis_id": "hB", "question": "b2", "status": "open", "required_evidence_roles": []},
             {"id": "gC1", "hypothesis_id": "hC", "question": "c1", "status": "contradicted", "required_evidence_roles": []},
             {"id": "gC2", "hypothesis_id": "hC", "question": "c2", "status": "open", "required_evidence_roles": []}],
    "observations": [_o14(1, "gA1", "a", "t1"), _o14(2, "gA1", "b", "t2"), _o14(3, "gA1", "c", "t3"), _o14(4, "gA2", "a", "t1"), _o14(5, "gA2", "d", "t4"), _o14(6, "gA2", "e", "t5"),
                     _o14(7, "gB1", "f", "t6"), _o14(8, "gC2", "g", "t7")],
    "queries": [{"id": "qB1", "gap_id": "gB1", "channel": "reddit", "query": "b1"}, {"id": "qB2", "gap_id": "gB2", "channel": "reddit", "query": "b2"},
                {"id": "qA1", "gap_id": "gA1", "channel": "reddit", "query": "a1"}, {"id": "qC2", "gap_id": "gC2", "channel": "reddit", "query": "c2"}]})
_s14["rounds"]["research"] = 1
_al14 = _al.hypothesis_allocation(_s14, pol)
_by14 = {a["hypothesis_id"]: a for a in _al14}
ok(set(_by14) == {"hA", "hB", "hC"}, "allocation covers live hypotheses only (REJECTED excluded)")
ok(_by14["hA"]["floor_reached"] and not _by14["hA"]["starved"], "hA: both gaps at the bar -> floor reached")
ok(_by14["hB"]["starved"] and _by14["hB"]["need_more_total"] == 5 and _by14["hB"]["queries"] == ["qB1", "qB2"],
   f"hB: open gaps at 1 and 0 threads -> starved, needs 5 more, its queries listed ({_by14['hB']['need_more_total']})")
ok(not _by14["hC"]["starved"] and _by14["hC"]["contradicted_gaps"] == 1, "hC: a contradicted gap means the evidence spoke -> not starved")
ok(_al14[0]["hypothesis_id"] == "hB" and _al14[0]["rank"] == 1, "starved hypothesis ranks first")
ok(_al.starved_rejections([{"id": "hB", "status": "REJECTED"}], _s14, pol) and not _al.starved_rejections([{"id": "hC", "status": "REJECTED"}], _s14, pol),
   "REJECTED refused for the starved hypothesis, allowed after a contradiction")
_s14x = copy.deepcopy(_s14); _s14x["rounds"]["research"] = int(pol["evidence"]["max_research_rounds"])
ok(not _al.starved_rejections([{"id": "hB", "status": "REJECTED"}], _s14x, pol), "budget exhausted: rejection for lack of evidence is allowed")
_pol_noalloc = copy.deepcopy(pol); _pol_noalloc["evidence"]["allocation"] = {"enforce_no_starved_rejection": False}
ok(not _al.starved_rejections([{"id": "hB", "status": "REJECTED"}], _s14, _pol_noalloc), "policy off: the law is advisory")
_iq = _al.interleave_queries(copy.deepcopy(_s14["data"]["queries"]), _al14, _s14["data"]["gaps"])
ok([q["id"] for q in _iq][:3] == ["qB1", "qC2", "qA1"] and all(q.get("hypothesis_id") and q.get("allocation_rank") for q in _iq),
   f"queries interleaved starved-first across hypotheses ({[q['id'] for q in _iq]})")

# controller enforces it at challenge (CLI) — reuse the positive walk's hypothesis shapes
_ch = os.path.join(tmp, "alloc_ch.json")
ctl("init", "--state", _ch, "--signal", "allocation challenge probe")
with open(_ch, encoding="utf-8") as f:
    _chs = json.load(f)
_chs["node"] = "challenge"; _chs["rounds"]["research"] = 1
_chs["data"]["corpus_evidence"] = [{"id": "polymath:chunk:k1", "summary": "row", "source": "s"}]
_chs["data"]["hypotheses"] = [dict(h, status="CHALLENGED"), dict(h2, status="CHALLENGED"), dict(h3, status="CHALLENGED")]
_chs["data"]["gaps"] = [{"id": "g1", "hypothesis_id": "h1", "question": "?", "status": "supported", "required_evidence_roles": []},
                        {"id": "g2", "hypothesis_id": "h2", "question": "?", "status": "open", "required_evidence_roles": []},
                        {"id": "g3", "hypothesis_id": "h3", "question": "?", "status": "contradicted", "required_evidence_roles": []}]
_chs["data"]["observations"] = [_o14(1, "g1", "a", "t1"), _o14(2, "g1", "b", "t2"), _o14(3, "g1", "c", "t3"), _o14(9, "g3", "z", "t9", contradicts=True)]
_chs["data"]["queries"] = [{"id": "q2", "gap_id": "g2", "channel": "reddit", "query": "g2 keywords"}]
with open(_ch, "w", encoding="utf-8") as f:
    json.dump(_chs, f)
_chal = [{"id": "cx", "hypothesis_id": "h2", "argument": "thin", "verdict": "REJECTED"}]
rc14, out14 = submit(_ch, "challenge", {"challenges": _chal, "hypotheses": [dict(h, status="SUPPORTED"), dict(h2, status="REJECTED"), dict(h3, status="REJECTED")]})
ok(rc14 == 1 and any("allocation: h2" in e and "q2" in e for e in out14.get("schema_errors") or []),
   f"controller refuses REJECTED for starved h2 and names its queries ({(out14.get('schema_errors') or ['?'])[0][:120]})")
rc14b, out14b = submit(_ch, "challenge", {"challenges": _chal, "hypotheses": [dict(h, status="SUPPORTED"), dict(h2, status="CHALLENGED"), dict(h3, status="REJECTED")]})
ok(rc14b == 0, f"h3 REJECTED on a contradicted gap and h2 kept CHALLENGED is accepted ({out14b.get('schema_errors')})")
rc14c, out14c = ctl("status", "--state", _ch)
ok(any(a["hypothesis_id"] == "h2" and a["starved"] and a["rank"] == 1 for a in out14c.get("allocation") or []), "status shows the allocation rollup with h2 starved at rank 1")

# sourcing per concept
_sp = _models.new_state("src14", "sourcing probe"); _sp["node"] = "supplier_search"
_sp["data"]["mechanisms"] = [{"id": "m1", "name": "wearable-wireless-audio", "status": "SUPPORTED", "hypothesis_id": "h1", "supporting_observation_ids": ["a1"]}]
_sp["data"]["product_candidates"] = [{"id": "p1", "mechanism_id": "m1", "name": "DJI Mic class"}]
_sp["data"]["product_concepts"] = [
    {"id": "pcA", "mechanism_id": "m1", "name": "Clip mic", "form_factor": "wearable clip", "target_moment": "t", "variations": [{"name": "Clip mic lite"}, {"name": "Clip mic pro"}], "evidence_refs": ["a1"]},
    {"id": "pcB", "mechanism_id": "m1", "name": "Collar loop", "form_factor": "garment-integrated collar", "target_moment": "t", "variations": [{"name": "Collar loop soft"}, {"name": "Collar loop stiff"}], "evidence_refs": ["a1"]},
    {"id": "pcC", "mechanism_id": "m1", "name": "Desk puck", "form_factor": "tabletop puck", "target_moment": "t", "variations": [{"name": "Puck mini"}, {"name": "Puck max"}], "evidence_refs": ["a1"]}]
_note14 = executors.EXECUTORS["python.sourcing_plan_compiler"](_sp, pol)
ok(len(_sp["data"]["sourcing_plan"]) == 3 * len(pol["sourcing"]["channels"]) and "Clip mic lite" in _sp["data"]["sourcing_plan"][0]["search_terms"] and "DJI Mic class" in _sp["data"]["sourcing_plan"][0]["search_terms"]
   and {j["channel"] for j in _sp["data"]["sourcing_plan"]} == set(pol["sourcing"]["channels"]),
   "sourcing plan: one job per concept PER CHANNEL (alibaba + cjdropshipping) with variation + candidate terms")
ok(g["nodes"]["supplier_search"].get("on_enter") == "python.sourcing_plan_compiler", "supplier_search compiles its sourcing plan on entry")
_sp["data"]["supplier_candidates"] = [
    {"id": "s1", "product_name": "Wireless Clip Mic Kit", "supplier_name": "A", "price_raw": "US $9.90", "moq_raw": "50 pcs", "url": "u", "concept_id": "pcA"},
    {"id": "s2", "product_name": "Soft Collar Loop Lavalier", "supplier_name": "B", "price_raw": "US $4.00", "moq_raw": "100 pcs", "url": "u"},
    {"id": "s3", "product_name": "Wireless Clip Mic Kit v2", "supplier_name": "C", "price_raw": "¥25", "moq_raw": "100 pcs", "url": "u", "concept_id": "pcA"}]
executors.supplier(_sp, pol)
_cov14 = {c["concept_id"]: c for c in _sp["data"]["sourcing_coverage"]}
ok(_sp["data"]["supplier_candidates"][1].get("concept_id") == "pcB" and _sp["data"]["supplier_candidates"][1].get("concept_resolved_by") == "name_overlap",
   "a candidate without concept_id is resolved when exactly one concept matches its name")
ok(_cov14["pcA"]["status"] == "sourced" and _cov14["pcA"]["candidates"] == 2 and _cov14["pcA"]["parsed"] == 1
   and _cov14["pcB"]["status"] == "sourced" and _cov14["pcC"]["status"] == "unsourced",
   f"coverage per concept: sourced / sourced / UNSOURCED ({ {k: v['status'] for k, v in _cov14.items()} })")
# report + triage on the real terminal state with one concept left unsourced
with open(pos, encoding="utf-8") as f:
    _rs14 = json.load(f)
_rs14["data"]["product_concepts"] = _rs14["data"].get("product_concepts") or []
_rs14["data"]["product_concepts"].append({"id": "pc_orphan", "mechanism_id": "m1", "name": "Ankle pouch", "form_factor": "ankle strap", "target_moment": "t",
                                         "variations": [{"name": "v1"}, {"name": "v2"}], "evidence_refs": [o["id"] for o in _rs14["data"]["observations"]][:1]})
executors.sourcing_coverage(_rs14)
_html14 = _rep.render(_rep.build_model(_rs14))
ok("UNSOURCED" in _html14 and "Ankle pouch" in _html14 and "concepts have supplier leads" in _html14, "report shows the unsourced concept as a finding, with coverage in the header")
_tri14 = os.path.join(tmp, "tri14.json")
with open(_tri14, "w", encoding="utf-8") as f:
    json.dump(_rs14, f)
_res14 = _rt.triage(_tri14, pol)
ok(any(b["code"] == "CONCEPT_UNSOURCED" and "pc_orphan" in b["where"] for b in _res14["bugs"]), "triage flags CONCEPT_UNSOURCED")
_st14 = copy.deepcopy(_s14); _st14["data"]["hypotheses"][1]["status"] = "REJECTED"; _st14["node"] = "gaps"
_tri14b = os.path.join(tmp, "tri14b.json")
ctl("init", "--state", _tri14b, "--signal", "starved triage probe")
with open(_tri14b, encoding="utf-8") as f:
    _base14 = json.load(f)
_base14["data"].update(_st14["data"]); _base14["rounds"]["research"] = 1; _base14["node"] = "gaps"
with open(_tri14b, "w", encoding="utf-8") as f:
    json.dump(_base14, f)
_res14b = _rt.triage(_tri14b, pol)
ok(any(b["code"] == "STARVED_REJECTION" and "hB" in b["where"] for b in _res14b["bugs"]), "triage flags STARVED_REJECTION for a thin-evidence rejection with budget left")

# allocation must count the way curate counts (freshness + roles) — R4 lesson
_s14f = copy.deepcopy(_s14)
_s14f["data"]["gaps"][0]["required_freshness"] = ["LIVE"]          # gA1 demands LIVE
_s14f["data"]["gaps"][0]["status"] = "open"
for _o in _s14f["data"]["observations"]:
    if _o["gap_id"] == "gA1":
        _o["freshness"] = {"class": "FAST"}
_alf = {a["hypothesis_id"]: a for a in _al.hypothesis_allocation(_s14f, pol)}
ok(_alf["hA"]["gaps"][0]["threads"] == 0 and not _alf["hA"]["floor_reached"],
   "a LIVE-only gap fed with FAST evidence counts zero threads in the allocation (same filter as curate)")

# lead cap must not re-collapse the portfolio (R4 lesson): interleave across concepts
_L = [dict(id=f"lh{i}", concept_id="cHigh", mechanism_id="mH", evidence_score=40) for i in range(6)] + \
     [dict(id=f"ll{i}", concept_id="cLow", mechanism_id="mL", evidence_score=15) for i in range(3)] + \
     [dict(id=f"lm{i}", concept_id="cMid", mechanism_id="mM", evidence_score=20) for i in range(2)]
_L.sort(key=lambda x: -x["evidence_score"])
_IL = executors.interleave_leads(_L)
ok([l["concept_id"] for l in _IL[:6]] == ["cHigh", "cMid", "cLow", "cHigh", "cMid", "cLow"],
   f"leads interleave across concepts, best-evidenced first, before any cap ({[l['concept_id'] for l in _IL[:6]]})")
ok(len({l["concept_id"] for l in _IL[:4]}) == 3, "a cap of 4 keeps every concept in the result set")
# triage duplicate rule matches curate: same quote on two gaps is NOT a duplicate
_dq = os.path.join(tmp, "dupq.json")
ctl("init", "--state", _dq, "--signal", "dup quote probe")
with open(_dq, encoding="utf-8") as f:
    _dqs = json.load(f)
_dqs["data"]["observations"] = [_o14(1, "gA", "a", "t1"), dict(_o14(2, "gB", "a", "t1"), quote_ref="q1"), dict(_o14(3, "gA", "b", "t2"), quote_ref="q1")]
with open(_dq, "w", encoding="utf-8") as f:
    json.dump(_dqs, f)
_dres = _rt.triage(_dq, pol)
_dd = [b for b in _dres["bugs"] if b["code"] == "OBS_DUPLICATE"]
ok(_dd and "1 duplicate" in _dd[0]["message"], f"triage counts duplicates per (quote, gap): q1 on gA twice = 1, q1 on gB is not ({_dd[0]['message'] if _dd else None})")

# ---------------------------------------------------------------------------
# 15. docs/21 — the utilization receipt and Polymath capability negotiation
# ---------------------------------------------------------------------------
import utilization as _ut
import corpus_polymath as _cpm
import http.server, threading, socket
with open(pos, encoding="utf-8") as f:
    _u_state = json.load(f)
_u = _ut.compute(_u_state)
ok(_u["leads"]["total"] == len(_u_state["data"]["leads"]) and _u["gaps"]["total"] == len(_u_state["data"]["gaps"])
   and _u["observations"]["total"] == len(_u_state["data"]["observations"]) and _u["corpus"]["mode"] == "generic",
   "utilization receipt counts leads, gaps, observations; mode defaults to generic")
ok("| measure | value |" in _ut.to_markdown(_u) and "leads across concepts" in _ut.to_markdown(_u), "utilization renders as a table")
ok(_u_state["data"].get("utilization", {}).get("leads", {}).get("total") == len(_u_state["data"]["leads"]), "qualify wrote the receipt into the run state")
_html15 = _rep.render(_rep.build_model(_u_state))
ok("Evidence utilization" in _html15, "report shows the utilization section")
_tri15 = subprocess.run([PY, CTL, "triage-run", "--state", pos, "--markdown"], capture_output=True, text=True).stdout
ok("Evidence utilization (docs/21)" in _tri15 and "corpus backend / mode" in _tri15, "triage-run --markdown appends the receipt")

# capability negotiation against a stub backend: native when advertised, generic otherwise, --generic forces control
_SAMPLE = json.load(open(os.path.join(ROOT, "tests", "fixtures", "evidence_rows_sample.json")))
_PLANFIX = json.load(open(os.path.join(ROOT, "tests", "fixtures", "corpus_plan_fixture.json")))
class _Stub(http.server.BaseHTTPRequestHandler):
    native = True
    calls = []
    def log_message(self, *a): pass
    def _send(self, code, body):
        data = json.dumps(body).encode(); self.send_response(code); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        _Stub.calls.append(("GET", self.path))
        if self.path == "/capabilities" and _Stub.native:
            return self._send(200, {"backend": "polymath", "version": "stub", "contracts": {"retrieve-evidence-rows": "v1", "corpus-plan": "v1"}})
        if self.path.startswith("/corpora/"):
            return self._send(200, {"documents": []})
        return self._send(404, {"detail": "no"})
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        _Stub.calls.append(("POST", self.path, body.get("signal") or body.get("query")))
        if self.path == "/retrieve/plan":
            plan = _PLANFIX["expected"]
            rows = [dict(r, query_ids=[plan[i % len(plan)]["id"]]) for i, r in enumerate(_SAMPLE["evidence_rows"])]
            return self._send(200, {"plan": plan, "plan_contract": "corpus-plan-v1", "evidence_rows": rows, "evidence_contract": "retrieve-evidence-rows-v1"})
        if self.path == "/retrieve":
            return self._send(200, dict(_SAMPLE))
        return self._send(404, {"detail": "no"})
_sock = socket.socket(); _sock.bind(("127.0.0.1", 0)); _port = _sock.getsockname()[1]; _sock.close()
_srv = http.server.ThreadingHTTPServer(("127.0.0.1", _port), _Stub); threading.Thread(target=_srv.serve_forever, daemon=True).start()
_cs15 = os.path.join(tmp, "caps.json")
ctl("init", "--state", _cs15, "--signal", _PLANFIX["signal"], "--corpus", "polymath:stubcorp")
ctl("step", "--state", _cs15)                      # -> corpus (local plan compiled on entry)
_outp = os.path.join(tmp, "caps_payload.json")
def _adapter(*extra):
    r = subprocess.run([PY, os.path.join(ROOT, "python", "corpus_polymath.py"), "--state", _cs15, "--url", f"http://127.0.0.1:{_port}", "--out", _outp, *extra], capture_output=True, text=True)
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"stderr": r.stderr[-300:]}, (json.load(open(_outp)) if os.path.exists(_outp) else {})
_Stub.native = True; _Stub.calls.clear()
_note, _pay = _adapter()
_be = _pay.get("corpus_backend") or {}
ok(_be.get("mode") == "native" and _be.get("plan_source") == "polymath" and _be.get("plan_parity") is True,
   f"native backend: plan compiled by Polymath, parity with the local plan ({_be.get('mode')}, parity={_be.get('plan_parity')})")
ok(any(c[1] == "/retrieve/plan" for c in _Stub.calls) and not any(c[1] == "/retrieve" for c in _Stub.calls),
   "native mode calls /retrieve/plan once per corpus, never the per-query path")
ok(all(r.get("query_ids") for r in _pay.get("corpus_evidence") or []) and all(r["can_establish"] for r in _pay["corpus_evidence"]),
   "rows keep the server's query provenance and the docs/04 authority hints")
_Stub.calls.clear(); _note_g, _pay_g = _adapter("--generic")
ok((_pay_g.get("corpus_backend") or {}).get("mode") == "generic" and any(c[1] == "/retrieve" for c in _Stub.calls) and not any(c[1] == "/retrieve/plan" for c in _Stub.calls),
   "--generic forces the docs/18 path against the same backend (the control arm)")
_Stub.native = False; _Stub.calls.clear(); _note_n, _pay_n = _adapter()
ok((_pay_n.get("corpus_backend") or {}).get("mode") == "generic" and (_pay_n.get("corpus_backend") or {}).get("version") is None,
   "a backend without /capabilities is served generically, no error")
rc15, out15 = submit(_cs15, "corpus", _pay)
ok(rc15 == 0 and (json.load(open(_cs15))["data"].get("corpus_backend") or {}).get("mode") == "native", "corpus_backend is accepted as an optional output and lands in the state")
_srv.shutdown()

# ---------------------------------------------------------------------------
# 16. docs/21 step 3 — field evidence re-enters a run with its identity
# ---------------------------------------------------------------------------
import field_evidence as _fe
import datetime as _dt
_frow = {"id": "polymath:chunk:fe1", "kind": "chunk", "tags": ["chunk", "corpus_evergreen", "field_evidence"], "source": "polymath/field-evidence-v1 · r/PCOS · 1pon609",
         "text": 'FIELD_OBS author=u/ppklp roles=WORKAROUND_EVIDENCE|BEHAVIOR_SUPPORT purchase=no freshness=LIVE gap=gSame obs=obs_1\n"Epilator - lasts me about a week, doesn’t damage skin the way shaving does and i never get ingrown hairs"\nproblem: shaving damages skin\nworkaround: facial epilator, weekly',
         "document": {"frontmatter": {"platform": "reddit", "thread_key": "1pon609", "community": "PCOS", "source_url": "https://www.reddit.com/r/PCOS/comments/1pon609/", "exported_at": "2026-09-03", "field_evidence": "v1"}}}
_fst = {"data": {"hypotheses": [{"id": "hX", "status": "CHALLENGED"}, {"id": "hDead", "status": "REJECTED"}],
        "gaps": [{"id": "gSame", "hypothesis_id": "hX", "status": "open", "question": "anything at all"},
                 {"id": "gKw", "hypothesis_id": "hX", "status": "open", "question": "do epilators damage skin or cause ingrown hairs on coarse chin hair"},
                 {"id": "gNo", "hypothesis_id": "hX", "status": "open", "question": "portion sizes on semaglutide"},
                 {"id": "gDead", "hypothesis_id": "hDead", "status": "open", "question": "epilator skin ingrown hairs"}],
        "observations": [], "corpus_evidence": [_frow, dict(_frow, id="polymath:chunk:plain", tags=["chunk"], text="just a passage")]}}
_fc = _fe.candidates(_fst, today=_dt.date(2026, 9, 3))
_fmap = {c["gap_id"]: c for c in _fc}
ok(set(_fmap) == {"gSame", "gKw"}, f"field rows become candidates for the same gap id and keyword-matched open gaps of LIVE hypotheses only ({sorted(_fmap)})")
ok(_fmap["gSame"]["source_identity"] == {"source_family": "community", "platform": "reddit", "author_key": "u/ppklp", "thread_key": "1pon609"}
   and _fmap["gSame"]["corpus_row_id"] == "polymath:chunk:fe1" and _fmap["gSame"]["evidence_roles"] == ["WORKAROUND_EVIDENCE", "BEHAVIOR_SUPPORT"],
   "candidates keep the ORIGINAL author/thread identity, roles and cite the corpus row")
ok(_fmap["gSame"]["freshness"]["class"] == "LIVE" and _fe.recompute_freshness("LIVE", "2026-09-03", _dt.date(2026, 12, 15)) == "FAST"
   and _fe.recompute_freshness("FAST", "2026-09-03", _dt.date(2029, 1, 1)) == "SLOW", "freshness is recomputed from the export date and decays")
_fu = _ut.compute({"data": {"observations": _fc, "gaps": _fst["data"]["gaps"], "corpus_evidence": _fst["data"]["corpus_evidence"]}, "rounds": {}})
ok(_fu["observations"]["from_corpus_rows"] == 2 and _fu["gaps"]["with_corpus_support"] == 2, "the receipt counts observations from corpus rows and gaps with corpus support")
# adapter tags field rows and adds the advertised field corpus
_tag_rows = _cpm.rows_from_evidence_rows({"evidence_rows": [{"id": "chunk:z", "kind": "chunk", "doc_id": "d", "title": "t", "source": "s", "text": _frow["text"], "text_clean": _frow["text"],
                                                                 "lanes": ["vector"], "score": 0.5, "document": {"source_name": "reddit_1pon609.md", "frontmatter": _frow["document"]["frontmatter"]}}]}, "field-evidence-v1")
ok(_tag_rows and "field_evidence" in _tag_rows[0]["tags"] and _tag_rows[0]["document"]["frontmatter"]["thread_key"] == "1pon609", "adapter tags field-evidence rows and keeps the document frontmatter")
_be_f = _cpm.backend_record({"backend": "polymath", "version": "x", "contracts": {"retrieve-evidence-rows": "v1", "corpus-plan": "v1", "field-evidence-corpus": "field-evidence-v1"}}, "u")
ok(_be_f["contracts"]["field-evidence-corpus"] == "field-evidence-v1" and _be_f["mode"] == "native", "capabilities carry the field corpus id for the adapter to append")

# typed rows (TYPED-CLAIMS-V1) flow through the adapter and the receipt
_typed = _cpm.rows_from_evidence_rows({"evidence_rows": [
    {"id": "fact:f1", "kind": "graph_fact", "doc_id": "d", "title": "t", "source": "s", "text": "women USES car tweezers", "text_clean": "women USES car tweezers",
     "lanes": ["graph"], "score": 0.1, "fact": {"subject": "women", "predicate": "USES", "object": "car tweezers", "claim_kind": "workaround"}, "claim_kind": "workaround",
     "evidence": [{"doc_id": "d", "chunk_id": "c"}]},
    {"id": "chunk:c2", "kind": "chunk", "doc_id": "d", "title": "t", "source": "s", "text": "plain", "text_clean": "plain", "lanes": ["vector"], "score": 0.2}]}, "mbb")
ok(_typed[0].get("claim_kind") == "workaround" and "typed:workaround" in _typed[0]["tags"] and "claim_kind" not in _typed[1], "adapter carries claim_kind and tags typed rows")
_ust = {"data": {"corpus_evidence": _typed, "primitives": {"evidence_refs": {"workarounds": [_typed[0]["id"]], "behaviors": [_typed[1]["id"]]}}}, "rounds": {}}
_uu = _ut.compute(_ust)
ok(_uu["corpus"]["typed_rows"] == 1 and _uu["corpus"]["rows_by_claim_kind"] == {"workaround": 1} and _uu["citations"]["typed_rows_cited"] == 1
   and "typed rows cited" in _ut.to_markdown(_uu), "the receipt counts typed rows retrieved and cited")

# ---------------------------------------------------------------------------
# 17. docs/22 — the full RAG answers the plan (chat lane), corpus names
# ---------------------------------------------------------------------------
class _ChatStub(http.server.BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *a): pass
    def _send(self, code, body):
        data = json.dumps(body).encode(); self.send_response(code); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        _ChatStub.calls.append(("GET", self.path))
        if self.path == "/capabilities":
            return self._send(200, {"backend": "polymath", "version": "stub", "contracts": {"retrieve-evidence-rows": "v1", "corpus-plan": "v1", "chat-evidence": "v1"}})
        if self.path.startswith("/corpora"):
            return self._send(200, {"corpora": [{"corpus_id": "c_ab12cd34ef", "name": "Mark Builds Brands"}, {"corpus_id": "stubcorp", "name": "stubcorp"}]})
        return self._send(404, {"detail": "no"})
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        _ChatStub.calls.append(("POST", self.path, body.get("corpus_id"), body.get("message")))
        if self.path == "/retrieve/plan":
            plan = _PLANFIX["expected"]
            return self._send(200, {"plan": plan, "plan_contract": "corpus-plan-v1", "evidence_rows": [dict(r, query_ids=[plan[0]["id"]]) for r in _SAMPLE["evidence_rows"]], "evidence_contract": "retrieve-evidence-rows-v1"})
        if self.path == "/chat":
            abst = (body.get("message") or "").lower().startswith("why do people keep")   # the 'contrast' reformulation abstains
            return self._send(200, {"answer": "I don't have enough grounded evidence to answer this question." if abst else "Relevant passage: ugly pages convert when the offer is clear.",
                                    "citations": [] if abst else [{"citation_id": 1}], "claims": [{"text": "x"}],
                                    "meta": {"verdict": "insufficient_evidence" if abst else "supported", "abstained": abst, "uncovered_query_terms": ["portion"] if abst else [], "mode": "HYBRID"},
                                    "evidence_rows": _SAMPLE["evidence_rows"][:2], "evidence_contract": "retrieve-evidence-rows-v1"})
        return self._send(404, {"detail": "no"})
_sock2 = socket.socket(); _sock2.bind(("127.0.0.1", 0)); _port2 = _sock2.getsockname()[1]; _sock2.close()
_srv2 = http.server.ThreadingHTTPServer(("127.0.0.1", _port2), _ChatStub); threading.Thread(target=_srv2.serve_forever, daemon=True).start()
_cs17 = os.path.join(tmp, "chatlane.json")
ctl("init", "--state", _cs17, "--signal", _PLANFIX["signal"], "--corpus", "polymath:Mark Builds Brands")
ctl("step", "--state", _cs17)
_out17 = os.path.join(tmp, "chatlane_payload.json")
_r17 = subprocess.run([PY, os.path.join(ROOT, "python", "corpus_polymath.py"), "--state", _cs17, "--url", f"http://127.0.0.1:{_port2}", "--out", _out17], capture_output=True, text=True)
_note17 = json.loads(_r17.stdout.strip().splitlines()[-1]) if _r17.stdout.strip() else {"stderr": _r17.stderr[-300:]}
_pay17 = json.load(open(_out17)) if os.path.exists(_out17) else {}
_be17 = _pay17.get("corpus_backend") or {}
ok(_be17.get("mode") == "native" and _be17.get("lane") == "chat+plan" and any(c[1] == "/chat" for c in _ChatStub.calls) and any(c[1] == "/retrieve/plan" for c in _ChatStub.calls) and not any(c[1] == "/retrieve" for c in _ChatStub.calls),
   f"native default lane = full RAG answers per reformulation PLUS the EXPLORE rows; never the per-query path ({_note17.get('lane')}, {_note17.get('mode')})")
ok(all(a.get("asked_as") and len(a["asked_as"]) < len(a["question"]) + 40 and a["asked_as"].endswith("?") for a in (_pay17.get("corpus_answers") or [])),
   "the answer path is asked a short concrete question built from the reformulation's terms")
ok(all(c[2] == "c_ab12cd34ef" for c in _ChatStub.calls if c[0] == "POST") and _be17.get("corpus_names", {}).get("c_ab12cd34ef") == "Mark Builds Brands",
   "a run identity by display NAME resolves to the immutable corpus id")
_ans17 = _pay17.get("corpus_answers") or []
ok(_ans17 and all(a["authority"] == "CORPUS_SYNTHESIS" for a in _ans17) and any(a["abstained"] for a in _ans17) and any(not a["abstained"] for a in _ans17),
   f"answers are recorded as CORPUS_SYNTHESIS, admitted and abstained alike ({len(_ans17)} asked, {sum(1 for a in _ans17 if not a['abstained'])} admitted)")
ok(all(set(a["citations"]) <= {r["id"] for r in _pay17["corpus_evidence"]} for a in _ans17) and all(r.get("query_ids") for r in _pay17["corpus_evidence"]),
   "every answer cites rows that are in corpus_evidence; rows keep query provenance")
rc17, out17 = submit(_cs17, "corpus", _pay17)
ok(rc17 == 0 and len(json.load(open(_cs17))["data"].get("corpus_answers") or []) == len(_ans17), "corpus_answers land in the state as an optional output")
_u17 = _ut.compute(json.load(open(_cs17)))
ok(_u17["corpus"]["answers"] == len(_ans17) and _u17["corpus"]["answers_admitted"] == sum(1 for a in _ans17 if not a["abstained"]), "the receipt counts answers asked and admitted")
_srv2.shutdown()

# the documents seed, they do not bound: the primitives prompt must ask about the PEOPLE and allow inferred physical jobs
_pp = open(os.path.join(ROOT, "prompts", "opportunity_primitives.md"), encoding="utf-8").read()
ok("inferred:" in _pp and "population" in _pp and "AFTER its evidence boundary" in _pp and "A named population is never required" in _pp
   and "no human population or activity" not in _pp,
   "primitives prompt reasons about people AND objects, allows inferred jobs behind the evidence boundary, and never requires a named population (docs/26 item 8)")

# ---------------------------------------------------------------------------
# 18. docs/23 — registry maintenance: candidates -> deterministic review -> L5 approval -> patch, never a live edit
# ---------------------------------------------------------------------------
import hashlib as _hl
import memory as _mem
_mg = graphmod.load_graph("maintenance_graph.yaml")
ok(all((_mg["nodes"][n] or {}).get("executor", "").startswith("python.") and (_mg["nodes"][n] or {}).get("executor") in executors.EXECUTORS
       for n in ("collect", "normalize", "resolve_type", "deduplicate", "novelty_check", "evidence_review", "promotion_gate", "patch", "compile_registry", "regression")),
   "every maintenance transform/gate has a registered executor (the layer is no longer deferred)")
_ms = _models.new_state("maint_t18", "maintenance walk probe"); _ms["graph_file"] = "maintenance_graph.yaml"; _ms["node"] = "collect"
_ms["data"]["registry_candidates"] = [
    {"id": "rc_mech", "kind": "MECHANISM_CANDIDATE", "name": "cue-anchored dose staging", "payload": {"principle": "stage each dose at its cue", "activity": "take a daily supplement regime", "task": "retrieve the dose at the cue"}, "evidence_refs": ["o1", "o2"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 3},
    {"id": "rc_act", "kind": "ACTIVITY_CANDIDATE", "name": "protect skin while removing coarse facial hair", "payload": {"task": "remove coarse chin hair without irritation", "context": "daily bathroom routine"}, "evidence_refs": ["o3"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 2},
    {"id": "rc_fric_ok", "kind": "FRICTION_CANDIDATE", "name": "movement_restriction", "payload": {"friction_family": "movement_restriction", "description": "kit restricts gesture"}, "evidence_refs": ["o1"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 2},
    {"id": "rc_fric_new", "kind": "FRICTION_CANDIDATE", "name": "sock_slippage_v9", "payload": {"friction_family": "sock_slippage_v9"}, "evidence_refs": ["o4"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 3},
    {"id": "rc_query", "kind": "QUERY_PATTERN_CANDIDATE", "name": "reddit:tape transmitter belt", "payload": {"channel": "reddit", "query": "tape transmitter belt", "roles_yielded": ["WORKAROUND_EVIDENCE"]}, "evidence_refs": ["o1"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 3},
    {"id": "rc_src", "kind": "SOURCE_CANDIDATE", "name": "reddit:community", "payload": {"platform": "reddit", "source_family": "community", "roles_yielded": ["FRICTION_EVIDENCE"]}, "evidence_refs": ["o1"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 4},
    {"id": "rc_thin", "kind": "MECHANISM_CANDIDATE", "name": "one-run wonder", "payload": {}, "evidence_refs": ["o9"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 1},
    {"id": "rc_motif", "kind": "REASONING_MOTIF_CANDIDATE", "name": "PROBLEM_LED:x", "payload": {}, "evidence_refs": ["o1"], "source_run": "r4", "authority": "CANDIDATE", "status": "PROPOSED", "runs": 3}]
_mem.create_run(_ms["run_id"], _ms["data"]["signal"], _ms["node"])
_mst = os.path.join(tmp, "maint_t18.json")
with open(_mst, "w", encoding="utf-8") as f:
    json.dump(_ms, f)
_live_pack = os.path.join(ROOT, "registry", "trailsignal", "outdoor_activity_niche_seed.csv")
_live_tpl = os.path.join(ROOT, "registry", "trailsignal", "search_query_templates.csv")
_h_before = (_hl.sha256(open(_live_pack, "rb").read()).hexdigest(), _hl.sha256(open(_live_tpl, "rb").read()).hexdigest())
_steps18 = []; _research_visits18 = 0
for _ in range(12):
    _cur = json.load(open(_mst))
    if _cur["node"] == "research":
        # the harness has no web stack: an honest capability deficit, then the review continues and holds the thin candidate
        _research_visits18 += 1
        submit(_mst, "research", {"capability_failure": {"capability": "web_research", "detail": "harness: no field research lane"}})
    if _cur["node"] in ("human_approval", "stop", "publish"):
        break
    rc, o = ctl("step", "--state", _mst); _steps18.append((o.get("advanced_to") or o.get("error"), (o.get("note") or "")[:80]))
_msn = json.load(open(_mst))
ok(_research_visits18 == 1, f"a thin candidate earns exactly ONE research visit before it is held ({_research_visits18})")
ok(_msn["node"] == "human_approval" and _msn.get("verdict") == "NEEDS_APPROVAL",
   f"walk: collect -> ... -> promotion_gate -> human_approval with NEEDS_APPROVAL ({_msn['node']}, {_msn.get('verdict')}; {_steps18[-1]})")
_pst = {c["id"]: c for c in _msn["data"]["registry_candidates"]}
ok(_pst["rc_mech"]["promotion_status"] == "ELIGIBLE" and _pst["rc_query"]["promotion_status"] == "ELIGIBLE" and _pst["rc_src"]["promotion_status"] == "ELIGIBLE",
   "recurring, evidenced candidates with a table are ELIGIBLE")
ok(_pst["rc_fric_new"]["promotion_status"] == "HELD" and "friction_library" in _pst["rc_fric_new"]["hold_reason"],
   "a friction family not in the library is HELD (vertical growth is never invented)")
ok(_pst["rc_thin"]["promotion_status"] == "HELD" and _pst["rc_motif"]["promotion_status"] == "HELD" and _pst["rc_fric_ok"]["promotion_status"] == "EXISTING",
   f"thin evidence and motifs are HELD; a known family is EXISTING ({_pst['rc_fric_ok'].get('dedupe_status')})")
ok(all("draft_row" in c for c in _msn["data"]["registry_candidates"]) and _pst["rc_mech"]["draft_row"]["fact_status"] == "hypothesis" and _pst["rc_mech"]["draft_row"]["product_territory"] == "cue-anchored dose staging",
   "eligible seeds are drafted in the AtomicActivitySeed schema with fact_status hypothesis")
_apps = [{"candidate_id": "rc_mech", "decision": "approve", "approver": "test"}, {"candidate_id": "rc_act", "decision": "approve"},
         {"candidate_id": "rc_query", "decision": "approve"}, {"candidate_id": "rc_src", "decision": "reject", "note": "HIGH risk, not now"}]
rc18, out18 = submit(_mst, "human_approval", {"approvals": _apps})
ok(rc18 == 0, f"L5 approvals are an accepted output ({out18.get('schema_errors')})")
for _ in range(4):
    rc, o = ctl("step", "--state", _mst); _steps18.append((o.get("advanced_to") or o.get("error"), (o.get("note") or "")[:90]))
_msn = json.load(open(_mst)); _rp = _msn["data"].get("registry_patch") or {}
ok(_msn["node"] == "publish" and _msn.get("verdict") == "MAINTENANCE_COMPLETE", f"patch -> compile -> regression -> publish ({_msn['node']}, {_msn.get('verdict')}; {_steps18[-3:]})")
ok(_rp.get("rows_by_table", {}).get("discovered_activity_niche_seed.csv") == 2 and _rp["rows_by_table"].get("search_query_templates.csv") == 1 and "source_registry.csv" not in _rp["rows_by_table"],
   f"patch holds 2 seeds + 1 query template; the rejected source is absent ({_rp.get('rows_by_table')})")
ok(os.path.exists(os.path.join(ROOT, _rp["diff"])) and os.path.getsize(os.path.join(ROOT, _rp["diff"])) > 0 and all(os.path.exists(os.path.join(ROOT, a["src"])) for a in _rp["apply"]),
   "a unified diff and patched copies exist under registry/patches/<run>")
_h_after = (_hl.sha256(open(_live_pack, "rb").read()).hexdigest(), _hl.sha256(open(_live_tpl, "rb").read()).hexdigest())
ok(_h_after == _h_before, "the LIVE registry files are byte-identical — nothing is promoted without a human copy + commit")
ok(_rp["compile"]["valid"] and _rp["compile"]["seeds"] == _rp["compile"]["seeds_before"] + 2 and _rp["compile"]["templates"] == _rp["compile"]["templates_before"] + 1,
   f"the overlay registry compiles VALID with +2 seeds, +1 template ({_rp['compile']['seeds_before']}→{_rp['compile']['seeds']})")
ok(_rp["regression"]["passed"], "regression (doctor + overlay compile) passed")
import shutil as _sh
_sh.rmtree(os.path.join(ROOT, "registry", "patches", "maint_t18"), ignore_errors=True)
try:
    os.remove(os.path.join(ROOT, "registry", "patches", "maint_t18.diff"))
except OSError:
    pass

# ---------------------------------------------------------------------------
# 19. docs/24 — evidence channels with tool chains; sourcing on Alibaba + CJdropshipping
# ---------------------------------------------------------------------------
_gq19 = {"run_id": "gq19", "data": {"communities": ["r/PCOS"], "hypotheses": [{"id": "h1", "status": "CHALLENGED", "gaps": ["do PCOS users say tweezers fail on coarse chin hair?"]}],
         "gaps": [{"id": "g19", "hypothesis_id": "h1", "question": "do PCOS users say tweezers fail on coarse chin hair?", "status": "open", "required_evidence_roles": ["FRICTION_EVIDENCE"]}], "queries": []}}
executors.gap_compiler(_gq19, pol)
_q19 = {q["channel"]: q for q in _gq19["data"]["queries"]}
ok(set(_q19) == set(pol["evidence_channels"]) and [q["channel"] for q in _gq19["data"]["queries"]] == pol["evidence_channels"],
   f"every enabled evidence channel is compiled per gap, in policy order ({list(_q19)})")
ok(all(q.get("tools") and q.get("identity") and q.get("source_family") for q in _q19.values()) and "opencli amazon discussion" in " ".join(_q19["amazon_reviews"]["tools"])
   and "opencli youtube comments" in " ".join(_q19["youtube"]["tools"]) and "opencli xiaohongshu comments" in " ".join(_q19["xiaohongshu"]["tools"]),
   "each channel query carries the exact tool chain, the identity key and the source family")
ok(_q19["amazon_reviews"]["source_family"] == "review" and "FRICTION_EVIDENCE" not in _q19["amazon_reviews"]["expected_evidence_roles"] and "PRODUCT_COMPLAINT" in _q19["amazon_reviews"]["expected_evidence_roles"],
   "amazon reviews are the review family: product complaints, never life-without-the-product friction")
_pol19 = copy.deepcopy(pol); _pol19["evidence_channels"] = ["reddit", "amazon_reviews"]
_gq19b = copy.deepcopy(_gq19); _gq19b["data"]["queries"] = []; _gq19b["data"]["gaps"][0]["id"] = "g19b"; _gq19b["data"]["hypotheses"][0]["gaps"] = ["another gap question about coarse chin hair"]
executors.gap_compiler(_gq19b, _pol19)
ok({q["channel"] for q in _gq19b["data"]["queries"] if q["gap_id"] != "g19"} == {"reddit", "amazon_reviews"}, "channels are a policy switch: disabling one removes its queries")
import verifiers as _vf
_rev_ok = {"id": "r1", "gap_id": "g19", "source": "amazon.com/dp/B0X", "quote_ref": "broke after a week so I tape it", "evidence_roles": ["PRODUCT_COMPLAINT", "WORKAROUND_EVIDENCE"],
           "freshness": {"class": "LIVE"}, "source_identity": {"source_family": "review", "platform": "amazon", "author_key": "reviewer_a", "thread_key": "B0X"}}
_a1, _e1 = _vf.admit_observations([_rev_ok], pol)
_a2, _e2 = _vf.admit_observations([dict(_rev_ok, id="r2", evidence_roles=["FRICTION_EVIDENCE"])], pol)
ok(not _e1 and _e2 and any("may not establish FRICTION_EVIDENCE" in e for e in _e2), "an Amazon review is admitted for complaint/workaround and refused for FRICTION_EVIDENCE")
_sp19 = _models.new_state("src19", "sourcing channels"); _sp19["node"] = "normalize_supplier"
_sp19["data"]["mechanisms"] = [{"id": "m1", "name": "wearable-wireless-audio", "status": "SUPPORTED", "hypothesis_id": "h1", "supporting_observation_ids": ["a1"]}]
_sp19["data"]["product_concepts"] = [{"id": "pcA", "mechanism_id": "m1", "name": "Clip mic", "form_factor": "wearable clip", "target_moment": "t", "variations": [{"name": "lite"}, {"name": "pro"}], "evidence_refs": ["a1"]}]
_sp19["data"]["supplier_candidates"] = [
    {"id": "s_cj", "product_name": "Wireless Clip Mic", "supplier_name": "CJ", "price_raw": "$4.20", "moq_raw": "not shown in listing snippet", "url": "https://cjdropshipping.com/product/wireless-clip-mic-p-1A2B3C4D.html", "concept_id": "pcA", "mechanism_id": "m1", "channel": "cjdropshipping"},
    {"id": "s_ali", "product_name": "Wireless Clip Mic Kit", "supplier_name": "Shenzhen", "price_raw": "US $3.10", "moq_raw": "not shown in listing snippet", "url": "https://www.alibaba.com/product-detail/x_1601000000000.html", "concept_id": "pcA", "mechanism_id": "m1", "channel": "alibaba"}]
executors.supplier(_sp19, pol)
_by19 = {s["id"]: s for s in _sp19["data"]["supplier_candidates"]}
ok(_by19["s_cj"]["moq_units"] == 1 and "default" in _by19["s_cj"].get("moq_note", "") and _by19["s_ali"]["moq_units"] is None,
   "a CJdropshipping row without MOQ text defaults to 1 (said so on the row); an Alibaba row does not")
import sourcing_exa as _sx
_cj = _sx.parse_listing("cjdropshipping", {"title": "Wireless Clip Mic | CJ", "url": "https://cjdropshipping.com/product/wireless-clip-mic-p-1A2B3C4D.html", "text": "Price: $4.20 ships from US warehouse"})
_al = _sx.parse_listing("alibaba", {"title": "Clip Mic Kit", "url": "https://www.alibaba.com/product-detail/Clip-Mic_1601234567890.html", "text": "US $3.10-3.90 / piece Min. order: 50 pieces"})
ok(_cj and _cj["channel"] == "cjdropshipping" and _cj["price_raw"] == "$4.20" and _cj["moq_raw"] == _sx.NOT_SHOWN
   and _al and _al["moq_raw"].lower().startswith("min. order") and _sx.parse_listing("alibaba", {"title": "x", "url": "https://example.com/p", "text": ""}) is None,
   "the sourcing helper parses CJ and Alibaba listing URLs, keeps price/MOQ verbatim, and never invents a missing value")

# ---------------------------------------------------------------------------
# 20. LIVED-WORLD-V2 (docs/25): population discovery, evidence cards, provenance
# ---------------------------------------------------------------------------
import lived_world as _lwm  # noqa: E402
import provenance as _pvm  # noqa: E402
import models as _models20  # noqa: E402
_pol20 = graphmod.load_policies()
# 20a. schemas are real: each new object validates / fails on its authority fields
ok(not _models20.validate({"id": "l1", "kind": "COMMUNITY", "name": "r/x", "source_lane": "OPEN_FIELD", "nominated_by": ["search receipt"],
                            "authority": "LEAD", "status": "NOMINATED"}, "population_lead"), "population_lead schema accepts a well-formed lead")
ok(any("authority" in e for e in _models20.validate({"id": "l1", "kind": "COMMUNITY", "name": "r/x", "source_lane": "OPEN_FIELD",
                                                      "nominated_by": ["x"], "authority": "DEMAND", "status": "NOMINATED"}, "population_lead")),
   "population_lead schema refuses any authority but LEAD")
ok(any("unknowns" in e for e in _models20.validate({"id": "s", "authority": "RECONSTRUCTED"}, "lived_situation")),
   "lived_situation schema requires unknowns (preserved, never invented away)")
ok(any("THIN" in e or "authority" in e for e in _models20.validate({"id": "c", "community": "x", "friction_family": "f", "card_ids": ["a"], "record_ids": ["r"],
                                                                     "record_count": 1, "thread_count": 1, "independent_voices": 1, "authority": "STRONG", "unknowns": []}, "lived_evidence_cluster")),
   "lived_evidence_cluster authority is THIN or ANCHOR only")
ok(any("collection_roles" in e for e in _models20.validate({"id": "p", "name": "n", "physical_jobs": ["j"], "moments": ["m"], "collection_roles": ["HERO"]}, "product_slot")),
   "product_slot collection_roles are the five loadout roles")
# 20b. nomination lanes: signal communities (seed), corpus population_leads, prior field rows, registry situations
_st = _models20.new_state("lw20", "SEED: Primal Queen sells organ supplements to postpartum and perimenopausal women. Creators record standing up.")
_st["node"] = "population_nominate"
_st["data"]["communities"] = ["r/Menopause"]
_st["data"]["primitives"] = {"generative_signal": True, "frictions": ["occupied_hand"], "shared_predicates": ["access", "attach"],
                             "population_leads": [{"name": "night-shift nurses", "why": "habit book names them", "evidence_refs": ["e1"], "frictions": ["access_latency"]},
                                                  "perimenopausal women"]}
_st["data"]["corpus_evidence"] = [{"id": "fe1", "summary": "FIELD_OBS author=u/a roles=FRICTION_EVIDENCE purchase=no freshness=LIVE gap=g obs=o\n\"quote\"\nproblem: x", "tags": ["chunk", "field_evidence"],
                                   "document": {"frontmatter": {"community": "Zepbound", "platform": "reddit", "thread_key": "t1", "exported_at": "2026-09-01"}}}]
note20 = _lwm.nominate(_st, _pol20)
_leads = _lwm.all_leads(_st); _by_lane = {}
for l in _leads: _by_lane.setdefault(l["source_lane"], []).append(l)
ok(set(_by_lane) >= {"SIGNAL", "CORPUS", "REGISTRY", "FIELD_RECORDS"} and all(l["authority"] == "LEAD" for l in _leads),
   f"all four nomination lanes produce leads, every one authority LEAD ({ {k: len(v) for k, v in _by_lane.items()} })")
_seedy = {l["name"]: l["seed_population"] for l in _leads}
ok(_seedy.get("r/Menopause") is True and _seedy.get("perimenopausal women") is True and _seedy.get("night-shift nurses") is False,
   "leads restating the signal's own population are marked seed_population; a book-named population is not")
_rank = _lwm.rank_leads(_st, _pol20); _byid = _lwm.lead_by_id(_st)
ok(_byid[_rank[0]]["seed_population"] is False and all(_byid[i]["voi"] >= _byid[j]["voi"] for i, j in zip(_rank, _rank[1:])),
   "VOI ranking is monotone and discounts the seed population — non-seed leads are visited first")
ok(all(q.get("tools") and q.get("lead_id") for l in _leads for q in l["channel_queries"])
   and any(q.get("subreddit_hints") == ["zepbound"] for l in _by_lane["FIELD_RECORDS"] for q in l["channel_queries"]),
   "lead channel queries carry tool chains and the community key as the reddit scope")
# 20c. queue rounds, batch size, stagnation and wall clock are ceilings, not vibes
_pol_small = copy.deepcopy(_pol20); _pol_small["lived_world"]["batch_size"] = 2; _pol_small["lived_world"]["max_rounds"] = 2
_lwm.queue(_st, _pol_small)
ok(len(_st["population_queue"]["batch"]) == 2 and all(_byid[i]["status"] == "INSTANTIATING" for i in _st["population_queue"]["batch"]),
   "queue hands exactly batch_size leads and marks them INSTANTIATING")
_lwm.cards(_st, _pol_small)                      # no records: the batch is EXHAUSTED for now
ok(all(_byid[i]["status"] == "EXHAUSTED" for i in _st["population_queue"]["batch"]), "a visited lead with no records is EXHAUSTED, never padded")
_lwm.gate(_st, _pol_small)
ok(_st["population_loop"]["continue"] is True and _st["population_loop"]["rounds"] == 1, "no ANCHOR yet and budget left: one more round")
_lwm.queue(_st, _pol_small); _lwm.cards(_st, _pol_small); _lwm.gate(_st, _pol_small)
ok(_st["population_loop"]["continue"] is False and ("stagnation" in _st["population_loop"]["reason"] or "ceiling" in _st["population_loop"]["reason"]),
   f"stagnation / round ceiling stops the loop honestly ({_st['population_loop']['reason']})")
_st["population_queue"]["started_at"] = "2026-01-01T00:00:00+00:00"; _st["population_loop"] = {}
_lwm.gate(_st, _pol_small)
ok("wall clock" in _st["population_loop"]["reason"], "wall-clock ceiling is enforced")
# 20d. anchor threshold is configurable and decides THIN vs ANCHOR deterministically
def _r20(i, comm, author, thread):
    return {"id": f"r{i}", "lead_id": _leads[0]["id"], "source": f"u{i}", "quote_ref": f"q{i}", "community": comm, "problem": "p", "workaround": "w" if i % 2 else "",
            "evidence_roles": ["FRICTION_EVIDENCE"], "freshness": {"class": "LIVE"},
            "source_identity": {"source_family": "community", "platform": "reddit", "author_key": author, "thread_key": thread}}
_st["data"]["field_records"] = [_r20(i, "r/Zepbound", f"a{i}", f"t{i % 2}") for i in range(5)]
_lwm.cards(_st, _pol20)
ok(_st["data"]["lived_clusters"][0]["authority"] == "THIN" and _st["data"]["lived_clusters"][0]["independent_voices"] == 2,
   "5 authors in 2 threads = 2 voices = THIN (same thread is one voice, docs/04 §16)")
_st["data"]["field_records"] = [_r20(i, "r/Zepbound", f"a{i}", f"t{i % 3}") for i in range(5)]
_lwm.cards(_st, _pol20)
ok(_st["data"]["lived_clusters"][0]["authority"] == "ANCHOR", "5 records / 3 threads / 3 voices = ANCHOR at the default threshold")
_pol_tight = copy.deepcopy(_pol20); _pol_tight["lived_world"]["anchor_threshold"]["min_records"] = 8
_lwm.cards(_st, _pol_tight)
ok(_st["data"]["lived_clusters"][0]["authority"] == "THIN" and _st["data"]["lived_clusters"][0]["threshold"]["min_records"] == 8,
   "raising the threshold flips the same cluster to THIN — configurable, recorded on the cluster")
_st["data"]["field_records"] = [_r20(i, "r/Zepbound", "one_author", "one_thread") for i in range(6)]
_lwm.cards(_st, _pol20)
ok(_st["data"]["lived_clusters"][0]["authority"] == "THIN" and _st["data"]["lived_clusters"][0]["independent_voices"] == 1
   and len(_st["data"]["participant_cards"]) == 1,
   "six records from one author in one thread = ONE voice = THIN (independence law)")
# 20e. corpus question compiler: friction / mechanism level, capped, never per person
_st["data"]["field_records"] = [dict(_r20(i, "r/Zepbound", f"a{i}", f"t{i % 3}"), friction_family="small_parts") for i in range(5)]
_lwm.cards(_st, _pol20); _lwm.compile_corpus_questions(_st, _pol20)
ok(_st["data"]["corpus_questions"] and any("small parts" in q["question"] for q in _st["data"]["corpus_questions"])
   and any(q["question"].startswith("What explains this workaround") for q in _st["data"]["corpus_questions"])
   and not any("u/" in q["question"] or "a0" in q["question"] for q in _st["data"]["corpus_questions"]),
   f"questions ask about the friction and the workaround, never about a person ({_st['data']['corpus_questions'][0]['question'][:60]})")
_pol_cap = copy.deepcopy(_pol20); _pol_cap["corpus"]["max_questions"] = 1
_lwm.compile_corpus_questions(_st, _pol_cap)
ok(len(_st["data"]["corpus_questions"]) == 1, "question count honours corpus.max_questions")
# 20f. CORPUS_EXAMPLE tagging is deterministic and never drops a row
_rows = [{"id": "d1", "kind": "document", "doc_id": "D", "summary": "profile", "text": "profile", "document_summary": {"major_entities": ["Primal Queen", "market"]}},
         {"id": "c1", "kind": "chunk", "doc_id": "D", "summary": "Primal Queen sells organ supplements to postpartum women", "text": "Primal Queen sells organ supplements to postpartum women", "tags": ["chunk"]},
         {"id": "c2", "kind": "chunk", "doc_id": "D", "summary": "enter a proven market and carve out a specific segment", "text": "enter a proven market and carve out a specific segment", "tags": ["chunk"]}]
_n = _pvm.tag_corpus_examples(_rows, ["hydrogen water bottle"])
ok(_n == 1 and "CORPUS_EXAMPLE" in _rows[1]["tags"] and "CORPUS_EXAMPLE" not in _rows[2]["tags"] and _rows[1]["example_terms"] == ["Primal Queen"]
   and len(_rows) == 3,
   "rows naming a document's proper-noun entity are tagged CORPUS_EXAMPLE; the mechanism row is not; nothing is dropped")
# 20g. provenance: echo lineage vs legal overlap vs field origin
_ps = _models20.new_state("prov20", "seed"); _pd = _ps["data"]
_pd["corpus_evidence"] = _rows
_pd["hypotheses"] = [{"id": "h_echo", "status": "SUPPORTED"}, {"id": "h_ok", "status": "SUPPORTED", "lived_anchor_ids": ["cl1"]}]
_pd["mechanisms"] = [{"id": "m_echo", "hypothesis_id": "h_echo", "status": "SUPPORTED"}, {"id": "m_ok", "hypothesis_id": "h_ok", "status": "SUPPORTED"}]
_pd["observations"] = [{"id": f"o{i}", "gap_id": "g", "community": "r/Menopause", "quote_ref": "q", "problem": "p", "evidence_roles": ["FRICTION_EVIDENCE"], "freshness": {"class": "LIVE"},
                        "source_identity": {"source_family": "community", "platform": "reddit", "author_key": f"oa{i}", "thread_key": f"ot{i}"}} for i in range(2)]
_pd["field_records"] = [{"id": f"f{i}", "lead_id": "l", "community": c, "quote_ref": "q", "problem": "p", "workaround": "uses a magnetic pill caddy", "products_named": ["pill caddy"],
                         "evidence_roles": ["WORKAROUND_EVIDENCE"], "freshness": {"class": "LIVE"},
                         "source_identity": {"source_family": "community", "platform": "reddit", "author_key": f"fa{i}", "thread_key": f"ft{i}"}}
                        for i, c in enumerate(["r/Zepbound", "r/Zepbound", "r/PCOS", "r/PCOS"])]
_pd["lived_clusters"] = [{"id": "cl1", "authority": "ANCHOR", "record_ids": ["f0", "f1", "f2", "f3"], "community": "zepbound", "seed_population": False}]
_pd["product_concepts"] = [{"id": "pc_echo", "mechanism_id": "m_echo", "name": "Organ supplements for postpartum women", "form_factor": "supplement", "evidence_refs": ["o0", "o1"]},
                           {"id": "pc_legal", "mechanism_id": "m_ok", "name": "Organ supplement dose caddy", "form_factor": "supplement caddy", "evidence_refs": ["f0", "f1", "f2", "f3", "o0"]},
                           {"id": "pc_field", "mechanism_id": "m_ok", "name": "Magnetic pill caddy", "form_factor": "magnetic caddy", "evidence_refs": ["f0", "f2", "f3"]}]
_pd["leads"] = [{"id": "L1", "concept_id": "pc_echo", "product_name": "organ caps"}, {"id": "L2", "concept_id": "pc_legal", "product_name": "caddy"}]
_sum = _pvm.enforce(_ps, _pol20)
_pv = {r["concept_id"]: r for r in _pd["provenance"]}
ok(_pv["pc_echo"]["verdict"] == "CORPUS_ECHO_UNGROUNDED" and _pv["pc_echo"]["example_overlap"],
   "lineage corpus example → same noun → same-noun search only = CORPUS_ECHO_UNGROUNDED")
ok(_pv["pc_legal"]["verdict"] == "GROUNDED" and _pv["pc_legal"]["example_overlap"],
   "the SAME category stays legal when independent participants across communities ground it")
ok(_pv["pc_field"]["field_originated"] is True and _pv["pc_echo"]["field_originated"] is False,
   "a noun that lives only in field records is field-originated; the echoed noun is not")
ok(len(_pd["leads"]) == 1 and _pd["leads"][0]["concept_id"] == "pc_legal" and _pd["excluded_leads"] and _sum["excluded_leads"] == 1,
   "echo leads are excluded with the reason; grounded leads survive")
_cc = _pvm.corpus_contribution(_ps)
ok(_cc["rows_retrieved"] == 3 and _cc["rows_cited"] == 0 and _cc["cited_share_of_shelf"] == 0.0,
   "contribution counts CITED rows, so a fully retrieved shelf with nothing cited scores zero")
_pd["hypotheses"][1]["hop_refs"] = {"0": ["c2"]}
_cc = _pvm.corpus_contribution(_ps)
ok(_cc["rows_cited"] == 1 and _cc["mechanism_only_contributions"] == 1 and _cc["example_rows_cited"] == 0,
   "a cited mechanism row that shares no noun with any concept is a mechanism-only contribution")
# 20h. prior field rows re-enter as field_records for nominated leads (origin PRIOR_RUN)
import field_evidence as _fe20  # noqa: E402
_fs = _models20.new_state("fe20", "s"); _fs["data"]["community_leads"] = [{"id": "lz", "kind": "COMMUNITY", "name": "r/Zepbound", "community_key": "Zepbound", "source_lane": "SIGNAL", "nominated_by": ["signal"], "authority": "LEAD", "status": "NOMINATED"}]
_fs["data"]["corpus_evidence"] = [{"id": "row9", "tags": ["chunk", "field_evidence"], "source": "https://reddit.com/r/Zepbound/t9",
                                   "text": "FIELD_OBS author=u/zed roles=WORKAROUND_EVIDENCE|FRICTION_EVIDENCE purchase=yes freshness=LIVE gap=g1 obs=o1\n\"I pre-portion into tiny jars\"\nproblem: cannot finish plates\nworkaround: tiny jars",
                                   "document": {"frontmatter": {"community": "Zepbound", "platform": "reddit", "thread_key": "t9", "exported_at": "2026-09-01"}}}]
_recs = _fe20.lead_candidates(_fs, today=__import__("datetime").date(2026, 9, 4))
ok(len(_recs) == 1 and _recs[0]["lead_id"] == "lz" and _recs[0]["origin"] == "PRIOR_RUN" and _recs[0]["source_identity"]["author_key"] == "u/zed"
   and _recs[0]["freshness"]["class"] == "LIVE" and not _lwm.validate_records(_recs, _fs, _pol20),
   "prior field rows map to their community's lead with the original author and recomputed freshness, and pass the record contract")
# 20i. the calibration acceptance test runs on a finished state and reports per-criterion receipts
_acc = subprocess.run([PY, os.path.join(ROOT, "tests", "calibration_acceptance.py"), "--state", pos, "--heterogeneous-docs", "Some Novel", "--trap-text", "pillow"], capture_output=True, text=True)
_rep = json.loads(_acc.stdout)
ok(set(_rep["statuses"]) == {"corpus_independence", "heterogeneous_source_reasoning", "noun_echo_resistance", "legitimate_echo_survival",
                              "latent_population_discovery", "field_originated_opportunity", "irrelevant_source_rejection", "hypothesis_death"}
   and _acc.returncode == (0 if _rep["pass"] else 1) and "cited_share_of_shelf" in _rep["diagnostics"],
   "calibration acceptance reports the eight canaries (docs/26 §6) with shelf share as a diagnostic only")
ok(_rep["statuses"]["corpus_independence"] == "PASS" and _rep["statuses"]["latent_population_discovery"] == "PASS"
   and _rep["statuses"]["field_originated_opportunity"] == "PASS" and _rep["statuses"]["irrelevant_source_rejection"] == "PASS"
   and _rep["statuses"]["hypothesis_death"] == "PASS" and _rep["statuses"]["noun_echo_resistance"] == "NOT_TRIGGERED",
   f"the synthetic walk earns the mandatory canaries and reports untriggered ones honestly ({_rep['statuses']})")
ok(_rep["statuses"]["heterogeneous_source_reasoning"] == "FAIL" and _rep["pass"] is False,
   "a configured heterogeneous document that nothing built on FAILS canary 2 and the run (the novel row was IRRELEVANT here)")
_acc2 = subprocess.run([PY, os.path.join(ROOT, "tests", "calibration_acceptance.py"), "--state", pos, "--trap-text", "pillow"], capture_output=True, text=True)
_rep2 = json.loads(_acc2.stdout)
ok(_rep2["statuses"]["heterogeneous_source_reasoning"] == "NOT_EVALUATED" and _rep2["pass"] is True and _acc2.returncode == 0,
   "without configured heterogeneous documents canary 2 is NOT_EVALUATED and the synthetic walk passes")
_acc3 = subprocess.run([PY, os.path.join(ROOT, "tests", "calibration_acceptance.py"), "--state", pos], capture_output=True, text=True)
_rep3 = json.loads(_acc3.stdout)
ok(_rep3["statuses"]["irrelevant_source_rejection"] == "NOT_EVALUATED" and _rep3["pass"] is False,
   "without a configured trap canary 7 is NOT_EVALUATED and a mandatory canary cannot be passed by vibes (item 6)")
ok(doctor.run()["ok"], "doctor green over the lived-world surface")

# ---------------------------------------------------------------------------
# 21. docs/26 — source-agnostic interpretation: schemas, latent lane, relevance law, corpus_named, canaries
# ---------------------------------------------------------------------------
ok(not _models20.validate({"id": "s", "kind": "IDENTITY_SIGNAL", "text": "t", "evidence_refs": ["r"], "authority": "LATENT_HYPOTHESIS"}, "latent_structure")
   and any("kind" in e for e in _models20.validate({"id": "s", "kind": "VIBE", "text": "t", "evidence_refs": ["r"], "authority": "LATENT_HYPOTHESIS"}, "latent_structure")),
   "latent_structure schema: 24 typed kinds, authority LATENT_HYPOTHESIS")
ok(any("evidentiary_authority" in e for e in _models20.validate({"id": "o", "kind": "OBSERVED_PRODUCT", "name": "socks", "evidence_refs": ["r"], "evidentiary_authority": "HIGH"}, "corpus_observation")),
   "corpus_observation: a named product never carries authority for current demand")
_st21 = _models20.new_state("lw21", "seed about a guitar left in the middle of the room"); _st21["node"] = "population_nominate"
_st21["data"]["primitives"] = {"generative_signal": True, "frictions": [], "shared_predicates": []}
_st21["data"]["latent_structures"] = [{"id": f"s{i}", "kind": "ACCESS_PROBLEM", "text": f"reaching a small item {i} while both hands hold something", "evidence_refs": ["e1"], "authority": "LATENT_HYPOTHESIS"} for i in range(9)]
_st21["data"]["latent_structures"].append({"id": "s_env", "kind": "ENVIRONMENT", "text": "a damp cellar", "evidence_refs": ["e1"], "authority": "LATENT_HYPOTHESIS"})
_lwm.nominate(_st21, _pol20)
_lat21 = [l for l in _lwm.all_leads(_st21) if l.get("search_mode") == "LATENT"]
ok(len(_lat21) == int(_pol20["lived_world"]["nominate_max_latent"]) and all(l["source_lane"] == "LATENT" and l["latent_structure_id"] for l in _lat21)
   and not any(l["latent_structure_id"] == "s_env" for l in _lat21),
   "latent leads are capped by nominate_max_latent and only searchable kinds (an ENVIRONMENT alone is not a population search)")
ok(all("hands" in l["channel_queries"][0]["query"] or "item" in l["channel_queries"][0]["query"] for l in _lat21),
   "a LATENT lead's queries are built from the structure's language, never from a group name")
# relevance law: analogies skip IRRELEVANT graph rows
_st21["data"]["primitives"].update({"transferable_invariants": ["x"], "shared_predicates": ["access"], "frictions": ["occupied_hand"], "physical_jobs": ["reach item"]})
_st21["data"]["corpus_evidence"] = [{"id": "gf1", "kind": "graph_fact", "tags": ["graph_fact"], "title": "Novel", "fact": {"subject": "reach", "predicate": "REQUIRES", "object": "item access"}, "summary": "reach REQUIRES item access"},
                                    {"id": "gf2", "kind": "graph_fact", "tags": ["graph_fact"], "title": "Manual", "fact": {"subject": "reach", "predicate": "REQUIRES", "object": "item hands"}, "summary": "reach REQUIRES item hands"}]
_st21["data"]["row_relevance"] = {"gf1": "IRRELEVANT", "gf2": "STRUCTURAL_ANALOGY"}
_an = executors._corpus_analogies(_st21, _st21["data"]["primitives"], 8)
ok([a["seed_id"] for a in _an] == ["gf2"], "cross-domain analogies skip rows classified IRRELEVANT and keep structural ones")
# corpus_named receipt
_cn = _models20.new_state("cn21", "s"); _cn["data"]["corpus_evidence"] = [{"id": "r1", "text": "she wore compression socks on every long flight", "summary": "compression socks on flights"}]
_cn["data"]["corpus_observations"] = [{"id": "o1", "kind": "OBSERVED_PRODUCT", "name": "compression socks", "evidence_refs": ["r1"], "evidentiary_authority": "NONE_FOR_CURRENT_DEMAND"}]
ok(_pvm.corpus_named({"name": "Compression socks for nurses", "form_factor": "sock"}, _cn)["named"] is True
   and _pvm.corpus_named({"name": "Cabin ankle sleeve", "form_factor": "sleeve"}, _cn)["named"] is False,
   "corpus_named: a bigram or an observed-product overlap names the concept; a different noun is corpus-independent")
# canary statuses on synthetic states
_cs = copy.deepcopy(_ps); _cs["rounds"] = {"research": 1}
_cs["data"]["corpus_evidence"].append({"id": "c3", "kind": "chunk", "doc_id": "N", "summary": "the pillow scene from the novel", "text": "the pillow scene from the novel", "tags": ["chunk"]})
_cs["data"]["row_relevance"] = {"c2": "STRUCTURAL_ANALOGY", "c3": "IRRELEVANT"}   # c2 is cited by h_ok's hop; c3 is the known trap, untouched
_cs["data"]["community_leads"] = [{"id": "lz", "kind": "COMMUNITY", "name": "r/Zepbound", "community_key": "Zepbound", "source_lane": "OPEN_FIELD", "nominated_by": ["search"], "authority": "LEAD", "status": "INSTANTIATED", "record_ids": ["f0"]}]
_cs["data"]["hypotheses"].append({"id": "h_dead", "status": "REJECTED", "hop_refs": {"0": ["c2"]}})
_cs["data"]["gaps"] = [{"id": "g_dead", "hypothesis_id": "h_dead", "status": "contradicted"}]
_cs["data"]["observations"].append({"id": "o_c", "gap_id": "g_dead", "contradicts": True, "community": "r/x", "quote_ref": "q", "problem": "p", "evidence_roles": ["CONTRADICTION"], "freshness": {"class": "LIVE"}, "source_identity": {"source_family": "community", "platform": "reddit", "author_key": "z", "thread_key": "zt"}})
sys.path.insert(0, os.path.join(ROOT, "tests"))
import calibration_acceptance as _cal  # noqa: E402
_rep21 = _cal.evaluate(_cs, _pol20, trap_texts={"pillow scene"})
ok(_rep21["statuses"]["noun_echo_resistance"] == "PASS" and _rep21["statuses"]["legitimate_echo_survival"] == "PASS"
   and _rep21["statuses"]["latent_population_discovery"] == "PASS" and _rep21["statuses"]["irrelevant_source_rejection"] == "PASS"
   and _rep21["statuses"]["hypothesis_death"] == "PASS",
   f"canaries 3/4/5/7/8 PASS on a state that refused an echo, kept a grounded echo, instantiated an open-field community, marked a row irrelevant and killed a corpus hypothesis ({_rep21['statuses']})")
_cs2 = copy.deepcopy(_cs); _cs2["data"]["row_relevance"] = {}
ok(_cal.evaluate(_cs2, _pol20, trap_texts={"pillow scene"})["statuses"]["irrelevant_source_rejection"] == "FAIL" and _cal.evaluate(_cs2, _pol20, trap_texts={"pillow scene"})["pass"] is False,
   "a run that forced every retrieved passage into play FAILS canary 7 and the calibration")
ok("cited_share_of_shelf" in _rep21["diagnostics"] and "cited_share_of_shelf" not in _rep21["statuses"], "shelf share is a diagnostic, never a gate")
ok(doctor.run()["ok"], "doctor green over the docs/26 surface")

# ---------------------------------------------------------------------------
# 22. senior-review regressions (2026-09-04): fail-closed relevance, referential lineage, field_originated,
#     field-caused death, known-trap containment, document scope + policy B, population-free generative rule
# ---------------------------------------------------------------------------
# 22a. fail-closed relevance at hypothesize: an UNCLASSIFIED corpus row cannot be a hop; classifying it in the same payload heals it
_fc = os.path.join(tmp, "failclosed.json")
ctl("init", "--state", _fc, "--signal", "fail-closed relevance probe")
_fcs = json.load(open(_fc)); _fcs["node"] = "hypothesize"
_fcs["data"]["corpus_evidence"] = [{"id": "rowA", "summary": "a classified row"}, {"id": "rowB", "summary": "an unclassified row"}, {"id": "rowC", "summary": "a dead row"}]
_fcs["data"]["row_relevance"] = {"rowA": "STRUCTURAL_ANALOGY", "rowC": "IRRELEVANT"}
_fcs["data"]["primitives"] = {"generative_signal": True}
json.dump(_fcs, open(_fc, "w"))
_hf = lambda hid, refs: {"id": hid, "source": "s", "path": ["a", "b", "c", "d"], "target_mechanism": f"mech_{hid}", "evidence_boundary": {"first_inference_at": "a"},
                         "gaps": ["g1", "g2"], "status": "WORKING_HYPOTHESIS", "alternatives": ["x"], "falsifiers": ["y"], "grounding": "CORPUS_ONLY", "hop_refs": {"1": refs}}
rc, out = submit(_fc, "hypothesize", {"hypotheses": [_hf("h1", ["rowB"]), _hf("h2", ["rowA"]), _hf("h3", ["rowA"])]})
ok(rc == 1 and any("UNCLASSIFIED" in e for e in out.get("schema_errors", [])), "an unclassified corpus row cited as a hop is refused — relevance is fail-closed (item 2)")
rc, out = submit(_fc, "hypothesize", {"hypotheses": [_hf("h1", ["rowC"]), _hf("h2", ["rowA"]), _hf("h3", ["rowA"])]})
ok(rc == 1 and any("IRRELEVANT" in e for e in out.get("schema_errors", [])), "an IRRELEVANT row cited as a hop is refused")
rc, out = submit(_fc, "hypothesize", {"hypotheses": [_hf("h1", ["nope_999"]), _hf("h2", ["rowA"]), _hf("h3", ["rowA"])]})
ok(rc == 1 and any("does not exist" in e for e in out.get("schema_errors", [])), "a hop citing a row that does not exist is refused")
rc, out = submit(_fc, "hypothesize", {"row_relevance": {"rowB": "SEMANTIC_MATCH"}, "hypotheses": [_hf("h1", ["rowB"]), _hf("h2", ["rowA"]), _hf("h3", ["rowA"])]})
ok(rc == 0 and json.load(open(_fc))["data"]["row_relevance"].get("rowB") == "SEMANTIC_MATCH" and json.load(open(_fc))["data"]["row_relevance"].get("rowA") == "STRUCTURAL_ANALOGY",
   "hypothesize may classify the rows it cites in the same payload; the map MERGES, earlier classifications survive")
# 22b. referential validation of interpretation refs at primitives (item 3)
_rf = os.path.join(tmp, "refs.json")
ctl("init", "--state", _rf, "--signal", "referential probe")
_rfs = json.load(open(_rf)); _rfs["node"] = "primitives"
_rfs["data"]["corpus_evidence"] = [{"id": "r1", "summary": "one"}, {"id": "r2", "summary": "two"}, {"id": "r3", "summary": "three"}]
json.dump(_rfs, open(_rf, "w"))
_ls = lambda refs: {"id": "s1", "kind": "ACCESS_PROBLEM", "text": "t", "evidence_refs": refs, "authority": "LATENT_HYPOTHESIS"}
_co = lambda refs: {"id": "o1", "kind": "OBSERVED_PRODUCT", "name": "socks", "evidence_refs": refs, "evidentiary_authority": "NONE_FOR_CURRENT_DEMAND"}
_pr = lambda ls, co, rel: {"primitives": {"generative_signal": True, "latent_structures": [ls], "corpus_observations": [co], "row_relevance": rel}}
rc, out = submit(_rf, "primitives", _pr(_ls(["nonexistent_row_999"]), _co(["r1"]), {"r1": "SEMANTIC_MATCH"}))
ok(rc == 1 and any("does not exist" in e and "latent_structures" in e for e in out.get("schema_errors", [])), "a latent structure citing a nonexistent row is refused (item 3)")
rc, out = submit(_rf, "primitives", _pr(_ls(["r2"]), _co(["r1"]), {"r1": "SEMANTIC_MATCH"}))
ok(rc == 1 and any("UNCLASSIFIED" in e and "latent_structures" in e for e in out.get("schema_errors", [])), "a latent structure citing an unclassified row is refused")
rc, out = submit(_rf, "primitives", _pr(_ls(["r1"]), _co(["r3"]), {"r1": "SEMANTIC_MATCH", "r3": "IRRELEVANT"}))
ok(rc == 1 and any("IRRELEVANT" in e and "corpus_observations" in e for e in out.get("schema_errors", [])), "a corpus observation citing an IRRELEVANT row is refused")
rc, out = submit(_rf, "primitives", {"primitives": {"generative_signal": True, "evidence_refs": {"behaviors": ["r2"]}, "row_relevance": {"r1": "SEMANTIC_MATCH"}}})
ok(rc == 1 and any("primitives.evidence_refs.behaviors" in e for e in out.get("schema_errors", [])), "classic primitives evidence_refs obey the same lineage law")
rc, out = submit(_rf, "primitives", _pr(_ls(["r1"]), _co(["r1"]), {"r1": "SEMANTIC_MATCH", "r3": "IRRELEVANT"}))
ok(rc == 0 and json.load(open(_rf))["data"]["latent_structures"][0]["id"] == "s1", "classified, existing, non-irrelevant refs are accepted and mirrored")
# 22c. analogies require classification (fail-closed), not merely non-IRRELEVANT
_st22 = _models20.new_state("an22", "s"); _st22["data"]["primitives"] = {"transferable_invariants": ["x"], "shared_predicates": ["access"], "frictions": ["occupied_hand"], "physical_jobs": ["reach item"]}
_st22["data"]["corpus_evidence"] = [{"id": "gfU", "kind": "graph_fact", "tags": ["graph_fact"], "title": "Unclassified", "fact": {"subject": "reach", "predicate": "REQUIRES", "object": "item access"}, "summary": "reach REQUIRES item access"},
                                    {"id": "gfC", "kind": "graph_fact", "tags": ["graph_fact"], "title": "Classified", "fact": {"subject": "reach", "predicate": "REQUIRES", "object": "item hands"}, "summary": "reach REQUIRES item hands"}]
_st22["data"]["row_relevance"] = {"gfC": "SEMANTIC_MATCH"}
ok([a["seed_id"] for a in executors._corpus_analogies(_st22, _st22["data"]["primitives"], 8)] == ["gfC"], "structural_lookup analogies come only from CLASSIFIED rows — unclassified rows are readable, never lineage")
# 22d. field_originated uses corpus_named, not zero overlap with the whole corpus (item 4)
_fo = _models20.new_state("fo22", "s"); _fod = _fo["data"]
_fod["corpus_evidence"] = [{"id": "c1", "text": "a magnetic closure keeps the running vest shut; a sleeve of fabric hides the zip", "summary": "magnetic closure running vest sleeve"}]
_fod["hypotheses"] = [{"id": "h", "status": "SUPPORTED", "hop_refs": {"0": ["c1"]}}]; _fod["mechanisms"] = [{"id": "m", "hypothesis_id": "h", "status": "SUPPORTED"}]
_fod["field_records"] = [{"id": f"f{i}", "lead_id": "l", "community": c, "quote_ref": "q", "problem": "gels leak", "workaround": "rubber-bands a gel sleeve to the strap", "products_named": ["magnetic gel sleeve"],
                          "evidence_roles": ["WORKAROUND_EVIDENCE"], "freshness": {"class": "LIVE"}, "source_identity": {"source_family": "community", "platform": "reddit", "author_key": f"a{i}", "thread_key": f"t{i}"}}
                         for i, c in enumerate(["r/running", "r/running", "r/trailrunning"])]
_fod["product_concepts"] = [{"id": "pc", "mechanism_id": "m", "name": "Magnetic gel sleeve", "form_factor": "strap sleeve", "evidence_refs": ["f0", "f1", "f2"]}]
_ln = _pvm.lineage(_fod["product_concepts"][0], _fo, _pol20)
ok(_ln["field_originated"] is True and _ln["corpus_named"] is False and _ln["field_lineage"] is True,
   "a field-named noun sharing ordinary tokens ('magnetic', 'sleeve') with the corpus is still field-originated — corpus_named decides, not token overlap (item 4)")
_fod["corpus_observations"] = [{"id": "o", "kind": "OBSERVED_PRODUCT", "name": "magnetic gel sleeve", "evidence_refs": ["c1"], "evidentiary_authority": "NONE_FOR_CURRENT_DEMAND"}]
ok(_pvm.lineage(_fod["product_concepts"][0], _fo, _pol20)["field_originated"] is False, "once the corpus NAMED the product it is no longer field-originated")
# 22e. hypothesis_death requires a field cause (item 5)
_hd = copy.deepcopy(_cs); _hd["rounds"] = {"research": 2}
_hd["data"]["hypotheses"] = [{"id": "h_dead", "status": "REJECTED", "hop_refs": {"0": ["c2"]}}]
_hd["data"]["gaps"] = [{"id": "g_dead", "hypothesis_id": "h_dead", "status": "open"}]
_hd["data"]["observations"] = [o for o in _hd["data"]["observations"] if not o.get("contradicts")]; _hd["data"]["challenges"] = []; _hd["data"]["evaluations"] = []
_r_hd = _cal.evaluate(_hd, _pol20, trap_texts={"pillow scene"})
ok(_r_hd["statuses"]["hypothesis_death"] == "FAIL" and _r_hd["checks"]["hypothesis_death"]["rejected_without_field_cause"] == ["h_dead"],
   "a corpus hypothesis rejected after two rounds with NO field cause does not satisfy hypothesis_death (item 5)")
_hd["data"]["challenges"] = [{"id": "ch", "hypothesis_id": "h_dead", "verdict": "REJECTED", "argument": "field says no", "evidence_refs": ["o0"]}]
ok(_cal.evaluate(_hd, _pol20, trap_texts={"pillow scene"})["statuses"]["hypothesis_death"] == "PASS", "a challenge that rejects it citing admitted field evidence counts as field-caused death")
# 22f. known-trap containment (item 6)
_tp = copy.deepcopy(_cs)   # c3 = the known trap ("pillow scene"): classified IRRELEVANT, referenced by nothing
ok(_cal.evaluate(_tp, _pol20, trap_texts={"pillow scene"})["statuses"]["irrelevant_source_rejection"] == "PASS", "a retrieved trap that is classified IRRELEVANT and untouched downstream PASSES canary 7")
_tp2 = copy.deepcopy(_tp); _tp2["data"]["latent_structures"] = [{"id": "s", "kind": "FRICTION", "text": "t", "evidence_refs": ["c3"], "authority": "LATENT_HYPOTHESIS"}]
_r7 = _cal.evaluate(_tp2, _pol20, trap_texts={"pillow scene"})
ok(_r7["statuses"]["irrelevant_source_rejection"] == "FAIL" and _r7["checks"]["irrelevant_source_rejection"]["leaked_downstream"] == ["c3"], "a trap referenced by a latent structure FAILS canary 7 (leak is visible)")
_tp3 = copy.deepcopy(_tp); _tp3["data"]["row_relevance"] = {}
ok(_cal.evaluate(_tp3, _pol20, trap_texts={"pillow scene"})["checks"]["irrelevant_source_rejection"]["unclassified"] == ["c3"], "an unclassified trap FAILS canary 7 — silence is not resistance")
ok(_cal.evaluate(_tp, _pol20, trap_texts={"never retrieved text"})["statuses"]["irrelevant_source_rejection"] == "FAIL", "a trap the retrieval never returned FAILS canary 7 with an explicit note")
# 22g. document scope threads into retrieve + plan and skips the unscoped /chat (item 7, policy B)
class _ScopeStub(http.server.BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *a): pass
    def _send(self, code, body):
        data = json.dumps(body).encode(); self.send_response(code); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path == "/capabilities":
            return self._send(200, {"backend": "polymath", "version": "stub", "contracts": {"retrieve-evidence-rows": "v1", "corpus-plan": "v1", "chat-evidence": "v1", "document_ids": True}})
        return self._send(404, {"detail": "no"})
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        _ScopeStub.calls.append((self.path, body))
        rows = [dict(r) for r in _SAMPLE["evidence_rows"]]
        if self.path == "/retrieve/plan":
            return self._send(200, {"plan": _PLANFIX["expected"], "evidence_rows": [dict(r, query_ids=[_PLANFIX["expected"][0]["id"]]) for r in rows]})
        if self.path == "/retrieve":
            return self._send(200, dict(_SAMPLE))
        if self.path == "/chat":
            return self._send(200, {"answer": "unscoped", "evidence_rows": rows, "meta": {}})
        return self._send(404, {"detail": "no"})
_sk = socket.socket(); _sk.bind(("127.0.0.1", 0)); _sport = _sk.getsockname()[1]; _sk.close()
_ssrv = http.server.ThreadingHTTPServer(("127.0.0.1", _sport), _ScopeStub); threading.Thread(target=_ssrv.serve_forever, daemon=True).start()
_sc22 = os.path.join(tmp, "scope.json")
rc, out = ctl("init", "--state", _sc22, "--signal", _PLANFIX["signal"], "--corpus", "polymath:stubcorp", "--document-id", "docA", "--document-id", "docB")
ok(rc == 0 and json.load(open(_sc22)).get("document_scope") == ["docA", "docB"], "init records a document scope on the run")
ctl("step", "--state", _sc22)
_sout = os.path.join(tmp, "scope_payload.json")
def _sadapter(*extra):
    r = subprocess.run([PY, os.path.join(ROOT, "python", "corpus_polymath.py"), "--state", _sc22, "--url", f"http://127.0.0.1:{_sport}", "--out", _sout, *extra], capture_output=True, text=True)
    _note = next((json.loads(l) for l in reversed(r.stderr.strip().splitlines()) if l.startswith("{")), {"stderr": r.stderr[-400:]})
    return _note, (json.load(open(_sout)) if os.path.exists(_sout) else {})
_ScopeStub.calls.clear(); _n1, _p1 = _sadapter()                       # default --via chat
ok(not any(p == "/chat" for p, _ in _ScopeStub.calls) and any(p == "/retrieve/plan" and b.get("document_ids") == ["docA", "docB"] for p, b in _ScopeStub.calls)
   and (_p1.get("corpus_backend") or {}).get("chat_skipped") and _n1.get("document_scope") == ["docA", "docB"],
   "with a document scope the adapter never calls the unscoped /chat and threads document_ids into /retrieve/plan (policy B)")
_ScopeStub.calls.clear(); _n2, _p2 = _sadapter("--generic", "--document-id", "docC")
ok(all(b.get("document_ids") == ["docC", "docA", "docB"] for p, b in _ScopeStub.calls if p == "/retrieve") and any(p == "/retrieve" for p, _ in _ScopeStub.calls),
   "the generic per-query path threads the CLI ∪ run scope into every /retrieve body")
_ssrv.shutdown()
# 22h. the population-free generative rule is in the prompt and the old requirement is gone (item 8)
_pp22 = open(os.path.join(ROOT, "prompts", "opportunity_primitives.md"), encoding="utf-8").read()
ok("A named population is never required" in _pp22 and "LATENT PROBLEM → population" in _pp22 and "no human population or activity" not in _pp22,
   "generative_signal rule: a latent structure without any population is generative (item 8)")
ok(doctor.run()["ok"], "doctor green over the senior-review regressions")

if FAILS:
    print(f"\n{len(FAILS)} CHECKS FAILED: " + "; ".join(FAILS[:8]))
    sys.exit(1)
print(f"\nALL {PASS} CHECKS PASSED")
