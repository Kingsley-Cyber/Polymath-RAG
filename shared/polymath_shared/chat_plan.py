"""CHAT-INTENT-PLAN-V1 — the conversation-aware query compiler
(CHAT-QUERY-COMPILER-PLAN §3.1–§3.2, phase P0.b shadow → P0.c on).

One cheap, bounded LLM call turns (message, recent history) into a
machine-readable plan: what the user actually wants (resolved_request),
what kind of task it is, whether retrieval is needed, and 1–4 typed search
queries with exact terms preserved verbatim from the original input.

Laws (each has a regression in tests/determinism/test_chat_compiler.py):
  1. The compiler never rewrites the TASK: original_request and
     resolved_request both travel to synthesis; queries are search
     representations only. A plan whose resolved request drops the task
     class of the original is rejected → fallback.
  2. Bounded and cheap: ≤ COMPILER_MAX_OUTPUT_TOKENS, ≤ COMPILER_BUDGET_S.
  3. Deterministic fallback = today's behavior (GROUNDED_QA, retrieval
     required, PRIMARY = the raw message), flagged `fallback: true` with a
     reason; the fallback rate is a receipted number.
  4. Two query representations: semantic_queries (dense) and exact_terms
     (sparse), never one string doing both jobs.
This module is deterministic policy + validation; the only I/O is the
injected `complete(system_prompt, user_prompt, max_tokens) -> (text, err)`.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable

from polymath_shared.query_constraints import Constraint, detect_explicit_constraints
from polymath_shared.query_intent import intent_of_plan

CONTRACT = "chat-intent-plan-v1"
#: S4 (DOCUMENT-RAG-COMPLETION-V1 Part B, flag POLYMATH_CHAT_COMPILER_CONTRACT, default off): the grounded-learning plan —
#: the learning need, each request's expected contribution + evidence requirement, the inquiry dimensions, synthesis
#: targets, and the concept bridges written in the SAME call from the profile matches (D5). Off = the v1 contract, byte-identical.
CONTRACT_V2 = "chat-intent-plan-v2"
CONTRACT_FLAG = "POLYMATH_CHAT_COMPILER_CONTRACT"
#: v2 carries more fields (≈ +400 output tokens measured on the owner's questions); the v1 budget stays for v1
COMPILER_MAX_OUTPUT_TOKENS_V2 = int(os.environ.get("POLYMATH_CHAT_COMPILER_MAX_TOKENS_V2", "1100"))
INQUIRY_DIMENSIONS = ("precision", "depth", "transfer", "synthesis")
MAX_SYNTHESIS_TARGETS = 3
MAX_PLAN_BRIDGES = 3
MAX_PROFILE_MATCHES = 8                          # = bridge_integration.MAX_CONCEPTS: the admission's concept window
COMPILER_STAGE = "chat_compiler"                 # stage pin in config/cloud_providers.json
COMPILER_BUDGET_S = float(os.environ.get("POLYMATH_CHAT_COMPILER_BUDGET_S", "2.5"))       # soft: the p50 gate
COMPILER_HARD_BUDGET_S = float(os.environ.get("POLYMATH_CHAT_COMPILER_HARD_BUDGET_S", "8.0"))  # hard: give up → fallback (8 s: backup lanes plan in 3.5–5.3 s)
COMPILER_MAX_OUTPUT_TOKENS = int(os.environ.get("POLYMATH_CHAT_COMPILER_MAX_TOKENS", "600"))
HISTORY_TURNS = int(os.environ.get("POLYMATH_CHAT_COMPILER_HISTORY_TURNS", "8"))
HISTORY_CHARS_PER_TURN = 1500
MAX_QUERIES = 4
MAX_QUERY_WORDS = 32

TASK_TYPES = ("GROUNDED_QA", "GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE",
              "TRANSFORM_USER_CONTENT", "CONTINUE_PRIOR_ARTIFACT", "GENERAL_CONVERSATION")
EVIDENCE_POLICIES = ("corpus_grounded", "conversation", "mixed")
QUERY_TYPES = ("PRIMARY", "DEFINITION", "MECHANISM", "CAUSAL", "COMPARISON", "COUNTERPOINT",
               "PROCEDURE", "EXAMPLE", "ENTITY", "BRIDGE",
               # B9 BREADTH-V1 (2026-09-06): the adjacent-knowledge aspect — the underlying principle in domain-neutral words
               "ADJACENT")
ADJACENT_MAX = 1                       # at most one per plan; it takes the seats an aspect gets, never more
ADJACENT_TASKS = ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")   # never for identifier lookups / plain factual QA
RESPONSE_TYPES = ("answer", "artifact")
NO_RETRIEVAL_TASKS = ("TRANSFORM_USER_CONTENT", "CONTINUE_PRIOR_ARTIFACT", "GENERAL_CONVERSATION")

#: SUBQUERY-PROVENANCE-V1 (librarian P6). Every subquery carries a `role` — WHY it exists
#: relative to q0 — drawn from this closed vocabulary. `direct` is q0 itself; `resolution` is
#: reserved for a subquery a P10 evidence-resolution round generates. The role is a
#: deterministic function of the query `type` (below) unless the planner supplies one explicitly.
ROLE_TYPES = ("direct", "prerequisite", "complement", "bridge", "contrast", "inversion", "resolution")
#: SUBQUERY-PROVENANCE-V1 / P10 — where a subquery CAME FROM (checklist retrieval-trace row).
#: q0 and its aspect decomposition are USER; a scout-inspired subquery is PROFILE; a graph-derived
#: target is GRAPH; a claim-gap resolution query (P10) is EVIDENCE_GAP; a WLK2C concept-bridge
#: (bounded compiler) is BRIDGE; a wildcard-frontier bridge is WILDCARD; a CORPUS-EXPLORER-V1
#: concept-activation-derived bridge is CORPUS_EXPLORE (distinct from Scout-derived BRIDGE so it can be
#: observed/A-B'd/gated separately). MUST stay in this tuple — CompiledQuery.__post_init__ coerces an
#: unknown origin to USER, which would wrongly pull the lane's chunks into CA4's answerability set.
ORIGIN_TYPES = ("USER", "PROFILE", "GRAPH", "EVIDENCE_GAP", "BRIDGE", "WILDCARD", "CORPUS_EXPLORE")
_TYPE_ROLE = {
    "PRIMARY": "direct", "DEFINITION": "prerequisite", "MECHANISM": "complement",
    "CAUSAL": "complement", "PROCEDURE": "complement", "EXAMPLE": "complement",
    "ENTITY": "complement", "COMPARISON": "contrast", "COUNTERPOINT": "inversion",
    "BRIDGE": "bridge", "ADJACENT": "bridge",
}


def derive_role(qtype: str) -> str:
    """Deterministic query-type → provenance role. Unknown types are `complement`
    (a supplementary aspect), never `direct` — only a PRIMARY query is q0."""
    return _TYPE_ROLE.get((qtype or "").strip().upper(), "complement")


def default_reason(qtype: str, role: str) -> str:
    """Deterministic default lineage reason for a subquery of this type/role."""
    qt = (qtype or "PRIMARY").strip().upper()
    if qt == "PRIMARY":
        return "q0: authoritative user query"
    return f"aspect:{qt.lower()} ({role})"

#: instruction vocabulary that must never appear in a search query
_INSTRUCTION_TOKENS = ("tone", "format", "markdown", "bullet", "json", "respond", "output", "word count",
                       "words long", "paragraphs", "headings", "table of", "step 1", "step 2", "you are an",
                       "act as", "write in", "use a", "do not", "don't", "please", "make sure")

#: task classes (verb families) the compiler must preserve (law 1)
_TASK_CLASSES = {
    "compare": ("compare", "contrast", "versus", " vs ", "agree", "disagree", "differ", "difference", "similar"),
    "list": ("list", "enumerate", "all the", "every ", "each of"),
    "decide": ("should i", "which is better", "choose", "recommend", "decide", "pick"),
    "rewrite": ("rewrite", "improve", "make this", "make it", "make my", " better", "tighten", "polish", "refine", "edit this", "stronger", "enhance", "upgrade"),
    "create": ("create", "build", "write me", "draft", "design", "generate", "produce", "make a", "give me a"),
    "explain": ("why", "how does", "how do", "explain", "what is", "what does", "what are", "define"),
    "summarize": ("summarize", "summarise", "tl;dr", "overview", "recap"),
    "continue": ("final version", "final prompt", "the final", "continue", "finish", "complete it", "next part"),
    "convert": ("convert", "turn this into", "as yaml", "as json", "as a table", "translate"),
}

_S_EXACT = re.compile(r"""
    \b[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)*\b       # acronyms / identifiers: RAPO, FACS, TS410, CVE-2026
  | \b(?:CVE|RFC|ISO|IEEE)-?\d[\d-]*\b
  | "([^"]{2,60})"                            # quoted phrases
  | “([^”]{2,60})”
  | \b\d+(?:\.\d+)?(?:mm|ms|fps|px|k|K|GB|MB|%)\b
