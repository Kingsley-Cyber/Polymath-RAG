"""AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8 (the owner's worker-pack prompt 06): Polymath reads permitted pages FOR a connected harness
that has no browser of its own, through the MCP tool `research_acquire`. Pinned here, with a recorded backend (no browser, no database,
no network):
  * WHO: the owner only (a principal is refused; the MCP gate leaves the tool out of every principal's scope);
  * WHEN: only for the run's OPEN research step, inside its disallowed classes, search intents and query budget;
  * WHAT: content permalinks matched in full, listing searches on the supported sites, web search as leads only; the backend calls
    no write command;
  * WHAT IS TRUE: one source per (page, publish date), each comment's own date and its precision, no handle on the wire, a wall is
    HUMAN_ACTION_REQUIRED and never a read.
The audit of 2026-09-25 (the owner's "yes") added: an undated comment is dated by its page (or withheld), never at the moment of
reading; YouTube is read in our own tab (full text, the video's date, whether more exist); Instagram's post-date row is never a
comment and a signed-out post view is a sign-in requirement; a read that returned nothing spends no query; every read names a search
intent; TikTok's login modal is a wall; a request relayed by a proxy is refused.
TRAIL-EXT-BUGHUNT-V1 (2026-09-26) added: a page that only MENTIONS a wall (its title, opening text, community name or slug) is read
(B-17); a comment list whose HTTP-200 reply did not parse, or carried no comment section, is unavailable, never a read (B-18); only
a request naming a loopback host reaches the route (B-28).
"""
import ast
import asyncio
import contextlib
import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.acquisition import opencli as O  # noqa: E402
from polymath_shared.acquisition import service as S  # noqa: E402

VIDEO = "https://www.tiktok.com/@creator/video/7400000000000000001"
ACTION = {"action_id": "hact_" + "a" * 24, "run_id": "adr_" + "b" * 32, "budget": {"max_queries": 3, "max_sources": 15, "max_observations": 60},
          "disallowed_source_roles": [], "search_intents": [{"intent_id": "si_comments", "intent": "comments", "evidence_goal": "friction",
                                                             "evidence_roles": ["friction"]}]}


class Recorded:
    """A backend that answers from a recording (what the browser bridge returned for one read)."""

    def __init__(self, raw):
        self.raw, self.reads = raw, []

    def status(self):
        return {"backend": "recorded", "available": True}

    def read(self, target, limit):
        self.reads.append((target, limit))
        return dict(self.raw)


def _action(**kw):
    """A fresh open research step per test (the query budget is counted per action id)."""
    return {**ACTION, "action_id": "hact_" + hashlib.sha256(json.dumps(kw, sort_keys=True).encode()).hexdigest()[:24], **kw}


def test_the_code_under_test_is_this_checkout():
    for mod in (S, O):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


def test_only_the_owner_may_acquire():
    for op in ("catalog", "comments"):
        with pytest.raises(S.AcquisitionRefused) as exc:
            S.acquire(principal_id="prn_fred", action=ACTION, operation=op, target=VIDEO, backend=Recorded({"state": "ok"}))
        assert exc.value.status == 403 and exc.value.code == "OWNER_ONLY"


@pytest.mark.parametrize("url,canonical", [
    (VIDEO, VIDEO), (VIDEO + "?is_from_webapp=1&sender_device=pc", VIDEO),
    ("https://www.instagram.com/reel/C0ABCDEFGHI/", "https://www.instagram.com/p/C0ABCDEFGHI/"),
    ("https://instagram.com/reels/C0ABCDEFGHI", "https://www.instagram.com/p/C0ABCDEFGHI/"),
    ("https://www.youtube.com/watch?v=o1t-Km5cfo0&t=42s", "https://www.youtube.com/watch?v=o1t-Km5cfo0"),
    ("https://youtu.be/o1t-Km5cfo0", "https://www.youtube.com/watch?v=o1t-Km5cfo0"),
    ("https://old.reddit.com/r/coldplunge/comments/abc123/my_tub_leaks/", "https://www.reddit.com/r/coldplunge/comments/abc123/")])
def test_comment_targets_are_content_permalinks_in_canonical_form(url, canonical):
    t = S.resolve("comments", url)
    assert t.url == canonical and t.source_class in ("video_platform", "community_discussion")


@pytest.mark.parametrize("url", [
    "https://vm.tiktok.com/ZMabcdefg/", "https://www.tiktok.com/@creator", "https://www.tiktok.com/messages",
    "https://www.instagram.com/accounts/edit/", "https://www.instagram.com/someone/", "https://www.youtube.com/feed/history",
    "https://www.youtube.com/@channel", "https://www.reddit.com/user/me/saved", "https://www.amazon.com/gp/your-account/order-history",
    "https://mail.google.com/mail/u/0/", "javascript:alert(1)", VIDEO + "\nhttps://mail.google.com/", "file:///etc/passwd"])
def test_account_pages_feeds_profiles_short_links_and_other_sites_are_refused(url):
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.resolve("comments", url)
    assert exc.value.status == 422 and exc.value.code == "TARGET_NOT_PERMITTED"


