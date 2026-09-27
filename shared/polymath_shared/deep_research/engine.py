"""DEEP-RESEARCH-MODE-V1 engine (slice DR1): a breadth × depth research loop over the caller's own libraries.
Loop after dzhng/deep-research, MIT; no text copied.

Pure: no I/O, no network, no Polymath imports (moves read the question's intent through the regex classifier, `moves.py`).
Injected ports do the work, so the route (DR2) owns transport, lanes, streaming and receipts, and tests run the whole loop
with fakes:
    retrieve(query, scope) -> [Row]                   evidence retrieval inside the request's libraries
    complete(prompt, *, system, max_tokens) -> str    one budgeted LLM call
    gate(question, [(id, text)]) -> {id: score}       optional, moves only: each planned query's relevance to the question

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
WHY moves (DR6, plan §10): with `Config.moves` every planned query carries a MOVE (broad / deep / adjacent / inverse), the
controller (`moves.py`) sets each plan's quota from the question's intent and what the run found so far, the retrieve port is
told the move (and a deep query's anchor documents) so the route can send it to the search built for it, and an optional gate
drops a planned query that misses the ORIGINAL question before it is searched. The signals read counts merged in plan order,
so they are as deterministic as the rest. With moves off (the default) none of it runs: DR1's prompts, calls and outcome.
"""
from __future__ import annotations

import copy
import datetime as _dt
import math
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from typing import Any, Protocol

from . import moves as M
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
    doc_id: str = ""          # DR6: the row's document ("" = unknown); the concentration signal reads it

    def __post_init__(self) -> None:
        if not isinstance(self.cid, str) or not _CID.fullmatch(self.cid):
            raise ValueError(f"unusable cid {self.cid!r}: 1-200 chars, no whitespace, brackets, quotes, commas or semicolons")
        if not isinstance(self.text, str) or not isinstance(self.source, str):
            raise TypeError("Row.text and Row.source must be str")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError(f"Row.score must be a number, got {type(self.score).__name__}")
        if not isinstance(self.doc_id, str):
            raise TypeError("Row.doc_id must be str")


@dataclass(frozen=True)
class Learning:
    text: str
    cids: tuple[str, ...]
    goal: str                 # the GOAL of the query whose rows produced it (the report groups by it)
    depth: int                # the level that found it: 1 = the question's own queries
    query: str = ""
    move: str = "broad"       # DR6: the move of the search that found it (the report's sections follow it)
    goal_id: str = ""         # the level-1 search whose thread found it ("1.2"; its children's findings share it)
    doc_ids: tuple[str, ...] = ()   # the documents of its cited rows, first citation first (unknown ids left out)


@dataclass(frozen=True)
class QueryRecord:
    id: str                   # "1.2" = the 2nd query planned by node "1"; the child node it spawns takes the same id
    node: str
    query: str
    goal: str
    depth: int
    rows: int = 0
    status: str = "unfinished"   # ok | empty | error | gated (moves: dropped by the gate) | unfinished (cut off by a halt)
    move: str = ""            # DR6: the search's move ("" with moves off)
    goal_id: str = ""         # the level-1 goal its thread belongs to


@dataclass(frozen=True)
class Goal:
    """One level-1 search: a part of the question the run researched. `ResearchOutcome.goals` lists them in plan order,
    whatever became of them (the QueryRecord with the same id says)."""
    id: str                   # the level-1 query id; every query and learning of its thread carries it as `goal_id`
    goal: str
    query: str
    move: str


class RetrievePort(Protocol):
    """Called as `retrieve(query, scope)`; with moves on as `retrieve(query, scope, move=…, anchor_docs=…)`."""
    def __call__(self, query: str, scope: Any, /) -> Sequence[Row]: ...


class CompletePort(Protocol):
    def __call__(self, prompt: str, *, system: str, max_tokens: int) -> str: ...


