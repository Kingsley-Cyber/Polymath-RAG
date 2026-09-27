"""DEEP-RESEARCH-MODE-V1 slice DR6a (§10): research moves in the engine, run with FAKE ports (no I/O, no LLM, no database).

What must hold (§10.2–§10.8): the MOVE grammar (optional, defaulted by level; an unknown value is a repair); a plan's quota
filled in plan order and a short level filled from the leftovers; `allocate` sums to n and never varies; each intent's mix
and the evaluative reserve; the repeat / concentration / one-sided / dry signals; gap nodes inside the budget; the relevance
gate (drops under its floor, fails open, the spawn floor ends a thread); the receipt's moves block and the report's sections;
no signal depends on timing; and moves off = DR1's engine."""
from __future__ import annotations

import hashlib
import random
import re
import threading
import time
from collections import Counter

import pytest
from polymath_shared.deep_research import (
    MOVES,
    Config,
    Row,
    allocate,
    parse_plan,
    run_research,
)
from polymath_shared.deep_research import moves as M
from polymath_shared.deep_research.prompts import REPORT_SYSTEM, REPORT_SYSTEM_GOALS

MECHANISM_Q = "How does habit stacking change daily routines?"     # MECHANISM, not evaluative
EVALUATIVE_Q = "Is habit stacking worth it?"                        # EXPLORATORY, evaluative
DEFINITION_Q = "What is habit stacking?"                            # DEFINITION, not evaluative
THREAD = "THREAD (the search this plan follows up)"
ASKED = re.compile(r"Write at most (\d+) QUERY lines")
SLOT = re.compile(r"^- (\d+) (broad|deep|adjacent|inverse): ", re.MULTILINE)
ROW_CID = re.compile(r'<row cid="([^"]+)"')


def section(prompt: str, head: str) -> str:
    return prompt.split(f"{head}:\n", 1)[1].split("\n\n", 1)[0]


def asked_moves(prompt: str) -> list[str]:
    """The plan prompt's quota, one move per slot, in MOVES order ([] without a MOVES section)."""
    if "MOVES: write " not in prompt:
        return []
    block = prompt.split("MOVES: write ", 1)[1].split("\n\n", 1)[0]
    return [move for n, move in SLOT.findall(block) for _ in range(int(n))]


def thread_of(prompt: str) -> str:
    return section(prompt, THREAD) if f"{THREAD}:\n" in prompt else ""


def tag(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:8]


class LLM:
    """Scripted `complete`, recording every call. Default plan: exactly the moves the quota asks for, one QUERY line per
    slot, named "<move> q<call>s<slot> habit stacking" (so an inverse query shares the topic). Default extract: one learning
    citing the call's first row, one fresh follow-up, DONE: no."""

    def __init__(self, *, plan=None, extract=None):
        self.plan, self.extract = plan, extract
        self.calls: list[tuple[str, str, str]] = []
        self._lock = threading.Lock()

    def __call__(self, prompt: str, *, system: str, max_tokens: int) -> str:
        with self._lock:
            kind = "extract" if "LEARNING:" in system else "plan"
            self.calls.append((kind, system, prompt))
            n = len(self.calls)
        if kind == "extract":
            cids = ROW_CID.findall(prompt)
            if self.extract:
                return self.extract(prompt, cids, n)
            query = section(prompt, "SEARCH QUERY")
            return f"LEARNING: finding{n} on {query} [{cids[0]}]\nFOLLOWUP: next{n} detail{n}?\nDONE: no"
        if self.plan:
            return self.plan(prompt, n)
        return "\n".join(f"QUERY: {move} q{n}s{i} habit stacking || GOAL: goal{n}s{i} || MOVE: {move}"
                         for i, move in enumerate(asked_moves(prompt)))

    def plans(self) -> list[tuple[str, str]]:
        return [(system, prompt) for kind, system, prompt in self.calls if kind == "plan"]