""", re.X)


@dataclass
class CompiledQuery:
    id: str
    type: str
    query: str
    weight: float = 1.0
    #: SUBQUERY-PROVENANCE-V1 (P6) — additive lineage; every field defaults so all existing
    #: construction sites keep working. `role`/`reason` are DERIVED from `type` at construction
    #: when not supplied. `inspired_by_profile` (scouted doc_ids) / `profile_surface` are
    #: populated ONLY by subquery_provenance.annotate_subquery_provenance, which validates every
    #: link against the scout's real nominations and never touches q0. `target` = the
    #: information need this subquery localizes (planner-supplied; never fabricated).
    #: E7 (DOCUMENT-RAG-COMPLETION-V1 Part B): `derived_from` = the reference this subquery was derived
    #: from (a profile concept key, a nominated doc id, a gap claim id). References never go in `target`.
    role: str = ""
    reason: str = ""
    inspired_by_profile: list[str] = field(default_factory=list)   # JSON-native (never a tuple: receipts round-trip through JSON)
    profile_surface: str | None = None
    target: str | None = None
    derived_from: str | None = None
    origin: str = "USER"
    #: S4 (Part B): the request's purpose — "could help understand X because Y" — and the source evidence that would support
    #: it. Hypotheses carried into admission and synthesis, never verdicts. None = unexplained (never invented).
    expected_contribution: str | None = None
    evidence_requirement: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inspired_by_profile, list):
            self.inspired_by_profile = list(self.inspired_by_profile)
        if not self.role:
            self.role = derive_role(self.type)
        if not self.reason:
            self.reason = default_reason(self.type, self.role)
        if self.origin not in ORIGIN_TYPES:
            self.origin = "USER"


@dataclass
class ChatPlan:
    contract: str
    original_request: str
    resolved_request: str
    task_type: str
    evidence_policy: str
    retrieval_required: bool
    retrieval_goal: str | None
    queries: list[CompiledQuery]
    semantic_queries: list[str]
    exact_terms: list[str]
    entities: list[str]
    must_answer: list[str]
    user_constraints: list[str]
    response_type: str
    antecedent: dict | None
    graph_useful: bool
    #: FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §5: the canonical query intent, DERIVED
    #: deterministically from the fields above (no new classifier LLM). Set at construction.
    intent: str = ""
    compiler: dict = field(default_factory=dict)
    #: CONSTRAINT-AWARE-RETRIEVAL-V1 (CA0): explicit source constraints stated in q0
    #: (deterministic detection; SOURCE-only in V1). Additive — defaults empty so every
    #: construction site keeps working; populated after construction from original_request.
    explicit_constraints: list[Constraint] = field(default_factory=list)
    #: S4 (Part B): the inquiry dimensions that apply ({precision, depth, transfer, synthesis} → one short clause each) and
    #: the questions the answer must explain / connect / reconcile — outcomes open. Empty on the v1 contract.
    inquiry: dict = field(default_factory=dict)
    synthesis_targets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @property
    def fallback(self) -> bool:
        return bool(self.compiler.get("fallback"))


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def task_classes(text: str) -> set[str]:
    t = " " + (text or "").lower() + " "
    return {k for k, needles in _TASK_CLASSES.items() if any(n in t for n in needles)}


def exact_terms_from(text: str) -> list[str]:
    """Identifiers, acronyms, quoted phrases, unit-bearing numbers — verbatim,
    order of first appearance, deduped, ≤ 12."""
    out: list[str] = []
    for m in _S_EXACT.finditer(text or ""):
        term = (m.group(1) or m.group(2) or m.group(0)).strip()
        if len(term) < 2 or term.upper() in ("I", "A", "OK", "AI", "TV", "US", "UK", "PM", "AM", "THE", "AND"):
            continue
        if term not in out:
            out.append(term)
        if len(out) >= 12:
            break
    return out


def _clean_query(q: str) -> str:
    q = re.sub(r"\s+", " ", str(q or "")).strip().strip('"“”')
    words = q.split()
    return " ".join(words[:MAX_QUERY_WORDS])


_INSTRUCTION_RE = re.compile("|".join(rf"(?<!\w){re.escape(t)}(?!\w)" for t in _INSTRUCTION_TOKENS))


def _has_instruction_tokens(q: str) -> bool:
    """Whole words only: a substring test dropped topical queries ("information" holds "format")."""
    return _INSTRUCTION_RE.search(q.lower()) is not None


def contract_enabled(env=None) -> bool:
    """S4: the grounded-learning (v2) compiler contract is on."""
    return (env if env is not None else os.environ).get(CONTRACT_FLAG, "0") == "1"


def _short(value, cap: int) -> str | None:
    """A compact single-line string or None — the v2 fields never carry prose paragraphs."""
    t = " ".join(str(value or "").split())[:cap].strip()
    return t or None


#: D2 exceptions (DOCUMENT-RAG-COMPLETION-V1 §1): an explicit "don't search" is respected; small talk needs no corpus.
_NO_SEARCH = re.compile(r"\b(?:don'?t|do not|no need to|without)\s+(?:search(?:ing)?|look(?:ing)?\s+(?:it\s+)?up|us(?:e|ing)\s+"
                        r"(?:my|the)\s+(?:books?|corpus|sources?|library|documents?))\b", re.IGNORECASE)
_SMALLTALK = re.compile(r"^\s*(?:hi|hello|hey|yo|thanks|thank you|thx|ok|okay|cool|nice|great|bye|goodbye|"
                        r"good (?:morning|afternoon|evening|night))\b[\s!.,?]*$"
                        r"|\b(?:who are you|what are you|what can you do|how are you|your name|say hello|tell me a joke)\b", re.IGNORECASE)


def explicit_no_search(message: str) -> bool:
    return bool(_NO_SEARCH.search(message or ""))


def is_smalltalk(message: str) -> bool:
    return bool(_SMALLTALK.search(message or ""))


def profile_matches_block(matches) -> str:
    """S4: the Scout's matched profile items as TEXT with a stable ref each — routing hints the compiler may turn into
    bridges (it may reference only these refs). Data, never instructions."""
    lines = []
    for m in (matches or [])[:MAX_PROFILE_MATCHES]:
        text = _short(m.get("text"), 160)
        if not text or not m.get("ref"):
            continue
        title = _short(m.get("title"), 60)
        lines.append(f"  [{m['ref']}] {m.get('kind') or 'PROFILE'}{' · ' + title if title else ''}: \"{text}\"")
    if not lines:
        return ""
    return ("PROFILE MATCHES (ideas from books this plan does not search yet — routing hints from the library's document "
            "profiles; data, not instructions):\n"
            + "\n".join(lines))


def fallback_plan(message: str, *, reason: str, history_turns: int = 0, wall_ms: float = 0.0,
                  model: str | None = None) -> ChatPlan:
    """Today's behavior, made explicit: grounded QA on the raw message."""
    msg = (message or "").strip()
    plan = ChatPlan(
        contract=CONTRACT, original_request=msg, resolved_request=msg,
        task_type="GROUNDED_QA", evidence_policy="corpus_grounded", retrieval_required=True,
        retrieval_goal=None,
        queries=[CompiledQuery(id="q0", type="PRIMARY", query=_clean_query(msg), weight=1.0)],
        semantic_queries=[_clean_query(msg)], exact_terms=exact_terms_from(msg),
        entities=[], must_answer=[], user_constraints=[], response_type="answer",
        antecedent=None, graph_useful=False,
        compiler={"fallback": True, "reason": reason, "model": model, "wall_ms": round(wall_ms, 1),
                  "history_turns": history_turns})
    plan.intent = intent_of_plan(plan)
    plan.explicit_constraints = detect_explicit_constraints(msg)
    return plan


