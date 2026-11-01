"""product-search-v1 hypotheses: the retrieval steering (inside the compiler's own caps), the PRODUCT HYPOTHESIS contract, and the
deterministic read-back of the answer's `product-hypotheses` block (good, drifted, missing → fallback). Pure: shared/ only."""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared import chat_plan as CP  # noqa: E402
from polymath_shared.product_search import hypotheses as H  # noqa: E402
from polymath_shared.product_search.intent import detect  # noqa: E402

MSG = "Find me products I could dropship for pet owners in the US"
LEGEND = {"S1", "S2", "S3", "S4"}
GOOD = """Three product hypotheses from your library [S1].

1. **Self-cleaning litter box** — scooping is the chore owners complain about most [S1].

```product-hypotheses
[{"title": "Self-cleaning litter box", "problem": "Daily scooping", "audience": "cat owners", "evidence_tags": ["S1", "S9"],
  "search_terms": ["self cleaning litter box", "automatic litter box"], "confidence": "medium"},
 {"title": "Calming dog bed", "problem": "Anxious dogs", "audience": "dog owners", "evidence_tags": ["S2"],
  "search_terms": ["calming dog bed"], "confidence": "high"}]
```"""


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(H.__file__).resolve().is_relative_to(ROOT), H.__file__


# ---------------------------------------------------------------- parse: good

def test_a_labelled_block_reads_ok_and_leaves_the_prose():
    p = H.parse_block(GOOD, LEGEND)
    assert p.status == "ok" and p.reason is None and p.notes == []
    assert [h["id"] for h in p.hypotheses] == ["h1", "h2"]
    h1 = p.hypotheses[0]
    assert h1 == {"id": "h1", "title": "Self-cleaning litter box", "problem": "Daily scooping", "audience": "cat owners",
                  "evidence_tags": ["S1"], "search_terms": ["self cleaning litter box", "automatic litter box"], "confidence": "medium"}
    assert p.tags_dropped == 1                                   # S9 is not a tag of this turn: dropped and counted
    assert "```" not in p.clean_text and "product-hypotheses" not in p.clean_text
    assert p.clean_text.endswith("owners complain about most [S1].")
    assert p.receipt() == {"status": "ok", "reason": None, "hypotheses": 2, "notes": [], "tags_dropped": 1}


# ---------------------------------------------------------------- parse: drift

@pytest.mark.parametrize("case,text,notes,titles,tags", [
    ("json label, trailing commas, wrapper, aliases, tag string, unclosed",
     'Prose [S2].\nMachine-readable block:\n~~~json\n{"hypotheses": [{"Name": "Calming dog bed", "Pain": "anxiety", '
     '"Evidence": "[S2], [S3]", "Search Terms": "calming dog bed; donut pet bed",}, ]}\n',
     ["repaired", "label_drift", "unclosed_fence"], ["Calming dog bed"], [["S2", "S3"]]),
    ("cut off at the output bound",
     'Prose.\n```product-hypotheses\n[{"title": "Pet water fountain", "search_terms": ["pet water fountain"]}, {"title": "Leash b',
     ["truncated", "unclosed_fence"], ["Pet water fountain"], [[]]),
    ("no fence at all",
     'Prose.\n[{"title": "Pet water fountain", "evidence_tags": [2]}]', ["unfenced"], ["Pet water fountain"], [["S2"]]),
    ("single quotes (a Python literal)",
     "```product-hypotheses\n[{'title': 'Poop bag holder', 'search_terms': 'poop bag holder, leash bag'}]\n```",
     ["repaired", "python_literal"], ["Poop bag holder"], [[]]),
    ("smart quotes",
     "```product-hypotheses\n[{“title”: “Car seat cover”, “evidence_tags”: [“S4”]}]\n```",
     ["repaired"], ["Car seat cover"], [["S4"]]),
])
def test_small_format_drift_still_reads_and_is_labelled_drifted(case, text, notes, titles, tags):
    p = H.parse_block(text, LEGEND)
    assert p.status == "drifted", (case, p)
    assert p.notes == notes, (case, p.notes)
    assert [h["title"] for h in p.hypotheses] == titles and [h["evidence_tags"] for h in p.hypotheses] == tags
    assert all(1 <= len(h["search_terms"]) <= H.MAX_TERMS for h in p.hypotheses)       # a missing term list comes from the title
    assert "[{" not in p.clean_text


def test_search_terms_are_short_plain_and_capped():
    p = H.parse_block('```product-hypotheses\n[{"title": "X", "search_terms": ["  Self-Cleaning   Litter Box!! ", "a", '
                      '"one two three four five six seven eight", "b c", "d e", "f g"]}]\n```', None)
    assert p.hypotheses[0]["search_terms"] == ["self-cleaning litter box", "one two three four five six", "b c"]


def test_at_most_five_hypotheses_and_untitled_objects_are_dropped():
    items = ", ".join('{"title": "T%d"}' % i for i in range(8))
    p = H.parse_block('```product-hypotheses\n[{"problem": "no title"}, ' + items + ']\n```', None)
    assert [h["title"] for h in p.hypotheses] == ["T0", "T1", "T2", "T3", "T4"]


