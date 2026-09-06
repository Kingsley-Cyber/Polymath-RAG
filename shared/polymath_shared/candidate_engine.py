"""CANDIDATE-RETRIEVAL-V1 — the CHAT-RETRIEVAL-V2 candidate engine
(CHAT-QUERY-COMPILER-PLAN §3.14, §3.21, §3.22; phase P1.a).

Three independent experts, fused at the CHILD level with full provenance;
no lane is an authority over another:

    LANE A  HIERARCHICAL_ROUTE   doc summaries → documents → section
                                 summaries → children (context, breadth)
    LANE B  GLOBAL_DENSE_CHILD   every child, dense, no document prerequisite
    LANE C  GLOBAL_SPARSE_CHILD  every child, BM25 sparse, no document
                                 prerequisite (exact terms)

    UNION + DEDUPE (provenance kept) → one cross-encoder rerank over a
    bounded prefix → final evidence.

Pure given the injected search callables (no Qdrant, no Postgres here):

    dense_search(kind, top_k, extra_filters) -> [{payload, score}]  (desc)
    sparse_search(top_k)                    -> [{payload, score}]  (desc), raises when unavailable
    region_lookup(chunk_ids)                -> {chunk_id: region_role}

Seams the plan closes here (§3.21): #1 sparse runs ONCE (lane C; the
adapter is built without the routing companion probe); #2 no Postgres
lexical fallback — an unavailable sparse lane is DEGRADED, dense lanes
continue; #3 no plan copy — one `CandidateBudget` is consumed directly;
#4 one budget authority; #14 the query shape is read from the RESOLVED
request (`shape_budget`). Rescue caps do not exist: B and C are lanes.
`hybrid-retrieval-v1` / `pass1-retrieval-v2` are untouched for /retrieve,
/ask and TRAIL.

P1.d — CONCURRENCY-DEADLINES-V1 (§3.16): the lanes are concurrent tasks on a
bounded pool under ONE wall-clock budget (`lane_deadline_s`); a lane past
its deadline is dropped with a `<lane>_timeout` receipt in `degraded` and
the turn completes on the others; results are collected by lane NAME and
fused in the fixed lane order, so the union never depends on completion
order (no deadline hit ⇒ byte-identical to the sequential engine). Lane C
may be handed in pre-started (BM25 needs no embedding). The judge's
deadline lives in the route (one rerank call per turn, `rerank_deadline_s`).
"""
from __future__ import annotations

import re
import time
from collections import Counter
from concurrent.futures import CancelledError, Executor, Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Iterable, Optional

from polymath_shared.pass1 import (
    REPRESENTATION_KIND_CHILD,
    REPRESENTATION_KIND_DOCUMENT_SUMMARY,
    REPRESENTATION_KIND_ENTITY_CARD,
    REPRESENTATION_KIND_SECTION_SUMMARY,
    DocumentCandidate,
    LaneHit,
    _rrf_score,
    aggregate_documents_n,
    resolve_sections,
)
from polymath_shared.query_shape import is_document_metadata_query, is_enumeration_query

CANDIDATE_ENGINE_VERSION = "candidate-retrieval-v1"
CHAT_RETRIEVAL_PLAN_VERSION = "chat-retrieval-v2"
CONCURRENCY_CONTRACT = "concurrency-deadlines-v1"    # P1.d: concurrent lanes + wall-clock budgets + one judge

LANE_A = "HIERARCHICAL_ROUTE"
LANE_B = "GLOBAL_DENSE_CHILD"
LANE_C = "GLOBAL_SPARSE_CHILD"
ARRIVAL_NEIGHBOR = "NEIGHBOR_EXPANSION"
LANES = (LANE_A, LANE_B, LANE_C)


@dataclass(frozen=True)
class CandidateBudget:
    """ONE budget authority for chat retrieval (§3.8, §3.21 #4). Modes
    override only what they genuinely need (P1.e)."""
    hierarchy_doc_k: int = 16
    hierarchy_section_k: int = 24
    hierarchy_child_k: int = 3              # children deepened per section
    hierarchy_max_documents: int = 6
    hierarchy_max_sections_per_document: int = 2
    entity_card_k: int = 8                  # routing votes only (never evidence)
    entity_card_max_docs_per_card: int = 4
    global_dense_k: int = 50
    global_sparse_k: int = 40
    merged_candidate_max: int = 120
    #: MEASURED 2026-09-05: the reranker sidecar scores ~4 pairs/s on this
    #: machine (10 → 2.4 s, 30 → 7.6 s, 100 → 24 s), so the whole union
    #: cannot be judged per turn yet (§3.8 "until the sidecar cap is
    #: raised"). The rerank prefix is fusion order; the funnel shows what
    #: it costs (LOST_AT_RERANK vs LOST_AT_UNION_TRUNCATION).
    #: P1.c (measured 2026-09-06 on the frozen-plan B replay, composer on): at 20 judged pairs survival-given-union
    #: was 22/27 = 0.815 with four gold chunks sitting at union ranks 21/21/27/38, never judged. 24 seats the two
    #: rank-21 golds (23/27 = 0.852, gate ≥ 0.85; MRR 0.578) for +0.9 s rerank p50; 28 adds the rank-27 gold
    #: (24/27 = 0.889, MRR 0.594) for another +1.7 s p50 under contention (+1.0 s fresh) — recorded, not taken:
    #: the plan's rerank budget is 3 s and P1.d makes the judged prefix deadline-aware (28 = its ceiling candidate).
    rerank_max: int = 24
    #: EVIDENCE-DIET-V1 step 3 (backlog B11, measured 2026-09-06): the judged prefix was the top of the fusion
    #: order, and the three largest matchers took 88 of 104–148 union slots per turn — a six-candidate book never
    #: reached the judge. The prefix is now filled document-fairly: round 1 seats every surfaced document's best
    #: candidate (document order = first appearance in the fusion order), then the fusion order continues under a
    #: per-document cap, then any remaining seats fill in fusion order ignoring the cap (seats are never left
    #: empty). Relevance — the judge — still decides survival; the receipt names how many documents were judged
    #: and how many candidates the cap deferred (`judged_docs`, `capped_out`, `prefix_policy`).
    rerank_round_robin: bool = True
    rerank_doc_cap: int = 8
    #: B11 step 3 re-measure (2026-09-06): with 24 seats the round-robin first pass (9–13 surfaced documents) displaced
    #: the dominant documents' 2nd–8th candidates and cost recall (B hit@10 0.667 → 0.600, survival 0.852 → 0.778;
    #: L hit@10 1.0 → 0.9 with fewer degraded turns). The backlog row named 32 seats on the fast judge as the
    #: re-measure; the judge at fp16 / 384 tokens scores 32 pairs in one batched call.
    rerank_max_fair: int = 32
    synthesis_max: int = 15
    rrf_k: int = 60
    neighbor_expansion: int = 0
    neighbor_expansion_max: int = 8
    demote_noisy_regions: bool = True
    lanes: tuple[str, ...] = LANES
    #: P1.b decomposition (§3.10, §3.16): typed subqueries run lanes B + C only,
    #: with smaller K; document routing (lane A) happens once, on the primary.
    subquery_dense_k: int = 20
    subquery_sparse_k: int = 15
    max_subqueries: int = 3
    #: one targeted second pass for the weakest aspect (0 candidates): B + C
    #: again at K × factor; at most one per turn
    second_pass_factor: int = 2
    #: provenance-normalised fusion: a chunk's score is its BEST per-query
    #: contribution plus a bounded agreement term — N redundant subqueries
    #: can at most double it, never pile up linearly
    agreement_bonus: float = 0.5
    #: ASPECT SEATS (P1.b gate "every dimension ✓ or flagged weak"): every
    #: typed subquery gets at least this many of its own candidates into the
    #: judged prefix (the prefix may grow by seats × subqueries), an aspect
    #: whose best judged candidate scores below the floor (sigmoid of the
    #: judge logit) is WEAK and named as such, and every non-weak aspect not
    #: yet represented in the final set gets one seat (its best judged
    #: candidate) in place of the lowest primary-only item.
    #: R1 (2026-09-06): the PRIMARY is judged by the same floor — when every primary candidate is
    #: below it, q0 is flagged `below_floor` too (the P1.b residual: a compare side named only by the
    #: primary was shown as covered while the judge had rejected all of its evidence).
    aspect_prefix_seats: int = 3
    aspect_weak_floor: float = 0.5
    aspect_final_seats: int = 1
    #: P1.c EVIDENCE COMPOSER (§3.17): deterministic, metadata only. Slots
    #: over the judged prefix: pure relevance → source diversity (soft max
    #: per document unless the score gap to the best unrepresented document
    #: is large) → sparse winners (lane C arrivals) → aspect coverage (one
    #: seat per non-weak compiled query not yet represented) → fill. Scores
    #: are compared on a sigmoid of the raw judge logit so "gap 0.1" means
    #: the same thing on every reranker model.
    compose_relevance_slots: int = 8
    compose_diversity_slots: int = 4
    compose_doc_soft_max: int = 3
    compose_sparse_slots: int = 3
    compose_aspect_slots: int = 3
    compose_score_gap: float = 0.1
    #: dominance guard (P1.c gate): max share of the final set one document may fill when ≥ 3 documents are within the gap
    compose_dominance_share: float = 0.6
    #: bounded multi-lane agreement: +boost per extra lane, capped, applied to
    #: the sigmoid score for ORDERING inside composition only — never enough
    #: to pass a candidate with a clearly higher judge score (§5 #10c)
    compose_agreement_boost: float = 0.02
    compose_agreement_cap: float = 0.05
    #: P1.d CONCURRENCY-DEADLINES-V1 (§3.16 "wall-clock budgets, not only K"; starting budgets to benchmark).
    #: `embed_deadline_s`: the ONE embedding call's budget — a hard dependency (no vector, no dense lane), so the
    #: route waits past it and RECEIPTS the breach (`embed_deadline`), it never drops the stage.
    #: `lane_deadline_s`: the core lanes' budget, measured from engine entry over the T=0 lanes, the hierarchical
    #: deepening and the second pass together; a lane still pending at the deadline is dropped and receipted
    #: `<lane>_timeout` (its late result is ignored), the turn completes on the other lanes.
    #: `rerank_deadline_s`: the judge's budget; past it the turn proceeds in fusion order (`rerank_timeout`).
    #: `max_workers`: the bounded per-turn pool the lanes share (≤ 5 primary + 2 × subqueries + ≤ 12 deepening tasks).
    embed_deadline_s: float = 2.5
    lane_deadline_s: float = 3.0
    #: BENCHMARKED 2026-09-06 (P1.d arm 1, frozen-plan B, 24 judged pairs): the §3.16 starting value of 3.0 s is below this
    #: reranker's physical floor (~240 ms/pair fresh → 5.8 s for 24 pairs; 27–52 s under enrichment thrash) and timed the
    #: judge out on 30/30 turns, silently turning composition into fusion order (MRR 0.578 → 0.562). 8.0 s admits the
    #: normal fresh case with margin and still catches the thrash case; the Metal lease removes the thrash, not the per-pair cost.
    rerank_deadline_s: float = 8.0
    max_workers: int = 8
    #: P1.e MODE-COMPOSITION-V1 (§3.16 "graph / wildcard (bounded optional)", §3.19): the WILDCARD frontier's
    #: budget for the work that EXTENDS the turn beyond the core result — joining the latent sweep (which ran
    #: beside the lanes from the embedding on) plus baseline exclusion and two-hop validation. Past it the turn
    #: answers with the core evidence and an empty `wildcard` lane, receipted `wildcard_timeout` (the late
    #: frontier is not awaited). Starting budget from the plan; the route reads POLYMATH_CHAT_WILDCARD_DEADLINE_S.
    wildcard_deadline_s: float = 2.5

    def to_dict(self) -> dict:
        d = asdict(self)
        d["lanes"] = list(self.lanes)
        return d


