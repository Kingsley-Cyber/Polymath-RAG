"""DEEP-RESEARCH-MODE-V1 slices DR7a–c, the engine side (§11.3, §11.4), with FAKE ports (no I/O, no LLM, no database).

What must hold: the plan card's plan is exactly one planner call, accepted as a run's level 1; a confirmed plan seeds level 1
with no planner call, the gate never drops its goals (`user_kept`) and the budget grows with it; Finish now stops the run
after the calls in flight (`finished_early`); with moves a `coverage` event follows each level and `coverage_complete` stops a
covered run early; the evidence model's confidence, counter-evidence, open questions, sources and method on fixed learnings;
the sentence audit on crafted reports; the estimate; and moves off stays DR1's engine."""
from __future__ import annotations

import re
import threading

import pytest
from polymath_shared.deep_research import (
    STOP_REASONS,
    Config,
    Goal,
    Learning,
    QueryRecord,
    ResearchOutcome,
    Row,
    audit_report,
    coverage,
    coverage_complete,
    estimate,
    evidence_model,
    plan_goals,
    run_research,
    split_sentences,
)

MECHANISM_Q = "How does habit stacking change daily routines?"     # MECHANISM, not evaluative
LOOKUP_Q = "What is habit stacking, and is it worth it?"         # DEFINITION + evaluative: the same quota as MECHANISM_Q
THREAD = "THREAD (the search this plan follows up)"
ASKED = re.compile(r"Write at most (\d+) QUERY lines")
SLOT = re.compile(r"^- (\d+) (broad|deep|adjacent|inverse): ", re.MULTILINE)
ROW_CID = re.compile(r'<row cid="([^"]+)"')


def section(prompt: str, head: str) -> str:
    return prompt.split(f"{head}:\n", 1)[1].split("\n\n", 1)[0]


def asked_moves(prompt: str) -> list[str]:
    if "MOVES: write " not in prompt:
        return []
    block = prompt.split("MOVES: write ", 1)[1].split("\n\n", 1)[0]
    return [move for n, move in SLOT.findall(block) for _ in range(int(n))]


class LLM:
    """Scripted `complete`, recording every call; the same defaults as the DR6 moves tests (one query per quota slot named
    "<move> q<call>s<slot> habit stacking"; one learning citing the call's first row, one follow-up, DONE: no)."""

    def __init__(self, *, plan=None, extract=None, on_call=None):
        self.plan, self.extract, self.on_call = plan, extract, on_call
        self.calls: list[tuple[str, str, str]] = []
        self._lock = threading.Lock()

    def __call__(self, prompt: str, *, system: str, max_tokens: int) -> str:
        with self._lock:
            kind = "extract" if "LEARNING:" in system else "plan"
            self.calls.append((kind, system, prompt))
            n = len(self.calls)
        if self.on_call:
            self.on_call(kind, n)
        if kind == "extract":
            cids = ROW_CID.findall(prompt)
            if self.extract:
                return self.extract(prompt, cids, n)
            return f"LEARNING: finding{n} on {section(prompt, 'SEARCH QUERY')} [{cids[0]}]\nFOLLOWUP: next{n} detail{n}?\nDONE: no"
        if self.plan:
            return self.plan(prompt, n)
        moves = asked_moves(prompt) or ["broad"] * int(ASKED.search(prompt)[1])
        return "\n".join(f"QUERY: {move} q{n}s{i} habit stacking || GOAL: goal{n}s{i} || MOVE: {move}"
                         for i, move in enumerate(moves))

    def kinds(self) -> list[str]:
        return [kind for kind, _, _ in self.calls]


