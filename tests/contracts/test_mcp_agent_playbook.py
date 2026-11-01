"""PRODUCT-SEARCH-E2E (the owner, 2026-11-01): what every connected agent is TOLD, on both MCP servers and in every connect prompt.

  "the agent no matter the model tends to be unaware of what the tools do and how to use its also, its bad all around." /
  "the trail agent os and or product search tools the agents must know how to use it, how it works, e2e." /
  "it should never use a users claude native web search due to bot detections and it should work."

Pinned here:
  * both servers list `product_search` (POST /product/search) and `supplier_parse` (POST /supplier/parse) with the same parameters
    and the same description, and send exactly the contract bodies;
  * the server instructions are ONE ordered playbook (library -> questions -> product_search -> local Agent Reach -> honest gaps ->
    governed research the agent drives);
  * no agent-facing text — instructions, every tool description, the guide's resources and prompt, the connect prompts — sends an
    agent to its own / built-in web search, fetch or browser (a regex over the strings the servers actually serve);
  * polymath_answer and product_search send the app's DEFAULT model when none is named (the web UI's rule), asked once per window;
    the legacy `ask` stays on /chat's deterministic default (TRAIL reads its claims);
  * polymath_search / polymath_explore keep a product turn's `product_research` and `agent_steps`;
  * upload_text carries the principal it is for (FRIEND-JOURNEY F15).
In process: every orchestrator call is faked or served by an in-memory app; no network, no database.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("orchestrator", "shared"):
    sys.path.insert(0, str(ROOT / _sub))

import httpx
import pytest
from fastapi import FastAPI, Request
from polymath_shared import mcp_retrieval as MR
from polymath_shared.adapter import harness_guide as HG
from starlette.testclient import TestClient

OWNER_KEY = "owner-playbook-key-0123456789"
NEW_TOOLS = ("product_search", "supplier_parse")
#: the descriptions both servers take from the ONE shared copy (MR)
SHARED = {"product_search": MR.PRODUCT_SEARCH, "supplier_parse": MR.SUPPLIER_PARSE, "supplier_search": MR.SUPPLIER_SEARCH,
          "supplier_product": MR.SUPPLIER_PRODUCT, "supplier_freight": MR.SUPPLIER_FREIGHT, "supplier_warehouses": MR.SUPPLIER_WAREHOUSES,
          "adapter_list": MR.ADAPTER_LIST, "adapter_start": MR.ADAPTER_START, "adapter_next": MR.ADAPTER_NEXT,
          "research_acquire": MR.RESEARCH_ACQUIRE}
CATALOG = {"synthesizers": [{"id": "litellm:other", "label": "Other", "default": False},
                            {"id": "litellm:hidden", "label": "Hidden", "offered": False, "default": False},
                            {"id": "litellm:the-default", "label": "Default", "default": True}]}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__
    return mod


def _servers() -> dict:
    return {"A": _load("playbook_mcp_a", "orchestrator/orchestrator/mcp_server.py").mcp,
            "B": _load("playbook_mcp_b", "mcp_server/polymath_mcp.py").server}


def _flat(text: str) -> str:
    return " ".join(str(text or "").split())


def test_the_code_under_test_is_this_checkout():
    from orchestrator.api import web_settings
    for mod in (MR, HG, web_settings):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── the two new tools, on both servers
def test_both_servers_list_product_search_and_supplier_parse_with_the_same_contract():
    tools = {label: {t.name: t for t in asyncio.run(server.list_tools())} for label, server in _servers().items()}
    a, b = tools["A"], tools["B"]
    for name in NEW_TOOLS:
        assert name in a and name in b, name
        assert a[name].input_schema.get("properties") == b[name].input_schema.get("properties"), name     # names, types, defaults
        assert sorted(a[name].input_schema.get("required") or []) == sorted(b[name].input_schema.get("required") or []), name
    assert a["product_search"].input_schema["required"] == ["message"]                 # owner R11: no library has to be guessed
    assert a["product_search"].input_schema["properties"]["corpus_id"].get("default") is None
    assert set(a["product_search"].input_schema["properties"]) == {"message", "corpus_id", "geography", "model", "hypotheses",
                                                                   "limit_per_hypothesis"}
    assert sorted(a["supplier_parse"].input_schema["required"]) == ["raw_text", "site"]
    for name, text in SHARED.items():                                     # one shared copy: the two servers cannot drift
        assert _flat(a[name].description) == _flat(b[name].description) == _flat(text), name
    assert _flat(a["polymath_models"].description) == _flat(b["polymath_models"].description)
    assert "product_search" in a["polymath_models"].description


def test_server_a_names_every_tool_it_registers():
    mod = _load("playbook_mcp_a_names", "orchestrator/orchestrator/mcp_server.py")
    assert set(mod._TOOL_NAMES) == {t.name for t in mod.mcp._tool_manager.list_tools()}           # /health and the policy law read it
    assert set(NEW_TOOLS) <= set(mod._TOOL_NAMES)


def test_product_search_tells_the_whole_flow():
    text = _flat(MR.PRODUCT_SEARCH)
    for needle in ("THE entry point for product questions", "Any library works", "Polymath reads the library", "CJ Dropshipping's official API",
                   "Alibaba is never searched from the host", "AGENT_REACH_REQUIRED", "fallback", MR.AGENT_REACH_REPO, MR.AGENT_REACH_VERIFY,
                   "supplier_parse", "no terminal", "CJ API results only", "never your built-in web search", "supply evidence, never proof of demand",
                   "product_research.next.full_research", MR.PRODUCT_ADAPTER, "never start it unasked", "you drive"):
        assert needle in text, needle
    # what Polymath does comes before what the agent does, and the offer of the full run comes last
    assert text.index("(1) Polymath") < text.index("(2) Polymath") < text.index("(3)") < text.index("(4) You") < text.index("never start it unasked")
    assert "each item {" + ", ".join(MR.CJ_ITEM_FIELDS) + "}" in text                      # the product-search-v1 CJ item names
    assert _flat(MR.RUN_FALLBACK) in text


def test_every_fallback_text_matches_the_fallback_the_acquisition_layer_builds():
    """The descriptions name the keys `agent_reach.fallback` really returns, and say its commands are step OBJECTS: execute `run` on the
    user's machine (once per `for_each` item), then do `then`."""
    from polymath_shared.acquisition import agent_reach as AR
    fb = AR.fallback(AR.ALIBABA, "dry bag", "AGENT_REACH_REQUIRED", "Alibaba is read only through your own Agent Reach")
    described = ("kind", "reason_code", "why", "run_on", "never", "install", "commands", "submit", "walls")
    assert set(described) <= set(fb) and {"repo", "verify"} <= set(fb["install"]), sorted(fb)
    assert (fb["install"]["repo"], fb["install"]["verify"]) == (MR.AGENT_REACH_REPO, MR.AGENT_REACH_VERIFY)
    assert all(isinstance(c, dict) and {"run", "then"} <= set(c) and set(c) <= {"step", "run", "what", "for_each", "then"} for c in fb["commands"])
    assert fb["submit"]["tool"] == "supplier_parse" and set(fb["submit"]["arguments"]) == {"site", "raw_text"}
    for text in (MR.SUPPLIER_SEARCH, MR.PRODUCT_SEARCH, MR.playbook(list_tool="list_corpora", add_documents="")):
        assert _flat(MR.RUN_FALLBACK) in _flat(text)
    assert "`submit.arguments.site`" in MR.SUPPLIER_PARSE and "`for_each`" in MR.SUPPLIER_PARSE and "ONE command's whole output" in MR.SUPPLIER_PARSE
    assert "`run`, `what`, `for_each`," in _flat(HG.GUIDE) and "`then`" in HG.GUIDE


