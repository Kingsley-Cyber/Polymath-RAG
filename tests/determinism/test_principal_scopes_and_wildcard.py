"""PRODUCT-SEARCH-E2E friend-journey items in the principal policy (orchestrator/mcp_principals.py), the owner's decisions of 2026-11-01:
  * F2: a principal made by script gets the SAME scopes as a web friend ("everything" but admin: upload into its writable
    libraries, its history, cancelling its runs, deep research): PROFILES["friend"] = FRIEND_SCOPES;
  * F9: a friend reaches polymath_deep_research (knowledge.research is a friend scope) — and an EXISTING web friend, whose stored
    scopes predate it, gets it too: a record tagged "profile": "friend" holds the profile's current scopes when it is read (no
    registry rewrite); an untagged record keeps exactly what it stores;
  * F3: corpus_ids ["*"] = every library that exists at request time, never another person's private library (the shared rule
    query_scope.grant_allows), in the gate's corpus check and in list filtering; never for writing.
The whole chain where it matters: HTTP -> Server A's REAL gate -> the MCP tool -> the orchestrator's REAL adapter API, over the
in-memory store (test_mcp_principals_gate._build). No network, no database."""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(ROOT / "tests" / "determinism"))

import pytest
import test_mcp_principals_gate as GATE
from polymath_shared import query_scope as QS
from starlette.testclient import TestClient

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W


def test_the_code_under_test_is_this_checkout():
    for mod in (P, W, QS):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── F2 / F9: the friend scopes
def test_script_friends_and_web_friends_get_the_same_scopes_deep_research_included():
    assert P.PROFILES["friend"] == P.FRIEND_SCOPES
    assert set(P.FRIEND_SCOPES) == set(P.SCOPES) - {P.ADMIN}                  # "everything" but admin
    assert {P.UPLOAD_TEXT, P.HISTORY_READ, P.ADAPTER_CANCEL, P.KNOWLEDGE_RESEARCH} <= set(P.FRIEND_SCOPES)
    assert set(W.FRIEND_SCOPES) <= set(P.FRIEND_SCOPES)
    web = P.principal_from_record({"principal_id": "prn_web", "profile": "friend", "scopes": list(W.FRIEND_SCOPES)})
    script = P.principal_from_record({"principal_id": "prn_cli", "scopes": list(P.PROFILES["friend"])})
    assert web.scopes == script.scopes == frozenset(P.FRIEND_SCOPES)


def test_an_existing_friend_gains_the_profiles_scopes_when_read_and_an_untagged_record_does_not():
    old = sorted(P.FRIEND_PROFILE)                                          # a friend stored before deep research was a friend scope
    tagged = P.principal_from_record({"principal_id": "prn_ugo", "profile": "friend", "scopes": old})
    plain = P.principal_from_record({"principal_id": "prn_accept", "scopes": old})
    assert P.KNOWLEDGE_RESEARCH in tagged.scopes and P.ADMIN not in tagged.scopes
    assert plain.scopes == frozenset(old)                                   # no tag, no widening: exactly what is stored
    assert P.authorize(tagged, "polymath_deep_research", {"corpus_id": "c"}).reason == "corpus_not_allowed"   # scope ok, corpus still checked
    assert P.authorize(plain, "polymath_deep_research", {"corpus_id": "c"}).reason == "insufficient_scope"
    with pytest.raises(ValueError, match="admin scope"):                     # a profile never smuggles admin in, and admin is never stored
        P.principal_from_record({"principal_id": "prn_xy", "profile": "friend", "scopes": ["admin"]})


def test_through_server_a_an_existing_web_friend_reaches_deep_research(monkeypatch, tmp_path):
    w = GATE._build(monkeypatch, tmp_path)
    ugo = w.add("prn_ugo", scopes=P.FRIEND_PROFILE, profile="friend")       # stored scopes predate F9
    acc = w.add("prn_accept", scopes=P.FRIEND_PROFILE)                      # an acceptance principal: no profile tag
    with TestClient(w.mod.build_app()) as c:
        w.c = c
        report = GATE._payload(GATE._call(w, ugo, "polymath_deep_research", {"question": "carts", "corpus_id": "commerce-v1"}))
        assert report["report"] == "a report on commerce-v1 [c1]"
        assert w.seen[-1] == {"path": "/research/deep", "principal": "prn_ugo", "agent": "claude-code/2.1"}
        GATE._denied(GATE._call(w, ugo, "polymath_deep_research", {"question": "carts", "corpus_id": "owner-private"}), "corpus_not_allowed")
        GATE._denied(GATE._call(w, acc, "polymath_deep_research", {"question": "carts", "corpus_id": "commerce-v1"}), "insufficient_scope")
        listed = {t["name"] for t in json.loads(GATE._post(w, ugo, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).text)["result"]["tools"]}
        assert {"polymath_deep_research", "upload_text", "recent_queries", "adapter_cancel", "supplier_search", "supplier_parse", "product_search"} <= listed


