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
  * upload_text carries the principal it is for (FRIEND-JOURNEY F15);
  * PRODUCT-DECISION-REPORT-V1 (B5): both servers list product_report_start / _status / _compile / _list with one contract and one
    description, each proxies its /product/report/* route with a timeout that fits, a friend key sees and calls all four through the
    REAL gate, the descriptions and the playbook's step 7 tell the whole loop (the fetch script runs ONCE on the user's machine,
    never a built-in web tool) and the owner-approved subagent recipe per harness, and no text carries a fetch command.
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
from fastapi import FastAPI, HTTPException, Request
from polymath_shared import mcp_retrieval as MR
from polymath_shared.adapter import harness_guide as HG
from starlette.testclient import TestClient

OWNER_KEY = "owner-playbook-key-0123456789"
NEW_TOOLS = ("product_search", "supplier_parse")
#: PRODUCT-DECISION-REPORT-V1 (B5): the decision report tools, both servers
REPORT_TOOLS = ("product_report_start", "product_report_status", "product_report_compile", "product_report_list")
#: the descriptions both servers take from the ONE shared copy (MR)
SHARED = {"product_search": MR.PRODUCT_SEARCH, "supplier_parse": MR.SUPPLIER_PARSE, "supplier_search": MR.SUPPLIER_SEARCH,
          "supplier_product": MR.SUPPLIER_PRODUCT, "supplier_freight": MR.SUPPLIER_FREIGHT, "supplier_warehouses": MR.SUPPLIER_WAREHOUSES,
          "adapter_list": MR.ADAPTER_LIST, "adapter_start": MR.ADAPTER_START, "adapter_next": MR.ADAPTER_NEXT,
          "research_acquire": MR.RESEARCH_ACQUIRE,
          "product_report_start": MR.PRODUCT_REPORT_START, "product_report_status": MR.PRODUCT_REPORT_STATUS,
          "product_report_compile": MR.PRODUCT_REPORT_COMPILE, "product_report_list": MR.PRODUCT_REPORT_LIST}
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
         "6. Governed research", "7. Decision reports")


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
                       "`agent_reach`", HG.PROMPT_NAME, HG.GUIDE_URI, "a decision report (step 7)", *REPORT_TOOLS[:3]):
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
    for label in ("A", "B"):                                              # the report texts are scanned on both servers
        assert {f"server {label} tool {name}" for name in REPORT_TOOLS} <= set(texts), label
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
    heads: list = []                                                   # the extra headers each call carried (C1: X-Upload-Token)

    async def fake_orch(method, path, **kw):
        calls.append((method, path, kw.get("json"), kw.get("timeout")))
        heads.append(kw.get("headers"))
        return replies.get(path, {})
    monkeypatch.setattr(mod, "_orch", fake_orch)
    return type("A", (), {"mod": mod, "calls": calls, "replies": replies, "heads": heads})


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

    heads: list = []                                                   # the extra headers each _adapter call carried

    def fake_adapter(method, path, payload=None, timeout=None, headers=None):
        calls.append((method, path, payload, timeout))
        heads.append(headers)
        return replies.get(path, {})
    monkeypatch.setattr(mod, "_post", fake_post)
    monkeypatch.setattr(mod, "_get", fake_get)
    monkeypatch.setattr(mod, "_adapter", fake_adapter)
    return type("B", (), {"mod": mod, "calls": calls, "replies": replies, "heads": heads})


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


def test_the_texts_say_a_library_is_optional_for_product_search_and_report_start_only():
    from orchestrator import mcp_principals as P
    # PRODUCT-DECISION-REPORT-V1 (B5): a report starts like a product search (it picks its products from the libraries you can use)
    assert [t for t, (_, kind) in P.TOOL_POLICY.items() if kind == P.CORPUS_OPTIONAL] == ["product_search", "product_report_start"]
    for text in (MR.PRODUCT_SEARCH, MR.PRODUCT_REPORT_START, MR.playbook(list_tool="list_corpora", add_documents="")):
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
    assert {"product_search", "supplier_parse", *REPORT_TOOLS} <= set(CAP.MCP_TOOLS) <= listed, sorted(set(CAP.MCP_TOOLS) - listed)
    assert set(CAP.MCP_HIDDEN_TOOLS) <= registered - listed                        # (capabilities_payload() reads the DB: not here)
    assert CAP.REPORT_MCP_TOOLS == list(REPORT_TOOLS)
    # PRODUCT-DECISION-REPORT-V1 §4.6: every report route, the upload capability included
    assert {"/product/report/start", "/product/report/{report_id}/status", "/product/report/{report_id}/upload/{token}",
            "/product/report/{report_id}/compile", "/product/report/{report_id}", "/product/reports"} <= set(CAP.ENDPOINTS)
    assert MR.REPORT_START_PATH in CAP.ENDPOINTS and MR.REPORT_LIST_PATH in CAP.ENDPOINTS
    assert MR.report_path("{report_id}", "status") in CAP.ENDPOINTS and MR.report_path("{report_id}", "compile") in CAP.ENDPOINTS


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
    # PRODUCT-DECISION-REPORT-V1 (B5): section 5 gives a human the four tools, their routes and waits, and the loop
    report = _flat(doc[doc.index("## 5. Product decision reports"):])
    for needle in (*(f"`{t}(" for t in REPORT_TOOLS), "`POST /product/report/start`", "`GET /product/report/{id}/status`",
                   "`POST /product/report/{id}/compile`", "`GET /product/reports`", "Every friend key may call them",
                   "only the principal that started it, and the owner, can read it", "runs it ONCE with bash in the user's terminal",
                   "always the script of the latest answer", "never fetches them with its built-in web search, web fetch or browser",
                   "`fetch_plan.script`", "`fetch_plan.round` 2", "`rounds[].complete`", "`upload.url`", "`report_url`", "`next`",
                   "runs the latest `fetch_plan.script` once more, never more", "**One upload link per report (contract C1).**",
                   "A user with no terminal (claude.ai, the web link) compiles anyway", "need a local agent",
                   "**Where the upload link points.**", "Server A sends `upload_base`", "`local` when the MCP request came to its "
                   "loopback listener with no edge headers", "`public` for every other caller", "Server B (stdio, on the host) always "
                   "sends `local`", "`contracts/product/v1/product_report.schema.json`"):
        assert needle in report, needle
    assert "`fetch." not in report and "`fetch`" not in report                     # the route's names only (`fetch_plan`)
    waits = {"product_report_start": MR.REPORT_TIMEOUT_S["start"], "product_report_status": MR.REPORT_TIMEOUT_S["status"],
             "product_report_compile": MR.REPORT_TIMEOUT_S["compile"], "product_report_list": MR.REPORT_TIMEOUT_S["list"]}
    for name, seconds in waits.items():                                  # the table states the waits the servers really use
        row = next(line for line in doc.splitlines() if line.startswith(f"| `{name}("))
        assert f"| {int(seconds)} s" in row, (name, row)


# ─────────────────────────────────────────────────────────── PRODUCT-DECISION-REPORT-V1 (B5): the decision report tools
RID = "rpt_0123456789abcdef01234567"
#: what a fetch command looks like; it travels in the status answer's `fetch_plan` (a tool RESULT), never in a text an agent is told
FETCH_COMMAND_TOKENS = ("mcporter", "curl ", "exa.", "jina.", "r.jina", "wget ", "python3 ")
#: the routes' answers (B4b): the start / status view and the compile view
REPORT_SCHEMA = json.loads((ROOT / "contracts/product/v1/product_report.schema.json").read_text(encoding="utf-8"))
#: the start / status fields the texts name (a dotted path; `name[]` = an array's items)
STATUS_FIELDS = ("report_id", "status", "next", "round", "rounds[].round", "rounds[].packets", "rounds[].received", "rounds[].complete",
                 "fetch_plan", "fetch_plan.round", "fetch_plan.packets", "fetch_plan.script", "fetch_plan.script_sha256",
                 "fetch_plan.limits", "fetch_plan.how", "candidates.status", "candidates.items[].candidate_id", "candidates.items[].title",
                 "candidates.items[].search_terms", "host.status", "host.cj", "host.ebay", "upload.url", "upload.expires_at", "upload.via",
                 "uploads.total", "uploads.by_round", "uploads.by_source", "compiled.at", "compiled.report_url", "compiled.stale")
COMPILE_FIELDS = ("report_id", "status", "report_url", "inputs", "next", "summary[].candidate_id", "summary[].title", "summary[].offers",
                  "summary[].reference_price_usd", "summary[].channels")
CHANNEL_FIELDS = ("sell_price_usd", "margin_before_ads_usd", "margin_pct", "break_even_ad_cost_usd", "delivery", "delivery_reason")
#: the list fields PRODUCT_REPORT_LIST names (the list view is the route's own, not in the schema: checked against the route)
LIST_FIELDS = ("report_id", "status", "round", "candidates", "uploads", "compiled", "compiled_at", "report_path")


def _schema_node(node: dict) -> dict:
    """A schema node with its $ref followed and a nullable `oneOf` [null, X] reduced to X."""
    while True:
        if "$ref" in node:
            node = REPORT_SCHEMA["$defs"][node["$ref"].rsplit("/", 1)[-1]]
        elif "oneOf" in node and len([n for n in node["oneOf"] if n.get("type") != "null"]) == 1:
            node = next(n for n in node["oneOf"] if n.get("type") != "null")
        else:
            return node


def _schema_field(view: str, path: str) -> dict:
    """The schema node of `path` in `status_view` (start and status) or `compile_view`; KeyError when the contract has no such
    field (a key it requires without describing counts: `fetch_plan.how`)."""
    node = _schema_node(REPORT_SCHEMA["$defs"][view])
    for part in path.split("."):
        name = part.removesuffix("[]")
        if name not in (node.get("properties") or {}) and name in (node.get("required") or []):
            node = {}
        else:
            node = _schema_node(node["properties"][name])
        if part.endswith("[]"):
            node = _schema_node(node["items"])
    return node


def _report_texts() -> dict[str, str]:
    doc = (ROOT / "mcp_server/CONNECTORS.md").read_text(encoding="utf-8")
    from orchestrator.api import web_settings as WS
    prompts = {"connect prompt (owner, key-free)": WS.owner_prompt(["cinema"]),
               "connect prompt (friend)": WS.connect_prompt("pmk_abc", ["cinema"], "fr-fred", url="https://mcp.example.test/mcp"),
               "connect prompt (owner key)": WS.connect_prompt("k" * 24, ["cinema"], None, url="https://mcp.example.test/mcp", owner=True)}
    playbook = MR.playbook(list_tool="list_corpora", add_documents="")
    return {"start": MR.PRODUCT_REPORT_START, "status": MR.PRODUCT_REPORT_STATUS, "compile": MR.PRODUCT_REPORT_COMPILE,
            "list": MR.PRODUCT_REPORT_LIST, "playbook step 7": playbook[playbook.index("7. Decision reports"):],
            "CONNECTORS.md section 5": doc[doc.index("## 5. Product decision reports"):],
            **{k: v[v.index("8. Decision reports"):v.index('9. "insufficient_evidence"')] for k, v in prompts.items()}}


def test_both_servers_list_the_four_report_tools_with_one_contract():
    tools = {label: {t.name: t for t in asyncio.run(server.list_tools())} for label, server in _servers().items()}
    a, b = tools["A"], tools["B"]
    for name in REPORT_TOOLS:
        assert name in a and name in b, name                                         # LISTED on both (an agent is offered them)
        assert a[name].input_schema.get("properties") == b[name].input_schema.get("properties"), name     # names, types, defaults
        assert sorted(a[name].input_schema.get("required") or []) == sorted(b[name].input_schema.get("required") or []), name
        assert _flat(a[name].description) == _flat(b[name].description) == _flat(SHARED[name]), name
    start = a["product_report_start"].input_schema
    assert set(start["properties"]) == {"message", "corpus_id", "products", "channels", "ship_to", "max_products"}   # never upload_base
    assert not start.get("required")                                                 # message OR products; no library to guess
    assert [start["properties"][k].get("default") for k in ("message", "corpus_id", "products", "channels", "ship_to", "max_products")] == \
        [None, None, None, None, "US", 5]
    assert a["product_report_status"].input_schema["required"] == ["report_id"]
    assert set(a["product_report_compile"].input_schema["properties"]) == {"report_id", "verdicts"}
    assert a["product_report_compile"].input_schema["required"] == ["report_id"]
    assert not a["product_report_list"].input_schema.get("properties")
    mod = _load("playbook_mcp_a_report_names", "orchestrator/orchestrator/mcp_server.py")
    assert set(REPORT_TOOLS) <= set(mod._TOOL_NAMES)                                 # /health and the policy law read it
    from orchestrator import mcp_principals as P
    assert {t: P.TOOL_POLICY[t] for t in REPORT_TOOLS} == {"product_report_start": (P.SUPPLIER_SCOPES, P.CORPUS_OPTIONAL),
                                                           "product_report_status": (P.SUPPLIER_SCOPES, P.NONE),
                                                           "product_report_compile": (P.SUPPLIER_SCOPES, P.NONE),
                                                           "product_report_list": (P.SUPPLIER_SCOPES, P.NONE)}
    assert P.TOOL_POLICY["product_report_start"][0] == P.TOOL_POLICY["product_search"][0]        # the same scope as product_search


def test_each_report_tool_proxies_its_route_with_a_timeout_and_an_upload_base_that_fit(server_a, server_b):
    """Server A tells the route where the fetch script runs (`upload_base`: local for a caller on its loopback listener, public for
    any other); Server B (stdio, on the host) always local."""
    ideas = [{"title": " Dry bag ", "search_terms": ["dry bag 20l", " "], "junk": 1}, {"title": " "}, "not an idea",
             {"title": "Lint roller", "search_terms": "pet hair roller"}]
    for label, s, base in (("A", server_a, "public"), ("B", server_b, "local")):
        def run(call):
            return asyncio.run(call) if label == "A" else call
        s.replies[MR.REPORT_START_PATH] = {"report_id": RID, "status": "collecting", "fetch_plan": None}
        out = run(s.mod.product_report_start("what should I sell to hikers?", "cinema", products=ideas,
                                              channels=[" TikTok_US ", "shopify", "shopify", " "], ship_to=" us ", max_products=3))
        assert out == {"report_id": RID, "status": "collecting", "fetch_plan": None}, label    # passed through unchanged
        assert s.calls[-1] == ("POST", "/product/report/start",
                               {"message": "what should I sell to hikers?", "corpus_id": "cinema",
                                "products": [{"title": "Dry bag", "search_terms": ["dry bag 20l"]},
                                             {"title": "Lint roller", "search_terms": ["pet hair roller"]}],
                                "channels": ["tiktok_us", "shopify"], "ship_to": "US", "max_products": 3, "upload_base": base},
                               MR.REPORT_TIMEOUT_S["start"]), label
        run(s.mod.product_report_start("find me products to dropship"))                      # no library named: every one you can use
        assert s.calls[-1][2] == {"message": "find me products to dropship", "ship_to": "US", "max_products": 5, "upload_base": base}
        status_path = f"/product/report/{RID}/status?upload_base={base}"
        s.replies[status_path] = {"report_id": RID, "status": "collecting", "fetch_plan": {"round": 1, "script": "#!/usr/bin/env bash\n"}}
        assert run(s.mod.product_report_status(f" {RID} ")) == s.replies[status_path], label
        assert s.calls[-1] == ("GET", status_path, None, MR.REPORT_TIMEOUT_S["status"]), label
        run(s.mod.product_report_compile(RID, verdicts={"c1": " strong margin on shopify ", "c2": " ", " ": "no id"}))
        assert s.calls[-1] == ("POST", f"/product/report/{RID}/compile", {"verdicts": {"c1": "strong margin on shopify"}},
                               MR.REPORT_TIMEOUT_S["compile"]), label
        run(s.mod.product_report_compile(RID))
        assert s.calls[-1][2] == {}, label                                                   # no verdicts: Polymath's numbers only
        run(s.mod.product_report_list())
        assert s.calls[-1] == ("GET", "/product/reports", None, MR.REPORT_TIMEOUT_S["list"]), label
        before = len(s.calls)
        for bad in ("../../adapter/adr_1/cancel", f"{RID}/../../reports", f"{RID}?owner=1", "rpt_short", "", None):
            for tool in (s.mod.product_report_status, s.mod.product_report_compile):
                refused = run(tool(bad))
                assert refused["status"] == 422 and refused["error"].startswith("REPORT_ID_INVALID"), (label, bad)
        assert len(s.calls) == before, label                                                 # a bad id never reaches a route path
    here = server_a.mod._CALLER_IS_LOCAL.set(True)                                          # the gate saw the loopback listener
    try:
        asyncio.run(server_a.mod.product_report_start("q"))
        assert server_a.calls[-1][2]["upload_base"] == "local"
        asyncio.run(server_a.mod.product_report_status(RID))
        assert server_a.calls[-1][1] == f"/product/report/{RID}/status?upload_base=local"
    finally:
        server_a.mod._CALLER_IS_LOCAL.reset(here)
    assert server_b.mod.UPLOAD_BASE == "local"
    assert MR.REPORT_TIMEOUT_S["start"] <= 60 and MR.REPORT_TIMEOUT_S["compile"] == 120      # start is quick; compile <= 120 s
    assert max(MR.REPORT_TIMEOUT_S["status"], MR.REPORT_TIMEOUT_S["list"]) <= 30


def test_the_report_bodies_carry_only_the_route_keys():
    body = MR.report_start_body(None, "  ", products=[{"title": "x", "search_terms": None, "problem": "invented"}], channels=None,
                                ship_to=None, max_products=None)
    assert body == {"products": [{"title": "x", "search_terms": []}], "ship_to": "US"}
    assert MR.report_start_body("q", ship_to="", max_products="8") == {"message": "q", "ship_to": "US", "max_products": 8}
    for base in MR.REPORT_UPLOAD_BASES:
        assert MR.report_start_body("q", upload_base=base)["upload_base"] == base
        assert MR.report_status_path(RID, base) == f"/product/report/{RID}/status?upload_base={base}"
    for bad in (None, "", "LOCAL", "elsewhere", "public&x=1"):
        assert "upload_base" not in MR.report_start_body("q", upload_base=bad) and MR.report_status_path(RID, bad) == f"/product/report/{RID}/status"
    assert MR.REPORT_UPLOAD_BASES == tuple(_schema_field("status_view", "upload.via")["enum"])          # the route's two answers
    assert MR.report_compile_body(None) == {} == MR.report_compile_body(["c1", "ok"]) == MR.report_compile_body({"c1": ""})
    assert MR.report_compile_body({"c1": "ok", 7: "seven"}) == {"verdicts": {"c1": "ok", "7": "seven"}}
    assert MR.normalize_report_id(RID) == RID and MR.normalize_report_id(f"\t{RID}\n") == RID
    for bad in ("rpt_" + "a" * 23, "rpt_" + "a" * 25, "rpt_" + "g" * 24, RID.upper(), "RPT_0123456789abcdef01234567", 7, None):
        assert MR.normalize_report_id(bad) is None, bad                                       # report_store.REPORT_ID_RE's form only
    from polymath_shared.product_search import report_store
    assert MR.REPORT_ID.pattern == report_store.REPORT_ID_RE.pattern.strip("^$") == REPORT_SCHEMA["$defs"]["report_id"]["pattern"].strip("^$")
    assert MR.REPORT_CHANNELS == tuple(REPORT_SCHEMA["$defs"]["channels"]["items"]["enum"])  # plan §2's channel ids, as the contract
    assert (MR.REPORT_DEFAULT_PRODUCTS, MR.REPORT_MAX_PRODUCTS, MR.REPORT_VERDICT_MAX) == (5, 8, 1200)  # plan §3 / §4.6
    assert _schema_field("compile_view", "verdicts")["additionalProperties"]["properties"]["chars"]["maximum"] == MR.REPORT_VERDICT_MAX
    assert _schema_field("status_view", "request.max_products")["maximum"] == MR.REPORT_MAX_PRODUCTS


def test_the_report_texts_name_only_the_fields_the_routes_return(monkeypatch):
    """contracts/product/v1/product_report.schema.json is the routes' answer: every response field a text names exists there with
    the values the text states; the list fields exist in the real list route's answer; no old name (`fetch`) survives."""
    for path in STATUS_FIELDS:
        _schema_field("status_view", path)
    for path in COMPILE_FIELDS:
        _schema_field("compile_view", path)
    assert set(CHANNEL_FIELDS) == set(_schema_field("compile_view", "summary[].channels")["additionalProperties"]["properties"])
    status_like = _flat(MR.PRODUCT_REPORT_STATUS + " " + MR.PRODUCT_REPORT_START)
    for path in STATUS_FIELDS:                                           # each one named in the status description, in its form
        tail = path.split(".")[-1].removesuffix("[]")
        assert f"`{path}`" in status_like or tail in status_like, path
    texts = _report_texts()
    dotted = re.compile(r"`([a-z_]+(?:\[\])?(?:\.[a-z_]+(?:\[\])?)+)`")
    # contract C1 (review fix round): `upload.token` gains `required` and `upload.mint_after`, which B4b adds to the schema in
    # parallel; until its schema says `required`, that one field is the contract's, not yet the schema's
    c1_pending = set() if "required" in _schema_field("status_view", "upload.token")["enum"] else {"upload.mint_after"}
    for where, text in texts.items():
        for path in dotted.findall(text):                               # every `a.b` a text names is a start / status field
            if path not in c1_pending:
                _schema_field("status_view", path)
        assert "`fetch." not in text and "`fetch`" not in text and "fetch.script" not in text.replace("fetch_plan.script", ""), where
    enums = {"status": "status_view", "candidates.status": "status_view", "host.status": "status_view"}
    status = _flat(MR.PRODUCT_REPORT_STATUS)
    for path, view in enums.items():
        assert " | ".join(_schema_field(view, path)["enum"]) in status, path
    delivery = [v for v in _schema_field("compile_view", "summary[].channels")["additionalProperties"]["properties"]["delivery"]["enum"] if v]
    assert " | ".join(delivery) in _flat(MR.PRODUCT_REPORT_COMPILE)
    assert set(_schema_field("status_view", "fetch_plan.round")["enum"]) == {1, 2} and "`fetch_plan.round` 2" in _flat(MR.REPORT_LOOP)
    compile_ = _flat(MR.PRODUCT_REPORT_COMPILE)
    assert all(f in compile_ for f in ("`report_url`", "`summary`", "`inputs`", "`next`", *CHANNEL_FIELDS, "reference_price_usd", "offers"))
    # the list view: the real route through its router at the loopback Host the MCP servers call (no database: the store faked)
    from contextlib import nullcontext
    from orchestrator.api import product_report as PR
    assert pathlib.Path(PR.__file__).resolve().is_relative_to(ROOT), PR.__file__
    row = {"report_id": RID, "status": "compiled", "round": 2, "created_at": None, "updated_at": None, "request": {"products_from": "caller"},
           "candidates": {"status": "ready", "items": [{"candidate_id": "c1", "title": "Dry bag"}]}, "uploads": 3, "compiled": True,
           "compiled_at": "2026-11-02T10:00:00Z", "upload_expires_at": None, "owner_principal_id": None}
    monkeypatch.setattr(PR, "tx", lambda: nullcontext(None))
    monkeypatch.setattr(PR.store, "list_for", lambda conn, principal, limit=50, before=None: [row])
    app = FastAPI()
    app.include_router(PR.router)
    with TestClient(app, base_url="http://127.0.0.1:7200") as client:
        answer = client.get(MR.REPORT_LIST_PATH)
    assert answer.status_code == 200, answer.text[:300]
    listed = answer.json()
    item = listed["reports"][0]
    assert set(LIST_FIELDS) <= set(item) and item["candidates"] == [{"candidate_id": "c1", "title": "Dry bag"}], item
    assert all(f"`{f}`" in MR.PRODUCT_REPORT_LIST for f in LIST_FIELDS) and "newest first" in MR.PRODUCT_REPORT_LIST


def test_no_report_text_asks_an_agent_to_resend_a_token():
    """The MCP servers hold a report's upload token and send it back themselves (contract C1), and the runnable script is in the
    latest answer: no agent-facing text tells an agent to keep, resend or paste a token or to send the header itself; the
    status text says the agent never handles one (CONNECTORS.md, for humans, may name the header the servers send)."""
    for where, text in _report_texts().items():
        low = _flat(text).lower()
        for wrong in ("send the token", "send the held token", "resend", "paste the token", "keep the token"):
            assert wrong not in low, (where, wrong)
        if where != "CONNECTORS.md section 5":
            assert "x-upload-token" not in low and "upload_token" not in low, where
        assert "latest answer" in low or where in ("compile", "list"), where                 # the run instruction: the latest script
    assert "you never handle a token" in _flat(MR.PRODUCT_REPORT_STATUS)


def test_the_report_descriptions_tell_the_whole_loop_in_order():
    start = _flat(MR.PRODUCT_REPORT_START)
    loop = ("Every answer carries `next`", "follow it", "(1) product_report_start -> `report_id`",
            "(2) While `fetch_plan` is null", "`candidates.status` collecting", "product_report_status(report_id) again as `next` says",
            "(3) Save `fetch_plan.script` unchanged to a file", "`fetch_plan.script_sha256`", "run it ONCE with bash in the user's terminal",
            "always the script of the latest answer", "let it finish before you call status", "uploads each raw output to `upload.url` itself",
            "Do not read the pages into the conversation", "(4) Call product_report_status", "`rounds[].complete`",
            "if a finished run left its round incomplete (`rounds[].received` below `rounds[].packets`), run the latest "
            "`fetch_plan.script` once more, never more", "`fetch_plan.round` 2",
            "run it ONCE the same way", "(5) When every `rounds[].complete` is true and `host.status` is done or failed",
            "product_report_compile(report_id) -> `report_url` and `summary`", "(6) Optional: write a short verdict per product from `summary`",
            "call product_report_compile(report_id, verdicts) again", "(7) Share `report_url` with the user",
            "No terminal on the user's side", "compile once `host.status` is done or failed", "need a local agent")
    at = [start.index(step) for step in loop]
    assert at == sorted(at), [s for s, i in zip(loop, at)]
    assert at[-1] < start.index("Arguments:") < start.index("Subagents")              # the loop first: a clipped text keeps it
    assert start.index("product_report_start ->") < 700
    for text in (start, _flat(MR.PRODUCT_REPORT_STATUS), _flat(MR.REPORT_LOOP)):
        assert MR.NO_BUILT_IN_WEB in text and "into the conversation" in text and "ONCE" in text
    assert _flat(MR.LOCAL_AGENT_REACH) in start and MR.AGENT_REACH_REPO in start and f"`{MR.AGENT_REACH_VERIFY}`" in start
    assert "otherwise leave it out and Polymath searches every library you can use" in start
    assert all(c in start for c in MR.REPORT_CHANNELS) and "ship_to = US" in start and "Reports are private" in start
    assert all(code in start for code in ("MESSAGE_REQUIRED", "BAD_PRODUCTS", "BAD_SHIP_TO", "UNKNOWN_CHANNEL"))   # the route's 422s
    status = _flat(MR.PRODUCT_REPORT_STATUS)
    for needle in ("`fetch_plan` {round, packets, script, script_sha256, limits, how} (null until the candidates are ready)",
                   "`rounds` [{round, packets, received, complete}]", "`upload` {url, expires_at, via: local = the Polymath host only, "
                   "public = any machine, token, mint_after}", "`uploads` {total, by_round, by_source}", "`compiled` {at, report_url, stale}",
                   "and `next`: one sentence saying what to do now; follow it", "always the script of the latest answer",
                   "ONCE (once more only if a finished run left its round incomplete)",
                   "A NEW `fetch_plan.round` (2) is the next round", "when every `rounds[].complete` is true and `host.status` is done "
                   "or failed, call product_report_compile"):
        assert needle in status, needle
    compile_ = _flat(MR.PRODUCT_REPORT_COMPILE)
    for needle in ("PASS | WARN | FAIL | UNKNOWN", "never a guess",
                   "Returns `report_url` (share it with the user: it opens in a browser signed in to Polymath)", "up to 2 minutes",
                   f"at most {MR.REPORT_VERDICT_MAX} characters", "written from `summary`", "compile again with them",
                   "CANDIDATES_PENDING, HOST_DATA_PENDING", "compile anyway", "need a local agent"):
        assert needle in compile_, needle
    assert "private" in MR.PRODUCT_REPORT_LIST and "product_report_status" in MR.PRODUCT_REPORT_LIST


def test_the_playbook_gains_the_report_step_on_both_servers():
    for label, server in _servers().items():
        text = server.instructions
        step = _flat(text[text.index("7. Decision reports"):])
        for needle in ("product_report_start(message or products; corpus_id optional)", "while `fetch_plan` is null, call "
                       "product_report_status(report_id) as `next` says", "save `fetch_plan.script` to a file and run it ONCE with bash "
                       "in the user's terminal, always the latest answer's script", "uploads the raw output to `upload.url` itself",
                       "a round left incomplete: its latest script once more, never more",
                       "never read the pages into the conversation", MR.NO_BUILT_IN_WEB, "a new `fetch_plan.round` (2)",
                       "when every `rounds[].complete` is true, product_report_compile(report_id)",
                       "optionally a short verdict per product from its `summary`", "product_report_compile(report_id, verdicts) -> "
                       "share `report_url`", "Every answer's `next` says what to do now", "No terminal: compile anyway",
                       "Subagents never fetch", "cheap model at low effort", "product_report_start's description has the recipe"):
            assert needle in step, (label, needle)
        three = _flat(text[text.index("3. Product questions"):text.index("4. Live web")])
        assert "OFFER the full governed run (step 6) or a decision report (step 7); never start it unasked" in three, label


def test_every_connect_prompt_gains_one_step_on_the_report_tools():
    """web_settings.usage_lines (the owner's key-free prompt, a friend's prompt, the owner-key prompt): ONE numbered step on the
    report tools, the playbook's step 7 in the user's voice; the closing insufficient_evidence rule moves to 9."""
    from orchestrator.api import web_settings as WS
    assert pathlib.Path(WS.__file__).resolve().is_relative_to(ROOT), WS.__file__
    for where, text in _report_texts().items():
        if not where.startswith("connect prompt"):
            continue
        full = {"connect prompt (owner, key-free)": WS.owner_prompt(["cinema"]),
                "connect prompt (friend)": WS.connect_prompt("pmk_abc", ["cinema"], "fr-fred", url="https://mcp.example.test/mcp"),
                "connect prompt (owner key)": WS.connect_prompt("k" * 24, ["cinema"], None, url="https://mcp.example.test/mcp",
                                                                owner=True)}[where]
        lines = [ln for ln in full.splitlines() if "product_report_" in ln]
        assert len(lines) == 1 and lines[0].startswith("8. Decision reports"), (where, lines)       # one line
        assert full.index("7. The supplier") < full.index("8. Decision reports") < full.index('9. "insufficient_evidence"'), where
        for needle in ("product_report_start", "every answer's `next` says what to do now", "fetch_plan.script", "run it ONCE with bash",
                       "always the latest answer's script", "never read the pages into the chat", "product_report_status after it finishes",
                       "fetch_plan.round 2", "rounds[].complete", "product_report_compile returns report_url", "candidate_id",
                       "give me report_url", "With no terminal, compile anyway"):
            assert needle in text, (where, needle)
        assert not offenders(full), (where, offenders(full))


#: the owner-approved subagent recipe (plan §4.7): the same words in the start description and CONNECTORS.md
RECIPE = ("fetching is the script's job, never a subagent's", "cheap model at low effort", "inherited defaults are the expensive trap",
          "inherits the parent's top model and effort", "claude code", "haiku 5.5 at effort low", "websearch and webfetch disallowed",
          "sonnet 5.5 or opus 5.5 at effort high", "codex", "gpt-6 luna at low reasoning effort", "gpt-6.1 sol at high",
          "`tool_timeout_sec`", "above 120", "hermes", "deepseek-v4.1-flash with thinking off", "5 children at most",
          "runs agent reach in the terminal, never its own web tool (that is not agent reach)", "opencode",
          "`opencode run --auto`", "no polymath mcp server is configured there by default", "mcp timeout")


def test_the_subagent_recipe_is_the_owner_approved_one_in_the_description_and_connectors_md():
    doc = (ROOT / "mcp_server/CONNECTORS.md").read_text(encoding="utf-8")
    copies = {"description": _flat(MR.PRODUCT_REPORT_START).lower(),
              "CONNECTORS.md": _flat(doc[doc.index("## 5. Product decision reports"):]).lower()}
    for where, text in copies.items():
        for needle in RECIPE:
            assert needle in text, (where, needle)
        assert "for judgment" in text and "one per product writing its verdict" in text, where


def test_no_report_text_carries_a_fetch_command_or_points_at_an_agents_own_web_tools():
    """The fetch script's commands travel in the status answer (`fetch_plan`), never in what an agent is told; the operating guide
    stays command-free and harness-neutral as before."""
    texts = {**_report_texts(), "playbook": MR.playbook(list_tool="list_corpora", add_documents=""), "guide": HG.GUIDE,
             "prompt description": HG.PROMPT_DESCRIPTION}
    for where, text in texts.items():
        low = text.lower()
        assert not [t for t in FETCH_COMMAND_TOKENS if t in low], (where, [t for t in FETCH_COMMAND_TOKENS if t in low])
        assert not offenders(text), (where, offenders(text))


def _report_world(monkeypatch, tmp_path, principals: dict[str, dict]):
    """Server A behind its REAL gate, a registry holding `principals` (id -> record overrides), and an in-memory orchestrator that
    serves the four report routes and records what reached them (with the trusted principal header and the query). A report
    another principal started answers 404, as the route's privacy rule does."""
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    keys = {}
    for pid, extra in principals.items():
        raw, key = P.new_bearer()
        doc["principals"].append({"principal_id": pid, "name": pid, "enabled": True, "revoked_at": None, "scopes": sorted(P.FRIEND_SCOPES),
                                  "profile": "friend", "corpus_ids": ["commerce-v1"], "adapter_ids": [], "writable_corpus_ids": [],
                                  "created_at": P._now_iso(), "expires_at": None, "rate_per_minute": None, "keys": [key], **extra})
        keys[pid] = raw
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    seen: list[tuple] = []
    owners = {RID: "prn_friend"}
    orch = FastAPI()

    def who(request: Request):
        return request.headers.get("x-polymath-principal")

    def mine(request: Request, report_id: str) -> None:
        if who(request) is not None and owners.get(report_id) != who(request):     # the owner (no header) sees every report
            raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")

    @orch.post("/product/report/start")
    async def start(request: Request):
        seen.append(("POST", request.url.path, who(request), await request.json()))
        return {"report_id": RID, "status": "collecting", "fetch_plan": None}

    @orch.get("/product/report/{report_id}/status")
    async def status(report_id: str, request: Request):
        seen.append(("GET", request.url.path, who(request), str(request.url.query)))
        mine(request, report_id)
        return {"report_id": report_id, "status": "collecting", "fetch_plan": {"round": 1, "script": "#!/usr/bin/env bash\n"}}

    @orch.post("/product/report/{report_id}/compile")
    async def compile_(report_id: str, request: Request):
        seen.append(("POST", request.url.path, who(request), await request.json()))
        mine(request, report_id)
        return {"report_id": report_id, "status": "compiled", "report_url": f"https://rag.example.test/product/report/{report_id}"}

    @orch.get("/product/reports")
    async def reports(request: Request):
        seen.append(("GET", request.url.path, who(request), str(request.url.query)))
        return {"reports": [{"report_id": r, "status": "compiled"} for r, o in owners.items() if who(request) in (None, o)]}
    real_client = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.ASGITransport(app=orch)}))
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    return mod, keys, seen


def _rpc(c, key: str, method: str, params: dict, host: str | None = None):
    return c.post("/mcp", headers={**ACCEPT, "Authorization": f"Bearer {key}", **({"Host": host} if host else {})},
                  json={"jsonrpc": "2.0", "id": 11, "method": method, "params": params})


def _result(resp) -> dict:
    assert resp.status_code == 200, resp.text[:300]
    body = resp.text if resp.text.lstrip().startswith("{") else [ln[5:].strip() for ln in resp.text.splitlines() if ln.startswith("data:")][-1]
    return json.loads(body)["result"]


def _tool_out(resp) -> dict:
    result = _result(resp)
    sc = result.get("structuredContent")
    return sc if isinstance(sc, dict) and "result" not in sc else json.loads(result["content"][0]["text"])


def test_a_friend_key_sees_and_calls_the_four_report_tools_through_the_real_gate(monkeypatch, tmp_path):
    mod, keys, seen = _report_world(monkeypatch, tmp_path, {"prn_friend": {"corpus_ids": ["commerce-v1", "fr-friend"]},
                                                            "prn_lister": {"scopes": ["adapter.list"], "profile": None}})
    friend, lister = keys["prn_friend"], keys["prn_lister"]
    loopback = f"127.0.0.1:{mod.PORT}"

    def call(key, name, arguments, host=None):
        return _rpc(c, key, "tools/call", {"name": name, "arguments": arguments}, host)
    with TestClient(mod.build_app()) as c:
        listed = {t["name"] for t in _result(_rpc(c, friend, "tools/list", {}))["tools"]}
        assert set(REPORT_TOOLS) <= listed                                            # a friend is OFFERED all four
        assert not set(REPORT_TOOLS) & {t["name"] for t in _result(_rpc(c, lister, "tools/list", {}))["tools"]}
        started = _tool_out(call(friend, "product_report_start", {"message": "what should I sell to hikers?", "max_products": 3}))
        named = _tool_out(call(friend, "product_report_start", {"message": "x", "corpus_id": "fr-friend"}))
        status = _tool_out(call(friend, "product_report_status", {"report_id": RID}))
        compiled = _tool_out(call(friend, "product_report_compile", {"report_id": RID, "verdicts": {"c1": "good margin"}}))
        mine = _tool_out(call(friend, "product_report_list", {}))
        theirs = _tool_out(call(friend, "product_report_status", {"report_id": "rpt_" + "f" * 24}))
        refused = [(call(friend, "product_report_start", {"message": "x", "corpus_id": "owner-private"}), "corpus_not_allowed"),
                   (call(friend, "product_report_start", {"message": "x", "corpus_id": "*"}), "corpus_not_allowed"),
                   *[(call(lister, name, args), "insufficient_scope") for name, args in
                     (("product_report_start", {"message": "x"}), ("product_report_status", {"report_id": RID}),
                      ("product_report_compile", {"report_id": RID}), ("product_report_list", {}))]]
        owner = _tool_out(call(OWNER_KEY, "product_report_list", {}))
        here = _tool_out(call(OWNER_KEY, "product_report_start", {"products": [{"title": "Dry bag"}]}, host=loopback))   # on this host
        here_status = _tool_out(call(OWNER_KEY, "product_report_status", {"report_id": RID}, host=loopback))
        edge = _tool_out(call(OWNER_KEY, "product_report_status", {"report_id": RID}))   # the owner through the public host
    assert started["report_id"] == RID and named["status"] == "collecting" and status["fetch_plan"]["round"] == 1
    assert compiled["report_url"].endswith(RID) and [r["report_id"] for r in mine["reports"]] == [RID]
    assert theirs == {"error": "REPORT_NOT_FOUND", "status": 404}                     # another's report: the route's refusal, passed on
    assert owner["reports"] == [{"report_id": RID, "status": "compiled"}] and here["report_id"] == RID
    assert here_status["status"] == edge["status"] == "collecting"
    for resp, reason in refused:
        assert resp.status_code == 403 and resp.json()["error"]["data"]["reason"] == reason, resp.text[:300]
    assert seen == [("POST", "/product/report/start", "prn_friend",
                     {"message": "what should I sell to hikers?", "ship_to": "US", "max_products": 3, "upload_base": "public"}),
                    ("POST", "/product/report/start", "prn_friend",
                     {"message": "x", "corpus_id": "fr-friend", "ship_to": "US", "max_products": 5, "upload_base": "public"}),
                    ("GET", f"/product/report/{RID}/status", "prn_friend", "upload_base=public"),     # another machine: the public door
                    ("POST", f"/product/report/{RID}/compile", "prn_friend", {"verdicts": {"c1": "good margin"}}),
                    ("GET", "/product/reports", "prn_friend", ""),
                    ("GET", "/product/report/rpt_ffffffffffffffffffffffff/status", "prn_friend", "upload_base=public"),
                    ("GET", "/product/reports", None, ""),
                    ("POST", "/product/report/start", None,                                          # the loopback listener: local
                     {"products": [{"title": "Dry bag", "search_terms": []}], "ship_to": "US", "max_products": 5, "upload_base": "local"}),
                    ("GET", f"/product/report/{RID}/status", None, "upload_base=local"),
                    ("GET", f"/product/report/{RID}/status", None, "upload_base=public")]           # nothing refused reached it


def test_the_upload_base_the_servers_send_is_the_one_the_routes_read_and_it_picks_the_upload_url(monkeypatch):
    """The other half of the gate test above: the routes read `upload_base` from the start body and the status query (the names
    the servers send), accept exactly the two words, and pick the upload URL's base by it: `local` = this host's orchestrator,
    `public` = the public web door (an agent on another machine)."""
    import inspect
    import typing

    from orchestrator.api import product_report as PR
    from pydantic import ValidationError
    from starlette.requests import Request as StarletteRequest
    assert pathlib.Path(PR.__file__).resolve().is_relative_to(ROOT), PR.__file__
    assert set(typing.get_args(typing.get_args(PR.ReportStartRequest.model_fields["upload_base"].annotation)[0])) == set(MR.REPORT_UPLOAD_BASES)
    for base in MR.REPORT_UPLOAD_BASES:
        assert PR.ReportStartRequest(**MR.report_start_body("q", upload_base=base)).upload_base == base
    with pytest.raises(ValidationError):
        PR.ReportStartRequest(message="q", upload_base="elsewhere")
    assert "upload_base" in inspect.signature(PR.product_report_status).parameters                 # a query parameter of status
    status_hint = typing.get_type_hints(PR.product_report_status)["upload_base"]                       # Literal[...] | None
    assert {v for arg in typing.get_args(status_hint) for v in typing.get_args(arg)} == set(MR.REPORT_UPLOAD_BASES)
    monkeypatch.setenv("POLYMATH_PUBLIC_URL", "https://rag.example.test")
    monkeypatch.delenv("POLYMATH_ORCH_URL", raising=False)
    plain = StarletteRequest({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})
    assert PR.upload_target(plain, "public")[:2] == ("public", "https://rag.example.test")       # another machine: the public door
    assert PR.upload_target(plain, "local")[:2] == ("local", "http://127.0.0.1:7200")          # this host


# ─────────────────────────────────────────────────────────── review fix round (CONTRACTS C1, C7, C8, C9)
TOKEN_A, TOKEN_B = "A" * 43, "b_-" + "c" * 40


def _upload_answer(state: str, url_token: str | None = None, report_id: str = RID, **upload) -> dict:
    url = f"http://127.0.0.1:7200/product/report/{report_id}/upload/{url_token or 'UPLOAD_TOKEN'}"
    return {"report_id": report_id, "status": "collecting", "upload": {"url": url, "token": state, **upload},
            "next": "Run round 1's fetch script (fetch_plan.script, one shell command) on the user's machine."}


def test_the_upload_token_is_taken_from_start_or_a_minted_status_only():
    start = {**_upload_answer("minted", TOKEN_A), "upload_token": TOKEN_A}
    assert MR.report_token_from(start, RID) == TOKEN_A
    assert MR.report_token_from(_upload_answer("minted", TOKEN_B), RID) == TOKEN_B                # parsed from upload.url
    for state in ("reused", "required", "expired", "none"):
        assert MR.report_token_from(_upload_answer(state, TOKEN_B), RID) is None, state             # nothing new to keep
    assert MR.report_token_from(_upload_answer("minted"), RID) is None                             # the placeholder is never kept
    assert MR.report_token_from(_upload_answer("minted", TOKEN_B, report_id="rpt_" + "f" * 24), RID) is None   # another report's
    broken = _upload_answer("minted", TOKEN_B)
    broken["upload"]["url"] += "?x=1"
    assert MR.report_token_from(broken, RID) is None and MR.report_token_from({"upload_token": "short"}) is None
    assert MR.report_token_from({"error": "refused", "status": 409, "upload_token": TOKEN_A}) is None
    assert MR.REPORT_TOKEN_STATES == ("minted", "reused", "required", "expired", "none")            # contract C1's five values
    assert set(_schema_field("status_view", "upload.token")["enum"]) <= set(MR.REPORT_TOKEN_STATES)  # every value the route sends
    from polymath_shared.product_search import report_store
    assert MR._UPLOAD_TOKEN.pattern == report_store.TOKEN_RE.pattern.strip("^$")                   # the form the store mints


def test_the_token_cache_holds_256_reports_drops_the_least_recently_used_and_forgets_an_expired_token():
    cache = MR.ReportTokens()
    assert cache.cap == MR.REPORT_TOKEN_CACHE_MAX == 256
    for i in range(257):
        cache.remember(("prn_x", f"r{i}"), {"upload_token": f"{i:043d}"})
    assert len(cache) == 256 and cache.get(("prn_x", "r0")) is None and cache.get(("prn_x", "r256")) == f"{256:043d}"
    assert cache.get(("prn_x", "r1")) == f"{1:043d}"                                            # used now: kept over r2
    cache.remember(("prn_x", "new"), {"upload_token": "n" * 43})
    assert cache.get(("prn_x", "r1")) and cache.get(("prn_x", "r2")) is None and len(cache) == 256
    cache.remember(("prn_x", "new"), _upload_answer("required", mint_after="2026-11-02T18:01:00Z"))   # changes nothing
    assert cache.headers(("prn_x", "new")) == {MR.REPORT_TOKEN_HEADER: "n" * 43} and MR.REPORT_TOKEN_HEADER == "X-Upload-Token"
    cache.remember(("prn_x", "new"), _upload_answer("expired"))
    assert cache.get(("prn_x", "new")) is None and cache.headers(("prn_x", "new")) == {}


def test_both_servers_send_the_held_token_on_every_status_call_server_a_per_principal(server_a, server_b):
    from orchestrator import mcp_principals as P
    for label, s, base in (("A", server_a, "public"), ("B", server_b, "local")):
        def run(call):
            return asyncio.run(call) if label == "A" else call
        path = f"/product/report/{RID}/status?upload_base={base}"
        s.replies[MR.REPORT_START_PATH] = {**_upload_answer("minted", TOKEN_A), "upload_token": TOKEN_A}
        run(s.mod.product_report_start("what should I sell?"))
        s.replies[path] = _upload_answer("reused", TOKEN_A)
        run(s.mod.product_report_status(RID))
        assert s.heads[-1] == {"X-Upload-Token": TOKEN_A}, label                                   # the token start handed out
        s.replies[path] = _upload_answer("minted", TOKEN_B)                                        # a held token the route refused
        run(s.mod.product_report_status(RID))
        assert s.heads[-1] == {"X-Upload-Token": TOKEN_A}, label
        s.replies[path] = _upload_answer("reused", TOKEN_B)
        run(s.mod.product_report_status(RID))
        assert s.heads[-1] == {"X-Upload-Token": TOKEN_B}, label                                   # ... is replaced by the new one
        s.replies[path] = _upload_answer("expired")
        run(s.mod.product_report_status(RID))
        run(s.mod.product_report_status(RID))
        assert not s.heads[-1], label                                                              # an expired token is never sent
    # Server A holds tokens per principal AND report: another principal never sends (or learns) this one's token
    a = server_a
    a.replies[MR.REPORT_START_PATH] = {**_upload_answer("minted", TOKEN_A), "upload_token": TOKEN_A}
    asyncio.run(a.mod.product_report_start("q"))
    other = a.mod._PRINCIPAL.set(P.Principal(principal_id="prn_other"))
    try:
        asyncio.run(a.mod.product_report_status(RID))
        assert not a.heads[-1]
    finally:
        a.mod._PRINCIPAL.reset(other)
    asyncio.run(a.mod.product_report_status(RID))
    assert a.heads[-1] == {"X-Upload-Token": TOKEN_A}


def test_a_required_answer_says_plainly_when_to_call_status_again_and_next_passes_through(server_a, server_b):
    """C1 `required` adds `upload_note` in plain words; C9: the route's `next` (a stalled compile: "compile again") is never
    rewritten; every other key passes through as the route sent it."""
    when = "2026-11-02T18:01:00Z"
    stalled = {**_upload_answer("required", mint_after=when), "status": "compiling",
               "next": "The compile started more than 300 s ago and did not finish: call product_report_compile again."}
    for label, s, base in (("A", server_a, "public"), ("B", server_b, "local")):
        def run(call):
            return asyncio.run(call) if label == "A" else call
        path = f"/product/report/{RID}/status?upload_base={base}"
        s.replies[path] = stalled
        out = run(s.mod.product_report_status(RID))
        assert out["next"] == stalled["next"] and {k: v for k, v in out.items() if k != "upload_note"} == stalled, label
        assert out["upload_note"] == (f"No fetch script to run in this answer: this report handed out an upload link less than a "
                                      f"minute ago and this connection does not hold it. Call product_report_status {RID} again "
                                      f"after {when} and run that answer's script; never run an older or placeholder script in its "
                                      f"place."), label
        for state in ("minted", "reused", "expired", "none"):                                       # only `required` gets a note
            s.replies[path] = _upload_answer(state, TOKEN_A if state in ("minted", "reused") else None)
            assert "upload_note" not in run(s.mod.product_report_status(RID)), (label, state)


def test_report_job_running_becomes_one_plain_sentence(server_a, server_b):
    busy = {"error": {"error_code": "REPORT_JOB_RUNNING", "message": "this principal already has a report job running",
                      "retry_after_s": 42, "report_id": RID}, "status": 429}
    for label, s in (("A", server_a), ("B", server_b)):
        s.replies[MR.REPORT_START_PATH] = busy
        out = s.mod.product_report_start("what should I sell?")
        out = asyncio.run(out) if label == "A" else out
        assert out == {"error": f"a report is still being prepared; check product_report_status {RID} or wait 42 s, then start again",
                       "error_code": "REPORT_JOB_RUNNING", "status": 429, "report_id": RID, "retry_after_s": 42}, label
    bare = MR.shape_report({"error": {"error_code": "REPORT_JOB_RUNNING", "retry_after_s": "soon"}, "status": 429})
    assert bare["error"] == "a report is still being prepared; check product_report_list or wait a minute, then start again"
    for other in ({"error": {"error_code": "SUPPLIER_RATE_LIMITED"}, "status": 429}, {"error": "busy", "status": 429},
                  {"error": {"error_code": "REPORT_JOB_RUNNING"}, "status": 409}):
        assert MR.shape_report(other) == other                                                       # anything else unchanged


def test_the_texts_tell_every_token_state_the_signed_in_link_the_busy_start_and_the_stalled_compile():
    status = _flat(MR.PRODUCT_REPORT_STATUS)
    for state, meaning in (("minted", "a new link, now held here"), ("reused", "the held link (the script runs as given)"),
                           ("required", "this answer has no script to run"), ("expired", "the upload time ran out: compile with what"),
                           ("none", "no fetch plan yet")):
        assert f"{state} = {meaning}" in status, state
    assert "required = this answer has no script to run (`fetch_plan.script` is null: the report handed out a link less than a " \
           "minute ago, not to this connection): call product_report_status again after `upload.mint_after`, and never run an " \
           "older or placeholder script in its place" in status
    assert "This server keeps each report's upload token and sends it back on every status call" in status
    texts = _report_texts()
    for where in ("start", "compile", "playbook step 7", "CONNECTORS.md section 5", "connect prompt (owner, key-free)",
                  "connect prompt (friend)", "connect prompt (owner key)"):
        assert "opens in a browser signed in to Polymath" in _flat(texts[where]), where           # C7
    assert "If an answer's `fetch_plan.script` is null (`upload.token` required), it has no script: call status again after " \
           "`upload.mint_after`, and never run an older or placeholder script in its place" in _flat(MR.REPORT_LOOP)
    assert "`fetch_plan.script` null, `upload.token` required: that answer has no script, so call status again after " \
           "`upload.mint_after` and never run an older or placeholder script" in _flat(texts["playbook step 7"])
    start = _flat(MR.PRODUCT_REPORT_START)
    assert "429 REPORT_JOB_RUNNING: a report of yours is still being prepared, so check product_report_status for the report it " \
           "names or wait the seconds it gives, then start again" in start                         # C8
    assert "COMPILE_IN_PROGRESS) = call status first and do what its `next` says (a compile that stalled says compile again)" in \
        _flat(MR.PRODUCT_REPORT_COMPILE)                                                            # C9
    doc = _flat(texts["CONNECTORS.md section 5"])
    for needle in ("**One upload link per report (contract C1).**", "Server A per principal and report, Server B per report",
                   "at most 256 reports, the least recently used dropped first", "`minted`: a new link", "`reused`: the held link",
                   "`required`: the answer has no script to run (`fetch_plan.script` is null, and the answer says why)",
                   "call `product_report_status` again after `upload.mint_after`",
                   "`expired`: the report's upload time ran out", "`none`: no fetch plan yet", "429 `REPORT_JOB_RUNNING`",
                   "a report is still being prepared; check product_report_status <id> or wait <retry_after_s> s",
                   "the tools pass `next` through unchanged"):
        assert needle in doc, needle


def test_through_the_real_gate_status_calls_carry_the_principals_own_held_token(monkeypatch, tmp_path):
    """C1 end to end on Server A: the token start handed a friend travels back on the friend's status calls; the owner's call for
    the same report holds none, gets `required`, and is told in plain words when to call again."""
    from orchestrator import mcp_principals as P
    P = importlib.reload(P)
    registry = tmp_path / "principals.json"
    doc = P.read_registry(registry)
    raw, key = P.new_bearer()
    doc["principals"].append({"principal_id": "prn_friend", "name": "friend", "enabled": True, "revoked_at": None, "profile": "friend",
                              "scopes": sorted(P.FRIEND_SCOPES), "corpus_ids": ["commerce-v1"], "adapter_ids": [],
                              "writable_corpus_ids": [], "created_at": P._now_iso(), "expires_at": None, "rate_per_minute": None,
                              "keys": [key]})
    P.write_registry(registry, doc)
    monkeypatch.setenv("POLYMATH_MCP_API_KEY", OWNER_KEY)
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(registry))
    from orchestrator import mcp_server
    mod = importlib.reload(mcp_server)
    seen: list[tuple] = []
    when = "2026-11-02T18:01:00Z"
    orch = FastAPI()

    @orch.post("/product/report/start")
    async def start(request: Request):
        await request.json()
        return {**_upload_answer("minted", TOKEN_A), "upload_token": TOKEN_A}

    @orch.get("/product/report/{report_id}/status")
    async def status(report_id: str, request: Request):
        sent = request.headers.get("x-upload-token")
        seen.append((request.headers.get("x-polymath-principal"), sent))
        return _upload_answer("reused", TOKEN_A) if sent == TOKEN_A else _upload_answer("required", mint_after=when)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.ASGITransport(app=orch)}))
    monkeypatch.setattr(mod, "ORCH", "http://orchestrator.test")
    with TestClient(mod.build_app()) as c:
        _tool_out(_rpc(c, raw, "tools/call", {"name": "product_report_start", "arguments": {"message": "what should I sell?"}}))
        first = _tool_out(_rpc(c, raw, "tools/call", {"name": "product_report_status", "arguments": {"report_id": RID}}))
        again = _tool_out(_rpc(c, raw, "tools/call", {"name": "product_report_status", "arguments": {"report_id": RID}}))
        owner = _tool_out(_rpc(c, OWNER_KEY, "tools/call", {"name": "product_report_status", "arguments": {"report_id": RID}}))
    assert seen == [("prn_friend", TOKEN_A), ("prn_friend", TOKEN_A), (None, None)]
    assert first["upload"]["token"] == again["upload"]["token"] == "reused" and "upload_note" not in again
    assert owner["upload"]["token"] == "required" and f"again after {when}" in owner["upload_note"]


# ─────────────────────────────────────────────────────────── review fix round 2: an answer may carry no script (R3 verify NEW-2)
def test_an_answer_without_a_script_sends_the_agent_back_to_status_never_to_an_older_script():
    """A `required` answer carries `fetch_plan.script = null` (B4b) instead of a script that cannot upload. Every agent-facing text
    that says "the latest answer's script" says what to do when that answer has none: call product_report_status again after
    `upload.mint_after`, and never run an older script (or one whose link is a placeholder) in its place."""
    texts = _report_texts()
    needles = {
        "status": ("always the script of the latest answer that carries one (a null `fetch_plan.script`: call status again after "
                   "`upload.mint_after`)", "`fetch_plan.script` is null", "never run an older or placeholder script in its place"),
        "start": ("always the script of the latest answer that carries one", "If an answer's `fetch_plan.script` is null",
                  "never run an older or placeholder script in its place"),
        "playbook step 7": ("always the latest answer's script when it carries one", "`fetch_plan.script` null",
                            "never run an older or placeholder script"),
        "CONNECTORS.md section 5": ("always the script of the latest answer that carries one", "When an answer's `fetch_plan.script` is "
                                    "null", "never runs an older or placeholder script in its place"),
    }
    for where, wanted in needles.items():
        flat = _flat(texts[where])
        for needle in wanted:
            assert needle in flat, (where, needle)
    for where, text in texts.items():
        if where.startswith("connect prompt"):
            line = next(ln for ln in text.splitlines() if "product_report_" in ln)
            rule, exception = "always the latest answer's script", ("when an answer's fetch_plan.script is null it has no script, so "
                                                                    "call product_report_status again after its upload.mint_after and "
                                                                    "never run an older script with a placeholder link instead")
            assert rule in line and exception in line and line.index(rule) < line.index(exception), where   # the same step, in order
        flat = _flat(text).lower()
        if "latest answer" in flat:                                      # no unqualified "always the latest script" survives
            assert "null" in flat and "mint_after" in flat, where
    for label, server in _servers().items():                           # the servers serve exactly these texts
        step = _flat(server.instructions[server.instructions.index("7. Decision reports"):])
        assert "never run an older or placeholder script" in step, label
    withheld = {**_upload_answer("required", mint_after="2026-11-02T18:01:00Z"),
                "fetch_plan": {"round": 1, "packets": [], "script": None, "script_sha256": None, "limits": {}, "how": {}}}
    shaped = MR.shape_report(withheld)
    assert shaped["fetch_plan"] == withheld["fetch_plan"] and shaped["fetch_plan"]["script"] is None      # passed through as sent
    assert "never run an older or placeholder script in its place" in shaped["upload_note"]


def test_the_review_fix_contracts_are_cited_where_the_token_code_lives():
    """The report-token code names where C1-C10 and the upload capability are recorded, and those records exist."""
    line = "C1-C10 are the review-fix contracts recorded in docs/wiki/work-log/2026-11-02-product-decision-report.md"
    adr = "docs/wiki/decisions/0023-report-upload-capability.md"
    for rel in ("shared/polymath_shared/mcp_retrieval.py", "orchestrator/orchestrator/mcp_server.py"):
        src = _flat(" ".join(ln.lstrip("#: ") for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines()))
        assert line in src and f"(the capability is ADR-0023, {adr})" in src, rel
    worklog = (ROOT / "docs/wiki/work-log/2026-11-02-product-decision-report.md").read_text(encoding="utf-8")
    assert "Review-fix contracts C1" in worklog and "**C1 upload tokens.**" in worklog
    assert "# ADR-0023" in (ROOT / adr).read_text(encoding="utf-8")
