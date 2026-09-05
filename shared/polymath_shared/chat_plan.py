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

CONTRACT = "chat-intent-plan-v1"
COMPILER_STAGE = "chat_compiler"                 # stage pin in config/cloud_providers.json
COMPILER_BUDGET_S = float(os.environ.get("POLYMATH_CHAT_COMPILER_BUDGET_S", "2.5"))       # soft: the p50 gate
COMPILER_HARD_BUDGET_S = float(os.environ.get("POLYMATH_CHAT_COMPILER_HARD_BUDGET_S", "6.0"))  # hard: give up → fallback
COMPILER_MAX_OUTPUT_TOKENS = int(os.environ.get("POLYMATH_CHAT_COMPILER_MAX_TOKENS", "600"))
HISTORY_TURNS = int(os.environ.get("POLYMATH_CHAT_COMPILER_HISTORY_TURNS", "8"))
HISTORY_CHARS_PER_TURN = 1500
MAX_QUERIES = 4
MAX_QUERY_WORDS = 32

TASK_TYPES = ("GROUNDED_QA", "GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE",
              "TRANSFORM_USER_CONTENT", "CONTINUE_PRIOR_ARTIFACT", "GENERAL_CONVERSATION")
EVIDENCE_POLICIES = ("corpus_grounded", "conversation", "mixed")
QUERY_TYPES = ("PRIMARY", "DEFINITION", "MECHANISM", "CAUSAL", "COMPARISON", "COUNTERPOINT",
               "PROCEDURE", "EXAMPLE", "ENTITY", "BRIDGE")
RESPONSE_TYPES = ("answer", "artifact")
NO_RETRIEVAL_TASKS = ("TRANSFORM_USER_CONTENT", "CONTINUE_PRIOR_ARTIFACT", "GENERAL_CONVERSATION")

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
    compiler: dict = field(default_factory=dict)

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


def _has_instruction_tokens(q: str) -> bool:
    ql = f" {q.lower()} "
    return any(tok in ql for tok in _INSTRUCTION_TOKENS)


def fallback_plan(message: str, *, reason: str, history_turns: int = 0, wall_ms: float = 0.0,
                  model: str | None = None) -> ChatPlan:
    """Today's behavior, made explicit: grounded QA on the raw message."""
    msg = (message or "").strip()
    return ChatPlan(
        contract=CONTRACT, original_request=msg, resolved_request=msg,
        task_type="GROUNDED_QA", evidence_policy="corpus_grounded", retrieval_required=True,
        retrieval_goal=None,
        queries=[CompiledQuery(id="q0", type="PRIMARY", query=_clean_query(msg), weight=1.0)],
        semantic_queries=[_clean_query(msg)], exact_terms=exact_terms_from(msg),
        entities=[], must_answer=[], user_constraints=[], response_type="answer",
        antecedent=None, graph_useful=False,
        compiler={"fallback": True, "reason": reason, "model": model, "wall_ms": round(wall_ms, 1),
                  "history_turns": history_turns})


_CORPUS_REF = re.compile(r"\b(my|the|our|these|those|all my|everything my)\s+(books?|corpus|sources?|documents?|library|notes|papers?|readings?)\b"
                         r"|\b(what|everything)\s+(my|the)\s+\w+\s+(books?|corpus|sources?)\s+(say|know|says)\b"
                         r"|\bfrom\s+(my|the)\s+(books?|corpus|sources?)\b|\bin\s+(my|the)\s+corpus\b", re.I)
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


