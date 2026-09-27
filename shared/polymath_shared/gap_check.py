"""FACET-RETRIEVAL-V1 F6 (register 11.545, plan §3.6) — the gap check, the answer's safety net.

The finding (plan §1): the answer claimed the library "doesn't bridge emotional direction to video model controls" while the
handbook does; no search had asked. After the answer text is generated, every "doesn't cover / not covered / no source /
the corpus lacks" sentence (a small deterministic pattern list, `GAP_PATTERNS`) and every facet the retrieval receipt marked
uncovered becomes ONE targeted retrieval through the turn's own retrieval function (`chat_retrieve_mode` in the turn's mode,
the same libraries, a small limit — no new lane). Found (≥ 1 passage the judge scores above the floor) → a short
"More on this" addition with citations (ONE bounded model call for all the found gaps, a deterministic cited stub when the
call fails) and the original gap sentence is marked `refuted` in the receipt and pointed at the addition; not found → the
sentence's claim is rewritten deterministically to "the passages found don't cover X" and the searches tried ride the
receipt (`meta.gap_check`). Never on a lookup (`eligible`).

Pure: no I/O, no model call — the caller passes `retrieve`, `hydrate` and `complete`. Flag `POLYMATH_CHAT_GAP_CHECK`
(default on): `0` = no check, no `meta.gap_check`, no phase — today's answer byte for byte.
"""
from __future__ import annotations

import math
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .deep_research.evidence import split_sentences

CONTRACT = "chat-gap-check-v1"
FLAG = "POLYMATH_CHAT_GAP_CHECK"
DEFAULT_MAX_CLAIMS = 3           # retrievals per turn (sentences first, then uncovered facets)
DEFAULT_LIMIT = 8                # seats per targeted retrieval
DEFAULT_BUDGET_S = 12.0          # wall budget for the retrievals; a claim past it is receipted `budget`
DEFAULT_MAX_TOKENS = 700         # the one bounded call
CITE_MAX = 3                     # passages offered per found claim
PASSAGE_CHARS = 1500
SECTION_LEAD = "**More on this.**"
SYNTHESIS_TASKS = ("GROUNDED_SYNTHESIS", "CREATE_FROM_KNOWLEDGE")
GAP_TASKS = ("GROUNDED_QA",) + SYNTHESIS_TASKS
S_TAG = re.compile(r"\[S(\d{1,3})\]")

_SUBJECT = (r"(?:the |this |these |those |your |our |its |my )?(?:retrieved |provided |available |cited |current |present |"
            r"whole |entire |underlying )?(?:library|libraries|corpus|corpora|evidence|source|sources|document|documents|"
            r"documentation|material|materials|book|books|passage|passages|text|texts|reading|readings|chapter|chapters|"
            r"handbook|guide|notes|literature|knowledge base|content)")
_NEG_DO = r"(?:doesn't|does not|don't|do not|didn't|did not|fails to|fail to)"
_NEG_SINGULAR = r"(?:never|lacks|has no|had no|offers no|contains no|provides no|gives no|includes no|says nothing|is silent|falls short|stops short|only touches|barely touches)"
_NEG_PLURAL = r"(?:lack|have no|offer no|contain no|provide no|give no|include no|say nothing|are silent|fall short|stop short)"
_NEG = rf"(?:{_NEG_DO}|{_NEG_SINGULAR}|{_NEG_PLURAL})"
_IN = r"(?:in|from|within|among|across|of|anywhere in|part of|present in|found in|covered in|covered by|addressed in|addressed by|discussed in|mentioned in|included in|available in|documented in|by)"

