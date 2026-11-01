"""SUPPLIER-APIS (the owner's decision of 2026-09-27): the listings the new backends return are the listings the supply join already
reads. A cjdropshipping.com listing from CJ's official API and an alibaba.com listing from the USER's own Agent Reach (PRODUCT-SEARCH-E2E,
2026-11-01: a real Exa result from the owner's probe, parsed by `agent_reach.parse` as supplier_parse parses it) go through
`research_acquire`'s shaping (`service.shape`), the harness writes each one as the supply step's intent asks (`listing:`, `supplier:`,
`price as listed:`, `MOQ as listed:`, `channel:`, `concept:`, and the source copied as returned), TrailSignal's admission is
stubbed as in the supply-join tests, and the REAL `supply.leads` executor joins them: prices and minimum orders parse, CJ's missing
minimum order takes the channel's default, each concept is sourced. Reuses the supply-join test's executor harness
(`test_adapter_ecommerce_supply_join._exec`). Fake HTTP only; no database, no network."""
from __future__ import annotations

import hashlib
import itertools
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_adapter_ecommerce_supply_join as SJ
from polymath_shared.acquisition import agent_reach as AR
from polymath_shared.acquisition import cj_api as CJ
from polymath_shared.acquisition import service as S

_SEQ = itertools.count()
CJ_PRODUCT = {"id": "04A22450-67F0-4617-A132-E7AE7F8963B0", "nameEn": "Heated Glove Liner Touchscreen", "sellPrice": "11.85", "nowPrice": "9.50",
              "threeCategoryName": "Gloves", "supplierName": "", "listedNum": 12, "warehouseInventoryNum": 340}
#: the owner's Agent Reach probe (2026-11-01): an Exa search restricted to alibaba.com; its third result states a price, a minimum order
#: and the supplier ("FREE shipping capped at $30" stands before the price: the old snippet parser took that cap for the price)
ALI_EXA = ROOT / "tests" / "fixtures" / "agent_reach" / "alibaba_exa_pet_hair_remover.txt"
ALI_URL = "https://www.alibaba.com/product-detail/Factory-Wholesale-Pet-Grooming-Products-Two_1601569422319.html"


def _cj_raw(target):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path.removeprefix("/api2.0/v1")
        data = ({"accessToken": "tok-join-1", "accessTokenExpiryDate": "2027-03-01T09:16:33+08:00"} if path == CJ.TOKEN
                else {"totalRecords": 1, "content": [{"productList": [CJ_PRODUCT]}]})
        return httpx.Response(200, json={"code": 200, "result": True, "message": "Success", "data": data})
    key = f"CJ{next(_SEQ)}@api@" + hashlib.sha256(b"supply-join").hexdigest()[:32]
    client = CJ.CJClient(key, transport=httpx.MockTransport(handler), sleep=lambda s: None)
    return CJ.CJListings(client).read(target, 20)


def _ali_raw(target):
    got = AR.parse(target.site, ALI_EXA.read_text(encoding="utf-8").split("\n---\n")[2])
    assert got["tool_class"] == "agent_reach.exa" and got["refused"] == []
    return {"state": "ok", "retrieved_at": "2026-11-01T10:33:00Z", "records": got["records"], "total": None, "complete": None,
            "backend_notes": got["notes"]}


def _read(site: str, raw_of, tag: str) -> dict:
    t = S.resolve("listings", "heated glove liner", site)
    raw = raw_of(t)
    action = {"action_id": "hact_" + hashlib.sha256(tag.encode()).hexdigest()[:24], "run_id": "adr_" + "7" * 32}
    return S.shape(t, raw, action=action, search_intent_id="si_supply", retrieved_at=raw["retrieved_at"], used=1, cap=5, limit=20)


def _written(out: dict, channel: str, concept: str, prefix: str) -> tuple[list[dict], list[dict]]:
    """What a harness writes from a read, as the supply step's intent asks: one observation per listing, its context tags, the source
    copied as returned."""
    sources = {s["source_id"]: s for s in out["sources"]}
    obs = []
    for n, item in enumerate(out["items"]):
        lst = item["listing"]
        obs.append({"observation_id": f"{prefix}{n}", "source_id": item["source_id"], "claim": "a supplier lists this product",
                    "paraphrase_or_excerpt": item["excerpt"], "context": f"listing: {lst['title']} · supplier: {lst.get('supplier') or 'none'} · "
                    f"price as listed: {lst.get('price_as_listed') or ''} · MOQ as listed: {lst.get('minimum_order_as_listed') or ''} · "
                    f"channel: {channel} · concept: {concept}"})
    return obs, [sources[o["source_id"]] for o in obs]


def test_the_code_under_test_is_this_checkout():
    for mod in (CJ, AR, S, SJ.W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


def test_api_and_search_listings_join_as_supply_with_their_price_and_minimum_order():
    cj_out, ali_out = _read("cjdropshipping.com", _cj_raw, "join-cj"), _read("alibaba.com", _ali_raw, "join-ali")
    assert cj_out["status"] == "OK" and ali_out["status"] == "OK"
    cj_obs, cj_src = _written(cj_out, "cjdropshipping", "pc_1", "ocj")
    ali_obs, ali_src = _written(ali_out, "alibaba", "pc_1", "oali")
    admitted = [{"admitted_evidence_id": f"fev_{o['observation_id']}", "observation_id": o["observation_id"], "evidence_role": "price",
                 "polarity": "supporting", "hypothesis_ids": [SJ.H1], "independence_group": ch, "freshness": "fresh"}
                for o, ch in [(o, "cjdropshipping") for o in cj_obs] + [(o, "alibaba") for o in ali_obs]]
    out = SJ._exec("supply.leads", {"admissions": [{"admitted": admitted}], "receipts": [{"observations": cj_obs + ali_obs, "sources": cj_src + ali_src}],
                                    "product_concepts": SJ.CONCEPTS, "mechanisms": SJ.MECHS, "live_hypotheses": SJ.LIVE})["output"]
    by = {c["channel"]: c for c in out["supplier_candidates"]}
    assert set(by) == {"cjdropshipping", "alibaba"} and out["joined"]["without_listing"] == 0 and out["unjoined"] == []
    cj, ali = by["cjdropshipping"], by["alibaba"]
    assert (cj["price_usd_low"], cj["moq_units"], cj["concept_id"]) == (11.85, 1, "pc_1") and "default MOQ" in cj["moq_note"]
    assert cj["url"] == "https://cjdropshipping.com/product/heated-glove-liner-touchscreen-p-04A22450-67F0-4617-A132-E7AE7F8963B0.html"
    assert (ali["price_usd_low"], ali["price_usd_high"], ali["moq_units"], ali["concept_id"]) == (1.25, 1.25, 10, "pc_1")
    assert ali["supplier_name"] == "Huizhou Shengfeng Feather Craft Factory" and ali["url"] == ALI_URL
    assert cj["supplier_name"] is None and out["joined"]["without_supplier_name"] == 1     # CJ's API named no supplier: never invented
    assert {c["concept_id"]: c["status"] for c in out["sourcing_coverage"]}["pc_1"] == "sourced"
