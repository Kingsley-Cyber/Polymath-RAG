"""product-search-v1 service: the CJ / Alibaba lookups per hypothesis with an injected fake supplier (never CJ for real), the
documented item names, S1's fallback passed through unchanged, refusals degraded (never a failed turn), the cap, the dedupe, the
offer of the full run, and the receipt summary (counts and statuses only). Pure: shared/ only."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.acquisition.service import AcquisitionRefused  # noqa: E402
from polymath_shared.product_search import service as S  # noqa: E402
from polymath_shared.product_search.intent import detect  # noqa: E402

MSG = "Find me products I could dropship for pet owners in the US"
S1_FALLBACK = {"kind": "AGENT_REACH", "reason_code": "CJ_EMPTY", "why": "CJ's API found no product for this query",
               "site": "cjdropshipping.com", "query": "q", "run_on": "your machine", "never": "never your built-in web search",
               "install": {"repo": S.AGENT_REACH_REPO, "verify": S.AGENT_REACH_VERIFY},
               "commands": [{"step": 1, "run": "mcporter call exa.web_search_exa query='site:cjdropshipping.com q'",
                             "what": "searches", "then": "send it to supplier_parse"}],
               "submit": {"tool": "supplier_parse"}}


def _listing(pid: str, title: str, **over) -> dict:
    """One item exactly as supplier.search returns it: service.shape over cj_api.listing_record (fields nested under `listing`)."""
    listing = {"title": title, "price_as_listed": "US$12.50", "minimum_order_as_listed": "1 unit", "supplier": "Acme",
               "discount_price_as_listed": "US$9.99", "category": "Pet Supplies", "image": f"https://img.cj/{pid}.jpg",
               "product_id": pid, "sku": f"CJ{pid}", "listed_by_stores": "1203", "warehouse_inventory": "0", **over}
    return {"item_id": f"itm_{pid}", "kind": "listing", "source_id": f"src_{pid}", "excerpt": f"{title} · price as listed",
            "published_at": None, "date_precision": "none", "date_shown": None, "listing": listing}


class FakeSupplier:
    """supplier.search's contract: OK / EMPTY (+ S1 fallback) / UNAVAILABLE (+ S1 fallback) / a refusal; records every call."""

    def __init__(self, table: dict):
        self.table, self.calls = table, []

    def __call__(self, *, principal_id, query, source="cj", limit=10):
        self.calls.append({"principal_id": principal_id, "query": query, "source": source, "limit": limit})
        got = self.table.get(query, "EMPTY")
        if isinstance(got, Exception):
            raise got
        if got == "EMPTY":
            return {"status": "EMPTY", "sources": [], "items": [], "reason_code": "CJ_EMPTY", "fallback": dict(S1_FALLBACK, query=query),
                    "limitations": ["CJ's API found no product for this query"]}
        if got == "UNAVAILABLE":
            return {"status": "UNAVAILABLE", "sources": [], "items": [], "reason_code": "CJ_API_DISABLED",
                    "fallback": dict(S1_FALLBACK, reason_code="CJ_API_DISABLED", query=query), "limitations": ["CJ has disabled API access"]}
        if got == "OLD_UNAVAILABLE":                                    # a supplier that predates `fallback`
            return {"status": "UNAVAILABLE", "sources": [], "items": [], "limitations": ["CJ_API_KEY is not set on this host"]}
        items = [_listing(pid, title) for pid, title in got]
        return {"status": "OK", "items": items, "fallback": None, "reason_code": None,
                "sources": [{"source_id": f"src_{pid}", "url": f"https://cjdropshipping.com/product/x-p-{pid}.html"} for pid, _ in got],
                "limitations": ["listings from the CJ Dropshipping API"]}


def _turn(fake, **kw) -> S.ProductTurn:
    return S.ProductTurn(detect(MSG), message=MSG, corpus_ids=["commerce-v1"], principal_id="prn_fred", search=fake, **kw)


