"""DEEP-RESEARCH-MODE-V1 slice DR6b (§10.1): `/retrieve`'s optional `intent`.

Absent: every existing caller is unchanged — the kwargs `chat_retrieve_mode` receives are exactly the pre-intent ones, with
and without ✨ latent, in HYBRID, GRAPH and WILDCARD. Present: chat's own application of the §33 policy (ui.py P2b / P6):
`apply_intent_policy(intent, default_budget())`, ✨ still winning the latent lane, and the policy's graph assist. Unknown: a
typed 422 `unknown_intent`. A path that cannot honour it (FAST, GNN, the default lane, the v1 rollback, `utility`): a typed
422 `intent_unsupported`, never a silent no-op. Pure dispatch: the scope, the core and the legacy services are fakes."""
from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import replace

import pytest
from fastapi import HTTPException
from orchestrator.api import retrieve as retrieve_mod
from orchestrator.api.retrieve import RetrieveRequest, _retrieve_impl
from polymath_shared.query_intent import INTENTS, apply_intent_policy, policy_for
from polymath_shared.query_scope import QueryScope

CORPUS = "cinema"
QUERY = "how does light shape a shot's mood"


@contextlib.contextmanager
def _tx():
    yield None


@pytest.fixture()
def core(monkeypatch):
    """The v2 core recorded, the scope resolved without a database, v2 by default."""
    import orchestrator.api.chat_retrieval as cr_mod
    calls: list[tuple[str, str, str, dict]] = []
    monkeypatch.setattr(retrieve_mod, "tx", _tx)
    monkeypatch.setattr(retrieve_mod, "resolve_http_scope", lambda conn, req: QueryScope(mode="CORPUS", corpus_ids=(CORPUS,)))
    monkeypatch.setattr(cr_mod, "chat_retrieve_mode",
                        lambda mode, query, cid, **kw: calls.append((mode, query, cid, kw)) or {"evidence": [], "meta": {}})
    monkeypatch.delenv("POLYMATH_RETRIEVE_ENGINE", raising=False)
    for name in [n for n in os.environ if n.startswith("POLYMATH_CHAT_")]:
        monkeypatch.delenv(name, raising=False)                      # the budget knobs: the defaults are the contract
    return calls


def _run(**body):
    return asyncio.run(_retrieve_impl(RetrieveRequest(**body)))


def _refused(**body) -> dict:
    with pytest.raises(HTTPException) as exc:
        _run(**body)
    assert exc.value.status_code == 422
    return exc.value.detail


@pytest.mark.parametrize("mode", ["HYBRID", "GRAPH", "WILDCARD"])
@pytest.mark.parametrize("latent", [None, False, True])
def test_absent_intent_leaves_every_caller_unchanged(core, mode, latent):
    from orchestrator.api.chat_retrieval import default_budget
    _run(query=QUERY, corpus_id=CORPUS, mode=mode, latent=latent)
    _run(query=QUERY, corpus_id=CORPUS, mode=mode, latent=latent, intent="  ")         # blank = absent
    # the pre-intent code: `_kw = {}; if req.latent: _kw["budget"] = replace(default_budget(), latent_enabled=True)`
    expected = {"budget": replace(default_budget(), latent_enabled=True)} if latent else {}
    assert core == [(mode, QUERY, CORPUS, expected)] * 2


@pytest.mark.parametrize("mode", ["HYBRID", "GRAPH", "WILDCARD"])
@pytest.mark.parametrize("intent", ["RELATIONSHIP", "COMPARISON", "exploratory"])
def test_an_intent_applies_chats_policy(core, mode, intent):
    from orchestrator.api.chat_retrieval import default_budget
    _run(query=QUERY, corpus_id=CORPUS, mode=mode, intent=intent)
    _run(query=QUERY, corpus_id=CORPUS, mode=mode, intent=intent, latent=True)
    canon = intent.upper()
    # ui.py P2b / P6: _apply_intent(plan.intent, _default_budget()); ✨ wins the latent lane; graph assist = policy.graph
    budget = apply_intent_policy(canon, default_budget())
    assert core == [(mode, QUERY, CORPUS, {"budget": budget, "graph_assist": policy_for(canon).graph}),
                    (mode, QUERY, CORPUS, {"budget": replace(budget, latent_enabled=True),
                                           "graph_assist": policy_for(canon).graph})]
    assert budget != default_budget()                  # the policy changed something, or this proves nothing


def test_the_relationship_intent_switches_on_the_reserved_surfaces(core):
    _run(query=QUERY, corpus_id=CORPUS, mode="HYBRID", intent="RELATIONSHIP")
    kw = core[0][3]
    assert kw["graph_assist"] == "auto" and kw["budget"].seealso_fanout_enabled and kw["budget"].graph_dest_enabled
    assert {"SEEALSO", "BRIDGE", "ANCHOR"} <= set(kw["budget"].atom_kinds)


def test_an_unknown_intent_is_a_typed_422(core):
    detail = _refused(query=QUERY, corpus_id=CORPUS, mode="HYBRID", intent="VIBES")
    assert detail["error_code"] == "unknown_intent" and all(i in detail["message"] for i in INTENTS)
    assert core == []


@pytest.mark.parametrize("body", [
    {"mode": "FAST"}, {"mode": "GNN"}, {}, {"mode": "EXPLORE"}, {"mode": "HYBRID", "utility": True}])
def test_a_path_that_cannot_honour_an_intent_refuses_it(core, monkeypatch, body):
    import orchestrator.api.fast as fast_mod
    monkeypatch.setattr(fast_mod, "fast_retrieve", lambda *a, **k: pytest.fail("FAST must not run with an intent"))
    detail = _refused(query=QUERY, corpus_id=CORPUS, intent="RELATIONSHIP", **body)
    assert detail["error_code"] == "intent_unsupported" and core == []


@pytest.mark.parametrize("mode", ["HYBRID", "GRAPH", "WILDCARD"])
def test_the_v1_rollback_refuses_an_intent_rather_than_drop_it(core, monkeypatch, mode):
    monkeypatch.setenv("POLYMATH_RETRIEVE_ENGINE", "v1")
    assert _refused(query=QUERY, corpus_id=CORPUS, mode=mode, intent="COMPARISON")["error_code"] == "intent_unsupported"
    assert core == []
