"""ACCEPTANCE-HARNESS-V1: human-agreement scoring (owner production gate).

Scores ADMITTED T2 knowledge against frozen human labels. Four metrics,
per the owner spec: entity_recall, predicate_precision, event_recall,
evidence_support. Pure functions — labels are fixtures, scored once,
never tuned against.
"""
from __future__ import annotations


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def entity_recall(labels: dict, admitted_entities: list[str]) -> dict:
    expected = {_norm(e) for e in labels.get("entities", [])}
    got = {_norm(e) for e in admitted_entities}
    hits = expected & got
    return {"metric": "entity_recall",
            "score": round(len(hits) / len(expected), 4) if expected else None,
            "expected": len(expected), "hit": len(hits),
            "missing": sorted(expected - got)}


def predicate_precision(labels: dict, admitted_facts: list[dict]) -> dict:
    """Fraction of admitted facts whose (subject, predicate, object)
    triple matches a human label."""
    labelled = {(_norm(f.get("subject")), _norm(f.get("predicate")),
                 _norm(f.get("object")))
                for f in labels.get("facts", [])}
    if not admitted_facts:
        return {"metric": "predicate_precision", "score": None,
                "admitted": 0, "matched": 0}
    matched = sum(
        1 for f in admitted_facts
        if (_norm(f.get("subject")), _norm(f.get("predicate")),
            _norm(f.get("object"))) in labelled)
    return {"metric": "predicate_precision",
            "score": round(matched / len(admitted_facts), 4),
            "admitted": len(admitted_facts), "matched": matched}


def event_recall(labels: dict, admitted_events: list[dict]) -> dict:
    expected = labels.get("events", [])
    if not expected:
        return {"metric": "event_recall", "score": None,
                "expected": 0, "hit": 0}
    norm_types = {_norm(e.get("type")) for e in admitted_events}
    hit = sum(1 for e in expected
              if any(_norm(t) in norm_types or
                     norm_types & {_norm(t)} for t in [e.get("type")]))
    # count an event as covered when its type family appears among
    # admitted events (evaluation <-> evaluation_event)
    hit = 0
    for e in expected:
        want = _norm(e.get("type"))
        if any(want and (want in t or t in want) for t in norm_types):
            hit += 1
    return {"metric": "event_recall",
            "score": round(hit / len(expected), 4),
            "expected": len(expected), "hit": hit}


def evidence_support(labels: dict, admitted_facts: list[dict]) -> dict:
    """Of the MATCHED labelled facts, how many carry surviving evidence
    provenance (evidence span / offsets present)."""
    labelled = {(_norm(f.get("subject")), _norm(f.get("predicate")),
                 _norm(f.get("object")))
                for f in labels.get("facts", [])}
    supported = matched = 0
    for f in admitted_facts:
        key = (_norm(f.get("subject")), _norm(f.get("predicate")),
               _norm(f.get("object")))
        if key not in labelled:
            continue
        matched += 1
        prov = f.get("provenance") or {}
        if prov.get("trigger_surface") or prov.get("evidence_start") \
                is not None or f.get("chunk_id"):
            supported += 1
    return {"metric": "evidence_support",
            "score": round(supported / matched, 4) if matched else None,
            "matched": matched, "supported": supported}


def score_acceptance(labels: dict, *, admitted_entities: list[str],
                     admitted_facts: list[dict],
                     admitted_events: list[dict]) -> dict:
    return {
        "contract": "acceptance-harness-v1",
        "entity_recall": entity_recall(labels, admitted_entities),
        "predicate_precision": predicate_precision(labels, admitted_facts),
        "event_recall": event_recall(labels, admitted_events),
        "evidence_support": evidence_support(labels, admitted_facts),
    }
