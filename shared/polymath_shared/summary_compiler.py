"""SUMMARY-COMPILER-V1 — the deterministic parent / section / document
summary compiler (owner spec, 2026-08-30).

Model-free, deterministic, source-derived, hierarchy-aware, triple-aware,
coverage-preserving, bounded, provenance-preserving. No GLiNER, no spaCy,
no generation: sentences are verbatim source slices with chunk offsets.

Pipeline (one call per parent; the same pattern one level up for the
document):

    child sentences (regex, offsets kept)
      → importance = trusted-triple support + lexical salience (TF-IDF
        against the document background) + centrality + structural quality
      → coverage-first selection (best sentence of EVERY child first)
      → Jaccard de-duplication (stronger representative survives)
      → source-order restoration
      → {summary, relations (trusted triples only), keywords}
      → one serialized embed text

The LLM adapter (`digest_variant`) never replaces the deterministic card;
it only decides which variant is ACTIVE for the routing slot.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

COMPILER_CONTRACT = "summary-compiler-v1"

SECTION_MAX_SENTENCES = 6
SECTION_MAX_CHARS = 1200
DOC_MAX_SENTENCES = 12
DOC_MAX_CHARS = 1600
MAX_RELATIONS_SECTION = 5
MAX_RELATIONS_DOCUMENT = 8
MAX_KEYWORDS = 8
DEDUPE_JACCARD = 0.8
MIN_SENTENCE_CHARS = 20
MAX_SENTENCE_CHARS = 600
PREFERRED_SENTENCE_CHARS = 220     # coverage picks prefer compact sentences

# Weights (part of the contract; a change re-profiles).
W_TRIPLE, W_SALIENCE, W_CENTRALITY, W_QUALITY = 1.0, 1.0, 0.5, 0.5

_WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
_STOP = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are was were be "
    "been being that this these those it its they them their there here which who whom whose "
    "what when where why how not no nor so such than too very can could may might must shall "
    "should will would do does did done have has had i you he she we us our your his her him "
    "me my own into over under again once more most other some any all both each few between "
    "during before after above below up down out off also just about because while".split())
# Sentence boundary: terminal punctuation + space + capital/digit/quote, or
# a newline — never inside "i.e." / "e.g." / "vs." / "etc." (fixed-width
# lookbehinds), never mid-token.
_SPLIT_RE = re.compile(
    r"(?<!\bi\.e\.)(?<!\be\.g\.)(?<!\bvs\.)(?<!\betc\.)(?<!\bcf\.)"
    r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n+")
_DIGIT_RE = re.compile(r"\d")
_TERMINAL_RE = re.compile(r"[.!?][\"')\]]?\s*$")
_ALPHA_TOKEN_RE = re.compile(r"[A-Za-z]+")

RELATION_PHRASES: dict[str, str] = {
    # 17 ontology ids + RELATED_TO (workers/llm_direct.py writes these)
    "IS_A": "is a", "PART_OF": "is part of", "HAS_PROPERTY": "has",
    "SAME_AS": "is the same as", "USES": "uses", "REQUIRES": "requires",
    "PRODUCES": "produces", "CAUSES": "causes", "REGULATES": "regulates",
    "CORRELATES_WITH": "correlates with", "CONSTRAINED_BY": "is constrained by",
    "PRECEDES": "precedes", "MEASURES": "measures", "LOCATED_IN": "is located in",
    "ALTERNATIVE_TO": "is an alternative to", "OPPOSES": "opposes",
    "ACTS_ON": "acts on", "RELATED_TO": "is related to",
    # rule-pack (compiler-era) ids still present in older facts
    "trained_on": "was trained on", "evaluated_on": "was evaluated on",
    "released_on": "was released on", "published_on": "was published on",
    "occurred_at": "occurred at", "introduced": "introduces", "proposed": "proposes",
    "uses": "uses", "uses_method": "uses the method", "contains_component": "includes",
    "part_of": "is part of", "member_of": "is a member of", "is_a": "is a",
    "instance_of": "is an instance of", "similar_to": "is similar to",
    "located_in": "is located in", "derived_from": "derives from",
    "acquired": "acquired", "created": "created", "developed": "developed",
    "introduced_by": "was introduced by", "proposed_by": "was proposed by",
    "evaluated_against": "was evaluated against", "compared_against": "was compared against",
    "depends_on": "depends on", "uses_component": "uses", "founded": "founded",
    "employs": "employs", "causes": "causes", "influences": "influences",
    "measured_by": "is measured by", "associated_with": "is associated with",
    "transforms_into": "transforms into", "enables": "enables", "owns": "owns",
    "leads": "leads", "has_role": "has the role", "subsidiary_of": "is a subsidiary of",
    "implemented_with": "is implemented with",
}


def render_relation(predicate: str, subject: str, obj: str) -> str | None:
    phrase = RELATION_PHRASES.get(predicate) or RELATION_PHRASES.get(str(predicate).upper())
    subject, obj = (subject or "").strip(), (obj or "").strip()
    if not (phrase and subject and obj):
        return None
    return f"{subject} {phrase} {obj}."


@dataclass(frozen=True)
class Sentence:
    child_id: str
    child_index: int
    ordinal: int
    start: int          # offsets inside the child chunk text
    end: int
    text: str


@dataclass
class CompiledSummary:
    summary: str
    sentences: list[dict]           # provenance, source order
    relations: list[str]
    relation_items: list[dict]
    keywords: list[str]
    coverage: dict
    embed_text: str
    contract: str = COMPILER_CONTRACT
    variant: str = "deterministic"


# ----------------------------------------------------------------- tokens

def tokens(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall((text or "").lower()) if t not in _STOP]


def build_background(texts: list[str]) -> dict[str, int]:
    """Document frequency of content tokens over the given units (the
    document's children for a section, its parents for the document)."""
    df: dict[str, int] = {}
    for t in texts:
        for w in set(tokens(t)):
            df[w] = df.get(w, 0) + 1
    df["__n__"] = len(texts)
    return df


def _idf(word: str, background: dict[str, int]) -> float:
    n = max(1, int(background.get("__n__", 1)))
    return math.log((n + 1.0) / (background.get(word, 0) + 1.0)) + 1.0


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Verbatim sentences with (start, end) offsets inside `text`."""
    out: list[tuple[int, int, str]] = []
    pos = 0
    for m in _SPLIT_RE.finditer(text or ""):
        seg = text[pos:m.start()]
        if seg.strip():
            s = pos + (len(seg) - len(seg.lstrip()))
            e = pos + len(seg.rstrip())
            out.append((s, e, text[s:e]))
        pos = m.end()
    tail = (text or "")[pos:]
    if tail.strip():
        s = pos + (len(tail) - len(tail.lstrip()))
        e = pos + len(tail.rstrip())
        out.append((s, e, text[s:e]))
    return out


def structural_quality(sentence: str) -> float:
    """0 for fragments / dumps / headings / OCR garbage, 1 for prose."""
    from polymath_shared.region_role import signals as _region_signals
    words = sentence.split()
    n = len(words)
    if n < 4 or len(sentence) < MIN_SENTENCE_CHARS or len(sentence) > MAX_SENTENCE_CHARS:
        return 0.0
    alpha = sum(1 for w in words if _ALPHA_TOKEN_RE.fullmatch(w.strip(".,;:()\"'")))
    alpha_ratio = alpha / n
    if alpha_ratio < 0.4 or sentence.lstrip().startswith("#"):
        return 0.0
    if sum(1 for w in words if _DIGIT_RE.search(w)) > n / 2:
        return 0.0                                  # log / packet / table dump
    sig = _region_signals(sentence)
    if sig["common_share"] < 0.15 and sig["mean_alpha_len"] < 4.5:
        return 0.0                                  # OCR garbage ("ee oe Se RE")
    if sig["mean_alpha_len"] < 3.2 or sig["symbol_share"] >= 0.05 or sig["digit_share"] >= 0.2:
        return 0.0                                  # OCR debris / markup / numeric dumps
    score = 1.0
    if not (6 <= n <= 60):
        score -= 0.5
    if alpha_ratio < 0.6 or not _TERMINAL_RE.search(sentence):
        score -= 0.5
    if sentence.rstrip().endswith("?"):
        score -= 0.25                               # explanations outrank question stems
    return max(0.0, score)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --------------------------------------------------------------- scoring

def _score_sentences(sents: list[Sentence], background: dict[str, int],
                     triples: list[dict]) -> dict[Sentence, dict]:
    tok = {s: tokens(s.text) for s in sents}
    centroid: Counter = Counter()
    for s in sents:
        centroid.update(tok[s])
    cnorm = math.sqrt(sum(v * v for v in centroid.values())) or 1.0
    raw_sal = {}
    for s in sents:
        uniq = set(tok[s])
        raw_sal[s] = (sum(_idf(w, background) for w in uniq) / math.sqrt(1 + len(uniq))) if uniq else 0.0
    max_sal = max(raw_sal.values(), default=0.0) or 1.0
    scored: dict[Sentence, dict] = {}
    for s in sents:
        tf = Counter(tok[s])
        snorm = math.sqrt(sum(v * v for v in tf.values())) or 1.0
        centrality = sum(tf[w] * centroid[w] for w in tf) / (snorm * cnorm)
        trusted = untrusted = 0
        for t in triples:
            if t.get("chunk_id") != s.child_id or t.get("start") is None:
                continue
            if t["start"] < s.end and t["end"] > s.start:
                if t.get("trusted"):
                    trusted += 1
                else:
                    untrusted += 1
        triple = min(2, trusted) * 1.0 + min(2, untrusted) * 0.5
        quality = structural_quality(s.text)
        salience = raw_sal[s] / max_sal
        total = (W_TRIPLE * triple + W_SALIENCE * salience
                 + W_CENTRALITY * centrality + W_QUALITY * quality)
        scored[s] = {"score": round(total, 6), "salience": round(salience, 4),
                     "centrality": round(centrality, 4), "quality": quality,
                     "triples_trusted": trusted, "triples_untrusted": untrusted}
    return scored


def _regions(n_units: int, max_regions: int) -> list[list[int]]:
    """Consecutive coverage regions: one per unit while units fit the
    sentence budget, otherwise `max_regions` near-equal groups of ordered
    units (owner spec: "apply the same rule across ordered coverage
    regions" — a 181-parent document keeps every region represented
    instead of every parent)."""
    if n_units <= max_regions:
        return [[i] for i in range(n_units)]
    out: list[list[int]] = []
    size, extra = divmod(n_units, max_regions)
    start = 0
    for r in range(max_regions):
        end = start + size + (1 if r < extra else 0)
        out.append(list(range(start, end)))
        start = end
    return out


def _select(units: list[list[Sentence]], scored: dict[Sentence, dict], *,
            max_sentences: int, max_chars: int) -> tuple[list[Sentence], list[int], int]:
    """Coverage first (best usable sentence per region, in order), then
    the strongest remaining sentences; returns (chosen, uncovered_unit_indexes,
    regions)."""
    key = lambda s: (-scored[s]["score"], s.child_index, s.start)  # noqa: E731
    chosen: list[Sentence] = []
    chosen_set: set[Sentence] = set()
    uncovered: list[int] = []
    regions = _regions(len(units), max_sentences)
    for region in regions:
        usable = [s for idx in region for s in units[idx] if scored[s]["quality"] > 0.0]
        if not usable:
            uncovered.extend(region)
            continue
        compact = [s for s in usable if len(s.text) <= PREFERRED_SENTENCE_CHARS] or usable
        best = sorted(compact, key=key)[0]
        chosen.append(best)
        chosen_set.add(best)
    pool = sorted((s for unit in units for s in unit
                   if s not in chosen_set and scored[s]["quality"] > 0.0), key=key)
    chars = sum(len(s.text) for s in chosen)
    for s in pool:
        if len(chosen) >= max_sentences or chars + len(s.text) + 1 > max_chars:
            break
        chosen.append(s)
        chosen_set.add(s)
        chars += len(s.text) + 1
    return chosen, uncovered, len(regions)


def _dedupe(chosen: list[Sentence], scored: dict[Sentence, dict]) -> list[Sentence]:
    kept: list[Sentence] = []
    for s in sorted(chosen, key=lambda x: (-scored[x]["score"], x.child_index, x.start)):
        st = set(tokens(s.text))
        if any(_jaccard(st, set(tokens(k.text))) >= DEDUPE_JACCARD for k in kept):
            continue
        kept.append(s)
    return sorted(kept, key=lambda x: (x.child_index, x.start))


def _fit(chosen: list[Sentence], scored: dict[Sentence, dict],
         max_chars: int) -> tuple[list[Sentence], bool]:
    """HARD bound on the summary length. Extras go first; a unit's
    reserved sentence is dropped only as a last resort (weakest first),
    and that loss is reported as `truncated` in the receipt."""
    total = sum(len(s.text) + 1 for s in chosen)
    if total <= max_chars + 1:
        return chosen, False
    seen_units: set[int] = set()
    reserved: list[Sentence] = []
    extras: list[Sentence] = []
    for s in chosen:                       # chosen is in selection order: reserved first
        if s.child_index in seen_units:
            extras.append(s)
        else:
            seen_units.add(s.child_index)
            reserved.append(s)
    keep = list(reserved)
    used = sum(len(s.text) + 1 for s in keep)
    for s in extras:
        if used + len(s.text) + 1 <= max_chars + 1:
            keep.append(s)
            used += len(s.text) + 1
    truncated = False
    while used > max_chars + 1 and len(keep) > 1:
        weakest = min(keep, key=lambda x: (scored[x]["score"], -x.child_index))
        keep.remove(weakest)
        used -= len(weakest.text) + 1
        truncated = True
    keep.sort(key=lambda x: (x.child_index, x.start))
    return keep, truncated


def _keywords(prose_texts: list[str], background: dict[str, int],
              triple_items: list[dict], *, limit: int = MAX_KEYWORDS) -> list[str]:
    """Keywords come from trusted triple endpoints, then from PROSE
    sentences only (structural quality > 0) — OCR debris that repeats
    ("eee", "rere") never has prose to live in."""
    out: list[str] = []
    seen: set[str] = set()
    for t in triple_items:
        for surf in (t.get("subject"), t.get("object")):
            k = (surf or "").strip()
            if k and k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
    tf: Counter = Counter()
    for text in prose_texts:
        toks = [t for t in tokens(text) if not _DIGIT_RE.search(t) and not _debris(t)]
        tf.update(t for t in toks if len(t) >= 4)
        tf.update(f"{a} {b}" for a, b in zip(toks, toks[1:])
                  if len(a) >= 3 and len(b) >= 3 and a != b)
    n = max(1, int(background.get("__n__", 1)))
    min_df = 1 if n < 3 else (2 if n < 50 else 3)
    scored = []
    for term, c in tf.items():
        df = background.get(term, 0) if " " not in term else min(
            background.get(term.split()[0], 0), background.get(term.split()[1], 0))
        if df < min_df:
            continue                    # hapax / OCR debris never becomes a keyword
        scored.append((-(c * _idf(term, background)), term))
    chosen_terms: list[str] = []
    for _neg, term in sorted(scored):
        if len(out) >= limit:
            break
        if term in seen:
            continue
        parts = term.split()
        # a unigram already carried by a chosen bigram, or a plural/singular
        # twin of a chosen term, adds no routing signal
        if any(term in c.split() for c in chosen_terms if " " in c):
            continue
        if any(t == term + "s" or term == t + "s" for t in chosen_terms):
            continue
        seen.add(term)
        chosen_terms.append(term)
        out.append(term)
        if len(parts) == 2:
            seen.update(parts)
    return out[:limit]


def _debris(token: str) -> bool:
    """OCR debris that survives inside a prose sentence: short tokens made
    of one or two distinct letters ("ee", "eee", "rere")."""
    return len(token) <= 5 and len(set(token)) <= 2


def serialize(summary: str, relations: list[str], keywords: list[str]) -> str:
    """The ONE deterministic text representation that is embedded. Empty
    capsules omit their block so the vector carries source signal only."""
    parts = [f"SUMMARY:\n{summary.strip()}"]
    if relations:
        parts.append("RELATIONSHIPS:\n" + "\n".join(relations))
    if keywords:
        parts.append("KEY CONCEPTS:\n" + "; ".join(keywords))
    return "\n\n".join(parts)


# ------------------------------------------------------------- compilers

def _triple_items(triples: list[dict], chunk_ids: set[str] | None, limit: int) -> list[dict]:
    items: list[dict] = []
    seen: set[tuple] = set()
    for t in sorted((t for t in triples if t.get("trusted")),
                    key=lambda t: (t.get("order", 0), t.get("start") or 0)):
        if chunk_ids is not None and t.get("chunk_id") not in chunk_ids:
            continue
        key = (t.get("predicate"), (t.get("subject") or "").lower(), (t.get("object") or "").lower())
        if key in seen:
            continue
        rendered = render_relation(t.get("predicate", ""), t.get("subject", ""), t.get("object", ""))
        if not rendered:
            continue
        seen.add(key)
        items.append({"predicate": t.get("predicate"), "subject": t.get("subject"),
                      "object": t.get("object"), "text": rendered,
                      "fact_id": t.get("fact_id"), "chunk_id": t.get("chunk_id")})
        if len(items) >= limit:
            break
    return items


def _compile(units: list[dict], *, background: dict[str, int] | None,
             triples: list[dict], max_sentences: int, max_chars: int,
             max_relations: int, level: str, single_child_overlap: bool) -> CompiledSummary:
    unit_texts = [u.get("text") or "" for u in units]
    if background is None or "__n__" not in background:
        background = build_background(unit_texts)
    sents_by_unit: list[list[Sentence]] = []
    for idx, u in enumerate(units):
        sents = [Sentence(child_id=u["chunk_id"], child_index=idx, ordinal=k, start=s, end=e, text=t)
                 for k, (s, e, t) in enumerate(split_sentences(u.get("text") or ""))]
        sents_by_unit.append(sents)
    all_sents = [s for unit in sents_by_unit for s in unit]
    scored = _score_sentences(all_sents, background, triples)
    chosen, uncovered, n_regions = _select(
        sents_by_unit, scored, max_sentences=max_sentences, max_chars=max_chars)
    chosen = _dedupe(chosen, scored)
    chosen, truncated = _fit(chosen, scored, max_chars)
    covered_units = {s.child_index for s in chosen}
    summary = " ".join(s.text for s in chosen)
    unit_ids = {u["chunk_id"] for u in units}
    rel_items = _triple_items(triples, unit_ids if level == "section" else None, max_relations)
    relations = [r["text"] for r in rel_items]
    prose_texts = [s.text for s in all_sents if scored[s]["quality"] > 0.0]
    keywords = _keywords(prose_texts, background, rel_items)
    no_prose = [i for i, unit in enumerate(sents_by_unit)
                if not any(scored[s]["quality"] > 0.0 for s in unit)]
    provenance = [{
        "chunk_id": s.child_id, "child_index": s.child_index, "start": s.start, "end": s.end,
        "reason": "coverage-representative-sentence" if s is next(
            (x for x in chosen if x.child_index == s.child_index), None) else "salience-extra",
        "score": scored[s]["score"], "triples_trusted": scored[s]["triples_trusted"],
        "single_child_overlap": single_child_overlap,
    } for s in chosen]
    region_mode = n_regions < len(units)
    # `uncovered` = STARVED units: prose was available and none of it was
    # selected (in region mode: a region with prose left empty). Units
    # without any usable sentence are `no_prose_units` — a property of the
    # source, not a compiler failure; the verifier gates on starvation only.
    if region_mode:
        starved = [units[i]["chunk_id"] for i in uncovered if i not in no_prose]
    else:
        starved = [units[i]["chunk_id"] for i in range(len(units))
                   if i not in covered_units and i not in no_prose]
    coverage = {
        "level": level,
        "units_total": len(units),
        "units_covered": len(covered_units),
        "regions": n_regions,
        "uncovered": starved,
        "no_prose_units": [units[i]["chunk_id"] for i in no_prose],
        "sentences": len(chosen),
        "chars": len(summary),
        "truncated": truncated,
        "relations": len(relations),
        "keywords": len(keywords),
        "contract": COMPILER_CONTRACT,
    }
    return CompiledSummary(summary=summary, sentences=provenance, relations=relations,
                           relation_items=rel_items, keywords=keywords, coverage=coverage,
                           embed_text=serialize(summary, relations, keywords))


def compile_section(children: list[dict], *, parent_id: str,
                    background: dict[str, int] | None = None,
                    facts: list[dict] | None = None,
                    max_sentences: int = SECTION_MAX_SENTENCES,
                    max_chars: int = SECTION_MAX_CHARS) -> CompiledSummary:
    """children: [{chunk_id, text}] in source order (noise already
    removed by the caller). facts: [{predicate, subject, object, chunk_id,
    start, end, trusted, fact_id}] linked to those chunks."""
    units = [{"chunk_id": c.get("chunk_id") or c.get("id"), "text": c.get("text") or ""}
             for c in children]
    return _compile(units, background=background, triples=list(facts or []),
                    max_sentences=max_sentences, max_chars=max_chars,
                    max_relations=MAX_RELATIONS_SECTION, level="section",
                    single_child_overlap=len(units) == 1)


def compile_document(parents: list[dict], *, doc_id: str,
                     facts: list[dict] | None = None,
                     max_sentences: int = DOC_MAX_SENTENCES,
                     max_chars: int = DOC_MAX_CHARS) -> CompiledSummary:
    """Hierarchical step: parents: [{chunk_id, summary?, text?}] — the
    compiled plain summary of each parent when available, else its text.
    Coverage is preserved across the ordered parents."""
    units = [{"chunk_id": p["chunk_id"], "text": (p.get("summary") or p.get("text") or "")}
             for p in parents]
    return _compile(units, background=None, triples=list(facts or []),
                    max_sentences=max_sentences, max_chars=max_chars,
                    max_relations=MAX_RELATIONS_DOCUMENT, level="document",
                    single_child_overlap=False)


# -------------------------------------------------------- digest adapter

DIGEST_MIN_WORDS = 6


def digest_variant(digests: list[dict], deterministic: CompiledSummary) -> CompiledSummary | None:
    """The LLM adapter: the extractor's per-neighborhood digests
    (`central_claim`, `main_mechanism`, `retrieval_uses`) for one parent,
    rendered as the SUMMARY block over the SAME deterministic relations and
    keywords. Returns None when no clean digest exists — the deterministic
    card then stays active. Never invents relations."""
    from polymath_shared.region_role import signals
    claims: list[str] = []
    uses: list[str] = []
    for d in digests or []:
        claim = " ".join(x.strip() for x in ((d.get("central_claim") or ""), (d.get("main_mechanism") or "")) if x and x.strip())
        if claim and claim not in claims:
            claims.append(claim)
        for u in d.get("retrieval_uses") or []:
            u = (u or "").strip()
            if u and u not in uses:
                uses.append(u)
    text = " ".join(claims).strip()
    if len(text.split()) < DIGEST_MIN_WORDS:
        return None
    sig = signals(text)
    if sig["common_share"] < 0.15 and sig["mean_alpha_len"] < 4.5:
        return None                                   # garbage in, no adapter out
    keywords = list(deterministic.keywords)
    for u in uses:
        if u.lower() not in {k.lower() for k in keywords} and len(keywords) < MAX_KEYWORDS + 3:
            keywords.append(u)
    return CompiledSummary(
        summary=text, sentences=[], relations=list(deterministic.relations),
        relation_items=list(deterministic.relation_items), keywords=keywords,
        coverage={**deterministic.coverage, "adapter": "llm_digest", "digests": len(claims)},
        embed_text=serialize(text, deterministic.relations, keywords),
        variant="llm_digest")


def contract_fingerprint() -> dict:
    return {"contract": COMPILER_CONTRACT,
            "weights": [W_TRIPLE, W_SALIENCE, W_CENTRALITY, W_QUALITY],
            "caps": [SECTION_MAX_SENTENCES, SECTION_MAX_CHARS, DOC_MAX_SENTENCES, DOC_MAX_CHARS,
                     MAX_RELATIONS_SECTION, MAX_RELATIONS_DOCUMENT, MAX_KEYWORDS],
            "dedupe_jaccard": DEDUPE_JACCARD, "digest_min_words": DIGEST_MIN_WORDS}