def test_listings_run_only_on_the_supported_sites_and_queries_are_bounded():
    assert S.resolve("listings", "camera rain cover", "www.alibaba.com").query == "camera rain cover"
    assert S.resolve("listings", "camera rain cover", "https://cjdropshipping.com/").source_class == "supplier_listing"
    assert S.resolve("listings", "camera rain cover", "amazon.com").source_class == "marketplace_listing"
    for bad_site in ("ebay.com", "mail.google.com", None):
        with pytest.raises(S.AcquisitionRefused) as exc:
            S.resolve("listings", "camera rain cover", bad_site)
        assert exc.value.code == "SITE_NOT_SUPPORTED"
    for bad_query in ("", "x", "y" * 301):
        with pytest.raises(S.AcquisitionRefused):
            S.resolve("web_search", bad_query)
    assert S.resolve("web_search", "rain  covers", "tiktok.com").query == "site:tiktok.com rain covers"
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.resolve("post_comment", VIDEO)
    assert exc.value.code == "UNKNOWN_OPERATION"


def test_a_read_needs_the_open_research_step_and_stays_inside_it():
    ok = Recorded({"state": "ok", "records": []})
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.acquire(principal_id=None, action=None, operation="comments", target=VIDEO, backend=ok)
    assert exc.value.status == 409 and exc.value.code == "NO_OPEN_RESEARCH_STEP"
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.acquire(principal_id=None, action=_action(disallowed_source_roles=["video_platform"]), operation="comments", target=VIDEO, backend=ok)
    assert exc.value.code == "SOURCE_DISALLOWED"
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.acquire(principal_id=None, action=_action(tag=1), operation="comments", target=VIDEO, search_intent_id="si_invented", backend=ok)
    assert exc.value.code == "UNKNOWN_SEARCH_INTENT"
    budgeted = _action(budget={"max_queries": 2})
    for _ in range(2):
        S.acquire(principal_id=None, action=budgeted, operation="comments", target=VIDEO, search_intent_id="si_comments", backend=ok)
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.acquire(principal_id=None, action=budgeted, operation="comments", target=VIDEO, search_intent_id="si_comments", backend=ok)
    assert exc.value.status == 429 and exc.value.code == "QUERY_BUDGET_SPENT" and len(ok.reads) == 2
    with pytest.raises(S.AcquisitionRefused) as exc:
        S.acquire(principal_id=None, action=_action(tag="no-intent"), operation="comments", target=VIDEO, backend=ok)
    assert exc.value.status == 422 and exc.value.code == "MISSING_SEARCH_INTENT"
    assert S.acquire(principal_id=None, action=None, operation="catalog", target="", backend=ok)["owner_only"] is True


def test_each_comment_keeps_its_own_date_and_says_how_precise_it_is():
    raw = {"state": "ok", "page_url": VIDEO, "retrieved_at": "2026-09-25T20:00:00Z", "total": 237, "complete": False, "records": [
        {"kind": "caption", "ref": "caption", "text": "it's still raining", "published_at": "2026-06-10T19:26:26Z", "precision": "exact"},
        {"kind": "comment", "ref": "c1", "text": "my lens fogged up in the rain", "published_at": "2026-06-13T16:10:23Z", "precision": "exact",
         "author": "SomeHandle", "likes": 90},
        {"kind": "comment", "ref": "c2", "text": "same, gave up and used a bag", "published_at": "2026-06-13T16:10:23Z", "precision": "exact",
         "author": "other.handle"},
        {"kind": "comment", "ref": "c3", "text": "3 years later still true", "published_at": "2029-01-01T00:00:00Z", "precision": "relative",
         "date_shown": "3 weeks ago", "author": "SomeHandle"}]}
    out = S.acquire(principal_id=None, action=_action(tag=2), operation="comments", target=VIDEO, search_intent_id="si_comments",
                    backend=Recorded(raw))
    by = {i["excerpt"]: i for i in out["items"]}
    src = {s["source_id"]: s for s in out["sources"]}
    assert out["status"] == "PARTIAL" and out["completeness"] == {"read": 4, "available": 237, "complete": False, "order": "the site's own order"}
    assert [src[by[t]["source_id"]]["published_at_if_known"] for t in ("it's still raining", "my lens fogged up in the rain")] == \
        ["2026-06-10T19:26:26Z", "2026-06-13T16:10:23Z"]
    assert by["my lens fogged up in the rain"]["source_id"] == by["same, gave up and used a bag"]["source_id"]      # same page, same date: one row
    rel = by["3 years later still true"]
    assert rel["published_at"] is None and rel["date_precision"] == "relative" and rel["date_shown"] == "3 weeks ago"
    assert rel["source_id"] is None and rel["source_date"] == "none"            # never turned into a date, never dated at reading time
    assert any("not receipt-ready" in x for x in out["limitations"]) and any("untrusted page text" in x for x in out["limitations"])
    assert {s["url"] for s in out["sources"]} == {VIDEO} and {s["source_class"] for s in out["sources"]} == {"video_platform"}
    assert all(s["retrieved_at"] == "2026-09-25T20:00:00Z" for s in out["sources"])
    wire = json.dumps(out)
    assert "SomeHandle" not in wire and "other.handle" not in wire                                                   # a pseudonym, never the handle
    assert by["my lens fogged up in the rain"]["author_key"] == rel["author_key"] != by["same, gave up and used a bag"]["author_key"]
    assert out["tool_trace"] == {"search_intent_id": "si_comments", "tool_class": "polymath.acquire/comments", "query_count": 1}
    assert re.fullmatch(r"acq_[0-9a-f]{24}", out["acquisition_id"]) and any("relative age" in x for x in out["limitations"])
    assert any("read 4 of 237" in x for x in out["limitations"])
    dated = S.acquire(principal_id=None, action=_action(tag="page-dated"), operation="comments", target=VIDEO, search_intent_id="si_comments",
                      backend=Recorded(dict(raw, page_published_at="2026-06-10T19:26:26Z")))
    rel2 = next(i for i in dated["items"] if i["excerpt"] == "3 years later still true")
    assert rel2["source_date"] == "page" and rel2["published_at"] is None
    assert {s["source_id"]: s for s in dated["sources"]}[rel2["source_id"]]["published_at_if_known"] == "2026-06-10T19:26:26Z"
    assert any("dated by the page's publish date" in x for x in dated["limitations"])


