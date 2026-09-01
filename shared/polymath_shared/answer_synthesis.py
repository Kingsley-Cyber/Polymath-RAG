"""R3b: grounded answer generation (deterministic; no stores).

Pipeline: R3a EvidenceBundle -> claim synthesis (proposer) ->
deterministic validation -> prose rendering with citations.

Trust boundary: the proposer is NEVER trusted to obey the grounding
rule by prompting alone. It emits structured claims referencing bundle
item ids; the validator decides which claims may render. v2 uses a
deterministic template proposer; an LLM proposer can replace it later
without changing the validator or renderer.

Typed support lanes (D3, v2):
  - GRAPH lane claims (fact triples): a claim must have >=1 support
    bundle item with lane=graph, kind=claim; every meaningful token of
    the claim text must appear in the union of its supporting claim
    surfaces (kills the "founded in 2019" fabrication class).
  - TEXT lane claims (verbatim passages): the claim text must be a
    verbatim, case-insensitive substring of at least one supporting
    lane=text item's passage — excerpts are cut from the passage
    itself, so no fabrication can survive.
  - The lanes are INDEPENDENT: a text-only bundle produces a cited
    passage answer; a graph-only bundle produces the fact answer.
    Graph evidence augments text, never gates it. Abstention only
    when BOTH lanes are empty. Mixed-lane support for one claim is
    rejected (fail-closed).
  - malformed entries are dropped deterministically;
  - conflicts (same entity pair, different predicate) are marked on
    both claims and never arbitrated;
  - epistemic scope (attributed/speculative/hypothetical/conditional)
    survives into the rendered prose and the claims ledger.

ANSWER-ADMISSION-V1 (2026-08-26): evidence RETRIEVAL is not evidence
SUFFICIENCY. A nonce query once returned ten cited passages marked
supported — dense similarity retrieves related-looking text for any
string. Two deterministic gates now separate "found related text" from
"can answer this query", reusing the codebase's existing term
conventions (tokens() + the substring-containment convention of
lexical_score) — no similarity thresholds:

  1. TEXT per-claim: a passage may support a claim only if it contains
     at least one query content term (len>=4, stopword-filtered).
  2. Answer-level coverage (both lanes): the union of all supporting
     surfaces (graph claim candidates + text passages) must contain
     EVERY query content term, or the answer is INSUFFICIENT_EVIDENCE
     and the system abstains. NO ANSWER > UNSUPPORTED ANSWER.

ANSWER-ADMISSION-V2 (2026-09-01): the v1 gates abstained on plainly
answerable questions for three lexical reasons found live (ecom-meta
battery: "How do habits and jobs-to-be-done theory together explain
repeat purchases?" abstained with 14 grounded claims withheld):
  a. tokens() keeps hyphenated compounds whole, so the query term
     "jobs-to-be-done" could never be covered by sources that write
     "jobs to be done" — a compound now also counts as covered when
     its spaced form appears, or when ALL of its content sub-tokens
     are covered.
  b. Relation words ("together", "explain", "compare"...) state the
     question's requested RELATION, not its content — evidence about
     both sides rarely repeats them verbatim. They are no longer
     required of the evidence (never required, still allowed).
  c. All-or-abstain coverage let ONE rare term veto an otherwise
     grounded answer. Gate 2 now requires >=75% coverage (uncovered
     <= len(terms)//4): queries of <=3 content terms still require
     every term (nonce regressions unchanged); longer questions
     tolerate one uncovered term per four. meta.uncovered_query_terms
     stays honest either way.

Verdicts: meta.verdict = "supported" | "insufficient_evidence";
backend failures never reach synthesis (typed 502 upstream).

Determinism: pure functions of the bundle; identical input produces
byte-identical output. Citation numbering follows first appearance of
supporting bundle items in claim order (bundle order is deterministic).
"""
from __future__ import annotations

from typing import Callable, Iterable

from polymath_shared.identity import content_hash
from polymath_shared.retrieval import tokens

SYNTHESIS_VERSION = "deterministic-template-v3"
CHAT_CONTRACT_ID = "answer/chat_response/v2"
ANSWER_ADMISSION_VERSION = "answer-admission-v2"

