"""Run/step state transitions for the cognitive-adapter runtime. Pure and deterministic: same (manifest, state, inputs)
=> same next step, same issued step dict, same acceptance verdict. Persistence is the caller's job (receipts/outbox)."""
from __future__ import annotations

import csv
import datetime as _dt
import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from .contracts import AGENT_ANSWERED_STEP_TYPES, AUTOMATIC_STEP_TYPES, ORIGIN_ID_FIELDS, PRIOR_EVIDENCE_KINDS, TERMINAL_RUN_STATUSES, assert_valid, bounded_text, schema, stable_hash, validate
from .harness_guide import FILES as _GUIDE_FILES, SOURCES_URI as _SOURCES_URI
from .manifest import Manifest


class SubmissionRejected(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


class BudgetExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class RunState:
    """The durable-in-Postgres part of a run, as the pure core sees it. Immutable; transitions return new states."""
    run_id: str
    adapter_id: str
    status: str = "created"
    current_step_id: str | None = None
    sequence: int = 0                       # steps issued so far (1-based sequence of the last issued step)
    steps_accepted: int = 0
    branch_loops: int = 0
    agent_reason_count: int = 0
    external_operation_count: int = 0
    harness_action_count: int = 0
    input: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)      # request_options (corpus scope, retrieval mode, …)
    outputs: dict[str, Any] = field(default_factory=dict)       # step_id -> accepted/executed output payload
    output_order: tuple[str, ...] = ()                         # step ids in acceptance order (JSONB drops dict order); newest last
    failure: dict[str, Any] | None = None
    gap: dict[str, Any] | None = None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_RUN_STATUSES