def test_the_supplier_tools_say_who_may_call_them_how_cj_is_paced_and_what_a_fallback_is():
    for name in ("supplier_search", "supplier_product", "supplier_freight", "supplier_warehouses"):
        text = _flat(SHARED[name])
        assert text.startswith("READ-ONLY") and "owner key only" not in text and "SearXNG" not in text, name
        assert "any key that can call" in text and "pace" in text and "fallback" in text, name
    search = _flat(MR.SUPPLIER_SEARCH)
    assert "AGENT_REACH_REQUIRED" in search and "source=\"alibaba\": never searched from the host" in search
    for key in ("kind AGENT_REACH", "reason_code", "why", "run_on", "never", "install{repo, verify}", "commands", "submit", "supplier_parse"):
        assert key in search, key
    assert "OWNER KEY ONLY" in MR.RESEARCH_ACQUIRE                                   # the host browser stays the owner's


def test_only_search_and_product_promise_a_fallback_and_every_supplier_text_matches_the_acquisition_layer():
    """acquisition/supplier.py: supplier_search and supplier_product answer a CJ failure with an Agent Reach `fallback`; a freight
    quote or the warehouse list cannot be had on the user's side, so those answer `fallback: null` with a `reason_code`."""
    from polymath_shared.acquisition import agent_reach as AR
    from polymath_shared.acquisition import supplier as SUP
    assert "a `fallback`" in MR.SUPPLIER_SEARCH and "exactly as supplier_search does" in MR.SUPPLIER_PRODUCT
    for text in (MR.SUPPLIER_FREIGHT, MR.SUPPLIER_WAREHOUSES):
        assert "`fallback: null`" in text and "exactly as supplier_search does" not in text and "and a `fallback`" not in text
    no_key = {"CJ_API_KEY": ""}
    assert SUP.freight(principal_id=None, variant_id="D4057F56-3F09-4541-8461-9D76D014846D", country="US", env=no_key)["fallback"] is None
    assert SUP.warehouses(principal_id=None, env=no_key)["fallback"] is None
    assert SUP.product(principal_id=None, product_id="04A22450-67F0-4617-A132-E7AE7F8963B0", env=no_key)["fallback"]["kind"] == AR.KIND
    assert set(MR.SUPPLIER_REASON_CODES) == set(SUP.REASON_CODES.values()) | {"CJ_NO_KEY", "CJ_EMPTY", "ALIBABA_AGENT_REACH_ONLY", "HUMAN_CHECK"}
    for text in (MR.SUPPLIER_SEARCH, MR.SUPPLIER_PARSE):
        assert all(code in text for code in MR.SUPPLIER_REASON_CODES)
        assert all(w in text for w in ("SUPPLIER_RATE_LIMITED", "SUPPLIER_BUSY", "Retry-After", f"{SUP.RATE_DEFAULT} supplier calls a minute"))
    parse = _flat(MR.SUPPLIER_PARSE)
    for needle in ("OK | EMPTY | HUMAN_CHECK", "`refused` [{url, code, why}]", "OFF_SITE", "NOT_A_PRODUCT_PAGE", "DUPLICATE", "OVER_LIMIT",
                   "`next`", f"at most {AR.MAX_RAW_BYTES} bytes", "ONE command's whole output per call"):
        assert needle in parse, needle