def shape_budget(resolved_request: str, budget: CandidateBudget) -> CandidateBudget:
    """QUERY-SHAPE on the RESOLVED request (§3.21 #14): depth profile for
    completeness questions, region demotion lifted for document-metadata
    questions. Deterministic; same predicates as `query_shape`."""
    out = budget
    if is_enumeration_query(resolved_request):
        out = replace(out, hierarchy_section_k=max(out.hierarchy_section_k, 32),
                      hierarchy_max_sections_per_document=max(out.hierarchy_max_sections_per_document, 8),
                      hierarchy_child_k=max(out.hierarchy_child_k, 4),
                      global_dense_k=max(out.global_dense_k, 60),
                      rerank_max=max(out.rerank_max, 28), synthesis_max=max(out.synthesis_max, 28),
                      neighbor_expansion=max(out.neighbor_expansion, 1))
    if is_document_metadata_query(resolved_request):
        out = replace(out, demote_noisy_regions=False)
    return out


#: Query-side only (the BM25 projection is frozen, §3.23). The collection
#: applies an IDF modifier to the query, but the stored values are RAW term
#: frequencies (no BM25 k1/b saturation), so a chunk repeating common query
#: tokens ("animation" ×8, "style" ×12) still outscores one rare identifier.
#: MEASURED 2026-09-05 (fixture L, "UPA"): bare token → gold rank 1; the
#: compiler's "UPA animation studio history style" → gold outside the top
#: 200. Lane C therefore searches the EXACT TERMS ALONE when the plan has
#: any (that is its job: what the user literally said), and otherwise the
#: topical text with function words stripped.
_SPARSE_STOPWORDS = frozenset("""a an and are as at be been but by can could did do does for from had has have he her
his how i if in into is it its of on or our she so than that the their them then there these they this to
was we were what when where which who why will with would you your about above after again all also am any
because before being below between both down during each few further here more most not now off once only other
out over own same should some such through too under until up very while""".split())


def sparse_query_for(text: str, exact_terms: Iterable[str] | None = None) -> tuple[list[str], str]:
    """Tokens lane C searches, and which rule chose them ("exact_terms" |
    "topical" | "raw"). Pure; deterministic."""
    from polymath_shared.sparse_bm25 import tokenize
    exact = [t for t in (exact_terms or []) if str(t).strip()]
    if exact:
        toks = tokenize(" ".join(str(t) for t in exact))
        if toks:
            return toks, "exact_terms"
    toks = [t for t in tokenize(text) if t not in _SPARSE_STOPWORDS]
    if toks:
        return toks, "topical"
    return tokenize(text), "raw"


def sparse_vector_for(text: str, exact_terms: Iterable[str] | None = None) -> tuple[Optional[tuple[tuple[int, ...], tuple[float, ...]]], str]:
    """(indices, values) for lane C from `sparse_query_for` — one tf per token."""
    from collections import Counter
    from polymath_shared.sparse_bm25 import token_index
    toks, rule = sparse_query_for(text, exact_terms)
    if not toks:
        return None, rule
    counts = Counter(token_index(t) for t in toks)
    items = sorted(counts.items())
    return (tuple(i for i, _ in items), tuple(float(v) for _, v in items)), rule


@dataclass(frozen=True)
class SearchContext:
    """Immutable per-turn search inputs (§3.22): one query vector, one
    sparse query, shared by every lane."""
    query: str
    corpus_id: str
    collection: str
    qvec: tuple[float, ...]
    sparse_query: Optional[tuple[tuple[int, ...], tuple[float, ...]]] = None
    exact_terms: tuple[str, ...] = ()
    hidden_generations: tuple[str, ...] = ()
    query_id: str = "q0"
    sparse_rule: str = "topical"          # which rule built sparse_query (receipted)


@dataclass(frozen=True)
class SubQuery:
    """One typed subquery of the compiled plan (§3.1), with its own vector
    and sparse query. Runs lanes B + C only."""
    query_id: str
    qtype: str
    text: str
    weight: float
    qvec: tuple[float, ...]
    sparse_query: Optional[tuple[tuple[int, ...], tuple[float, ...]]] = None
    sparse_rule: str = "topical"


