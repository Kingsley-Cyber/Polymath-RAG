"""SUPPLIER-APIS (the owner's decision of 2026-09-27): a CHALLENGE-PAGE DETECTOR, never a solver.
`challenge.looks_like_challenge(text)` names a verification wall (a slider, "verify you are human", "unusual traffic", a bot block, a
CJK security check) and says None for content that only MENTIONS one (B-17's whole-line lesson): a wall line must stand as a whole
segment, the wall's lines must make up the text, one line content also uses is not enough, and "Access denied" needs a bot notice.
It is used in two places:
  (a) the acquisition read paths: a page that is a wall is HUMAN_ACTION_REQUIRED once the reader got nothing, and a wall's text is
      never a listing or a search row;
  (b) the receipt check: an observation that quotes a wall is refused, CHALLENGE_PAGE_AS_EVIDENCE, naming the observation and source.
Recorded page texts only: no browser, no network, no database.
"""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.acquisition import challenge as CH
from polymath_shared.acquisition import opencli as O
from polymath_shared.acquisition import service as S
from polymath_shared.adapter import transitions as T

#: interstitials as their pages show them (title and opening text, the way `opencli._page` reads them)
WALLS = {
    "a slider after unusual traffic": "Captcha Interception\nSorry, we have detected unusual traffic from your network.\nPlease slide to verify",
    "a CJK slider": "亲，请拖动下方滑块完成验证\n"
                    "请按住滑块，拖动到最右边",
    "a CJK security check": "安全验证\n请完成下列验证后继续",
    "a verification redirect": "Human verification\nWe would like to make sure you are not a robot.",
    "an interstitial that checks the browser": "Just a moment...\nwww.example.com\nVerifying you are human. This may take a few seconds.\n"
                                               "www.example.com needs to review the security of your connection before proceeding.\n"
                                               "Ray ID: 8a1b2c3d4e5f6a7b\nPerformance & security by Example Edge",
    "an older browser check": "Just a moment...\nChecking your browser before accessing example.com.\nThis process is automatic. Your browser "
                              "will redirect to your requested content shortly.\nPlease allow up to 5 seconds…\nDDoS protection by Example Edge",
    "a block page": "Attention Required!\nSorry, you have been blocked\nYou are unable to access example.com\nWhy have I been blocked?\n"
                    "This website is using a security service to protect itself from online attacks.",
    "a search engine's traffic check": "Our systems have detected unusual traffic from your computer network. This page checks to see if it's "
                                       "really you sending the requests, and not a robot.",
    "access denied with a reference": "Access Denied\nYou don't have permission to access \"http://www.example.com/\" on this server.\n"
                                      "Reference #18.5f2c1402.1695000000.1a2b3c",
    "access denied with a bot notice": "Access denied\nWe detected automated traffic from your network.",
    "press and hold": "Press & Hold to confirm you are a human (and not a bot).\nReference ID 1a2b3c4d-5e6f",
    "type the characters": "Enter the characters you see below\nSorry, we just need to make sure you're not a robot. For best results, "
                           "please make sure your browser is accepting cookies.",
    "an interruption page": "Pardon Our Interruption\nAs you were browsing something about your browser made us think you were a bot.",
    "a checkbox widget": "I'm not a robot\nreCAPTCHA\nPrivacy - Terms",
    "one quoted line": "Sorry, we have detected unusual traffic from your network. Please slide to verify.",
}
#: content that MENTIONS a wall (B-17's pages among them): never a wall
CONTENT = {
    "a thread title": "Why does my camera app keep showing a captcha? : r/AskPhotography\nr/AskPhotography",
    "a thread's opening text": "Skip to main content r/AskPhotography Endless human verification: I am not a robot",
    "a post titled Captcha": "Captcha\nit asks me to prove I am not a robot",
    "a comment": "honestly, the 'verify you are human' popups are the worst part of this site",
    "a lyric": "slide to the left, slide to the right",
    "a phone": "slide to unlock",
    "a plain 403": "Access Denied",
    "a listing": "Security Check Mirror · price as listed: US$3.20 · minimum order as listed: 100 pieces · supplier: unresolved",
    "a page with a heading among content": "Security check\n" + "\n".join(f"Great cover number {i}, it ships fast and works in the rain." for i in range(8)),
    "a joke": "I'm not a robot",
    "a pause": "Just a moment...",
    "a CJK review": "这个相机雨罩非常好用，我在下雨天拍摄时一直用它"
                    "，完全不用担心安全验证之类的问题而且价格也"
                    "很便宜推荐大家购买这款雨罩产品",
    "nothing": "",
}


def test_the_code_under_test_is_this_checkout():
    for mod in (CH, O, S, T):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


@pytest.mark.parametrize("name", sorted(WALLS))
def test_a_verification_wall_is_named(name):
    assert CH.looks_like_challenge(WALLS[name]), name


@pytest.mark.parametrize("name", sorted(CONTENT))
def test_content_that_mentions_a_check_is_content(name):
    assert CH.looks_like_challenge(CONTENT[name]) is None, name


def test_the_detector_only_reads_it_never_acts():
    src = (ROOT / "shared/polymath_shared/acquisition/challenge.py").read_text()
    assert not any(f"import {m}" in src for m in ("httpx", "subprocess", "requests", "socket", "time", "os"))     # pure: no I/O, no waiting


# ─────────────────────────────────────────────────────────── (a) the read paths
@pytest.mark.parametrize("title,text", [
    ("Just a moment...", "www.example.com\nVerifying you are human. This may take a few seconds.\nRay ID: 8a1b2c3d4e5f6a7b"),
    ("Access Denied", "You don't have permission to access \"http://www.example.com/\" on this server.\nReference #18.5f2c1402"),
    ("安全验证", "请按住滑块，拖动到最右边")])
