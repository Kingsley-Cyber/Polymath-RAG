"""FACET-RETRIEVAL-V1 F1 — the facet step of the chat query compiler (register 11.545; docs/wiki/plans/FACET-RETRIEVAL-V1.md §3.1).

The measured failure (receipt q_e09925df009649c6be872299, 2026-09-27): the compiler's three USER queries were about
storytelling and psychology; "direction for an AI video ad" got no search, so the section that answered it was never
retrieved. The owner's decision: "the compiler should be corpus agnostic for subqueries" — the facets of a request come from
the QUESTION, never from which documents exist.

This module is that step. `compile_facets` makes ONE bounded LLM call whose prompt holds the message and the recent
conversation and nothing else — no corpus id, no library titles, no profile matches (the prompt builder has no parameter
for them, so it cannot). It names 1–5 facets (a facet = a part of the request that could be answered on its own), each
with one search query and the WAY it is asked (an aspect type). The compiler's wording call (`chat_plan.compile_plan`)
then receives the facets and gives every query a `facet_id`; a facet the model leaves without a query gets the facet's
own query. Every failure path returns `facets: None` with a reason and the plan derives its facets from the compiled
queries instead (one per USER query — today's decomposition, unchanged). `facet_coverage` is the receipt's verdict after
retrieval: a facet is covered when ≥ 1 of its queries returned final evidence above the judge floor.

Pure: the only I/O is the injected `complete(system_prompt, user_prompt, max_tokens) -> (text, err)`.
"""
from __future__ import annotations

import math
import os
import time
from collections.abc import Callable, Iterable

from polymath_shared.chat_plan import (
    MAX_FACETS,
    QUERY_TYPES,
    _clean_query,
    _has_instruction_tokens,
    _history_block,
    _parse_json_object,
    _short,
    facets_enabled,
)

FACET_CONTRACT = "chat-facets-v1"
#: the facet call is short: ≤ 5 facets × (name + query + type) — measured ≈ 180 output tokens on the owner's questions
FACET_MAX_OUTPUT_TOKENS = int(os.environ.get("POLYMATH_CHAT_FACETS_MAX_TOKENS", "400"))
#: hard budget: past it the turn plans without the step (the facets derive from the compiled queries), never waits
FACET_BUDGET_S = float(os.environ.get("POLYMATH_CHAT_FACETS_BUDGET_S", "4.0"))
MAX_FACET_NAME_CHARS = 80
#: the WAY a facet is asked — the aspect types; BRIDGE / ADJACENT are not facets (a bridge serves one, ADJACENT restates one)
FACET_TYPES = tuple(t for t in QUERY_TYPES if t not in ("BRIDGE", "ADJACENT"))

__all__ = ["FACET_BUDGET_S", "FACET_CONTRACT", "FACET_MAX_OUTPUT_TOKENS", "FACET_SYSTEM_PROMPT", "compile_facets",
           "facet_coverage", "facet_user_prompt", "facets_enabled", "parse_facets"]

FACET_SYSTEM_PROMPT = """You are the FACET NAMER for a retrieval-augmented assistant. You do NOT answer the user, and you know
nothing about which books or documents exist — the facets come from the request alone.
Read the current message plus the recent conversation and emit ONE JSON object:
{"resolved_request": "...", "facets": [{"id": "f1", "name": "...", "query": "...", "type": "..."}]}
Rules:
- resolved_request: the request as one standalone sentence, pronouns and references resolved from the conversation.
  NEVER change the task.
- A FACET is a part of the request that could be answered on its own — a distinct thing the answer must know or decide.
  Name 1 to 5, most central first; f1 is the request's core. A lookup, a definition or a single-subject question has
  exactly ONE facet. A request that asks for several things, or for a deliverable that needs several kinds of knowledge,
  has one facet per thing: a story AND how to direct the tool that will make it; a comparison's two sides; a method AND
  its failure modes; an effect AND how to produce it. Name the facets the user did not spell out but the deliverable
  cannot do without — how to instruct or direct a named tool, model or medium is a facet of its own.
- name: at most 8 words, in the user's own terms. query: a SHORT search query for that facet alone — topical words only,
  never tone, length, format or output instructions; identifiers, acronyms and product or model names copied VERBATIM.
- type: how the facet is asked — PRIMARY for f1; otherwise one of DEFINITION, MECHANISM, CAUSAL, COMPARISON, COUNTERPOINT,
  PROCEDURE, EXAMPLE, ENTITY.
- Never invent a facet the request does not need; never split one thing into synonyms.
Output ONLY the JSON object. No prose, no markdown fences."""


