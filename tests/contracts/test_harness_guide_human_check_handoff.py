"""SUPPLIER-APIS (the owner's decision of 2026-09-27): every copy of the operating guide hands a human check to the harness's USER.
When `research_acquire` answers HUMAN_ACTION_REQUIRED the harness stops, asks its user to open the named site in their own browser
and pass the check themselves, waits for their reply and calls again with the same query; it never tries to solve, skip or work
around a check, and if the user cannot, it records the limitation and goes on without that source. A page it fetched itself that is
a verification wall is not evidence: it marks the source "needs you" and moves on (a receipt quoting one is refused).
The copies: the guide (`harness_guide.GUIDE`, served as the resource polymath://adapter/guide), the prompt `run_governed_research`,
the `research_acquire` description on BOTH MCP servers, and Server B's CONNECTORS.md. None of them suggests getting past a check.
"""
import asyncio
import importlib.util
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.adapter import harness_guide as HG

HANDOFF = ("HUMAN_ACTION_REQUIRED", "ask your user to open that site in their own browser", "pass the check themselves",
           "wait for their reply", "call again with the same query", "never try to solve, skip or work around a check",
           "continue without that source")
#: a sentence that names getting past a check must also say never / not / no
PAST_A_CHECK = re.compile(r"\b(?:solve[sd]?|solver|solving|bypass\w*|skip\w*|work(?:s|ed)?\s+around|evad\w+|circumvent\w*|get\s+past|rotat\w+|proxies)\b",
                          re.IGNORECASE)
NEGATION = re.compile(r"\b(?:never|not|no|nothing)\b", re.IGNORECASE)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _flat(text: str) -> str:
    return " ".join(str(text).split())


def _copies() -> dict[str, str]:
    a = {t.name: t for t in asyncio.run(_load("handoff_mcp_a", "orchestrator/orchestrator/mcp_server.py").mcp.list_tools())}
    b = {t.name: t for t in asyncio.run(_load("handoff_mcp_b", "mcp_server/polymath_mcp.py").server.list_tools())}
    connectors = (ROOT / "mcp_server/CONNECTORS.md").read_text(encoding="utf-8")
    section = connectors[connectors.index("**A harness with no browser"):connectors.index("## 4.")]
    return {"guide": HG.GUIDE, "prompt": HG.prompt_text("some.adapter", "a seed"), "server A": a["research_acquire"].description,
            "server B": b["research_acquire"].description, "CONNECTORS.md": section}


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(HG.__file__).resolve().is_relative_to(ROOT), HG.__file__


@pytest.mark.parametrize("where", ["guide", "prompt", "server A", "server B"])
def test_every_copy_hands_a_human_check_to_the_user(where):
    text = _flat(_copies()[where]).lower()
    for phrase in HANDOFF:
        assert phrase.lower() in text, (where, phrase)


def test_connectors_says_the_same_in_the_third_person():
    text = _flat(_copies()["CONNECTORS.md"]).lower()
    for phrase in ("human_action_required", "asks its user to open that site in their own browser", "pass the check themselves",
                   "waits for their reply", "calls again with the same query", "never tries to solve, skip or work around a check",
                   "continues without that source"):
        assert phrase in text, phrase


def test_both_servers_describe_research_acquire_identically():
    copies = _copies()
    assert _flat(copies["server A"]) == _flat(copies["server B"])


@pytest.mark.parametrize("where", ["guide", "prompt", "server A", "server B", "CONNECTORS.md"])
def test_no_copy_suggests_getting_past_a_check(where):
    for sentence in re.split(r"(?<=[.;:])\s+|\n\s*[-*]\s+", _copies()[where]):
        if PAST_A_CHECK.search(sentence):
            assert NEGATION.search(sentence), (where, sentence)


def test_a_fetched_wall_is_not_evidence_and_the_source_needs_the_user():
    for where in ("guide", "prompt"):
        text = _flat(_copies()[where])
        assert "verification wall" in text and "is not evidence: never quote it" in text, where
        assert 'Mark the source "needs you"' in text and "CHALLENGE_PAGE_AS_EVIDENCE" in text, where
    assert "CHALLENGE_PAGE_AS_EVIDENCE" in _copies()["CONNECTORS.md"]