def test_an_interstitial_the_reader_got_nothing_from_is_a_human_check(title, text):
    """None of these holds the three wall words the reader knew before (human verification, not a robot, captcha)."""
    page = {"url": "https://www.example.com/search?q=rain+cover", "title": title, "text": text}
    assert not any(w in f"{title} {text}".lower() for w in O.WALL_WORDS)
    assert O.blocked(page) is None                                     # before a read: only routes and prompts count (B-17)
    assert O.blocked(page, read_nothing=True) == "human_check"
    assert O._nothing(page) == "human_check"


def test_a_page_that_mentions_a_check_and_gave_nothing_stays_unavailable():
    page = {"url": "https://www.example.com/search?q=rain+cover", "title": "Rain covers", "text": "no results for rain cover"}
    assert O._nothing(page) == "unavailable"


ACTION = {"action_id": "hact_" + "f" * 24, "run_id": "adr_" + "e" * 32, "budget": {"max_queries": 5}, "disallowed_source_roles": [],
          "search_intents": [{"intent_id": "si_supply"}]}
WALL_LISTING = {"kind": "listing", "ref": "x1", "url": "https://www.example.com/product-detail/x_12345678.html", "text": "Captcha Interception",
                "published_at": None, "precision": "none", "listing": {"title": "Captcha Interception", "price_as_listed": None,
                                                                        "card": "Sorry, we have detected unusual traffic from your network. Please slide to verify"}}
REAL_LISTING = O.OpenCLIBackend._listing("https://www.example.com/product-detail/y_12345679.html", "Rain cover",
                                         "Rain cover\n$3.20 - $4.10\nMin. order: 500 pieces\nNingbo Example Trading Co., Ltd.")


def _shape(operation, target, site, records, tag):
    t = S.resolve(operation, target, site)
    return S.shape(t, {"state": "ok", "records": records}, action={**ACTION, "action_id": ACTION["action_id"][:-4] + tag}, search_intent_id="si_supply",
                   retrieved_at="2026-09-27T10:00:00Z", used=1, cap=5, limit=20)


def test_a_walls_text_is_never_a_listing_and_a_read_of_only_walls_is_a_human_check():
    mixed = _shape("listings", "rain cover", "alibaba.com", [WALL_LISTING, REAL_LISTING], "0001")
    assert [i["listing"]["title"] for i in mixed["items"]] == ["Rain cover"] and mixed["status"] == "OK"
    assert any(x.startswith("1 row(s) held a verification page's text") for x in mixed["limitations"])
    walls = _shape("listings", "rain cover", "alibaba.com", [WALL_LISTING], "0002")
    assert walls["status"] == "HUMAN_ACTION_REQUIRED" and walls["items"] == [] and walls["human_action"]["site"] == "alibaba.com"
    leads = _shape("web_search", "rain cover", None, [{"url": "https://example.org/a", "title": "Just a moment...",
                                                       "snippet": "Verifying you are human. This may take a few seconds."},
                                                      {"url": "https://example.org/b", "title": "Rain covers compared", "snippet": "we tested six"}], "0003")
    assert [i["url"] for i in leads["items"]] == ["https://example.org/b"] and leads["status"] == "OK"


def test_comments_and_ordinary_reads_are_untouched():
    """Comment readers parse the sites' own comment lists (JSON): a wall never arrives as a comment, and a comment that jokes about
    one is kept (the filter covers listing and search rows only)."""
    t = S.resolve("comments", "https://www.tiktok.com/@creator/video/7400000000000000001")
    raw = {"state": "ok", "records": [{"kind": "comment", "ref": "c1", "text": "I'm not a robot\nreCAPTCHA", "published_at": "2026-06-13T16:10:23Z",
                                       "precision": "exact"}]}
    out = S.shape(t, raw, action=ACTION, search_intent_id="si_supply", retrieved_at="2026-09-27T10:00:00Z", used=1, cap=5, limit=20)
    assert out["status"] == "OK" and len(out["items"]) == 1 and not any("verification page" in x for x in out["limitations"])


# ─────────────────────────────────────────────────────────── (b) the receipt check
EXAMPLE = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
STEP = {"run_id": EXAMPLE["run_id"], "harness_action": {"action_id": EXAMPLE["action_id"]}}


def test_the_example_receipt_is_still_accepted():
    assert T.validate_receipt(STEP, EXAMPLE) == []


@pytest.mark.parametrize("name", ["one quoted line", "a verification redirect", "a CJK slider"])
def test_an_observation_that_quotes_a_wall_is_refused_by_name(name):
    receipt = copy.deepcopy(EXAMPLE)
    receipt["observations"][1]["paraphrase_or_excerpt"] = WALLS[name][:600]
    errors = T.validate_receipt(STEP, receipt)
    (err,) = [e for e in errors if e.startswith("CHALLENGE_PAGE_AS_EVIDENCE")]
    obs = receipt["observations"][1]
    assert f"observation {obs['observation_id']} (source {obs['source_id']})" in err and "not evidence" in err
    assert len(errors) == 1                                             # nothing else about the receipt changed


def test_an_observation_that_mentions_a_check_is_accepted():
    receipt = copy.deepcopy(EXAMPLE)
    receipt["observations"][0]["paraphrase_or_excerpt"] = "the shop's 'verify you are human' page loops forever, so I gave up and bought a bag"
    assert T.validate_receipt(STEP, receipt) == []
