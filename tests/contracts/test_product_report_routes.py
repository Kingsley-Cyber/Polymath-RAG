"""PRODUCT-DECISION-REPORT-V1 (B4b, plan §3 and §4.6): the decision-report service and routes, end to end in process.

Every test runs TWICE: on an in-memory store (always) and on the REAL report_store against a sealed Postgres (the throwaway
database of the sealed harness: POLYMATH_TEST_DSN on a port other than the fleet's 5432, a near-empty `documents` table; never the
fleet's database). B1 (`fetch_plan.build`, `agent_reach.parse_report_source`), B2 (`host_data.collect`) and B4a
(`dossier.render_decision`) are injected fakes, and once more REAL on the recorded fixtures of 2026-11-02 (B1's Agent Reach outputs,
B2's CJ answers through its own recorded supplier double, B4a's engine render with B3's unit economics); the product turn is faked, or
run through the product route's own machinery on the chat-runtime harness (stores, sidecars, LLM and supplier faked). No network:
no CJ, eBay, Exa, Jina or model.

Covered: start with products (at once, round-1 plan, the first upload token, stored only as sha256), start without products
(a background product turn as the caller's principal; typed failures), the status view (with and without the token), the upload
capability (wrong / another report's / expired token, oversize, unknown packet, finished round -> typed 4xx), idempotent
re-upload, round 1 -> round 2 from the parsed next_targets, compile (the §4.4 bundle, the agent's verdicts, typed refusals, a
failed render and a retry), the HTML under a CSP without script, the list, owner vs principal privacy, the web boundary's classes,
receipts (kind product_report, counts and statuses only) and the contract schema on real responses. Review-fix round: a re-bound
page reaches no report route and no product search (R1 #1), the capability is checked before the body is read (R1 #3), one
background job per principal on daemon threads (C8, R3 #1), the upload token never reaches a log line (R1 #4), contract C1's token
minting, a lost or unsaved compile (C9), NUL characters, an oversize packet (C10), staleness by the uploads' set (R3 #4) and
degraded host data in status and the compile receipt (C6)."""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import threading
import time
from urllib.parse import urlsplit

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "orchestrator", ROOT / "tests" / "determinism"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import jsonschema
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from orchestrator.api import product_report as R
from polymath_shared import principal_context
from polymath_shared.principal_context import PrincipalContextMiddleware
from polymath_shared.product_search import report_store as S

SCHEMA = json.loads((ROOT / "contracts/product/v1/product_report.schema.json").read_text())
EXAMPLE = json.loads((ROOT / "contracts/product/v1/product_report.example.json").read_text())
UA = "report-contract-test/1.0"
PRODUCTS = [{"title": "Automatic pet feeder", "search_terms": ["automatic pet feeder"]},
            {"title": "Calming dog bed", "search_terms": ["calming dog bed", "donut pet bed"]}]


def test_the_modules_under_test_are_this_checkout():
    for mod in (R, S, principal_context):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ───────────────────────────────────────────────────────────────── the two stores
class MemoryStore:
    """report_store's storage in memory; every check is the real module's pure one (check_capability, check_upload,
    check_transition, the helpers). The same route tests run on the real store in the sealed harness."""

    def __init__(self):
        self.reports: dict[str, dict] = {}
        self.ups: dict[tuple[str, str], dict] = {}
        self.lock = threading.RLock()

    def __getattr__(self, name):
        return getattr(S, name)

    def _out(self, row: dict, with_html: bool = False) -> dict:
        d = copy.deepcopy(row)
        if not with_html:
            d.pop("html", None)
        return d

    @staticmethod
    def _json(value):
        """What a jsonb write keeps: the store's own `_j` (U+0000 stripped)."""
        return json.loads(S._j(value)) if value is not None else None

    def create(self, conn, *, owner_principal_id, request, candidates, host=None, at=None):
        with self.lock:
            t = at or S.now()
            rid, token = S.new_report_id(), S.new_upload_token()
            self.reports[rid] = {"report_id": rid, "owner_principal_id": owner_principal_id, "status": "collecting",
                                 "request": self._json(request), "candidates": self._json(candidates), "host": self._json(host),
                                 "model": None, "verdicts": None, "html": None,
                                 "upload_tokens": S.with_token([], S.token_sha256(token), t), "upload_expires_at": t + S.UPLOAD_TTL,
                                 "round": 1, "compile_started_at": None, "created_at": t, "updated_at": t}
            return self._out(self.reports[rid]), token

    def get(self, conn, report_id, *, principal_id, for_update=False, with_html=False):
        with self.lock:
            row = self.reports.get(report_id) if isinstance(report_id, str) else None
            if row is None or (principal_id is not None and row["owner_principal_id"] != principal_id):
                raise S.UnknownReport(report_id)
            return self._out(row, with_html)

    def mint_token(self, conn, report_id, *, at=None, every_s=None):
        with self.lock:
            if report_id not in self.reports:
                raise S.UnknownReport(report_id)
            row = self.reports[report_id]
            t, newest = at or S.now(), S.last_minted(row)
            if every_s is not None and newest is not None and t < newest + dt.timedelta(seconds=every_s):
                raise S.MintTooSoon(newest + dt.timedelta(seconds=every_s))
            token = S.new_upload_token()
            row["upload_tokens"] = S.with_token(S.tokens_of(row), S.token_sha256(token), t)
            return token

    def mark_used(self, conn, report_id, token, *, at=None):
        with self.lock:
            row = self.reports[report_id]
            row["upload_tokens"] = S.touched(S.tokens_of(row), S.token_sha256(token), at)

    def by_capability(self, conn, report_id, token, *, at=None, for_update=False):
        with self.lock:
            row = self.reports.get(report_id) if S.well_formed_capability(report_id, token) else None
            S.check_capability(row, token, at)
            return self._out(row)

    def list_for(self, conn, principal_id, *, limit=50, before=None):
        with self.lock:
            rows = sorted(self.reports.values(), key=lambda r: (r["created_at"], r["report_id"]), reverse=True)
            if principal_id is not None:
                rows = [r for r in rows if r["owner_principal_id"] == principal_id]
            out = []
            for r in rows[:limit]:
                d = {k: copy.deepcopy(r[k]) for k in ("report_id", "owner_principal_id", "status", "request", "candidates", "round",
                                                      "created_at", "updated_at", "upload_expires_at")}
                d.update(compiled=r["html"] is not None, compiled_at=(r["model"] or {}).get("compiled_at"),
                         uploads=sum(1 for (rid, _p) in self.ups if rid == r["report_id"]))
                out.append(d)
            return out

    def html_of(self, conn, report_id, *, principal_id):
        return self.get(conn, report_id, principal_id=principal_id, with_html=True).get("html")

    def _set(self, report_id, **kw):
        with self.lock:
            self.reports[report_id].update({k: self._json(v) for k, v in kw.items()}, updated_at=S.now())

    def save_candidates(self, conn, report_id, candidates):
        self._set(report_id, candidates=candidates)

    def save_host(self, conn, report_id, host):
        self._set(report_id, host=host)

    def save_model(self, conn, report_id, model):
        self._set(report_id, model=model)

    def save_verdicts(self, conn, report_id, verdicts):
        self._set(report_id, verdicts=verdicts)

    def save_html(self, conn, report_id, html):
        with self.lock:
            self.reports[report_id].update(html=str(html).replace("\x00", ""), updated_at=S.now())

    def transition(self, conn, report_id, wanted, *, current, at=None):
        with self.lock:
            S.check_transition(current, wanted)
            if self.reports[report_id]["status"] != current:
                raise S.BadTransition(current, wanted)
            self.reports[report_id].update(status=wanted, updated_at=S.now(),
                                           **({"compile_started_at": at or S.now()} if wanted == "compiling" else {}))

    def advance_round(self, conn, report_id, *, current):
        with self.lock:
            if current >= S.MAX_ROUND or self.reports[report_id]["round"] != current:
                return False
            self.reports[report_id].update(round=current + 1, updated_at=S.now())
            return True

    def uploads(self, conn, report_id, *, round_=None):
        with self.lock:
            rows = [copy.deepcopy(u) for (rid, _p), u in self.ups.items() if rid == report_id and (round_ is None or u["round"] == round_)]
            return sorted(rows, key=lambda u: (u["round"], u["packet_id"]))

    def add_upload(self, conn, report_id, *, packet_id, round_, source, kind, raw, status, parsed, refused, at=None):
        with self.lock:
            S.check_upload(len(raw), packet_id, replaced=False, held=0)
            replaced = (report_id, packet_id) in self.ups
            held = sum(1 for (rid, _p) in self.ups if rid == report_id)
            S.check_upload(len(raw), packet_id, replaced=replaced, held=held)
            kept = replaced and self.ups[(report_id, packet_id)]["status"] == "OK" and status != "OK"   # the store's ON CONFLICT rule
            if not kept:
                self.ups[(report_id, packet_id)] = {
                    "report_id": report_id, "packet_id": packet_id, "round": round_, "source": source, "kind": kind,
                    "received_at": at or S.now(), "bytes": len(raw), "sha256": S.content_sha256(raw), "status": status,
                    "parsed": self._json(parsed), "refused": self._json(refused)}
            self.reports[report_id]["updated_at"] = S.now()
            return {"replaced": replaced and not kept, "kept_earlier": kept, "bytes": len(raw), "sha256": S.content_sha256(raw),
                    "uploads": held + (0 if replaced else 1)}

    # test helpers
    def expire(self, report_id):
        self.reports[report_id]["upload_expires_at"] = S.now() - dt.timedelta(seconds=1)

    def raw_row_text(self, report_id) -> str:
        return json.dumps(self.reports[report_id], default=str) + json.dumps(
            [u for (rid, _p), u in self.ups.items() if rid == report_id], default=str)

    def owner_of(self, report_id):
        return self.reports[report_id]["owner_principal_id"]

    def held(self, report_id):
        return [e["sha256"] for e in self.reports[report_id]["upload_tokens"]]

    def upload_row(self, report_id, packet_id):
        return copy.deepcopy(self.ups[(report_id, packet_id)])

    def set_compiling(self, report_id, age_s):
        """A compile that started `age_s` seconds ago and never finished (a restart lost it)."""
        self.reports[report_id].update(status="compiling", compile_started_at=S.now() - dt.timedelta(seconds=age_s))

    def row(self, report_id):
        return copy.deepcopy(self.reports[report_id])


def sealed_dsn() -> str | None:
    """The sealed harness's throwaway database, or None. Never the fleet's: an explicit POLYMATH_TEST_DSN, not on port 5432, whose
    `documents` table is near-empty (the fleet's holds thousands)."""
    dsn = os.environ.get("POLYMATH_TEST_DSN")
    if not dsn or (urlsplit(dsn).port or 5432) == 5432:
        return None
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            if conn.execute("SELECT to_regclass('product_reports')").fetchone()[0] is None:
                return None
            if int(conn.execute("SELECT count(*) FROM documents").fetchone()[0]) >= 1000:
                return None
    except Exception:  # noqa: BLE001 — no database: the postgres variant is skipped
        return None
    return dsn


class PgStore:
    """The REAL report_store on the sealed database, plus the helpers the tests need."""

    def __init__(self, dsn):
        import psycopg
        self.psycopg, self.dsn = psycopg, dsn

    def __getattr__(self, name):
        return getattr(S, name)

    @contextlib.contextmanager
    def tx(self):
        with self.psycopg.connect(self.dsn, autocommit=False) as conn:
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def expire(self, report_id):
        with self.tx() as c:
            c.execute("UPDATE product_reports SET upload_expires_at = now() - interval '1 second' WHERE report_id = %s", (report_id,))

    def raw_row_text(self, report_id) -> str:
        with self.tx() as c:
            a = c.execute("SELECT row_to_json(r)::text FROM product_reports r WHERE report_id = %s", (report_id,)).fetchone()[0]
            b = c.execute("SELECT coalesce(json_agg(u)::text, '') FROM product_report_uploads u WHERE report_id = %s",
                          (report_id,)).fetchone()[0]
            return a + b

    def owner_of(self, report_id):
        with self.tx() as c:
            return c.execute("SELECT owner_principal_id FROM product_reports WHERE report_id = %s", (report_id,)).fetchone()[0]

    def held(self, report_id):
        with self.tx() as c:
            return [e["sha256"] for e in c.execute("SELECT upload_tokens FROM product_reports WHERE report_id = %s",
                                                   (report_id,)).fetchone()[0]]

    def upload_row(self, report_id, packet_id):
        with self.tx() as c:
            return S.uploads(c, report_id) and next(u for u in S.uploads(c, report_id) if u["packet_id"] == packet_id)

    def set_compiling(self, report_id, age_s):
        with self.tx() as c:
            c.execute("UPDATE product_reports SET status = 'compiling', compile_started_at = now() - make_interval(secs => %s) "
                      "WHERE report_id = %s", (age_s, report_id))

    def row(self, report_id):
        with self.tx() as c:
            return S.get(c, report_id, principal_id=None, with_html=True)

    def receipts(self, report_ids):
        """This test's product_report receipts: by the report id in their meta, or (an error receipt has no meta) by the
        compile's question."""
        with self.tx() as c:
            return [dict(zip(("kind", "status", "meta", "principal_id", "client"), r)) for r in c.execute(
                "SELECT kind, status, meta, principal_id, client FROM query_receipts WHERE kind = 'product_report' "
                "AND (meta->'product_report'->>'report_id' = ANY(%s) OR question_head = ANY(%s))",
                (list(report_ids), [f"compile {r}" for r in report_ids])).fetchall()]


@contextlib.contextmanager
def _no_db():
    yield None