HYPS = [{"id": "h1", "title": "Smart feeder", "problem": "missed meals", "audience": "pet owners", "evidence_tags": ["S1"],
         "search_terms": ["automatic pet feeder"], "confidence": "medium"},
        {"id": "h2", "title": "Calming bed", "problem": None, "audience": None, "evidence_tags": ["S2"],
         "search_terms": ["calming dog bed"], "confidence": None},
        {"id": "h3", "title": "Disabled thing", "problem": None, "audience": None, "evidence_tags": ["S3"],
         "search_terms": ["disabled thing"], "confidence": None},
        {"id": "h4", "title": "Refused thing", "problem": None, "audience": None, "evidence_tags": [],
         "search_terms": ["refused thing"], "confidence": None}]
TABLE = {"automatic pet feeder": [("1001", "Automatic Pet Feeder 4L"), ("1002", "Smart Feeder Wifi")],
         "calming dog bed": "EMPTY", "disabled thing": "UNAVAILABLE",
         "refused thing": AcquisitionRefused(403, "OWNER_ONLY", "a principal key may not use the supplier tools")}


def _finish(fake, hyps=HYPS, legend_n=4):
    from polymath_shared.product_search import hypotheses as H
    t = _turn(fake)
    t.parse = H.HypothesisParse("ok", None, [dict(h) for h in hyps], "prose")
    legend = [{"tag": f"S{i}", "chunk_id": f"c{i}"} for i in range(1, legend_n + 1)]
    return t, t.finish_llm(legend=legend)


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(S.__file__).resolve().is_relative_to(ROOT), S.__file__


def test_ok_items_are_flattened_to_the_documented_names_with_their_source_url():
    fake = FakeSupplier(TABLE)
    _, (block, verdict, md) = _finish(fake)
    cj = block["hypotheses"][0]["cj"]
    assert cj["status"] == "OK" and cj["search_term"] == "automatic pet feeder" and cj["fallback"] is None
    item = cj["items"][0]
    assert list(item) == list(S.ITEM_FIELDS)
    assert item == {"title": "Automatic Pet Feeder 4L", "price": "US$12.50", "discount_price": "US$9.99", "moq": "1 unit",
                    "image": "https://img.cj/1001.jpg", "url": "https://cjdropshipping.com/product/x-p-1001.html",
                    "product_id": "1001", "sku": "CJ1001", "category": "Pet Supplies", "stores_listing": "1203",
                    "warehouse_stock": "0", "supplier": "Acme"}           # "0" stays "0": a count, never dropped


def test_a_missing_field_is_null_never_invented():
    item = S.item_view({"listing": {"title": "Bare"}, "source_id": "nope"}, {})
    assert item == {k: ("Bare" if k == "title" else None) for k in S.ITEM_FIELDS}
    flat = S.item_view({"title": "Flat", "price": "US$1", "url": "javascript:alert(1)"}, {})
    assert flat["title"] == "Flat" and flat["price"] == "US$1" and flat["url"] is None      # only an http(s) URL is a URL


def test_empty_and_unavailable_pass_s1s_fallback_through_unchanged():
    fake = FakeSupplier(TABLE)
    _, (block, _, _) = _finish(fake)
    empty, disabled = block["hypotheses"][1]["cj"], block["hypotheses"][2]["cj"]
    assert empty["status"] == "EMPTY" and empty["items"] == [] and empty["fallback"] == dict(S1_FALLBACK, query="calming dog bed")
    assert disabled["status"] == "UNAVAILABLE" and disabled["reason_code"] == "CJ_API_DISABLED"
    assert disabled["fallback"]["reason_code"] == "CJ_API_DISABLED" and isinstance(disabled["fallback"]["commands"][0], dict)


def test_a_refusal_degrades_to_a_typed_unavailable_entry_with_a_fallback_never_a_failed_turn():
    fake = FakeSupplier(TABLE)
    _, (block, verdict, md) = _finish(fake)
    refused = block["hypotheses"][3]["cj"]
    assert refused["status"] == "UNAVAILABLE" and refused["reason_code"] == "OWNER_ONLY"
    assert refused["refused"] == {"code": "OWNER_ONLY", "status": 403, "message": "a principal key may not use the supplier tools"}
    fb = refused["fallback"]
    assert fb["kind"] == "AGENT_REACH" and fb["reason_code"] == "OWNER_ONLY" and fb["site"] == "cjdropshipping.com"
    assert fb["install"]["repo"] == S.AGENT_REACH_REPO and fb["commands"] and all(isinstance(c, dict) and c.get("run") for c in fb["commands"])
    assert any("could not be searched for 2 of 4" in x for x in block["limitations"])      # disabled + refused, said once