@pytest.mark.parametrize("state,words", [("human_check", "human check"), ("sign_in", "sign-in")])
def test_a_wall_is_a_human_action_and_never_a_read(state, words):
    out = S.acquire(principal_id=None, action=_action(tag=state), operation="listings", target="camera rain cover", site="cjdropshipping.com",
                    search_intent_id="si_comments", backend=Recorded({"state": state, "page_url": "https://cjdropshipping.com/search/camera+rain+cover.html"}))
    assert out["status"] == "HUMAN_ACTION_REQUIRED" and out["items"] == [] and out["sources"] == []
    assert out["human_action"]["kind"] == state and out["human_action"]["retry"] is True and "cjdropshipping.com" in out["human_action"]["instruction"]
    assert any(words in x and "not bypassed" in x for x in out["limitations"])
    assert out["budget"]["refunded"] is True and out["budget"]["queries_used_here"] == 0 and out["tool_trace"]["query_count"] == 0


def test_a_person_can_act_and_the_caller_can_call_again_without_spending_the_budget():
    step = _action(tag="waits", budget={"max_queries": 2})
    wall = Recorded({"state": "human_check"})
    for _ in range(5):                                                   # the owner has not passed the check yet
        assert S.acquire(principal_id=None, action=step, operation="listings", target="rain cover", site="cjdropshipping.com",
                         search_intent_id="si_comments", backend=wall)["status"] == "HUMAN_ACTION_REQUIRED"
    read = S.acquire(principal_id=None, action=step, operation="listings", target="rain cover", site="cjdropshipping.com",
                     search_intent_id="si_comments", backend=Recorded({"state": "ok", "records": []}))
    assert read["status"] == "EMPTY" and read["budget"]["queries_used_here"] == 1       # the check passed: the read goes through
    with pytest.raises(S.AcquisitionRefused) as exc:                                  # attempts stop at three times the budget
        S.acquire(principal_id=None, action=step, operation="listings", target="rain cover", site="cjdropshipping.com",
                  search_intent_id="si_comments", backend=wall)
    assert exc.value.code == "ATTEMPTS_SPENT"


def test_listings_are_one_source_each_and_search_results_are_never_sources():
    listing = O.OpenCLIBackend._listing("https://www.alibaba.com/product-detail/x_1.html", "Rain cover",
                                        "Rain cover\n$3.20 - $4.10\nMin. order: 500 pieces\nNingbo Example Trading Co., Ltd.\n5 yrs")
    out = S.acquire(principal_id=None, action=_action(tag=3), operation="listings", target="rain cover", site="alibaba.com",
                    search_intent_id="si_comments", backend=Recorded({"state": "ok", "records": [listing, dict(listing, url="https://www.alibaba.com/product-detail/x_2.html", ref="x2")]}))
    assert [s["source_class"] for s in out["sources"]] == ["supplier_listing"] * 2 and all(s["published_at_if_known"] is None for s in out["sources"])
    assert "source_date" not in out["items"][0]                        # a listing is observed as it is when read: it keeps its source
    assert out["items"][0]["listing"]["price_as_listed"] == "$3.20 - $4.10" and out["items"][0]["date_precision"] == "none"
    found = S.acquire(principal_id=None, action=_action(tag=4), operation="web_search", target="rain cover lens fog",
                      search_intent_id="si_comments", backend=Recorded({"state": "ok", "records": [{"url": "https://example.org/a", "title": "A", "snippet": "s"}]}))
    assert found["sources"] == [] and found["items"][0]["kind"] == "result" and any("leads, not evidence" in x for x in found["limitations"])