def test_the_list_tools_say_what_each_library_flag_means():
    for label, server in _servers().items():
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        listing = tools["list_corpora" if label == "A" else "polymath_list_corpora"]
        assert MR.CORPUS_FLAGS in listing.description, label
    for needle in ("`query_ready` true = searchable now, so use it", "`in_all_libraries` true = included when a query names no library",
                   "`private` true = your own library", "`notes`"):
        assert needle in MR.CORPUS_FLAGS, needle


def _corpora_world(monkeypatch, tmp_path, principals: dict[str, list[str]], served: dict):
    """Server A behind its gate, principals with the given read grants, and a /corpora that answers what `served[principal]` says
    (the orchestrator filters per caller since CORPUS-ACCESS-PARITY; None = the owner)."""
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    keys = {}
    for pid, grant in principals.items():
        raw, key = P.new_bearer()
        doc["principals"].append({"principal_id": pid, "name": pid, "enabled": True, "revoked_at": None, "scopes": sorted(P.FRIEND_PROFILE),
                                  "corpus_ids": grant, "adapter_ids": [], "writable_corpus_ids": [], "created_at": P._now_iso(),
                                  "expires_at": None, "rate_per_minute": None, "keys": [key]})
        keys[pid] = raw
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    orch = FastAPI()

    @orch.get("/corpora")
    async def corpora(request: Request):
        rows = served[request.headers.get("x-polymath-principal")]
        return {"corpora": [{"corpus_id": c, "name": c, "documents": 3, "query_ready": True, "in_all_libraries": not c.startswith("fr-"),
                             "private": c.startswith("fr-"), "purpose": "production", "query_enabled": True} for c in rows],
                "notes": {"query_ready": "searchable now", "in_all_libraries": "included when no library is named"}}
    real_client = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.ASGITransport(app=orch)}))
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    return mod, keys