def test_an_old_supplier_without_fallback_gets_one_built_by_agent_reach():
    fake = FakeSupplier({"automatic pet feeder": "OLD_UNAVAILABLE"})
    _, (block, _, _) = _finish(fake, hyps=HYPS[:1])
    cj = block["hypotheses"][0]["cj"]
    assert cj["status"] == "UNAVAILABLE" and cj["reason_code"] == "CJ_UNAVAILABLE"
    assert cj["fallback"]["kind"] == "AGENT_REACH" and "CJ_API_KEY" in cj["fallback"]["why"]


def test_alibaba_is_never_searched_on_the_host_it_is_an_agent_reach_handoff():
    fake = FakeSupplier(TABLE)
    _, (block, _, _) = _finish(fake)
    assert all(c["source"] == "cj" for c in fake.calls)                                     # no alibaba call at all
    for h in block["hypotheses"]:
        ali = h["alibaba"]
        assert ali["status"] == "AGENT_REACH_REQUIRED" and ali["reason_code"] == "ALIBABA_AGENT_REACH_ONLY"
        assert ali["fallback"]["site"] == "alibaba.com" and ali["fallback"]["query"] == h["search_terms"][0]


def test_the_principal_reaches_every_cj_search_one_search_per_hypothesis_with_the_limit():
    fake = FakeSupplier(TABLE)
    _finish(fake)
    assert [c["query"] for c in fake.calls] == ["automatic pet feeder", "calming dog bed", "disabled thing", "refused thing"]
    assert {c["principal_id"] for c in fake.calls} == {"prn_fred"} and {c["limit"] for c in fake.calls} == {S.DEFAULT_LIMIT}


def test_at_most_max_lookups_searches_a_turn_and_the_rest_say_not_searched():
    fake = FakeSupplier({})
    hyps = [{"id": f"h{i}", "title": f"T{i}", "evidence_tags": ["S1"], "search_terms": [f"term {i}"]} for i in range(1, 6)]
    t = _turn(fake)
    look = t._lookups(2)
    out = t._with_finds(hyps, look)
    assert len(fake.calls) == 2 and [h["cj"]["status"] for h in out] == ["EMPTY", "EMPTY", "NOT_SEARCHED", "NOT_SEARCHED", "NOT_SEARCHED"]
    assert look.skipped_cap == 3


def test_the_same_product_is_kept_once_across_hypotheses_and_a_repeated_term_takes_the_next():
    fake = FakeSupplier({"pet feeder": [("1001", "Feeder A"), ("1002", "Feeder B")], "smart feeder": [("1001", "Feeder A"), ("1003", "C")]})
    hyps = [{"id": "h1", "title": "A", "evidence_tags": ["S1"], "search_terms": ["pet feeder"]},
            {"id": "h2", "title": "B", "evidence_tags": ["S1"], "search_terms": ["pet feeder", "smart feeder"]}]
    t, (block, _, _) = _finish(fake, hyps=hyps)
    assert [c["query"] for c in fake.calls] == ["pet feeder", "smart feeder"]               # h2's first term was taken: its second
    assert [i["product_id"] for i in block["hypotheses"][0]["cj"]["items"]] == ["1001", "1002"]
    assert [i["product_id"] for i in block["hypotheses"][1]["cj"]["items"]] == ["1003"]      # 1001 kept once
    assert block["receipts"]["deduped"] == 1