class Retriever:
    """Records (query, move, anchor_docs). Two rows per query, cids from the query text, one document per query; `rows_for`
    may answer a query itself (None = the default rows)."""

    def __init__(self, rows_for=None, delay: float = 0.0):
        self.rows_for, self.delay = rows_for, delay
        self.calls: list[tuple[str, str | None, tuple[str, ...]]] = []
        self._lock = threading.Lock()

    def __call__(self, query: str, scope: object, *, move: str | None = None, anchor_docs=()):
        with self._lock:
            self.calls.append((query, move, tuple(anchor_docs)))
        if self.delay:
            time.sleep(random.uniform(0, self.delay))
        rows = self.rows_for(query) if self.rows_for is not None else None
        if rows is not None:
            return rows
        slug = re.sub(r"\W+", "-", query)[:60].strip("-")
        return [Row(f"{slug}-a", f"text about {query}", "Doc", 0.9, doc_id=f"doc-{slug}"),
                Row(f"{slug}-b", "more text", "Doc", 0.4, doc_id=f"doc-{slug}")]

    def moves(self) -> list[str | None]:
        return [move for _, move, _ in self.calls]


def run(llm: LLM, ret: Retriever | None = None, *, question: str = MECHANISM_Q, gate=None, **cfg):
    ret = ret or Retriever()
    events: list[dict] = []
    out = run_research(question, ("habits",), retrieve=ret, complete=llm, gate=gate,
                       config=Config(**{"today": "2026-09-26", "moves": True, **cfg}), on_event=events.append)
    return out, ret, events


# ─────────────────────────────────────────────────────────── the MOVE grammar and the planner's quota
def test_the_move_field_is_optional_and_an_unknown_one_is_a_repair():
    parsed = parse_plan("QUERY: a1 x || GOAL: g1 || MOVE: deep\n"
                        "QUERY: b1 x || GOAL: g2\n"
                        "QUERY: c1 x || GOAL: g3 || MOVE: sideways\n"
                        "- query: d1 x || goal: g4 || move: Inverse.\n"
                        "QUERY: e1 x || MOVE: adjacent || GOAL: g5\n"
                        "QUERY: chess move: e4 openings || GOAL: g6\n"
                        "QUERY: f1 x || GOAL: g7\n"
                        "MOVE: broad\n", moves=True)
    assert [(i.query, i.goal, i.move) for i in parsed.items] == [
        ("a1 x", "g1", "deep"), ("b1 x", "g2", ""), ("c1 x", "g3", ""), ("d1 x", "g4", "inverse"),
        ("e1 x", "g5", "adjacent"), ("chess move: e4 openings", "g6", ""), ("f1 x", "g7", "broad")]
    assert (parsed.repairs, parsed.unparsed) == (4, 0)       # the unknown move, the loose line, the order, the lone MOVE
    off = parse_plan("QUERY: a1 x || GOAL: g1 || MOVE: deep")  # moves off: DR1's parse (the field is goal text)
    assert [(i.query, i.goal, i.move) for i in off.items] == [("a1 x", "g1 || MOVE: deep", "")] and off.repairs == 0


def test_a_missing_move_is_broad_at_level_one_and_deep_below():
    def plan(prompt, n):                                      # the model never writes MOVE
        return "\n".join(f"QUERY: topic{n}q{i} habit stacking || GOAL: g{n}q{i}"
                         for i in range(int(ASKED.search(prompt)[1])))

    out, ret, _ = run(LLM(plan=plan), breadth=2, depth=2)
    move_of = {query: move for query, move, _ in ret.calls}
    assert Counter((q.depth, move_of[q.query]) for q in out.queries) == {(1, "broad"): 2, (2, "deep"): 2}
    assert out.parse_repairs == 0                             # MOVE is optional: a line without it is still strict


def test_an_unknown_move_takes_the_default_and_counts_as_a_repair():
    def plan(prompt, n):
        return "\n".join(f"QUERY: topic{n}q{i} habit stacking || GOAL: g || MOVE: sideways"
                         for i in range(int(ASKED.search(prompt)[1])))

    out, ret, _ = run(LLM(plan=plan), breadth=3, depth=1)
    assert ret.moves() == ["broad"] * 3 and out.parse_repairs == 3