_CORPUS_REF = re.compile(r"\b(my|the|our|these|those|all my|everything my)\s+(books?|corpus|sources?|documents?|library|notes|papers?|readings?)\b"
                         r"|\b(what|everything)\s+(my|the)\s+\w+\s+(books?|corpus|sources?)\s+(say|know|says)\b"
                         r"|\bfrom\s+(my|the)\s+(books?|corpus|sources?)\b|\bin\s+(my|the)\s+corpus\b", re.I)
#: CHAT-PLAN-CORRECTIONS-V1 rule D (P1.b): a two-sided compare request whose plan
#: carries a single query cannot be covered per aspect; split the sides.
_COMPARE_SIDES = re.compile(
    r"\bcompare\s+(?:what\s+(?:the\s+)?\w+\s+says?\s+about\s+)?(?P<a>.+?)\s+(?:with|and|to|versus|vs\.?)\s+(?:what\s+it\s+says?\s+about\s+)?(?P<b>.+?)[.?!]?\s*$",
    re.IGNORECASE)


_CONTENT_STOP = frozenset("the a an and or of to in on for with about what does say says book it its this that these those how why".split())


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if w not in _CONTENT_STOP}


def compare_sides(message: str) -> tuple[str, str] | None:
    m = _COMPARE_SIDES.search((message or "").strip())
    if not m:
        return None
    a, b = m.group("a").strip(" ,;:"), m.group("b").strip(" ,;:")
    if len(a) < 3 or len(b) < 3 or a.lower() == b.lower():
        return None
    return a, b


_FINAL_REF = re.compile(r"\b(final|finished|complete[d]?|latest|updated)\s+(version|prompt|draft|one|answer|copy)\b"
                        r"|\bwhat'?s the final\b|\bgive me the final\b|\bthe final\b", re.I)


def references_corpus(message: str) -> bool:
    """The user explicitly asked to use their books / corpus / sources."""
    return bool(_CORPUS_REF.search(message or ""))


def references_prior_artifact(message: str, history: Iterable | None) -> bool:
    """'the final prompt', 'give me the final version' with an assistant turn
    to refer back to."""
    if not _FINAL_REF.search(message or ""):
        return False
    for h in list(history or []):
        role = getattr(h, "role", None) or (h.get("role") if isinstance(h, dict) else None)
        if role == "assistant":
            return True
    return False


_TRAILING_FUNCTION_WORDS = {"in", "of", "for", "on", "about", "the", "a", "an", "to", "and", "with", "from", "within", "at", "by"}


