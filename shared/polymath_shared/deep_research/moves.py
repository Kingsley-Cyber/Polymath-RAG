"""DEEP-RESEARCH-MODE-V1 §10 (slice DR6a): research moves. Every planned search is one of four MOVES, and this small
controller picks each plan's mix from the question's intent and what the run has found so far:

    broad     another part of the question
    deep      drill into a strong finding
    adjacent  nearby ideas that connect
    inverse   limits, exceptions, failure cases, critiques, opposite cases

Pure and deterministic: no I/O, no model call, no clock. The question's intent is `query_intent.classify_intent` (a regex
classifier, no LLM); everything else is arithmetic on counts the engine hands in, so the same run always gets the same mix.
The engine owns WHEN the controller is asked; the route owns WHERE each move searches (§10.1).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from fractions import Fraction

MOVES = ("broad", "deep", "adjacent", "inverse")
BROAD, DEEP, ADJACENT, INVERSE = MOVES
#: §10.3 starting weights (broad, deep, adjacent, inverse) per canonical intent (query_intent.INTENTS)
INTENT_WEIGHTS: dict[str, tuple[int, int, int, int]] = {
    "EXACT": (1, 3, 0, 0), "DEFINITION": (1, 3, 0, 0),
    "MECHANISM": (1, 2, 0, 1), "PROCEDURE": (1, 2, 0, 1), "APPLICATION": (1, 2, 0, 1),
    "COMPARISON": (2, 0, 0, 2),
    "RELATIONSHIP": (1, 0, 3, 0),
    "SYNTHESIS": (2, 0, 2, 0), "EXPLORATORY": (2, 0, 2, 0),
    "RECALL": (2, 1, 1, 0),
}
#: a child starts from its parent's move: broad or deep → deep (today's meaning below level 1); adjacent → adjacent + deep;
#: inverse → inverse + deep (the parent's own move wins a single slot)
CHILD_WEIGHTS: dict[str, tuple[int, int, int, int]] = {
    BROAD: (0, 1, 0, 0), DEEP: (0, 1, 0, 0), ADJACENT: (0, 1, 2, 0), INVERSE: (0, 1, 0, 2)}
ONE_SIDED_INTENTS = frozenset({"MECHANISM", "PROCEDURE", "APPLICATION"})
REPEAT_SHARE = 0.5          # this share of a parent's rows already seen in the run → one slot moves from deep to adjacent
CONCENTRATION_DOCS = 2      # a parent's learnings citing rows of at most this many documents → its deep queries anchor there
ONE_SIDED_LEARNINGS = 3     # this many learnings so far, none from an inverse search → the richest child gets an inverse slot
DRY_LEVELS = 2              # a move searched on this many levels without a learning gets weight 0 for the rest of the run
#: a question asking for a judgement. Tuning after DR7f (live, 2026-09-27: "…is it useful for film actors?" planned no inverse
#: part): the words a judgement is asked in, kept narrow; "good" alone stays out ("What makes a good shot?" asks for none)
_EVALUATIVE = re.compile(
    r"\b(?:should|worth(?:while)?|best|does it work|is it true|effective(?:ness)?|pros and cons"
    r"|useful(?:ness)?|helpful|valuable|recommend(?:ed|ation)?|good idea|any good|is it good|(?:better|worse) than"
    r"|reliable|trustworthy|overrated|underrated|works? well)\b", re.IGNORECASE)
_INVERSE = MOVES.index(INVERSE)
_DEEP = MOVES.index(DEEP)
_ADJACENT = MOVES.index(ADJACENT)


def question_intent(question: str) -> str:
    """The question's canonical intent (deterministic; imported late so a moves-off run never loads the classifier)."""
    from polymath_shared.query_intent import classify_intent
    intent = classify_intent(question)
    return intent if intent in INTENT_WEIGHTS else "EXPLORATORY"


def is_evaluative(question: str) -> bool:
    """A question that asks for a judgement gets one inverse slot on every level. The words: "should", "worth(while)",
    "best", "does it work", "is it true", "effective(ness)", "pros and cons", "useful(ness)", "helpful", "valuable",
    "recommend(ed)", "recommendation", "good idea", "any good", "is it good", "better than", "worse than", "reliable",
    "trustworthy", "overrated", "underrated", "work well", "works well". "good" alone is not one."""
    return bool(_EVALUATIVE.search(question or ""))


