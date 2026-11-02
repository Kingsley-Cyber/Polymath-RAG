"""PRODUCT-DECISION-REPORT-V1 (B4b, plan §3 and §4.6): one HTML decision report per product search, compiled by Polymath for any
agent, stored privately per user. This module is the service that ties the other slices together; it calls them by their plan
names (`DEPS`): B1 `agent_reach.parse_report_source` and `fetch_plan.build`, B2 `host_data.collect`, B4a
`dossier.render_decision`, and — for a start without products — the product route's own machinery
(`orchestrator.api.product._forced_turn`, PRODUCT-SEARCH-E2E).

  POST /product/report/start               products from the body, or (none sent) the product route's hypotheses, formed by ONE
                                            product turn in a background thread. Returns at once (`status: collecting`): the
                                            report id, the candidates when known, the host-data status, the round-1 fetch plan
                                            and the report's first upload token (`upload_token`, shown once). Host data (CJ + eBay,
                                            B2) is collected in a background thread as the caller's principal. C8: 429
                                            REPORT_JOB_RUNNING while the caller's background-job slots are full (the owner 2,
                                            a friend 1; a slot is free again after 15 minutes whatever its job does).
  GET  /product/report/{id}/status          candidates, host status (with `degraded` and its `reasons`, C6), the current round and
                                            its fetch plan (B1) with `upload = {url, expires_at, token, ...}`, per-source upload
                                            counts and `next` (what the agent does now, one sentence). Upload tokens (contract C1):
                                            a caller that sends a token the report holds (`X-Upload-Token`) gets it reused; one
                                            without a token gets a fresh one minted into the plan's URLs, at most once per report
                                            per minute (else `required`, with `upload.mint_after`, and no script: a script that
                                            cannot upload is withheld, `fetch_plan.script_withheld` says why).
  POST /product/report/{id}/upload/{token}?packet=<packet_id>
                                            CAPABILITY: no session. The upload token (any token the report holds — not one-time:
                                            it uploads until the report's 6 h expiry) and the packet (this report, the current
                                            round) are checked BEFORE the body is read; then the size (2 MiB; 300 packets a report:
                                            an oversize upload is recorded as OUTPUT_TOO_LARGE and answered 413, C10). The text is
                                            parsed by B1's `parse_report_source` and stored (a re-upload replaces, but an OK packet
                                            is never replaced by a worse one: `kept_earlier`); when round 1 is complete, round 2
                                            is minted from the parsed `next_targets`.
  POST /product/report/{id}/compile        the decision bundle (plan §4.4: candidates, host, parsed per candidate, settings) ->
                                            B4a's `render_decision` -> the model and the HTML stored; the agent's verdicts
                                            (<= 1200 characters per candidate) are stored as the agent's (C9: a lost compile may
                                            run again after 300 s; a failed save is `failed` COMPILE_SAVE_FAILED).
  GET  /product/report/{id}                the stored HTML under a CSP that allows no script (the dossier's headers).
  GET  /product/reports                    the caller's reports, newest first.

Who may call (R1 #1, the supplier routes' B-28 rule): every route but the upload answers only the MCP servers on this host
(called directly at a loopback Host) and the signed-in web app (relayed by the proxy past the web boundary); the upload answers
a script through the proxy, or a direct caller at a loopback Host. A page that re-bound its own name to this machine is refused.
Privacy (the adapter runs' rule, migration 0066): no principal = the owner / a trusted-local caller, who reaches every report; a
principal (a friend, forwarded by Server A or the web boundary) reaches only its own; "not yours" and "no such report" are one
404. Upload URLs: `http://127.0.0.1:7200/...` for a local caller, `{public base}/...` for a remote one (`upload_base`). One query
receipt of kind `product_report` per start and per compile (counts and statuses only; a compile's `meta.degraded` names what was
degraded, C6). Background jobs run on daemon threads (a restart never waits for them; `_ensure_jobs` restarts a lost stage).
Nothing here calls a web service itself: CJ and eBay are B2's, every web page is read by the user's own Agent Reach through the
fetch script. C1–C10 in this module are the review-fix contracts recorded in docs/wiki/work-log/2026-11-02-product-decision-report.md;
the upload capability itself is ADR-0023 (docs/wiki/decisions/0023-report-upload-capability.md)."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from orchestrator.api.adapter import (
    REPORT_HEADERS,  # the dossier's page headers: a CSP that allows no script, nosniff
)
from orchestrator.api.product import refuse_rebinding
from polymath_shared import principal_context
from polymath_shared.db import tx
from polymath_shared.product_search import report_store as store
from polymath_shared.query_receipts import record_query_receipt
from pydantic import BaseModel, Field

router = APIRouter()
log = logging.getLogger("orchestrator.product_report")

CONTRACT = store.CONTRACT
KIND = "product_report"
#: plan §2 channel ids
CHANNELS = ("tiktok_us", "tiktok_cross_border", "shopify", "ebay", "amazon_fbm")
DEFAULT_MAX_PRODUCTS, MAX_PRODUCTS = 5, 8
#: the markets the channel rules describe (plan §2; unit_economics refuses any other settings.ship_to)
SHIP_TO = ("US",)
VERDICT_MAX = 1200
#: plan §4.6 / the owner's decisions of 2026-11-02: 19.3 % returns (NRF 2025-10-15), Shopify plan cost spread over 100 orders
RETURNS_RATE, SHOPIFY_MONTHLY_ORDERS = 0.193, 100
LOCAL_BASE = "http://127.0.0.1:7200"
#: the PUBLIC WEB DOOR (rag.kingsleylab.xyz -> Caddy -> this listener). The MCP door web_settings.mcp_url() names
#: (POLYMATH_PUBLIC_MCP_URL, mcp.kingsleylab.xyz) is Server A on :8930 and serves no orchestrator route, so an upload cannot go
#: there. Same mechanism as web_settings (an env value with this deployment's default); set it EMPTY on a server without a public
#: web door: every caller then gets the local URL.
PUBLIC_URL_ENV = "POLYMATH_PUBLIC_URL"
DEFAULT_PUBLIC_URL = "https://rag.kingsleylab.xyz"
TOKEN_HEADER = "x-upload-token"
TOKEN_PLACEHOLDER = "UPLOAD_TOKEN"
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded")
#: C9: a compile whose `compile_started_at` is this old without finishing was lost (a restart): it may be started again
COMPILE_STALE_S = 300
#: C8: what a start refused because the caller's job slots are full suggests waiting
JOB_RETRY_AFTER_S = 30
#: C8: background jobs one caller may run at once. The owner (no principal: the web app, Hermes, Server A's owner key and Server B
#: all arrive so) 2, a friend 1. A job, or a start's claim, holds its slot at most JOB_SLOT_S — longer than the worst real job (8
#: candidates x 4 CJ calls x 20 s plus fair-use waits) — so a stage stuck past it never locks its caller out.
OWNER_JOB_SLOTS, PRINCIPAL_JOB_SLOTS = 2, 1
JOB_SLOT_S = 15 * 60
#: LIVE-RUN FIX (rpt_30887faa…, 2026-11-02): a product turn whose model block cannot be read gives 0 hypotheses on some runs and 5
#: on the next; such a turn is run once more before the request's own search words become the candidates, and then they are
#: labelled for what they are (`candidates.source` request_terms, `candidates.note`).
PRODUCT_TURN_TRIES = 2
REQUEST_TERMS_NOTE = "the library gave no product ideas; these are the request's own search words"
#: C6: the host-data statuses that mean a source could not be read in full (NO_MATCH / EMPTY / NOT_SEARCHED are answers)
DEGRADED_HOST_STATUSES = frozenset({"PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED", "NOT_FETCHED"})


# ─────────────────────────────────────────────────────────── the other slices, by their plan names
class _Deps:
    """The functions this service calls (plan §4.1–4.5), resolved at call time from the real modules; tests replace them."""

    def build_plan(self, report_id: str, candidates: list[dict], *, round: int, upload: dict, targets: list[dict] | None = None,
                   ebay_api: bool = False) -> dict:
        from polymath_shared.product_search import fetch_plan  # B1
        return fetch_plan.build(report_id, candidates, round=round, upload=upload, targets=targets, ebay_api=ebay_api)

    def ebay_configured(self) -> bool:
        """Does this host read eBay through the Browse API (B2: EBAY_CLIENT_ID and EBAY_CLIENT_SECRET set)? Then the fetch plan
        holds no eBay Exa search (plan §4.2). Names only: no value is read into the report, no call is made."""
        from polymath_shared.acquisition import ebay_api  # B2
        return ebay_api.configured(os.environ)

    def parse(self, source: str, raw_text: str, *, kind: str, candidate_terms: list[str] | None = None) -> dict:
        from polymath_shared.acquisition import agent_reach  # B1
        return agent_reach.parse_report_source(source, raw_text, kind=kind, candidate_terms=candidate_terms)

    def collect(self, candidates: list[dict], *, principal_id: str | None, ship_to: str = "US") -> dict:
        from polymath_shared.product_search import host_data  # B2
        return host_data.collect(candidates, principal_id=principal_id, ship_to=ship_to)

    def render(self, bundle: dict) -> dict:
        from polymath_shared.adapter import dossier  # B4a
        return dossier.render_decision(bundle)

    def product_turn(self, *, message: str, corpus_id: str | None, corpus_ids: list[str] | None, geography: str | None,
                     model: str | None, client: str, receipt_ids: list[str] | None = None) -> dict:
        """ONE product turn through the product route's own machinery (PRODUCT-SEARCH-E2E): forced product mode, the app's default
        model unless `model`, the caller's scope; its own query receipt (kind `product`, route `product/report/start`), whose id
        is appended to `receipt_ids` (C6: the report keeps it)."""
        from orchestrator.api import product
        preq = product.ProductSearchRequest(message=message, corpus_id=corpus_id, corpus_ids=corpus_ids, geography=geography,
                                            model=model)

        def sink(payload: dict) -> None:
            qid = record_query_receipt(tx, kind=product.KIND, client=client, **payload)
            if receipt_ids is not None and qid:
                receipt_ids.append(qid)
        return product._forced_turn(preq, message, sink, route="product/report/start")

    def resolve_scope(self, *, message: str, corpus_id: str | None, corpus_ids: list[str] | None) -> list[str]:
        """The libraries a product turn would search for this caller — the product route's resolver (typed refusals)."""
        from orchestrator.api import product
        return product._resolve_corpora(product.ProductSearchRequest(message=message, corpus_id=corpus_id, corpus_ids=corpus_ids))