class GatePort(Protocol):
    """DR6 §10.4: each (id, planned query) scored against the original question, in [0, 1]; an id left out is unscored."""
    def __call__(self, question: str, items: Sequence[tuple[str, str]], /) -> Mapping[str, float]: ...


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
    moves: bool = False                # DR6 research moves (plan §10); False = DR1's engine, byte for byte
    gate_floor: float = 0.2            # moves: a planned query the gate scores under this is dropped before its search
    spawn_floor: float = 0.35          # moves: a query scored under this keeps its learnings but spawns no child

    def __post_init__(self) -> None:
        if not 1 <= self.breadth <= MAX_BREADTH or not 1 <= self.depth <= MAX_DEPTH:
            raise ValueError(f"breadth must be 1..{MAX_BREADTH} and depth 1..{MAX_DEPTH}")
        if not 0 <= self.gate_floor <= 1 or not 0 <= self.spawn_floor <= 1:
            raise ValueError("gate_floor and spawn_floor must be in [0, 1]")
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
    moves: dict[str, Any] | None = None   # DR6: the moves block of the receipt (§10.7); None = moves were off
    goals: tuple[Goal, ...] = ()          # the level-1 searches in plan order: the goals every learning's goal_id names

    def report_prompt(self, question: str, *, max_learnings: int | None = None) -> tuple[str, str]:
        """(system, prompt) for the report call the route makes: the top learnings by citation coverage, grouped by goal
        (with moves: under the three sections of §10.5, first)."""
        chosen = top_learnings(self.learnings, self.report_max_learnings if max_learnings is None else max_learnings)
        if self.moves is None:
            return P.report_prompt(question, today=self.today, learnings=chosen, empty_threads=self.empty_threads,
                                   open_followups=self.open_followups)
        inverse = self.moves["inverse"]
        return P.report_prompt(question, today=self.today, learnings=chosen, empty_threads=self.empty_threads,
                               open_followups=self.open_followups, moves=True, inverse_searched=inverse["searched"],
                               inverse_learnings=inverse["learnings"])

    def summary(self) -> dict[str, Any]:
        """The receipt's numbers: counts, the stop reason and every fallback (plan §3, §6); with moves, the moves block."""
        out = {"stop_reason": self.stop_reason, "levels": self.levels, "retrievals": self.retrievals,
               "llm_calls": self.llm_calls, "tokens_est": self.tokens_est, "token_limit": self.token_limit,
               "learnings": len(self.learnings), "cited_rows": len(self.evidence), "seen_rows": self.seen_rows,
               "queries": len(self.queries), "dropped_learnings": self.dropped_learnings, "parse_repairs": self.parse_repairs,
               "unparsed_lines": self.unparsed_lines, "empty_retrievals": self.empty_retrievals,
               "duplicate_queries": self.duplicate_queries, "retrieval_errors": self.retrieval_errors,
               "llm_errors": self.llm_errors, "errors": list(self.errors), "elapsed_s": self.elapsed_s}
        if self.moves is not None:
            out["moves"] = copy.deepcopy(self.moves)
        return out


