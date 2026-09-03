"""extraction-observability-v1 (ADR: OBSERVABILITY gate 2026-08-16).

The observer records what the extraction system did; it decides
nothing. Provider-neutral, semantic-logic-neutral, never sees
evaluator gold. Timing fields exist for operations only and NEVER
participate in semantic hashes.

Modes (POLYMATH_EXTRACTION_TRACE):
  off     — no collection; semantic path untouched, byte-identical
  summary — funnel counters + reason distributions + first-loss only
  full    — complete event chains (debug/qualification/probes)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

OBSERVER_CONTRACT_VERSION = "extraction-observability-v1"

# ---- reason codes (stable, machine-readable) ----------------------------

DISCOVERY = {
    "GLINER_PROPOSED", "GLINER_NO_PROPOSAL", "GLINER_BELOW_THRESHOLD",
    "GLINER_PARTIAL_BOUNDARY", "GLINER_TYPE_CONFLICT", "GLINER_LABEL_UNMAPPED",
}
SYNTAX = {
    "SPACY_NOUN_CHUNK_FOUND", "SPACY_NO_ARGUMENT_NP",
    "DEPENDENCY_ARGUMENT_FOUND", "DEPENDENCY_ARGUMENT_AMBIGUOUS",
}
RESCUE = {
    "RESCUE_NOT_REQUIRED", "RESCUE_NOT_ELIGIBLE", "RESCUE_QUERY_CREATED",
    "RESCUE_NO_PREDICTION", "RESCUE_PARTIAL_SPAN", "RESCUE_TYPE_ILLEGAL",
    "RESCUE_ACCEPTED", "BOUNDARY_UNRESOLVED",
}
ADMISSION = {
    "ADMITTED_GLOBAL", "ADMITTED_CORPUS_SCOPED", "ADMITTED_DOCUMENT_SCOPED",
    "ADMITTED_MENTION_ONLY",
}
TRIGGER = {
    "NO_LEXICAL_TRIGGER", "TRIGGER_FOUND", "TRIGGER_AMBIGUOUS",
    "TRIGGER_OUTSIDE_ARGUMENT_WINDOW", "TRIGGER_PREDICATE_UNSUPPORTED",
}
ARGUMENT_BINDING = {
    "SUBJECT_FOUND", "SUBJECT_ENDPOINT_UNAVAILABLE", "SUBJECT_MENTION_ONLY",
    "SUBJECT_TYPE_INCOMPATIBLE", "OBJECT_FOUND", "OBJECT_ENDPOINT_UNAVAILABLE",
    "OBJECT_MENTION_ONLY", "OBJECT_TYPE_INCOMPATIBLE",
    "ARGUMENT_DISTANCE_EXCEEDED", "ARGUMENT_CROSSES_SENTENCE_SCOPE",
    "ARGUMENT_BINDING_AMBIGUOUS", "COORDINATION_EXPANDED",
    "COORDINATION_AMBIGUOUS",
}
CANDIDATE = {
    "CANDIDATE_CREATED", "CANDIDATE_NOT_CREATED", "DUPLICATE_CANDIDATE_SUPPRESSED",
}
COMPILER = {
    "FRAME_MATCH", "FRAME_MISMATCH", "TYPE_SIGNATURE_MATCH",
    "TYPE_SIGNATURE_MISMATCH", "NEGATED", "MODAL", "CONDITIONAL",
    "VOICE_NORMALIZED", "SURFACE_WEAK", "E3B_REJECTED",
    "COMPILER_ACCEPTED", "COMPILER_REJECTED", "AMBIGUOUS_PREDICATE",
    "UNSUPPORTED_PREDICATE",
}
FACT = {
    "FACT_ACCEPTED", "FACT_DUPLICATE_NOOP", "FACT_REJECTED",
    "GRAPH_ELIGIBLE", "GRAPH_INELIGIBLE_MENTION_ONLY",
    "GRAPH_INELIGIBLE_DOCUMENT_SCOPED",
}

# -- kimi_v1 lane (ADR-0016 Phase 5) --------------------------------------
# The realigned pipeline binds arguments from the UD tree, assigns
# PropBank roles, and applies the type pre-check AFTER structure exists.
# Each step needs its own vocabulary so a terminal outcome is explained by
# the step that actually produced it (qualification criterion #14). The
# legacy_v1 lane never emits these codes.
UD_BINDING = {
    "UD_SUBJECT_BOUND", "UD_OBJECT_BOUND", "UD_OBLIQUE_BOUND",
    "UD_NO_ARGUMENT_IN_SLOT",
}
ROLE = {
    "ROLE_ARG0_ASSIGNED", "ROLE_ARG1_ASSIGNED", "ROLE_ARG2_ASSIGNED",
    "ROLE_ASSIGNED", "ROLE_NO_ROLESET", "ROLE_ORIENTATION_INCOMPLETE",
}
TYPE_PRECHECK = {
    "TYPE_PRECHECK_PASS", "TYPE_PRECHECK_FAIL",
    "TYPE_PRECHECK_IMPOSSIBLE", "TYPE_PRECHECK_NO_VIABLE_PAIR",
}

ALL_CODES = (DISCOVERY | SYNTAX | RESCUE | ADMISSION | TRIGGER
             | ARGUMENT_BINDING | CANDIDATE | COMPILER | FACT
             | UD_BINDING | ROLE | TYPE_PRECHECK)

# Non-terminal step outcomes. They explain the PATH a trigger took and
# must never enter the first-loss distribution, because the pipeline
# continues past every one of them: an empty UD slot still goes to bounded
# linear recall, and one type-rejected pair still leaves the other pairs.
# Only the codes NOT listed here end a trigger's life -- notably
# TYPE_PRECHECK_NO_VIABLE_PAIR, which fires once every pair has failed.
STEP_CODES = (UD_BINDING | ROLE | TYPE_PRECHECK) - {
    "TYPE_PRECHECK_NO_VIABLE_PAIR",
}

FIRST_LOSS_STAGES = (
    "chunking", "gliner_discovery", "syntax_alignment", "rescue",
    "admission", "trigger", "ud_binding", "argument_binding",
    "role_assignment", "type_precheck", "candidate_generation",
    "frame", "type_signature", "negation_modality", "compiler",
    "fact_persistence", "graph_projection",
)

# -- fallback discipline (ADR-0016 directive Phase 17) --------------------
# `BindingSource` (contracts.py) names the specific MECHANISM that bound an
# argument; the directive names three DISCIPLINE TIERS. Both vocabularies
# are real, so this is the explicit mapping between them rather than a
# rename of the enum.
UD_PRIMARY = "UD_PRIMARY"
SAFE_FALLBACK = "SAFE_FALLBACK"
BOUNDED_RECALL = "BOUNDED_RECALL"
BINDING_DISCIPLINE = {
    "UD_DIRECT": UD_PRIMARY,
    "UD_PREPOSITIONAL": UD_PRIMARY,
    "UD_PASSIVE": UD_PRIMARY,
    "UD_COORDINATION": UD_PRIMARY,
    "SAFE_LOCAL_PATTERN": SAFE_FALLBACK,
    "BOUNDED_LINEAR_RECALL": BOUNDED_RECALL,
    "UD_DEPENDENCY": UD_PRIMARY,
    "NOMINAL_DEPENDENCY": UD_PRIMARY,
    "CONTROL_SUBJECT": UD_PRIMARY,
    "CONTROL_OBJECT": UD_PRIMARY,
    "DISCOURSE_ANAPHORA": SAFE_FALLBACK,
    # SPOKEN-RELATION-ADAPTER-V1: antecedent recovery follows explicit
    # dependency edges (relcl head, copular equation) — tree evidence,
    # not a recall window.
    "RELCL_ANTECEDENT": UD_PRIMARY,
}


def binding_discipline(source) -> str:
    """Map a BindingSource (enum or bare string) to its directive tier.

    Unknown sources degrade to BOUNDED_RECALL: the observer never claims
    stronger provenance than it can prove."""
    return BINDING_DISCIPLINE.get(str(getattr(source, "value", source)),
                                  BOUNDED_RECALL)


def event_id(payload: dict) -> str:
    return "tev_" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:40]


@dataclass
class TraceEvent:
    event_type: str                 # discovery|syntax|rescue|admission|trigger|binding|candidate|compiler|fact
    decision: str                   # code from the enums above
    reason_code: str
    run_id: str = ""
    doc_id: str = ""
    chunk_id: str = ""
    sentence_id: str = ""
    surface: str = ""
    char_start: int | None = None
    char_end: int | None = None
    detail: dict = field(default_factory=dict)
    parent_id: str = ""
    duration_ms: float | None = None  # operational only; never hashed

    def envelope(self, contracts: dict) -> dict:
        base = {
            "observer_contract_version": OBSERVER_CONTRACT_VERSION,
            "event_type": self.event_type,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "run_id": self.run_id, "doc_id": self.doc_id,
            "chunk_id": self.chunk_id, "sentence_id": self.sentence_id,
            "trace_parent_id": self.parent_id,
            "surface": self.surface,
            "char_start": self.char_start, "char_end": self.char_end,
            "detail": self.detail,
            **contracts,
        }
        ev = {"trace_event_id": event_id(base), **base}
        if self.duration_ms is not None:
            ev["duration_ms"] = self.duration_ms  # post-hash, operational
        return ev


SUMMARY_EVENT_TYPES = {"candidate", "compiler", "fact", "first_loss", "admission", "rescue"}


class TraceCollector:
    """In-memory collector; ONE batch persist per stage attempt. No
    per-event commits. Modes: off collects nothing."""

    def __init__(self, mode: str, run_id: str, contracts: dict | None = None):
        self.mode = mode
        self.run_id = run_id
        self.contracts = contracts or {}
        self.events: list[dict] = []
        self.timings: dict[str, float] = {}
        self._t0: dict[str, float] = {}
        self._counts: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return self.mode in ("summary", "full")

    @property
    def full(self) -> bool:
        return self.mode == "full"

    def record(self, **kwargs) -> None:
        if not self.enabled:
            return
        if not self.full and kwargs.get("event_type") not in SUMMARY_EVENT_TYPES:
            return  # summary mode: terminal decisions only
        ev = TraceEvent(run_id=self.run_id, **kwargs)
        self.events.append(ev.envelope(self.contracts))

    def count(self, key: str, n: int = 1) -> None:
        if self.enabled:
            self._counts[key] = self._counts.get(key, 0) + n

    def stage_start(self, name: str) -> None:
        self._t0[name] = time.perf_counter()

    def stage_end(self, name: str) -> None:
        if name in self._t0:
            self.timings[name] = round((time.perf_counter() - self._t0.pop(name)) * 1000, 2)

    def flush(self, conn) -> int:
        """Batch persist all events; returns rows written (0 when off)."""
        if not self.events:
            return 0
        rows = [
            (e["trace_event_id"], self.run_id, e["doc_id"], e["chunk_id"],
             e["sentence_id"], e["event_type"], e["decision"], e["reason_code"],
             e["surface"], e.get("char_start"), e.get("char_end"),
             json.dumps(e, default=str))
            for e in self.events
        ]
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO extraction_trace_events
                    (trace_event_id, run_id, doc_id, chunk_id, sentence_id,
                     event_type, decision, reason_code, surface,
                     char_start, char_end, envelope)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (trace_event_id) DO NOTHING
                """,
                rows,
            )
            inserted = cur.rowcount
        # ON CONFLICT DO NOTHING means attempted != inserted. Reporting
        # len(rows) here made the stage artifact claim events that the
        # table had silently deduplicated away.
        written = inserted if inserted is not None and inserted >= 0 else len(rows)
        self.events = []
        return written

    def funnel(self) -> dict:
        return {
            "counts": getattr(self, "_counts", {}),
            "reason_distribution": self._reason_distribution(),
            "first_loss": self._first_loss_distribution(),
            "timings_ms": self.timings,
            "events": len(self.events),
        }

    def _reason_distribution(self) -> dict:
        dist: dict[str, int] = {}
        for e in self.events:
            dist[e["reason_code"]] = dist.get(e["reason_code"], 0) + 1
        return dict(sorted(dist.items(), key=lambda kv: -kv[1]))

    def _first_loss_distribution(self) -> dict:
        dist: dict[str, int] = {}
        for e in self.events:
            if e["event_type"] == "first_loss":
                stage = e["detail"].get("first_loss_stage", "unknown")
                dist[stage] = dist.get(stage, 0) + 1
        return dist


def trace_mode() -> str:
    import os
    return os.environ.get("POLYMATH_EXTRACTION_TRACE", "off")


def extraction_contracts() -> dict:
    """Identity fields pinned into every envelope (§2)."""
    from polymath_shared.query_policy import QUERY_POLICY_VERSION
    from polymath_shared.settings import get_settings
    from polymath_shared.execution import _build_sha

    s = get_settings()
    return {
        "extraction_contract_hash": "pinned-per-stage-attempt",
        "chunk_contract_hash": s.worker.chunker,
        "query_policy_version": QUERY_POLICY_VERSION,
        # Without this, legacy_v1 and kimi_v1 runs of the SAME corpus at the
        # same pack produce byte-identical envelopes, so the second arm's
        # events collide on trace_event_id and are dropped by ON CONFLICT.
        # An A/B then reads as if one arm emitted nothing.
        "relation_pipeline": os.environ.get("POLYMATH_RELATION_PIPELINE", "legacy_v1"),
        "worker_build_sha": _build_sha(),
    }