@dataclass
class CandidateEvidence:
    chunk_id: str
    doc_id: str
    parent_id: str
    source_name: str
    text: str
    arrivals: list[str] = field(default_factory=list)
    query_ids: list[str] = field(default_factory=list)
    hierarchy_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    rerank_score: Optional[float] = None
    fused_score: float = 0.0
    document_rank: Optional[int] = None
    is_neighbor: bool = False
    region_role: Optional[str] = None
    #: per-query lane contribution (weighted RRF), P1.b provenance
    query_scores: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        """The evidence dict shape the orchestrator, assembler and funnel
        already consume (`arrival` = first arrival, plus the full list)."""
        return {"chunk_id": self.chunk_id, "doc_id": self.doc_id, "parent_id": self.parent_id,
                "source_name": self.source_name, "text": self.text,
                "arrival": (self.arrivals[0] if self.arrivals else None), "arrivals": list(self.arrivals),
                "query_ids": list(self.query_ids), "hierarchy_rank": self.hierarchy_rank,
                "dense_rank": self.dense_rank, "sparse_rank": self.sparse_rank,
                "dense_score": self.dense_score, "sparse_score": self.sparse_score,
                "rerank_score": self.rerank_score, "fused_score": round(self.fused_score, 6),
                "document_rank": self.document_rank, "is_neighbor": self.is_neighbor,
                "region_role": self.region_role, "query_scores": {k: round(v, 6) for k, v in self.query_scores.items()},
                "similarity": self.dense_score if self.dense_score is not None else self.sparse_score}


@dataclass
class CandidateResult:
    context: SearchContext
    budget: CandidateBudget
    documents: list[DocumentCandidate]
    selected_documents: list[DocumentCandidate]
    selected_sections: list[dict]
    lane_a: list[CandidateEvidence]
    lane_b: list[CandidateEvidence]
    lane_c: list[CandidateEvidence]
    union: list[CandidateEvidence]           # fused order, capped at merged_candidate_max
    union_ids_uncapped: list[str]            # RETRIEVAL-FUNNEL-V1 `union` (before the cap)
    degraded: list[dict]
    timings_ms: dict
    trace: dict


def _hits(kind: str, rows: Iterable[dict], corpus_id: str, top_k: int, *,
          card_k: int = 0, card_max_docs: int = 0) -> list[LaneHit]:
    """Raw adapter rows → LaneHits (rank = position). Entity cards expand
    to one vote per (card, doc), exactly as pass1 does."""
    hits: list[LaneHit] = []
    for i, row in enumerate(list(rows)[:top_k]):
        payload = row.get("payload") or {}
        score = float(row.get("score") or 0.0)
        if kind == REPRESENTATION_KIND_ENTITY_CARD:
            if i >= card_k:
                continue
            docs = list(payload.get("doc_ids") or [])
            if not docs and payload.get("doc_id"):
                docs = [payload["doc_id"]]
            for d in docs[:card_max_docs]:
                hits.append(LaneHit(representation_kind=kind, rank=i, raw_similarity=score,
                                    corpus_id=payload.get("corpus_id", corpus_id), doc_id=d, parent_id="",
                                    chunk_id="", summary_id=payload.get("summary_id") or "",
                                    source_name=payload.get("source_name", ""), text=payload.get("text", "")))
            continue
        hits.append(LaneHit(representation_kind=kind, rank=i, raw_similarity=score,
                            corpus_id=payload.get("corpus_id", corpus_id), doc_id=payload.get("doc_id", ""),
                            parent_id=payload.get("parent_id", ""), chunk_id=payload.get("chunk_id") or "",
                            summary_id=payload.get("summary_id") or "", source_name=payload.get("source_name", ""),
                            text=payload.get("text", "")))
    return hits


def _sink_noisy(hits: list[LaneHit], roles: dict) -> list[LaneHit]:
    """DOCUMENT-REGION-V1 inside a lane: demote, never delete."""
    if not roles:
        return hits
    from polymath_shared.document_region import is_noisy
    out = sorted(hits, key=lambda h: (1 if is_noisy(roles.get(h.chunk_id)) else 0, h.rank))
    for i, h in enumerate(out):
        h.rank = i
    return out


def _call_dense(dense_search, kind, top_k, extra, qvec):
    """Adapters may accept a `qvec` keyword (P1.b); older ones close over the primary vector."""
    if qvec is None:
        return dense_search(kind, top_k, extra)
    try:
        return dense_search(kind, top_k, extra, qvec=qvec)
    except TypeError:
        return dense_search(kind, top_k, extra)


def _call_sparse(sparse_search, top_k, sparse_query):
    if sparse_query is None:
        return sparse_search(top_k)
    try:
        return sparse_search(top_k, sparse_query=sparse_query)
    except TypeError:
        return sparse_search(top_k)


class _Outcome:
    """What one lane produced: rows, its milliseconds, and whether it was
    dropped at the deadline (`timeout`; `started=False` when the budget was
    already spent before the stage could be launched) or raised (`error`)."""
    __slots__ = ("rows", "ms", "timeout", "error", "started")

    def __init__(self, rows: list, ms: float, *, timeout: bool = False, error: Optional[BaseException] = None, started: bool = True):
        self.rows, self.ms, self.timeout, self.error, self.started = rows, ms, timeout, error, started


def _timed_call(fn: Callable[[], list]) -> tuple[list, float]:
    t0 = time.perf_counter()
    rows = fn()
    return rows, round((time.perf_counter() - t0) * 1000, 1)


def _submit(executor: Executor, tasks: list[tuple[str, Callable[[], list]]]) -> dict[str, Future]:
    """Submit lanes in the given (fixed) order; every future resolves to
    (rows, own_ms). Submission order is the only order the pool sees."""
    return {name: executor.submit(_timed_call, fn) for name, fn in tasks}


def _gather(futs: dict[str, Future], deadline: float, *, raw: frozenset = frozenset()) -> dict[str, _Outcome]:
    """Collect lanes by NAME (never by completion order) against one absolute
    `deadline` (perf_counter clock). A lane still pending at the deadline is
    dropped — its future is cancelled if it has not started, its late result
    is ignored if it has — and reported as `timeout`; a lane that raised is
    reported as `error`. Nothing is raised here. `raw` names futures whose
    result is plain rows (pre-started outside the engine) rather than
    (rows, ms); their `ms` is the time the engine waited for them."""
    out: dict[str, _Outcome] = {}
    for name, fut in futs.items():
        t_wait = time.perf_counter()
        try:
            r = fut.result(timeout=max(0.0, deadline - t_wait))
            if name in raw:
                rows, ms = r, round((time.perf_counter() - t_wait) * 1000, 1)
            else:
                rows, ms = r
            out[name] = _Outcome(list(rows or []), ms)
        except (FutureTimeout, CancelledError):
            fut.cancel()
            out[name] = _Outcome([], round((time.perf_counter() - t_wait) * 1000, 1), timeout=True)
        except Exception as exc:  # noqa: BLE001 — the caller decides per lane (propagate / degrade / ignore)
            out[name] = _Outcome([], round((time.perf_counter() - t_wait) * 1000, 1), error=exc)
    return out


def _run_stage(pool: Executor, tasks: list[tuple[str, Callable[[], list]]], deadline: float) -> dict[str, _Outcome]:
    """Submit-and-gather one dependent stage (the deepening fan-out, the
    second pass). Nothing is launched once the deadline has passed — a hard
    budget never starts work it cannot wait for — so the stage is reported
    as not started, deterministically, instead of racing a zero timeout."""
    if not tasks:
        return {}
    if time.perf_counter() >= deadline:
        return {name: _Outcome([], 0.0, timeout=True, started=False) for name, _ in tasks}
    return _gather(_submit(pool, tasks), deadline)


def _deadline_reason(budget: CandidateBudget, waited_ms: float, started: bool, plural: bool = False) -> str:
    if not started:
        return f"not started: the core budget (lane_deadline_s={budget.lane_deadline_s:g}) was spent before this stage"
    return f"no result after {waited_ms:.0f} ms; lane_deadline_s={budget.lane_deadline_s:g} — late result{'s' if plural else ''} ignored"


def _timeout_receipt(name: str, budget: CandidateBudget, effect: str, o: _Outcome) -> dict:
    return {"component": f"{name}_timeout", "effect": effect, "reason": _deadline_reason(budget, o.ms, o.started)}