def validate_report_citations(report_text: str, outcome: ResearchOutcome) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(valid, unknown) cids a report cites, first appearance first. Valid = a row in `outcome.evidence`."""
    cited = P.cited_ids(report_text)
    return (tuple(c for c in cited if c in outcome.evidence), tuple(c for c in cited if c not in outcome.evidence))


def run_research(question: str, scope: Any, *, retrieve: RetrievePort, complete: CompletePort, config: Config | None = None,
                 on_event: Callable[[dict[str, Any]], None] | None = None,
                 cancel: threading.Event | None = None, gate: GatePort | None = None) -> ResearchOutcome:
    """Run the loop to a stop reason. `on_event` is called from THIS thread only, never from the pool. Setting `cancel` stops
    the run within ~_POLL_S: in-flight port calls are abandoned, not awaited, and the outcome says "cancelled". `gate` is
    read only with `config.moves` (None = no relevance gate)."""
    return _Run(question, scope, retrieve, complete, config or Config(), on_event, cancel, gate).execute()


# ─────────────────────────────────────────────────────────── internals
def _tokens(text: str) -> frozenset[str]:
    words = re.findall(r"\w+", text.casefold())
    return frozenset(w for w in words if w not in _STOPWORDS) or frozenset(words)


def _near_duplicate(tokens: frozenset[str], seen: Sequence[frozenset[str]]) -> bool:
    return any(len(tokens & s) / (len(tokens | s) or 1) >= NEAR_DUPLICATE for s in seen)


_FOLLOWUP_HEAD = "Follow-up directions:"


def _child_goal(goal: str, followups: Sequence[str]) -> str:
    head = [goal.strip()] if goal.strip() else []
    return "\n".join(head + [_FOLLOWUP_HEAD] + [f"- {f}" for f in followups])


@dataclass(frozen=True)
class _Node:
    id: str
    query: str
    goal: str
    depth: int                # levels left, this one included
    breadth: int
    level: int
    followups: tuple[str, ...] = ()
    goal_id: str = ""                     # the level-1 goal this thread belongs to ("" at the root)
    # ── moves only (DR6)
    quota: tuple[int, ...] = ()           # the controller's mix, in MOVES order; sums to breadth
    anchors: tuple[str, ...] = ()         # the documents this node's deep queries search inside (concentration)
    findings: tuple[str, ...] = ()        # the parent's learnings: an inverse query must share a term with them or the thread
    learned: int = 0                      # the parent's learning count (the richest thread gets the one-sided inverse slot)
    gap: bool = False                     # a gap node: one broad reformulation of a level-1 search that found nothing


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
    goal_id: str = ""                     # its own id at level 1; its node's goal below
    move: str = ""                        # moves: what kind of search it is
    cids: tuple[str, ...] = ()            # the rows its search returned (the repeat signal reads them)
    drift: bool = False                   # moves: scored under the spawn floor, so its thread ends with it


@dataclass
class _Job:
    admit: Callable[[], bool]                                   # scheduler thread: halt checks + counters
    call: Callable[[], Any]                                     # pool thread: exactly one port call, nothing else
    done: Callable[[Any, BaseException | None], _Job | None]    # scheduler thread: may hand back the branch's next job


class _Run:
    def __init__(self, question: str, scope: Any, retrieve: RetrievePort, complete: CompletePort, cfg: Config,
                 on_event: Callable[[dict[str, Any]], None] | None, cancel: threading.Event | None,
                 gate: GatePort | None = None) -> None:
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
        # ── moves (DR6): read only when cfg.moves
        self.moves, self.gate = cfg.moves, gate
        self.intent = M.question_intent(self.question) if self.moves else ""
        self.evaluative = M.is_evaluative(self.question) if self.moves else False
        self.level_stats: list[dict[str, Any]] = []       # per level: asked / planned / searched / learnings, per move
        self.seen_cids: set[str] = set()                  # rows of the levels merged so far, in plan order (repeat)
        self.dry_strikes = dict.fromkeys(M.MOVES, 0)
        self.dry: set[str] = set()
        self.signals = dict.fromkeys(("repeat", "concentration", "one_sided"), 0)
        self.gate_scored = self.gate_dropped = self.gate_failed_open = self.drift_stopped = self.gap_nodes = 0
        self.inverse_unanchored = self.deep_anchored = self.deep_unanchored = 0

    # ── the level loop
    def execute(self) -> ResearchOutcome:
        root = _Node("1", self.question, "", self.cfg.depth, self.cfg.breadth, 1)
        if self.moves:
            root = replace(root, quota=M.root_quota(self.intent, root.breadth, evaluative=self.evaluative))
        frontier = [root]
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
        if self.moves:
            self._open_level(frontier)
        self._drive(pool, deque(self._plan_job(node, plans) for node in frontier))
        branches = [br for node in frontier if node.id in plans for br in self._accept_plan(node, plans[node.id])]
        if self.moves and self.gate is not None and branches:
            self._drive(pool, deque([self._gate_job(frontier[0].level, branches)]))
        self._drive(pool, deque(self._retrieve_job(br) for br in branches if br.status != "gated"))
        return self._merge(frontier[0].level, branches)

    def _open_level(self, frontier: list[_Node]) -> None:
        zero = dict.fromkeys(M.MOVES, 0)
        asked = dict(zero)
        for node in frontier:
            for move, n in zip(M.MOVES, node.quota):
                asked[move] += n
        self.level_stats.append({"level": frontier[0].level, "asked": asked, "planned": dict(zero),
                                 "searched": dict(zero), "learnings": dict(zero)})

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
            goal=node.goal, known=top_learnings(self.learnings, P.PLAN_KNOWN), searched=self.searched_text,
            moves=list(zip(M.MOVES, node.quota)) if self.moves else None, gap=node.gap)

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
        if self.moves:
            return self._accept_moves(node, reply)
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
                bid = f"{node.id}.{len(accepted) + 1}"
                accepted.append(_Branch(bid, node, item.query, item.goal, goal_id=node.goal_id or bid))
        self.branches.extend(accepted)
        self._emit("plan", node.level, node=node.id, query=node.query, queries=[br.query for br in accepted],
                   error=reply is None)
        return accepted

    def _accept_moves(self, node: _Node, reply: str | None) -> list[_Branch]:
        """§10.2: each move up to its quota, in plan order; slots left empty are then filled by the remaining queries in
        order, so a level never runs under its breadth because the model ignored the quota. A near-duplicate, or an inverse
        query that shares no content term with its thread, is dropped and counted where it would have taken a slot."""
        accepted: list[_Branch] = []
        if reply is not None:
            parsed = P.parse_plan(reply, moves=True)
            self.repairs += parsed.repairs
            self.unparsed += parsed.unparsed
            open_slots = dict(zip(M.MOVES, node.quota))
            default = M.BROAD if node.gap else M.default_move(node.level)   # a gap node asks for one broad query
            anchor = self._anchor_terms(node)
            later: list[tuple[P.PlanItem, str]] = []
            for item in parsed.items:
                move = item.move or default
                if open_slots.get(move, 0) > 0:
                    if self._take_query(node, item, move, anchor, accepted):
                        open_slots[move] -= 1
                else:
                    later.append((item, move))
            for item, move in later:
                if len(accepted) == node.breadth:
                    break
                self._take_query(node, item, move, anchor, accepted)
        self.branches.extend(accepted)
        planned = self.level_stats[-1]["planned"]
        for br in accepted:
            planned[br.move] += 1
        self._emit("plan", node.level, node=node.id, query=node.query, queries=[br.query for br in accepted],
                   moves=[br.move for br in accepted], error=reply is None)
        return accepted

    def _take_query(self, node: _Node, item: P.PlanItem, move: str, anchor: frozenset[str],
                    accepted: list[_Branch]) -> bool:
        tokens = _tokens(item.query)
        if _near_duplicate(tokens, self.searched):
            self.duplicates += 1
            return False
        if move == M.INVERSE and not tokens & anchor:
            self.inverse_unanchored += 1          # "criticisms of psychology": it tests nothing this thread holds
            return False
        self.searched.append(tokens)
        self.searched_text.append(item.query)
        bid = f"{node.id}.{len(accepted) + 1}"
        accepted.append(_Branch(bid, node, item.query, item.goal, goal_id=node.goal_id or bid, move=move))
        return True

    @staticmethod
    def _anchor_terms(node: _Node) -> frozenset[str]:
        """What an inverse query must share a content term with: its thread (the question itself at level 1), the thread's
        goal and the parent's findings. The query's own GOAL line does not count: restating the query there passes anything."""
        terms = set(_tokens(node.query)) | set(_tokens(node.goal.replace(_FOLLOWUP_HEAD, " ")))
        for finding in node.findings:
            terms |= _tokens(finding)
        return frozenset(terms)

    # ── the relevance gate (moves)
    def _gate_job(self, level: int, branches: list[_Branch]) -> _Job:
        """§10.4: one call per level, before any of its searches: every planned query against the ORIGINAL question. Under
        `gate_floor` = dropped, never searched; under `spawn_floor` = searched, learnings kept, no child (no drift chains).
        A gate that raises, or a query it leaves unscored, keeps the query (fail-open) and is counted."""
        items = [(br.id, br.query) for br in branches]

        def done(result: Any, exc: BaseException | None) -> None:
            if exc is not None:
                self._error("gate", exc)
                self.gate_failed_open += len(branches)
                self._emit("gate", level, scored=0, dropped=0, failed_open=len(branches))
                return
            if not isinstance(result, Mapping):
                raise TypeError(f"gate() must return a mapping of id to score, got {type(result).__name__}")
            scored = dropped = unscored = 0
            for br in branches:
                score = result.get(br.id)
                if score is None:
                    unscored += 1
                    continue
                if isinstance(score, bool) or not isinstance(score, (int, float)):
                    raise TypeError(f"gate() scores must be numbers, got {type(score).__name__}")
                scored += 1
                if score < self.cfg.gate_floor:
                    dropped += 1
                    br.status = "gated"
                    self.completed += 1
                elif score < self.cfg.spawn_floor:
                    br.drift = True
            self.gate_scored += scored
            self.gate_dropped += dropped
            self.gate_failed_open += unscored
            self._emit("gate", level, scored=scored, dropped=dropped, failed_open=unscored)

        return _Job(lambda: not self._halted(), lambda: self.gate(self.question, items), done)

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
            br.cids = tuple(r.cid for r in rows)
            if not any(r.score >= self.cfg.score_floor for r in rows):
                self.empty += 1
                self._finish(br, "empty", "retrieve")
                return None
            self._emit("retrieve", br.node.level, id=br.id, query=br.query, rows=len(rows), **self._move_field(br))
            return self._extract_job(br, rows[: self.cfg.max_rows_per_query])

        if not self.moves:
            return _Job(self._admit_retrieval, lambda: self.retrieve(br.query, self.scope), done)
        anchors = br.node.anchors if br.move == M.DEEP else ()
        return _Job(lambda: self._admit_search(br, anchors),
                    lambda: self.retrieve(br.query, self.scope, move=br.move, anchor_docs=anchors), done)

    def _admit_search(self, br: _Branch, anchors: tuple[str, ...]) -> bool:
        if not self._admit_retrieval():
            return False
        self.level_stats[-1]["searched"][br.move] += 1
        if br.move == M.DEEP:
            if anchors:
                self.deep_anchored += 1
            else:
                self.deep_unanchored += 1
        return True

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
        self._emit(stage, br.node.level, id=br.id, query=br.query, rows=br.rows, status=status, **self._move_field(br),
                   **fields)

    def _move_field(self, br: _Branch) -> dict[str, str]:
        return {"move": br.move} if self.moves else {}

    # ── merge a finished level, in plan order
    def _merge(self, level: int, branches: list[_Branch]) -> tuple[list[_Node], int]:
        if self.moves:
            return self._merge_moves(level, branches)
        added = new_followups = 0
        children: list[_Node] = []
        halted = self._halted()                                   # "budget remains" is judged once, for the whole level
        for br in branches:
            if br.status != "ok":
                continue
            for line in br.learnings:
                added += self._add_learning(Learning(line.text, line.cids, br.goal, level, br.query, goal_id=br.goal_id))
            width = math.ceil(br.node.breadth / 2)
            fresh = self._fresh_followups(br, width)
            if br.node.depth > 1:
                new_followups += len(fresh)
            if fresh and br.node.depth > 1 and not br.done and not halted:
                children.append(_Node(br.id, br.query, _child_goal(br.goal, fresh), br.node.depth - 1, width, level + 1,
                                      tuple(fresh), goal_id=br.goal_id))
            elif fresh and not br.done:
                self.open_followups.extend(fresh)
        self._emit("level_done", level, new_learnings=added, followups=new_followups, next=len(children))
        return children, new_followups

    def _fresh_followups(self, br: _Branch, width: int) -> list[str]:
        """≤ width of the branch's follow-ups that are not near-duplicates of a searched query or an earlier follow-up."""
        fresh: list[str] = []
        for followup in br.followups:
            if len(fresh) == width:
                break
            tokens = _tokens(followup)
            if _near_duplicate(tokens, self.searched) or _near_duplicate(tokens, self.followups_seen):
                continue
            self.followups_seen.append(tokens)
            fresh.append(followup)
        return fresh

    def _merge_moves(self, level: int, branches: list[_Branch]) -> tuple[list[_Node], int]:
        """`_merge` with moves (§10.3): learnings keep their move; a child's mix comes from the controller (its parent's move,
        then the repeat / concentration / one-sided signals, dry moves at 0); a thread under the spawn floor spawns nothing;
        a level-1 thread that found nothing gets one broad reformulation while the run's budget allows it (a gap node)."""
        added = new_followups = 0
        stats = self.level_stats[-1]
        halted = self._halted()                                   # "budget remains" is judged once, for the whole level
        spawn: list[tuple[int, _Branch, list[str], bool]] = []
        gaps: list[tuple[int, _Branch]] = []
        for i, br in enumerate(branches):
            repeat = M.is_repeat(br.cids, self.seen_cids)        # judged in plan order: timing never changes it
            self.seen_cids.update(br.cids)
            spawned = False
            if br.status == "ok":
                for line in br.learnings:
                    new = self._add_learning(Learning(line.text, line.cids, br.goal, level, br.query, br.move,
                                                      goal_id=br.goal_id))
                    added += new
                    stats["learnings"][br.move] += new
                fresh = self._fresh_followups(br, math.ceil(br.node.breadth / 2))
                if br.node.depth > 1:
                    new_followups += len(fresh)
                if fresh and br.node.depth > 1 and not br.done and not halted:
                    if br.drift:
                        self.drift_stopped += 1                   # off the question: its learnings stay, its thread ends
                    else:
                        spawn.append((i, br, fresh, repeat))
                        spawned = True
                elif fresh and not br.done:
                    self.open_followups.extend(fresh)
            found_nothing = br.status == "empty" or (br.status == "ok" and not br.learnings)
            if level == 1 and found_nothing and not spawned and not br.drift and br.node.depth > 1 and not halted:
                gaps.append((i, br))
        self._dry_after(stats)
        children = self._inverse_slot([(i, self._child(br, fresh, level, repeat)) for i, br, fresh, repeat in spawn])
        for i, br in gaps:
            if self._affordable([node for _, node in children]):
                children.append((i, _Node(br.id, br.query, br.goal, br.node.depth - 1, 1, level + 1,
                                          goal_id=br.goal_id, quota=(1, 0, 0, 0), gap=True)))   # one broad query
                self.gap_nodes += 1
        nodes = [node for _, node in sorted(children, key=lambda c: c[0])]
        self._emit("level_done", level, new_learnings=added, followups=new_followups, next=len(nodes))
        return nodes, new_followups

    def _child(self, br: _Branch, fresh: list[str], level: int, repeat: bool) -> _Node:
        width = math.ceil(br.node.breadth / 2)
        quota = M.child_quota(br.move, width, repeat=repeat, dry=self.dry)
        if quota != M.child_quota(br.move, width, repeat=False, dry=self.dry):
            self.signals["repeat"] += 1
        anchors = M.concentration_anchors([self.rows[c].doc_id for line in br.learnings for c in line.cids])
        if anchors:
            self.signals["concentration"] += 1
        return _Node(br.id, br.query, _child_goal(br.goal, fresh), br.node.depth - 1, width, level + 1, tuple(fresh),
                     goal_id=br.goal_id, quota=quota, anchors=anchors, findings=tuple(line.text for line in br.learnings),
                     learned=len(br.learnings))

    def _inverse_slot(self, children: list[tuple[int, _Node]]) -> list[tuple[int, _Node]]:
        """One inverse slot on the next level when the run is one-sided so far, or the question is evaluative and no child
        has one (the reserve): the child whose parent found the most gets it (ties: plan order). Not once inverse is dry."""
        if not children or M.INVERSE in self.dry:
            return children
        inverse = M.MOVES.index(M.INVERSE)
        k = max(range(len(children)), key=lambda j: (children[j][1].learned, -j))
        i, target = children[k]
        if not target.quota[inverse] and M.is_one_sided(self.intent, self.evaluative, [ln.move for ln in self.learnings]):
            target = replace(target, quota=M.with_inverse(target.quota))
            self.signals["one_sided"] += 1
        elif self.evaluative and not any(node.quota[inverse] for _, node in children):
            target = replace(target, quota=M.with_inverse(target.quota))
        children[k] = (i, target)
        return children

    def _dry_after(self, stats: dict[str, Any]) -> None:
        for move in M.MOVES:
            if stats["searched"][move] and not stats["learnings"][move]:
                self.dry_strikes[move] += 1
                if self.dry_strikes[move] >= M.DRY_LEVELS:
                    self.dry.add(move)

    def _affordable(self, queued: list[_Node]) -> bool:
        """A gap node (one plan, one search, one extract) fits the run's call and retrieval limits beside everything already
        queued for the next level, each queued node planning once and searching at most its breadth."""
        width = sum(node.breadth for node in queued)
        return (self.retrievals + width + 1 <= self.cfg.retrieval_limit
                and self.llm_calls + len(queued) + width + 2 <= self.cfg.llm_call_limit)

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
        queries = tuple(QueryRecord(br.id, br.node.id, br.query, br.goal, br.node.level, br.rows, br.status, br.move,
                                    br.goal_id) for br in self.branches)
        # each learning names the documents it cites (DR7 reads them; pooled citations included), and the goals list the
        # level-1 searches in plan order
        learnings = tuple(replace(ln, doc_ids=tuple(dict.fromkeys(d for c in ln.cids if (d := self.rows[c].doc_id))))
                          for ln in self.learnings)
        goals = tuple(Goal(br.id, br.goal, br.query, br.move or M.BROAD) for br in self.branches if br.node.level == 1)
        moves = None
        if self.moves:                                            # the receipt's moves block (§10.7)
            moves = {
                "intent": self.intent, "evaluative": self.evaluative, "levels": copy.deepcopy(self.level_stats),
                "gate": None if self.gate is None else {"scored": self.gate_scored, "dropped": self.gate_dropped,
                                                        "failed_open": self.gate_failed_open},
                "drift_stopped": self.drift_stopped, "gap_nodes": self.gap_nodes,
                "dry_moves": [m for m in M.MOVES if m in self.dry], "inverse_unanchored": self.inverse_unanchored,
                "deep": {"anchored": self.deep_anchored, "unanchored": self.deep_unanchored},
                "inverse": {"searched": sum(s["searched"][M.INVERSE] for s in self.level_stats),
                            "learnings": sum(1 for ln in self.learnings if ln.move == M.INVERSE)},
                "signals": dict(self.signals)}
        return ResearchOutcome(
            learnings=learnings, evidence=evidence, seen_rows=len(self.rows), queries=queries,
            stop_reason=stop, levels=levels, retrievals=self.retrievals, llm_calls=self.llm_calls, tokens_est=self.tokens,
            token_limit=self.cfg.token_limit, dropped_learnings=self.dropped, parse_repairs=self.repairs,
            unparsed_lines=self.unparsed, empty_retrievals=self.empty, duplicate_queries=self.duplicates,
            retrieval_errors=self.retrieval_errors, llm_errors=self.llm_errors, errors=tuple(self.errors),
            empty_threads=tuple(br.query for br in self.branches if br.status == "empty"),
            open_followups=tuple(self.open_followups),
            elapsed_s=round(self.cfg.clock() - self.t0, 3), today=self.today,
            report_max_learnings=self.cfg.report_max_learnings, moves=moves, goals=goals)