def test_quotas_fill_in_plan_order_and_a_short_level_fills_from_the_leftovers():
    reply = ("QUERY: deep one habit stacking || GOAL: a || MOVE: deep\n"
             "QUERY: deep two habit stacking || GOAL: b || MOVE: deep\n"
             "QUERY: deep three habit stacking || GOAL: c || MOVE: deep\n"
             "QUERY: broad four habit stacking || GOAL: d || MOVE: broad\n")
    llm = LLM(plan=lambda prompt, n: reply)
    out, ret, events = run(llm, breadth=3, depth=1)
    system, prompt = llm.plans()[0]
    assert asked_moves(prompt) == ["broad", "deep", "inverse"]                # MECHANISM at breadth 3
    assert "MOVES: write 1 broad, 1 deep and 1 inverse query." in prompt and "|| MOVE: <broad|deep|adjacent|inverse>" in system
    # deep one takes the deep slot, broad four the broad slot; no inverse was written, so deep two fills the empty slot
    assert [(q.id, q.query) for q in out.queries] == [
        ("1.1", "deep one habit stacking"), ("1.2", "broad four habit stacking"), ("1.3", "deep two habit stacking")]
    assert sorted(ret.moves()) == ["broad", "deep", "deep"]
    level = out.summary()["moves"]["levels"][0]
    assert level["asked"] == {"broad": 1, "deep": 1, "adjacent": 0, "inverse": 1}
    assert level["planned"] == level["searched"] == {"broad": 1, "deep": 2, "adjacent": 0, "inverse": 0}
    assert next(e for e in events if e["stage"] == "plan")["moves"] == ["deep", "broad", "deep"]


def test_an_inverse_query_that_tests_nothing_in_its_thread_is_dropped_and_its_slot_refilled():
    reply = ("QUERY: criticisms of psychology research || GOAL: habit stacking critiques || MOVE: inverse\n"
             "QUERY: broad view habit stacking || GOAL: a || MOVE: broad\n"
             "QUERY: deep dive habit stacking || GOAL: b || MOVE: deep\n"
             "QUERY: when does habit stacking fail || GOAL: limits || MOVE: inverse\n")
    out, ret, _ = run(LLM(plan=lambda prompt, n: reply), breadth=3, depth=1)
    assert sorted(q for q, _, _ in ret.calls) == ["broad view habit stacking", "deep dive habit stacking",
                                                   "when does habit stacking fail"]
    assert out.summary()["moves"]["inverse_unanchored"] == 1   # its own GOAL naming the topic does not anchor it


# ─────────────────────────────────────────────────────────── the controller
def test_allocate_sums_to_n_and_never_varies():
    for weights in [(1, 3, 0, 0), (1, 2, 0, 1), (2, 0, 0, 2), (1, 0, 3, 0), (2, 0, 2, 0), (2, 1, 1, 0), (0, 0, 0, 0),
                    (0.5, 0.25, 0, 0.25)]:
        for n in range(9):
            split = allocate(weights, n)
            assert sum(split) == n and len(split) == len(MOVES) and min(split) >= 0
            assert all(allocate(weights, n) == split for _ in range(3))
            if any(weights):
                assert all(k == 0 for k, w in zip(split, weights) if w == 0)     # a zero weight never gets a slot
    assert allocate((1, 2, 0, 1), 3) == (1, 1, 0, 1)       # remainders .75 / .5 / 0 / .75: broad, then inverse
    assert allocate((2, 0, 0, 2), 3) == (2, 0, 0, 1)       # a tie goes to the earlier move
    assert allocate((0, 0, 0, 0), 4) == (1, 1, 1, 1)       # no weight at all: even


@pytest.mark.parametrize("intent, three, four", [
    ("EXACT", (1, 2, 0, 0), (1, 3, 0, 0)), ("DEFINITION", (1, 2, 0, 0), (1, 3, 0, 0)),
    ("MECHANISM", (1, 1, 0, 1), (1, 2, 0, 1)), ("PROCEDURE", (1, 1, 0, 1), (1, 2, 0, 1)),
    ("APPLICATION", (1, 1, 0, 1), (1, 2, 0, 1)), ("COMPARISON", (2, 0, 0, 1), (2, 0, 0, 2)),
    ("RELATIONSHIP", (1, 0, 2, 0), (1, 0, 3, 0)), ("SYNTHESIS", (2, 0, 1, 0), (2, 0, 2, 0)),
    ("EXPLORATORY", (2, 0, 1, 0), (2, 0, 2, 0)), ("RECALL", (1, 1, 1, 0), (2, 1, 1, 0))])
def test_each_intents_mix(intent, three, four):
    assert M.root_quota(intent, 3, evaluative=False) == three and M.root_quota(intent, 4, evaluative=False) == four