class Retriever:
    """Records (query, move); two rows per query from two documents unless `rows_for` answers (None = default rows)."""

    def __init__(self, rows_for=None):
        self.rows_for = rows_for
        self.calls: list[tuple[str, str | None]] = []
        self._lock = threading.Lock()

    def __call__(self, query: str, scope: object, *, move: str | None = None, anchor_docs=()):
        with self._lock:
            self.calls.append((query, move))
        rows = self.rows_for(query) if self.rows_for is not None else None
        if rows is not None:
            return rows
        slug = re.sub(r"\W+", "-", query)[:60].strip("-")
        return [Row(f"{slug}-a", f"text about {query}", "Doc A", 0.9, doc_id=f"docA-{slug}", title=f"A {slug}"),
                Row(f"{slug}-b", "more text", "Doc B", 0.5, doc_id=f"docB-{slug}", title=f"B {slug}")]


def run(llm: LLM, ret: Retriever | None = None, *, question: str = MECHANISM_Q, gate=None, finish=None, plan=None, **cfg):
    ret = ret or Retriever()
    events: list[dict] = []
    out = run_research(question, ("habits",), retrieve=ret, complete=llm, gate=gate, finish=finish, plan=plan,
                       config=Config(**{"today": "2026-09-26", "moves": True, **cfg}), on_event=events.append)
    return out, ret, events


def two_doc_extract(prompt, cids, n):
    """Two learnings from the call's two rows (two documents): every goal is covered after one level."""
    query = section(prompt, "SEARCH QUERY")
    return (f"LEARNING: first{n} on {query} [{cids[0]}]\nLEARNING: second{n} on {query} [{cids[1]}]\n"
            f"FOLLOWUP: next{n} detail{n}?\nDONE: no")


# ─────────────────────────────────────────────────────────── DR7a: the plan card and the confirmed plan
def test_the_plan_card_is_one_planner_call_accepted_like_a_runs_level_one():
    llm = LLM()
    draft = plan_goals(MECHANISM_Q, complete=llm, config=Config(today="2026-09-26", moves=True))
    assert llm.kinds() == ["plan"] and asked_moves(llm.calls[0][2]) == ["broad", "deep", "inverse"]
    assert [(g.id, g.goal, g.query, g.move) for g in draft.goals] == [
        ("1.1", "goal1s0", "broad q1s0 habit stacking", "broad"), ("1.2", "goal1s1", "deep q1s1 habit stacking", "deep"),
        ("1.3", "goal1s2", "inverse q1s2 habit stacking", "inverse")]
    out, _, _ = run(LLM(), depth=1)                                     # a run's level 1 is the same plan
    assert [(g.id, g.query, g.move) for g in out.goals] == [(g.id, g.query, g.move) for g in draft.goals]
    # the run's acceptance, not a looser one: a duplicate and an unanchored inverse query are dropped and counted
    reply = ("QUERY: broad view habit stacking || GOAL: a || MOVE: broad\nQUERY: broad view habit stacking || GOAL: b || "
             "MOVE: deep\nQUERY: criticisms of psychology || GOAL: c || MOVE: inverse\n")
    draft = plan_goals(MECHANISM_Q, complete=LLM(plan=lambda p, n: reply), config=Config(today="2026-09-26", moves=True))
    assert [g.query for g in draft.goals] == ["broad view habit stacking"]
    assert (draft.duplicate_queries, draft.inverse_unanchored) == (1, 1)
    llm = LLM()                                                         # moves off: DR1's planner, every goal broad
    draft = plan_goals(MECHANISM_Q, complete=llm, config=Config(today="2026-09-26"))
    assert "MOVES" not in llm.calls[0][2] and {g.move for g in draft.goals} == {"broad"} and len(draft.goals) == 3


def test_a_planner_error_propagates_to_the_caller():
    def broken(prompt, n):
        raise ConnectionError("lane down")

    with pytest.raises(ConnectionError):
        plan_goals(MECHANISM_Q, complete=LLM(plan=broken), config=Config(today="2026-09-26", moves=True))


