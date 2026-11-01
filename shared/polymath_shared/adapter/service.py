"""The adapter-run service: what the orchestrator routes (adapter_*) and the step worker call. Composes the pure core
(transitions/manifest/contracts) with the store; each public function runs inside the caller's transaction."""
from __future__ import annotations

import json
import os

import datetime as _dt
import hashlib
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .contracts import AGENT_ANSWERED_STEP_TYPES, AUTOMATIC_STEP_TYPES, PRIOR_EVIDENCE_KINDS, ContractViolation, assert_valid, bounded_text, stable_hash, validate
from .manifest import ADAPTER_DIR, Manifest, ManifestError, ManifestInvalid, list_manifests
from . import corpus_seed as CS, domain as DOMAIN, evidence_boundary as EB, hypotheses as H, research_gaps as RG, semantic_view as SV, store, trail_client, transitions as T
from .hypotheses import HypothesisRejected
from .transitions import BudgetExhausted, RunState, SubmissionRejected

#: an executor for one automatic step: (step, state, manifest) -> ExecOutcome
ExecOutcome = dict[str, Any]   # keys: output (dict), evidence_refs (list), external (dict|None), gap (dict|None)
Executor = Callable[[dict[str, Any], RunState, Manifest], ExecOutcome]

KNOWLEDGE_KINDS = ("chunk", "document", "graph_fact", "graph_hop", "parent_map")
MAX_CONTEXT_REFS = 200
CONTEXT_CLASS_ORDER = ("field_evidence", "chunk", "graph_fact", "other")
#: reserved DISPLAY floor per class (floors sum to MAX_CONTEXT_REFS, unused spills over); this budgets ONLY what an issued step shows
#: for citation, never the gate-facing admitted set (context.admitted_evidence_ids carries that complete, uncapped from the store).
CONTEXT_BUDGET = {"field_evidence": 80, "chunk": 50, "graph_fact": 40, "other": 30}


def _context_class(kind: str) -> str:
    return kind if kind in ("field_evidence", "chunk", "graph_fact") else "other"


class UnknownAdapter(KeyError):
    pass


class UnknownRun(KeyError):
    pass


class NotTerminal(RuntimeError):
    pass


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=4)
def _registry(directory: str) -> dict[str, Manifest]:
    return {m.adapter_id: m for m in list_manifests(Path(directory))}


def registry(directory: Path | None = None) -> dict[str, Manifest]:
    return _registry(str(directory or ADAPTER_DIR))


def reset_registry() -> None:
    _registry.cache_clear()


def manifest_for(adapter_id: str, directory: Path | None = None) -> Manifest:
    try:
        return registry(directory)[adapter_id]
    except KeyError:
        raise UnknownAdapter(adapter_id) from None


def list_adapters(directory: Path | None = None) -> list[dict[str, Any]]:
    out = []
    for m in registry(directory).values():
        ext = [s for s in m.steps.values() if s["type"] == "EXTERNAL_OPERATION"]
        out.append({**m.identity, "description": m.raw.get("description", ""), "steps": len(m.steps),
                    "agent_reason_steps": sum(1 for s in m.steps.values() if s["type"] == "AGENT_REASON"),
                    "external_operations": {"working": sum(1 for s in ext if (s.get("external") or {}).get("availability") == "working"),
                                            "planned": sum(1 for s in ext if (s.get("external") or {}).get("availability") == "planned")},
                    "input_schema": m.raw.get("input_schema"), "entry_step_id": m.entry_step_id, "terminal_step_id": m.terminal_step_id})
    return out


# ─────────────────────────────────────────────────────────── lifecycle (routes)
class NotRunOwner(Exception):
    """A request made on behalf of a principal named a run that principal does not own (or that does not exist — the two
    are deliberately indistinguishable to the caller)."""


def assert_owner(conn, run_id: str, principal_id: str | None) -> None:
    """RUN OWNERSHIP. No principal = the legacy / trusted-local caller: unchanged. With a principal, ONLY a run whose
    `owner_principal_id` equals it is reachable; a NULL owner is legacy state, never "public"."""
    if principal_id is None:
        return
    exists, owner = store.run_owner(conn, run_id)
    if not exists or owner != principal_id:
        raise NotRunOwner(run_id)


START_RECEIPT_VERSION = "adapter_start_receipt.v1"


def start(conn, *, adapter_id: str, input_payload: dict[str, Any], request_options: dict[str, Any] | None = None,
          directory: Path | None = None, owner_principal_id: str | None = None,
          corpus_view: Callable[[list[str]], Any] | None = None, catalog: Any = None) -> dict[str, Any]:
    """Create a durable run (status running — the worker picks it up). Idempotent on request_options.idempotency_key.

    PRODUCT-SEARCH-E2E: an entry step may opt into start-time scope work through its `config` (manifest data, no domain named here):
    `seed_check` (a domain operation that tells a seed that can generate nothing, early and plainly — SEED_NOT_GENERATIVE with a hint),
    `corpus_scope` (named corpora validated now; none named = the caller's share of "all libraries", `corpus_view` narrowing it for a
    principal) and `corpus_seed` (no seed = one derived from the corpora, `<field>_origin: corpus`). The corpus readers are the store's
    (`catalog` = the store unless a caller hands another). What was decided travels as the
    START RECEIPT: beside the run ref in the response, kept in the run's request options, and recorded by the entry step's output.
    A refusal raises CS.StartRefused (a SubmissionRejected-compatible typed error: code, message, hint)."""
    m = manifest_for(adapter_id, directory)
    opts = dict(request_options or {})
    assert_valid("adapter_run_request", {"adapter_id": adapter_id, "input": input_payload, "request_options": opts})
    key = opts.get("idempotency_key")
    if key and owner_principal_id:
        key = f"{key}@{owner_principal_id}"          # an idempotency key is per owner: never another principal's run
    if key:
        existing = store.find_run_by_idempotency(conn, f"{adapter_id}:{key}")
        if existing:
            return _with_start_receipt(conn, existing)
    seed = f"{adapter_id}:{key}" if key else f"{adapter_id}:{uuid.uuid4()}"
    run_id = "adr_" + hashlib.sha256(seed.encode()).hexdigest()[:32]
    T.start_run(m, run_id, input_payload, opts)                       # the REQUESTER's input is valid before anything is derived
    inp, receipt = dict(input_payload), None
    entry_cfg = m.step(m.entry_step_id).get("config") or {}
    if any(entry_cfg.get(k) is not None for k in ("seed_check", "corpus_scope", "corpus_seed")):
        inp, opts, receipt = _start_scope(conn, m, run_id, inp, opts, entry_cfg, corpus_view=corpus_view, catalog=catalog or store)
    state = T.start_run(m, run_id, inp, opts)
    state = T.replace(state, status="running")
    store.insert_run(conn, state, m, idempotency_key=(f"{adapter_id}:{key}" if key else None),
                     agent_identity=opts.get("agent_identity"))
    if owner_principal_id:
        store.set_run_owner(conn, run_id, owner_principal_id)
    return _with_start_receipt(conn, run_id)


def _with_start_receipt(conn, run_id: str) -> dict[str, Any]:
    """The AdapterRunRefV1 (validated, unchanged) plus — beside it, never inside it — the run's start receipt when it has one."""
    ref = run_ref(conn, run_id)
    loaded = store.load_run(conn, run_id)
    receipt = (loaded[0].options or {}).get("start_receipt") if loaded else None
    return {**ref, "start_receipt": receipt} if isinstance(receipt, dict) else ref


def _start_scope(conn, m: Manifest, run_id: str, inp: dict[str, Any], opts: dict[str, Any], cfg: dict[str, Any], *,
                 corpus_view, catalog) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    seed_cfg = cfg.get("corpus_seed") if isinstance(cfg.get("corpus_seed"), dict) else {}
    check_cfg = cfg.get("seed_check") if isinstance(cfg.get("seed_check"), dict) else None
    field = str(seed_cfg.get("field") or (check_cfg or {}).get("field") or "seed")
    given = inp.get(field).strip() if isinstance(inp.get(field), str) and inp.get(field).strip() else None
    inp.pop(f"{field}_origin", None)                                   # the runtime says where the seed came from, never the requester
    receipt: dict[str, Any] = {"schema_version": START_RECEIPT_VERSION}
    if given and check_cfg:
        receipt["seed_check"] = _seed_check(m, run_id, inp, field, check_cfg)
    if cfg.get("corpus_scope") is not None:
        scope = CS.resolve_scope(conn, catalog, inp, opts, config=cfg.get("corpus_scope") if isinstance(cfg.get("corpus_scope"), dict) else {},
                                 corpus_view=corpus_view, seed=given)
        if scope["origin"] == "default":
            opts["corpus_ids"] = list(scope["corpus_ids"])
        receipt["corpus_scope"] = scope
    if cfg.get("corpus_seed") is not None:
        if given:
            receipt["seed"] = {"field": field, "origin": "user", "text": given}      # the requester's input stays exactly as sent
        else:
            corpora = list(opts.get("corpus_ids") or inp.get("corpus_ids") or [])
            if not corpora:
                raise CS.StartRefused("SEED_UNAVAILABLE", "no seed was given and no corpus is in scope to derive one from",
                                      "give a seed (a problem, an audience or a situation) or name the corpora to research")
            derived = CS.corpus_seed(conn, catalog, corpora)
            inp[field], inp[f"{field}_origin"] = derived["seed"], "corpus"
            receipt["seed"] = {"field": field, "origin": "corpus", "text": derived["seed"], "lineage": derived["lineage"]}
    opts["start_receipt"] = receipt
    return inp, opts, receipt


