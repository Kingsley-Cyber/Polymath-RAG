"""SUPPLIER-APIS (owner-approved 2026-09-27): READ-ONLY supplier tools on BOTH of Polymath's MCP servers, so every connected harness
(Claude Code, Codex, Hermes, Gemini CLI, OpenCode) gets them and no write tool ever exists. CJ's own MCP server is not used: its token
cannot be scoped and also reaches orders, payments, payment links, disputes and store listings.
  * the tools: supplier_search(query, source="cj"|"alibaba", limit=10), supplier_product(product_id),
    supplier_freight(variant_id, country, quantity=1, from_country="CN"), supplier_warehouses(): the same names, parameters and
    descriptions on Server A and Server B, owner-only (not in the principals' TOOL_POLICY: a friend's key is refused at the gate);
  * the routes behind them (`/supplier/*`, next to `/adapter/{id}/acquire`): the MCP servers on this host only (no proxy, a loopback
    Host, B-28), the owner only (a principal gets 403), an OWNER line at the web boundary;
  * the shapes: search = research_acquire's listing shape (sources + items + completeness + limitations), product = the product and
    its variants, freight = CJ's options, warehouses = CJ's list;
  * nothing writes: the CJ client's routes are the sign-in and four reads, and no supplier tool or route names an order, a cart, a
    payment, a dispute or a store listing.
Fake HTTP only (no call reaches CJ or a search engine); no browser, no database.
"""
import ast
import asyncio
import hashlib
import importlib.util
import itertools
import json
import pathlib
import re
import sys

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(ROOT / "tests" / "determinism"))

from polymath_shared.acquisition import cj_api as CJ
from polymath_shared.acquisition import searxng as SX
from polymath_shared.acquisition import supplier as SUP

TOOLS = {"supplier_search": {"query", "source", "limit"}, "supplier_product": {"product_id"},
         "supplier_freight": {"variant_id", "country", "quantity", "from_country"}, "supplier_warehouses": set()}
#: what a write route or tool would be named: an order, a cart, a payment, a dispute, a store listing, a sourcing request, a change
WRITE = re.compile(r"order|cart|pay|dispute|addtomyproduct|myproduct|listed|publish|delist|sourcing|shop|create|confirm|delete|cancel"
                   r"|merge|update|individualization|logout|refresh", re.IGNORECASE)
_SEQ = itertools.count()
PID, VID = "04A22450-67F0-4617-A132-E7AE7F8963B0", "D4057F56-3F09-4541-8461-9D76D014846D"


def _key() -> str:
    return f"CJ{next(_SEQ):04d}@api@" + hashlib.sha256(f"tools-{next(_SEQ)}".encode()).hexdigest()[:32]


def _ok(data):
    return httpx.Response(200, json={"code": 200, "result": True, "message": "Success", "data": data, "requestId": "r", "success": True})


DETAILS = {"pid": PID, "productNameEn": "Small trailer model", "productSku": "CJJJJTJT05843", "bigImage": "https://cf.cjdropshipping.com/a.jpg",
           "productImageSet": ["https://cf.cjdropshipping.com/a.jpg", "https://cf.cjdropshipping.com/b.jpg"], "productWeight": "1500.0",
           "productUnit": "unit(s)", "categoryName": "Home & Garden", "sellPrice": 58.09, "suggestSellPrice": "0.97-4.08", "listedNum": 392,
           "supplierName": "", "variants": [{"vid": VID, "pid": PID, "variantNameEn": "Small trailer model Black", "variantSku": "CJJJJTJT05843-Black",
                                             "variantKey": "Black-XXL", "variantWeight": 1580.0, "variantSellPrice": 58.09, "variantSugSellPrice": 0.97,
                                             "inventories": [{"countryCode": "CN", "totalInventory": 12912, "cjInventory": 0, "factoryInventory": 12912}]}]}