def retrieve_candidates(ctx: SearchContext, budget: CandidateBudget, *,
                        dense_search: Callable[..., list[dict]],
                        sparse_search: Callable[..., list[dict]],
                        region_lookup: Optional[Callable[[list[str]], dict]] = None,
                        subqueries: Iterable[SubQuery] = (),
                        executor: Optional[Executor] = None,
                        prestarted: Optional[dict] = None) -> CandidateResult:
    """CONCURRENCY-DEADLINES-V1 (P1.d, §3.16): the lanes of a turn run as
    concurrent tasks on a bounded pool, under ONE wall-clock budget
    (`lane_deadline_s`, the core lanes) measured from entry:

        T=0   doc summaries ∥ section summaries ∥ entity cards ∥ global dense
              child ∥ global sparse child ∥ every subquery's B + C
        then  routing aggregation → the hierarchical child deepening fan-out
              (one task per selected section) ∥ the subquery lanes still running
        then  (at most) one second pass for the first empty aspect

    A lane past the deadline is dropped — late result ignored — and receipted
    in `degraded` as {"component": "<lane>_timeout", …}; the turn completes
    with the other lanes. Results are collected BY LANE NAME and fused in the
    fixed lane order, so the union never depends on completion order: with no
    deadline hit the output is byte-identical to the sequential P1.b/P1.c
    engine (lane exceptions propagate or degrade exactly as before).

    `executor`: a caller-owned pool (the route shares one per turn); when
    None a pool of `max_workers` is created here and shut down on every path
    (never awaited — a late lane may not hold the turn). `prestarted`: lanes
    the caller started before calling (BM25 needs no embedding, §3.16), keyed
    by lane name (`global_sparse_child`, `sub_<qid>_sparse`) → a Future or a
    list of rows; a pre-started lane is not searched again.
    """
    timings: dict[str, float] = {}
    degraded: list[dict] = []
    lanes = set(budget.lanes)
    subqueries = list(subqueries or [])[:budget.max_subqueries]
    prestarted = dict(prestarted or {})
    t_turn = time.perf_counter()
    deadline = t_turn + float(budget.lane_deadline_s)
    own_pool = executor is None
    pool: Executor = executor if executor is not None else ThreadPoolExecutor(
        max_workers=max(1, int(budget.max_workers)), thread_name_prefix="candidate-lanes")
    try:
        return _retrieve_on(ctx, budget, pool, dense_search, sparse_search, region_lookup, subqueries, prestarted,
                            lanes, deadline, t_turn, timings, degraded)
    finally:
        if own_pool:
            pool.shutdown(wait=False, cancel_futures=True)      # never wait on a late lane; queued work is dropped


def _prestarted_future(value) -> Future:
    """Rows already in hand become a resolved future; a Future is used as is."""
    if isinstance(value, Future):
        return value
    f: Future = Future()
    f.set_result(list(value or []))
    return f