def default_move(level: int) -> str:
    """A plan line without a MOVE (or with an unknown one): broad at level 1, deep below (today's meaning)."""
    return BROAD if level <= 1 else DEEP


def allocate(weights: Sequence[float], n: int) -> tuple[int, ...]:
    """n slots split by weight: floors first, then the largest remainders (ties in MOVES order). Always sums to n; no
    positive weight at all = equal weights. Exact arithmetic, so the same weights always give the same split."""
    ws = [max(Fraction(w), Fraction(0)) for w in weights]
    if n <= 0:
        return tuple(0 for _ in ws)
    total = sum(ws, Fraction(0))
    if total == 0:
        ws, total = [Fraction(1)] * len(ws), Fraction(len(ws))
    exact = [n * w / total for w in ws]
    counts = [int(q) for q in exact]
    for i in sorted(range(len(ws)), key=lambda i: (-(exact[i] - counts[i]), i))[: n - sum(counts)]:
        counts[i] += 1
    return tuple(counts)


def _live(weights: Sequence[int], dry: Iterable[str]) -> tuple[int, ...]:
    """The weights with every dry move at 0; if that leaves nothing, the moves that are not dry, equally; then as given."""
    dry = set(dry)
    live = tuple(0 if m in dry else w for m, w in zip(MOVES, weights))
    if any(live):
        return live
    even = tuple(0 if m in dry else 1 for m in MOVES)
    return even if any(even) else tuple(weights)


def with_inverse(quota: Sequence[int]) -> tuple[int, ...]:
    """The quota with at least one inverse slot, taken from deep, else from the move holding the most (ties: the later
    move, so broad keeps the question's own coverage longest)."""
    q = list(quota)
    if q[_INVERSE] > 0 or not any(q):
        return tuple(q)
    src = _DEEP if q[_DEEP] > 0 else max((j for j in range(len(q)) if j != _INVERSE), key=lambda j: (q[j], j))
    q[src] -= 1
    q[_INVERSE] += 1
    return tuple(q)


def root_quota(intent: str, n: int, *, evaluative: bool) -> tuple[int, ...]:
    """Level 1: the intent's weights over the question's own breadth; an evaluative question reserves an inverse slot."""
    quota = allocate(INTENT_WEIGHTS.get(intent, INTENT_WEIGHTS["EXPLORATORY"]), n)
    return with_inverse(quota) if evaluative else quota


def child_quota(parent_move: str, n: int, *, repeat: bool, dry: Iterable[str] = ()) -> tuple[int, ...]:
    """Level ≥ 2: the parent's move sets the mix (dry moves at 0); a repeating parent moves one slot from deep to adjacent."""
    dry = set(dry)
    q = list(allocate(_live(CHILD_WEIGHTS.get(parent_move, CHILD_WEIGHTS[DEEP]), dry), n))
    if repeat and q[_DEEP] > 0 and ADJACENT not in dry:
        q[_DEEP] -= 1
        q[_ADJACENT] += 1
    return tuple(q)


def is_repeat(parent_rows: Sequence[str], seen: set[str]) -> bool:
    """At least REPEAT_SHARE of the parent's rows were already seen in the run (before it, in plan order)."""
    rows = set(parent_rows)
    return bool(rows) and len(rows & seen) >= REPEAT_SHARE * len(rows)


def concentration_anchors(cited_docs: Sequence[str]) -> tuple[str, ...]:
    """The documents a parent's learnings cite, first citation first, when they are 1..CONCENTRATION_DOCS; else none. A
    cited row without a document id leaves the spread unknown, so nothing is anchored."""
    docs = tuple(dict.fromkeys(cited_docs))
    if not docs or "" in docs or len(docs) > CONCENTRATION_DOCS:
        return ()
    return docs


def is_one_sided(intent: str, evaluative: bool, learning_moves: Sequence[str]) -> bool:
    """≥ ONE_SIDED_LEARNINGS learnings so far, none from an inverse search, on a question that should be tested."""
    return (len(learning_moves) >= ONE_SIDED_LEARNINGS and INVERSE not in learning_moves
            and (evaluative or intent in ONE_SIDED_INTENTS))