#: Words that state the question's requested RELATION between content
#: terms rather than content itself ("how do X and Y TOGETHER EXPLAIN
#: Z"). Evidence that answers the question rarely repeats them
#: verbatim, so they are never REQUIRED of the supporting surfaces.
#: Deliberately small and meta-linguistic: a word that could name a
#: domain concept (influence, cause, effect) does NOT belong here.
_RELATION_WORDS = frozenset(
    "together jointly explain explains explained explaining describe "
    "describes discuss discusses summarize summarizes compare compares "
    "comparison contrast contrasts relate relates related relationship "
    "relationships connection connections versus difference differences "
    "differ differs overall respectively".split())

ABSTENTION_MESSAGE = (
    "I don't have enough grounded evidence to answer this question."
)
CONFLICT_NOTE = (
    " Note: conflicting evidence exists; both claims are shown without "
    "arbitration."
)

GRAPH_LANE = "graph"
TEXT_LANE = "text"

TEXT_EXCERPT_WIDTH = 160


def bundle_item_id(item: dict) -> str:
    """Stable R3a item id: content hash of the item itself. The R3a
    bundle ordering is deterministic, but ids are content-derived so
    they stay valid across reorderings."""
    return "bitem_" + content_hash(item)[:16]


def _index_items(bundle: dict) -> tuple[dict[str, dict], list[str]]:
    items = bundle.get("evidence_bundle") or []
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for item in items:
        iid = bundle_item_id(item)
        by_id[iid] = item
        order.append(iid)
    return by_id, order