def test_a_confirmed_plan_seeds_level_one_with_no_planner_call():
    plan = [("does it stick", "habit stacking adherence studies", "broad"),
            ("where it breaks", "when does habit stacking fail", "inverse"),
            ("the cue", "habit stacking cue design", "deep"),
            ("links", "habit stacking and implementation intentions", "adjacent")]
    llm = LLM()
    out, ret, events = run(llm, plan=plan, breadth=2, depth=2, concurrency=1)    # 4 goals = 2 × breadth
    assert llm.kinds()[0] == "extract" and llm.kinds().count("plan") == 4       # only the four children plan
    assert [(q, m) for q, m in ret.calls[:4]] == [("habit stacking adherence studies", "broad"),
                                                  ("when does habit stacking fail", "inverse"),
                                                  ("habit stacking cue design", "deep"),
                                                  ("habit stacking and implementation intentions", "adjacent")]
    assert [(g.id, g.goal, g.query, g.move) for g in out.goals] == [
        (f"1.{i + 1}", goal, query, move) for i, (goal, query, move) in enumerate(plan)]
    assert out.confirmed_plan and out.stop_reason == "frontier_empty" and out.retrievals == 8   # the budget grew with it
    first = next(e for e in events if e["stage"] == "plan")
    assert first["confirmed"] is True and first["goal_id"] is None
    assert first["goals"] == [{"id": f"1.{i + 1}", "goal": g, "query": q, "move": m} for i, (g, q, m) in enumerate(plan)]
    assert out.summary()["moves"]["levels"][0]["asked"] == {"broad": 1, "deep": 1, "adjacent": 1, "inverse": 1}


def test_a_confirmed_plan_is_checked():
    with pytest.raises(ValueError):
        run(LLM(), plan=[("g", f"query number {i}", "broad") for i in range(5)], breadth=2)   # over 2 × breadth
    with pytest.raises(ValueError):
        run(LLM(), plan=[("g", "   ", "broad")])
    with pytest.raises(ValueError):
        run(LLM(), plan=[("g", "a fine query", "sideways")])
    with pytest.raises(ValueError):
        run(LLM(), plan=[])
    out, ret, _ = run(LLM(), plan=[("g", "a fine query", "sideways")], moves=False, depth=1)  # moves off: moves unread
    assert [q for q, _ in ret.calls] == ["a fine query"] and out.goals[0].move == "broad"


def test_the_gate_never_drops_a_confirmed_goal():
    plan = [("a", "habit stacking adherence", "broad"), ("b", "sourdough starters", "broad")]
    scored = []

    def gate(question, items):
        scored.append([text for _, text in items])
        return {qid: (0.05 if "sourdough" in text else 0.9) for qid, text in items}

    llm = LLM()
    out, ret, events = run(llm, plan=plan, gate=gate, breadth=2, depth=2, concurrency=1)
    assert scored[0] == ["habit stacking adherence", "sourdough starters"]           # the gate still scores them
    assert "sourdough starters" in [q for q, _ in ret.calls]                         # ... and searches the low one anyway
    assert out.summary()["moves"]["gate"]["user_kept"] == 1 and out.summary()["moves"]["gate"]["dropped"] == 0
    assert next(e for e in events if e["stage"] == "gate")["user_kept"] == 1
    threads = [section(p, THREAD) for kind, _, p in llm.calls if kind == "plan"]
    assert threads == ["habit stacking adherence"]              # under the spawn floor, the kept goal spawns no child
    # a query the planner wrote is still dropped: level 2 scored under the floor
    out, ret, _ = run(LLM(), plan=plan[:1], breadth=2, depth=2, gate=lambda q, items: {
        qid: (0.05 if not text.startswith("habit") else 0.9) for qid, text in items})
    assert out.summary()["moves"]["gate"] == {"scored": 2, "dropped": 1, "user_kept": 0, "thread_kept": 0, "failed_open": 0}