def _retrieve_on(ctx: SearchContext, budget: CandidateBudget, pool: Executor, dense_search, sparse_search, region_lookup,
                 subqueries: list[SubQuery], prestarted: dict, lanes: set, deadline: float, t_turn: float,
                 timings: dict, degraded: list) -> CandidateResult:
    LANE_DROPPED = "lane dropped this turn (deadline); the other lanes continue"
    SPARSE_DROPPED = "no exact-match lane this turn; dense lanes only"

    # ---- T=0: every independent lane, submitted in the fixed lane order ----------------
    primary_tasks: list[tuple[str, Callable[[], list]]] = []
    raw: set[str] = set()
    pre_futs: dict[str, Future] = {}
    if LANE_B in lanes or LANE_A in lanes:
        primary_tasks.append(("global_dense_child", lambda: dense_search(REPRESENTATION_KIND_CHILD, budget.global_dense_k, None)))
    if LANE_C in lanes:
        if "global_sparse_child" in prestarted:
            pre_futs["global_sparse_child"] = _prestarted_future(prestarted["global_sparse_child"]); raw.add("global_sparse_child")
        else:
            primary_tasks.append(("global_sparse_child", lambda: sparse_search(budget.global_sparse_k)))
    if LANE_A in lanes:
        primary_tasks.append(("document_summary", lambda: dense_search(REPRESENTATION_KIND_DOCUMENT_SUMMARY, budget.hierarchy_doc_k, None)))
        primary_tasks.append(("section_summary", lambda: dense_search(REPRESENTATION_KIND_SECTION_SUMMARY, budget.hierarchy_section_k, None)))
        if budget.entity_card_k > 0:
            primary_tasks.append(("entity_card", lambda: dense_search(REPRESENTATION_KIND_ENTITY_CARD,
                                                                      budget.entity_card_k * budget.entity_card_max_docs_per_card, None)))
    sub_tasks: list[tuple[str, Callable[[], list]]] = []
    sub_pre: dict[str, Future] = {}
    for sq in subqueries:
        if LANE_B in lanes:
            sub_tasks.append((f"sub_{sq.query_id}_dense", lambda sq=sq: _call_dense(dense_search, REPRESENTATION_KIND_CHILD, budget.subquery_dense_k, None, sq.qvec)))
        if LANE_C in lanes and sq.sparse_query is not None:
            name = f"sub_{sq.query_id}_sparse"
            if name in prestarted:
                sub_pre[name] = _prestarted_future(prestarted[name]); raw.add(name)
            else:
                sub_tasks.append((name, lambda sq=sq: _call_sparse(sparse_search, budget.subquery_sparse_k, sq.sparse_query)))
    futs = _submit(pool, primary_tasks + sub_tasks)
    futs.update(pre_futs); futs.update(sub_pre)
    # the ROUTING lanes first: the hierarchical deepening needs all four of them and nothing else — lane C is
    # gathered only once the deepening is in flight, so a slow BM25 never delays the fan-out
    routing_names = [n for n, _ in primary_tasks if n != "global_sparse_child"]
    outs = _gather({n: futs[n] for n in routing_names}, deadline, raw=frozenset(raw))
    timings["lanes_wall"] = round((time.perf_counter() - t_turn) * 1000, 1)
    for name in routing_names:
        timings[name] = outs[name].ms

    def dropped(name: str, effect: str) -> None:
        degraded.append(_timeout_receipt(name, budget, effect, outs[name]))

    # ---- lanes B and C (primary) — the sequential engine's failure semantics, lane by lane ----
    child_rows: list[dict] = []
    if "global_dense_child" in outs:
        o = outs["global_dense_child"]
        if o.error is not None:
            raise o.error                                       # as before: the primary dense lane failing fails the turn
        if o.timeout:
            dropped("global_dense_child", LANE_DROPPED)
        child_rows = o.rows
    child_lane = _hits(REPRESENTATION_KIND_CHILD, child_rows, ctx.corpus_id, budget.global_dense_k)
    roles: dict = {}
    if budget.demote_noisy_regions and region_lookup is not None and child_lane:
        try:
            roles = region_lookup([h.chunk_id for h in child_lane if h.chunk_id]) or {}
        except Exception:  # noqa: BLE001 — demotion is best-effort
            roles = {}
        child_lane = _sink_noisy(child_lane, roles)

    # ---- lane A: hierarchical route (routing lanes gathered above; deepening fans out concurrently) ----
    doc_lane: list[LaneHit] = []
    section_lane: list[LaneHit] = []
    card_lane: list[LaneHit] = []
    documents: list[DocumentCandidate] = []
    selected_documents: list[DocumentCandidate] = []
    selected_sections: list[dict] = []
    lane_a: list[CandidateEvidence] = []
    if LANE_A in lanes:
        for name in ("document_summary", "section_summary"):
            if outs[name].error is not None:
                raise outs[name].error
            if outs[name].timeout:
                dropped(name, LANE_DROPPED)
        doc_lane = _hits(REPRESENTATION_KIND_DOCUMENT_SUMMARY, outs["document_summary"].rows, ctx.corpus_id, budget.hierarchy_doc_k)
        section_lane = _hits(REPRESENTATION_KIND_SECTION_SUMMARY, outs["section_summary"].rows, ctx.corpus_id, budget.hierarchy_section_k)
        if "entity_card" in outs:
            o = outs["entity_card"]
            if o.timeout:
                dropped("entity_card", "no entity-card routing votes this turn")
            if o.error is None and not o.timeout:               # a failing card probe stays silent: routing votes only
                card_lane = _hits(REPRESENTATION_KIND_ENTITY_CARD, o.rows, ctx.corpus_id,
                                  budget.entity_card_k * budget.entity_card_max_docs_per_card,
                                  card_k=budget.entity_card_k, card_max_docs=budget.entity_card_max_docs_per_card)
        documents = aggregate_documents_n(
            [(REPRESENTATION_KIND_DOCUMENT_SUMMARY, doc_lane), (REPRESENTATION_KIND_SECTION_SUMMARY, section_lane),
             (REPRESENTATION_KIND_CHILD, child_lane), (REPRESENTATION_KIND_ENTITY_CARD, card_lane)], k=budget.rrf_k)
        selected_documents = documents[:budget.hierarchy_max_documents]
        selected_sections = resolve_sections(selected_documents, budget.hierarchy_max_sections_per_document)
        doc_rank = {d.doc_id: d.aggregate_rank for d in selected_documents}
        t0 = time.perf_counter()
        deep_tasks = [(f"deep_{i}", (lambda section=section: dense_search(REPRESENTATION_KIND_CHILD, budget.hierarchy_child_k,
                                                                          {"doc_id": section["doc_id"], "parent_id": section["parent_id"]})))
                      for i, section in enumerate(selected_sections)]
        deep = _run_stage(pool, deep_tasks, deadline)
        timings["hierarchical_children"] = round((time.perf_counter() - t0) * 1000, 1)
        for name, o in deep.items():                            # fixed section order: the first failing deepening raises, as before
            if o.error is not None:
                raise o.error
        late = [n for n, o in deep.items() if o.timeout]
        if late:
            degraded.append({"component": "hierarchical_children_timeout",
                             "effect": f"{len(late)} of {len(deep)} section deepenings dropped; lane A keeps the sections that answered",
                             "reason": _deadline_reason(budget, max(deep[n].ms for n in late), any(deep[n].started for n in late), plural=True)})
        seen_a: set[str] = set()
        for i, section in enumerate(selected_sections):
            for h in _hits(REPRESENTATION_KIND_CHILD, deep[f"deep_{i}"].rows, ctx.corpus_id, budget.hierarchy_child_k):
                if not h.chunk_id or h.chunk_id in seen_a:
                    continue
                seen_a.add(h.chunk_id)
                lane_a.append(CandidateEvidence(
                    chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name, text=h.text,
                    arrivals=[LANE_A], query_ids=[ctx.query_id], hierarchy_rank=len(lane_a), dense_score=h.raw_similarity,
                    document_rank=doc_rank.get(h.doc_id)))

    # ---- lane C (primary): running since T=0, joined here — BM25 is not a routing input -----------------
    sparse_lane: list[LaneHit] = []
    if "global_sparse_child" in futs:
        outs.update(_gather({"global_sparse_child": futs["global_sparse_child"]}, deadline, raw=frozenset(raw)))
        o = outs["global_sparse_child"]
        timings["global_sparse_child"] = o.ms
        if o.error is not None:                                 # §3.21 #2: DEGRADED, never a Postgres scan
            degraded.append({"component": "sparse_lane", "effect": SPARSE_DROPPED,
                             "reason": f"{type(o.error).__name__}: {str(o.error)[:160]}"})
        elif o.timeout:
            dropped("global_sparse_child", SPARSE_DROPPED)
        else:
            sparse_lane = _hits("child_lexical", o.rows, ctx.corpus_id, budget.global_sparse_k)

    lane_b = [CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                text=h.text, arrivals=[LANE_B], query_ids=[ctx.query_id], dense_rank=h.rank,
                                dense_score=h.raw_similarity, region_role=roles.get(h.chunk_id))
              for h in child_lane if h.chunk_id] if LANE_B in lanes else []
    lane_c = [CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                text=h.text, arrivals=[LANE_C], query_ids=[ctx.query_id], sparse_rank=h.rank,
                                sparse_score=h.raw_similarity)
              for h in sparse_lane if h.chunk_id]

    # ---- typed subqueries: lanes B + C only (§3.16), per-query provenance; started at T=0, gathered here ------
    aspects: dict[str, dict] = {ctx.query_id: {"type": "PRIMARY", "query": ctx.query, "weight": 1.0,
                                               "lanes": {LANE_A: len(lane_a), LANE_B: len(lane_b), LANE_C: len(lane_c)},
                                               "degraded": [d["component"] for d in degraded]}}
    sub_items: list[CandidateEvidence] = []
    second_pass: Optional[dict] = None
    sub_names = [n for n, _ in sub_tasks] + list(sub_pre)
    sub_outs = _gather({n: futs[n] for n in sub_names}, deadline, raw=frozenset(raw))
    for name in sub_names:
        timings[name] = sub_outs[name].ms

    def _items_for(sq: SubQuery, outcomes: dict[str, _Outcome], dk: int, sk: int) -> tuple[list[CandidateEvidence], dict]:
        items: list[CandidateEvidence] = []
        info = {"type": sq.qtype, "query": sq.text, "weight": sq.weight, "lanes": {LANE_B: 0, LANE_C: 0}, "degraded": []}
        o = outcomes.get("dense")
        if o is not None:
            if o.error is not None:
                info["degraded"].append(f"dense:{type(o.error).__name__}")
            elif o.timeout:
                info["degraded"].append("dense:timeout")
            else:
                hits = _sink_noisy(_hits(REPRESENTATION_KIND_CHILD, o.rows, ctx.corpus_id, dk), roles) if roles else _hits(REPRESENTATION_KIND_CHILD, o.rows, ctx.corpus_id, dk)
                for h in hits:
                    if h.chunk_id:
                        items.append(CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                                       text=h.text, arrivals=[LANE_B], query_ids=[sq.query_id],
                                                       query_scores={sq.query_id: sq.weight * _rrf_score(h.rank, budget.rrf_k)},
                                                       dense_score=h.raw_similarity))
                info["lanes"][LANE_B] = sum(1 for h in hits if h.chunk_id)
        o = outcomes.get("sparse")
        if o is not None:
            if o.error is not None:
                info["degraded"].append(f"sparse:{type(o.error).__name__}")
            elif o.timeout:
                info["degraded"].append("sparse:timeout")
            else:
                hits = _hits("child_lexical", o.rows, ctx.corpus_id, sk)
                for h in hits:
                    if h.chunk_id:
                        items.append(CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                                       text=h.text, arrivals=[LANE_C], query_ids=[sq.query_id],
                                                       query_scores={sq.query_id: sq.weight * _rrf_score(h.rank, budget.rrf_k)},
                                                       sparse_score=h.raw_similarity))
                info["lanes"][LANE_C] = sum(1 for h in hits if h.chunk_id)
        return items, info

    for sq in subqueries:
        outcomes = {}
        if f"sub_{sq.query_id}_dense" in sub_outs:
            outcomes["dense"] = sub_outs[f"sub_{sq.query_id}_dense"]
        if f"sub_{sq.query_id}_sparse" in sub_outs:
            outcomes["sparse"] = sub_outs[f"sub_{sq.query_id}_sparse"]
        items, info = _items_for(sq, outcomes, budget.subquery_dense_k, budget.subquery_sparse_k)
        for lane_key, o in outcomes.items():
            if o.timeout:
                degraded.append(_timeout_receipt(f"sub_{sq.query_id}_{lane_key}", budget, f"aspect {sq.query_id} loses its {lane_key} lane this turn", o))
        aspects[sq.query_id] = info
        sub_items.extend(items)
    # one targeted second pass: the first aspect that found nothing gets B + C again at K × factor — but an aspect
    # whose lanes were DROPPED at the deadline was not given time, not found empty: no second pass for it
    for sq in subqueries:
        info = aspects[sq.query_id]
        if info["lanes"][LANE_B] + info["lanes"][LANE_C] == 0 and budget.second_pass_factor > 1 \
                and not any(d.endswith(":timeout") for d in info["degraded"]):
            dk, sk = budget.subquery_dense_k * budget.second_pass_factor, budget.subquery_sparse_k * budget.second_pass_factor
            tasks2: list[tuple[str, Callable[[], list]]] = []
            if LANE_B in lanes:
                tasks2.append(("dense", lambda sq=sq, dk=dk: _call_dense(dense_search, REPRESENTATION_KIND_CHILD, dk, None, sq.qvec)))
            if LANE_C in lanes and sq.sparse_query is not None:
                tasks2.append(("sparse", lambda sq=sq, sk=sk: _call_sparse(sparse_search, sk, sq.sparse_query)))
            outs2 = _run_stage(pool, tasks2, deadline)
            for lane_key, o in outs2.items():
                timings[f"sub_{sq.query_id}_{lane_key}"] = o.ms
                if o.timeout:
                    degraded.append(_timeout_receipt(f"sub_{sq.query_id}_{lane_key}", budget, f"second pass for aspect {sq.query_id} dropped", o))
            items, info2 = _items_for(sq, outs2, dk, sk)
            second_pass = {"query_id": sq.query_id, "before": 0, "after": len(items)}
            aspects[sq.query_id] = {**info2, "second_pass": True}
            sub_items.extend(items)
            break

    # ---- union + dedupe + provenance-preserving fusion (fixed lane order: A, B, C, subqueries) --------
    t_union = time.perf_counter()
    by_id: dict[str, CandidateEvidence] = {}
    for c in lane_a + lane_b + lane_c:
        c.query_scores = dict(c.query_scores)
    for lane_items in (lane_a, lane_b, lane_c, sub_items):
        for c in lane_items:
            cur = by_id.get(c.chunk_id)
            if cur is None:
                by_id[c.chunk_id] = replace_candidate(c)
                continue
            for a in c.arrivals:
                if a not in cur.arrivals:
                    cur.arrivals.append(a)
            for q in c.query_ids:
                if q not in cur.query_ids:
                    cur.query_ids.append(q)
            if cur.hierarchy_rank is None:
                cur.hierarchy_rank = c.hierarchy_rank
            if cur.dense_rank is None:
                cur.dense_rank, cur.dense_score = c.dense_rank, (c.dense_score if c.dense_score is not None else cur.dense_score)
            if cur.sparse_rank is None:
                cur.sparse_rank, cur.sparse_score = c.sparse_rank, c.sparse_score
            if cur.document_rank is None:
                cur.document_rank = c.document_rank
            if not cur.text and c.text:
                cur.text = c.text
            for qid, sc in c.query_scores.items():
                cur.query_scores[qid] = cur.query_scores.get(qid, 0.0) + sc
    # primary contribution = the three lane ranks (as before); subquery contributions are per query
    for c in by_id.values():
        primary = sum(_rrf_score(r, budget.rrf_k) for r in (c.hierarchy_rank, c.dense_rank, c.sparse_rank) if r is not None)
        if primary:
            c.query_scores[ctx.query_id] = primary
        if c.region_role is None:
            c.region_role = roles.get(c.chunk_id)
    # §3.10 per-document normalisation: under one subquery, only a document's best chunk keeps that
    # query's full contribution (others keep half) — N chunks of one document cannot stack a subquery's vote
    for qid in [sq.query_id for sq in subqueries]:
        best_by_doc: dict[str, str] = {}
        for c in sorted(by_id.values(), key=lambda c: -c.query_scores.get(qid, 0.0)):
            if qid not in c.query_scores:
                continue
            if c.doc_id in best_by_doc:
                c.query_scores[qid] *= 0.5
            else:
                best_by_doc[c.doc_id] = c.chunk_id
    for c in by_id.values():
        if not c.query_scores:
            c.fused_score = 0.0
            continue
        best = max(c.query_scores.values())
        extra = sum(c.query_scores.values()) - best
        c.fused_score = best + min(best, budget.agreement_bonus * extra)
    fused = sorted(by_id.values(), key=lambda c: (-c.fused_score, c.chunk_id))
    if budget.demote_noisy_regions and roles:
        from polymath_shared.document_region import is_noisy
        fused = sorted(fused, key=lambda c: 1 if is_noisy(c.region_role) else 0)   # stable: order kept within groups
    # GRAPH-EVIDENCE-HYGIENE-V1 (backlog B8, measured 2026-09-06): back-of-book index pages of the VES Handbook
    # ("solver operators (SOPs) [837](…#p837) Sony F3 camera [249](…#p249) …") reached the judged set and the prompt.
    # The role-based demotion above only sees chunks whose region_role is set; these carried none. A conservative
    # lexical test drops index pages and page-number lists BEFORE truncation (noise must not spend union slots
    # either), and every drop is receipted (`noise_dropped`, `noise_reasons`, `noise_sample`). Prose never matches:
    # the test needs a page-link density or a bare-number share no paragraph of a book has.
    noise_dropped: list[tuple[str, str]] = []
    kept: list[CandidateEvidence] = []
    for c in fused:
        why = structural_noise_reason(c.text)
        if why:
            noise_dropped.append((c.chunk_id, why))
        else:
            kept.append(c)
    fused = kept
    union_ids_uncapped = [c.chunk_id for c in fused]
    union = fused[:budget.merged_candidate_max]
    timings["union"] = round((time.perf_counter() - t_union) * 1000, 1)
    timings["core_wall"] = round((time.perf_counter() - t_turn) * 1000, 1)

    trace = {
        "plan": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION, "rrf_k": budget.rrf_k,
        "budget": budget.to_dict(),
        "lane_sizes": {"document_summary": len(doc_lane), "section_summary": len(section_lane), "entity_card": len(card_lane),
                       "hierarchical_children": len(lane_a), "global_dense_child": len(lane_b), "global_sparse_child": len(lane_c),
                       "union": len(union), "union_uncapped": len(union_ids_uncapped)},
        "funnel_lanes": {"hierarchical": [c.chunk_id for c in lane_a], "global_dense_child": [c.chunk_id for c in lane_b],
                         "global_sparse_child": [c.chunk_id for c in lane_c]},
        "funnel_union": union_ids_uncapped,
        "document_candidates": [{"doc_id": d.doc_id, "aggregate_rank": d.aggregate_rank, "aggregate_score": round(d.aggregate_score, 6),
                                 "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
                                 "representation_kinds_present": d.representation_kinds_present} for d in documents],
        "multi_lane": sum(1 for c in union if len(c.arrivals) > 1),
        "sparse_rule": ctx.sparse_rule, "exact_terms": list(ctx.exact_terms),
        # P1.b aspect coverage: per compiled query — lanes, union candidates, degradations
        "aspects": {qid: {**info, "union": sum(1 for c in union if qid in c.query_ids)} for qid, info in aspects.items()},
        "subqueries": len(subqueries), "second_pass": second_pass,
        # P1.d receipts: the pool, the deadline, which lanes were handed in pre-started, which were dropped
        "concurrency": {"contract": CONCURRENCY_CONTRACT, "max_workers": max(1, int(budget.max_workers)),
                        "lane_deadline_s": budget.lane_deadline_s, "prestarted": sorted(raw),
                        "timed_out": [d["component"][:-len("_timeout")] for d in degraded if d["component"].endswith("_timeout")]},
        "degraded": list(degraded), "timings_ms": dict(timings),
    }
    trace["noise_dropped"] = len(noise_dropped)
    trace["noise_reasons"] = dict(Counter(w for _, w in noise_dropped))
    trace["noise_sample"] = [cid for cid, _ in noise_dropped[:5]]
    return CandidateResult(context=ctx, budget=budget, documents=documents, selected_documents=selected_documents,
                           selected_sections=selected_sections, lane_a=lane_a, lane_b=lane_b, lane_c=lane_c,
                           union=union, union_ids_uncapped=union_ids_uncapped, degraded=degraded, timings_ms=timings, trace=trace)