# ───────────────────────────────────────────────────────────────── the other slices, faked
def fake_build(report_id, candidates, *, round, upload, targets=None, ebay_api=False):
    packets = []
    if round == 1:
        for c in candidates:
            for source in ("reddit", "amazon", "alibaba"):
                packets.append({"packet_id": f"r1-{c['candidate_id']}-{source}", "candidate_id": c["candidate_id"], "source": source,
                                "kind": "search", "commands": [f"mcporter call exa.web_search_exa query={c['search_terms'][0]!r}"],
                                "expect": "exa_text"})
    else:
        for i, t in enumerate(targets or []):
            packets.append({"packet_id": f"r2-{t['candidate_id']}-{t['source']}-{i}", "candidate_id": t["candidate_id"],
                            "source": t["source"], "kind": "page", "commands": [f"curl -s https://r.jina.ai/{t['url']}"],
                            "expect": "jina_page"})
    script = "#!/usr/bin/env bash\nset -u\n" + "\n".join(
        f"echo data | curl -s -X POST --data-binary @- '{upload['url']}?packet={p['packet_id']}'" for p in packets) + "\n"
    return {"round": round, "packets": packets, "script": script, "script_sha256": hashlib.sha256(script.encode()).hexdigest(),
            "limits": {"exa_parallel": 3, "jina_per_minute": 20}, "how": "run the script once on the user's machine"}


def fake_parse(source, raw_text, *, kind, candidate_terms=None):
    if not raw_text.strip():
        return {"status": "EMPTY", "source": source, "kind": kind, "records": [], "next_targets": [],
                "refused": [{"code": "EMPTY_OUTPUT", "why": "nothing to read"}]}
    if "BLOCKED" in raw_text:
        return {"status": "BLOCKED", "source": source, "kind": kind, "records": [], "next_targets": [],
                "refused": [{"code": "BLOCKED", "why": "Access Denied"}]}
    if "BOOM" in raw_text:
        raise RuntimeError("parser bug")
    rec = {"kind": "thread" if source == "reddit" else "listing", "title": raw_text.strip()[:40], "url": f"https://{source}.example/1"}
    targets = ([{"url": "https://www.amazon.com/dp/B0TEST0001", "source": "amazon", "kind": "page", "why": "top result"},
                {"url": "https://www.amazon.com/dp/B0TEST0002", "source": "amazon", "kind": "page", "why": "second result"}]
               if source == "amazon" and kind == "search" else [])
    return {"status": "OK", "source": source, "kind": kind, "records": [rec], "next_targets": targets, "refused": []}


DECISION_HTML = "<!doctype html><html><head><title>Decision</title></head><body><h1>Decision report</h1><p>numbers</p></body></html>"


class Fakes:
    def __init__(self):
        self.collect_calls, self.render_bundles, self.build_calls, self.turn_calls = [], [], [], []
        self.collect_gate: threading.Event | None = None
        self.render_error: Exception | None = None

    def build(self, report_id, candidates, *, round, upload, targets=None, ebay_api=False):
        self.build_calls.append({"round": round, "upload": dict(upload), "targets": copy.deepcopy(targets), "ebay_api": ebay_api})
        return fake_build(report_id, candidates, round=round, upload=upload, targets=targets)

    def collect(self, candidates, *, principal_id, ship_to="US"):
        if self.collect_gate is not None:
            assert self.collect_gate.wait(10)
        self.collect_calls.append({"principal_id": principal_id, "current": principal_context.current(), "ship_to": ship_to,
                                   "candidates": [c["candidate_id"] for c in candidates]})
        return {"cj": {c["candidate_id"]: {"status": "OK", "reason_code": None, "products": [
                    {"product_id": f"cj-{c['candidate_id']}", "title": c["title"], "sell_price_usd": 6.5, "weight_g": 450,
                     "freight": {"CN": [{"carrier": "CJPacket", "cost_usd": 4.1, "days_min": 7, "days_max": 12}], "US": []},
                     "us_stock_confirmed": False}], "relevance": {"kept": [], "dropped": []}} for c in candidates},
                "ebay": {c["candidate_id"]: {"status": "UNAVAILABLE", "reason_code": "EBAY_NOT_CONFIGURED", "listings": []}
                         for c in candidates},
                "receipts": [{"kind": "cj_search", "status": "OK"}]}

    def render(self, bundle):
        self.render_bundles.append(copy.deepcopy(bundle))
        if self.render_error is not None:
            raise self.render_error
        products = [{"candidate_id": c["candidate_id"], "title": c["title"],
                     "offers": [{"offer_id": "o1", "source": "cj", "unit_cost_usd": 6.5, "moq": 1}],
                     "market": {"amazon": {"n": 1, "median": 29.99, "min": 29.99, "max": 29.99}, "reference_price_usd": 29.99},
                     "channels": {"shopify": {"sell_price_usd": 29.99, "unit_cost_usd": 6.5, "shipping_usd": 4.1, "fees_usd": 1.18,
                                              "returns_usd": 2.05, "margin_before_ads_usd": 16.16, "margin_pct": 53.9,
                                              "break_even_ad_cost_usd": 16.16,
                                              "delivery": {"verdict": "WARN", "reason": "D 12 > 7", "origin": "CN", "days_max": 12}},
                                  "tiktok_us": {"sell_price_usd": 29.99, "margin_before_ads_usd": None, "margin_pct": None,
                                                "break_even_ad_cost_usd": None,
                                                "delivery": {"verdict": "FAIL", "reason": "ships from China", "origin": "CN"}}}}
                    for c in bundle["candidates"]]
        return {"html": DECISION_HTML, "decision": {"products": products, "assumptions": {}}}


# ───────────────────────────────────────────────────────────────── the rig
def _backends():
    return ["memory", pytest.param("postgres", marks=pytest.mark.skipif(sealed_dsn() is None, reason="needs the sealed Postgres"))]


@pytest.fixture(params=_backends())
def rig(request, monkeypatch):
    backend = request.param
    fakes = Fakes()
    if backend == "memory":
        st = MemoryStore()
        monkeypatch.setattr(R, "store", st)
        monkeypatch.setattr(R, "tx", _no_db)
    else:
        st = PgStore(sealed_dsn())
        monkeypatch.setattr(R, "tx", st.tx)
    receipts: list[dict] = []
    real_record = R.record_query_receipt

    def spy(tx_factory, **kw):
        receipts.append({**kw, "_principal": principal_context.current()})      # the principal the receipt is stamped with
        return real_record(tx_factory, **kw) if backend == "postgres" else "q_test"
    monkeypatch.setattr(R, "record_query_receipt", spy)
    monkeypatch.setattr(R.DEPS, "build_plan", fakes.build)
    monkeypatch.setattr(R.DEPS, "parse", fake_parse)
    monkeypatch.setattr(R.DEPS, "collect", fakes.collect)
    monkeypatch.setattr(R.DEPS, "render", fakes.render)
    monkeypatch.setattr(R.DEPS, "ebay_configured", lambda: False)
    monkeypatch.setattr(R, "_JOBS", {})
    monkeypatch.setattr(R, "_CLAIMS", {})
    monkeypatch.setattr(R, "_JOB_ERRORS", {})
    monkeypatch.delenv("POLYMATH_PUBLIC_URL", raising=False)
    monkeypatch.delenv("POLYMATH_ORCH_URL", raising=False)
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.include_router(R.router)

    class Rig:
        pass
    g = Rig()
    g.backend, g.store, g.fakes, g.receipts = backend, st, fakes, receipts
    g.client = TestClient(app, base_url="http://127.0.0.1:7200")
    g.created: list[str] = []
    yield g
    for job in list(R._JOBS.values()):
        job["thread"].join(30)
    if backend == "postgres" and g.created:
        with st.tx() as c:
            c.execute("DELETE FROM product_reports WHERE report_id = ANY(%s)", (g.created,))
            c.execute("DELETE FROM query_receipts WHERE kind = 'product_report' AND (meta->'product_report'->>'report_id' = ANY(%s) "
                      "OR question_head = ANY(%s))", (g.created, [f"compile {r}" for r in g.created]))


def _h(principal=None, token=None):
    return {"user-agent": UA, **({"X-Polymath-Principal": principal} if principal else {}),
            **({"X-Upload-Token": token} if token else {})}


def _start(g, body=None, principal=None, wait=True):
    r = g.client.post("/product/report/start", json=body or {"products": PRODUCTS}, headers=_h(principal))
    assert r.status_code == 200, r.text[:600]
    out = r.json()
    g.created.append(out["report_id"])
    if wait:
        R.wait_for_jobs(out["report_id"])
    return out


def _status(g, rid, principal=None, token=None, **params):
    return g.client.get(f"/product/report/{rid}/status", headers=_h(principal, token), params=params)


def _upload(g, rid, token, packet, text="a page", **kw):
    return g.client.post(f"/product/report/{rid}/upload/{token}", params={"packet": packet} if packet else {},
                         content=text.encode() if isinstance(text, str) else text, headers={"content-type": "text/plain", **kw})


def _valid(instance, part=None):
    """Validate against the contract schema (the whole oneOf, or one $defs part)."""
    schema = SCHEMA if part is None else {**SCHEMA, "oneOf": [{"$ref": f"#/$defs/{part}"}]}
    jsonschema.Draft202012Validator(schema).validate(instance)


# ───────────────────────────────────────────────────────────────── registration and classes
def test_the_routes_are_registered_and_classified_and_only_start_wakes_the_embedder():
    from orchestrator import web_boundary as B
    src = (ROOT / "orchestrator" / "orchestrator" / "main.py").read_text(encoding="utf-8")
    assert "from orchestrator.api.product_report import router as product_report_router" in src
    assert "app.include_router(product_report_router)" in src
    wake = src.split("async def _query_activity_signal", 1)[1].split("try:", 1)[0]
    assert '"/product/report/start"' in wake and "compile" not in wake and "upload" not in wake
    cases = [("POST", "/product/report/start", B.USER), ("GET", "/product/reports", B.USER),
             ("GET", "/product/report/rpt_x/status", B.USER), ("POST", "/product/report/rpt_x/compile", B.USER),
             ("GET", "/product/report/rpt_x", B.USER), ("POST", "/product/report/rpt_x/upload/tok", B.CAPABILITY),
             ("GET", "/product/report/rpt_x/upload/tok", None), ("POST", "/product/report/rpt_x/status", None),
             ("DELETE", "/product/report/rpt_x", None), ("PUT", "/product/report/rpt_x/upload/tok", None)]
    assert [(m, p, B.classify(m, p)) for m, p, _c in cases] == cases
    from orchestrator.main import app

    def walk(routes):                    # through included routers (FastAPI 0.14x nests them), as test_web_boundary walks them
        for r in routes:
            if hasattr(r, "original_router"):
                yield from walk(r.original_router.routes)
            else:
                yield getattr(r, "path", None)
    paths = set(walk(app.routes))
    assert {"/product/report/start", "/product/reports", "/product/report/{report_id}", "/product/report/{report_id}/status",
            "/product/report/{report_id}/compile", "/product/report/{report_id}/upload/{token}"} <= paths


def test_the_report_page_sends_the_dossiers_headers():
    from orchestrator.api import adapter
    assert R.REPORT_HEADERS is adapter.REPORT_HEADERS
    csp = R.REPORT_HEADERS["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "script" not in csp and R.REPORT_HEADERS["X-Content-Type-Options"] == "nosniff"


# ───────────────────────────────────────────────────────────────── start with products
def test_start_with_products_answers_at_once_with_the_round_one_plan_and_its_first_upload_token(rig):
    g = rig
    out = _start(g, {"products": PRODUCTS, "channels": ["shopify", "tiktok_us"], "max_products": 20}, principal="prn_alice")
    _valid(out, "status_view")
    rid, token = out["report_id"], out["upload_token"]
    assert out["view"] == "start" and out["status"] == "collecting" and re.fullmatch(r"rpt_[0-9a-f]{24}", rid)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert out["candidates"]["status"] == "ready" and [c["candidate_id"] for c in out["candidates"]["items"]] == ["c1", "c2"]
    assert out["candidates"]["items"][1]["search_terms"] == ["calming dog bed", "donut pet bed"]
    assert out["request"]["max_products"] == 8 and out["request"]["channels"] == ["shopify", "tiktok_us"]
    # the round-1 plan is runnable: its upload URL carries the fresh token (public: a principal is never on this host)
    up = out["upload"]
    assert up["token"] == "minted" and up["url"] == f"https://rag.kingsleylab.xyz/product/report/{rid}/upload/{token}"
    assert out["fetch_plan"]["round"] == 1 and len(out["fetch_plan"]["packets"]) == 6 and token in out["fetch_plan"]["script"]
    assert out["rounds"] == [{"round": 1, "packets": 6, "received": 0, "complete": False}]
    assert "fetch script" in out["next"]
    # the token is shown once and stored only as its sha256
    raw = g.store.raw_row_text(rid)
    assert token not in raw and S.token_sha256(token) in raw
    assert g.store.owner_of(rid) == "prn_alice"
    # host data ran in the background as the caller's principal
    assert g.fakes.collect_calls == [{"principal_id": "prn_alice", "current": "prn_alice", "ship_to": "US", "candidates": ["c1", "c2"]}]
    st = _status(g, rid, principal="prn_alice").json()
    assert st["host"]["status"] == "done" and st["host"]["cj"] == {"c1": {"status": "OK", "reason_code": None, "products": 1},
                                                                    "c2": {"status": "OK", "reason_code": None, "products": 1}}
    assert st["host"]["ebay"]["c1"]["reason_code"] == "EBAY_NOT_CONFIGURED"
    # one receipt, kind product_report: counts and statuses only
    assert len(g.receipts) == 1
    rec = g.receipts[0]
    assert rec["kind"] == "product_report" and rec["client"] == UA and rec.get("error") is None
    meta = rec["out"]["meta"]
    assert meta["route"] == "product/report/start" and meta["product_report"] == {
        "action": "start", "report_id": rid, "status": "collecting", "products_from": "caller", "candidates": 2, "max_products": 8,
        "channels": 2, "ship_to": "US", "upload_via": "public", "fetch_packets": 6}
    assert "pet feeder" not in json.dumps(meta).lower()
    if g.backend == "postgres":
        stored = g.store.receipts([rid])
        assert len(stored) == 1 and stored[0]["principal_id"] == "prn_alice" and stored[0]["meta"]["product_report"]["candidates"] == 2
    # the compile's receipt is the caller's too (written in a worker thread, under the request's principal)
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h("prn_alice")).status_code == 200
    assert [(r["out"]["meta"]["product_report"]["action"], r["_principal"]) for r in g.receipts] == [
        ("start", "prn_alice"), ("compile", "prn_alice")]
    bad = g.client.post(f"/product/report/{rid}/compile", json={"verdicts": {"c7": "x"}}, headers=_h("prn_alice"))
    assert bad.status_code == 422 and g.receipts[-1]["error"] and g.receipts[-1]["_principal"] == "prn_alice"
    if g.backend == "postgres":
        assert sorted((r["status"], r["principal_id"]) for r in g.store.receipts([rid])) == [
            ("error", "prn_alice"), ("ok", "prn_alice"), ("ok", "prn_alice")]


