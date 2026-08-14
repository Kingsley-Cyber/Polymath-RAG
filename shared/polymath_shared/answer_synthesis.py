"""R3b: grounded answer generation (deterministic; no stores).

Pipeline: R3a EvidenceBundle -> claim synthesis (proposer) ->
deterministic validation -> prose rendering with citations.

Trust boundary: the proposer is NEVER trusted to obey the grounding
rule by prompting alone. It emits structured claims referencing bundle
item ids; the validator decides which claims may render. v1 uses a
deterministic template proposer; an LLM proposer can replace it later
without changing the validator or renderer.

Rules enforced by the validator (fail-closed):
  - a claim must have >=1 support bundle item that is kind=claim
    (evidence-only items may accompany, never substitute);
  - every support id must resolve to a real bundle item id;
  - every meaningful token of the claim text must appear in the union
    of its supporting claim surfaces (kills the "founded in 2019"
    fabrication class);
  - malformed entries are dropped deterministically;
  - conflicts (same entity pair, different predicate) are marked on
    both claims and never arbitrated;
  - epistemic scope (attributed/speculative/hypothetical/conditional)
    survives into the rendered prose and the claims ledger.

Determinism: pure functions of the bundle; identical input produces
byte-identical output. Citation numbering follows first appearance of
supporting bundle items in claim order (bundle order is deterministic).
"""
from __future__ import annotations

from typing import Callable, Iterable

from polymath_shared.identity import content_hash
from polymath_shared.retrieval import tokens

SYNTHESIS_VERSION = "deterministic-template-v1"
CHAT_CONTRACT_ID = "answer/chat_response/v1"

ABSTENTION_MESSAGE = (
    "I don't have enough grounded evidence to answer this question."
)
CONFLICT_NOTE = (
    " Note: conflicting evidence exists; both claims are shown without "
    "arbitration."
)


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


def synthesize_claims(bundle: dict) -> list[dict]:
    """v1 template proposer: one claim per bundle claim item.

    Evidence-only items inform prose but never become factual claims.
    Output is already deterministic (bundle order)."""
    proposed: list[dict] = []
    for item in bundle.get("evidence_bundle") or []:
        if item.get("kind") != "claim":
            continue
        proposed.append({
            "text": item.get("claim_candidate") or "",
            "support": [bundle_item_id(item)],
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
        claim_items = [
            iid for iid in raw["support"]
            if iid in items_by_id and items_by_id[iid].get("kind") == "claim"
        ]
        missing = [iid for iid in raw["support"] if iid not in items_by_id]
        surfaces = [items_by_id[iid].get("claim_candidate") or "" for iid in claim_items]
        ok = (
            bool(claim_items)
            and not missing
            and _grounded(raw["text"], surfaces)
        )
        row = {
            "text": raw["text"],
            "support": raw["support"],
            "status": "supported" if ok else "unsupported",
        }
        primary = claim_items[0] if claim_items else (raw["support"][0] if raw["support"] else None)
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

    Citations reference bundle item ids (not merely documents) and
    retain the exact source locators."""
    items_by_id, item_order = _index_items(bundle)

    citation_order: list[str] = []  # primary support item ids, in use
    citation_ids: dict[str, int] = {}
    sentences: list[str] = []
    ledger = list(validation["supported"]) + list(validation["unsupported"])

    for claim in validation["supported"]:
        support_ids = [s for s in claim["support"] if s in items_by_id]
        if not support_ids:
            continue
        primary = support_ids[0]
        if primary not in citation_ids:
            citation_order.append(primary)
            citation_ids[primary] = len(citation_order)
        sentence = f"{_epistemic_prefix(claim)}{claim['text']} [{citation_ids[primary]}]"
        sentences.append(sentence)

    has_conflict = any(c.get("conflicts_with") for c in validation["supported"])
    if sentences:
        answer = " ".join(sentences)
        if has_conflict:
            answer += CONFLICT_NOTE
    else:
        answer = ABSTENTION_MESSAGE

    citations = []
    for iid in citation_order:
        item = items_by_id[iid]
        doc_ids = [item.get("source_document_id") or ""]
        locators = [(item.get("source_span") or {}).get("locator") or ""]
        citations.append({
            "citation_id": citation_ids[iid],
            "bundle_item_ids": [iid],
            "source_document_ids": [d for d in doc_ids if d],
            "locators": [l for l in locators if l],
        })

    return {
        "answer": answer,
        "citations": citations,
        "claims": ledger,
        "meta": {
            "contract_id": CHAT_CONTRACT_ID,
            "synthesis_version": SYNTHESIS_VERSION,
            "abstained": not sentences,
            "supported_claim_count": len(validation["supported"]),
            "unsupported_claim_count": len(validation["unsupported"]),
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
