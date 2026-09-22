"""OpportunitySemanticViewV1 — a DERIVED, READ-ONLY projection over state the runtime already owns (owner decision 2026-09-21,
restoration reference §3.2 / §7). Pure and deterministic: functions over the hypothesis ledger's newest revisions, the run's step
outputs and the stored admissions. Nothing here is persisted, revised or sent to Trail as-is; it is not a ledger and not a store.

Why it exists: every consumer used to receive `{hypothesis_id, revision, status, statement}` although the ledger holds mechanism,
population, activity, task, context, friction, assumptions, falsifiers, contradictions, gaps and support — and the step outputs hold
the structures, leads, bridge, jobs, mechanisms and concepts that belong to that hypothesis. The view joins them BY ID (never by
name or by prose) and each consumer takes the smallest projection it needs:

    agent_projection          reasoning steps (through the opt-in `materials` channel: `config.show` path `semantics.*`)
    query_projection          research planning (domain operations: `config.inputs` path `context.semantics.*`)
    product_reality_projection  concept → marketplace research
    trail_projection          CLOSED, exactly Trail's four wire fields — Trail's wire models are `extra="forbid"`

Step outputs are read BY KEY (newest accepted step first), never by step id or domain name: the generic engine knows keys a
manifest's steps emit, not a domain. A value that does not exist is reported as missing — never fabricated."""
from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping

from . import evidence_boundary as EB
from .hypotheses import ABSORBED_STATUSES

VIEW_VERSION = "opportunity_semantic_view.v1"
TEXT_CHARS = 400                 # every free-text value is clipped; the view is context, the ledger stays the record
MAX_ITEMS = 12                   # per list inside one hypothesis view
MAX_FIELD_EVIDENCE = 24
TRAIL_WIRE_FIELDS = ("hypothesis_id", "revision", "status", "statement")
SEMANTIC_FIELDS = ("population", "activity", "task", "context", "mechanism", "suspected_friction")
#: primitive families (a step output `primitives.<family>`: list of strings) joined to a hypothesis through shared cited evidence ids
PRIMITIVE_FAMILIES = ("drivers", "behaviors", "adaptations", "constraints", "workarounds", "physical_interactions", "frictions",
                      "latent_values", "physical_jobs", "unresolved_questions")
#: run-level families: source-independent by definition, offered to every hypothesis of the run
RUN_LEVEL_FAMILIES = ("transferable_invariants", "shared_predicates")


def _clip(v: Any, n: int = TEXT_CHARS) -> Any:
    if isinstance(v, str):
        return v if len(v) <= n else v[: n - 1] + "…"
    if isinstance(v, list):
        return [_clip(x, n) for x in v[:MAX_ITEMS]]
    if isinstance(v, Mapping):
        return {str(k): _clip(x, n) for k, x in v.items()}
    return v


def _newest(outputs: Mapping[str, Any], key: str, order: Iterable[str] = ()) -> Any:
    """The newest accepted step output carrying `key` (top level, then one level down) — the same rule as `service._gather`."""
    for sid in reversed(tuple(order) or tuple(outputs)):
        out = outputs.get(sid)
        if isinstance(out, Mapping):
            if key in out:
                return out[key]
            for v in out.values():
                if isinstance(v, Mapping) and key in v:
                    return v[key]
    return None


def _dicts(v: Any) -> list[Mapping[str, Any]]:
    return [x for x in v or [] if isinstance(x, Mapping)] if isinstance(v, list) else []


def known_origin_ids(outputs: Mapping[str, Any], order: Iterable[str] = ()) -> dict[str, set[str]]:
    """The lead ids and latent-structure ids this run has actually produced — what a hypothesis may name as its origin."""
    order = tuple(order)
    leads = _dicts(_newest(outputs, "population_leads", order)) + _dicts(_newest(outputs, "community_leads", order))
    return {"lead_ids": {str(l["id"]) for l in leads if l.get("id")},
            "latent_structure_ids": {str(s["id"]) for s in _dicts(_newest(outputs, "latent_structures", order)) if s.get("id")}}


def _support_ids(state: Mapping[str, Any]) -> list[str]:
    out = []
    for item in state.get("knowledge_support") or []:
        rid = next((v for k, v in item.items() if k.endswith("_id") and v), None)
        if rid and str(rid) not in out:
            out.append(str(rid))
    return out


def _lead_ref(lead: Mapping[str, Any]) -> dict[str, Any]:
    return _clip({k: lead[k] for k in ("id", "name", "kind", "source_lane", "search_mode", "seed_population", "latent_structure_id",
                                         "voi", "expected_frictions", "activities", "contexts", "why") if lead.get(k) not in (None, "", [])})


