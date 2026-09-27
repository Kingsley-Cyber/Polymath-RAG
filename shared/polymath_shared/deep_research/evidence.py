"""DEEP-RESEARCH-MODE-V1 §11.4 (slice DR7b): the evidence model and the sentence audit.

The evidence model is everything factual the report page shows about a run's evidence. It is derived from the outcome by
rule, never from the model's prose or tone:
    confidence   per finding: contested (its goal also has an inverse finding) · strong (≥ 2 documents) · single_source
    counter      the inverse findings, each with its goal
    open         goals with fewer than 2 findings first, then the unexplored follow-ups; de-duplicated; at most 5
    sources      by document: the passages cited and how many findings each document supports
    method       how the run went, in counts
    coverage     per goal: its findings and the distinct documents they cite (the live meters, and the moves-on stop)
The audit splits the report's prose into sentences (headings skipped) and lists the ones with no valid [cid].

Pure: no I/O, no model call. The sentence rule is one regex and a few line rules (`split_sentences`), so the page can
mirror it exactly and mark the same sentences by index.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence
from typing import Any

from .moves import INVERSE, MOVES
from .prompts import cited_ids

CONTESTED, STRONG, SINGLE_SOURCE = "contested", "strong", "single_source"
OPEN_QUESTIONS_MAX = 5
COVERED_LEARNINGS = COVERED_DOCUMENTS = 2        # a goal is covered at ≥ 2 findings from ≥ 2 distinct documents


# ─────────────────────────────────────────────────────────── coverage
def coverage(goal_ids: Sequence[str], learnings: Iterable[Any]) -> list[dict[str, Any]]:
    """Per goal, in the order given: {id, learnings, documents}, counting every learning its thread found (any move) and
    the distinct known documents they cite."""
    count = dict.fromkeys(goal_ids, 0)
    docs: dict[str, set[str]] = {g: set() for g in goal_ids}
    for ln in learnings:
        if ln.goal_id in count:
            count[ln.goal_id] += 1
            docs[ln.goal_id].update(d for d in ln.doc_ids if d)
    return [{"id": g, "learnings": count[g], "documents": len(docs[g])} for g in goal_ids]


def coverage_complete(goals: Sequence[dict[str, Any]]) -> bool:
    """Every goal has ≥ 2 findings from ≥ 2 distinct documents (and there is at least one goal)."""
    return bool(goals) and all(g["learnings"] >= COVERED_LEARNINGS and g["documents"] >= COVERED_DOCUMENTS for g in goals)


# ─────────────────────────────────────────────────────────── the evidence model
def confidence(doc_ids: Sequence[str], contested: bool) -> str:
    if contested:
        return CONTESTED
    return STRONG if len({d for d in doc_ids if d}) >= 2 else SINGLE_SOURCE


def _key(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip(" ?.!")


def evidence_model(outcome: Any, *, intent: str = "", evaluative: bool = False, preset: str = "",
                   model: str = "") -> dict[str, Any]:
    """`report_model` (§11.3): {goals, counter, open_questions, sources, method}.
    - goals: every level-1 goal in plan order, {id, goal, query, move, status, findings: [{text, cids, confidence, move}],
      documents}; its findings are its thread's non-inverse learnings, `documents` counts the distinct documents all of its
      learnings cite (counter-evidence included), `status` is its level-1 search's (ok | empty | error | gated | unfinished).
    - counter: the inverse learnings, {text, cids, goal_id}, in discovery order.
    - open_questions: ≤ 5 strings: goals (their GOAL text, else their query) with fewer than 2 learnings that the gate did
      not drop, then the run's unsearched follow-ups; de-duplicated ignoring case, spacing and end punctuation.
    - sources: by document, {doc_id, title, cids, findings}: its cited passages in first-citation order and how many
      learnings cite at least one of them; most findings first, then first cited.
    - method: the run in counts (see `_method`)."""
    goals = list(outcome.goals)
    status = {q.id: q.status for q in outcome.queries}
    contested = {ln.goal_id for ln in outcome.learnings if ln.move == INVERSE}
    findings: dict[str, list[dict[str, Any]]] = {g.id: [] for g in goals}
    counter: list[dict[str, Any]] = []
    for ln in outcome.learnings:
        if ln.move == INVERSE:
            counter.append({"text": ln.text, "cids": list(ln.cids), "goal_id": ln.goal_id})
        else:
            findings[ln.goal_id].append({"text": ln.text, "cids": list(ln.cids),
                                         "confidence": confidence(ln.doc_ids, ln.goal_id in contested), "move": ln.move})
    covered = {c["id"]: c for c in coverage([g.id for g in goals], outcome.learnings)}
    model_goals = [{"id": g.id, "goal": g.goal, "query": g.query, "move": g.move, "status": status.get(g.id, "unfinished"),
                    "findings": findings[g.id], "documents": covered[g.id]["documents"]} for g in goals]

    open_questions: list[str] = []
    seen: set[str] = set()
    thin = [g.goal or g.query for g in goals
            if covered[g.id]["learnings"] < COVERED_LEARNINGS and status.get(g.id) != "gated"]
    for text in thin + list(outcome.open_followups):
        key = _key(text)
        if key and key not in seen and len(open_questions) < OPEN_QUESTIONS_MAX:
            seen.add(key)
            open_questions.append(text)

    by_doc: dict[str, dict[str, Any]] = {}
    for cid, row in outcome.evidence.items():                      # first-citation order
        entry = by_doc.setdefault(row.doc_id, {"doc_id": row.doc_id, "title": row.title or row.source, "cids": [],
                                               "findings": 0})
        entry["cids"].append(cid)
    doc_of = {cid: row.doc_id for cid, row in outcome.evidence.items()}
    for ln in outcome.learnings:
        for doc in dict.fromkeys(doc_of[c] for c in ln.cids if c in doc_of):
            by_doc[doc]["findings"] += 1
    order = {doc: i for i, doc in enumerate(by_doc)}
    sources = sorted(by_doc.values(), key=lambda s: (-s["findings"], order[s["doc_id"]]))
    return {"goals": model_goals, "counter": counter, "open_questions": open_questions, "sources": sources,
            "method": _method(outcome, intent=intent, evaluative=evaluative, preset=preset, model=model,
                              documents=len(by_doc))}


def _method(outcome: Any, *, intent: str, evaluative: bool, preset: str, model: str, documents: int) -> dict[str, Any]:
    """The Method tab's facts: {preset, model, intent, evaluative, moves, plan, levels, searches, searches_by_move,
    llm_calls, learnings, passages, documents, gate, gap_nodes, drift_stopped, dropped_learnings, empty_searches,
    errors, stop_reason, elapsed_s}. With moves off `searches_by_move`, `gate`, `gap_nodes` and `drift_stopped` are None."""
    moves = outcome.moves
    by_move = None
    if moves is not None:
        by_move = {m: sum(level["searched"][m] for level in moves["levels"]) for m in MOVES}
    return {"preset": preset, "model": model, "intent": intent, "evaluative": evaluative, "moves": moves is not None,
            "plan": "confirmed" if outcome.confirmed_plan else "planned", "levels": outcome.levels,
            "searches": outcome.retrievals, "searches_by_move": by_move, "llm_calls": outcome.llm_calls,
            "learnings": len(outcome.learnings), "passages": len(outcome.evidence), "documents": documents,
            "gate": None if moves is None else moves["gate"],
            "gap_nodes": None if moves is None else moves["gap_nodes"],
            "drift_stopped": None if moves is None else moves["drift_stopped"],
            "dropped_learnings": outcome.dropped_learnings, "empty_searches": outcome.empty_retrievals,
            "errors": outcome.retrieval_errors + outcome.llm_errors, "stop_reason": outcome.stop_reason,
            "elapsed_s": outcome.elapsed_s}


# ─────────────────────────────────────────────────────────── the sentence audit
#: A line is skipped when it is blank, a heading, a horizontal rule, a table row, or inside (or on) a ``` / ~~~ fence.
FENCE = re.compile(r"^\s{0,3}(?:```|~~~)")
HEADING = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
RULE = re.compile(r"^\s{0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
TABLE = re.compile(r"^\s*\|")
#: stripped from the start of a kept line: blockquote marks, then one list marker ("- ", "* ", "+ ", "1. ", "1) ")
MARKER = re.compile(r"^\s*(?:>\s?)*\s*(?:(?:[-*+]|\d{1,3}[.)])\s+)?")
#: one sentence: from a non-space character, lazily, to a run of . ! ? (not right after the abbreviations e.g / i.e / vs /
#: cf / dr / mr / mrs / pp / ch / vol / fig / approx), then closing quotes, brackets or Markdown emphasis (`**Claim.** Next`
#: is two sentences, so a bold claim cannot borrow the next sentence's citation), then any [..] citation groups, then
#: whitespace or the line's end; or else to the line's end. Case-insensitive. The same pattern string runs unchanged in
#: JavaScript with the flags "gis" (dotAll, so "." matches every character of a line in both languages).
SENTENCE_PATTERN = (r"\S.*?(?:(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bcf)(?<!\bdr)(?<!\bmr)(?<!\bmrs)(?<!\bpp)(?<!\bch)"
                    r"(?<!\bvol)(?<!\bfig)(?<!\bapprox)[.!?]+[\"'\u201d\u2019)*_]*(?:\s*\[[^\[\]]*\])*(?=\s|$)|$)")
SENTENCE = re.compile(SENTENCE_PATTERN, re.IGNORECASE | re.DOTALL)


def split_sentences(text: str) -> list[str]:
    """The report's sentences, in order; `audit_report`'s indices point into this list. The rule, for the page to mirror:
    1. Normalise line ends to "\\n" and split into lines.
    2. Skip a line inside a fence (the fence lines too), a blank line, a heading (`#`), a horizontal rule, a table row.
    3. Strip `MARKER` from the start of each kept line; each line is split on its own (a sentence never spans lines).
    4. The line's sentences are the non-empty matches of `SENTENCE` over it, each stripped of surrounding whitespace."""
    out: list[str] = []
    fenced = False
    for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced or not line.strip() or HEADING.match(line) or RULE.match(line) or TABLE.match(line):
            continue
        body = MARKER.sub("", line, count=1)
        out.extend(s for s in (m.group(0).strip() for m in SENTENCE.finditer(body)) if s)
    return out


def audit_report(text: str, valid_ids: Collection[str]) -> dict[str, Any]:
    """`audit` (§11.3): {sentences, cited, uncited: [index], invalid_cids}. A sentence is cited when it carries at least one
    [cid] that is a row of the run (`valid_ids`); indices are 0-based into `split_sentences(text)`. `invalid_cids` lists
    every cited id that is not a row of the run, first appearance first (the answer's `unknown_citations`)."""
    sentences = split_sentences(text)
    uncited = [i for i, s in enumerate(sentences) if not any(c in valid_ids for c in cited_ids(s))]
    return {"sentences": len(sentences), "cited": len(sentences) - len(uncited), "uncited": uncited,
            "invalid_cids": [c for c in cited_ids(text) if c not in valid_ids]}
