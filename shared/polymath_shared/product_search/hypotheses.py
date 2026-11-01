"""PRODUCT HYPOTHESES (product-search-v1): how a product turn reads the corpus, what the synthesizer is asked to write, and how its
machine-readable hypothesis block is read back.

  * `steer_plan` / `steer_text` — retrieval is steered toward HYPOTHESIS MATERIAL (frictions, workarounds, unmet jobs, audiences,
    recurring complaints, use situations) over whatever corpus the turn chose. On a compiled plan: up to three USER-origin aspect
    subqueries inside the compiler's own cap (`chat_plan.MAX_QUERIES`, `MAX_QUERIES_FACETS` on a facet plan), each its own facet
    while `MAX_FACETS` allows; a plan that would not retrieve is made to (`plan_for_evidence_route`, rule
    `product_search:retrieval_required`). Without a compiled plan (compiler off / shadow): one deterministic addition to the
    retrieval text. No seed needed: with neither a seed nor an audience the aspects are generic discovery over the corpus.
    DOCUMENT-SKELETON-V1 holds: the skeleton may ROUTE, the evidence stays real passages, and every hypothesis must cite them.
  * `contract_block` — the PRODUCT HYPOTHESIS contract appended to the synthesis system prompt: 3–5 hypotheses, labelled as
    hypotheses, each citing the [S#] passages that inspired it, never "the corpus doesn't recommend products", ending with ONE
    fenced `product-hypotheses` JSON block.
  * `parse_block` — that block read back deterministically, robust to small drift (another fence label, ~~~ fences, a missing
    closing fence, trailing commas, smart quotes, single quotes, a wrapper object, key aliases, tags written "[S2]" or 2). A
    failed read is status `fallback` with its reason — the caller then searches the intent's own terms, receipted, never silent.
Pure: no I/O."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

from polymath_shared.chat_plan import (
    MAX_FACETS,
    MAX_QUERIES,
    MAX_QUERIES_FACETS,
    CompiledQuery,
    _clean_query,
    _has_instruction_tokens,
    plan_for_evidence_route,
    sync_facets,
)

CONTRACT_NAME = "product-hypothesis-contract-v1"
BLOCK_LABEL = "product-hypotheses"
STEER_RULE = "product_search:retrieval_required"
ASPECT_IDS = ("ps1", "ps2", "ps3")
ASPECT_WEIGHT = 0.85
MAX_HYPOTHESES = 5
MAX_TERMS = 3
TITLE_MAX, PROBLEM_MAX, AUDIENCE_MAX, TERM_MAX = 120, 400, 120, 60
CONFIDENCE = ("high", "medium", "low")


# ------------------------------------------------------------------------------------------------------------- steering --
def _subject(intent) -> tuple[str | None, str | None]:
    return (getattr(intent, "audience", None) or None), (getattr(intent, "seed", None) or None)


def aspects_for(intent) -> list[tuple[str, str, str]]:
    """(label, query type, query text): the hypothesis material to retrieve for this intent."""
    audience, seed = _subject(intent)
    if audience and seed:
        rows = [("frictions", "MECHANISM", f"{audience} frustrations, complaints and recurring problems with {seed}"),
                ("workarounds", "EXAMPLE", f"workarounds and makeshift fixes {audience} rely on for {seed}"),
                ("unmet_jobs", "MECHANISM", f"unmet needs and jobs {audience} struggle to get done around {seed}")]
    elif audience:
        rows = [("frictions", "MECHANISM", f"{audience} frustrations, complaints and recurring problems"),
                ("workarounds", "EXAMPLE", f"workarounds and makeshift fixes {audience} rely on"),
                ("unmet_jobs", "MECHANISM", f"unmet needs and jobs {audience} struggle to get done")]
    elif seed:
        rows = [("frictions", "MECHANISM", f"problems, frustrations and complaints with {seed}"),
                ("workarounds", "EXAMPLE", f"workarounds and makeshift fixes people rely on for {seed}"),
                ("use_situations", "EXAMPLE", f"unmet needs and use situations around {seed}")]
    else:
        rows = [("frictions", "MECHANISM", "recurring frustrations, complaints and everyday problems people describe"),
                ("workarounds", "EXAMPLE", "workarounds and makeshift fixes people improvise"),
                ("unmet_jobs", "MECHANISM", "unmet needs of particular audiences and the situations they struggle in")]
    return [(label, qtype, _clean_query(text)) for label, qtype, text in rows if not _has_instruction_tokens(text)]


def steer_plan(plan, intent):
    """(plan, receipt): the compiled plan with the product aspects added inside the compiler's cap. Lowest-weight non-PRIMARY USER
    queries make room when the cap is full (q0 is never touched); a facet plan gives each aspect its own facet while MAX_FACETS
    allows (a facet a replaced query leaves empty is dropped). The receipt rides `plan.compiler["product_search"]`."""
    audience, seed = _subject(intent)
    retrieving = bool(plan.retrieval_required and plan.queries)
    plan = plan_for_evidence_route(plan, override_rule=STEER_RULE)
    receipt: dict[str, Any] = {"mode": "plan", "subject": {"audience": audience, "seed": seed}, "added": [], "replaced": [],
                               "facets_added": [], "facets_dropped": [], "retrieval_override": not retrieving}
    cap = MAX_QUERIES_FACETS if plan.facets else MAX_QUERIES
    have = {q.query.strip().lower() for q in plan.queries}
    aspects = [a for a in aspects_for(intent) if a[2].lower() not in have][:len(ASPECT_IDS)]
    user = [q for q in plan.queries if q.origin == "USER"]
    need = len(aspects) - max(0, cap - len(user))
    if need > 0:
        order = {id(q): i for i, q in enumerate(plan.queries)}
        droppable = sorted((q for q in user if q.type != "PRIMARY"), key=lambda q: (q.weight, -order[id(q)]))[:need]
        gone = {id(q) for q in droppable}
        plan.queries = [q for q in plan.queries if id(q) not in gone]
        receipt["replaced"] = [q.id for q in droppable]
        aspects = aspects[:max(0, cap - (len(user) - len(droppable)))]
    used_ids = {q.id for q in plan.queries}
    added: list[CompiledQuery] = []
    for (label, qtype, text), qid in zip(aspects, (i for i in ASPECT_IDS if i not in used_ids)):
        added.append(CompiledQuery(id=qid, type=qtype, query=text, weight=ASPECT_WEIGHT, role="complement",
                                   reason=f"product hypothesis material: {label}", target=f"product hypotheses: {label}",
                                   origin="USER"))
    plan.queries = list(plan.queries) + added
    plan.semantic_queries = list(plan.semantic_queries or []) + [q.query for q in added]
    receipt["added"] = [{"id": q.id, "type": q.type, "label": q.reason.split(": ", 1)[-1]} for q in added]
    if plan.facets:
        taken = {str(f.get("id")) for f in plan.facets}                  # ids are never reused, even a dropped facet's
        live = {q.facet_id for q in plan.queries if q.facet_id}
        receipt["facets_dropped"] = [str(f.get("id")) for f in plan.facets if str(f.get("id")) not in live]
        plan.facets = [f for f in plan.facets if str(f.get("id")) in live]   # a facet a replaced query left empty goes first
        for q in added:
            if len(plan.facets) >= MAX_FACETS:
                break
            fid = next(f"f{n}" for n in range(1, len(taken) + 2) if f"f{n}" not in taken)
            taken.add(fid)
            q.facet_id = fid
            plan.facets.append({"id": fid, "name": f"product hypotheses: {q.reason.split(': ', 1)[-1]}"[:80], "query_ids": [q.id]})
            receipt["facets_added"].append(fid)
        sync_facets(plan)                                                 # the rest attach by overlap; query_ids are rebuilt
        receipt["facets_dropped"] += [str(f.get("id")) for f in plan.facets if not f.get("query_ids")]
        plan.facets = [f for f in plan.facets if f.get("query_ids")]
    if isinstance(getattr(plan, "compiler", None), dict):
        plan.compiler["product_search"] = receipt
    return plan, receipt


def steer_text(query: str, intent) -> tuple[str, dict[str, Any]]:
    """(retrieval text, receipt) for a turn with no compiled plan: the question plus one deterministic hypothesis-material addition."""
    audience, seed = _subject(intent)
    subject = audience or seed
    addition = f"{subject} frustrations, workarounds and unmet needs" if subject else "frustrations, workarounds and unmet needs"
    return f"{(query or '').strip()} {addition}".strip(), {"mode": "text", "addition": addition,
                                                           "subject": {"audience": audience, "seed": seed}}


# ------------------------------------------------------------------------------------------------------------- contract --
def contract_block(intent) -> str:
    """The PRODUCT HYPOTHESIS contract, appended to the synthesis system prompt of a product turn."""
    audience, seed = _subject(intent)
    geo = getattr(intent, "geography", None)
    who = f" for {audience}" if audience else ""
    where = f" (selling market: {geo})" if geo else ""
    seeded = f' The user named "{seed}": treat it as a seed to explore, not a limit.' if seed else ""
    return f"""PRODUCT HYPOTHESIS CONTRACT ({CONTRACT_NAME}). This turn is a PRODUCT SEARCH: the user wants products they could \