ROUTES = {
    CJ.TOKEN: lambda req: _ok({"accessToken": "tok-tools-5b1", "accessTokenExpiryDate": "2027-03-01T09:16:33+08:00"}),
    CJ.SEARCH: lambda req: _ok({"totalRecords": 1, "content": [{"productList": [{"id": PID, "nameEn": "Small trailer model", "sellPrice": "58.09",
                                                                                 "threeCategoryName": "Toys", "listedNum": 392}]}]}),
    CJ.PRODUCT: lambda req: _ok(DETAILS if req.url.params.get("pid") == PID else None),
    CJ.FREIGHT: lambda req: _ok([{"logisticAging": "2-5", "logisticPrice": 4.71, "logisticPriceCn": 30.54, "logisticName": "USPS+"}]),
    CJ.WAREHOUSES: lambda req: _ok([{"areaEn": "China Warehouse", "areaId": 1, "countryCode": "CN", "nameEn": "China", "valueEn": "CN",
                                     "disabled": False, "id": "1"}]),
}


class FakeCJ:
    def __init__(self):
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api2.0/v1")
        self.calls.append((request.method, path, json.loads(request.content) if request.content else None))
        return ROUTES[path](request) if path in ROUTES else httpx.Response(404, json={"code": 404})


class NoSleep:
    def __init__(self):
        self.t = 0.0

    def sleep(self, s):
        self.t += s

    def clock(self):
        return self.t


def _cj(fake) -> CJ.CJClient:
    ns = NoSleep()
    return CJ.CJClient(_key(), transport=httpx.MockTransport(fake), sleep=ns.sleep, clock=ns.clock)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _servers():
    a = {t.name: t for t in asyncio.run(_load("supplier_mcp_a", "orchestrator/orchestrator/mcp_server.py").mcp.list_tools())}
    b = {t.name: t for t in asyncio.run(_load("supplier_mcp_b", "mcp_server/polymath_mcp.py").server.list_tools())}
    return a, b


def test_the_code_under_test_is_this_checkout():
    for mod in (CJ, SX, SUP):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── the tools, on both servers
def test_both_servers_publish_the_four_supplier_tools_identically():
    a, b = _servers()
    for label, tools in (("A", a), ("B", b)):
        assert {n for n in tools if n.startswith("supplier_")} == set(TOOLS), label
    for name, params in TOOLS.items():
        sa, sb = a[name].input_schema, b[name].input_schema
        assert set(sa.get("properties") or {}) == params and sa.get("properties") == sb.get("properties"), name   # names, types, defaults
        assert sorted(sa.get("required") or []) == sorted(sb.get("required") or []), name
        assert " ".join(a[name].description.split()) == " ".join(b[name].description.split()), name
        assert "READ-ONLY" in a[name].description and "owner key only" in a[name].description, name
    assert a["supplier_search"].input_schema["properties"]["source"]["default"] == "cj"
    assert a["supplier_search"].input_schema["properties"]["limit"]["default"] == 10
    assert a["supplier_freight"].input_schema["properties"]["quantity"]["default"] == 1
    assert sorted(a["supplier_freight"].input_schema.get("required") or []) == ["country", "variant_id"]


def test_the_tools_are_owner_only_by_default_deny():
    from orchestrator import mcp_principals as P
    mod = _load("supplier_mcp_a_names", "orchestrator/orchestrator/mcp_server.py")
    assert set(TOOLS) <= set(mod._TOOL_NAMES)
    assert not set(TOOLS) & set(P.TOOL_POLICY)                               # no scope reaches them: a principal is refused at the gate