#: (name, strong, pattern). A STRONG pattern names the corpus itself (library / corpus / evidence / sources …) and counts even
#: on a cited sentence; a weak one ("is not covered", "no source on") counts only on an uncited sentence — a cited "there is
#: no evidence that …" is a claim ABOUT a source, not a gap.
GAP_PATTERNS: list[tuple[str, bool, re.Pattern]] = [
    ("passages_found", True, re.compile(r"\bthe passages (?:first )?found (?:don't|do not|didn't|did not) (?:cover|address|include|bridge|mention|discuss|explain|reach)\b", re.IGNORECASE)),
    ("subject_negated", True, re.compile(rf"\b{_SUBJECT}(?:\s+\w+){{0,2}}\s+{_NEG}\b", re.IGNORECASE)),
    ("nothing_in", True, re.compile(rf"\b(?:nothing|none|nowhere|no passage|no source|no document|no section|no chapter|no book|neither)\s+{_IN}\s+{_SUBJECT}", re.IGNORECASE)),
    ("not_in", True, re.compile(rf"\b(?:not|nowhere|absent|missing|isn't|aren't|is not|are not|wasn't|weren't|was not|were not)\s+"
                                rf"(?:directly\s+|explicitly\s+|fully\s+|specifically\s+)?{_IN}\s+{_SUBJECT}", re.IGNORECASE)),
    ("beyond", True, re.compile(rf"\b(?:beyond|outside|outside of)\s+(?:the scope of\s+|what\s+)?{_SUBJECT}", re.IGNORECASE)),
    ("not_covered", False, re.compile(r"\b(?:isn't|aren't|wasn't|weren't|is not|are not|was not|were not|not|never|nowhere)\s+"
                                      r"(?:directly\s+|explicitly\s+|fully\s+|specifically\s+|well\s+)?"
                                      r"(?:covered|addressed|discussed|mentioned|documented|explained|treated|included|represented|supported|bridged|described|detailed|answered)\b", re.IGNORECASE)),
    ("un_covered", False, re.compile(r"\b(?:remains?|stays?|is|are|left)\s+(?:un(?:covered|addressed|documented|answered|explained|supported|mentioned))\b", re.IGNORECASE)),
    ("no_source", False, re.compile(r"\b(?:no|nothing|none of the|not one|not a single|neither)\s+(?:direct |specific |explicit |dedicated |single |relevant |clear )?"
                                    r"(?:source|sources|passage|passages|evidence|material|section|sections|document|documents|chapter|chapters|book|books|coverage|mention|guidance|discussion|treatment|reference|references)\b", re.IGNORECASE)),
    ("gap_word", False, re.compile(rf"\b(?:gap|gaps|blind spot|blind spots)\s+(?:in|of|within)\s+{_SUBJECT}", re.IGNORECASE)),
    ("would_need", False, re.compile(r"\bwould (?:need|require)\s+(?:a |an |another |additional |more |further |other )?(?:source|sources|passage|passages|evidence|material|document|documents|reference|references)\b", re.IGNORECASE)),
    ("cannot_find", False, re.compile(r"\b(?:cannot|can't|could not|couldn't|unable to|was unable to|were unable to)\s+(?:be\s+)?(?:find|found|locate|located|identify|identified|verify|verified|confirm|confirmed|trace|traced)\b", re.IGNORECASE)),
]

STOPWORDS = frozenset((
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "of", "in", "on", "at", "to", "for", "from", "by",
    "with", "without", "about", "into", "onto", "over", "under", "between", "among", "across", "through", "during",
    "before", "after", "above", "below", "up", "down", "out", "off", "than", "then", "that", "this", "these",
    "those", "there", "here", "it", "its", "it's", "is", "are", "was", "were", "be", "been", "being", "am", "do",
    "does", "did", "done", "doing", "have", "has", "had", "having", "will", "would", "shall", "should", "can",
    "could", "may", "might", "must", "not", "no", "nor", "n't", "don't", "doesn't", "didn't", "isn't", "aren't",
    "wasn't", "weren't", "won't", "wouldn't", "can't", "couldn't", "shouldn't", "i", "me", "my", "mine", "we", "us",
    "our", "ours", "you", "your", "yours", "he", "him", "his", "she", "her", "hers", "they", "them", "their",
    "theirs", "who", "whom", "whose", "which", "what", "when", "where", "why", "how", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such", "only", "own", "same", "very", "s", "t", "just", "now", "also",
    "as", "if", "while", "because", "until", "although", "though", "whether", "either", "neither", "one", "two",
    "three", "first", "second", "per", "via", "etc", "e.g", "i.e",
))
#: the gap vocabulary itself never becomes a search term
GAP_WORDS = frozenset((
    "library", "libraries", "corpus", "corpora", "evidence", "source", "sources", "document", "documents",
    "documentation", "material", "materials", "book", "books", "passage", "passages", "text", "texts", "reading",
    "readings", "chapter", "chapters", "handbook", "guide", "notes", "literature", "knowledge", "base", "content",
    "retrieved", "provided", "available", "cited", "current", "present", "whole", "entire", "underlying", "cover",
    "covers", "covered", "covering", "address", "addresses", "addressed", "addressing", "mention", "mentions",
    "mentioned", "discuss", "discusses", "discussed", "explain", "explains", "explained", "include", "includes",
    "included", "contain", "contains", "contained", "provide", "provides", "provided", "offer", "offers", "offered",
    "give", "gives", "gave", "say", "says", "said", "found", "find", "treat", "treats", "treated", "describe",
    "describes", "described", "detail", "details", "detailed", "answer", "answers", "answered", "support",
    "supports", "supported", "represent", "represents", "represented", "bridged", "directly", "explicitly",
    "specifically", "fully", "well", "anywhere", "nothing", "none", "neither", "beyond", "outside", "scope", "lack",
    "lacks", "lacking", "silent", "short", "touches", "barely", "fails", "fail", "never", "does", "doesn't", "don't",
    "didn't", "did", "not", "gap", "gaps", "spot", "spots", "need", "needs", "require", "requires", "would",
    "unable", "cannot", "locate", "located", "identify", "verify", "confirm", "remains", "remain", "stays",
    "uncovered", "unaddressed", "undocumented", "unanswered", "unexplained", "unsupported", "however", "therefore",
    "instead", "specific", "explicit", "dedicated", "single", "relevant", "clear", "direct", "further", "additional",
    "another",
))
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
_TERMINAL = re.compile(r"([.!?]+[\"'”’)*_]*)$")