def test_upload_urls_are_local_for_the_owner_here_and_public_for_a_principal_or_a_proxied_caller(rig, monkeypatch):
    g = rig
    own = _start(g)                                                          # the owner on this host
    assert own["upload"]["via"] == "local" and own["upload"]["url"].startswith("http://127.0.0.1:7200/product/report/")
    friend = _start(g, principal="prn_fred")                                 # a friend: never on this host
    assert friend["upload"]["via"] == "public" and friend["upload"]["url"].startswith("https://rag.kingsleylab.xyz/product/report/")
    asked = _start(g, {"products": PRODUCTS, "upload_base": "public"})        # Server A says the owner's agent is remote
    assert asked["upload"]["via"] == "public"
    st = _status(g, asked["report_id"]).json()                               # the start's choice is kept for its status
    assert st["upload"]["via"] == "public"
    assert _status(g, asked["report_id"], upload_base="local").json()["upload"]["via"] == "local"
    # a relayed caller is remote (the route itself sees it only after the web boundary: the web-door test runs that path)
    from starlette.requests import Request as StarletteRequest
    relayed = StarletteRequest({"type": "http", "method": "GET", "path": "/", "headers": [(b"x-forwarded-for", b"203.0.113.9")]})
    assert R.upload_target(relayed, None)[0] == "public"
    refused = g.client.get(f"/product/report/{own['report_id']}/status", headers={**_h(), "x-forwarded-for": "203.0.113.9"})
    assert refused.status_code == 403 and refused.json()["detail"]["error_code"] == "PROXIED_CALLER"   # R1 #1: no web sign-in
    monkeypatch.setenv("POLYMATH_PUBLIC_URL", "https://reports.example.test")
    assert _status(g, friend["report_id"], principal="prn_fred").json()["upload"]["url"].startswith("https://reports.example.test/")
    monkeypatch.setenv("POLYMATH_PUBLIC_URL", "")                              # no public door: the local link, said
    st = _status(g, friend["report_id"], principal="prn_fred").json()
    assert st["upload"]["via"] == "local" and st["upload"]["note"].startswith("PUBLIC_URL_UNKNOWN")


def test_start_refusals_are_typed(rig):
    g = rig
    for body, code in [({"message": "  "}, "MESSAGE_REQUIRED"), ({}, "MESSAGE_REQUIRED"),
                       ({"products": [{"title": "  "}]}, "BAD_PRODUCTS"),
                       ({"products": PRODUCTS, "ship_to": "USA"}, "BAD_SHIP_TO"), ({"products": PRODUCTS, "ship_to": "GB"}, "BAD_SHIP_TO"),
                       ({"products": PRODUCTS, "channels": ["shopify", "etsy"]}, "UNKNOWN_CHANNEL")]:
        r = g.client.post("/product/report/start", json=body, headers=_h())
        assert r.status_code == 422 and r.json()["detail"]["error_code"] == code, (body, r.text)
    assert all(rec.get("error") for rec in g.receipts) and len(g.receipts) == 6


# ───────────────────────────────────────────────────────────────── the status view and the token
def _token(url: str) -> str:
    return url.rsplit("/upload/", 1)[1]


class Clock:
    """The service's clock (R._now), moved by hand: contract C1's one-mint-a-minute rule and C9's stale compile run on it."""

    def __init__(self, monkeypatch):
        self.t = S.now() + dt.timedelta(seconds=1)
        monkeypatch.setattr(R, "_now", lambda: self.t)

    def tick(self, seconds: float) -> None:
        self.t += dt.timedelta(seconds=seconds)


@pytest.fixture()
def clock(monkeypatch):
    return Clock(monkeypatch)


def test_status_without_a_token_mints_at_most_once_a_minute_and_says_so(rig, clock):
    """Contract C1. A caller that holds no token gets a fresh one minted into the plan's URLs — but at most one per report per
    minute: inside that minute it is `required` (the placeholder, `mint_after`, no script — NEW-2: a script that cannot upload is
    withheld, `script_withheld` says why — and `next` says when to call again, or to run the script already held)."""
    g = rig
    out = _start(g, principal="prn_alice")                                     # start always mints
    rid, first = out["report_id"], out["upload_token"]
    assert out["upload"]["token"] == "minted" and "mint_after" not in out["upload"]
    st = _status(g, rid, principal="prn_alice").json()                         # no token, inside the start's minute
    _valid(st, "status_view")
    assert st["upload"]["token"] == "required" and _token(st["upload"]["url"]) == R.TOKEN_PLACEHOLDER
    plan = st["fetch_plan"]
    assert plan["script"] is None and plan["script_sha256"] is None and "upload_token" not in st          # NEW-2
    assert plan["packets"] and all("/upload/" not in c for p in plan["packets"] for c in p["commands"])  # no URL in a command
    newest = S.last_minted(g.store.row(rid))
    assert st["upload"]["mint_after"] == S.iso(newest + dt.timedelta(seconds=S.MINT_EVERY_S))
    assert st["upload"]["mint_after"] in plan["script_withheld"]
    assert st["upload"]["mint_after"] in st["next"] and "X-Upload-Token" not in st["next"]      # an MCP agent sets no header
    assert "the fetch script you already have" in st["next"]
    assert len(g.store.held(rid)) == 1                                         # nothing minted
    clock.tick(S.MINT_EVERY_S + 1)
    st = _status(g, rid, principal="prn_alice").json()                         # the minute is over: a fresh token
    _valid(st, "status_view")
    fresh = _token(st["upload"]["url"])
    assert st["upload"]["token"] == "minted" and S.TOKEN_RE.match(fresh) and fresh not in (first,)
    assert fresh in st["fetch_plan"]["script"] and "fetch script" in st["next"] and "mint_after" not in st["upload"]
    assert "script_withheld" not in st["fetch_plan"]
    raw = g.store.raw_row_text(rid)
    assert fresh not in raw and first not in raw and S.token_sha256(fresh) in raw and S.token_sha256(first) in raw
    assert g.store.held(rid) == [S.token_sha256(first), S.token_sha256(fresh)]
    assert _status(g, rid, principal="prn_alice").json()["upload"]["token"] == "required"      # and again: one a minute
    # every token the report holds uploads: the fresh one and the first one (not one-time; until the report expires)
    assert _upload(g, rid, fresh, "r1-c1-reddit", "from the status script").status_code == 200
    assert _upload(g, rid, first, "r1-c1-amazon", "from the start script").status_code == 200


def test_a_held_token_sent_back_is_reused_and_touched_and_a_wrong_one_counts_as_none(rig, clock):
    g = rig
    out = _start(g, principal="prn_alice")
    rid, first = out["report_id"], out["upload_token"]
    before = next(e for e in g.store.row(rid)["upload_tokens"] if e["sha256"] == S.token_sha256(first))
    clock.tick(5)
    reused = _status(g, rid, principal="prn_alice", token=first).json()
    _valid(reused, "status_view")
    assert reused["upload"]["token"] == "reused" and _token(reused["upload"]["url"]) == first and len(g.store.held(rid)) == 1
    after = next(e for e in g.store.row(rid)["upload_tokens"] if e["sha256"] == S.token_sha256(first))
    assert before["used_at"] is None and after["used_at"] == S.stamp(clock.t)              # its last use: touched
    other = _start(g, principal="prn_bob")
    for wrong in (other["upload_token"], S.new_upload_token(), "not-a-token"):              # another report's, unknown, malformed
        st = _status(g, rid, principal="prn_alice", token=wrong).json()
        assert st["upload"]["token"] == "required" and "mint_after" in st["upload"]       # as if none was sent (inside the minute)
    clock.tick(S.MINT_EVERY_S + 1)
    st = _status(g, rid, principal="prn_alice", token=other["upload_token"]).json()
    assert st["upload"]["token"] == "minted" and _token(st["upload"]["url"]) != other["upload_token"]
    r = _upload(g, rid, other["upload_token"], "r1-c1-alibaba")                            # another report's token: refused
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "UPLOAD_TOKEN_INVALID"


def test_polling_without_the_token_never_evicts_a_copied_token(rig, clock):
    """R3 #2 (repro A): a panel that polls every 4 s without the token used to mint 30 tokens in 2 minutes and evict a script that
    was copied but not run yet. Now a minute of polling mints at most one token: the copied one keeps working."""
    g = rig
    out = _start(g)
    rid, copied = out["report_id"], out["upload_token"]                      # the person copies the start's script
    for _ in range(S.MAX_TOKENS + 5):                                          # 35 polls x 4 s = 140 s of an open panel
        _status(g, rid)
        clock.tick(4)
    assert len(g.store.held(rid)) <= 4                                         # one a minute at most
    assert _upload(g, rid, copied, "r1-c1-reddit", "page").status_code == 200


def test_the_held_tokens_are_capped_and_a_token_in_use_is_never_the_one_dropped(rig, clock):
    g = rig
    out = _start(g)
    rid, first = out["report_id"], out["upload_token"]
    minted = []
    for _ in range(S.MAX_TOKENS - 1):
        clock.tick(S.MINT_EVERY_S + 1)
        minted.append(_token(_status(g, rid).json()["upload"]["url"]))
    assert len(g.store.held(rid)) == S.MAX_TOKENS
    clock.tick(1)
    assert _upload(g, rid, first, "r1-c1-reddit", "still running").status_code == 200   # the first token is in use again
    newest = []
    for _ in range(2):
        clock.tick(S.MINT_EVERY_S + 1)
        newest.append(_token(_status(g, rid).json()["upload"]["url"]))
    held = g.store.held(rid)
    assert len(held) == S.MAX_TOKENS and S.token_sha256(first) in held                      # used lately: kept
    assert S.token_sha256(minted[0]) not in held and S.token_sha256(minted[1]) not in held  # the two least recently active: gone
    r = _upload(g, rid, minted[0], "r1-c1-amazon")
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "UPLOAD_TOKEN_INVALID"
    assert all(_upload(g, rid, t, "r1-c1-alibaba").status_code == 200 for t in (first, minted[2], *newest))


def test_status_mints_nothing_when_no_script_can_run(rig, monkeypatch, clock):
    g = rig
    gate = threading.Event()
    monkeypatch.setattr(R.DEPS, "resolve_scope", lambda **kw: ["cinema"])
    monkeypatch.setattr(R.DEPS, "product_turn", lambda **kw: gate.wait(10) and _turn(["Smart pet feeder"]))
    forming = _start(g, {"message": "products for pet owners"}, wait=False)       # no candidates yet: no plan to run
    clock.tick(S.MINT_EVERY_S + 1)
    st = _status(g, forming["report_id"]).json()
    _valid(st, "status_view")
    assert st["fetch_plan"] is None and st["upload"]["token"] == "none" and st["upload"]["url"].endswith("/upload/UPLOAD_TOKEN")
    assert len(g.store.held(forming["report_id"])) == 1
    gate.set()
    R.wait_for_jobs(forming["report_id"])
    lapsed = _start(g)
    g.store.expire(lapsed["report_id"])                                            # the report's capability has lapsed
    clock.tick(S.MINT_EVERY_S + 1)
    st = _status(g, lapsed["report_id"]).json()
    _valid(st, "status_view")
    assert st["upload"]["token"] == "expired" and st["upload"]["url"].endswith("/upload/UPLOAD_TOKEN") and "expired" in st["next"]
    assert len(g.store.held(lapsed["report_id"])) == 1
    st = _status(g, lapsed["report_id"], token=lapsed["upload_token"]).json()      # even its own token: nothing runs any more
    assert st["upload"]["token"] == "expired" and len(g.store.held(lapsed["report_id"])) == 1


def test_the_upload_capability_refuses_with_typed_4xx(rig):
    g = rig
    a, b = _start(g, principal="prn_alice"), _start(g, principal="prn_alice")
    rid, token = a["report_id"], a["upload_token"]
    packet = a["fetch_plan"]["packets"][0]["packet_id"]

    def code(r):
        return r.status_code, r.json()["detail"]["error_code"]
    assert code(_upload(g, rid, S.new_upload_token(), packet)) == (403, "UPLOAD_TOKEN_INVALID")             # wrong token
    assert code(_upload(g, rid, "not-a-token", packet)) == (403, "UPLOAD_TOKEN_INVALID")                    # malformed
    assert code(_upload(g, rid, b["upload_token"], packet)) == (403, "UPLOAD_TOKEN_INVALID")                # another report's
    assert code(_upload(g, "rpt_" + "0" * 24, token, packet)) == (403, "UPLOAD_TOKEN_INVALID")             # no such report
    assert code(_upload(g, rid, token, None)) == (422, "PACKET_REQUIRED")
    assert code(_upload(g, rid, token, "r9-c1-nowhere")) == (404, "UNKNOWN_PACKET")
    assert code(_upload(g, rid, token, packet, b"x" * (S.MAX_UPLOAD_BYTES + 1))) == (413, "UPLOAD_TOO_LARGE")
    ok = _upload(g, rid, token, packet, b"x" * S.MAX_UPLOAD_BYTES)                                           # exactly 2 MB is fine
    assert ok.status_code == 200 and ok.json()["bytes"] == S.MAX_UPLOAD_BYTES
    g.store.expire(rid)
    assert code(_upload(g, rid, token, packet)) == (410, "UPLOAD_EXPIRED")
    st = _status(g, rid, principal="prn_alice", token=token).json()
    assert st["upload"]["expired"] is True and st["upload"]["token"] == "expired" and "expired" in st["next"]
    assert _token(st["upload"]["url"]) == R.TOKEN_PLACEHOLDER