# ─────────────────────────────────────────────────────────── DR7c: Finish now
def test_finish_now_stops_after_the_calls_in_flight_and_keeps_what_was_found():
    finish = threading.Event()
    llm = LLM(on_call=lambda kind, n: finish.set() if kind == "extract" else None)
    out, ret, events = run(llm, finish=finish, concurrency=1)
    assert out.stop_reason == "finished_early" and "finished_early" in STOP_REASONS
    assert llm.kinds() == ["plan", "extract"] and len(ret.calls) == 1               # the extract in flight finished ...
    assert len(out.learnings) == 1 and out.levels == 1                              # ... and its learning was kept
    assert events[-1]["stop_reason"] == "finished_early"
    finish = threading.Event()
    finish.set()                                                                   # pressed before anything started
    out, ret, _ = run(LLM(), finish=finish)
    assert (out.stop_reason, out.llm_calls, ret.calls) == ("finished_early", 0, [])


# ─────────────────────────────────────────────────────────── DR7b: coverage
def test_coverage_follows_each_level_and_a_covered_run_stops_early():
    out, _, events = run(LLM(extract=two_doc_extract), question=LOOKUP_Q, concurrency=1)   # standard 3 × 2; a lookup
    cov = [e for e in events if e["stage"] == "coverage"]
    assert len(cov) == 1 and cov[0]["goals"] == [{"id": f"1.{i}", "learnings": 2, "documents": 2} for i in (1, 2, 3)]
    assert (cov[0]["documents"], cov[0]["passages"]) == (6, 6)          # the run's distinct cited documents, rows read
    assert out.stop_reason == "coverage_complete" and out.levels == 1 and out.retrievals == 3
    assert len(out.open_followups) == 3                          # the queued children's directions stay open questions
    # one goal with a single document is not covered: the run goes on to level 2
    def rows_for(query):
        if query.startswith("deep"):
            slug = re.sub(r"\W+", "-", query)
            return [Row(f"{slug}-a", "a", "Doc", 0.9, doc_id="one"), Row(f"{slug}-b", "b", "Doc", 0.8, doc_id="one")]
        return None

    out, _, events = run(LLM(extract=two_doc_extract), Retriever(rows_for), question=LOOKUP_Q, concurrency=1)
    assert out.stop_reason == "frontier_empty" and out.levels == 2
    assert [c["documents"] for c in next(e for e in events if e["stage"] == "coverage")["goals"]] == [2, 1, 2]
    assert sum(e["stage"] == "coverage" for e in events) == 2                      # after every level, the last included


def test_a_goal_the_gate_dropped_does_not_block_coverage():
    def gate(question, items):
        return {qid: (0.05 if text.startswith("inverse") else 0.9) for qid, text in items}

    out, _, events = run(LLM(extract=two_doc_extract), gate=gate, question=LOOKUP_Q, concurrency=1)
    goals = next(e for e in events if e["stage"] == "coverage")["goals"]
    assert goals[2] == {"id": "1.3", "learnings": 0, "documents": 0} and out.stop_reason == "coverage_complete"


def test_a_covered_first_level_never_cuts_the_depth_of_a_how_question():
    """DR6d (live, 2026-09-26): with the early stop open to every question, the standard and thorough runs stopped after level
    1 and read 6 and 5 books where the old loop read 9 and 12. A MECHANISM question keeps the depth the person chose."""
    out, _, events = run(LLM(extract=two_doc_extract), concurrency=1)              # MECHANISM_Q, standard 3 × 2, covered at 1
    first = next(e for e in events if e["stage"] == "coverage")["goals"]
    assert all(g["learnings"] >= 2 and g["documents"] >= 2 for g in first)          # level 1 IS covered ...
    assert out.stop_reason != "coverage_complete" and out.levels == 2               # ... and the run still goes to level 2
    assert out.retrievals > 3


def test_moves_off_has_no_coverage_and_no_coverage_stop():
    events: list[dict] = []
    out = run_research(MECHANISM_Q, ("habits",), retrieve=Retriever(), complete=LLM(extract=two_doc_extract),
                       config=Config(today="2026-09-26"), on_event=events.append)
    assert out.stop_reason == "frontier_empty" and out.levels == 2
    assert not any(e["stage"] == "coverage" for e in events)
    assert not any("goal_id" in e or "goals" in e for e in events)