# ─────────────────────────────────────────────────────────── F3: the wildcard grant
def test_the_wildcard_reaches_every_library_but_another_friends_private_one_and_never_writes():
    p = P.principal_from_record({"principal_id": "prn_wild", "profile": "friend", "scopes": list(W.FRIEND_SCOPES),
                                 "corpus_ids": ["*", "fr-wild"], "writable_corpus_ids": ["fr-wild"]})
    assert p.corpus_ids.every and sorted(p.corpus_ids) == ["*", "fr-wild"]
    seen = [c for c in ("cinema", "commerce-v1", "a-library-made-tomorrow", "fr-wild", "fr-bob") if c in p.corpus_ids]
    assert seen == ["cinema", "commerce-v1", "a-library-made-tomorrow", "fr-wild"]          # the corpora listed now, filtered per request
    assert [c for c in ("cinema", "fr-bob", "fr-wild") if QS.grant_allows(c, p.corpus_ids)] == ["cinema", "fr-wild"]   # one rule
    for tool in ("polymath_search", "polymath_explore", "product_search"):
        assert P.authorize(p, tool, {"corpus_id": "a-library-made-tomorrow"}).allowed, tool
        assert P.authorize(p, tool, {"corpus_id": "fr-bob"}).reason == "corpus_not_allowed", tool
        assert P.authorize(p, tool, {"corpus_id": "*"}).reason == "corpus_not_allowed", tool    # "*" names no library
    assert P.authorize(p, "upload_text", {"corpus_id": "cinema"}).reason == "corpus_not_writable"   # the wildcard never writes
    assert P.authorize(p, "upload_text", {"corpus_id": "fr-wild"}).allowed
    named = P.Principal(principal_id="prn_named", scopes=frozenset(P.FRIEND_PROFILE), corpus_ids=frozenset({"cinema"}))
    assert "commerce-v1" not in named.corpus_ids and "*" not in named.corpus_ids                # no wildcard, no widening
    built = P.Principal(principal_id="prn_built", scopes=frozenset(P.FRIEND_PROFILE), corpus_ids=frozenset({"*"}))
    assert "cinema" in built.corpus_ids                                                     # however a Principal is built


def test_through_server_a_a_wildcard_friend_lists_searches_and_starts_on_any_library(monkeypatch, tmp_path):
    w = GATE._build(monkeypatch, tmp_path)
    wild = w.add("prn_wild", corpora=("*",))
    with TestClient(w.mod.build_app()) as c:
        w.c = c
        listed = [x["corpus_id"] for x in GATE._payload(GATE._call(w, wild, "list_corpora", {}))["corpora"]]
        assert listed == ["commerce-v1", "owner-private"]                   # every library that exists now
        alice = [x["corpus_id"] for x in GATE._payload(GATE._call(w, w.keys["prn_alice"], "list_corpora", {}))["corpora"]]
        assert alice == ["commerce-v1"]                                     # a named grant is unchanged
        rows = GATE._payload(GATE._call(w, wild, "polymath_search", {"query": "carts", "corpus_id": "owner-private"}))
        assert rows["evidence_rows"][0]["text"] == "a row from owner-private"
        GATE._denied(GATE._call(w, wild, "polymath_search", {"query": "carts", "corpus_id": "fr-bob"}), "corpus_not_allowed")
        GATE._denied(GATE._call(w, wild, "polymath_search", {"query": "carts"}), "corpus_not_allowed")     # no corpus is still not "any"
        ref = GATE._payload(GATE._call(w, wild, "adapter_start", {**GATE.START, "request_options": {"corpus_ids": ["owner-private"]}}))
        assert w.store.run_owner(None, ref["run_id"]) == (True, "prn_wild")