def _seed_check(m: Manifest, run_id: str, inp: dict[str, Any], field: str, check: dict[str, Any]) -> dict[str, Any]:
    """The entry step's start-time domain check of a requester's seed. A non-generative verdict refuses the start (typed, with the
    domain's plain hint); a domain refusal refuses it with the domain's code; a broken check never blocks a start — it is recorded."""
    cfg = {**check, "inputs": dict(check.get("inputs") or {field: f"input.{field}"})}
    req = DOMAIN.request(domain=str(cfg.get("domain") or ""), operation=str(cfg.get("operation") or ""), run_id=run_id,
                         step_id=f"{m.entry_step_id}:seed_check", run_input=inp, scope={"input": inp}, config=cfg)
    try:
        out = DOMAIN.run(str(cfg.get("domain") or ""), str(cfg.get("operation") or ""), req)
    except DOMAIN.DomainCrash as exc:
        return {"ran": False, "error": str(exc)[:500]}
    if out.get("gap"):
        raise CS.StartRefused(out["gap"]["code"], out["gap"]["message"])
    verdict = {k: v for k, v in (out.get("output") or {}).items() if not str(k).startswith("_")}
    if verdict.get("generative") is False:
        raise CS.StartRefused(str(verdict.get("reason_code") or "SEED_NOT_GENERATIVE"),
                              str(verdict.get("message") or "this seed names no problem, audience or situation the research can start from"),
                              str(verdict.get("hint") or "") or None)
    return {"ran": True, **{k: verdict[k] for k in ("generative", "reason_code", "signals") if k in verdict}}


def run_ref(conn, run_id: str) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    ref = {"run_id": run_id, "adapter_id": state.adapter_id, "adapter_version": meta["adapter_version"],
           "workflow_version": meta["workflow_version"], "created_at": _ts(meta["created_at"]), "status": state.status}
    assert_valid("adapter_run_ref", ref)
    return ref


def _ts(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return v.astimezone(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def status(conn, run_id: str, directory: Path | None = None) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    m = manifest_for(state.adapter_id, directory)
    return T.run_status_view(m, state, started_at=_ts(meta["created_at"]), updated_at=_ts(meta["updated_at"]),
                             terminal_at=_ts(meta["terminal_at"]), agent_identity=meta.get("agent_identity"),
                             identity={k: meta.get(k) for k in m.identity})          # B-57: the versions the RUN started under, as run_ref says


def next_step(conn, run_id: str, directory: Path | None = None) -> dict[str, Any]:
    """The step the connected agent must answer, or the run status when nothing is awaiting it. An awaiting step travels with a
    SIBLING `evidence` key (GOVERNED-CONVERGENCE-V1 TG2a): READABLE rows for exactly the ids in `step.context.evidence_refs`,
    hydrated from the run's stored step outputs. The AdapterStepV1 itself is unchanged — ids stay the citation contract."""
    st = status(conn, run_id, directory)
    if st["status"] in ("awaiting_agent", "awaiting_harness"):
        row = store.current_step(conn, run_id)
        if row and row["status"] == "issued":
            out = {"kind": "step", "step": row["step"], "status": st, "evidence": _readable_evidence(conn, run_id, row["step"])}
            materials = _materials(conn, run_id, row["step"], directory)
            if materials is not None:
                out["materials"] = materials
            out.update(_beside(conn, run_id, row, directory))
            rej = row.get("receipt") if isinstance(row.get("receipt"), dict) else None
            if rej and rej.get("status") == "rejected":
                # F2: the open step's last refusal (a schema, citation or LAW verdict) stays readable beside it — an agent that lost the 422
                # still sees exactly what to fix
                out["last_rejection"] = {"errors": list((rej.get("validation") or {}).get("errors") or [])[:40], "at": rej.get("ended_at")}
            return out
    return {"kind": "status", "status": st}


#: the reply's own keys: a manifest's `config.beside` may never name one
RESERVED_BESIDE = frozenset({"kind", "step", "status", "evidence", "materials", "last_rejection"})
BESIDE_MAX_BYTES = 800_000


def _beside(conn, run_id: str, row: dict[str, Any], directory: Path | None) -> dict[str, Any]:
    """PRODUCT-SEARCH-E2E: SIBLING keys beside an issued step, named by its manifest (`config.beside`: name -> a dotted path, or a list
    of paths of which the first present wins, over `outputs.` / `input.` / `prefetch.` — the host prefetch stored on the issued row).
    How a research step is run on the user's machine (`agent_reach`, computed by the adapter's DOMAIN from its own data) or a draft the
    host built (`supplier_draft`) travels here — never inside the AdapterStepV1, which stays source-neutral and unchanged. Nothing here
    is evidence. Reads stored state only; a failure is SAID, never raised."""
    try:
        state = store.load_run(conn, run_id)[0]
        beside = (manifest_for(state.adapter_id, directory).step(row["step"]["step_id"]).get("config") or {}).get("beside")
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(beside, dict) or not beside:
        return {}
    try:
        prefetch = (row.get("output") or {}).get(PREFETCH_KEY) if isinstance(row.get("output"), dict) else None
        scope = {"outputs": state.outputs, "input": state.input, "prefetch": prefetch if isinstance(prefetch, dict) else {}}
        out: dict[str, Any] = {}
        room, too_large = BESIDE_MAX_BYTES, []
        for name, paths in beside.items():
            if name in RESERVED_BESIDE:
                continue
            for path in (paths if isinstance(paths, list) else [paths]):
                val = T._lookup(str(path), scope)
                if val is None:
                    continue
                size = len(json.dumps(val, ensure_ascii=False, default=str).encode())
                if size > room:
                    too_large.append(name)
                else:
                    room -= size
                    out[name] = val
                break
        if too_large:
            out["beside_too_large"] = too_large
        return out
    except Exception as exc:  # noqa: BLE001 — never let a sibling key take adapter_next down
        return {"beside_error": f"{type(exc).__name__}: {exc}"[:500]}


#: the most a step's `materials` may weigh on the wire (the agent still gets its step when a value does not fit — and is told which)
MATERIALS_MAX_BYTES = 400_000


def _materials(conn, run_id: str, step: dict[str, Any], directory: Path | None) -> dict[str, Any] | None:
    """ADR-0020 addendum: an agent-answered step may be SHOWN selected prior step outputs. The manifest names them
    (`config.show`: name -> dotted path over `outputs` / `input` / `semantics`); they travel as a SIBLING key of the step, exactly
    like `evidence` — the AdapterStepV1 contract and the citation rules are unchanged, and nothing here is evidence. `semantics` is
    the DERIVED OpportunitySemanticViewV1 (semantic_view.py): the ledger's newest revisions joined by id to the run's own outputs —
    built only when a path asks for it. A manifest without `config.show` yields no key at all. Reads stored state only; a failure
    is SAID, never raised."""
    try:                                   # OPT-IN FIRST: if this step's manifest did not ask for materials — or that cannot even be determined — there is NO key
        loaded = store.load_run(conn, run_id)
        state = loaded[0] if loaded else None
        show = (manifest_for(state.adapter_id, directory).step(step["step_id"]).get("config") or {}).get("show") if state else None
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(show, dict) or not show:
        return None
    try:
        scope = {"outputs": state.outputs, "input": state.input}
        if any(str(d).split(".", 1)[0] == "semantics" for d in show.values()):
            scope["semantics"] = _semantics(conn, run_id, state, manifest_for(state.adapter_id, directory))
        values: dict[str, Any] = {}
        missing, too_large, room = [], [], MATERIALS_MAX_BYTES
        for name, dotted in show.items():
            val = T._lookup(str(dotted), scope)
            if val is None:
                missing.append(name)
                continue
            size = len(json.dumps(val, ensure_ascii=False, default=str).encode())
            if size > room:
                too_large.append(name)
                continue
            room -= size
            values[name] = val
        return {"values": values, "missing": missing, "too_large": too_large, "authority": "PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence"}
    except Exception as exc:  # noqa: BLE001 — never let the readable view take adapter_next down
        return {"values": {}, "missing": [], "too_large": [], "error": f"{type(exc).__name__}: {exc}"[:500]}


def _semantics(conn, run_id: str, state: RunState, m: Manifest | None = None) -> dict[str, Any]:
    """OpportunitySemanticViewV1 for the run as it stands NOW: a read of the ledger, the outputs and the stored steps. Never stored.
    `research_gaps` = every hypothesis's open gaps from every legitimate source, each owned and stably identified (research_gaps.py)."""
    stored = [{"step_id": s["step_id"], "sequence": s["sequence"], "output": s.get("output")} for s in store.list_steps(conn, run_id)]
    current = store.current_hypotheses(conn, run_id)
    scope = SV.scope(SV.build(current, state.outputs, order=state.output_order, step_outputs=stored, run_id=run_id), friction_family_ids=_friction_family_ids(state))
    roles = list(((m.raw if m else {}) or {}).get("evidence_roles") or [])
    scope["research_gaps"] = RG.harvest(current, state.outputs, order=state.output_order,
                                        default_role="behavior" if "behavior" in roles or not roles else roles[0])
    return scope


def _friction_family_ids(state: RunState) -> list[str]:
    """Registry friction-family ids this run may name as a structured candidate: the ids Trail's registry projection returned as
    `friction_primitive` priors (their `label` after ADR-069 is the family id). Nothing else — never a guess from prose."""
    out: list[str] = []
    for p in _collect_lists(state, "priors"):
        if isinstance(p, dict) and p.get("prior_role") == "friction_primitive" and p.get("label"):
            out.append(str(p["label"]))
    return sorted(set(out))


def _wants_semantics(spec: dict[str, Any]) -> bool:
    """An automatic step opts in by naming a `context.semantics…` path anywhere in its `config` (a DOMAIN_OPERATION input, or an
    EXTERNAL_OPERATION's `gaps_from`)."""
    def walk(v: Any) -> bool:
        if isinstance(v, str):
            return v.startswith("context.semantics")
        if isinstance(v, dict):
            return any(walk(x) for x in v.values())
        return isinstance(v, list) and any(walk(x) for x in v)
    return walk(spec.get("config") or {})


def _readable_evidence(conn, run_id: str, step: dict[str, Any]) -> dict[str, Any]:
    """Hydration reads stored JSON only; if it ever fails the agent still gets its step, and the failure is SAID, not hidden."""
    try:
        stored = [{"step_id": s["step_id"], "sequence": s["sequence"], "output": s.get("output")} for s in store.list_steps(conn, run_id)]
        return EB.hydrate((step.get("context") or {}).get("evidence_refs") or [], stored)
    except Exception as exc:  # noqa: BLE001 — never let the readable view take adapter_next down
        return {"rows": [], "receipts": [], "error": f"{type(exc).__name__}: {exc}"[:500]}


def submit(conn, run_id: str, submission: dict[str, Any], directory: Path | None = None) -> dict[str, Any]:
    """Validate and accept an AGENT_REASON submission; the run returns to `running` for the worker. Raises SubmissionRejected."""
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    m = manifest_for(state.adapter_id, directory)
    row = store.current_step(conn, run_id)
    if not row:
        raise SubmissionRejected(["no step has been issued"])
    step = row["step"]
    sub = {**submission, "run_id": run_id}
    sub.setdefault("submitted_at", now_iso())
    sub.setdefault("submission_hash", stable_hash(submission.get("payload")))
    started = now_iso()
    try:
        try:
            new_state = T.accept_submission(m, state, step, sub)
        except ManifestError as exc:
            if isinstance(exc, ManifestInvalid):
                raise
            # bug hunt B-57: a redeploy renamed or removed the step this run awaits; nothing can accept an answer for it. Refused, typed,
            # and the run stays parked (a rollback of the deploy resumes it; cancel ends it)
            raise SubmissionRejected([f"MANIFEST_VERSION_UNAVAILABLE: {_drift(exc, m, meta)}"]) from None
    except SubmissionRejected as exc:
        receipt = _receipt(step, "rejected", started, evidence_ids=[], model=sub.get("submitted_by", {}).get("model"),
                           validation={"ok": False, "errors": exc.errors})
        # the step stays ISSUED (the agent may retry); the rejection is receipted on the row
        store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)
        _touch(conn, run_id)
        raise
    who = sub.get("submitted_by", {}).get("model") or sub.get("submitted_by", {}).get("agent_identity")
    if step["step_type"] == "AGENT_REASON":
        # F2: the law that follows this reasoning step runs NOW, on the submitted payload, so the agent gets the law's verdict in the
        # submit response (a K_situations shape error waited 1024 s for the worker to re-issue the step). Same law, same inputs, same
        # repair budget: a verdict the branch would route back to this very step is refused here and counts one repair loop
        law_errors = _law_at_submit(conn, run_id, m, state, new_state, step)
        if law_errors:
            receipt = _receipt(step, "rejected", started, evidence_ids=[], model=who, validation={"ok": False, "errors": law_errors})
            store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)
            store.save_state(conn, T.replace(state, branch_loops=state.branch_loops + 1))
            raise SubmissionRejected(law_errors)
    if step["step_type"] == "HARNESS_ACTION":
        # a HarnessResearchReceiptV1: provenance recorded, nothing admitted yet (TrailSignal admission is the next automatic step)
        rec = dict(sub["payload"])
        too_large = _receipt_too_large(conn, run_id, state, m, step, rec)
        if too_large:
            receipt = _receipt(step, "rejected", started, evidence_ids=[], model=rec.get("harness_id") or who, validation={"ok": False, "errors": too_large})
            store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)      # the step stays open for a smaller receipt
            _touch(conn, run_id)
            raise SubmissionRejected(too_large)
        rhash = stable_hash(rec)
        store.record_receipt(conn, step["harness_action"]["action_id"], rec, rhash)
        output = {**rec, "_harness_action_id": step["harness_action"]["action_id"], "_receipt_hash": rhash}
        pre = (row.get("output") or {}).get(PREFETCH_KEY) if isinstance(row.get("output"), dict) else None
        if isinstance(pre, dict) and pre.get("summary") is not None:
            output["_host_prefetch"] = pre["summary"]            # what the host looked up before the step (lineage; never sent to Trail)
        new_state = T.replace(new_state, outputs={**new_state.outputs, step["step_id"]: output})   # later steps see the bound receipt
        receipt = _receipt(step, "accepted", started, evidence_ids=[], model=rec.get("harness_id") or who, validation={"ok": True, "errors": []})
        receipt["harness_receipt_hash"] = rhash
        receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
        store.finish_step(conn, run_id, row["sequence"], status="accepted", receipt=receipt, output=output, submission=sub)
        store.save_state(conn, new_state)
        return status(conn, run_id, directory)
    # reference §9.2: a research gap belongs to exactly one LIVE hypothesis — refused here, typed, so Trail never has to guess an owner;
    # and (bug hunt B-22) its role must be one Trail's gap compiler accepts, or the next Trail step ends the run
    gap_errors = RG.unowned_gap_errors(sub["payload"], [h for h, s_ in store.current_hypotheses(conn, run_id).items() if s_["status"] not in H.ABSORBED_STATUSES]) \
        + RG.gap_wire_errors(sub["payload"])
    if gap_errors:
        receipt = _receipt(step, "rejected", started, evidence_ids=[], model=who, validation={"ok": False, "errors": gap_errors})
        store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)
        _touch(conn, run_id)
        raise SubmissionRejected(gap_errors)
    # θ ledger: generated hypotheses and/or proposed transitions inside a reasoning payload become durable state in the SAME unit
    output = dict(sub["payload"])
    transition_ids: list[str] = []
    try:
        output, transition_ids = _apply_theta(conn, run_id, step, m, state, output, started)
    except HypothesisRejected as exc:
        errors = ["hypotheses: " + e for e in exc.errors]
        receipt = _receipt(step, "rejected", started, evidence_ids=[], model=who, validation={"ok": False, "errors": errors})
        store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)
        _touch(conn, run_id)
        raise SubmissionRejected(errors) from None
    new_state = T.replace(new_state, outputs={**new_state.outputs, step["step_id"]: output})       # payload + ledger ids
    receipt = _receipt(step, "accepted", started, evidence_ids=sorted(_cited(sub["payload"])), model=who, validation={"ok": True, "errors": []})
    if transition_ids:
        receipt["hypothesis_transition_ids"] = transition_ids
        receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    store.finish_step(conn, run_id, row["sequence"], status="accepted", receipt=receipt, output=output, submission=sub)
    store.save_state(conn, new_state)
    return status(conn, run_id, directory)


