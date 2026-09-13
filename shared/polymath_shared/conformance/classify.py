"""The classification vocabulary. One state per discovered component.

The ordering matters: `NOT_TESTED` and `UNKNOWN` must never render as success, because
an audit that reports "no evidence" as green is worse than no audit — it launders
ignorance into confidence.
"""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    WORKING_PROVEN = "WORKING_PROVEN"            # live + observed + contract + pipeline/E2E
    WORKING_UNQUALIFIED = "WORKING_UNQUALIFIED"  # functional, qualification evidence missing
    CONFIGURED_IDLE = "CONFIGURED_IDLE"          # valid + reachable, no current workload
    BROKEN_REACHABLE = "BROKEN_REACHABLE"        # callable but fails its contract
    SHADOWED = "SHADOWED"                        # exists, but another impl owns live traffic
    LEGACY_REQUIRED = "LEGACY_REQUIRED"          # old, still has proven readers / rollback need
    RETIRE_CANDIDATE = "RETIRE_CANDIDATE"        # replacement exists, proof incomplete
    DEAD_PROVEN = "DEAD_PROVEN"                  # zero dependency, safe to remove
    NOT_TESTED = "NOT_TESTED"
    UNKNOWN = "UNKNOWN"


#: States that may be rendered as success by any consumer (UI, CI, report).
GREEN = frozenset({State.WORKING_PROVEN})

#: States that are acceptable but explicitly NOT success.
AMBER = frozenset({State.WORKING_UNQUALIFIED, State.CONFIGURED_IDLE,
                   State.LEGACY_REQUIRED, State.RETIRE_CANDIDATE, State.SHADOWED})

#: States that are failures or absence of evidence. NOT_TESTED lives here deliberately.
RED = frozenset({State.BROKEN_REACHABLE, State.NOT_TESTED, State.UNKNOWN})


def is_green(state: State | str) -> bool:
    return State(state) in GREEN


def severity(state: State | str) -> str:
    s = State(state)
    return "green" if s in GREEN else ("amber" if s in AMBER else "red")


class Level(str, Enum):
    """Proof depth. A PASS at one level says nothing about the levels above it."""
    IMPLEMENTED = "IMPLEMENTED"                  # code exists
    WIRED = "WIRED"                              # reachable from an entrypoint/scheduler
    LIVE = "LIVE"                                # present in the running system
    OBSERVED = "OBSERVED"                        # has actually executed, with evidence
    CONTRACT_QUALIFIED = "CONTRACT_QUALIFIED"    # meets its function contract
    PIPELINE_QUALIFIED = "PIPELINE_QUALIFIED"    # ticket -> ... -> projection -> readiness
    E2E_QUALIFIED = "E2E_QUALIFIED"              # upload -> query -> evidence -> answer


LEVEL_ORDER = [Level.IMPLEMENTED, Level.WIRED, Level.LIVE, Level.OBSERVED,
               Level.CONTRACT_QUALIFIED, Level.PIPELINE_QUALIFIED, Level.E2E_QUALIFIED]


def highest(levels: set[Level] | set[str]) -> Level | None:
    got = {Level(l) for l in levels}
    for lvl in reversed(LEVEL_ORDER):
        if lvl in got:
            return lvl
    return None


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"
    NOT_TESTED = "NOT_TESTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


#: The permanent function contracts. Models qualify AGAINST these; the functions do not
#: adapt to individual models. `parent_enrichment` is deliberately absent — it is
#: transitional/legacy unless repo evidence proves otherwise (see discovery.legacy_scan).
PERMANENT_FUNCTIONS = ("GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT")