def enabled(env: Mapping[str, str] | None = None) -> bool:
    raw = (env if env is not None else os.environ).get(FLAG, "1")
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def limits() -> dict[str, Any]:
    return {"max_claims": _env_int("POLYMATH_CHAT_GAP_CHECK_MAX_CLAIMS", DEFAULT_MAX_CLAIMS),
            "limit": _env_int("POLYMATH_CHAT_GAP_CHECK_LIMIT", DEFAULT_LIMIT),
            "budget_s": _env_float("POLYMATH_CHAT_GAP_CHECK_BUDGET_S", DEFAULT_BUDGET_S),
            "max_tokens": _env_int("POLYMATH_CHAT_GAP_CHECK_MAX_TOKENS", DEFAULT_MAX_TOKENS)}


def eligible(plan: Any) -> bool:
    """A synthesis task (GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE), or a GROUNDED_QA with ≥ 2 facets — never a lookup
    (≤ 1 facet), never a turn without retrieval, never a transform / continuation / conversation."""
    if plan is None or not getattr(plan, "retrieval_required", False):
        return False
    task = getattr(plan, "task_type", None)
    if task not in GAP_TASKS:
        return False
    if task in SYNTHESIS_TASKS:
        return True
    facets = [f for f in (getattr(plan, "facets", None) or []) if isinstance(f, Mapping) and f.get("id")]
    return len(facets) >= 2


def sigmoid(x: float | None) -> float | None:
    if x is None:
        return None
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x)))))


# ─────────────────────────────────────────────────────────── the gap sentences

def gap_sentences(text: str) -> list[dict[str, Any]]:
    """Every sentence of the answer (headings, fences, tables skipped — `split_sentences`) that claims a gap: {index, text,
    pattern}. Deterministic, first matching pattern named."""
    out: list[dict[str, Any]] = []
    for i, s in enumerate(split_sentences(text or "")):
        cited = bool(S_TAG.search(s))
        for name, strong, pat in GAP_PATTERNS:
            if not strong and cited:
                continue
            if pat.search(s):
                out.append({"index": i, "text": s, "pattern": name})
                break
    return out


def content_words(text: str) -> list[str]:
    """The sentence's content words in order (deduped, lowercase, ≥ 3 letters, no stopwords, no gap vocabulary, no tags)."""
    body = S_TAG.sub(" ", text or "")
    body = re.sub(r"[*_`#>]+", " ", body)
    seen: dict[str, None] = {}
    for w in _WORD.findall(body):
        lw = w.lower().strip("'-")
        if len(lw) < 3 or lw in STOPWORDS or lw in GAP_WORDS:
            continue
        seen.setdefault(lw, None)
    return list(seen)


