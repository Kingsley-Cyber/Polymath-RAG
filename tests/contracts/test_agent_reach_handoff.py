"""PRODUCT-SEARCH-E2E (the owner's decisions of 2026-11-01): the user-side Agent Reach handoff and the server-side parser of its output.
  * "cj dropshipping is api and agent reach cli, and alibaba is strictly agent reach"; "it should never use a users claude native web
    search due to bot detections"; "prompt users to install it on their end and use their agent reach setup if api fails".
  * the host never calls Exa or Jina: `agent_reach.fallback` only BUILDS shell-safe commands (an Exa search restricted to the site
    through mcporter, a Jina Reader read per product page) and `agent_reach.parse` / `supplier.parse` / POST /supplier/parse only
    read what the user sends back, line by line, into the supplier_search shape;
  * a verification page is refused (HUMAN_CHECK) everywhere: the parser, the challenge detector, the receipt check.
Fixtures (tests/fixtures/agent_reach/) are the owner's REAL Agent Reach probe outputs of 2026-11-01, unedited, except the probe
script's own `curl_exit=0` line dropped from the access-denied read:
  alibaba_exa_pet_hair_remover.txt         `mcporter call exa.web_search_exa` restricted to alibaba.com, 3 product results
  alibaba_jina_product_page.txt            `curl -s https://r.jina.ai/<alibaba product page>` (80 KB, other products' prices beside)
  alibaba_jina_showroom_access_denied.txt  Jina on an alibaba.com showroom page: Akamai's Access Denied
  cj_exa_pet_hair_remover.txt              Exa restricted to cjdropshipping.com: 1 product, 2 "Human verification" pages
  cj_jina_human_verification.txt           Jina on a CJ product page: landed on /egg/cj/validation.html
No network, no browser, no database."""
from __future__ import annotations

import ast
import copy
import json
import pathlib
import shlex
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import agent_reach as AR
from polymath_shared.acquisition import challenge as CH
from polymath_shared.acquisition import searxng as SX
from polymath_shared.acquisition import service as S
from polymath_shared.acquisition import supplier as SUP
from polymath_shared.adapter import transitions as T

FIX = ROOT / "tests" / "fixtures" / "agent_reach"
ALI_EXA, ALI_JINA, ALI_DENIED = "alibaba_exa_pet_hair_remover.txt", "alibaba_jina_product_page.txt", "alibaba_jina_showroom_access_denied.txt"
CJ_EXA, CJ_JINA = "cj_exa_pet_hair_remover.txt", "cj_jina_human_verification.txt"


def _fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _listings(site: str, name: str) -> list[dict]:
    return [r["listing"] for r in AR.parse(site, _fx(name))["records"]]


@pytest.fixture(autouse=True)
def _fresh_fair_use(monkeypatch):
    monkeypatch.setattr(SUP, "FAIR_USE", SUP.FairUse())


def test_the_code_under_test_is_this_checkout():
    for mod in (AR, CH, SX, S, SUP, T):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


def test_the_host_never_reads_the_web_for_agent_reach():
    """The module only builds commands and parses text: it imports nothing that could reach the network or run a command."""
    tree = ast.parse((ROOT / "shared/polymath_shared/acquisition/agent_reach.py").read_text())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not imported & {"httpx", "requests", "urllib3", "socket", "subprocess", "aiohttp", "os"}, imported
    assert not hasattr(SX, "SearXNGListings") and not hasattr(SX, "parse_snippet") and not hasattr(SX, "base_url")   # retired