def test_the_upload_cap_is_the_parsers_cap_and_the_boundary_holds(rig, monkeypatch):
    """ONE number: the route's cap (report_store.MAX_UPLOAD_BYTES), the parser's (agent_reach.MAX_REPORT_BYTES, which B1's packets
    carry as `expect.max_bytes`) and the migration's CHECK — 2 MiB. Exactly that many bytes are stored and parsed with no size
    refusal; one byte more is answered 413 and recorded as an OUTPUT_TOO_LARGE packet with no body (C10)."""
    from polymath_shared.acquisition import agent_reach as AR
    g = rig
    monkeypatch.delattr(R.DEPS, "parse")                                         # the real parser (B1)
    assert S.MAX_UPLOAD_BYTES == AR.MAX_REPORT_BYTES == 2 * 1024 * 1024 == 2097152
    assert "bytes       INTEGER NOT NULL CHECK (bytes BETWEEN 0 AND 2097152)" in (
        ROOT / "stores" / "postgres" / "migrations" / "0068_product_reports.sql").read_text()
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    at_cap = _upload(g, rid, token, "r1-c1-amazon", b"x" * S.MAX_UPLOAD_BYTES)
    assert at_cap.status_code == 200 and at_cap.json()["bytes"] == S.MAX_UPLOAD_BYTES
    row = g.store.upload_row(rid, "r1-c1-amazon")
    assert row["bytes"] == S.MAX_UPLOAD_BYTES and row["status"] == "UNRECOGNISED"   # read whole: not a reader's output ...
    assert [r["code"] for r in row["refused"]] == ["UNRECOGNISED_OUTPUT"]           # ... and never refused for its size
    over = _upload(g, rid, token, "r1-c1-amazon", b"x" * (S.MAX_UPLOAD_BYTES + 1))
    assert over.status_code == 413 and over.json()["detail"]["error_code"] == "UPLOAD_TOO_LARGE"
    kept = g.store.upload_row(rid, "r1-c1-amazon")                               # C10: recorded, with no body
    assert (kept["status"], kept["bytes"], [r["code"] for r in kept["refused"]]) == ("OUTPUT_TOO_LARGE", 0, ["OUTPUT_TOO_LARGE"])
    parsed = AR.parse_report_source("amazon", "x" * (AR.MAX_REPORT_BYTES + 1), kind="search")
    assert [r["code"] for r in parsed["refused"]] == ["OUTPUT_TOO_LARGE"]          # the parser's own bound is the same number


def test_an_upload_is_parsed_stored_and_replaced_on_reupload(rig):
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    r1 = _upload(g, rid, token, "r1-c1-reddit", "first thread")
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["status"] == "OK" and body["records"] == 1 and body["replaced"] is False and body["source"] == "reddit"
    assert body["candidate_id"] == "c1" and body["received"] == 1 and body["expected"] == 6 and body["round_complete"] is False
    again = _upload(g, rid, token, "r1-c1-reddit", "second thread").json()
    assert again["replaced"] is True and again["received"] == 1 and again["sha256"] != body["sha256"]
    blocked = _upload(g, rid, token, "r1-c1-alibaba", "BLOCKED page").json()
    assert blocked["status"] == "BLOCKED" and blocked["records"] == 0 and blocked["refused"] == 1
    broken = _upload(g, rid, token, "r1-c2-alibaba", "BOOM").json()                # a parser failure is stored, typed
    assert broken["status"] == "UNRECOGNISED" and broken["refused"] == 1
    empty = _upload(g, rid, token, "r1-c2-reddit", b"").json()                      # an empty output is a packet too: EMPTY
    assert empty["status"] == "EMPTY" and empty["bytes"] == 0 and empty["sha256"] == hashlib.sha256(b"").hexdigest()
    st = _status(g, rid).json()
    assert st["uploads"] == {"total": 4, "by_round": {"1": 4},
                             "by_source": {"alibaba": {"BLOCKED": 1, "UNRECOGNISED": 1}, "reddit": {"EMPTY": 1, "OK": 1}}}
    assert st["request"]["ebay_api"] is False and g.fakes.build_calls[-1]["ebay_api"] is False


def test_round_one_complete_mints_round_two_from_the_parsed_next_targets(rig):
    g = rig
    out = _start(g, principal="prn_alice")
    rid, token = out["report_id"], out["upload_token"]
    packets = [p["packet_id"] for p in out["fetch_plan"]["packets"]]
    last = None
    for i, pid in enumerate(packets):
        last = _upload(g, rid, token, pid, f"text {i}").json()
        assert last["current_round"] == (2 if i == len(packets) - 1 else 1)
    assert last["round_complete"] is True and last["received"] == 6
    st = _status(g, rid, principal="prn_alice", token=token).json()
    _valid(st, "status_view")
    assert st["round"] == 2 and st["rounds"][0] == {"round": 1, "packets": 6, "received": 6, "complete": True}
    plan2 = st["fetch_plan"]
    assert plan2["round"] == 2 and len(plan2["packets"]) == 4                     # 2 amazon targets per candidate's amazon packet
    assert {p["candidate_id"] for p in plan2["packets"]} == {"c1", "c2"} and all(p["kind"] == "page" for p in plan2["packets"])
    targets = next(c for c in g.fakes.build_calls if c["round"] == 2)["targets"]
    assert targets[0] == {"url": "https://www.amazon.com/dp/B0TEST0001", "source": "amazon", "kind": "page", "why": "top result",
                          "candidate_id": "c1"}
    # a packet of the finished round is refused; round 2's packets are taken
    r = _upload(g, rid, token, packets[0], "late")
    assert r.status_code == 409 and r.json()["detail"]["error_code"] == "ROUND_CLOSED"
    for pid in [p["packet_id"] for p in plan2["packets"]]:
        res = _upload(g, rid, token, pid, "product page").json()
        assert res["round"] == 2 and res["current_round"] == 2
    st = _status(g, rid, principal="prn_alice", token=token).json()
    assert st["rounds"][1] == {"round": 2, "packets": 4, "received": 4, "complete": True}
    assert "product_report_compile now" in st["next"]


# ───────────────────────────────────────────────────────────────── privacy and the list
def test_a_principal_reaches_only_its_own_reports_and_the_owner_reaches_all(rig):
    g = rig
    import uuid
    a_id, b_id = f"prn_alice_{uuid.uuid4().hex[:8]}", f"prn_bob_{uuid.uuid4().hex[:8]}"
    alice, bob, mine = _start(g, principal=a_id), _start(g, principal=b_id), _start(g)
    rid = alice["report_id"]
    for path, method in ((f"/product/report/{rid}/status", "get"), (f"/product/report/{rid}", "get"),
                         (f"/product/report/{rid}/compile", "post")):
        r = getattr(g.client, method)(path, headers=_h(b_id))
        assert r.status_code == 404 and r.json()["detail"]["error_code"] == "REPORT_NOT_FOUND", (path, r.text)
    # "not yours" and "no such report" are one answer
    assert _status(g, "rpt_" + "f" * 24, principal=b_id).json() == _status(g, rid, principal=b_id).json()
    assert _status(g, rid, principal=a_id).status_code == 200 and _status(g, rid).status_code == 200            # the owner
    assert _status(g, mine["report_id"], principal=a_id).status_code == 404                                    # owner's own: private
    lists = {p: g.client.get("/product/reports", headers=_h(p)).json() for p in (a_id, b_id, None)}
    assert [r["report_id"] for r in lists[a_id]["reports"]] == [rid]
    assert [r["report_id"] for r in lists[b_id]["reports"]] == [bob["report_id"]]
    everyone = {r["report_id"]: r for r in lists[None]["reports"]}
    assert {rid, bob["report_id"], mine["report_id"]} <= set(everyone)
    assert everyone[rid]["owner_principal_id"] == a_id and "owner_principal_id" not in lists[a_id]["reports"][0]
    item = lists[a_id]["reports"][0]
    assert item["candidates"] == [{"candidate_id": "c1", "title": "Automatic pet feeder"},
                                  {"candidate_id": "c2", "title": "Calming dog bed"}]
    assert item["compiled"] is False and item["uploads"] == 0 and item["report_path"] == f"/product/report/{rid}"
    assert "upload_token_sha256" not in json.dumps(lists)


# ───────────────────────────────────────────────────────────────── start without products: the background product turn
def _turn(titles, *, verdict="product_hypotheses"):
    return {"verdict": verdict, "model": "fake", "product_research": {
        "corpus_ids": ["cinema"], "hypotheses": [{"id": f"h{i + 1}", "title": t, "problem": "p", "audience": "pet owners",
                                                  "evidence_tags": ["S1"], "search_terms": [t.lower()], "confidence": "medium"}
                                                 for i, t in enumerate(titles)]}}


def test_start_without_products_returns_at_once_and_the_product_turn_runs_in_the_background(rig, monkeypatch):
    g = rig
    gate, seen = threading.Event(), []

    def turn(**kw):
        seen.append({**kw, "current": principal_context.current()})
        assert gate.wait(10)
        kw["receipt_ids"].append("q_the_product_turn")                         # the turn's own receipt (C6: kept on the report)
        return _turn(["Smart pet feeder", "Calming dog bed", "Cat water fountain"])
    monkeypatch.setattr(R.DEPS, "product_turn", turn)
    monkeypatch.setattr(R.DEPS, "resolve_scope", lambda **kw: ["cinema"])
    t0 = time.perf_counter()
    out = _start(g, {"message": "what should I sell to pet owners?", "corpus_id": "cinema", "max_products": 2},
                 principal="prn_alice", wait=False)
    assert time.perf_counter() - t0 < 3.0                                      # never waits for the product turn
    _valid(out, "status_view")
    rid = out["report_id"]
    assert out["status"] == "collecting" and out["candidates"] == {"status": "collecting", "source": "product_route", "items": [],
                                                                    "error": None, "note": None, "product_turn_receipt_id": None,
                                                                    "product_turn_receipt_ids": []}
    assert out["fetch_plan"] is None and out["rounds"] == [] and "forming the product candidates" in out["next"]
    assert out["host"]["status"] == "pending" and out["request"]["products_from"] == "product_route"
    gate.set()
    R.wait_for_jobs(rid)
    assert seen[0]["current"] == "prn_alice" and seen[0]["geography"] == "US" and seen[0]["corpus_id"] == "cinema"
    st = _status(g, rid, principal="prn_alice", token=out["upload_token"]).json()
    _valid(st, "status_view")
    assert [c["title"] for c in st["candidates"]["items"]] == ["Smart pet feeder", "Calming dog bed"]   # max_products
    assert st["candidates"]["items"][0]["source"] == "product_route" and st["candidates"]["status"] == "ready"
    assert st["host"]["status"] == "done" and g.fakes.collect_calls[0]["current"] == "prn_alice"
    assert st["fetch_plan"]["round"] == 1 and out["upload_token"] in st["fetch_plan"]["script"]
    assert st["candidates"]["product_turn_receipt_id"] == "q_the_product_turn"
    rec = g.receipts[-1]
    assert rec["out"]["meta"]["product_report"]["products_from"] == "product_route" and rec["scope_corpora"] == ["cinema"]
    assert rec["scope_kind"] == "corpus" and rec["question"] == "what should I sell to pet owners?"


def test_a_product_turn_that_forms_nothing_or_fails_leaves_a_typed_failed_report(rig, monkeypatch):
    g = rig
    monkeypatch.setattr(R.DEPS, "resolve_scope", lambda **kw: ["cinema"])
    outcomes = iter([_turn([]), _turn([]),                     # no idea and no search word, twice (a turn with none is retried)
                     HTTPException(404, {"error_code": "QUERY_SCOPE_EMPTY", "message": "nothing to search"}),
                     RuntimeError("model down")])

    def turn(**kw):
        nxt = next(outcomes)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt
    monkeypatch.setattr(R.DEPS, "product_turn", turn)
    codes = []
    for _ in range(3):
        out = _start(g, {"message": "products for pet owners"})
        st = _status(g, out["report_id"]).json()
        _valid(st, "status_view")
        assert st["status"] == "failed" and st["candidates"]["status"] == "failed" and st["fetch_plan"] is None
        assert "start a new report with products" in st["next"]
        codes.append(st["candidates"]["error"]["error_code"])
        r = g.client.post(f"/product/report/{out['report_id']}/compile", json={}, headers=_h())
        assert r.status_code == 409 and r.json()["detail"]["error_code"] == "NO_CANDIDATES"
    assert codes == ["NO_CANDIDATES", "QUERY_SCOPE_EMPTY", "PRODUCT_TURN_FAILED"]


def test_a_scope_refusal_is_typed_at_start(rig, monkeypatch):
    g = rig

    def refuse(**kw):
        raise HTTPException(404, {"error_code": "QUERY_SCOPE_EMPTY", "message": "no library for this caller"})
    monkeypatch.setattr(R.DEPS, "resolve_scope", refuse)
    r = g.client.post("/product/report/start", json={"message": "products for pet owners"}, headers=_h("prn_alice"))
    assert r.status_code == 404 and r.json()["detail"]["error_code"] == "QUERY_SCOPE_EMPTY"
    assert g.receipts[-1]["error"] and g.receipts[-1]["kind"] == "product_report"