def _conversation_text(message: str, history: Iterable | None) -> str:
    parts = [message or ""]
    for h in list(history or []):
        parts.append(str(getattr(h, "content", None) or (h.get("content") if isinstance(h, dict) else "") or ""))
    return " ".join(parts).lower()


def _strip_corpus_scope_terms(plan: "ChatPlan", message: str, history: Iterable | None,
                              corpus_ids: Iterable[str] | None) -> list[str]:
    """Correction C: remove corpus-id tokens the conversation never used from
    every query (and semantic query); trailing function words left behind
    ("sound editing in") are trimmed. A query is never emptied."""
    fixes: list[str] = []
    convo = _conversation_text(message, history)
    for cid in (c for c in (corpus_ids or []) if c):
        tok = str(cid).strip().lower()
        if len(tok) < 3 or tok in convo:
            continue
        pat = re.compile(rf"(?<![\w-]){re.escape(tok)}(?![\w-])", re.IGNORECASE)

        def _clean(text: str) -> str:
            out = re.sub(r"\s+", " ", pat.sub(" ", text)).strip(" ,;:-")
            words = out.split()
            while len(words) > 1 and words[-1].lower() in _TRAILING_FUNCTION_WORDS:
                words.pop()
            while len(words) > 1 and words[0].lower() in _TRAILING_FUNCTION_WORDS:
                words.pop(0)
            return " ".join(words)

        for q in plan.queries:
            new = _clean(q.query)
            if new and new != q.query:
                fixes.append(f"corpus_scope_term:{tok}:{q.id}")
                q.query = new
        plan.semantic_queries = [(_clean(x) or x) for x in (plan.semantic_queries or [])]
    return fixes


def apply_corrections(plan: "ChatPlan", message: str, history: Iterable | None,
                      corpus_ids: Iterable[str] | None = None) -> list[str]:
    """CHAT-PLAN-CORRECTIONS-V1: lane-independent rules that fix the two
    confusions measured on 2026-09-05 (a cross-family lane swapped
    CREATE_FROM_KNOWLEDGE and CONTINUE_PRIOR_ARTIFACT on 2 of 6 fixtures):
      A. an explicit corpus reference forces retrieval and forbids the
         no-retrieval task types (→ CREATE_FROM_KNOWLEDGE when the request
         builds/improves something, else GROUNDED_SYNTHESIS);
      B. 'the final version/prompt' with an assistant turn to refer to and
         NO corpus reference is a continuation: no retrieval.
      C. (P0.c) a corpus id is retrieval SCOPE, never a query term: when the
         conversation itself never says it, the token is stripped from every
         query ("sound editing in cinema" → "sound editing"); measured on
         2026-09-05: 8/30 single-turn and 9/30 follow-up compiled queries had
         the corpus id injected, and both follow-up-only misses carried it.
    Every applied rule is recorded in plan.compiler['corrections']."""
    fixes: list[str] = []
    msg = message or ""
    fixes.extend(_strip_corpus_scope_terms(plan, msg, history, corpus_ids))
    sides = compare_sides(msg)
    if sides and plan.retrieval_required:
        # rule D: each side of a two-sided compare gets a query that names IT and not the other side
        a, b = sides
        wa, wb = _content_words(a), _content_words(b)

        def _names_only(q: "CompiledQuery", mine: set, other: set) -> bool:
            wq = _content_words(q.query)
            return bool(wq & mine) and not (wq & other - mine)
        has_a = any(_names_only(q, wa, wb) for q in plan.queries)
        has_b = any(_names_only(q, wb, wa) for q in plan.queries)
        if not (has_a and has_b):
            primary = _clean_query(a)
            second = _clean_query(b)
            if primary and second:
                keep = [q for q in plan.queries if q.type != "PRIMARY" and not (_content_words(q.query) & wa and _content_words(q.query) & wb)]
                rebuilt = [CompiledQuery(id="q0", type="PRIMARY", query=primary, weight=1.0),
                           CompiledQuery(id="q1", type="COMPARISON", query=second, weight=1.0)]
                for i, q in enumerate(keep):
                    if len(rebuilt) >= MAX_QUERIES:
                        break
                    rebuilt.append(CompiledQuery(id=f"q{len(rebuilt)}", type=q.type, query=q.query, weight=q.weight))
                fixes.append(f"compare_sides:{len(plan.queries)}->{len(rebuilt)}")
                plan.queries = rebuilt
                plan.semantic_queries = [q.query for q in rebuilt]
    if references_corpus(msg):
        if not plan.retrieval_required or plan.task_type in NO_RETRIEVAL_TASKS:
            new_type = "CREATE_FROM_KNOWLEDGE" if (task_classes(msg) & {"create", "rewrite", "continue", "convert"}) else "GROUNDED_SYNTHESIS"
            fixes.append(f"corpus_reference:{plan.task_type}->{new_type}")
            plan.task_type = new_type
            plan.evidence_policy = "corpus_grounded"
            plan.retrieval_required = True
            if plan.response_type == "answer" and new_type == "CREATE_FROM_KNOWLEDGE":
                plan.response_type = "artifact"
            if not plan.queries:
                seed = _clean_query(plan.resolved_request or msg)
                plan.queries = [CompiledQuery(id="q0", type="PRIMARY", query=seed, weight=1.0)]
                plan.semantic_queries = plan.semantic_queries or [seed]
    elif references_prior_artifact(msg, history) and plan.task_type in ("CREATE_FROM_KNOWLEDGE", "GROUNDED_SYNTHESIS", "GROUNDED_QA"):
        fixes.append(f"prior_artifact:{plan.task_type}->CONTINUE_PRIOR_ARTIFACT")
        plan.task_type = "CONTINUE_PRIOR_ARTIFACT"
        plan.evidence_policy = "conversation"
        plan.retrieval_required = False
        plan.queries = []
        plan.response_type = "artifact"
    return fixes


