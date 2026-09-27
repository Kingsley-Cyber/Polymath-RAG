"""DEEP-RESEARCH-MODE-V1 engine (slice DR1): a breadth × depth research loop over the caller's own libraries.
Loop after dzhng/deep-research, MIT; no text copied.

Pure: no I/O, no network, no Polymath imports. Two injected ports do the work, so the route (DR2) owns transport, lanes,
streaming and receipts, and tests run the whole loop with fakes:
    retrieve(query, scope) -> [Row]                   evidence retrieval inside the request's libraries
    complete(prompt, *, system, max_tokens) -> str    one budgeted LLM call

WHY levels, not recursion: dzhng recurses per branch. Here the tree is walked one level at a time, so progress streams as
"level k, completed/total", the budget and the deadline are checked before EVERY port call, and each level's plans see the
learnings of the whole level before it (per-branch learnings were left out on purpose: siblings re-asked each other's queries).
WHY the scope is opaque: `scope` reaches every retrieve call as the very object the caller passed. No LLM output ever touches
it, so a plan can change WHAT is searched for, never WHERE (K1: an LLM never widens a scope).
WHY every learning cites: a learning survives only when ALL its cids are rows of the call that produced it. The rest are
dropped and COUNTED, and `evidence` keeps only rows a surviving learning cites (plan §6).
WHY the outcome never depends on timing: port calls run on a bounded pool, but queries are de-duplicated in frontier order after
a level's plans all return, and learnings merge in plan order after its extracts all return. Only halts (budget, deadline,
cancel) can cut a level short, and they are reported as the stop reason.
"""
from __future__ import annotations

import datetime as _dt
import math
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from typing import Any, Protocol

from . import prompts as P

#: breadth × depth presets (plan §3). The route maps the composer's preset name through PRESETS / Config.preset.
QUICK, STANDARD, THOROUGH = (3, 1), (3, 2), (4, 2)
PRESETS: dict[str, tuple[int, int]] = {"quick": QUICK, "standard": STANDARD, "thorough": THOROUGH}
#: frontier_empty / no_new_followups end a run naturally; budget / deadline / cancelled cut it short
STOP_REASONS = ("frontier_empty", "no_new_followups", "budget", "deadline", "cancelled")
DEADLINE_HARD_MAX_S = 360.0
MAX_BREADTH, MAX_DEPTH, MAX_CONCURRENCY = 6, 4, 8
HEADROOM = 1.25                      # derived call and retrieval limits sit this far above a full run
NEAR_DUPLICATE = 0.8                 # normalised-token Jaccard at or above which two queries are one query
LEARNINGS_PER_EXTRACT = 3
PLAN_PROMPT_TOKENS_EST = 1_200       # plan system + question + goal + known learnings + searched list, before the output
EXTRACT_PROMPT_TOKENS_EST = 700      # extract system + question + goal + query, before the rows
_POLL_S = 0.25                       # how often an in-flight wait re-checks the deadline and the cancel flag
_CID = re.compile(r"[^\s\[\]<>\"',;]{1,200}")
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for", "from", "how", "in", "into", "is", "it", "its",
    "of", "on", "or", "than", "that", "the", "their", "this", "to", "vs", "was", "were", "what", "when", "where", "which", "who",
    "whom", "whose", "why", "with"})


@dataclass(frozen=True)
class Row:
    """One retrieved passage. `cid` is what the model copies into citations, so it must be 1-200 characters with no
    whitespace, square or angle brackets, quotes, commas or semicolons (the parsers split on those)."""
    cid: str
    text: str
    source: str               # title / section label shown to the model beside the row
    score: float

    def __post_init__(self) -> None:
        if not isinstance(self.cid, str) or not _CID.fullmatch(self.cid):
            raise ValueError(f"unusable cid {self.cid!r}: 1-200 chars, no whitespace, brackets, quotes, commas or semicolons")
        if not isinstance(self.text, str) or not isinstance(self.source, str):
            raise TypeError("Row.text and Row.source must be str")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError(f"Row.score must be a number, got {type(self.score).__name__}")