def test_start_without_products_runs_the_product_routes_own_machinery(rig, monkeypatch):
    """The real `product._forced_turn` (and `product._resolve_corpora`) on the chat-runtime harness: retrieval, the LLM and the
    supplier faked; the turn runs in the background as the caller's principal and its hypotheses become the candidates."""
    from orchestrator.api import product as product_mod
    from orchestrator.api import ui
    from test_chat_runtime import _fake_tx
    from test_product_runtime import Product
    g = rig
    p = Product(monkeypatch)
    monkeypatch.setattr(product_mod, "tx", _fake_tx)
    monkeypatch.setattr(ui, "_default_synthesizer", lambda: "ollama:fake")
    out = _start(g, {"message": "what should I sell to pet owners in the US?", "corpus_id": "cinema"}, principal="prn_fred",
                 wait=False)
    assert out["candidates"]["status"] == "collecting"
    R.wait_for_jobs(out["report_id"])
    st = _status(g, out["report_id"], principal="prn_fred").json()
    assert [c["title"] for c in st["candidates"]["items"]] == ["Smart pet feeder", "Calming dog bed"]
    assert st["candidates"]["items"][0]["search_terms"] == ["automatic pet feeder"]
    assert p.engine_calls and {c["principal_id"] for c in p.calls} == {"prn_fred"}          # retrieval ran; CJ as the principal
    kinds = [r["kind"] for r in g.receipts]
    assert kinds == ["product_report", "product"]                                          # the start's, then the product turn's own
    assert st["host"]["status"] == "done"


# ───────────────────────────────────────────────────────────────── compile, the page
def _fill(g, out):
    """Upload every packet of round 1, then of round 2; returns the status after both."""
    rid, token = out["report_id"], out["upload_token"]
    for _ in range(2):
        st = _status(g, rid, token=token).json()
        for p in st["fetch_plan"]["packets"]:
            assert _upload(g, rid, token, p["packet_id"], f"{p['source']} text for {p['candidate_id']}").status_code == 200
    return _status(g, rid, token=token).json()


def test_compile_builds_the_plan_bundle_stores_the_model_html_and_the_agents_verdicts(rig):
    g = rig
    out = _start(g, {"products": PRODUCTS, "channels": ["shopify", "tiktok_us"]})
    rid = out["report_id"]
    _fill(g, out)
    r = g.client.post(f"/product/report/{rid}/compile", json={"verdicts": {"c1": "Strong demand, ships slowly.", "c2": "  "},
                                                              "agent_identity": "claude-code"}, headers=_h())
    assert r.status_code == 200, r.text[:600]
    res = r.json()
    _valid(res, "compile_view")
    _valid(res)
    assert res["status"] == "compiled" and res["report_url"] == f"http://127.0.0.1:7200/product/report/{rid}"
    assert res["verdicts"] == {"c1": {"by": "agent", "chars": len("Strong demand, ships slowly.")}}
    assert res["settings"] == {"returns_rate": 0.193, "shopify_monthly_orders": 100, "as_of": dt.datetime.now(dt.UTC).date().isoformat(),
                               "ship_to": "US", "channels": ["shopify", "tiktok_us"]}
    assert res["inputs"] == {"candidates": 2, "uploads": 10, "host": "done",
                             "records": {"reddit": 2, "amazon": 6, "ebay": 0, "alibaba": 2}}
    assert res["summary"][0]["channels"]["shopify"]["delivery"] == "WARN" and res["summary"][0]["reference_price_usd"] == 29.99
    assert res["html_sha256"] == hashlib.sha256(DECISION_HTML.encode()).hexdigest()
    # the bundle: plan §4.4's four keys (candidates, host = B2's output, parsed per candidate, settings), plus what only the page
    # reads (B4a render_decision): the agent's verdicts, the report id, a title, and per Agent Reach source what was read (C11)
    bundle = g.fakes.render_bundles[-1]
    assert set(bundle) == {"candidates", "host", "parsed", "settings", "verdicts", "report_id", "title", "sources"}
    assert [c["candidate_id"] for c in bundle["candidates"]] == ["c1", "c2"] and bundle["host"]["cj"]["c1"]["status"] == "OK"
    assert set(bundle["parsed"]) == {"c1", "c2"} and set(bundle["parsed"]["c1"]) == {"reddit", "amazon", "ebay", "alibaba"}
    assert [x["title"] for x in bundle["parsed"]["c1"]["amazon"]] == ["amazon text for c1"] * 3       # round 1, then round 2
    assert bundle["verdicts"] == {"c1": "Strong demand, ships slowly."}
    assert bundle["report_id"] == rid and bundle["title"] == "Automatic pet feeder; Calming dog bed"
    assert bundle["settings"] == res["settings"]
    # stored: status compiled, the page under the CSP, verdicts as the agent's
    st = _status(g, rid).json()
    assert st["status"] == "compiled" and st["compiled"]["at"] == res["compiled_at"] and st["compiled"]["stale"] is False
    assert st["compiled"]["report_url"] == res["report_url"] and "The report is compiled" in st["next"]
    page = g.client.get(f"/product/report/{rid}", headers=_h())
    assert page.status_code == 200 and page.text == DECISION_HTML
    assert page.headers["content-security-policy"] == R.REPORT_HEADERS["Content-Security-Policy"]
    assert "script-src" not in page.headers["content-security-policy"] and "default-src 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff" and page.headers["cache-control"] == "no-store"
    dl = g.client.get(f"/product/report/{rid}", params={"download": 1}, headers=_h())
    assert dl.headers["content-disposition"] == f'attachment; filename="product-report-{rid}.html"'
    raw = g.store.raw_row_text(rid)
    assert '"by": "agent"' in raw.replace('"by":"agent"', '"by": "agent"') and "claude-code" in raw
    # a compile without verdicts keeps the stored ones; one receipt per compile, counts only
    again = g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()
    assert again["verdicts"] == res["verdicts"]
    comp = [x for x in g.receipts if (x.get("out") or {}).get("meta", {}).get("route") == "product/report/compile"]
    assert len(comp) == 2 and comp[0]["out"]["meta"]["product_report"] == {
        "action": "compile", "report_id": rid, "candidates": 2, "uploads": 10, "host": "done",
        "records": {"reddit": 2, "amazon": 6, "ebay": 0, "alibaba": 2}, "verdicts": 1, "status": "compiled",
        "html_bytes": len(DECISION_HTML)}
    assert "Strong demand" not in json.dumps([{k: v for k, v in x.items() if k != "req"} for x in comp])   # what a receipt stores
    _valid(_status(g, rid).json(), "status_view")


def test_compile_refusals_and_a_failed_render_are_typed_and_retryable(rig):
    g = rig
    g.fakes.collect_gate = threading.Event()
    out = _start(g, wait=False)
    rid = out["report_id"]
    r = g.client.post(f"/product/report/{rid}/compile", json={}, headers=_h())
    assert r.status_code == 409 and r.json()["detail"]["error_code"] == "HOST_DATA_PENDING"
    g.fakes.collect_gate.set()
    R.wait_for_jobs(rid)
    for verdicts, code in (({"c9": "x"}, "UNKNOWN_CANDIDATE"), ({"c1": "x" * 1201}, "VERDICT_TOO_LONG")):
        r = g.client.post(f"/product/report/{rid}/compile", json={"verdicts": verdicts}, headers=_h())
        assert r.status_code == 422 and r.json()["detail"]["error_code"] == code
    assert g.client.post(f"/product/report/{rid}/compile", json={"verdicts": {"c1": "x" * 1200}}, headers=_h()).status_code == 200
    # a render failure: typed, the report left `failed` with the error, the last good page still served; a retry compiles
    g.fakes.render_error = type("DossierError", (RuntimeError,), {"code": "DECISION_TIMEOUT"})("slow")
    r = g.client.post(f"/product/report/{rid}/compile", json={}, headers=_h())
    assert r.status_code == 504 and r.json()["detail"]["error_code"] == "DECISION_TIMEOUT"
    st = _status(g, rid).json()
    _valid(st, "status_view")
    assert st["status"] == "failed" and st["compiled"]["error"]["error_code"] == "DECISION_TIMEOUT" and "compile failed" in st["next"]
    assert g.client.get(f"/product/report/{rid}", headers=_h()).status_code == 200
    g.fakes.render_error = ValueError("bad bundle")
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()["detail"]["error_code"] == "RENDER_FAILED"
    g.fakes.render_error = None
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()["status"] == "compiled"
    assert _status(g, rid).json()["compiled"]["error"] is None


def test_an_uncompiled_report_has_no_page_and_a_new_upload_makes_the_compiled_one_stale(rig):
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    r = g.client.get(f"/product/report/{rid}", headers=_h())
    assert r.status_code == 404 and r.json()["detail"]["error_code"] == "NOT_COMPILED"
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).status_code == 200    # host data only: allowed
    _upload(g, rid, token, out["fetch_plan"]["packets"][0]["packet_id"], "later page")      # the same second: still stale (R3 #4)
    st = _status(g, rid).json()
    assert st["status"] == "compiled" and st["compiled"]["stale"] is True and "fetch script" in st["next"]


def test_a_lost_compile_can_be_started_again(rig, clock):
    """C9 (R3 #3, repro B): a compile a restart lost stays `compiling`. Older than COMPILE_STALE_S by `compile_started_at` (not
    `updated_at`, which every upload bumps), status says to compile again and compile does; a younger one is still in progress."""
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    g.store.set_compiling(rid, 3600)                                                  # an hour-old compile: certainly lost
    st = _status(g, rid).json()
    _valid(st, "status_view")
    assert st["status"] == "compiling" and "call product_report_compile again" in st["next"] and st["compile_started_at"]
    assert _upload(g, rid, token, out["fetch_plan"]["packets"][0]["packet_id"], "a script still uploading").status_code == 200
    assert "call product_report_compile again" in _status(g, rid).json()["next"]     # an upload does not make it fresh
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()["status"] == "compiled"
    g.store.set_compiling(rid, 10)                                                    # a compile that started 10 s ago
    assert "call product_report_status again" in _status(g, rid).json()["next"]
    r = g.client.post(f"/product/report/{rid}/compile", headers=_h())
    assert r.status_code == 409 and r.json()["detail"]["error_code"] == "COMPILE_IN_PROGRESS"
    clock.tick(R.COMPILE_STALE_S + 1)                                                 # ... until it is stale too
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()["status"] == "compiled"


# ───────────────────────────────────────────────────────────────── the web boundary in front of the routes
def test_through_the_web_door_the_upload_needs_no_session_and_everything_else_does(rig, tmp_path, monkeypatch):
    from orchestrator.api import web_auth

    from orchestrator import web_accounts as W
    from orchestrator import web_boundary as B
    g = rig
    reg = tmp_path / "principals.json"
    monkeypatch.setenv("POLYMATH_MCP_PRINCIPALS_FILE", str(reg))
    monkeypatch.setenv("POLYMATH_WEB_SESSION_SECRET", "k" * 48)
    W.set_owner_password(reg, "correct horse battery")
    W.add_friend(reg, "fred", "correct horse battery", corpus_ids=["cinema"], must_change=False)
    monkeypatch.setattr(web_auth, "THROTTLE", W.LoginThrottle())
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.add_middleware(B.WebBoundaryMiddleware)
    app.include_router(web_auth.router)
    app.include_router(R.router)
    web = TestClient(app, base_url="https://testserver", headers={"x-forwarded-for": "203.0.113.9"})
    assert web.get("/product/reports").json()["detail"]["error_code"] == "LOGIN_REQUIRED"
    assert web.post("/product/report/start", json={"products": PRODUCTS}).json()["detail"]["error_code"] == "LOGIN_REQUIRED"
    r = web.post("/auth/login", json={"username": "fred", "password": "correct horse battery"})
    assert r.status_code == 200, r.text
    csrf = web.cookies.get(W.CSRF_COOKIE)
    assert web.post("/product/report/start", json={"products": PRODUCTS}).json()["detail"]["error_code"] == "CSRF_FAILED"
    out = web.post("/product/report/start", json={"products": PRODUCTS}, headers={W.CSRF_HEADER: csrf}).json()
    g.created.append(out["report_id"])
    R.wait_for_jobs(out["report_id"])
    rid, token = out["report_id"], out["upload_token"]
    fred = next(r["principal_id"] for r in W.read_registry(reg)["principals"] if (r.get("web") or {}).get("username") == "fred")
    assert g.store.owner_of(rid) == fred
    assert out["upload"]["via"] == "public" and out["upload"]["url"].startswith("https://rag.kingsleylab.xyz/")
    # the script's upload: no cookie, no CSRF header, a principal header it tries to send is dropped
    script = TestClient(app, base_url="https://testserver", headers={"x-forwarded-for": "198.51.100.7"})
    up = script.post(f"/product/report/{rid}/upload/{token}", params={"packet": "r1-c1-reddit"}, content=b"thread text",
                     headers={"content-type": "text/plain", "X-Polymath-Principal": "prn_mallory"})
    assert up.status_code == 200, up.text
    bad = script.post(f"/product/report/{rid}/upload/{S.new_upload_token()}", params={"packet": "r1-c1-reddit"}, content=b"x")
    assert bad.status_code == 403 and bad.json()["detail"]["error_code"] == "UPLOAD_TOKEN_INVALID"
    assert script.get(f"/product/report/{rid}/status").json()["detail"]["error_code"] == "LOGIN_REQUIRED"
    st = web.get(f"/product/report/{rid}/status").json()
    assert st["uploads"]["total"] == 1 and st["upload"]["via"] == "public"


# ───────────────────────────────────────────────────────────────── the contract
def test_the_contract_example_validates_and_matches_the_live_shapes(rig):
    g = rig
    _valid(EXAMPLE["status"], "status_view")
    _valid(EXAMPLE["compile"], "compile_view")
    _valid(EXAMPLE["status"])
    _valid(EXAMPLE["compile"])
    out = _start(g)
    st = _fill(g, out)
    res = g.client.post(f"/product/report/{out['report_id']}/compile", json={"verdicts": {"c1": "worth a test order"}}, headers=_h()).json()
    for live, ex in ((st, EXAMPLE["status"]), (res, EXAMPLE["compile"])):
        assert set(live) == set(ex), set(live) ^ set(ex)
    with pytest.raises(jsonschema.ValidationError):                      # a status view never carries the token
        _valid({**st, "upload_token": out["upload_token"]}, "status_view")
    with pytest.raises(jsonschema.ValidationError):
        _valid({**res, "status": "collecting"}, "compile_view")


# ───────────────────────────────────────────────────────────────── the real slices, on the recorded fixtures of 2026-11-02
FIXTURES = ROOT / "tests" / "fixtures" / "product_report"
E2E_PRODUCTS = [{"title": "Candle warmer lamp", "search_terms": ["candle warmer"]},
                {"title": "Self-cleaning slicker brush", "search_terms": ["self cleaning slicker brush"]}]