# ─────────────────────────────────────────────────────────── the parser on the real probe outputs
def test_alibaba_exa_results_parse_line_by_line_with_tiers_moq_and_supplier():
    got = AR.parse("alibaba.com", _fx(ALI_EXA))
    assert got["tool_class"] == "agent_reach.exa" and got["documents"] == 3 and got["refused"] == []
    first, second, third = (r["listing"] for r in got["records"])
    assert first["title"] == ("Silicone Double Sided Pet Hair & Lint Remover for Cats Clean Tool for Shaver Sweater Fabric Scraper on "
                              "Clothes & Carpet")
    assert first["price_as_listed"] == "$0.18 (55-99 pieces), $0.17 (100-499 pieces), $0.16 (≥500 pieces)"     # every tier, verbatim
    assert first["minimum_order_as_listed"] == "55 pieces"                    # BUG 3 fixed: the first tier IS the minimum order
    assert (first["reviews_as_shown"], first["sold_as_shown"], first["supplier"]) == ("5.0 (2 reviews)", "261 sold", None)
    assert (second["supplier"], second["supplier_years_as_shown"], second["minimum_order_as_listed"]) == \
        ("Yiwu Kinghon Pet Products Co., Ltd.", "8 yrs", "50pcs")
    assert second["price_as_listed"] is None and second["reviews_as_shown"] == "no reviews yet"
    # BUG 1 fixed: "FREE shipping capped at $30" is a sentence, never the price; the price line is "$1.25"
    assert third["price_as_listed"] == "$1.25" and third["minimum_order_as_listed"] == "10 pcs"
    # BUG 2 fixed: the supplier is the company's own whole line, never title words glued onto it
    assert (third["supplier"], third["supplier_years_as_shown"], third["sold_as_shown"]) == ("Huizhou Shengfeng Feather Craft Factory", "6 yrs", "2481 sold")
    assert [r["url"] for r in got["records"]] == [
        "https://www.alibaba.com/product-detail/Silicone-Double-Sided-Pet-Hair-Lint_1601132652199.html",
        "https://www.alibaba.com/product-detail/KingHon-Washable-Reusable-Self-Cleaning-Dog_1601213346227.html",
        "https://www.alibaba.com/product-detail/Factory-Wholesale-Pet-Grooming-Products-Two_1601569422319.html"]
    assert [r["listing"]["product_id"] for r in got["records"]] == ["1601132652199", "1601213346227", "1601569422319"]


def test_the_alibaba_jina_page_gives_the_supplier_card_and_tiers_never_other_products_prices():
    got = AR.parse("www.alibaba.com", _fx(ALI_JINA))
    assert got["tool_class"] == "agent_reach.jina" and got["documents"] == 1 and got["refused"] == []
    (rec,) = got["records"]
    lst = rec["listing"]
    assert (lst["supplier"], lst["supplier_years_as_shown"]) == ("Suzhou Fine Era Trade Co., Ltd.", "8 yrs")      # the company card
    assert lst["price_as_listed"] == "$0.18 (55-99 pieces), $0.17 (100-499 pieces), $0.16 (≥500 pieces)"
    assert lst["minimum_order_as_listed"] == "55 pieces"                      # never "1 piece" / "$3.98" of a recommended product
    assert (lst["reviews_as_shown"], lst["sold_as_shown"]) == ("5.0 (2 reviews)", "351 sold")
    assert rec["url"] == "https://www.alibaba.com/product-detail/Silicone-Double-Sided-Pet-Hair-Lint_1601132652199.html"
    assert rec["text"].startswith("Silicone Double Sided Pet Hair") and "supplier: Suzhou Fine Era Trade Co., Ltd." in rec["text"]


def test_cj_exa_output_keeps_the_product_and_refuses_both_human_verification_pages():
    got = AR.parse("cjdropshipping.com", _fx(CJ_EXA))
    (rec,) = got["records"]
    assert rec["listing"]["product_id"] == "1436180227997962240" and rec["listing"]["price_as_listed"] == "$0.27-1.73"
    assert rec["listing"]["sku"] == "CJGY128170303CX" and rec["listing"]["title"].startswith("Silicone Dog Bath Massage Gloves")
    assert [r["code"] for r in got["refused"]] == ["HUMAN_CHECK", "HUMAN_CHECK"]
    assert got["refused"][0]["url"].startswith("https://cjdropshipping.com/product/pet-hair-remover-mitt")     # a product URL, a check page's text
    assert "/egg/cj/validation.html" in got["refused"][1]["url"]                                               # the check page itself
    assert any("2 page(s) refused: HUMAN_CHECK" in n for n in got["notes"])