def _listed(c, key: str) -> dict:
    r = c.post("/mcp", headers={**ACCEPT, "Authorization": f"Bearer {key}"},
               json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_corpora", "arguments": {}}})
    assert r.status_code == 200, r.text[:300]
    body = r.text if r.text.lstrip().startswith("{") else [ln[5:].strip() for ln in r.text.splitlines() if ln.startswith("data:")][-1]
    result = json.loads(body)["result"]
    sc = result.get("structuredContent")
    return sc if isinstance(sc, dict) and "result" not in sc else json.loads(result["content"][0]["text"])


def test_list_corpora_passes_the_per_caller_list_through_for_a_wildcard_friend_and_narrows_a_listed_one(monkeypatch, tmp_path):
    from polymath_shared import query_scope as QS
    served = {"prn_star": ["cinema", "commerce-v1", "fr-star"],
              "prn_listed": ["cinema", "commerce-v1", "fr-listed"],       # an orchestrator that over-answered: the MCP layer still narrows
              None: ["cinema", "commerce-v1", "fr-star", "fr-listed", "owner-private"]}
    mod, keys = _corpora_world(monkeypatch, tmp_path, {"prn_star": ["*", "fr-star"], "prn_listed": ["commerce-v1", "fr-listed"]}, served)
    assert mod.ALL_LIBRARIES == QS.ALL_LIBRARIES
    with TestClient(mod.build_app()) as c:
        star, listed, owner = _listed(c, keys["prn_star"]), _listed(c, keys["prn_listed"]), _listed(c, OWNER_KEY)
    assert [r["corpus_id"] for r in star["corpora"]] == ["cinema", "commerce-v1", "fr-star"]          # "*" = all the orchestrator returned
    assert [r["corpus_id"] for r in listed["corpora"]] == ["commerce-v1", "fr-listed"]               # a listed grant stays its list
    assert [r["corpus_id"] for r in owner["corpora"]] == served[None]
    for out in (star, listed, owner):
        assert out["notes"]["in_all_libraries"] == "included when no library is named"              # the notes pass through
    row = star["corpora"][2]
    assert (row["private"], row["in_all_libraries"], row["query_ready"]) == (True, False, True)


# ─────────────────────────────────────────────────────────── the playbook
STEPS = ("1. Pick a library", "2. Library questions", "3. Product questions", "4. Live web", "5. verdict=insufficient_evidence",
         "6. Governed research")


def test_the_instructions_are_one_ordered_playbook_on_both_servers():
    for label, server in _servers().items():
        text = server.instructions
        at = [text.index(s) for s in STEPS]
        assert at == sorted(at), (label, at)
        listing = "list_corpora()" if label == "A" else "polymath_list_corpora()"
        for needle in (listing, "Any library works", "query_ready", "product_search", "never start it unasked", "LOCAL Agent Reach",
                       MR.AGENT_REACH_REPO, f"`{MR.AGENT_REACH_VERIFY}`", "never your built-in web search, web fetch or browser",
                       "supplier_parse", "no terminal", "CJ API results only", "adapter_start", "adapter_next / adapter_submit",
                       "YOU drive every step", "Polymath never reasons for you", f"{MR.PRODUCT_REASON_STEPS} in product research",
                       "`agent_reach`", HG.PROMPT_NAME, HG.GUIDE_URI):
            assert needle in text, (label, needle)
        assert all(f"{m}:" in text for m in MR.RETRIEVAL_MODES), label
    a, b = (s.instructions for s in _servers().values())
    assert a.replace("list_corpora()", "X").split("\n")[2:] == b.replace("polymath_list_corpora()", "X").split("\n")[2:]   # same steps 2-6


def test_the_numbers_and_names_the_texts_promise_are_the_real_ones():
    manifest = json.loads((ROOT / "config/adapters/ecommerce.product_research.json").read_text())
    assert sum(s["type"] == "AGENT_REASON" for s in manifest["steps"]) == MR.PRODUCT_REASON_STEPS
    assert manifest["adapter_id"] == MR.PRODUCT_ADAPTER and manifest["description"].startswith("PREFERRED")
    from orchestrator.api import web_settings
    assert (MR.GUIDE_PROMPT, MR.GUIDE_RESOURCE) == (HG.PROMPT_NAME, HG.GUIDE_URI)
    assert MR.AGENT_REACH_REPO == HG.AGENT_REACH_REPO == web_settings.AGENT_REACH_REPO
    assert MR.AGENT_REACH_VERIFY == web_settings.AGENT_REACH_VERIFY


def test_the_guide_documents_the_agent_reach_steps_the_draft_receipt_and_distinct_platforms():
    guide = _flat(HG.GUIDE)
    for needle in ("**you** drive the run", "Polymath never reasons for you", "local Agent Reach", HG.AGENT_REACH_REPO,
                   "Never use your built-in web search, web fetch or browser", "`agent_reach`", "local_only, never, install, per_intent",
                   "`install.verify`", "`intent_id`, `channel`, `commands`, `tool_class`, `receipt_tags`", "no terminal",
                   "needs a local agent with a terminal", "supplier_parse(site, raw_text)", "draft receipt",
                   "count distinct platforms (independence groups), never observations", "price claim needs 3 platforms",
                   "a risk claim 1", "an ANCHOR cluster 3"):
        assert needle in guide, needle
    assert MR.AGENT_REACH_VERIFY not in HG.GUIDE and "doctor" not in HG.GUIDE      # exact commands travel in tool results, never here
    assert "local Agent Reach" in HG.PROMPT_DESCRIPTION and "ANY tools" not in HG.PROMPT_DESCRIPTION


# ─────────────────────────────────────────────────────────── no text sends an agent to its own web tools
#: a directive that points an agent at its own / built-in web tools (every form the owner's rule retired)
OWN_WEB = re.compile(
    r"\b(?:your|its)\s+own\s+(?:web[\s-]?)?(?:tools?|search(?:es)?|search\s+engine|browser|browsing|fetch(?:er)?|web)\b"
    r"|\bany\s+tools?\b"
    r"|\bwith\s+whatever\s+tools?\b"
    r"|\b(?:native|built-?in|builtin)\s+(?:web[\s-]?)?(?:search|tools?|browser|browsing|fetch)\b"
    r"|\bweb\s+search(?:es)?,\s+(?:web\s+)?fetch\b"
    r"|\bgo\s+research\s+with\b"
    r"|\bresearch\s+steps\s+need\s+your\b",
    re.IGNORECASE)
NEGATION = re.compile(r"\b(?:never|not|no|nobody|nothing|don't|do\s+not)\b", re.IGNORECASE)
CLAUSE = re.compile(r"(?<=[.;:!?])\s+|\n+")
#: agent-facing texts still to be rewritten elsewhere. Empty since the adapter slice rewrote the last four (harness_action.schema.json:5,
#: transitions.HARNESS_RECEIPT_RULES, both product manifests' descriptions): every text below must now pass
PENDING_ELSEWHERE: set[str] = set()


def offenders(text: str) -> list[str]:
    """Every clause that points at an agent's own / built-in web tools without a negation BEFORE the phrase."""
    bad = []
    for clause in CLAUSE.split(str(text or "")):
        for m in OWN_WEB.finditer(clause):
            if not NEGATION.search(clause[:m.start()]):
                bad.append(clause.strip()[:160])
    return bad


def test_the_detector_catches_every_retired_wording_and_passes_the_new_rule():
    for old in ("HARNESS_ACTION step: go research with YOUR OWN tools — web search, browser, APIs — within its search intents",
                "Use any tool you have: web search, fetch, a browser, an official API.",
                "Research steps need your own web tools (search, browse).",
                "How to run any adapter end to end with any tools you have: the prompt run_governed_research",
                "the harness decides which native tools to use and answers with a receipt",
                "the host harness investigates customers, products and supply with its own tools; TrailSignal alone admits evidence",
                "Research with whatever tools you like; quote pages verbatim.", "Use your built-in web search for the field step."):
        assert offenders(old), old
    for new in ("Live web = the user's LOCAL Agent Reach, never your built-in web search, web fetch or browser (bot detection blocks them).",
                "Every other caller runs the commands on the user's own machine, and no caller uses a built-in web search, web fetch or browser.",
                "ask your user to open that site in their own browser on the Polymath host and pass the check themselves",
                "Add documents to your own library (fr-fred) with upload_text."):
        assert not offenders(new), new


async def _served(server) -> dict[str, str]:
    texts = {"instructions": server.instructions}
    for t in server._tool_manager.list_tools():                          # every registered tool, listed or legacy
        texts[f"tool {t.name}"] = t.description or ""
    for r in await server.list_resources():
        texts[f"resource {r.uri}"] = "\n".join(str(getattr(c, "content", c)) for c in await server.read_resource(str(r.uri)))
        texts[f"resource title {r.uri}"] = f"{r.title or ''} {r.description or ''}"
    for p in await server.list_prompts():
        texts[f"prompt description {p.name}"] = p.description or ""
        texts[f"prompt {p.name}"] = json.dumps((await server.get_prompt(p.name, {"adapter_id": "x.y", "seed": "s"})).model_dump(mode="json"))
    return texts


def _every_agent_facing_text() -> dict[str, str]:
    from orchestrator.api import web_settings as WS
    from polymath_shared.adapter import transitions as T
    from polymath_shared.adapter.manifest import ADAPTER_DIR, list_manifests
    texts: dict[str, str] = {}
    for label, server in _servers().items():
        for where, text in asyncio.run(_served(server)).items():
            key = where if where.startswith("resource") or where.startswith("prompt") else f"server {label} {where}"
            texts[key] = text
    texts["connect prompt (owner, key-free)"] = WS.owner_prompt(["cinema"])
    texts["connect prompt (friend)"] = WS.connect_prompt("pmk_abc", ["cinema"], "fr-fred", url="https://mcp.example.test/mcp")
    texts["connect prompt (friend, every library)"] = WS.connect_prompt("pmk_abc", ["*", "fr-fred"], "fr-fred", url="https://mcp.example.test/mcp")
    texts["connect prompt (owner key)"] = WS.connect_prompt("k" * 24, ["cinema"], None, url="https://mcp.example.test/mcp", owner=True)
    texts["mcp_server/CONNECTORS.md"] = (ROOT / "mcp_server/CONNECTORS.md").read_text(encoding="utf-8")   # what a harness's human reads
    texts["acceptance rule (transitions.HARNESS_RECEIPT_RULES)"] = "\n".join(T.HARNESS_RECEIPT_RULES)
    for m in list_manifests(ADAPTER_DIR):                                 # what adapter_list serves for each adapter
        texts[f"adapter description {m.adapter_id}"] = str(m.raw.get("description") or "")
    return texts


def test_no_agent_facing_text_sends_an_agent_to_its_own_web_tools():
    texts = _every_agent_facing_text()
    assert {"instructions", "tool product_search", "tool adapter_next", "tool research_acquire"} <= {k.split(" ", 2)[-1] for k in texts}
    assert f"resource {HG.GUIDE_URI}" in texts and f"prompt {HG.PROMPT_NAME}" in texts
    found = {where: bad for where, text in texts.items() if (bad := offenders(text))}
    assert set(found) <= PENDING_ELSEWHERE, {k: v for k, v in found.items() if k not in PENDING_ELSEWHERE}


# ─────────────────────────────────────────────────────────── the app's default model, and the product / parse routes
@pytest.fixture()
def server_a(monkeypatch, tmp_path):
    registry = tmp_path / "principals.json"
    registry.write_text(json.dumps({"schema": "polymath_mcp_principals.v1", "principals": []}))
    registry.chmod(0o600)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_principals, mcp_server
    importlib.reload(mcp_principals)
    mod = importlib.reload(mcp_server)
    assert pathlib.Path(mod.__file__).is_relative_to(ROOT), mod.__file__
    calls: list[tuple] = []
    replies: dict = {}

    async def fake_orch(method, path, **kw):
        calls.append((method, path, kw.get("json"), kw.get("timeout")))
        return replies.get(path, {})
    monkeypatch.setattr(mod, "_orch", fake_orch)
    return type("A", (), {"mod": mod, "calls": calls, "replies": replies})


@pytest.fixture()
def server_b(monkeypatch):
    mod = _load("playbook_mcp_b_calls", "mcp_server/polymath_mcp.py")
    calls: list[tuple] = []
    replies: dict = {}

    def fake_post(path, payload, timeout=300):
        calls.append(("POST", path, payload, timeout))
        return replies.get(path, {})

    def fake_get(path, **params):
        calls.append(("GET", path, params, None))
        reply = replies.get(path, {})
        if isinstance(reply, Exception):
            raise reply
        return reply

    def fake_adapter(method, path, payload=None):
        calls.append((method, path, payload, None))
        return replies.get(path, {})
    monkeypatch.setattr(mod, "_post", fake_post)
    monkeypatch.setattr(mod, "_get", fake_get)
    monkeypatch.setattr(mod, "_adapter", fake_adapter)
    return type("B", (), {"mod": mod, "calls": calls, "replies": replies})


def test_the_default_model_is_the_catalog_row_the_web_ui_picks():
    assert MR.default_model(CATALOG) == "litellm:the-default"                                   # the row marked `default`
    assert MR.default_model({"synthesizers": [{"id": "litellm:hidden", "offered": False}, {"id": "ollama:b"}]}) == "ollama:b"
    assert MR.default_model({}) is None and MR.default_model({"error": "down", "status": 502}) is None
    assert MR.shape_models(CATALOG)["default"] == "litellm:the-default"                          # polymath_models names the same one
    clock = [100.0]
    cache = MR.DefaultModel(ttl_s=60, clock=lambda: clock[0])
    assert cache.cached() is None and cache.remember({}) is None and cache.cached() is None      # a failed ask is not remembered
    assert cache.remember(CATALOG) == "litellm:the-default" and cache.cached() == "litellm:the-default"
    clock[0] += 61
    assert cache.cached() is None                                                                # asked again after the window


def test_polymath_answer_writes_with_the_apps_default_model_when_none_is_named(server_a):
    a = server_a
    a.replies["/synthesizers"] = CATALOG
    asyncio.run(a.mod.polymath_answer("q", "cinema"))
    assert [c[1] for c in a.calls] == ["/synthesizers", "/chat"]
    assert a.calls[-1][2] == {"message": "q", "corpus_id": "cinema", "mode": "HYBRID", "synthesizer": "litellm:the-default"}
    asyncio.run(a.mod.polymath_answer("q", "cinema", mode="graph"))
    assert [c[1] for c in a.calls] == ["/synthesizers", "/chat", "/chat"]                       # remembered: asked once per window
    assert a.calls[-1][2]["synthesizer"] == "litellm:the-default"
    asyncio.run(a.mod.polymath_answer("q", "cinema", model="litellm:named"))
    assert a.calls[-1][2]["synthesizer"] == "litellm:named" and len(a.calls) == 4                # a named model is sent as named
    a.mod._DEFAULT_MODEL = MR.DefaultModel()
    a.replies["/synthesizers"] = {"error": "orchestrator down", "status": 502}
    asyncio.run(a.mod.polymath_answer("q", "cinema"))
    assert "synthesizer" not in a.calls[-1][2]                                                   # no catalog: nothing invented
    asyncio.run(a.mod.ask("q", "cinema"))
    assert a.calls[-1][1] == "/chat" and "synthesizer" not in a.calls[-1][2]                     # legacy `ask`: /chat's own default
    assert a.calls[-2][1] == "/chat"                                                             # ... and it never asked the catalog


def test_server_b_answers_with_the_same_default(server_b):
    b = server_b
    b.replies["/synthesizers"] = CATALOG
    b.mod.polymath_answer("q", "cinema", mode="GRAPH", reasoning="debate")
    assert b.calls[-1] == ("POST", "/chat", MR.answer_body("q", "cinema", "GRAPH", reasoning="debate", model="litellm:the-default"), 300)
    b.mod.polymath_answer("q", "cinema")
    assert [c[1] for c in b.calls] == ["/synthesizers", "/chat", "/chat"]
    b.mod._DEFAULT_MODEL = MR.DefaultModel()
    b.replies["/synthesizers"] = httpx.ConnectError("refused")
    b.mod.polymath_answer("q", "cinema")
    assert "synthesizer" not in b.calls[-1][2]


PRODUCT_REPLY = {"answer": "Three product ideas from the library [S1].", "verdict": "supported",
                 "product_research": {"contract": "product-search-v1", "intent": "what_to_sell", "corpus_ids": ["cinema"],
                                      "hypotheses": [{"id": "h1", "title": "Dry bag", "cj": {"status": "OK", "items": [{"title": "x"}]},
                                                      "alibaba": {"status": "AGENT_REACH_REQUIRED", "fallback": {"kind": "AGENT_REACH"}}}],
                                      "next": {"full_research": {"tool": "adapter_start", "adapter_id": MR.PRODUCT_ADAPTER,
                                                                 "who_drives": "your agent"}}},
                 "evidence": [{"text": "z" * 900, "chunk_id": "c1"}] * 20, "retrieval": {"mode": "HYBRID"}, "phases": [{"stage": "answer"}]}


def test_product_search_sends_the_contract_body_and_keeps_product_research(server_a, server_b):
    ideas = [{"title": "Dry bag", "search_terms": ["dry bag", " "], "junk": 1}, {"title": " "}, "not an idea"]
    for label, s in (("A", server_a), ("B", server_b)):
        s.replies["/synthesizers"] = CATALOG
        s.replies["/product/search"] = PRODUCT_REPLY
        call = s.mod.product_search("what should I sell to hikers?", "cinema", geography="US", hypotheses=ideas, limit_per_hypothesis=3)
        out = asyncio.run(call) if label == "A" else call
        method, path, body, timeout = s.calls[-1]
        assert (method, path, timeout) == ("POST", "/product/search", 600), label
        assert body == {"message": "what should I sell to hikers?", "corpus_id": "cinema", "geography": "US", "model": "litellm:the-default",
                        "hypotheses": [{"title": "Dry bag", "search_terms": ["dry bag"]}], "limit_per_hypothesis": 3}, label
        assert out["product_research"] == PRODUCT_REPLY["product_research"] and out["answer"] == PRODUCT_REPLY["answer"], label
        assert len(out["evidence"]) == MR.ANSWER_HITS and len(out["evidence"][0]["text"]) == MR.ANSWER_HIT_TEXT, label
        assert out["evidence"][0]["truncated"] is True and out["phases"] == PRODUCT_REPLY["phases"], label
        bare = s.mod.product_search("find me products", "cinema", model="litellm:named")
        bare = asyncio.run(bare) if label == "A" else bare
        assert s.calls[-1][2] == {"message": "find me products", "corpus_id": "cinema", "model": "litellm:named"}, label
        anywhere = s.mod.product_search("what should I sell?")                          # owner R11: no library named
        anywhere = asyncio.run(anywhere) if label == "A" else anywhere
        assert s.calls[-1][2] == {"message": "what should I sell?", "model": "litellm:the-default"}, label   # every library you can use
    assert "corpus_id" not in MR.product_body("q", "  ") and "corpus_id" not in MR.product_body("q")
    refused = {"error": {"error_code": "CORPUS_NOT_FOUND"}, "status": 404}
    assert MR.shape_product(refused) == refused


def test_supplier_parse_proxies_the_parse_route(server_a, server_b):
    raw = "1. Dry bag 20L | US$2.10-3.40 | Min. order: 100 pieces | https://www.example.test/item/1\n"
    for label, s in (("A", server_a), ("B", server_b)):
        s.replies["/supplier/parse"] = {"status": "OK", "items": [], "sources": []}
        out = s.mod.supplier_parse(" alibaba ", raw)
        out = asyncio.run(out) if label == "A" else out
        assert s.calls[-1][:3] == ("POST", "/supplier/parse", {"site": "alibaba", "raw_text": raw}), label
        assert out == {"status": "OK", "items": [], "sources": []}, label


# ─────────────────────────────────────────────────────────── search / explore keep a product turn's keys
def test_search_and_explore_keep_product_research_and_agent_steps():
    product = {"contract": "product-search-v1", "hypotheses": [{"id": "h1"}]}
    steps = [{"step": 1, "do": "relay the answer"}]
    turn = {"meta": {"mode": "HYBRID"}, "evidence_rows": [{"id": "c1", "kind": "chunk", "text": "a"}], "evidence_packet": {"evidence": []},
            "product_research": product, "agent_steps": steps, "phases": [{"stage": "x"}]}
    for shaped in (MR.shape_search(turn, 5), MR.shape_explore(turn)):
        assert shaped["product_research"] == product and shaped["agent_steps"] == steps
        assert "phases" not in shaped
    plain = {k: v for k, v in turn.items() if k not in MR.PRODUCT_KEYS}
    for shaped in (MR.shape_search(plain, 5), MR.shape_explore(plain)):
        assert not set(MR.PRODUCT_KEYS) & set(shaped)                                        # a library turn gains nothing


# ─────────────────────────────────────────────────────────── F15: upload_text carries the principal it is for
ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "Host": "mcp.kingsleylab.xyz",
          "User-Agent": "claude-code/2.1"}