def test_the_block_offers_the_full_run_with_the_turns_corpora_and_never_a_null_geography():
    fake = FakeSupplier(TABLE)
    _, (block, _, _) = _finish(fake)
    full = block["next"]["full_research"]
    assert full["tool"] == "adapter_start" and full["adapter_id"] == "ecommerce.product_research" and full["auto_start"] is False
    assert full["input"] == {"seed": "products for pet owners", "corpus_ids": ["commerce-v1"], "geography": "US"}
    assert full["request_options"] == {"corpus_ids": ["commerce-v1"]} and full["who_drives"] == "your agent"
    no_geo = S.next_block(detect("what should I sell on Shopify"), ["c1"], "what should I sell on Shopify")["full_research"]["input"]
    assert no_geo == {"seed": "what should I sell on Shopify", "corpus_ids": ["c1"]} and "geography" not in no_geo
    assert block["agent_reach"] == {"local_only": True, "install": {"repo": "https://github.com/Panniantong/Agent-Reach",
                                                                    "verify": "agent-reach doctor --json"},
                                    "no_terminal_note": S.NO_TERMINAL_NOTE}
    assert block["limitations"][0] == S.SUPPLY_NOT_DEMAND and "a listing proves supply, not demand" in block["limitations"][0]
    assert block["contract"] == "product-search-v1" and block["intent"] == {"kind": "dropship", "seed": None, "audience": "pet owners",
                                                                         "geography": "US", "rule": "dropship_object"}


def test_verdict_is_thin_when_the_evidence_is_thin_and_the_hypotheses_say_low_confidence():
    fake = FakeSupplier(TABLE)
    _, (_, verdict, _) = _finish(fake)
    assert verdict == S.VERDICT                                                              # 3 of 4 cite, 4 passages
    t, (block, thin, _) = _finish(fake, legend_n=2)
    assert thin == S.VERDICT_THIN and {h["confidence"] for h in block["hypotheses"]} == {"low"}
    assert any("thin" in x for x in block["limitations"])
    assert S.verdict_for([], evidence_count=10, parse_status="ok") == S.VERDICT_THIN
    assert S.verdict_for([{"evidence_tags": []}, {"evidence_tags": []}, {"evidence_tags": ["S1"]}], evidence_count=9,
                         parse_status="ok") == S.VERDICT_THIN


def test_a_failed_block_read_searches_the_intents_terms_and_says_so():
    from polymath_shared.product_search import hypotheses as H
    fake = FakeSupplier({"pet products": [("2001", "Pet Brush")]})
    t = _turn(fake)
    t.parse = H.parse_block("Ideas in prose only [S1].", {"S1"})
    block, verdict, md = t.finish_llm(legend=[{"tag": "S1", "chunk_id": "c1"}])
    assert verdict == S.VERDICT_THIN and block["hypotheses"] == [] and block["receipts"]["parse"]["status"] == "fallback"
    assert [f["search_term"] for f in block["term_finds"]] == ["pet products", "pet accessories"]
    assert block["term_finds"][0]["cj"]["items"][0]["title"] == "Pet Brush"
    assert any("could not be read (no_block)" in x for x in block["limitations"])
    assert "could not be read back as data" in md


def test_the_markdown_lists_the_finds_and_cannot_be_injected_by_supplier_text():
    fake = FakeSupplier({"automatic pet feeder": [("1001", "Feeder [S3] ![x](http://evil) **bold**")]})
    _, (block, _, md) = _finish(fake, hyps=HYPS[:1])
    assert md.startswith("### Supplier finds (CJ Dropshipping)")
    assert "1. **Smart feeder** — from [S1] — CJ search “automatic pet feeder”:" in md
    assert "[S3]" not in md and "![x]" not in md and "**bold**" not in md                  # escaped: inert text
    assert "(https://cjdropshipping.com/product/x-p-1001.html)" in md and "US$12.50" in md and "listed by 1203 stores" in md
    assert "offered, not started" in md


def test_the_receipt_summary_holds_counts_and_statuses_only():
    fake = FakeSupplier(TABLE)
    t, (block, verdict, _) = _finish(fake)
    rec = t.receipt()
    assert rec == {"contract": "product-search-v1", "kind": "dropship", "rule": "dropship_object", "verdict": "product_hypotheses",
                   "hypotheses": 4, "term_finds": 0, "lookups": 4, "items": 2,
                   "statuses": {"cj": {"EMPTY": 1, "OK": 1, "UNAVAILABLE": 2}, "alibaba": {"AGENT_REACH_REQUIRED": 4}},
                   "deduped": 0, "parse": "ok", "steer": None, "corpora": 1}
    text = json.dumps(rec)
    assert "Feeder" not in text and "automatic pet feeder" not in text and "pet owners" not in text