def _touch(conn, run_id: str) -> None:
    """A refused submission is agent activity: the run is not idle (F8). A store without the call (an older double) is left alone."""
    fn = getattr(store, "touch_run", None)
    if callable(fn):
        fn(conn, run_id)


#: a law verdict's error lists, in the order the agent should read them (the domain laws' own output keys)
LAW_ERROR_KEYS = ("errors", "bridge_errors", "portfolio_errors", "anchor_errors")


def _law_at_submit(conn, run_id: str, m: Manifest, state: RunState, accepted: RunState, step: dict[str, Any]) -> list[str] | None:
    """F2 (opt-in per reasoning step: `config.law_at_submit`). The step's `next` must be a DOMAIN_OPERATION law and the law's `next` a
    BRANCH. The law runs on the run as it WOULD stand with this payload accepted (the same issued step, the same selected inputs, the
    same domain code the worker runs) and the branch is resolved on the result. If the branch would return the run to THIS step (a
    failed law with repair budget left), the errors are returned: the submission is refused now and the step stays open. Anything else
    — the law passes, routes elsewhere (a spent budget -> the honest refusal; too few hypotheses -> generation), refuses typed, or cannot
    run — is accepted and the worker runs the law exactly as before."""
    spec = m.step(step["step_id"])
    if not (spec.get("config") or {}).get("law_at_submit"):
        return None
    law_id = spec.get("next")
    law = m.steps.get(law_id) if law_id else None
    route_id = (law or {}).get("next")
    route = m.steps.get(route_id) if route_id else None
    if not law or law.get("type") != "DOMAIN_OPERATION" or not route or route.get("type") != "BRANCH":
        return None
    hyps = store.current_hypotheses(conn, run_id)
    try:
        st_law, law_step = T.issue_step(m, accepted, issued_at=now_iso(), evidence_refs=[], inputs=accepted.input, admitted_evidence_ids=[],
                                        hypotheses=H.context_view(hyps), registry_snapshot=_registry_snapshot(accepted))
    except (BudgetExhausted, ContractViolation, RuntimeError):
        return None
    if _wants_semantics(law):
        law_step = {**law_step, "context": {**(law_step.get("context") or {}), "semantics": _semantics(conn, run_id, st_law, m)}}
    cfg = law.get("config") or {}
    scope = {"input": st_law.input, "options": st_law.options, "outputs": st_law.outputs, "context": law_step.get("context") or {}}
    req = DOMAIN.request(domain=str(cfg.get("domain") or ""), operation=str(cfg.get("operation") or ""), run_id=run_id, step_id=law_id,
                         run_input=st_law.input, scope=scope, config=cfg)
    try:
        out = DOMAIN.run(str(cfg.get("domain") or ""), str(cfg.get("operation") or ""), req)
    except DOMAIN.DomainCrash:
        return None
    if out.get("gap") or not isinstance(out.get("output"), dict):
        return None
    st_route = T.replace(T.record_automatic_output(st_law, law_id, out["output"]), current_step_id=route_id)
    if T.next_step_id(m, st_route) != step["step_id"] or state.branch_loops + 1 > int(m.budgets.get("max_branch_loops", 10**9)):
        return None
    errors = [str(e) for k in LAW_ERROR_KEYS for e in (out["output"].get(k) or []) if isinstance(out["output"].get(k), list)]
    head = f"LAW_UNSATISFIED ({law_id}): the domain law refused this answer (repair loop {state.branch_loops + 1}); fix exactly these and resubmit"
    return [head] + (errors or ["the law returned no error text"])[:40]