#: (candidate, packet kind) -> what the user's Agent Reach printed for that read (recorded 2026-11-02; B1's fixtures)
ROUND1_OUTPUT = {("c1", "reddit-1"): "exa_reddit_candle.out",            # 0 bytes: an empty output, stored as EMPTY
                 ("c1", "reddit-2"): "exa_reddit_candle_r2.out", ("c1", "amazon-1"): "exa_amazon_candle.out",
                 ("c1", "amazon-2"): "jina_amazon_search.out", ("c1", "alibaba-1"): "exa_alibaba_candle.out",
                 ("c1", "ebay-1"): "exa_ebay_candle.out",
                 ("c2", "reddit-1"): "exa_reddit_brush.out", ("c2", "reddit-2"): "exa_reddit_brush.out",
                 ("c2", "amazon-1"): "exa_amazon_brush.out", ("c2", "amazon-2"): "jina_amazon_search_links.out",
                 ("c2", "alibaba-1"): "exa_alibaba_brush.out", ("c2", "ebay-1"): "exa_ebay_brush.out"}
ROUND2_OUTPUT = {("c1", "amazon"): "jina_amazon_product.out", ("c1", "alibaba"): "jina_alibaba_B_retry.out",
                 ("c2", "amazon"): "jina_amazon_product.out", ("c2", "alibaba"): "jina_alibaba_A.out"}


def _recorded_supplier():
    """B2's own recorded CJ double (tests/contracts/test_report_host_data.py: the supplier tools' real answers of 2026-11-02), or
    None when a slice has not landed in this checkout."""
    try:
        from polymath_shared.acquisition import agent_reach
        from polymath_shared.adapter import dossier
        from polymath_shared.product_search import fetch_plan, host_data  # noqa: F401
        try:
            from contracts.test_report_host_data import Recorded
        except ImportError:
            sys.path.insert(0, str(ROOT / "tests" / "contracts"))
            from test_report_host_data import Recorded
    except ImportError:
        return None
    if not (hasattr(agent_reach, "parse_report_source") and hasattr(dossier, "render_decision")):
        return None
    return Recorded


@pytest.mark.skipif(_recorded_supplier() is None, reason="B1 / B2 / B4a have not landed in this checkout")
def test_end_to_end_with_the_real_slices_on_recorded_fixtures(rig, monkeypatch):
    """B1 `fetch_plan.build` and `parse_report_source`, B2 `host_data.collect` (its recorded CJ double, no eBay keys) and B4a
    `render_decision` (the engine, B3's unit economics) — all REAL; only the network is replaced by what it answered on 2026-11-02."""
    from polymath_shared.product_search import host_data
    g = rig
    recorded = _recorded_supplier()()
    for name in ("build_plan", "parse", "render"):
        monkeypatch.delattr(R.DEPS, name)                                    # the class's own: the real slices
    monkeypatch.setattr(R.DEPS, "collect", lambda cands, *, principal_id, ship_to="US": host_data.collect(
        cands, principal_id=principal_id, ship_to=ship_to, supplier_fns=recorded, env={}, sleep=lambda s: None))
    out = _start(g, {"products": E2E_PRODUCTS})
    _valid(out, "status_view")
    rid, token = out["report_id"], out["upload_token"]
    plan1 = out["fetch_plan"]
    assert plan1["round"] == 1 and plan1["script_sha256"] == hashlib.sha256(plan1["script"].encode()).hexdigest()
    assert out["upload"]["url"] in plan1["script"] and not re.search(r"(^|[;&|(\s])eval\s", plan1["script"])   # no eval
    assert all(p["expect"]["max_bytes"] == S.MAX_UPLOAD_BYTES for p in plan1["packets"])   # B1's packets: the route's cap
    kinds = {(p["candidate_id"], p["packet_id"].split("-", 2)[2]) for p in plan1["packets"]}
    assert kinds == set(ROUND1_OUTPUT), kinds ^ set(ROUND1_OUTPUT)          # eBay through Exa: this host has no eBay keys
    st = _status(g, rid).json()
    assert st["host"]["status"] == "done" and st["host"]["cj"]["c2"]["status"] and recorded.calls       # CJ, recorded
    statuses = {}
    for p in plan1["packets"]:
        body = (FIXTURES / ROUND1_OUTPUT[(p["candidate_id"], p["packet_id"].split("-", 2)[2])]).read_bytes()
        r = _upload(g, rid, token, p["packet_id"], body)
        assert r.status_code == 200, (p["packet_id"], r.text[:300])
        statuses[p["packet_id"]] = r.json()["status"]
    assert statuses["r1-c1-reddit-1"] == "EMPTY" and statuses["r1-c2-reddit-1"] == "OK" and statuses["r1-c2-amazon-2"] == "OK"
    st = _status(g, rid, token=token).json()
    _valid(st, "status_view")
    assert st["round"] == 2 and st["rounds"][0]["complete"] is True
    plan2 = st["fetch_plan"]
    assert plan2["round"] == 2 and plan2["packets"], "round 2 reads the product pages round 1 found"
    assert all(p["kind"] == "page" and p["source"] in ("amazon", "alibaba") for p in plan2["packets"])
    assert sum(1 for p in plan2["packets"] if p["candidate_id"] == "c2" and p["source"] == "amazon") <= 3
    for p in plan2["packets"]:
        r = _upload(g, rid, token, p["packet_id"], (FIXTURES / ROUND2_OUTPUT[(p["candidate_id"], p["source"])]).read_bytes())
        assert r.status_code == 200 and r.json()["round"] == 2, r.text[:300]
    st = _status(g, rid, token=token).json()
    assert all(r["complete"] for r in st["rounds"]) and "product_report_compile now" in st["next"]
    res = g.client.post(f"/product/report/{rid}/compile",
                        json={"verdicts": {"c2": "Steady Reddit praise; CN shipping fails TikTok US, fine for Shopify."}}, headers=_h())
    assert res.status_code == 200, res.text[:800]
    comp = res.json()
    _valid(comp, "compile_view")
    assert [p["candidate_id"] for p in comp["summary"]] == ["c1", "c2"] and comp["inputs"]["records"]["reddit"] > 0
    page = g.client.get(f"/product/report/{rid}", headers=_h())
    assert page.status_code == 200 and "Self-cleaning slicker brush" in page.text and "<script" not in page.text.lower()
    assert "Steady Reddit praise" in page.text                                # the agent's verdict, on the page
    assert page.headers["content-security-policy"] == R.REPORT_HEADERS["Content-Security-Policy"]
    _valid(_status(g, rid).json(), "status_view")


# ───────────────────────────────────────────────────────────────── review-fix round (R1 security, R3 reliability)
def _main_like_app():
    """main.py's middleware stack and the routes at stake: the report routes, /product/search and the supplier routes."""
    from orchestrator.api import acquisition
    from orchestrator.api import product as product_mod

    from orchestrator import web_boundary as B
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.add_middleware(B.WebBoundaryMiddleware)
    app.include_router(R.router)
    app.include_router(product_mod.router)
    app.include_router(acquisition.router)
    return app


def test_a_rebound_page_reaches_no_report_route_and_no_product_search(rig):
    """R1 #1 (DNS rebinding; the secreview repro): a page that re-bound its own name to 127.0.0.1 calls :7200 directly, with no
    proxy header and ITS Host. Every report route and /product/search now refuse it exactly as the supplier routes do (B-28):
    403 NON_LOOPBACK_HOST, before anything is read, minted, written or spent."""
    g = rig
    out = _start(g, principal="prn_friend_alice")                             # a friend's private report
    rid, token = out["report_id"], out["upload_token"]
    assert g.client.post(f"/product/report/{rid}/compile", json={}, headers=_h("prn_friend_alice")).status_code == 200
    held, receipts = list(g.store.held(rid)), len(g.receipts)
    evil = TestClient(_main_like_app(), base_url="http://rebind.attacker.example:7200")
    assert evil.get("/supplier/warehouses").json()["detail"]["code"] == "NON_LOOPBACK_HOST"          # the control
    calls = [("get", "/product/reports", None), ("get", f"/product/report/{rid}", None),
             ("get", f"/product/report/{rid}/status", None), ("post", f"/product/report/{rid}/compile", {}),
             ("post", "/product/report/start", {"products": PRODUCTS}), ("post", "/product/search", {"message": "pet products"})]
    for method, path, body in calls:
        r = getattr(evil, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (path, r.status_code, r.text[:200])
        assert r.json()["detail"]["error_code"] == r.json()["detail"]["code"] == "NON_LOOPBACK_HOST", path
    up = evil.post(f"/product/report/{rid}/upload/{token}", params={"packet": "r1-c1-reddit"}, content=b"attacker text",
                   headers={"content-type": "text/plain"})
    assert up.status_code == 403 and up.json()["detail"]["error_code"] == "NON_LOOPBACK_HOST"
    assert g.store.held(rid) == held and len(g.receipts) == receipts            # nothing minted, nothing receipted
    with pytest.raises(KeyError):
        g.store.upload_row(rid, "r1-c1-reddit") if g.backend == "memory" else (_ for _ in ()).throw(KeyError())
    # the same calls from this host (Server A at 127.0.0.1) and a relayed request that skipped the web boundary
    local = TestClient(_main_like_app(), base_url="http://127.0.0.1:7200")
    assert local.get(f"/product/report/{rid}/status", headers=_h("prn_friend_alice")).status_code == 200
    relayed = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers={**_h(), "x-forwarded-for": "198.51.100.1"})
    assert relayed.status_code == 403 and relayed.json()["detail"]["error_code"] == "PROXIED_CALLER"


def test_an_upload_with_a_bad_capability_reads_no_body(rig, monkeypatch):
    """R1 #3 (the secreview repro): the capability is checked before the body is read — a malformed one costs no read and no
    transaction, a well-formed wrong one one transaction and no read; a refused upload stores nothing."""
    from orchestrator import web_boundary as B
    g = rig
    out = _start(g)
    rid = out["report_id"]
    seen = {"bytes": [], "tx": 0}
    real_read, real_tx = R._read_capped, R.tx

    async def spy_read(request, limit):
        got = await real_read(request, limit)
        seen["bytes"].append(len(got[0]))
        return got

    def spy_tx():
        seen["tx"] += 1
        return real_tx()
    monkeypatch.setattr(R, "_read_capped", spy_read)
    monkeypatch.setattr(R, "tx", spy_tx)
    app = FastAPI()
    app.add_middleware(PrincipalContextMiddleware)
    app.add_middleware(B.WebBoundaryMiddleware)
    app.include_router(R.router)
    door = TestClient(app, base_url="https://rag.kingsleylab.xyz", headers={"x-forwarded-for": "198.51.100.66"})
    body = b"x" * S.MAX_UPLOAD_BYTES
    r = door.post("/product/report/not-a-report/upload/not-a-token", params={"packet": "p"}, content=body,
                  headers={"content-type": "text/plain"})
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "UPLOAD_TOKEN_INVALID"
    assert seen == {"bytes": [], "tx": 0}
    r = door.post(f"/product/report/{rid}/upload/{S.new_upload_token()}", params={"packet": "r1-c1-reddit"}, content=body,
                  headers={"content-type": "text/plain"})
    assert r.status_code == 403 and r.json()["detail"]["error_code"] == "UPLOAD_TOKEN_INVALID"
    assert seen == {"bytes": [], "tx": 1}
    r = door.post(f"/product/report/{rid}/upload/{out['upload_token']}", params={"packet": "r9-nowhere"}, content=body,
                  headers={"content-type": "text/plain"})
    assert r.status_code == 404 and r.json()["detail"]["error_code"] == "UNKNOWN_PACKET" and seen["bytes"] == []


def test_one_principal_runs_one_report_job_at_a_time(rig, monkeypatch):
    """R1 #2 / C8: a principal whose report is still gathering its data gets 429 REPORT_JOB_RUNNING (retry_after_s, the running
    report) on its next start; another principal — the owner here — is never queued behind it."""
    g = rig
    gate = threading.Event()
    real_collect = g.fakes.collect

    def collect(candidates, *, principal_id, ship_to="US"):
        if principal_id == "prn_friend_alice":
            assert gate.wait(10)
        return real_collect(candidates, principal_id=principal_id, ship_to=ship_to)
    monkeypatch.setattr(R.DEPS, "collect", collect)
    first = _start(g, principal="prn_friend_alice", wait=False)
    busy = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h("prn_friend_alice"))
    assert busy.status_code == 429 and busy.headers["retry-after"] == str(R.JOB_RETRY_AFTER_S)
    assert busy.json()["detail"] == {"error_code": "REPORT_JOB_RUNNING", "retry_after_s": R.JOB_RETRY_AFTER_S,
                                     "report_id": first["report_id"], "message": busy.json()["detail"]["message"]}
    assert g.receipts[-1]["error"] and "REPORT_JOB_RUNNING" in g.receipts[-1]["error"]
    owner = _start(g)                                                          # not queued behind the friend's job
    assert _status(g, owner["report_id"]).json()["host"]["status"] == "done"
    assert _status(g, first["report_id"], principal="prn_friend_alice").json()["host"]["status"] in ("pending", "collecting")
    gate.set()
    R.wait_for_jobs(first["report_id"])
    assert _start(g, principal="prn_friend_alice")["status"] == "collecting"   # its job done: the next start is served
    assert all(job["thread"].daemon for job in R._JOBS.values())


def test_background_jobs_never_hold_up_a_restart():
    """R3 #1: a stage runs on a DAEMON thread, so the interpreter exits at once with a long stage still running (a non-daemon
    pool made uvicorn's exit wait for every running and queued job: 8.47 s for 6 x 4 s jobs in the review)."""
    import subprocess
    code = ("import time\n"
            "from orchestrator.api import product_report as R\n"
            "for n in range(6):\n"
            "    R._launch(f'rpt_{n:024x}', 'host', f'prn_p{n}', lambda: time.sleep(60))\n"
            "print(all(j['thread'].daemon and j['thread'].is_alive() for j in R._JOBS.values()), len(R._JOBS))\n")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": os.pathsep.join(str(ROOT / d) for d in ("shared", "orchestrator")),
           "POLYMATH_PG_DSN": "postgresql://nobody:x@127.0.0.1:1/none", "HOME": os.environ.get("HOME", "/tmp")}
    t0 = time.monotonic()
    done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    assert done.stdout.split() == ["True", "6"] and time.monotonic() - t0 < 20