# ─────────────────────────────────────────────────────────── a library left unnamed; a friend's own private library
def test_adapter_start_and_product_search_may_name_no_library_but_a_named_one_is_checked():
    """CORPUS-ACCESS-PARITY / PRODUCT-SEARCH-E2E: the orchestrator resolves an unnamed library within the principal's grant (the run
    defaults to its searchable libraries; product search to every library it may use), so the gate lets it through; a library
    that IS named is checked exactly as before. product_search's policy kind says so itself (CORPUS_OPTIONAL)."""
    fred = P.principal_from_record({"principal_id": "prn_fred", "profile": "friend", "scopes": list(W.FRIEND_SCOPES),
                                    "corpus_ids": ["cinema", "fr-fred"], "adapter_ids": ["ecommerce.product_research"]})
    start = {"adapter_id": "ecommerce.product_research", "input": {"seed": "cat owners"}}
    for unnamed in (start, {**start, "request_options": {}}, {**start, "request_options": {"corpus_ids": []}}):
        assert P.authorize(fred, "adapter_start", unnamed).allowed, unnamed
    assert P.authorize(fred, "adapter_start", {**start, "request_options": {"corpus_ids": ["cinema", "fr-fred"]}}).allowed
    for bad in (["owner-private"], ["cinema", "fr-bob"], ["*"], [7]):
        assert P.authorize(fred, "adapter_start", {**start, "request_options": {"corpus_ids": bad}}).reason == "corpus_not_allowed", bad
    assert P.authorize(fred, "adapter_start", {**start, "adapter_id": "trail.product_discovery"}).reason == "adapter_not_allowed"
    assert P.TOOL_POLICY["product_search"][1] == P.CORPUS_OPTIONAL
    for unnamed in ({"message": "what should I sell"}, {"message": "x", "corpus_id": None}, {"message": "x", "corpus_id": "  "}):
        assert P.authorize(fred, "product_search", unnamed).allowed, unnamed
    assert P.authorize(fred, "product_search", {"message": "x", "corpus_id": "cinema"}).allowed
    for bad in ("owner-private", "fr-bob", "*", ["cinema"]):
        assert P.authorize(fred, "product_search", {"message": "x", "corpus_id": bad}).reason == "corpus_not_allowed", bad
    assert P.authorize(fred, "polymath_search", {"query": "x"}).reason == "corpus_not_allowed"       # CORPUS tools still name one


def test_the_wildcard_opens_a_friends_own_private_library_and_never_another_friends():
    """A web friend on "every library" holds ["*", "fr-<self>"] (web_accounts._grant): its own private library is reached, another
    friend's never — in the gate's corpus check, an adapter start and list filtering alike, as the orchestrator's web scope does."""
    fred = P.principal_from_record({"principal_id": "prn_fred", "profile": "friend", "scopes": list(W.FRIEND_SCOPES),
                                    "corpus_ids": ["*", "fr-fred"], "writable_corpus_ids": ["fr-fred"],
                                    "adapter_ids": ["ecommerce.product_research"]})
    for tool, args in (("polymath_search", {"query": "x", "corpus_id": "fr-fred"}), ("product_search", {"message": "x", "corpus_id": "fr-fred"}),
                       ("adapter_start", {"adapter_id": "ecommerce.product_research", "request_options": {"corpus_ids": ["fr-fred", "cinema"]}})):
        assert P.authorize(fred, tool, args).allowed, tool
    for tool, args in (("polymath_search", {"query": "x", "corpus_id": "fr-bob"}), ("product_search", {"message": "x", "corpus_id": "fr-bob"}),
                       ("adapter_start", {"adapter_id": "ecommerce.product_research", "request_options": {"corpus_ids": ["cinema", "fr-bob"]}})):
        assert P.authorize(fred, tool, args).reason == "corpus_not_allowed", tool
    listed = [c for c in ("cinema", "commerce-v1", "fr-fred", "fr-bob", "fr-ugo") if c in fred.corpus_ids]
    assert listed == ["cinema", "commerce-v1", "fr-fred"]                    # what list_corpora keeps of the corpora that exist
    bare = P.principal_from_record({"principal_id": "prn_cli", "scopes": list(P.FRIEND_PROFILE), "corpus_ids": ["*"]})
    assert "fr-cli" not in bare.corpus_ids and "fr-bob" not in bare.corpus_ids     # a private library opens only when the grant names it
