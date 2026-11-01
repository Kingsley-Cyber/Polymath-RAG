"""PRODUCT-INTENT-V1 (product-search-v1): the deterministic product-request detector, table-driven.

It must fire on requests to FIND products to sell or suppliers for one (with or without a niche), and never on knowledge
questions ABOUT products. Pure: shared/ only."""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.product_search import intent as PI  # noqa: E402

#: (message, rule, audience, geography, seed) — None = not asserted beyond "absent"
POSITIVES = [
    ("Find me products I could dropship for pet owners in the US", "dropship_object", "pet owners", "US", None),
    ("what should I sell to new moms?", "sell_object", "new moms", None, None),
    ("What products can I sell to dog owners in the UK?", "sell_object", "dog owners", "GB", None),
    ("give me product ideas for gamers", "product_ideas", "gamers", None, None),
    ("suggest dropshipping products for fitness enthusiasts", "dropship_noun", "fitness enthusiasts", None, None),
    ("find suppliers for yoga mats", "supplier_request", None, None, "yoga mats"),
    ("Find a supplier for silicone baking mats", "supplier_request", None, None, "silicone baking mats"),
    ("source LED dog collars from Alibaba", "supplier_request", None, None, "led dog collars"),
    ("what should I sell on Shopify", "sell_object", None, None, None),
    ("winning products for the UK market", "product_ideas", None, "GB", None),
    ("find me something to dropship", "dropship_object", None, None, None),
    ("products to sell to dog owners", "sell_object", "dog owners", None, None),
    ("help me find a product to sell online", "sell_object", None, None, None),
    ("I want to start a dropshipping store for cat lovers, what should I sell?", "sell_object", "cat lovers", None, None),
    ("list trending products for summer in Canada", "product_ideas", None, "CA", "summer"),
    ("find CJ dropshipping products for home office workers", "supplier_request", "home office workers", None, None),
    ("what can I dropship to college students", "dropship_object", "college students", None, None),
    ("which products could I source from Alibaba for hikers", "sell_object", "hikers", None, None),
    ("recommend products for a camping store", "request_products", None, None, "camping"),
    ("find me a winning product", "product_ideas", None, None, None),
    ("what are good products to sell on Amazon for parents", "sell_object", "parents", None, None),
    ("brainstorm product ideas from this corpus", "product_ideas", None, None, None),
    ("use the corpus to find products for pet owners", "request_products", "pet owners", None, None),
    ("show me CJ finds for anxious dog owners", "supplier_request", "anxious dog owners", None, None),
    ("any products I could sell to busy parents in Australia?", "sell_object", "busy parents", "AU", None),
    ("find products for remote workers", "request_products", "remote workers", None, None),
    ("dropship ideas for beginners", "dropship_noun", "beginners", None, None),
    ("what product should I launch for runners", "sell_object", "runners", None, None),
    ("can you find me products to sell for seniors in the US", "sell_object", "seniors", "US", None),
    ("What are some winning products for pet owners?", "product_ideas", "pet owners", None, None),
    ("search CJ for self cleaning litter boxes", "supplier_request", None, None, "self cleaning litter boxes"),
    ("find me dog toys on CJ", "supplier_request", None, None, "dog toys"),
    ("products for busy parents?", "terse_products", "busy parents", None, None),
    ("Where can I source yoga mats?", "supplier_request", None, None, "yoga mats"),
    ("according to the book, what products should I sell to pet owners?", "sell_object", "pet owners", None, None),
    ("hypothesize products from my library for American homeowners", "request_products", "american homeowners", "US", None),
]

NEGATIVES = [
    "what does Christensen say about the products customers hire",
    "how should I price a product",
    "what is dropshipping",
    "how does dropshipping work",
    "what are the risks of dropshipping",
    "explain the product life cycle",
    "what makes a winning product according to the book",
    "how do I write a product description",
    "summarize the chapter on product-market fit",
    "what is a minimum viable product",
    "compare dropshipping and wholesale",
    "who are the main suppliers mentioned in chapter 3",
    "why do customers hire products",
    "how do I find product-market fit",
    "what does the author recommend about choosing suppliers",
    "how many products did Amazon sell in 2020",
    "define jobs to be done",
    "what are the best practices for product photography",
    "tell me about the history of Alibaba",
    "how do I evaluate a supplier's reliability",
    "What does the book say about dropshipping products?",
    "show me the products mentioned in chapter 2",
    "how do I come up with product ideas",
    "is dropshipping profitable",
    "what should I carry on a hike",
    "what could we launch to fix onboarding",
    "how to dropship",
    "What can I offer customers to improve retention?",
    "what does RAPO say about prompts",
]


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(PI.__file__).resolve().is_relative_to(ROOT), PI.__file__