def test_nothing_in_the_supplier_client_or_tools_can_write():
    assert CJ.ENDPOINTS == ("/authentication/getAccessToken", "/product/listV2", "/product/query", "/logistic/freightCalculate",
                            "/product/globalWarehouseList")
    tree = ast.parse((ROOT / "shared/polymath_shared/acquisition/cj_api.py").read_text())
    in_fstrings = {id(v) for j in ast.walk(tree) if isinstance(j, ast.JoinedStr) for v in j.values}     # the product PAGE URL's parts
    routes = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in in_fstrings
              and re.fullmatch(r"/[A-Za-z][\w/]*", n.value)}
    assert routes == set(CJ.ENDPOINTS), routes                               # the module names no other CJ route
    assert not [r for r in CJ.ENDPOINTS if WRITE.search(r)]
    a, b = _servers()
    assert not [n for n in (*a, *b) if n.startswith("supplier_") and WRITE.search(n)]
    assert SUP.TOOLS == tuple(TOOLS)
    fake = FakeCJ()
    client = _cj(fake)
    client.search("toy trailer", 5), client.product(PID), client.freight(VID, "US", 1, "CN"), client.warehouses()
    assert {(m, p) for m, p, _ in fake.calls} == {("POST", CJ.TOKEN), ("GET", CJ.SEARCH), ("GET", CJ.PRODUCT), ("POST", CJ.FREIGHT),
                                                  ("GET", CJ.WAREHOUSES)}
    src = (ROOT / "orchestrator/orchestrator/api/acquisition.py").read_text()
    assert set(re.findall(r'"(/supplier/[a-z]+)"', src)) == {"/supplier/search", "/supplier/product", "/supplier/freight", "/supplier/warehouses"}


def test_the_web_boundary_keeps_the_routes_for_the_owner():
    from orchestrator import web_boundary as B
    for method, path in (("POST", "/supplier/search"), ("POST", "/supplier/product"), ("POST", "/supplier/freight"), ("GET", "/supplier/warehouses")):
        assert B.classify(method, path) == B.OWNER, path
    assert B.classify("POST", "/supplier/order") is None and B.classify("POST", "/supplier") is None