def test_upload_text_carries_the_principal_it_is_for(monkeypatch, tmp_path):
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    raw, key = P.new_bearer()
    doc["principals"].append({"principal_id": "prn_writer", "name": "writer", "enabled": True, "revoked_at": None,
                              "scopes": sorted({*P.FRIEND_PROFILE, P.UPLOAD_TEXT}), "corpus_ids": ["fr-writer"], "adapter_ids": [],
                              "writable_corpus_ids": ["fr-writer"], "created_at": P._now_iso(), "expires_at": None, "rate_per_minute": None,
                              "keys": [key]})
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    seen: list[dict] = []
    orch = FastAPI()

    @orch.post("/upload")
    async def upload(request: Request):
        await request.body()
        seen.append({"principal": request.headers.get("x-polymath-principal"), "agent": request.headers.get("user-agent")})
        return {"run_id": "run_1", "source_name": "note.md"}
    real_client = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.ASGITransport(app=orch)}))
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    call = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "upload_text", "arguments": {"text": "hello", "corpus_id": "fr-writer", "source_name": "note.md"}}}
    with TestClient(mod.build_app()) as c:
        friend = c.post("/mcp", json=call, headers={**ACCEPT, "Authorization": f"Bearer {raw}"})
        owner = c.post("/mcp", json=call, headers={**ACCEPT, "Authorization": f"Bearer {OWNER_KEY}"})
    assert friend.status_code == 200 and owner.status_code == 200, (friend.text[:300], owner.text[:300])
    assert seen == [{"principal": "prn_writer", "agent": "claude-code/2.1"},           # the friend's upload is the friend's
                    {"principal": None, "agent": "claude-code/2.1"}]                    # the owner stays the trusted caller
    assert asyncio.run(mod.upload_text("x", "fr-writer")) == mod.NO_PRINCIPAL and len(seen) == 2      # no gate ran: nothing goes out