def replace_candidate(c: CandidateEvidence) -> CandidateEvidence:
    return CandidateEvidence(**{**c.__dict__, "arrivals": list(c.arrivals), "query_ids": list(c.query_ids)})


def _sig(x: Optional[float]) -> float:
    import math
    if x is None:
        return 0.0
    x = max(-30.0, min(30.0, float(x)))
    return 1.0 / (1.0 + math.exp(-x))


def judged_score(c: CandidateEvidence, budget: CandidateBudget) -> float:
    """Sigmoid of the judge's logit plus the bounded agreement bonus (ordering only)."""
    if c.rerank_score is None:          # degraded judge: fusion order stands (it already carries lane agreement)
        return 0.0
    extra = max(0, len(c.arrivals) - 1)
    return _sig(c.rerank_score) + min(budget.compose_agreement_cap, budget.compose_agreement_boost * extra)


def compose_evidence(judged: list[CandidateEvidence], budget: CandidateBudget, *, weak_aspects: Iterable[str] = (),
                     primary_id: str = "q0") -> tuple[list[CandidateEvidence], dict]:
    """EVIDENCE-COMPOSER-V1 (§3.17). `judged` = the reranked prefix in judge
    order (rerank_score set, or fusion order when the judge degraded).
    Returns (final, composition trace). A chunk may satisfy several slots;
    the final list is deduped and may therefore be shorter than the cap."""
    cap = budget.synthesis_max
    weak = set(weak_aspects or ())
    if not judged:
        return [], {"slots": {}, "doc_counts": {}, "doc_share_top": 0.0, "docs_within_gap": 0, "dominance": False, "aspect_seats": [], "agreement_reordered": 0}
    order = sorted(range(len(judged)), key=lambda i: (-judged_score(judged[i], budget), i))
    order = [judged[i] for i in order]
    final: list[CandidateEvidence] = []
    seen: set[str] = set()
    slots = {"relevance": 0, "diversity": 0, "sparse": 0, "aspect": 0, "fill": 0}
    doc_count: dict[str, int] = {}
    aspect_seats: list[dict] = []

    def admit(c: CandidateEvidence, slot: str) -> bool:
        if c.chunk_id in seen or len(final) >= cap:
            return False
        seen.add(c.chunk_id); final.append(c); doc_count[c.doc_id] = doc_count.get(c.doc_id, 0) + 1; slots[slot] += 1
        return True

    judged_any = any(c.rerank_score is not None for c in judged)
    floor = budget.aspect_weak_floor if judged_any else None

    def accepted(c: CandidateEvidence) -> bool:
        """Slots 2–4 never promote what the judge rejected (sigmoid < floor); the fill step may still take it."""
        return floor is None or c.rerank_score is None or _sig(c.rerank_score) >= floor

    def best_unrepresented() -> Optional[float]:
        return next((judged_score(c, budget) for c in order if c.doc_id not in doc_count and accepted(c)), None)

    # DOMINANCE GUARD (P1.c gate): while ≥ 3 documents score within the gap of the top, no document may take more
    # than compose_dominance_share of the set through slots 2–5; the final fill pass lifts the cap so seats are never
    # left empty when only one document has evidence left (the receipt then says the dominance was not avoidable)
    top_now = judged_score(order[0], budget)
    docs_within_now = len({c.doc_id for c in order if top_now - judged_score(c, budget) <= budget.compose_score_gap})
    share_cap = int(budget.compose_dominance_share * cap)
    guard = docs_within_now >= 3

    def capped(c: CandidateEvidence) -> bool:
        return guard and doc_count.get(c.doc_id, 0) >= share_cap

    # 1. pure relevance
    for c in order[:budget.compose_relevance_slots]:
        admit(c, "relevance")
    # 2. source diversity (≤ compose_diversity_slots, judge-accepted only): soft max per document unless the
    #    score gap to the best unrepresented document is large
    for c in order:
        if len(final) >= cap or slots["diversity"] >= budget.compose_diversity_slots:
            break
        if c.chunk_id in seen or not accepted(c) or capped(c):
            continue
        bu = best_unrepresented()
        under_cap = doc_count.get(c.doc_id, 0) < budget.compose_doc_soft_max
        big_gap = bu is None or (judged_score(c, budget) - bu) >= budget.compose_score_gap
        if under_cap or big_gap:
            admit(c, "diversity")
    # 3. sparse winners (exact-match lane arrivals) not yet seated
    n = 0
    for c in order:
        if n >= budget.compose_sparse_slots or len(final) >= cap:
            break
        if LANE_C in c.arrivals and c.chunk_id not in seen and accepted(c) and not capped(c) and admit(c, "sparse"):
            n += 1
    # 4. aspect coverage: one seat per non-weak compiled query not yet represented (displacing the lowest
    #    item that is not another aspect's only representative when the set is full)
    represented = {q for c in final for q in c.query_ids}
    aspects = []
    for c in order:
        for q in c.query_ids:
            if q != primary_id and q not in weak and q not in aspects:
                aspects.append(q)
    for q in aspects[:budget.compose_aspect_slots]:
        if q in represented:
            continue
        best_c = next((c for c in order if q in c.query_ids and accepted(c) and not capped(c)), None)
        if best_c is None or best_c.chunk_id in seen:
            continue
        displaced = None
        if len(final) >= cap:
            for c in reversed(final):
                others = [x for x in c.query_ids if x != primary_id]
                if not others or all(sum(1 for f in final if x in f.query_ids) > 1 for x in others):
                    displaced = c; break
            if displaced is None:
                continue
            final.remove(displaced); seen.discard(displaced.chunk_id); doc_count[displaced.doc_id] -= 1
        admit(best_c, "aspect"); represented.update(best_c.query_ids)
        aspect_seats.append({"query_id": q, "chunk_id": best_c.chunk_id, "displaced": (displaced.chunk_id if displaced else None)})
    # 5. fill remaining seats in judge order — with the DOMINANCE GUARD (gate: no final set with > 60 % of its
    #    chunks from one document when ≥ 3 documents score within the gap of the top): while that holds, a document
    #    already at the share cap yields its fill seats to the other close documents; a second pass lifts the cap so
    #    seats are never left empty when only one document has evidence left
    for c in order:
        if len(final) >= cap:
            break
        if c.chunk_id in seen or capped(c):
            continue
        admit(c, "fill")
    for c in order:
        if len(final) >= cap:
            break
        if c.chunk_id not in seen:
            admit(c, "fill")
    # dominance receipt (gate: no final set with > 60 % from one document when ≥ 3 documents score within 0.1 of the top)
    top = judged_score(order[0], budget)
    docs_within = len({c.doc_id for c in order if top - judged_score(c, budget) <= budget.compose_score_gap})
    share_top = (max(doc_count.values()) / len(final)) if final else 0.0
    top_doc = max(doc_count, key=doc_count.get) if doc_count else None
    literal = bool(share_top > budget.compose_dominance_share and docs_within >= 3)
    # avoidable = a judge-accepted chunk of ANOTHER document was left out while the top document exceeded the share
    avoidable = literal and any(c.chunk_id not in seen and c.doc_id != top_doc and accepted(c) for c in order)
    trace = {"slots": slots, "doc_counts": dict(sorted(doc_count.items(), key=lambda kv: -kv[1])), "doc_share_top": round(share_top, 3),
             "docs_within_gap": docs_within, "dominance": literal, "dominance_avoidable": avoidable, "aspect_seats": aspect_seats,
             "agreement_reordered": sum(1 for i, c in enumerate(order) if c is not judged[i])}
    return final, trace