@pytest.mark.parametrize("card,expected", [
    (" Silicone Camera Case Cover5% off $2,000$2.06-3.49Min. order: 200 piecesShenzhen Wjm Silicone & Plastic Electronic Co., Ltd.20 yrsCN5.0/5.0(4)",
     ("$2.06-3.49", "200 pieces", "Shenzhen Wjm Silicone & Plastic Electronic Co., Ltd.")),
    ("New ABS Material\nDelivery by Nov 04\n$0.18\nMin. order: 10 pieces\nGuangzhou Jucheng Automotive Supplies Co., Ltd\n1 yr\nCN",
     ("$0.18", "10 pieces", "Guangzhou Jucheng Automotive Supplies Co., Ltd")),
    ("List Added Products Backpack Rain Cover $0.64-3.71 QTY", ("$0.64-3.71", None, None))])
def test_listing_cards_parse_as_the_page_shows_them(card, expected):
    got = O.OpenCLIBackend._listing("https://x/1", "List\nAdded Products\nBackpack Rain Cover\nLists: 111\n$0.64-3.71\nQTY", card)["listing"]
    assert (got["price_as_listed"], got["minimum_order_as_listed"], got["supplier"]) == expected
    assert got["title"] == "Backpack Rain Cover"                                     # page labels are not the title


@pytest.mark.parametrize("page,expected", [
    ({"url": "https://frontend.cjdropshipping.com/egg/cj/validation.html?rd=x", "title": "Human verification", "text": "We would like to make sure you are not a robot."}, "human_check"),
    ({"url": "https://www.instagram.com/accounts/login/?next=%2Fp%2Fx%2F", "title": "Login", "text": ""}, "sign_in"),
    ({"url": VIDEO, "title": "(3)TikTok - Make Your Day", "text": "it's still raining"}, None),
    ({"url": VIDEO, "title": "TikTok - Make Your Day", "text": "it's still raining", "login_prompt": True}, "sign_in")])
def test_walls_are_recognised_from_the_page_state(page, expected):
    assert O.blocked(page) == expected


def test_the_backend_calls_only_read_commands():
    tree = ast.parse((ROOT / "shared/polymath_shared/acquisition/opencli.py").read_text())
    verbs, site_cmds = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant) and isinstance(node.elts[0].value, str):
            first = node.elts[0].value
            consts = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if first == "browser":
                verbs.update(c for c in consts[1:] if c in ("open", "eval", "close", "click", "type", "fill", "upload", "keys", "select",
                                                           "check", "drag", "dblclick", "dialog"))
            elif first not in ("doctor",) and len(consts) >= 2 and re.fullmatch(r"[a-z0-9-]+", first):
                site_cmds.add((first, consts[1]))
    assert verbs == {"open", "eval", "close"}, verbs
    assert site_cmds == {("duckduckgo", "search"), ("amazon", "search")}, site_cmds


def _backend_with_tab(page, data):
    b = O.OpenCLIBackend()
    b._in_tab = lambda url, settle, js: (page, data, "2026-09-25T21:00:00Z")
    return b


def test_youtube_is_read_whole_with_the_video_date_and_says_when_more_exist():
    yt = S.resolve("comments", "https://www.youtube.com/watch?v=o1t-Km5cfo0")
    long_text = "the cover blocks the eyepiece " * 20                           # 600 characters: never cut at 300
    data = {"status": 200, "parsed": True, "items": 21, "published": "2017-08-19T01:08:16-07:00", "has_more": True,
            "comments": [{"id": "Ugx1", "text": long_text, "age": "2 years ago", "author": "@viewer", "likes": "15"}]}
    raw = _backend_with_tab({"url": yt.url, "title": "video", "text": "", "login_prompt": False}, data)._youtube_comments(yt, 50)
    assert raw["complete"] is False and raw["page_published_at"] == "2017-08-19T08:08:16Z" and raw["records"][0]["text"] == long_text
    out = S.shape(yt, raw, action=_action(tag="yt"), search_intent_id="si_comments", retrieved_at=raw["retrieved_at"], used=1, cap=3, limit=50)
    item, src = out["items"][0], out["sources"][0]
    assert out["status"] == "PARTIAL" and item["source_date"] == "page" and src["published_at_if_known"] == "2017-08-19T08:08:16Z"
    assert len(item["excerpt"]) == len(long_text.strip()) and item["date_shown"] == "2 years ago"


INSTAGRAM_SIGNED_IN = {"blocks": [
    {"datetime": "2025-11-15T18:26:42.000Z", "shown": "44w", "block": "georges.camera\n \n44w\nWe ain't electronic engineers, but water is really bad for electronics."},
    {"datetime": "2025-11-17T08:08:38.000Z", "shown": "44w", "block": "myownbeat\n \n44w\nAlso love the 3rd one!\n1 like\nReply"},
    {"datetime": "2025-11-15T18:26:40.000Z", "shown": "November 15, 2025", "block": "233\n8\n2\nNovember 15, 2025"},
    {"datetime": "2025-11-17T08:08:38.000Z", "shown": "44w", "block": "myownbeat\n \n44w\nAlso love the 3rd one!\n1 like\nReply"}]}