def validate_plan(raw: dict, message: str) -> tuple[ChatPlan | None, str | None]:
    """Strict contract check + law 1. Returns (plan, None) or (None, reason)."""
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
    if task in ("GROUNDED_QA", "GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE"):
        rr = True
    queries: list[CompiledQuery] = []
    for i, q in enumerate(raw.get("queries") or []):
        if not isinstance(q, dict):
            continue
        text = _clean_query(q.get("query"))
        if not text or _has_instruction_tokens(text):
            continue
        qtype = str(q.get("type") or "PRIMARY").strip().upper()
        if qtype not in QUERY_TYPES:
            qtype = "PRIMARY" if i == 0 else "MECHANISM"
        try:
            weight = float(q.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        queries.append(CompiledQuery(id=f"q{len(queries)}", type=qtype, query=text, weight=max(0.1, min(1.0, weight))))
        if len(queries) >= MAX_QUERIES:
            break
    if rr:
        if not queries:
            return None, "no_queries_for_retrieval"
        if sum(1 for q in queries if q.type == "PRIMARY") != 1:
            queries[0].type = "PRIMARY"
            for q in queries[1:]:
                if q.type == "PRIMARY":
                    q.type = "MECHANISM"
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
    return plan, None


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
  COMPARISON, COUNTERPOINT, PROCEDURE, EXAMPLE, ENTITY, BRIDGE. Empty when retrieval_required is false.
- The corpus name(s) named below are SCOPE, never query words: search "sound editing", not "sound editing in cinema".
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
- "do the authors agree or disagree about X?" → GROUNDED_SYNTHESIS with a COMPARISON query per side.
Output ONLY the JSON object. No prose, no markdown fences."""


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


def user_prompt(message: str, history: Iterable, corpus_ids: Iterable[str] | None = None) -> tuple[str, int]:
    hist, n = _history_block(history)
    corpora = ", ".join(c for c in (corpus_ids or []) if c) or "the user's corpus"
    return (f"CORPUS IN SCOPE: {corpora}\n\nRECENT CONVERSATION:\n{hist}\n\n"
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
                 model: str | None = None) -> ChatPlan:
    """Run the compiler through `complete` (system_prompt, user_prompt,
    max_tokens) -> (text, error). Every failure path returns the fallback
    plan with a reason; the wall time is recorded either way.

    Two budgets: `budget_s` is the SOFT target the p50 gate measures
    (`compiler.over_budget`); `hard_budget_s` (default 2× soft, env
    POLYMATH_CHAT_COMPILER_HARD_BUDGET_S) is where a late plan is discarded
    for the fallback — a plan that lands at 2.9 s is still worth more than
    losing it, but a turn never waits on the compiler indefinitely."""
    hard = float(hard_budget_s if hard_budget_s is not None else max(COMPILER_HARD_BUDGET_S, 2 * budget_s))
    t0 = time.perf_counter()
    prompt, n_hist = user_prompt(message, history, corpus_ids)
    try:
        text, err = complete(SYSTEM_PROMPT, prompt, COMPILER_MAX_OUTPUT_TOKENS)
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
    plan, reason = validate_plan(raw, message)
    if plan is None:
        return fallback_plan(message, reason=f"invalid_plan:{reason}", history_turns=n_hist, wall_ms=wall_ms, model=model)
    fixes = apply_corrections(plan, message, history, corpus_ids=corpus_ids)
    plan.compiler = {"fallback": False, "reason": None, "model": model, "wall_ms": round(wall_ms, 1),
                     "over_budget": wall_ms > budget_s * 1000, "history_turns": n_hist, "raw_chars": len(text or ""),
                     "corrections": fixes}
    return plan


def plan_receipt(plan: ChatPlan) -> dict:
    """Compact form for query receipts / SSE (§3.6)."""
    return {
        "contract": plan.contract, "task_type": plan.task_type, "evidence_policy": plan.evidence_policy,
        "retrieval_required": plan.retrieval_required, "response_type": plan.response_type,
        "resolved_request": plan.resolved_request[:400], "queries": [asdict(q) for q in plan.queries],
        "semantic_queries": plan.semantic_queries, "exact_terms": plan.exact_terms,
        "must_answer": plan.must_answer, "antecedent": plan.antecedent, "graph_useful": plan.graph_useful,
        "compiler": plan.compiler,
    }


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