# ─────────────────────────────────────────────────────────── the routes
def _app(monkeypatch, fake=None, env=None):
    from fastapi import FastAPI
    from orchestrator.api import acquisition as R
    from polymath_shared import principal_context
    for k in ("CJ_API_KEY", "SEARXNG_URL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    if fake is not None:
        monkeypatch.setattr(CJ, "client_from_env", lambda e, **kw: _cj(fake))
    app = FastAPI()
    app.add_middleware(principal_context.PrincipalContextMiddleware)
    app.include_router(R.router)
    return app


def _client(app):
    from fastapi.testclient import TestClient
    return TestClient(app, base_url="http://127.0.0.1:7200")               # how the MCP servers call it (B-28)


def test_the_owner_searches_cj_and_gets_research_acquires_listing_shape(monkeypatch):
    c = _client(_app(monkeypatch, FakeCJ()))
    r = c.post("/supplier/search", json={"query": "toy trailer", "source": "cj"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["contract"], out["tool"], out["source"], out["site"], out["status"]) == ("supplier-tools-v1", "supplier_search", "cj",
                                                                                       "cjdropshipping.com", "OK")
    (item,), (src,) = out["items"], out["sources"]
    assert set(src) == {"source_id", "url", "source_class", "retrieved_at", "published_at_if_known"} and src["source_class"] == "supplier_listing"
    assert item["source_id"] == src["source_id"] and item["kind"] == "listing" and item["date_precision"] == "none"
    assert {"title", "price_as_listed", "minimum_order_as_listed", "supplier", "product_id"} <= set(item["listing"])
    assert item["listing"]["price_as_listed"] == "US$58.09" and item["listing"]["product_id"] == PID
    assert any("CJ Dropshipping API" in x for x in out["limitations"]) and out["completeness"]["read"] == 1


def test_the_owner_searches_alibaba_through_searxng(monkeypatch):
    results = [{"url": "https://www.alibaba.com/product-detail/Toy-Trailer_1600123456789.html", "title": "Toy Trailer - Buy Toy Product on Alibaba.com",
                "content": "US$1.10-1.60. Min. order: 100 pieces"}]
    seen = []

    def searx(req: httpx.Request) -> httpx.Response:
        seen.append((str(req.url.copy_with(query=None)), req.url.params["q"], req.url.params["format"]))
        return httpx.Response(200, json={"results": results, "unresponsive_engines": []})
    real = SX.SearXNGListings
    monkeypatch.setattr(SX, "SearXNGListings", lambda base, **kw: real(base, transport=httpx.MockTransport(searx)))
    out = _client(_app(monkeypatch)).post("/supplier/search", json={"query": "toy trailer", "source": "alibaba", "limit": 5}).json()
    assert seen == [("http://127.0.0.1:8888/search", "site:alibaba.com toy trailer", "json")]      # SEARXNG_URL unset: the local default
    assert out["status"] == "OK" and out["site"] == "alibaba.com"
    (item,) = out["items"]
    assert (item["listing"]["price_as_listed"], item["listing"]["minimum_order_as_listed"]) == ("US$1.10-1.60", "100 pieces")
    assert "found through search-engine results (SearXNG); snippet-level data" in out["limitations"]


def test_product_freight_and_warehouses_read_cj_and_say_so(monkeypatch):
    fake = FakeCJ()
    c = _client(_app(monkeypatch, fake))
    prod = c.post("/supplier/product", json={"product_id": PID}).json()
    assert prod["status"] == "OK" and prod["product"]["product_id"] == PID and prod["product"]["price_as_listed"] == "US$58.09"
    assert prod["product"]["suggested_retail_as_listed"] == "US$0.97-4.08" and prod["product"]["url"].endswith(f"-p-{PID}.html")
    (variant,) = prod["variants"]
    assert (variant["variant_id"], variant["options"], variant["price_as_listed"], variant["weight_g"]) == (VID, "Black-XXL", "US$58.09", "1580.0")
    assert variant["stock"] == [{"country": "CN", "total": "12912", "cj_warehouse": "0", "factory": "12912"}]
    gone = c.post("/supplier/product", json={"product_id": "0000000000000000000"}).json()
    assert gone["status"] == "NOT_FOUND" and gone["product"] is None
    quote = c.post("/supplier/freight", json={"variant_id": VID, "country": "us", "quantity": 2}).json()
    assert quote["status"] == "OK" and quote["request"] == {"variant_id": VID, "from_country": "CN", "to_country": "US", "quantity": 2}
    assert quote["options"] == [{"carrier": "USPS+", "cost_usd": 4.71, "delivery_days": "2-5", "taxes_usd": None, "clearance_usd": None, "total_usd": None}]
    sent = [body for m, p, body in fake.calls if p == CJ.FREIGHT]
    assert sent == [{"startCountryCode": "CN", "endCountryCode": "US", "products": [{"quantity": 2, "vid": VID}]}]
    houses = c.get("/supplier/warehouses").json()
    assert houses["status"] == "OK" and houses["warehouses"] == [{"id": "1", "name": "China Warehouse", "country_code": "CN", "country": "China",
                                                                  "code": "CN", "available": True}]
    assert all(any("CJ" in x for x in r["limitations"]) for r in (prod, quote, houses))


def test_a_principal_is_refused_and_so_is_anything_but_a_direct_loopback_call(monkeypatch):
    from fastapi.testclient import TestClient
    from polymath_shared import principal_context
    fake = FakeCJ()
    app = _app(monkeypatch, fake)
    c = _client(app)
    calls = [("post", "/supplier/search", {"query": "toy trailer"}), ("post", "/supplier/product", {"product_id": PID}),
             ("post", "/supplier/freight", {"variant_id": VID, "country": "US"}), ("get", "/supplier/warehouses", None)]
    for method, path, body in calls:
        r = getattr(c, method)(path, headers={principal_context.HEADER: "prn_fred"}, **({"json": body} if body else {}))
        assert r.status_code == 403 and r.json()["detail"]["code"] == "OWNER_ONLY", (path, r.text)
        r = getattr(c, method)(path, headers={"X-Forwarded-For": "203.0.113.9"}, **({"json": body} if body else {}))
        assert r.status_code == 403 and r.json()["detail"]["code"] == "PROXIED_CALLER", path
        r = getattr(TestClient(app, base_url="http://rebind.attacker.example:7200"), method)(path, **({"json": body} if body else {}))
        assert r.status_code == 403 and r.json()["detail"]["code"] == "NON_LOOPBACK_HOST", path
    assert fake.calls == []                                                   # nothing reached CJ


@pytest.mark.parametrize("path,body,code", [
    ("/supplier/search", {"query": "toy trailer", "source": "ebay"}, "UNKNOWN_SOURCE"), ("/supplier/search", {"query": "x"}, "BAD_QUERY"),
    ("/supplier/product", {"product_id": "../../order/create"}, "BAD_ID"), ("/supplier/freight", {"variant_id": VID, "country": "USA"}, "BAD_COUNTRY"),
    ("/supplier/freight", {"variant_id": VID, "country": "US", "quantity": 0}, "BAD_QUANTITY"),
    ("/supplier/freight", {"variant_id": VID, "country": "US", "from_country": "C1"}, "BAD_COUNTRY")])
def test_bad_arguments_are_refused_before_cj_is_called(monkeypatch, path, body, code):
    fake = FakeCJ()
    r = _client(_app(monkeypatch, fake)).post(path, json=body)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code and fake.calls == []


def test_without_a_key_the_cj_tools_answer_unavailable_and_say_why(monkeypatch):
    c = _client(_app(monkeypatch))
    for r in (c.post("/supplier/search", json={"query": "toy trailer"}), c.post("/supplier/product", json={"product_id": PID}),
              c.post("/supplier/freight", json={"variant_id": VID, "country": "US"}), c.get("/supplier/warehouses")):
        out = r.json()
        assert r.status_code == 200 and out["status"] == "UNAVAILABLE" and any("CJ_API_KEY is not set" in x for x in out["limitations"]), out
    off = _client(_app(monkeypatch, env={"SEARXNG_URL": "off"})).post("/supplier/search", json={"query": "toy trailer", "source": "alibaba"}).json()
    assert off["status"] == "UNAVAILABLE" and any("SEARXNG_URL=off" in x for x in off["limitations"])


# ─────────────────────────────────────────────────────────── the whole chain through Server A's gate
def test_through_server_a_the_owner_key_reaches_cj_and_a_friends_key_is_refused(monkeypatch, tmp_path):
    import test_mcp_principals_gate as GATE
    from fastapi.testclient import TestClient
    w = GATE._build(monkeypatch, tmp_path)
    fake = FakeCJ()
    orch = _app(monkeypatch, fake)
    real = httpx.AsyncClient
    monkeypatch.setattr(w.mod.httpx, "AsyncClient", lambda *a, **k: real(*a, **{**k, "transport": httpx.ASGITransport(app=orch)}))
    monkeypatch.setattr(w.mod, "ORCH", "http://127.0.0.1:7200")
    with TestClient(w.mod.build_app()) as c:
        w.c = c
        out = GATE._payload(GATE._call(w, GATE.OWNER_KEY, "supplier_search", {"query": "toy trailer"}, host=GATE.LOOPBACK))
        assert out["status"] == "OK" and out["items"][0]["listing"]["product_id"] == PID
        for tool, args in (("supplier_search", {"query": "toy trailer"}), ("supplier_product", {"product_id": PID}),
                           ("supplier_freight", {"variant_id": VID, "country": "US"}), ("supplier_warehouses", {})):
            GATE._denied(GATE._call(w, w.keys["prn_alice"], tool, args), "tool_not_permitted")
        listed = {t["name"] for t in json.loads(GATE._post(w, w.keys["prn_alice"], {"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                                                                                     "params": {}}).text)["result"]["tools"]}
        assert not listed & set(TOOLS)                                        # a friend never even sees them
    assert [p for _, p, _ in fake.calls] == [CJ.TOKEN, CJ.SEARCH]             # only the owner's one search reached CJ


# ─────────────────────────────────────────────────────────── what a harness is told
def test_the_connect_prompt_and_connectors_name_the_tools_as_owner_only():
    from orchestrator.api.web_settings import connect_prompt
    text = connect_prompt("pmk_abc", ["cinema"], "fr-fred", url="https://mcp.example.test/mcp")
    line = next(ln for ln in text.splitlines() if "supplier_search" in ln)
    assert all(t in line for t in TOOLS) and "owner-only" in line and "read-only" in line
    doc = (ROOT / "mcp_server/CONNECTORS.md").read_text(encoding="utf-8")
    section = doc[doc.index("**Supplier tools (owner key only, read-only).**"):]
    assert all(f"`{t}(" in section for t in TOOLS) and "friend's key is refused (403)" in section