def gap_query(sentence: str, *, fallback: str = "", max_words: int = 12) -> str:
    """The targeted search for a gap sentence: its content words (≤ 12); a sentence with fewer than two content words borrows
    the fallback's (the resolved request's) first content words so the search still names the topic; empty = no search."""
    words = content_words(sentence)
    if len(words) < 2:
        for w in content_words(fallback):
            if w not in words:
                words.append(w)
            if len(words) >= 8:
                break
    return " ".join(words[:max_words])


# ─────────────────────────────────────────────────────────── the deterministic edits

_R_SUBJECT_DO = re.compile(rf"\b({_SUBJECT})((?:\s+\w+){{0,2}})\s+({_NEG_DO})\b", re.IGNORECASE)
_R_SUBJECT_SING = re.compile(rf"\b({_SUBJECT})((?:\s+\w+){{0,2}})\s+({_NEG_SINGULAR})\b", re.IGNORECASE)
_R_SUBJECT_PLUR = re.compile(rf"\b({_SUBJECT})((?:\s+\w+){{0,2}})\s+({_NEG_PLURAL})\b", re.IGNORECASE)
_R_NOTHING_IN = re.compile(rf"(\b(?:nothing|none|nowhere|no passage|no source|no document|no section|no chapter|no book|neither)\s+{_IN}\s+)({_SUBJECT})", re.IGNORECASE)
_R_NOT_IN = re.compile(rf"(\b(?:not|nowhere|absent|missing|isn't|aren't|is not|are not|wasn't|weren't|was not|were not)\s+"
                       rf"(?:directly\s+|explicitly\s+|fully\s+|specifically\s+)?{_IN}\s+)({_SUBJECT})", re.IGNORECASE)
_R_BEYOND = re.compile(rf"(\b(?:beyond|outside|outside of)\s+(?:the scope of\s+|what\s+)?)({_SUBJECT})", re.IGNORECASE)
_R_PARTICIPLE = re.compile(r"\b((?:isn't|aren't|wasn't|weren't|is not|are not|was not|were not|not|never|nowhere)\s+"
                           r"(?:directly\s+|explicitly\s+|fully\s+|specifically\s+|well\s+)?"
                           r"(?:covered|addressed|discussed|mentioned|documented|explained|treated|included|represented|supported|bridged|described|detailed|answered))\b"
                           rf"(?!\s+{_IN}\b)", re.IGNORECASE)


def _cap(repl: str, original: str) -> str:
    return repl[0].upper() + repl[1:] if original[:1].isupper() else repl


_PLURAL_SUBJECTS = frozenset(("libraries", "corpora", "sources", "documents", "materials", "books", "passages", "texts",
                              "readings", "chapters", "notes"))
_DO_PLURAL = {"doesn't": "don't", "does not": "do not", "fails to": "fail to"}
_ALREADY_HONEST = re.compile(r"\bthe passages found\b", re.IGNORECASE)


def _is_plural(subject_phrase: str) -> bool:
    return subject_phrase.split()[-1].lower() in _PLURAL_SUBJECTS


def honest_rewrite(sentence: str, *, subject: str = "the passages found", singular: str = "the material found",
                   strong_only: bool = False) -> tuple[str, str | None]:
    """The claim rewritten so it speaks only of the passages that were searched: ("…", rule) — rule None = unchanged.
    A corpus subject with do-support ("the library doesn't bridge") becomes `subject` with the plural negation ("the passages
    found don't bridge"); an inflected negation keeps the original subject's number — a plural subject ("the sources never
    explain") takes `subject`, a singular one ("the library never explains", "the corpus lacks") takes `singular` ("the
    material found never explains") so the verb still agrees. A sentence already worded on the passages found is left alone
    (the found case renames it "first found"). `strong_only` skips the weak-pattern qualifier (the found case adds its own
    pointer instead)."""
    s = sentence or ""
    if _ALREADY_HONEST.search(s):
        if subject != "the passages found":
            return _ALREADY_HONEST.sub(lambda m: _cap(subject, m.group(0)), s, count=1), "first_found"
        return s, None
    m = _R_SUBJECT_DO.search(s)
    if m:
        neg = m.group(3).lower()
        return s[:m.start()] + _cap(f"{subject} {_DO_PLURAL.get(neg, neg)}", m.group(1)) + s[m.end():], "subject_do"
    m = _R_SUBJECT_PLUR.search(s)
    if m:
        return s[:m.start()] + _cap(f"{subject} {m.group(3).lower()}", m.group(1)) + s[m.end():], "subject_plural"
    m = _R_SUBJECT_SING.search(s)
    if m:
        who = subject if _is_plural(m.group(1)) else singular
        return s[:m.start()] + _cap(f"{who} {m.group(3).lower()}", m.group(1)) + s[m.end():], "subject_singular"
    for rule, pat in (("nothing_in", _R_NOTHING_IN), ("not_in", _R_NOT_IN), ("beyond", _R_BEYOND)):
        m = pat.search(s)
        if m:
            return s[:m.start()] + m.group(1) + subject + s[m.end():], rule
    if strong_only:
        return s, None
    m = _R_PARTICIPLE.search(s)
    if m:
        return s[:m.start()] + m.group(1) + f" by {subject}" + s[m.end():], "participle_by"
    for name, strong, pat in GAP_PATTERNS:
        if not strong and pat.search(s):
            core, punct = _split_terminal(s)
            return f"{core} (among {subject}){punct}", "qualified"
    return s, None