_PAGE_LINK_RE = re.compile(r"\]\([^)\s]*#p\d+\)|\[\d{1,4}\]\(")          # "[837](019_…chapter7.html#p837)"
_NUMBER_TOKEN_RE = re.compile(r"^\W*\d{1,4}\W*$")


def structural_noise_reason(text: str) -> Optional[str]:
    """Pure: a reason when a candidate's text is a back-of-book index page or a page-number list, else None.
    Thresholds are conservative — ≥ 6 page links AND ≥ 1 per 120 characters, or ≥ 40 tokens of which ≥ 45 % are
    bare numbers — so that dense prose with a few citations never matches."""
    t = (text or "").strip()
    if len(t) < 80:
        return None
    links = len(_PAGE_LINK_RE.findall(t))
    if links >= 6 and links / max(1.0, len(t) / 120.0) >= 1.0:
        return "index_page_links"
    tokens = t.split()
    if len(tokens) >= 40:
        numeric = sum(1 for tok in tokens if _NUMBER_TOKEN_RE.match(tok))
        if numeric / len(tokens) >= 0.45:
            return "number_list"
    return None


def judged_prefix(union: list, budget: CandidateBudget) -> tuple[list, dict]:
    """EVIDENCE-DIET-V1 step 3: the `rerank_max` candidates the judge will score. Pure; fusion order is
    preserved within a document and the set is decided document-fairly (see CandidateBudget). With
    `rerank_round_robin` off this is exactly the old `union[:rerank_max]`."""
    # fair policy: `rerank_max_fair` seats (32 by measurement); the old slice keeps `rerank_max` (24)
    k = int(budget.rerank_max_fair if budget.rerank_round_robin else budget.rerank_max)
    if not budget.rerank_round_robin or k <= 0:
        pre = list(union[:k])
        docs = {}
        for c in pre:
            docs[c.doc_id] = docs.get(c.doc_id, 0) + 1
        return pre, {"policy": "fusion", "judged_docs": len(docs), "capped_out": 0, "docs": docs}
    cap = max(1, int(budget.rerank_doc_cap))
    by_doc: dict[str, list] = {}
    doc_order: list[str] = []
    for c in union:
        if c.doc_id not in by_doc:
            by_doc[c.doc_id] = []
            doc_order.append(c.doc_id)
        by_doc[c.doc_id].append(c)
    chosen: list = []
    seen: set[str] = set()
    taken: dict[str, int] = {d: 0 for d in doc_order}

    def _seat(c) -> bool:
        if c.chunk_id in seen or len(chosen) >= k:
            return False
        chosen.append(c); seen.add(c.chunk_id); taken[c.doc_id] += 1
        return True

    # round 1: every surfaced document's best candidate, in order of first appearance
    for d in doc_order:
        if len(chosen) >= k:
            break
        _seat(by_doc[d][0])
    # then the fusion order under the per-document cap
    capped_out = 0
    for c in union:
        if len(chosen) >= k:
            break
        if c.chunk_id in seen:
            continue
        if taken[c.doc_id] >= cap:
            capped_out += 1
            continue
        _seat(c)
    # never leave seats empty: fill in fusion order ignoring the cap
    for c in union:
        if len(chosen) >= k:
            break
        _seat(c)
    # the SET is document-fair; the ORDER stays the fusion order (the degraded-judge path composes in prefix order,
    # the receipts read `pre_g3_order` as fusion order, and the judge's own ordering replaces it when it answers)
    rank = {c.chunk_id: i for i, c in enumerate(union)}
    chosen.sort(key=lambda c: rank[c.chunk_id])
    docs = {d: n for d, n in taken.items() if n}
    return chosen, {"policy": f"round_robin:cap{cap}", "judged_docs": len(docs), "capped_out": capped_out, "docs": docs}