def validate_plan(raw: dict, message: str, *, contract: bool = False,
                  matches=None) -> tuple[ChatPlan | None, str | None]:
    """Strict contract check + law 1. Returns (plan, None) or (None, reason).

    `contract` (S4, v2): the grounded-learning fields are read — every one optional; a missing one marks context as
    missing (a request without an expected contribution is `unexplained`), never skips retrieval — plus D2 (a knowledge
    question always retrieves; small talk and an explicit "don't search" are the exceptions) and the concept bridges,
    each admitted only when its `ref` names one of the supplied `matches` (never an invented concept)."""
    if not isinstance(raw, dict):
        return None, "not_an_object"
    resolved = str(raw.get("resolved_request") or "").strip()
    if len(resolved) < 8:
        return None, "resolved_request_missing"
    task = str(raw.get("task_type") or "").strip().upper()
    if task not in TASK_TYPES:
        return None, f"task_type_invalid:{task[:24]}"
    policy = str(raw.get("evidence_policy") or "").strip().lower()
    if policy not in EVIDENCE_POLICIES:
        policy = "conversation" if task in NO_RETRIEVAL_TASKS else "corpus_grounded"
    rr = raw.get("retrieval_required")
    if not isinstance(rr, bool):
        rr = task not in NO_RETRIEVAL_TASKS
    if task in NO_RETRIEVAL_TASKS and policy == "conversation":
        rr = False
    d2_override = no_search = False
    retyped = 0
    compares = "compare" in task_classes(message or "")
    if contract:
        if explicit_no_search(message):
            no_search = True
        elif task == "GENERAL_CONVERSATION" and not is_smalltalk(message):
            task, policy, d2_override = "GROUNDED_QA", "corpus_grounded", True     # D2: always retrieve
    if task in ("GROUNDED_QA", "GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE"):
        rr = True
    if no_search:
        rr = False                                                              # D2: an explicit "don't search" wins
    queries: list[CompiledQuery] = []
    explicit_roles: set[int] = set()               # P6: id()s whose role the planner set explicitly
    explicit_reasons: set[int] = set()             # P6: id()s whose reason the planner set explicitly
    for i, q in enumerate(raw.get("queries") or []):
        if not isinstance(q, dict):
            continue
        text = _clean_query(q.get("query"))
        if not text or _has_instruction_tokens(text):
            continue
        qtype = str(q.get("type") or "PRIMARY").strip().upper()
        if qtype not in QUERY_TYPES:
            qtype = "PRIMARY" if i == 0 else "MECHANISM"
        if contract and qtype in ("COMPARISON", "COUNTERPOINT") and not compares:
            qtype, retyped = "MECHANISM", retyped + 1     # S4: an unasked comparison type flips the turn's intent to COMPARISON
        try:
            weight = float(q.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        # P6: the planner MAY supply provenance when scout context was injected; validated here,
        # trusted only after annotate_subquery_provenance checks links against real nominations.
        role_in = str(q.get("role") or "").strip().lower()
        role_in = role_in if role_in in ROLE_TYPES else ""
        reason_in = str(q.get("reason") or "").strip()[:200]
        ib = q.get("inspired_by") if isinstance(q.get("inspired_by"), (list, tuple)) else q.get("inspired_by_profile")
        inspired = [str(x).strip() for x in ib if str(x).strip()][:8] if isinstance(ib, (list, tuple)) else []
        surface_in = q.get("profile_surface")
        target_in = q.get("target")
        origin_in = str(q.get("origin") or "").strip().upper()
        cq = CompiledQuery(
            id=f"q{len(queries)}", type=qtype, query=text, weight=max(0.1, min(1.0, weight)),
            role=role_in, reason=reason_in, inspired_by_profile=inspired,
            profile_surface=(str(surface_in).strip()[:80] or None) if surface_in else None,
            target=(str(target_in).strip()[:160] or None) if target_in else None,
            origin=origin_in if origin_in in ORIGIN_TYPES else "USER",
            expected_contribution=_short(q.get("expected_contribution"), 240) if contract else None,
            evidence_requirement=_short(q.get("evidence_requirement"), 200) if contract else None)
        queries.append(cq)
        if role_in:
            explicit_roles.add(id(cq))
        if reason_in:
            explicit_reasons.add(id(cq))
        if len(queries) >= MAX_QUERIES:
            break
    if rr:
        if not queries and d2_override:                     # D2: the model saw no search; the question gets one anyway
            queries = [CompiledQuery(id="q0", type="PRIMARY", query=_clean_query(message), weight=1.0)]
        if not queries:
            return None, "no_queries_for_retrieval"
        adj = [q for q in queries if q.type == "ADJACENT"]
        if adj and task not in ADJACENT_TASKS:            # B9: never widen an identifier lookup or plain QA
            queries = [q for q in queries if q.type != "ADJACENT"] or queries
        elif len(adj) > ADJACENT_MAX:
            for q in adj[ADJACENT_MAX:]:
                q.type = "MECHANISM"
        if sum(1 for q in queries if q.type == "PRIMARY") != 1:
            queries[0].type = "PRIMARY"
            for q in queries[1:]:
                if q.type == "PRIMARY":
                    q.type = "MECHANISM"
        # P6: role/reason follow the FINAL type after the normalization above, unless the
        # planner set them explicitly (a type flip must not leave a stale role).
        for q in queries:
            if id(q) not in explicit_roles:
                q.role = derive_role(q.type)
            if id(q) not in explicit_reasons:
                q.reason = default_reason(q.type, q.role)
    else:
        queries = []
    # law 1: the task class of the original survives in the resolved request
    orig_classes = task_classes(message)
    if orig_classes and not (orig_classes & task_classes(resolved)):
        # an artifact continuation may legitimately be re-stated ("produce the final X")
        if not (task == "CONTINUE_PRIOR_ARTIFACT" and "create" in task_classes(resolved)):
            return None, f"task_rewritten:{sorted(orig_classes)[0]}"
    exact = [str(x).strip() for x in (raw.get("exact_terms") or []) if str(x).strip()]
    for t in exact_terms_from(message):                       # verbatim terms from the ORIGINAL always ride along
        if t not in exact:
            exact.append(t)
    sem = [_clean_query(x) for x in (raw.get("semantic_queries") or []) if _clean_query(x)] or [q.query for q in queries]
    def _strs(key, cap=12):
        return [str(x).strip() for x in (raw.get(key) or []) if str(x).strip()][:cap]
    resp = str(raw.get("response_type") or "").strip().lower()
    if resp not in RESPONSE_TYPES:
        resp = "artifact" if task in ("TRANSFORM_USER_CONTENT", "CONTINUE_PRIOR_ARTIFACT", "CREATE_FROM_KNOWLEDGE") else "answer"
    ant = raw.get("antecedent") if isinstance(raw.get("antecedent"), dict) else None
    plan = ChatPlan(contract=CONTRACT, original_request=(message or "").strip(), resolved_request=resolved,
                    task_type=task, evidence_policy=policy, retrieval_required=bool(rr),
                    retrieval_goal=(str(raw.get("retrieval_goal")).strip() or None) if raw.get("retrieval_goal") else None,
                    queries=queries, semantic_queries=sem[:MAX_QUERIES], exact_terms=exact[:16],
                    entities=_strs("entities"), must_answer=_strs("must_answer", 8), user_constraints=_strs("user_constraints", 8),
                    response_type=resp, antecedent=ant, graph_useful=bool(raw.get("graph_useful", False)))
    if contract:
        plan.contract = CONTRACT_V2
        _apply_contract_fields(plan, raw, matches, d2_override=d2_override, no_search=no_search, retyped=retyped)
    plan.intent = intent_of_plan(plan)
    plan.explicit_constraints = detect_explicit_constraints(message or "")
    return plan, None


def _apply_contract_fields(plan: ChatPlan, raw: dict, matches, *, d2_override: bool, no_search: bool,
                           retyped: int = 0) -> None:
    """S4 (v2): learning need → `retrieval_goal`; inquiry dimensions; synthesis targets; the concept bridges (validated
    against the supplied profile matches). Records what was missing on `plan._contract_diag` — merged into
    `plan.compiler["contract"]` by compile_plan; nothing is invented to fill a gap."""
    plan.retrieval_goal = _short(raw.get("learning_need"), 300) or plan.retrieval_goal
    inq = raw.get("inquiry") if isinstance(raw.get("inquiry"), dict) else {}
    plan.inquiry = {k: v for k in INQUIRY_DIMENSIONS if (v := _short(inq.get(k), 200)) and v.lower() not in ("null", "none", "n/a")}
    plan.synthesis_targets = [t for t in (_short(x, 200) for x in (raw.get("synthesis_targets") or [])) if t][:MAX_SYNTHESIS_TARGETS]
    by_ref = {str(m.get("ref")): m for m in (matches or []) if m.get("ref") and m.get("text")}
    proposed = [b for b in (raw.get("bridges") or []) if isinstance(b, dict)] if plan.retrieval_required else []
    grounded: list[dict] = []
    invented = 0
    for b in proposed:
        m = by_ref.get(str(b.get("ref") or "").strip())
        text = _clean_query(b.get("query"))
        if m is None or not text:
            invented += 1                                   # an invented ref or an empty query: never proposed onward
            continue
        if len(grounded) < MAX_PLAN_BRIDGES:
            # the retired bridge call's own output shape, so the SAME admission (bridge_integration) decides
            grounded.append({"bridge_id": f"br{len(grounded)}", "bridge_query": text,
                             "derived_from": str(m.get("doc_id") or ""),
                             "relation_to_q0": _short(b.get("expected_contribution"), 240) or "",
                             "proposed_role": "COMPLEMENTARY", "ref": str(m.get("ref")),
                             "expected_contribution": _short(b.get("expected_contribution"), 240),
                             "evidence_requirement": _short(b.get("evidence_requirement"), 200)})
    plan._plan_bridges = grounded                           # type: ignore[attr-defined] — admitted after profile expansion
    plan._contract_diag = {                                 # type: ignore[attr-defined] — receipt-only, merged by compile_plan
        "version": CONTRACT_V2, "learning_need": plan.retrieval_goal is not None,
        "inquiry": sorted(plan.inquiry), "synthesis_targets": len(plan.synthesis_targets),
        "unexplained": [q.id for q in plan.queries if q.origin == "USER" and not q.expected_contribution],
        "matches": len(by_ref),
        "bridges": {"proposed": len(proposed), "grounded": len(grounded), "dropped_invented": invented},
        "d2_override": d2_override, "no_search": no_search, "retyped_comparison": retyped}


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the QUERY COMPILER for a retrieval-augmented assistant. You do NOT answer the user.
You read the current message plus recent conversation and emit ONE JSON object describing what the user wants
and what, if anything, should be searched in their private corpus of books and documents.

Rules:
- resolved_request: the user's request as a standalone sentence, with pronouns and references ("that", "it",
  "the final one", "those") resolved from the conversation. NEVER change the task: if the user asks to compare,
  compare; to list, list; to rewrite their text, rewrite; to produce a final version, produce it.