def test_coverage_counts_every_learning_of_a_goal_and_its_distinct_documents():
    lns = [Learning("a", ("c1",), "g", 1, goal_id="1.1", doc_ids=("d1",)),
           Learning("b", ("c2",), "g", 2, move="inverse", goal_id="1.1", doc_ids=("d2", "")),
           Learning("c", ("c3",), "g", 1, goal_id="1.2", doc_ids=("d3",)),
           Learning("x", ("c4",), "g", 1, goal_id="9.9", doc_ids=("d9",))]
    cov = coverage(["1.1", "1.2", "1.3"], lns)
    assert cov == [{"id": "1.1", "learnings": 2, "documents": 2}, {"id": "1.2", "learnings": 1, "documents": 1},
                   {"id": "1.3", "learnings": 0, "documents": 0}]
    assert not coverage_complete(cov) and coverage_complete(cov[:1]) and not coverage_complete([])


# ─────────────────────────────────────────────────────────── DR7b: the evidence model, on fixed learnings
def outcome_with(learnings, *, moves=True, open_followups=(), statuses=None):
    rows = {"c1": Row("c1", "t", "Laban · ch. 1", 0.9, doc_id="laban", title="Laban"),
            "c2": Row("c2", "t", "Benesh · p. 12", 0.9, doc_id="benesh", title="Benesh"),
            "c3": Row("c3", "t", "Laban · ch. 2", 0.9, doc_id="laban", title="Laban"),
            "c4": Row("c4", "t", "Notes · untitled", 0.9, doc_id="notes"),
            "c5": Row("c5", "t", "Stray row", 0.9)}
    goals = (Goal("1.1", "how effort is written", "laban effort notation", "broad"),
             Goal("1.2", "where notation fails", "limits of effort notation", "inverse"),
             Goal("1.3", "what it connects to", "effort and acting", "adjacent"),
             Goal("1.4", "off the question", "sourdough", "broad"))
    statuses = statuses or {"1.1": "ok", "1.2": "ok", "1.3": "empty", "1.4": "gated"}
    queries = tuple(QueryRecord(g.id, "1", g.query, g.goal, 1, 2, statuses[g.id], g.move, g.id) for g in goals)
    cited = {c for ln in learnings for c in ln.cids}
    block = None if not moves else {
        "intent": "MECHANISM", "evaluative": False, "gate": {"scored": 4, "dropped": 1, "user_kept": 0, "failed_open": 0},
        "gap_nodes": 1, "drift_stopped": 0,
        "levels": [{"level": 1, "asked": {}, "planned": {}, "learnings": {},
                    "searched": {"broad": 1, "deep": 2, "adjacent": 1, "inverse": 1}}]}
    return ResearchOutcome(
        learnings=tuple(learnings), evidence={c: r for c, r in rows.items() if c in cited}, seen_rows=9, queries=queries,
        stop_reason="frontier_empty", levels=2, retrievals=5, llm_calls=8, tokens_est=1000, token_limit=9000,
        dropped_learnings=1, parse_repairs=0, unparsed_lines=0, empty_retrievals=1, duplicate_queries=0, retrieval_errors=0,
        llm_errors=1, errors=("extract:TimeoutError",), empty_threads=("effort and acting",),
        open_followups=tuple(open_followups), elapsed_s=61.5, today="2026-09-26", moves=block, goals=goals)