INSTAGRAM_SIGNED_OUT = {"blocks": [
    {"datetime": "2025-11-15T18:26:40.000Z", "shown": "November 15, 2025",
     "block": "Log In\nSign Up\nNever miss a post from georges.camera\nSign up for Instagram to stay in the loop.\nSign up\nLog in\ngeorges.camera"}]}


def test_instagram_post_date_row_is_the_page_date_and_a_signed_out_view_is_a_sign_in():
    ig = S.resolve("comments", "https://www.instagram.com/p/DRFkr7rkvUJ/")
    raw = _backend_with_tab({"url": ig.url, "title": "Instagram", "text": "georges.camera"}, INSTAGRAM_SIGNED_IN)._instagram_comments(ig, 20)
    assert [(r["kind"], r["author"]) for r in raw["records"]] == [("caption", "georges.camera"), ("comment", "myownbeat"), ("comment", "myownbeat")]
    assert raw["page_published_at"] == "2025-11-15T18:26:40Z"                  # the post's own date, never a comment
    shaped = S.shape(ig, raw, action=_action(tag="ig"), search_intent_id="si_comments", retrieved_at=raw["retrieved_at"], used=1, cap=3, limit=20)
    assert [i["excerpt"] for i in shaped["items"]].count("Also love the 3rd one!") == 1   # the post view renders it twice: one item
    out = _backend_with_tab({"url": ig.url, "title": "Instagram", "text": "Log In Sign Up Never miss a post"}, INSTAGRAM_SIGNED_OUT)
    assert out._instagram_comments(ig, 20)["state"] == "sign_in"