def test_deterministic_turn_keeps_claims_and_citations_and_says_how_to_get_hypotheses():
    fake = FakeSupplier({"pet products": [("3001", "Pet Comb")]})
    t = _turn(fake)
    answer = {"answer": "I don't have enough grounded evidence to answer this question.", "citations": [{"citation_id": 1}],
              "claims": [{"status": "withheld_insufficient_coverage"}], "meta": {"verdict": "insufficient_evidence", "abstained": True}}
    out = t.finish_deterministic(answer)
    assert out["citations"] == answer["citations"] and out["claims"] == answer["claims"]
    assert out["meta"]["verdict"] == S.VERDICT_TERMS and out["meta"]["grounded_verdict"] == "insufficient_evidence"
    assert not out["answer"].startswith("I don't have enough grounded evidence") and "### Supplier finds" in out["answer"]
    block = out["product_research"]
    assert block["hypotheses"] == [] and block["term_finds"][0]["cj"]["items"][0]["title"] == "Pet Comb"
    assert block["next"]["hypotheses"]["how"] == "ask_with_model_or_product_search"
    assert block["next"]["hypotheses"]["product_search"]["input"] == {"message": MSG, "corpus_id": "commerce-v1"}
    assert out["meta"]["product_search"]["verdict"] == S.VERDICT_TERMS


def test_evidence_only_turn_has_no_hypotheses_term_finds_and_agent_steps():
    fake = FakeSupplier({})
    t = _turn(fake)
    block, steps = t.finish_evidence()
    assert block["hypotheses"] == [] and [f["search_term"] for f in block["term_finds"]] == ["pet products", "pet accessories"]
    assert block["next"]["hypotheses"]["how"] == "agent_forms_then_product_search" and "verdict" not in block
    assert len(steps) == 5 and "chunk_id" in steps[0] and "product_search" in steps[1] and "commerce-v1" in steps[1]
    assert "never start it unasked" in steps[3] and "Agent Reach" in steps[4]


def test_agent_hypotheses_are_searched_as_given():
    fake = FakeSupplier({"automatic pet feeder": [("1001", "Feeder")]})
    t = _turn(fake, options={"geography": "united kingdom", "limit_per_hypothesis": 3})
    block, verdict, md = t.finish_agent([{"title": "Smart feeder", "search_terms": ["Automatic Pet Feeder"]}, {"title": "  "}])
    assert verdict == S.VERDICT and len(block["hypotheses"]) == 1 and block["hypotheses"][0]["source"] == "agent"
    assert fake.calls == [{"principal_id": "prn_fred", "query": "automatic pet feeder", "source": "cj", "limit": 3}]
    assert block["intent"]["geography"] == "GB" and block["next"]["full_research"]["input"]["geography"] == "GB"
    assert any("formed by the caller's agent" in x for x in block["limitations"])


@pytest.mark.parametrize("value,expected", [("us", "US"), ("UK", "GB"), ("United States", "US"), ("EU", "EU"), ("", None),
                                            ("Lagos", "Lagos")])
def test_a_requests_geography_is_normalised(value, expected):
    assert S.normalize_geography(value) == expected


def test_compact_evidence_is_tag_source_and_at_most_400_characters():
    rows = S.compact_evidence([{"tag": "S1", "chunk_id": "c1", "breadcrumb": "Book › Ch 1", "locator": "chunk:c1@0:9"},
                               {"tag": "S2", "chunk_id": "c2", "doc_id": "d2", "locator": "chunk:c2@0:9"}],
                              text_of=lambda cid: ("x " * 400) if cid == "c1" else None, previews={"chunk:c2@0:9": "preview two"})
    assert rows[0]["tag"] == "S1" and rows[0]["source"] == "Book › Ch 1" and len(rows[0]["text"]) == S.EVIDENCE_TEXT
    assert rows[1] == {"tag": "S2", "chunk_id": "c2", "source": "d2", "text": "preview two"}