# ---------------------------------------------------------------- parse: missing → fallback (receipted, never silent)

@pytest.mark.parametrize("text,reason", [
    ("Three ideas [S1], but no block.", "no_block"),
    ("Ideas.\n```product-hypotheses\n[{title: oops, ]]\n```", "unparseable"),
    ('Ideas.\n```product-hypotheses\n[{"problem": "no title anywhere"}]\n```', "no_hypotheses"),
])
def test_a_missing_or_unreadable_block_is_a_typed_fallback(text, reason):
    p = H.parse_block(text, LEGEND)
    assert p.status == "fallback" and p.reason == reason and p.hypotheses == []
    assert p.receipt()["status"] == "fallback" and p.receipt()["reason"] == reason
    assert "product-hypotheses" not in p.clean_text          # an unreadable block of ours still leaves the prose
    assert p.clean_text.startswith(text.split("\n")[0].rstrip())


def test_an_unrelated_code_block_is_kept_in_the_answer():
    text = "Here is code:\n```python\nprint('hi')\n```\nNo hypotheses block."
    p = H.parse_block(text, None)
    assert p.status == "fallback" and "print('hi')" in p.clean_text


# ---------------------------------------------------------------- the contract

def test_the_contract_asks_for_hypotheses_from_any_corpus_and_the_exact_block():
    block = H.contract_block(detect(MSG))
    for needle in ("PRODUCT HYPOTHESIS CONTRACT", "3 to 5 product HYPOTHESES", "[S#]", "doesn't recommend products",
                   "never ask the user for a niche", "frictions, workarounds, unmet jobs", f"```{H.BLOCK_LABEL}",
                   '"search_terms"', '"evidence_tags"', "low-confidence", "selling market: US", "for pet owners",
                   "this contract wins"):
        assert needle in block, needle
    seeded = H.contract_block(detect("find suppliers for yoga mats"))
    assert 'The user named "yoga mats"' in seeded and "selling market" not in seeded
    # the example in the contract is a placeholder, never a product that would bias every corpus
    assert "litter" not in block.lower()


# ---------------------------------------------------------------- steering

def _plan(message: str, queries: list[dict], facets: list[dict] | None = None) -> CP.ChatPlan:
    raw = {"resolved_request": message, "task_type": "CREATE_FROM_KNOWLEDGE", "evidence_policy": "corpus_grounded",
           "retrieval_required": True, "queries": queries, "semantic_queries": [], "exact_terms": [], "entities": [],
           "must_answer": [], "user_constraints": [], "response_type": "answer", "antecedent": None, "graph_useful": False}
    plan, err = CP.validate_plan(raw, message, facets=facets)
    assert plan is not None, err
    plan.compiler = {"fallback": False}
    return plan


def test_aspects_are_hypothesis_material_for_the_audience_seed_or_nothing():
    aud = H.aspects_for(detect(MSG))
    assert [a[0] for a in aud] == ["frictions", "workarounds", "unmet_jobs"] and all("pet owners" in a[2] for a in aud)
    seed = H.aspects_for(detect("find suppliers for yoga mats"))
    assert all("yoga mats" in a[2] for a in seed)
    generic = H.aspects_for(detect("what should I sell on Shopify"))
    assert len(generic) == 3 and all("shopify" not in a[2].lower() for a in generic)          # no niche needed
    for a in aud + seed + generic:
        assert a[1] in CP.QUERY_TYPES and a[1] not in ("PRIMARY", "COMPARISON", "COUNTERPOINT", "ADJACENT")
        assert not CP._has_instruction_tokens(a[2]) and len(a[2].split()) <= CP.MAX_QUERY_WORDS
        assert "US" not in a[2].split()                                                         # a country is not hypothesis material


def test_steering_a_plan_keeps_q0_and_stays_inside_max_queries():
    plan = _plan(MSG, [{"type": "PRIMARY", "query": "dropshipping products for pet owners"},
                       {"type": "MECHANISM", "query": "pet owner buying behaviour", "weight": 0.9},
                       {"type": "EXAMPLE", "query": "dropshipping success stories", "weight": 0.5}])
    q0 = plan.queries[0].query
    steered, receipt = H.steer_plan(plan, detect(MSG))
    user = [q for q in steered.queries if q.origin == "USER"]
    assert len(user) <= CP.MAX_QUERIES and steered.queries[0].type == "PRIMARY" and steered.queries[0].query == q0
    assert [q.id for q in steered.queries] == ["q0", "ps1", "ps2", "ps3"]                    # cap 4: q0 + the three aspects
    assert receipt["replaced"] == ["q2", "q1"]                                                 # lowest weight made room first
    # a plan with room keeps every compiled query
    roomy = _plan(MSG, [{"type": "PRIMARY", "query": "dropshipping products for pet owners"}])
    steered_roomy, receipt_roomy = H.steer_plan(roomy, detect(MSG))
    assert [q.id for q in steered_roomy.queries] == ["q0", "ps1", "ps2", "ps3"] and receipt_roomy["replaced"] == []
    assert steered.compiler["product_search"] is receipt and receipt["mode"] == "plan" and receipt["retrieval_override"] is False
    assert all(q.reason.startswith("product hypothesis material") and q.weight == H.ASPECT_WEIGHT for q in steered.queries
               if q.id.startswith("ps"))
    assert CP.retrieval_text_for(steered) == CP.retrieval_text_for(plan)                     # q0 still drives lane A