def test_the_evidence_model_rates_each_finding_by_rule():
    lns = [Learning("effort has four factors", ("c1", "c2"), "g", 1, goal_id="1.1", doc_ids=("laban", "benesh")),
           Learning("effort is written in a staff", ("c3",), "g", 2, move="deep", goal_id="1.1", doc_ids=("laban",)),
           Learning("notation drops timing detail", ("c4",), "g", 1, move="inverse", goal_id="1.2", doc_ids=("notes",)),
           Learning("the limits are practical", ("c2",), "g", 2, move="deep", goal_id="1.2", doc_ids=("benesh",)),
           Learning("an unplaced row", ("c5",), "g", 2, move="deep", goal_id="1.3")]
    model = evidence_model(outcome_with(lns), intent="MECHANISM", evaluative=False, preset="standard", model="m")
    goals = {g["id"]: g for g in model["goals"]}
    assert [g["id"] for g in model["goals"]] == ["1.1", "1.2", "1.3", "1.4"]
    assert [(f["text"], f["confidence"], f["move"]) for f in goals["1.1"]["findings"]] == [
        ("effort has four factors", "strong", "broad"), ("effort is written in a staff", "single_source", "deep")]
    # 1.2 has an inverse finding: its own findings are contested, the inverse one is counter-evidence, not a finding
    assert [(f["text"], f["confidence"]) for f in goals["1.2"]["findings"]] == [("the limits are practical", "contested")]
    assert model["counter"] == [{"text": "notation drops timing detail", "cids": ["c4"], "goal_id": "1.2"}]
    assert goals["1.3"]["findings"][0]["confidence"] == "single_source"              # an unknown document is not a second one
    assert [(g["documents"], g["status"], g["query"], g["move"]) for g in model["goals"]] == [
        (2, "ok", "laban effort notation", "broad"), (2, "ok", "limits of effort notation", "inverse"),
        (0, "empty", "effort and acting", "adjacent"), (0, "gated", "sourdough", "broad")]
    assert set(goals["1.1"]) == {"id", "goal", "query", "move", "status", "findings", "documents"}
    assert set(goals["1.1"]["findings"][0]) == {"text", "cids", "confidence", "move"}


def test_open_questions_put_thin_goals_first_then_open_follow_ups_deduplicated_and_capped():
    lns = [Learning("a", ("c1",), "g", 1, goal_id="1.1", doc_ids=("laban",)),
           Learning("b", ("c3",), "g", 1, goal_id="1.1", doc_ids=("laban",))]
    follow = ("How is effort taught?", "how is  EFFORT taught", "Who wrote the first score?", "What is shape?",
              "What is flow?", "What is weight?")
    model = evidence_model(outcome_with(lns, open_followups=follow))
    # 1.1 has two learnings; 1.2 and 1.3 are thin; 1.4 was dropped by the gate (off the question): never an open question
    assert model["open_questions"] == ["where notation fails", "what it connects to", "How is effort taught?",
                                       "Who wrote the first score?", "What is shape?"]


def test_sources_are_by_document_with_their_passages_and_findings():
    lns = [Learning("a", ("c1", "c2"), "g", 1, goal_id="1.1", doc_ids=("laban", "benesh")),
           Learning("b", ("c3",), "g", 1, goal_id="1.1", doc_ids=("laban",)),
           Learning("c", ("c4", "c2"), "g", 1, move="inverse", goal_id="1.2", doc_ids=("notes", "benesh")),
           Learning("d", ("c5",), "g", 1, goal_id="1.2"),
           Learning("e", ("c4",), "g", 2, goal_id="1.3", doc_ids=("notes",)),
           Learning("f", ("c4",), "g", 2, goal_id="1.3", doc_ids=("notes",))]
    model = evidence_model(outcome_with(lns))
    # most findings first (notes: 3, cited after laban and benesh), then first cited
    assert model["sources"] == [
        {"doc_id": "notes", "title": "Notes · untitled", "cids": ["c4"], "findings": 3},   # no title: the row's label
        {"doc_id": "laban", "title": "Laban", "cids": ["c1", "c3"], "findings": 2},
        {"doc_id": "benesh", "title": "Benesh", "cids": ["c2"], "findings": 2},
        {"doc_id": "", "title": "Stray row", "cids": ["c5"], "findings": 1}]


