"""Semantic query compilation (restoration reference §9.3 / §9.4). Pure; no I/O.

Trail decides WHAT evidence is needed (role, stage, source classes, freshness, independence, budget) and ships stage templates with
grammar slots. Polymath owns the human-language vocabulary. This module turns ONE hypothesis's semantic state (the governed
runtime's query projection: population, activity, task, context, friction, workarounds, mechanism, falsifiers) plus ONE evidence
gap into a search string, and binds Trail's template slots from the same state.

Two laws:
  * governance text is never a search string. A gate gap ("corroborate from a second independent source", "reach 10 independent
    observations (2 so far)") states an evidence REQUIREMENT; the search that serves it is compiled from the vocabulary of the
    hypothesis that gap belongs to. Only a gap a reasoning step wrote (`origin` ledger / step / agent_open / bridge) contributes
    its own words.
  * a slot that cannot be bound is REPORTED (`missing`), never sent to a search engine as `{activity}`."""
from __future__ import annotations

import re
from typing import Any, Mapping

SEMANTIC_ORIGINS = frozenset({"ledger", "step", "agent_open", "bridge"})
MAX_TERMS = 8
#: Trail's grammar slot -> the hypothesis field that binds it (`product_territory` binds from a territory NAME, when Trail returns one)
SLOT_FIELDS = {"activity": "activity", "task": "task", "friction_family": "suspected_friction", "friction": "suspected_friction",
               "population": "population", "context": "context"}
#: vocabulary a role adds to the search when the hypothesis offers nothing more specific
ROLE_TERMS = {"workaround": ("workaround",), "demand": ("worth", "buying"), "price": ("price",)}
_SLOT = re.compile(r"{(\w+)}")


#: function words the engine's gap stop-list does not cover, and the vocabulary of evidence GOVERNANCE — a reasoning step may echo it
#: ("independent voices", "a second source") but it names a requirement on the evidence, never something a person would type
_FUNCTION_WORDS = frozenset({"while", "during", "because", "without", "within", "onto", "over", "under", "between", "across", "being", "very", "more", "most",
                             "some", "your", "our", "its", "out", "outside", "inside", "one", "two", "three", "not", "never", "already", "use", "using"})
GOVERNANCE_TERMS = frozenset({"independent", "independence", "voices", "voice", "corroborate", "corroboration", "observations", "observation", "admitted",
                              "admission", "source", "sources", "thread", "threads", "second", "evidence", "record", "records", "far", "yet"})


def keywords(text: Any, n: int = MAX_TERMS, *, drop: frozenset = frozenset()) -> list[str]:
    from executors import _gap_keywords                      # the engine's one stop-word rule
    return [t for t in _gap_keywords(str(text or "").replace("_", " "), 24) if t not in _FUNCTION_WORDS and t not in drop][:n]


def _merge(*groups: list[str], cap: int = MAX_TERMS) -> list[str]:
    out: list[str] = []
    for g in groups:
        for t in g:
            if t not in out:
                out.append(t)
    return out[:cap]


def vocabulary(view: Mapping[str, Any] | None) -> dict[str, list[str]]:
    v = view or {}
    who = keywords(v.get("population"), 3) or keywords(next(iter(v.get("population_aliases") or []), ""), 3)
    return {"who": who, "doing": keywords(v.get("task"), 3) or keywords(v.get("activity"), 2), "activity": keywords(v.get("activity"), 2),
            "friction": keywords(v.get("suspected_friction"), 3), "workaround": keywords(next(iter(v.get("workarounds") or []), ""), 3),
            "context": keywords(v.get("context"), 2), "mechanism": keywords(v.get("mechanism"), 3)}


def gap_query(gap: Mapping[str, Any], view: Mapping[str, Any] | None, *, origin: str | None, statement: str = "") -> dict[str, Any]:
    """-> {"query": str, "basis": [...], "used_question": bool}. `query` is "" when nothing lawful can be compiled (the caller
    reports it; it never falls back to governance text)."""
    voc = vocabulary(view)
    role = str(gap.get("evidence_role") or "")
    semantic = origin in SEMANTIC_ORIGINS
    own = keywords(gap.get("question"), 6, drop=GOVERNANCE_TERMS) if semantic else []
    has_state = bool(voc["who"] or voc["doing"] or voc["friction"])
    if not has_state:
        # no semantic state for this hypothesis: a reasoning step's own question may be searched; governance text may not
        terms, basis = (own, ["gap_question"]) if own else (keywords(statement, 6), ["hypothesis_statement"] if statement else [])
        return {"query": " ".join(terms), "basis": basis, "used_question": bool(own)}
    focus = {"workaround": voc["workaround"] or voc["friction"], "friction": voc["friction"], "behavior": voc["friction"] or voc["context"],
             "demand": voc["friction"], "price": voc["mechanism"] or voc["friction"]}.get(role, voc["friction"])
    novel = [t for t in own if t not in voc["who"] + voc["doing"] + focus][:2]
    # with the gap's own words: who 2 + doing 2 + the gap's 2 + focus 2; without (a gate gap): who 3 + doing 3 + focus 3 — eight terms at most
    parts = (voc["who"][:2], voc["doing"][:2], novel, focus[:2]) if novel else (voc["who"], voc["doing"], focus)
    terms = _merge(*parts, list(ROLE_TERMS.get(role, ())))
    basis = [k for k, used in (("population", voc["who"]), ("task", voc["doing"]), ("gap_question", novel), ("friction", focus), ("role", ROLE_TERMS.get(role))) if used]
    return {"query": " ".join(terms), "basis": basis, "used_question": bool(novel)}


def falsifier_query(view: Mapping[str, Any]) -> dict[str, Any]:
    """One contradiction-seeking search per hypothesis: who + what they do + the words of its first falsifier."""
    voc = vocabulary(view)
    falsifier = next(iter(view.get("falsifiers") or []), "")
    if not falsifier or not (voc["who"] or voc["doing"]):
        return {"query": "", "basis": []}
    return {"query": " ".join(_merge(voc["who"], voc["doing"], keywords(falsifier, 4))), "basis": ["population", "task", "falsifier"], "falsifier": str(falsifier)[:300]}


def bind_template(template: str, view: Mapping[str, Any] | None, *, overrides: Mapping[str, str] | None = None) -> tuple[str | None, list[str]]:
    """Trail's template with every slot bound from the hypothesis's state -> (text, []); or (None, [missing slot names]).
    `overrides`: a slot value the caller already compiled (product reality binds `{product_territory}` with the CONCEPT's market
    phrase — form factor + the mechanism's `product_terms` — not with a registry territory)."""
    v = view or {}
    values: dict[str, str] = {}
    missing: list[str] = []
    for slot in dict.fromkeys(_SLOT.findall(template or "")):
        if (overrides or {}).get(slot):
            value = " ".join(str(overrides[slot]).split())
        elif slot == "product_territory":
            name = next((str(t.get("territory_name")) for t in v.get("territories") or [] if isinstance(t, Mapping) and t.get("territory_name")), "")
            value = " ".join(keywords(name, 4))
        else:
            value = " ".join(keywords(v.get(SLOT_FIELDS.get(slot, "")), 4)) if slot in SLOT_FIELDS else ""
        if value:
            values[slot] = value
        else:
            missing.append(slot)
    if missing:
        return None, missing
    return " ".join(_SLOT.sub(lambda m: values[m.group(1)], template).split()), []


def has_unbound_slot(text: Any) -> bool:
    return bool(_SLOT.search(str(text or "")))