DEPS = _Deps()

# ─────────────────────────────────────────────────────────── background work (one process: the launchd plist runs one uvicorn)
#: R3 #1 / R1 #2: every background stage runs on its own DAEMON thread (a SIGTERM never waits for a product turn or a host
#: collection; `_ensure_jobs` restarts a stage a restart lost). No shared pool: C8 lets each principal run one job at a time.
_JOBS: dict[str, dict[str, Any]] = {}          # f"{report_id}:{stage}" -> {thread, owner, report_id, stage, started}
_CLAIMS: dict[str, dict[str, tuple[str | None, float]]] = {}   # owner key -> {claim id: (report_id or None, when)}
_JOB_ERRORS: dict[str, BaseException] = {}     # report_id -> the exception a stage raised (tests' `wait_for_jobs` raises it)
_JOBS_LOCK = threading.Lock()


class JobRunning(Exception):
    """C8: this caller's job slots are full (`report_id` is one of the reports holding them, when known)."""

    def __init__(self, report_id: str | None) -> None:
        super().__init__(report_id or "")
        self.report_id = report_id


def _who(principal: str | None) -> str:
    return principal or ""                       # "" = the owner / a trusted-local caller


def _prune() -> None:
    for key in [k for k, e in _JOBS.items() if not e["thread"].is_alive()]:
        _JOBS.pop(key, None)


def _slots(principal: str | None) -> int:
    return OWNER_JOB_SLOTS if principal is None else PRINCIPAL_JOB_SLOTS


def _holding(principal: str | None) -> list[str | None]:
    """The reports holding this caller's slots: its live jobs and its starts' claims younger than JOB_SLOT_S (lock held)."""
    _prune()
    owner, now = _who(principal), time.monotonic()
    jobs = [e["report_id"] for e in _JOBS.values() if e["owner"] == owner and now - e["started"] < JOB_SLOT_S]
    claims = [rid for rid, t in (_CLAIMS.get(owner) or {}).values() if now - t < JOB_SLOT_S]
    return [*jobs, *claims]


def _alive(report_id: str, stage: str) -> bool:
    with _JOBS_LOCK:
        e = _JOBS.get(f"{report_id}:{stage}")
        return e is not None and e["thread"].is_alive()


def _claim(principal: str | None, report_id: str | None = None) -> str:
    """C8: reserve one of this caller's job slots (a start creating its report, or a status call restarting a lost stage).
    Returns the claim's id; JobRunning when every slot is held."""
    with _JOBS_LOCK:
        holding = _holding(principal)
        if len(holding) >= _slots(principal):
            raise JobRunning(next((r for r in holding if r), None))
        cid = os.urandom(8).hex()
        _CLAIMS.setdefault(_who(principal), {})[cid] = (report_id, time.monotonic())
        return cid


def _release(principal: str | None, claim: str | None) -> None:
    """Give a claim back (a no-op once `_launch` has turned it into the job it reserved)."""
    with _JOBS_LOCK:
        claims = _CLAIMS.get(_who(principal)) or {}
        claims.pop(claim or "", None)
        if not claims:
            _CLAIMS.pop(_who(principal), None)


def _launch(report_id: str, stage: str, owner: str | None, fn: Callable[[], None], *, claim: str | None = None) -> bool:
    """Run `fn` on a daemon thread unless the same stage of the same report is already running (False when it was). `claim`:
    the slot reserved for it, handed over to the job in the same step (never counted twice)."""
    key = f"{report_id}:{stage}"

    def run() -> None:
        try:
            fn()
        except BaseException as exc:  # a stage records its own failures; anything else is logged and kept
            log.exception("product report %s %s stage failed", report_id, stage)
            with _JOBS_LOCK:
                _JOB_ERRORS[report_id] = exc
                while len(_JOB_ERRORS) > 100:
                    _JOB_ERRORS.pop(next(iter(_JOB_ERRORS)))
    with _JOBS_LOCK:
        _prune()
        if key in _JOBS:
            return False
        (_CLAIMS.get(_who(owner)) or {}).pop(claim or "", None)
        thread = threading.Thread(target=run, name=f"product-report-{stage}-{report_id}", daemon=True)
        _JOBS[key] = {"thread": thread, "owner": _who(owner), "report_id": report_id, "stage": stage, "started": time.monotonic()}
        thread.start()
        return True


def wait_for_jobs(report_id: str, timeout: float = 30.0) -> None:
    """Block until this report's background stages are done (tests and scripts); re-raise what a stage raised."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with _JOBS_LOCK:
            live = [e["thread"] for e in _JOBS.values() if e["report_id"] == report_id and e["thread"].is_alive()]
        if not live:
            break
        live[0].join(max(0.01, deadline - time.monotonic()))
    with _JOBS_LOCK:
        failed = _JOB_ERRORS.pop(report_id, None)
    if failed is not None:
        raise failed


def _now() -> _dt.datetime:
    return store.now()


def _err(code: str, message: str) -> dict[str, str]:
    return {"error_code": code, "message": message}


def _refuse(status_code: int, error_code: str, text: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status_code, detail={**_err(error_code, text), **extra})


def _not_found() -> HTTPException:
    return _refuse(404, "REPORT_NOT_FOUND", "no such product report for this caller")


def _clean(value: Any) -> Any:
    """C9: U+0000 out of what a caller sends (jsonb and text refuse it; the store strips it again before every write)."""
    return store.strip_nul(value)


def _save(report_id: str, fn: Callable[[Any], None]) -> None:
    with tx() as conn:
        fn(conn)


def _collect_host(report_id: str, principal: str | None, items: list[dict], ship_to: str) -> None:
    """B2 host data as the report owner's principal; a failure is recorded on the report, never raised (the report compiles
    without host data: every number it needed is then UNKNOWN)."""
    with principal_context.acting_as(principal):
        started = store.iso(_now())
        _save(report_id, lambda c: store.save_host(c, report_id, {"status": "collecting", "started_at": started, "finished_at": None,
                                                                   "error": None, "data": None}))
        try:
            data = DEPS.collect(items, principal_id=principal, ship_to=ship_to)
            host = {"status": "done", "started_at": started, "finished_at": store.iso(_now()), "error": None,
                    "data": data if isinstance(data, dict) else {}}
        except Exception as exc:  # noqa: BLE001 — recorded, typed; the report goes on
            log.warning("product report %s host data failed: %s", report_id, f"{type(exc).__name__}: {exc}"[:300])
            code = str(getattr(exc, "code", "") or "")          # a supplier refusal keeps its own code (a fair-use limit, ...)
            host = {"status": "failed", "started_at": started, "finished_at": store.iso(_now()),
                    "error": _err(code if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,80}", code) else "HOST_DATA_FAILED",
                                  f"the CJ / eBay host data could not be collected ({type(exc).__name__})"),
                    "data": None}
        _save(report_id, lambda c: store.save_host(c, report_id, host))


def candidates_from_block(block: Mapping[str, Any] | None, max_products: int) -> list[dict[str, Any]]:
    """The report's candidates from a product turn's `product_research` block: its hypotheses (title, search terms, problem,
    audience, the passages it rests on), else its search-term finds; at most `max_products`."""
    from polymath_shared.product_search import hypotheses as H
    block = _clean(dict(block or {}))
    out: list[dict[str, Any]] = []
    for h in block.get("hypotheses") or []:
        title = H._text(h.get("title"), H.TITLE_MAX) if isinstance(h, Mapping) else None
        if title:
            out.append({"candidate_id": f"c{len(out) + 1}", "title": title, "search_terms": H._terms(h.get("search_terms"), title),
                        "problem": H._text(h.get("problem"), H.PROBLEM_MAX), "audience": H._text(h.get("audience"), H.AUDIENCE_MAX),
                        "source": "product_route", "hypothesis_id": h.get("id"),
                        "evidence_tags": [str(t) for t in h.get("evidence_tags") or []], "confidence": h.get("confidence")})
    if not out:
        for t in block.get("term_finds") or []:
            term = H._text((t or {}).get("search_term"), H.TERM_MAX) if isinstance(t, Mapping) else None
            if term:
                out.append({"candidate_id": f"c{len(out) + 1}", "title": term, "search_terms": H._terms([term], term),
                            "problem": None, "audience": None, "source": "request_terms"})
    return out[:max_products]


def _hypotheses(out: Any, key: str = "hypotheses") -> int:
    """How many hypotheses (or, with key="term_finds", search-word finds) a product turn's block holds."""
    block = (out or {}).get("product_research") if isinstance(out, Mapping) else None
    return len((block or {}).get(key) or []) if isinstance(block, Mapping) else 0