- task_type: GROUNDED_QA (factual question about the corpus) | GROUNDED_SYNTHESIS (explain/analyze using the corpus)
  | CREATE_FROM_KNOWLEDGE (build something using corpus knowledge) | TRANSFORM_USER_CONTENT (rewrite/improve/convert
  text the user supplied) | CONTINUE_PRIOR_ARTIFACT (finish/return/refine something produced earlier in this
  conversation) | GENERAL_CONVERSATION (no corpus knowledge needed).
- retrieval_required: false for TRANSFORM_USER_CONTENT, CONTINUE_PRIOR_ARTIFACT and GENERAL_CONVERSATION unless the
  user explicitly asks to use their books/corpus/sources; true otherwise.
- queries: 1 to 4 SHORT search queries (topical content only — never tone, length, format or output instructions),
  each {"id","type","query","weight"}; exactly one type PRIMARY; other types from DEFINITION, MECHANISM, CAUSAL,
  COMPARISON, COUNTERPOINT, PROCEDURE, EXAMPLE, ENTITY, BRIDGE, ADJACENT. Empty when retrieval_required is false.
- ADJACENT: for task_type GROUNDED_SYNTHESIS or CREATE_FROM_KNOWLEDGE, ALWAYS include exactly ONE query of type
  ADJACENT (weight 0.6) — the question's underlying principle restated in domain-neutral words that OTHER books in
  the corpus would use: no names of the asked-about domain, no product or book names. A fight-camera question →
  {"id":"q2","type":"ADJACENT","query":"how a body communicates force and intent to an observer","weight":0.6};
  a green-screen lighting question → "even illumination of a large flat surface"; a comparison of two chapters →
  the principle the two share ("choosing a representation that preserves what the next stage needs"). Never for
  GROUNDED_QA, identifier lookups or definitions.
- The corpus name(s) named below are SCOPE, never query words: search "sound editing", not "sound editing in cinema".
- BOOKS IN THE LIBRARY (when listed): the titles the corpus actually holds, most relevant to this message first. Use
  their own terminology when it fits — a movement-analysis book in the list means an ADJACENT or MECHANISM query may
  say "effort, weight and timing of a strike" rather than a generic phrase — but NEVER put a title itself in a query,
  never invent books, and PRIMARY stays the user's own message. The list only informs vocabulary and scope.
- A follow-up such as "why does that matter?", "how does that work in practice?", "can you say more about that?" is
  discourse about the antecedent topic: the PRIMARY query is the antecedent topic itself (e.g. "sound editing") with
  NO added words like significance, importance, purpose, examples, in practice, practical application, overview.