@pytest.mark.parametrize("site,name", [("cjdropshipping.com", CJ_JINA), ("alibaba.com", ALI_DENIED)])
def test_a_jina_read_that_landed_on_a_check_page_admits_nothing(site, name):
    got = AR.parse(site, _fx(name))
    assert got["records"] == [] and [r["code"] for r in got["refused"]] == ["HUMAN_CHECK"]
    assert "Never solve, skip or work around it" in got["refused"][0]["why"]


def test_supplier_parse_returns_the_supplier_search_shape_with_the_tool_class():
    out = SUP.parse(principal_id="prn_fred", site="alibaba", raw_text=_fx(ALI_EXA))
    assert (out["contract"], out["tool"], out["source"], out["site"], out["status"]) == ("supplier-tools-v1", "supplier_parse", "alibaba", "alibaba.com", "OK")
    assert out["tool_class"] == out["tool_trace"]["tool_class"] == "agent_reach.exa" and out["tool_trace"]["query_count"] == 1
    assert len(out["items"]) == len(out["sources"]) == 3 and {s["source_class"] for s in out["sources"]} == {"supplier_listing"}
    assert all(i["source_id"] in {s["source_id"] for s in out["sources"]} and i["kind"] == "listing" for i in out["items"])
    assert out["items"][0]["listing"]["product_id"] == "1601132652199" and out["refused"] == [] and out["fallback"] is None
    assert any("untrusted" in x for x in out["limitations"]) and any("Polymath opened no page" in x for x in out["limitations"])
    # after an Exa search: the exact Jina command for each product it found (no placeholder left to fill in)
    assert out["next"]["commands"][0] == "curl -s https://r.jina.ai/https://www.alibaba.com/product-detail/Silicone-Double-Sided-Pet-Hair-Lint_1601132652199.html"
    page = SUP.parse(principal_id=None, site="alibaba.com", raw_text=_fx(ALI_JINA))
    assert page["tool_class"] == "agent_reach.jina" and page["next"] is None and page["items"][0]["listing"]["supplier"] == "Suzhou Fine Era Trade Co., Ltd."
    walls = SUP.parse(principal_id="prn_fred", site="cj", raw_text=_fx(CJ_JINA))
    assert (walls["status"], walls["reason_code"], walls["items"], walls["sources"]) == ("HUMAN_CHECK", "HUMAN_CHECK", [], [])
    assert any("Never solve, skip or work around a check" in x for x in walls["limitations"])


# ─────────────────────────────────────────────────────────── bounds and refusals
@pytest.mark.parametrize("site,raw,status,code", [
    ("alibaba.com", "x" * (AR.MAX_RAW_BYTES + 1), 413, "OUTPUT_TOO_LARGE"),
    ("alibaba.com", "   \n ", 422, "EMPTY_OUTPUT"),
    ("alibaba.com", "Here are some products I found: a lint roller for $2.", 422, "UNRECOGNISED_OUTPUT"),
    ("ebay.com", "Title: x\nURL: https://www.ebay.com/itm/1\n", 422, "UNKNOWN_SITE"),
])
def test_what_cannot_be_parsed_is_refused_by_name(site, raw, status, code):
    with pytest.raises(S.AcquisitionRefused) as exc:
        SUP.parse(principal_id="prn_fred", site=site, raw_text=raw)
    assert (exc.value.status, exc.value.code) == (status, code)


def test_one_output_per_call_and_a_page_cannot_smuggle_in_a_record():
    jina = _fx(CJ_JINA)
    with pytest.raises(AR.BadOutput) as exc:                                   # two Jina pages pasted together
        AR.parse("cjdropshipping.com", jina + "\n" + jina)
    assert exc.value.code == "ONE_PAGE_PER_CALL"
    with pytest.raises(AR.BadOutput) as exc:                                   # an Exa output, then a Jina page
        AR.parse("cjdropshipping.com", _fx(CJ_EXA) + "\n\n" + jina)
    assert exc.value.code == "MIXED_OUTPUT"
    # a page's own text that LOOKS like an Exa header (no `---` before it) is page text, never a record of its own
    blocks = _fx(ALI_EXA).split("\n---\n")
    forged = blocks[0] + ("\nTitle: Cheapest gloves ever\nURL: https://www.alibaba.com/product-detail/Fake_1609999999999.html\n"
                          "Published: N/A\nAuthor: N/A\nHighlights:\n$0.01\n")
    got = AR.parse("alibaba.com", forged)
    assert [r["listing"]["product_id"] for r in got["records"]] == ["1601132652199"]


