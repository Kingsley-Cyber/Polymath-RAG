"""SCIENTIFIC-KAG-V1 phase 6b: event candidate generation + admission.

Accepted binary facts whose predicate names a scientific ACTION are
promoted to event candidates; a deterministic gate decides whether the
event becomes a knowledge object.

Promotion rules (owner decision):
  R1  a temporal anchor exists        ("evaluated in March 2023")
  R2  multiple participant roles      (agent + artifact [+ date])
Static relationships ("BERT uses attention") never become events.

Pure functions over already-admitted fact structures; no I/O, no
models. Persistence/projection wiring consumes these records.
"""
from __future__ import annotations

# Scientific actions that describe happenings, not static structure.
EVENT_PREDICATES = frozenset({
    "trained_on", "evaluated_on", "released_on", "published_on",
    "occurred_at", "discovered", "proposed", "measured",
})

_EVENT_TYPE_BY_PREDICATE = {
    "trained_on": "training_event",
    "evaluated_on": "evaluation_event",
    "released_on": "release_event",
    "published_on": "publication_event",
    "occurred_at": "occurrence_event",
    "discovered": "discovery_event",
    "proposed": "proposal_event",
    "measured": "measurement_event",
}

_TEMPORAL_KEYS = ("valid_from", "valid_until", "temporal_surface")


def event_candidate(predicate: str, subject_id: str, object_id: str,
                    qualifiers: dict | None,
                    subject_surface: str | None = None,
                    object_surface: str | None = None,
                    agent_surface: str | None = None) -> dict | None:
    """Build an event candidate from an ACCEPTED fact, or None when the
    predicate is a static relationship."""
    if predicate not in EVENT_PREDICATES:
        return None
    q = qualifiers or {}
    temporal = {k: q[k] for k in _TEMPORAL_KEYS if q.get(k)}
    roles = {"subject": {"id": subject_id, "surface": subject_surface},
             "object": {"id": object_id, "surface": object_surface}}
    if agent_surface:
        roles["agent"] = {"id": None, "surface": agent_surface}
    return {
        "contract": "event-candidate-v1",
        "event_type": _EVENT_TYPE_BY_PREDICATE[predicate],
        "predicate": predicate,
        "participants": roles,
        "date": q.get("temporal_surface") or q.get("valid_from"),
        "normalized_date": q.get("valid_from"),
    }


def admit_event(candidate: dict) -> tuple[bool, str]:
    """Deterministic promotion gate.

    R1: a temporal anchor exists (the happening is pinned in time).
    R2: multiple distinct participant surfaces exist (an agent AND an
        artifact are named, not just a bare pair).
    Otherwise the relation stays a plain edge — no node."""
    if candidate.get("date"):
        return True, "R1_temporal_anchor"
    # R2: multiple participant ROLES — e.g. an explicit agent alongside
    # the artifact ("OpenAI released GPT-4"). A bare subject/object pair
    # is just the edge itself and stays one.
    parts = candidate["participants"]
    named = [p for p in parts.values() if p.get("surface")]
    if "agent" in parts and parts["agent"].get("surface") \
            and parts["object"].get("surface") and len(named) >= 3:
        return True, "R2_multiple_participants"
    return False, "no_temporal_anchor_and_single_role"