def _excerpt(passage: str, query: str, width: int = TEXT_EXCERPT_WIDTH) -> str:
    """Deterministic passage excerpt: a window around the first
    occurrence of the query's rarest long token (ties: longest token
    first). Word-boundary trimmed. Pure and byte-stable."""
    terms = sorted(
        {t for t in tokens(query) if len(t) > 3},
        key=lambda t: (passage.lower().count(t.lower()), -len(t), t),
    )
    if not terms or not passage:
        return passage[:width].strip()
    lower = passage.lower()
    idx = lower.find(terms[0].lower())
    if idx == -1:
        return passage[:width].strip()
    start = max(0, idx - width // 2)
    end = min(len(passage), start + width)
    start = max(0, end - width)
    while start > 0 and passage[start] not in " \n\t":
        start -= 1
    while end < len(passage) and passage[end] not in " \n\t":
        end += 1
    return passage[start:end].strip()


def _passage_of(item: dict) -> str:
    return (item.get("source_span") or {}).get("text") or ""


def _text_grounded(claim_text: str, passages: list[str]) -> bool:
    """Fail-closed TEXT lane grounding: the claim must be a verbatim,
    case-insensitive substring of at least one supporting passage."""
    if not claim_text.strip():
        return False
    lowered = claim_text.lower()
    return any(lowered in (p or "").lower() for p in passages)


def query_content_terms(query: str) -> set[str]:
    """The query's content terms: stopword-filtered tokens of length
    >=4 (the existing seed/entity-surface convention), minus relation
    words (v2b — they name the asked-for relation, not content). Falls
    back to all tokens for very short queries so the gate never
    trivially passes on an empty term set."""
    toks = tokens(query)
    terms = {t for t in toks if len(t) >= 4 and t not in _RELATION_WORDS}
    return terms or {t for t in toks if t not in _RELATION_WORDS} or toks


def _compound_subterms(term: str) -> list[str]:
    """Content sub-tokens of a hyphen/underscore compound ('jobs-to-
    be-done' -> ['jobs', 'done']); [] for a plain term."""
    if "-" not in term and "_" not in term:
        return []
    parts = [p for p in term.replace("_", "-").split("-") if p]
    return [p for p in parts if len(p) >= 4 and p not in _RELATION_WORDS]


def _term_covered(term: str, surfaces: Iterable[str]) -> bool:
    """Substring containment, the lexical_score convention: 'configure'
    covers 'configures', 'step' covers 'steps'. v2a: a hyphenated
    compound is also covered by its spaced form ('jobs to be done')
    or by every one of its content sub-tokens appearing somewhere in
    the surfaces — sources normalize hyphens freely."""
    t = term.lower()
    lowered = [(s or "").lower() for s in surfaces]
    if any(t in s for s in lowered):
        return True
    if "-" in t or "_" in t:
        spaced = t.replace("_", " ").replace("-", " ")
        if any(spaced in s for s in lowered):
            return True
        subs = _compound_subterms(t)
        if subs and all(any(sub in s for s in lowered) for sub in subs):
            return True
    return False


def _query_relevant(query: str, passages: list[str]) -> bool:
    """ANSWER-ADMISSION-V1 gate 1: a passage with ZERO query content
    terms is dense-retrieval noise — it can inform nothing about this
    query and never supports a claim."""
    terms = query_content_terms(query)
    if not terms:
        return False
    return any(_term_covered(term, passages) for term in terms)


def synthesize_claims(bundle: dict) -> list[dict]:
    """v2 template proposer: one GRAPH claim per graph claim item and
    one TEXT passage claim per text evidence item (typed lanes).

    Evidence-only items inform prose but never become factual claims.
    Output is already deterministic (bundle order)."""
    query = bundle.get("query") or ""
    proposed: list[dict] = []
    for item in bundle.get("evidence_bundle") or []:
        if item.get("kind") == "claim" and item.get("lane") == GRAPH_LANE:
            proposed.append({
                "text": item.get("claim_candidate") or "",
                "support": [bundle_item_id(item)],
                "lane": GRAPH_LANE,
            })
        elif item.get("kind") == "evidence" and item.get("lane") == TEXT_LANE:
            passage = _passage_of(item)
            if not passage.strip():
                continue
            proposed.append({
                "text": _excerpt(passage, query),
                "support": [bundle_item_id(item)],
                "lane": TEXT_LANE,
            })
    return proposed


def _normalize(proposed: Iterable) -> list[dict]:
    """Deterministic repair of malformed proposer output.

    Structurally invalid entries are dropped; semantically checkable
    entries are kept for validation."""
    out: list[dict] = []
    for entry in proposed or []:
        if not isinstance(entry, dict):
            continue
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        support = entry.get("support")
        if not isinstance(support, list):
            support = []
        ids: list[str] = []
        for s in support:
            if isinstance(s, str) and s and s not in ids:
                ids.append(s)
        if not ids:
            continue
        out.append({"text": text.strip(), "support": ids})
    return out


def _grounded(claim_text: str, claim_surfaces: list[str]) -> bool:
    """Every meaningful token of the claim must appear in the union of
    its supporting claim surfaces (deterministic, conservative)."""
    claim_toks = tokens(claim_text)
    if not claim_toks:
        return False
    surface_toks = tokens(" ".join(s for s in claim_surfaces if s))
    return claim_toks <= surface_toks


def _conflicts(items_by_id: dict[str, dict], item_order: list[str]) -> dict[str, list[str]]:
    """Conflict pairs among claim items, deterministically detected and
    never arbitrated:
      - same predicate + same object + different subject (competing
        claims about the same target), or
      - same ordered entity pair + different predicate (competing
        relation claims about the same pair)."""
    conflicts: dict[str, set[str]] = {iid: set() for iid in item_order}
    claim_items = [
        (iid, items_by_id[iid]) for iid in item_order
        if items_by_id[iid].get("kind") == "claim"
    ]
    for i, (id_a, item_a) in enumerate(claim_items):
        for id_b, item_b in claim_items[i + 1:]:
            pair_a = item_a.get("entity_ids") or {}
            pair_b = item_b.get("entity_ids") or {}
            pred_a = item_a.get("predicate")
            pred_b = item_b.get("predicate")
            same_object = (
                pair_a.get("object_id") and pair_a.get("object_id") == pair_b.get("object_id")
            )
            different_subject = pair_a.get("subject_id") != pair_b.get("subject_id")
            same_pair_different_pred = (
                pair_a.get("subject_id") and pair_a == pair_b and pred_a != pred_b
            )
            if (same_object and pred_a == pred_b and different_subject) or same_pair_different_pred:
                conflicts[id_a].add(id_b)
                conflicts[id_b].add(id_a)
    return {iid: sorted(s) for iid, s in conflicts.items() if s}


def validate_claims(proposed: Iterable, bundle: dict) -> dict:
    """Deterministic validator. Returns
    {supported: [...], unsupported: [...], conflicts: {...}} with
    bundle item ids resolved."""
    items_by_id, item_order = _index_items(bundle)
    normalized = _normalize(proposed)
    conflicts = _conflicts(items_by_id, item_order)

    supported: list[dict] = []
    unsupported: list[dict] = []

    for raw in normalized:
        support_items = [items_by_id[iid] for iid in raw["support"] if iid in items_by_id]
        missing = [iid for iid in raw["support"] if iid not in items_by_id]
        lanes = {i.get("lane") for i in support_items if i.get("lane")}
        # Typed-lane validation: a claim is supported by exactly one
        # lane (mixed support is fail-closed).
        if lanes == {GRAPH_LANE}:
            claim_items = [iid for iid in raw["support"]
                           if items_by_id[iid].get("kind") == "claim"]
            surfaces = [items_by_id[iid].get("claim_candidate") or "" for iid in claim_items]
            ok = (
                bool(claim_items)
                and not missing
                and _grounded(raw["text"], surfaces)
            )
            lane = GRAPH_LANE
        elif lanes == {TEXT_LANE}:
            passages = [_passage_of(i) for i in support_items]
            ok = (
                bool(support_items)
                and not missing
                and _text_grounded(raw["text"], passages)
                # ANSWER-ADMISSION-V1 gate 1: retrieval similarity is
                # not query relevance — the supporting passage must
                # share at least one query content term.
                and _query_relevant(bundle.get("query") or "", passages)
            )
            lane = TEXT_LANE
        else:
            ok = False
            lane = None
        row = {
            "text": raw["text"],
            "support": raw["support"],
            "status": "supported" if ok else "unsupported",
        }
        if lane:
            row["lane"] = lane
        primary = raw["support"][0] if raw["support"] else None
        primary_item = items_by_id.get(primary) if primary else None
        if primary_item and primary_item.get("kind") == "claim":
            epistemics = primary_item.get("epistemics") or {}
            conditions = (primary_item.get("applicability") or {}).get("conditions") or []
            row["epistemics"] = {
                "certainty": epistemics.get("certainty"),
                "attributed": epistemics.get("attributed"),
                "attribution_source": epistemics.get("attribution_source"),
                "conditional": "conditional" in conditions,
                "negated": epistemics.get("negated"),
            }
            if ok and primary in conflicts:
                row["conflicts_with"] = conflicts[primary]
        (supported if ok else unsupported).append(row)

    return {"supported": supported, "unsupported": unsupported,
            "conflicts": conflicts}


def _epistemic_prefix(claim: dict) -> str:
    ep = claim.get("epistemics") or {}
    prefix = ""
    if ep.get("conditional"):
        prefix += "Under the stated condition, "
    certainty = ep.get("certainty")
    if certainty == "speculative":
        prefix += "It is possible that "
    elif certainty == "hypothetical":
        prefix += "Hypothetically, "
    if ep.get("attributed"):
        source = ep.get("attribution_source") or "the cited source"
        prefix += f"According to {source}, "
    return prefix


def render_answer(bundle: dict, query: str, validation: dict) -> dict:
    """Deterministic renderer: prose + citations + claim ledger.

    GRAPH lane claims render as factual sentences (epistemic prefix);
    TEXT lane claims render as cited passages. Graph augments text and
    renders first; text alone still produces an answer (D3).

    Citations reference bundle item ids (not merely documents) and
    retain the exact source locators."""
    items_by_id, item_order = _index_items(bundle)

    citation_order: list[str] = []  # primary support item ids, in use
    citation_ids: dict[str, int] = {}
    sentences: list[str] = []
    passages: list[str] = []
    ledger = list(validation["supported"]) + list(validation["unsupported"])

    for claim in validation["supported"]:
        support_ids = [s for s in claim["support"] if s in items_by_id]
        if not support_ids:
            continue
        primary = support_ids[0]
        if primary not in citation_ids:
            citation_order.append(primary)
            citation_ids[primary] = len(citation_order)
        if claim.get("lane") == TEXT_LANE:
            passages.append(f"Relevant passage: \u201c{claim['text']}\u201d [{citation_ids[primary]}]")
        else:
            sentence = f"{_epistemic_prefix(claim)}{claim['text']} [{citation_ids[primary]}]"
            sentences.append(sentence)

    # ANSWER-ADMISSION-V1 gate 2: answer-level query coverage. The
    # union of every supporting surface (graph claim candidates + text
    # passages) must contain EVERY query content term. Related text
    # that leaves part of the question untouched is not an answer.
    support_surfaces: list[str] = []
    for claim in validation["supported"]:
        for iid in claim["support"]:
            item = items_by_id.get(iid)
            if not item:
                continue
            if item.get("kind") == "claim":
                support_surfaces.append(item.get("claim_candidate") or "")
            else:
                support_surfaces.append(_passage_of(item))
    required_terms = query_content_terms(query)
    uncovered = sorted(
        term for term in required_terms
        if not _term_covered(term, support_surfaces)
    ) if validation["supported"] else []

    # v2c quorum: >=75% of content terms covered. <=3 terms -> 0
    # uncovered allowed (nonce behavior unchanged); one uncovered term
    # tolerated per four content terms beyond that.
    coverage_ok = len(uncovered) <= len(required_terms) // 4

    has_conflict = any(c.get("conflicts_with") for c in validation["supported"])
    if (sentences or passages) and coverage_ok:
        answer = " ".join(sentences + passages)
        if has_conflict:
            answer += CONFLICT_NOTE
        verdict = "supported"
    else:
        answer = ABSTENTION_MESSAGE
        verdict = "insufficient_evidence"
        sentences, passages = [], []
        citation_order, citation_ids = [], {}
        # Claims that passed claim-level grounding but were withheld by
        # answer-level coverage stay visible in the ledger, honestly
        # labeled — they are grounded text, not an answer.
        ledger = [
            dict(row, status="withheld_insufficient_coverage")
            if row.get("status") == "supported" else row
            for row in ledger
        ]

    citations = []
    for iid in citation_order:
        item = items_by_id[iid]
        doc_ids = [item.get("source_document_id") or ""]
        locators = [(item.get("source_span") or {}).get("locator") or ""]
        # UI-V3 §3.3: the human locator rides beside the raw locator —
        # additive, empty when the bundle item predates presentation.
        human = (item.get("presentation") or {}).get("human_locator") or ""
        citations.append({
            "citation_id": citation_ids[iid],
            "bundle_item_ids": [iid],
            "source_document_ids": [d for d in doc_ids if d],
            "locators": [l for l in locators if l],
            "human_locators": [human] if human else [],
        })

    supported = validation["supported"] if verdict == "supported" else []
    return {
        "answer": answer,
        "citations": citations,
        "claims": ledger,
        "meta": {
            "contract_id": CHAT_CONTRACT_ID,
            "synthesis_version": SYNTHESIS_VERSION,
            "answer_admission": ANSWER_ADMISSION_VERSION,
            "verdict": verdict,
            "uncovered_query_terms": uncovered,
            "abstained": verdict != "supported",
            "supported_claim_count": len(supported),
            "unsupported_claim_count": len(validation["unsupported"]),
            "text_support_count": sum(
                1 for c in supported if c.get("lane") == TEXT_LANE
            ),
        },
    }


def grounded_answer(
    bundle: dict,
    query: str,
    synthesize: Callable[[dict], list[dict]] = synthesize_claims,
) -> dict:
    """The full R3b pipeline: propose -> validate -> render.

    Deterministic for identical (bundle, synthesizer output)."""
    proposed = synthesize(bundle)
    validation = validate_claims(proposed, bundle)
    return render_answer(bundle, query, validation)