def _split_terminal(sentence: str) -> tuple[str, str]:
    m = _TERMINAL.search(sentence)
    if not m:
        return sentence, ""
    return sentence[:m.start()], m.group(1)


def mark_found(sentence: str, tags: Iterable[str]) -> str:
    """The refuted claim, pointed at the addition: "… (more below: [S7] [S8])." — the tags become citation chips."""
    core, punct = _split_terminal(sentence)
    chips = " ".join(f"[{t}]" for t in tags)
    return f"{core} (more below: {chips}){punct}" if chips else sentence


def strip_unknown_tags(text: str, allowed: Iterable[str]) -> tuple[str, int]:
    """Every [S#] the model wrote that is not an offered passage is removed (the addition may cite only what the check found)."""
    ok = set(allowed)
    dropped = 0

    def _sub(m: re.Match) -> str:
        nonlocal dropped
        if f"S{m.group(1)}" in ok:
            return m.group(0)
        dropped += 1
        return ""
    out = S_TAG.sub(_sub, text or "")
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", out))
    return out.strip(), dropped


# ─────────────────────────────────────────────────────────── the bounded call

ADDITION_SYSTEM = (
    "You extend an answer that was written from a corpus. The answer claimed that some things were not covered; a targeted "
    "search then found the passages below. Write ONLY the addition: for each claim, one short paragraph (two to four "
    "sentences) giving what the passages say about it, every factual sentence ending with its [S#] tag from the passages "
    "given — never another tag, never a fact the passages do not state, never a guess about the rest of the corpus. Plain "
    "paragraphs: no heading, no preamble, no list of the claims, no restatement of the answer. Under 120 words per claim.")


def addition_messages(resolved_request: str, claims: list[dict[str, Any]], passages: list[dict[str, Any]]) -> list[dict[str, str]]:
    claim_lines = "\n".join(f"{i}. {c['text']}" for i, c in enumerate(claims, 1))
    body = []
    for p in passages:
        crumb = p.get("breadcrumb") or p.get("locator") or ""
        body.append(f"[{p['tag']}] {crumb}\n{(p.get('text') or '')[:PASSAGE_CHARS]}")
    user = (f"REQUEST:\n{resolved_request}\n\nCLAIMS THE SEARCH REFUTED:\n{claim_lines}\n\n"
            "PASSAGES FOUND:\n" + "\n---\n".join(body))
    return [{"role": "system", "content": ADDITION_SYSTEM}, {"role": "user", "content": user}]


def stub_addition(claims: list[dict[str, Any]]) -> str:
    """When the bounded call fails: a deterministic, cited pointer per found claim."""
    parts = []
    for c in claims:
        refs = "; ".join(f"{(p.get('breadcrumb') or p.get('locator') or 'passage')} [{p['tag']}]" for p in c["passages"])
        parts.append(f"See {refs}.")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────── the check