# ─────────────────────────────────────────────────────────── owner R11: product_search never needs a library guessed
def _gate(monkeypatch, tmp_path, principals: dict[str, dict]):
    """Server A behind its REAL gate, a registry holding `principals` (id -> record overrides), and an in-memory orchestrator that
    records what reached /product/search (with the trusted principal header)."""
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    keys = {}
    for pid, extra in principals.items():
        raw, key = P.new_bearer()
        doc["principals"].append({"principal_id": pid, "name": pid, "enabled": True, "revoked_at": None, "scopes": sorted(P.FRIEND_PROFILE),
                                  "corpus_ids": ["commerce-v1"], "adapter_ids": [], "writable_corpus_ids": [], "created_at": P._now_iso(),
                                  "expires_at": None, "rate_per_minute": None, "keys": [key], **extra})
        keys[pid] = raw
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    seen: list[dict] = []
    orch = FastAPI()

    @orch.get("/synthesizers")
    async def synthesizers():
        return CATALOG

    @orch.post("/product/search")
    async def product(request: Request):
        seen.append({"principal": request.headers.get("x-polymath-principal"), "body": await request.json()})
        return {"answer": "ideas", "product_research": {"contract": "product-search-v1"}}
    real_client = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.ASGITransport(app=orch)}))
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    return mod, keys, seen