def _structure_ref(s: Mapping[str, Any], basis: str) -> dict[str, Any]:
    return _clip({**{k: s[k] for k in ("id", "kind", "text", "physical_job", "shared_predicates", "possible_populations",
                                         "applicability_outside_source", "evidence_refs") if s.get(k) not in (None, "", [])}, "basis": basis})


def _field_evidence(step_outputs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Admitted field evidence of EVERY loop pass, read from the stored admissions joined to their receipts (the evidence boundary's
    own index — one reader of that shape, not two)."""
    entries = [e for e in step_outputs or [] if isinstance(e, Mapping)]
    return [r for r in EB._index_rows(entries).values() if r.get("kind") == "field_evidence"]


def for_hypothesis(state: Mapping[str, Any], outputs: Mapping[str, Any], *, order: Iterable[str] = (),
                   field_rows: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """One hypothesis → its OpportunitySemanticViewV1. `state` is the NEWEST ledger revision (the caller chooses it)."""
    order = tuple(order)
    hid = str(state["hypothesis_id"])
    support = _support_ids(state)
    support_set = set(support)
    missing: list[str] = [f for f in SEMANTIC_FIELDS if not state.get(f)]

    # origin: DECLARED ids only (a lineage claim is never inferred); each id resolved against what the run produced
    leads = {str(l["id"]): l for l in _dicts(_newest(outputs, "population_leads", order)) + _dicts(_newest(outputs, "community_leads", order)) if l.get("id")}
    structures = {str(s["id"]): s for s in _dicts(_newest(outputs, "latent_structures", order)) if s.get("id")}
    lead_ids = [str(i) for i in state.get("lead_ids") or []]
    structure_ids = [str(i) for i in state.get("latent_structure_ids") or []]
    origin_leads = [_lead_ref(leads[i]) for i in lead_ids if i in leads]
    # a declared lead names its own structure: that link is the engine's, already an id
    via_lead = [str(l["latent_structure_id"]) for l in origin_leads if l.get("latent_structure_id")]
    declared = [i for i in dict.fromkeys(structure_ids + via_lead) if i in structures]
    overlap = [i for i, s in structures.items() if i not in declared and support_set & {str(r) for r in s.get("evidence_refs") or []}]
    if not lead_ids and not structure_ids:
        missing.append("origin")

    prim = _newest(outputs, "primitives", order)
    prim = prim if isinstance(prim, Mapping) else {}
    prim_refs = prim.get("evidence_refs") if isinstance(prim.get("evidence_refs"), Mapping) else {}
    relevant = {fam: _clip([str(x) for x in prim.get(fam) or [] if isinstance(x, str)])
                for fam in PRIMITIVE_FAMILIES
                if prim.get(fam) and support_set & {str(r) for r in prim_refs.get(fam) or []}}
    run_level = {fam: _clip([str(x) for x in prim.get(fam) or [] if isinstance(x, str)]) for fam in RUN_LEVEL_FAMILIES if prim.get(fam)}

    bridge = next((b for b in _dicts(_newest(outputs, "bridges", order)) if str(b.get("hypothesis_id")) == hid), None)
    if bridge is None:
        missing.append("bridge")
    jobs = [j for j in _dicts(_newest(outputs, "physical_jobs", order)) if str(j.get("hypothesis_id")) == hid]
    mechanisms = [m for m in _dicts(_newest(outputs, "mechanisms", order)) if str(m.get("hypothesis_id")) == hid]
    mech_ids = {str(m.get("id")) for m in mechanisms if m.get("id")}
    concepts = [c for c in _dicts(_newest(outputs, "product_concepts", order))
                if str(c.get("mechanism_id")) in mech_ids or str(c.get("hypothesis_id") or "") == hid]
    priors = [p for p in _dicts(_newest(outputs, "priors", order)) if hid in [str(x) for x in p.get("hypothesis_ids") or []]]
    territories = [t for t in _dicts(_newest(outputs, "territories", order)) if hid in [str(x) for x in t.get("hypothesis_ids") or []]]
    evidence = [r for r in field_rows or [] if hid in [str(x) for x in r.get("hypothesis_ids") or []]]

    return {
        "view_version": VIEW_VERSION,
        "hypothesis": {"hypothesis_id": hid, "revision": int(state["revision"]), "status": state["status"], "statement": state["statement"],
                       "parent_hypothesis_ids": list(state.get("parent_hypothesis_ids") or [])},
        "origin": {"lead_ids": lead_ids, "latent_structure_ids": structure_ids, "leads": origin_leads[:MAX_ITEMS],
                   "unresolved_ids": [i for i in lead_ids if i not in leads] + [i for i in structure_ids if i not in structures],
                   "seed_population": (any(bool(l.get("seed_population")) for l in origin_leads) if origin_leads else None)},
        "semantics": {**{f: _clip(state.get(f)) for f in SEMANTIC_FIELDS},
                      "assumptions": _clip(list(state.get("assumptions") or [])), "falsifiers": _clip(list(state.get("falsifiers") or [])),
                      "contradictions": _clip([dict(c) for c in state.get("contradictions") or []])},
        "knowledge": {"supporting_evidence_ids": support[:MAX_FIELD_EVIDENCE], "knowledge_support_count": len(support),
                      "knowledge_gaps": _clip([dict(g) for g in state.get("knowledge_gaps") or []]),
                      "field_evidence_ids": list(state.get("field_evidence_ids") or [])[:MAX_FIELD_EVIDENCE]},
        "transduction": {"latent_structures": [_structure_ref(structures[i], "DECLARED") for i in declared][:MAX_ITEMS]
                                              + [_structure_ref(structures[i], "SHARED_EVIDENCE") for i in overlap][:MAX_ITEMS],
                         "primitives_sharing_evidence": relevant, "run_level": run_level},
        "bridge": (_clip({k: bridge[k] for k in ("source", "path", "target_mechanism", "evidence_boundary", "gaps", "alternatives",
                                                 "falsifiers", "status", "grounding") if bridge.get(k) not in (None, "", [])}) if bridge else None),
        "jobs": _clip([{k: j[k] for k in ("job", "mechanism") if j.get(k)} for j in jobs]),
        "mechanisms": _clip([{k: m[k] for k in ("id", "name", "product_terms", "evidence_refs") if m.get(k) not in (None, "", [])} for m in mechanisms]),
        "concepts": _clip([{k: c[k] for k in ("id", "name", "mechanism_id", "form_factor", "target_moment", "buyer", "differentiator", "variations")
                            if c.get(k) not in (None, "", [])} for c in concepts]),
        "trail": {"priors": _clip([{k: p[k] for k in ("registry_record_id", "record_id", "prior_role", "label", "section") if p.get(k)} for p in priors]),
                  "territories": _clip([{k: t[k] for k in ("territory_id", "territory", "territory_name") if t.get(k)} for t in territories])},
        "field_evidence": [_clip({"evidence_id": r.get("id"), "evidence_role": r.get("evidence_role"), "polarity": r.get("polarity"),
                                  "source": r.get("source"), "source_class": r.get("source_class"), "text": r.get("text")})
                           for r in evidence][-MAX_FIELD_EVIDENCE:],
        "missing": missing,
    }


def build(current: Mapping[str, Mapping[str, Any]], outputs: Mapping[str, Any], *, order: Iterable[str] = (),
          step_outputs: Iterable[Mapping[str, Any]] = (), run_id: str | None = None, include_absorbed: bool = False) -> dict[str, Any]:
    """Every live hypothesis of a run → its view, in generation order (`current` = hypothesis_id → NEWEST revision, the store's
    order). Inputs are never mutated: the builder reads deep copies."""
    current, outputs = copy.deepcopy(dict(current or {})), copy.deepcopy(dict(outputs or {}))
    order = tuple(order)
    rows = _field_evidence(copy.deepcopy(list(step_outputs or [])))
    views = [for_hypothesis(s, outputs, order=order, field_rows=rows) for s in current.values()
             if include_absorbed or s.get("status") not in ABSORBED_STATUSES]
    return {"view_version": VIEW_VERSION, "run_id": run_id, "authority": "DERIVED_READ_ONLY — the ledger and the step outputs are the record",
            "hypotheses": views}


# ─────────────────────────────────────────────────────────── consumer projections
def agent_projection(view: Mapping[str, Any]) -> dict[str, Any]:
    """Reasoning steps: everything except the opaque coordinate block."""
    return {k: copy.deepcopy(v) for k, v in view.items() if k != "trail"}


def query_projection(view: Mapping[str, Any]) -> dict[str, Any]:
    """Research planning: the vocabulary a human-language query is compiled from. No evidence text, no concepts."""
    h, s = view["hypothesis"], view["semantics"]
    return {"hypothesis_id": h["hypothesis_id"], "revision": h["revision"], "status": h["status"], "statement": h["statement"],
            **{f: s.get(f) for f in SEMANTIC_FIELDS}, "falsifiers": list(s.get("falsifiers") or []),
            "workarounds": list((view["transduction"]["primitives_sharing_evidence"] or {}).get("workarounds") or []),
            "population_aliases": [l["name"] for l in view["origin"]["leads"] if l.get("name")],
            "knowledge_gaps": copy.deepcopy(view["knowledge"]["knowledge_gaps"]),
            "bridge_gaps": list((view.get("bridge") or {}).get("gaps") or []),
            "territories": copy.deepcopy(view["trail"]["territories"])}


def product_reality_projection(view: Mapping[str, Any]) -> dict[str, Any]:
    """Concept → marketplace research: concepts with the mechanism vocabulary (`product_terms`) that names them on a market."""
    h, s = view["hypothesis"], view["semantics"]
    return {"hypothesis_id": h["hypothesis_id"], "statement": h["statement"], "population": s.get("population"), "activity": s.get("activity"),
            "task": s.get("task"), "suspected_friction": s.get("suspected_friction"), "jobs": copy.deepcopy(view["jobs"]),
            "mechanisms": copy.deepcopy(view["mechanisms"]), "concepts": copy.deepcopy(view["concepts"]),
            "territories": copy.deepcopy(view["trail"]["territories"])}


def trail_projection(hypothesis: Mapping[str, Any]) -> dict[str, Any]:
    """CLOSED: exactly the four fields Trail's `ResearchHypothesisViewV1` admits (`extra="forbid"`). Accepts a view, a view's
    `hypothesis` block, a ledger state or an already-thin context entry; anything else it carries is dropped on purpose."""
    src = hypothesis.get("hypothesis") if isinstance(hypothesis.get("hypothesis"), Mapping) else hypothesis
    return {"hypothesis_id": str(src["hypothesis_id"]), "revision": int(src["revision"]), "status": src["status"], "statement": src["statement"]}


#: Trail's `ResearchHypothesisViewV1` after ADR-069 (embedded core re-pinned): the four fields + the caller's STATED knowledge support +
#: optional STRUCTURED candidates. Still CLOSED — exactly these keys, nothing of the rich view crosses the wire.
TRAIL_WIRE_EXTENDED_FIELDS = TRAIL_WIRE_FIELDS + ("knowledge_support_count", "candidate_friction_families", "candidate_activity", "candidate_task", "candidate_context",
                                                  "candidate_predicates", "candidate_product_territories")


def trail_wire(view: Mapping[str, Any], *, friction_family_ids: Iterable[str] = ()) -> dict[str, Any]:
    """ADR-069 wire for ONE hypothesis from its view. Candidates are DETERMINISTIC facts the ledger already holds — activity / task /
    context verbatim, the run's shared predicates — plus a friction family ONLY when the ledger's `suspected_friction` IS a registry
    family id (the engine's own exact-id rule; free text is never guessed into a family). Absent values stay absent so Trail's lexical
    path decides, exactly as before."""
    h, s = view["hypothesis"], view.get("semantics") or {}
    families = set(friction_family_ids)
    friction = str(s.get("suspected_friction") or "").strip().lower().replace(" ", "_")
    out = {**trail_projection(h), "knowledge_support_count": int((view.get("knowledge") or {}).get("knowledge_support_count") or 0),
           "candidate_friction_families": [friction] if friction and friction in families else [],
           "candidate_activity": _short(s.get("activity")), "candidate_task": _short(s.get("task")), "candidate_context": _short(s.get("context")),
           "candidate_predicates": [str(p) for p in ((view.get("transduction") or {}).get("run_level") or {}).get("shared_predicates") or [] if _identifier(p)][:MAX_ITEMS],
           "candidate_product_territories": []}
    return {k: v for k, v in out.items() if v not in (None, [])}


def _short(v: Any) -> str | None:
    text = " ".join(str(v or "").split())
    return text[:512] or None


def _identifier(v: Any) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", str(v or "")))


PROJECTIONS = {"agent": agent_projection, "query": query_projection, "product_reality": product_reality_projection}


def scope(view: Mapping[str, Any], *, friction_family_ids: Iterable[str] = ()) -> dict[str, Any]:
    """What a manifest path may address: `semantics.hypotheses` (agent projection), `semantics.query`, `semantics.product_reality`
    — each a list in generation order — plus `semantics.trail` (the ADR-069 wire, closed) and `semantics.by_id.<hypothesis_id>` (the full view)."""
    hyps = list(view.get("hypotheses") or [])
    return {"view_version": view.get("view_version"), "authority": view.get("authority"),
            "hypotheses": [agent_projection(v) for v in hyps], "query": [query_projection(v) for v in hyps],
            "product_reality": [product_reality_projection(v) for v in hyps],
            "trail": [trail_wire(v, friction_family_ids=friction_family_ids) for v in hyps],
            "by_id": {v["hypothesis"]["hypothesis_id"]: copy.deepcopy(dict(v)) for v in hyps}}