@pytest.mark.parametrize("question, intent, mix", [
    (MECHANISM_Q, "MECHANISM", "1 broad, 1 deep and 1 inverse query"),
    (DEFINITION_Q, "DEFINITION", "1 broad and 2 deep queries"),
    ("How does jobs-to-be-done thinking relate to blue ocean strategy?", "RELATIONSHIP", "1 broad and 2 adjacent queries"),
    ("Compare habit stacking and temptation bundling", "COMPARISON", "2 broad and 1 inverse query")])
def test_the_questions_intent_sets_the_first_plans_mix(question, intent, mix):
    llm = LLM()
    out, _, _ = run(llm, question=question, breadth=3, depth=1)
    assert f"MOVES: write {mix}." in llm.plans()[0][1] and out.summary()["moves"]["intent"] == intent


def test_an_evaluative_question_reserves_an_inverse_slot_on_every_level():
    for q in (EVALUATIVE_Q, "Should I light night scenes with practicals?", "Which camera is best in low light?",
              "The pros and cons of habit stacking", "How effective is spaced repetition?"):
        assert M.is_evaluative(q), q
    assert not M.is_evaluative(MECHANISM_Q) and not M.is_evaluative("What is the bestiary about?")
    assert M.root_quota("EXPLORATORY", 3, evaluative=True) == (1, 0, 1, 1)
    assert M.root_quota("DEFINITION", 3, evaluative=True) == (1, 1, 0, 1)      # taken from deep first
    assert M.root_quota("COMPARISON", 3, evaluative=True) == (2, 0, 0, 1)      # already holds one: unchanged
    # level 2: the inverse search found nothing, so no child descends from it; the richest child (ties: plan order) gets
    # the reserved slot, and the empty search gets its broad reformulation (a gap node)
    empty = "inverse q1s2 habit stacking"
    llm = LLM()
    out, _, _ = run(llm, Retriever(rows_for=lambda q: [] if q == empty else None), question=EVALUATIVE_Q, breadth=3,
                    depth=2, concurrency=1)
    levels = out.summary()["moves"]["levels"]
    assert levels[0]["asked"] == {"broad": 1, "deep": 0, "adjacent": 1, "inverse": 1}
    assert levels[1]["asked"] == {"broad": 1, "deep": 2, "adjacent": 1, "inverse": 1}
    asked = {thread_of(p): asked_moves(p) for _, p in llm.plans()[1:]}
    assert asked == {"broad q1s0 habit stacking": ["deep", "inverse"], "adjacent q1s1 habit stacking": ["deep", "adjacent"],
                     empty: ["broad"]}
    assert out.summary()["moves"]["signals"]["one_sided"] == 0                 # 2 learnings: the reserve, not the signal


def test_repeat_moves_a_slot_from_deep_to_adjacent():
    shared = [Row("same-a", "the same passage", "Doc", 0.9, doc_id="d1"), Row("same-b", "another", "Doc", 0.8, doc_id="d2"),
              Row("same-c", "a third", "Doc", 0.7, doc_id="d3")]
    llm = LLM()
    out, _, _ = run(llm, Retriever(rows_for=lambda q: shared), breadth=2, depth=2, concurrency=1)
    # the broad search came first in plan order, so only the deep search's rows were all seen already
    asked = {thread_of(p): asked_moves(p) for _, p in llm.plans()[1:]}
    assert asked == {"broad q1s0 habit stacking": ["deep"], "deep q1s1 habit stacking": ["adjacent"]}
    assert out.summary()["moves"]["signals"]["repeat"] == 1
    assert M.child_quota("deep", 2, repeat=True) == (0, 1, 1, 0) and M.child_quota("adjacent", 2, repeat=False) == (0, 1, 1, 0)
    assert M.child_quota("inverse", 2, repeat=False) == (0, 1, 0, 1) and M.child_quota("inverse", 1, repeat=False) == (0, 0, 0, 1)