def test_the_table_is_big_enough():
    assert len(POSITIVES) >= 25 and len(NEGATIVES) >= 15


@pytest.mark.parametrize("message,rule,audience,geography,seed", POSITIVES, ids=[p[0][:48] for p in POSITIVES])
def test_a_product_request_fires_with_its_rule_and_extraction(message, rule, audience, geography, seed):
    got = PI.detect(message)
    assert got is not None, message
    assert got.rule == rule, (message, got)
    assert got.kind in PI.KINDS and got.source == "message"
    assert got.audience == audience, (message, got.audience)
    assert got.geography == geography, (message, got.geography)
    if seed is not None:
        assert got.seed == seed, (message, got.seed)
    # every term is short and plain: a CJ catalogue search
    assert len(got.search_terms) <= PI.MAX_TERMS and all(2 <= len(t) <= 60 and len(t.split()) <= 6 for t in got.search_terms)


@pytest.mark.parametrize("message", NEGATIVES)
def test_a_knowledge_question_about_products_never_fires(message):
    assert PI.detect(message) is None, (message, PI.detect(message))


def test_terms_come_from_the_seed_else_the_audience_root_else_none():
    assert PI.detect("find suppliers for yoga mats").search_terms == ("yoga mats",)
    assert PI.detect("Find me products I could dropship for pet owners in the US").search_terms == ("pet products", "pet accessories")
    assert PI.detect("what should I sell to new moms?").search_terms == ("baby products", "baby accessories")   # no root: the table
    assert PI.detect("recommend products for a camping store").search_terms == ("camping products",)           # a niche seed
    assert PI.detect("what should I sell on Shopify").search_terms == ()                                       # no niche needed


def test_a_place_is_never_a_seed_or_an_audience_root():
    winning = PI.detect("winning products for the UK market")
    assert winning.seed is None and winning.geography == "GB" and winning.search_terms == ()
    homes = PI.detect("hypothesize products from my library for American homeowners")
    assert homes.geography == "US" and homes.search_terms == ("home products", "home accessories")


def test_us_the_pronoun_is_not_the_united_states_but_US_is():
    assert PI.detect("give us product ideas for gamers").geography is None
    assert PI.detect("give me product ideas for gamers in the US").geography == "US"
    assert PI.detect("product ideas for German shepherd owners").geography is None          # a dog breed, not Germany


def test_a_vetoed_rule_is_named_for_the_receipt_but_does_not_fire():
    assert PI.detect("how do I come up with product ideas") is None
    rule, kind, vetoed = PI._match(PI._norm("how do I come up with product ideas"))
    assert rule is None and kind is None and vetoed[0] == "product_ideas" and set(vetoed) <= {"product_ideas", "request_products"}


HISTORY = [{"role": "user", "content": "Find me products I could dropship for pet owners in the US"},
           {"role": "assistant", "content": "Here are three product hypotheses ..."}]


@pytest.mark.parametrize("message", ["find suppliers for that", "any CJ listings for those?", "now search them on alibaba",
                                     "find suppliers for the second one"])
def test_a_follow_up_takes_its_seed_audience_and_market_from_the_last_user_turn(message):
    got = PI.detect(message, HISTORY)
    assert got is not None and got.source == "history" and got.audience == "pet owners" and got.geography == "US"
    assert got.seed is None and got.search_terms == ("pet products", "pet accessories")


def test_a_deictic_message_without_product_words_or_history_does_not_fire():
    assert PI.detect("and for those?", HISTORY) is None
    assert PI.detect("tell me more about that", HISTORY) is None


def test_history_turn_objects_with_attributes_are_read_too():
    class Turn:
        def __init__(self, role, content):
            self.role, self.content = role, content
    got = PI.detect("find suppliers for that", [Turn("user", "what can I dropship to college students"), Turn("assistant", "...")])
    assert got.source == "history" and got.audience == "college students"


def test_force_always_returns_an_intent_and_keeps_a_matched_rule():
    forced = PI.detect("tell me about the history of Alibaba", force=True)
    assert forced is not None and forced.rule == "forced" and forced.kind == "forced" and forced.source == "forced"
    kept = PI.detect("find suppliers for yoga mats", force=True)
    assert kept.rule == "supplier_request" and kept.source == "message"


def test_as_dict_is_the_receipt_shape():
    d = PI.detect("Find me products I could dropship for pet owners in the US").as_dict()
    assert d == {"contract": "product-intent-v1", "kind": "dropship", "rule": "dropship_object", "seed": None, "seed_kind": None,
                 "audience": "pet owners", "geography": "US", "search_terms": ["pet products", "pet accessories"], "source": "message"}