def test_a_plan_that_would_not_retrieve_is_made_to():
    plan = CP.ChatPlan(contract=CP.CONTRACT, original_request=MSG, resolved_request=MSG, task_type="GENERAL_CONVERSATION",
                       evidence_policy="conversation", retrieval_required=False, retrieval_goal=None, queries=[], semantic_queries=[],
                       exact_terms=[], entities=[], must_answer=[], user_constraints=[], response_type="answer", antecedent=None,
                       graph_useful=False, compiler={"fallback": False})
    steered, receipt = H.steer_plan(plan, detect(MSG))
    assert steered.retrieval_required is True and steered.task_type == "GROUNDED_QA"
    assert [q.id for q in steered.queries] == ["q0", "ps1", "ps2", "ps3"] and receipt["retrieval_override"] is True
    assert steered.compiler["evidence_route_override"]["rule"] == H.STEER_RULE


def test_on_a_facet_plan_each_aspect_gets_its_own_facet_while_max_facets_allows():
    facets = [{"id": "f1", "name": "pet products", "query": "dropshipping products for pet owners", "type": "PRIMARY"},
              {"id": "f2", "name": "US market", "query": "US pet market size", "type": "EXAMPLE"}]
    plan = _plan(MSG, [{"type": "PRIMARY", "query": "dropshipping products for pet owners", "facet_id": "f1"},
                       {"type": "EXAMPLE", "query": "US pet market size", "facet_id": "f2"}], facets=facets)
    assert len(plan.facets) == 2
    steered, receipt = H.steer_plan(plan, detect(MSG))
    assert len([q for q in steered.queries if q.origin == "USER"]) <= CP.MAX_QUERIES_FACETS
    assert receipt["facets_added"] == ["f3", "f4", "f5"] and len(steered.facets) == CP.MAX_FACETS
    by_id = {f["id"]: f["query_ids"] for f in steered.facets}
    assert by_id["f3"] == ["ps1"] and by_id["f4"] == ["ps2"] and by_id["f5"] == ["ps3"] and by_id["f1"] == ["q0"]
    assert all(q.facet_id for q in steered.queries)


def test_a_facet_a_replaced_query_leaves_empty_is_dropped():
    facets = [{"id": f"f{i}", "name": f"facet {i}", "query": f"query number {i}", "type": "EXAMPLE"} for i in range(1, 6)]
    queries = [{"type": "PRIMARY", "query": "query number 1", "facet_id": "f1"}] + \
              [{"type": "EXAMPLE", "query": f"query number {i}", "facet_id": f"f{i}", "weight": 1.0 - i / 10} for i in range(2, 6)] + \
              [{"type": "ADJACENT", "query": "underlying principle of query", "weight": 0.2}]
    plan = _plan(MSG, queries, facets=facets)
    assert len(plan.facets) == CP.MAX_FACETS and len(plan.queries) == CP.MAX_QUERIES_FACETS
    steered, receipt = H.steer_plan(plan, detect(MSG))
    assert len([q for q in steered.queries if q.origin == "USER"]) <= CP.MAX_QUERIES_FACETS
    assert receipt["replaced"] == ["q5", "q4", "q3"]                       # the ADJACENT (0.2), then the weakest aspects
    assert receipt["facets_dropped"] == ["f4", "f5"]                         # their facets were left empty: dropped first
    assert receipt["facets_added"] == ["f6", "f7"]                           # freed slots reused, ids never reused
    assert len(steered.facets) == CP.MAX_FACETS and all(f["query_ids"] for f in steered.facets)
    by_id = {f["id"]: f["query_ids"] for f in steered.facets}
    assert by_id["f6"][0] == "ps1" and by_id["f7"][0] == "ps2"
    assert sum(by_id.values(), []).count("ps3") == 1                         # the third attaches by overlap (sync_facets)
    assert {q.id for q in steered.queries} == {"q0", "q1", "q2", "ps1", "ps2", "ps3"}


def test_steer_text_adds_one_deterministic_hypothesis_phrase():
    text, receipt = H.steer_text("find me products", detect(MSG))
    assert text == "find me products pet owners frustrations, workarounds and unmet needs"
    assert receipt == {"mode": "text", "addition": "pet owners frustrations, workarounds and unmet needs",
                       "subject": {"audience": "pet owners", "seed": None}}
    assert H.steer_text("what should I sell", detect("what should I sell on Shopify"))[0].endswith("frustrations, workarounds and unmet needs")
