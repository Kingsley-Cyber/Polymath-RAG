"""GOVERNED-CONVERGENCE-V1 TG2 — the cognitive adapter's EVIDENCE BOUNDARY (pure: no I/O, no clock, no network).

Two jobs, one module:

* READABLE evidence (TG2a). An issued AGENT_REASON / HARNESS_ACTION step carries evidence IDS for citation; `hydrate` turns
  exactly those ids back into bounded, readable rows (text, source, role, grade) from the run's STORED step outputs, so the
  connected agent reasons over evidence instead of over identifiers.
* The evidence-boundary knowledge surface (TG2b, opt-in per manifest step). A knowledge step may obtain corpus evidence
  through the orchestrator's evidence route (full planning + Corpus Explore -> EvidencePacket, `synthesis_performed=false`)
  instead of the legacy retrieve lane. This module owns the rules the worker only executes: the orchestrator path
  allow-list, the ORIGINAL-need rule (never a reformulation), one corpus per call with a bounded fan-out, the exact request
  body, the fail-closed packet check, and the packet -> contract-row / evidence-ref mapping.

The adapter never reaches a Polymath SYNTHESIS route: nesting a second synthesis inside an agent's reasoning is the defect
this boundary exists to prevent. The allow-list below is the whole outbound surface of the adapter step worker.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

import jsonschema

#: repository root = .../shared/polymath_shared/adapter/evidence_boundary.py -> parents[3]
_REPO = Path(__file__).resolve().parents[3]
PACKET_SCHEMA_PATH = _REPO / "contracts" / "evidence" / "v1" / "evidence_packet.schema.json"
PACKET_SCHEMA_VERSION = "evidence-packet-v1"

SURFACE_LEGACY = "retrieve"
SURFACE_BOUNDARY = "evidence_boundary"
SURFACES = (SURFACE_LEGACY, SURFACE_BOUNDARY)
#: kill switch: `retrieve` forces the legacy surface on every step, whatever the manifest says (recorded, never silent)
ENV_SURFACE = "POLYMATH_ADAPTER_KNOWLEDGE_SURFACE"
FORCED_BY_ENV = "surface_forced_by_env"

EVIDENCE_PATH = "/chat/evidence"
#: the ONLY orchestrator paths the adapter step worker may POST to
ALLOWED_ORCH_PATHS = frozenset({EVIDENCE_PATH, "/retrieve", "/retrieve/plan"})
BOUNDARY_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD")

DEFAULT_MAX_CALLS = 3
MAX_NEED_CHARS = 2000
DEFAULT_MAX_ROWS = 40
ROW_TEXT_CHARS = 700
UTILITY_ROLES = ("DIRECT", "COMPLEMENTARY", "DIVERGENT", "RELATED")
CA4_GRADES = ("DIRECT", "PARTIAL", "RELATED")
_GRADE_RANK = {g: i for i, g in enumerate(CA4_GRADES)}
REF_KINDS = ("chunk", "document", "graph_fact", "graph_hop")
_ORIGIN = re.compile(r"[A-Z][A-Z0-9_]{0,39}")          # == adapter_step.schema.json evidence_refs[].origin

GAP_CONTRACT_MISMATCH = "EVIDENCE_CONTRACT_MISMATCH"
GAP_SURFACE_UNAVAILABLE = "EVIDENCE_SURFACE_UNAVAILABLE"
ON_UNAVAILABLE = ("gap", "continue")

HYDRATE_MAX_ROWS = 60
HYDRATE_MAX_CHARS = 600
HYDRATE_MAX_RECEIPTS = 12
#: reserved floors per evidence class inside the hydrate cap (sum == HYDRATE_MAX_ROWS; unused floors spill over in this order)
#: so freshly admitted field evidence is never starved by a large graded chunk set, and the reverse.
HYDRATE_BUDGET = {"field_evidence": 24, "chunk": 20, "graph_fact": 10, "other": 6}
HYDRATE_CLASS_ORDER = ("field_evidence", "chunk", "graph_fact", "other")
#: LATER-PASS RESERVATION (restoration reference §8.5): inside a knowledge class at most this share of the slots is reserved for rows
#: a LATER retrieval pass returned (hypothesis-targeted / loop retrieval), newest pass first. The caps do not move. With one pass
#: nothing changes. Without it the stable first-pass order filled every slot and a targeted retrieval was citable but never readable.
RECENT_SHARE = 0.4
KNOWLEDGE_ROW_KEYS = ("rows", "graph_rows")


class PathNotAllowed(ValueError):
    """The adapter step worker tried to reach an orchestrator path outside the allow-list."""


# ─────────────────────────────────────────────────────────── surface selection
def resolve_surface(config: Mapping[str, Any] | None, env: Mapping[str, str] | None = None) -> tuple[str, list[str]]:
    """(surface, degraded_reasons). The default surface is LEGACY: a step opts in with `config.surface`. The env kill switch
    only ever forces legacy, and only a step that asked for the boundary records that it was forced."""
    requested = str((config or {}).get("surface") or SURFACE_LEGACY)
    if requested not in SURFACES:
        raise ValueError(f"unknown knowledge surface {requested!r} (expected one of {', '.join(SURFACES)})")
    forced = str((env or {}).get(ENV_SURFACE) or "").strip().lower() == SURFACE_LEGACY
    if requested == SURFACE_BOUNDARY and forced:
        return SURFACE_LEGACY, [FORCED_BY_ENV]
    return requested, []


def assert_allowed_path(path: str) -> str:
    if path not in ALLOWED_ORCH_PATHS:
        raise PathNotAllowed(f"adapter step worker may not reach {path!r}; allowed: {', '.join(sorted(ALLOWED_ORCH_PATHS))}")
    return path


def user_agent(run_id: str, step_id: str, sequence: int) -> str:
    """Correlates a boundary call with its query receipt (`query_receipts.client`)."""
    return f"polymath-adapter-step/{run_id}/{step_id}/{int(sequence)}"


# ─────────────────────────────────────────────────────────── the ORIGINAL need
def _path(obj: Mapping[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def domain_compiled_need(config: Mapping[str, Any] | None, outputs: Mapping[str, Any] | None, trusted_steps: Iterable[str]) -> str | None:
    """The ONE narrow exception to "a step output never becomes a retrieval need" (restoration reference §9.5): a `source` of the
    form `outputs.<step>.<key>` is honoured only when `<step>` is in `trusted_steps` — the manifest's DOMAIN_OPERATION steps, i.e. a
    need COMPILED BY DETERMINISTIC DOMAIN CODE from admitted field evidence (`K_questions.need`). An agent-answered step is never
    trusted, so an LLM-written reformulation still can not reach the explorer. The runtime resolves this (service.advance); the
    evidence executor itself still never reads a step output."""
    parts = str((config or {}).get("source") or "").split(".")
    if parts[0] != "outputs" or len(parts) < 3 or parts[1] not in set(trusted_steps):
        return None
    value = _path({"outputs": dict(outputs or {})}, ".".join(parts))
    text = " ".join(str(value).split())[:MAX_NEED_CHARS] if isinstance(value, str) else ""
    return text or None


def original_needs(config: Mapping[str, Any] | None, inputs: Mapping[str, Any] | None, options: Mapping[str, Any] | None = None,
                   hypotheses: Iterable[Mapping[str, Any]] | None = None, *, compiled_need: str | None = None) -> list[str]:
    """The information need(s) a boundary step submits: the run's ORIGINAL seed, or — for `query_from: hypotheses` — one need
    per live hypothesis statement (distinct agent-authored needs, in generation order). By construction this never sees a step
    output, so a compiled reformulation can not reach the explorer: Polymath owns retrieval planning, the caller owns the need.
    `compiled_need`: a need the RUNTIME already resolved through `domain_compiled_need` (deterministic domain code only) — when
    present it is the need; otherwise nothing changes."""
    cfg, inp = dict(config or {}), dict(inputs or {})
    needs: list[str] = []
    if cfg.get("query_from") == "hypotheses":
        needs = [str(h.get("statement") or "").strip() for h in hypotheses or []]
    if not any(needs) and isinstance(compiled_need, str) and compiled_need.strip():
        needs = [compiled_need]
    if not any(needs):
        seed = _path({"input": inp, "options": dict(options or {})}, str(cfg["source"])) if cfg.get("source") else None
        if not (isinstance(seed, str) and seed.strip()):
            seed = next((inp[k] for k in ("question", "seed", "seed_idea", "query", "signal", "topic", "problem")
                         if isinstance(inp.get(k), str) and inp[k].strip()), None)
        if not (isinstance(seed, str) and seed.strip()):
            seed = next((v for v in inp.values() if isinstance(v, str) and v.strip()), None)
        needs = [seed] if isinstance(seed, str) else []
    out, seen = [], set()
    for need in needs:
        text = " ".join(str(need or "").split())[:MAX_NEED_CHARS]
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    if not out:
        raise ValueError("no information need in input (set config.source on the step, e.g. input.seed)")
    return out


def plan_calls(needs: list[str], corpus_ids: list[str], *, max_calls: int = DEFAULT_MAX_CALLS) -> dict[str, Any]:
    """One corpus per call (every chat mode is single-corpus), bounded. Order is deterministic: every need against the first
    corpus, then the next corpus — so a tight budget drops whole CORPORA last-first, and what was skipped is recorded."""
    cap = max(1, int(max_calls))
    pairs = [{"need_index": i, "need": need, "corpus_id": cid} for cid in corpus_ids for i, need in enumerate(needs)]
    return {"calls": pairs[:cap],
            "truncated": [{"corpus_id": p["corpus_id"], "need_index": p["need_index"], "reason": "max_calls"} for p in pairs[cap:]]}


#: K1 (R8, register 11.485): Trail ideation reads REFERENCE material only — every evidence request an adapter makes says so,
#: and the orchestrator enforces it on every search of the turn (profile scout, Corpus Explore, every lane)
TRAIL_SCOPE: dict[str, list[str]] = {"roles": ["reference"]}


def request_body(need: str, corpus_id: str, *, mode: str = "WILDCARD", corpus_explorer: bool = True) -> dict[str, Any]:
    """EXACTLY the five fields the evidence route needs: the need, one corpus, the mode, the explorer toggle and the
    reference-only scope (K1). No synthesizer, no history, no pre-decomposed subqueries."""
    m = str(mode or "").upper()
    if m not in BOUNDARY_MODES:
        raise ValueError(f"unknown evidence-boundary mode {mode!r} (expected one of {', '.join(BOUNDARY_MODES)})")
    if not (isinstance(need, str) and need.strip()) or not (isinstance(corpus_id, str) and corpus_id.strip()):
        raise ValueError("an evidence-boundary call needs a non-empty need and exactly one corpus_id")
    return {"message": need, "corpus_id": corpus_id, "mode": m, "corpus_explorer": bool(corpus_explorer),
            "scope": {"roles": list(TRAIL_SCOPE["roles"])}}


# ─────────────────────────────────────────────────────────── the packet contract (consumer side, fail-closed)
@lru_cache(maxsize=1)
def packet_schema() -> dict[str, Any]:
    return json.loads(PACKET_SCHEMA_PATH.read_text())


@lru_cache(maxsize=1)
def _packet_validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(packet_schema())


def check_response(resp: Any) -> list[str]:
    """Violations of the evidence-boundary response contract (empty = lawful). ANY violation is a terminal
    EVIDENCE_CONTRACT_MISMATCH for the caller — a packet that is the wrong version, or that reports a synthesis, is never
    repaired, downgraded to the legacy lane, or partially consumed."""
    if not isinstance(resp, Mapping):
        return ["response is not an object"]
    packet = resp.get("evidence_packet")
    if not isinstance(packet, Mapping):
        return ["response carries no evidence_packet object"]
    errs: list[str] = []
    if packet.get("schema_version") != PACKET_SCHEMA_VERSION:
        errs.append(f"schema_version is {packet.get('schema_version')!r}, expected {PACKET_SCHEMA_VERSION!r}")
    if packet.get("synthesis_performed") is not False:
        errs.append(f"packet.synthesis_performed is {packet.get('synthesis_performed')!r}, expected false")
    if "synthesis_performed" in resp and resp.get("synthesis_performed") is not False:
        errs.append(f"response.synthesis_performed is {resp.get('synthesis_performed')!r}, expected false")
    if errs:
        return errs
    found = sorted(_packet_validator().iter_errors(dict(packet)), key=lambda e: (list(map(str, e.path)), e.message))
    return [("/".join(map(str, e.path)) or "$") + ": " + e.message for e in found][:8]


def _clip(value: Any, n: int) -> str:
    return str(value or "")[: max(0, int(n))]


def rows_from_packet(packet: Mapping[str, Any], corpus_id: str, *, max_text: int = ROW_TEXT_CHARS) -> list[dict[str, Any]]:
    """Packet evidence -> contract-shaped rows (the shape every adapter knowledge step stores), plus the boundary's own
    fields: utility_role, ca4_grade, c4_valid, origin. A packet is single-corpus, so the row's corpus is the call's."""
    rows: list[dict[str, Any]] = []
    for item in packet.get("evidence") or []:
        cid = str(item.get("chunk_id") or "")
        if not cid:
            continue
        prov = item.get("provenance") if isinstance(item.get("provenance"), Mapping) else {}
        full = str(item.get("text") or "")
        # RB5: a packet says whether its text is an excerpt; clipping it further here is said too, never silent
        clipped = len(full) > max(0, int(max_text))
        row: dict[str, Any] = {"id": cid, "kind": "chunk", "doc_id": str(item.get("document_id") or "") or None, "corpus_id": corpus_id,
                               "source": _clip(item.get("source"), 300) or None, "text": _clip(full, max_text),
                               "text_truncated": True if clipped else item.get("text_truncated"),
                               "text_chars": item.get("text_chars") if isinstance(item.get("text_chars"), int) else None,
                               "utility_role": str(item.get("utility_role") or "") or None,
                               "synthesis_role": str(item.get("synthesis_role") or "") or None,
                               "ca4_grade": str(item.get("ca4_grade") or "") or None, "c4_valid": bool(item.get("c4_valid")),
                               "origin": str(item.get("origin") or "") or None,
                               "query_ids": [str(q) for q in (item.get("query_ids") or [])][:8]}
        if prov.get("relation_to_q0"):
            row["relation_to_q0"] = _clip(prov.get("relation_to_q0"), 300)
        rows.append({k: v for k, v in row.items() if v is not None})
    return rows


def _grade_rank(row: Mapping[str, Any]) -> int:
    return _GRADE_RANK.get(str(row.get("ca4_grade") or "").upper(), len(_GRADE_RANK))


def merge_rows(row_lists: Iterable[list[dict[str, Any]]], *, max_rows: int = DEFAULT_MAX_ROWS) -> tuple[list[dict[str, Any]], int]:
    """Union across calls: first occurrence of an id wins, graded rows first (DIRECT, PARTIAL, RELATED, then ungraded),
    stable within a grade. Returns (rows, dropped_by_cap)."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rows in row_lists:
        for r in rows or []:
            rid = str(r.get("id") or "")
            if rid and rid not in seen:
                seen.add(rid)
                merged.append(r)
    merged.sort(key=_grade_rank)                       # list.sort is stable
    cap = max(0, int(max_rows))
    return merged[:cap], max(0, len(merged) - cap)