def test_a_concentrated_parent_anchors_its_childs_deep_queries():
    def rows_for(query):                          # the broad search's rows share one book; the deep search's span three
        slug = re.sub(r"\W+", "-", query)
        if query.startswith("broad"):
            return [Row(f"{slug}-a", "a", "Doc", 0.9, doc_id="book-1"), Row(f"{slug}-b", "b", "Doc", 0.8, doc_id="book-1")]
        return [Row(f"{slug}-{i}", f"t{i}", "Doc", 0.9, doc_id=f"book-{i + 2}") for i in range(3)]

    def extract(prompt, cids, n):                 # every learning cites every row of its call
        return f"LEARNING: finding{n} " + " ".join(f"[{c}]" for c in cids) + f"\nFOLLOWUP: next{n} detail{n}?\nDONE: no"

    out, ret, _ = run(LLM(extract=extract), Retriever(rows_for=rows_for), breadth=2, depth=2, concurrency=1)
    deep = {query: anchors for query, move, anchors in ret.calls if move == "deep"}
    assert deep == {"deep q1s1 habit stacking": (), "deep q4s0 habit stacking": ("book-1",), "deep q5s0 habit stacking": ()}
    m = out.summary()["moves"]
    assert m["deep"] == {"anchored": 1, "unanchored": 2} and m["signals"]["concentration"] == 1
    assert M.concentration_anchors(["b1", "b2", "b1"]) == ("b1", "b2")
    assert M.concentration_anchors(["b1", "b2", "b3"]) == () and M.concentration_anchors(["b1", ""]) == ()
    # only deep queries search inside the anchors: an anchored adjacent / inverse child's other move searches everywhere
    one_book = Retriever(rows_for=lambda q: [Row(re.sub(r"\W+", "-", q) + "-a", "a", "Doc", 0.9, doc_id="book-1")])
    _, ret, _ = run(LLM(), one_book, question=EVALUATIVE_Q, breadth=3, depth=2, concurrency=1)
    level_two = [(move, anchors) for query, move, anchors in ret.calls if not query.endswith(("q1s0 habit stacking",
                                                                                            "q1s1 habit stacking",
                                                                                            "q1s2 habit stacking"))]
    assert Counter(move for move, _ in level_two) == {"deep": 4, "adjacent": 1, "inverse": 1}
    assert all(anchors == (("book-1",) if move == "deep" else ()) for move, anchors in level_two)


def test_a_one_sided_run_gives_its_richest_thread_an_inverse_slot():
    def extract(prompt, cids, n):                 # the broad search finds two things, the deep one finds one
        query = section(prompt, "SEARCH QUERY")
        found = [f"LEARNING: finding{n}x{j} on {query} [{cids[j]}]" for j in range(2 if query.startswith("broad") else 1)]
        return "\n".join(found + [f"FOLLOWUP: next{n} detail{n}?", "DONE: no"])

    llm = LLM(extract=extract)
    out, _, _ = run(llm, breadth=2, depth=2, concurrency=1)     # MECHANISM at breadth 2: 1 broad + 1 deep, no inverse
    asked = {thread_of(p): asked_moves(p) for _, p in llm.plans()[1:]}
    assert asked == {"broad q1s0 habit stacking": ["inverse"], "deep q1s1 habit stacking": ["deep"]}
    assert out.summary()["moves"]["signals"]["one_sided"] == 1
    llm = LLM(extract=extract)                                 # a definition is not one-sided by nature
    run(llm, question=DEFINITION_Q, breadth=2, depth=2, concurrency=1)
    assert all("inverse" not in asked_moves(p) for _, p in llm.plans())


def test_a_move_that_finds_nothing_on_two_levels_goes_dry():
    def extract(prompt, cids, n):                 # deep searches never yield a learning, but their threads go on
        query = section(prompt, "SEARCH QUERY")
        found = [] if query.startswith("deep") else [f"LEARNING: finding{n} [{cids[0]}]"]
        return "\n".join(found + [f"FOLLOWUP: next{n} detail{n}?", "DONE: no"])

    out, _, _ = run(LLM(extract=extract), breadth=2, depth=3, concurrency=1)
    m = out.summary()["moves"]
    assert [lv["asked"]["deep"] for lv in m["levels"]] == [1, 2, 0]
    assert m["levels"][0]["learnings"]["deep"] == m["levels"][1]["learnings"]["deep"] == 0
    assert m["dry_moves"] == ["deep"] and m["levels"][2]["asked"] == {"broad": 2, "deep": 0, "adjacent": 0, "inverse": 0}