@dataclass(frozen=True)
class Learning:
    text: str
    cids: tuple[str, ...]
    goal: str                 # the GOAL of the query whose rows produced it (the report groups by it)
    depth: int                # the level that found it: 1 = the question's own queries
    query: str = ""


@dataclass(frozen=True)
class QueryRecord:
    id: str                   # "1.2" = the 2nd query planned by node "1"; the child node it spawns takes the same id
    node: str
    query: str
    goal: str
    depth: int
    rows: int = 0
    status: str = "unfinished"   # ok | empty | error | unfinished (planned, then cut off by a halt)


class RetrievePort(Protocol):
    def __call__(self, query: str, scope: Any, /) -> Sequence[Row]: ...


class CompletePort(Protocol):
    def __call__(self, prompt: str, *, system: str, max_tokens: int) -> str: ...


def preset_cost(breadth: int, depth: int) -> tuple[int, int, int]:
    """(plan calls, retrievals, extract calls) of a FULL run, where every extract returns follow-ups and DONE: no. Nothing can
    exceed it: a plan keeps ≤ breadth queries and each query spawns ≤ 1 child. The report call is the route's, not counted."""
    plans = retrievals = 0
    nodes, width = 1, breadth
    for _ in range(depth):
        plans += nodes
        retrievals += nodes * width
        nodes, width = nodes * width, math.ceil(width / 2)
    return plans, retrievals, retrievals


