"""Per-hypothesis research gaps (restoration reference §9.1 / §9.2). Pure and deterministic.

One hypothesis -> ITS gaps -> ITS research program. Before this module only a step's top-level `knowledge_gaps` reached Trail's
`gaps.compile`; the ledger's own gaps, the bridge's gaps and the agent's `open_gaps` were lost (the newest `open_gaps` in the run is
Trail's own gate list, which shadowed the agent's). `harvest` gathers every legitimate source without duplication, keeps or mints a
STABLE gap id, records where each gap came from, and REFUSES a gap that no live hypothesis owns — Polymath never sends Trail a gap
whose owner Trail would have to guess.

    origin      source                                                           sent to Trail as
    ledger      HypothesisStateV1.knowledge_gaps (status open)                    knowledge_gaps
    step        a non-Trail step output's top-level `knowledge_gaps[]`            knowledge_gaps
    agent_open  a non-Trail step output's `open_gaps[]`                           knowledge_gaps
    bridge      `bridges[].gaps[]` (strings) of the hypothesis's bridge           knowledge_gaps
    trail_gate  the NEWEST Trail output's `open_gaps[]` (governance gate gaps)     open_gaps

`origin` never crosses Trail's closed wire (`trail_gap`); it stays on Polymath's side so the query compiler can tell a semantic
question from governance text ("corroborate from a second independent source") and never search the latter literally."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

from .hypotheses import ABSORBED_STATUSES

MAX_GAPS = 100
SEMANTIC_ORIGINS = ("ledger", "step", "agent_open", "bridge")
GATE_ORIGIN = "trail_gate"
TRAIL_GAP_FIELDS = ("gap_id", "hypothesis_id", "question", "evidence_role")
REFUSAL_MISSING, REFUSAL_NOT_LIVE = "GAP_OWNER_MISSING", "GAP_OWNER_NOT_LIVE"


def _norm(question: Any) -> str:
    return " ".join(str(question or "").lower().split())


def gap_id(hypothesis_id: str, origin: str, question: str) -> str:
    """Stable across rounds: the same question about the same hypothesis keeps its id (no `gap_0`, `gap_1` per round)."""
    return f"gap_{str(hypothesis_id)[4:12]}_{origin[0]}{hashlib.sha256(_norm(question).encode('utf-8')).hexdigest()[:8]}"


def _is_trail_output(out: Mapping[str, Any]) -> bool:
    return "trail_operation_id" in out or "operation_kind" in out


def _ordered(outputs: Mapping[str, Any], order: Iterable[str]) -> list[Mapping[str, Any]]:
    return [outputs[s] for s in (tuple(order) or tuple(outputs)) if isinstance(outputs.get(s), Mapping)]


def harvest(current: Mapping[str, Mapping[str, Any]], outputs: Mapping[str, Any], *, order: Iterable[str] = (),
            default_role: str = "behavior") -> dict[str, Any]:
    """-> {"knowledge_gaps": [...], "open_gaps": [...], "refused": [...]}; every kept gap = {gap_id, hypothesis_id, question,
    evidence_role, origin}. Deterministic: ledger order, then acceptance order; first occurrence of a (hypothesis, question) wins."""
    live = {h for h, s in current.items() if s.get("status") not in ABSORBED_STATUSES}
    outs = _ordered(outputs, order)
    kept: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # gap A-05: a question the LEDGER closed stays closed — the same question never re-enters through another origin (a step's
    # knowledge_gaps, the agent's open_gaps, a bridge) under a new origin-based id. TrailSignal's own gate gaps are TrailSignal's.
    closed = {(str(hid), _norm(g.get("question"))) for hid, state in current.items() for g in state.get("knowledge_gaps") or []
              if isinstance(g, Mapping) and g.get("status") == "closed" and g.get("question")}
    not_reoffered = [0]

    def offer(origin: str, hid: Any, question: Any, role: Any, given_id: Any = None, bucket: list[dict[str, Any]] = kept) -> None:
        q = str(question or "").strip()
        if not q:
            return
        if not hid:
            refused.append({"code": REFUSAL_MISSING, "origin": origin, "question": q[:300]})
            return
        if str(hid) not in live:
            refused.append({"code": REFUSAL_NOT_LIVE, "origin": origin, "hypothesis_id": str(hid), "question": q[:300]})
            return
        key = (str(hid), _norm(q))
        if origin != GATE_ORIGIN and key in closed:
            not_reoffered[0] += 1
            return
        if key in seen:
            return
        seen.add(key)
        bucket.append({"gap_id": str(given_id) if given_id else gap_id(str(hid), origin, q), "hypothesis_id": str(hid), "question": q[:2000],
                       "evidence_role": str(role or default_role), "origin": origin})

    for hid, state in current.items():
        if hid not in live:                      # an absorbed hypothesis's own ledger gaps simply end with it — not a refusal
            continue
        for g in state.get("knowledge_gaps") or []:
            if isinstance(g, Mapping) and g.get("status", "open") == "open":
                offer("ledger", hid, g.get("question"), g.get("evidence_role"), g.get("gap_id"))
    for out in outs:
        if not _is_trail_output(out):
            for g in out.get("knowledge_gaps") or []:
                if isinstance(g, Mapping):
                    offer("step", g.get("hypothesis_id"), g.get("question"), g.get("evidence_role"))
    for out in outs:
        if not _is_trail_output(out):
            for g in out.get("open_gaps") or []:
                if isinstance(g, Mapping):
                    offer("agent_open", g.get("hypothesis_id"), g.get("question"), g.get("evidence_role"))
    bridges = next((o["bridges"] for o in reversed(outs) if isinstance(o.get("bridges"), list)), [])
    for b in bridges:
        if isinstance(b, Mapping):
            for q in b.get("gaps") or []:
                if isinstance(q, str):
                    offer("bridge", b.get("hypothesis_id"), q, None)
    gate: list[dict[str, Any]] = []
    newest_trail = next((o for o in reversed(outs) if _is_trail_output(o) and isinstance(o.get("open_gaps"), list)), None)
    for g in (newest_trail or {}).get("open_gaps") or []:
        if isinstance(g, Mapping):
            offer(GATE_ORIGIN, g.get("hypothesis_id"), g.get("question"), g.get("evidence_role"), g.get("gap_id"), bucket=gate)
    return {"knowledge_gaps": kept[:MAX_GAPS], "open_gaps": gate[:MAX_GAPS], "refused": refused[:MAX_GAPS],
            "dropped_over_cap": max(0, len(kept) - MAX_GAPS) + max(0, len(gate) - MAX_GAPS), "closed_not_reoffered": not_reoffered[0]}


def trail_gap(gap: Mapping[str, Any]) -> dict[str, Any]:
    """CLOSED: exactly the fields of Trail's `ResearchKnowledgeGapV1` (`extra="forbid"`)."""
    return {k: gap[k] for k in TRAIL_GAP_FIELDS}