def run_gap_check(text: str, *, resolved_request: str, legend: Iterable[Mapping[str, Any]],
                  retrieve: Callable[[str], Iterable[Mapping[str, Any]]],
                  hydrate: Callable[[Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
                  complete: Callable[[list[dict[str, str]], int], str] | None = None,
                  floor: float = 0.5, facets_uncovered: Iterable[Mapping[str, Any]] = (),
                  max_claims: int | None = None, limit: int | None = None, budget_s: float | None = None,
                  max_tokens: int | None = None, cite_max: int = CITE_MAX,
                  clock: Callable[[], float] = time.perf_counter) -> dict[str, Any]:
    """The check on one answer. Returns {text, legend_added, receipt}:
    - text: the answer with its gap sentences edited and, when anything was found, the "More on this" addition appended;
    - legend_added: the new legend entries ({tag, locator, chunk_id, doc_id, text, breadcrumb, …}) the caller appends to the
      turn's legend and chunk inventory so the new [S#] chips resolve;
    - receipt: `meta.gap_check` — {contract, claims, searches, ms, call, section_added, limits, budget_exhausted}.
    `retrieve(query)` returns the turn's final rows ({chunk_id, doc_id, rerank_score}); `hydrate(row)` the passage's text and
    presentation for a chunk not already in the legend (None = skip it); `complete(messages, max_tokens)` the one bounded
    model call (None or a failure = the deterministic stub)."""
    lim = limits()
    max_claims = lim["max_claims"] if max_claims is None else max_claims
    limit = lim["limit"] if limit is None else limit
    budget_s = lim["budget_s"] if budget_s is None else budget_s
    max_tokens = lim["max_tokens"] if max_tokens is None else max_tokens
    t0 = clock()
    entries = [dict(e) for e in (legend or ()) if e.get("tag")]
    tag_of_chunk = {str(e.get("chunk_id")): str(e["tag"]) for e in entries if e.get("chunk_id")}
    next_n = max([int(m) for e in entries for m in S_TAG.findall(f"[{e['tag']}]")] or [0]) + 1

    claims: list[dict[str, Any]] = []
    for g in gap_sentences(text):
        if len(claims) >= max_claims:
            break
        claims.append({"text": g["text"][:240], "sentence": g["text"], "source": "sentence", "pattern": g["pattern"],
                       "facet_id": None, "query": gap_query(g["text"], fallback=resolved_request)})
    for f in facets_uncovered or ():
        if len(claims) >= max_claims:
            break
        fid = str(f.get("id") or "")
        q = " ".join(str(f.get("query") or f.get("name") or "").split())
        if not fid or not q:
            continue
        claims.append({"text": f'facet {fid} "{str(f.get("name") or "")[:80]}" (uncovered by this turn\'s searches)',
                       "sentence": None, "source": "facet", "pattern": None, "facet_id": fid, "query": q[:200]})

    searches: list[dict[str, Any]] = []
    legend_added: list[dict[str, Any]] = []
    budget_exhausted = False
    for c in claims:
        c.update({"found": 0, "returned": 0, "cited_added": [], "refuted": False, "edited": None, "unjudged": 0,
                  "error": None, "skipped": None, "passages": []})
        if not c["query"]:
            c["skipped"] = "no_content_words"
            continue
        if clock() - t0 > budget_s:
            c["skipped"] = "budget"
            budget_exhausted = True
            continue
        ts = clock()
        try:
            rows = [dict(r) for r in (retrieve(c["query"]) or ()) if isinstance(r, Mapping)][:max(1, limit)]
        except Exception as exc:  # noqa: BLE001 — a failed search is a receipted search, never a broken turn
            c["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            searches.append({"query": c["query"], "returned": 0, "above_floor": 0, "ms": round((clock() - ts) * 1000, 1),
                             "error": c["error"]})
            continue
        above: list[dict[str, Any]] = []
        for r in rows:
            s = sigmoid(r.get("rerank_score"))
            if s is None:
                c["unjudged"] += 1
                continue
            if s >= floor and r.get("chunk_id"):
                above.append(r)
        c["returned"] = len(rows)
        c["found"] = len(above)
        searches.append({"query": c["query"], "returned": len(rows), "above_floor": len(above),
                         "ms": round((clock() - ts) * 1000, 1)})
        for r in above:
            if len(c["passages"]) >= cite_max:
                break
            cid = str(r["chunk_id"])
            if cid in tag_of_chunk:
                e = next(x for x in entries + legend_added if str(x.get("chunk_id")) == cid)
                c["passages"].append({"tag": tag_of_chunk[cid], "chunk_id": cid, "doc_id": e.get("doc_id"),
                                      "text": e.get("text") or "", "breadcrumb": e.get("breadcrumb") or "",
                                      "locator": e.get("locator") or f"chunk:{cid}", "new": False})
                continue
            h = None
            if hydrate is not None:
                try:
                    h = hydrate(r)
                except Exception as exc:  # noqa: BLE001 — an unhydrated passage cannot be cited; say so
                    c["error"] = f"hydrate:{type(exc).__name__}"
                    h = None
            if not h or not (h.get("text") or "").strip():
                continue
            tag = f"S{next_n}"
            next_n += 1
            entry = {"tag": tag, "locator": h.get("locator") or f"chunk:{cid}", "chunk_id": cid, "doc_id": h.get("doc_id") or r.get("doc_id"),
                     "text": str(h.get("text") or "")[:PASSAGE_CHARS], "breadcrumb": h.get("breadcrumb") or "",
                     "carried": False, "carry_score": None, "gap_check": True,
                     "source_name": h.get("source_name") or "", "title": h.get("title") or "",
                     "heading_path": h.get("heading_path") or "", "human_locator": h.get("human_locator") or ""}
            legend_added.append(entry)
            tag_of_chunk[cid] = tag
            c["passages"].append({**{k: entry[k] for k in ("tag", "chunk_id", "doc_id", "text", "breadcrumb", "locator")}, "new": True})
        if c["passages"]:
            c["refuted"] = c["source"] == "sentence"
            c["cited_added"] = [p["tag"] for p in c["passages"]]

    found = [c for c in claims if c["passages"]]
    new_text = text or ""
    for c in claims:
        if c["source"] != "sentence" or not c["sentence"]:
            continue
        if not c["passages"] and (c["skipped"] or c["error"]):
            continue                                               # no search ran (or it failed): the claim is neither found nor refuted
        if c["passages"]:
            rewritten, rule = honest_rewrite(c["sentence"], subject="the passages first found", singular="the material first found",
                                             strong_only=True)
            edited = mark_found(rewritten, c["cited_added"])
            c["edited"] = f"{rule}+pointer" if rule else "pointer"
        else:
            edited, rule = honest_rewrite(c["sentence"])
            c["edited"] = rule
        if edited != c["sentence"] and c["sentence"] in new_text:
            new_text = new_text.replace(c["sentence"], edited, 1)
        elif edited != c["sentence"]:
            c["edited"] = None                                     # the sentence is not a verbatim substring (never expected)
    call: dict[str, Any] | None = None
    section_added = False
    if found:
        offered = [p for c in found for p in c["passages"]]
        seen_tags: set[str] = set()
        passages = []
        for p in offered:
            if p["tag"] not in seen_tags:
                seen_tags.add(p["tag"])
                passages.append(p)
        body = ""
        call = {"made": False, "ok": False, "fallback": None, "error": None, "max_tokens": max_tokens,
                "claims": len(found), "passages": len(passages)}
        if complete is not None:
            call["made"] = True
            try:
                out = complete(addition_messages(resolved_request, found, passages), max_tokens)
                body, dropped = strip_unknown_tags(str(out or ""), seen_tags)
                call["dropped_tags"] = dropped
                if body and any(f"[{t}]" in body for t in seen_tags):
                    call["ok"] = True
                else:
                    call["error"] = "empty_or_uncited"
                    body = ""
            except Exception as exc:  # noqa: BLE001 — the addition is additive; the stub keeps the citations
                call["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                body = ""
        if not body:
            body = stub_addition(found)
            call["fallback"] = "stub"
        new_text = new_text.rstrip() + "\n\n" + SECTION_LEAD + " " + body.strip()
        section_added = True
    receipt = {"contract": CONTRACT,
               "claims": [{k: v for k, v in c.items() if k not in ("sentence", "passages")} for c in claims],
               "searches": searches, "ms": round((clock() - t0) * 1000, 1), "call": call, "section_added": section_added,
               "limits": {"max_claims": max_claims, "limit": limit, "budget_s": budget_s, "floor": floor},
               "budget_exhausted": budget_exhausted}
    return {"text": new_text, "legend_added": legend_added, "receipt": receipt}