def _call(c, key: str, arguments: dict):
    return c.post("/mcp", headers={**ACCEPT, "Authorization": f"Bearer {key}"},
                  json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "product_search", "arguments": arguments}})


def test_a_principal_may_omit_the_library_and_a_named_library_is_still_checked(monkeypatch, tmp_path):
    """The gate's own rule (mcp_principals CORPUS_OPTIONAL): no library named = allowed (the orchestrator resolves within the
    caller's grant); a named library must be in the grant — never another person's private `fr-*`, a wildcard grant included."""
    mod, keys, seen = _gate(monkeypatch, tmp_path, {"prn_friend": {"corpus_ids": ["commerce-v1", "fr-friend"]},
                                                    "prn_star": {"corpus_ids": ["*", "fr-star"]},
                                                    "prn_lister": {"scopes": ["adapter.list"]}})
    ask = "what should I sell?"
    with TestClient(mod.build_app()) as c:
        allowed = [_call(c, keys["prn_friend"], {"message": ask}), _call(c, keys["prn_friend"], {"message": ask, "corpus_id": "commerce-v1"}),
                   _call(c, keys["prn_friend"], {"message": ask, "corpus_id": "  "}), _call(c, keys["prn_star"], {"message": ask}),
                   _call(c, keys["prn_star"], {"message": ask, "corpus_id": "cinema"}),
                   _call(c, keys["prn_star"], {"message": ask, "corpus_id": "fr-star"})]
        refused = [(_call(c, keys["prn_friend"], {"message": ask, "corpus_id": "owner-private"}), "corpus_not_allowed"),
                   (_call(c, keys["prn_friend"], {"message": ask, "corpus_id": "fr-star"}), "corpus_not_allowed"),
                   (_call(c, keys["prn_star"], {"message": ask, "corpus_id": "fr-friend"}), "corpus_not_allowed"),
                   (_call(c, keys["prn_friend"], {"message": ask, "corpus_id": "*"}), "corpus_not_allowed"),
                   (_call(c, keys["prn_lister"], {"message": ask}), "insufficient_scope")]
    assert all(r.status_code == 200 for r in allowed), [r.text[:200] for r in allowed if r.status_code != 200]
    assert [s["principal"] for s in seen] == ["prn_friend"] * 3 + ["prn_star"] * 3       # the orchestrator resolves within THAT grant
    assert [s["body"].get("corpus_id") for s in seen] == [None, "commerce-v1", None, None, "cinema", "fr-star"]
    for r, reason in refused:
        assert r.status_code == 403 and r.json()["error"]["data"]["reason"] == reason, r.text[:300]
    assert len(seen) == 6                                                          # nothing refused reached the orchestrator