def select_evidence(result: CandidateResult, budget: CandidateBudget, *,
                    rerank_children: Optional[Callable[[str, list[dict]], list[dict]]] = None,
                    neighbor_lookup: Optional[Callable[[list[dict], int], list[dict]]] = None) -> tuple[list[CandidateEvidence], dict]:
    """One cross-encoder judgement over the fusion-ordered prefix
    (`rerank_max`), pure relevance to `synthesis_max`, then the depth
    profile's neighbour expansion (additive, after the judge — the
    candidate set the reranker scored is never changed). P1.c owns the
    composition slots; here relevance order is the whole law."""
    import math
    union = result.union
    primary_id = result.context.query_id
    aspects_all = list((result.trace.get("aspects") or {}).keys()) or [primary_id]
    sub_ids = [q for q in aspects_all if q != primary_id]
    prefix, prefix_receipt = judged_prefix(union, budget)
    in_prefix = {c.chunk_id for c in prefix}
    aspect_prefix: dict[str, int] = {}
    for qid in sub_ids:                                   # reserve judged seats per aspect
        have = sum(1 for c in prefix if qid in c.query_ids)
        for c in union:
            if have >= budget.aspect_prefix_seats:
                break
            if qid in c.query_ids and c.chunk_id not in in_prefix:
                prefix.append(c); in_prefix.add(c.chunk_id); have += 1
        aspect_prefix[qid] = have
    pre = [c.chunk_id for c in prefix]
    post = list(pre)
    scores: dict[str, float] = {}
    if rerank_children is not None and prefix:
        rows = [c.to_row() for c in prefix]
        reranked = rerank_children(result.context.query, rows)
        post = [r["chunk_id"] for r in reranked]
        assert set(post) == set(pre), "rerank changed the candidate set"
        scores = {r["chunk_id"]: r.get("rerank_score") for r in reranked}
        by_id = {c.chunk_id: c for c in prefix}
        prefix = [by_id[cid] for cid in post]
        for c in prefix:
            c.rerank_score = scores.get(c.chunk_id)

    def _sigmoid(x):
        x = max(-30.0, min(30.0, float(x)))
        return 1.0 / (1.0 + math.exp(-x))

    judged = bool(scores) and any(v is not None for v in scores.values())
    aspect_best: dict[str, Optional[float]] = {}
    weak_reason: dict[str, str] = {}
    for qid in aspects_all:
        cands = [c for c in prefix if qid in c.query_ids]
        if not cands:
            aspect_best[qid] = None; weak_reason[qid] = "no_candidates"; continue
        if judged:
            best = max((_sigmoid(c.rerank_score) for c in cands if c.rerank_score is not None), default=None)
            aspect_best[qid] = round(best, 4) if best is not None else None
            if best is not None and best < budget.aspect_weak_floor:   # the PRIMARY too (R1): irrelevant-only evidence is named, not shown as coverage
                weak_reason[qid] = "below_floor"
        else:
            aspect_best[qid] = None
    # the composition sees only JUDGED verdicts (below_floor / no_candidates); an unjudged turn keeps fusion order
    final, composition = compose_evidence(prefix, budget, weak_aspects=set(weak_reason), primary_id=primary_id)
    # ACCEPTANCE FINDING A1 (2026-09-06): when a judge was expected (the route always passes one) but scored nothing —
    # `rerank_timeout` past the deadline, or a parked sidecar — no floor verdict exists, so nothing was flagged and every
    # aspect READ as covered (M system-honest 0.844 on judge-timeout turns vs 1.0 on judged turns). Coverage that the
    # judge never verified is named as such: every aspect with candidates is flagged `unjudged` (a receipt and a prompt
    # line, never a filter — selection above is unchanged). Callers without a judge (rerank_children=None) are unchanged.
    judge_state = "live" if judged else ("unjudged" if (rerank_children is not None and prefix) else "absent")
    if judge_state == "unjudged":
        for qid in aspects_all:
            weak_reason.setdefault(qid, "unjudged")
    seated = composition["aspect_seats"]
    added = 0
    if budget.neighbor_expansion > 0 and neighbor_lookup is not None and final:
        try:
            neighbours = neighbor_lookup([{"doc_id": c.doc_id, "chunk_id": c.chunk_id} for c in final], budget.neighbor_expansion) or []
        except Exception:  # noqa: BLE001 — additive, never fails the turn
            neighbours = []
        have = {c.chunk_id for c in final}
        for n in neighbours:
            cid = n.get("chunk_id")
            if not cid or cid in have:
                continue
            have.add(cid)
            final.append(CandidateEvidence(chunk_id=cid, doc_id=n.get("doc_id", ""), parent_id=n.get("parent_id", ""),
                                           source_name=n.get("source_name", ""), text=n.get("text", ""),
                                           arrivals=[ARRIVAL_NEIGHBOR], query_ids=[result.context.query_id], is_neighbor=True))
            added += 1
            if added >= budget.neighbor_expansion_max:
                break
    aspects = (result.trace.get("aspects") or {})
    aspect_final = {qid: sum(1 for c in final if qid in c.query_ids) for qid in aspects}
    weak = sorted(set(weak_reason) | {qid for qid, n in aspect_final.items() if n == 0 and qid != primary_id})
    trace = {"pre_g3_order": pre, "post_g3_order": post, "g3_scores": scores, "rerank_prefix": len(pre),
             "neighbors_added": added, "final": [c.chunk_id for c in final],
             "aspect_final": aspect_final, "weak_aspects": weak, "weak_reasons": weak_reason, "judge": judge_state,
             "aspect_prefix": aspect_prefix, "aspect_best": aspect_best, "aspect_seated": seated, "composition": composition,
             "prefix_policy": prefix_receipt["policy"], "judged_docs": prefix_receipt["judged_docs"],
             "capped_out": prefix_receipt["capped_out"], "prefix_docs": prefix_receipt["docs"],
             "final_detail": [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "rerank_score": c.rerank_score,
                               "arrivals": list(c.arrivals), "query_ids": list(c.query_ids)} for c in final]}
    return final, trace