def _receipt_too_large(conn, run_id: str, state: RunState, m: Manifest, step: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    """bug hunt B-05, owner decision 2026-09-26 ("keep refusal for oversized receipts, not trimming"): when the next step admits this
    receipt, build the `evidence.admit` request it will send — the payload the worker assembles (its stage, the hypotheses it sends, every
    admitted id, the action id, the receipt) in the envelope of that step — and measure it by TrailSignal's own rule. Over the limit: the
    refusal names the size, the limit and how many observations must go, and the step stays open for a smaller receipt. [] = it fits."""
    nxt = m.step(step["step_id"]).get("next")
    admit = m.steps.get(nxt) if nxt else None
    if not admit or admit.get("type") != "EXTERNAL_OPERATION" or (admit.get("external") or {}).get("operation_kind") != "evidence.admit":
        return []
    cfg = admit.get("config") or {}
    hyps = H.context_view(store.current_hypotheses(conn, run_id))
    if cfg.get("hypotheses_from") == "context.semantics.trail":             # the closed extended wire, as the worker sends it
        hyps = list(_semantics(conn, run_id, state, m).get("trail") or []) or hyps
    payload = {"stage": cfg.get("stage"), "hypotheses": hyps, "admitted_evidence_ids": [r["id"] for r in store.admitted_evidence_refs(conn, run_id)],
               "action_id": step["harness_action"]["action_id"], "receipt": {k: v for k, v in receipt.items() if not str(k).startswith("_")}}
    over = trail_client.admission_overflow(payload, key=trail_client.identifier(run_id, nxt, str(state.sequence + 1)), run_ref=run_id,
                                           registry_snapshot_id=(_registry_snapshot(state) or {}).get("snapshot_id"))
    if not over:
        return []
    fit = over["observations_that_fit"]
    keep = (f"keep at most {fit} of its {over['observations']} observations (drop at least {over['observations'] - fit}, with the sources "
            "only they cite)" if fit is not None else "cite fewer sources and merge repeated limitations")
    message = (f"RECEIPT_TOO_LARGE: TrailSignal's admission of this receipt would be a {over['bytes']}-byte request and its limit is "
               f"{over['limit_bytes']} bytes: {keep}, then resubmit (nothing is trimmed for you)")
    return [message]


def _apply_theta(conn, run_id: str, step: dict[str, Any], m: Manifest, state: RunState, payload: dict[str, Any], now: str) -> tuple[dict[str, Any], list[str]]:
    """A reasoning payload may carry `hypotheses` (θ GENERATE) and/or `transitions` (θ REVISE/SPLIT proposals). They are validated by
    the pure ledger against the step's context and persisted as immutable revisions + transitions; the payload gains the ids."""
    out = dict(payload)
    tids: list[str] = []
    max_h = int(m.budgets.get("max_hypotheses", 8))
    snapshot = _registry_snapshot(state)
    current = store.current_hypotheses(conn, run_id)
    # bug hunt B-48: all or nothing — both halves are validated before anything is written, so a refused submission (whose rejection
    # receipt the route now commits) never leaves generated hypotheses behind
    writes: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
    if isinstance(payload.get("hypotheses"), list) and step.get("theta_op") in (None, "generate_hypotheses", "split_hypotheses", "derive_mechanisms",
                                                                                "cross_map_frictions", "derive_physical_jobs", "derive_analogies", "generate_product_mechanisms") \
            and (step.get("cognitive_op") == "theta" or step.get("theta_op")):
        live_n = len([h for h in current.values() if h["status"] not in H.ABSORBED_STATUSES])
        limit = max(0, max_h - live_n) or 1
        step_cap = (m.step(step["step_id"]).get("config") or {}).get("max_live_hypotheses")
        if isinstance(step_cap, int) and not isinstance(step_cap, bool):
            # F2: a generation step may cap the LIVE ledger it leaves (the bridge portfolio's own bound): never a generation the next law
            # can only refuse as unreachable
            if step_cap - live_n < 1:
                raise HypothesisRejected([f"the ledger already holds {live_n} live hypotheses and this step allows at most {step_cap}: "
                                          "generate none"])
            limit = min(limit, step_cap - live_n)
        states, trs = H.generate(run_id, step, payload["hypotheses"], registry_snapshot_id=(snapshot or {}).get("snapshot_id"), recorded_at=now,
                                 max_hypotheses=limit,
                                 ordinal_base=len(current), known_origin_ids=SV.known_origin_ids(state.outputs, state.output_order))
        writes.append((states, trs))
        out["hypothesis_ids"] = [s_["hypothesis_id"] for s_ in states]
        tids += [t["transition_id"] for t in trs]
        current.update({s_["hypothesis_id"]: s_ for s_ in states})
    if isinstance(payload.get("transitions"), list) and payload["transitions"]:
        allowed = _allowed_causes(conn, run_id, step, current)
        states, trs = H.apply(run_id, step, current, payload["transitions"], actor="theta", allowed_causes=allowed, recorded_at=now,
                              registry_snapshot_id=(snapshot or {}).get("snapshot_id"), max_hypotheses=max_h,
                              known_origin_ids=SV.known_origin_ids(state.outputs, state.output_order))
        writes.append((states, trs))
        out["hypothesis_transition_ids"] = [t["transition_id"] for t in trs]
        tids += out["hypothesis_transition_ids"]
    for states, trs in writes:
        store.insert_hypothesis_revisions(conn, states)
        store.insert_transitions(conn, trs)
    return out, tids


def _allowed_causes(conn, run_id: str, step: dict[str, Any], current: dict[str, dict[str, Any]]) -> dict[str, str]:
    allowed = {r["id"]: r["kind"] for r in step.get("context", {}).get("evidence_refs") or []}
    allowed.update({h: "hypothesis" for h in current})
    allowed.update({a: "evidence_admission" for a in store.admission_ids(conn, run_id)})
    allowed.update({r["id"]: "field_evidence" for r in store.admitted_evidence_refs(conn, run_id)})
    allowed.update({sid: "step_output" for sid in store.load_run(conn, run_id)[0].outputs})
    return allowed


def _registry_snapshot(state: RunState) -> dict[str, Any] | None:
    snap = _gather(state.outputs, "registry_snapshot", state.output_order)
    if isinstance(snap, dict) and snap.get("snapshot_id") and snap.get("content_hash"):
        return {"snapshot_id": str(snap["snapshot_id"]), "content_hash": str(snap["content_hash"])}
    return None


def _compile_harness_action(state: RunState, spec: dict[str, Any], step_id: str, sequence: int, hyps: dict[str, dict[str, Any]],
                            snapshot: dict[str, Any] | None, issued_at: str) -> dict[str, Any] | None:
    """HarnessActionV1 = the manifest's `harness` block (kind, roles, budget, independence, freshness) + the latest compiled research
    directive found in prior step outputs (`research_directive`: gaps, search intents, conditions, geography, language) + the live
    hypotheses + the registry snapshot. Without a directive there is nothing lawful to hand to the harness → None (typed gap)."""
    directive = _gather(state.outputs, "research_directive", state.output_order)
    if not isinstance(directive, dict) or not directive.get("search_intents") or not snapshot:
        return None
    hb = spec.get("harness") or {}
    live = [h for h, s_ in hyps.items() if s_["status"] not in H.ABSORBED_STATUSES] or list(directive.get("hypothesis_ids") or [])   # generation order (store), not hash order
    if not live:
        return None
    budget = {**{"max_queries": 20, "max_sources": 15, "max_observations": 60}, **(directive.get("budget") or {}), **(hb.get("budget") or {})}
    # the requester's limits reach the research (gap A-04): geography / language fill what TrailSignal left open, freshness_days only
    # TIGHTENS the window, and constraints / exclusions / category travel in the objective the harness reads
    limits = state.input if isinstance(state.input, dict) else {}
    windows = [d for d in (hb.get("freshness_max_age_days", (directive.get("freshness_requirement") or {}).get("max_age_days")), limits.get("freshness_days"))
               if isinstance(d, int) and not isinstance(d, bool) and d > 0]
    asked = [f"{label}: " + "; ".join(str(v) for v in (value if isinstance(value, list) else [value]) if str(v).strip())
             for label, value in (("constraints", limits.get("constraints")), ("exclude", limits.get("exclusions")), ("category", limits.get("category")))
             if value and (not isinstance(value, list) or any(str(v).strip() for v in value))]
    geography = directive.get("geography") or limits.get("geography")
    language = directive.get("language") or limits.get("language")
    objective = str(directive.get("objective") or spec.get("objective") or spec.get("title") or step_id)
    if asked:
        objective = f"{objective}\nThe requester's limits (honour them in every search): " + " · ".join(asked)
    action = {"action_id": "hact_" + hashlib.sha256(f"{state.run_id}:{step_id}:{sequence}".encode()).hexdigest()[:24], "run_id": state.run_id, "step_id": step_id,
              "action_kind": hb["action_kind"], "hypothesis_ids": live[:64], "objective": objective[:4000],
              "evidence_gaps": list(directive.get("evidence_gaps") or [])[:200], "search_intents": list(directive["search_intents"])[:100],
              "preferred_source_roles": list(hb.get("preferred_source_roles") or directive.get("preferred_source_roles") or [])[:50],
              "disallowed_source_roles": list(hb.get("disallowed_source_roles") or directive.get("disallowed_source_roles") or [])[:50],
              "freshness_requirement": {"max_age_days": min(windows) if windows else None,
                                        "policy_ref": (directive.get("freshness_requirement") or {}).get("policy_ref")},
              "geography": str(geography)[:200] if geography else None, "language": str(language)[:50] if language else None,
              "minimum_independent_sources": int(hb.get("minimum_independent_sources") or directive.get("minimum_independent_sources") or 1),
              "success_condition": str(directive.get("success_condition") or "the evidence gaps are answered by independent sources")[:2000],
              "falsification_condition": str(directive.get("falsification_condition") or "independent sources contradict the hypotheses")[:2000],
              "budget": budget, "registry_snapshot": snapshot, "issued_at": issued_at}
    return action


def cancel(conn, run_id: str, directory: Path | None = None,
           external_cancel: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Cancel the run (terminal, idempotent). If the current step holds a NON-terminal external operation and a cancel
    callable is supplied, it is invoked best-effort (its outcome or error is recorded on the receipt; cancel never blocks)."""
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    if state.terminal:
        return status(conn, run_id, directory)
    row = store.current_step(conn, run_id)
    ext = (row or {}).get("external_operation")
    if ext and ext.get("phase") != "TERMINAL" and external_cancel is not None:
        try:
            updated = external_cancel(ext)
            if updated:
                assert_valid("external_operation_receipt", updated)
                store.finish_step(conn, run_id, row["sequence"], status=row["status"], receipt=None, external=updated)
        except Exception as exc:  # noqa: BLE001 — best effort; the run still cancels
            ext2 = {**ext, "failure": {"code": "EXTERNAL_CANCEL_FAILED", "message": f"{type(exc).__name__}: {exc}"[:2000]}}
            store.finish_step(conn, run_id, row["sequence"], status=row["status"], receipt=None, external=ext2)
    _close_open_step(conn, run_id, row, "RUN_CANCELLED: the run was cancelled while this step was open")
    store.save_state(conn, T.cancel_run(state))
    return status(conn, run_id, directory)


def _close_open_step(conn, run_id: str, row: dict[str, Any] | None, reason: str) -> None:
    """F8: a run that ends while a step is open (cancel, idle expiry) closes that step `skipped` with a receipt saying why — never a
    terminal run with an `issued` step left behind (5 such rows were found)."""
    if row and row.get("status") == "issued":
        store.finish_step(conn, run_id, row["sequence"], status="skipped",
                          receipt=_receipt(row["step"], "skipped", now_iso(), evidence_ids=[], model=None, validation={"ok": False, "errors": [reason]}))


#: F8: a run waiting on the connected agent with no activity this long ends with a typed gap (configurable; default 24 h)
IDLE_EXPIRY_S = int(os.environ.get("POLYMATH_ADAPTER_IDLE_EXPIRY_S", str(24 * 3600)))


def expire_idle(conn, *, idle_s: int | None = None, limit: int = 20) -> list[str]:
    """F8: every run waiting on the agent (awaiting_agent / awaiting_harness) with no activity for `idle_s` seconds ends typed —
    AGENT_IDLE_EXPIRED, naming the step it waited at — and its open step is closed. A run whose row another transaction holds is skipped
    (SKIP LOCKED) and seen again next time. Returns the run ids expired. Runs inside the caller's transaction."""
    bound = int(idle_s if idle_s is not None else IDLE_EXPIRY_S)
    finder = getattr(store, "idle_runs", None)
    if bound <= 0 or not callable(finder):
        return []
    expired = []
    for run_id in finder(conn, bound, limit):
        loaded = store.load_run(conn, run_id, for_update=True)
        if not loaded or loaded[0].status not in ("awaiting_agent", "awaiting_harness"):
            continue
        state = loaded[0]
        row = store.current_step(conn, run_id)
        message = (f"no answer from the connected agent for {bound} s while the run was {state.status} at {state.current_step_id}: the run "
                   "ended; start a new run to continue (an idle run never holds its place forever)")
        _close_open_step(conn, run_id, row, f"AGENT_IDLE_EXPIRED: {message}")
        store.save_state(conn, T.terminal_gap(state, "AGENT_IDLE_EXPIRED", message, step_id=state.current_step_id))
        expired.append(run_id)
    return expired


def result(conn, run_id: str) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    if not state.terminal:
        raise NotTerminal(state.status)
    res = store.load_result(conn, run_id)
    if res is None:                       # cancelled / failed / gap before COMPILE_RESULT: synthesise the terminal result
        # bug hunt B-29 / B-14: from what the run DID produce (the terminal step's includes over its step outputs), never an empty
        # output beside a lineage that counts admitted evidence; the status and the typed gap stay what they are
        res = _compile_result(conn, run_id, state, manifest_for(state.adapter_id), output=None, persist=True)
    return res


# ─────────────────────────────────────────────────────────── the step engine (worker)
def advance(conn, run_id: str, executors: dict[str, Executor], *, max_steps: int | None = None,
            directory: Path | None = None) -> RunState:
    """Drive a RUNNING run forward on ONE connection: issue the next step; execute automatic steps through `executors`; stop at an
    AGENT_REASON step (awaiting_agent), at COMPILE_RESULT (completed + result), at a typed gap, or after `max_steps`. Every step is the
    same three phases the worker runs in SEPARATE transactions (F7): `prepare` (issue / find the step, under the run's row lock) →
    `execute` (the executor; here inline) → `apply` (record the outcome). A record that would break its OWN contract (the step to issue,
    a receipt, a result) never leaves this function: the unit ends with a durable typed failure naming the contract, the fields and the
    rules (external review M1-04; bug hunt B-02)."""
    done = 0
    while True:
        unit = prepare(conn, run_id, executors, directory=directory)
        if unit.kind == "done":
            return unit.state
        if unit.kind == "prefetch":
            return apply_prefetch(conn, run_id, unit, run_prefetch(executors, unit), directory=directory)
        outcome = execute(executors, unit)
        state = apply(conn, run_id, unit, outcome, directory=directory)
        ok = outcome.get("ok") or {}
        if "raised" in outcome or ok.get("pending") or ok.get("gap") or state.status != "running":
            return state
        done += 1
        if max_steps is not None and done >= max_steps:
            return state


class LeaseLost(RuntimeError):
    """The worker no longer holds the run's lease (it expired while a step executed outside any transaction, and another worker may
    have claimed the run): the outcome is never applied."""


@dataclass
class Unit:
    """One step unit between its phases (F7). `kind`: `done` (nothing to execute: the run waits, completed, ended or could not go on),
    `execute` (an issued automatic step and its executor's inputs) or `prefetch` (a HARNESS_ACTION about to be issued whose manifest
    asks the host for lookups first). Never stored; the database row is the authority — `apply` re-checks it."""
    kind: str
    state: RunState
    step: dict[str, Any] | None = None
    started: str = ""
    manifest: Manifest | None = None
    spec: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    owner_principal_id: str | None = None


def prepare(conn, run_id: str, executors: dict[str, Any], *, directory: Path | None = None) -> Unit:
    """Phase 1, under the run's row lock: issue the next step (or find the issued one) and say what must run outside the transaction.
    Contract violations and manifest drift end the run typed, exactly as `advance` always did."""
    try:
        return _prepare(conn, run_id, executors, directory)
    except ContractViolation as exc:
        return Unit("done", fail_run(conn, run_id, code="STEP_CONTRACT_VIOLATION", message=_violation_reason(exc), directory=directory))
    except ManifestInvalid:
        raise
    except (ManifestError, UnknownAdapter) as exc:
        return Unit("done", _manifest_gap(conn, run_id, exc, directory))


def execute(executors: dict[str, Any], unit: Unit) -> dict[str, Any]:
    """Phase 2, OUTSIDE any transaction: the step's executor. -> {"ok": outcome} or {"raised": "Type: message"} (a step failure the
    `apply` phase records typed). LeaseLost propagates: the caller drops the unit."""
    executor = executors.get(unit.step["step_type"])
    try:
        return {"ok": executor(unit.step, unit.state, unit.manifest or manifest_for(unit.state.adapter_id))}
    except LeaseLost:
        raise
    except Exception as exc:  # noqa: BLE001 — a step failure is a typed run failure, never a silent skip
        return {"raised": f"{type(exc).__name__}: {exc}"[:2000]}


def apply(conn, run_id: str, unit: Unit, outcome: dict[str, Any], *, directory: Path | None = None) -> RunState:
    """Phase 3, under the run's row lock again: record the outcome — only if the run still stands at THIS issued step (a cancel, an
    idle expiry or another worker may have moved it meanwhile: the outcome is then discarded, never applied to a different state)."""
    try:
        return _apply(conn, run_id, unit, outcome, directory)
    except ContractViolation as exc:
        return fail_run(conn, run_id, code="STEP_CONTRACT_VIOLATION", message=_violation_reason(exc), directory=directory)
    except ManifestInvalid:
        raise
    except (ManifestError, UnknownAdapter) as exc:
        return _manifest_gap(conn, run_id, exc, directory)


def _drift(exc: Exception, m: Manifest | None, meta: dict[str, Any]) -> str:
    loaded = f"the loaded manifest is {m.adapter_version}" if m is not None else "no manifest of that adapter is admitted now"
    return f"{exc}: this run started under {meta.get('adapter_id')} {meta.get('adapter_version')}; {loaded}"


def _manifest_gap(conn, run_id: str, exc: Exception, directory: Path | None) -> RunState:
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    if state.terminal:
        return state
    try:
        m: Manifest | None = manifest_for(state.adapter_id, directory)
    except UnknownAdapter:
        m = None
    message = _drift(exc, m, meta)
    row = store.current_step(conn, run_id)
    if row and row["status"] == "issued" and row["step"].get("step_type") not in AGENT_ANSWERED_STEP_TYPES:
        store.finish_step(conn, run_id, row["sequence"], status="skipped",
                          receipt=_receipt(row["step"], "skipped", now_iso(), evidence_ids=[], model=None, validation={"ok": False, "errors": [message]}))
    state = T.terminal_gap(state, "MANIFEST_VERSION_UNAVAILABLE", message, step_id=state.current_step_id)
    store.save_state(conn, state)
    return state


def _violation_reason(exc: ContractViolation) -> str:
    """Which contract, which fields, which rules — each validator message bounded so an oversized value is never echoed whole."""
    more = f" (+{len(exc.errors) - 5} more)" if len(exc.errors) > 5 else ""
    return f"{exc.name}: " + "; ".join(bounded_text(e, 300) for e in exc.errors[:5]) + more


def fail_run(conn, run_id: str, *, code: str, message: str, directory: Path | None = None) -> RunState:
    """A DURABLE typed failure for a run whose step could not complete as one lawful unit (M1-04; bug hunt B-02 / B-06): an issued step
    is closed `failed` with its receipt, the run ends `failed` with the reason and the step it concerns (the issued step, else the one
    that could not be issued). A terminal run is left untouched. Runs inside the caller's transaction."""
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    if state.terminal:
        return state
    row = store.current_step(conn, run_id)
    issued = row if row and row["status"] == "issued" else None
    step_id = issued["step_id"] if issued else None
    if step_id is None:
        try:
            step_id = T.next_step_id(manifest_for(state.adapter_id, directory), state)
        except Exception:  # noqa: BLE001 — the manifest itself may be what failed (a redeploy renamed the step); name where the run stands
            step_id = state.current_step_id
    failure = {"code": code, "message": bounded_text(message, FAILURE_MESSAGE_MAX), **({"step_id": step_id} if step_id else {})}
    if issued:
        store.finish_step(conn, run_id, issued["sequence"], status="failed",
                          receipt=_receipt(issued["step"], "failed", now_iso(), evidence_ids=[], model=None,
                                           validation={"ok": False, "errors": [failure["message"]]}, failure=failure))
    state = T.replace(state, status="failed", failure=failure)
    store.save_state(conn, state)
    return state


def _prepare(conn, run_id: str, executors: dict[str, Any], directory: Path | None) -> Unit:
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    m = manifest_for(state.adapter_id, directory)
    if state.status != "running":
        return Unit("done", state)
    row = store.current_step(conn, run_id)
    if row and row["status"] == "issued":
        # an automatic step issued by a crashed worker (or before the executor ran outside the transaction), or a PENDING external
        # operation: re-execute it (idempotent) — a prior ExternalOperationReceiptV1 travels with the step so the executor polls
        step = dict(row["step"])
        if row.get("external_operation"):
            step["_external_receipt"] = row["external_operation"]
        if row.get("output"):
            step["_partial_output"] = row["output"]
    else:
        hyps = store.current_hypotheses(conn, run_id)
        snapshot = _registry_snapshot(state)
        sid = T.next_step_id(m, state)
        harness_action = None
        if sid and m.step(sid)["type"] == "HARNESS_ACTION":
            harness_action = _compile_harness_action(state, m.step(sid), sid, state.sequence + 1, hyps, snapshot, now_iso())
            if harness_action is None:
                state = T.terminal_gap(state, "HARNESS_DIRECTIVE_MISSING",
                                       f"{sid}: no compiled research directive, registry snapshot or live hypothesis to hand to the harness", step_id=sid)
                store.save_state(conn, state)
                return Unit("done", state)
            if _host_prefetch(m.step(sid)) and callable(executors.get(HOST_PREFETCH)):
                # PRODUCT-SEARCH-E2E: the host's own lookups run BEFORE the step is issued (outside the transaction), so the agent never
                # sees the step without what they produced (`apply_prefetch` issues it with the result beside it)
                return Unit("prefetch", state, spec=m.step(sid), action=harness_action, manifest=m,
                            owner_principal_id=store.run_owner(conn, run_id)[1])
        issued = _issue(conn, state, m, hyps, snapshot, harness_action)
        if isinstance(issued, RunState):
            return Unit("done", issued)
        state, step = issued
        if step["step_type"] in AGENT_ANSWERED_STEP_TYPES:
            return Unit("done", state)                       # the agent / harness answers through adapter_submit
    started = now_iso()
    if step["step_type"] == "COMPILE_RESULT":
        out = _compile_result(conn, run_id, state, m, output=None, persist=True, step=step)
        receipt = _receipt(step, "executed", started, evidence_ids=out["lineage"]["polymath_evidence_ids"], model=None,
                           validation={"ok": True, "errors": []})
        store.finish_step(conn, run_id, step["sequence"], status="executed", receipt=receipt, output={"result_hash": stable_hash(out)})
        state = T.record_automatic_output(state, step["step_id"], {"result_hash": stable_hash(out)})
        state = T.complete_run(state)
        store.save_state(conn, state)
        return Unit("done", state)
    if not callable(executors.get(step["step_type"])):
        state = T.terminal_gap(state, "STEP_TYPE_UNSUPPORTED", f"no executor for {step['step_type']}", step_id=step["step_id"])
        store.finish_step(conn, run_id, step["sequence"], status="skipped",
                          receipt=_receipt(step, "skipped", started, evidence_ids=[], model=None, validation={"ok": False, "errors": ["unsupported"]}))
        store.save_state(conn, state)
        return Unit("done", state)
    compiled_need = EB.domain_compiled_need(m.step(step["step_id"]).get("config"), state.outputs,
                                            [sid_ for sid_, spec_ in m.steps.items() if spec_.get("type") == "DOMAIN_OPERATION"])
    if compiled_need:
        step = {**step, "_compiled_need": compiled_need}       # in memory only; honoured by the boundary executor, from domain code only
    if _wants_semantics(m.step(step["step_id"])):
        # IN MEMORY ONLY: the stored AdapterStepV1 (schema-closed context, four-field hypotheses) is untouched, and so is every
        # Trail payload — `_payload_for` reads `context.hypotheses`. The executor's copy of the step gains the derived view.
        step = {**step, "context": {**(step.get("context") or {}), "semantics": _semantics(conn, run_id, state, m)}}
    if step["step_type"] in KNOWLEDGE_STEP_TYPES:
        gens = _corpus_generations(conn, state)
        if gens:
            step = {**step, "_corpus_generations": gens}         # in memory only: keys the run's evidence cache (F3)
    return Unit("execute", state, step=step, started=started, manifest=m)


#: the step types that ask Polymath's knowledge surface (F3: their calls are cached per run, keyed by the corpus generation)
KNOWLEDGE_STEP_TYPES = frozenset({"POLYMATH_RETRIEVE", "POLYMATH_GRAPH_EXPAND", "POLYMATH_COMPILE_PLAN"})


def _corpus_generations(conn, state: RunState) -> dict[str, str]:
    """corpus id -> what it serves now (store.corpus_generation). A corpus whose generation cannot be read is left out: its calls are
    never answered from the cache."""
    fn = getattr(store, "corpus_generation", None)
    ids = state.input.get("corpus_ids") or state.options.get("corpus_ids") or []
    out: dict[str, str] = {}
    for cid in [c for c in ids if isinstance(c, str) and c.strip()] if callable(fn) else []:
        try:
            gen = fn(conn, cid)
        except Exception:  # noqa: BLE001
            continue
        if gen:
            out[cid] = str(gen)
    return out


def _issue(conn, state: RunState, m: Manifest, hyps: dict[str, dict[str, Any]], snapshot: dict[str, Any] | None,
           harness_action: dict[str, Any] | None) -> tuple[RunState, dict[str, Any]] | RunState:
    """Issue the next step and persist it (step row, harness action, run state). A spent budget ends the run typed (-> the state)."""
    try:
        state2, step = T.issue_step(m, state, issued_at=now_iso(), evidence_refs=_context_refs(conn, state, m), inputs=state.input,
                                    admitted_evidence_ids=[r["id"] for r in store.admitted_evidence_refs(conn, state.run_id)],
                                    hypotheses=H.context_view(hyps), registry_snapshot=snapshot, harness_action=harness_action)
    except BudgetExhausted as exc:
        state = T.terminal_gap(state, "BUDGET_EXHAUSTED", str(exc), step_id=state.current_step_id)
        store.save_state(conn, state)
        return state
    store.insert_step(conn, step)
    if harness_action:
        store.insert_harness_action(conn, harness_action, step["sequence"])
    store.save_state(conn, state2)
    return state2, step


def _apply(conn, run_id: str, unit: Unit, result: dict[str, Any], directory: Path | None) -> RunState:
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    step, started = unit.step, unit.started
    row = store.current_step(conn, run_id)
    if state.status != "running" or not row or int(row["sequence"]) != int(step["sequence"]) or row["status"] != "issued":
        return state                                      # the run moved on meanwhile (cancelled, expired, re-claimed): discard
    m = manifest_for(state.adapter_id, directory)
    if "raised" in result:
        failure = {"code": "STEP_EXECUTOR_ERROR", "message": str(result["raised"])[:2000], "step_id": step["step_id"]}
        store.finish_step(conn, run_id, step["sequence"], status="failed",
                          receipt=_receipt(step, "failed", started, evidence_ids=[], model=None, validation={"ok": False, "errors": [failure["message"]]}, failure=failure))
        state = T.replace(state, status="failed", failure=failure)
        store.save_state(conn, state)
        return state
    outcome = result.get("ok") or {}
    if outcome.get("pending"):
        # EXTERNAL_OPERATION two-phase: the operation is submitted/polled but not terminal. Record its
        # ExternalOperationReceiptV1 on the ISSUED step and stop; the next claim re-executes this step, which
        # finds the receipt and polls again (idempotent by operation_id — never a second submit).
        ext = outcome.get("external")
        if ext:
            assert_valid("external_operation_receipt", ext)
        store.finish_step(conn, run_id, step["sequence"], status="issued", receipt=None, external=ext,
                          output=outcome.get("output"))          # composite progress survives the pause
        state = T.replace(state, status="running")
        store.save_state(conn, state)
        return state
    gap = outcome.get("gap")
    if gap:
        store.finish_step(conn, run_id, step["sequence"], status="skipped",
                          receipt=_receipt(step, "skipped", started, evidence_ids=[], model=None, validation={"ok": False, "errors": [gap["message"]]}, failure=None),
                          external=outcome.get("external"))
        state = T.terminal_gap(state, gap["code"], gap["message"], step_id=step["step_id"])
        store.save_state(conn, state)
        return state
    output = dict(outcome.get("output") or {})
    refs = list(outcome.get("evidence_refs") or [])
    if refs:
        output["_evidence_refs"] = refs
    # ADR-0019: an automatic step may carry TrailSignal's admission projection and/or φ verdicts; both become durable state
    # in this same unit, or the run ends with a typed gap — a verdict is never silently dropped
    gap = _apply_phi_outputs(conn, run_id, step, m, state, output, started)
    if gap:
        store.finish_step(conn, run_id, step["sequence"], status="skipped",
                          receipt=_receipt(step, "skipped", started, evidence_ids=[], model=None, validation={"ok": False, "errors": [gap["message"]]}),
                          external=outcome.get("external"), output=output)
        state = T.terminal_gap(state, gap["code"], gap["message"], step_id=step["step_id"])
        store.save_state(conn, state)
        return state
    receipt = _receipt(step, "executed", started, evidence_ids=[r["id"] for r in refs], model=None,
                       validation={"ok": True, "errors": []},
                       external_ids=[outcome["external"]["operation_id"]] if outcome.get("external") else [])
    if output.get("hypothesis_transition_ids"):
        receipt["hypothesis_transition_ids"] = list(output["hypothesis_transition_ids"])
        receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    if output.get("evidence_admission"):
        receipt["admission_id"] = output["evidence_admission"]["admission_id"]
        receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    store.finish_step(conn, run_id, step["sequence"], status="executed", receipt=receipt, output=output, external=outcome.get("external"))
    state = T.record_automatic_output(state, step["step_id"], output)
    store.save_state(conn, state)
    return state


# ─────────────────────────────────────────────────────────── host prefetch (PRODUCT-SEARCH-E2E: a supply step's host lookups)
#: the executors-dict key of the HOST PREFETCH hook (the worker supplies it; a caller without it issues research steps plainly)
HOST_PREFETCH = "HOST_PREFETCH"
#: where a prefetch result lives on the ISSUED step row's output (never an AdapterStepV1 field; `config.beside` reads it as `prefetch.`)
PREFETCH_KEY = "_prefetch"


def _host_prefetch(spec: dict[str, Any]) -> dict[str, Any] | None:
    cfg = (spec.get("config") or {}).get("host_prefetch")
    return cfg if isinstance(cfg, dict) and cfg.get("lookups") else None


def run_prefetch(executors: dict[str, Any], unit: Unit) -> dict[str, Any]:
    """Phase 2 of a prefetch unit, OUTSIDE any transaction: the manifest's lookups (`config.host_prefetch.lookups`, a dotted path to a
    list the domain compiled) through the caller's HOST_PREFETCH hook, which runs them with the run OWNER's principal and hands the
    results to the manifest's domain builder. A failure is SAID in the result, never raised: the step is issued either way."""
    cfg = _host_prefetch(unit.spec or {}) or {}
    lookups = T._lookup(str(cfg.get("lookups")), {"outputs": unit.state.outputs, "input": unit.state.input})
    lookups = [x for x in lookups if isinstance(x, dict)] if isinstance(lookups, list) else []
    try:
        return dict(executors[HOST_PREFETCH](unit, lookups, cfg) or {})
    except LeaseLost:
        raise
    except Exception as exc:  # noqa: BLE001 — the agent still gets its step; what failed is recorded beside it
        return {"error": f"{type(exc).__name__}: {exc}"[:1000], "lookups": len(lookups)}


def apply_prefetch(conn, run_id: str, unit: Unit, result: dict[str, Any], *, directory: Path | None = None) -> RunState:
    """Phase 3 of a prefetch unit: issue the HARNESS_ACTION exactly as `prepare` would have — only if the run still stands where the
    prefetch was planned (same sequence, still running, same compiled action) — with the result on the issued row."""
    try:
        loaded = store.load_run(conn, run_id, for_update=True)
        if not loaded:
            raise UnknownRun(run_id)
        state, _ = loaded
        if state.status != "running" or state.sequence != unit.state.sequence or state.current_step_id != unit.state.current_step_id:
            return state
        m = manifest_for(state.adapter_id, directory)
        hyps = store.current_hypotheses(conn, run_id)
        snapshot = _registry_snapshot(state)
        sid = T.next_step_id(m, state)
        action = _compile_harness_action(state, m.step(sid), sid, state.sequence + 1, hyps, snapshot, now_iso()) if sid else None
        if action is None or action["action_id"] != (unit.action or {}).get("action_id"):
            return state                                   # the next prepare compiles and issues it afresh
        issued = _issue(conn, state, m, hyps, snapshot, action)
        if isinstance(issued, RunState):
            return issued
        state, step = issued
        store.finish_step(conn, run_id, step["sequence"], status="issued", receipt=None, output={PREFETCH_KEY: result})
        return state
    except ContractViolation as exc:
        return fail_run(conn, run_id, code="STEP_CONTRACT_VIOLATION", message=_violation_reason(exc), directory=directory)
    except ManifestInvalid:
        raise
    except (ManifestError, UnknownAdapter) as exc:
        return _manifest_gap(conn, run_id, exc, directory)


# ─────────────────────────────────────────────────────────── helpers
def _cited(payload: Any) -> set[str]:
    return T._cited_ids(payload)


#: the step contract's own bound on `context.evidence_refs` (adapter_step.schema.json maxItems)
STEP_CONTEXT_MAX_REFS = 500


def _step_budget(state: RunState, m: Manifest | None) -> tuple[dict[str, int], int]:
    """(per-class display floors, cap) for the step about to be issued. Gap A-12: a step whose job is to cite across the WHOLE run (the
    final interpretation cites field evidence from three research stages) may widen its display (`config.context_budget`, manifest data:
    class -> floor), within the step contract's 500 refs. Every other step keeps the default floors."""
    budget, cap = dict(CONTEXT_BUDGET), MAX_CONTEXT_REFS
    if m is None:
        return budget, cap
    try:
        sid = T.next_step_id(m, state)
        asked = (m.step(sid).get("config") or {}).get("context_budget") if sid else None
    except Exception:  # noqa: BLE001 — a step that cannot be resolved keeps the default display
        asked = None
    if isinstance(asked, dict):
        budget = {c: max(0, int(asked.get(c, budget[c]))) for c in budget}
        cap = min(sum(budget.values()), STEP_CONTEXT_MAX_REFS)
    return budget, cap


def _fair_by_group(refs: list[dict[str, Any]], take: int, group_of: dict[str, str]) -> list[dict[str, Any]]:
    """`take` refs of `refs` (admitted order) shared EVENLY across admission groups — round-robin, newest admission first for the spare —
    so a later stage's admitted evidence (product reality, supply) is never crowded out of the display by the first stage's (gap A-12).
    Within the cap nothing changes; the result keeps admitted order."""
    if take >= len(refs):
        return list(refs)
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in refs:
        groups.setdefault(group_of.get(str(r["id"]), ""), []).append(r)
    order = list(reversed(list(groups)))                                # newest admission first
    chosen: set[str] = set()
    depth = 0
    while len(chosen) < take:
        progressed = False
        for g in order:
            if depth < len(groups[g]) and len(chosen) < take:
                chosen.add(str(groups[g][depth]["id"]))
                progressed = True
        if not progressed:
            break
        depth += 1
    return [r for r in refs if str(r["id"]) in chosen]


def _context_refs(conn, state: RunState, m: Manifest | None = None) -> list[dict[str, Any]]:
    """The DISPLAY context an issued step carries FOR CITATION, capped (MAX_CONTEXT_REFS, or the step's own `config.context_budget`):
    admitted field evidence and knowledge refs, balanced per class (reserved floors + deterministic spillover + stable order) so no class
    starves another, and field evidence shared across the run's admissions (A-12). This is NOT the gate-facing admitted set — the complete
    admitted_evidence_ids the qualify/score gates count over travel as their own context field (advance → issue_step), sourced from the
    store accumulator and never capped."""
    budget, cap = _step_budget(state, m)
    buckets: dict[str, list[dict[str, Any]]] = {c: [] for c in budget}
    seen: set[str] = set()

    def _add(ref: dict[str, Any]) -> None:
        rid = str(ref["id"])
        if rid in seen:
            return
        seen.add(rid)
        buckets[_context_class(str(ref.get("kind", "")))].append(ref)

    for ref in store.admitted_evidence_refs(conn, state.run_id):   # admitted field evidence for citation (ORDER BY admitted_at, evidence_id)
        _add(ref)
    for sid in state.output_order or tuple(state.outputs):
        for ref in (state.outputs.get(sid) or {}).get("_evidence_refs") or []:
            _add(ref)

    take = {c: min(len(buckets[c]), budget[c]) for c in budget}
    spare = cap - sum(take.values())
    for c in CONTEXT_CLASS_ORDER:
        if spare <= 0:
            break
        extra = min(spare, len(buckets[c]) - take[c])
        take[c] += extra
        spare -= extra
    # a LATER retrieval pass keeps a bounded share of each knowledge class (EB.reserve_recent): what a targeted retrieval returned
    # must stay CITABLE, or `hydrate` — which reads exactly these ids — can never make it readable
    passes = EB.knowledge_passes(state.outputs.get(sid) for sid in (state.output_order or tuple(state.outputs)))
    group_of: dict[str, str] = {}
    groups_of = getattr(store, "admitted_evidence_groups", None)
    if callable(groups_of) and len(buckets["field_evidence"]) > take["field_evidence"]:
        try:
            group_of = dict(groups_of(conn, state.run_id) or {})
        except Exception:  # noqa: BLE001 — no grouping known: the display keeps admitted order, as before A-12
            group_of = {}
    out: list[dict[str, Any]] = []
    for c in CONTEXT_CLASS_ORDER:
        out.extend(_fair_by_group(buckets[c], take[c], group_of) if c == "field_evidence" else EB.reserve_recent(buckets[c], take[c], passes))
    return out[:cap]


def _apply_phi_outputs(conn, run_id: str, step: dict[str, Any], m: Manifest, state: RunState, output: dict[str, Any], now: str) -> dict[str, Any] | None:
    """Admission projections (`evidence_admission`) and φ verdicts (`hypothesis_verdicts`) on an automatic step's output."""
    adm = output.get("evidence_admission")
    if adm is not None:
        errs = validate("evidence_admission", adm)
        if errs or adm.get("run_id") != run_id:
            return {"code": "ADMISSION_INVALID", "message": "; ".join(errs[:5]) or "admission run_id mismatch"}
        if store.harness_action_row(conn, adm["action_id"]) is None:
            return {"code": "ADMISSION_INVALID", "message": f"admission for unknown harness action {adm['action_id']}"}
        store.record_admission(conn, adm)
        output["_admitted_evidence_ids"] = [a["admitted_evidence_id"] for a in adm.get("admitted") or []]
    verdicts = output.get("hypothesis_verdicts")
    if verdicts:
        current = store.current_hypotheses(conn, run_id)
        allowed = _allowed_causes(conn, run_id, step, current)
        allowed.update({r["id"]: r["kind"] for r in output.get("_evidence_refs") or []})
        try:
            states, trs = H.apply(run_id, step, current, list(verdicts), actor="phi", allowed_causes=allowed, recorded_at=now,
                                  registry_snapshot_id=(_registry_snapshot(state) or {}).get("snapshot_id"), max_hypotheses=int(m.budgets.get("max_hypotheses", 8)))
        except HypothesisRejected as exc:
            return {"code": "PHI_VERDICT_INVALID", "message": "; ".join(exc.errors[:5])}
        store.insert_hypothesis_revisions(conn, states)
        store.insert_transitions(conn, trs)
        output["hypothesis_transition_ids"] = [t["transition_id"] for t in trs]
    return None


#: the receipt contract's own bounds (adapter_step_receipt: validation.errors[] maxLength 1000, failure.message maxLength 2000)
RECEIPT_ERROR_MAX, FAILURE_MESSAGE_MAX = 1000, 2000


def _receipt(step: dict[str, Any], status_: str, started: str, *, evidence_ids: list[str], model: str | None,
             validation: dict[str, Any], failure: dict[str, Any] | None = None, external_ids: list[str] | None = None) -> dict[str, Any]:
    # bug hunt B-02 / B-04: the reasons a receipt copies (a domain refusal up to 2000 chars, an executor error, a validator message that
    # echoes an oversized value) outgrew its 1000-char error bound, and the receipt's own assert escaped `advance`. The receipt keeps a
    # BOUNDED copy (head + tail, the elision counted); the full reason stays on the run's gap / failure and in the rejection's errors.
    validation = {**validation, "errors": [bounded_text(e, RECEIPT_ERROR_MAX) for e in validation.get("errors") or []]} if "errors" in validation else validation
    if failure is not None:
        failure = {**failure, "message": bounded_text(failure.get("message", ""), FAILURE_MESSAGE_MAX)}
    ended = now_iso()
    r = {"run_id": step["run_id"], "step_id": step["step_id"], "step_type": step["step_type"], "sequence": step["sequence"],
         "status": status_, "started_at": started, "ended_at": ended,
         "wall_ms": max(0, int((_dt.datetime.fromisoformat(ended.replace("Z", "+00:00")) - _dt.datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds() * 1000)),
         "evidence_ids": list(evidence_ids), "external_operation_ids": list(external_ids or []), "model_or_agent": model,
         "validation": validation, "failure": failure}
    r["receipt_hash"] = stable_hash(r)
    assert_valid("adapter_step_receipt", r)
    return r


def _gather(outputs: dict[str, Any], key: str, order: tuple[str, ...] = ()) -> Any:
    """First value named `key` found in step outputs, NEWEST accepted step first (top level, then one level down). `order` is the
    run's acceptance order — JSONB does not keep dict order, so callers pass `state.output_order`. A Trail operation's output that
    does not FILL `key` is skipped (gap A-15: runs stored before the fix carry every unfilled envelope field as [] or null)."""
    for sid in reversed(order or tuple(outputs)):
        out = outputs.get(sid) or {}
        if isinstance(out, dict):
            if key in out and trail_client.fills(out.get("operation_kind"), key):
                return out[key]
            for v in out.values():
                if isinstance(v, dict) and key in v:
                    return v[key]
    return None


def _ordered_step_outputs(state: RunState) -> list[Any]:
    """Step outputs in the run's authoritative acceptance order (JSONB does not preserve dict order; output_order is stored separately)."""
    return [state.outputs[sid] for sid in (state.output_order or tuple(state.outputs)) if sid in state.outputs]


def _collect_lists(state: RunState, key: str) -> list[Any]:
    found: list[Any] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key and isinstance(v, list):
                    found.extend(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    for out in _ordered_step_outputs(state):                      # acceptance order, never dict/JSONB iteration order
        walk(out)
    return found


def _compile_result(conn, run_id: str, state: RunState, m: Manifest, *, output: dict[str, Any] | None, persist: bool,
                    step: dict[str, Any] | None = None) -> dict[str, Any]:
    _, meta = store.load_run(conn, run_id)
    steps = store.list_steps(conn, run_id)
    include = list((step or {}).get("config", {}).get("include") or (m.step(m.terminal_step_id).get("config") or {}).get("include") or [])
    if output is None:
        output = {}
        for key in include:
            if isinstance(key, dict):
                # {"collect_all": <key>, "as": <output key>}: EVERY occurrence of a step-output key, in sequence order, read from the
                # stored steps (state.outputs keeps only the newest pass of a looped step; a plain include gathers only the newest).
                src = key.get("collect_all")
                vals = [s["output"][src] for s in steps if src and isinstance(s.get("output"), dict) and s["output"].get(src) is not None]
                if vals:
                    output[str(key.get("as") or src)] = vals
                continue
            if key == "lineage":
                continue
            if key == "hypothesis_semantics":
                # restoration reference §13: the dossier renders hypotheses from AUTHORITATIVE state, not from the four-field step view.
                # The result is the run's outcome document; it carries the DERIVED view as it stood at the end (every live and
                # absorbed hypothesis) — the ledger stays the record, nothing reads this back into the run.
                view = SV.build(store.current_hypotheses(conn, run_id), state.outputs, order=state.output_order, run_id=run_id, include_absorbed=True,
                                step_outputs=[{"step_id": s["step_id"], "sequence": s["sequence"], "output": s.get("output")} for s in steps])
                output[key] = view["hypotheses"]
                continue
            v = _gather(state.outputs, key, state.output_order)
            if v is not None:
                output[key] = v
    # bug hunt B-24: the lineage names EVERY knowledge ref the run produced — every pass of a looped step (state.outputs keeps only the
    # newest) and beyond the 200-ref display window (`_context_refs`, what a step shows) — and every knowledge id the ledger cites
    evidence_ids, query_ids, ext_ops = [], [], []
    for s in steps:
        for r in (s["output"].get("_evidence_refs") or []) if isinstance(s.get("output"), dict) else []:
            (query_ids if r.get("kind") == "query_receipt" else evidence_ids if r.get("kind") in KNOWLEDGE_KINDS else []).append(r["id"])
    actions = store.list_harness_actions(conn, run_id)
    hyps = store.current_hypotheses(conn, run_id)
    for h in hyps.values():
        for item in h.get("knowledge_support") or []:
            evidence_ids += [item[f] for f in ("chunk_id", "document_id", "graph_fact_id") if item.get(f)]
            query_ids += [item["retrieval_trace_id"]] if item.get("retrieval_trace_id") else []
    snapshots = sorted({str((_gather({sid: o}, "registry_snapshot") or {}).get("snapshot_id")) for sid, o in state.outputs.items()
                        if isinstance(_gather({sid: o}, "registry_snapshot"), dict)} - {"None"})
    score_ids = [str(x) for x in _collect_lists(state, "trail_score_record_ids") if isinstance(x, str)]
    ts = _gather(state.outputs, "trail_score", state.output_order)
    if isinstance(ts, dict) and ts.get("record_id"):
        score_ids.append(str(ts["record_id"]))
    for s in steps:
        e = s.get("external_operation")
        if e:
            ext_ops.append({"external_system": e["external_system"], "operation_kind": e.get("operation_kind"), "operation_id": e["operation_id"],
                            "record_ids": list(e.get("record_ids") or [])})
    # composite steps (e.g. batch acquire + per-artifact extraction) report their sub-operations on the step output
    for out in _ordered_step_outputs(state):                      # external-operation lineage in acceptance order
        for e in (out or {}).get("_external_operations") or []:
            if e.get("operation_id") and e["operation_id"] not in {x["operation_id"] for x in ext_ops}:
                ext_ops.append({"external_system": e.get("external_system", "trailsignal"), "operation_kind": e.get("operation_kind"),
                                "operation_id": e["operation_id"], "record_ids": list(e.get("record_ids") or [])})
    terminal_status = {"completed": "completed", "terminal_gap": "terminal_gap", "cancelled": "cancelled", "failed": "failed"}.get(state.status, "completed")
    res = {"run_id": run_id, **m.identity, "status": terminal_status, "started_at": _ts(meta["created_at"]),
           "terminal_at": _ts(meta["terminal_at"]) or now_iso(), "output": output,
           "lineage": {"polymath_evidence_ids": sorted(set(evidence_ids)), "query_receipt_ids": sorted(set(query_ids)),
                       "step_receipt_hashes": [s["receipt"]["receipt_hash"] for s in steps if s.get("receipt")],
                       "external_operations": ext_ops,
                       "hypothesis_ids": sorted(hyps), "admitted_evidence_ids": sorted(r["id"] for r in store.admitted_evidence_refs(conn, run_id)),
                       "harness_action_ids": [a["action_id"] for a in actions],
                       "harness_ids": sorted({(a["receipt"] or {}).get("harness_id") for a in actions if a.get("receipt")} - {None}),
                       "registry_snapshot_ids": snapshots, "trail_score_record_ids": sorted(set(score_ids))},
           "contradictions": [c for c in _collect_lists(state, "contradictions") if isinstance(c, dict)],
           "unknowns": [({"about": u} if isinstance(u, str) else u) for u in _collect_lists(state, "unknowns")],
           "gap": state.gap, "agent_identity": meta.get("agent_identity")}
    assert_valid("adapter_result", res)
    if persist:
        store.insert_result(conn, run_id, res, stable_hash(res))
    return res