def trail_gap_payload(semantics: Mapping[str, Any] | None) -> dict[str, list[dict[str, Any]]] | None:
    """The `knowledge_gaps` / `open_gaps` of a `gaps.compile` payload from a harvested set — or None when the step did not opt in
    (the caller then keeps its previous behaviour)."""
    harvested = (semantics or {}).get("research_gaps") if isinstance(semantics, Mapping) else None
    if not isinstance(harvested, Mapping):
        return None
    return {"knowledge_gaps": [trail_gap(g) for g in harvested.get("knowledge_gaps") or []],
            "open_gaps": [trail_gap(g) for g in harvested.get("open_gaps") or []]}


def unowned_gap_errors(payload: Any, live_hypothesis_ids: Iterable[str]) -> list[str]:
    """Submit-time law (reference §9.2): every gap an agent writes at the TOP LEVEL of a reasoning payload (`knowledge_gaps`,
    `open_gaps`) names the live hypothesis it belongs to. (A gap nested in a hypothesis proposal or in a REVISE `changes` object is
    owned by that hypothesis already.) A typed refusal — never a guess, never the first hypothesis."""
    live = set(live_hypothesis_ids)
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return errors
    for key in ("knowledge_gaps", "open_gaps"):
        for n, g in enumerate(payload.get(key) or [] if isinstance(payload.get(key), list) else []):
            if not isinstance(g, Mapping):
                continue
            hid = g.get("hypothesis_id")
            if not hid:
                errors.append(f"{REFUSAL_MISSING}: {key}[{n}] names no hypothesis_id — a research gap belongs to exactly one live hypothesis")
            elif str(hid) not in live:
                errors.append(f"{REFUSAL_NOT_LIVE}: {key}[{n}] names {hid!r}, which is not a live hypothesis of this run")
    return errors