@pytest.mark.parametrize("max_retrievals, gaps", [(None, 1), (8, 1), (7, 0)])
def test_a_level_one_search_that_found_nothing_gets_one_broad_reformulation_inside_the_budget(max_retrievals, gaps):
    empty = "deep q1s1 habit stacking"
    llm = LLM()
    out, ret, _ = run(llm, Retriever(rows_for=lambda q: [] if q == empty else None), breadth=3, depth=2, concurrency=1,
                      max_retrievals=max_retrievals)
    limit = Config(breadth=3, depth=2, max_retrievals=max_retrievals).retrieval_limit
    assert out.summary()["moves"]["gap_nodes"] == gaps and out.retrievals <= limit and out.stop_reason == "frontier_empty"
    gap_plans = [p for _, p in llm.plans() if "FOUND NOTHING USABLE" in p]
    assert len(gap_plans) == gaps
    if gaps:
        (plan,) = gap_plans
        assert thread_of(plan) == empty and section(plan, "GOAL SO FAR") == "goal1s1" and asked_moves(plan) == ["broad"]
        assert [move for query, move, _ in ret.calls if query.startswith("broad q")].count("broad") == 2


# ─────────────────────────────────────────────────────────── the relevance gate
def test_the_gate_drops_a_query_under_its_floor_before_it_is_searched():
    seen = []

    def gate(question, items):
        seen.append((question, list(items)))
        return {qid: (0.05 if text.startswith("inverse") else 0.9) for qid, text in items}

    out, ret, events = run(LLM(), gate=gate, breadth=3, depth=1)
    assert seen[0][0] == MECHANISM_Q                                   # the ORIGINAL question, not the thread
    assert [text for _, text in seen[0][1]] == ["broad q1s0 habit stacking", "deep q1s1 habit stacking",
                                                "inverse q1s2 habit stacking"]
    assert sorted(ret.moves()) == ["broad", "deep"] and [q.status for q in out.queries] == ["ok", "ok", "gated"]
    m = out.summary()["moves"]
    assert m["gate"] == {"scored": 3, "dropped": 1, "user_kept": 0, "failed_open": 0}
    assert m["levels"][0]["searched"]["inverse"] == 0
    assert next(e for e in events if e["stage"] == "gate")["dropped"] == 1
    assert events[-1]["completed"] == events[-1]["total"] == 3


def test_the_gate_fails_open_and_counts_it():
    def broken(question, items):
        raise TimeoutError("reranker parked")

    out, ret, _ = run(LLM(), gate=broken, breadth=3, depth=1)
    assert len(ret.calls) == 3 and {q.status for q in out.queries} == {"ok"}
    assert out.summary()["moves"]["gate"] == {"scored": 0, "dropped": 0, "user_kept": 0, "failed_open": 3}
    assert "gate:TimeoutError" in out.errors
    out, ret, _ = run(LLM(), gate=lambda question, items: {}, breadth=3, depth=1)      # a judge that scores nothing
    assert len(ret.calls) == 3 and out.summary()["moves"]["gate"]["failed_open"] == 3


def test_a_hung_gate_never_outlives_the_deadline():
    release = threading.Event()

    def hung(question, items):
        release.wait(5)
        return {}

    started = time.monotonic()
    try:
        out, ret, _ = run(LLM(), gate=hung, deadline_s=0.5)
    finally:
        release.set()
    assert time.monotonic() - started < 2.0 and out.stop_reason == "deadline" and ret.calls == []


def test_a_query_under_the_spawn_floor_keeps_its_learnings_but_spawns_nothing():
    def gate(question, items):
        return {qid: (0.3 if text.startswith("broad") else 0.9) for qid, text in items}

    llm = LLM()
    out, _, _ = run(llm, gate=gate, breadth=3, depth=2, concurrency=1)
    broad = next(q for q in out.queries if q.query == "broad q1s0 habit stacking")
    assert broad.status == "ok" and any(ln.query == broad.query for ln in out.learnings)
    assert out.summary()["moves"]["drift_stopped"] == 1
    threads = [thread_of(p) for _, p in llm.plans()[1:]]
    assert sorted(threads) == ["deep q1s1 habit stacking", "inverse q1s2 habit stacking"]
    assert "next2 detail2?" not in out.open_followups          # a drifting thread's follow-ups are not open questions