def _form_candidates(report_id: str, principal: str | None, request: dict[str, Any], client: str) -> None:
    """The start without products: the product turn (the product route's machinery) as the caller's principal; its hypotheses
    become the candidates, then the host data. A turn with NO hypothesis (its model block could not be read: it varies run to run)
    is run ONCE more with the same request; still none, and the request's own search words (the turn's term finds) become the
    candidates, labelled `request_terms` with a plain note. Every failure is typed on the report (status `failed`); every turn's
    receipt id is kept on the report (C6)."""
    with principal_context.acting_as(principal):
        receipt_ids: list[str] = []

        def record(out: Any, tries: int) -> dict[str, Any]:
            block = (out or {}).get("product_research") if isinstance(out, Mapping) else None
            return {"verdict": (out or {}).get("verdict") if isinstance(out, Mapping) else None,
                    "model": (out or {}).get("model") if isinstance(out, Mapping) else None,
                    "corpus_ids": list((block or {}).get("corpus_ids") or []), "hypotheses": _hypotheses(out), "tries": tries,
                    "receipt_id": receipt_ids[-1] if receipt_ids else None, "receipt_ids": list(receipt_ids)}

        def fail(code: str, message: str, turn: dict | None = None) -> None:
            def write(conn) -> None:
                store.save_candidates(conn, report_id, {"status": "failed", "source": "product_route", "items": [],
                                                        "error": _err(code, message), "note": None,
                                                        "product_turn": turn or record(None, 0)})
                row = store.get(conn, report_id, principal_id=None, for_update=True)
                if row["status"] == "collecting":
                    store.transition(conn, report_id, "failed", current="collecting")
            _save(report_id, write)

        def turn_once() -> Any:
            return DEPS.product_turn(message=request["message"], corpus_id=request.get("corpus_id"),
                                     corpus_ids=request.get("corpus_ids"), geography=request.get("ship_to"),
                                     model=request.get("model"), client=client, receipt_ids=receipt_ids)
        try:
            out = turn_once()
        except HTTPException as exc:
            d = exc.detail if isinstance(exc.detail, dict) else {}
            fail(str(d.get("error_code") or d.get("code") or f"HTTP_{exc.status_code}"),
                 str(d.get("message") or d.get("next_step") or exc.detail)[:500])
            return
        except Exception as exc:  # noqa: BLE001 — typed on the report
            log.warning("product report %s product turn failed: %s", report_id, f"{type(exc).__name__}: {exc}"[:300])
            fail("PRODUCT_TURN_FAILED", f"the product turn failed on this server ({type(exc).__name__})")
            return
        tries = 1
        while _hypotheses(out) == 0 and tries < PRODUCT_TURN_TRIES:   # no product idea read from the model: once more
            tries += 1
            try:
                again = turn_once()
            except Exception as exc:  # noqa: BLE001 — the first turn's answer stands
                log.warning("product report %s product turn retry failed: %s", report_id, f"{type(exc).__name__}: {exc}"[:300])
                break
            if _hypotheses(again) or _hypotheses(again, "term_finds") or not _hypotheses(out, "term_finds"):
                out = again                                       # the retry's ideas; else its own search words, else the first's
        block = (out or {}).get("product_research") if isinstance(out, Mapping) else None
        items = candidates_from_block(block, int(request.get("max_products") or DEFAULT_MAX_PRODUCTS))
        turn = record(out, tries)
        if not items:
            fail("NO_CANDIDATES", "the product turn formed no product hypothesis and no search term from the library", turn)
            return
        from_terms = _hypotheses(out) == 0
        _save(report_id, lambda c: store.save_candidates(c, report_id, {
            "status": "ready", "source": "request_terms" if from_terms else "product_route", "items": items, "error": None,
            "note": REQUEST_TERMS_NOTE if from_terms else None, "product_turn": turn}))
        _collect_host(report_id, principal, items, request.get("ship_to") or "US")


def _ensure_jobs(row: Mapping[str, Any], principal: str | None) -> None:
    """A stage the row says is still running but this process does not run (a restart lost it) is started again, as the report's
    owner, and only through a claim on that owner's job slots (C8): when they are full nothing starts now and a later status call
    tries again. Idempotent."""
    rid, cand, host = row["report_id"], row.get("candidates") or {}, row.get("host") or {}
    request = row.get("request") or {}
    owner = row.get("owner_principal_id")
    if _alive(rid, "candidates") or _alive(rid, "host"):
        return
    if cand.get("status") == "collecting":
        stage, fn = "candidates", (lambda: _form_candidates(rid, owner, dict(request), str(request.get("client") or "")))
    elif cand.get("status") == "ready" and host.get("status") in (None, "pending", "collecting"):
        items = list(cand.get("items") or [])
        stage, fn = "host", (lambda: _collect_host(rid, owner, items, request.get("ship_to") or "US"))
    else:
        return
    try:
        claim = _claim(owner, rid)
    except JobRunning:
        return
    try:
        _launch(rid, stage, owner, fn, claim=claim)
    finally:
        _release(owner, claim)


# ─────────────────────────────────────────────────────────── who may call, upload URLs
def _proxied(request: Request) -> bool:
    return any(request.headers.get(h) for h in PROXY_HEADERS)


def _refuse_rebound_upload(request: Request) -> None:
    """R1 #1 for the upload (a CAPABILITY route: no session, so the web sign-in rule cannot apply): a relayed request is the
    public door's (the proxy forwarded it); a direct one must name this machine's loopback, never a re-bound page's own name."""
    from orchestrator.api.acquisition import loopback_host
    if not _proxied(request) and not loopback_host(request.headers.get("host")):
        raise _refuse(403, "NON_LOOPBACK_HOST", "the upload answers the public web door or a caller on this host at 127.0.0.1 / "
                                                "localhost; a request naming another host is refused", code="NON_LOOPBACK_HOST")


def local_base() -> str:
    return (os.environ.get("POLYMATH_ORCH_URL") or LOCAL_BASE).rstrip("/")


def public_base() -> str | None:
    """The public web door's origin, or None when this server has none (POLYMATH_PUBLIC_URL set empty or malformed)."""
    raw = os.environ.get(PUBLIC_URL_ENV, DEFAULT_PUBLIC_URL).strip().rstrip("/")
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.query or parts.fragment:
        return None
    return raw


def upload_target(request: Request, choice: str | None) -> tuple[str, str, str | None]:
    """(via, base, note). `choice` (local | public) wins; else a caller that came through the web door or acts for a principal
    (a friend: never on this host) is remote, everyone else (the owner's agent on this Mac, Hermes) local. No public door known =
    the local URL, said in `note`."""
    remote = (choice == "public") if choice in ("local", "public") else (_proxied(request) or principal_context.current() is not None)
    if not remote:
        return "local", local_base(), None
    base = public_base()
    if base is None:
        return "local", local_base(), ("PUBLIC_URL_UNKNOWN: this server has no public web address (POLYMATH_PUBLIC_URL), so the "
                                       "upload link is the local one and works only on the Polymath host")
    return "public", base, None


def _upload_url(base: str, report_id: str, token: str) -> str:
    return f"{base}/product/report/{report_id}/upload/{token}"