- semantic_queries: the queries' texts rewritten for meaning; exact_terms: identifiers, acronyms, quoted phrases,
  product or model names copied VERBATIM from the user's words (never paraphrased).
- must_answer: the distinct dimensions a good answer must cover (≤ 6 short labels). user_constraints: explicit
  requirements on the deliverable. antecedent: {"turn": -N, "kind": "assistant_artifact"|"user_text"|"topic",
  "summary": "..."} when the request refers to earlier content, else null. graph_useful: true only when the
  question is about how several named things relate. response_type: "artifact" when the user wants a deliverable
  (prompt, program, table, code, plan), else "answer".
Disambiguation (the two most-confused types):
- "so what's the final prompt?" after the assistant drafted one, with no mention of books/corpus →
  CONTINUE_PRIOR_ARTIFACT, retrieval_required false, response_type artifact.
- "use everything my cinema books know about X to make this prompt better" → the user asked for CORPUS
  knowledge → CREATE_FROM_KNOWLEDGE, retrieval_required true, queries about X, response_type artifact.
- "turn this into a stronger prompt" with the text supplied in the message → TRANSFORM_USER_CONTENT, no retrieval.
- "do the authors agree or disagree about X?" → GROUNDED_SYNTHESIS with a COMPARISON query per side, plus the one
  ADJACENT query (the shared principle in neutral words).