# ─────────────────────────────────────────────────────────── receipts, events, the report
def test_the_receipt_carries_the_moves_block_and_the_report_its_goals():
    out, _, events = run(LLM(), question=EVALUATIVE_Q, gate=lambda q, items: {i: 0.9 for i, _ in items}, breadth=3,
                         depth=1, concurrency=1)
    m = out.summary()["moves"]
    assert set(m) == {"intent", "evaluative", "levels", "gate", "drift_stopped", "gap_nodes", "dry_moves",
                      "inverse_unanchored", "deep", "inverse", "signals"}
    assert (m["intent"], m["evaluative"]) == ("EXPLORATORY", True)
    assert m["gate"] == {"scored": 3, "dropped": 0, "user_kept": 0, "failed_open": 0}
    mix = {"broad": 1, "deep": 0, "adjacent": 1, "inverse": 1}
    assert m["levels"] == [{"level": 1, "asked": mix, "planned": mix, "searched": mix, "learnings": mix}]
    assert m["inverse"] == {"searched": 1, "learnings": 1} and {ln.move for ln in out.learnings} == {"broad", "adjacent", "inverse"}
    plan = next(e for e in events if e["stage"] == "plan")
    assert plan["moves"] == ["broad", "adjacent", "inverse"]
    searches = [e for e in events if e["stage"] in ("retrieve", "extract")]
    assert searches and all(e["query"].split()[0] == e["move"] for e in searches)
    # DR7b replaced §10.5's move sections: a TL;DR, one section per goal in plan order, the inverse findings apart
    system, prompt = out.report_prompt(EVALUATIVE_Q)
    assert system == REPORT_SYSTEM_GOALS.format(today="2026-09-26") != REPORT_SYSTEM.format(today="2026-09-26")
    assert "## TL;DR" in system and "## Where sources disagree" in system and "Do not list the sources" in system
    first, second = prompt.index("GOAL: goal1s0\n"), prompt.index("GOAL: goal1s1\n")
    against = prompt.index("COUNTER-EVIDENCE")
    assert first < prompt.index("on broad q1s0") < second < prompt.index("on adjacent q1s1") < against
    assert against < prompt.index("- (goal: goal1s2) finding") < prompt.index("on inverse q1s2") < prompt.index("</data>")
    assert "GOAL: goal1s2" not in prompt and "SEARCHED, NOTHING FOUND" not in prompt


def test_counter_evidence_that_found_nothing_is_none_in_the_report_and_counted_for_the_page():
    def extract(prompt, cids, n):
        query = section(prompt, "SEARCH QUERY")
        return "DONE: yes" if query.startswith("inverse") else f"LEARNING: finding{n} on {query} [{cids[0]}]\nDONE: yes"

    out, _, _ = run(LLM(extract=extract), question=EVALUATIVE_Q, breadth=3, depth=1)
    assert out.summary()["moves"]["inverse"] == {"searched": 1, "learnings": 0}      # the page's "none found" line reads it
    _, prompt = out.report_prompt(EVALUATIVE_Q)
    assert "COUNTER-EVIDENCE (learnings that cut against the findings above):\n(none)" in prompt


def test_the_moves_never_depend_on_timing():
    """Names come from the thread (not the call order), deep searches share rows (repeat) and every row sits in one book
    (concentration): with 1 or 3 workers and jittered searches, the same queries, statuses, learnings and moves block."""
    def plan(prompt, n):
        t = tag(thread_of(prompt) or "root")
        return "\n".join(f"QUERY: {move} {t} s{i} habit stacking || GOAL: goal {t} s{i} || MOVE: {move}"
                         for i, move in enumerate(asked_moves(prompt)))

    def extract(prompt, cids, n):
        query = section(prompt, "SEARCH QUERY")
        return f"LEARNING: finding on {query} [{cids[0]}]\nFOLLOWUP: what else about {tag(query)}?\nDONE: no"

    def rows_for(query):
        slug = "shared" if query.startswith("deep") else re.sub(r"\W+", "-", query)
        return [Row(f"{slug}-a", "text", "Doc", 0.9, doc_id="book-1"), Row(f"{slug}-b", "more", "Doc", 0.5, doc_id="book-1")]

    shapes = []
    for workers in (1, 3):
        out, _, _ = run(LLM(plan=plan, extract=extract), Retriever(rows_for=rows_for, delay=0.01), question=EVALUATIVE_Q,
                        breadth=4, depth=2, concurrency=workers, gate=lambda q, items: {i: 0.9 for i, _ in items})
        summary = out.summary()
        summary.pop("elapsed_s")
        shapes.append(([(q.id, q.query, q.status) for q in out.queries], [(ln.text, ln.move) for ln in out.learnings],
                       summary))
    assert shapes[0] == shapes[1]
    assert shapes[0][2]["moves"]["signals"]["concentration"] > 0 and shapes[0][2]["moves"]["deep"]["anchored"] > 0


