"""CORPUS-PLAN-V1 (2026-09-03) — Polymath compiles the research reformulations.

A consumer sends ONE signal; Polymath compiles 3–5 deterministic
reformulations (seed / tension / communities / invariant / contrast, padded
for short signals), runs each through the EXPLORE evidence view and returns
the merged rows stamped with the query ids that found them. The compiler is
a byte-for-byte port of TRAIL OS `python/corpus_queries.py` — same hashing,
same ids — and `contracts/retrieve/v1/corpus_plan_fixture.json` pins parity
in both repos. No LLM, no state: same signal, same plan.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


def stable_id(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]

_STOP = set("""a an and are as at be been being by for from has have how i if in into is it its of on or that the their them
there these they this to was were what when where which who why will with would you your about after also because before
between both can could do does did each even every few had here him his how just like made make many may me more most much
my never no nor not now off once only other our out over own same she should so some still such than then through too under
until up very we well while whole""".split())

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(])")


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    return [s.strip() for s in _SENT.split(text) if len(s.strip()) > 20]


def _section(signal: str, marker: str) -> str:
    i = signal.upper().find(marker.upper())
    if i == -1:
        return ""
    rest = signal[i + len(marker):]
    j = re.search(r"\n\s*\n|(?:LATENT INTERPRETATION|SEED)\s*\(", rest)
    return rest[: j.start()] if j else rest


def _keywords(text: str, n: int = 8) -> list[str]:
    toks = re.findall(r"[a-zA-Z][a-zA-Z\-']{3,}", (text or "").lower())
    freq: dict[str, int] = {}
    for t in toks:
        if t in _STOP:
            continue
        freq[t] = freq.get(t, 0) + 1
    return [t for t, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def _trim(s: str, n: int = 220) -> str:
    s = re.sub(r"\s+", " ", s).strip().strip('"“”')
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0]


def compile_queries(state: dict, policies: dict) -> list[dict]:
    signal = state["data"].get("signal") or ""
    seed = _section(signal, "SEED") or signal
    latent = _section(signal, "LATENT INTERPRETATION")
    out: list[dict] = []

    def add(kind: str, text: str, why: str, minlen: int = 12):
        text = _trim(text)
        if len(text) < minlen or any(q["query"] == text for q in out):
            return
        out.append({"id": stable_id("cq", kind, text), "kind": kind, "query": text, "why": why})

    ss = _sentences(re.sub(r"^\s*\([^)]*\):?\s*", "", seed))
    if ss:
        add("seed", ss[0], "the concrete situation the seed describes")
    ls = _sentences(latent)
    if ls:
        add("tension", ls[0], "the latent human tension beneath the topic")
    for s in ls[1:]:
        low = s.lower()
        if "communit" in low or "forum" in low or "subreddit" in low or "r/" in low:
            add("communities", s.split(":", 1)[-1], "where the tension is lived — recall across contexts")
            break
    for s in ls[1:]:
        low = s.lower()
        if any(w in low for w in ("capacity", "aspiration", "tension is", "sense of", "wants", "want to")):
            add("invariant", s, "the capacity / aspiration — the cross-domain hook")
            break
    kws = _keywords(seed + " " + latent, 10)
    if len(kws) >= 4:
        add("contrast", "why do people keep " + " ".join(kws[:6]), "behaviour-level probe from the strongest terms")
    pol = (policies.get("corpus") or {})
    lo, hi = int(pol.get("min_queries", 3)), int(pol.get("max_queries", 5))
    if len(out) < lo:
        for s in (ss + ls)[1:]:
            if len(out) >= lo:
                break
            add("sentence", s, "additional reformulation to reach the minimum breadth")
    # a short or plain signal still gets a plan: the seed verbatim, its strongest
    # terms, and a behaviour probe — never an empty corpus lane
    if len(out) < lo:
        add("seed", seed.strip() or signal.strip(), "the seed verbatim", minlen=3)
        kws = kws or _keywords(signal, 6)
        if kws:
            add("keywords", " ".join(kws[:6]), "the strongest terms, unordered — recall over precision", minlen=3)
            add("behaviour", "how people cope with " + " ".join(kws[:4]), "behaviour-level probe", minlen=3)
    return out[:hi]


def corpus_query_compiler(state: dict, policies: dict) -> str:
    qs = compile_queries(state, policies)
    state["data"]["corpus_queries"] = qs
    return f"compiled {len(qs)} corpus reformulations: " + ", ".join(q["kind"] for q in qs)


def compile_plan(signal: str, communities: list | None = None, min_queries: int = 3, max_queries: int = 5) -> list[dict]:
    state = {"data": {"signal": signal or "", "communities": list(communities or [])}}
    policies = {"corpus": {"min_queries": int(min_queries), "max_queries": int(max_queries)}}
    return compile_queries(state, policies)


router = APIRouter()


class PlanRequest(BaseModel):
    signal: str
    corpus_id: Optional[str] = None
    corpus_ids: Optional[list[str]] = None
    limit: int = 24
    explore: bool = True
    communities: list[str] = []
    min_queries: int = 3
    max_queries: int = 5
    # DOCUMENT-SCOPED-RETRIEVE-V1: threaded into every reformulation's retrieve
    document_ids: Optional[list[str]] = None


@router.post("/retrieve/plan")
async def retrieve_plan(req: PlanRequest) -> dict:
    from orchestrator.api.retrieve import RetrieveRequest, _retrieve_impl

    signal = (req.signal or "").strip()
    if not signal:
        raise HTTPException(status_code=422, detail="signal is required")
    corpus_ids = list(req.corpus_ids or ([req.corpus_id] if req.corpus_id else []))
    if not corpus_ids:
        raise HTTPException(status_code=422, detail="corpus_id or corpus_ids is required")
    plan = compile_plan(signal, req.communities, req.min_queries, req.max_queries)
    merged: dict[str, dict] = {}
    per_query, errors = [], []
    for q in plan:
        for cid in corpus_ids:
            rreq = RetrieveRequest(query=q["query"], corpus_id=cid, limit=int(req.limit),
                                   mode="EXPLORE" if req.explore else None, evidence=True,
                                   document_ids=req.document_ids)
            try:
                out = await _retrieve_impl(rreq)
            except HTTPException as exc:
                errors.append({"query_id": q["id"], "corpus_id": cid, "status": exc.status_code, "detail": str(exc.detail)[:200]})
                continue
            new = 0
            for row in out.get("evidence_rows") or []:
                rid = row.get("id")
                if not rid:
                    continue
                if rid in merged:
                    if q["id"] not in merged[rid]["query_ids"]:
                        merged[rid]["query_ids"].append(q["id"])
                    continue
                merged[rid] = dict(row, query_ids=[q["id"]], corpus_id=row.get("corpus_id") or cid)
                new += 1
            per_query.append({"query_id": q["id"], "kind": q["kind"], "corpus_id": cid, "new_rows": new})
    out = {"plan": plan, "plan_contract": "corpus-plan-v1",
           "evidence_rows": list(merged.values()), "evidence_contract": "retrieve-evidence-rows-v1",
           "corpus_ids": corpus_ids, "per_query": per_query, "errors": errors}
    if req.document_ids:
        out["document_ids"] = list(req.document_ids)  # the filter as applied (additive)
    return out