@dataclass(frozen=True)
class Config:
    """One run's shape and budget. `max_retrievals` / `max_llm_calls` / `max_tokens` left at None are derived from
    breadth × depth with headroom (the *_limit properties), so `dataclasses.replace(cfg, breadth=4)` re-derives them."""
    breadth: int = STANDARD[0]
    depth: int = STANDARD[1]
    concurrency: int = 2               # the embedder and reranker share one Metal GPU (plan §3)
    deadline_s: float = 240.0          # hard max DEADLINE_HARD_MAX_S
    max_retrievals: int | None = None
    max_llm_calls: int | None = None
    max_tokens: int | None = None      # the run's whole estimated token budget, report reserve included
    report_reserve: float = 0.15       # the engine stops at (1 - reserve) = 85% of max_tokens; the rest is the report's
    score_floor: float = 0.0           # a retrieval with no row scoring at or above it ends its branch
    max_rows_per_query: int = 10
    max_row_chars: int = 1_600
    plan_max_tokens: int = 512
    extract_max_tokens: int = 1_024
    report_max_learnings: int = 30
    today: str | None = None           # ISO date for the prompts; None = the local date at run start
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        if not 1 <= self.breadth <= MAX_BREADTH or not 1 <= self.depth <= MAX_DEPTH:
            raise ValueError(f"breadth must be 1..{MAX_BREADTH} and depth 1..{MAX_DEPTH}")
        if not 1 <= self.concurrency <= MAX_CONCURRENCY:
            raise ValueError(f"concurrency must be 1..{MAX_CONCURRENCY}")
        if not 0 < self.deadline_s <= DEADLINE_HARD_MAX_S:
            raise ValueError(f"deadline_s must be in (0, {DEADLINE_HARD_MAX_S:g}]")
        if not 0 <= self.report_reserve < 1:
            raise ValueError("report_reserve must be in [0, 1)")
        for name in ("max_retrievals", "max_llm_calls", "max_tokens"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"{name} must be >= 1 or None")
        if min(self.max_rows_per_query, self.max_row_chars, self.plan_max_tokens, self.extract_max_tokens,
               self.report_max_learnings) < 1:
            raise ValueError("row, token and learning caps must be >= 1")

    @classmethod
    def preset(cls, name: str, **overrides: Any) -> Config:
        try:
            breadth, depth = PRESETS[name.strip().lower()]
        except KeyError:
            raise ValueError(f"unknown preset {name!r}; expected one of {sorted(PRESETS)}") from None
        return cls(breadth=breadth, depth=depth, **overrides)

    @property
    def retrieval_limit(self) -> int:
        if self.max_retrievals is not None:
            return self.max_retrievals
        return math.ceil(preset_cost(self.breadth, self.depth)[1] * HEADROOM)

    @property
    def llm_call_limit(self) -> int:
        if self.max_llm_calls is not None:
            return self.max_llm_calls
        plans, _, extracts = preset_cost(self.breadth, self.depth)
        return math.ceil((plans + extracts) * HEADROOM)

    @property
    def token_limit(self) -> int:
        if self.max_tokens is not None:
            return self.max_tokens
        plans, _, extracts = preset_cost(self.breadth, self.depth)
        plan_call = PLAN_PROMPT_TOKENS_EST + self.plan_max_tokens
        extract_call = (EXTRACT_PROMPT_TOKENS_EST + self.max_rows_per_query * (self.max_row_chars // 4 + 16)
                        + self.extract_max_tokens)
        return math.ceil((plans * plan_call + extracts * extract_call) * HEADROOM / (1 - self.report_reserve))

    @property
    def stop_tokens(self) -> int:
        """The engine's share: at or past this estimate no new call starts."""
        return int(round(self.token_limit * (1 - self.report_reserve), 6))


def top_learnings(learnings: Sequence[Learning], n: int) -> list[Learning]:
    """The n learnings citing the most distinct rows (ties: found first), returned in discovery order."""
    keep = sorted(sorted(range(len(learnings)), key=lambda i: (-len(learnings[i].cids), i))[:max(0, n)])
    return [learnings[i] for i in keep]


@dataclass(frozen=True)
class ResearchOutcome:
    learnings: tuple[Learning, ...]
    evidence: dict[str, Row]           # only rows a surviving learning cites, in first-citation order
    seen_rows: int                     # distinct rows retrieved in the run, cited or not
    queries: tuple[QueryRecord, ...]
    stop_reason: str
    levels: int
    retrievals: int
    llm_calls: int
    tokens_est: int
    token_limit: int
    dropped_learnings: int             # no cid, an empty text, or a cid that is not a row of its own call
    parse_repairs: int                 # reply lines read only by the lenient parser
    unparsed_lines: int                # reply lines that matched no format
    empty_retrievals: int              # no rows, or none at or above the score floor: that branch ended
    duplicate_queries: int             # planned queries dropped as near-duplicates of the question or a searched query
    retrieval_errors: int              # the retrieve port raised: that branch ended
    llm_errors: int                    # the complete port raised: that node or branch ended
    errors: tuple[str, ...]            # "stage:ExceptionType", never the message (it may carry source text)
    empty_threads: tuple[str, ...]     # queries the libraries had nothing for
    open_followups: tuple[str, ...]    # new follow-ups never searched (depth or a halt ran out first)
    elapsed_s: float
    today: str
    report_max_learnings: int = 30

    def report_prompt(self, question: str, *, max_learnings: int | None = None) -> tuple[str, str]:
        """(system, prompt) for the report call the route makes: the top learnings by citation coverage, grouped by goal."""
        chosen = top_learnings(self.learnings, self.report_max_learnings if max_learnings is None else max_learnings)
        return P.report_prompt(question, today=self.today, learnings=chosen, empty_threads=self.empty_threads,
                               open_followups=self.open_followups)

    def summary(self) -> dict[str, Any]:
        """The receipt's numbers: counts, the stop reason and every fallback (plan §3, §6)."""
        return {"stop_reason": self.stop_reason, "levels": self.levels, "retrievals": self.retrievals,
                "llm_calls": self.llm_calls, "tokens_est": self.tokens_est, "token_limit": self.token_limit,
                "learnings": len(self.learnings), "cited_rows": len(self.evidence), "seen_rows": self.seen_rows,
                "queries": len(self.queries), "dropped_learnings": self.dropped_learnings, "parse_repairs": self.parse_repairs,
                "unparsed_lines": self.unparsed_lines, "empty_retrievals": self.empty_retrievals,
                "duplicate_queries": self.duplicate_queries, "retrieval_errors": self.retrieval_errors,
                "llm_errors": self.llm_errors, "errors": list(self.errors), "elapsed_s": self.elapsed_s}


def validate_report_citations(report_text: str, outcome: ResearchOutcome) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(valid, unknown) cids a report cites, first appearance first. Valid = a row in `outcome.evidence`."""
    cited = P.cited_ids(report_text)
    return (tuple(c for c in cited if c in outcome.evidence), tuple(c for c in cited if c not in outcome.evidence))


def run_research(question: str, scope: Any, *, retrieve: RetrievePort, complete: CompletePort, config: Config | None = None,
                 on_event: Callable[[dict[str, Any]], None] | None = None,
                 cancel: threading.Event | None = None) -> ResearchOutcome:
    """Run the loop to a stop reason. `on_event` is called from THIS thread only, never from the pool. Setting `cancel` stops
    the run within ~_POLL_S: in-flight port calls are abandoned, not awaited, and the outcome says "cancelled"."""
    return _Run(question, scope, retrieve, complete, config or Config(), on_event, cancel).execute()


# ─────────────────────────────────────────────────────────── internals
def _tokens(text: str) -> frozenset[str]:
    words = re.findall(r"\w+", text.casefold())
    return frozenset(w for w in words if w not in _STOPWORDS) or frozenset(words)


def _near_duplicate(tokens: frozenset[str], seen: Sequence[frozenset[str]]) -> bool:
    return any(len(tokens & s) / (len(tokens | s) or 1) >= NEAR_DUPLICATE for s in seen)


def _child_goal(goal: str, followups: Sequence[str]) -> str:
    head = [goal.strip()] if goal.strip() else []
    return "\n".join(head + ["Follow-up directions:"] + [f"- {f}" for f in followups])


@dataclass(frozen=True)
class _Node:
    id: str
    query: str
    goal: str
    depth: int                # levels left, this one included
    breadth: int
    level: int
    followups: tuple[str, ...] = ()


@dataclass
class _Branch:
    """One planned query and what became of it. Mutated by the scheduler thread only."""
    id: str
    node: _Node
    query: str
    goal: str
    rows: int = 0
    status: str = "unfinished"
    learnings: tuple[P.LearningLine, ...] = ()
    followups: tuple[str, ...] = ()
    done: bool = False


@dataclass
class _Job:
    admit: Callable[[], bool]                                   # scheduler thread: halt checks + counters
    call: Callable[[], Any]                                     # pool thread: exactly one port call, nothing else
    done: Callable[[Any, BaseException | None], _Job | None]    # scheduler thread: may hand back the branch's next job


class _Run:
    def __init__(self, question: str, scope: Any, retrieve: RetrievePort, complete: CompletePort, cfg: Config,
                 on_event: Callable[[dict[str, Any]], None] | None, cancel: threading.Event | None) -> None:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        self.question, self.scope, self.cfg = question.strip(), scope, cfg
        self.retrieve, self.complete, self.on_event, self.cancel = retrieve, complete, on_event, cancel
        self.today = cfg.today or _dt.datetime.now(_dt.UTC).astimezone().date().isoformat()   # the local date
        self.t0 = cfg.clock()
        self.halt: str | None = None
        self.learnings: list[Learning] = []
        self.rows: dict[str, Row] = {}
        self.branches: list[_Branch] = []
        self.searched: list[frozenset[str]] = [_tokens(self.question)]
        self.searched_text: list[str] = []
        self.followups_seen: list[frozenset[str]] = []
        self.open_followups: list[str] = []
        self.errors: dict[str, None] = {}
        self.retrievals = self.llm_calls = self.tokens = self.dropped = self.repairs = self.unparsed = 0
        self.empty = self.duplicates = self.retrieval_errors = self.llm_errors = self.completed = self.seq = 0

    # ── the level loop
    def execute(self) -> ResearchOutcome:
        frontier = [_Node("1", self.question, "", self.cfg.depth, self.cfg.breadth, 1)]
        levels, stop = 0, "frontier_empty"
        pool = ThreadPoolExecutor(max_workers=self.cfg.concurrency, thread_name_prefix="deep-research")
        try:
            while frontier and not self._halted():
                levels += 1
                could_recurse = any(node.depth > 1 for node in frontier)
                frontier, new_followups = self._level(pool, frontier)
                if not frontier and could_recurse and not new_followups:
                    stop = "no_new_followups"
            for node in frontier:                                 # queued, never planned: a halt came first
                self.open_followups.extend(node.followups)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)       # abandoned calls finish in the background, unread
        stop = self.halt or stop
        self._emit("stopped", levels, stop_reason=stop, learnings=len(self.learnings))
        return self._outcome(stop, levels)

    def _level(self, pool: ThreadPoolExecutor, frontier: list[_Node]) -> tuple[list[_Node], int]:
        plans: dict[str, str | None] = {}
        self._drive(pool, deque(self._plan_job(node, plans) for node in frontier))
        branches = [br for node in frontier if node.id in plans for br in self._accept_plan(node, plans[node.id])]
        self._drive(pool, deque(self._retrieve_job(br) for br in branches))
        return self._merge(frontier[0].level, branches)

    # ── the scheduler: port calls on the pool, everything else here
    def _drive(self, pool: ThreadPoolExecutor, jobs: deque[_Job]) -> None:
        pending: dict[Future[Any], tuple[int, _Job]] = {}
        while jobs or pending:
            while jobs and len(pending) < self.cfg.concurrency:
                job = jobs.popleft()
                if not job.admit():
                    jobs.clear()                                  # a halt is final: nothing queued may start
                    break
                self.seq += 1
                pending[pool.submit(job.call)] = (self.seq, job)
            if not pending:
                return
            done, _ = wait(pending, timeout=_POLL_S, return_when=FIRST_COMPLETED)
            if not done:
                if self._hard_stop():
                    return                                        # in-flight calls are abandoned, not awaited
                continue
            for fut in sorted(done, key=lambda f: pending[f][0]):
                _, job = pending.pop(fut)
                exc = fut.exception()
                follow = job.done(None if exc is not None else fut.result(), exc)
                if follow is not None:
                    jobs.appendleft(follow)                       # finish a branch before opening the next one

    def _halted(self) -> str | None:
        if self.halt is None:
            if self.cancel is not None and self.cancel.is_set():
                self.halt = "cancelled"
            elif self.cfg.clock() - self.t0 >= self.cfg.deadline_s:
                self.halt = "deadline"
            elif self.tokens >= self.cfg.stop_tokens:
                self.halt = "budget"
        return self.halt

    def _hard_stop(self) -> bool:
        """Cancel or deadline, checked even after a budget halt: a budget halt lets in-flight calls finish, but none of them
        may outlive the deadline or a cancel. The first halt stays the stop reason."""
        hit = (self.cancel is not None and self.cancel.is_set()) or self.cfg.clock() - self.t0 >= self.cfg.deadline_s
        if hit:
            self._halted()
        return hit

    def _admit_llm(self, system: str, prompt: str) -> bool:
        if self._halted():
            return False
        if self.llm_calls >= self.cfg.llm_call_limit:
            self.halt = "budget"
            return False
        self.llm_calls += 1
        self.tokens += (len(system) + len(prompt)) // 4              # the prompt counts the moment it is sent
        return True

    def _admit_retrieval(self) -> bool:
        if self._halted():
            return False
        if self.retrievals >= self.cfg.retrieval_limit:
            self.halt = "budget"
            return False
        self.retrievals += 1
        return True

    # ── plan
    def _plan_job(self, node: _Node, out: dict[str, str | None]) -> _Job:
        system, prompt = P.plan_prompt(
            self.question, today=self.today, breadth=node.breadth, thread=node.query if node.level > 1 else "",
            goal=node.goal, known=top_learnings(self.learnings, P.PLAN_KNOWN), searched=self.searched_text)

        def done(result: Any, exc: BaseException | None) -> None:
            if exc is not None:
                self.llm_errors += 1
                self._error("plan", exc)
                out[node.id] = None
                return
            reply = self._reply(result)
            self.tokens += len(reply) // 4
            out[node.id] = reply

        return _Job(lambda: self._admit_llm(system, prompt),
                    lambda: self.complete(prompt, system=system, max_tokens=self.cfg.plan_max_tokens), done)

    def _accept_plan(self, node: _Node, reply: str | None) -> list[_Branch]:
        accepted: list[_Branch] = []
        if reply is not None:
            parsed = P.parse_plan(reply)
            self.repairs += parsed.repairs
            self.unparsed += parsed.unparsed
            for item in parsed.items:
                if len(accepted) == node.breadth:
                    break
                tokens = _tokens(item.query)
                if _near_duplicate(tokens, self.searched):
                    self.duplicates += 1
                    continue
                self.searched.append(tokens)
                self.searched_text.append(item.query)
                accepted.append(_Branch(f"{node.id}.{len(accepted) + 1}", node, item.query, item.goal))
        self.branches.extend(accepted)
        self._emit("plan", node.level, node=node.id, query=node.query, queries=[br.query for br in accepted],
                   error=reply is None)
        return accepted

    # ── retrieve → extract
    def _retrieve_job(self, br: _Branch) -> _Job:
        def done(result: Any, exc: BaseException | None) -> _Job | None:
            if exc is not None:
                self.retrieval_errors += 1
                self._error("retrieve", exc)
                self._finish(br, "error", "retrieve")
                return None
            rows = self._rows(result)
            br.rows = len(rows)
            if not any(r.score >= self.cfg.score_floor for r in rows):
                self.empty += 1
                self._finish(br, "empty", "retrieve")
                return None
            self._emit("retrieve", br.node.level, id=br.id, query=br.query, rows=len(rows))
            return self._extract_job(br, rows[: self.cfg.max_rows_per_query])

        return _Job(self._admit_retrieval, lambda: self.retrieve(br.query, self.scope), done)

    def _extract_job(self, br: _Branch, rows: list[Row]) -> _Job:
        allowed = frozenset(r.cid for r in rows)
        system, prompt = P.extract_prompt(self.question, today=self.today, query=br.query, goal=br.goal, rows=rows,
                                          followups=math.ceil(br.node.breadth / 2), max_row_chars=self.cfg.max_row_chars)

        def done(result: Any, exc: BaseException | None) -> None:
            if exc is not None:
                self.llm_errors += 1
                self._error("extract", exc)
                self._finish(br, "error", "extract")
                return
            reply = self._reply(result)
            self.tokens += len(reply) // 4
            parsed = P.parse_extract(reply)
            self.repairs += parsed.repairs
            self.unparsed += parsed.unparsed
            kept: list[P.LearningLine] = []
            for line in parsed.learnings:
                if not line.text or not line.cids or not allowed.issuperset(line.cids):
                    self.dropped += 1                              # uncited, empty, or citing a row this call never saw
                elif len(kept) < LEARNINGS_PER_EXTRACT:
                    kept.append(line)
            br.learnings, br.followups, br.done = tuple(kept), parsed.followups, parsed.done
            self._finish(br, "ok", "extract", new_learnings=len(kept))

        return _Job(lambda: self._admit_llm(system, prompt),
                    lambda: self.complete(prompt, system=system, max_tokens=self.cfg.extract_max_tokens), done)

    def _finish(self, br: _Branch, status: str, stage: str, **fields: Any) -> None:
        br.status = status
        self.completed += 1
        self._emit(stage, br.node.level, id=br.id, query=br.query, rows=br.rows, status=status, **fields)

    # ── merge a finished level, in plan order
    def _merge(self, level: int, branches: list[_Branch]) -> tuple[list[_Node], int]:
        added = new_followups = 0
        children: list[_Node] = []
        halted = self._halted()                                   # "budget remains" is judged once, for the whole level
        for br in branches:
            if br.status != "ok":
                continue
            for line in br.learnings:
                added += self._add_learning(Learning(line.text, line.cids, br.goal, level, br.query))
            width = math.ceil(br.node.breadth / 2)
            fresh: list[str] = []
            for followup in br.followups:
                if len(fresh) == width:
                    break
                tokens = _tokens(followup)
                if _near_duplicate(tokens, self.searched) or _near_duplicate(tokens, self.followups_seen):
                    continue
                self.followups_seen.append(tokens)
                fresh.append(followup)
            if br.node.depth > 1:
                new_followups += len(fresh)
            if fresh and br.node.depth > 1 and not br.done and not halted:
                children.append(_Node(br.id, br.query, _child_goal(br.goal, fresh), br.node.depth - 1, width, level + 1,
                                      tuple(fresh)))
            elif fresh and not br.done:
                self.open_followups.extend(fresh)
        self._emit("level_done", level, new_learnings=added, followups=new_followups, next=len(children))
        return children, new_followups

    def _add_learning(self, new: Learning) -> int:
        key = " ".join(new.text.casefold().split())
        for i, old in enumerate(self.learnings):
            if " ".join(old.text.casefold().split()) == key:              # same finding again: pool the citations
                self.learnings[i] = replace(old, cids=tuple(dict.fromkeys(old.cids + new.cids)))
                return 0
        self.learnings.append(new)
        return 1

    # ── port results: a wrong TYPE is the route's bug and raises; a port that raises is counted and ends its branch
    @staticmethod
    def _reply(result: Any) -> str:
        if not isinstance(result, str):
            raise TypeError(f"complete() must return str, got {type(result).__name__}")
        return result

    def _rows(self, result: Any) -> list[Row]:
        if not isinstance(result, Sequence) or isinstance(result, (str, bytes)):
            raise TypeError(f"retrieve() must return a sequence of Row, got {type(result).__name__}")
        rows: dict[str, Row] = {}
        for row in result:
            if not isinstance(row, Row):
                raise TypeError(f"retrieve() must return Row items, got {type(row).__name__}")
            rows.setdefault(row.cid, row)
            self.rows.setdefault(row.cid, row)
        return list(rows.values())

    def _error(self, stage: str, exc: BaseException) -> None:
        if len(self.errors) < 10:
            self.errors.setdefault(f"{stage}:{type(exc).__name__}", None)

    def _emit(self, stage: str, depth: int, **fields: Any) -> None:
        if self.on_event is not None:
            self.on_event({"stage": stage, "depth": depth, "completed": self.completed,
                           "total": len(self.branches), **fields})

    def _outcome(self, stop: str, levels: int) -> ResearchOutcome:
        evidence: dict[str, Row] = {}
        for learning in self.learnings:
            for cid in learning.cids:
                evidence.setdefault(cid, self.rows[cid])
        queries = tuple(QueryRecord(br.id, br.node.id, br.query, br.goal, br.node.level, br.rows, br.status)
                        for br in self.branches)
        return ResearchOutcome(
            learnings=tuple(self.learnings), evidence=evidence, seen_rows=len(self.rows), queries=queries,
            stop_reason=stop, levels=levels, retrievals=self.retrievals, llm_calls=self.llm_calls, tokens_est=self.tokens,
            token_limit=self.cfg.token_limit, dropped_learnings=self.dropped, parse_repairs=self.repairs,
            unparsed_lines=self.unparsed, empty_retrievals=self.empty, duplicate_queries=self.duplicates,
            retrieval_errors=self.retrieval_errors, llm_errors=self.llm_errors, errors=tuple(self.errors),
            empty_threads=tuple(br.query for br in self.branches if br.status == "empty"),
            open_followups=tuple(self.open_followups),
            elapsed_s=round(self.cfg.clock() - self.t0, 3), today=self.today,
            report_max_learnings=self.cfg.report_max_learnings)