# ─────────────────────────────────────────────────────────── plans, rounds, the status view
def _items(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    cand = row.get("candidates") or {}
    return [dict(c) for c in cand.get("items") or [] if isinstance(c, Mapping)] if cand.get("status") == "ready" else []


def _plans(row: Mapping[str, Any], ups: list[dict], upload: dict) -> dict[int, dict]:
    """Every round's fetch plan up to the current one (B1 `build`; round 2's targets are round 1's parsed `next_targets`)."""
    items, rid = _items(row), row["report_id"]
    ebay = bool((row.get("request") or {}).get("ebay_api"))     # fixed at start: the round-1 packets never change under a report
    plans = {1: DEPS.build_plan(rid, items, round=1, upload=upload, ebay_api=ebay)}
    if int(row.get("round") or 1) >= 2:
        plans[2] = DEPS.build_plan(rid, items, round=2, upload=upload, targets=store.round_targets(ups, 1), ebay_api=ebay)
    return plans


def _packet_ids(plan: Mapping[str, Any] | None) -> list[str]:
    return [str(p.get("packet_id")) for p in (plan or {}).get("packets") or [] if isinstance(p, Mapping) and p.get("packet_id")]


def _rounds(plans: Mapping[int, dict], ups: list[dict]) -> list[dict[str, Any]]:
    out = []
    for r in sorted(plans):
        expected = set(_packet_ids(plans[r]))
        got = {str(u["packet_id"]) for u in ups if int(u.get("round") or 0) == r} & expected
        out.append({"round": r, "packets": len(expected), "received": len(got), "complete": expected <= got})
    return out


def host_reasons(host: Mapping[str, Any] | None) -> list[str]:
    """C6: why the host data is degraded — the reason code of every CJ / eBay entry B2 could not read in full (a status in
    DEGRADED_HOST_STATUSES: CJ_UNAVAILABLE, EBAY_NOT_CONFIGURED, EBAY_RATE_LIMITED, FAIR_USE_LIMITED, ...), and a failed
    collection's own code. Sorted, each once; [] = not degraded."""
    host = host or {}
    data = host.get("data") if isinstance(host.get("data"), Mapping) else {}
    reasons: set[str] = set()
    for section in ("cj", "ebay"):
        for entry in (data.get(section) or {}).values():
            entry = entry if isinstance(entry, Mapping) else {}
            status = str(entry.get("status") or "").upper()
            if status in DEGRADED_HOST_STATUSES:
                reasons.add(str(entry.get("reason_code") or f"{section.upper()}_{status}"))
    if host.get("status") == "failed":
        reasons.add(str((host.get("error") or {}).get("error_code") or "HOST_DATA_FAILED"))
    return sorted(reasons)


def _host_view(host: Mapping[str, Any] | None) -> dict[str, Any]:
    host = host or {}
    data = host.get("data") if isinstance(host.get("data"), Mapping) else {}

    def per(section: str, items_key: str) -> dict[str, Any]:
        out = {}
        for cid, v in (data.get(section) or {}).items():
            v = v if isinstance(v, Mapping) else {}
            out[str(cid)] = {"status": v.get("status"), "reason_code": v.get("reason_code"), items_key: len(v.get(items_key) or [])}
        return out
    reasons = host_reasons(host)
    return {"status": host.get("status") or "pending", "started_at": host.get("started_at"), "finished_at": host.get("finished_at"),
            "error": host.get("error"), "degraded": bool(reasons), "reasons": reasons, "cj": per("cj", "products"),
            "ebay": per("ebay", "listings")}


def degraded_meta(host: Mapping[str, Any] | None, ups: list[dict]) -> dict[str, Any]:
    """C6: a compile receipt's `meta.degraded` — the host's reasons and the count of every upload status that is not OK
    (BLOCKED, HUMAN_CHECK, EMPTY, OUTPUT_TOO_LARGE, UNRECOGNISED)."""
    counts: dict[str, int] = {}
    for u in ups:
        st = str(u.get("status") or "NONE")
        if st != "OK":
            counts[st] = counts.get(st, 0) + 1
    return {"host": host_reasons(host), "uploads": dict(sorted(counts.items()))}


def _compile_age(row: Mapping[str, Any]) -> float | None:
    started = row.get("compile_started_at")
    if isinstance(started, str):
        started = _dt.datetime.fromisoformat(started)
    return (_now() - started).total_seconds() if isinstance(started, _dt.datetime) else None


def _compile_stale(row: Mapping[str, Any]) -> bool:
    """C9: a `compiling` report whose compile started more than COMPILE_STALE_S ago (or never said when) was lost."""
    age = _compile_age(row)
    return row.get("status") == "compiling" and (age is None or age >= COMPILE_STALE_S)


def _compiled_view(row: Mapping[str, Any], ups: list[dict], base: str) -> dict[str, Any] | None:
    """R3 #4: stale = the stored uploads are no longer the set the compile read ((packet_id, sha256) pairs, not timestamps)."""
    model = row.get("model") if isinstance(row.get("model"), Mapping) else None
    if not model:
        return None
    at = model.get("compiled_at")
    read = model.get("uploads_sha256")
    return {"at": at, "report_url": f"{base}/product/report/{row['report_id']}" if at else None,
            "stale": bool(at and read is not None and read != store.uploads_digest(ups)), "error": model.get("error")}


REQUEST_TERMS_NEXT = ("The candidates are the request's own search words, not product ideas from the library: if they are "
                      "categories rather than products, start a new report with products: [{title, search_terms}] that you choose "
                      "(2-4 word catalogue terms each); if they already name products, carry on: ")


def next_step(*, status: str, cand: Mapping[str, Any], host: Mapping[str, Any], rounds: list[dict], current: int,
              upload: Mapping[str, Any], compiled: Mapping[str, Any] | None, plan_error: Mapping[str, Any] | None,
              compile_stale: bool = False) -> str:
    """What the agent should do now, in one sentence. Candidates that are the request's own search words (`request_terms`) are
    said so while round 1 has received nothing yet: the agent decides then whether to go on with them or start over with its
    own `products`."""
    said = _next_step(status=status, cand=cand, host=host, rounds=rounds, current=current, upload=upload, compiled=compiled,
                      plan_error=plan_error, compile_stale=compile_stale)
    first = next((r for r in rounds if r["round"] == 1), None)
    if (cand.get("source") == "request_terms" and cand.get("status") == "ready" and status == "collecting" and current == 1
            and first is not None and first["received"] == 0):
        return REQUEST_TERMS_NEXT + said[0].lower() + said[1:]
    return said


def _next_step(*, status: str, cand: Mapping[str, Any], host: Mapping[str, Any], rounds: list[dict], current: int,
               upload: Mapping[str, Any], compiled: Mapping[str, Any] | None, plan_error: Mapping[str, Any] | None,
               compile_stale: bool = False) -> str:
    if cand.get("status") == "failed":
        code = (cand.get("error") or {}).get("error_code") or "NO_CANDIDATES"
        return (f"No product candidates could be formed ({code}): start a new report with products: [{{title, search_terms}}] "
                "(or name a library with corpus_id).")
    if cand.get("status") != "ready":
        return ("Polymath is forming the product candidates from the library (one product turn): call product_report_status "
                "again in about 30 seconds.")
    if status == "compiling":
        if compile_stale:
            return (f"The last compile did not finish (it started more than {COMPILE_STALE_S} seconds ago): call "
                    "product_report_compile again.")
        return "The report is compiling: call product_report_status again in a few seconds."
    if status == "compiled" and compiled and compiled.get("at") and not compiled.get("stale"):
        return (f"The report is compiled: open {compiled.get('report_url')} (it opens in a browser signed in to Polymath); call "
                f"product_report_compile again with verdicts (at most {VERDICT_MAX} characters per candidate_id) to add your own "
                "reading.")
    if status == "failed" and compiled and compiled.get("error"):
        return (f"The last compile failed ({(compiled.get('error') or {}).get('error_code')}): call product_report_compile "
                "again.")
    if plan_error:
        return ("The fetch plan could not be built on this server (FETCH_PLAN_ERROR): call product_report_compile to compile "
                "with the CJ / eBay host data only.")
    cur = next((r for r in rounds if r["round"] == current), None)
    if upload.get("expired"):
        return "The upload link has expired: call product_report_compile now to compile with what was uploaded."
    if cur is not None and not cur["complete"]:
        progress = f"{cur['received']} of {cur['packets']} packets uploaded"
        if upload.get("token") == "required":
            return (f"Round {current} is ready ({progress}): a new upload link can be made after {upload.get('mint_after')}; call "
                    "product_report_status again then, or run the fetch script you already have.")
        return (f"Run round {current}'s fetch script (fetch_plan.script, one shell command) on the user's machine with their "
                f"local Agent Reach, then call product_report_status ({progress} so far).")
    if host.get("status") in ("pending", "collecting"):
        return ("Every fetch packet is in; Polymath is still collecting the CJ / eBay host data: call product_report_status "
                "again shortly, then product_report_compile.")
    return (f"Every fetch packet is in: call product_report_compile now (optionally with verdicts: one text of at most "
            f"{VERDICT_MAX} characters per candidate_id).")


def build_view(row: Mapping[str, Any], ups: list[dict], *, via: str, base: str, note: str | None, token: str | None,
               token_view: str, view: str = "status", mint_after: str | None = None) -> dict[str, Any]:
    """The status view (and the start view). Contract C1: `token` is the upload token the plan's URLs carry — minted for this
    response (`token_view` minted) or the caller's own held one (reused); None (required: a mint is not allowed yet, see
    `mint_after`; expired: the capability has lapsed; none: no plan to run) puts the placeholder UPLOAD_TOKEN there."""
    rid = row["report_id"]
    cand = row.get("candidates") or {}
    expired = store.expired(row)
    upload = {"url": _upload_url(base, rid, token or TOKEN_PLACEHOLDER), "expires_at": store.iso(row.get("upload_expires_at"))}
    plans: dict[int, dict] = {}
    plan_error = None
    if cand.get("status") == "ready" and _items(row):
        try:
            plans = _plans(row, ups, upload)
        except Exception as exc:  # noqa: BLE001 — the status still answers; the plan's absence is typed
            log.warning("product report %s fetch plan failed: %s", rid, f"{type(exc).__name__}: {exc}"[:300])
            plan_error = _err("FETCH_PLAN_ERROR", f"the fetch plan could not be built ({type(exc).__name__})")
    current = int(row.get("round") or 1)
    rounds = _rounds(plans, ups)
    shown = plans.get(current)
    if shown is not None and token_view in ("required", "expired"):          # NEW-2: no script that cannot upload
        shown = {**shown, "script": None, "script_sha256": None,
                 "script_withheld": (f"no upload link can be made until {mint_after}: call product_report_status again then, or run "
                                     "the fetch script you already have" if token_view == "required" else
                                     "the report's upload link has expired: nothing more can be uploaded; compile with what is in")}
    host = _host_view(row.get("host"))
    compiled = _compiled_view(row, ups, base)
    upload_out = {**upload, "expired": expired, "via": via, "token": token_view, "max_bytes": store.MAX_UPLOAD_BYTES,
                  "max_uploads": store.MAX_UPLOADS, **({"mint_after": mint_after} if mint_after else {}),
                  **({"note": note} if note else {})}
    request = row.get("request") or {}
    turn = cand.get("product_turn") if isinstance(cand.get("product_turn"), Mapping) else {}
    out: dict[str, Any] = {
        "contract": CONTRACT, "view": view, "report_id": rid, "status": row["status"],
        "created_at": store.iso(row.get("created_at")), "updated_at": store.iso(row.get("updated_at")),
        "compile_started_at": store.iso(row.get("compile_started_at")),
        "request": {k: request.get(k) for k in ("products_from", "message", "corpus_id", "corpus_ids", "ship_to", "channels",
                                                  "max_products", "ebay_api")},
        "candidates": {"status": cand.get("status") or "collecting", "source": cand.get("source"),
                       "items": [{k: c.get(k) for k in ("candidate_id", "title", "search_terms", "problem", "audience", "source")}
                                 for c in _items(row)],
                       "error": cand.get("error"), "note": cand.get("note"), "product_turn_receipt_id": turn.get("receipt_id"),
                       "product_turn_receipt_ids": list(turn.get("receipt_ids") or ([turn["receipt_id"]] if turn.get("receipt_id") else []))},
        "host": host, "round": current, "rounds": rounds, "fetch_plan": shown,
        "upload": upload_out, "uploads": store.upload_counts(ups), "compiled": compiled,
    }
    if plan_error:
        out["fetch_plan_error"] = plan_error
    out["next"] = next_step(status=row["status"], cand=out["candidates"], host=host, rounds=rounds, current=current,
                            upload=upload_out, compiled=compiled, plan_error=plan_error, compile_stale=_compile_stale(row))
    return out


# ─────────────────────────────────────────────────────────── requests
class ReportProductIn(BaseModel):
    title: str = Field(max_length=500)
    search_terms: list[str] = Field(default_factory=list, max_length=10)
    problem: str | None = Field(default=None, max_length=2000)
    audience: str | None = Field(default=None, max_length=500)


class ReportStartRequest(BaseModel):
    message: str | None = Field(default=None, max_length=4000)
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    products: list[ReportProductIn] | None = Field(default=None, max_length=50)
    ship_to: str = "US"
    channels: list[str] | None = None
    max_products: int | None = None
    model: str | None = None                       # the product turn's model when no products are sent (as /product/search)
    upload_base: Literal["local", "public"] | None = None   # where the user's fetch script runs (Server A knows; default: decided)


class ReportCompileRequest(BaseModel):
    verdicts: dict[str, str] | None = None         # {candidate_id: the agent's reading, <= 1200 characters}
    agent_identity: str | None = Field(default=None, max_length=120)


def candidates_from_products(products: list[ReportProductIn], max_products: int) -> list[dict[str, Any]]:
    """The caller's products as candidates: a title (trimmed), 1–3 search terms (from the title when none), once per title."""
    from polymath_shared.product_search import hypotheses as H
    out, seen = [], set()
    for p in products:
        title = H._text(_clean(p.title), H.TITLE_MAX)
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append({"candidate_id": f"c{len(out) + 1}", "title": title, "search_terms": H._terms(_clean(p.search_terms), title),
                    "problem": H._text(_clean(p.problem), H.PROBLEM_MAX), "audience": H._text(_clean(p.audience), H.AUDIENCE_MAX),
                    "source": "caller"})
        if len(out) >= max_products:
            break
    return out


def _start_settings(req: ReportStartRequest) -> tuple[str, list[str], int, str]:
    """(ship_to, channels, max_products, message) — or a typed 422. U+0000 is dropped from the message (C9)."""
    ship_to = str(req.ship_to or "US").strip().upper()
    if ship_to not in SHIP_TO:
        raise _refuse(422, "BAD_SHIP_TO", "ship_to is US: the channel rules (plan §2) and the money model describe the US market only")
    channels = list(dict.fromkeys(req.channels)) if req.channels else list(CHANNELS)
    unknown = [c for c in channels if c not in CHANNELS]
    if unknown:
        raise _refuse(422, "UNKNOWN_CHANNEL", f"channels are among {', '.join(CHANNELS)} (not {', '.join(map(str, unknown))})")
    max_products = max(1, min(int(req.max_products or DEFAULT_MAX_PRODUCTS), MAX_PRODUCTS))
    message = " ".join(_clean(str(req.message or "")).split())
    return ship_to, channels, max_products, message


def _ebay_api() -> bool:
    try:
        return bool(DEPS.ebay_configured())
    except Exception:  # noqa: BLE001 — unknown = the plan reads eBay through Exa (the report says which)
        return False


def _scope_kind(req: ReportStartRequest, from_products: bool) -> str | None:
    if from_products:
        return None
    return "corpus" if req.corpus_id else "corpora" if req.corpus_ids else "all_authorized"


def _receipt(*, action: str, question: str, req: Any, scope_corpora: list[str], scope_kind: str | None, wall_ms: float,
             client: str, meta: dict[str, Any] | None = None, error: str | None = None,
             degraded: dict[str, Any] | None = None) -> None:
    """ONE query receipt of kind product_report per start / compile: counts and statuses only (meta.product_report; a compile's
    meta.degraded, C6)."""
    out = None if error else {"verdict": (meta or {}).get("status"),
                              "meta": {"route": f"product/report/{action}", "product_report": meta or {},
                                       **({"degraded": degraded} if degraded is not None else {})}}
    record_query_receipt(tx, kind=KIND, question=_clean(question), req=req, scope_corpora=scope_corpora, scope_kind=scope_kind,
                         wall_ms=wall_ms, out=out, error=error, client=_clean(client))


def _error_text(exc: BaseException) -> str:
    detail = getattr(exc, "detail", None)
    return f"{type(exc).__name__}: {detail if detail is not None else exc}"


async def _as(principal: str | None, fn: Callable[..., Any], *args: Any) -> Any:
    """`fn(*args)` in a worker thread under the request's own principal (a context variable does not cross threads by itself; a
    receipt written without it would be stamped as the owner's)."""
    def call() -> Any:
        with principal_context.acting_as(principal):
            return fn(*args)
    return await run_in_threadpool(call)


# ─────────────────────────────────────────────────────────── routes
@router.post("/product/report/start")
async def product_report_start(req: ReportStartRequest, request: Request) -> dict:
    """Plan §3 step 1 — see the module docstring. 403 NON_LOOPBACK_HOST / PROXIED_CALLER (R1 #1); 422 MESSAGE_REQUIRED (no products
    and no message), BAD_PRODUCTS (no product has a title), BAD_SHIP_TO, UNKNOWN_CHANNEL; 429 REPORT_JOB_RUNNING (C8); a product
    turn's scope refusals (QUERY_SCOPE_EMPTY, CORPUS_NOT_ALLOWED, ...) come back typed at once. Never waits for the product turn
    or the host data."""
    refuse_rebinding(request, "the product report")     # before anything: no receipt, no job, no CJ / eBay / model call
    principal = principal_context.current()
    client = request.headers.get("user-agent", "")
    from_products = bool(req.products)
    t0 = time.perf_counter()
    scope: list[str] = [_clean(req.corpus_id)] if req.corpus_id else list(_clean(req.corpus_ids or []))
    try:
        ship_to, channels, max_products, message = _start_settings(req)
        if not from_products and not message:
            raise _refuse(422, "MESSAGE_REQUIRED", "send products: [{title, search_terms}], or a message (the user's product request) "
                                                   "for Polymath to form them from a library")
        items = candidates_from_products(req.products or [], max_products) if from_products else []
        if from_products and not items:
            raise _refuse(422, "BAD_PRODUCTS", "each product needs a title (and 1-3 search_terms)")
        via, base, note = upload_target(request, req.upload_base)
        try:
            claim = _claim(principal)                          # C8: the caller's job slots (the owner 2, a friend 1)
        except JobRunning as busy:
            slots = _slots(principal)
            raise HTTPException(status_code=429, headers={"Retry-After": str(JOB_RETRY_AFTER_S)}, detail={
                **_err("REPORT_JOB_RUNNING", f"{'both of your reports' if slots > 1 else 'a report of yours'} still "
                                             f"gathering data (a product turn or the CJ / eBay host data) use{'' if slots > 1 else 's'} "
                                             f"your {slots} background slot{'s' if slots > 1 else ''}: start the next one in about "
                                             f"{JOB_RETRY_AFTER_S} seconds"),
                "retry_after_s": JOB_RETRY_AFTER_S, "report_id": busy.report_id}) from None

        def _work() -> dict:
            nonlocal scope
            with principal_context.acting_as(principal):
                if not from_products:            # the product turn's scope, checked now: its refusals are the caller's, typed
                    scope = DEPS.resolve_scope(message=message, corpus_id=req.corpus_id, corpus_ids=req.corpus_ids)
                stored_request = {"products_from": "caller" if from_products else "product_route", "message": message or None,
                                  "corpus_id": _clean(req.corpus_id), "corpus_ids": _clean(req.corpus_ids), "ship_to": ship_to,
                                  "channels": channels, "max_products": max_products, "model": _clean(req.model),
                                  "upload_base": req.upload_base, "ebay_api": _ebay_api(), "client": _clean(client[:120])}
                candidates = ({"status": "ready", "source": "caller", "items": items, "error": None, "note": None, "product_turn": None}
                              if from_products else
                              {"status": "collecting", "source": "product_route", "items": [], "error": None, "note": None,
                               "product_turn": None})
                with tx() as conn:
                    row, token = store.create(conn, owner_principal_id=principal, request=stored_request, candidates=candidates,
                                              host={"status": "pending", "started_at": None, "finished_at": None, "error": None,
                                                    "data": None})
                rid = row["report_id"]
                if from_products:
                    _launch(rid, "host", principal, lambda: _collect_host(rid, principal, items, ship_to), claim=claim)
                else:
                    _launch(rid, "candidates", principal, lambda: _form_candidates(rid, principal, stored_request, client),
                            claim=claim)
                out = build_view(row, [], via=via, base=base, note=note, token=token, token_view="minted", view="start")
                out["upload_token"] = token
                _receipt(action="start", question=message or f"product report: {len(items)} products", req=req,
                         scope_corpora=list(scope or []), scope_kind=_scope_kind(req, from_products),
                         wall_ms=(time.perf_counter() - t0) * 1000.0, client=client,
                         meta={"action": "start", "report_id": rid, "status": out["status"],
                               "products_from": stored_request["products_from"], "candidates": len(items),
                               "max_products": max_products, "channels": len(channels), "ship_to": ship_to, "upload_via": via,
                               "fetch_packets": len(_packet_ids(out.get("fetch_plan")))})
                return out
        try:
            return await run_in_threadpool(_work)
        finally:
            _release(principal, claim)
    except Exception as exc:  # receipted, then re-raised unchanged
        error = _error_text(exc)
        await _as(principal, lambda: _receipt(action="start", question=" ".join(str(req.message or "").split()) or "product report",
                                              req=req, scope_corpora=list(scope or []), scope_kind=_scope_kind(req, from_products),
                                              wall_ms=(time.perf_counter() - t0) * 1000.0, client=client, error=error))
        raise


@router.get("/product/report/{report_id}/status")
async def product_report_status(report_id: str, request: Request, upload_base: Literal["local", "public"] | None = None) -> dict:
    """Plan §3 step 3 — see the module docstring. The caller's own reports only (one 404 for "not yours" and "no such report").
    Contract C1 decides the upload token: reused (a held X-Upload-Token, its last use touched) | minted (no valid token sent and the
    report minted none in the last MINT_EVERY_S) | required (no valid token sent, a mint is not allowed yet: `mint_after`) |
    expired | none (no plan to run). A wrong or unknown X-Upload-Token is treated as absent."""
    refuse_rebinding(request, "the product report")
    principal = principal_context.current()
    sent = request.headers.get(TOKEN_HEADER)

    def _work() -> dict:
        with principal_context.acting_as(principal):
            with tx() as conn:
                row = store.get(conn, report_id, principal_id=principal)
                ups = store.uploads(conn, report_id)
            _ensure_jobs(row, principal)
            via, base, note = upload_target(request, upload_base or (row.get("request") or {}).get("upload_base"))
            mint_after = None
            if store.expired(row):
                use, how = None, "expired"                        # nothing can upload any more: no token is minted
            elif store.capability_state(row, sent) == "valid":
                with tx() as conn:
                    store.mark_used(conn, report_id, sent, at=_now())
                use, how = sent, "reused"
            elif _items(row):                                     # a plan to return: a fresh token, at most once a minute
                try:
                    with tx() as conn:
                        use, how = store.mint_token(conn, report_id, at=_now(), every_s=store.MINT_EVERY_S), "minted"
                except store.MintTooSoon as soon:
                    use, how, mint_after = None, "required", store.iso(soon.mint_after)
            else:
                use, how = None, "none"                           # no plan yet (the candidates are being formed, or failed)
            return build_view(row, ups, via=via, base=base, note=note, token=use, token_view=how, mint_after=mint_after)
    try:
        return await run_in_threadpool(_work)
    except store.UnknownReport:
        raise _not_found() from None


async def _read_capped(request: Request, limit: int) -> tuple[bytes, int | None]:
    """(the body, None) — or (b"", the size seen) when it is over `limit`: a declared length says so before anything is read;
    otherwise reading stops at the first byte past the cap (nothing more of it is read or kept)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        return b"", int(declared)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return b"", size
        chunks.append(chunk)
    return b"".join(chunks), None


@router.post("/product/report/{report_id}/upload/{token}")
async def product_report_upload(report_id: str, token: str, request: Request, packet: str | None = None) -> dict:
    """The fetch script's upload (CAPABILITY: no session). Everything that needs no body is checked before the body is read
    (R1 #3): the Host (403 NON_LOOPBACK_HOST), the token's form, the packet name (422 PACKET_REQUIRED), then in one transaction the
    capability (403 UPLOAD_TOKEN_INVALID: a wrong token, another report's, an unknown report; 410 UPLOAD_EXPIRED), the candidates
    (409 CANDIDATES_PENDING) and the packet (404 UNKNOWN_PACKET; 409 ROUND_CLOSED for a packet of a finished round). Then the body:
    over 2 MiB is answered 413 UPLOAD_TOO_LARGE and RECORDED as an OUTPUT_TOO_LARGE packet with no body (C10: its round can still
    complete); 409 UPLOAD_LIMIT_REACHED at 300 packets. A packet the parser cannot read is still stored, with its typed refusal."""
    _refuse_rebound_upload(request)
    if not store.well_formed_capability(report_id, token):
        raise _refuse(403, "UPLOAD_TOKEN_INVALID", "this upload link is not valid for this report")    # no read, no transaction
    if not packet:
        raise _refuse(422, "PACKET_REQUIRED", "the upload names its packet: ?packet=<packet_id>")
    via = "public" if _proxied(request) else "local"
    base = (public_base() or local_base()) if via == "public" else local_base()

    def _open() -> tuple[dict, dict]:
        with tx() as conn:                                       # 1. the capability, the packet — before the body is read
            row = store.by_capability(conn, report_id, token)
            ups = store.uploads(conn, report_id)
        if (row.get("candidates") or {}).get("status") != "ready" or not _items(row):
            raise store.UploadRefused("CANDIDATES_PENDING", 409, "this report has no fetch plan yet")
        upload = {"url": _upload_url(base, report_id, token), "expires_at": store.iso(row.get("upload_expires_at"))}
        try:
            plans = _plans(row, ups, upload)
        except Exception as exc:  # noqa: BLE001
            log.warning("product report %s fetch plan failed at upload: %s", report_id, f"{type(exc).__name__}: {exc}"[:300])
            raise store.UploadRefused("FETCH_PLAN_ERROR", 503, "the fetch plan could not be rebuilt on this server") from None
        current = int(row.get("round") or 1)
        pkt = next((p for p in (plans.get(current) or {}).get("packets") or [] if str(p.get("packet_id")) == packet), None)
        if pkt is None:
            if any(packet in _packet_ids(plans.get(r)) for r in plans if r < current):
                raise store.UploadRefused("ROUND_CLOSED", 409, f"that packet belongs to a finished round: the report is on round {current}")
            raise store.UploadRefused("UNKNOWN_PACKET", 404, "no such packet in this report's current round")
        return {"row": row, "plans": plans, "current": current}, pkt

    def _store(ctx: dict, pkt: dict, raw: bytes, parsed: Mapping[str, Any], status: str) -> dict:
        current, plans = ctx["current"], ctx["plans"]
        source, kind = str(pkt.get("source") or ""), str(pkt.get("kind") or "")
        records = [r for r in parsed.get("records") or [] if isinstance(r, Mapping)]
        targets = [t for t in parsed.get("next_targets") or [] if isinstance(t, Mapping)]
        refused = list(parsed.get("refused") or [])
        with tx() as conn:                                       # 3. stored under the report's lock; round 1 done -> round 2
            locked = store.by_capability(conn, report_id, token, for_update=True)
            if int(locked.get("round") or 1) != current:
                raise store.UploadRefused("ROUND_CLOSED", 409, "the report moved to the next round while this packet was read")
            res = store.add_upload(conn, report_id, packet_id=packet, round_=current, source=source, kind=kind, raw=raw,
                                   status=status, parsed={"candidate_id": pkt.get("candidate_id"), "records": records,
                                                          "next_targets": targets}, refused=refused)
            store.mark_used(conn, report_id, token, at=_now())
            held = {u["packet_id"] for u in store.uploads(conn, report_id, round_=current)}
            expected = set(_packet_ids(plans.get(current)))
            complete = expected <= held
            advanced = complete and store.advance_round(conn, report_id, current=current)
        out = {"contract": CONTRACT, "view": "upload", "report_id": report_id, "packet_id": packet, "round": current,
               "candidate_id": pkt.get("candidate_id"), "source": source, "kind": kind, "status": status,
               "records": len(records), "next_targets": len(targets), "refused": len(refused), "bytes": res["bytes"],
               "sha256": res["sha256"], "replaced": res["replaced"], "kept_earlier": res["kept_earlier"],
               "received": len(expected & held), "expected": len(expected), "round_complete": complete,
               "current_round": current + 1 if advanced else current}
        if res["kept_earlier"]:                                  # NEW-1: an OK packet is never replaced by a worse one
            out["note"] = f"this upload was {status}: the earlier OK upload of this packet is kept"
        return out

    def _parse(ctx: dict, pkt: dict, raw: bytes) -> dict:
        cand = next((c for c in _items(ctx["row"]) if c["candidate_id"] == pkt.get("candidate_id")), {})
        try:                                                     # 2. the text, parsed deterministically (B1)
            parsed = DEPS.parse(str(pkt.get("source") or ""), raw.decode("utf-8", errors="replace"), kind=str(pkt.get("kind") or ""),
                                candidate_terms=list(cand.get("search_terms") or []) or None)
            parsed = parsed if isinstance(parsed, Mapping) else {}
        except Exception as exc:  # noqa: BLE001 — stored with its typed refusal; the script goes on
            parsed = {"status": "UNRECOGNISED", "records": [], "next_targets": [],
                      "refused": [{"code": "PARSE_ERROR", "why": f"the parser failed on this upload ({type(exc).__name__})"}]}
        return _store(ctx, pkt, raw, parsed, str(parsed.get("status") or "UNRECOGNISED"))

    def _too_large(ctx: dict, pkt: dict, size: int) -> dict:
        why = (f"the upload was {size} bytes, over the {store.MAX_UPLOAD_BYTES}-byte cap: nothing of it was kept (C10: the packet "
               "counts as received)")
        return _store(ctx, pkt, b"", {"status": "OUTPUT_TOO_LARGE", "records": [], "next_targets": [],
                                      "refused": [{"code": "OUTPUT_TOO_LARGE", "why": why}]}, "OUTPUT_TOO_LARGE")
    try:
        ctx, pkt = await run_in_threadpool(_open)
        raw, over = await _read_capped(request, store.MAX_UPLOAD_BYTES)
        if over is not None:
            recorded = await run_in_threadpool(_too_large, ctx, pkt, over)
            raise _refuse(413, "UPLOAD_TOO_LARGE", f"an upload holds at most {store.MAX_UPLOAD_BYTES} bytes; this packet is recorded "
                                                   "as OUTPUT_TOO_LARGE", recorded=recorded)
        return await run_in_threadpool(_parse, ctx, pkt, raw)
    except store.UploadRefused as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail()) from None


def _verdicts(raw: Mapping[str, str] | None, items: list[dict], agent_identity: str | None) -> dict[str, Any] | None:
    """The agent's verdicts as stored: {by: agent, agent_identity, submitted_at, items: {candidate_id: text}}; typed 422s. U+0000
    is dropped first (C9: it would fail the jsonb write after the render)."""
    if raw is None:
        return None
    known = {c["candidate_id"] for c in items}
    unknown = sorted(k for k in raw if k not in known)
    if unknown:
        raise _refuse(422, "UNKNOWN_CANDIDATE", f"verdicts are keyed by this report's candidate_id ({', '.join(sorted(known))}); "
                                                f"unknown: {', '.join(_clean(unknown[:5]))}")
    texts = {}
    for cid, text in raw.items():
        text = _clean(str(text or "")).strip()
        if len(text) > VERDICT_MAX:
            raise _refuse(422, "VERDICT_TOO_LONG", f"a verdict holds at most {VERDICT_MAX} characters ({cid}: {len(text)})")
        if text:
            texts[cid] = text
    return {"by": "agent", "agent_identity": _clean(agent_identity) or "connected-agent", "submitted_at": store.iso(_now()),
            "items": dict(sorted(texts.items()))}


def build_bundle(row: Mapping[str, Any], ups: list[dict], verdicts: Mapping[str, Any] | None, as_of: str) -> dict[str, Any]:
    """The decision bundle (plan §4.4): candidates, host (B2's `collect` output; none collected = empty sections with the host
    status), parsed per candidate, settings (the owner's returns rate and Shopify order count, today, the market and the channels)
    — plus what only the page reads (B4a `render_decision`): the agent's verdicts {candidate_id: text}, labelled there as the
    agent's, the report id, a title and `sources` (contract C11, plan §3.6): per Agent Reach source the report's fetch plans hold
    (reddit, amazon, alibaba; ebay only when the host has no eBay API — B1 plans no eBay packet otherwise) {planned: the packets
    planned across the rounds so far, received: the packets uploaded, statuses: {STATUS: count}}. The plans are rebuilt exactly as
    the status view rebuilds them (`_plans`: from the stored row and the round-1 uploads; nothing is stored for this), the counts
    come from the upload rows. A plan that cannot be rebuilt leaves `sources` out: the page then reads as it did before C11."""
    items = _items(row)
    request = row.get("request") or {}
    host = row.get("host") or {}
    data = host.get("data") if isinstance(host.get("data"), Mapping) else None
    bundle: dict[str, Any] = {
        "candidates": items,
        "host": dict(data) if data is not None else {"cj": {}, "ebay": {}, "receipts": [],
                                                      "status": host.get("status") or "pending", "error": host.get("error")},
        "parsed": store.parsed_by_candidate(ups, [c["candidate_id"] for c in items]),
        "settings": {"returns_rate": RETURNS_RATE, "shopify_monthly_orders": SHOPIFY_MONTHLY_ORDERS, "as_of": as_of,
                     "ship_to": request.get("ship_to") or "US", "channels": list(request.get("channels") or CHANNELS)},
        "verdicts": dict((verdicts or {}).get("items") or {}),
        "report_id": row["report_id"],
        "title": "; ".join(c["title"] for c in items)[:120],
    }
    try:                                    # the plans' packets only: the URL is the placeholder one, never shown or run
        upload = {"url": _upload_url(local_base(), row["report_id"], TOKEN_PLACEHOLDER), "expires_at": store.iso(row.get("upload_expires_at"))}
        plans = _plans(row, ups, upload) if items else {}
    except Exception as exc:  # noqa: BLE001 — the page still compiles; it only cannot say what was planned
        log.warning("product report %s: no Agent Reach counts, the fetch plan could not be rebuilt: %s", row["report_id"],
                    f"{type(exc).__name__}: {exc}"[:300])
        return bundle
    planned: dict[str, set[str]] = {}
    for plan in plans.values():
        for p in (plan or {}).get("packets") or []:
            if isinstance(p, Mapping) and p.get("packet_id") and p.get("source"):
                planned.setdefault(str(p["source"]), set()).add(str(p["packet_id"]))
    sources: dict[str, Any] = {}
    for src in sorted(planned, key=lambda s: (store.SOURCES.index(s) if s in store.SOURCES else len(store.SOURCES), s)):
        rows = [u for u in ups if str(u.get("source")) == src]          # every upload of the source: "nothing uploaded" is then exact
        statuses: dict[str, int] = {}
        for u in rows:
            status = str(u.get("status") or "NONE")
            statuses[status] = statuses.get(status, 0) + 1
        sources[src] = {"planned": len(planned[src]), "received": len({str(u.get("packet_id")) for u in rows}),
                        "statuses": dict(sorted(statuses.items()))}
    bundle["sources"] = sources
    return bundle


def _num(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def decision_summary(decision: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Per candidate: the reference price, the offers, and per channel the margin, the break-even ad cost and the delivery verdict
    (B3's numbers, read as they are; a missing value stays null)."""
    out = []
    for p in (decision or {}).get("products") or []:
        if not isinstance(p, Mapping):
            continue
        channels = {}
        for cid, ch in (p.get("channels") or {}).items():
            ch = ch if isinstance(ch, Mapping) else {}
            delivery = ch.get("delivery") if isinstance(ch.get("delivery"), Mapping) else {}
            channels[str(cid)] = {"sell_price_usd": _num(ch.get("sell_price_usd")), "margin_before_ads_usd": _num(ch.get("margin_before_ads_usd")),
                                  "margin_pct": _num(ch.get("margin_pct")), "break_even_ad_cost_usd": _num(ch.get("break_even_ad_cost_usd")),
                                  "delivery": delivery.get("verdict"), "delivery_reason": delivery.get("reason")}
        market = p.get("market") if isinstance(p.get("market"), Mapping) else {}
        out.append({"candidate_id": p.get("candidate_id"), "title": p.get("title"), "offers": len(p.get("offers") or []),
                    "reference_price_usd": _num(market.get("reference_price_usd")), "channels": channels})
    return out


@router.post("/product/report/{report_id}/compile")
async def product_report_compile(report_id: str, request: Request, req: ReportCompileRequest | None = None) -> dict:
    """Plan §3 step 5 — see the module docstring. 409 CANDIDATES_PENDING / NO_CANDIDATES / HOST_DATA_PENDING /
    COMPILE_IN_PROGRESS (a compile younger than COMPILE_STALE_S by `compile_started_at`; an older one was lost and this compile
    replaces it, C9); 422 UNKNOWN_CANDIDATE / VERDICT_TOO_LONG; a render failure keeps the renderer's typed code (B4a's DECISION_*
    codes: 504 for DECISION_TIMEOUT, 502 otherwise; RENDER_FAILED for an untyped one) and a failed save after the render is 500
    COMPILE_SAVE_FAILED (C9); both leave the report `failed` (compile again to retry)."""
    refuse_rebinding(request, "the product report")
    req = req or ReportCompileRequest()
    principal = principal_context.current()
    client = request.headers.get("user-agent", "")
    t0 = time.perf_counter()
    meta: dict[str, Any] = {"action": "compile", "report_id": report_id}
    degraded: dict[str, Any] = {}

    def _fail(row: Mapping[str, Any], code: str, message: str) -> None:
        """The report leaves `compiling` for `failed`, the error on its model (the last good page stays served)."""
        failure = {**dict(row.get("model") or {}), "error": _err(code, message), "failed_at": store.iso(_now())}
        with tx() as conn:
            store.save_model(conn, report_id, failure)
            store.transition(conn, report_id, "failed", current="compiling")
        meta.update({"status": "failed", "error_code": code})

    def _work() -> dict:
        with principal_context.acting_as(principal):
            with tx() as conn:                                   # 1. checks and the move to `compiling`, under the row lock
                row = store.get(conn, report_id, principal_id=principal, for_update=True)
                cand, host = row.get("candidates") or {}, row.get("host") or {}
                if cand.get("status") == "collecting":
                    raise _refuse(409, "CANDIDATES_PENDING", "the product candidates are still being formed: call status first")
                items = _items(row)
                if not items:
                    raise _refuse(409, "NO_CANDIDATES", "this report has no product candidates to compile")
                if host.get("status") in (None, "pending", "collecting"):
                    raise _refuse(409, "HOST_DATA_PENDING", "the CJ / eBay host data is still being collected: call status again shortly")
                status = row["status"]
                if status == "compiling":
                    if not _compile_stale(row):
                        raise _refuse(409, "COMPILE_IN_PROGRESS", "this report is compiling now: call status in a few seconds")
                    store.transition(conn, report_id, "failed", current="compiling")       # a lost compile (a restart)
                    status = "failed"
                verdicts = _verdicts(req.verdicts, items, req.agent_identity) if req.verdicts is not None else row.get("verdicts")
                store.transition(conn, report_id, "compiling", current=status, at=_now())
                ups = store.uploads(conn, report_id)
            as_of = _now().date().isoformat()
            bundle = build_bundle(row, ups, verdicts, as_of)     # 2. the bundle, rendered outside any transaction (B4a)
            meta.update({"candidates": len(items), "uploads": len(ups), "host": host.get("status"),
                         "records": {s: sum(len(v.get(s) or []) for v in bundle["parsed"].values()) for s in store.SOURCES},
                         "verdicts": len((verdicts or {}).get("items") or {})})
            degraded.update(degraded_meta(host, ups))
            try:
                rendered = DEPS.render(bundle)
                html, decision = rendered.get("html"), rendered.get("decision")
                if not isinstance(html, str) or not html.strip():
                    raise ValueError("the renderer returned no HTML")
            except Exception as exc:  # noqa: BLE001 — typed, recorded on the report, the report left `failed`
                code = str(getattr(exc, "code", "") or "RENDER_FAILED")
                log.warning("product report %s compile %s: %s", report_id, code, f"{type(exc).__name__}: {exc}"[:300])
                _fail(row, code, "the report could not be rendered")
                raise _refuse(504 if code in ("DECISION_TIMEOUT", "DOSSIER_TIMEOUT") else 502, code,
                              "the report could not be rendered: compile again") from None
            compiled_at = store.iso(_now())
            html = str(html).replace("\x00", "")
            digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
            model = {"compiled_at": compiled_at, "decision": decision if isinstance(decision, Mapping) else {},
                     "settings": bundle["settings"], "html_sha256": digest, "html_bytes": len(html.encode("utf-8")),
                     "bundle_sha256": hashlib.sha256(json.dumps(bundle, sort_keys=True, default=str).encode()).hexdigest(),
                     "uploads_sha256": store.uploads_digest(ups),      # R3 #4: the snapshot this compile read
                     "inputs": {k: meta[k] for k in ("candidates", "uploads", "host", "records")}, "error": None}
            try:
                with tx() as conn:                               # 3. stored; status `compiled`
                    store.save_model(conn, report_id, model)
                    store.save_html(conn, report_id, html)
                    if verdicts is not None:
                        store.save_verdicts(conn, report_id, verdicts)
                    store.transition(conn, report_id, "compiled", current="compiling")
            except Exception as exc:  # noqa: BLE001 — C9: never left `compiling`; typed; a later compile retries
                log.warning("product report %s compile save failed: %s", report_id, f"{type(exc).__name__}: {exc}"[:300])
                try:
                    _fail(row, "COMPILE_SAVE_FAILED", "the compiled report could not be saved")
                except Exception as again:  # noqa: BLE001 — still `compiling`: the stale limit lets the next compile in
                    log.warning("product report %s could not be marked failed: %s", report_id, f"{type(again).__name__}"[:200])
                    meta.update({"status": "failed", "error_code": "COMPILE_SAVE_FAILED"})
                raise _refuse(500, "COMPILE_SAVE_FAILED", "the compiled report could not be saved: compile again") from None
            _via, base, _note = upload_target(request, (row.get("request") or {}).get("upload_base"))
            report_url = f"{base}/product/report/{report_id}"
            meta.update({"status": "compiled", "html_bytes": model["html_bytes"]})
            return {"contract": CONTRACT, "view": "compile", "report_id": report_id, "status": "compiled",
                    "compiled_at": compiled_at, "report_url": report_url, "report_path": f"/product/report/{report_id}",
                    "html_bytes": model["html_bytes"], "html_sha256": digest, "settings": bundle["settings"],
                    "inputs": model["inputs"],
                    "verdicts": {cid: {"by": "agent", "chars": len(t)} for cid, t in ((verdicts or {}).get("items") or {}).items()},
                    "summary": decision_summary(model["decision"]),
                    "next": (f"Open {report_url} (the user's own report; it opens in a browser signed in to Polymath); call "
                             f"product_report_compile again with verdicts (at most {VERDICT_MAX} characters per candidate_id) to "
                             "add your own reading.")}

    def receipt(error: str | None = None) -> None:
        _receipt(action="compile", question=f"compile {report_id}", req=req, scope_corpora=[], scope_kind=None,
                 wall_ms=(time.perf_counter() - t0) * 1000.0, client=client, meta=None if error else meta, error=error,
                 degraded=None if error else degraded)
    try:
        out = await run_in_threadpool(_work)
    except store.UnknownReport:
        refused = _not_found()
        await _as(principal, receipt, _error_text(refused))
        raise refused from None
    except Exception as exc:  # receipted, then re-raised unchanged
        await _as(principal, receipt, _error_text(exc))
        raise
    await _as(principal, receipt)
    return out


@router.get("/product/report/{report_id}")
async def product_report_page(report_id: str, request: Request, download: bool = False) -> HTMLResponse:
    """The compiled report (the caller's own) under the dossier's CSP: no script, no fetch, no form, no framing by another site;
    `download=1` sends it as a file. 404 NOT_COMPILED before the first compile. (A browser without a session is sent to the web
    app's sign-in by the web boundary, C7.)"""
    refuse_rebinding(request, "the product report")
    principal = principal_context.current()

    def _work() -> str | None:
        with principal_context.acting_as(principal), tx() as conn:
            return store.html_of(conn, report_id, principal_id=principal)
    try:
        page = await run_in_threadpool(_work)
    except store.UnknownReport:
        raise _not_found() from None
    if page is None:
        raise _refuse(404, "NOT_COMPILED", f"this report is not compiled yet: POST /product/report/{report_id}/compile")
    headers = dict(REPORT_HEADERS)
    if download:
        headers["Content-Disposition"] = f'attachment; filename="product-report-{re.sub(r"[^A-Za-z0-9_.-]", "_", report_id)}.html"'
    return HTMLResponse(page, headers=headers)


@router.get("/product/reports")
async def product_reports(request: Request, limit: int = 50, before: str | None = None) -> dict:
    """The caller's reports, newest first (a principal: its own; the owner: every report, with its owner)."""
    refuse_rebinding(request, "the product report")
    principal = principal_context.current()

    def _work() -> list[dict]:
        with principal_context.acting_as(principal), tx() as conn:
            return store.list_for(conn, principal, limit=limit, before=before)
    rows = await run_in_threadpool(_work)
    out = []
    for r in rows:
        cand = r.get("candidates") or {}
        item = {"report_id": r["report_id"], "status": r["status"], "round": r.get("round"),
                "created_at": store.iso(r.get("created_at")), "updated_at": store.iso(r.get("updated_at")),
                "products_from": (r.get("request") or {}).get("products_from"), "candidates_status": cand.get("status"),
                "candidates": [{"candidate_id": c.get("candidate_id"), "title": c.get("title")} for c in cand.get("items") or []
                               if isinstance(c, Mapping)],
                "uploads": int(r.get("uploads") or 0), "compiled": bool(r.get("compiled")), "compiled_at": r.get("compiled_at"),
                "upload_expires_at": store.iso(r.get("upload_expires_at")), "report_path": f"/product/report/{r['report_id']}"}
        if principal is None:
            item["owner_principal_id"] = r.get("owner_principal_id")
        out.append(item)
    return {"contract": CONTRACT, "view": "list", "reports": out}