def refs_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """AdapterStepV1 evidence refs. The four boundary properties are OPTIONAL on the wire and closed-vocabulary: a value
    outside the vocabulary stays on the stored row and is simply not projected onto the ref."""
    refs: list[dict[str, Any]] = []
    for r in rows or []:
        rid, kind = r.get("id"), r.get("kind")
        if not rid or kind not in REF_KINDS:
            continue
        ref: dict[str, Any] = {"kind": kind, "id": str(rid)}
        for k in ("corpus_id", "doc_id"):
            if r.get(k):
                ref[k] = str(r[k])[:200]
        if isinstance(r.get("score"), (int, float)) and not isinstance(r.get("score"), bool):
            ref["score"] = float(r["score"])
        if str(r.get("utility_role") or "").upper() in UTILITY_ROLES:
            ref["utility_role"] = str(r["utility_role"]).upper()
        if str(r.get("ca4_grade") or "").upper() in CA4_GRADES:
            ref["ca4_grade"] = str(r["ca4_grade"]).upper()
        if isinstance(r.get("c4_valid"), bool):
            ref["c4_valid"] = r["c4_valid"]
        origin = str(r.get("origin") or "").upper()
        if _ORIGIN.fullmatch(origin):
            ref["origin"] = origin
        refs.append(ref)
    return refs


