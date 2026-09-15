"""Generic hypothesis ledger (ADR-0019 §3/§4). Pure and deterministic: functions over HypothesisStateV1 /
HypothesisTransitionV1 dicts; persistence is the store's job. The engine knows hypotheses, revisions and transitions and
never a domain: θ (the connected agent) may GENERATE, REVISE and SPLIT; φ (a TrailSignal deterministic verdict or a closed
VALIDATE rule) applies selective pressure — KILL, MERGE, WEAKEN, STRENGTHEN, CONTRADICT, PROMOTE. Every transition names
at least one cause of an allowed kind and every revision keeps its parents: ancestry and the evidence that changed a
hypothesis are never lost. A registry prior (`trail_prior`) may be attached as a coordinate but never cited as evidence."""
from __future__ import annotations

import hashlib
from typing import Any

from .contracts import (CITABLE_EVIDENCE_KINDS, HYPOTHESIS_STATUSES, PRIOR_EVIDENCE_KINDS, TRANSITION_KINDS,
                        assert_valid)


class HypothesisRejected(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


THETA_KINDS = frozenset({"GENERATE", "REVISE", "SPLIT"})                                   # generative transformation
PHI_KINDS = frozenset({"KILL", "MERGE", "WEAKEN", "STRENGTHEN", "CONTRADICT", "PROMOTE"})  # selective pressure
RESULTING_STATUS = {"GENERATE": "proposed", "REVISE": "revised", "SPLIT": "split", "MERGE": "merged", "WEAKEN": "weakened",
                    "STRENGTHEN": "strengthened", "CONTRADICT": "contradicted", "KILL": "killed", "PROMOTE": "promoted"}
ABSORBED_STATUSES = frozenset({"killed", "merged"})     # no further transitions
KNOWLEDGE_ID_FIELD = {"chunk": "chunk_id", "document": "document_id", "parent_map": "document_id", "graph_fact": "graph_fact_id",
                      "graph_hop": "graph_fact_id", "query_receipt": "retrieval_trace_id"}
CAUSE_KINDS = frozenset({"chunk", "document", "graph_fact", "graph_hop", "parent_map", "trail_prior", "field_evidence",
                         "evidence_admission", "hypothesis", "step_output"})
REVISABLE_FIELDS = ("statement", "mechanism", "population", "activity", "task", "context", "suspected_friction")


def _h(*parts: Any) -> str:
    return hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def hypothesis_id(run_id: str, step_id: str, ordinal: int) -> str:
    return "hyp_" + _h(run_id, step_id, ordinal)[:24]


def transition_id(run_id: str, hid: str, sequence: int, ordinal: int) -> str:
    return "hxt_" + _h(run_id, hid, sequence, ordinal)[:24]


def _allowed(refs: list[dict[str, Any]]) -> dict[str, str]:
    return {str(r["id"]): str(r["kind"]) for r in refs or []}


def _split_cited(ids: list[str], allowed: dict[str, str], errors: list[str], *, label: str) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Cited ids → (knowledge_support items, field_evidence ids, cause refs). Priors and unknown ids are refused."""
    support, field, causes = [], [], []
    for i in ids or []:
        kind = allowed.get(str(i))
        if kind is None:
            errors.append(f"{label}: {i!r} is not in context.evidence_refs")
            continue
        if kind in PRIOR_EVIDENCE_KINDS:
            errors.append(f"{label}: {i!r} is a registry prior and may never be cited as evidence")
            continue
        if kind not in CITABLE_EVIDENCE_KINDS:
            errors.append(f"{label}: {i!r} has non-citable kind {kind!r}")
            continue
        causes.append({"kind": kind, "id": str(i)})
        if kind == "field_evidence":
            field.append(str(i))
        elif kind in KNOWLEDGE_ID_FIELD:
            item = {"chunk_id": None, "document_id": None, "graph_fact_id": None, "retrieval_trace_id": None, "evidence_role": "background"}
            item[KNOWLEDGE_ID_FIELD[kind]] = str(i)
            support.append(item)
    return support, field, causes


def _priors(proposal: dict[str, Any], allowed: dict[str, str], snapshot_id: str | None, errors: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out, causes = [], []
    for p in proposal.get("trail_priors") or []:
        rid = str(p.get("registry_record_id", ""))
        if allowed.get(rid) not in PRIOR_EVIDENCE_KINDS:
            errors.append(f"trail_priors: {rid!r} is not a trail_prior in context")
            continue
        if not snapshot_id:
            errors.append("trail_priors cited but the run records no registry snapshot")
            continue
        out.append({"registry_snapshot_id": snapshot_id, "registry_record_id": rid, "prior_role": p.get("prior_role", "niche_candidate")})
        causes.append({"kind": "trail_prior", "id": rid})
    return out, causes


def _state(hid: str, run_id: str, proposal: dict[str, Any], *, parents: list[str], support, priors, field, recorded_at: str) -> dict[str, Any]:
    roles = proposal.get("support_roles") or {}
    for item in support:
        rid = next(v for k, v in item.items() if k.endswith("_id") and v)
        if rid in roles:
            item["evidence_role"] = roles[rid]
    contradictions = [{"statement": c.get("statement") or "cited contradicting evidence", "evidence_ids": list(c.get("evidence_ids") or [])}
                      for c in (proposal.get("contradictions") or []) if c.get("evidence_ids")]
    gaps = [{"gap_id": g.get("gap_id") or f"gap_{hid[4:12]}_{n}", "question": g["question"], "evidence_role": g.get("evidence_role", "behavior"),
             "status": g.get("status", "open")} for n, g in enumerate(proposal.get("knowledge_gaps") or []) if g.get("question")]
    return {"hypothesis_id": hid, "run_id": run_id, "parent_hypothesis_ids": list(parents), "revision": 0, "statement": proposal["statement"],
            "mechanism": proposal.get("mechanism"), "population": proposal.get("population"), "activity": proposal.get("activity"),
            "task": proposal.get("task"), "context": proposal.get("context"), "suspected_friction": proposal.get("suspected_friction"),
            "status": "proposed", "knowledge_support": support, "trail_priors": priors, "field_evidence_ids": sorted(set(field)),
            "assumptions": list(proposal.get("assumptions") or []), "contradictions": contradictions,
            "falsifiers": list(proposal.get("falsifiers") or []), "knowledge_gaps": gaps, "created_at": recorded_at, "updated_at": recorded_at}


def _transition(run_id: str, hid: str, kind: str, actor: str, step: dict[str, Any], ordinal: int, *, parents, children, causes,
                from_rev, to_rev, status, reason: str, recorded_at: str) -> dict[str, Any]:
    t = {"transition_id": transition_id(run_id, hid, int(step["sequence"]), ordinal), "run_id": run_id, "hypothesis_id": hid, "kind": kind,
         "actor": actor, "step_id": step["step_id"], "sequence": int(step["sequence"]), "parent_hypothesis_ids": list(parents),
         "child_hypothesis_ids": list(children), "cause_refs": list(causes), "from_revision": from_rev, "to_revision": to_rev,
         "resulting_status": status, "reason_code": reason, "proposal_receipt_hash": None, "recorded_at": recorded_at}
    assert_valid("hypothesis_transition", t)
    return t


# ─────────────────────────────────────────────────────────── θ: generate
def generate(run_id: str, step: dict[str, Any], proposals: list[dict[str, Any]], *, registry_snapshot_id: str | None,
             recorded_at: str, max_hypotheses: int = 8, parents: list[str] | None = None,
             ordinal_base: int = 0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """θ output → new HypothesisStateV1 revisions (revision 0) + GENERATE transitions. Every proposal must cite ≥1 evidence
    id from the step's context (knowledge or admitted field evidence); priors may be attached, never cited."""
    errors: list[str] = []
    allowed = _allowed(step.get("context", {}).get("evidence_refs") or [])
    if not proposals or len(proposals) > max_hypotheses:
        errors.append(f"between 1 and {max_hypotheses} hypotheses are required (got {len(proposals or [])})")
    states, transitions = [], []
    for n, prop in enumerate(proposals or []):
        if not isinstance(prop, dict) or not str(prop.get("statement", "")).strip():
            errors.append(f"hypothesis {n}: statement is required")
            continue
        support, field, causes = _split_cited(list(prop.get("supporting_evidence_ids") or []), allowed, errors, label=f"hypothesis {n}")
        priors, pcauses = _priors(prop, allowed, registry_snapshot_id, errors)
        if not causes:
            errors.append(f"hypothesis {n}: cite at least one evidence id")
            continue
        hid = hypothesis_id(run_id, step["step_id"], ordinal_base + n)
        st = _state(hid, run_id, prop, parents=parents or [], support=support, priors=priors, field=field, recorded_at=recorded_at)
        assert_valid("hypothesis_state", st)
        states.append(st)
        transitions.append(_transition(run_id, hid, "GENERATE", "theta", step, n, parents=parents or [], children=[], causes=causes + pcauses,
                                       from_rev=None, to_rev=0, status="proposed", reason="THETA_GENERATED", recorded_at=recorded_at))
    if errors:
        raise HypothesisRejected(errors)
    return states, transitions


# ─────────────────────────────────────────────────────────── θ / φ: transitions on existing hypotheses
def apply(run_id: str, step: dict[str, Any], current: dict[str, dict[str, Any]], requests: list[dict[str, Any]], *, actor: str,
          allowed_causes: dict[str, str], recorded_at: str, registry_snapshot_id: str | None = None,
          max_hypotheses: int = 8) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply typed transition requests to the CURRENT revisions (`current` = hypothesis_id → latest state). Returns the new
    revisions (and any children) plus the transition records. θ may only GENERATE/REVISE/SPLIT; φ applies selective pressure."""
    errors: list[str] = []
    new_states: dict[str, dict[str, Any]] = {}
    transitions: list[dict[str, Any]] = []
    live = dict(current)
    ordinal = 0

    def bump(hid: str, **changes: Any) -> dict[str, Any]:
        base = new_states.get(hid) or live[hid]
        st = {**base, **changes, "revision": int(base["revision"]) + (0 if hid in new_states else 1), "updated_at": recorded_at}
        new_states[hid] = st
        return st

    for n, req in enumerate(requests or []):
        kind, hid = str(req.get("kind", "")), str(req.get("hypothesis_id", ""))
        label = f"transition {n}"
        if kind not in TRANSITION_KINDS or kind == "GENERATE":
            errors.append(f"{label}: unknown or non-applicable kind {kind!r}"); continue
        if hid not in live:
            errors.append(f"{label}: unknown hypothesis {hid!r}"); continue
        if (new_states.get(hid) or live[hid])["status"] in ABSORBED_STATUSES:
            errors.append(f"{label}: {hid} is {live[hid]['status']} and cannot transition"); continue
        if actor == "theta" and kind not in THETA_KINDS:
            errors.append(f"{label}: {kind} is selective pressure and requires phi, not theta"); continue
        if actor not in ("theta", "phi", "runtime"):
            errors.append(f"{label}: unknown actor {actor!r}"); continue
        causes = []
        for c in req.get("cause_refs") or []:
            ck, ci = c.get("kind"), str(c.get("id", ""))
            if ck not in CAUSE_KINDS or allowed_causes.get(ci) != ck:
                errors.append(f"{label}: cause {ck}:{ci} is not an allowed cause in this step"); continue
            causes.append({"kind": ck, "id": ci})
        if not causes:
            errors.append(f"{label}: at least one cause ref is required"); continue
        reason = str(req.get("reason_code") or f"{actor.upper()}_{kind}")
        field_add = []
        for fid in req.get("field_evidence_ids") or []:
            if allowed_causes.get(str(fid)) != "field_evidence":
                errors.append(f"{label}: {fid!r} is not admitted field evidence"); continue
            field_add.append(str(fid))
        prev = new_states.get(hid) or live[hid]
        from_rev = int(prev["revision"])
        if kind == "SPLIT":
            children = req.get("children") or []
            if not children:
                errors.append(f"{label}: SPLIT needs children"); continue
            if len(live) + len(children) > max_hypotheses:
                errors.append(f"{label}: SPLIT would exceed max_hypotheses {max_hypotheses}"); continue
            child_ids = []
            for k, child in enumerate(children):
                cid = hypothesis_id(run_id, step["step_id"], 100 * (n + 1) + k)
                allowed_refs = [{"kind": v, "id": i} for i, v in allowed_causes.items()]
                cs, cf, cc = _split_cited(list(child.get("supporting_evidence_ids") or []), _allowed(allowed_refs), errors, label=f"{label} child {k}")
                st = _state(cid, run_id, {**child, "statement": child.get("statement") or prev["statement"]}, parents=[hid],
                            support=cs or list(prev["knowledge_support"]), priors=list(prev["trail_priors"]), field=cf + list(prev["field_evidence_ids"]), recorded_at=recorded_at)
                assert_valid("hypothesis_state", st)
                new_states[cid] = st; live[cid] = st; child_ids.append(cid)
                transitions.append(_transition(run_id, cid, "GENERATE", actor, step, ordinal, parents=[hid], children=[], causes=causes + [{"kind": "hypothesis", "id": hid}] + cc,
                                               from_rev=None, to_rev=0, status="proposed", reason=reason, recorded_at=recorded_at)); ordinal += 1
            st = bump(hid, status="split")
            transitions.append(_transition(run_id, hid, "SPLIT", actor, step, ordinal, parents=prev["parent_hypothesis_ids"], children=child_ids, causes=causes,
                                           from_rev=from_rev, to_rev=st["revision"], status="split", reason=reason, recorded_at=recorded_at)); ordinal += 1
            continue
        if kind == "MERGE":
            into = str(req.get("into_hypothesis_id", ""))
            if into not in live or into == hid or (new_states.get(into) or live[into])["status"] in ABSORBED_STATUSES:
                errors.append(f"{label}: MERGE target {into!r} is unknown, absorbed or the same hypothesis"); continue
            tgt = new_states.get(into) or live[into]
            merged_support = list(tgt["knowledge_support"]) + [s for s in prev["knowledge_support"] if s not in tgt["knowledge_support"]]
            t2 = bump(into, parent_hypothesis_ids=sorted(set(tgt["parent_hypothesis_ids"]) | {hid}), knowledge_support=merged_support,
                      field_evidence_ids=sorted(set(tgt["field_evidence_ids"]) | set(prev["field_evidence_ids"]) | set(field_add)),
                      contradictions=list(tgt["contradictions"]) + [c for c in prev["contradictions"] if c not in tgt["contradictions"]])
            assert_valid("hypothesis_state", t2)
            transitions.append(_transition(run_id, into, "REVISE", actor, step, ordinal, parents=t2["parent_hypothesis_ids"], children=[],
                                           causes=causes + [{"kind": "hypothesis", "id": hid}], from_rev=int(tgt["revision"]), to_rev=t2["revision"],
                                           status=t2["status"] if t2["status"] != "proposed" else "revised", reason="MERGED_IN", recorded_at=recorded_at)); ordinal += 1
            t2["status"] = t2["status"] if t2["status"] != "proposed" else "revised"
            st = bump(hid, status="merged")
            transitions.append(_transition(run_id, hid, "MERGE", actor, step, ordinal, parents=prev["parent_hypothesis_ids"], children=[into], causes=causes,
                                           from_rev=from_rev, to_rev=st["revision"], status="merged", reason=reason, recorded_at=recorded_at)); ordinal += 1
            continue
        changes: dict[str, Any] = {"status": RESULTING_STATUS[kind]}
        if kind == "REVISE":
            for f in REVISABLE_FIELDS:
                if f in (req.get("changes") or {}):
                    changes[f] = req["changes"][f]
        if kind == "CONTRADICT":
            contra = [{"statement": c.get("statement") or "contradicting evidence admitted", "evidence_ids": list(c.get("evidence_ids") or [])}
                      for c in (req.get("contradictions") or []) if c.get("evidence_ids")]
            if not contra:
                errors.append(f"{label}: CONTRADICT needs contradictions with evidence_ids"); continue
            changes["contradictions"] = list(prev["contradictions"]) + contra
        if field_add:
            changes["field_evidence_ids"] = sorted(set(prev["field_evidence_ids"]) | set(field_add))
        st = bump(hid, **changes)
        assert_valid("hypothesis_state", st)
        transitions.append(_transition(run_id, hid, kind, actor, step, ordinal, parents=st["parent_hypothesis_ids"], children=[], causes=causes,
                                       from_rev=from_rev, to_rev=st["revision"], status=st["status"], reason=reason, recorded_at=recorded_at)); ordinal += 1
    if errors:
        raise HypothesisRejected(errors)
    return list(new_states.values()), transitions


def context_view(current: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The bounded view an issued step carries: live (non-absorbed) hypotheses, newest revision, in generation order (the store's
    order; never the run-id-dependent hash order of the ids)."""
    return [{"hypothesis_id": h, "revision": int(s["revision"]), "status": s["status"], "statement": s["statement"]}
            for h, s in current.items() if s["status"] not in ABSORBED_STATUSES]


def lineage_intact(states: list[dict[str, Any]], transitions: list[dict[str, Any]]) -> list[str]:
    """Invariant check (tests + store): every revision > 0 has a transition reaching it; every child names its parent; every
    transition has ≥1 cause; a split/merge parent appears in its children's parent lists."""
    errs = []
    by_hid: dict[str, list[dict[str, Any]]] = {}
    for t in transitions:
        by_hid.setdefault(t["hypothesis_id"], []).append(t)
        if not t["cause_refs"]:
            errs.append(f"{t['transition_id']}: no cause")
    for s in states:
        hid = s["hypothesis_id"]
        revs = {t["to_revision"] for t in by_hid.get(hid, [])}
        if int(s["revision"]) not in revs:
            errs.append(f"{hid} r{s['revision']}: no transition produced this revision")
        for t in by_hid.get(hid, []):
            for p in t["parent_hypothesis_ids"]:
                if p not in s["parent_hypothesis_ids"] and t["kind"] == "GENERATE":
                    errs.append(f"{hid}: parent {p} recorded on the transition but missing from the state")
    return errs