def test_a_request_relayed_by_a_proxy_is_refused(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from orchestrator.api import acquisition as R
    monkeypatch.setattr(R, "tx", lambda: contextlib.nullcontext(None))
    monkeypatch.setattr(R.service, "assert_owner", lambda conn, run_id, principal: None)
    monkeypatch.setattr(R, "open_harness_action", lambda conn, run_id: _action(tag="proxy"))
    monkeypatch.setattr(S, "default_backend", lambda: Recorded({"state": "ok", "records": []}))
    app = FastAPI()
    app.include_router(R.router)
    client = TestClient(app, base_url="http://127.0.0.1:7200")                 # how the MCP servers call it (B-28)
    for headers in ({"X-Forwarded-For": "203.0.113.9"}, {"X-Forwarded-Host": "rag.example"}, {"Forwarded": "for=203.0.113.9"}):
        r = client.post("/adapter/adr_x/acquire", json={"operation": "catalog"}, headers=headers)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "PROXIED_CALLER"
    assert client.post("/adapter/adr_x/acquire", json={"operation": "catalog"}).status_code == 200      # the MCP servers call directly


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_both_servers_publish_research_acquire_identically_and_only_the_owner_can_call_it():
    a = {t.name: t for t in asyncio.run(_load("acq_mcp_a", "orchestrator/orchestrator/mcp_server.py").mcp.list_tools())}
    b = {t.name: t for t in asyncio.run(_load("acq_mcp_b", "mcp_server/polymath_mcp.py").server.list_tools())}
    ta, tb = a["research_acquire"], b["research_acquire"]
    assert ta.input_schema.get("properties") == tb.input_schema.get("properties")
    assert sorted(ta.input_schema.get("required") or []) == sorted(tb.input_schema.get("required") or []) == ["operation", "run_id"]
    assert " ".join(ta.description.split()) == " ".join(tb.description.split())
    from orchestrator import mcp_principals as P
    assert "research_acquire" not in P.TOOL_POLICY                      # default deny: owner-only by construction


def test_the_route_answers_with_the_policy(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from polymath_shared import principal_context
    from orchestrator.api import acquisition as R
    monkeypatch.setattr(R, "tx", lambda: contextlib.nullcontext(None))
    monkeypatch.setattr(R.service, "assert_owner", lambda conn, run_id, principal: None)
    open_step = {"now": None}
    monkeypatch.setattr(R, "open_harness_action", lambda conn, run_id: open_step["now"])
    monkeypatch.setattr(S, "default_backend", lambda: Recorded({"state": "ok", "page_url": VIDEO, "records": [
        {"kind": "comment", "ref": "c1", "text": "fogged up", "published_at": "2026-06-13T16:10:23Z", "precision": "exact"}]}))
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.include_router(R.router)
    client = TestClient(app, base_url="http://127.0.0.1:7200")                 # how the MCP servers call it (B-28)
    body = {"operation": "comments", "target": VIDEO, "search_intent_id": "si_comments"}
    r = client.post("/adapter/adr_x/acquire", json=body)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NO_OPEN_RESEARCH_STEP"
    open_step["now"] = _action(tag="route")
    r = client.post("/adapter/adr_x/acquire", json=body, headers={principal_context.HEADER: "prn_fred"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "OWNER_ONLY"
    r = client.post("/adapter/adr_x/acquire", json=body)
    assert r.status_code == 200 and r.json()["status"] == "OK" and r.json()["items"][0]["published_at"] == "2026-06-13T16:10:23Z"
    r = client.post("/adapter/adr_x/acquire", json={**body, "target": "https://vm.tiktok.com/ZMabcdefg/"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "TARGET_NOT_PERMITTED"


# ----------------------------------------------------------------------------- TRAIL-EXT-BUGHUNT-V1: B-17, B-18, B-28 (2026-09-26)
READ_AT = "2026-09-26T10:00:00Z"
THREAD = "https://www.reddit.com/r/AskPhotography/comments/abc123/"
THREAD_JSON = {"status": 200, "post": {"title": "Endless captcha loop on my camera app", "text": "it asks me to prove I am not a robot",
                                        "created": 1758000000, "author": "op", "comments": 1},
               "comments": [{"id": "c1", "text": "the app makes you Sign in to continue before you can fly", "created": 1758000100,
                             "author": "someone", "score": 3}]}
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed (the browser host runs OpenCLI, a Node program)")


def _browser(page, answer):
    """The REAL `_in_tab` over a stubbed browser: `_page` gives the recorded page state, the reader script answers `answer`."""
    b = O.OpenCLIBackend(binary="/nonexistent/opencli")
    calls = []
    b._open = lambda session, url, settle: calls.append("open")
    b._page = lambda session: dict(page)
    b._eval = lambda session, js: calls.append("reader") or answer
    b._close = lambda session: calls.append("close")
    return b, calls


#: readable pages whose title, opening text, slug, community name or search word only MENTIONS a wall (B-17)
MENTIONS = [
    {"url": THREAD, "title": "Why does my camera app keep showing a captcha? : r/AskPhotography", "text": "r/AskPhotography", "login_prompt": False},
    {"url": THREAD, "title": "r/AskPhotography", "text": "Skip to main content r/AskPhotography Endless human verification: I am not a robot",
     "login_prompt": False},
    {"url": "https://www.reddit.com/r/SideProject/comments/abc123/validation_would_you_buy_this/", "title": "r/SideProject", "text": "x"},
    {"url": "https://www.reddit.com/r/SideProject/comments/abc123/captcha/", "title": "r/SideProject", "text": "x"},
    {"url": "https://www.reddit.com/r/loginhelp/comments/abc123/locked_out_of_my_account/", "title": "r/loginhelp", "text": "x"},
    {"url": "https://cjdropshipping.com/search/validation.html", "title": "validation - search", "text": "x"}]


@pytest.mark.parametrize("page", MENTIONS)
def test_a_page_that_only_mentions_a_wall_is_not_a_wall(page):
    assert O.blocked(page) is None


@pytest.mark.parametrize("page", MENTIONS[:3])
def test_the_reader_runs_on_such_a_page_and_its_read_is_kept(page):
    b, calls = _browser(page, THREAD_JSON)
    raw = b._reddit_comments(S.resolve("comments", THREAD), 20)
    assert calls == ["open", "reader", "close"] and raw["state"] == "ok"
    out = S.acquire(principal_id=None, action=_action(tag=["mentions", page["url"], page["title"]]), operation="comments", target=THREAD,
                    search_intent_id="si_comments", backend=Recorded(raw))
    assert out["status"] == "OK" and out["human_action"] is None and len(out["items"]) == 2 and "refunded" not in out["budget"]


@pytest.mark.parametrize("page,why", [
    ({"url": "https://frontend.cjdropshipping.com/egg/cj/validation.html?rd=x", "title": "Human verification", "text": ""}, "human_check"),
    ({"url": "https://www.tiktok.com/login?redirect_url=x", "title": "Log in", "text": ""}, "sign_in"),
    ({"url": "https://www.instagram.com/accounts/login/?next=%2Fp%2Fx%2F", "title": "Login", "text": ""}, "sign_in"),
    ({"url": VIDEO, "title": "TikTok - Make Your Day", "text": "it's still raining", "login_prompt": True}, "sign_in")])
def test_a_wall_route_or_a_sign_in_prompt_still_stops_the_reader_before_it_runs(page, why):
    b, calls = _browser(page, THREAD_JSON)
    assert b._reddit_comments(S.resolve("comments", THREAD), 20)["state"] == why and calls == ["open", "close"]


def test_a_wall_word_still_names_the_wall_when_the_page_gave_nothing():
    """A human check that keeps the page's own URL shows its words, and the reader finds nothing on it."""
    page = {"url": "https://www.alibaba.com/trade/search?SearchText=rain+cover", "title": "Captcha Interception", "text": "slide to verify"}
    b, calls = _browser(page, [])
    raw = b._alibaba_listings(S.resolve("listings", "rain cover", "alibaba.com"), 20)
    assert raw["state"] == "human_check" and calls == ["open", "reader", "close"]
    b, _ = _browser(dict(page, url=THREAD, title="Captcha"), {"status": 403})
    assert b._reddit_comments(S.resolve("comments", THREAD), 20)["state"] == "human_check"
    b, _ = _browser(dict(page, title="Rain covers", text="no results"), [])
    assert b._alibaba_listings(S.resolve("listings", "rain cover", "alibaba.com"), 20)["state"] == "unavailable"


PROMPT_LINES = [("Log in to TikTok\nUse QR code\nUse phone / email / username", True),          # the modal's own heading
                ("For You\nSign in to continue\nNot now", True),
                ("the app makes you Sign in to continue before you can fly", False),        # a comment that mentions it
                ("honestly, the 'log in to continue' popups are the worst part", False)]


@pytest.mark.parametrize("text,prompt", PROMPT_LINES)
def test_a_sign_in_prompt_is_a_whole_line_of_the_page_never_words_inside_a_comment(text, prompt):
    assert bool(re.search(O.LOGIN_PROMPT, text, re.IGNORECASE | re.MULTILINE)) is prompt


def _node(stub, *args):
    got = subprocess.run([NODE, "-e", stub, *args], capture_output=True, text=True, timeout=30, check=False)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def _page_js():
    b = O.OpenCLIBackend(binary="/nonexistent/opencli")
    seen = {}
    b._eval = lambda session, js: seen.setdefault("js", js)
    b._page("pm-acq-test")
    return seen["js"]


PAGE_STUB = r"""
const [js, text] = [process.argv[1], process.argv[2]];
globalThis.location = {href: 'https://www.tiktok.com/@creator/video/7400000000000000001'};
globalThis.document = {title: 'TikTok', body: {innerText: text}};
process.stdout.write(String(eval(js)));
"""


@needs_node
@pytest.mark.parametrize("text,prompt", PROMPT_LINES)
def test_the_page_script_flags_a_sign_in_prompt_only_as_a_whole_line(text, prompt):
    assert _node(PAGE_STUB, _page_js(), text)["login_prompt"] is prompt


#: the page scripts run in node with the browser's globals stubbed; `fetch` answers HTTP 200 with the given body (B-18)
READER_STUB = r"""
const [js, mode, body] = [process.argv[1], process.argv[2], process.argv[3]];
globalThis.window = globalThis;
globalThis.location = {pathname: '/x', href: 'https://x/'};
globalThis.fetch = async () => ({status: 200, json: async () => JSON.parse(body)});
if (mode === 'tiktok') {
  const u = {__DEFAULT_SCOPE__: {'webapp.video-detail': {itemInfo: {itemStruct: {desc: 'rain again on my lens', createTime: 1718047586}}}}};
  globalThis.document = {getElementById: () => ({textContent: JSON.stringify(u)}), querySelector: () => null};
} else {
  globalThis.ytInitialData = {contents: {a: {itemSectionRenderer: {sectionIdentifier: 'comment-item-section',
      contents: [{continuationItemRenderer: {continuationEndpoint: {continuationCommand: {token: 'TOKEN123'}}}}]}}}};
  globalThis.ytcfg = {get: () => ({client: {}})};
  globalThis.document = {getElementById: () => null, querySelector: () => ({content: '2024-01-01T00:00:00-08:00'})};
}
Promise.resolve(eval(js)).then(r => process.stdout.write(r));
"""
YOUTUBE = "https://www.youtube.com/watch?v=o1t-Km5cfo0"


def _reader_js(reader, target):
    b = O.OpenCLIBackend(binary="/nonexistent/opencli")
    seen = {}

    def in_tab(url, settle, js):
        seen["js"] = js
        return {"url": url, "title": "t", "text": ""}, None, READ_AT
    b._in_tab = in_tab
    getattr(b, reader)(S.resolve("comments", target), 20)
    return seen["js"]


def _acquired(reader, target, data, tag):
    t = S.resolve("comments", target)
    raw = getattr(_backend_with_tab({"url": t.url, "title": "t", "text": ""}, data), reader)(t, 20)
    return S.acquire(principal_id=None, action=_action(tag=tag), operation="comments", target=target, search_intent_id="si_comments",
                     backend=Recorded(raw))


@pytest.mark.parametrize("reader,target,data", [
    ("_tiktok_comments", VIDEO, {"status": 200, "parsed": False, "code": None, "total": None, "has_more": None, "comments": [],
                                 "video": {"desc": "rain again on my lens", "created": 1718047586}}),
    ("_youtube_comments", YOUTUBE, {"status": 200, "parsed": False, "published": "2024-01-01T00:00:00-08:00", "comments": [],
                                    "has_more": False, "items": 0}),
    ("_youtube_comments", YOUTUBE, {"status": 200, "parsed": True, "published": "2024-01-01T00:00:00-08:00", "comments": [],
                                    "has_more": False, "items": 0}),
    ("_youtube_comments", YOUTUBE, {"status": 200, "parsed": True, "published": "2024-01-01T00:00:00-08:00", "comments": [],
                                    "has_more": False, "items": 3, "threads": 2})])                  # threads whose text never came
def test_a_comment_list_that_did_not_answer_is_unavailable_never_a_read(reader, target, data):
    out = _acquired(reader, target, data, ["no-answer", reader, data["parsed"], data.get("threads")])
    assert out["status"] == "UNAVAILABLE" and out["items"] == [] and out["completeness"]["complete"] is None
    assert out["budget"]["refunded"] is True and any("comment list did not answer" in x for x in out["limitations"])


def test_a_parsed_empty_comment_list_is_still_a_read():
    tt = _acquired("_tiktok_comments", VIDEO, {"status": 200, "parsed": True, "code": 0, "total": 0, "has_more": 0, "comments": [],
                                                "video": {"desc": "rain again on my lens", "created": 1718047586}}, "tt-empty")
    assert tt["status"] == "OK" and [i["kind"] for i in tt["items"]] == ["caption"] and tt["completeness"]["complete"] is True
    yt = _acquired("_youtube_comments", YOUTUBE, {"status": 200, "parsed": True, "published": "2024-01-01T00:00:00-08:00", "comments": [],
                                                  "has_more": False, "items": 1}, "yt-empty")
    assert yt["status"] == "EMPTY" and yt["completeness"]["complete"] is True and "refunded" not in yt["budget"]


@needs_node
def test_the_page_scripts_say_whether_the_comment_list_answered():
    tt_js, yt_js = _reader_js("_tiktok_comments", VIDEO), _reader_js("_youtube_comments", YOUTUBE)
    for js, mode in ((tt_js, "tiktok"), (yt_js, "youtube")):
        data = _node(READER_STUB, js, mode, "")                                      # HTTP 200 with a body that does not parse
        assert data["status"] == 200 and data["parsed"] is False
        out = _acquired("_tiktok_comments" if mode == "tiktok" else "_youtube_comments", VIDEO if mode == "tiktok" else YOUTUBE, data,
                        ["node", mode])
        assert out["status"] == "UNAVAILABLE" and out["budget"]["refunded"] is True
    tt = _node(READER_STUB, tt_js, "tiktok", json.dumps({"status_code": 0, "comments": [], "total": 0, "has_more": 0}))
    assert tt["parsed"] is True and tt["code"] == 0
    header_only = {"onResponseReceivedEndpoints": [{"reloadContinuationItemsCommand": {"continuationItems": [{"commentsHeaderRenderer": {}}]}}]}
    yt = _node(READER_STUB, yt_js, "youtube", json.dumps(header_only))
    assert yt["parsed"] is True and yt["items"] == 1 and yt["comments"] == [] and yt["has_more"] is False
    assert _acquired("_youtube_comments", YOUTUBE, yt, "node-yt-empty")["status"] == "EMPTY"
    assert _node(READER_STUB, yt_js, "youtube", json.dumps({"responseContext": {}}))["items"] == 0
    unread = {"onResponseReceivedEndpoints": header_only["onResponseReceivedEndpoints"] + [
        {"reloadContinuationItemsCommand": {"continuationItems": [{"commentThreadRenderer": {}}, {"commentThreadRenderer": {}}]}}]}
    yt = _node(READER_STUB, yt_js, "youtube", json.dumps(unread))                  # threads listed, their text nowhere to be read
    assert yt["threads"] == 2 and yt["comments"] == [] and _acquired("_youtube_comments", YOUTUBE, yt, "node-yt-unread")["status"] == "UNAVAILABLE"


def _route_app(monkeypatch, reads, tag):
    """The acquisition route behind the orchestrator's own middleware order (main.py: principal context, web boundary, CORS)."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from orchestrator.api import acquisition as R
    from orchestrator.web_boundary import WebBoundaryMiddleware
    from polymath_shared import principal_context
    monkeypatch.setattr(R, "tx", lambda: contextlib.nullcontext(None))
    monkeypatch.setattr(R.service, "assert_owner", lambda conn, run_id, principal: None)
    monkeypatch.setattr(R, "open_harness_action", lambda conn, run_id: _action(tag=tag))
    backend = Recorded({"state": "ok", "records": []})
    backend.reads = reads
    monkeypatch.setattr(S, "default_backend", lambda: backend)
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.add_middleware(WebBoundaryMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(R.router)
    return app


@pytest.mark.parametrize("host,status", [("rebind.attacker.example:7200", 403), ("192.168.1.20:7200", 403), ("127.0.0.1:7200", 200),
                                         ("localhost:7200", 200), ("[::1]:7200", 200)])
def test_only_a_request_naming_a_loopback_host_reaches_the_host_browser(monkeypatch, host, status):
    """A page that re-binds its own name to 127.0.0.1 (DNS rebinding) reaches this listener directly, without proxy headers, but it
    still sends ITS name as the Host: only the names the MCP servers call (127.0.0.1 / localhost) reach the owner's browser."""
    from fastapi.testclient import TestClient
    reads = []
    client = TestClient(_route_app(monkeypatch, reads, ["rebind", host]))
    body = {"operation": "comments", "target": VIDEO, "search_intent_id": "si_comments"}
    r = client.post("/adapter/adr_x/acquire", json=body, headers={"Host": host, "Origin": f"http://{host}"})    # as the browser sends it
    assert r.status_code == status, r.text
    if status == 403:
        assert r.json()["detail"]["code"] == "NON_LOOPBACK_HOST" and reads == []
    else:
        assert r.json()["status"] == "EMPTY" and len(reads) == 1