def call_record(call: Mapping[str, Any], packet: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What one boundary call is remembered as on the step output (bounded; the packet itself is not stored)."""
    plan = packet.get("plan") if isinstance(packet.get("plan"), Mapping) else {}
    firing = (packet.get("receipts") or {}).get("firing") if isinstance(packet.get("receipts"), Mapping) else None
    grades: dict[str, int] = {}
    for r in rows:
        g = str(r.get("ca4_grade") or "UNGRADED")
        grades[g] = grades.get(g, 0) + 1
    rec = {"need_index": call.get("need_index"), "corpus_id": call.get("corpus_id"),
           "contract": {"schema_version": packet.get("schema_version"), "synthesis_performed": packet.get("synthesis_performed"), "valid": True},
           "retrieval_mode": packet.get("retrieval_mode"), "n_evidence": len(rows), "grades": grades,
           "compiled_queries": len(plan.get("compiled_queries") or []),
           "corpus_explorer_requested": bool(plan.get("corpus_explorer_requested")), "corpus_explorer_used": bool(plan.get("corpus_explorer_used"))}
    if isinstance(firing, Mapping):
        rec["firing"] = {k: firing.get(k) for k in ("requested", "fired", "cause") if k in firing}
    return rec


def unavailable_outcome(policy: str, step_id: str, reason: str) -> dict[str, Any]:
    """The evidence surface (and any configured fallback) could not be reached. `gap` ends the run with a typed gap (a gap is
    always terminal); `continue` succeeds with NO evidence and says so through `unknowns` — never through `knowledge_gaps`,
    which is forwarded to TrailSignal as a research gap and would turn an outage into a field-research instruction."""
    if policy not in ON_UNAVAILABLE:
        raise ValueError(f"unknown on_unavailable policy {policy!r} (expected one of {', '.join(ON_UNAVAILABLE)})")
    if policy == "gap":
        return {"gap": {"code": GAP_SURFACE_UNAVAILABLE, "message": f"{step_id}: {reason}"[:2000]}}
    return {"output": {"surface": SURFACE_BOUNDARY, "rows": [], "calls": [], "retrieval_completed": False, "degraded": True,
                       "degraded_reasons": ["evidence_surface_unavailable"],
                       "unknowns": [{"about": f"corpus evidence for step {step_id} could not be retrieved", "reason": reason[:500],
                                     "step_id": step_id}]},
            "evidence_refs": []}


# ─────────────────────────────────────────────────────────── readable evidence for adapter_next (TG2a)
def _hydrate_class(kind: str) -> str:
    return kind if kind in ("field_evidence", "chunk", "graph_fact") else "other"


def knowledge_passes(outputs: Iterable[Mapping[str, Any] | None]) -> dict[str, int]:
    """row id -> index of the NEWEST retrieval pass that returned it (0 = the first pass). `outputs` = step outputs in run order
    (every step, knowledge or not). A pass is a maximal run of ADJACENT knowledge outputs (an output with a `rows` / `graph_rows`
    key, even an empty one): plan + retrieve + graph of one round are one pass; any other step between two rounds separates them."""
    passes: dict[str, int] = {}
    index, inside = -1, False
    for out in outputs:
        knowledge = isinstance(out, Mapping) and any(k in out for k in KNOWLEDGE_ROW_KEYS)
        if not knowledge:
            inside = False
            continue
        if not inside:
            index, inside = index + 1, True
        for key in KNOWLEDGE_ROW_KEYS:
            for row in out.get(key) or []:
                if isinstance(row, Mapping) and row.get("id"):
                    passes[str(row["id"])] = index
    return passes


def reserve_recent(bucket: list[dict[str, Any]], take: int, passes: Mapping[str, int], *, share: float = RECENT_SHARE) -> list[dict[str, Any]]:
    """`take` items of `bucket` (already in its baseline order). Up to ceil(take x share) slots go to items of a LATER pass, newest
    pass first and baseline order inside a pass; the remaining slots are filled in baseline order. Deterministic; the result keeps
    baseline order, so a run with a single pass gets exactly what it got before."""
    take = max(0, min(int(take), len(bucket)))
    later = [r for r in bucket if passes.get(str(r.get("id")), 0) > 0]
    if not take or not later or take == len(bucket):
        return bucket[:take]
    quota = min(len(later), take, -(-int(take * share * 1000) // 1000))                 # ceil without float drift
    reserved = {str(r["id"]) for r in sorted(later, key=lambda r: -passes[str(r["id"])])[:quota]}     # stable: baseline order inside a pass
    rest = [str(r.get("id")) for r in bucket if str(r.get("id")) not in reserved][: take - len(reserved)]
    chosen = reserved | set(rest)
    return [r for r in bucket if str(r.get("id")) in chosen]


def _index_rows(step_outputs: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """id -> the stored row. Knowledge rows come from `rows` / `graph_rows`; field evidence is rebuilt from a Trail admission
    (`evidence_admission.admitted[]`) joined to the harness receipt it judged (same action_id, same observation_id)."""
    index: dict[str, dict[str, Any]] = {}
    receipts: dict[str, Mapping[str, Any]] = {}
    outs = [o.get("output") for o in step_outputs if isinstance(o.get("output"), Mapping)]
    for out in outs:
        if isinstance(out.get("observations"), list) and out.get("action_id"):
            receipts[str(out["action_id"])] = out
        for key in ("rows", "graph_rows"):
            for row in out.get(key) or []:
                if not (isinstance(row, Mapping) and row.get("id")):
                    continue
                rid = str(row["id"])
                if rid not in index or (_grade_rank(row) < _grade_rank(index[rid])):
                    index[rid] = dict(row)                   # a graded copy of the same chunk beats an ungraded one
    for out in outs:
        adm = out.get("evidence_admission")
        if not isinstance(adm, Mapping):
            continue
        rec = receipts.get(str(adm.get("action_id") or "")) or {}
        obs = {str(o.get("observation_id")): o for o in rec.get("observations") or [] if isinstance(o, Mapping)}
        srcs = {str(s.get("source_id")): s for s in rec.get("sources") or [] if isinstance(s, Mapping)}
        for a in adm.get("admitted") or []:
            if not (isinstance(a, Mapping) and a.get("admitted_evidence_id")):
                continue
            o = obs.get(str(a.get("observation_id"))) or {}
            s = srcs.get(str(a.get("source_id") or o.get("source_id"))) or {}
            text = " — ".join(x for x in (str(o.get("claim") or "").strip(), str(o.get("paraphrase_or_excerpt") or "").strip()) if x)
            row = {"id": str(a["admitted_evidence_id"]), "kind": "field_evidence", "text": text, "source": s.get("url"),
                   "source_class": a.get("source_class") or s.get("source_class"), "evidence_role": a.get("evidence_role"),
                   "polarity": a.get("polarity"), "hypothesis_ids": list(a.get("hypothesis_ids") or []),
                   "independence_group": a.get("independence_group"), "freshness": a.get("freshness"),
                   "published_at_if_known": s.get("published_at_if_known"), "metric_if_present": o.get("metric_if_present")}
            index[row["id"]] = {k: v for k, v in row.items() if v not in (None, "", [])}
    return index


_ROW_KEYS = ("id", "kind", "doc_id", "corpus_id", "title", "source", "heading_path", "text", "text_truncated", "text_chars", "score", "utility_role", "synthesis_role",
             "ca4_grade", "c4_valid", "origin", "relation_to_q0", "source_class", "evidence_role", "polarity", "hypothesis_ids",
             "independence_group", "freshness", "published_at_if_known", "metric_if_present")


def _readable(row: Mapping[str, Any], max_chars: int) -> dict[str, Any]:
    text = str(row.get("text") or row.get("text_clean") or row.get("summary") or "")
    out = {k: row[k] for k in _ROW_KEYS if k in row and k != "text"}
    out["text"] = _clip(text, max_chars)
    if len(text) > max(0, int(max_chars)):
        out["text_truncated"] = True                          # the readable view cut it again: say so
    return out


def _receipt_view(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    out = entry.get("output")
    if not isinstance(out, Mapping) or not any(k in out for k in ("rows", "graph_rows")):
        return None
    view: dict[str, Any] = {"step_id": entry.get("step_id"), "sequence": entry.get("sequence"),
                            "surface": out.get("surface") or SURFACE_LEGACY, "mode": out.get("mode"),
                            "n_rows": len(out.get("rows") or []) + len(out.get("graph_rows") or [])}
    for k in ("query", "needs", "corpus_ids", "retrieval_completed", "degraded", "degraded_reasons", "truncated", "evidence_contract"):
        if out.get(k) not in (None, [], ""):
            view[k] = out[k]
    if isinstance(out.get("queries"), list):
        view["compiled_queries"] = len(out["queries"])
    if isinstance(out.get("calls"), list):
        view["calls"] = list(out["calls"])[:DEFAULT_MAX_CALLS * 2]
    return view


def hydrate(evidence_refs: Iterable[Mapping[str, Any]], step_outputs: Iterable[Mapping[str, Any]], *,
            max_rows: int = HYDRATE_MAX_ROWS, max_chars: int = HYDRATE_MAX_CHARS) -> dict[str, Any]:
    """READABLE evidence for exactly the ids in an issued step's `context.evidence_refs`.

    `step_outputs`: the run's stored steps in sequence order, each `{step_id, sequence, output}` (every bounded-loop pass is
    its own entry, so nothing a loop re-ran is lost). Returns `{rows, receipts, coverage}`: rows are capped at `max_rows`
    x `max_chars`, balanced per evidence class (HYDRATE_BUDGET) and graded-first inside a class; `receipts` say how each
    knowledge step obtained its evidence; `coverage` says how many refs have no readable row, so a cap is never silent."""
    entries = [e for e in step_outputs if isinstance(e, Mapping)]
    index = _index_rows(entries)
    buckets: dict[str, list[dict[str, Any]]] = {c: [] for c in HYDRATE_BUDGET}
    seen: set[str] = set()
    n_refs = unresolved = 0
    for ref in evidence_refs or []:
        rid = str(ref.get("id") or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        n_refs += 1
        row = index.get(rid)
        if row is None:
            unresolved += 1
            continue
        merged = {**{k: ref[k] for k in ("utility_role", "ca4_grade", "c4_valid", "origin") if k in ref}, **row,
                  "kind": row.get("kind") or ref.get("kind")}
        buckets[_hydrate_class(str(merged.get("kind") or ""))].append(merged)
    for c in buckets:
        buckets[c].sort(key=_grade_rank)                      # stable: ref order inside a grade
    cap = max(0, int(max_rows))
    scale = cap / float(HYDRATE_MAX_ROWS) if HYDRATE_MAX_ROWS else 0.0
    take = {c: min(len(buckets[c]), int(HYDRATE_BUDGET[c] * scale)) for c in HYDRATE_BUDGET}
    spare = cap - sum(take.values())
    for c in HYDRATE_CLASS_ORDER:
        if spare <= 0:
            break
        extra = min(spare, len(buckets[c]) - take[c])
        take[c] += extra
        spare -= extra
    passes = knowledge_passes(e.get("output") for e in sorted(entries, key=lambda e: int(e.get("sequence") or 0)))
    picked = {c: (buckets[c][: take[c]] if c == "field_evidence" else reserve_recent(buckets[c], take[c], passes)) for c in HYDRATE_CLASS_ORDER}
    rows = []
    for c in HYDRATE_CLASS_ORDER:
        for r in picked[c]:
            view = _readable(r, max_chars)
            if passes.get(str(r.get("id")), 0) > 0:
                view["retrieval_pass"] = passes[str(r["id"])]          # a row a LATER (targeted / loop) retrieval returned
            rows.append(view)
    receipts = [v for v in (_receipt_view(e) for e in entries) if v][-HYDRATE_MAX_RECEIPTS:]
    return {"rows": rows, "receipts": receipts,
            "coverage": {"refs": n_refs, "readable": n_refs - unresolved, "returned": len(rows), "unresolved": unresolved,
                         "max_rows": cap, "max_chars": int(max_chars)},
            "allocation": {"passes": (max(passes.values()) + 1 if passes else 0), "recent_share": RECENT_SHARE,
                           "later_pass_rows": sum(1 for r in rows if r.get("retrieval_pass"))}}