def test_the_method_says_how_the_run_went():
    lns = [Learning("a", ("c1",), "g", 1, goal_id="1.1", doc_ids=("laban",))]
    method = evidence_model(outcome_with(lns), intent="MECHANISM", evaluative=True, preset="standard",
                            model="litellm:m")["method"]
    assert method == {
        "preset": "standard", "model": "litellm:m", "intent": "MECHANISM", "evaluative": True,
        "moves": {"broad": 1, "deep": 2, "adjacent": 1, "inverse": 1},                 # the page reads it as searches per move
        "plan": "planned", "levels": 2, "searches": 5, "llm_calls": 8, "learnings": 1, "passages": 1, "documents": 1,
        "gate": {"scored": 4, "dropped": 1, "user_kept": 0, "failed_open": 0}, "gap_nodes": 1, "drift_stopped": 0,
        "dropped_learnings": 1, "empty_searches": 1, "errors": 1, "stop_reason": "frontier_empty", "elapsed_s": 61.5}
    off = evidence_model(outcome_with(lns, moves=False))["method"]
    assert (off["moves"], off["gate"], off["gap_nodes"], off["drift_stopped"]) == (None, None, None, None)


def test_a_moves_run_carries_everything_the_evidence_model_reads():
    """Through the engine: goals, goal ids, moves and documents line up, so the model needs nothing re-derived."""
    out, _, _ = run(LLM(extract=two_doc_extract), concurrency=1, depth=1)
    model = evidence_model(out)
    assert [len(g["findings"]) for g in model["goals"]] == [2, 2, 0] and len(model["counter"]) == 2
    assert {f["confidence"] for g in model["goals"][:2] for f in g["findings"]} == {"single_source"}
    assert all(len(s["cids"]) == 1 and s["findings"] == 1 for s in model["sources"]) and len(model["sources"]) == 6


# ─────────────────────────────────────────────────────────── DR7b: the sentence audit (the page's split, rule by rule)
def test_split_skips_blank_lines_headings_fences_tables_and_rules():
    report = ("## TL;DR\n#hashtag line\n\n   \nKept one.\n```\nCode. Not prose.\n```\n~~~\nMore code.\n~~~\n"
              "| a | b |\n  | c |\n---\n***\n___\n===\n- - -\nKept two.")
    # a heading needs "# " (CommonMark), so "#hashtag line" is prose; "===" is a setext underline and is skipped
    assert split_sentences(report) == ["#hashtag line", "Kept one.", "Kept two."]
    assert split_sentences("") == [] and split_sentences("## only a heading\n\n") == []


def test_split_strips_blockquote_marks_and_one_list_marker():
    assert split_sentences("> Quoted line. Another.\n> > Nested.\n- Dash item\n* Star item\n+ Plus item\n"
                           "1. Numbered item\n12) Paren item\n1.5 metres is not a marker.") == [
        "Quoted line.", "Another.", "Nested.", "Dash item", "Star item", "Plus item", "Numbered item", "Paren item",
        "1.5 metres is not a marker."]
    assert split_sentences("- 1. Nested marker") == ["1.", "Nested marker"]          # one marker only: "1." stays prose
    assert split_sentences("> - quoted item. Next.") == ["quoted item.", "Next."]


def test_split_breaks_after_terminal_punctuation_and_its_closers_before_whitespace():
    q, s = chr(0x201D), chr(0x2019)                                  # closing curly quotes
    assert split_sentences("One. Two! Three? Four") == ["One.", "Two!", "Three?", "Four"]
    assert split_sentences(f'He said "stop." Then (left.) Next [x.] More **bold.** _it._ Curly{q}. X.{s} End') == [
        'He said "stop."', "Then (left.)", "Next [x.] More **bold.**", "_it._", f"Curly{q}.", f"X.{s}", "End"]
    assert split_sentences("Pi is 3.14 today.x not split. e.g. this splits") == [
        "Pi is 3.14 today.x not split.", "e.g. this splits"]              # no whitespace, no split; an abbreviation never ends one
    assert split_sentences("A.   B.\tC.") == ["A.", "B.", "C."]
    # NBSP and the ideographic space split in both languages. (U+0085 is whitespace to Python's \\s and not to JavaScript's:
    # a report carrying it audits to a different count on the page, which then shows the counts alone.)
    assert split_sentences("One." + chr(0xA0) + "Two." + chr(0x3000) + "Three.") == ["One.", "Two.", "Three."]