def test_the_texts_say_a_library_is_optional_for_product_search_only():
    from orchestrator import mcp_principals as P
    assert [t for t, (_, kind) in P.TOOL_POLICY.items() if kind == P.CORPUS_OPTIONAL] == ["product_search"]
    for text in (MR.PRODUCT_SEARCH, MR.playbook(list_tool="list_corpora", add_documents="")):
        assert "otherwise" in text and "every library you can use" in text
    assert "a 404 QUERY_SCOPE_EMPTY whose next_step names list_corpora" in MR.PRODUCT_SEARCH   # the route's real status (S3/S4)
    assert "product_search may leave it out" in MR.playbook(list_tool="list_corpora", add_documents="")
    from orchestrator.api.web_settings import connect_prompt
    assert "leave corpus_id out and every library open to me is searched" in connect_prompt("k", ["cinema"], None, url="https://x.test/mcp")


def test_capabilities_advertises_the_tools_server_a_lists():
    from orchestrator.api import capabilities as CAP
    server = _load("playbook_mcp_a_caps", "orchestrator/orchestrator/mcp_server.py").mcp
    listed = {t.name for t in asyncio.run(server.list_tools())}
    registered = {t.name for t in server._tool_manager.list_tools()}
    assert {"product_search", "supplier_parse"} <= set(CAP.MCP_TOOLS) <= listed, sorted(set(CAP.MCP_TOOLS) - listed)
    assert set(CAP.MCP_HIDDEN_TOOLS) <= registered - listed                        # (capabilities_payload() reads the DB: not here)


def test_connectors_md_gives_a_human_the_same_rules():
    doc = (ROOT / "mcp_server/CONNECTORS.md").read_text(encoding="utf-8")
    flat = _flat(doc)
    for needle in ("**Product questions → `product_search`", "otherwise leave it out and Polymath searches every library the key can use",
                   "`supplier_parse(site, raw_text)`", MR.AGENT_REACH_REPO, f"`{MR.AGENT_REACH_VERIFY}`",
                   "never an agent's built-in web search, web fetch or browser", "`agent_reach` sibling key", "distinct platforms",
                   "claude.ai, the web link", "**Supplier tools (read-only, every key).**", "a friend's key included",
                   "alibaba.com is never read on this host", "{run, what, for_each, then}"):
        assert needle in flat, needle
    assert "SearXNG" not in doc.replace("`SEARXNG_URL`, `SEARXNG_SECRET`", "") or "no longer used by the code" in doc
    assert "WHATEVER tools" not in doc and "web search, fetch, a browser" not in doc and "owner key only, read-only" not in doc
    assert not offenders(doc), offenders(doc)