def test_a_report_upload_token_never_reaches_a_log_line(monkeypatch):
    """R1 #4: the access log line of an upload carries its token (a token uploads for 6 hours); through the real formatter it is
    redacted, the report id stays readable."""
    import io
    import logging

    from orchestrator import json_logging as J
    root = logging.getLogger()
    saved = (list(root.handlers), root.level, {n: list(logging.getLogger(n).handlers) for n in J.UVICORN_LOGGERS})
    buf = io.StringIO()
    try:
        J.configure_orchestrator_logging(buf, force=True, secrets=[])
        token, rid = S.new_upload_token(), S.new_report_id()
        logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "203.0.113.9:5121", "POST",
                                                 f"/product/report/{rid}/upload/{token}?packet=r1-c1-reddit-1", "1.1", 200)
        line = json.loads(buf.getvalue().strip().splitlines()[-1])
        assert line["event"] == "uvicorn.access" and token not in buf.getvalue()
        assert f"/product/report/{rid}/upload/<redacted>?packet=r1-c1-reddit-1" in line["message"]
        assert J.redact(f"/product/report/{rid}/upload/UPLOAD_TOKEN") == f"/product/report/{rid}/upload/UPLOAD_TOKEN"   # a placeholder
    finally:
        root.handlers, root.level = saved[0], saved[1]
        for n, hs in saved[2].items():
            logging.getLogger(n).handlers = hs


def test_an_oversize_packet_is_recorded_and_its_round_can_complete(rig):
    """C10 (R3 #5, repro E): an upload over 2 MiB is still answered 413, and its packet is RECORDED as OUTPUT_TOO_LARGE with no
    body, so round 1 completes and round 2 is minted; a smaller re-upload of that packet would replace it."""
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    packets = [p["packet_id"] for p in out["fetch_plan"]["packets"]]
    last = next(p for p in packets if p.endswith("alibaba") and "c2" in p)
    for p in packets:
        if p != last:
            assert _upload(g, rid, token, p, "page").status_code == 200
    r = _upload(g, rid, token, last, b"x" * (S.MAX_UPLOAD_BYTES + 1))
    assert r.status_code == 413 and r.json()["detail"]["error_code"] == "UPLOAD_TOO_LARGE"
    recorded = r.json()["detail"]["recorded"]
    assert (recorded["status"], recorded["bytes"], recorded["round_complete"], recorded["current_round"]) == ("OUTPUT_TOO_LARGE", 0, True, 2)
    st = _status(g, rid, token=token).json()
    _valid(st, "status_view")
    assert st["round"] == 2 and st["rounds"][0]["complete"] is True and st["uploads"]["by_source"]["alibaba"] == {"OK": 1, "OUTPUT_TOO_LARGE": 1}
    row = g.store.upload_row(rid, last)
    assert row["bytes"] == 0 and row["sha256"] == hashlib.sha256(b"").hexdigest() and row["refused"][0]["code"] == "OUTPUT_TOO_LARGE"


def test_a_failed_save_after_the_render_leaves_the_report_failed_and_compile_retries(rig, monkeypatch):
    """C9 (R3 #3, repro C): a store error after the render used to leave the report `compiling` (409 for good). Now it is `failed`,
    COMPILE_SAVE_FAILED, `next` says compile again, and the next compile goes through."""
    g = rig
    out = _start(g)
    rid = out["report_id"]
    target = g.store if g.backend == "memory" else S
    real, calls = target.save_html, {"n": 0}

    def flaky(conn, report_id, html):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient database error")
        return real(conn, report_id, html)
    monkeypatch.setattr(target, "save_html", flaky)
    r = g.client.post(f"/product/report/{rid}/compile", headers=_h())
    assert r.status_code == 500 and r.json()["detail"]["error_code"] == "COMPILE_SAVE_FAILED"
    st = _status(g, rid).json()
    _valid(st, "status_view")
    assert st["status"] == "failed" and st["compiled"]["error"]["error_code"] == "COMPILE_SAVE_FAILED"
    assert "The last compile failed (COMPILE_SAVE_FAILED)" in st["next"]
    assert g.receipts[-1]["error"] and "COMPILE_SAVE_FAILED" in g.receipts[-1]["error"]
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()["status"] == "compiled"


def test_a_nul_character_never_reaches_a_write(rig, monkeypatch):
    """C9 (R3 #3, repros F and G): U+0000 in a title, a search term, a message or a verdict used to fail the jsonb write (a 500 at
    start; a report stuck `compiling`). It is dropped before every write; on Postgres the writes now succeed."""
    g = rig
    out = _start(g, {"products": [{"title": "pet\u0000feeder", "search_terms": ["pet\u0000 feeder"], "problem": "a\u0000b"}]})
    rid = out["report_id"]
    item = out["candidates"]["items"][0]
    assert (item["title"], item["search_terms"], item["problem"]) == ("petfeeder", ["pet feeder"], "ab")
    r = g.client.post(f"/product/report/{rid}/compile", json={"verdicts": {"c1": "good\u0000margin"}}, headers=_h())
    assert r.status_code == 200 and r.json()["verdicts"] == {"c1": {"by": "agent", "chars": len("goodmargin")}}
    row = g.store.row(rid)
    assert row["verdicts"]["items"] == {"c1": "goodmargin"} and "\u0000" not in json.dumps(row, default=str)
    monkeypatch.setattr(R.DEPS, "resolve_scope", lambda **kw: ["cinema"])
    monkeypatch.setattr(R.DEPS, "product_turn", lambda **kw: _turn(["Smart\u0000 pet feeder"]))
    turned = _start(g, {"message": "pet\u0000 products", "corpus_id": "cinema"})
    st = _status(g, turned["report_id"]).json()
    assert st["request"]["message"] == "pet products" and st["candidates"]["items"][0]["title"] == "Smart pet feeder"
    assert g.receipts[-1]["question"] == "pet products"


def test_an_upload_during_the_render_makes_the_compiled_report_stale(rig, monkeypatch):
    """R3 #4 (repro D): a packet uploaded while the render runs is not in that compile; the compiled report used to say it was
    current (timestamps cut to the second). Staleness now compares the (packet_id, sha256) set the compile read."""
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    packets = [p["packet_id"] for p in out["fetch_plan"]["packets"]]
    for p in packets[:-1]:
        assert _upload(g, rid, token, p, f"page {p}").status_code == 200
    real_render = R.DEPS.render

    def render_while_the_script_uploads(bundle):
        res = {}
        th = threading.Thread(target=lambda: res.setdefault("r", _upload(g, rid, token, packets[-1], "the last page")))
        th.start()
        th.join(20)
        assert res["r"].status_code == 200
        return real_render(bundle)
    monkeypatch.setattr(R.DEPS, "render", render_while_the_script_uploads)
    c = g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()
    assert c["inputs"]["uploads"] == len(packets) - 1
    st = _status(g, rid, token=token).json()
    assert st["uploads"]["total"] == len(packets) and st["compiled"]["stale"] is True
    assert not st["next"].startswith("The report is compiled")
    monkeypatch.setattr(R.DEPS, "render", real_render)
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).json()["inputs"]["uploads"] == len(packets)
    assert _status(g, rid).json()["compiled"]["stale"] is False


def test_degraded_host_data_and_upload_problems_reach_status_and_the_compile_receipt(rig, monkeypatch):
    """C6 (R3 #6): host data stays `done` when collection returns, with `degraded` and its reason codes; a compile receipt's
    meta.degraded holds those reasons and the count of every upload status that is not OK."""
    g = rig
    real_collect = g.fakes.collect

    def collect(candidates, *, principal_id, ship_to="US"):
        data = real_collect(candidates, principal_id=principal_id, ship_to=ship_to)
        data["cj"]["c1"] = {"status": "UNAVAILABLE", "reason_code": "CJ_UNAVAILABLE", "products": []}
        data["cj"]["c2"] = {"status": "NO_MATCH", "reason_code": "CJ_NO_RELEVANT", "products": []}     # an answer, not degraded
        data["ebay"] = {c["candidate_id"]: {"status": "UNAVAILABLE", "reason_code": "FAIR_USE_LIMITED", "listings": []}
                        for c in candidates}
        return data
    monkeypatch.setattr(R.DEPS, "collect", collect)
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    st = _status(g, rid).json()
    _valid(st, "status_view")
    assert st["host"]["status"] == "done" and st["host"]["degraded"] is True
    assert st["host"]["reasons"] == ["CJ_UNAVAILABLE", "FAIR_USE_LIMITED"]
    _upload(g, rid, token, "r1-c1-reddit", "BLOCKED page")
    _upload(g, rid, token, "r1-c1-amazon", b"")
    _upload(g, rid, token, "r1-c1-alibaba", "ok page")
    assert g.client.post(f"/product/report/{rid}/compile", headers=_h()).status_code == 200
    meta = g.receipts[-1]["out"]["meta"]
    assert meta["degraded"] == {"host": ["CJ_UNAVAILABLE", "FAIR_USE_LIMITED"], "uploads": {"BLOCKED": 1, "EMPTY": 1}}
    if g.backend == "postgres":
        stored = next(r for r in g.store.receipts([rid]) if r["meta"]["product_report"]["action"] == "compile")
        assert stored["meta"]["degraded"]["uploads"] == {"BLOCKED": 1, "EMPTY": 1}


# ───────────────────────────────────────────────────────────────── review-fix round 2 (R3 verify: NEW-1 .. NEW-3)
def _packets(out):
    return [p["packet_id"] for p in out["fetch_plan"]["packets"]]


def test_an_empty_reupload_never_replaces_a_good_packet(rig):
    """NEW-1 (repro N1): re-running a round's script re-uploads every packet, and a keyless re-run often hits Exa's or Jina's
    limits. An OK packet is never replaced by a worse one: the answer says the earlier OK upload was kept."""
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    pid = _packets(out)[0]
    good = _upload(g, rid, token, pid, "a good page").json()
    assert good["status"] == "OK" and good["kept_earlier"] is False
    worse = _upload(g, rid, token, pid, "").json()                          # the re-run's read hit Exa's 429: empty
    assert worse["status"] == "EMPTY" and worse["kept_earlier"] is True and worse["replaced"] is False
    assert worse["note"] == "this upload was EMPTY: the earlier OK upload of this packet is kept"
    row = g.store.upload_row(rid, pid)
    assert row["status"] == "OK" and row["parsed"]["records"] == [{"kind": "thread", "title": "a good page",
                                                                    "url": "https://reddit.example/1"}]
    assert row["sha256"] == good["sha256"]
    blocked = _upload(g, rid, token, pid, "BLOCKED page").json()           # a block page: the same rule
    assert blocked["status"] == "BLOCKED" and blocked["kept_earlier"] is True and g.store.upload_row(rid, pid)["status"] == "OK"
    better = _upload(g, rid, token, pid, "a newer good page").json()       # OK replaces OK
    assert better["replaced"] is True and better["kept_earlier"] is False
    assert g.store.upload_row(rid, pid)["parsed"]["records"][0]["title"] == "a newer good page"
    other = _packets(out)[1]                                                # a non-OK packet is replaced by anything
    assert _upload(g, rid, token, other, "").json()["status"] == "EMPTY"
    assert _upload(g, rid, token, other, "BLOCKED page").json()["replaced"] is True
    assert _upload(g, rid, token, other, "now it reads").json()["replaced"] is True
    assert g.store.upload_row(rid, other)["status"] == "OK"


def test_an_oversize_reupload_never_replaces_a_good_packet(rig):
    """NEW-1 (repro N1b): the oversize answer is still 413, but an OK packet stays; the 413 says it was kept."""
    g = rig
    out = _start(g)
    rid, token = out["report_id"], out["upload_token"]
    pid = _packets(out)[0]
    assert _upload(g, rid, token, pid, "a good page").json()["status"] == "OK"
    r = _upload(g, rid, token, pid, b"x" * (S.MAX_UPLOAD_BYTES + 1))
    assert r.status_code == 413 and r.json()["detail"]["recorded"]["kept_earlier"] is True
    row = g.store.upload_row(rid, pid)
    assert row["status"] == "OK" and row["bytes"] == len(b"a good page") and row["parsed"]["records"]


def test_a_required_or_expired_answer_carries_no_script_that_cannot_upload(rig, clock):
    """NEW-2 (repro N2): a `required` answer used to offer a script whose every upload is 403 (the placeholder token). Its plan
    keeps the packets but no script (`script_withheld` says why); so does an expired report's."""
    g = rig
    out = _start(g)
    rid = out["report_id"]
    st = _status(g, rid).json()
    _valid(st, "status_view")
    assert st["upload"]["token"] == "required" and st["fetch_plan"]["script"] is None
    assert st["fetch_plan"]["script_withheld"].startswith("no upload link can be made until ")
    r = _upload(g, rid, "UPLOAD_TOKEN", _packets(out)[0], "page")           # what such a script's uploads would get
    assert r.status_code == 403
    g.store.expire(rid)
    st = _status(g, rid, token=out["upload_token"]).json()
    _valid(st, "status_view")
    assert st["upload"]["token"] == "expired" and st["fetch_plan"]["script"] is None
    assert "expired" in st["fetch_plan"]["script_withheld"]
    with pytest.raises(jsonschema.ValidationError):                         # the schema pins it: a dead script is never shown
        _valid({**st, "fetch_plan": {**st["fetch_plan"], "script": "#!/usr/bin/env bash", "script_sha256": "0" * 64}}, "status_view")