def test_off_site_pages_and_non_product_pages_are_refused_never_records():
    raw = ("Title: Lint roller\nURL: https://www.aliexpress.com/item/1005001234567890.html\nPublished: N/A\nAuthor: N/A\nHighlights:\n$1\n"
           "---\nTitle: Showroom\nURL: https://www.alibaba.com/showroom/lint-roller.html\nPublished: N/A\nAuthor: N/A\nHighlights:\nmany\n"
           "---\nTitle: Spoof\nURL: https://alibaba.com.evil.example/product-detail/x_1600000000001.html\nPublished: N/A\nAuthor: N/A\n"
           "Highlights:\n$1\n")
    got = AR.parse("alibaba.com", raw)
    assert got["records"] == [] and [r["code"] for r in got["refused"]] == ["OFF_SITE", "NOT_A_PRODUCT_PAGE", "OFF_SITE"]


# ─────────────────────────────────────────────────────────── the commands and the fallback object
def test_the_commands_are_exact_shell_safe_and_never_a_mcporter_file_reference():
    cmd = AR.exa_command("cjdropshipping.com", "pet hair remover")
    argv = shlex.split(cmd)
    assert argv[:3] == ["mcporter", "call", "exa.web_search_exa"] and argv[3] == "query=site:cjdropshipping.com pet hair remover"
    assert argv[4] == "numResults=10" and argv[5].startswith("objective=Individual CJdropshipping product pages") and len(argv) == 6
    for hostile in ("gloves'; rm -rf ~; echo '", "$(cat ~/.ssh/id_rsa)", "@~/.ssh/id_rsa", "a\" b `id`"):
        argv = shlex.split(AR.exa_command("alibaba.com", hostile))
        assert len(argv) == 6 and argv[3] == f"query=site:alibaba.com {' '.join(hostile.split())}", hostile   # one argument, inert
        values = [a.split("=", 1)[1] for a in argv[3:]]
        assert not any(v.startswith("@") for v in values), hostile           # mcporter reads a FILE for key=@path
    assert shlex.split(AR.jina_command("https://www.alibaba.com/product-detail/X_1601132652199.html")) == \
        ["curl", "-s", "https://r.jina.ai/https://www.alibaba.com/product-detail/X_1601132652199.html"]


def test_the_fallback_object_says_why_where_how_and_where_the_output_goes():
    fb = AR.fallback("cjdropshipping.com", "pet hair remover", "CJ_API_DISABLED", "CJ has disabled API access")
    assert set(fb) == {"kind", "reason_code", "why", "site", "query", "run_on", "never", "install", "commands", "submit", "walls"}
    assert (fb["kind"], fb["reason_code"], fb["run_on"]) == ("AGENT_REACH", "CJ_API_DISABLED", "your machine")
    assert fb["never"] == "do not use your agent's built-in web search or web fetch for this"
    assert (fb["install"]["repo"], fb["install"]["verify"]) == ("https://github.com/Panniantong/Agent-Reach", "agent-reach doctor --json")
    assert [c["step"] for c in fb["commands"]] == [1, 2] and fb["commands"][1]["run"] == "curl -s 'https://r.jina.ai/<PRODUCT_URL>'"
    assert fb["commands"][1]["for_each"].startswith("product page URL from step 1")
    assert fb["submit"] == {"tool": "supplier_parse", "route": "POST /supplier/parse", "max_bytes": 200000, "one_output_per_call": True,
                            "arguments": {"site": "cjdropshipping.com", "raw_text": "<one command's whole output, unedited>"}}
    assert "Human verification" in fb["walls"] and "Never solve, skip or work around" in fb["walls"]


