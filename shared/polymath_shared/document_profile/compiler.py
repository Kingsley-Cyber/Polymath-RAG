"""
rag_compiler_final.py

Tolerant compiler for compact tagged-line LLM document profiles.

Preferred model output:

    ONE: <what the document is fundamentally about>
    SUMMARY: <1-2 dense sentences>

    TOPIC: <specific retrieval neighborhood>      # target 4-6
    TERM: <entity / jargon / framework>           # target 4-7
    Q: <natural question the document answers>    # target 3-5
    SEARCH: <realistic short search query>        # target 4-6
    SEEALSO: <neighboring document concept>        # target 1-2
    END

Backward compatibility:
- DETAIL is still accepted but is optional.
- Older TOPIC / TERM / Q-only profiles still compile.
- Variant tags, missing colons, wrapped lines, and END variants are repaired.

Design goal:
Content correctness matters more than perfect formatting. Cardinality targets are
soft coverage goals, not hard validity requirements. Only a missing semantic core
causes compilation failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

SCHEMA_VERSION = "rag-profile-v3"          # v3 (owner 2026-09-07): THEORY + CONCEPT, new counts, atomic representations
PROMPT_VERSION = "doc-profile-v3"
COMPILER_VERSION = "rag-compiler-v3"

# Preferred counts for a lean but useful retrieval profile.
# (advisory floor, aim) — owner 2026-09-07: "increase output to 10 topics, 10 terms, Q 15, search 15,
# theory & concept 10, see also 10". The aim is what the prompt asks for; the floor only raises a BELOW_TARGET
# info; counts are never required (readiness is the semantic core + a query hook).
TARGET_COUNTS: dict[str, tuple[int, int]] = {
    "TOPIC":   (5, 10),
    "TERM":    (5, 10),
    "Q":       (8, 15),
    "SEARCH":  (8, 15),
    "THEORY":  (4, 10),     # the frameworks / mechanisms / explanatory lenses behind the document
    "CONCEPT": (4, 10),     # transferable ideas that could appear in another field
    "SEEALSO": (5, 10),
}

# Defensive caps. Going under target is allowed. Going far over target is
# wasteful and is deterministically capped.
HARD_MAX: dict[str, int] = {          # aim + headroom; anything beyond is deterministically capped (LIST_CAPPED)
    "TOPIC": 16,
    "TERM": 16,
    "Q": 22,
    "SEARCH": 22,
    "THEORY": 16,
    "CONCEPT": 16,
    "SEEALSO": 16,
}

TAG_ALIASES: dict[str, str] = {
    "ONE": "ONE",
    "ONELINER": "ONE",
    "ONE-LINER": "ONE",
    "TLDR": "ONE",

    "SUMMARY": "SUMMARY",
    "SUM": "SUMMARY",
    "ABSTRACT": "SUMMARY",

    # Kept only for backward compatibility with v1 prompts.
    "DETAIL": "DETAIL",
    "DETAILS": "DETAIL",
    "ANALYSIS": "DETAIL",

    "TOPIC": "TOPIC",
    "TOPICS": "TOPIC",
    "TAG": "TOPIC",
    "TAGS": "TOPIC",
    "THEME": "TOPIC",
    "THEMES": "TOPIC",

    "TERM": "TERM",
    "TERMS": "TERM",
    "KEYWORD": "TERM",
    "KEYWORDS": "TERM",
    "ENTITY": "TERM",
    "ENTITIES": "TERM",

    "Q": "Q",
    "QS": "Q",
    "QUESTION": "Q",
    "QUESTIONS": "Q",
    "QUERY": "Q",
    "QUERIES": "Q",

    "SEARCH": "SEARCH",
    "SEARCHES": "SEARCH",
    "SEARCHQUERY": "SEARCH",
    "SEARCHQUERIES": "SEARCH",
    "SEARCH-QUERY": "SEARCH",
    "SEARCH-QUERIES": "SEARCH",

    # v3: the explanatory lens and the transferable idea are their own surfaces
    "THEORY": "THEORY",
    "THEORIES": "THEORY",
    "FRAMEWORK": "THEORY",
    "FRAMEWORKS": "THEORY",
    "MECHANISM": "THEORY",
    "MECHANISMS": "THEORY",
    "MODEL": "THEORY",
    "LENS": "THEORY",
    "CONCEPT": "CONCEPT",
    "CONCEPTS": "CONCEPT",
    "PRINCIPLE": "CONCEPT",
    "PRINCIPLES": "CONCEPT",
    "PATTERN": "CONCEPT",
    "PATTERNS": "CONCEPT",

    "SEEALSO": "SEEALSO",
    "SEE-ALSO": "SEEALSO",
    "RELATED": "SEEALSO",
    "RELATEDDOC": "SEEALSO",
    "RELATEDDOCS": "SEEALSO",
    "RELATEDDOCUMENT": "SEEALSO",
    "RELATEDDOCUMENTS": "SEEALSO",

    "END": "END",
}

SEVERITY = {"info": 0, "warn": 1, "error": 2}
GroundingMode = Literal["off", "warn", "drop"]


@dataclass(slots=True)
class Issue:
    severity: str
    code: str
    message: str
    line_no: int = -1


@dataclass(slots=True)
class Record:
    one_liner: str = ""
    summary: str = ""
    detail: str = ""  # legacy/optional
    topics: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    searches: list[str] = field(default_factory=list)
    theories: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    seealso: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CompileResult:
    record: Record
    issues: list[Issue] = field(default_factory=list)
    truncated: bool = False
    ok: bool = False

    # Backward-compatible aggregate. This is compiler/coverage confidence,
    # NOT a claim that the model's semantics are factually true.
    quality: float = 0.0
    format_quality: float = 0.0
    coverage_quality: float = 0.0

    def report(self) -> str:
        ordered = sorted(self.issues, key=lambda x: -SEVERITY[x.severity])
        body: list[str] = []

        for issue in ordered:
            loc = f"line {issue.line_no}" if issue.line_no >= 0 else "global"
            body.append(
                f"[{issue.severity.upper():5}] "
                f"{issue.code:24} ({loc}) {issue.message}"
            )

        verdict = "OK" if self.ok else "NEEDS RETRY/REVIEW"
        header = (
            f"quality={self.quality:.2f} "
            f"format={self.format_quality:.2f} "
            f"coverage={self.coverage_quality:.2f} "
            f"truncated={self.truncated} -> {verdict}"
        )
        return header + ("\n" + "\n".join(body) if body else "")


# ----------------------------------------------------------------------
# Lexical helpers
# ----------------------------------------------------------------------

_END_SENTINEL = re.compile(
    r"^\s*[-*\u2022]?\s*END(?:\s*[:.\-]\s*.*)?\s*$",
    re.IGNORECASE,
)

_TAG_LINE = re.compile(
    r"^\s*[-*\u2022]?\s*([A-Za-z][A-Za-z\- ]{0,22}?)\s*[:\-]\s*(.*?)\s*$"
)

# Broad enough to accept lowercase aliases and "SEARCH labor movement history".
_MISSING_COLON = re.compile(
    r"^\s*[-*\u2022]?\s*([A-Za-z][A-Za-z\- ]{0,22}?)\s+(.+?)\s*$"
)

_TAGLIKE_UNKNOWN = re.compile(
    r"^\s*[-*\u2022]?\s*[A-Za-z][A-Za-z\- ]{0,22}\s*[:\-]\s*"
)

_BULLET_NUM = re.compile(r"^[-*\u2022]?\s*(?:\d+[.)]\s+)?")


def _alias_key(tag: str) -> str:
    # Preserve hyphen-aware aliases first, then fall back to compact form.
    return re.sub(r"\s+", "", tag.strip().upper())


def _canonical_tag(tag: str) -> str | None:
    key = _alias_key(tag)
    if key in TAG_ALIASES:
        return TAG_ALIASES[key]

    compact = key.replace("-", "")
    for alias, canonical in TAG_ALIASES.items():
        if alias.replace("-", "") == compact:
            return canonical

    return None


def clean_value(value: str) -> str:
    value = _BULLET_NUM.sub("", value, count=1)
    value = value.strip().strip('"\'`*_ ')
    value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    return value.strip()


def _looks_like_known_tag_line(line: str) -> bool:
    if _END_SENTINEL.match(line):
        return True

    m = _TAG_LINE.match(line)
    if m and _canonical_tag(m.group(1)):
        return True

    m = _MISSING_COLON.match(line)
    if m and _canonical_tag(m.group(1)):
        return True

    return False


def _normalize_compare(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"[^a-z0-9/+.#-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------------
# Stage 1: normalization
# ----------------------------------------------------------------------

def normalize(raw: str, issues: list[Issue]) -> str:
    out: list[str] = []
    started = False

    for line_no, line in enumerate(raw.splitlines(), 1):
        s = line.strip()

        if not s:
            if started:
                out.append("")
            continue

        if s.startswith("```"):
            issues.append(
                Issue("info", "FENCE_STRIPPED", "removed markdown fence", line_no)
            )
            continue

        # END / END: / END. / END: done / lowercase variants.
        if _END_SENTINEL.match(s):
            if s != "END":
                issues.append(
                    Issue(
                        "info",
                        "END_NORMALIZED",
                        f"normalized sentinel {s!r} -> 'END'",
                        line_no,
                    )
                )
            s = "END"

        else:
            # Colon/dash form.
            m = _TAG_LINE.match(s)
            if m:
                raw_tag, raw_value = m.group(1), m.group(2)
                canonical = _canonical_tag(raw_tag)

                if canonical:
                    if raw_tag.strip().upper() != canonical:
                        issues.append(
                            Issue(
                                "info",
                                "TAG_NORMALIZED",
                                f"{raw_tag!r} -> {canonical!r}",
                                line_no,
                            )
                        )
                    s = f"{canonical}: {raw_value}"

            # Missing-colon form. Run this only when the line is not already
            # in explicit TAG: value / TAG - value form. Do not call
            # _looks_like_known_tag_line() here because that helper also
            # recognizes missing-colon variants and would prevent repair.
            if not _TAG_LINE.match(s):
                m2 = _MISSING_COLON.match(s)
                if m2:
                    canonical = _canonical_tag(m2.group(1))
                    if canonical and canonical != "END":
                        issues.append(
                            Issue(
                                "info",
                                "COLON_INSERTED",
                                f"missing colon after {m2.group(1)!r}",
                                line_no,
                            )
                        )
                        s = f"{canonical}: {m2.group(2)}"

        # Ignore prose before the first recognized schema line.
        if not started:
            if _looks_like_known_tag_line(s):
                started = True
            else:
                issues.append(
                    Issue(
                        "info",
                        "PREAMBLE_DROPPED",
                        f"dropped: {s[:70]!r}",
                        line_no,
                    )
                )
                continue

        out.append(s)

    return "\n".join(out)


# ----------------------------------------------------------------------
# Stage 2: tolerant parser
# ----------------------------------------------------------------------

_TEXT_ATTR = {
    "ONE": "one_liner",
    "SUMMARY": "summary",
    "DETAIL": "detail",
}

_LIST_ATTR = {
    "TOPIC": "topics",
    "TERM": "terms",
    "Q": "questions",
    "SEARCH": "searches",
    "THEORY": "theories",
    "CONCEPT": "concepts",
    "SEEALSO": "seealso",
}


def _append_continuation(rec: Record, last_tag: str, text: str) -> None:
    if last_tag in _TEXT_ATTR:
        attr = _TEXT_ATTR[last_tag]
        current = getattr(rec, attr)
        setattr(rec, attr, f"{current} {text}".strip())
        return

    if last_tag in _LIST_ATTR:
        attr = _LIST_ATTR[last_tag]
        items: list[str] = getattr(rec, attr)
        if items:
            items[-1] = f"{items[-1]} {text}".strip()


def parse(norm: str, issues: list[Issue]) -> tuple[Record, bool]:
    rec = Record()
    truncated = True
    seen_text_tags: set[str] = set()
    last_tag: str | None = None

    for line_no, line in enumerate(norm.splitlines(), 1):
        s = line.strip()
        if not s:
            continue

        if _END_SENTINEL.match(s):
            truncated = False
            break

        m = _TAG_LINE.match(s)
        if not m:
            # Wrapped lines are accepted for both text and list values.
            # Unknown "FOO: bar" lines are never silently merged.
            if (
                last_tag
                and not _TAGLIKE_UNKNOWN.match(s)
                and not _looks_like_known_tag_line(s)
            ):
                continuation = clean_value(s)
                if continuation:
                    _append_continuation(rec, last_tag, continuation)
                    issues.append(
                        Issue(
                            "info",
                            "LINE_MERGED",
                            f"wrapped line merged into {last_tag}",
                            line_no,
                        )
                    )
                continue

            issues.append(
                Issue(
                    "warn",
                    "GARBAGE_LINE",
                    f"unparseable line dropped: {s[:70]!r}",
                    line_no,
                )
            )
            last_tag = None
            continue

        raw_tag, raw_value = m.group(1), m.group(2)
        tag = _canonical_tag(raw_tag)

        if tag is None:
            issues.append(
                Issue(
                    "warn",
                    "UNKNOWN_TAG",
                    f"unknown tag {raw_tag!r} dropped",
                    line_no,
                )
            )
            last_tag = None
            continue

        if tag == "END":
            truncated = False
            break

        value = clean_value(raw_value)
        if not value:
            issues.append(
                Issue("warn", "EMPTY_VALUE", f"{tag} had empty value", line_no)
            )
            last_tag = None
            continue

        if tag in _TEXT_ATTR:
            if tag in seen_text_tags:
                # Repeated prose fields are safer to merge than to discard.
                attr = _TEXT_ATTR[tag]
                current = getattr(rec, attr)
                setattr(rec, attr, f"{current} {value}".strip())
                issues.append(
                    Issue(
                        "info",
                        "DUPLICATE_TEXT_MERGED",
                        f"additional {tag} merged into existing field",
                        line_no,
                    )
                )
            else:
                setattr(rec, _TEXT_ATTR[tag], value)
                seen_text_tags.add(tag)

            last_tag = tag
            continue

        getattr(rec, _LIST_ATTR[tag]).append(value)
        last_tag = tag

    if truncated:
        # Missing END is evidence of possible truncation, but not by itself a
        # reason to reject otherwise complete and useful output.
        issues.append(
            Issue(
                "warn",
                "NO_END_SENTINEL",
                "missing END; content retained because semantic completeness is evaluated separately",
            )
        )

    return rec, truncated


# ----------------------------------------------------------------------
# Stage 3: validation / repair
# ----------------------------------------------------------------------

def _dedupe_preserve_surface(items: list[str]) -> tuple[list[str], int]:
    seen: set[str] = set()
    out: list[str] = []

    for item in items:
        key = _normalize_compare(item)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out, len(items) - len(out)


def _question_signature(q: str) -> str:
    stop = {
        "what", "how", "why", "when", "where", "which", "who",
        "does", "do", "did", "is", "are", "was", "were",
        "the", "and", "for", "from", "with", "this", "that",
    }
    words = [
        w for w in re.findall(r"[a-z0-9]{3,}", q.casefold())
        if w not in stop
    ]
    return " ".join(sorted(words)[:5])


def _term_grounded(term: str, source_text: str) -> bool:
    """
    Lexical guard only. It is intentionally conservative.

    Because callers often pass excerpts rather than the entire document,
    absence from source_text is NOT automatically treated as hallucination.
    `grounding_mode` controls whether an ungrounded term is merely reported
    or actually dropped.
    """
    if not source_text.strip():
        return True

    src = _normalize_compare(source_text)
    term_norm = _normalize_compare(term)

    if not term_norm:
        return False

    if term_norm in src:
        return True

    term_tokens = re.findall(r"[a-z0-9][a-z0-9/+.#-]*", term_norm)
    src_tokens = set(re.findall(r"[a-z0-9][a-z0-9/+.#-]*", src))

    if not term_tokens:
        return False

    if len(term_tokens) == 1:
        return term_tokens[0] in src_tokens

    meaningful = [t for t in term_tokens if len(t) >= 3] or term_tokens
    return all(token in src_tokens for token in meaningful)


def _repair_core(rec: Record, issues: list[Issue]) -> None:
    # SUMMARY is the preferred semantic center. Reuse available prose instead
    # of rejecting good content merely because the model skipped a tag.
    if not rec.summary:
        if rec.detail:
            rec.summary = rec.detail
            issues.append(
                Issue("info", "SUMMARY_FALLBACK", "SUMMARY recovered from DETAIL")
            )
        elif rec.one_liner:
            rec.summary = rec.one_liner
            issues.append(
                Issue("info", "SUMMARY_FALLBACK", "SUMMARY recovered from ONE")
            )

    if not rec.one_liner and rec.summary:
        # Deterministic first-sentence recovery; no new semantic content added.
        first = re.split(r"(?<=[.!?])\s+", rec.summary.strip(), maxsplit=1)[0]
        rec.one_liner = first
        issues.append(
            Issue("info", "ONE_FALLBACK", "ONE recovered from first SUMMARY sentence")
        )


def validate(
    rec: Record,
    issues: list[Issue],
    source_text: str = "",
    grounding_mode: GroundingMode = "warn",
) -> None:
    _repair_core(rec, issues)

    # Preserve model surface form while deduping case/spacing variants.
    for attr in ("topics", "terms", "questions", "searches", "theories", "concepts", "seealso"):
        values = getattr(rec, attr)
        deduped, removed = _dedupe_preserve_surface(values)
        setattr(rec, attr, deduped)
        if removed:
            issues.append(
                Issue(
                    "info",
                    "DEDUPED",
                    f"removed {removed} duplicate value(s) from {attr}",
                )
            )

    # Cheap near-duplicate question removal.
    signatures: set[str] = set()
    kept_questions: list[str] = []

    for q in rec.questions:
        q = q.strip()
        if not q:
            continue

        if not q.endswith("?"):
            q = q.rstrip(".!") + "?"
            issues.append(
                Issue("info", "QUESTIONMARK_ADDED", f"normalized question: {q!r}")
            )

        sig = _question_signature(q)
        if sig and sig in signatures:
            issues.append(
                Issue("info", "DUP_QUESTION", f"dropped near-duplicate: {q[:60]!r}")
            )
            continue

        if sig:
            signatures.add(sig)
        kept_questions.append(q)

    rec.questions = kept_questions

    # SEARCH should look like a search query, but do not reject a good semantic
    # query simply because the model used punctuation or more words.
    normalized_searches: list[str] = []
    for search in rec.searches:
        s = search.strip()
        if s.endswith("?"):
            s = s[:-1].rstrip()
            issues.append(
                Issue("info", "SEARCH_QMARK_REMOVED", f"removed '?' from {search!r}")
            )
        normalized_searches.append(s)
    rec.searches = normalized_searches

    # TERM grounding is advisory by default because source_text may only contain
    # excerpts. Use grounding_mode="drop" only when source_text is authoritative.
    if source_text and grounding_mode != "off":
        grounded_terms: list[str] = []

        for term in rec.terms:
            if _term_grounded(term, source_text):
                grounded_terms.append(term)
                continue

            issues.append(
                Issue(
                    "warn" if grounding_mode == "warn" else "info",
                    "UNGROUNDED_TERM",
                    f"term not lexically found in supplied source_text: {term!r}",
                )
            )

            if grounding_mode != "drop":
                grounded_terms.append(term)

        rec.terms = grounded_terms

    # Soft coverage diagnostics + defensive max caps.
    for tag, target in TARGET_COUNTS.items():
        attr = _LIST_ATTR[tag]
        values = getattr(rec, attr)
        target_lo, _target_hi = target
        hard_max = HARD_MAX[tag]

        if len(values) > hard_max:
            setattr(rec, attr, values[:hard_max])
            issues.append(
                Issue(
                    "info",
                    "LIST_CAPPED",
                    f"{tag} capped at {hard_max} values (had {len(values)})",
                )
            )
            values = getattr(rec, attr)

        if len(values) < target_lo:
            # This is intentionally informational: right-but-short output should
            # normally index rather than trigger an unnecessary retry.
            issues.append(
                Issue(
                    "info",
                    "BELOW_TARGET",
                    f"{tag}: got {len(values)}, preferred >= {target_lo}",
                )
            )

    # Only lack of a semantic core is fatal.
    if not rec.one_liner and not rec.summary:
        issues.append(
            Issue(
                "error",
                "NO_SEMANTIC_CORE",
                "no usable ONE, SUMMARY, or legacy DETAIL content was produced",
            )
        )


# ----------------------------------------------------------------------
# Stage 4: scoring / emission
# ----------------------------------------------------------------------

def _format_quality(issues: list[Issue]) -> float:
    """
    Formatting/structural confidence.

    Benign automatic repairs are free. Warnings are light penalties.
    True compiler errors are expensive.
    """
    score = 1.0
    for issue in issues:
        if issue.severity == "error":
            score -= 0.40
        elif issue.severity == "warn":
            score -= 0.04
        # info repairs intentionally do not reduce format quality

    return max(0.0, min(1.0, score))


def _coverage_quality(rec: Record) -> float:
    """
    Measures how much of the preferred retrieval profile was produced.
    It does not decide correctness.
    """
    components: list[float] = []

    for tag, (target_lo, _target_hi) in TARGET_COUNTS.items():
        values = getattr(rec, _LIST_ATTR[tag])
        if target_lo == 0:
            components.append(1.0)
        else:
            components.append(min(1.0, len(values) / target_lo))

    # Semantic core receives its own full component.
    components.append(1.0 if rec.one_liner and rec.summary else 0.5)

    return sum(components) / len(components)


def _quality(format_quality: float, coverage_quality: float) -> float:
    # Deliberately tolerant: correctness/usable structure outranks perfect count
    # adherence. Coverage can reduce confidence without creating false failures.
    score = 0.75 * format_quality + 0.25 * coverage_quality
    return max(0.0, min(1.0, score))


def semantic_artifact(rec: Record) -> dict:
    """The compiled semantic artifact (owner spec 2026-09-07): plain fields, atomic lists."""
    return {
        "one": rec.one_liner, "summary": rec.summary, "topics": list(rec.topics), "terms": list(rec.terms),
        "questions": list(rec.questions), "searches": list(rec.searches), "theories": list(rec.theories),
        "concepts": list(rec.concepts), "seealso": list(rec.seealso),
    }


def profile_valid(rec: Record) -> tuple[bool, list[str]]:
    """The tolerant readiness contract (owner 2026-09-07) — the part the compiler can decide:
    a semantic core (ONE or SUMMARY) and a query hook (Q or SEARCH). The identity and theme
    vectors and at least one Q/SEARCH vector are the projector's half of the same contract.
    Exact counts are never required; END is never required; TOPIC / TERM are preferred, not required."""
    missing: list[str] = []
    if not (rec.one_liner or rec.summary):
        missing.append("semantic_core")
    if not (rec.questions or rec.searches):
        missing.append("query_hook")
    return (not missing), missing


def emit(rec: Record, doc_id: str) -> dict:
    """
    Emit specialized retrieval surfaces.

    Existing v1 keys remain:
      embed_topic
      embed_theme
      embed_questions

    v2 adds:
      embed_search
      embed_seealso

    Empty optional surfaces are omitted so downstream embedding workers do not
    accidentally embed empty strings.
    """
    identity_parts = [rec.one_liner]
    if rec.topics:
        identity_parts.append("Topics: " + ", ".join(rec.topics))
    embed_topic = "\n".join(x for x in identity_parts if x).strip()

    theme_parts = [rec.summary]
    if rec.detail and _normalize_compare(rec.detail) != _normalize_compare(rec.summary):
        theme_parts.append(rec.detail)
    embed_theme = "\n".join(x for x in theme_parts if x).strip()

    payload = {
        "doc_id": doc_id,
        "schema_version": SCHEMA_VERSION,
        # legacy pooled surfaces (v1 / v2 consumers) — the projector must NOT embed these; see `representations`
        "embed_topic": embed_topic,
        "embed_theme": embed_theme,
        "embed_questions": "\n".join(rec.questions),
        "metadata": {
            "topics": rec.topics,
            "terms": rec.terms,
            "theories": rec.theories,
            "concepts": rec.concepts,
            "seealso": rec.seealso,
        },
        # v3: ATOMIC units — the compiler produces semantic units, the projector produces vectors
        # (str → one vector, list[str] → one vector PER item). Never five long strings.
        "representations": {
            "identity": embed_topic,
            "theme": embed_theme,
            "questions": list(rec.questions),
            "searches": list(rec.searches),
            "theories": list(rec.theories),
            "concepts": list(rec.concepts),
            "seealso": list(rec.seealso),
        },
        "artifact": semantic_artifact(rec),
    }

    if rec.searches:
        payload["embed_search"] = "\n".join(rec.searches)

    if rec.seealso:
        payload["embed_seealso"] = "\n".join(rec.seealso)

    return payload


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def compile_llm_output(
    raw: str,
    doc_id: str = "",
    source_text: str = "",
    grounding_mode: GroundingMode = "warn",
) -> CompileResult:
    """
    Compile raw tagged-line model text.

    `grounding_mode`:
      off  - do not inspect TERM grounding
      warn - report lexical misses but preserve terms (default; best for excerpts)
      drop - remove lexically ungrounded terms (best only when source_text is complete)
    """
    if grounding_mode not in {"off", "warn", "drop"}:
        raise ValueError("grounding_mode must be 'off', 'warn', or 'drop'")

    issues: list[Issue] = []
    norm = normalize(raw, issues)
    rec, truncated = parse(norm, issues)
    validate(rec, issues, source_text, grounding_mode)

    ok = not any(issue.severity == "error" for issue in issues)
    fmt = _format_quality(issues)
    coverage = _coverage_quality(rec)

    return CompileResult(
        record=rec,
        issues=issues,
        truncated=truncated,
        ok=ok,
        quality=_quality(fmt, coverage),
        format_quality=fmt,
        coverage_quality=coverage,
    )


def index_document(
    raw: str,
    doc_id: str,
    source_text: str = "",
    min_quality: float = 0.70,
    grounding_mode: GroundingMode = "warn",
):
    """
    Backward-compatible one-liner.

    Returns payload dict when accepted, otherwise None.
    """
    result = compile_llm_output(
        raw,
        doc_id=doc_id,
        source_text=source_text,
        grounding_mode=grounding_mode,
    )

    if result.ok and result.quality >= min_quality:
        return emit(result.record, doc_id)

    return None


def index_document_with_result(
    raw: str,
    doc_id: str,
    source_text: str = "",
    min_quality: float = 0.70,
    grounding_mode: GroundingMode = "warn",
) -> tuple[dict | None, CompileResult]:
    """
    Production-worker variant. Always returns the CompileResult so retry logic
    can distinguish a true failure from harmless format drift.
    """
    result = compile_llm_output(
        raw,
        doc_id=doc_id,
        source_text=source_text,
        grounding_mode=grounding_mode,
    )

    payload = None
    if result.ok and result.quality >= min_quality:
        payload = emit(result.record, doc_id)

    return payload, result