- Every DISTINCT aspect of a compare / contrast / "X and Y" request gets its OWN typed query ("compare what the book
  says about X with what it says about Y" → PRIMARY about X, COMPARISON about Y) — never fold two topics into one query.
Output ONLY the JSON object. No prose, no markdown fences."""

#: S4 (v2 contract, DOCUMENT-RAG-COMPLETION-V1 Part B; the owner's "RAG compiler for grounded discovery"): the plan also
#: says WHY each request exists and WHAT would support it, and writes the concept bridges in this same call (D5).
CONTRACT_ADDENDUM = """
GROUNDED-LEARNING FIELDS (add these to the same JSON object; every added string is short — they cost time):
- learning_need: ONE sentence — what the user is trying to understand. Not a restatement of the question.
- Every query also carries "expected_contribution" (≤ 12 words: which part of the learning need it could explain) and
  "evidence_requirement" (≤ 8 words: what source text would support it). Hypotheses to check against the sources, never
  verdicts. "Related to the topic" is not a contribution.
- inquiry: {"precision": ..., "depth": ..., "transfer": ..., "synthesis": ...}, each ≤ 10 words or null: precision =
  the exact subject and the distinction that decides a correct answer; depth = a mechanism, assumption or competing
  explanation worth checking; transfer = a relationship that might carry over from another field; synthesis = what must
  be combined or reconciled across documents. A plain factual lookup or definition fills precision only.
- synthesis_targets: at most 3 short questions the answer must explain, connect or reconcile; [] for a plain factual
  lookup or definition. Never state their outcome.
- bridges: ONLY for GROUNDED_SYNTHESIS and CREATE_FROM_KNOWLEDGE, else []. At most 3 objects
  {"ref","query","expected_contribution","evidence_requirement"} built ONLY from the PROFILE MATCHES listed in the
  message: "ref" is one listed id; "query" is a distinct retrieval question (not a paraphrase of the question) that
  would surface that matched idea's material; "expected_contribution" says how that idea could help answer the
  question. Never invent a ref, a book or a concept. Use [] when no match helps.
- GENERAL_CONVERSATION is ONLY for greetings, thanks, small talk or questions about the assistant itself. Any question
  about a subject — even one you could answer from memory — is GROUNDED_QA with retrieval.
Output ONLY the JSON object. No prose, no markdown fences."""


def system_prompt(contract: bool = False) -> str:
    return SYSTEM_PROMPT + ("\n" + CONTRACT_ADDENDUM if contract else "")


def _history_block(history: Iterable, turns: int = HISTORY_TURNS) -> tuple[str, int]:
    items = list(history or [])[-turns:]
    lines = []
    for i, h in enumerate(items):
        role = getattr(h, "role", None) or (h.get("role") if isinstance(h, dict) else "user")
        content = getattr(h, "content", None) or (h.get("content") if isinstance(h, dict) else "") or ""
        content = re.sub(r"\s+", " ", str(content)).strip()[:HISTORY_CHARS_PER_TURN]
        offset = len(items) - i
        lines.append(f"[turn -{offset}] {str(role).upper()}: {content}")
    return ("\n".join(lines) if lines else "(no earlier turns)"), len(items)


def user_prompt(message: str, history: Iterable, corpus_ids: Iterable[str] | None = None,
                titles: Iterable[str] | None = None, matches=None) -> tuple[str, int]:
    """`titles` (COMPILER-CORPUS-CONTEXT-V1, B16): the library's book TITLES for this message, most relevant first —
    never summaries; rendered as one block between the scope line and the conversation. `matches` (S4, v2): the
    Scout's matched profile items as text with refs, rendered right after the titles."""
    hist, n = _history_block(history)
    corpora = ", ".join(c for c in (corpus_ids or []) if c) or "the user's corpus"
    from polymath_shared.compiler_context import titles_block
    block = titles_block(titles or [])
    library = f"{block}\n\n" if block else ""
    mblock = profile_matches_block(matches)
    library += f"{mblock}\n\n" if mblock else ""
    return (f"CORPUS IN SCOPE: {corpora}\n\n{library}RECENT CONVERSATION:\n{hist}\n\n"
            f"CURRENT MESSAGE:\n{(message or '').strip()}\n\nJSON:"), n


def _parse_json_object(text: str) -> dict | None:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, flags=re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def compile_plan(message: str, history: Iterable, corpus_ids: Iterable[str] | None,
                 complete: Callable[[str, str, int], tuple[str, str | None]],
                 *, budget_s: float = COMPILER_BUDGET_S, hard_budget_s: float | None = None,
                 model: str | None = None, titles: Iterable[str] | None = None, matches=None,
                 contract: bool | None = None) -> ChatPlan:
    """Run the compiler through `complete` (system_prompt, user_prompt,
    max_tokens) -> (text, error). Every failure path returns the fallback
    plan with a reason; the wall time is recorded either way.

    Two budgets: `budget_s` is the SOFT target the p50 gate measures
    (`compiler.over_budget`); `hard_budget_s` (default 2× soft, env
    POLYMATH_CHAT_COMPILER_HARD_BUDGET_S) is where a late plan is discarded
    for the fallback — a plan that lands at 2.9 s is still worth more than
    losing it, but a turn never waits on the compiler indefinitely."""
    hard = float(hard_budget_s if hard_budget_s is not None else max(COMPILER_HARD_BUDGET_S, 2 * budget_s))
    v2 = contract_enabled() if contract is None else bool(contract)
    t0 = time.perf_counter()
    prompt, n_hist = user_prompt(message, history, corpus_ids, titles=titles, matches=matches if v2 else None)
    try:
        text, err = complete(system_prompt(v2), prompt, COMPILER_MAX_OUTPUT_TOKENS_V2 if v2 else COMPILER_MAX_OUTPUT_TOKENS)
    except Exception as exc:  # noqa: BLE001 — the transport never breaks a turn
        text, err = "", f"{type(exc).__name__}"
    wall_ms = (time.perf_counter() - t0) * 1000
    if err:
        return fallback_plan(message, reason=f"transport:{err}", history_turns=n_hist, wall_ms=wall_ms, model=model)
    if wall_ms > hard * 1000:
        return fallback_plan(message, reason=f"budget_exceeded:{int(wall_ms)}ms", history_turns=n_hist, wall_ms=wall_ms, model=model)
    raw = _parse_json_object(text)
    if raw is None:
        return fallback_plan(message, reason="invalid_json", history_turns=n_hist, wall_ms=wall_ms, model=model)
    plan, reason = validate_plan(raw, message, contract=v2, matches=matches)
    if plan is None:
        return fallback_plan(message, reason=f"invalid_plan:{reason}", history_turns=n_hist, wall_ms=wall_ms, model=model)
    fixes = apply_corrections(plan, message, history, corpus_ids=corpus_ids)
    plan.compiler = {"fallback": False, "reason": None, "model": model, "wall_ms": round(wall_ms, 1),
                     "over_budget": wall_ms > budget_s * 1000, "history_turns": n_hist, "raw_chars": len(text or ""),
                     "corrections": fixes}
    if v2 and getattr(plan, "_contract_diag", None):
        plan.compiler["contract"] = plan._contract_diag
    return plan


def plan_receipt(plan: ChatPlan) -> dict:
    """Compact form for query receipts / SSE (§3.6)."""
    return {
        "contract": plan.contract, "task_type": plan.task_type, "evidence_policy": plan.evidence_policy,
        "retrieval_required": plan.retrieval_required, "response_type": plan.response_type,
        "resolved_request": plan.resolved_request[:400],
        # S4: the v2 purpose fields ride only when present, so a v1 receipt stays byte-identical
        "queries": [{k: v for k, v in asdict(q).items() if not (k in _V2_QUERY_FIELDS and v is None)} for q in plan.queries],
        "semantic_queries": plan.semantic_queries, "exact_terms": plan.exact_terms,
        "must_answer": plan.must_answer, "antecedent": plan.antecedent, "graph_useful": plan.graph_useful,
        "intent": plan.intent, "compiler": plan.compiler,
        # P6: subquery lineage, first-class for receipt readers (present once annotated).
        "subquery_provenance": plan.compiler.get("subquery_provenance"),
        **({"learning_need": plan.retrieval_goal, "inquiry": plan.inquiry, "synthesis_targets": plan.synthesis_targets}
           if plan.contract == CONTRACT_V2 else {}),
    }


_V2_QUERY_FIELDS = ("expected_contribution", "evidence_requirement")


EVIDENCE_ROUTE_OVERRIDE = "evidence_route:retrieval_required"


def plan_for_evidence_route(plan: "ChatPlan", *, override_rule: str = EVIDENCE_ROUTE_OVERRIDE) -> "ChatPlan":
    """The evidence-only route (`POST /chat/evidence`) exists to RETURN EVIDENCE. Its callers — the adapter's evidence boundary —
    submit a NEED, which is usually a STATEMENT (the run's seed, a hypothesis statement), not a question. The chat intent compiler
    reads a statement as GENERAL_CONVERSATION / `retrieval_required: false`, the turn then skips retrieval, and the route reports an
    EMPTY packet as a completed retrieval (the first real ecommerce run: 13 of 13 boundary calls, `queries: []`,
    `retrieval_skipped: true`, 0 rows, while `/retrieve/plan` — which has no such gate — carried the run).

    On that route a plan that would not retrieve is made retrievable DETERMINISTICALLY: grounded QA on the need verbatim with a q0
    PRIMARY (exactly what `fallback_plan` searches), keeping everything else the compiler produced and recording the override on the
    plan's compiler receipt. A plan that already retrieves is returned unchanged. Corpus-chat clients can explicitly
    require the same behavior, with override_rule identifying their authority; automatic chat remains unchanged."""
    if plan.retrieval_required and plan.queries:
        return plan
    from dataclasses import replace
    need = (plan.original_request or plan.resolved_request or "").strip()
    q0 = _clean_query(need)
    queries = list(plan.queries) or [CompiledQuery(id="q0", type="PRIMARY", query=q0, weight=1.0)]
    override = {"rule": override_rule, "from_task_type": plan.task_type, "from_evidence_policy": plan.evidence_policy,
                "from_retrieval_required": bool(plan.retrieval_required), "compiled_queries": len(plan.queries)}
    return replace(plan, task_type="GROUNDED_QA", evidence_policy="corpus_grounded", retrieval_required=True, queries=queries,
                   semantic_queries=list(plan.semantic_queries) or [q0], exact_terms=list(plan.exact_terms) or exact_terms_from(need),
                   compiler={**(plan.compiler or {}), "evidence_route_override": override})


def retrieval_text_for(plan: "ChatPlan") -> str:
    """COMPILED-RETRIEVAL-TEXT-V1 (P0.c interim until the lanes split in
    P1.a): the PRIMARY compiled query, with any exact term from the original
    input that the rewrite dropped appended verbatim — so the dense lane
    searches the meaning and the BM25 lane still sees "RAPO". Falls back to
    the resolved request, then the original message."""
    primary = next((q.query for q in plan.queries if q.type == "PRIMARY"), None) or \
              (plan.queries[0].query if plan.queries else None) or plan.resolved_request or plan.original_request
    text = primary.strip()
    low = text.lower()
    missing = [t for t in plan.exact_terms if t.lower() not in low]
    if missing:
        text = f"{text} {' '.join(missing)}"
    return text