def test_split_gives_a_leading_citation_group_to_the_sentence_before():
    assert split_sentences("A fact. [c1] Next. [c2, c3] [c4] Last.") == ["A fact. [c1]", "Next. [c2, c3] [c4]", "Last."]
    assert split_sentences("Only citations. [c1] [c2]") == ["Only citations. [c1] [c2]"]
    assert split_sentences("See it. [the site](https://example.org) now.") == [
        "See it.", "[the site](https://example.org) now."]                # a link is not a citation group
    assert split_sentences("[c1] at the start of a line stays.") == ["[c1] at the start of a line stays."]


def test_split_never_spans_lines_and_drops_empty_pieces():
    assert split_sentences("First line without an end\ncontinues here.\r\nWindows line.  \n") == [
        "First line without an end", "continues here.", "Windows line."]


def test_the_split_is_the_pages_own():
    """The report view's own cases (frontend-v2 deep-report.test.tsx), which it checks against `auditSentences`."""
    md = ("# Title\nOne fact [c1]. Two facts. [c2] Three?\n\n- Item one [c3].\n- Item two\n```\nCode. Not prose.\n```\n"
          "| a | b |\n---\n> Quoted line. Another.")
    assert split_sentences(md) == ["One fact [c1].", "Two facts. [c2]", "Three?", "Item one [c3].", "Item two",
                                   "Quoted line.", "Another."]
    assert split_sentences('He said "stop." Then left [c1].\n**Bold claim.** Next one.') == [
        'He said "stop."', "Then left [c1].", "**Bold claim.**", "Next one."]


def test_the_audit_lists_the_sentences_without_a_valid_citation():
    prose = ("## TL;DR\n"
             "Laban effort has four factors: weight, time, space and flow [c1]. Teachers use effort notation to train "
             "expressive movement [c2]. It is taught mostly in dance schools.\n\n"
             "## The four factors\n"
             "Weight, time, space and flow each run between two poles [c1][c3]. **Flow is the hardest to observe.** Some "
             "writers add a fifth factor [c9].\n\n"
             "## Where sources disagree\n"
             "Critics say the notation is too coarse for film acting [c4].")
    # the page's fixture and the audit it expects (deep-report.test.tsx)
    assert audit_report(prose, {"c1", "c2", "c3", "c4"}) == {"sentences": 7, "cited": 4, "uncited": [2, 4, 5],
                                                              "invalid_cids": ["c9"]}
    assert audit_report("A claim [the site](https://example.org). Two agree [c9, c1].", {"c1"}) == {
        "sentences": 2, "cited": 1, "uncited": [0], "invalid_cids": ["c9"]}
    assert audit_report("", {"c1"}) == {"sentences": 0, "cited": 0, "uncited": [], "invalid_cids": []}


# ─────────────────────────────────────────────────────────── DR7a: the estimate
@pytest.mark.parametrize("preset, searches, calls, seconds", [
    ("quick", 3, 5, 43), ("standard", 9, 14, 109), ("thorough", 12, 18, 142)])
def test_the_estimate_matches_the_cost_table(preset, searches, calls, seconds):
    assert estimate(Config.preset(preset)) == {"searches": searches, "llm_calls": calls, "seconds": seconds}
    assert estimate(Config.preset(preset), planned=True)["llm_calls"] == calls - 1      # the plan card made level 1


def test_the_estimate_follows_a_confirmed_plans_width_and_the_deadline():
    wide = Config.preset("standard", first_width=6)          # 6 goals, then 2 children each
    assert estimate(wide, planned=True) == {"searches": 18, "llm_calls": 6 + 18 + 1, "seconds": 208}
    assert estimate(Config.preset("thorough", first_width=8, deadline_s=120))["seconds"] == 120
    assert wide.retrieval_limit > Config.preset("standard").retrieval_limit