def facet_user_prompt(message: str, history: Iterable) -> tuple[str, int]:
    """The facet step's prompt: the conversation and the message. There is no parameter for a corpus, a title list or a
    profile match — the step is corpus-agnostic by construction."""
    hist, n = _history_block(history)
    return f"RECENT CONVERSATION:\n{hist}\n\nCURRENT MESSAGE:\n{(message or '').strip()}\n\nJSON:", n


def parse_facets(raw: dict, message: str) -> tuple[list[dict] | None, str | None]:
    """Strict, deterministic. (facets, None) or (None, reason). Ids are renumbered f1…fn in the model's order; a facet
    without a usable name is dropped; a query that carries output instructions or is empty falls back to the name; a
    facet whose query repeats an earlier facet's (synonyms) is folded; f1 is PRIMARY and every other facet a listed
    aspect type (unknown → MECHANISM). More than MAX_FACETS → the first MAX_FACETS."""
    if not isinstance(raw, dict):
        return None, "not_an_object"
    items = raw.get("facets")
    if not isinstance(items, list) or not items:
        return None, "facets_missing"
    out: list[dict] = []
    seen_queries: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        name = _short(it.get("name"), MAX_FACET_NAME_CHARS)
        if not name:
            continue
        query = _clean_query(it.get("query"))
        if not query or _has_instruction_tokens(query):
            query = _clean_query(name)
            if not query or _has_instruction_tokens(query):
                continue
        key = query.lower()
        if key in seen_queries:
            continue
        seen_queries.add(key)
        qtype = str(it.get("type") or "").strip().upper()
        if not out:
            qtype = "PRIMARY"
        elif qtype not in FACET_TYPES or qtype == "PRIMARY":
            qtype = "MECHANISM"
        out.append({"id": f"f{len(out) + 1}", "name": name, "query": query, "type": qtype})
        if len(out) >= MAX_FACETS:
            break
    if not out:
        return None, "no_usable_facets"
    return out, None


def compile_facets(message: str, history: Iterable, complete: Callable[[str, str, int], tuple[str, str | None]],
                   *, budget_s: float = FACET_BUDGET_S, model: str | None = None) -> dict:
    """ONE bounded call → {"contract", "facets": [...] | None, "fallback", "reason", "wall_ms", "model", "n",
    "resolved_request"}. Never raises; every failure is a receipted `facets: None` (the plan derives its facets)."""
    t0 = time.perf_counter()
    prompt, n_hist = facet_user_prompt(message, history)
    rec: dict = {"contract": FACET_CONTRACT, "model": model, "history_turns": n_hist, "facets": None, "n": 0,
                 "fallback": True, "reason": None, "resolved_request": None}
    try:
        text, err = complete(FACET_SYSTEM_PROMPT, prompt, FACET_MAX_OUTPUT_TOKENS)
    except Exception as exc:  # noqa: BLE001 — the transport never breaks a turn
        text, err = "", f"{type(exc).__name__}"
    wall_ms = (time.perf_counter() - t0) * 1000
    rec["wall_ms"] = round(wall_ms, 1)
    if err:
        rec["reason"] = f"transport:{err}"
        return rec
    if wall_ms > budget_s * 1000:
        rec["reason"] = f"budget_exceeded:{int(wall_ms)}ms"
        return rec
    raw = _parse_json_object(text)
    if raw is None:
        rec["reason"] = "invalid_json"
        return rec
    facets, reason = parse_facets(raw, message)
    if facets is None:
        rec["reason"] = f"invalid_facets:{reason}"
        return rec
    rec.update({"facets": facets, "n": len(facets), "fallback": False, "resolved_request": _short(raw.get("resolved_request"), 400)})
    return rec


def _sig(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x)))))


def facet_coverage(facets: Iterable[dict], final_detail: Iterable[dict], *, floor: float) -> dict:
    """The receipt's verdict per facet: COVERED when ≥ 1 of its queries returned final evidence whose judge score clears
    `floor` (the sigmoid of the logit — `aspect_weak_floor`). On a turn the judge never scored (fusion order stands)
    a facet with final evidence counts as covered and the verdict says `judge: unjudged`, never a floor verdict."""
    rows = [r for r in (final_detail or []) if isinstance(r, dict)]
    judged = any(r.get("rerank_score") is not None for r in rows)
    covered: list[str] = []
    uncovered: list[str] = []
    for f in facets or []:
        fid = str(f.get("id") or "")
        if not fid:
            continue
        qids = {str(q) for q in (f.get("query_ids") or [])}
        hit = False
        for r in rows:
            if not (qids & {str(q) for q in (r.get("query_ids") or [])}):
                continue
            s = r.get("rerank_score")
            if (s is None and not judged) or (s is not None and _sig(s) >= floor):
                hit = True
                break
        (covered if hit else uncovered).append(fid)
    return {"covered": covered, "uncovered": uncovered, "judge": "live" if judged else "unjudged"}