def test_the_outcome_names_each_learnings_goal_move_and_documents():
    """What DR7's evidence model reads without re-deriving it: the goals in plan order; a goal id per level-1 thread that its
    children's queries and learnings inherit (a gap node's too); each learning's move and the documents it cites."""
    empty = "deep q1s1 habit stacking"
    out, _, _ = run(LLM(), Retriever(rows_for=lambda q: [] if q == empty else None), breadth=3, depth=2, concurrency=1)
    assert [(g.id, g.goal, g.query, g.move) for g in out.goals] == [
        ("1.1", "goal1s0", "broad q1s0 habit stacking", "broad"), ("1.2", "goal1s1", empty, "deep"),
        ("1.3", "goal1s2", "inverse q1s2 habit stacking", "inverse")]
    assert all(q.goal_id == ".".join(q.id.split(".")[:2]) for q in out.queries)
    assert {q.goal_id for q in out.queries if q.depth == 2} == {"1.1", "1.2", "1.3"}          # 1.2's gap node included
    record = {q.query: q for q in out.queries}
    for ln in out.learnings:
        assert (ln.goal_id, ln.move) == (record[ln.query].goal_id, record[ln.query].move)
        assert ln.doc_ids == ("doc-" + re.sub(r"\W+", "-", ln.query)[:60].strip("-"),)
    # a finding two searches share pools its citations, and its documents with them; it keeps its first finder's goal
    out, _, _ = run(LLM(extract=lambda prompt, cids, n: f"LEARNING: the same finding [{cids[0]}]\nDONE: yes"), breadth=3,
                    depth=1)
    (only,) = out.learnings
    assert len(only.doc_ids) == 3 and only.goal_id == "1.1" and set(only.cids) == set(out.evidence)
    # with moves off the goals and goal ids are there too (DR7 does not depend on moves)
    out = run_research(MECHANISM_Q, ("habits",), retrieve=lambda q, s: [Row(re.sub(r"\W+", "-", q), "t", "Doc", 0.9, "d")],
                       complete=LLM(plan=lambda p, n: "QUERY: t1 x1 || GOAL: g1\nQUERY: t2 x2 || GOAL: g2"),
                       config=Config(today="2026-09-26", depth=1))
    assert [(g.id, g.move) for g in out.goals] == [("1.1", "broad"), ("1.2", "broad")]
    assert [(ln.goal_id, ln.doc_ids) for ln in out.learnings] == [("1.1", ("d",)), ("1.2", ("d",))]


# ─────────────────────────────────────────────────────────── moves off
def test_moves_off_is_dr1s_engine():
    """The two-argument retrieve port, no gate call, no MOVE text in any prompt, no moves block, the DR1 report prompt."""
    class TwoArgs:
        def __init__(self):
            self.calls = []

        def __call__(self, query, scope, /):
            self.calls.append(query)
            return [Row(re.sub(r"\W+", "-", query) + "-a", "text", "Doc", 0.9)]

    def never(question, items):
        raise AssertionError("moves off never gates")

    llm = LLM(plan=lambda prompt, n: "\n".join(f"QUERY: t{n}q{i} x{n}y{i} || GOAL: g"
                                               for i in range(int(ASKED.search(prompt)[1]))))
    ret = TwoArgs()
    out = run_research(MECHANISM_Q, ("habits",), retrieve=ret, complete=llm, gate=never, config=Config(today="2026-09-26"))
    assert (out.retrievals, out.llm_calls, out.stop_reason, len(ret.calls)) == (9, 13, "frontier_empty", 9)
    assert all("MOVE" not in system and "MOVES" not in prompt for _, system, prompt in llm.calls)
    assert "moves" not in out.summary() and out.moves is None and {ln.move for ln in out.learnings} == {"broad"}
    system, prompt = out.report_prompt(MECHANISM_Q)
    assert system == REPORT_SYSTEM.format(today="2026-09-26") and "SECTION:" not in prompt