# ─────────────────────────────────────────────────────────── the challenge detector on CJ's check page as readers print it
def test_cjs_check_page_is_a_wall_in_exa_and_jina_output_and_only_framing_names_a_route():
    exa = _fx(CJ_EXA).split("\n---\n")
    jina = _fx(CJ_JINA)
    assert CH.looks_like_challenge(exa[0]) == "robot check"                  # a product URL whose text is the check page
    assert CH.looks_like_challenge(exa[0].split("Highlights:", 1)[1])
    assert CH.looks_like_challenge(exa[2]) == "verification page route"       # Exa's URL: is /egg/cj/validation.html
    assert CH.looks_like_challenge(jina) == "verification page route"         # Jina's Final URL: landed on it
    assert CH.looks_like_challenge(jina.split("Markdown Content:", 1)[1])     # the markdown alone: images and form furniture are not content
    title_only = "Title: Human verification\n\nURL Source: https://cjdropshipping.com/product/x-p-1436180227997962240.html\n\nMarkdown Content:\nLoading...\n\nSubmit"
    assert CH.looks_like_challenge(title_only) == "human check"               # the check page's own title
    assert CH.wall_route("https://frontend.cjdropshipping.com/egg/cj/validation.html?rd=x") and not CH.wall_route("https://cjdropshipping.com/search/validation.html")
    # content stays content: a real product read, a post titled Captcha, a link that merely mentions the route
    assert CH.looks_like_challenge(exa[1]) is None and CH.looks_like_challenge(_fx(ALI_JINA)) is None
    assert CH.looks_like_challenge("Title: Captcha\n\nURL Source: https://www.reddit.com/r/x/comments/abc123/captcha/\n\nMarkdown Content:\n"
                                   "it asks me to prove I am not a robot") is None
    assert CH.looks_like_challenge("CJ keeps sending me to [this page](https://frontend.cjdropshipping.com/egg/cj/validation.html) when I "
                                   "search, has anyone found a way to contact support about it? I have tried three browsers already.") is None


EXAMPLE = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
STEP = {"run_id": EXAMPLE["run_id"], "harness_action": {"action_id": EXAMPLE["action_id"]}}


@pytest.mark.parametrize("quote", [_fx(CJ_JINA)[:2000], _fx(CJ_EXA).split("\n---\n")[0].split("Highlights:", 1)[1][:600]])
def test_a_receipt_that_quotes_cjs_check_page_is_refused(quote):
    receipt = copy.deepcopy(EXAMPLE)
    receipt["observations"][1]["paraphrase_or_excerpt"] = quote[:600]
    errors = T.validate_receipt(STEP, receipt)
    assert [e for e in errors if e.startswith("CHALLENGE_PAGE_AS_EVIDENCE")], errors


# ─────────────────────────────────────────────────────────── the route
def _app(monkeypatch):
    from fastapi import FastAPI
    from orchestrator.api import acquisition as R
    from polymath_shared import principal_context
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.include_router(R.router)
    return app


def test_the_parse_route_serves_the_owner_and_friends_and_keeps_the_route_rules(monkeypatch):
    from fastapi.testclient import TestClient
    from polymath_shared import principal_context
    app = _app(monkeypatch)
    c = TestClient(app, base_url="http://127.0.0.1:7200")
    body = {"site": "alibaba.com", "raw_text": _fx(ALI_EXA)}
    for headers in ({}, {principal_context.HEADER: "prn_fred"}):
        r = c.post("/supplier/parse", json=body, headers=headers)
        assert r.status_code == 200 and r.json()["status"] == "OK" and len(r.json()["items"]) == 3, r.text
    assert c.post("/supplier/parse", json=body, headers={"X-Forwarded-For": "203.0.113.9"}).json()["detail"]["code"] == "PROXIED_CALLER"
    assert TestClient(app, base_url="http://rebind.attacker.example:7200").post("/supplier/parse", json=body).status_code == 403
    big = c.post("/supplier/parse", json={"site": "alibaba.com", "raw_text": "x" * (AR.MAX_RAW_BYTES + 1)})
    assert big.status_code == 413 and big.json()["detail"]["code"] == "OUTPUT_TOO_LARGE"