def _gate_collect(monkeypatch, g, who):
    """The host collect of `who` (a principal id, or None for the owner) waits on the returned gate."""
    gate = threading.Event()
    real = g.fakes.collect

    def collect(candidates, *, principal_id, ship_to="US"):
        if principal_id == who:
            assert gate.wait(10)
        return real(candidates, principal_id=principal_id, ship_to=ship_to)
    monkeypatch.setattr(R.DEPS, "collect", collect)
    return gate


def test_the_owner_runs_two_report_jobs_at_once_and_a_friend_one(rig, monkeypatch):
    """NEW-3 / C8: every owner surface (the web app, Hermes, Server A's owner key, Server B) arrives with no principal; the owner
    has 2 job slots, a friend 1. A third owner start while two are gathering data: 429 naming one of them."""
    g = rig
    gate = _gate_collect(monkeypatch, g, None)
    agent = _start(g, wait=False)                                          # e.g. the owner's agent through Server B
    web = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h())          # the owner's web app
    assert web.status_code == 200
    g.created.append(web.json()["report_id"])
    third = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h())
    assert third.status_code == 429 and third.json()["detail"]["report_id"] in (agent["report_id"], web.json()["report_id"])
    assert "2 background slots" in third.json()["detail"]["message"]
    gate.set()
    for rid in (agent["report_id"], web.json()["report_id"]):
        R.wait_for_jobs(rid)
    assert _start(g)["status"] == "collecting"


def test_a_job_slot_frees_itself_after_fifteen_minutes(rig, monkeypatch):
    """NEW-3: a job (or a start's claim) holds its slot at most JOB_SLOT_S — longer than the worst real job — so a stage stuck
    past it never locks its caller out."""
    g = rig
    gate = _gate_collect(monkeypatch, g, "prn_friend_alice")
    stuck = _start(g, principal="prn_friend_alice", wait=False)
    r = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h("prn_friend_alice"))
    assert r.status_code == 429 and r.json()["detail"]["report_id"] == stuck["report_id"]
    for job in R._JOBS.values():                                           # 15 minutes and a second later
        job["started"] -= R.JOB_SLOT_S + 1
    later = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h("prn_friend_alice"))
    assert later.status_code == 200
    g.created.append(later.json()["report_id"])
    gate.set()
    for rid in (stuck["report_id"], later.json()["report_id"]):
        R.wait_for_jobs(rid)


def _lose_host_stage(g, rid):
    """What a restart leaves: the row says the host stage is collecting, no thread runs it."""
    if g.backend == "memory":
        g.store.reports[rid]["host"] = {"status": "collecting"}
    else:
        with g.store.tx() as c:
            c.execute("UPDATE product_reports SET host = '{\"status\": \"collecting\"}'::jsonb WHERE report_id = %s", (rid,))


def test_a_lost_stage_restarts_only_through_a_claim(rig, monkeypatch):
    """NEW-3: `_ensure_jobs` restarts a lost stage only through a claim on the owner's slots — a start in flight (its claim)
    keeps a status poll from running a second job for one friend; a later poll restarts it. And a poll that restarts an old
    report's lost stage for the OWNER leaves the owner's second slot free for the next start."""
    g = rig
    old = _start(g, principal="prn_friend_alice")
    _lose_host_stage(g, old["report_id"])
    claim = R._claim("prn_friend_alice")                                    # a start of this friend is creating its report
    _status(g, old["report_id"], principal="prn_friend_alice")
    assert not R._alive(old["report_id"], "host")                           # refused: one job for a friend; nothing started
    R._release("prn_friend_alice", claim)
    assert _status(g, old["report_id"], principal="prn_friend_alice").json()["host"]["status"] in ("collecting", "done")
    R.wait_for_jobs(old["report_id"])
    assert _status(g, old["report_id"], principal="prn_friend_alice").json()["host"]["status"] == "done"   # the next poll did
    mine = _start(g)
    _lose_host_stage(g, mine["report_id"])
    gate = _gate_collect(monkeypatch, g, None)
    _status(g, mine["report_id"])                                           # the owner's panel polls: the stage restarts
    assert R._alive(mine["report_id"], "host")
    nxt = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h())
    assert nxt.status_code == 200                                           # the owner's second slot
    g.created.append(nxt.json()["report_id"])
    gate.set()
    for rid in (mine["report_id"], nxt.json()["report_id"]):
        R.wait_for_jobs(rid)


def test_a_claim_is_given_back_on_every_path(rig, monkeypatch):
    """C8 (the verify round's probes): a refused start, a failed product turn, a failed host collection and a stage that raises
    past its own handlers all give the slot back."""
    g = rig

    def refuse(**kw):
        raise HTTPException(404, {"error_code": "QUERY_SCOPE_EMPTY", "message": "no library"})
    monkeypatch.setattr(R.DEPS, "resolve_scope", refuse)
    assert g.client.post("/product/report/start", json={"message": "pet products"}, headers=_h("prn_friend_alice")).status_code == 404
    assert not R._CLAIMS
    monkeypatch.setattr(R.DEPS, "resolve_scope", lambda **kw: ["cinema"])

    def turn(**kw):
        raise RuntimeError("model down")
    monkeypatch.setattr(R.DEPS, "product_turn", turn)
    failed = _start(g, {"message": "pet products"}, principal="prn_friend_alice")
    assert _status(g, failed["report_id"], principal="prn_friend_alice").json()["candidates"]["status"] == "failed"

    def collect(candidates, *, principal_id, ship_to="US"):
        raise RuntimeError("CJ down")
    monkeypatch.setattr(R.DEPS, "collect", collect)
    second = _start(g, principal="prn_friend_alice")
    assert _status(g, second["report_id"], principal="prn_friend_alice").json()["host"]["status"] == "failed"
    monkeypatch.setattr(R.DEPS, "collect", g.fakes.collect)
    target = g.store if g.backend == "memory" else S
    real, calls = target.save_host, {"n": 0}

    def flaky(conn, report_id, host):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database gone")
        return real(conn, report_id, host)
    monkeypatch.setattr(target, "save_host", flaky)
    raised = g.client.post("/product/report/start", json={"products": PRODUCTS}, headers=_h("prn_friend_alice")).json()
    g.created.append(raised["report_id"])
    with pytest.raises(RuntimeError):
        R.wait_for_jobs(raised["report_id"])
    assert _start(g, principal="prn_friend_alice")["status"] == "collecting" and not R._CLAIMS


# ───────────────────────────────────────────────────────────────── contract C11 (B3): a compile with nothing uploaded
@pytest.mark.skipif(_recorded_supplier() is None, reason="B1 / B2 / B4a have not landed in this checkout")
def test_a_compile_with_no_uploads_says_needs_a_local_agent_for_reddit_amazon_and_alibaba(rig, monkeypatch):
    """Contract C11 (plan §3.6, users without a terminal): the candidates, the host's CJ / eBay data and the compile run, nothing is
    uploaded. The bundle carries `sources` — per Agent Reach source B1's real plan holds, the packets planned, 0 received, no status —
    and the page (B4a's real render, B3's engine) says 'Needs a local agent' in the Reddit, Amazon and Alibaba sections, with the
    counts near the top, instead of 'No Reddit threads were collected.'"""
    import html

    from polymath_shared.adapter import dossier
    g = rig
    bundles: list[dict] = []
    monkeypatch.delattr(R.DEPS, "build_plan")                                  # B1's real fetch plan (the class's own)
    monkeypatch.setattr(R.DEPS, "render", lambda bundle: bundles.append(copy.deepcopy(bundle)) or dossier.render_decision(bundle))
    out = _start(g)
    rid = out["report_id"]
    planned: dict[str, int] = {}
    for p in out["fetch_plan"]["packets"]:
        planned[p["source"]] = planned.get(p["source"], 0) + 1
    assert set(planned) == {"reddit", "amazon", "alibaba", "ebay"}           # this host has no eBay API: eBay is planned through Agent Reach
    res = g.client.post(f"/product/report/{rid}/compile", json={}, headers=_h())
    assert res.status_code == 200, res.text[:600]
    assert bundles[-1]["sources"] == {s: {"planned": n, "received": 0, "statuses": {}} for s, n in planned.items()}
    page = g.client.get(f"/product/report/{rid}", headers=_h())
    assert page.status_code == 200 and "<script" not in page.text.lower()
    text = html.unescape(re.sub(r"<[^>]+>", "", page.text))
    for label in ("Reddit", "Amazon", "Alibaba"):
        note = (f"{label}. Needs a local agent: nothing from {label} was uploaded for this report. Run the report's fetch script on a "
                "computer with Agent Reach (product_report_status gives it), then compile again.")
        assert text.count(note) == len(PRODUCTS), label                       # once in each product's section
    head = ", ".join(f"{label} 0/{planned[s]}" for s, label in (("reddit", "Reddit"), ("amazon", "Amazon"), ("alibaba", "Alibaba"), ("ebay", "eBay")))
    assert f"Read through your Agent Reach: {head}" in text and text.count("Read through your Agent Reach") == 1
    demand = text[text.index("Demand"): text.index("Supply")]
    assert "No Reddit threads were collected." not in demand


# ───────────────────────────────────────────────────────────────── live-run fix: a product turn with no product idea
def _turn_terms(terms):
    """What the live turn of rpt_30887faa… returned: verdict thin, the model's block unreadable, 0 hypotheses, the request's own
    search words as term finds."""
    return {"verdict": "product_hypotheses_thin", "model": "deepseek-v4-flash", "product_research": {
        "corpus_ids": ["commerce-v1"], "hypotheses": [],
        "term_finds": [{"search_term": t, "cj": {"status": "OK", "items": []}} for t in terms]}}


def _turn_rig(monkeypatch, answers):
    """The product turn answering `answers` in order; every call recorded with the receipt id it writes."""
    calls = []

    def turn(**kw):
        calls.append(kw["message"])
        kw["receipt_ids"].append(f"q_turn_{len(calls)}")
        return answers[len(calls) - 1]
    monkeypatch.setattr(R.DEPS, "product_turn", turn)
    monkeypatch.setattr(R.DEPS, "resolve_scope", lambda **kw: ["commerce-v1"])
    return calls


ASK = "Find me products I could dropship to pet owners in the US"


def test_a_turn_with_no_product_idea_is_run_once_more_then_the_request_words_are_labelled(rig, monkeypatch):
    """0 hypotheses, then 0 again: two turns (both receipts kept), and the request's own search words become the candidates —
    `source` request_terms, a plain `note`, and `next` tells the agent to start over with its own `products` when they are
    categories rather than products."""
    g = rig
    calls = _turn_rig(monkeypatch, [_turn_terms(["pet products", "pet accessories"]), _turn_terms(["pet products", "pet accessories"])])
    out = _start(g, {"message": ASK, "corpus_id": "commerce-v1"})
    assert calls == [ASK, ASK]                                                # the same request, twice
    st = _status(g, out["report_id"], token=out["upload_token"]).json()
    _valid(st, "status_view")
    cand = st["candidates"]
    assert (cand["status"], cand["source"]) == ("ready", "request_terms")
    assert cand["note"] == "the library gave no product ideas; these are the request's own search words"
    assert [c["title"] for c in cand["items"]] == ["pet products", "pet accessories"]
    assert {c["source"] for c in cand["items"]} == {"request_terms"}
    assert cand["product_turn_receipt_ids"] == ["q_turn_1", "q_turn_2"] and cand["product_turn_receipt_id"] == "q_turn_2"
    assert st["next"].startswith("The candidates are the request's own search words, not product ideas from the library")
    assert "start a new report with products: [{title, search_terms}]" in st["next"] and "(2-4 word catalogue terms each)" in st["next"]
    assert "if they already name products, carry on: run round 1's fetch script" in st["next"]
    turn = g.store.row(out["report_id"])["candidates"]["product_turn"]
    assert (turn["tries"], turn["hypotheses"], turn["receipt_ids"]) == (2, 0, ["q_turn_1", "q_turn_2"])
    _upload(g, out["report_id"], out["upload_token"], st["fetch_plan"]["packets"][0]["packet_id"], "a page")
    later = _status(g, out["report_id"], token=out["upload_token"]).json()      # the agent went on: no more of the warning
    assert later["candidates"]["source"] == "request_terms" and later["next"].startswith("Run round 1's fetch script")


def test_a_turn_with_no_product_idea_then_three_uses_the_retry(rig, monkeypatch):
    """0 hypotheses, then 3: two turns, and the second turn's hypotheses are the candidates (source product_route, no note)."""
    g = rig
    calls = _turn_rig(monkeypatch, [_turn_terms(["pet products"]), _turn(["Smart pet feeder", "Calming dog bed", "Cat water fountain"])])
    out = _start(g, {"message": ASK})
    assert len(calls) == 2
    st = _status(g, out["report_id"], token=out["upload_token"]).json()
    _valid(st, "status_view")
    cand = st["candidates"]
    assert (cand["source"], cand["note"]) == ("product_route", None)
    assert [c["title"] for c in cand["items"]] == ["Smart pet feeder", "Calming dog bed", "Cat water fountain"]
    assert cand["product_turn_receipt_ids"] == ["q_turn_1", "q_turn_2"] and st["next"].startswith("Run round 1's fetch script")
    assert g.store.row(out["report_id"])["candidates"]["product_turn"]["tries"] == 2


def test_a_turn_with_product_ideas_runs_once(rig, monkeypatch):
    """3 hypotheses at once: one turn; and a report started with `products` never runs one (its source stays caller)."""
    g = rig
    calls = _turn_rig(monkeypatch, [_turn(["Smart pet feeder", "Calming dog bed", "Cat water fountain"])])
    out = _start(g, {"message": ASK})
    st = _status(g, out["report_id"], token=out["upload_token"]).json()
    assert len(calls) == 1 and st["candidates"]["source"] == "product_route" and st["candidates"]["product_turn_receipt_ids"] == ["q_turn_1"]
    assert len(st["candidates"]["items"]) == 3 and st["candidates"]["note"] is None
    mine = _start(g, {"products": PRODUCTS})
    assert len(calls) == 1 and mine["candidates"]["source"] == "caller" and mine["candidates"]["note"] is None
    assert not mine["next"].startswith("The candidates are the request's own search words")