# ─────────────────────────────────────────────────────────── predicates (closed)
def _lookup(path: str, ctx: dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def evaluate_predicate(pred: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Closed predicate vocabulary over a dotted path into ``ctx``:
    exists · count_gte(n) · count_lt(n) · equals(value) · all_of(of) · any_of(of). Unknown op → False (never raises)."""
    op = pred.get("op")
    if op == "all_of":
        return all(evaluate_predicate(p, ctx) for p in pred.get("of") or [])
    if op == "any_of":
        return any(evaluate_predicate(p, ctx) for p in pred.get("of") or [])
    val = _lookup(str(pred.get("path", "")), ctx)
    if op == "exists":
        return val is not None
    if op == "equals":
        return val == pred.get("value")
    if op in ("count_gte", "count_lt"):
        n = int(pred.get("n", 0))
        count = len(val) if isinstance(val, (list, dict, str)) else (int(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else 0)
        return count >= n if op == "count_gte" else count < n
    return False


def _ctx(state: RunState) -> dict[str, Any]:
    return {"steps": {sid: {"output": out} for sid, out in state.outputs.items()},
            "run": {"branch_loops": state.branch_loops, "sequence": state.sequence, "steps_accepted": state.steps_accepted,
                    "agent_reason_count": state.agent_reason_count, "external_operation_count": state.external_operation_count},
            "input": state.input, "options": state.options}


# ─────────────────────────────────────────────────────────── navigation
def next_step_id(manifest: Manifest, state: RunState) -> str | None:
    """The step that follows ``state.current_step_id`` (or the entry step for a fresh run). A BRANCH step is resolved
    HERE: the first branch whose predicate holds wins, else its default ``next``; taking a branch counts a loop."""
    if state.current_step_id is None:
        return manifest.entry_step_id
    cur = manifest.step(state.current_step_id)
    if cur["type"] == "BRANCH":
        for b in cur.get("branches") or []:
            if evaluate_predicate(b["when"], _ctx(state)):
                return b["next"]
    return cur.get("next")


def _check_budgets(manifest: Manifest, state: RunState, step_type: str, took_branch: bool) -> None:
    b = manifest.budgets
    if state.sequence + 1 > b["max_steps"]:
        raise BudgetExhausted(f"max_steps {b['max_steps']} reached")
    if step_type == "AGENT_REASON" and state.agent_reason_count + 1 > b["max_agent_reason"]:
        raise BudgetExhausted(f"max_agent_reason {b['max_agent_reason']} reached")
    if step_type == "EXTERNAL_OPERATION" and state.external_operation_count + 1 > b.get("max_external_operations", 10**9):
        raise BudgetExhausted(f"max_external_operations reached")
    if step_type == "HARNESS_ACTION" and state.harness_action_count + 1 > b.get("max_harness_actions", 10**9):
        raise BudgetExhausted("max_harness_actions reached")
    if took_branch and state.branch_loops + 1 > b["max_branch_loops"]:
        raise BudgetExhausted(f"max_branch_loops {b['max_branch_loops']} reached")


def start_run(manifest: Manifest, run_id: str, input_payload: dict[str, Any], options: dict[str, Any] | None = None) -> RunState:
    """Validate the domain input against the manifest's input_schema and open the run (status=created)."""
    errors = [e.message for e in jsonschema.Draft202012Validator(manifest.raw.get("input_schema") or {"type": "object"}).iter_errors(input_payload)]
    if errors:
        raise SubmissionRejected(["input: " + m for m in sorted(errors)])
    return RunState(run_id=run_id, adapter_id=manifest.adapter_id, input=dict(input_payload), options=dict(options or {}))


#: AUTORESEARCH-SOURCES-AND-HARNESS-V1 (gaps H-02, H-04): what EVERY research step tells the harness about its answer, whatever the
#: adapter — source- and harness-neutral (the source table is TrailSignal's pinned data, served by both MCP servers as a resource)
HARNESS_RECEIPT_RULES = (
    'Answer with adapter_submit(kind="receipt"): ONE HarnessResearchReceiptV1 that validates against output_schema; action_id = harness_action.action_id.',
    "Research with any tools you have; never invent a source, a quote, a date or a number. A page you could not read (login wall, CAPTCHA, rate "
    "limit, region block) is a limitation to report, never to bypass.",
    "sources[].url is the page the evidence is on, as its canonical permalink (routing is by URL: a short link can route to the wrong source); "
    "published_at_if_known is that page's own date (a comment's own date), else null; every timestamp is a full date-time in UTC ending in Z "
    "(2026-09-21T06:15:00Z; never a date alone or a local offset) and every count is a whole number (4, not 4.0).",
    "source_class and evidence_role_claimed come from the source table (resource polymath://trail/source-capabilities.csv); an observation outside a "
    "source's stage, roles or freshness is rejected by admission: a finding, not a failure.",
    "paraphrase_or_excerpt quotes the evidence (at most 600 characters); never record a person's name or handle. Record in each observation's "
    "context the `key: value` tags the step objective names.",
)


def issue_step(manifest: Manifest, state: RunState, *, issued_at: str, evidence_refs: list[dict[str, Any]] | None = None,
               inputs: dict[str, Any] | None = None, hypotheses: list[dict[str, Any]] | None = None,
               registry_snapshot: dict[str, Any] | None = None, harness_action: dict[str, Any] | None = None,
               admitted_evidence_ids: list[str] | None = None) -> tuple[RunState, dict[str, Any]]:
    """Advance to the next step and build its AdapterStepV1 dict (validated). Returns (new_state, step).
    Terminal runs never issue; budget exhaustion raises BudgetExhausted for the caller to record as a typed gap."""
    if state.terminal:
        raise RuntimeError(f"run {state.run_id} is terminal ({state.status})")
    sid = next_step_id(manifest, state)
    if sid is None:
        raise RuntimeError("no successor step — the manifest graph should have reached COMPILE_RESULT")
    took_branch = state.current_step_id is not None and manifest.step(state.current_step_id)["type"] == "BRANCH" \
        and sid != manifest.step(state.current_step_id).get("next")
    spec = manifest.step(sid)
    _check_budgets(manifest, state, spec["type"], took_branch)
    seq = state.sequence + 1
    if spec["type"] == "HARNESS_ACTION":
        if not harness_action:
            raise RuntimeError(f"{sid}: HARNESS_ACTION needs a compiled harness action (no research directive available)")
        assert_valid("harness_action", harness_action)
    context = {"evidence_refs": list(evidence_refs or []), "inputs": dict(inputs or {}), "prior_step_ids": list(state.outputs.keys()),
               "admitted_evidence_ids": list(admitted_evidence_ids or [])}
    if hypotheses:
        context["hypotheses"] = list(hypotheses)
    if registry_snapshot:
        context["registry_snapshot"] = dict(registry_snapshot)
    step = {
        "run_id": state.run_id, "step_id": sid, "step_type": spec["type"], "sequence": seq, "issued_at": issued_at,
        "objective": spec.get("objective") or spec.get("title") or sid,
        "context": context,
        "constraints": list(spec.get("constraints") or []),
        "output_schema": dict(spec.get("output_schema") or (schema("harness_receipt") if spec["type"] == "HARNESS_ACTION" else {"type": "object"})),
        "acceptance_rules": list(spec.get("acceptance_rules") or []) + (list(HARNESS_RECEIPT_RULES) if spec["type"] == "HARNESS_ACTION" else []),
        "external": ({"system": spec["external"]["system"], "operation_kind": spec["external"]["operation_kind"]}
                     if spec["type"] == "EXTERNAL_OPERATION" else None),
        "cognitive_op": spec.get("cognitive_op") or ("theta" if spec["type"] == "AGENT_REASON" and spec.get("theta_op") else None),
        "theta_op": spec.get("theta_op"),
        "harness_action": dict(harness_action) if spec["type"] == "HARNESS_ACTION" else None,
        "expires_at": None,
    }
    assert_valid("adapter_step", step)
    status = {"AGENT_REASON": "awaiting_agent", "HARNESS_ACTION": "awaiting_harness"}.get(spec["type"], "running")
    new = replace(state, status=status, current_step_id=sid, sequence=seq,
                  branch_loops=state.branch_loops + (1 if took_branch else 0),
                  agent_reason_count=state.agent_reason_count + (1 if spec["type"] == "AGENT_REASON" else 0),
                  external_operation_count=state.external_operation_count + (1 if spec["type"] == "EXTERNAL_OPERATION" else 0),
                  harness_action_count=state.harness_action_count + (1 if spec["type"] == "HARNESS_ACTION" else 0))
    return new, step


def _bump_order(order: tuple[str, ...], step_id: str) -> tuple[str, ...]:
    """Acceptance order of step outputs; a step re-entered through a loop moves to the end (newest last)."""
    return tuple(x for x in order if x != step_id) + (step_id,)


def newest_output(state: RunState, key: str) -> Any:
    """The value under `key` on the most recently accepted/executed step output that carries it (top level, or one level down)."""
    for sid in reversed(state.output_order or tuple(state.outputs)):
        out = state.outputs.get(sid)
        if isinstance(out, dict):
            if key in out:
                return out[key]
            for v in out.values():
                if isinstance(v, dict) and key in v:
                    return v[key]
    return None


# ─────────────────────────────────────────────────────────── submissions
def _cited_ids(payload: Any) -> set[str]:
    """Every string under a key that ends with `_ids` (the citation convention of AGENT_REASON output schemas) — except the
    ORIGIN_ID_FIELDS, which name a hypothesis's lineage inside the run and are validated by the ledger, not cited as evidence."""
    out: set[str] = set()
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k in ORIGIN_ID_FIELDS:
                continue
            if k.endswith("_ids") and isinstance(v, list):
                out |= {x for x in v if isinstance(x, str)}
            else:
                out |= _cited_ids(v)
    elif isinstance(payload, list):
        for v in payload:
            out |= _cited_ids(v)
    return out


def _ref_strings(value: Any) -> set[str]:
    """The record ids a `*_refs` value names: a string, a list of strings, or a map of such lists. Object items (a transition's
    `{kind, id}` causes) are the ledger's to check, not this rule's."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {x for x in value if isinstance(x, str)}
    if isinstance(value, dict):
        return set().union(*(_ref_strings(v) for v in value.values() if not isinstance(v, dict)))
    return set()


def _id_values(node: Any) -> set[str]:
    """Every id recorded in a run's outputs: values of `id` / `*_id` keys and items of `*_ids` lists, at any depth."""
    out: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            if (k == "id" or k.endswith("_id")) and isinstance(v, str):
                out.add(v)
            elif k.endswith("_ids") and isinstance(v, list):
                out |= {x for x in v if isinstance(x, str)}
            else:
                out |= _id_values(v)
    elif isinstance(node, list):
        for v in node:
            out |= _id_values(v)
    return out


def run_record_ids(state: RunState, step: dict[str, Any]) -> set[str]:
    """What a `*_refs` value may name (gap A-06): a record THIS run produced or showed the agent — the step's evidence and
    hypotheses, the run's step ids, and every id recorded in its outputs (TrailSignal's record ids among them)."""
    ctx = step.get("context") or {}
    ids = {r.get("id") for r in ctx.get("evidence_refs") or [] if isinstance(r, dict)}
    ids |= {h.get("hypothesis_id") for h in ctx.get("hypotheses") or [] if isinstance(h, dict)}
    ids |= set(state.outputs) | _id_values(state.outputs)
    return {i for i in ids if isinstance(i, str) and i}


def _cited_refs_by_field(payload: Any, out: dict[str, set[str]] | None = None) -> dict[str, set[str]]:
    """Every record id under a key that ends with `_refs` (gap A-06: `*_refs` fields escaped the citation check), by field name (at any
    depth) so a typed field can be checked against its own records (bug hunt B-50)."""
    out = {} if out is None else out
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k.endswith("_refs"):
                out.setdefault(k, set()).update(_ref_strings(v))
            else:
                _cited_refs_by_field(v, out)
    elif isinstance(payload, list):
        for v in payload:
            _cited_refs_by_field(v, out)
    return out


def typed_record_ids(state: RunState, rule: dict[str, Any]) -> dict[str, tuple[list[str], set[str]]]:
    """bug hunt B-50: a manifest may TYPE a `*_refs` field (`config.refs_must_resolve: {"trail_score_refs": ["trail_scores",
    "score_refusals"]}`): it then resolves only against the records found under those output keys (a list of ids, or of records carrying
    their `record_id`) in any step output of the run. -> {field: (output keys, ids)}."""
    typed: dict[str, tuple[list[str], set[str]]] = {}
    for field_name, keys in rule.items():
        keys = [str(k) for k in (keys if isinstance(keys, list) else [keys])]
        ids: set[str] = set()
        for out in state.outputs.values():
            for key in keys:
                value = out.get(key) if isinstance(out, dict) else None
                for item in value if isinstance(value, list) else [value]:
                    rid = item.get("record_id") if isinstance(item, dict) else item
                    if isinstance(rid, str) and rid:
                        ids.add(rid)
        typed[str(field_name)] = (keys, ids)
    return typed


def validate_submission(step: dict[str, Any], payload: Any, *, known_refs: set[str] | None = None,
                        typed_refs: dict[str, tuple[list[str], set[str]]] | None = None) -> list[str]:
    """The step's output_schema + the machine-checkable acceptance invariant: every cited `*_ids` value must be an
    id from context.evidence_refs (an agent may never cite evidence it was not given); with `known_refs`, every `*_refs`
    value must name a record the run produced (gap A-06) — and a field the manifest TYPED (`typed_refs`, bug hunt B-50) only a record
    of its own kind."""
    errors = [("payload/" + "/".join(map(str, e.path)) if e.path else "payload") + ": " + e.message
              for e in sorted(jsonschema.Draft202012Validator(step["output_schema"]).iter_errors(payload),
                              key=lambda e: (list(map(str, e.path)), e.message))]
    refs = step.get("context", {}).get("evidence_refs", [])
    allowed = {r["id"] for r in refs if r.get("kind") not in PRIOR_EVIDENCE_KINDS}
    priors = {r["id"] for r in refs if r.get("kind") in PRIOR_EVIDENCE_KINDS}
    cited = _cited_ids(payload)
    cited_priors = sorted(cited & priors)
    if cited_priors:
        errors.append("registry priors may never be cited as evidence: " + ", ".join(cited_priors[:10]))
    uncited = sorted(cited - allowed - priors) if allowed or cited else []
    if uncited:
        errors.append("cited ids not in context.evidence_refs: " + ", ".join(uncited[:10]))
    if known_refs is not None:
        typed_refs = typed_refs or {}
        by_field = _cited_refs_by_field(payload)
        unknown = sorted(set().union(*(ids for f, ids in by_field.items() if f not in typed_refs)) - known_refs - allowed - priors)
        if unknown:
            errors.append("referenced records this run never produced: " + ", ".join(unknown[:10]))
        for f in sorted(set(typed_refs) & set(by_field)):
            keys, ids = typed_refs[f]
            wrong = sorted(by_field[f] - ids)
            if wrong:
                errors.append(f"{f} may name only {' / '.join(keys)} records of this run ({', '.join(sorted(ids)[:10]) or 'none yet'}), "
                              f"not: {', '.join(wrong[:10])}")
    return errors


def validate_receipt(step: dict[str, Any], payload: Any) -> list[str]:
    """A HARNESS_ACTION answer is a HarnessResearchReceiptV1 for THIS action: provenance shape only (the harness never decides
    what counts as evidence — TrailSignal admission does)."""
    errors = ["payload: " + e for e in validate("harness_receipt", payload)]
    action = step.get("harness_action") or {}
    if isinstance(payload, dict):
        if payload.get("action_id") != action.get("action_id"):
            errors.append(f"receipt action_id {payload.get('action_id')!r} does not match the issued action {action.get('action_id')!r}")
        if payload.get("run_id") != step["run_id"]:
            errors.append("receipt run_id does not match the run")
        # TRAIL PARITY, cross-field (a JSON schema cannot say these; TrailSignal's HarnessResearchReceiptV1 enforces both, and a receipt
        # that broke one ended a real run as TRAIL_REFUSED instead of being handed back to the harness):
        listed = {s.get("source_id") for s in payload.get("sources") or [] if isinstance(s, dict)}
        orphan = sorted({str(o.get("source_id")) for o in payload.get("observations") or [] if isinstance(o, dict) and o.get("source_id") not in listed})
        if orphan:
            errors.append("observations name sources that are not listed: " + ", ".join(orphan[:10]))
        for o in payload.get("observations") or []:
            if isinstance(o, dict) and o.get("hypothesis_relations"):
                unlinked = sorted({str(r.get("hypothesis_id")) for r in o["hypothesis_relations"] if isinstance(r, dict) and r.get("hypothesis_id") not in (o.get("hypothesis_ids") or [])})
                if unlinked:
                    errors.append(f"observation {o.get('observation_id')} states a relation to a hypothesis it does not link: " + ", ".join(unlinked[:5]))
        started, completed = _instant(payload.get("started_at")), _instant(payload.get("completed_at"))
        if started and completed and completed < started:
            errors.append("completed_at precedes started_at")
        errors += _trail_wire_value_errors(payload)
    return errors


#: bug hunt B-03, TRAIL PARITY for values: TrailSignal parses every receipt timestamp as a UTC datetime (its BoundaryModel refuses a
#: naive or non-UTC value; a date alone is naive) and every count as a STRICT integer. This runtime cannot check either through the
#: schema: the `date-time` format goes unchecked without an optional validator package, and JSON Schema's `integer` admits 4.0.
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


def _utc_instant_error(value: str) -> str | None:
    if not _RFC3339.match(value):
        return f"{value[:60]!r} is not an RFC 3339 date-time; write UTC ending in Z, e.g. 2026-09-21T06:15:00Z"
    norm = value[:10] + "T" + value[11:]                                          # RFC 3339 allows `t`, ` ` and `z`; Python's parser wants T and an offset
    t = _instant(norm[:-1] + "+00:00" if norm[-1] in "Zz" else norm)
    if t is None:
        return f"{value!r} is not a valid date-time"
    if t.utcoffset() != _dt.timedelta(0):
        return f"{value!r} is not UTC; convert it and end it with Z"
    return None


def _trail_wire_value_errors(payload: dict[str, Any]) -> list[str]:
    errors = []
    instants = [("started_at", payload.get("started_at")), ("completed_at", payload.get("completed_at"))]
    for n, s in enumerate(payload.get("sources") or []):
        if isinstance(s, dict):
            instants += [(f"sources/{n}/retrieved_at", s.get("retrieved_at")), (f"sources/{n}/published_at_if_known", s.get("published_at_if_known"))]
    for where, value in instants:
        why = _utc_instant_error(value) if isinstance(value, str) else None          # a missing or non-string value is the schema's to report
        if why:
            errors.append(f"payload/{where}: {why}")
    counts = [(f"observations/{n}/metric_if_present/sample_n", (o.get("metric_if_present") or {}).get("sample_n"))
              for n, o in enumerate(payload.get("observations") or []) if isinstance(o, dict) and isinstance(o.get("metric_if_present"), dict)]
    counts += [(f"tool_trace/{n}/query_count", t.get("query_count")) for n, t in enumerate(payload.get("tool_trace") or []) if isinstance(t, dict)]
    # the schema refuses every other float here; an integer-valued one (4.0) is the only one it lets through
    errors += [f"payload/{where}: {value!r} is not an integer; write {int(value)}" for where, value in counts if isinstance(value, float) and value.is_integer()]
    # bug hunt B-19: a class the pinned source table routes only through a `-` row is not a web source (today `first_party`, a
    # participant interview, counted one independence group PER OBSERVATION); a public page declared as one minted a voice per
    # observation — five observations on two pages anchored a lived cluster
    for n, s in enumerate(payload.get("sources") or []):
        if isinstance(s, dict) and s.get("source_class") in _no_web_classes() and re.match(r"(?i)^https?://", str(s.get("url") or "")):
            errors.append(f"payload/sources/{n}/source_class: {s['source_class']!r} is a first-hand source that TrailSignal counts once per "
                          "observation; a public page is not one — declare the class its host routes to (the source table)")
        # bug hunt B-44: TrailSignal routes a URL to the first row (source_id order) whose pattern is its host OR appears ANYWHERE in it,
        # so a real account handle in a path that happens to contain another platform's domain was admitted as that platform's evidence
        routed = _misrouted(str(s.get("url") or "")) if isinstance(s, dict) else None
        if routed:
            errors.append(f"payload/sources/{n}/url: TrailSignal would route this page to {routed[0]} because {routed[1]!r} appears in its path, "
                          "not its host; it cannot be admitted as its own platform's evidence — leave it out and report it as a limitation")
    return errors


@lru_cache(maxsize=1)
def _source_table() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """TrailSignal's PINNED source table as its admission routes it: (source_id, source_class, patterns) of every enabled row, in
    source_id order (the registry compiler sorts the snapshot's source roles by id)."""
    table = Path(__file__).resolve().parents[3] / _GUIDE_FILES[_SOURCES_URI]
    with table.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if str(r.get("enabled") or "").strip().lower() == "true"]
    return tuple(sorted((str(r.get("source_id") or ""), str(r.get("source_class") or ""),
                         tuple(p.strip() for p in str(r.get("domains_or_patterns") or "").split(";") if p.strip())) for r in rows))


@lru_cache(maxsize=1)
def _no_web_classes() -> frozenset[str]:
    """Source classes whose every enabled row in TrailSignal's PINNED source table routes through `-` (no web domain at all)."""
    patterns: dict[str, set[str]] = {}
    for _sid, cls, pats in _source_table():
        patterns.setdefault(cls, set()).update(pats)
    return frozenset(c for c, p in patterns.items() if c and p == {"-"})


def _misrouted(url: str) -> tuple[str, str] | None:
    """(source_id, pattern) when TrailSignal's routing sends `url` to a row none of whose patterns names the url's HOST — the row was
    matched by text elsewhere in the url; None when the url routes on its own host (or by class, or not at all)."""
    if not re.match(r"(?i)^https?://", url):
        return None
    host = re.sub(r"^[a-z]+://", "", url.lower()).split("/", 1)[0].split("@")[-1].split(":")[0]      # TrailSignal's own host_of
    host = host.removeprefix("www.")
    for source_id, _cls, patterns in _source_table():
        concrete = [p for p in patterns if p not in ("*", "-")]
        hit = next((p for p in concrete if host == p or host.endswith("." + p) or p in url), None)
        if hit is not None:
            on_host = any(host == p.split("/", 1)[0] or host.endswith("." + p.split("/", 1)[0]) for p in concrete)
            return None if on_host else (source_id, hit)
    return None


def _instant(value: Any):
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def accept_submission(manifest: Manifest, state: RunState, step: dict[str, Any], submission: dict[str, Any]) -> RunState:
    """Validate an AdapterSubmissionV1 (reasoning or receipt) for the CURRENT awaiting step and record its payload. Anything
    out of order — a duplicate submit, a wrong step, a wrong kind — is rejected with the reason."""
    assert_valid("adapter_submission", submission)
    if state.terminal:
        raise SubmissionRejected([f"run is terminal ({state.status})"])
    expected = {"AGENT_REASON": ("awaiting_agent", "reasoning"), "HARNESS_ACTION": ("awaiting_harness", "receipt")}.get(step["step_type"])
    if expected is None or state.status != expected[0] or step["step_id"] != state.current_step_id or submission["step_id"] != state.current_step_id:
        raise SubmissionRejected([f"step {submission['step_id']!r} is not the awaiting step {state.current_step_id!r}"])
    if submission.get("kind") and submission["kind"] != expected[1]:
        raise SubmissionRejected([f"submission kind {submission['kind']!r} does not fit a {step['step_type']} step (expected {expected[1]!r})"])
    # gap A-06, opt-in per step (manifest data `config.refs_must_resolve`): its `*_refs` values must name records the run produced; a map
    # (bug hunt B-50) also types named fields: each resolves only against the records of the output keys it lists
    refs_rule = (manifest.step(step["step_id"]).get("config") or {}).get("refs_must_resolve")
    errors = (validate_receipt(step, submission["payload"]) if step["step_type"] == "HARNESS_ACTION"
              else validate_submission(step, submission["payload"], known_refs=run_record_ids(state, step) if refs_rule else None,
                                       typed_refs=typed_record_ids(state, refs_rule) if isinstance(refs_rule, dict) else None))
    if errors:
        raise SubmissionRejected(errors)
    # A step id re-entered through a bounded loop is a NEW issuance: its payload may legitimately differ from the earlier pass
    # (the earlier output stays on its own step row + receipt). A duplicate submit of the same issuance is refused above because
    # the run is no longer awaiting once the first one is accepted.
    return replace(state, status="running", steps_accepted=state.steps_accepted + 1,
                   outputs={**state.outputs, step["step_id"]: submission["payload"]}, output_order=_bump_order(state.output_order, step["step_id"]))


def record_automatic_output(state: RunState, step_id: str, output: dict[str, Any]) -> RunState:
    """An automatic step (retrieve/plan/graph/external/validate/branch/compile) executed by the runtime."""
    if state.current_step_id != step_id or state.status != "running":
        raise RuntimeError(f"step {step_id!r} is not the running step {state.current_step_id!r}")
    return replace(state, steps_accepted=state.steps_accepted + 1, outputs={**state.outputs, step_id: output}, output_order=_bump_order(state.output_order, step_id))


def cancel_run(state: RunState) -> RunState:
    """Cancellation is terminal and idempotent; accepted work is never rolled back."""
    if state.terminal:
        return state
    return replace(state, status="cancelled")


#: the gap contract's own bound (adapter_run_status / adapter_result `gap.message` maxLength)
GAP_MESSAGE_MAX = 2000


def terminal_gap(state: RunState, code: str, message: str, step_id: str | None = None) -> RunState:
    if state.terminal:
        return state
    # bug hunt B-02: a gap message is a reason (a refusal, a verdict, an admission error) that can outgrow the gap contract; an unbounded
    # one made every later status / result view of the run raise. Bounded here, head and tail kept, what was elided counted.
    return replace(state, status="terminal_gap", gap={"code": code, "message": bounded_text(message, GAP_MESSAGE_MAX), **({"step_id": step_id} if step_id else {})})


def complete_run(state: RunState) -> RunState:
    if state.status != "running":
        raise RuntimeError(f"cannot complete a run in status {state.status}")
    return replace(state, status="completed")


def run_status_view(manifest: Manifest, state: RunState, *, started_at: str, updated_at: str,
                    terminal_at: str | None = None, agent_identity: str | None = None,
                    identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """The AdapterRunStatusV1 projection of a state (validated). `identity`: the versions the RUN was started under (the caller's
    stored record), else the manifest's. A current step the loaded manifest no longer has (a redeploy renamed or removed it; bug hunt
    B-57) has no type to report: None, never an exception — the run stays readable and cancellable."""
    spec = manifest.steps.get(state.current_step_id) if state.current_step_id else None
    view = {"run_id": state.run_id, **manifest.identity, **{k: v for k, v in (identity or {}).items() if k in manifest.identity and v},
            "status": state.status, "current_step_id": state.current_step_id,
            "current_step_type": spec["type"] if spec else None, "steps_issued": state.sequence,
            "steps_accepted": state.steps_accepted, "branch_loops": state.branch_loops, "harness_actions": state.harness_action_count,
            "started_at": started_at,
            "updated_at": updated_at, "terminal_at": terminal_at, "failure": state.failure, "gap": state.gap,
            "agent_identity": agent_identity}
    assert_valid("adapter_run_status", view)
    return view