sell{who}{where}. Where any display rule above disagrees with this contract, this contract wins.
- The library does not need to name, sell or recommend products. Read the EVIDENCE for frictions, workarounds, unmet jobs, \
audiences, recurring complaints and use situations, and turn them into product ideas. Never answer that the corpus "doesn't \
recommend products", "contains no products" or "names no niche", and never ask the user for a niche first: the library is the \
source of the ideas.{seeded}
- Form 3 to 5 product HYPOTHESES. Label them as hypotheses (inferences from the passages), never as facts the library states \
or products it recommends. For each: a short product name, the problem it solves and for whom, and the [S#] tags of the \
passages that inspired it, cited at the end of the sentence they support.
- Thin evidence still gets hypotheses: mark them low-confidence and name the evidence that is missing. An aspect with no or \
weak evidence means that kind of material is thin, never that no product can be hypothesised.
- Do not claim demand, sales, prices, margins or supplier availability: CJ Dropshipping is searched after your answer with \
your search terms, and the app appends the finds and the offer of the full research run below it. Do not add next steps or \
an offer yourself.
- END the answer with exactly one fenced block labelled {BLOCK_LABEL}: a JSON array with one object per hypothesis, in the \
order you presented them, and nothing after the block:
```{BLOCK_LABEL}
[{{"title": "<short product name>", "problem": "<the problem it solves, one sentence>", "audience": "<who has the problem>", \
"evidence_tags": ["S1", "S4"], "search_terms": ["<2-4 word catalogue search>", "<another search>"], "confidence": "medium"}}]
```
  search_terms: 1 to 3 short supplier-catalogue searches, 2 to 4 plain words each, naming the product itself (no brand, no \
audience or country words). evidence_tags: only [S#] tags from the EVIDENCE above. confidence: high, medium or low."""


# ---------------------------------------------------------------------------------------------------------------- parse --
@dataclass
class HypothesisParse:
    """What the answer's hypothesis block held. `status`: ok (a labelled block, clean JSON) | drifted (read after a repair, a
    label drift, a missing fence or a cut) | fallback (nothing usable: `reason` says why)."""
    status: str
    reason: str | None = None
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    clean_text: str = ""
    notes: list[str] = field(default_factory=list)
    tags_dropped: int = 0

    def receipt(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "hypotheses": len(self.hypotheses), "notes": list(self.notes),
                "tags_dropped": self.tags_dropped}


_FENCE = re.compile(r"(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^\n`~]*)\n(?P<body>.*?)(?:\n[ \t]*(?P=fence)[ \t]*(?=\n|$)|\Z)", re.S)
_LABEL_OURS = re.compile(r"^\s*(?:product[-_ ]?hypothes[ie]s|hypothes[ie]s|product[-_ ]?search|products?)\b", re.I)
_LABEL_DATA = re.compile(r"^\s*(?:json5?|jsonc|javascript|js|text)?\s*$", re.I)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_SMART = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"})
_TAG = re.compile(r"S?\s*(\d{1,3})", re.I)
_TERM_SPLIT = re.compile(r"[,;|/\n]+")
_MD = re.compile(r"[*_`#>]+")
_STOPWORDS = frozenset("a an the for of to and or with your their my our that this these those who which in on at by from".split())
_INTRO = re.compile(r"(?:block|json|machine|hypothes[ie]s|structured)[^\n]*:\s*$", re.I)
_ALIASES = {
    "title": ("title", "name", "product", "product_name", "idea", "hypothesis"),
    "problem": ("problem", "pain", "pain_point", "friction", "need", "why", "rationale", "job", "problem_solved"),
    "audience": ("audience", "for", "customer", "customers", "target", "target_audience", "who", "segment"),
    "evidence_tags": ("evidence_tags", "evidence", "tags", "citations", "cites", "sources", "source_tags", "evidence_ids", "cited_tags"),
    "search_terms": ("search_terms", "terms", "cj_terms", "search", "queries", "keywords", "cj_search_terms", "search_queries",
                     "cj_search"),
    "confidence": ("confidence", "certainty"),
}


def _loads(body: str) -> tuple[Any, list[str]]:
    """JSON, then the small repairs, then a Python literal (single quotes); (None, notes) when nothing reads."""
    text = (body or "").strip()
    try:
        return json.loads(text), []
    except ValueError:
        pass
    notes: list[str] = []
    fixed = _TRAILING_COMMA.sub(r"\1", text.translate(_SMART))
    for attempt, note in ((fixed, "repaired"), (_cut(fixed), "truncated")):
        if not attempt:
            continue
        try:
            return json.loads(attempt), [note]
        except ValueError:
            pass
        try:
            got = ast.literal_eval(attempt)
            if isinstance(got, (list, dict)):
                return got, [note, "python_literal"]
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            pass
    return None, notes


def _cut(text: str) -> str | None:
    """An array cut off mid-way (the output bound hit): keep its complete objects and close it."""
    if not text.startswith("[") or text.rstrip().endswith("]"):
        return None
    end = text.rfind("}")
    return text[:end + 1] + "]" if end > 0 else None


def _key(k: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(k or "").strip().lower())


def _field(obj: dict, name: str) -> Any:
    keyed = {_key(k): v for k, v in obj.items()}
    return next((keyed[a] for a in _ALIASES[name] if a in keyed and keyed[a] not in (None, "", [])), None)


def _text(value: Any, cap: int) -> str | None:
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value if v not in (None, ""))
    text = " ".join(_MD.sub(" ", str(value or "")).split()).strip(" -:")
    return text[:cap].rstrip() or None


def _tags(value: Any, legend: set[str] | None) -> tuple[list[str], int]:
    items = value if isinstance(value, (list, tuple)) else [value]
    found: list[str] = []
    for item in items:
        if item is None or isinstance(item, bool):
            continue
        for m in _TAG.finditer(str(item)):
            tag = f"S{int(m.group(1))}"
            if tag not in found:
                found.append(tag)
    kept = [t for t in found if legend is None or t in legend]
    return kept, len(found) - len(kept)


def _term(raw: Any) -> str | None:
    words = [w for w in re.findall(r"[\w'&+-]+", str(raw or "").lower()) if w.strip("'-")][:6]
    term = " ".join(words)[:TERM_MAX].strip()
    return term if len(term) >= 2 else None


def _terms(value: Any, title: str) -> list[str]:
    raw = value if isinstance(value, (list, tuple)) else (_TERM_SPLIT.split(str(value)) if value else [])
    terms = list(dict.fromkeys(t for t in (_term(r) for r in raw) if t))[:MAX_TERMS]
    if not terms:
        words = [w for w in re.findall(r"[\w'&+-]+", title.lower()) if w not in _STOPWORDS][:5]
        terms = [t for t in [_term(" ".join(words))] if t]
    return terms


def normalize(items: Any, legend: set[str] | None = None) -> tuple[list[dict[str, Any]], int]:
    """The block's objects as product-search-v1 hypotheses (id, title, problem, audience, evidence_tags, search_terms,
    confidence), at most MAX_HYPOTHESES; an object without a title is dropped. Returns (hypotheses, tags dropped)."""
    if isinstance(items, dict):
        items = next((items[k] for k in ("hypotheses", "products", "ideas", "items", "product_hypotheses") if isinstance(items.get(k), list)),
                     [items])
    out: list[dict[str, Any]] = []
    dropped = 0
    for obj in items if isinstance(items, list) else []:
        if not isinstance(obj, dict):
            continue
        title = _text(_field(obj, "title"), TITLE_MAX)
        if not title:
            continue
        tags, lost = _tags(_field(obj, "evidence_tags"), legend)
        dropped += lost
        conf = str(_field(obj, "confidence") or "").strip().lower()
        out.append({"id": f"h{len(out) + 1}", "title": title, "problem": _text(_field(obj, "problem"), PROBLEM_MAX),
                    "audience": _text(_field(obj, "audience"), AUDIENCE_MAX), "evidence_tags": tags,
                    "search_terms": _terms(_field(obj, "search_terms"), title),
                    "confidence": conf if conf in CONFIDENCE else None})
        if len(out) >= MAX_HYPOTHESES:
            break
    return out, dropped


def _strip(text: str, start: int, end: int) -> str:
    """The answer without the block at [start, end), and without an intro line that only announced it."""
    head, tail = text[:start].rstrip(), text[end:].strip()
    lines = head.split("\n")
    if lines and _INTRO.search(lines[-1]) and len(lines[-1]) <= 160:
        head = "\n".join(lines[:-1]).rstrip()
    head = re.sub(r"(?:\n\s*(?:-{3,}|\*{3,}|_{3,})\s*)+$", "", head).rstrip()
    return f"{head}\n\n{tail}".strip() if tail else head


def parse_block(answer_text: str, legend_tags=None) -> HypothesisParse:
    """Read the answer's `product-hypotheses` block. `legend_tags` = the turn's [S#] tags (a tag outside them is dropped and
    counted); None keeps every tag."""
    text = answer_text or ""
    legend = set(legend_tags) if legend_tags is not None else None
    blocks = list(_FENCE.finditer(text))
    ours = [m for m in blocks if _LABEL_OURS.match(m.group("info") or "")]
    data = [m for m in blocks if m not in ours and _LABEL_DATA.match(m.group("info") or "")]
    outcome = None                                   # what the last labelled block yielded: "unparseable" | "no_hypotheses"
    for group, drift in ((ours[::-1], None), (data[::-1], "label")):
        for m in group:
            parsed, notes = _loads(m.group("body"))
            hyps, dropped = normalize(parsed, legend) if parsed is not None else ([], 0)
            if not hyps:
                if drift is None and outcome is None:
                    outcome = "unparseable" if parsed is None else "no_hypotheses"
                continue
            closed = m.group(0).rstrip().endswith(m.group("fence"))
            notes = notes + ([f"{drift}_drift"] if drift else []) + ([] if closed else ["unclosed_fence"])
            return HypothesisParse("drifted" if notes else "ok", None, hyps, _strip(text, m.start(), m.end()), notes, dropped)
    arrays = list(re.finditer(r"\[\s*\{", text))
    if arrays:                                       # an unfenced array at the end of the answer
        start = arrays[-1].start()
        parsed, notes = _loads(text[start:])
        hyps, dropped = normalize(parsed, legend) if parsed is not None else ([], 0)
        if hyps:
            return HypothesisParse("drifted", None, hyps, _strip(text, start, len(text)), notes + ["unfenced"], dropped)
    if ours:
        last = ours[-1]
        return HypothesisParse("fallback", outcome or "unparseable", [], _strip(text, last.start(), last.end()))
    return HypothesisParse("fallback", "no_block", [], text.strip())
