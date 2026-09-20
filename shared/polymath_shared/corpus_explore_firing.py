"""CORPUS-EXPLORE-FIRING-V1 — miss attribution for Corpus Explore (pure).

CORPUS-EXPLORER-V1 shipped fail-open: every gate that closes returns silently, so a request that asked
for Corpus Explore and did not get it looks identical to one that never asked. CE7 measured 14/18 firing
and could not say WHY the other four did not fire. This module makes every non-firing request carry
exactly ONE cause code — the FIRST gate that closed, in pipeline order — so the miss rate is attributable
and no fallback is silent.

Pure: `classify` is a total function of a flat `FiringState` (the live path in
`orchestrator/api/ui.py::_add_corpus_explore_expansion` only fills the state in). It changes no gate, no
threshold, no ranking — it observes. "fired" means the explorer ADDED >=1 CORPUS_EXPLORE subquery to a
plan whose retrieval then ran; an activation set that produced no subquery is a miss, not a fire.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass

CONTRACT = "corpus-explore-firing-v1"

CAPABILITY_OFF = "CAPABILITY_OFF"                  # server capability POLYMATH_CORPUS_EXPLORER != 1
REQUEST_OFF = "REQUEST_OFF"                        # the request did not ask for Corpus Explore
PLAN_FALLBACK = "PLAN_FALLBACK"                    # the chat compiler fell back (the gate skips fallback plans)
INTENT_INELIGIBLE = "INTENT_INELIGIBLE"            # plan.intent not in LATENT_INTENTS
ATOMS_EMPTY = "ATOMS_EMPTY"                        # atoms exist, search returned none
ATOMS_ERROR_OR_TIMEOUT = "ATOMS_ERROR_OR_TIMEOUT"  # embed / qdrant raised or timed out
NO_ATOM_COVERAGE = "NO_ATOM_COVERAGE"              # no CONCEPT/THEORY atoms to search (coverage audit's job)
CANDIDATES_FILTERED = "CANDIDATES_FILTERED"        # hits aggregated to zero candidates
BRIDGE_COMPILE_EMPTY = "BRIDGE_COMPILE_EMPTY"      # the bridge model returned nothing (or raised)
BRIDGE_JSON_INVALID = "BRIDGE_JSON_INVALID"        # the bridge model returned unparseable output
SUBQUERY_DROPPED = "SUBQUERY_DROPPED"              # bridges generated, none survived validation / dedup
OTHER = "OTHER"                                    # anything else — `detail` says what

CAUSES: tuple[str, ...] = (
    CAPABILITY_OFF, REQUEST_OFF, PLAN_FALLBACK, INTENT_INELIGIBLE, ATOMS_EMPTY, ATOMS_ERROR_OR_TIMEOUT,
    NO_ATOM_COVERAGE, CANDIDATES_FILTERED, BRIDGE_COMPILE_EMPTY, BRIDGE_JSON_INVALID, SUBQUERY_DROPPED, OTHER,
)

JSON_OK = "ok"
JSON_EMPTY_OUTPUT = "empty_output"
JSON_INVALID = "invalid_json"

#: Phase B (proven cause). A chat-compiler FALLBACK plan is "grounded QA on the raw message": it still has a
#: q0 PRIMARY and a deterministic intent, and its retrieval runs. The explorer used to skip EVERY fallback
#: plan, so a compiler transport blip (all lanes timed out / 429) silently cost the turn its exploration —
#: the measured intermittent miss. Fallback reasons split in two:
#:   NO JUDGMENT  — the compiler said nothing usable (unreachable, too late, unparseable). Nothing argues
#:                  against exploring; the explorer may run (exactly as the Scout BRIDGE expansion always has).
#:   INVALID JUDGMENT (`invalid_plan:*`) — the compiler DID answer and the answer failed validation (e.g.
#:                  `no_queries_for_retrieval`, a non-latent task type). That is a signal; stay closed.
NO_JUDGMENT_FALLBACK_PREFIXES: tuple[str, ...] = (
    "transport:", "budget_exceeded:", "invalid_json", "compiler_unavailable:", "join_failed:")
FALLBACK_OPEN_ENV = "POLYMATH_CORPUS_EXPLORER_FALLBACK_OPEN"   # kill switch; default off = pre-fix gate


def fallback_open_enabled() -> bool:
    return os.environ.get(FALLBACK_OPEN_ENV, "0") == "1"


def fallback_blocks_explorer(reason: str | None, *, fallback_open: bool | None = None) -> bool:
    """Does this fallback plan keep the explorer closed? With the switch off: always (the pre-fix gate).
    With it on: only an INVALID-JUDGMENT fallback blocks; a NO-JUDGMENT fallback lets the explorer run.
    An unknown / missing reason blocks (fail closed). Pure."""
    if fallback_open is None:
        fallback_open = fallback_open_enabled()
    if not fallback_open:
        return True
    r = (reason or "").strip()
    return not any(r.startswith(p) for p in NO_JUDGMENT_FALLBACK_PREFIXES)


@dataclass
class FiringState:
    """Flat gate state, filled in along the live path. `None` = the stage was never reached."""
    capability_on: bool = False
    requested: bool = False
    plan_present: bool = True
    plan_fallback: bool = False
    fallback_reason: str | None = None
    fallback_blocks: bool = True            # does this fallback keep the explorer closed? (Phase B)
    has_primary: bool = True
    no_primary_reason: str | None = None    # e.g. retrieval_not_required:TRANSFORM_USER_CONTENT
    upstream_error: str | None = None       # a plan-finish step BEFORE the explorer raised (type name)
    no_corpus: bool = False
    stage: str | None = None                # embed | search | expand — where the explorer currently is
    atoms_error: str | None = None          # embed / qdrant exception (type name)
    fetch_errors: int = 0                   # per-corpus fetches that raised (swallowed by activate_corpus)
    n_hits: int | None = None
    atom_universe: int | None = None        # CONCEPT/THEORY atoms available to search (None = unknown)
    n_candidates: int | None = None
    intent: str | None = None
    eligible: bool | None = None
    eligible_reason: str | None = None
    generate_error: str | None = None       # the bridge model call raised (type name)
    json_status: str | None = None          # ok | empty_output | invalid_json
    generated: int | None = None
    admitted: int | None = None
    added: int | None = None
    explorer_error: str | None = None       # an unexpected exception inside the explorer (type name)
    retrieval_skipped: bool = False         # the turn skipped retrieval, so added subqueries never ran


def classify(s: FiringState) -> tuple[bool, str | None, str | None]:
    """(fired, cause, detail). Total + deterministic: returns the FIRST closed gate in pipeline order, so a
    non-firing request has exactly one cause and a firing request has none."""
    if not s.capability_on:
        return False, CAPABILITY_OFF, None
    if not s.requested:
        return False, REQUEST_OFF, None
    if not s.plan_present:
        return False, OTHER, "no_plan"
    if s.plan_fallback and s.fallback_blocks:
        return False, PLAN_FALLBACK, (s.fallback_reason or None)
    if not s.has_primary:
        # q0 AUTHORITY (by design): the compiler routed the turn as no-retrieval, so there is no q0 retrieval
        # to supplement. An expansion never CREATES retrieval where the compiler decided none.
        return False, OTHER, ("no_primary" + (f":{s.no_primary_reason}" if s.no_primary_reason else ""))
    if s.upstream_error:
        return False, OTHER, f"finish_error:{s.upstream_error}"
    if s.no_corpus:
        return False, OTHER, "no_corpus"
    if s.atoms_error:
        return False, ATOMS_ERROR_OR_TIMEOUT, f"{s.stage or 'atoms'}:{s.atoms_error}"
    if s.n_hits is None:
        # the explorer never produced a hit count: it raised before/around activation, or was never entered
        return False, OTHER, (f"explorer_error:{s.explorer_error}" if s.explorer_error else "not_attempted")
    if s.n_hits == 0:
        if s.fetch_errors:
            return False, ATOMS_ERROR_OR_TIMEOUT, f"fetch_errors:{s.fetch_errors}"
        if s.atom_universe == 0:
            return False, NO_ATOM_COVERAGE, "atom_universe:0"
        return False, ATOMS_EMPTY, (None if s.atom_universe is None else f"atom_universe:{s.atom_universe}")
    if not s.n_candidates:
        return False, CANDIDATES_FILTERED, f"hits:{s.n_hits}"
    if s.explorer_error:
        return False, OTHER, f"explorer_error:{s.explorer_error}"
    if s.eligible is False:
        reason = s.eligible_reason or "ineligible"
        if reason == "intent_not_latent":
            return False, INTENT_INELIGIBLE, f"intent:{s.intent or ''}"
        if reason == "no_nominated_concepts":
            return False, CANDIDATES_FILTERED, reason
        return False, OTHER, reason
    if s.generate_error:
        return False, BRIDGE_COMPILE_EMPTY, f"generate_error:{s.generate_error}"
    if s.json_status == JSON_INVALID:
        return False, BRIDGE_JSON_INVALID, None
    if not s.generated:
        return False, BRIDGE_COMPILE_EMPTY, (s.json_status or None)
    if not s.added:
        return False, SUBQUERY_DROPPED, f"generated:{s.generated} admitted:{s.admitted or 0}"
    if s.retrieval_skipped:
        return False, OTHER, "retrieval_skipped"
    return True, None, None


def firing_receipt(s: FiringState) -> dict:
    """The bounded receipt surfaced beside `corpus_activation` and inside the EvidencePacket."""
    fired, cause, detail = classify(s)
    stages = {k: v for k, v in asdict(s).items()
              if k in ("intent", "n_hits", "atom_universe", "n_candidates", "eligible", "json_status",
                       "generated", "admitted", "added", "fetch_errors") and v is not None}
    if s.plan_fallback:
        # a fire ON a fallback plan is visible as such (the Phase B path), never mistaken for a normal fire
        stages["plan_fallback"] = s.fallback_reason or True
    return {"contract": CONTRACT, "requested": bool(s.requested), "fired": fired,
            "cause": cause, "detail": detail, "stages": stages}


def record(receipt: dict, *, q0: str = "") -> None:
    """Best-effort JSONL append of every REQUESTED turn's firing receipt, so the miss RATE is countable
    across turns (no silent fallback). Never raises; never records un-requested turns (noise)."""
    try:
        if not (receipt or {}).get("requested"):
            return
        import hashlib
        import json
        import time
        path = os.environ.get("POLYMATH_CE_FIRING_RECEIPT",
                              "/private/tmp/polymath_fleet/corpus_explore_firing.jsonl")
        row = {"ts": round(time.time(), 3), "q0_sha": hashlib.sha1((q0 or "").encode()).hexdigest()[:12],
               "fired": receipt.get("fired"), "cause": receipt.get("cause"), "detail": receipt.get("detail"),
               "stages": receipt.get("stages")}
        with open(path, "a") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001
        pass


def summarize(rows) -> dict:
    """Cause table over receipts: {n, fired, firing_rate, causes{cause: count}}. Pure."""
    rows = [r for r in (rows or ()) if isinstance(r, dict) and r.get("requested", True)]
    causes: dict[str, int] = {}
    fired = 0
    for r in rows:
        if r.get("fired"):
            fired += 1
        else:
            c = r.get("cause") or OTHER
            causes[c] = causes.get(c, 0) + 1
    n = len(rows)
    return {"n": n, "fired": fired, "firing_rate": (round(fired / n, 3) if n else None),
            "causes": dict(sorted(causes.items(), key=lambda kv: (-kv[1], kv[0])))}


def turn_receipt(plan_receipt, *, capability_on: bool, requested: bool, compiler_applied: bool,
                 retrieval_skipped: bool, compiler_flag: str = "on") -> dict:
    """The TURN-level receipt. `plan_receipt` is the explorer's plan-level receipt (or None when the turn
    compiled no plan). A plan-level miss keeps its cause (first closed gate). A plan-level fire is still a
    turn-level MISS when the plan never reached retrieval (a non-`on` compiler flag) or the turn skipped
    retrieval — the added subqueries never ran. Pure."""
    if not isinstance(plan_receipt, dict):
        rec = firing_receipt(FiringState(capability_on=capability_on, requested=requested, plan_present=False))
        if rec["cause"] == OTHER:
            rec["detail"] = f"no_plan:compiler_flag={compiler_flag}"
        return rec
    rec = dict(plan_receipt)
    if rec.get("fired"):
        if not compiler_applied:
            rec.update({"fired": False, "cause": OTHER, "detail": f"compiler_not_applied:{compiler_flag}"})
        elif retrieval_skipped:
            rec.update({"fired": False, "cause": OTHER, "detail": "retrieval_skipped"})
    return rec
